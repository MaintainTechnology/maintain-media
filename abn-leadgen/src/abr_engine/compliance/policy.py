"""Current capability approvals; no implicit live authority."""
import re
from datetime import datetime

from abr_engine.config import Settings

REQUIRED_GATES = {
    "collection": {"G1", "G2", "G3", "G7"},
    "website_collection": {"G1", "G3", "G7"},
    "email_action": {"G1", "G3", "G4", "G7"},
    "phone_action": {"G1", "G3", "G4", "G7"},
    "crm": {"G1", "G3", "G5", "G7"},
    "sheets": {"G1", "G3", "G5", "G7"},
    "abr": {"G1", "G2", "G3", "G6", "G7"},
    "retention": {"G1", "G3", "G7"},
    "backup": {"G1", "G3", "G7"},
}

# Website/address collection is a separate reviewed purpose, never implicit in
# permission to ingest the QBCC register. Its source authority must remain current too.
REQUIRED_CAPABILITIES = {"website_collection": ("collection",)}


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
    reasons = ["GATE_" + gate + "_CLOSED" for gate in sorted(REQUIRED_GATES[capability] - valid)]
    for prerequisite in REQUIRED_CAPABILITIES.get(capability, ()):
        reasons.extend(gate_reasons(conn, settings, prerequisite, now))
    return list(dict.fromkeys(reasons))
