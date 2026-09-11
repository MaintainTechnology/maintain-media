"""Atomic, replay-safe source occurrence promotion into PostgreSQL authority.

Callers create pipeline_run first and commit only after this function returns.
This module uses a savepoint when called inside an existing transaction: an
injected failure never leaves partial events or candidate changes behind.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4, uuid5

import duckdb
import pyarrow.parquet as pq
from psycopg.types.json import Jsonb

from abr_engine.diff.events import iter_events
from abr_engine.ingest.common import SourceError, canonical_json, digest_file, normalize_abn
from abr_engine.ingest.quality import parquet_fill, validate_fill
from abr_engine.ingest.snapshots import content_identity
from abr_engine.qualify.abr import qualify_abr, qualify_qbcc, target_geography
from abr_engine.qualify.queue import score


def source_lock_key(source: str, schema: str = "public") -> int:
    return int.from_bytes(
        hashlib.sha256(f"{schema}:source:{source}".encode()).digest()[:8], "big", signed=True
    )


def _object_key(run_id, source: str, path: Path) -> str:
    path_hash = hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    return f"staging/{source}/{run_id}/{path_hash}/{path.name}"


def declare_artifact(conn, run_id, source: str, path: Path, *, artifact_class: str | None = None) -> dict:
    """Register ownership BEFORE the writer creates the file."""
    path = Path(path).resolve()
    if artifact_class is None:
        artifact_class = (
            "snapshot"
            if path.suffix.lower() == ".parquet"
            else "raw"
            if path.suffix.lower() in (".xml", ".zip", ".csv")
            else "manifest"
        )
    key = _object_key(run_id, source, path)
    conn.execute(
        "INSERT INTO artifact_manifest(artifact_id,run_id,source,object_key,content_digest,byte_count,state,local_path,artifact_class) "
        "VALUES(%s,%s,%s,%s,'',0,'writing',%s,%s) ON CONFLICT(object_key) DO NOTHING",
        (uuid4(), run_id, source, key, str(path), artifact_class),
    )
    return conn.execute("SELECT * FROM artifact_manifest WHERE object_key=%s", (key,)).fetchone()


def verify_artifact(conn, run_id, source: str, path: Path, *, check=None) -> dict:
    """Verify local writer bytes; upload adapters must also verify remote bytes."""
    # Checked live hashing may obtain current authority on another connection.
    # Do it before taking an artifact row lock, preserving control->artifact order.
    checked_digest = digest_file(path, check=check) if check is not None else None
    key = _object_key(run_id, source, path)
    row = conn.execute("SELECT * FROM artifact_manifest WHERE object_key=%s FOR UPDATE", (key,)).fetchone()
    if not row or row["state"] in ("deleting", "deleted", "orphan") or row["source"] != source:
        raise SourceError("ARTIFACT_NOT_OWNED")
    digest, size = checked_digest or digest_file(path), path.stat().st_size
    if row["state"] in ("verified", "referenced"):
        if row["content_digest"] != digest or row["byte_count"] != size:
            raise SourceError("VERIFIED_ARTIFACT_CHANGED")
        return row
    return conn.execute(
        "UPDATE artifact_manifest SET content_digest=%s,byte_count=%s,verified_at=clock_timestamp(),state='verified' "
        "WHERE artifact_id=%s RETURNING *",
        (digest, size, row["artifact_id"]),
    ).fetchone()


def register_artifacts(conn, run_id, source: str, paths: list[Path]) -> list[dict]:
    """Adopt existing offline fixture files, or verify previously declared files.

    Live writers must use declare_artifact before writing, then verify_artifact.
    This convenience helper does not claim pre-upload ownership for existing files.
    """
    result = []
    for path in paths:
        declare_artifact(conn, run_id, source, Path(path))
        result.append(verify_artifact(conn, run_id, source, Path(path)))
    return result


def _verified(conn, run_id, source, paths, analysis=None):
    if len({str(p.resolve()) for p in paths}) != len(paths):
        raise SourceError("DUPLICATE_ARTIFACT_PATH")
    rows = []
    for path in paths:
        row = conn.execute(
            "SELECT * FROM artifact_manifest WHERE object_key=%s" + ("" if analysis else " FOR UPDATE"),
            (_object_key(run_id, source, path),),
        ).fetchone()
        if (
            not row
            or row["state"] != "verified"
            or not row["verified_at"]
            or row["content_digest"] != (analysis.file_digest(path) if analysis else digest_file(path))
            or row["byte_count"] != path.stat().st_size
        ):
            raise SourceError("ARTIFACT_NOT_VERIFIED")
        rows.append(row)
    return rows


def _json_safe(value):
    return json.loads(json.dumps(value, default=str))


def _fault(fault, stage: str):
    if fault:
        fault(stage)


def _manifest_check(conn, service, source: str, manifest: dict, run: dict):
    required = (
        "snapshot_id",
        "observation_id",
        "observed_at",
        "schema_version",
        "parser_version",
        "content_digest",
        "generation",
    )
    if any(not manifest.get(k) for k in required) or manifest.get("coherence") != "validated":
        raise SourceError("FRESH_COHERENCE_EVIDENCE_REQUIRED")
    UUID(str(manifest["snapshot_id"]))
    UUID(str(manifest["observation_id"]))
    observed = datetime.fromisoformat(str(manifest["observed_at"]))
    now = service.now(conn)
    if (
        observed.tzinfo is None
        or observed > now + timedelta(minutes=5)
        or observed < run["started_at"] - timedelta(hours=24)
    ):
        raise SourceError("INVALID_OBSERVATION_TIME")
    kind = manifest.get("observation_kind")
    if kind == "fixture_read":
        if service.settings.mode != "fixture" or run["mode"] != "fixture":
            raise SourceError("FIXTURE_OBSERVATION_IN_LIVE_MODE")
    elif kind == "publisher_revalidation":
        if (
            not manifest.get("approved_mapping_evidence")
            or not manifest.get("inventory_before_digest")
            or manifest["inventory_before_digest"] != manifest.get("inventory_after_digest")
            or not manifest.get("publisher_revalidation_evidence")
        ):
            raise SourceError("FRESH_COHERENCE_EVIDENCE_REQUIRED")
    else:
        raise SourceError("CACHED_BYTES_NOT_NEW_OBSERVATION")
    if source == "abr":
        if (
            not manifest.get("identity_parts")
            or content_identity(manifest["identity_parts"]) != manifest["content_digest"]
        ):
            raise SourceError("CONTENT_IDENTITY_MISMATCH")
    elif source != "qbcc":
        raise SourceError("UNKNOWN_SOURCE")
    if not isinstance(manifest["content_digest"], str) or len(manifest["content_digest"]) != 64:
        raise SourceError("INVALID_CONTENT_DIGEST")
    duplicate = conn.execute(
        "SELECT snapshot_id FROM source_snapshot WHERE source=%s AND manifest->>'observation_id'=%s",
        (source, str(manifest["observation_id"])),
    ).fetchone()
    if duplicate:
        raise SourceError("OBSERVATION_ALREADY_USED")
    observation = conn.execute(
        "SELECT * FROM source_observation WHERE observation_id=%s", (manifest["observation_id"],)
    ).fetchone()
    if observation and (
        observation["run_id"] != run["run_id"]
        or observation["source"] != source
        or observation["manifest"].get("content_digest") != manifest["content_digest"]
    ):
        raise SourceError("OBSERVATION_ALREADY_USED")
    if not observation:
        conn.execute(
            "INSERT INTO source_observation(observation_id,run_id,source,manifest,observed_at) VALUES(%s,%s,%s,%s,%s)",
            (manifest["observation_id"], run["run_id"], source, Jsonb(manifest), observed),
        )
    return observed


def _validate_event_set(previous: list[str], current: list[Path], events_path: Path, *, check=None) -> None:
    """Reject omitted/forged event payloads even when their bytes were staged.

    This bounded analytical check compares the complete expected event relation
    in both directions. It supplements artifact integrity with semantic binding.
    """
    from contextlib import ExitStack
    from sys import exc_info

    from abr_engine.ops.analytical import analytical_guard

    con = duckdb.connect()
    guard = ExitStack()
    try:
        guard.enter_context(analytical_guard(con, check))
        con.execute("SET memory_limit='512MB'")
        con.execute("SET threads=2")
        con.execute("SET max_temp_directory_size='8GB'")
        con.execute("SET temp_directory=?", [str(events_path.parent / "promotion-spill")])
        con.from_parquet(previous).create_view("p")
        con.from_parquet([str(p) for p in current]).create_view("c")
        con.from_parquet(str(events_path)).create_view("actual_events")
        con.execute("""CREATE VIEW expected_events AS
          SELECT coalesce(p.abn,c.abn) abn, kind event_type,
            CASE WHEN p.abn IS NOT NULL THEN to_json(p) END before_json,
            CASE WHEN c.abn IS NOT NULL THEN to_json(c) END after_json,
            CASE WHEN kind IN ('gst_registered','gst_cancelled') THEN c.gst_date
                 WHEN kind IN ('abn_new','abn_cancelled','abn_reactivated') THEN c.status_date END effective_date
          FROM p FULL OUTER JOIN c ON p.abn=c.abn
          CROSS JOIN LATERAL (VALUES
            ('abn_new',p.abn IS NULL AND c.status='ACT'),
            ('abn_cancelled',p.status='ACT' AND c.status='CAN'),
            ('abn_reactivated',p.status='CAN' AND c.status='ACT'),
            ('gst_registered',p.abn IS NOT NULL AND p.gst_status!='ACT' AND c.gst_status='ACT'),
            ('gst_cancelled',p.abn IS NOT NULL AND p.gst_status='ACT' AND c.gst_status!='ACT'),
            ('name_changed',p.abn IS NOT NULL AND c.abn IS NOT NULL AND p.name_hash!=c.name_hash),
            ('abn_disappeared',p.abn IS NOT NULL AND c.abn IS NULL)
          ) event(kind,emitted) WHERE emitted""")
        projection = "abn,event_type,before_json,after_json,effective_date"
        for left, right in (("expected_events", "actual_events"), ("actual_events", "expected_events")):
            if con.execute(
                f"SELECT {projection} FROM {left} EXCEPT ALL SELECT {projection} FROM {right} LIMIT 1"
            ).fetchone():
                raise SourceError("DIFF_EVENT_SET_MISMATCH")
    finally:
        try:
            guard.__exit__(*exc_info())
        finally:
            con.close()


def _matching_alias_groups(conn, service, kind: str, value: str):
    groups = set()
    for version, token in service.keys.matches(kind, value):
        for row in conn.execute(
            "SELECT group_id FROM suppression_alias WHERE alias_type=%s AND key_version=%s AND alias_token=%s",
            (kind, version, token),
        ):
            groups.add(service.canonical_group(conn, row["group_id"]))
    return groups


def _matching_groups(conn, service, abn: str):
    validated = normalize_abn(abn)
    assert validated is not None
    return _matching_alias_groups(conn, service, "abn", validated)


def _source_restriction(conn, service, abn, event_type, event_id):
    reason = "cancellation" if event_type == "abn_cancelled" else "disappearance"
    for group in sorted(_matching_groups(conn, service, abn), key=str):
        if "SUPPRESSED_" + reason.upper() in service.restricted(conn, group):
            continue
        service.suppress(
            conn,
            {"group_id": group, "reason": reason, "source": "abr"},
            "source-promotion",
            str(uuid5(UUID(str(event_id)), str(group))),
        )


def _abr_candidates(conn, service, events: list[dict], manifest: dict) -> int:
    row = json.loads(events[0]["after_json"]) if events[0]["after_json"] else None
    if not row:
        return 0
    kinds = {event["event_type"] for event in events}
    qualification = None
    if manifest.get("effective_date"):
        from datetime import date

        publication_date = date.fromisoformat(manifest["effective_date"])
        qualification = qualify_abr(row, kinds, publication_date)
    # No synthetic industry corpus is fabricated at promotion. GST-transition A
    # is independent of classifier; otherwise fresh ABNs are counted as C only.
    fields = {k: row[k] for k in ("status", "status_date", "gst_status", "gst_date", "entity_class")}
    groups = _matching_groups(conn, service, row["abn"])
    for group in groups:
        for lead in conn.execute("SELECT lead_id FROM lead_entity WHERE group_id=%s", (group,)):
            service.authority(conn, lead["lead_id"])
            conn.execute(
                "UPDATE lead_entity SET display_name=%s,state=%s,postcode=%s,fields=fields||%s,revision=revision+1 WHERE lead_id=%s",
                (row["main_name"], row["state"], row["postcode"], Jsonb(fields), lead["lead_id"]),
            )
            service.invalidate(conn, lead["lead_id"])
    if (
        not qualification
        or not qualification.enrichment_eligible
        or any(service.restricted(conn, group) for group in groups)
    ):
        return 0
    assert qualification.tier is not None
    event_key = next(event["event_id"] for event in events if event["event_type"] == "gst_registered")
    service.create_lead(
        conn,
        name=row["main_name"],
        source="abr",
        alias=row["abn"],
        state=row["state"],
        postcode=row["postcode"],
        tier=qualification.tier,
        signal="gst_registered",
        score=score(
            source="abr",
            tier=qualification.tier,
            geography=True,
            company=row["entity_class"] == "company",
            provisional=True,
        ),
        event_key=event_key,
        fields=fields,
    )
    conn.execute(
        "UPDATE candidate_queue SET state='pending_enrichment' WHERE event_key=%s AND state='needs_review'",
        (str(event_key),),
    )
    return 1


def _refresh_known_abr(conn, service, paths: list[Path], snapshot_id: UUID) -> None:
    """Refresh promoted profiles even when the change emits no named ABR event.

    In particular postcode/GST changes cannot leave a stale ready candidate.
    Only the small promoted alias set enters Python; full register rows stay in
    DuckDB. The database authority lock keeps merges/suppression coherent.
    """
    service.authority(conn)
    analytical = duckdb.connect()
    try:
        analytical.execute("SET memory_limit='512MB'")
        analytical.execute("SET threads=2")
        analytical.execute("SET max_temp_directory_size='8GB'")
        analytical.execute("SET temp_directory=?", [str(paths[0].parent / "refresh-spill")])
        analytical.execute(
            "CREATE TABLE wanted(abn VARCHAR, lead_id VARCHAR, group_id VARCHAR, source VARCHAR, PRIMARY KEY(abn,lead_id))"
        )
        with conn.cursor(name="known_aliases_" + uuid4().hex) as aliases:
            aliases.execute(
                "WITH RECURSIVE families AS (SELECT group_id AS alias_group,group_id,merged_into_group_id FROM business_group "
                "UNION ALL SELECT f.alias_group,g.group_id,g.merged_into_group_id FROM families f JOIN business_group g "
                "ON g.group_id=f.merged_into_group_id) SELECT a.encrypted_identifier,l.lead_id,l.group_id,l.source "
                "FROM lead_source_link a JOIN families f ON f.alias_group=a.group_id AND f.merged_into_group_id IS NULL "
                "JOIN lead_entity l ON l.group_id=f.group_id WHERE a.source_type='abn'"
            )
            while rows := aliases.fetchmany(1000):
                analytical.executemany(
                    "INSERT INTO wanted VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
                    [
                        (
                            service.keys.decrypt(r["encrypted_identifier"]),
                            str(r["lead_id"]),
                            str(r["group_id"]),
                            r["source"],
                        )
                        for r in rows
                    ],
                )
        analytical.from_parquet([str(p) for p in paths]).create_view("current_businesses")
        reader = analytical.execute(
            "SELECT c.*,w.lead_id,w.group_id,w.source profile_source FROM current_businesses c JOIN wanted w USING(abn)"
        ).to_arrow_reader(batch_size=1000)
        for batch in reader:
            for row in batch.to_pylist():
                fields = {
                    key: _json_safe(row[key])
                    for key in ("status", "status_date", "gst_status", "gst_date", "entity_class")
                }
                conn.execute(
                    "UPDATE lead_entity SET display_name=%s,state=%s,postcode=%s,fields=fields||%s,revision=revision+1 WHERE lead_id=%s",
                    (row["main_name"], row["state"], row["postcode"], Jsonb(fields), row["lead_id"]),
                )
                service.invalidate(conn, row["lead_id"])
                if row["status"] == "CAN" and not service.restricted(conn, UUID(row["group_id"])):
                    service.suppress(
                        conn,
                        {"group_id": row["group_id"], "reason": "cancellation", "source": "abr"},
                        "source-promotion",
                        str(uuid5(snapshot_id, f"current-cancelled:{row['group_id']}")),
                    )
                if not target_geography(row["state"], row["postcode"]) or (
                    row["profile_source"] == "abr" and row["gst_status"] != "ACT"
                ):
                    conn.execute(
                        "UPDATE candidate_queue SET state='disqualified' WHERE lead_id=%s AND state NOT IN ('suppressed','exported')",
                        (row["lead_id"],),
                    )
    finally:
        analytical.close()


def _qbcc_promote(conn, service, paths, prior_manifest, manifest, snapshot_id, observed, rebaseline):
    prior = {}
    if prior_manifest and not rebaseline:
        for path in prior_manifest["parquet_paths"]:
            if not Path(path).exists():
                raise SourceError("PRIOR_ARTIFACT_EXPIRED_REBASELINE_REQUIRED")
            for batch in pq.ParquetFile(path).iter_batches(batch_size=50000):
                prior.update({r["licence_number"]: r for r in batch.to_pylist()})
    count = 0
    candidate_groups = set()
    for path in paths:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=50000):
            for row in batch.to_pylist():
                if row["status"] in ("CANCELLED", "SUSPENDED", "INACTIVE"):
                    groups = _matching_alias_groups(conn, service, "qbcc", row["licence_number"])
                    if row.get("abn"):
                        groups |= _matching_groups(conn, service, row["abn"])
                    reason = "cancellation" if row["status"] == "CANCELLED" else "source_inactive"
                    for group in groups:
                        if "SUPPRESSED_" + reason.upper() not in service.restricted(conn, group):
                            service.suppress(
                                conn,
                                {"group_id": group, "reason": reason, "source": "qbcc", "entity_only": True},
                                "source-promotion",
                                str(uuid5(snapshot_id, f"inactive:{group}")),
                            )
                old = prior.get(row["licence_number"])
                if rebaseline and prior_manifest:
                    continue
                kind = (
                    "icp_backlog"
                    if not prior_manifest or rebaseline
                    else "new"
                    if old is None
                    else "category_changed"
                    if old["financial_category"] != row["financial_category"]
                    else None
                )
                if not kind or (
                    kind == "icp_backlog"
                    and (row["financial_category"] not in ("1", "2") or row["status"] != "ACTIVE")
                ):
                    continue
                event_id = uuid5(snapshot_id, f"{row['licence_number']}:{kind}")
                conn.execute(
                    "INSERT INTO qbcc_event(event_id,snapshot_id,licence_number,event_type,payload,detected_at) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        event_id,
                        snapshot_id,
                        row["licence_number"],
                        kind,
                        Jsonb({"before": old, "after": row}),
                        observed,
                    ),
                )
                count += 1
                if not qualify_qbcc(row, kind).enrichment_eligible:
                    groups = _matching_alias_groups(conn, service, "qbcc", row["licence_number"])
                    for group in groups:
                        conn.execute(
                            "UPDATE candidate_queue q SET state='disqualified' FROM lead_entity l WHERE q.lead_id=l.lead_id AND l.group_id=%s AND l.source='qbcc' AND q.state NOT IN ('suppressed','exported')",
                            (group,),
                        )
                    continue
                try:
                    with conn.transaction():
                        lead = service.create_lead(
                            conn,
                            name=row["licensee_name"],
                            source="qbcc",
                            alias=row["licence_number"],
                            abn=row.get("abn"),
                            state=row["state"],
                            postcode=row["postcode"],
                            tier="A",
                            signal={
                                "icp_backlog": "qbcc_backlog",
                                "new": "qbcc_new",
                                "category_changed": "qbcc_category_changed",
                            }[kind],
                            score=score(
                                source="qbcc",
                                tier="A",
                                geography=True,
                                category=row["financial_category"],
                                company=row["entity_class"] == "company",
                                provisional=True,
                            ),
                            event_key=str(event_id),
                            fields={
                                "financial_category": row["financial_category"],
                                "entity_class": row["entity_class"],
                                "source_observed_at": observed.isoformat(),
                            },
                        )
                        candidate_groups.add(lead["group_id"])
                        conn.execute(
                            "UPDATE candidate_queue SET state='pending_enrichment' WHERE event_key=%s AND state='needs_review'",
                            (str(event_id),),
                        )
                except Exception as exc:
                    # Suppressed identities and conflicting aliases remain held; do not
                    # swallow programmer/database failures or grant a fresh profile.
                    if getattr(exc, "code", None) not in (
                        "SUPPRESSED_SOURCE_IDENTITY",
                        "IDENTITY_MERGE_REVIEW_REQUIRED",
                    ):
                        raise
    return count, len(candidate_groups)


def promote(
    conn,
    service,
    run_id,
    source: str,
    manifest: dict,
    parquet_paths: list[Path],
    events_path: Path | None = None,
    expected_version: int = 0,
    rebaseline: bool = False,
    fault=None,
    candidate_mode: str = "qualify",
    analysis=None,
    final_authority=None,
    analysis_check=None,
    local_check=None,
) -> dict:
    """Returns staged result; outer caller commit makes it visible atomically.

    Fault hooks: after_artifacts, after_snapshot, after_events, before_cursor,
    after_cursor, before_commit. A crash after outer commit is replayed by run_id.
    """
    if candidate_mode not in {"qualify", "observe_only"} or (source != "abr" and candidate_mode != "qualify"):
        raise SourceError("INVALID_CANDIDATE_MODE")
    paths = [Path(p) for p in parquet_paths]
    if analysis is not None:
        from abr_engine.ops.abr_analysis import ABRAnalysis

        if (type(analysis) is not ABRAnalysis or source != "abr" or candidate_mode != "observe_only"
                or not callable(final_authority) or not callable(analysis_check) or not callable(local_check)):
            raise SourceError("ABR_ANALYSIS_REQUIRED")
        analysis.validate(run_id, manifest, paths, events_path, expected_version)
    commit_started = None
    if not paths or expected_version < 0:
        raise SourceError("INVALID_PROMOTION_INPUT")
    snapshot_id = UUID(str(manifest.get("snapshot_id")))
    with conn.transaction():
        schema = conn.execute("SELECT current_schema() AS name").fetchone()["name"]
        acquired = conn.execute(
            "SELECT pg_try_advisory_xact_lock(%s) AS acquired", (source_lock_key(source, schema),)
        ).fetchone()["acquired"]
        if not acquired:
            raise SourceError("SOURCE_STAGE_LOCK_BUSY")
        run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
        if not run:
            raise SourceError("RUN_REQUIRED")
        prior_result = (run["manifest"] or {}).get("promotion_results", {}).get(source)
        if prior_result:
            if prior_result["request_snapshot_id"] != str(snapshot_id) or prior_result[
                "content_digest"
            ] != manifest.get("content_digest"):
                raise SourceError("RUN_REPLAY_BODY_MISMATCH")
            return {**prior_result, "replayed": True}
        conn.execute("INSERT INTO source_cursor(source) VALUES(%s) ON CONFLICT DO NOTHING", (source,))
        cursor = conn.execute("SELECT * FROM source_cursor WHERE source=%s FOR UPDATE", (source,)).fetchone()
        if cursor["version"] != expected_version:
            raise SourceError("SOURCE_CURSOR_CONFLICT")
        observed = _manifest_check(conn, service, source, manifest, run)
        prior = (
            conn.execute(
                "SELECT s.*,c.content_digest,c.parser_version,c.schema_version FROM source_snapshot s JOIN source_content c USING(content_id) WHERE s.snapshot_id=%s",
                (cursor["snapshot_id"],),
            ).fetchone()
            if cursor["snapshot_id"]
            else None
        )
        if (
            prior
            and (
                prior["parser_version"] != manifest["parser_version"]
                or prior["schema_version"] != manifest["schema_version"]
            )
            and (not rebaseline or not manifest.get("rebaseline_reason"))
        ):
            raise SourceError("PARSER_SCHEMA_REBASELINE_REQUIRED")
        artifacts = _verified(conn, run_id, source, paths + ([Path(events_path)] if events_path else []), analysis)
        if source == "abr":
            current_quality = analysis.quality if analysis else parquet_fill(paths)
            previous_quality = None
            if prior and not rebaseline and analysis is None:
                previous_paths = [Path(path) for path in prior["manifest"]["parquet_paths"]]
                for path in previous_paths:
                    recorded = conn.execute(
                        "SELECT content_digest,byte_count FROM artifact_manifest WHERE local_path=%s AND state IN ('verified','referenced') ORDER BY created_at DESC LIMIT 1",
                        (str(path.resolve()),),
                    ).fetchone()
                    if (
                        not recorded
                        or not path.is_file()
                        or path.stat().st_size != recorded["byte_count"]
                        or digest_file(path) != recorded["content_digest"]
                    ):
                        raise SourceError("PREVIOUS_ARTIFACT_UNAVAILABLE")
                previous_quality = parquet_fill(previous_paths)
            if analysis is None:
                validate_fill(current_quality, manifest, previous_quality)
            manifest = {**manifest, **current_quality}
        _fault(fault, "after_artifacts")
        is_noop = bool(
            prior
            and not rebaseline
            and all(prior[k] == manifest[k] for k in ("content_digest", "parser_version", "schema_version"))
        )
        if is_noop:
            assert prior is not None
            result = {
                "snapshot_id": str(prior["snapshot_id"]),
                "request_snapshot_id": str(snapshot_id),
                "content_digest": manifest["content_digest"],
                "cursor_version": expected_version,
                "noop": True,
                "replayed": False,
                "events": 0,
                "candidates": 0,
            }
        else:
            if source == "abr":
                for path in paths:
                    with pq.ParquetFile(path) as table:
                        metadata = table.schema_arrow.metadata or {}
                        if (
                            metadata.get(b"schema_version", b"").decode() != manifest["schema_version"]
                            or metadata.get(b"parser_version", b"").decode() != manifest["parser_version"]
                        ):
                            raise SourceError("PARQUET_CONTRACT_MISMATCH")
            stored_manifest = {**manifest, "parquet_paths": [str(p.resolve()) for p in paths]}
            content = conn.execute(
                "INSERT INTO source_content(content_id,source,content_digest,schema_version,parser_version,artifact_ref) VALUES(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(source,content_digest,schema_version,parser_version) DO UPDATE SET artifact_ref=EXCLUDED.artifact_ref RETURNING content_id",
                (
                    uuid4(),
                    source,
                    manifest["content_digest"],
                    manifest["schema_version"],
                    manifest["parser_version"],
                    canonical_json(stored_manifest["parquet_paths"]),
                ),
            ).fetchone()
            if not content:
                content = conn.execute(
                    "SELECT content_id FROM source_content WHERE source=%s AND content_digest=%s AND schema_version=%s AND parser_version=%s",
                    (
                        source,
                        manifest["content_digest"],
                        manifest["schema_version"],
                        manifest["parser_version"],
                    ),
                ).fetchone()
            conn.execute(
                "INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,%s,%s,%s,%s,'validated')",
                (snapshot_id, source, content["content_id"], expected_version, Jsonb(stored_manifest)),
            )
            _fault(fault, "after_snapshot")
            event_count = candidate_count = 0
            restrictions = []
            if source == "abr":
                if candidate_mode == "qualify":
                    _refresh_known_abr(conn, service, paths, snapshot_id)
                if prior and not rebaseline and events_path is None:
                    raise SourceError("FULL_DIFF_OUTPUT_REQUIRED")
                if prior and not rebaseline and analysis is None:
                    prior_paths = prior["manifest"]["parquet_paths"]
                    for path in prior_paths:
                        owned = conn.execute(
                            "SELECT * FROM artifact_manifest WHERE snapshot_id=%s AND content_digest=%s AND state='referenced'",
                            (prior["snapshot_id"], digest_file(Path(path))),
                        ).fetchone()
                        if not owned:
                            raise SourceError("PRIOR_ARTIFACT_INTEGRITY_FAILURE")
                    assert events_path is not None
                    _validate_event_set(prior_paths, paths, Path(events_path))
                if events_path:
                    for abn, grouped in itertools.groupby(
                        iter_events(Path(events_path)), key=lambda e: e["abn"]
                    ):
                        business_events = list(grouped)
                        if (not prior or rebaseline) and business_events:
                            raise SourceError("BASELINE_EVENTS_FORBIDDEN")
                        for event in business_events:
                            if analysis is not None and event_count % 1000 == 0:
                                analysis_check()
                            if event["snapshot_id"] != str(snapshot_id) or event.get(
                                "previous_snapshot_id"
                            ) != (str(cursor["snapshot_id"]) if cursor["snapshot_id"] else None):
                                raise SourceError("DIFF_CURSOR_BINDING_MISMATCH")
                            conn.execute(
                                "INSERT INTO abr_event(event_id,snapshot_id,abn,event_type,payload,detected_at) VALUES(%s,%s,%s,%s,%s,%s)",
                                (
                                    event["event_id"],
                                    snapshot_id,
                                    normalize_abn(abn),
                                    event["event_type"],
                                    Jsonb(_json_safe(event)),
                                    observed,
                                ),
                            )
                            event_count += 1
                            if event["event_type"] in ("abn_cancelled", "abn_disappeared"):
                                if analysis is not None:
                                    if abn in analysis.known_abns:
                                        restrictions.append((abn, event["event_type"], event["event_id"]))
                                else:
                                    _source_restriction(conn, service, abn, event["event_type"], event["event_id"])
                        if candidate_mode == "qualify":
                            candidate_count += _abr_candidates(conn, service, business_events, manifest)
            else:
                event_count, candidate_count = _qbcc_promote(
                    conn,
                    service,
                    paths,
                    prior["manifest"] if prior else None,
                    manifest,
                    snapshot_id,
                    observed,
                    rebaseline,
                )
            _fault(fault, "after_events")
            if analysis is not None:
                commit_started = analysis.finalize(conn, service, snapshot_id, final_authority, local_check)
                for abn, event_type, event_id in restrictions:
                    if monotonic() - commit_started > 2:
                        raise SourceError("ABR_CONTROL_COMMIT_DEADLINE")
                    _source_restriction(conn, service, abn, event_type, event_id)
            _fault(fault, "before_cursor")
            updated = conn.execute(
                "UPDATE source_cursor SET snapshot_id=%s,version=version+1,last_success_at=clock_timestamp() WHERE source=%s AND version=%s RETURNING version",
                (snapshot_id, source, expected_version),
            ).fetchone()
            if not updated:
                raise SourceError("SOURCE_CURSOR_CONFLICT")
            _fault(fault, "after_cursor")
            conn.execute("UPDATE source_snapshot SET state='committed' WHERE snapshot_id=%s", (snapshot_id,))
            conn.execute(
                "INSERT INTO source_promotion(run_id,source,from_snapshot_id,to_snapshot_id) VALUES(%s,%s,%s,%s)",
                (run_id, source, cursor["snapshot_id"], snapshot_id),
            )
            for artifact in artifacts:
                conn.execute(
                    "UPDATE artifact_manifest SET state='referenced',snapshot_id=%s WHERE artifact_id=%s",
                    (snapshot_id, artifact["artifact_id"]),
                )
            result = {
                "snapshot_id": str(snapshot_id),
                "request_snapshot_id": str(snapshot_id),
                "content_digest": manifest["content_digest"],
                "cursor_version": updated["version"],
                "noop": False,
                "replayed": False,
                "events": event_count,
                "candidates": candidate_count,
            }
        run_manifest = run["manifest"] or {}
        if analysis is not None and commit_started is None:
            commit_started = analysis.finalize(conn, service, snapshot_id, final_authority, local_check)
        run_manifest.setdefault("promotion_results", {})[source] = result
        conn.execute(
            "UPDATE pipeline_run SET manifest=%s,heartbeat_at=clock_timestamp() WHERE run_id=%s",
            (Jsonb(run_manifest), run_id),
        )
        _fault(fault, "before_commit")
        if commit_started is not None and monotonic() - commit_started > 3:
            raise SourceError("ABR_CONTROL_COMMIT_DEADLINE")
        return result
