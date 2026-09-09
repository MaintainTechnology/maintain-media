"""Explicit synthetic review records for local acceptance; never runs in live modes."""
from datetime import timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, digest

CONTENT = digest({"body": "Synthetic relevant service example", "sender": "Maintain Media fixture",
                  "unsubscribe": "fixture no-contact utility", "purpose": "local acceptance only"})


def seed_policy(conn, service):
    if service.settings.mode != "fixture":
        raise DomainError("FIXTURE_ONLY", 403)
    now = service.now(conn)
    version = "fixture-policy-" + str(uuid4())
    conn.execute("INSERT INTO policy(version,state,scope,evidence_ref,actor_id,approved_at,expires_at,settings) "
                 "VALUES(%s,'approved','synthetic','synthetic-approval-only','fixture-owner',%s,%s,%s)",
                 (version, now - timedelta(seconds=1), now + timedelta(days=90), Jsonb({
                     "approved_content": {"fixture-campaign:fixture-template": CONTENT},
                     "sender_identity": "Maintain Media fixture", "unsubscribe_utility": True,
                     "notice_sources": ["synthetic QBCC", "synthetic website"],
                     "holiday_calendar": {"from": now.date().isoformat(), "to": (now + timedelta(days=30)).date().isoformat(),
                                          "localities": ["Brisbane", "Coffs Harbour"], "holidays": [],
                                          "evidence_ref": "synthetic-calendar-not-real-holidays"}})))
    return version


def seed_contact(conn, service, *, name="Synthetic Builder", alias=None, allow=True, phone=False,
                 existing_lead=None):
    if service.settings.mode != "fixture":
        raise DomainError("FIXTURE_ONLY", 403)
    alias = alias or str(uuid4().int)[:12]
    lead = existing_lead or service.create_lead(conn, name=name, source="qbcc", alias=alias,
                                               fields={"recipient_timezone": "Australia/Brisbane",
                                                       "timezone_reviewed": True, "locality": "Brisbane"})
    now = service.now(conn)
    if existing_lead:
        alias_row = conn.execute("SELECT encrypted_identifier FROM lead_source_link WHERE group_id=%s AND source_type='qbcc' ORDER BY link_id LIMIT 1", (lead["group_id"],)).fetchone()
        alias = service.keys.decrypt(alias_row["encrypted_identifier"])
        conn.execute("UPDATE lead_entity SET fields=%s WHERE lead_id=%s", (Jsonb({"recipient_timezone": "Australia/Brisbane", "timezone_reviewed": True, "locality": "Brisbane"}), lead["lead_id"]))
    domain = "example.com"
    identity = service.identity(conn, {"lead_id": lead["lead_id"], "registrable_domain": domain,
                                      "expected_revision": lead["revision"], "assessment": "approved",
                                      "method": "exact_identifier", "evidence_refs": {
                                          "source_identifier": alias, "page_identifier": alias,
                                          "html": f"<p>QBCC licence {alias}</p>", "page_url": "https://example.com/",
                                          "captured_at": now.isoformat(),
                                          "references": ["fixture-source", "fixture-html"]},
                                      "reason": "Explicit synthetic identity fixture"}, "fixture-reviewer")
    value = "0412345678" if phone else "synthetic-" + str(lead["lead_id"])[:8] + "@example.com"
    html = f"<html><title>Synthetic business</title><p>Licence {alias}</p><p>{value}</p></html>"
    contact = service.add_contact(conn, lead_id=lead["lead_id"], channel="mobile" if phone else "email",
                                  value=value, identity_id=identity["identity_id"], source_url="https://example.com/contact",
                                  excerpt="Synthetic contact page for local tests", actor="fixture-collector",
                                  capture={"html": html, "captured_at": now, "collector_version": "fixture-v1",
                                           "robots_result": "allowed", "terms_scope": "Explicit fixture content permission",
                                           "method": "synthetic-static"}, verification="deliverable" if allow else "unknown",
                                  verified_at=now)
    service.licence(conn, {"lead_id": lead["lead_id"], "licence_number": alias, "status": "active",
                          "identity_match": True, "evidence_ref": "synthetic-current-licence-review", "reviewed_at": now}, "fixture-reviewer")
    if not phone:
        service.basis(conn, {"contact_id": contact["contact_id"], "channel": "email", "expected_revision": 1,
                            "basis_type": "express", "assessment_state": "pass" if allow else "unknown",
                            "express_scope": "Synthetic permission for fixture-campaign only",
                            "express_evidence": {"source_ref": "synthetic-signed-consent-fixture", "consented_at": now.isoformat(),
                                                 "campaign_ids": ["fixture-campaign"], "withdrawal_state": "active"},
                            "evidence_provenance_id": contact["first_provenance_id"], "reason": "Synthetic express consent test"}, "fixture-reviewer")
    else:
        from abr_engine.compliance.wash import create_batch, import_receipt
        batch = create_batch(conn, service, [value])
        records = [{"phone": value, "result": "clear" if allow else "listed", "washed_at": now.isoformat()}]
        import_receipt(conn, service, batch["batch_id"], records,
                       {"format": "maintain-fixture-wash-v1", "account": "fixture-account", "batch_digest": batch["digest"],
                        "count": 1, "records_digest": digest(records)}, "fixture-operator")
    conn.execute("UPDATE candidate_queue SET state=%s WHERE lead_id=%s", ("ready" if allow else "needs_review", lead["lead_id"]))
    return {"lead": service.lead(conn, lead["lead_id"]), "contact": service.contact(conn, contact["contact_id"]), "identity": identity}
