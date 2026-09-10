"""Recoverable offline pipeline. PostgreSQL stage records own all retries."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import shutil
import sys
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import psutil
from psycopg.types.json import Jsonb

from abr_engine import __version__
from abr_engine.config import ROOT
from abr_engine.control.service import DomainError, digest, json_safe
from abr_engine.db import connect, transaction
from abr_engine.diff.events import diff_snapshots
from abr_engine.enrich.worker import SyntheticProvider, drain_one
from abr_engine.export.report import ReportContext, render_report, safe_rows
from abr_engine.export.worklist import build_worklist, report_context
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ingest.abr_download import ArchiveResource, ingest_archives
from abr_engine.ingest.abr_parse import PARSER_VERSION, SCHEMA_VERSION, ABRMapping
from abr_engine.ingest.common import digest_file
from abr_engine.ingest.qbcc import parse_qbcc, write_qbcc_parquet
from abr_engine.ops.monitor import monitor_run
from abr_engine.ops.promotion import declare_artifact, promote, source_lock_key, verify_artifact
from abr_engine.ops.summary import operational_summary

SOURCES = {"all", "abr", "qbcc"}
ABR_FIXTURES = {"abr_baseline", "abr_changed", "abr_same_date_correction", "abr_identical_republish"}


def safe_root(settings) -> Path:
    root = settings.output_dir
    return (root if root.is_absolute() else ROOT / root).resolve()


def _within(root: Path, path: Path | str) -> Path:
    resolved = Path(path).resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise DomainError("ARTIFACT_PATH_OUTSIDE_STORAGE", 409)
    return resolved


def _fault(fault, point):
    if fault:
        fault(point)


@contextmanager
def process_lock(path: Path):
    """Nonblocking OS lock whose handle is released when the process exits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if not path.stat().st_size:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            # sys.platform, not os.name: type checkers narrow on it, so the
            # Windows-only msvcrt branch is skipped when checking on Linux.
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl = importlib.import_module("fcntl")

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise DomainError("PROCESS_STAGE_LOCK_BUSY", 409) from None
        yield
    finally:
        if acquired:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl = importlib.import_module("fcntl")

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


@contextmanager
def _session_lock(settings, key: int):
    conn = connect(settings)
    conn.commit()
    conn.autocommit = True
    acquired = False
    try:
        locked = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()
        assert locked is not None
        acquired = locked["acquired"]
        if not acquired:
            raise DomainError("SOURCE_STAGE_LOCK_BUSY", 409)
        yield conn
    finally:
        if acquired and not conn.closed:
            conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
        conn.close()


def _update_metadata(conn, run_id, field: str, value):
    row = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
    metadata = row["manifest"] or {}
    metadata[field] = json_safe(value)
    conn.execute(
        "UPDATE pipeline_run SET manifest=%s,heartbeat_at=clock_timestamp() WHERE run_id=%s",
        (Jsonb(metadata), run_id),
    )
    return metadata


def _save_stage(conn, run_id, source, stage):
    row = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
    stages = (row["manifest"] or {}).get("source_stages", {})
    stages[source] = json_safe(stage)
    _update_metadata(conn, run_id, "source_stages", stages)


def _alarm(settings, run_id, subject, code):
    safe_code = (
        code
        if isinstance(code, str) and code.replace("_", "").isalnum() and len(code) <= 100
        else "PIPELINE_FAILURE"
    )
    with transaction(settings) as conn:
        conn.execute(
            "INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(run_id,code,subject_key) DO NOTHING",
            (
                uuid4(),
                run_id,
                safe_code,
                subject,
                Jsonb({"owner": "operator", "runbook": "ops/runbook.md#source-recovery"}),
            ),
        )
        conn.execute(
            "UPDATE pipeline_run SET state='held',heartbeat_at=clock_timestamp() WHERE run_id=%s", (run_id,)
        )


@contextmanager
def _resources(settings, run_id):
    stop = threading.Event()
    process = psutil.Process()
    data = {
        "sampled_peak_rss_bytes": process.memory_info().rss,
        "sample_interval_seconds": 0.1,
        "full_scale_certified": False,
        "heartbeat_failures": 0,
    }

    def monitor():
        last_heartbeat = time.monotonic()
        while not stop.wait(0.1):
            data["sampled_peak_rss_bytes"] = max(data["sampled_peak_rss_bytes"], process.memory_info().rss)
            if time.monotonic() - last_heartbeat >= 30:
                try:
                    with transaction(settings) as conn:
                        conn.execute("SET LOCAL lock_timeout='1s'")
                        conn.execute("SET LOCAL statement_timeout='2s'")
                        conn.execute(
                            "UPDATE pipeline_run SET heartbeat_at=clock_timestamp() WHERE run_id=%s",
                            (run_id,),
                        )
                except Exception:  # noqa: BLE001 - measured heartbeat failure, no exception text logged
                    data["heartbeat_failures"] += 1
                last_heartbeat = time.monotonic()

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        yield data
    finally:
        stop.set()
        thread.join(timeout=6)


