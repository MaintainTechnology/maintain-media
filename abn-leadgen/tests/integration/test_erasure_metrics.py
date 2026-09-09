from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from abr_engine.compliance.retention import erase_profile, minimise_database_evidence
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.costs import CostStatement, import_costs
from abr_engine.ops.pilot_facts import retain_profile_metrics
from abr_engine.ops.summary import operational_summary
from abr_engine.qualify.identity import merge_groups


@pytest.mark.parametrize("preselection", [False, True])
def test_closed_window_pilot_totals_survive_optout_profile_erasure(db, service, preselection):
    seed_policy(db, service)
    record = seed_contact(db, service)
    now = service.now(db)
    work = build_worklist(db, service, now.date()-timedelta(days=now.weekday()))
    row = db.execute("SELECT * FROM worklist_row WHERE worklist_id=%s", (work["worklist_id"],)).fetchone()
    if preselection:
        service.outcome(db, row["row_id"], {"expected_version": 1, "status": "contacted_nurture", "attempts": 99,
            "invitation_state": "unknown", "notes": "Excluded old observation", "occurred_at": now-timedelta(days=1)}, "fixture-operator", uuid4())
    for version, status in ((1, "contacted_nurture"), (2, "meeting_booked"), (3, "meeting_held")):
        version += int(preselection)
        service.outcome(db, row["row_id"], {"expected_version": version, "status": status, "attempts": 2,
            "invitation_state": "unknown", "notes": "Private identifying note", "occurred_at": service.now(db)}, "fixture-operator", uuid4())
    run = uuid4()
    db.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','complete')", (run,))
    end = service.now(db)
    before = operational_summary(db, service, run, now-timedelta(days=56), end)
    assert before["cohorts"][0]["contacted_groups"] == before["cohorts"][0]["booked_groups"] == 1
    assert before["cohorts"][0]["attempts"] == 2
    retain_profile_metrics(db, service, record["lead"]["lead_id"], now=service.now(db))
    assert operational_summary(db, service, run, now-timedelta(days=56), end)["cohorts"] == before["cohorts"]
    service.suppress(db, {"lead_id": record["lead"]["lead_id"], "reason": "unsubscribe", "source": "fixture"}, "operator", uuid4())
    erase_profile(db, service, record["lead"]["group_id"])
    after = operational_summary(db, service, run, now-timedelta(days=56), end)
    assert after["cohorts"] == before["cohorts"]
    assert after["worked_seconds"] == before["worked_seconds"]
    assert not db.execute("SELECT 1 FROM outcome_event").fetchone()
    assert not db.execute("SELECT 1 FROM lead_entity").fetchone()
    assert db.execute("SELECT count(*) n FROM retained_outcome_fact").fetchone()["n"] == 3+int(preselection)


def test_erased_activity_expires_without_live_fallback_and_scoped_hold_survives(db, service):
    seed_policy(db, service)
    record = seed_contact(db, service)
    now = service.now(db)
    work = build_worklist(db, service, now.date()-timedelta(days=now.weekday()))
    activity = uuid4()
    db.execute("INSERT INTO operator_activity(activity_id,actor_id,worklist_id,lead_id,category,started_at,ended_at) VALUES(%s,'operator-personal-name',%s,%s,'calling',%s,%s)",
        (activity, work["worklist_id"], record["lead"]["lead_id"], now-timedelta(hours=1), now))
    run = uuid4()
    db.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','complete')", (run,))
    erase_profile(db, service, record["lead"]["group_id"])
    assert operational_summary(db, service, run, now-timedelta(days=1), now+timedelta(seconds=1))["worked_seconds"] == 3600
    held = uuid4()
    db.execute("INSERT INTO retention_hold VALUES(%s,'activity_metric',%s,'reviewer','Minimal metrics hold',%s)", (held, str(activity), now))
    minimise_database_evidence(db, service, now=now+timedelta(days=800), execute=True)
    assert db.execute("SELECT 1 FROM retained_activity_fact WHERE activity_id=%s", (activity,)).fetchone()
    db.execute("DELETE FROM retention_hold WHERE hold_id=%s", (held,))
    minimise_database_evidence(db, service, now=now+timedelta(days=800), execute=True)
    assert not db.execute("SELECT 1 FROM retained_activity_fact").fetchone()
    assert not db.execute("SELECT 1 FROM operator_activity WHERE activity_id=%s", (activity,)).fetchone()
    assert operational_summary(db, service, run, now-timedelta(days=1), now+timedelta(seconds=1))["worked_seconds"] == 0


