"""Pure cohort and work-time calculations; no sheet-edit proxy for worked time."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    activity_id: UUID
    actor_id: UUID
    category: Literal["calling", "research", "wash", "review", "admin"]
    started_at: AwareDatetime
    ended_at: AwareDatetime
    correction_of: UUID | None = None

    @model_validator(mode="after")
    def duration(self):
        if not 0 <= (self.ended_at - self.started_at).total_seconds() <= 86400:
            raise ValueError("activity duration must be between zero and 24 hours")
        return self


def _window(start: datetime, end: datetime) -> None:
    if start.utcoffset() is None or end.utcoffset() is None or start >= end:
        raise ValueError("window must be increasing timezone-aware instants")


def union_work_seconds(activities: list[Activity], start: datetime, end: datetime) -> float:
    """Sum interval unions per actor in [start,end), applying append-only corrections.

    All categories contribute. Concurrent work by different operators is additive.
    The caller supplies the complete relevant correction history, even across the window.
    """
    _window(start, end)
    unique: dict[UUID, Activity] = {}
    replaced = set()
    for activity in activities:
        if activity.activity_id in unique:
            if unique[activity.activity_id] != activity:
                raise ValueError("conflicting activity id")
            continue
        if activity.correction_of:
            prior = unique.get(activity.correction_of)
            if not prior or prior.actor_id != activity.actor_id or activity.correction_of in replaced:
                raise ValueError("correction must replace one earlier, same-actor current activity")
            replaced.add(activity.correction_of)
        unique[activity.activity_id] = activity
    intervals = defaultdict(list)
    for key, activity in unique.items():
        if key in replaced:
            continue
        left, right = max(start, activity.started_at), min(end, activity.ended_at)
        if left < right:
            intervals[activity.actor_id].append((left, right))
    seconds = 0.0
    for actor_intervals in intervals.values():
        ordered = sorted(actor_intervals)
        current_start, current_end = ordered[0]
        for left, right in ordered[1:]:
            if left <= current_end:
                current_end = max(current_end, right)
            else:
                seconds += (current_end - current_start).total_seconds()
                current_start, current_end = left, right
        seconds += (current_end - current_start).total_seconds()
    return seconds


class CohortEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cohort_id: UUID
    group_id: UUID
    tier: Literal["A", "B", "C"]
    originating_signal: str
    selected_at: AwareDatetime


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: UUID
    cohort_id: UUID
    group_id: UUID
    occurred_at: AwareDatetime
    kind: Literal["attempt", "contacted", "meeting_booked", "meeting_held"]
    attempts: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def attempts_only(self):
        if self.kind != "attempt" and self.attempts:
            raise ValueError("attempt increments belong only to dated attempt events")
        if self.kind == "attempt" and not self.attempts:
            raise ValueError("attempt event must increment attempts")
        return self


class _Bucket(TypedDict):
    selected: set[UUID]
    contacted: set[UUID]
    booked: set[UUID]
    held: set[UUID]
    attempted: set[UUID]
    attempts: int


def cohort_metrics(entries: list[CohortEntry], outcomes: list[Outcome], start: datetime,
                   end: datetime) -> list[dict]:
    """Fixed selection tier/signal; dedupe groups/events and use actual dated observations.

    Meeting events are evidence of contact but held does not fabricate a booked event.
    A business may belong to different explicitly declared cohorts, never two tiers/signals
    within one cohort. No current lead tier is consulted or retrospectively reassigned.
    """
    _window(start, end)
    membership: dict[tuple[UUID, UUID], CohortEntry] = {}
    buckets: dict[tuple[str, str, str], _Bucket] = {}
    for entry in entries:
        identity = (entry.cohort_id, entry.group_id)
        if identity in membership and membership[identity] != entry:
            raise ValueError("conflicting fixed cohort attribution")
        membership[identity] = entry
        key = (str(entry.cohort_id), entry.tier, entry.originating_signal)
        buckets.setdefault(key, {"selected": set(), "contacted": set(), "booked": set(),
                                 "held": set(), "attempted": set(), "attempts": 0})
        if entry.selected_at < end:
            buckets[key]["selected"].add(entry.group_id)
    seen: dict[UUID, Outcome] = {}
    for event in outcomes:
        if event.event_id in seen:
            if seen[event.event_id] != event:
                raise ValueError("conflicting outcome event id")
            continue
        seen[event.event_id] = event
        selected = membership.get((event.cohort_id, event.group_id))
        if not selected:
            raise ValueError("outcome missing cohort membership")
        if event.occurred_at < selected.selected_at:
            raise ValueError("outcome predates cohort selection")
        if not start <= event.occurred_at < end:
            continue
        bucket = buckets[(str(selected.cohort_id), selected.tier, selected.originating_signal)]
        if event.kind == "attempt":
            bucket["attempted"].add(event.group_id)
            bucket["attempts"] += event.attempts
        else:
            bucket["contacted"].add(event.group_id)
            if event.kind == "meeting_booked":
                bucket["booked"].add(event.group_id)
            if event.kind == "meeting_held":
                bucket["held"].add(event.group_id)
    results = []
    for (cohort, tier, signal), bucket in sorted(buckets.items()):
        denominator = len(bucket["contacted"])
        results.append({"cohort_id": cohort, "tier": tier, "originating_signal": signal,
                        "window_start": start.isoformat(), "window_end_exclusive": end.isoformat(),
                        "selected_groups": len(bucket["selected"]), "attempts": bucket["attempts"],
                        "attempted_groups": len(bucket["attempted"]), "contacted_groups": denominator,
                        "booked_groups": len(bucket["booked"]), "held_groups": len(bucket["held"]),
                        "booking_rate": len(bucket["booked"]) / denominator if denominator else None,
                        "held_rate": len(bucket["held"]) / denominator if denominator else None})
    return results


def cash_and_time_metrics(costs_micro_aud: dict[str, int], worked_seconds: float,
                          hourly_rate_micro_aud: int) -> dict:
    """Explicit full cash categories; missing categories remain unknown, not zero."""
    categories = {"hosting", "storage_backups_requests_egress", "enrichment", "dncr",
                  "sheets_crm_licences", "developer"}
    if set(costs_micro_aud) - categories or any(value < 0 for value in costs_micro_aud.values()):
        raise ValueError("unknown or negative cost")
    if worked_seconds < 0 or hourly_rate_micro_aud < 0:
        raise ValueError("negative worked time or tariff")
    missing = sorted(categories - costs_micro_aud.keys())
    labour = round(worked_seconds * hourly_rate_micro_aud / 3600)
    return {"cash_micro_aud": sum(costs_micro_aud.values()), "operator_micro_aud": labour,
            "fully_loaded_micro_aud": None if missing else sum(costs_micro_aud.values()) + labour,
            "missing_cost_categories": missing, "worked_seconds": worked_seconds,
            "automatic_procurement_cap_micro_aud": 0}