def _declare(conn, run_id, source, root, paths, artifact_class=None):
    for path in paths:
        declare_artifact(conn, run_id, source, _within(root, path), artifact_class=artifact_class)


def _verify(conn, run_id, source, root, paths, *, referenced=False):
    rows = []
    for path in paths:
        row = verify_artifact(conn, run_id, source, _within(root, path))
        if referenced:
            conn.execute(
                "UPDATE artifact_manifest SET state='referenced' WHERE artifact_id=%s", (row["artifact_id"],)
            )
        rows.append(row)
    return rows


def _prepare_source(conn, settings, service, root, run_id, selected, request, fault):
    now = service.now(conn)
    cursor = conn.execute(
        "SELECT c.*,s.manifest FROM source_cursor c LEFT JOIN source_snapshot s ON s.snapshot_id=c.snapshot_id WHERE c.source=%s",
        (selected,),
    ).fetchone()
    attempt = uuid4()
    base = root / "staging" / selected / str(run_id) / str(attempt)
    work = base / "normalised"
    manifest = {
        "snapshot_id": str(uuid4()),
        "observation_id": str(uuid4()),
        "observed_at": now.isoformat(),
        "observation_kind": "fixture_read",
        "source": selected,
        "source_licence_ref": "synthetic-fixture-no-live-data",
        "retrieved_at": now.isoformat(),
        "dataset_id": f"synthetic-{selected}",
        "publisher_timestamp": None,
    }
    stage = {
        "status": "writing",
        "attempt_id": str(attempt),
        "source": selected,
        "manifest": manifest,
        "expected_version": cursor["version"] if cursor else 0,
    }
    with conn.transaction():
        _save_stage(conn, run_id, selected, stage)
    base.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    if selected == "abr":
        fixture_path = ROOT / "tests/fixtures/abr" / (request["abr_fixture"] + ".zip")
        raw = base / "input.zip"
        with zipfile.ZipFile(fixture_path) as archive:
            names = archive.namelist()
        if not names or len(names) > 1000:
            raise DomainError("FIXTURE_MEMBER_INVENTORY_INVALID")
        generated_raw = [work / "resource-0" / f"member-{i}" / "source.xml" for i in range(len(names))]
        paths = [path.parent / "records.parquet" for path in generated_raw]
        transient = [
            path.parent / name
            for path in paths
            for name in ("records.parquet.writing", "uniqueness.sqlite", "uniqueness.sqlite-journal")
        ]
        events = work / "events.parquet"
        with conn.transaction():
            _declare(conn, run_id, selected, root, [raw, *generated_raw, *paths, events])
            _declare(conn, run_id, selected, root, transient, "snapshot")
        shutil.copyfile(fixture_path, raw)
        resource = ArchiveResource(
            "fixture-abr", "fixture", raw, {name: name for name in names}, declared_size=raw.stat().st_size
        )
        inventory = [{"resource_id": resource.resource_id, "part_label": resource.part_label}]
        publication = ingest_archives(
            [resource],
            work,
            mapping=ABRMapping.fixture(),
            inventory_before=inventory,
            inventory_after=inventory,
            required_parts={"fixture"},
            expected_sequences={1},
        )
        manifest.update(publication.manifest)
        manifest.update(
            {
                "parser_version": PARSER_VERSION,
                "schema_version": SCHEMA_VERSION,
                "effective_date": publication.manifest["extract_time"][:10],
            }
        )
        previous = (
            [_within(root, p) for p in cursor["manifest"]["parquet_paths"]]
            if cursor and cursor["snapshot_id"]
            else None
        )
        if request["rebaseline"]:
            manifest["rebaseline_reason"] = request["rebaseline_reason"]
        diff_snapshots(
            previous,
            paths,
            events,
            snapshot_id=manifest["snapshot_id"],
            observed_at=now,
            previous_snapshot_id=str(cursor["snapshot_id"]) if previous else None,
            rebaseline=request["rebaseline"],
        )
        counts = {
            "source_rows": sum(m.row_count for m in publication.members),
            "declared_rows": sum(int(m.header["record_count"]) for m in publication.members),
            "normalised_rows": sum(m.row_count for m in publication.members),
            "quarantined_records": 0,
            "members": len(publication.members),
            "field_fill": [m.field_fill for m in publication.members],
            "field_fill_weighted": publication.manifest["field_fill_weighted"],
        }
        all_paths = [raw, *generated_raw, *paths, events]
        with conn.transaction():
            conn.execute(
                "UPDATE artifact_manifest SET state='orphan',deletion_reason='parser-temporary-closed' WHERE run_id=%s AND local_path=ANY(%s)",
                (run_id, [str(path.resolve()) for path in transient]),
            )
    else:
        fixture_path = ROOT / "tests/fixtures/qbcc/synthetic_contractors.csv"
        raw, paths, events = base / "input.csv", [work / "contractors.parquet"], None
        with conn.transaction():
            _declare(conn, run_id, selected, root, [raw, *paths])
        shutil.copyfile(fixture_path, raw)
        work.mkdir()
        parsed = parse_qbcc(raw)
        write_qbcc_parquet(parsed, paths[0])
        manifest.update(
            {
                "coherence": "validated",
                "content_digest": parsed.source_sha256,
                "generation": parsed.source_sha256,
                "parser_version": "fixture-qbcc-v1",
                "schema_version": "qbcc-v1",
                "mapping_version": parsed.mapping_version,
                "resources": [
                    {
                        "resource_id": "synthetic-qbcc",
                        "source_sha256": parsed.source_sha256,
                        "publisher_timestamp": None,
                        "url": None,
                        "etag": None,
                        "last_modified": None,
                        "declared_size": raw.stat().st_size,
                    }
                ],
                "category_counts": parsed.category_counts,
            }
        )
        counts = {
            "source_rows": parsed.row_count,
            "normalised_rows": len(parsed.records),
            "quarantined_licences": len(parsed.quarantined),
            "quarantined_rows": sum(r["row_count"] for r in parsed.quarantined),
            "category_counts": parsed.category_counts,
        }
        all_paths = [raw, *paths]
    _fault(fault, "after_parse")
    stage.update(
        {
            "status": "validated",
            "manifest": manifest,
            "paths": [str(p) for p in paths],
            "events": str(events) if events else None,
            "all_paths": [str(p) for p in all_paths],
            "counts": counts,
            "stage_elapsed_seconds": time.perf_counter() - started,
        }
    )
    with conn.transaction():
        _verify(conn, run_id, selected, root, all_paths)
        _save_stage(conn, run_id, selected, stage)
    _fault(fault, "after_stage_commit")
    return stage


