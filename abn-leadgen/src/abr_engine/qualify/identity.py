"""Reviewed group consolidation without rewriting contact evidence or historical outcomes."""
import json
from uuid import uuid4

from abr_engine.control.service import DomainError, json_safe


def duplicate_hints(conn, service, lead_id):
    """Opaque review hints only. A shared domain/phone/name never establishes identity."""
    service.personal_data_access(conn)
    lead = service.lead(conn, lead_id)
    family = service.group_family(conn, lead["group_id"])
    rows = conn.execute("""
      SELECT DISTINCT other.lead_id,other.group_id,
        CASE WHEN c.endpoint_token IS NOT NULL THEN 'shared_endpoint'
             WHEN d.registrable_domain IS NOT NULL THEN 'shared_domain'
             ELSE 'matching_name_and_full_address' END reason
      FROM lead_entity other
      LEFT JOIN contact_record c ON c.lead_id=other.lead_id AND EXISTS(
        SELECT 1 FROM contact_record own JOIN lead_entity ownlead USING(lead_id)
        WHERE ownlead.group_id=ANY(%s) AND own.endpoint_token=c.endpoint_token AND own.token_key_version=c.token_key_version)
      LEFT JOIN domain_identity d ON d.lead_id=other.lead_id AND EXISTS(
        SELECT 1 FROM domain_identity own JOIN lead_entity ownlead USING(lead_id)
        WHERE ownlead.group_id=ANY(%s) AND own.registrable_domain=d.registrable_domain)
      WHERE other.lifecycle='active' AND NOT(other.group_id=ANY(%s)) AND
        (c.endpoint_token IS NOT NULL OR d.registrable_domain IS NOT NULL OR
         (lower(trim(other.display_name))=lower(trim(%s)) AND
          length(trim(coalesce(other.fields->>'original_address','')))>0 AND
          lower(trim(other.fields->>'original_address'))=lower(trim(%s))))
      ORDER BY other.lead_id,other.group_id,reason LIMIT 50
      """, (family, family, family, lead["display_name"], lead["fields"].get("original_address", ""))).fetchall()
    return [{"lead_id": r["lead_id"], "group_id": service.canonical_group(conn, r["group_id"]), "reason": r["reason"],
             "action": "Review corroborating identity evidence; do not merge from this hint alone"} for r in rows]


def merge_groups(conn, service, data, actor):
    service.authority(conn)
    source = service.lead(conn, data["source_lead_id"])
    target = service.lead(conn, data["target_lead_id"])
    if source["revision"] != data["source_revision"] or target["revision"] != data["target_revision"]:
        raise DomainError("REVISION_CONFLICT", 409)
    source_group = service.canonical_group(conn, source["group_id"])
    target_group = service.canonical_group(conn, target["group_id"])
    if source_group == target_group or source_group != source["group_id"] or target_group != target["group_id"]:
        raise DomainError("MERGE_ALREADY_CONSOLIDATED", 409)
    evidence = data["evidence_refs"]
    if not all(isinstance(ref, str) and 1 <= len(ref.strip()) <= 500 for ref in evidence) or len({ref.strip() for ref in evidence}) < 2 or not data["reason"].strip():
        raise DomainError("MERGE_CORROBORATION_REQUIRED")
    family = service.group_family(conn, source_group) + service.group_family(conn, target_group)
    # A remote duplicate needs its own provider-reviewed consolidation; never silently reassign it.
    if conn.execute("SELECT 1 FROM crm_identity WHERE group_id=ANY(%s)", (family,)).fetchone():
        raise DomainError("REMOTE_MERGE_RECONCILIATION_REQUIRED", 409)
    if conn.execute("SELECT 1 FROM crm_outbox o JOIN lead_entity l USING(lead_id) WHERE l.group_id=ANY(%s) "
                    "AND o.state IN ('inflight','uncertain')", (family,)).fetchone():
        raise DomainError("REMOTE_MERGE_RECONCILIATION_REQUIRED", 409)
    merge_id = uuid4()
    conn.execute("UPDATE business_group SET merged_into_group_id=%s,restriction_revision=restriction_revision+1 WHERE group_id=%s",
                 (target_group, source_group))
    conn.execute("INSERT INTO group_merge(merge_id,source_group_id,target_group_id,actor_id,evidence_encrypted) VALUES(%s,%s,%s,%s,%s)",
                 (merge_id, source_group, target_group, actor, service.keys.encrypt(json.dumps(json_safe({"refs": evidence, "reason": data["reason"]})))))
    leads = conn.execute("SELECT lead_id,group_id FROM lead_entity WHERE group_id=ANY(%s)", (family,)).fetchall()
    for lead in leads:
        service.invalidate(conn, lead["lead_id"])
        conn.execute("UPDATE lead_entity SET revision=revision+1 WHERE lead_id=%s", (lead["lead_id"],))
        if lead["group_id"] != target_group:
            conn.execute("UPDATE lead_entity SET lifecycle='disqualified' WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("UPDATE candidate_queue SET state='disqualified' WHERE lead_id=%s", (lead["lead_id"],))
            conn.execute("INSERT INTO deletion_job(job_id,group_id) VALUES(%s,%s)", (uuid4(), lead["group_id"]))
        conn.execute("INSERT INTO propagation_outbox(outbox_id,group_id,reason) VALUES(%s,%s,'reviewed_merge')", (uuid4(), lead["group_id"]))
    # Copy active restrictions through the ordinary authority so all known endpoints are blocked.
    reasons = {row["reason"] for row in conn.execute("SELECT e.reason FROM suppression_event e WHERE e.group_id=ANY(%s) AND e.action='add' "
               "AND NOT EXISTS(SELECT 1 FROM suppression_event r WHERE r.resolves_event_id=e.event_id)", (family,)).fetchall()}
    for reason in reasons:
        service.suppress(conn, {"group_id": target_group, "reason": reason, "source": "reviewed_merge"}, actor, uuid4())
    service.audit(conn, actor, "business_groups_merged", merge_id, {"source_group_id": source_group, "target_group_id": target_group})
    return {"merge_id": merge_id, "canonical_group_id": target_group,
            "remaining_reasons": service.restricted(conn, target_group), "review_required": True}
