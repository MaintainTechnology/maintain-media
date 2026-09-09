import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from abr_engine.db import transaction
from abr_engine.fixture import seed_policy
from abr_engine.ops.monitor import (
    Observation,
    drain_mock,
    monitor_run,
    persist_observation,
    record_control_failure,
)


def run_row(conn):
    run = uuid4()
    conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','monitor-test','test','running')", (run,))
    return run


def test_closed_observation_rejects_personal_fields_and_unreferenced_inventory():
    base = {"run_id": uuid4(), "source": "abr", "observed_at": datetime.now(UTC)}
    for extra in ({"email": "personal@example.com"}, {"flags": ["personal@example.com"]},
                  {"backup_status": "passed"}, {"rss_bytes": -1}, {"source_age_days": float("nan")}):
        with pytest.raises(ValidationError):
            Observation.model_validate({**base, **extra})


def test_inventory_thresholds_are_persisted_deduplicated_and_unknown_explicit(db, service):
    run = run_row(db)
    now = service.now(db)
    observation = Observation(run_id=run, source="abr", observed_at=now, evidence_id=uuid4(),
        source_age_days=11, current_volume=101, comparable_volumes=[10, 10, 10, 10],
        field_fill_delta_pp=2.1, classification_delta_pp=3.1, mismatch_hours=169,
        hit_rate=.1, hit_rate_sample_size=30, approved_hit_rate_baseline=.5,
        approved_hit_rate_drop_pp=20, minimum_hit_rate_sample_size=20,
        free_disk_bytes=1, required_free_disk_bytes=2, rss_bytes=2*1024**3+1,
        timer_last_success_at=now-timedelta(seconds=61), timer_max_interval_seconds=60,
        backup_status="failed", restore_status="failed")
    result = persist_observation(db, observation)
    persist_observation(db, observation)
    expected = {"source_stale", "volume_deviation", "field_fill_breach", "classification_drift",
                "source_mismatch_escalation", "hit_rate_deterioration", "disk_capacity", "memory_limit",
                "timer_heartbeat_missed", "backup_failed", "restore_failed"}
    assert expected <= set(result["alarms"])
    assert "suppression_commit_seconds" in result["unknown_inputs"]
    assert db.execute("SELECT count(*) AS n FROM ops_observation").fetchone()["n"] == 1
    assert db.execute("SELECT count(*) AS n FROM alarm_outbox WHERE run_id=%s", (run,)).fetchone()["n"] == len(expected)


def test_actual_run_resources_policy_heartbeat_and_backup_failure(db, service):
    run = run_row(db)
    db.execute("UPDATE pipeline_run SET heartbeat_at=clock_timestamp()-interval '301 seconds' WHERE run_id=%s", (run,))
    backup = run_row(db)
    db.execute("UPDATE pipeline_run SET code_version='native-backup-drill',state='failed' WHERE run_id=%s", (backup,))
    result = monitor_run(db, service, run, {"resource_sample": {"sampled_peak_rss_bytes": 2*1024**3+1},
                                           "sources": {"abr": {"status": "held", "code": "RECORD_COUNT_MISMATCH"}}})
    alarms = {r["code"] for r in db.execute("SELECT code FROM alarm_outbox WHERE run_id=%s", (run,))}
    assert {"policy_expired", "timer_heartbeat_missed", "memory_limit", "backup_failed", "count_failure"} <= alarms
    assert all("required_free_disk_bytes" in source["unknown_inputs"] for source in result["sources"])
    assert result["notifications_sent"] == 0


def test_distinct_nonbaseline_publications_only_enter_volume_reference(db, service):
    seed_policy(db, service)
    now = service.now(db)
    for i in range(6):
        historical = run_row(db)
        snapshot = uuid4()
        for repeat in range(2):
            persist_observation(db, Observation(run_id=historical, source="abr", observed_at=now-timedelta(days=6-i, seconds=repeat),
                snapshot_id=snapshot, baseline=i==0, no_op=i==1, current_volume=10, member_count=1))
    run = run_row(db)
    result = monitor_run(db, service, run, {"sources": {"abr": {"snapshot_id": str(uuid4()), "candidates": 100, "validation": {"members": 2}}}})
    assert "volume_deviation" in result["sources"][0]["alarms"]
    assert "member_count_changed" in result["sources"][0]["alarms"]
    observation = db.execute("SELECT payload FROM ops_observation WHERE run_id=%s AND source='abr'", (run,)).fetchone()["payload"]
    assert observation["comparable_volumes"] == [10, 10, 10, 10]


def seed_delivery(settings, service):
    with transaction(settings) as conn:
        run = run_row(conn)
        persist_observation(conn, Observation(run_id=run, source="abr", observed_at=service.now(conn), flags={"policy_expired"}))
    return run


def test_mock_delivery_two_workers_one_receipt_and_no_raw_payload(settings, service):
    run = seed_delivery(settings, service)
    with transaction(settings) as conn:
        conn.execute("UPDATE alarm_outbox SET payload=%s WHERE run_id=%s", (Jsonb({"unsafe": "personal@example.com"}), run))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: drain_mock(settings, service), range(2)))
    assert sum(r["delivered_mock"] for r in results) == 1
    with transaction(settings) as conn:
        receipts = conn.execute("SELECT payload FROM ops_mock_delivery").fetchall()
        assert len(receipts) == 1 and "personal@example.com" not in str(receipts)
        assert conn.execute("SELECT state FROM alarm_outbox WHERE run_id=%s", (run,)).fetchone()["state"] == "succeeded"
    assert drain_mock(settings, service)["claimed"] == 0


