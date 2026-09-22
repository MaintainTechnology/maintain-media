"""Read bounded pages of accepted source rows, independently of lead qualification.

Parquet footers locate the requested row groups without scanning earlier records.
Only publisher fields are projected. Collection, enrichment and review authority
are never created by browsing a snapshot.
"""

from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from abr_engine.control.service import DomainError, json_safe
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError
from abr_engine.ingest.qbcc_review import _ordinary_path
from abr_engine.live.source_query import FIELDS, filtered_page, normalized_filters, normalized_sort
from abr_engine.pipeline import safe_root

PAGE_SIZE = 50
MAX_OFFSET = 100_000_000


def _snapshot(conn, settings, source, requested_run):
    if requested_run == "latest":
        row = conn.execute(
            "SELECT s.*,p.run_id FROM source_cursor c JOIN source_snapshot s USING(snapshot_id) "
            "LEFT JOIN source_promotion p ON p.to_snapshot_id=s.snapshot_id AND p.source=s.source "
            "WHERE c.source=%s AND s.source=%s", (source, source),
        ).fetchone()
    else:
        run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s AND mode=%s",
                           (UUID(requested_run), settings.mode)).fetchone()
        if not run:
            raise DomainError("SOURCE_RUN_NOT_FOUND", 404)
        manifest = run["manifest"] or {}
        kind = manifest.get("kind", "")
        run_source = manifest.get("source") or manifest.get("request", {}).get("source")
        if kind in {"abr_live_job", "qbcc_live_job", "qbcc_review_intake"}:
            run_source = kind.split("_")[0]
        if run_source and run_source != source:
            raise DomainError("SOURCE_RUN_NOT_FOUND", 404)
        if run["state"] != "complete":
            raise DomainError("SOURCE_RUN_NOT_COMPLETE", 409)
        # Live QBCC jobs refer to a separate accepted intake. No-op observations
        # refer to their prior snapshot and therefore have no new promotion row.
        receipt = (manifest.get("result") or manifest.get("acceptance_receipt")
                   or manifest.get("promotion_results", {}).get(source) or {})
        snapshot_id = receipt.get("snapshot_id")
        if snapshot_id:
            row = conn.execute("SELECT * FROM source_snapshot WHERE snapshot_id=%s AND source=%s",
                               (snapshot_id, source)).fetchone()
        else:
            row = conn.execute(
                "SELECT s.* FROM source_promotion p JOIN source_snapshot s ON s.snapshot_id=p.to_snapshot_id "
                "WHERE p.run_id=%s AND p.source=%s AND s.source=%s", (run["run_id"], source, source),
            ).fetchone()
        if not row:
            raise DomainError("SOURCE_RUN_NOT_FOUND", 404)
        row = {**row, "run_id": run["run_id"]}
    if row and row["state"] != "committed":
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    return row


def _plan(conn, service, source, requested_run, offset):
    service.personal_data_access(conn)
    snapshot = _snapshot(conn, service.settings, source, requested_run)
    manifest = snapshot["manifest"] if snapshot else {}
    result = {
        "source": source, "run_id": snapshot["run_id"] if snapshot else None,
        "snapshot_id": snapshot["snapshot_id"] if snapshot else None,
        "source_state": "available" if snapshot else "not_collected",
        "source_observed_at": manifest.get("observed_at"),
        "publisher_modified_at": manifest.get("publisher_modified_at") or manifest.get("source_published_at"),
        "publisher_extract_time": manifest.get("publisher_extract_time"),
        "baseline": bool(manifest.get("baseline")), "total": manifest.get("record_count", 0),
        "limit": PAGE_SIZE, "offset": offset, "next_offset": None, "records": [],
    }
    if not snapshot:
        return result, []
    paths = manifest.get("parquet_paths", [])
    if not paths or len(paths) > 512 or len(set(paths)) != len(paths):
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    artifacts = conn.execute(
        "SELECT * FROM artifact_manifest WHERE snapshot_id=%s AND source=%s "
        "AND artifact_class='snapshot' AND local_path=ANY(%s)",
        (snapshot["snapshot_id"], source, paths),
    ).fetchall()
    by_path = {row["local_path"]: row for row in artifacts}
    if any(path not in by_path for path in paths):
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    ordered = [by_path[path] for path in paths]
    if any(row["state"] in {"deleting", "deleted"} for row in ordered):
        result["source_state"] = "expired"
        return result, []
    if any(row["state"] != "referenced" or not row["verified_at"] for row in ordered):
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    return result, ordered


