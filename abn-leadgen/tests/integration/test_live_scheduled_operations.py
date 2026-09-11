"""Actual isolated PostgreSQL scheduled admission and gated maintenance."""
# ruff: noqa: F811 -- imported fixtures are intentionally injected by name.
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from test_live_qbcc import accepted  # noqa: F401
from test_live_qbcc_runtime import prepared  # noqa: F401
from test_live_retention import approved_retention  # noqa: F401
from test_qbcc_review_stage import live  # noqa: F401

from abr_engine.db import transaction
from abr_engine.live import abr_cleanup, schedule
from abr_engine.live import artifact_retention as live_artifacts


@pytest.fixture
def source_live(live):
    return live


@pytest.fixture
def isolated(settings, monkeypatch):
    for module in (schedule, abr_cleanup, live_artifacts):
        monkeypatch.setattr(module, "transaction", lambda ignored: transaction(settings))


def test_repeated_and_concurrent_weekly_admission_creates_one_durable_job(settings, prepared, isolated):
    adapter, calls, _, _, _ = prepared
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: schedule.submit_weekly(adapter.settings, runtime=adapter), range(2)))
    assert results[0]["job"]["job_id"] == results[1]["job"]["job_id"]
    assert all(row["job"]["state"] == "queued" for row in results) and calls == []
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM pipeline_run WHERE manifest->>'kind'='qbcc_live_job'").fetchone()["n"] == 1
    done = adapter.execute_pending(limit=1)
    assert done[0]["state"] == "complete" and len(calls) == 3
    repeated = schedule.submit_weekly(adapter.settings, runtime=adapter)
    assert repeated["job"]["state"] == "complete" and len(calls) == 3


def test_closed_weekly_gate_records_hold_without_keys_or_http(settings, prepared, isolated, monkeypatch):
    from abr_engine.live import runtime
    adapter, calls, _, _, _ = prepared
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE gate_name='G1'")
    monkeypatch.setattr(runtime, "load_keys", lambda _: pytest.fail("Closed admission must not load keys"))
    result = schedule.submit_weekly(adapter.settings, runtime=adapter)
    assert result["status"] == "held" and "GATE_G1_CLOSED" in result["job"]["reason_codes"]
    assert adapter.execute_pending() == [] and calls == []
    assert schedule.submit_weekly(adapter.settings, runtime=adapter)["job"]["job_id"] == result["job"]["job_id"]


def test_live_maintenance_requires_current_retention_policy(settings, approved_retention, isolated):
    config, _, _ = approved_retention
    with transaction(settings) as conn:
        conn.execute("UPDATE lead_entity SET last_qualifying_at=clock_timestamp()-interval '181 days'")
    preview = schedule.maintenance(config, kind="retention")
    assert preview["status"] == "preview" and len(preview["result"]["due_groups"]) == 1
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE scope='retention' AND gate_name='G1'")
    held = schedule.maintenance(config, kind="retention", execute=True)
    assert held["status"] == "held" and held["reason_codes"] == ["GATE_G1_CLOSED"]
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 1


def test_live_maintenance_applies_approved_retention_after_collection_withdrawal(settings, approved_retention, isolated):
    config, _, _ = approved_retention
    config = config.model_copy(update={"capabilities": {"retention": True}})
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE scope='collection'")
        conn.execute("UPDATE lead_entity SET last_qualifying_at=clock_timestamp()-interval '181 days'")
    result = schedule.maintenance(config, kind="retention", execute=True)
    assert result["status"] == "complete"
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM suppression_alias").fetchone()["n"] > 0


