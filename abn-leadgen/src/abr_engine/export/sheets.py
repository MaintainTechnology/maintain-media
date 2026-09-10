"""Account-bound private worklist disclosure; no raw records or fixture fallback."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from abr_engine.compliance.policy import current_gate_evidence, gate_reasons
from abr_engine.control.service import DomainError
from abr_engine.control.sheets_auth import BridgeRegistry, load_bridge_registry
from abr_engine.db import transaction
from abr_engine.export.report import CSV_FIELDS, worklist_rows
from abr_engine.export.worklist import report_context


def pull_worklist(settings, service, actor, registry: BridgeRegistry) -> dict:
    """The HTTP adapter must authenticate with SheetsAuthority before calling this.

    Every workbook reader must be mapped and entitled to the chosen worklist. A
    reviewer-owned timer must not expose their larger workspace to an unassigned
    operator merely because that operator can open the same Google Sheet.
    """
    actor.require("operator", "reviewer", "compliance")
    path = settings.sheets_bridge_file
    if path is None or settings.mode == "fixture":
        raise DomainError("LIVE_SHEETS_ONLY", 403)
    current = load_bridge_registry(path)
    if (current != registry or actor.actor_id not in current.editors
            or actor.scopes != frozenset(current.editors[actor.actor_id])):
        raise DomainError("SHEETS_REGISTRY_CHANGED", 401)
    try:
        raw = path.read_bytes()
        if load_bridge_registry(path) != current or path.read_bytes() != raw:
            raise DomainError("SHEETS_REGISTRY_CHANGED", 401)
    except OSError:
        raise DomainError("SHEETS_REGISTRY_CHANGED", 401) from None
    checksum = hashlib.sha256(raw).hexdigest()
    with transaction(settings) as conn:
        service.personal_data_access(conn)
        now = service.now(conn)
        result: dict[str, Any] = {"schema_version": 1, "spreadsheet_id": current.spreadsheet_id,
                  "sheet_id": current.sheet_id, "snapshot_id": str(uuid4()),
                  "owner_email": current.owner_email, "reader_emails": sorted(current.editors),
                  "generated_at": now.isoformat(),
                  "expires_at": min(now + timedelta(seconds=90), current.expires_at).isoformat(),
                  "disclosure_allowed": False, "reason_codes": [], "worklist_id": None,
                  "columns": list(CSV_FIELDS), "rows": []}
        reasons = gate_reasons(conn, settings, "sheets", now)
        gate = conn.execute("SELECT * FROM release_gate WHERE gate_name='G5' AND environment=%s "
                            "AND scope='sheets' ORDER BY revision DESC LIMIT 1", (settings.mode,)).fetchone()
        if (not gate or not current_gate_evidence(gate, now) or gate["evidence_sha256"] != checksum
                or gate["actor_id"] != current.approved_by):
            reasons.append("SHEETS_INSTALLATION_NOT_APPROVED")
        if reasons:
            result["reason_codes"] = sorted(set(reasons))
            return result  # Authenticated redaction instruction; zero business fields disclosed.
        gates = conn.execute("SELECT DISTINCT ON(gate_name) expires_at FROM release_gate "
                             "WHERE environment=%s AND scope='sheets' ORDER BY gate_name,revision DESC",
                             (settings.mode,)).fetchall()
        result["expires_at"] = min(now + timedelta(seconds=90), current.expires_at,
                                    *(row["expires_at"] for row in gates)).isoformat()
        worklist = conn.execute("SELECT worklist_id FROM worklist ORDER BY week DESC LIMIT 1").fetchone()
        if worklist:
            worklist_id = worklist["worklist_id"]
            for email, scopes in current.editors.items():
                if not set(scopes).intersection({"reviewer", "compliance"}):
                    assigned = conn.execute("SELECT 1 FROM worklist_assignment WHERE worklist_id=%s AND actor_id=%s",
                                            (worklist_id, email)).fetchone()
                    if not assigned:
                        raise DomainError("SHEETS_READER_NOT_ASSIGNED", 403)
            context = report_context(conn, service, worklist_id, worklist_id)
            result["rows"] = worklist_rows(context)
            result["worklist_id"] = str(worklist_id)
        if datetime.fromisoformat(result["expires_at"]) <= service.now(conn):
            result.update(rows=[], worklist_id=None, reason_codes=["SHEETS_DISCLOSURE_EXPIRED"])
            return result
        result["disclosure_allowed"] = True
        service.audit(conn, actor.actor_id, "private_sheets_worklist_pulled", current.spreadsheet_id,
                      {"snapshot_id": result["snapshot_id"], "row_count": len(result["rows"]),
                       "sheet_id": current.sheet_id, "registry_sha256": checksum})
        return result