def test_scoped_metric_hold_keeps_old_minimal_fact_without_identifying_profile(db, service):
    seed_policy(db, service)
    record = seed_contact(db, service)
    now = service.now(db)
    work = build_worklist(db, service, now.date()-timedelta(days=now.weekday()))
    row = db.execute("SELECT row_id FROM worklist_row WHERE worklist_id=%s", (work["worklist_id"],)).fetchone()
    service.outcome(db, row["row_id"], {"expected_version": 1, "status": "contacted_nurture", "attempts": 1,
        "invitation_state": "unknown", "notes": "Erase identifying text", "occurred_at": service.now(db)}, "fixture-operator", uuid4())
    db.execute("INSERT INTO retention_hold VALUES(%s,'cohort_metric',%s,'reviewer','Retain metric',%s)", (uuid4(), str(row["row_id"]), now))
    erase_profile(db, service, record["lead"]["group_id"], now=now+timedelta(days=800))
    assert not db.execute("SELECT 1 FROM lead_entity").fetchone()
    assert db.execute("SELECT 1 FROM retained_cohort_fact WHERE row_id=%s", (row["row_id"],)).fetchone()
    minimise_database_evidence(db, service, now=now+timedelta(days=800), execute=True)
    assert db.execute("SELECT 1 FROM retained_cohort_fact WHERE row_id=%s", (row["row_id"],)).fetchone()
    assert db.execute("SELECT 1 FROM retained_outcome_fact WHERE row_id=%s", (row["row_id"],)).fetchone()
    assert not db.execute("SELECT 1 FROM outcome_event").fetchone()


def manual_work(db, now, records, *, week_offset=0):
    work = uuid4()
    db.execute("INSERT INTO worklist VALUES(%s,%s,%s)", (work, now.date()+timedelta(days=week_offset), now-timedelta(days=1)))
    for ordinal, (record, tier) in enumerate(records, 1):
        db.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,decision,selected_tier,selected_signal) VALUES(%s,%s,%s,'{}',%s,'qbcc_backlog')",
            (UUID(int=ordinal+week_offset*1000), work, record["lead"]["lead_id"], tier))
    return work


def rate_evidence(db, service, work, tier, start, end):
    import_costs(db, service, CostStatement(statement_id=uuid4(), period_start=start, period_end=end,
        cohort_id=work, tier=tier, approved_by="fixture-owner", approved_at=service.now(db),
        source_receipt="fixture-reviewed-rate", cash=[], operator_rate={"hourly_micro_aud": 30_000_000, "source_ref": "fixture-rate"},
        time_coverage_complete=True))


def summary_run(db):
    run = uuid4()
    db.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','complete')", (run,))
    return run


def add_activity(db, record, work, start, end, correction=None):
    activity = uuid4()
    db.execute("INSERT INTO operator_activity(activity_id,actor_id,worklist_id,lead_id,category,started_at,ended_at,correction_of) VALUES(%s,'fixture-operator',%s,%s,'calling',%s,%s,%s)",
        (activity, work, record["lead"]["lead_id"], start, end, correction))
    return activity


