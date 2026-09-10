"""Actual isolated PG16 and encrypted local objects; no live providers or approvals."""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from test_production_backup_runtime import setup_backup

from abr_engine.compliance.retention import erase_profile
from abr_engine.db import connect
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops import backup_queue as queue

sys.path.insert(0, str(Path(__file__).parents[2] / "ops/aws"))
import backup_runtime as runtime
import backup_schedule as schedule
from backup_crypto import BackupError


def current(settings):
    with connect(settings) as conn:
        return queue.state(conn)


def test_commit_coalesces_all_changes_and_rollback_leaves_no_intent(settings):
    assert current(settings)["generation"] == 1
    with connect(settings) as conn:
        conn.execute("INSERT INTO business_group(group_id) VALUES(%s)", (uuid4(),))
        conn.rollback()
    assert current(settings)["generation"] == 1
    with connect(settings) as conn:
        for _ in range(80):
            group = uuid4()
            conn.execute("INSERT INTO business_group(group_id) VALUES(%s)", (group,))
            conn.execute("INSERT INTO deletion_job(job_id,group_id) VALUES(%s,%s)", (uuid4(), group))
        assert queue.state(conn)["generation"] == 1  # Deferred until commit.
    assert current(settings)["generation"] == 2
    with connect(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM backup_ledger_state").fetchone()["n"] == 1


def test_concurrent_commit_and_claims_do_not_deadlock_or_drop_generation(settings):
    barrier = threading.Barrier(4)
    def write(_):
        with connect(settings) as conn:
            conn.execute("INSERT INTO business_group(group_id) VALUES(%s)", (uuid4(),))
            barrier.wait(timeout=10)
        return True
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(write, range(4)))
    assert current(settings)["generation"] == 5
    def claim(_):
        with connect(settings) as conn:
            return queue.claim_attempt(conn) is not None
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(claim, range(4))) == 1


def test_snapshot_capture_and_upload_never_clear_later_committed_restriction(settings, service, tmp_path, monkeypatch):
    key, authority, store, staging = setup_backup(tmp_path)
    with connect(settings) as conn:
        seed_policy(conn, service)
        contact = seed_contact(conn, service)
    captured = current(settings)["generation"]
    original = store.put_verified
    def upload(*args, **kwargs):
        # This actual restriction commits during provider I/O; worker holds no DB lock.
        with connect(settings) as conn:
            service.suppress(conn, {"lead_id": contact["lead"]["lead_id"], "reason": "unsubscribe", "source": "synthetic"}, "fixture", uuid4())
            erase_profile(conn, service, contact["lead"]["group_id"])
        return original(*args, **kwargs)
    monkeypatch.setattr(store, "put_verified", upload)
    receipt = runtime.publish_ledger(settings, service, authority, key.public_key(), store, staging)
    state = current(settings)
    assert receipt["captured_generation"] == state["acknowledged_generation"] == captured
    assert state["generation"] > captured and state["pending_since"] is not None
    monkeypatch.setattr(store, "put_verified", original)
    runtime.publish_ledger(settings, service, authority, key.public_key(), store, staging)
    state = current(settings)
    assert state["generation"] == state["acknowledged_generation"] and state["pending_since"] is None


def test_repeatable_read_excludes_commit_after_generation_capture(settings, service, tmp_path, monkeypatch):
    key, authority, store, staging = setup_backup(tmp_path)
    exported = []
    old = runtime.export_ledger
    def capture(conn, service, **kwargs):
        with connect(settings) as writer:
            writer.execute("INSERT INTO business_group(group_id) VALUES(%s)", (uuid4(),))
        value = old(conn, service, **kwargs)
        payload = json.loads(service.keys.decrypt(value))
        exported.append(payload)
        return value
    monkeypatch.setattr(runtime, "export_ledger", capture)
    receipt = runtime.publish_ledger(settings, service, authority, key.public_key(), store, staging)
    assert exported[0]["groups"] == []
    assert current(settings)["generation"] > receipt["captured_generation"]


def test_uncommitted_change_is_not_acknowledged_then_commit_remains_pending(settings, service, tmp_path):
    key, authority, store, staging = setup_backup(tmp_path)
    with connect(settings) as writer:
        writer.execute("INSERT INTO business_group(group_id) VALUES(%s)", (uuid4(),))
        receipt = runtime.publish_ledger(settings, service, authority, key.public_key(), store, staging)
        assert receipt["captured_generation"] == 1
    assert current(settings)["generation"] == 2 and current(settings)["acknowledged_generation"] == 1


