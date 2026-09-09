import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from abr_engine.db import transaction
from abr_engine.export.crm import load_field_mapping
from abr_engine.export.mock_provider import PersistentMockCRM
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.propagation import drain_propagation


@pytest.fixture
def stop_case(settings, service):
    with transaction(settings) as conn:
        seed_policy(conn, service)
        record = seed_contact(conn, service)
        endpoint = service.keys.decrypt(record["contact"]["encrypted_value"])
    provider = PersistentMockCRM(settings, service.keys)
    group = str(record["lead"]["group_id"])
    mapped = load_field_mapping()["fields"]["abn"]["custom_field_id"]
    remote = provider.create(group, {"group_id": group, "business_name": "Synthetic", "endpoint": endpoint,
        "contact_id": str(record["contact"]["contact_id"]), "channel": "email", "abn": "synthetic",
        "tags": ["maintain-media:candidate", "customer-owned:retain"], "unrelated_notes": "retain fixture note",
        "custom_fields": [{"id": mapped, "value": "synthetic"}, {"id": "customer-owned", "value": "retain"}]}, str(uuid4()))
    with transaction(settings) as conn:
        conn.execute("INSERT INTO crm_identity(location_id,group_id,remote_id) VALUES('fixture',%s,%s)", (group, remote))
        # Endpoint-only stop must propagate despite no business-scoped restriction.
        service.suppress(conn, {"endpoint": endpoint, "channel": "email", "reason": "unsubscribe", "source": "fixture"}, "fixture-operator", uuid4())
    return record, provider, remote


def test_endpoint_only_stop_clears_owned_projection_preserves_other_tags(settings, service, stop_case):
    record, provider, remote = stop_case
    result = drain_propagation(settings, service)
    assert result["notifications_sent"] == 0 and result["results"][0]["state"] == "succeeded"
    assert result["results"][0]["verified_remote_records"] == 1
    assert result["results"][0]["elapsed_since_enqueue_seconds"] < 60
    payload = provider.fetch(remote)["payload"]
    assert payload["endpoint"] is None and payload["contact_id"] is None and payload["business_name"] is None
    assert payload["outreach_blocked"] is True
    assert payload["tags"] == ["customer-owned:retain", "maintain-media:suppressed"]
    assert payload["unrelated_notes"] == "retain fixture note"
    assert payload["custom_fields"][0]["value"] is None and payload["custom_fields"][1]["value"] == "retain"
    with transaction(settings) as conn:
        assert not service.gate(conn, record["contact"]["contact_id"])["allowed"]
        assert conn.execute("SELECT count(*) AS n FROM suppression_event").fetchone()["n"] > 0
        saved = conn.execute("SELECT completed_at,receipt FROM propagation_outbox").fetchone()
        assert saved["completed_at"] and saved["receipt"]["verified_remote_records"] == 1
    assert drain_propagation(settings, service)["results"] == []


def test_unknown_update_reconciles_before_success_without_repeating_write(settings, service, stop_case):
    _, base, remote = stop_case

    class Uncertain(PersistentMockCRM):
        calls = 0

        def update(self, remote_id, payload, request_id):
            self.calls += 1
            super().update(remote_id, payload, request_id)
            raise TimeoutError("unsafe provider error must not be recorded")

    provider = Uncertain(settings, service.keys)
    first = drain_propagation(settings, service, provider=provider)
    assert first["results"][0]["state"] == "retry"
    assert base.fetch(remote)["payload"]["outreach_blocked"]
    with transaction(settings) as conn:
        saved = conn.execute("SELECT * FROM propagation_outbox").fetchone()
        assert saved["completed_at"] is None and saved["receipt"] is None
        assert saved["last_error_code"] == "PROPAGATION_PROVIDER_UNCERTAIN"
        conn.execute("UPDATE propagation_outbox SET next_attempt_at=clock_timestamp()-interval '1 second'")
    assert drain_propagation(settings, service, provider=provider)["results"][0]["state"] == "succeeded"
    assert provider.calls == 1


def test_wrong_remote_identity_is_never_modified(settings, service, stop_case):
    _, base, remote = stop_case

    class Wrong(PersistentMockCRM):
        def fetch(self, remote_id):
            value = super().fetch(remote_id)
            value["group_id"] = str(uuid4())
            return value

        def update(self, *args):
            pytest.fail("wrong group update attempted")

    result = drain_propagation(settings, service, provider=Wrong(settings, service.keys))
    assert result["results"][0]["state"] == "retry"
    assert base.fetch(remote)["payload"]["endpoint"] is not None


def test_provider_io_releases_authority_and_second_worker_cannot_claim(settings, service, stop_case):
    record, _, _ = stop_case
    entered, release = threading.Event(), threading.Event()

    class Slow(PersistentMockCRM):
        def find_group(self, group_id):
            entered.set()
            assert release.wait(10)
            return super().find_group(group_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(drain_propagation, settings, service, provider=Slow(settings, service.keys))
        assert entered.wait(5)
        try:
            assert drain_propagation(settings, service)["results"] == []
            with transaction(settings) as conn:
                conn.execute("SET LOCAL lock_timeout='1s'")
                service.suppress(conn, {"lead_id": record["lead"]["lead_id"], "reason": "unsubscribe", "source": "fixture-race"}, "fixture-operator", uuid4())
        finally:
            release.set()
        assert first.result(timeout=10)["results"][0]["state"] == "succeeded"
    assert drain_propagation(settings, service)["results"][0]["state"] == "succeeded"


def test_quarantine_prevents_provider_projection_and_retry_is_bounded(settings, service, stop_case):
    class Forbidden:
        def find_group(self, group_id):
            pytest.fail("provider accessed under quarantine")

    with transaction(settings) as conn:
        conn.execute("UPDATE system_state SET value='true' WHERE name='restore_quarantine'")
    for index in range(5):
        result = drain_propagation(settings, service, provider=Forbidden())
        assert result["results"][0]["state"] == ("dead_letter" if index == 4 else "retry")
        assert drain_propagation(settings, service, provider=Forbidden())["results"] == []
        with transaction(settings) as conn:
            conn.execute("UPDATE propagation_outbox SET next_attempt_at=clock_timestamp()-interval '1 second'")
    with transaction(settings) as conn:
        row = conn.execute("SELECT completed_at,attempts FROM propagation_outbox").fetchone()
        assert row["completed_at"] is None and row["attempts"] == 5
        assert conn.execute("SELECT count(*) AS n FROM suppression_event").fetchone()["n"] > 0


@pytest.mark.parametrize("dispatched", [False, True])
def test_blocked_approval_without_dispatch_does_not_hold_propagation(settings, service, stop_case, dispatched):
    record, _, _ = stop_case
    with transaction(settings) as conn:
        worklist, row = uuid4(), uuid4()
        conn.execute("INSERT INTO worklist(worklist_id,week) VALUES(%s,'2026-09-07')", (worklist,))
        conn.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,decision,selected_tier,selected_signal) VALUES(%s,%s,%s,'{}','A','qbcc_backlog')", (row, worklist, record["lead"]["lead_id"]))
        conn.execute("INSERT INTO crm_outbox(outbox_id,row_id,location_id,lead_id,approved_version,actor_id,payload_digest,versions,state,operation_kind,dispatched_at) VALUES(%s,%s,'fixture',%s,1,'fixture-reviewer','fixture','{}','blocked','create',%s)",
                     (uuid4(), row, record["lead"]["lead_id"], service.now(conn) if dispatched else None))
    result = drain_propagation(settings, service)
    assert result["results"][0]["state"] == ("retry" if dispatched else "succeeded")
