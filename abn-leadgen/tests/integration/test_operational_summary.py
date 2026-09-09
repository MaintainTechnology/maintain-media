from datetime import timedelta
from uuid import uuid4

from abr_engine.export.report import safe_rows
from abr_engine.export.worklist import build_worklist, report_context
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.summary import operational_summary


def test_database_summary_counts_cumulative_attempts_and_deduplicates_alarm(db, service):
    seed_policy(db, service)
    seed_contact(db, service)
    now = service.now(db)
    worklist = build_worklist(db, service, now.date()-timedelta(days=now.weekday()))
    rendered = safe_rows(report_context(db, service, worklist["worklist_id"], uuid4()))
    assert rendered[0]["gate_label"] == "Email: needs send-time checks"
    row = db.execute("SELECT * FROM worklist_row WHERE worklist_id=%s", (worklist["worklist_id"],)).fetchone()
    for version, status in [(1, "contacted_nurture"), (2, "meeting_booked")]:
        service.outcome(db, row["row_id"], {"expected_version": version, "status": status, "attempts": 2,
                "invitation_state": "unknown", "notes": "", "occurred_at": service.now(db)}, "fixture-operator", uuid4())
    run = uuid4()
    db.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','running')", (run,))
    db.execute("INSERT INTO budget_month(month,cap,reserved,settled,frozen) VALUES('2026-09',150000000,0,0,true)")
    end = service.now(db)
    result = operational_summary(db, service, run, end-timedelta(weeks=8), end)
    assert result["cohorts"][0]["attempts"] == 2
    assert result["cohorts"][0]["contacted_groups"] == 1
    assert result["cohorts"][0]["booked_groups"] == 1
    assert result["cash_costs"] is None and result["pilot_observation"] == "synthetic_only"
    operational_summary(db, service, run, end-timedelta(weeks=8), end)
    assert db.execute("SELECT count(*) n FROM alarm_outbox WHERE run_id=%s AND code='budget_stop'", (run,)).fetchone()["n"] == 1
