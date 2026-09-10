"""Actual isolated PostgreSQL scheduled admission and gated maintenance."""
# ruff: noqa: F811 -- imported fixtures are intentionally injected by name.
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from test_live_qbcc import accepted  # noqa: F401
from test_live_qbcc_runtime import prepared  # noqa: F401
from test_live_retention import approved_retention  # noqa: F401
from test_qbcc_review_stage import live  # noqa: F401

from abr_engine.db import transaction
from abr_engine.live import schedule


@pytest.fixture
def source_live(live):
    return live


@pytest.fixture
def isolated(settings, monkeypatch):
    monkeypatch.setattr(schedule, "transaction", lambda ignored: transaction(settings))


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
