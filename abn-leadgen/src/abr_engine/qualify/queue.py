"""Deterministic queue decisions for transactionally persisted queue rows.

These functions never grant export/contact permission; callers recheck current
eligibility under their database locks before persisting a selected worklist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from abr_engine.qualify.policy import current_policy


def score(
    *,
    source: str,
    tier: str,
    confidence: str = "none",
    geography: bool,
    company: bool = False,
    category: str | None = None,
    deliverable_email: bool = False,
    phone: bool = False,
    website: bool = False,
    provisional: bool = False,
) -> int:
    rules = current_policy().scoring
    contact = (
        0
        if provisional
        else max(
            rules["contact"]["deliverable_email"] if deliverable_email else 0,
            rules["contact"]["phone"] if phone else 0,
            rules["contact"]["website"] if website else 0,
        )
    )
    if source == "abr":
        base = rules["abr_tier"].get(tier)
        if base is None:
            raise ValueError("unknown tier")
        value = base + rules["confidence"][confidence]
    elif source == "qbcc":
        if tier != "A" or category not in rules["qbcc_category"]:
            raise ValueError("non-qualifying QBCC score")
        value = rules["qbcc_tier_a"] + rules["qbcc_category"][category]
    else:
        raise ValueError("unknown source")
    return min(rules["cap"], value + rules["geography"] * geography + rules["company"] * company + contact)


@dataclass(frozen=True)
class QueueItem:
    lead_id: str
    group_id: str
    first_qualified_at: datetime
    final_score: int
    provisional_score: int
    state: str = "ready"
    tier: str = "A"
    eligible: bool = True
    worked: bool = False
    suppressed: bool = False
    last_qualifying_event: str | None = None
    endpoint_tokens: tuple[str, ...] = ()

    def __post_init__(self):
        if self.first_qualified_at.tzinfo is None or not (
            0 <= self.final_score <= 100 and 0 <= self.provisional_score <= 100
        ):
            raise ValueError("invalid queue date/score")


@dataclass(frozen=True)
class Selection:
    selected: tuple[QueueItem, ...]
    excluded: dict[str, str]


def select_worklist(
    items: list[QueueItem], now: datetime, *, limit: int = 60, oldest_reserve: int = 10
) -> Selection:
    rules = current_policy().queue
    if (
        now.tzinfo is None
        or not 0 <= limit <= rules["weekly_limit"]
        or not 0 <= oldest_reserve <= rules["oldest_reserve"]
    ):
        raise ValueError("invalid selection bounds")
    if len({r.lead_id for r in items}) != len(items):
        raise ValueError("duplicate lead IDs")
    excluded, eligible = {}, []
    for row in items:
        reason = (
            "SUPPRESSED"
            if row.suppressed or row.state == "suppressed"
            else "ALREADY_WORKED"
            if row.worked or row.state == "exported"
            else "QUEUE_EXPIRED"
            if now >= row.first_qualified_at + timedelta(weeks=rules["expiry_weeks"])
            else "FUTURE_QUALIFICATION"
            if now < row.first_qualified_at
            else "NOT_READY_OR_ELIGIBLE"
            if row.state != "ready" or not row.eligible or row.tier not in ("A", "B")
            else None
        )
        if reason:
            excluded[row.lead_id] = reason
        else:
            eligible.append(row)
    selected: list[QueueItem] = []
    groups: set[str] = set()
    endpoints: set[str] = set()

    def add(row):
        if row.group_id in groups:
            excluded[row.lead_id] = "DUPLICATE_BUSINESS_GROUP"
            return False
        if endpoints.intersection(row.endpoint_tokens):
            excluded[row.lead_id] = "SHARED_ENDPOINT_REVIEW"
            return False
        selected.append(row)
        groups.add(row.group_id)
        endpoints.update(row.endpoint_tokens)
        return True

    for row in sorted(eligible, key=lambda r: (r.first_qualified_at, r.lead_id)):
        if len(selected) >= min(oldest_reserve, limit):
            break
        add(row)
    picked = {r.lead_id for r in selected}
    for row in sorted(eligible, key=lambda r: (-r.final_score, r.first_qualified_at, r.lead_id)):
        if row.lead_id in picked:
            continue
        if len(selected) < limit:
            add(row)
        else:
            excluded.setdefault(row.lead_id, "CARRIED_CAPACITY")
    return Selection(tuple(selected), excluded)


def enrichment_order(items: list[QueueItem]) -> list[QueueItem]:
    return sorted(items, key=lambda r: (-r.provisional_score, r.first_qualified_at, r.lead_id))


def can_reactivate(item: QueueItem, new_event_id: str) -> bool:
    return bool(
        new_event_id
        and item.state == "deferred"
        and not item.suppressed
        and new_event_id != item.last_qualifying_event
    )
