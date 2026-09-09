"""Independent negative report boundary review; actual current PostgreSQL authority."""

from datetime import timedelta
from uuid import uuid4

import pytest

from abr_engine.control.service import DomainError
from abr_engine.export.worklist import build_worklist, report_context
from abr_engine.fixture import seed_contact, seed_policy


def test_report_flags_shared_domain_for_review_without_merging(db, service):
    seed_policy(db, service)
    seed_contact(db, service, name="Synthetic business one")
    seed_contact(db, service, name="Synthetic business two")
    now = service.now(db)
    work = build_worklist(db, service, now.date() - timedelta(days=now.weekday()))
    report = report_context(db, service, work["worklist_id"], uuid4())
    assert len(report.rows) == 2
    assert len({row.group_id for row in report.rows}) == 2
    assert all("potential duplicate" in row.next_action for row in report.rows)


@pytest.mark.parametrize("flag", ["restore_quarantine", "key_compromised", "memory"])
def test_report_context_refuses_personal_projection_in_quarantine(db, service, flag):
    seed_policy(db, service)
    seed_contact(db, service, name="Synthetic private business")
    now = service.now(db)
    work = build_worklist(db, service, now.date() - timedelta(days=now.weekday()))
    assert report_context(db, service, work["worklist_id"], uuid4()).rows
    if flag == "memory":
        service.keys.compromised = True
    else:
        db.execute("UPDATE system_state SET value='true' WHERE name=%s", (flag,))
    with pytest.raises(DomainError, match="AUTHORITY_QUARANTINED"):
        report_context(db, service, work["worklist_id"], uuid4())