@pytest.mark.parametrize("held", [False, True])
def test_review_staging_cleanup_remains_owned_and_hold_aware_after_collection_withdrawal(settings, live, isolated, held):
    from abr_engine.ingest.qbcc_review import stage_qbcc_review
    config, request, _ = live
    stage_qbcc_review(config, request)
    with transaction(settings) as conn:
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '8 days' WHERE run_id=%s", (request.run_id,))
        conn.execute("DELETE FROM release_gate WHERE scope='collection'")
        if held:
            conn.execute("INSERT INTO retention_hold VALUES(%s,'run',%s,'synthetic-owner','synthetic hold',clock_timestamp()+interval '1 day')", (uuid4(), str(request.run_id)))
    config = config.model_copy(update={"capabilities": {}})
    preview = schedule.maintenance(config, kind="review-staging")
    assert preview["status"] == ("held" if held else "preview")
    result = schedule.maintenance(config, kind="review-staging", execute=True)
    assert result["status"] == ("held" if held else "complete")
    assert result["result"]["decrypted_records"] == 0
    with transaction(settings) as conn:
        rows = conn.execute("SELECT state,local_path FROM artifact_manifest WHERE run_id=%s", (request.run_id,)).fetchall()
        assert len(rows) == 2
        assert all(row["state"] == ("verified" if held else "deleted") for row in rows)


@pytest.mark.parametrize("execute", [False, True])
@pytest.mark.parametrize("age_days", [0, 8])
def test_review_staging_skips_accepted_durable_source_at_any_age(settings, accepted, isolated, execute, age_days):
    config, request, _, _ = accepted
    with transaction(settings) as conn:
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-(%s * interval '1 day') WHERE run_id=%s", (age_days, request.run_id))
        before_run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request.run_id,)).fetchone()
        before_artifacts = conn.execute("SELECT * FROM artifact_manifest WHERE run_id=%s ORDER BY artifact_id", (request.run_id,)).fetchall()
        before_cursor = conn.execute("SELECT * FROM source_cursor WHERE source='qbcc'").fetchone()
        assert before_run["state"] == "complete" and before_run["manifest"]["intake_state"] == "accepted"
        assert all(row["state"] == "referenced" and row["snapshot_id"] for row in before_artifacts)
    saved_bytes = {row["local_path"]: Path(row["local_path"]).read_bytes() for row in before_artifacts}
    result = schedule.maintenance(config, kind="review-staging", execute=execute)
    assert result["status"] == ("complete" if execute else "preview")
    assert result["result"]["runs"] == []
    with transaction(settings) as conn:
        assert conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request.run_id,)).fetchone() == before_run
        assert conn.execute("SELECT * FROM artifact_manifest WHERE run_id=%s ORDER BY artifact_id", (request.run_id,)).fetchall() == before_artifacts
        assert conn.execute("SELECT * FROM source_cursor WHERE source='qbcc'").fetchone() == before_cursor
    assert all(Path(path).read_bytes() == data for path, data in saved_bytes.items())


def test_review_staging_still_expires_unreferenced_attempt_beside_accepted_source(settings, accepted, isolated):
    from abr_engine.ingest.qbcc_review import stage_qbcc_review
    config, accepted_request, _, _ = accepted
    with transaction(settings) as conn:
        cursor = conn.execute("SELECT version FROM source_cursor WHERE source='qbcc'").fetchone()["version"]
    pending = accepted_request.model_copy(update={"run_id": uuid4(), "expected_cursor_version": cursor})
    stage_qbcc_review(config, pending)
    with transaction(settings) as conn:
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '8 days'")
        accepted_files = conn.execute("SELECT local_path FROM artifact_manifest WHERE run_id=%s", (accepted_request.run_id,)).fetchall()
    result = schedule.maintenance(config, kind="review-staging", execute=True)
    assert result["status"] == "complete"
    assert result["result"]["runs"] == [{"run_id": str(pending.run_id), "state": "deleted", "deleted_files": 2}]
    with transaction(settings) as conn:
        assert all(row["state"] == "referenced" for row in conn.execute("SELECT state FROM artifact_manifest WHERE run_id=%s", (accepted_request.run_id,)))
        assert all(row["state"] == "deleted" for row in conn.execute("SELECT state FROM artifact_manifest WHERE run_id=%s", (pending.run_id,)))
    assert all(Path(row["local_path"]).is_file() for row in accepted_files)


