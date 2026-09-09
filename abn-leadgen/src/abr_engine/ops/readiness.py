"""Read-only live release evidence; implementation blockers cannot be approved away."""
from __future__ import annotations

from datetime import UTC, datetime

from abr_engine.compliance.policy import REQUIRED_GATES, current_gate_evidence
from abr_engine.config import Settings

# Keep these explicit until the corresponding real end-to-end acceptance is implemented.
# A transport implementation, YAML switch or synthetic test is not a working release path.
RUNTIME_BLOCKERS = {
    "collection": ["LIVE_PIPELINE_NOT_CONNECTED", "LIVE_DASHBOARD_NOT_CONNECTED"],
    "abr": ["LIVE_ABR_GENERATION_MAPPING_UNVERIFIED", "LIVE_PIPELINE_NOT_CONNECTED"],
    "crm": ["LIVE_CRM_DRAIN_NOT_CONNECTED", "LIVE_SUPPRESSION_PROPAGATION_NOT_CONNECTED"],
}


def readiness_report(settings: Settings, rows: list[dict], *, target: str,
                     now: datetime | None = None, database_available: bool = True) -> dict:
    if target not in {"pilot", "production"}:
        raise ValueError("A pilot or production target is required")
    now = now or datetime.now(UTC)
    selected = ("collection", "crm") if target == "pilot" else ("collection", "crm", "abr")
    checks = []
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
        if settings.mode != target:
            blockers.append("TARGET_ENVIRONMENT_NOT_CONFIGURED")
        if not settings.capabilities.get(capability, False):
            blockers.append("CAPABILITY_DISABLED")
        if not database_available:
            blockers.append("DATABASE_AUTHORITY_UNAVAILABLE")
        blockers.extend("GATE_" + gate + "_CLOSED" for gate in missing)
        checks.append({"capability": capability, "status": "blocked" if blockers else "ready",
                       "approved_gates": valid, "missing_gates": missing, "blockers": blockers})
    return {
        "status": "blocked" if any(c["blockers"] for c in checks) else "ready",
        "checked_at": now.isoformat(), "configured_mode": settings.mode, "target_mode": target,
        "database_authority_available": database_available, "checks": checks,
        "outreach": "outside_part_1", "production_installed": False,
        "next_steps": [
            "Supply the approved AU host and restricted service/storage identities.",
            "Record actual current G1/G2/G3/G5/G7 evidence for the chosen pilot capabilities.",
            "Connect real pipeline, dashboard, vendor write-back and suppression, then verify together.",
            "Start the measured QBCC pilot only after a usable authorised worklist is available.",
            "Require four measured QBCC weeks and the G6 owner decision before live ABR expansion.",
        ],
    }
