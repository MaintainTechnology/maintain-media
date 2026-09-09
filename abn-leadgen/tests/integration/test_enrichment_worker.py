"""Actual PostgreSQL commits around injected offline provider boundaries."""

from uuid import uuid4

import pytest

from abr_engine.db import transaction
from abr_engine.enrich.worker import ProviderResult, SyntheticProvider, drain_one
from abr_engine.fixture import seed_policy


@pytest.fixture
def candidate(settings, service):
    with transaction(settings) as conn:
        seed_policy(conn, service)
        lead = service.create_lead(
            conn,
            name="Synthetic worker",
            source="qbcc",
            alias="12345678",
            fields={"financial_category": "1", "entity_class": "company"},
        )
        queue = conn.execute("SELECT * FROM candidate_queue WHERE lead_id=%s", (lead["lead_id"],)).fetchone()
        conn.execute(
            "UPDATE candidate_queue SET state='pending_enrichment' WHERE candidate_id=%s",
            (queue["candidate_id"],),
        )
    return lead, queue


class Counting(SyntheticProvider):
    def __init__(self):
        self.calls = []
        self.reconciles = []

    def perform(self, operation_id, stage, prior_results, heartbeat):
        self.calls.append((operation_id, stage))
        return super().perform(operation_id, stage, prior_results, heartbeat)

    def reconcile(self, operation_id, stage, prior_results, heartbeat):
        self.reconciles.append((operation_id, stage))
        return super().perform(operation_id, stage, prior_results, heartbeat)


def test_complete_receipts_scores_and_lead_wide_cache(settings, service, candidate):
    _lead, queue = candidate
    provider = Counting()
    assert drain_one(settings, service, provider, candidate_id=queue["candidate_id"])["status"] == "complete"
    assert len(provider.calls) == 3
    with transaction(settings) as conn:
        assert (
            conn.execute("SELECT count(*) n FROM enrichment_operation WHERE state='complete'").fetchone()["n"]
            == 3
        )
        assert (
            conn.execute("SELECT count(*) n FROM budget_reservation WHERE state='settled'").fetchone()["n"]
            == 3
        )
        q = conn.execute(
            "SELECT * FROM candidate_queue WHERE candidate_id=%s", (queue["candidate_id"],)
        ).fetchone()
        assert q["last_attempt_at"] and q["score"] == 90
        service.create_lead(
            conn,
            name="Synthetic worker",
            source="qbcc",
            alias="12345678",
            event_key=str(uuid4()),
            fields={"financial_category": "1"},
        )
    assert drain_one(settings, service, provider)["status"] == "cached"
    assert len(provider.calls) == 3


def test_unknown_response_reconciles_same_id_and_never_repays(settings, service, candidate):
    provider = Counting()

    def crash(point):
        if point == "after_provider_response":
            raise OSError("synthetic process death")

    with pytest.raises(OSError):
        drain_one(settings, service, provider, fault=crash)
    assert len(provider.calls) == 1
    with transaction(settings) as conn:
        conn.execute("UPDATE enrichment_attempt SET lease_until=clock_timestamp()-interval '1 second'")
        conn.execute("UPDATE candidate_queue SET lease_until=clock_timestamp()-interval '1 second'")
    assert drain_one(settings, service, provider)["status"] == "complete"
    assert provider.reconciles[0] == provider.calls[0]
    assert [stage for _, stage in provider.calls] == ["lookup", "crawl", "verify"]


def test_nonzero_budget_stop_is_resumable_and_not_attempted(settings, service, candidate):
    class Paid(Counting):
        def tariff(self, stage, now):
            return {**super().tariff(stage, now), "native_upper_bound": "200"}

    provider = Paid()
    result = drain_one(settings, service, provider)
    assert result["reason"] == "BUDGET_STOP" and not provider.calls
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM budget_reservation").fetchone()["n"] == 0
        row = conn.execute("SELECT * FROM enrichment_attempt").fetchone()
        assert row["next_eligible_at"] is None and row["finished_at"] is None
        assert (
            conn.execute("SELECT last_attempt_at FROM candidate_queue").fetchone()["last_attempt_at"] is None
        )
    assert drain_one(settings, service, Counting())["status"] == "complete"


