"""Real PostgreSQL16 crash, source cursor, alias restriction and recovery proof."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pyarrow.parquet as pq
import pytest
from psycopg import sql

from abr_engine.config import ROOT
from abr_engine.db import connect
from abr_engine.diff.events import diff_snapshots
from abr_engine.ingest.abr_parse import PARSER_VERSION, SCHEMA_VERSION, parse_xml
from abr_engine.ingest.common import SourceError, digest_file
from abr_engine.ingest.qbcc import parse_qbcc, write_qbcc_parquet
from abr_engine.ingest.snapshots import content_identity
from abr_engine.ops.promotion import declare_artifact, promote, register_artifacts, source_lock_key


@pytest.fixture
def source_db(settings):
    """Independent schema permits real commits without touching other test data."""
    conn = connect(settings)
    schema = "test_abr_" + uuid4().hex
    conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
    for migration in sorted((ROOT / "migrations").glob("*.sql")):
        conn.execute(migration.read_text(encoding="utf-8"))
    conn.commit()
    try:
        yield conn, schema
    finally:
        conn.rollback()
        conn.execute("SET search_path TO public")
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()
        conn.close()


def stage(conn, tmp_path, fixture_name, previous=None, *, parser_version=None, with_events=True):
    run_id, snapshot_id = uuid4(), uuid4()
    conn.execute(
        "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','running')",
        (run_id,),
    )
    work = tmp_path / str(run_id)
    output = work / "records.parquet"
    declare_artifact(conn, run_id, "abr", output)
    source = ROOT / "tests" / "fixtures" / "abr" / f"{fixture_name}.xml"
    parsed = parse_xml(source, work)
    if parser_version:
        table = pq.read_table(output)
        table = table.replace_schema_metadata(
            {**table.schema.metadata, b"parser_version": parser_version.encode()}
        )
        pq.write_table(table, output, compression="zstd")
    identity_parts = [
        {
            "part_label": "fixture",
            "members": [{"member_label": "fixture.xml", "uncompressed_sha256": digest_file(source)}],
        }
    ]
    manifest = {
        "snapshot_id": str(snapshot_id),
        "observation_id": str(uuid4()),
        "observed_at": datetime.now(UTC).isoformat(),
        "observation_kind": "fixture_read",
        "schema_version": SCHEMA_VERSION,
        "parser_version": parser_version or PARSER_VERSION,
        "coherence": "validated",
        "generation": parsed.header["generation"],
        "identity_parts": identity_parts,
        "content_digest": content_identity(identity_parts),
        "effective_date": "2026-09-08",
    }
    events = None
    if previous and with_events:
        events = work / "events.parquet"
        declare_artifact(conn, run_id, "abr", events)
        diff_snapshots(
            [previous["path"]],
            [output],
            events,
            snapshot_id=str(snapshot_id),
            previous_snapshot_id=previous["manifest"]["snapshot_id"],
            observed_at=datetime.fromisoformat(manifest["observed_at"]),
            rebaseline=bool(parser_version),
        )
    register_artifacts(conn, run_id, "abr", [output] + ([events] if events else []))
    return {"run_id": run_id, "manifest": manifest, "path": output, "events": events}


def do_promote(conn, service, staged, expected=0, **kwargs):
    return promote(
        conn,
        service,
        staged["run_id"],
        "abr",
        staged["manifest"],
        [staged["path"]],
        events_path=staged["events"],
        expected_version=expected,
        **kwargs,
    )


def test_baseline_change_recurrence_retry_and_current_noop(source_db, service, tmp_path):
    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_baseline")
    assert do_promote(conn, service, a)["events"] == 0
    conn.commit()
    b = stage(conn, tmp_path, "abr_changed", previous=a)
    update = do_promote(conn, service, b, 1)
    assert update["events"] == 5 and update["candidates"] == 1
    conn.commit()
    again = stage(conn, tmp_path, "abr_baseline", previous=b)
    recurrence = do_promote(conn, service, again, 2)
    assert recurrence["events"] > 0 and recurrence["snapshot_id"] != a["manifest"]["snapshot_id"]
    conn.commit()
    assert do_promote(conn, service, again, 2)["replayed"]
    assert conn.execute("SELECT count(*) AS n FROM source_content").fetchone()["n"] == 2
    assert conn.execute("SELECT count(*) AS n FROM source_snapshot").fetchone()["n"] == 3
    assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()["version"] == 3
    unchanged = stage(conn, tmp_path, "abr_baseline", previous=again)
    assert do_promote(conn, service, unchanged, 3)["noop"]
    conn.commit()
    assert do_promote(conn, service, unchanged, 3)["replayed"]


@pytest.mark.parametrize(
    "point",
    ["after_artifacts", "after_snapshot", "after_events", "before_cursor", "after_cursor", "before_commit"],
)
def test_faults_rollback_all_source_effects_and_retry(source_db, service, tmp_path, point):
    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_baseline")
    do_promote(conn, service, a)
    conn.commit()
    b = stage(conn, tmp_path, "abr_changed", previous=a)
    conn.commit()  # retained verified staging is retryable after process failure

    def crash(stage):
        if stage == point:
            raise RuntimeError("injected crash")

    with pytest.raises(RuntimeError, match="injected crash"):
        do_promote(conn, service, b, 1, fault=crash)
    assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()["version"] == 1
    assert conn.execute("SELECT count(*) AS n FROM abr_event").fetchone()["n"] == 0
    assert conn.execute("SELECT count(*) AS n FROM lead_entity").fetchone()["n"] == 0
    assert do_promote(conn, service, b, 1)["events"] == 5
    conn.commit()
    assert do_promote(conn, service, b, 1)["replayed"]


def test_cached_observation_cursor_conflict_and_unverified_artifact_hold(source_db, service, tmp_path):
    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_baseline")
    do_promote(conn, service, a)
    b = stage(conn, tmp_path, "abr_changed", previous=a)
    with pytest.raises(SourceError, match="SOURCE_CURSOR_CONFLICT"):
        do_promote(conn, service, b, 0)
    b["manifest"]["observation_kind"] = "cached_bytes"
    with pytest.raises(SourceError, match="CACHED_BYTES_NOT_NEW_OBSERVATION"):
        do_promote(conn, service, b, 1)
    b["manifest"]["observation_kind"] = "fixture_read"
    original_observation = b["manifest"]["observation_id"]
    b["manifest"]["observation_id"] = a["manifest"]["observation_id"]
    with pytest.raises(SourceError, match="OBSERVATION_ALREADY_USED"):
        do_promote(conn, service, b, 1)
    b["manifest"]["observation_id"] = original_observation
    conn.execute("UPDATE artifact_manifest SET state='writing' WHERE run_id=%s", (b["run_id"],))
    with pytest.raises(SourceError, match="ARTIFACT_NOT_VERIFIED"):
        do_promote(conn, service, b, 1)
    assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()["version"] == 1


def test_source_lock_is_nonblocking_and_source_specific(source_db, service, settings, tmp_path):
    conn, schema = source_db
    staged = stage(conn, tmp_path, "abr_baseline")
    conn.commit()
    other = connect(settings)
    try:
        other.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        other.execute("SELECT pg_advisory_xact_lock(%s)", (source_lock_key("abr", schema),))
        with pytest.raises(SourceError, match="SOURCE_STAGE_LOCK_BUSY"):
            do_promote(conn, service, staged)
        assert conn.execute(
            "SELECT pg_try_advisory_xact_lock(%s) AS ok", (source_lock_key("qbcc", schema),)
        ).fetchone()["ok"]
        other.rollback()
        assert do_promote(conn, service, staged)["cursor_version"] == 1
    finally:
        other.close()


def test_parser_change_requires_explicit_rebaseline(source_db, service, tmp_path):
    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_baseline")
    do_promote(conn, service, a)
    b = stage(conn, tmp_path, "abr_changed", previous=a, parser_version="fixture-abr-v2")
    with pytest.raises(SourceError, match="PARSER_SCHEMA_REBASELINE_REQUIRED"):
        do_promote(conn, service, b, 1)
    b["manifest"]["rebaseline_reason"] = "Synthetic parser-contract migration fixture"
    assert do_promote(conn, service, b, 1, rebaseline=True)["events"] == 0


def test_cancellation_alias_blocks_group_in_same_transaction(source_db, service, tmp_path):
    conn, _ = source_db
    b = stage(conn, tmp_path, "abr_changed")
    do_promote(conn, service, b)
    # Baseline does not create ABR leads; seed a previously known source alias.
    row = pq.read_table(b["path"]).to_pylist()[1]
    lead = service.create_lead(conn, name="Synthetic Known Business", source="abr", alias=row["abn"])
    a = stage(conn, tmp_path, "abr_baseline", previous=b)
    result = do_promote(conn, service, a, 1)
    assert result["events"] > 0
    restriction = conn.execute(
        "SELECT reason FROM suppression_event WHERE group_id=%s", (lead["group_id"],)
    ).fetchone()
    assert restriction["reason"] == "cancellation"
    assert (
        conn.execute("SELECT state FROM candidate_queue WHERE lead_id=%s", (lead["lead_id"],)).fetchone()[
            "state"
        ]
        == "suppressed"
    )


def test_source_alias_cancellation_resolves_merged_family(source_db, service):
    from abr_engine.ops.promotion import _matching_groups, _source_restriction

    conn, _ = source_db
    old = service.create_lead(conn, name="Synthetic merged alias", source="abr", alias="51824753556")
    target = service.create_lead(conn, name="Synthetic surviving business", source="qbcc", alias="9876543")
    conn.execute(
        "UPDATE business_group SET merged_into_group_id=%s WHERE group_id=%s",
        (target["group_id"], old["group_id"]),
    )
    conn.execute("UPDATE lead_entity SET lifecycle='disqualified' WHERE lead_id=%s", (old["lead_id"],))
    assert _matching_groups(conn, service, "51824753556") == {target["group_id"]}
    _source_restriction(conn, service, "51824753556", "abn_cancelled", uuid4())
    assert "SUPPRESSED_CANCELLATION" in service.restricted(conn, target["group_id"])
    assert service.lead(conn, target["lead_id"])["lifecycle"] == "suppressed"


def test_empty_or_forged_full_diff_cannot_advance_cursor(source_db, service, tmp_path):
    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_baseline")
    do_promote(conn, service, a)
    b = stage(conn, tmp_path, "abr_changed", previous=a)
    table = pq.read_table(b["events"])
    pq.write_table(table.slice(0, 0), b["events"], compression="zstd")
    conn.execute("UPDATE artifact_manifest SET state='writing' WHERE run_id=%s", (b["run_id"],))
    register_artifacts(conn, b["run_id"], "abr", [b["path"], b["events"]])
    with pytest.raises(SourceError, match="DIFF_EVENT_SET_MISMATCH"):
        do_promote(conn, service, b, 1)
    assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()["version"] == 1


def test_publication_fill_breach_holds_cursor_and_valid_retry_promotes(source_db, service, tmp_path):
    import pyarrow as pa

    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_baseline")
    do_promote(conn, service, a)
    b = stage(conn, tmp_path, "abr_changed", previous=a)
    table = pq.read_table(b["path"])
    values = table.to_pylist()
    values[0]["postcode"] = None
    pq.write_table(pa.Table.from_pylist(values, schema=table.schema), b["path"], compression="zstd")
    conn.execute("UPDATE artifact_manifest SET state='writing' WHERE run_id=%s", (b["run_id"],))
    register_artifacts(conn, b["run_id"], "abr", [b["path"], b["events"]])
    with pytest.raises(SourceError, match="FIELD_FILL_BREACH"):
        do_promote(conn, service, b, 1)
    assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()["version"] == 1
    assert conn.execute("SELECT count(*) n FROM abr_event").fetchone()["n"] == 0
    pq.write_table(table, b["path"], compression="zstd")
    conn.execute("UPDATE artifact_manifest SET state='writing' WHERE run_id=%s", (b["run_id"],))
    register_artifacts(conn, b["run_id"], "abr", [b["path"], b["events"]])
    assert do_promote(conn, service, b, 1)["cursor_version"] == 2
    stored = conn.execute(
        "SELECT manifest FROM source_snapshot WHERE snapshot_id=%s", (b["manifest"]["snapshot_id"],)
    ).fetchone()["manifest"]
    assert stored["source_rows"] == 3 and stored["field_fill_weighted"]["postcode"] == 1


def test_zero_event_geography_change_disqualifies_existing_profile(source_db, service, tmp_path):
    conn, _ = source_db
    a = stage(conn, tmp_path, "abr_changed")
    do_promote(conn, service, a)
    row = pq.read_table(a["path"]).to_pylist()[0]
    lead = service.create_lead(conn, name="Synthetic Migrating Business", source="abr", alias=row["abn"])
    b = stage(conn, tmp_path, "abr_changed", previous=a)
    table = pq.read_table(b["path"])
    values = table.to_pylist()
    values[0]["state"] = "VIC"
    values[0]["postcode"] = "3000"
    import pyarrow as pa

    pq.write_table(pa.Table.from_pylist(values, schema=table.schema), b["path"], compression="zstd")
    # Model different coherent member content with no named ABR event.
    b["manifest"]["identity_parts"][0]["members"][0]["uncompressed_sha256"] = "a" * 64
    b["manifest"]["content_digest"] = content_identity(b["manifest"]["identity_parts"])
    conn.execute("UPDATE artifact_manifest SET state='writing' WHERE run_id=%s", (b["run_id"],))
    register_artifacts(conn, b["run_id"], "abr", [b["path"], b["events"]])
    assert do_promote(conn, service, b, 1)["events"] == 0
    assert (
        conn.execute("SELECT state FROM candidate_queue WHERE lead_id=%s", (lead["lead_id"],)).fetchone()[
            "state"
        ]
        == "disqualified"
    )


def test_qbcc_backlog_collapses_shared_abn_and_inactive_blocks_group(source_db, service, tmp_path):
    conn, _ = source_db
    source = ROOT / "tests/fixtures/qbcc/synthetic_contractors.csv"
    parsed = parse_qbcc(source)

    def qbcc_stage(result, suffix):
        run_id = uuid4()
        conn.execute(
            "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','running')",
            (run_id,),
        )
        path = tmp_path / f"{suffix}.parquet"
        declare_artifact(conn, run_id, "qbcc", path)
        write_qbcc_parquet(result, path)
        register_artifacts(conn, run_id, "qbcc", [path])
        manifest = {
            "snapshot_id": str(uuid4()),
            "observation_id": str(uuid4()),
            "observed_at": datetime.now(UTC).isoformat(),
            "observation_kind": "fixture_read",
            "schema_version": "qbcc-v1",
            "parser_version": "fixture-qbcc-v1",
            "coherence": "validated",
            "generation": suffix,
            "content_digest": result.source_sha256,
        }
        return run_id, path, manifest

    run, path, manifest = qbcc_stage(parsed, "baseline")
    result = promote(conn, service, run, "qbcc", manifest, [path])
    assert result["events"] == 3 and result["candidates"] == 2
    assert conn.execute("SELECT count(*) AS n FROM lead_entity").fetchone()["n"] == 2
    from dataclasses import replace

    inactive = replace(
        parsed, records=tuple({**r, "status": "SUSPENDED"} for r in parsed.records), source_sha256="a" * 64
    )
    run2, path2, manifest2 = qbcc_stage(inactive, "inactive")
    assert promote(conn, service, run2, "qbcc", manifest2, [path2], expected_version=1)["events"] == 0
    assert (
        conn.execute("SELECT count(*) AS n FROM lead_entity WHERE lifecycle='suppressed'").fetchone()["n"]
        == 2
    )
