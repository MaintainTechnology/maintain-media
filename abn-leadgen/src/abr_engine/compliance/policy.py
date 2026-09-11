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


def website_collection_policy(conn, settings: Settings, now: datetime) -> dict:
    """Current live phone-only purpose, bound to the exact website G1 evidence."""
    reasons = gate_reasons(conn, settings, "website_collection", now)
    if not reasons:
        reasons = gate_reasons(conn, settings, "retention", now)
    closed = {"allowed_channels": [], "expires_at": None, "reason_codes": reasons}
    if reasons:
        return closed
    policy = conn.execute("SELECT * FROM policy ORDER BY approved_at DESC,version DESC LIMIT 1").fetchone()
    authority = conn.execute(
        "SELECT evidence_sha256 FROM release_gate WHERE environment=%s AND scope='website_collection' "
        "AND gate_name='G1' ORDER BY revision DESC LIMIT 1", (settings.mode,),
    ).fetchone()
    policy_settings = policy["settings"] if policy and isinstance(policy["settings"], dict) else {}
    purpose = policy_settings.get("website_collection", {})
    retention = policy_settings.get("retention", {})
    valid = False
    if isinstance(purpose, dict):
        try:
            expiry = datetime.fromisoformat(purpose.get("expires_at", ""))
            channels = purpose.get("allowed_channels")
            valid = bool(
                policy and policy["state"] == "approved" and policy["scope"] == settings.mode
                and policy["approved_at"] <= now < policy["expires_at"]
                and isinstance(policy["evidence_ref"], str) and policy["evidence_ref"].strip()
                and isinstance(policy["actor_id"], str) and policy["actor_id"].strip()
                and purpose.get("approved") is True
                and isinstance(channels, list) and len(channels) == 2
                and set(channels) == {"mobile", "landline"}
                and expiry.tzinfo is not None and now < expiry <= policy["expires_at"]
                and isinstance(purpose.get("evidence_sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", purpose["evidence_sha256"])
                and authority and purpose["evidence_sha256"] == authority["evidence_sha256"]
                and isinstance(retention, dict) and retention.get("approved") is True
                and retention.get("schedule_version") == "abr-v4-defaults"
                and retention.get("retain_selected_evidence") is False
                and isinstance(retention.get("evidence_sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", retention["evidence_sha256"])
            )
        except (TypeError, ValueError):
            pass
    if not valid:
        return {**closed, "reason_codes": ["WEBSITE_COLLECTION_POLICY_REQUIRED"]}
    return {"allowed_channels": ["mobile", "landline"], "expires_at": expiry.isoformat(), "reason_codes": []}
