"""Current capability approvals; no implicit live authority."""
import re
from datetime import datetime

from abr_engine.config import Settings

REQUIRED_GATES = {
    "collection": {"G1", "G2", "G3", "G7"},
    "email_action": {"G1", "G3", "G4", "G7"},
    "phone_action": {"G1", "G3", "G4", "G7"},
    "crm": {"G1", "G3", "G5", "G7"},
    "abr": {"G1", "G2", "G3", "G6", "G7"},
}


def current_gate_evidence(record: dict, now: datetime) -> bool:
    """Use the same closed evidence contract for admission and release reporting."""
    approved, expires = record.get("approved_at"), record.get("expires_at")
    reference, checksum = record.get("evidence_ref"), record.get("evidence_sha256")
    return bool(
        isinstance(approved, datetime) and approved.tzinfo is not None
        and isinstance(expires, datetime) and expires.tzinfo is not None
        and approved <= now < expires
        and isinstance(reference, str) and reference.strip()
        and isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum)
    )


def gate_reasons(conn, settings: Settings, capability: str, now: datetime) -> list[str]:
    if settings.mode == "fixture":
        return []  # Synthetic service evaluations only; fixture transport cannot send.
    if not settings.capabilities.get(capability, False):
        return ["CAPABILITY_DISABLED"]
    rows = conn.execute("SELECT DISTINCT ON (gate_name) * FROM release_gate WHERE environment=%s "
                        "AND scope=%s ORDER BY gate_name,revision DESC", (settings.mode, capability)).fetchall()
    valid = {r["gate_name"] for r in rows if current_gate_evidence(r, now)}
    return ["GATE_" + gate + "_CLOSED" for gate in sorted(REQUIRED_GATES[capability] - valid)]