def test_mock_retry_due_time_and_five_attempt_dead_letter(settings, service):
    run = seed_delivery(settings, service)
    for attempt in range(1, 6):
        result = drain_mock(settings, service, fail=True)
        assert result["retry" if attempt < 5 else "dead_letter"] == 1
        assert drain_mock(settings, service, fail=True)["claimed"] == 0
        with transaction(settings) as conn:
            conn.execute("UPDATE alarm_outbox SET next_attempt_at=clock_timestamp()-interval '1 second' WHERE run_id=%s", (run,))
    with transaction(settings) as conn:
        assert conn.execute("SELECT attempts FROM alarm_outbox WHERE run_id=%s", (run,)).fetchone()["attempts"] == 5
        assert conn.execute("SELECT count(*) AS n FROM ops_mock_delivery").fetchone()["n"] == 0


def test_expired_claim_recovered_and_exhausted_claim_closed(settings, service):
    run = seed_delivery(settings, service)
    with transaction(settings) as conn:
        conn.execute("UPDATE alarm_outbox SET state='inflight',lease_owner=%s,lease_until=clock_timestamp()-interval '1 second',attempts=1 WHERE run_id=%s", (uuid4(), run))
    assert drain_mock(settings, service)["delivered_mock"] == 1
    run = seed_delivery(settings, service)
    with transaction(settings) as conn:
        conn.execute("UPDATE alarm_outbox SET state='inflight',lease_owner=%s,lease_until=clock_timestamp()-interval '1 second',attempts=5 WHERE run_id=%s", (uuid4(), run))
    assert drain_mock(settings, service)["claimed"] == 0
    with transaction(settings) as conn:
        assert conn.execute("SELECT state FROM alarm_outbox WHERE run_id=%s", (run,)).fetchone()["state"] == "dead_letter"


def test_control_failure_inventory_is_closed_and_durable(settings, service):
    run = seed_delivery(settings, service)
    assert record_control_failure(settings, "RECEIPT_CONTENT_MISMATCH")
    assert not record_control_failure(settings, "private@example.com")
    with transaction(settings) as conn:
        assert conn.execute("SELECT 1 FROM alarm_outbox WHERE run_id=%s AND code='invalid_receipt'", (run,)).fetchone()


def test_client_optout_date_does_not_fabricate_server_commit_latency(db, service):
    run = run_row(db)
    lead = service.create_lead(db, name="Synthetic delayed request", source="qbcc", alias="latency-fixture")
    service.suppress(db, {"lead_id": lead["lead_id"], "reason": "unsubscribe", "source": "fixture",
                         "requested_at": service.now(db)-timedelta(hours=1)}, "fixture-operator", uuid4())
    result = monitor_run(db, service, run)
    assert "suppression_commit_delayed" not in result["sources"][0]["alarms"]
    assert "suppression_commit_seconds" in result["sources"][0]["unknown_inputs"]
    observed = db.execute("SELECT payload FROM ops_observation WHERE run_id=%s AND source='abr'", (run,)).fetchone()["payload"]
    assert observed["suppression_commit_seconds"] is None
    assert observed["suppression_request_to_commit_seconds"] > 3500


@pytest.mark.parametrize("fraction,parser,expected", [(0.97, "parser-v1", True), (0.98, "parser-v1", False), (0.9, "parser-v2", False)])
def test_weighted_fill_uses_distinct_matching_contract_publication(db, service, fraction, parser, expected):
    prior_run = run_row(db)
    now = service.now(db)
    contract = {"parser_version": "parser-v1", "schema_version": "schema-v1"}
    digest = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    persist_observation(db, Observation(run_id=prior_run, source="abr", observed_at=now-timedelta(days=1),
        snapshot_id=uuid4(), source_contract_digest=digest, field_fill_weighted={"main_name": 1.0}, source_rows=100))
    run = run_row(db)
    content, snapshot = uuid4(), uuid4()
    db.execute("INSERT INTO source_content(content_id,source,content_digest,schema_version,parser_version,artifact_ref) VALUES(%s,'abr','fixture','schema-v1',%s,'fixture')", (content, parser))
    db.execute("INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,'abr',%s,0,%s,'committed')", (snapshot, content, Jsonb({"parser_version": parser, "schema_version": "schema-v1"})))
    db.execute("INSERT INTO source_cursor(source,snapshot_id,version) VALUES('abr',%s,1)", (snapshot,))
    result = monitor_run(db, service, run, {"sources": {"abr": {"snapshot_id": str(snapshot),
        "validation": {"field_fill_weighted": {"main_name": fraction}, "source_rows": 100}}}})
    assert ("field_fill_breach" in result["sources"][0]["alarms"]) is expected
    observed = db.execute("SELECT payload FROM ops_observation WHERE run_id=%s AND source='abr'", (run,)).fetchone()["payload"]
    assert observed["field_fill_weighted"] == {"main_name": fraction}
    if parser == "parser-v2":
        assert observed["field_fill_delta_pp"] is None
