"""Deterministic, endpoint-free alarms. Persist dedupe_key in the durable alarm outbox."""

from __future__ import annotations

import hashlib
import json
from statistics import median
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Flag = Literal[
    "integrity_failure", "schema_failure", "count_failure", "duplicate_failure",
    "unexpected_disappearance", "member_count_changed", "budget_stop", "quota_stop",
    "suppression_unconfirmed", "invalid_receipt", "writeback_conflict",
    "crm_reconciliation_pending", "policy_expired", "backup_failed", "restore_failed",
    "timer_heartbeat_missed", "spill_exhausted",
]


class AlarmInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    run_id: UUID
    source: Literal["abr", "qbcc"]
    baseline: bool = False
    no_op: bool = False
    source_age_days: float | None = Field(default=None, ge=0)
    mismatch_hours: float | None = Field(default=None, ge=0)
    field_fill_delta_pp: float | None = None
    classification_delta_pp: float | None = None
    current_volume: int | None = Field(default=None, ge=0)
    comparable_volumes: list[int] = Field(default_factory=list)
    zero_median_absolute_threshold: int | None = Field(default=None, ge=0)
    hit_rate: float | None = Field(default=None, ge=0, le=1)
    hit_rate_sample_size: int = Field(default=0, ge=0)
    approved_hit_rate_baseline: float | None = Field(default=None, ge=0, le=1)
    approved_hit_rate_drop_pp: float | None = Field(default=None, ge=0, le=100)
    minimum_hit_rate_sample_size: int | None = Field(default=None, ge=1)
    free_disk_bytes: int | None = Field(default=None, ge=0)
    required_free_disk_bytes: int | None = Field(default=None, ge=0)
    rss_bytes: int | None = Field(default=None, ge=0)
    suppression_commit_seconds: float | None = Field(default=None, ge=0)
    suppression_propagation_seconds: float | None = Field(default=None, ge=0)
    flags: set[Flag] = Field(default_factory=set)


class Alarm(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: UUID
    code: str
    severity: Literal["info", "warning", "critical"]
    owner: str
    runbook: str
    subject_key: str
    dedupe_key: str


def make_alarm(run_id: UUID, code: str, severity: Literal["info", "warning", "critical"] = "warning", *, subject_id: UUID | None = None) -> Alarm:
    allowed = set(get_args(Flag)) | {
        "source_stale", "source_mismatch", "source_mismatch_escalation", "field_fill_breach",
        "classification_drift", "volume_deviation", "volume_zero_threshold_missing",
        "hit_rate_deterioration", "disk_capacity", "memory_limit", "suppression_commit_delayed",
        "suppression_propagation_delayed",
    }
    if code not in allowed:
        raise ValueError("unknown alarm code")
    subject = str(subject_id) if subject_id else "run"
    digest = hashlib.sha256(json.dumps([str(run_id), code, subject], separators=(",", ":")).encode()).hexdigest()
    return Alarm(run_id=run_id, code=code, severity=severity,
                 owner="compliance" if code.startswith("suppression") else "operator",
                 runbook=f"ops/runbook.md#{code.replace('_', '-')}", subject_key=subject, dedupe_key=digest)


def evaluate_alarms(values: AlarmInputs) -> list[Alarm]:
    found = {}

    def add(code, severity="warning"):
        alarm = make_alarm(values.run_id, code, severity)
        found[alarm.dedupe_key] = alarm

    if any(value < 0 for value in values.comparable_volumes):
        raise ValueError("comparable volumes must be nonnegative")
    for flag in values.flags:
        severity = "info" if flag == "member_count_changed" else "critical"
        add(flag, severity)
    if values.source == "abr" and values.source_age_days is not None and values.source_age_days > 10:
        add("source_stale")
    if values.mismatch_hours is not None:
        if values.mismatch_hours >= 168:
            add("source_mismatch_escalation", "critical")
        elif values.mismatch_hours > 48:
            add("source_mismatch")
    # Integrity, resource and control alarms still apply on baseline/no-op runs.
    if values.field_fill_delta_pp is not None and abs(values.field_fill_delta_pp) > 2:
        add("field_fill_breach", "critical")
    if not values.baseline and not values.no_op:
        if values.classification_delta_pp is not None and abs(values.classification_delta_pp) > 3:
            add("classification_drift")
        if values.current_volume is not None and len(values.comparable_volumes) >= 4:
            reference = median(values.comparable_volumes[-4:])
            if reference:
                if abs(values.current_volume - reference) / reference > .5:
                    add("volume_deviation")
            elif values.zero_median_absolute_threshold is None:
                add("volume_zero_threshold_missing", "info")
            elif values.current_volume > values.zero_median_absolute_threshold:
                add("volume_deviation")
        if (values.hit_rate is not None and values.approved_hit_rate_baseline is not None
                and values.approved_hit_rate_drop_pp is not None
                and values.minimum_hit_rate_sample_size is not None
                and values.hit_rate_sample_size >= values.minimum_hit_rate_sample_size
                and (values.approved_hit_rate_baseline - values.hit_rate) * 100
                > values.approved_hit_rate_drop_pp):
            add("hit_rate_deterioration")
    if (values.free_disk_bytes is not None and values.required_free_disk_bytes is not None
            and values.free_disk_bytes < values.required_free_disk_bytes):
        add("disk_capacity", "critical")
    if values.rss_bytes is not None and values.rss_bytes > 2 * 1024**3:
        add("memory_limit", "critical")
    if values.suppression_commit_seconds is not None and values.suppression_commit_seconds > 5:
        add("suppression_commit_delayed", "critical")
    if values.suppression_propagation_seconds is not None and values.suppression_propagation_seconds > 60:
        add("suppression_propagation_delayed", "critical")
    return sorted(found.values(), key=lambda alarm: alarm.code)
