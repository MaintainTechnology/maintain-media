"""Read-only implementation, runtime observations and release approvals.

Optional runtime receipts are caller-supplied observations for this report only.
They never enable a capability, create a release gate, or replace gate evidence.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from abr_engine.compliance.policy import REQUIRED_CAPABILITIES, REQUIRED_GATES, current_gate_evidence
from abr_engine.config import Settings

# Source intake/review, dashboard, CRM drain/suppression and Sheets pull/write-back
# are connected in this build. Their installed account behavior still needs proof.
RUNTIME_BLOCKERS = {
    "collection": [],
    "website_collection": [],
    "crm": [],
    "sheets": [],
    "abr": ["LIVE_ABR_GENERATION_MAPPING_UNVERIFIED"],
}
RUNTIME_CHECKS = {
    "collection": {"private_service_installed", "database_access", "dashboard_auth", "qbcc_pipeline",
                   "scheduled_runs", "backup_restore"},
    "website_collection": {"scoped_collection_admission", "identity_licence_checks", "bounded_pinned_crawl",
                           "suppression_and_withdrawal", "provenance_without_permission"},
    "crm": {"ghl_account_installed", "field_mapping", "outbox_recovery", "suppression_readback", "workflow_isolation"},
    "sheets": {"private_workbook_installed", "editor_identity", "worklist_pull", "outcome_writeback", "suppression_latency"},
    "abr": {"abr_pipeline", "full_scale_capacity", "measured_qbcc_pilot"},
}


def _instant(value):
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
        return result if isinstance(result, datetime) and result.tzinfo is not None else None
    except ValueError:
        return None


def _runtime_observation(records: list[dict], capability: str, target: str, now: datetime) -> dict:
    required = RUNTIME_CHECKS[capability]
    unknown = {"status": "unverified", "observed_at": None, "passed_checks": [],
               "failed_checks": [], "unverified_checks": sorted(required)}
    selected = [row for row in records if isinstance(row, dict)
                and row.get("environment") == target and row.get("capability") == capability]
    if not selected or any(type(row.get("revision")) is not int or row["revision"] < 1 for row in selected):
        return unknown
    latest = max(selected, key=lambda row: row["revision"])
    if sum(row["revision"] == latest["revision"] for row in selected) != 1:
        return unknown
    observed, expires = _instant(latest.get("observed_at")), _instant(latest.get("expires_at"))
    checks = latest.get("checks")
    if (set(latest) != {"environment", "capability", "revision", "observed_at", "expires_at",
                       "evidence_ref", "evidence_sha256", "checks"}
            or not observed or not expires or not observed <= now < expires
            or not isinstance(latest.get("evidence_ref"), str) or not latest["evidence_ref"].strip()
            or not isinstance(latest.get("evidence_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", latest["evidence_sha256"])
            or not isinstance(checks, dict) or set(checks) != required
            or any(type(value) is not bool for value in checks.values())):
        return unknown
    return {"status": "verified" if all(checks.values()) else "failed", "observed_at": observed.isoformat(),
            "passed_checks": sorted(name for name, passed in checks.items() if passed),
            "failed_checks": sorted(name for name, passed in checks.items() if not passed), "unverified_checks": []}


def readiness_report(settings: Settings, rows: list[dict], *, target: str,
                     now: datetime | None = None, database_available: bool = True,
                     runtime_evidence: list[dict] | None = None) -> dict:
    if target not in {"pilot", "production"}:
        raise ValueError("A pilot or production target is required")
    now = now or datetime.now(UTC)
    selected: tuple[str, ...] = ("collection", "crm", "sheets") if target == "pilot" else ("collection", "crm", "sheets", "abr")
    if settings.capabilities.get("website_collection", False):
        selected += ("website_collection",)
    checks: list[dict] = []
    for capability in selected:
        latest: dict[str, dict] = {}
        for row in rows:
            if row["environment"] != target or row["scope"] != capability:
                continue
            prior = latest.get(row["gate_name"])
            if prior is None or row["revision"] > prior["revision"]:
                latest[row["gate_name"]] = row
        missing = []
        valid = []
        for gate in sorted(REQUIRED_GATES[capability]):
            record = latest.get(gate)
            if record and current_gate_evidence(record, now):
                valid.append(gate)
            else:
                missing.append(gate)
        blockers = list(RUNTIME_BLOCKERS[capability])
        runtime = _runtime_observation(runtime_evidence or [], capability, target, now)
        if runtime["status"] != "verified":
            blockers.append("LIVE_RUNTIME_CHECK_FAILED" if runtime["status"] == "failed" else "LIVE_RUNTIME_EVIDENCE_UNVERIFIED")
        if settings.mode != target:
            blockers.append("TARGET_ENVIRONMENT_NOT_CONFIGURED")
        if not settings.capabilities.get(capability, False):
            blockers.append("CAPABILITY_DISABLED")
        if not database_available:
            blockers.append("DATABASE_AUTHORITY_UNAVAILABLE")
        blockers.extend("GATE_" + gate + "_CLOSED" for gate in missing)
        for prerequisite in REQUIRED_CAPABILITIES.get(capability, ()):
            if not any(c["capability"] == prerequisite and c["status"] == "ready" for c in checks):
                blockers.append("DEPENDENCY_" + prerequisite.upper() + "_BLOCKED")
        checks.append({"capability": capability, "status": "blocked" if blockers else "ready",
                       "implementation_status": "mapping_unverified" if capability == "abr" else "implemented",
                       "runtime": runtime, "approved_gates": valid, "missing_gates": missing, "blockers": blockers})
    # A declared mode, reachable DB or approved G3/G7 is not an installation observation.
    installed = True if "private_service_installed" in checks[0]["runtime"]["passed_checks"] else None
    return {
        "status": "blocked" if any(c["blockers"] for c in checks) else "ready",
        "checked_at": now.isoformat(), "configured_mode": settings.mode, "target_mode": target,
        "database_authority_available": database_available, "checks": checks,
        "outreach": "outside_part_1", "target_service_installed": installed,
        "production_installed": installed if target == "production" else None,
        "runtime_evidence_source": "caller_supplied_observation" if runtime_evidence else "not_supplied",
        "next_steps": [
            "Verify the installed AU service, database access, staff sign-in, scheduled jobs and backup recovery; attach dated runtime observations.",
            "Record current G1/G2/G3/G5/G7 evidence for the required scopes; code and installation observations do not grant approval.",
            "Verify the actual GHL account and private Sheet: field mapping, named users, write-back, retries and measured suppression behavior.",
            "Start the measured QBCC pilot only after a usable authorised worklist is available.",
            "Require four measured QBCC weeks and the G6 owner decision before live ABR expansion.",
        ],
    }
