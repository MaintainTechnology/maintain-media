"""Evidence-backed fixture cost accounting; no purchasing or inferred cash commitments."""
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from abr_engine.control.service import DomainError, digest
from abr_engine.export.metrics import Activity, cash_and_time_metrics, union_work_seconds

CATEGORIES = {"hosting", "storage_backups_requests_egress", "enrichment", "dncr", "sheets_crm_licences", "developer"}
Money = Decimal


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CashLine(Closed):
    category: Literal["hosting", "storage_backups_requests_egress", "enrichment", "dncr", "sheets_crm_licences", "developer"]
    vendor: str = Field(min_length=1, max_length=120)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    gross_native: Money = Field(ge=0, max_digits=18, decimal_places=6)
    tax_native: Money = Field(ge=0, max_digits=18, decimal_places=6)
    fx_to_aud: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    fx_date: date
    unit_tariff_native: Money = Field(ge=0, max_digits=18, decimal_places=6)
    minimum_commitment_native: Money = Field(ge=0, max_digits=18, decimal_places=6)
    receipt_ref: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def evidence(self):
        if not self.vendor.strip() or not self.receipt_ref.strip() or self.tax_native > self.gross_native:
            raise ValueError("Nonblank receipt/vendor and tax within gross required")
        if self.currency == "AUD" and self.fx_to_aud != 1:
            raise ValueError("AUD conversion must equal one")
        return self


class OperatorRate(Closed):
    hourly_micro_aud: int = Field(ge=0, strict=True)
    source_ref: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def source(self):
        if not self.source_ref.strip():
            raise ValueError("Dated rate evidence required")
        return self


class CostStatement(Closed):
    statement_id: UUID
    period_start: AwareDatetime
    period_end: AwareDatetime
    cohort_id: UUID | None = None
    tier: Literal["A", "B", "C"] | None = None
    approved_by: str = Field(min_length=1, max_length=120)
    approved_at: AwareDatetime
    source_receipt: str = Field(min_length=1, max_length=500)
    cash: list[CashLine] = Field(max_length=100)
    operator_rate: OperatorRate | None = None
    time_coverage_complete: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def coherent(self):
        if self.period_start >= self.period_end or self.period_end > self.approved_at:
            raise ValueError("Closed period must precede dated approval")
        if (self.cohort_id is None) != (self.tier is None):
            raise ValueError("Cohort and fixed tier must be provided together")
        if not self.approved_by.strip() or not self.source_receipt.strip() or not self.cash and self.operator_rate is None:
            raise ValueError("Explicit owner, source and at least one cost/rate required")
        if len({line.receipt_ref.strip() for line in self.cash}) != len(self.cash):
            raise ValueError("Duplicate cash receipt; use distinct documented allocations")
        if any(line.fx_date > self.approved_at.date() or line.fx_date < self.period_start.date() for line in self.cash):
            raise ValueError("FX evidence must be dated within the period or before approval")
        return self


def import_costs(conn, service, statement: CostStatement, *, actor="fixture-cost-owner"):
    if service.settings.mode != "fixture":
        raise DomainError("LIVE_COST_IMPORT_APPROVAL_PENDING", 409)
    service.authority(conn)
    if statement.approved_at > service.now(conn):
        raise DomainError("FUTURE_COST_APPROVAL")
    payload = statement.model_dump(mode="json")
    checksum = digest(payload)
    prior = conn.execute("SELECT evidence_digest FROM cost_statement WHERE statement_id=%s", (statement.statement_id,)).fetchone()
    if prior:
        if prior["evidence_digest"] != checksum:
            raise DomainError("COST_STATEMENT_CONFLICT", 409)
        return {"statement_id": statement.statement_id, "state": "replayed"}
    if conn.execute("SELECT 1 FROM cost_statement WHERE period_start=%s AND period_end=%s AND cohort_id IS NOT DISTINCT FROM %s AND tier IS NOT DISTINCT FROM %s",
        (statement.period_start, statement.period_end, statement.cohort_id, statement.tier)).fetchone():
        raise DomainError("COST_PERIOD_ALREADY_RECORDED", 409)
    if statement.cohort_id and not conn.execute("SELECT 1 FROM worklist_row WHERE worklist_id=%s AND selected_tier=%s UNION ALL SELECT 1 FROM retained_cohort_fact WHERE worklist_id=%s AND selected_tier=%s", (statement.cohort_id, statement.tier, statement.cohort_id, statement.tier)).fetchone():
        raise DomainError("COST_COHORT_NOT_FOUND", 404)
    cash: dict[str, int] = {}
    for line in statement.cash:
        value = int((line.gross_native * line.fx_to_aud * 1_000_000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        cash[line.category] = cash.get(line.category, 0) + value
    numeric = {"cash": cash, "hourly_rate": statement.operator_rate.hourly_micro_aud if statement.operator_rate else None,
        "time_coverage_complete": statement.time_coverage_complete}
    conn.execute("INSERT INTO cost_statement(statement_id,period_start,period_end,cohort_id,tier,evidence_digest,encrypted_evidence,numeric_facts,imported_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (statement.statement_id, statement.period_start, statement.period_end, statement.cohort_id, statement.tier, checksum,
            service.keys.encrypt(json.dumps(payload, sort_keys=True)), Jsonb(numeric), actor))
    service.audit(conn, actor, "cost_evidence_imported", statement.statement_id)
    return {"statement_id": statement.statement_id, "state": "recorded"}


def cost_projection(conn, service, start, end, activities: list[Activity], *, cohort_id=None, tier=None):
    row = conn.execute("SELECT * FROM cost_statement WHERE period_start=%s AND period_end=%s AND cohort_id IS NOT DISTINCT FROM %s AND tier IS NOT DISTINCT FROM %s",
        (start, end, cohort_id, tier)).fetchone()
    if not row:
        return {"cash_costs": None, "hourly_rate": None, "missing_cost_categories": sorted(CATEGORIES | {"operator_rate"})}
    cash = row["numeric_facts"]["cash"]
    worked = union_work_seconds(activities, start, end)
    rate = row["numeric_facts"]["hourly_rate"]
    calculated = cash_and_time_metrics(cash, worked, rate or 0)
    if not cash:
        calculated["cash_micro_aud"] = None
    if rate is None or not row["numeric_facts"]["time_coverage_complete"]:
        calculated["operator_micro_aud"] = None
        calculated["fully_loaded_micro_aud"] = None
    missing = list(calculated["missing_cost_categories"])
    if rate is None:
        missing.append("operator_rate")
    if not row["numeric_facts"]["time_coverage_complete"]:
        missing.append("operator_time")
    calculated["missing_cost_categories"] = missing
    return {"cash_costs": {**calculated, "categories_micro_aud": cash, "statement_id": str(row["statement_id"]),
                "coverage": "exact_declared_window", "currency": "AUD"},
            "hourly_rate": rate, "missing_cost_categories": missing}
