"""Persist deterministic <=60 group worklists under current control authority."""
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, json_safe
from abr_engine.export.report import ReportContext, ReportRow
from abr_engine.qualify.queue import QueueItem, select_worklist


def build_worklist(conn, service, week: date):
    if week.weekday() != 0:
        raise DomainError("MONDAY_REQUIRED")
    service.authority(conn)
    prior = conn.execute("SELECT * FROM worklist WHERE week=%s", (week,)).fetchone()
    if prior:
        return {"worklist_id": prior["worklist_id"], "replayed": True,
                "selected": conn.execute("SELECT count(*) AS n FROM worklist_row WHERE worklist_id=%s", (prior["worklist_id"],)).fetchone()["n"]}
    now = service.now(conn)
    conn.execute("UPDATE candidate_queue SET state='deferred',deferred_at=%s WHERE state IN ('pending_enrichment','needs_review','ready') "
                 "AND first_qualified_at <= %s", (now, now - timedelta(weeks=8)))
    candidates = conn.execute("SELECT DISTINCT ON(q.lead_id) q.*,l.group_id FROM candidate_queue q "
                              "JOIN lead_entity l USING(lead_id) ORDER BY q.lead_id,"
                              "CASE WHEN q.state IN ('pending_enrichment','needs_review','ready') THEN 0 ELSE 1 END,"
                              "q.first_qualified_at,q.candidate_id").fetchall()
    items, gates, selected_candidates = [], {}, {}
    for candidate in candidates:
        lead_id = candidate["lead_id"]
        contacts = conn.execute("SELECT contact_id,endpoint_token FROM contact_record WHERE lead_id=%s ORDER BY channel,contact_id", (lead_id,)).fetchall()
        decisions = [(r, service.gate(conn, r["contact_id"])) for r in contacts]
        allowed = [(r, g) for r, g in decisions if g["allowed"]]
        if allowed:
            gates[str(lead_id)] = {**json_safe(allowed[0][1]), "contact_id": str(allowed[0][0]["contact_id"])}
        family = service.group_family(conn, candidate["group_id"])
        worked = conn.execute("SELECT 1 FROM worklist_row w JOIN lead_entity l USING(lead_id) WHERE l.group_id=ANY(%s) LIMIT 1", (family,)).fetchone() is not None
        items.append(QueueItem(str(lead_id), str(service.canonical_group(conn, candidate["group_id"])), candidate["first_qualified_at"], candidate["score"],
                               candidate["score"], candidate["state"], candidate["tier"], bool(allowed), worked,
                               bool(service.restricted(conn, candidate["group_id"])), endpoint_tokens=tuple(r["endpoint_token"] for r, g in allowed)))
        selected_candidates[str(lead_id)] = candidate
    selection = select_worklist(items, now)
    worklist_id = uuid4()
    conn.execute("INSERT INTO worklist(worklist_id,week) VALUES(%s,%s)", (worklist_id, week))
    if service.settings.mode == "fixture":
        for actor in ("fixture-reviewer", "fixture-operator"):
            conn.execute("INSERT INTO worklist_assignment(worklist_id,actor_id) VALUES(%s,%s)", (worklist_id, actor))
    for item in selection.selected:
        candidate = selected_candidates[item.lead_id]
        lead = service.lead(conn, item.lead_id)
        conn.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,candidate_id,decision,selected_tier,selected_signal) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                     (uuid4(), worklist_id, item.lead_id, candidate["candidate_id"], Jsonb(gates[item.lead_id]), lead["tier"], lead["signal"]))
        conn.execute("UPDATE candidate_queue SET state='exported',exported_at=%s WHERE candidate_id=%s", (now, candidate["candidate_id"]))
    return {"worklist_id": worklist_id, "selected": len(selection.selected), "excluded": selection.excluded, "replayed": False}


def report_context(conn, service, worklist_id, run_id):
    service.personal_data_access(conn)
    records = conn.execute("SELECT r.*,l.group_id,l.display_name,l.source,l.score FROM worklist_row r JOIN lead_entity l USING(lead_id) "
                           "WHERE worklist_id=%s ORDER BY l.score DESC,r.lead_id", (worklist_id,)).fetchall()
    rows = []
    canonical = {r["group_id"]: service.canonical_group(conn, r["group_id"]) for r in records}
    records.sort(key=lambda r: (r["group_id"] != canonical[r["group_id"]], -r["score"], str(r["row_id"])))
    seen = set()
    for r in records:
        if canonical[r["group_id"]] in seen:
            continue
        seen.add(canonical[r["group_id"]])
        outcome = conn.execute("SELECT * FROM outcome_event WHERE row_id=%s ORDER BY recorded_seq DESC LIMIT 1", (r["row_id"],)).fetchone() or {}
        source_manifest = conn.execute("SELECT s.manifest FROM source_snapshot s JOIN (SELECT snapshot_id,event_id FROM abr_event UNION ALL SELECT snapshot_id,event_id FROM qbcc_event) e USING(snapshot_id) "
                                       "JOIN candidate_queue q ON q.event_key=e.event_id::text WHERE q.candidate_id=%s", (r["candidate_id"],)).fetchone()
        publication = None
        if source_manifest:
            manifest = source_manifest["manifest"]
            if manifest.get("publisher_timestamp"):
                value = datetime.fromisoformat(manifest["publisher_timestamp"])
                publication = value if value.tzinfo else None
            elif manifest.get("effective_date"):
                publication = datetime.combine(date.fromisoformat(manifest["effective_date"]), time.min, UTC)
        contact_id = r["decision"].get("contact_id")
        gate: dict[str, Any] = service.gate(conn, contact_id) if contact_id else {"allowed": False, "reason_codes": ["NO_CONTACT"], "versions": {}}
        contact = service.contact(conn, contact_id) if contact_id else None
        from abr_engine.qualify.identity import duplicate_hints
        hints = duplicate_hints(conn, service, r["lead_id"])
        rows.append(ReportRow(row_id=r["row_id"], worklist_id=worklist_id, lead_id=r["lead_id"], group_id=canonical[r["group_id"]],
                              row_version=r["version"], business_name=r["display_name"], source=r["source"], signal=r["selected_signal"],
                              tier=r["selected_tier"], score=r["score"], channel=gate.get("channel"),
                              source_published_at=publication,
                              candidate_endpoint=service.keys.decrypt(contact["encrypted_value"]) if gate["allowed"] and contact else None,
                              export_allowed=gate["allowed"], gate_checked_at=gate.get("checked_at"), gate_expires_at=gate.get("expires_at"),
                              policy_version=gate["versions"].get("policy"), reason_codes=gate["reason_codes"],
                              next_action=("Review potential duplicate identity before manual export; shared details are only a clue"
                                           if hints else "Review current identity and contact restrictions"),
                              status=r["outcome"], attempts=outcome.get("attempts", 0), invitation_state=outcome.get("invitation_state", "unknown"),
                              invitation_evidence_ref=outcome.get("invitation_evidence_ref"), notes=outcome.get("notes", ""), occurred_at=outcome.get("occurred_at")))
    return ReportContext(run_id=run_id, generated_at=service.now(conn), mode=service.settings.mode, authorised_operator=True, rows=rows)
