from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from abr_engine.compliance.retention import minimise_database_evidence
from abr_engine.control.service import DomainError
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.costs import CATEGORIES, CostStatement, import_costs
from abr_engine.ops.summary import operational_summary


def setup(db, service):
    seed_policy(db, service)
    record = seed_contact(db, service)
    now = service.now(db)
    work = build_worklist(db, service, now.date()-timedelta(days=now.weekday()))
    start, end = now-timedelta(hours=2), now-timedelta(hours=1)
    db.execute("UPDATE worklist SET generated_at=%s WHERE worklist_id=%s", (start-timedelta(days=1), work["worklist_id"]))
    db.execute("INSERT INTO operator_activity(activity_id,actor_id,worklist_id,lead_id,category,started_at,ended_at) VALUES(%s,'fixture-operator',%s,%s,'research',%s,%s)",
        (uuid4(), work["worklist_id"], record["lead"]["lead_id"], start, end))
    run = uuid4()
    db.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','complete')", (run,))
    return now, start, end, run, work["worklist_id"]


def statement(now, start, end, **changes):
    cash = [{"category": category, "vendor": "Fixture supplier", "currency": "USD", "gross_native": "2.50",
        "tax_native": "0.50", "fx_to_aud": "1.6", "fx_date": start.date(), "unit_tariff_native": "2.50",
        "minimum_commitment_native": "2.50", "receipt_ref": "fixture-receipt-" + category} for category in sorted(CATEGORIES)]
    return CostStatement.model_validate({"statement_id": uuid4(), "period_start": start, "period_end": end,
        "approved_by": "fixture-owner", "approved_at": now, "source_receipt": "fixture-review-bundle",
        "cash": cash, "operator_rate": {"hourly_micro_aud": 30_000_000, "source_ref": "fixture-dated-rate"}, "time_coverage_complete": True, **changes})


def test_cost_inputs_make_full_costs_known_without_counting_budget_usage_as_cash(db, service):
    now, start, end, run, _work = setup(db, service)
    assert operational_summary(db, service, run, start, end)["cash_costs"] is None
    evidence = statement(now, start, end)
    assert import_costs(db, service, evidence)["state"] == "recorded"
    assert import_costs(db, service, evidence)["state"] == "replayed"
    result = operational_summary(db, service, run, start, end)
    assert result["hourly_rate"] == 30_000_000
    assert result["cash_costs"]["cash_micro_aud"] == 24_000_000
    assert result["cash_costs"]["operator_micro_aud"] == 30_000_000
    assert result["cash_costs"]["fully_loaded_micro_aud"] == 54_000_000
    assert result["cash_costs"]["automatic_procurement_cap_micro_aud"] == 0
    assert result["missing_cost_categories"] == []
    assert operational_summary(db, service, run, start-timedelta(days=1), end)["cash_costs"] is None
    stored = db.execute("SELECT encrypted_evidence FROM cost_statement").fetchone()["encrypted_evidence"]
    assert "Fixture supplier" not in stored and "fixture-receipt" not in stored


def test_partial_evidence_retains_unknowns_and_cohort_allocations_are_separate(db, service):
    now, start, end, run, work = setup(db, service)
    full = statement(now, start, end)
    partial = statement(now, start, end, cash=[full.cash[0].model_dump()], operator_rate=None)
    import_costs(db, service, partial)
    allocation = statement(now, start, end, cohort_id=work, tier="A")
    import_costs(db, service, allocation)
    result = operational_summary(db, service, run, start, end)
    assert result["cash_costs"]["cash_micro_aud"] == 4_000_000
    assert result["cash_costs"]["fully_loaded_micro_aud"] is None
    assert "operator_rate" in result["missing_cost_categories"]
    assert result["cohort_costs"][0]["cash_costs"]["fully_loaded_micro_aud"] == 54_000_000


def test_conflicting_period_future_approval_and_unsubstantiated_fields_rejected(db, service):
    now, start, end, _run, _work = setup(db, service)
    evidence = statement(now, start, end)
    import_costs(db, service, evidence)
    with pytest.raises(DomainError, match="COST_PERIOD_ALREADY_RECORDED"):
        import_costs(db, service, statement(now, start, end))
    with pytest.raises(DomainError, match="FUTURE_COST_APPROVAL"):
        import_costs(db, service, statement(now+timedelta(days=1), start, end))
    for change in ({"approved_by": " "}, {"source_receipt": " "}, {"currency": "BTC", "paid": True}):
        with pytest.raises(ValidationError):
            CostStatement.model_validate({**evidence.model_dump(), **change})
    bad = evidence.model_dump()
    bad["cash"][0]["gross_native"] = "NaN"
    with pytest.raises(ValidationError):
        CostStatement.model_validate(bad)


def test_cost_receipts_erased90days_numeric_metrics24months_and_unknown_time(db, service):
    now, start, end, run, _work = setup(db, service)
    evidence = statement(now, start, end, time_coverage_complete=False)
    import_costs(db, service, evidence)
    before = operational_summary(db, service, run, start, end)
    assert before["cash_costs"]["fully_loaded_micro_aud"] is None
    assert "operator_time" in before["missing_cost_categories"]
    result = minimise_database_evidence(db, service, now=now+timedelta(days=91), execute=True)
    assert result["cost_receipts"] == 1
    row = db.execute("SELECT * FROM cost_statement").fetchone()
    assert row["encrypted_evidence"] is None and row["evidence_erased_at"]
    assert set(row["numeric_facts"]) == {"cash", "hourly_rate", "time_coverage_complete"}
    assert operational_summary(db, service, run, start, end)["cash_costs"]["cash_micro_aud"] == 24_000_000
    assert minimise_database_evidence(db, service, now=now+timedelta(days=800), execute=True)["expired_cost_metrics"] == 1
    assert operational_summary(db, service, run, start, end)["cash_costs"] is None