def test_merged_group_activity_uses_first_fixed_tier_once_after_erasure(db, service):
    seed_policy(db, service)
    a, b, c = [seed_contact(db, service) for _ in range(3)]
    now = service.now(db)
    start, end = now-timedelta(hours=2), now-timedelta(hours=1)
    work = manual_work(db, now, [(a, "A"), (b, "B"), (c, "B")])
    add_activity(db, b, work, start, end)
    source, target = service.lead(db, a["lead"]["lead_id"]), service.lead(db, b["lead"]["lead_id"])
    merge_groups(db, service, {"source_lead_id": source["lead_id"], "target_lead_id": target["lead_id"],
        "source_revision": source["revision"], "target_revision": target["revision"], "evidence_refs": ["fixture-1", "fixture-2"], "reason": "Reviewed identity"}, "reviewer")
    for tier in ("A", "B"):
        rate_evidence(db, service, work, tier, start, end)
    run = summary_run(db)
    before = operational_summary(db, service, run, start, end)
    assert {r["tier"]: r["cash_costs"]["worked_seconds"] for r in before["cohort_costs"]} == {"A": 3600, "B": 0}
    erase_profile(db, service, a["lead"]["group_id"])
    erase_profile(db, service, b["lead"]["group_id"])
    after = operational_summary(db, service, run, start, end)
    assert after["cohorts"] == before["cohorts"]
    assert after["cohort_costs"] == before["cohort_costs"]


def test_cross_cohort_correction_and_late_cost_import_survive_erasure(db, service):
    seed_policy(db, service)
    a, b = seed_contact(db, service), seed_contact(db, service)
    now = service.now(db)
    start, end = now-timedelta(hours=2), now-timedelta(hours=1)
    first = manual_work(db, now, [(a, "A")])
    second = manual_work(db, now, [(b, "B")], week_offset=7)
    original = add_activity(db, a, first, start, end)
    add_activity(db, b, second, start, start+timedelta(minutes=30), original)
    for work, tier in ((first, "A"), (second, "B")):
        erase_profile(db, service, (a if tier == "A" else b)["lead"]["group_id"])
        rate_evidence(db, service, work, tier, start, end)
    result = operational_summary(db, service, summary_run(db), start, end)
    assert result["worked_seconds"] == 1800
    assert {r["tier"]: r["cash_costs"]["worked_seconds"] for r in result["cohort_costs"]} == {"A": 0, "B": 1800}


def test_expired_activity_chain_preserves_recent_correction_then_purges_all(db, service):
    seed_policy(db, service)
    record = seed_contact(db, service)
    now = service.now(db)
    work = manual_work(db, now, [(record, "A")])
    old = now-timedelta(days=800)
    original = add_activity(db, record, work, old-timedelta(hours=1), old)
    add_activity(db, record, work, now-timedelta(hours=1), now, original)
    orphan = add_activity(db, record, work, old-timedelta(hours=2), old-timedelta(hours=1))
    erase_profile(db, service, record["lead"]["group_id"])
    minimise_database_evidence(db, service, now=now, execute=True)
    assert not db.execute("SELECT 1 FROM operator_activity WHERE activity_id=%s", (orphan,)).fetchone()
    assert db.execute("SELECT count(*) n FROM retained_activity_fact").fetchone()["n"] == 2
    result = operational_summary(db, service, summary_run(db), now-timedelta(days=1), now+timedelta(seconds=1))
    assert result["worked_seconds"] == 3600
    minimise_database_evidence(db, service, now=now+timedelta(days=800), execute=True)
    assert not db.execute("SELECT 1 FROM retained_activity_fact").fetchone()
    assert not db.execute("SELECT 1 FROM operator_activity").fetchone()


def test_entirely_expired_chain_is_purged_in_first_retention_execution(db, service):
    seed_policy(db, service)
    record = seed_contact(db, service)
    now = service.now(db)
    work = manual_work(db, now, [(record, "A")])
    old = now-timedelta(days=800)
    original = add_activity(db, record, work, old-timedelta(hours=1), old)
    add_activity(db, record, work, old-timedelta(minutes=30), old, original)
    erase_profile(db, service, record["lead"]["group_id"])
    minimise_database_evidence(db, service, now=now, execute=True)
    assert not db.execute("SELECT 1 FROM retained_activity_fact").fetchone()
    assert not db.execute("SELECT 1 FROM operator_activity").fetchone()
    assert operational_summary(db, service, summary_run(db), old-timedelta(days=1), old+timedelta(seconds=1))["worked_seconds"] == 0