def _source_once(settings, service, root, run_id, selected, request, fault):
    with (
        process_lock(root / "locks" / settings.schema_name / f"{selected}.lock"),
        _session_lock(settings, source_lock_key(selected, settings.schema_name)) as conn,
    ):
        metadata = (
            conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (run_id,)).fetchone()[
                "manifest"
            ]
            or {}
        )
        done = metadata.get("promotion_results", {}).get(selected)
        stage = metadata.get("source_stages", {}).get(selected)
        if done:
            return {**done, "replayed": True, "validation": (stage or {}).get("counts", {})}
        if stage and stage.get("status") == "validated":
            for path in stage["all_paths"]:
                _within(root, path)
        else:
            with conn.transaction():
                conn.execute(
                    "UPDATE artifact_manifest SET state='orphan',deletion_reason='interrupted-stage' WHERE run_id=%s AND source=%s AND state='writing'",
                    (run_id, selected),
                )
            stage = _prepare_source(conn, settings, service, root, run_id, selected, request, fault)
        with conn.transaction():
            result = promote(
                conn,
                service,
                run_id,
                selected,
                stage["manifest"],
                [Path(p) for p in stage["paths"]],
                events_path=Path(stage["events"]) if stage["events"] else None,
                expected_version=stage["expected_version"],
                rebaseline=request["rebaseline"],
            )
            conn.execute(
                "UPDATE artifact_manifest SET state='referenced',snapshot_id=%s WHERE run_id=%s AND source=%s AND state='verified' AND artifact_class='raw'",
                (result["snapshot_id"], run_id, selected),
            )
        _fault(fault, "after_source_commit")
        event_counts = {}
        tier_counts = {}
        if result["events"]:
            event_table = "abr_event" if selected == "abr" else "qbcc_event"
            event_counts = {
                row["event_type"]: row["n"]
                for row in conn.execute(
                    f"SELECT event_type,count(*) AS n FROM {event_table} WHERE snapshot_id=%s GROUP BY event_type",
                    (result["snapshot_id"],),
                )
            }
            tier_counts = {
                row["tier"]: row["n"]
                for row in conn.execute(
                    f"SELECT q.tier,count(DISTINCT q.lead_id) AS n FROM candidate_queue q JOIN {event_table} e ON q.event_key=e.event_id::text WHERE e.snapshot_id=%s GROUP BY q.tier",
                    (result["snapshot_id"],),
                )
            }
        quality_alarms = []
        if event_counts.get("abn_disappeared"):
            quality_alarms.append("unexpected_disappearance")
            with conn.transaction():
                conn.execute(
                    "INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload) VALUES(%s,%s,'unexpected_disappearance',%s,%s) ON CONFLICT(run_id,code,subject_key) DO NOTHING",
                    (
                        uuid4(),
                        run_id,
                        selected,
                        Jsonb(
                            {
                                "owner": "operator",
                                "runbook": "ops/runbook.md#source-recovery",
                                "count": event_counts["abn_disappeared"],
                            }
                        ),
                    ),
                )
        return {
            **result,
            "validation": stage["counts"],
            "stage_elapsed_seconds": stage["stage_elapsed_seconds"],
            "event_counts": event_counts,
            "qualifying_groups_by_tier": tier_counts,
            "classification": {"enabled": False, "reason": "CLASSIFIER_DISABLED"}
            if selected == "abr"
            else None,
            "alarms": quality_alarms,
        }