def test_failure_and_revoked_authority_preserve_queue_without_secret_diagnostics(settings, service, tmp_path, monkeypatch):
    key, authority, store, staging = setup_backup(tmp_path)
    monkeypatch.setattr(store, "put_verified", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("SECRET_PROVIDER_BODY")))
    result = schedule.run_worker(settings, service, authority, key.public_key(), store, staging)
    assert result == {"status": "held", "code": "BACKUP_PUBLISH_FAILED", "acknowledged": False}
    state = current(settings)
    assert state["acknowledged_generation"] == 0 and state["last_error"] == "BACKUP_PUBLISH_FAILED"
    assert "SECRET" not in json.dumps(result)
    # Cadence survives failure/restart and surfaces the stored failure, without new I/O.
    result = schedule.run_worker(settings, service, authority, key.public_key(), store, staging)
    assert result["status"] == "held" and result["provider_operations"] == 0


def test_authority_withdrawn_after_upload_does_not_acknowledge(settings, service, tmp_path, monkeypatch):
    key, authority, store, staging = setup_backup(tmp_path)
    old = runtime._admit
    count = 0
    def admit(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 3:
            raise BackupError("SYNTHETIC_AUTHORITY_WITHDRAWN")
        return old(*args, **kwargs)
    monkeypatch.setattr(runtime, "_admit", admit)
    with pytest.raises(BackupError, match="WITHDRAWN"):
        runtime.publish_ledger(settings, service, authority, key.public_key(), store, staging)
    assert store.objects and current(settings)["acknowledged_generation"] == 0


def test_worker_cadence_baseline_retry_and_success_are_durable(settings, service, tmp_path):
    key, authority, store, staging = setup_backup(tmp_path)
    assert schedule.run_worker(settings, service, authority, key.public_key(), store, staging)["status"] == "acknowledged"
    count = len(store.objects)
    with connect(settings) as conn:
        conn.execute("INSERT INTO business_group(group_id) VALUES(%s)", (uuid4(),))
    assert schedule.run_worker(settings, service, authority, key.public_key(), store, staging)["status"] == "coalesced"
    assert len(store.objects) == count
    with connect(settings) as conn:
        conn.execute("UPDATE backup_ledger_state SET last_attempt_at=clock_timestamp()-interval '241 seconds'")
    assert schedule.run_worker(settings, service, authority, key.public_key(), store, staging)["status"] == "acknowledged"
    assert len(store.objects) == count + 1


def test_busy_capture_does_not_block_ledger_and_publication_busy_is_not_failure(settings, service, tmp_path):
    key, authority, store, staging = setup_backup(tmp_path)
    with runtime.publication_lease(staging, capture=True):
        assert schedule.run_worker(settings, service, authority, key.public_key(), store, staging)["status"] == "acknowledged"
    with runtime.publication_lease(staging):
        assert schedule.run_worker(settings, service, authority, key.public_key(), store, staging)["status"] == "deferred"
    assert current(settings)["consecutive_failures"] == 0


def test_failed_counter_saturates_and_overdue_is_visible(settings):
    with connect(settings) as conn:
        conn.execute("UPDATE backup_ledger_state SET consecutive_failures=2147483647,pending_since=clock_timestamp()-interval '6 minutes'")
        queue.failed(conn, "arbitrary-private-error")
        assert queue.state(conn)["consecutive_failures"] == 2147483647
        assert queue.health(conn)["acknowledgement_overdue"] is True


def test_recent_ack_of_old_snapshot_is_still_overdue(settings):
    from datetime import UTC, datetime, timedelta
    with connect(settings) as conn:
        queue.acknowledge(conn, 1, {"object_id": str(uuid4()), "sha256": "a"*64, "encrypted_bytes": 100,
            "ledger_watermark": (datetime.now(UTC)-timedelta(minutes=6)).isoformat()})
        value = queue.health(conn)
        assert value["acknowledgement_age_seconds"] < 5 and value["snapshot_age_seconds"] >= 360
        assert value["acknowledgement_overdue"] is True


def test_current_gate_denial_happens_before_provider_even_for_queued_worker(settings, service, tmp_path):
    key, authority, store, staging = setup_backup(tmp_path)
    from datetime import UTC, datetime, timedelta
    authority.expires_at = datetime.now(UTC)-timedelta(seconds=1)
    assert schedule.run_worker(settings, service, authority, key.public_key(), store, staging)["status"] == "held"
    assert store.objects == {} and current(settings)["acknowledged_generation"] == 0
