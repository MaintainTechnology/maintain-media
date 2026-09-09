"""Committed synthetic groups on isolated PostgreSQL16, real CRM phase transactions."""

import copy
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, json_safe
from abr_engine.db import transaction
from abr_engine.export.crm import MockCRM, approve, drain_one, load_field_mapping, mapped_fields
from abr_engine.fixture import seed_contact, seed_policy


@pytest.fixture
def crm_case(settings, service):
    with transaction(settings) as conn:
        policy = seed_policy(conn, service)
        seeded = seed_contact(conn, service, name="Synthetic CRM recovery")
        lead = seeded["lead"]
        worklist, row = uuid4(), uuid4()
        week = date(3000, 1, 1) + timedelta(days=uuid4().int % 100000)
        conn.execute("INSERT INTO worklist(worklist_id,week) VALUES(%s,%s)", (worklist, week))
        gate = service.gate(conn, seeded["contact"]["contact_id"])
        assert gate["allowed"], gate["reason_codes"]
        conn.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,decision,selected_tier,selected_signal) VALUES(%s,%s,%s,%s,'A','qbcc_backlog')",
                     (row, worklist, lead["lead_id"], Jsonb(json_safe(gate))))
        approved = approve(conn, service, {"row_id": row, "expected_version": 1, "decision": "approve", "reason": "Synthetic reviewed fixture"}, "fixture-reviewer")
        stored = conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s", (approved["outbox_id"],)).fetchone()
        assert "@example.com" not in stored["desired_payload_encrypted"]
    case = {"settings": settings, "service": service, "lead": lead, "row_id": row,
            "outbox_id": approved["outbox_id"], "worklist_id": worklist}
    try:
        yield case
    finally:
        # Only committed identities created by this fixture are removed. No shared table reset.
        with transaction(settings) as conn:
            conn.execute("SET LOCAL abr.retention_delete='on'")
            contact = seeded["contact"]["contact_id"]
            group = lead["group_id"]
            restricted = conn.execute("SELECT 1 FROM suppression_event WHERE group_id=%s", (group,)).fetchone() is not None
            conn.execute("DELETE FROM crm_identity WHERE group_id=%s", (group,))
            conn.execute("DELETE FROM crm_outbox WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("DELETE FROM outcome_event WHERE row_id=%s", (row,))
            conn.execute("DELETE FROM worklist_row WHERE row_id=%s", (row,))
            conn.execute("DELETE FROM worklist WHERE worklist_id=%s", (worklist,))
            conn.execute("DELETE FROM candidate_queue WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("DELETE FROM propagation_outbox WHERE group_id=%s", (group,))
            conn.execute("DELETE FROM deletion_job WHERE group_id=%s", (group,))
            conn.execute("DELETE FROM action_intent WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("DELETE FROM relevance_assessment WHERE contact_id=%s", (contact,))
            conn.execute("DELETE FROM contact_basis WHERE contact_id=%s", (contact,))
            conn.execute("DELETE FROM collection_provenance WHERE contact_id=%s", (contact,))
            conn.execute("DELETE FROM contact_record WHERE contact_id=%s", (contact,))
            conn.execute("DELETE FROM domain_identity WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("DELETE FROM licence_review WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("DELETE FROM lead_source_link WHERE group_id=%s", (group,))
            if not restricted:
                conn.execute("DELETE FROM suppression_alias WHERE group_id=%s", (group,))
            conn.execute("DELETE FROM lead_entity WHERE lead_id=%s", (lead["lead_id"],))
            if not restricted:
                conn.execute("DELETE FROM business_group WHERE group_id=%s", (group,))
            conn.execute("DELETE FROM policy WHERE version=%s", (policy,))


def drain(case, provider):
    return drain_one(case["settings"], case["service"], provider, case["outbox_id"])


def retry_now(case):
    with transaction(case["settings"]) as conn:
        conn.execute("UPDATE crm_outbox SET next_attempt_at=NULL WHERE outbox_id=%s", (case["outbox_id"],))


def stored(case):
    with transaction(case["settings"]) as conn:
        return conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s", (case["outbox_id"],)).fetchone()


def suppress(case):
    with transaction(case["settings"]) as conn:
        return case["service"].suppress(conn, {"lead_id": case["lead"]["lead_id"], "reason": "unsubscribe", "source": "crm-race-fixture"}, "fixture-operator", uuid4())


def test_create_timeout_reconciles_verified_payload_without_duplicate(crm_case):
    provider = MockCRM()
    provider.timeout_after_create = True
    assert drain(crm_case, provider)["state"] == "uncertain"
    assert stored(crm_case)["operation_kind"] == "create"
    retry_now(crm_case)
    assert drain(crm_case, provider)["state"] == "succeeded"
    assert provider.calls == 1 and len(provider.records) == 1
    assert drain(crm_case, provider)["state"] == "succeeded"
    assert provider.calls == 1
    payload = next(iter(provider.records.values()))["payload"]
    mapping = load_field_mapping()
    assert {item["id"] for item in payload["custom_fields"]} == {
        value["custom_field_id"] for value in mapping["fields"].values()
    } | {mapping["identity"]["custom_field_id"]}
    assert payload["custom_field_map_version"] == mapping["mapping_version"]


@pytest.mark.parametrize("after_write", [False, True])
def test_update_timeout_does_not_confuse_existing_identity_with_desired_fields(crm_case, after_write):
    class FailingUpdate(MockCRM):
        fail = True

        def update(self, remote_id, payload, request_id):
            if self.fail:
                self.fail = False
                if after_write:
                    super().update(remote_id, payload, request_id)
                raise TimeoutError("Synthetic update uncertainty")
            super().update(remote_id, payload, request_id)

    provider = FailingUpdate()
    group = str(crm_case["lead"]["group_id"])
    provider.records["existing"] = {"group_id": group, "payload": {"group_id": group, "business_name": "Old", "tags": ["unrelated-tag"]}}
    assert drain(crm_case, provider)["state"] == "uncertain"
    assert stored(crm_case)["operation_kind"] == "update"
    retry_now(crm_case)
    assert drain(crm_case, provider)["state"] == "succeeded"
    assert provider.records["existing"]["payload"]["business_name"] == "Synthetic CRM recovery"
    assert "unrelated-tag" in provider.records["existing"]["payload"]["tags"]
    assert len(provider.records) == 1


def test_lookup_timeout_retries_discovery_and_can_create(crm_case):
    class LookupTimeout(MockCRM):
        fail = True

        def find_group(self, group_id):
            if self.fail:
                self.fail = False
                raise TimeoutError("Lookup timed out before any write")
            return super().find_group(group_id)

    provider = LookupTimeout()
    assert drain(crm_case, provider)["state"] == "retry"
    assert stored(crm_case)["operation_kind"] == "lookup"
    retry_now(crm_case)
    assert drain(crm_case, provider)["state"] == "succeeded"
    assert provider.calls == 1


def test_unknown_create_without_match_never_blindly_creates_again(crm_case):
    class BeforeCreateTimeout(MockCRM):
        def create(self, group_id, payload, request_id):
            self.calls += 1
            raise TimeoutError("Unknown create result")

    provider = BeforeCreateTimeout()
    assert drain(crm_case, provider)["state"] == "uncertain"
    retry_now(crm_case)
    assert drain(crm_case, provider)["state"] == "uncertain"
    assert provider.calls == 1


def test_suppression_can_commit_during_provider_lookup_and_prevents_dispatch(crm_case):
    class SuppressDuringLookup(MockCRM):
        def find_group(self, group_id):
            started = time.perf_counter()
            receipt = suppress(crm_case)
            assert receipt["receipt_id"]
            assert time.perf_counter() - started < 5
            return super().find_group(group_id)

    provider = SuppressDuringLookup()
    assert drain(crm_case, provider)["state"] == "blocked"
    assert provider.calls == 0


def test_inflight_create_after_suppression_commits_adds_new_propagation_work(crm_case):
    class SuppressDuringCreate(MockCRM):
        def create(self, group_id, payload, request_id):
            suppress(crm_case)
            with transaction(crm_case["settings"]) as conn:
                conn.execute("UPDATE propagation_outbox SET state='succeeded',completed_at=now() WHERE group_id=%s", (crm_case["lead"]["group_id"],))
            return super().create(group_id, payload, request_id)

    provider = SuppressDuringCreate()
    assert drain(crm_case, provider)["state"] == "blocked"
    assert len(provider.records) == 1  # In-flight external work cannot be recalled atomically.
    with transaction(crm_case["settings"]) as conn:
        followup = conn.execute("SELECT * FROM propagation_outbox WHERE group_id=%s AND reason='crm_inflight_authority_changed'", (crm_case["lead"]["group_id"],)).fetchall()
        assert len(followup) == 1 and followup[0]["state"] == "pending"


def test_lease_ownership_blocks_second_worker_during_provider_io(crm_case):
    class ReentrantProvider(MockCRM):
        def find_group(self, group_id):
            result = drain(crm_case, MockCRM())
            assert result["state"] == "inflight"
            return super().find_group(group_id)

    provider = ReentrantProvider()
    assert drain(crm_case, provider)["state"] == "succeeded"
    assert provider.calls == 1


def test_worker_crash_after_remote_create_reclaims_by_durable_operation(crm_case):
    class CrashingProvider(MockCRM):
        def create(self, group_id, payload, request_id):
            super().create(group_id, payload, request_id)
            raise RuntimeError("Synthetic worker crash after remote commit")

    provider = CrashingProvider()
    with pytest.raises(RuntimeError, match="worker crash"):
        drain(crm_case, provider)
    assert stored(crm_case)["state"] == "inflight" and stored(crm_case)["operation_kind"] == "create"
    with transaction(crm_case["settings"]) as conn:
        conn.execute("UPDATE crm_outbox SET lease_until=clock_timestamp()-interval '1 second' WHERE outbox_id=%s", (crm_case["outbox_id"],))
    assert drain(crm_case, provider)["state"] == "succeeded"
    assert provider.calls == 1


def test_payload_mismatch_after_successful_response_does_not_mark_success(crm_case):
    class LyingProvider(MockCRM):
        def fetch(self, remote_id):
            result = copy.deepcopy(super().fetch(remote_id))
            result["payload"]["business_name"] = "Wrong value"
            return result

    assert drain(crm_case, LyingProvider())["state"] == "uncertain"


def test_repeated_uncertain_create_dead_letters_without_new_create(crm_case):
    class BeforeCreateTimeout(MockCRM):
        def create(self, group_id, payload, request_id):
            self.calls += 1
            raise TimeoutError("Unknown remote result")

    provider = BeforeCreateTimeout()
    for attempt in range(5):
        retry_now(crm_case)
        result = drain(crm_case, provider)
        assert result["state"] == ("dead_letter" if attempt == 4 else "uncertain")
    assert provider.calls == 1
    assert stored(crm_case)["attempts"] == 5


def test_review_revision_changed_during_lookup_prevents_dispatch(crm_case):
    class ChangeApproval(MockCRM):
        def find_group(self, group_id):
            with transaction(crm_case["settings"]) as conn:
                conn.execute("UPDATE worklist_row SET version=version+1 WHERE row_id=%s", (crm_case["row_id"],))
            return []

    provider = ChangeApproval()
    assert drain(crm_case, provider)["state"] == "blocked"
    assert provider.calls == 0


def test_contradictory_remote_group_is_held_without_updating(crm_case):
    class ContradictoryMatch(MockCRM):
        def find_group(self, group_id):
            return ["unrelated"]

    provider = ContradictoryMatch()
    provider.records["unrelated"] = {"group_id": str(uuid4()), "payload": {"business_name": "Unrelated"}}
    assert drain(crm_case, provider)["state"] == "blocked"
    assert provider.calls == 0


def test_suppressed_crashed_create_reconciles_for_removal_without_new_write(crm_case):
    class CrashingProvider(MockCRM):
        def create(self, group_id, payload, request_id):
            super().create(group_id, payload, request_id)
            raise RuntimeError("Worker vanished")

    provider = CrashingProvider()
    with pytest.raises(RuntimeError, match="vanished"):
        drain(crm_case, provider)
    suppress(crm_case)
    with transaction(crm_case["settings"]) as conn:
        conn.execute("UPDATE crm_outbox SET lease_until=clock_timestamp()-interval '1 second' WHERE outbox_id=%s", (crm_case["outbox_id"],))
    result = drain(crm_case, provider)
    assert result["state"] == "blocked" and result["reconciliation_pending"] is False
    assert provider.calls == 1
    with transaction(crm_case["settings"]) as conn:
        assert conn.execute("SELECT 1 FROM propagation_outbox WHERE group_id=%s AND reason='crm_inflight_reconciled'", (crm_case["lead"]["group_id"],)).fetchone()
        assert conn.execute("SELECT 1 FROM crm_identity WHERE group_id=%s", (crm_case["lead"]["group_id"],)).fetchone()
    assert drain(crm_case, provider)["state"] == "blocked" and provider.calls == 1


@pytest.mark.parametrize("field,value", [("score", True), ("score", 101), ("abn", "123"),
                                         ("tier", "B"), ("website", "javascript:alert(1)"),
                                         ("state", None), ("positioning_notes", "x" * 401)])
def test_typed_mapping_rejects_invalid_actual_projection(field, value):
    values = {"abn": None, "signal": "qbcc_backlog", "score": 90, "tier": "A", "industry": None,
              "entity_class": None, "state": "QLD", "website": None, "positioning_notes": None, "basis_summary": None}
    values[field] = value
    with pytest.raises(DomainError):
        mapped_fields(values, load_field_mapping())


def test_duplicate_custom_field_ids_fail_closed(tmp_path):
    root = Path(__file__).resolve().parents[2]
    mapping = yaml.safe_load((root / "integrations/crm_fields.yaml").read_text())
    mapping["fields"]["score"]["custom_field_id"] = mapping["fields"]["tier"]["custom_field_id"]
    invalid = tmp_path / "mapping.yaml"
    invalid.write_text(yaml.safe_dump(mapping), encoding="utf-8")
    with pytest.raises(DomainError, match="CRM_MAPPING_IDS_INVALID"):
        load_field_mapping(invalid)