def _report_context(settings, service, run_id):
    with transaction(settings) as conn:
        if not service.current_policy(conn):
            seed_policy(conn, service)
        local_date = service.now(conn).astimezone(ZoneInfo("Australia/Brisbane")).date()
        week = local_date - timedelta(days=local_date.weekday())
        existing = conn.execute("SELECT worklist_id FROM worklist WHERE week=%s", (week,)).fetchone()
        ready = conn.execute("SELECT 1 FROM candidate_queue WHERE state='ready' LIMIT 1").fetchone()
        if not existing and not ready:
            blocked = conn.execute("SELECT count(DISTINCT lead_id) AS n FROM candidate_queue").fetchone()
            assert blocked is not None
            return (
                {"worklist_id": None, "selected": 0},
                ReportContext(
                    run_id=run_id, generated_at=service.now(conn), mode="fixture", authorised_operator=True
                ),
                blocked["n"],
            )
        worklist = build_worklist(conn, service, week)
        context = report_context(conn, service, worklist["worklist_id"], run_id)
        blocked_row = conn.execute(
            "SELECT count(DISTINCT lead_id) AS n FROM candidate_queue WHERE state IN ('needs_review','suppressed','deferred','disqualified')"
        ).fetchone()
        assert blocked_row is not None
        blocked = blocked_row["n"]
        return worklist, context, blocked


def _fixture_enrichment(settings, service):
    with transaction(settings) as conn:
        if not service.current_policy(conn):
            seed_policy(conn, service)
        candidates = conn.execute(
            "SELECT DISTINCT ON (q.lead_id) q.candidate_id,q.lead_id,l.first_qualified_at "
            "FROM candidate_queue q JOIN lead_entity l USING(lead_id) WHERE l.source='qbcc' "
            "AND l.lifecycle='active' AND q.state='pending_enrichment' ORDER BY q.lead_id,q.first_qualified_at,q.candidate_id"
        ).fetchall()
        existing_approved = conn.execute("SELECT 1 FROM contact_basis WHERE state='pass' LIMIT 1").fetchone()
    results = []
    for index, candidate in enumerate(
        sorted(candidates, key=lambda c: (c["first_qualified_at"], str(c["lead_id"])))
    ):
        allow = not existing_approved and index == 0

        def explicit_fixture_approval(conn, service, lead_id, payload, allow=allow):
            # Synthetic signed permission is an explicit test adapter, never a provider result.
            if settings.mode != "fixture" or not all(p.get("synthetic") for p in payload.values()):
                raise DomainError("FIXTURE_APPROVAL_REQUIRED", 403)
            lead = service.lead(conn, lead_id)
            if not conn.execute("SELECT 1 FROM contact_record WHERE lead_id=%s", (lead_id,)).fetchone():
                seed_contact(conn, service, existing_lead=lead, allow=allow)
                conn.execute(
                    "UPDATE lead_entity SET fields=%s||fields WHERE lead_id=%s",
                    (Jsonb(lead["fields"]), lead_id),
                )

        results.append(
            drain_one(
                settings,
                service,
                SyntheticProvider(),
                candidate_id=candidate["candidate_id"],
                apply_result=explicit_fixture_approval,
            )
        )
    return results