def _identity(path):
    _ordinary_path(path)
    stat = path.stat()
    if not path.is_file():
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _read_page(settings, result, artifacts, filters=None, sort="source_order"):
    if result["source_state"] != "available":
        return {}
    root, seals, tables = safe_root(settings), {}, []
    # File access is outside the staff-control transaction. Footer reads and the
    # selected row groups are bounded; raw archives are never read or decompressed.
    with ExitStack() as stack:
        for artifact in artifacts:
            path = Path(artifact["local_path"])
            _ordinary_path(path)
            if not path.is_absolute() or not path.resolve().is_relative_to(root):
                raise DomainError("ARTIFACT_PATH_OUTSIDE_STORAGE", 409)
            identity = _identity(path)
            # Verification already hashed these immutable local files. Refuse a
            # file changed since verification without rehashing multi-GB snapshots
            # inside an HTTP request. ctime also detects same-size/restamped edits.
            verified_ns = int(artifact["verified_at"].timestamp() * 1_000_000_000)
            if (identity[2] != artifact["byte_count"]
                    or max(identity[3:]) > verified_ns):
                raise DomainError("SOURCE_ARTIFACT_CHANGED", 409)
            table = stack.enter_context(pq.ParquetFile(path))
            if not set(FIELDS[result["source"]]).issubset(table.schema_arrow.names):
                raise DomainError("SOURCE_SCHEMA_UNAVAILABLE", 409)
            tables.append(table)
            seals[str(path)] = identity
        total = sum(table.metadata.num_rows for table in tables)
        if result["total"] != total:
            raise DomainError("SOURCE_RECORD_COUNT_CHANGED", 409)
        if sort != "source_order" or (filters and filters.model_dump(exclude_none=True)):
            result["source_total"] = total
            result.update(filtered_page([Path(row["local_path"]) for row in artifacts], result["source"],
                                        filters, offset=result["offset"], limit=PAGE_SIZE, seals=seals, sort=sort))
            for path, sealed in seals.items():
                if _identity(Path(path)) != sealed:
                    raise DomainError("SOURCE_ARTIFACT_CHANGED", 409)
            return seals
        skip, remaining = result["offset"], PAGE_SIZE
        for table in tables:
            if skip >= table.metadata.num_rows:
                skip -= table.metadata.num_rows
                continue
            for group in range(table.num_row_groups):
                metadata = table.metadata.row_group(group)
                if skip >= metadata.num_rows:
                    skip -= metadata.num_rows
                    continue
                if metadata.total_byte_size > 256 * 1024**2 or metadata.num_rows > 1_048_576:
                    raise DomainError("SOURCE_ROW_GROUP_TOO_LARGE", 409)
                for batch in table.iter_batches(batch_size=2000, row_groups=[group],
                                               columns=list(FIELDS[result["source"]]), use_threads=False):
                    if skip >= batch.num_rows:
                        skip -= batch.num_rows
                        continue
                    take = min(remaining, batch.num_rows - skip)
                    result["records"].extend(batch.slice(skip, take).to_pylist())
                    remaining -= take
                    skip = 0
                    if not remaining:
                        break
                if not remaining:
                    break
            if not remaining:
                break
        next_offset = result["offset"] + len(result["records"])
        result["next_offset"] = next_offset if next_offset < total else None
        for path, sealed in seals.items():
            if _identity(Path(path)) != sealed:
                raise DomainError("SOURCE_ARTIFACT_CHANGED", 409)
    return seals


def list_source_records(settings, service, *, source, requested_run="latest", offset=0, actor, filters=None,
                        sort="source_order"):
    if source not in FIELDS or type(offset) is not int or not 0 <= offset <= MAX_OFFSET:
        raise DomainError("INVALID_INPUT", 422)
    if requested_run != "latest":
        try:
            UUID(requested_run)
        except (ValueError, TypeError, AttributeError):
            raise DomainError("INVALID_INPUT", 422) from None
    filters = normalized_filters(source, filters)
    sort = normalized_sort(source, sort)
    with transaction(settings) as conn:
        result, artifacts = _plan(conn, service, source, requested_run, offset)
    try:
        seals = _read_page(settings, result, artifacts, filters, sort)
        result.setdefault("source_total", result["total"])
        result["filters"] = filters.model_dump(exclude_none=True)
        result["sort"] = sort
        result["columns"] = list(FIELDS[source])
    except (OSError, pa.ArrowException, SourceError):
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409) from None
    with transaction(settings) as conn:
        # Recheck restore/retention state before returning any personal data.
        service.personal_data_access(conn)
        if artifacts:
            current = conn.execute(
                "SELECT * FROM artifact_manifest WHERE artifact_id=ANY(%s)",
                ([row["artifact_id"] for row in artifacts],),
            ).fetchall()
            by_id = {row["artifact_id"]: row for row in current}
            for artifact in artifacts:
                row = by_id.get(artifact["artifact_id"])
                if not row or any(row[k] != artifact[k] for k in (
                    "state", "content_digest", "byte_count", "verified_at", "snapshot_id", "local_path",
                )):
                    raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
            snapshot = conn.execute("SELECT state FROM source_snapshot WHERE snapshot_id=%s",
                                    (result["snapshot_id"],)).fetchone()
            if not snapshot or snapshot["state"] != "committed":
                raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
            try:
                for path, sealed in seals.items():
                    if _identity(Path(path)) != sealed:
                        raise DomainError("SOURCE_ARTIFACT_CHANGED", 409)
            except (OSError, SourceError):
                raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409) from None
        service.audit(conn, actor, "source_records_read", result["snapshot_id"] or source,
                      {"source": source, "run_id": result["run_id"], "offset": offset,
                       "count": len(result["records"]), "source_state": result["source_state"], "sort": sort})
    return json_safe(result)
