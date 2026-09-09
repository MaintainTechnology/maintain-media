from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from abr_engine.qualify.policy import current_policy


def completed_months(effective_date: date, publication_date: date) -> int | None:
    """Completed status-age months with end-of-month anniversary clamping."""
    if effective_date > publication_date:
        return None
    months = (
        (publication_date.year - effective_date.year) * 12 + publication_date.month - effective_date.month
    )
    anniversary_day = min(
        effective_date.day, calendar.monthrange(publication_date.year, publication_date.month)[1]
    )
    return months - int(publication_date.day < anniversary_day)


def target_geography(state: str | None, postcode: str | None, *, conflicting: bool = False) -> bool:
    if conflicting or not postcode or len(postcode) != 4 or not postcode.isascii() or not postcode.isdigit():
        return False
    rules = current_policy().qualification
    return state == rules["full_state"] or (
        state == rules["partial_state"] and rules["postcode_min"] <= postcode <= rules["postcode_max"]
    )


@dataclass(frozen=True)
class Qualification:
    tier: str | None
    enrichment_eligible: bool
    reason_codes: tuple[str, ...]
    status_age_months: int | None
    date_in_future: bool

    @property
    def rule_version(self) -> str:
        return current_policy().rule_version


def qualify_abr(
    record: dict, event_types: set[str], publication_date: date, *, confidence: str = "none"
) -> Qualification:
    rules = current_policy().qualification
    status_date = record.get("status_date")
    if isinstance(status_date, str):
        status_date = date.fromisoformat(status_date)
    future = bool(status_date and status_date > publication_date)
    age = completed_months(status_date, publication_date) if status_date else None
    reasons = []
    if record.get("status") != "ACT" or "abn_disappeared" in event_types or "abn_cancelled" in event_types:
        return Qualification(None, False, ("INACTIVE_OR_DISAPPEARED",), age, future)
    tier = None
    if future:
        reasons.append("FUTURE_STATUS_EFFECTIVE_DATE")
    elif (
        "gst_registered" in event_types
        and record.get("gst_status") == "ACT"
        and age is not None
        and rules["gst_age_min_months"] <= age < rules["gst_age_max_months_exclusive"]
    ):
        tier = "A"
    elif "abn_new" in event_types:
        tier = (
            "B"
            if (
                record.get("entity_class") in rules["tier_b_entity_classes"]
                and record.get("gst_status") == "ACT"
                and confidence in rules["tier_b_confidences"]
            )
            else "C"
        )
    if not target_geography(
        record.get("state"), record.get("postcode"), conflicting=record.get("geography_conflicting", False)
    ):
        reasons.append("GEOGRAPHY_OUTSIDE_OR_UNKNOWN")
    if tier not in ("A", "B"):
        reasons.append("NO_ENRICHABLE_QUALIFYING_SIGNAL")
    return Qualification(tier, tier in ("A", "B") and not reasons, tuple(reasons), age, future)


def qualify_qbcc(record: dict, event_type: str) -> Qualification:
    rules = current_policy().qualification
    reasons = []
    if (
        record.get("status") != "ACTIVE"
        or record.get("financial_category") not in rules["qbcc_categories"]
        or event_type not in rules["qbcc_events"]
    ):
        reasons.append("NO_ACTIVE_QBCC_QUALIFYING_SIGNAL")
    if not target_geography(record.get("state"), record.get("postcode")):
        reasons.append("GEOGRAPHY_OUTSIDE_OR_UNKNOWN")
    return Qualification("A" if not reasons else None, not reasons, tuple(reasons), None, False)