def _publish_report(settings, service, root, run_id, fault):
    worklist, context, blocked = _report_context(settings, service, run_id)
    generation = uuid4()
    temporary = root / "staging" / "reports" / str(run_id) / str(generation)
    destination = root / "reports" / str(run_id) / str(generation)
    filenames = {"html": "report.html", "markdown": "report.md", "csv": "worklist.csv"}
    temp_paths = [temporary / str(run_id) / name for name in filenames.values()]
    final_paths = {kind: destination / name for kind, name in filenames.items()}
    with transaction(settings) as conn:
        _declare(conn, run_id, "report", root, [*temp_paths, *final_paths.values()], "report")
    render_report(context, temporary)
    _fault(fault, "after_report_write")
    _within(root, temporary / str(run_id))
    _within(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    (temporary / str(run_id)).rename(destination)
    with transaction(settings) as conn:
        rows = _verify(conn, run_id, "report", root, final_paths.values(), referenced=True)
        conn.execute(
            "UPDATE artifact_manifest SET state='orphan',deletion_reason='published-by-rename' WHERE run_id=%s AND source='report' AND state='writing' AND local_path=ANY(%s)",
            (run_id, [str(p.resolve()) for p in temp_paths]),
        )
    return (
        worklist,
        blocked,
        final_paths,
        {str(Path(r["local_path"])): r["content_digest"] for r in rows},
        _report_fingerprint(context),
    )


def _report_fingerprint(context):
    volatile = {"generated_at", "gate_checked_at", "gate_expires_at"}
    return digest(
        [{key: value for key, value in row.items() if key not in volatile} for row in safe_rows(context)]
    )


def _current_report_authority(settings, service, run_id, result):
    with transaction(settings) as conn:
        if result.get("worklist_id"):
            context = report_context(conn, service, UUID(result["worklist_id"]), run_id)
        else:
            context = ReportContext(
                run_id=run_id, generated_at=service.now(conn), mode="fixture", authorised_operator=True
            )
        return result.get("report_authority_digest") == _report_fingerprint(context)


def _receipt(settings, root, run_id, result):
    path = _within(root, result["manifest_path"])
    with transaction(settings) as conn:
        _declare(conn, run_id, "manifest", root, [path], "manifest")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, indent=2, sort_keys=True).encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise DomainError("RUN_RECEIPT_INTEGRITY_FAILURE", 409)
    else:
        with path.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    with transaction(settings) as conn:
        _verify(conn, run_id, "manifest", root, [path], referenced=True)


def _valid_report(root, result):
    digests = result.get("artifact_digests", {})
    return bool(
        digests
        and all(
            _within(root, path).is_file() and digest_file(_within(root, path)) == checksum
            for path, checksum in digests.items()
        )
    )


