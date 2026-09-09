"""Reviewed calling business-policy checks; no dialling or legal determination."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class HolidayCalendar:
    locality: str
    timezone: str
    valid_from: date
    valid_until: date
    holidays: frozenset[date]
    policy_version: str
    evidence_ref: str
    approved: bool = False


@dataclass(frozen=True)
class CallingDecision:
    allowed: bool
    reason: str
    local_time: datetime | None = None


def evaluate_call_window(
    *,
    now: datetime,
    timezone: str | None,
    locality: str | None,
    timezone_confirmed: bool,
    calendar: HolidayCalendar | None,
) -> CallingDecision:
    if now.tzinfo is None:
        raise ValueError("UTC_REQUIRED")
    if not timezone_confirmed or not timezone or not locality:
        return CallingDecision(False, "TIMEZONE_LOCALITY_UNCONFIRMED")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return CallingDecision(False, "TIMEZONE_UNKNOWN")
    local = now.astimezone(zone)
    if (
        calendar is None
        or not calendar.approved
        or not calendar.policy_version
        or not calendar.evidence_ref
        or calendar.timezone != timezone
        or calendar.locality != locality
        or not calendar.valid_from <= local.date() <= calendar.valid_until
    ):
        return CallingDecision(False, "HOLIDAY_POLICY_UNKNOWN", local)
    if local.date() in calendar.holidays:
        return CallingDecision(False, "PUBLIC_HOLIDAY", local)
    if local.weekday() == 6:
        return CallingDecision(False, "SUNDAY", local)
    end_hour = 17 if local.weekday() == 5 else 18
    if not 9 <= local.hour < end_hour:
        return CallingDecision(False, "OUTSIDE_CALL_WINDOW", local)
    return CallingDecision(True, "CALL_WINDOW_PASSED", local)


def evaluate_licence_review(
    *,
    now: datetime,
    reviewed_at: datetime | None,
    status: str,
    identity_match: bool,
    evidence_ref: str | None,
) -> bool:
    if now.tzinfo is None:
        raise ValueError("UTC_REQUIRED")
    return bool(
        reviewed_at
        and reviewed_at.tzinfo
        and status == "active"
        and identity_match
        and evidence_ref
        and reviewed_at <= now < reviewed_at + timedelta(days=30)
    )


def invitation_state(state: str = "unknown", *, evidence_ref: str | None = None) -> str:
    if state not in {"invited", "uninvited", "unknown"}:
        raise ValueError("INVITATION_STATE_INVALID")
    if state == "invited" and not evidence_ref:
        raise ValueError("INVITATION_EVIDENCE_REQUIRED")
    return state