@pytest.mark.parametrize("change", ["unknown_lifecycle", "missing_lifecycle", "missing_receipt", "false_receipt", "incomplete_state"])
def test_review_staging_inconsistent_accepted_state_remains_held(settings, accepted, isolated, change):
    from psycopg.types.json import Jsonb
    config, request, _, _ = accepted
    with transaction(settings) as conn:
        run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request.run_id,)).fetchone()
        manifest = run["manifest"]
        if change == "unknown_lifecycle":
            manifest["intake_state"] = "unexpected"
        elif change == "missing_lifecycle":
            manifest.pop("intake_state")
        elif change == "missing_receipt":
            manifest.pop("acceptance_receipt")
        elif change == "false_receipt":
            manifest["acceptance_receipt"]["accepted"] = False
        conn.execute("UPDATE pipeline_run SET state=%s,manifest=%s WHERE run_id=%s", ("held" if change == "incomplete_state" else "complete", Jsonb(manifest), request.run_id))
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '8 days' WHERE run_id=%s", (request.run_id,))
        files = conn.execute("SELECT local_path FROM artifact_manifest WHERE run_id=%s", (request.run_id,)).fetchall()
    result = schedule.maintenance(config, kind="review-staging", execute=True)
    assert result["status"] == "held"
    assert result["result"]["runs"][0]["state"] == "held"
    assert result["result"]["runs"][0]["deleted_files"] == 0
    assert all(Path(row["local_path"]).is_file() for row in files)


def test_accepted_noop_uses_existing_ordinary_artifact_retention_without_changing_cursor(settings, accepted, approved_retention, isolated):
    from abr_engine.compliance.retention import artifact_retention
    from abr_engine.control.service import Service
    from abr_engine.ingest.qbcc_review import stage_qbcc_review
    from abr_engine.live.qbcc import accept_qbcc_snapshot
    config, keys, _ = approved_retention
    _, original, _, _ = accepted
    with transaction(settings) as conn:
        before_cursor = conn.execute("SELECT * FROM source_cursor WHERE source='qbcc'").fetchone()
    duplicate = original.model_copy(update={"run_id": uuid4(), "expected_cursor_version": before_cursor["version"]})
    stage_qbcc_review(config, duplicate)
    accepted_noop = accept_qbcc_snapshot(config, duplicate.run_id, before_cursor["version"], "synthetic-reviewer")
    assert accepted_noop["accepted"] and accepted_noop["noop"]
    with transaction(settings) as conn:
        files = conn.execute("SELECT * FROM artifact_manifest WHERE run_id=%s", (duplicate.run_id,)).fetchall()
        assert len(files) == 3 and all(row["snapshot_id"] is None and row["state"] == "verified" for row in files)
        # Completed/no-op files already use their explicit raw/snapshot classes;
        # the seven-day orphan rule still applies only to abandoned staging.
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '8 days' WHERE run_id=%s", (duplicate.run_id,))
        pending = artifact_retention(conn, Service(config, keys), now=Service.now(conn))
        assert not any(row["state"] == "due" for row in pending)
    cleanup = schedule.maintenance(config, kind="review-staging", execute=True)
    assert cleanup["status"] == "complete" and cleanup["result"]["runs"] == []
    assert all(Path(row["local_path"]).is_file() for row in files)
    with transaction(settings) as conn:
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '91 days' WHERE run_id=%s", (duplicate.run_id,))
        retained = artifact_retention(conn, Service(config, keys), now=Service.now(conn), execute=True)
        ids = {str(row["artifact_id"]) for row in files}
        assert all(row["state"] == "deleted" for row in retained if row["artifact_id"] in ids)
        assert conn.execute("SELECT * FROM source_cursor WHERE source='qbcc'").fetchone() == before_cursor
        assert all(row["state"] == "deleted" for row in conn.execute("SELECT state FROM artifact_manifest WHERE run_id=%s", (duplicate.run_id,)))
    assert all(not Path(row["local_path"]).exists() for row in files)