def execute(
    settings,
    service,
    source="all",
    run_id: UUID | None = None,
    *,
    abr_fixture="abr_baseline",
    rebaseline=False,
    rebaseline_reason=None,
    fault=None,
):
    if settings.mode != "fixture":
        raise DomainError("LIVE_SOURCE_APPROVALS_PENDING", 403)
    if source not in SOURCES or abr_fixture not in ABR_FIXTURES:
        raise DomainError("UNKNOWN_SOURCE_OR_FIXTURE")
    default_rebaseline_reason = "Fixture contract rebaseline requested by test/operator"
    if rebaseline_reason is not None and (
        not isinstance(rebaseline_reason, str)
        or not 10 <= len(rebaseline_reason.strip()) <= 2000
        or len(rebaseline_reason) > 2000
    ):
        raise DomainError("REBASELINE_REASON_REQUIRED")
    run_id = UUID(str(run_id)) if run_id else uuid4()
    root = safe_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    run_key = int.from_bytes(
        hashlib.sha256(f"{settings.schema_name}:pipeline:{run_id}".encode()).digest()[:8], "big", signed=True
    )
    with (
        process_lock(root / "locks" / settings.schema_name / f"run-{run_id}.lock"),
        _session_lock(settings, run_key),
    ):
        config_digest = digest(settings.model_dump())
        request = {
            "source": source,
            "abr_fixture": abr_fixture,
            "rebaseline": rebaseline,
            "rebaseline_reason": (rebaseline_reason or default_rebaseline_reason) if rebaseline else None,
        }
        with transaction(settings) as conn:
            existing = conn.execute(
                "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if existing and existing["config_digest"] != config_digest:
                raise DomainError("RESUME_CONFIG_CHANGED", 409)
            if not existing:
                conn.execute(
                    "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) VALUES(%s,'fixture',%s,%s,'running',%s)",
                    (run_id, __version__, config_digest, Jsonb({"request": request})),
                )
                metadata = {"request": request}
            else:
                metadata = existing["manifest"] or {}
                saved = metadata.get("request", request)
                if "rebaseline_reason" not in saved:
                    saved = {
                        **saved,
                        "rebaseline_reason": default_rebaseline_reason if saved["rebaseline"] else None,
                    }
                if (
                    (source != "all" and source != saved["source"])
                    or (abr_fixture != "abr_baseline" and abr_fixture != saved["abr_fixture"])
                    or (rebaseline and not saved["rebaseline"])
                    or (rebaseline_reason is not None and rebaseline_reason != saved["rebaseline_reason"])
                ):
                    raise DomainError("RESUME_REQUEST_CHANGED", 409)
                request = saved
                _update_metadata(conn, run_id, "request", request)
        stored = metadata.get("result")
        if (
            existing
            and existing["state"] == "complete"
            and stored
            and _valid_report(root, stored)
            and _current_report_authority(settings, service, run_id, stored)
        ):
            _receipt(settings, root, run_id, stored)
            return stored
        started = time.perf_counter()
        with _resources(settings, run_id) as measured:
            try:
                results, alarms = {}, []
                for selected in ["qbcc", "abr"] if request["source"] == "all" else [request["source"]]:
                    try:
                        results[selected] = _source_once(
                            settings, service, root, run_id, selected, request, fault
                        )
                    except Exception as exc:  # noqa: BLE001 - every source failure becomes a durable held result
                        code = getattr(exc, "code", "SOURCE_INTEGRITY_HELD")
                        _alarm(settings, run_id, selected, code)
                        results[selected] = {"status": "held", "code": code}
                        alarms.append({"source": selected, "code": code})
                enrichment = _fixture_enrichment(settings, service)
                worklist, blocked, outputs, artifact_digests, report_authority_digest = _publish_report(
                    settings, service, root, run_id, fault
                )
                with transaction(settings) as conn:
                    summary_end = service.now(conn)
                    operational = operational_summary(
                        conn, service, run_id, summary_end - timedelta(weeks=8), summary_end
                    )
                result = json_safe(
                    {
                        "schema_version": 2,
                        "run_id": run_id,
                        "status": "held" if alarms else "complete",
                        "manifest_path": str(root / "runs" / str(run_id) / f"{uuid4()}.json"),
                        "sources": results,
                        "counts": {
                            "selected": worklist["selected"],
                            "blocked_or_deferred": blocked,
                            "live_api_calls": 0,
                        },
                        "operational_summary": operational,
                        "enrichment": enrichment,
                        "worklist_id": worklist["worklist_id"],
                        "artifacts": outputs,
                        "artifact_digests": artifact_digests,
                        "report_authority_digest": report_authority_digest,
                        "alarms": alarms,
                        "runtime": platform.python_version(),
                        "code_version": __version__,
                        "config_digest": config_digest,
                        "resource_sample": {
                            **measured,
                            "elapsed_seconds": time.perf_counter() - started,
                            "ending_rss_bytes": psutil.Process().memory_info().rss,
                            "disk_free_bytes": shutil.disk_usage(root).free,
                        },
                        "production_gates": "PENDING",
                        "mode": "fixture",
                    }
                )
                with transaction(settings) as conn:
                    result["monitor"] = monitor_run(conn, service, run_id, result)
                    _declare(conn, run_id, "manifest", root, [Path(result["manifest_path"])], "manifest")
                    _update_metadata(conn, run_id, "result", result)
                    conn.execute(
                        "UPDATE pipeline_run SET state=%s,finished_at=clock_timestamp() WHERE run_id=%s",
                        ("held" if alarms else "complete", run_id),
                    )
                _fault(fault, "after_run_result_commit")
                _receipt(settings, root, run_id, result)
                return result
            except Exception as exc:
                _alarm(settings, run_id, "report", getattr(exc, "code", "PIPELINE_REPORT_FAILURE"))
                raise
