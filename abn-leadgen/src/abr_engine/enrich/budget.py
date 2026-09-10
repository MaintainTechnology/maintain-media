"""Pessimistic integer budget ledger with real row-lock concurrency."""
import hashlib
import json
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from abr_engine.db import lock


class BudgetError(ValueError):
    pass


def upper_micro_aud(native: str, fx: str, tax_rate: str = "0") -> int:
    values = [Decimal(v) for v in (native, fx, tax_rate)]
    if any(not v.is_finite() or v < 0 for v in values) or values[1] == 0:
        raise BudgetError("Invalid tariff")
    return int((values[0] * values[1] * (1 + values[2]) * Decimal("1.1") * 1_000_000)
               .to_integral_value(rounding=ROUND_CEILING))


def reserve(conn, *, operation_id: UUID, now: datetime, amount: int, tariff: dict,
            cap: int = 150_000_000) -> dict:
    if amount < 0 or cap < 0 or cap > 150_000_000:
        raise BudgetError("Invalid amount or cap")
    if not tariff.get("version") or not tariff.get("fx_date") or not tariff.get("currency"):
        raise BudgetError("Dated tariff and currency required")
    if not all(name in tariff for name in ("native_upper_bound", "fx", "tax_rate")):
        raise BudgetError("Priced tariff components required")
    required_amount = upper_micro_aud(tariff["native_upper_bound"], tariff["fx"], tariff["tax_rate"])
    if amount != required_amount:
        raise BudgetError("Reservation must match server-calculated worst-case tariff")
    fx_date = datetime.fromisoformat(tariff["fx_date"]).date()
    if not 0 <= (now.date() - fx_date).days <= 30:
        raise BudgetError("Stale FX")
    digest = hashlib.sha256(json.dumps({"amount": amount, "tariff": tariff}, sort_keys=True).encode()).hexdigest()
    # The live dashboard and every paid reservation serialize this policy read.
    # Lowering the limit stops new spend; existing reservations remain accounted for.
    lock(conn, "budget-policy")
    preferences = conn.execute("SELECT value FROM system_state WHERE name='live_dashboard_settings'").fetchone()
    if preferences:
        stored_cap = preferences["value"].get("monthly_cap_micro_aud") if isinstance(preferences["value"], dict) else None
        if type(stored_cap) is not int or not 0 <= stored_cap <= 150_000_000:
            raise BudgetError("BUDGET_POLICY_INVALID")
        cap = min(cap, stored_cap)
    lock(conn, "budget-operation:" + str(operation_id))
    prior = conn.execute("SELECT * FROM budget_reservation WHERE operation_id=%s", (operation_id,)).fetchone()
    if prior:
        if prior["body_digest"] != digest:
            raise BudgetError("Changed idempotent operation")
        return prior
    month = now.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m")
    conn.execute("INSERT INTO budget_month(month,cap) VALUES(%s,%s) ON CONFLICT DO NOTHING", (month, cap))
    budget = conn.execute("SELECT * FROM budget_month WHERE month=%s FOR UPDATE", (month,)).fetchone()
    if budget["frozen"] or budget["reserved"] + budget["settled"] + amount > min(cap, budget["cap"]):
        raise BudgetError("BUDGET_STOP")
    conn.execute("UPDATE budget_month SET reserved=reserved+%s WHERE month=%s", (amount, month))
    return conn.execute("INSERT INTO budget_reservation VALUES(%s,%s,%s,%s,%s,NULL,'reserved',%s,NULL,%s) RETURNING *",
                        (uuid4(), operation_id, digest, month, amount, Jsonb(tariff), now)).fetchone()


def settle(conn, reservation_id: UUID, actual: int | None, receipt: str | None) -> dict:
    row = conn.execute("SELECT * FROM budget_reservation WHERE reservation_id=%s FOR UPDATE", (reservation_id,)).fetchone()
    if not row:
        raise BudgetError("Unknown reservation")
    if row["state"] == "settled":
        if actual != row["actual"] or receipt != row["receipt_ref"]:
            raise BudgetError("Settlement mismatch")
        return row
    if actual is None:
        conn.execute("UPDATE budget_reservation SET state='uncertain' WHERE reservation_id=%s", (reservation_id,))
    elif actual < 0 or not receipt:
        raise BudgetError("Amount and receipt required")
    elif actual > row["amount"]:
        # Keep the entire reservation; record overrun without defeating ledger cap.
        conn.execute("UPDATE budget_month SET frozen=true WHERE month=%s", (row["month"],))
        conn.execute("UPDATE budget_reservation SET state='uncertain',actual=%s,receipt_ref=%s WHERE reservation_id=%s",
                     (actual, receipt, reservation_id))
    else:
        conn.execute("UPDATE budget_month SET reserved=reserved-%s,settled=settled+%s WHERE month=%s",
                     (row["amount"], actual, row["month"]))
        conn.execute("UPDATE budget_reservation SET state='settled',actual=%s,receipt_ref=%s WHERE reservation_id=%s",
                     (actual, receipt, reservation_id))
    return conn.execute("SELECT * FROM budget_reservation WHERE reservation_id=%s", (reservation_id,)).fetchone()
