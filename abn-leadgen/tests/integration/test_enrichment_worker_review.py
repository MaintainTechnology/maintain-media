"""Independent DB regressions at enrichment/merge/erasure boundaries."""
import pytest

from abr_engine.compliance.retention import erase_profile, minimise_database_evidence
from abr_engine.db import transaction
from abr_engine.enrich.worker import SyntheticProvider, drain_one
from abr_engine.fixture import seed_policy
from abr_engine.qualify.identity import merge_groups


class Counting(SyntheticProvider):
    def __init__(self):
        self.calls = []
    def perform(self, operation_id, stage, prior_results, heartbeat):
        self.calls.append((operation_id, stage))
        return super().perform(operation_id, stage, prior_results, heartbeat)


@pytest.mark.parametrize("quarantine", ["restore_quarantine", "key_compromised", "memory"])
def test_quarantine_prevents_any_provider_reservation_or_call(settings, service, quarantine):
    _lead, candidate = seed(settings, service, "88000004")
    if quarantine == "memory":
        service.keys.compromised = True
    else:
        with transaction(settings) as conn:
            conn.execute("INSERT INTO system_state(name,value) VALUES(%s,'true') ON CONFLICT(name) DO UPDATE SET value='true'", (quarantine,))
    provider = Counting()
    result = drain_one(settings, service, provider, candidate_id=candidate)
    assert result["status"] == "blocked" and result["reason"] == "AUTHORITY_QUARANTINED"
    assert not provider.calls
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM budget_reservation").fetchone()["n"] == 0


def seed(settings, service, alias):
    with transaction(settings) as conn:
        if not service.current_policy(conn):
            seed_policy(conn, service)
        lead = service.create_lead(conn, name="Synthetic review", source="qbcc", alias=alias,
            fields={"financial_category": "1", "entity_class": "company"})
        candidate = conn.execute("UPDATE candidate_queue SET state='pending_enrichment' WHERE lead_id=%s RETURNING candidate_id", (lead["lead_id"],)).fetchone()["candidate_id"]
    return lead, candidate


def test_merged_business_cooldown_survives_source_profile_erasure(settings, service):
    a, qa = seed(settings, service, "88000001")
    b, qb = seed(settings, service, "88000002")
    provider = Counting()
    assert drain_one(settings, service, provider, candidate_id=qa)["status"] == "complete"
    assert len(provider.calls) == 3
    with transaction(settings) as conn:
        a, b = service.lead(conn, a["lead_id"]), service.lead(conn, b["lead_id"])
        merge_groups(conn, service, {"source_lead_id": a["lead_id"], "target_lead_id": b["lead_id"],
            "source_revision": a["revision"], "target_revision": b["revision"],
            "evidence_refs": ["registry-corroboration", "reviewed-address"], "reason": "Confirmed same business"}, "reviewer")
        erase_profile(conn, service, a["group_id"])
    result = drain_one(settings, service, provider, candidate_id=qb)
    assert result["status"] == "cached", "Minimal paid-receipt authority must retain the family90d cooldown after erasure"
    assert len(provider.calls) == 3


def test_expired_retained_receipt_body_blocks_without_crash_or_repayment(settings, service):
    _lead, candidate = seed(settings, service, "88000003")
    class Holding(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            result = super().perform(operation_id, stage, prior_results, heartbeat)
            if stage == "lookup":
                with transaction(settings) as conn:
                    conn.execute("UPDATE policy SET expires_at=clock_timestamp()-interval '1 second'")
            return result
    provider = Holding()
    assert drain_one(settings, service, provider, candidate_id=candidate)["reason"] == "COLLECTION_POLICY_BLOCKED"
    with transaction(settings) as conn:
        conn.execute("UPDATE enrichment_operation SET completed_at=clock_timestamp()-interval '91 days'")
        minimise_database_evidence(conn, service, now=service.now(conn), execute=True)
        assert conn.execute("SELECT encrypted_result FROM enrichment_operation").fetchone()["encrypted_result"] is None
        conn.execute("UPDATE policy SET expires_at=clock_timestamp()+interval '30 days'")
        original = conn.execute("SELECT operation_id,reservation_id FROM enrichment_operation").fetchone()
    fresh = Counting()
    result = drain_one(settings, service, fresh, candidate_id=candidate)
    assert result["status"] == "blocked" and result["reason"] == "STAGE_EVIDENCE_EXPIRED"
    assert not fresh.calls
    with transaction(settings) as conn:
        assert conn.execute("SELECT operation_id,reservation_id FROM enrichment_operation").fetchall() == [original]
