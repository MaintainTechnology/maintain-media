"""Explicit cross-record constraints and time transitions missed by the first task audit."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb
from test_control_review_regressions import seeded_contact

from abr_engine.compliance.wash import create_batch, import_receipt
from abr_engine.control.service import digest
from abr_engine.enrich.budget import BudgetError, reserve, settle, upper_micro_aud


@pytest.mark.parametrize("changed", ["contact_id", "channel", "lead_id", "domain_identity_id"])
def test_real_database_rejects_cross_record_provenance(db, service, changed):
    _, first, _, _ = seeded_contact(db, service)
    second_lead, second, _, _ = seeded_contact(db, service)
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")  # Positive pairs must really satisfy all FKs.
    db.execute("SET CONSTRAINTS ALL DEFERRED")
    original = db.execute("SELECT * FROM collection_provenance WHERE provenance_id=%s",
                          (first["first_provenance_id"],)).fetchone()
    other = db.execute("SELECT * FROM collection_provenance WHERE provenance_id=%s",
                       (second["first_provenance_id"],)).fetchone()
    row = dict(original) | {"provenance_id": uuid4()}
    row[changed] = {"contact_id": second["contact_id"], "channel": "mobile",
                    "lead_id": second_lead["lead_id"], "domain_identity_id": other["domain_identity_id"]}[changed]
    query = sql.SQL("INSERT INTO collection_provenance ({}) VALUES ({})").format(
        sql.SQL(",").join(map(sql.Identifier, row)), sql.SQL(",").join(sql.Placeholder() for _ in row))
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        db.execute(query, [Jsonb(v) if isinstance(v, (dict, list)) else v for v in row.values()])
        db.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert db.execute("SELECT count(*) n FROM collection_provenance").fetchone()["n"] == 2


def test_first_capture_cannot_point_at_another_contacts_provenance(db, service):
    _, first, _, _ = seeded_contact(db, service)
    _, second, _, _ = seeded_contact(db, service)
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        db.execute("UPDATE contact_record SET first_provenance_id=%s WHERE contact_id=%s",
                   (second["first_provenance_id"], first["contact_id"]))
        db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_brisbane_month_rollover_preserves_uncertain_old_reservation(db):
    # Brisbane crosses midnight while the UTC calendar date remains unchanged.
    before = datetime(2026, 9, 30, 13, 59, 59, tzinfo=UTC)
    after = before + timedelta(seconds=2)
    tariff = {"version": "synthetic-dated", "currency": "AUD", "native_upper_bound": "90",
              "fx": "1", "tax_rate": "0", "fx_date": before.date().isoformat()}
    amount = upper_micro_aud("90", "1")
    operation = uuid4()
    first = reserve(db, operation_id=operation, now=before, amount=amount, tariff=tariff)
    settle(db, first["reservation_id"], None, None)
    replay = reserve(db, operation_id=operation, now=after, amount=amount, tariff=tariff)
    second = reserve(db, operation_id=uuid4(), now=after, amount=amount, tariff=tariff)
    assert replay["reservation_id"] == first["reservation_id"]
    assert replay["month"] == "2026-09" and replay["state"] == "uncertain"
    assert second["month"] == "2026-10"
    settle(db, first["reservation_id"], 80_000_000, "synthetic-reconciled-in-October")
    months = {r["month"]: r for r in db.execute("SELECT * FROM budget_month").fetchall()}
    assert months["2026-09"]["settled"] == 80_000_000 and months["2026-09"]["reserved"] == 0
    assert months["2026-10"]["settled"] == 0 and months["2026-10"]["reserved"] == amount


def test_zero_cap_refuses_paid_reservation_before_any_ledger_write(db):
    now = datetime(2026, 9, 9, tzinfo=UTC)
    tariff = {"version": "synthetic-zero-cap", "currency": "AUD", "native_upper_bound": "1",
              "fx": "1", "tax_rate": "0", "fx_date": now.date().isoformat()}
    with pytest.raises(BudgetError, match="BUDGET_STOP"), db.transaction():
        reserve(db, operation_id=uuid4(), now=now, amount=upper_micro_aud("1", "1"), tariff=tariff, cap=0)
    assert db.execute("SELECT count(*) n FROM budget_reservation").fetchone()["n"] == 0


@pytest.mark.parametrize("latest_result", ["listed", "error"])
@pytest.mark.parametrize("same_time", [False, True])
def test_latest_negative_wash_overrides_older_clear(db, service, latest_result, same_time):
    phone = "0412 345 678"
    _, contact, _, _ = seeded_contact(db, service, channel="mobile", value=phone,
                                      fields={"recipient_timezone": "Australia/Brisbane", "locality": "Brisbane", "timezone_reviewed": True})
    now = service.now(db)
    times = [now - timedelta(minutes=2), now - timedelta(minutes=2 if same_time else 1)]
    for result, when in zip(["clear", latest_result], times, strict=True):
        batch = create_batch(db, service, [phone])
        records = [{"phone": phone, "result": result, "washed_at": when.isoformat()}]
        receipt = {"format": "maintain-fixture-wash-v1", "account": "synthetic-manual",
                   "batch_digest": batch["digest"], "records_digest": digest(records), "count": 1}
        import_receipt(db, service, batch["batch_id"], records, receipt, "operator")
        gate = service.gate(db, contact["contact_id"])
        if result == "clear":
            assert gate["allowed"], gate["reason_codes"]
        else:
            assert not gate["allowed"] and "WASH_NOT_CURRENT_CLEAR" in gate["reason_codes"]