def test_suppression_during_transport_settles_but_never_applies(settings, service, candidate):
    lead, _ = candidate
    applied = []

    class Suppressing(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            with transaction(settings) as conn:
                service.suppress(
                    conn,
                    {"group_id": lead["group_id"], "reason": "unsubscribe", "source": "fixture"},
                    "fixture-reviewer",
                    str(uuid4()),
                )
            return super().perform(operation_id, stage, prior_results, heartbeat)

    result = drain_one(settings, service, Suppressing(), apply_result=lambda *args: applied.append(args))
    assert result["reason"] == "SUPPRESSED" and applied == []
    with transaction(settings) as conn:
        assert conn.execute("SELECT state FROM budget_reservation").fetchone()["state"] == "settled"
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0


@pytest.mark.parametrize(
    "state,expected", [("exhausted", "exhausted"), ("quota", "blocked"), ("uncertain", "blocked")]
)
def test_discovery_failure_vs_interruption(settings, service, candidate, state, expected):
    class Failure(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            return ProviderResult(
                state,
                None if state == "uncertain" else 0,
                None if state == "uncertain" else "fixture:" + str(operation_id),
            )

    assert drain_one(settings, service, Failure())["status"] == expected
    with transaction(settings) as conn:
        row = conn.execute("SELECT * FROM enrichment_attempt").fetchone()
        assert bool(row["next_eligible_at"]) == (state == "exhausted")


def test_claim_excludes_concurrent_worker_and_policy_revocation(settings, service, candidate):
    class Racing(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            assert drain_one(settings, service, Counting())["status"] == "idle"
            with transaction(settings) as conn:
                conn.execute("UPDATE policy SET expires_at=clock_timestamp()-interval '1 second'")
            return super().perform(operation_id, stage, prior_results, heartbeat)

    assert drain_one(settings, service, Racing())["reason"] == "COLLECTION_POLICY_BLOCKED"


def test_final_receipt_survives_policy_hold_without_provider_repay(settings, service, candidate):
    class FinalHold(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            result = super().perform(operation_id, stage, prior_results, heartbeat)
            if stage == "verify":
                with transaction(settings) as conn:
                    conn.execute("UPDATE policy SET expires_at=clock_timestamp()-interval '1 second'")
            return result

    provider = FinalHold()
    applied = []
    assert (
        drain_one(settings, service, provider, apply_result=lambda *args: applied.append(True))["reason"]
        == "COLLECTION_POLICY_BLOCKED"
    )
    assert not applied
    with transaction(settings) as conn:
        conn.execute("UPDATE policy SET expires_at=clock_timestamp()+interval '89 days'")
    assert (
        drain_one(settings, service, provider, apply_result=lambda *args: applied.append(True))["status"]
        == "complete"
    )
    assert len(provider.calls) == 3 and not provider.reconciles and applied == [True]


def test_expired_lease_response_cannot_apply_and_reconciles(settings, service, candidate):
    class Expiring(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            result = super().perform(operation_id, stage, prior_results, heartbeat)
            with transaction(settings) as conn:
                conn.execute(
                    "UPDATE enrichment_attempt SET lease_until=clock_timestamp()-interval '1 second'"
                )
                conn.execute("UPDATE candidate_queue SET lease_until=clock_timestamp()-interval '1 second'")
            return result

    applied = []
    assert (
        drain_one(settings, service, Expiring(), apply_result=lambda *args: applied.append(True))["reason"]
        == "LEASE_LOST"
    )
    assert not applied
    provider = Counting()
    assert drain_one(settings, service, provider)["status"] == "complete"
    assert len(provider.reconciles) == 1 and len(provider.calls) == 2


def test_exhausted_receipt_after_policy_hold_never_starts_later_stages(settings, service, candidate):
    class ExhaustedHold(Counting):
        def perform(self, operation_id, stage, prior_results, heartbeat):
            self.calls.append((operation_id, stage))
            with transaction(settings) as conn:
                conn.execute("UPDATE policy SET expires_at=clock_timestamp()-interval '1 second'")
            return ProviderResult("exhausted", 0, "fixture:" + str(operation_id))

    provider = ExhaustedHold()
    assert drain_one(settings, service, provider)["reason"] == "COLLECTION_POLICY_BLOCKED"
    with transaction(settings) as conn:
        conn.execute("UPDATE policy SET expires_at=clock_timestamp()+interval '30 days'")
    assert drain_one(settings, service, provider)["status"] == "exhausted"
    assert len(provider.calls) == 1 and not provider.reconciles
