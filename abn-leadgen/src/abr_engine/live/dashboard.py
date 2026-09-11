"""Private projections of actual PostgreSQL lead and run state; no fixture fallback."""

from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from abr_engine.compliance.policy import gate_reasons, website_collection_policy
from abr_engine.control.service import DomainError, json_safe
from abr_engine.db import lock


def job_projection(receipt):
    result = dict(receipt)
    result.setdefault("phase", result.get("state"))
    if result.get("state") in {"discovering", "downloading", "staging", "accepting", "validating", "parsing", "diffing", "promoting"}:
        result["state"] = "running"
    reasons = result.get("reason_codes") or []
    result["error_code"] = reasons[0] if reasons else None
    return json_safe(result)


def preferences(conn, settings):
    row = conn.execute("SELECT value FROM system_state WHERE name='live_dashboard_settings'").fetchone()
    return (
        row["value"]
        if row
        else {"default_source": "qbcc", "monthly_cap_micro_aud": settings.monthly_cap_micro_aud}
    )


def save_preferences(conn, service, patch, actor):
    lock(conn, "budget-policy")
    values = preferences(conn, service.settings)
    values.update(patch)
    if (
        values["default_source"] not in {"qbcc", "abr", "all"}
        or type(values["monthly_cap_micro_aud"]) is not int
        or not 0 <= values["monthly_cap_micro_aud"] <= service.settings.monthly_cap_micro_aud
    ):
        raise DomainError("INVALID_SETTINGS", 422)
    conn.execute(
        "INSERT INTO system_state(name,value) VALUES('live_dashboard_settings',%s) "
        "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
        (Jsonb(values),),
    )
    service.audit(conn, actor, "dashboard_settings_changed", "live_dashboard_settings", values)
    return values


def _crm_handoff(conn, service, actor, row_id, reasons):
    if "reviewer" not in actor.scopes:
        return None
    from abr_engine.export.crm import handoff_status
    return handoff_status(conn, service, row_id, contract_reasons=reasons)


def dashboard_state(conn, service, actor, *, worker_available=False):
    service.personal_data_access(conn)
    now = service.now(conn)
    crm_reasons = gate_reasons(conn, service.settings, "crm", now)
    if not crm_reasons and service.settings.mode != "fixture":
        from abr_engine.export.live_contract import live_contract
        try:
            live_contract(conn, service)
        except DomainError as error:
            crm_reasons = error.details.get("reasons") or [error.code]
    settings = preferences(conn, service.settings)
    records = conn.execute(
        "SELECT l.*,q.state AS queue_state,q.stage_data,w.row_id,w.version AS row_version,w.outcome,"
        "w.worklist_id,w.approval_state FROM lead_entity l "
        "JOIN business_group b USING(group_id) "
        "LEFT JOIN LATERAL (SELECT state,stage_data FROM candidate_queue WHERE lead_id=l.lead_id "
        "ORDER BY last_qualifying_at DESC,candidate_id LIMIT 1) q ON true "
        "LEFT JOIN LATERAL (SELECT r.* FROM worklist_row r JOIN worklist wl USING(worklist_id) "
        "WHERE r.lead_id=l.lead_id ORDER BY wl.week DESC LIMIT 1) w ON true "
        "WHERE b.merged_into_group_id IS NULL ORDER BY l.last_qualifying_at DESC,l.lead_id LIMIT 200"
    ).fetchall()
    website_jobs = {}
    if "reviewer" in actor.scopes:
        from abr_engine.live.enrichment import _website_receipt
        website_jobs = {
            row["manifest"]["lead_id"]: job_projection(_website_receipt(row))
            for row in conn.execute(
                "SELECT DISTINCT ON (manifest->>'lead_id') * FROM pipeline_run WHERE mode=%s "
                "AND manifest->>'kind'='website_collection_job' AND manifest->>'lead_id'=ANY(%s) "
                "ORDER BY manifest->>'lead_id',started_at DESC,run_id DESC",
                (service.settings.mode, [str(row["lead_id"]) for row in records]),
            ).fetchall()
        }
    leads = []
    for row in records:
        identifiers = conn.execute(
            "SELECT source_type,encrypted_identifier FROM lead_source_link WHERE group_id=%s "
            "ORDER BY linked_at DESC",
            (row["group_id"],),
        ).fetchall()
        abn = next(
            (
                service.keys.decrypt(link["encrypted_identifier"])
                for link in identifiers
                if link["source_type"] == "abn"
            ),
            None,
        )
        reasons = service.restricted(conn, row["group_id"])
        contacts = conn.execute(
            "SELECT contact_id,channel,revision,first_provenance_id FROM contact_record WHERE lead_id=%s ORDER BY contact_id",
            (row["lead_id"],),
        ).fetchall()
        safe_contacts = []
        for contact in contacts:
            decision = service.gate(conn, contact["contact_id"])
            safe_contacts.append(
                {
                    "contact_id": contact["contact_id"],
                    "channel": contact["channel"],
                    "revision": contact["revision"],
                    "provenance_id": contact["first_provenance_id"],
                    "allowed": decision["allowed"],
                    "reason_codes": decision["reason_codes"],
                }
            )
            reasons.extend(decision["reason_codes"])
        if not contacts:
            reasons.append("NO_CONTACT")
        outcome = (
            conn.execute(
                "SELECT attempts,invitation_state,invitation_evidence_ref,notes,occurred_at "
                "FROM outcome_event WHERE row_id=%s ORDER BY recorded_seq DESC LIMIT 1",
                (row["row_id"],),
            ).fetchone()
            if row["row_id"]
            else None
        ) or {}
        identity = conn.execute("SELECT identity_id,registrable_domain,assessment,expires_at FROM domain_identity "
                                "WHERE lead_id=%s ORDER BY assessment_seq DESC LIMIT 1", (row["lead_id"],)).fetchone()
        leads.append(
            {
                "lead_id": row["lead_id"],
                "group_id": row["group_id"],
                "business_name": row["display_name"],
                "abn": abn,
                "source": row["source"],
                "signal": row["signal"],
                "tier": row["tier"],
                "score": row["score"],
                "revision": row["revision"],
                "state": row["queue_state"] or row["lifecycle"],
                "first_observed_at": row["first_qualified_at"],
                "location": " ".join(filter(None, [row["state"], row["postcode"]])),
                "reason_codes": sorted(set(reasons)),
                "contacts": safe_contacts,
                "website_identity": identity,
                "website_job": website_jobs.get(str(row["lead_id"])),
                "row_id": row["row_id"],
                "row_version": row["row_version"],
                "worklist_id": row["worklist_id"],
                "outcome": row["outcome"],
                "approval_state": row["approval_state"],
                "crm_handoff": _crm_handoff(conn, service, actor, row["row_id"], crm_reasons),
                "outcome_details": outcome,
                "next_action": "Review current identity and contact restrictions; no messages are sent by this tool.",
            }
        )
    raw_runs = conn.execute(
        "SELECT * FROM pipeline_run WHERE mode=%s ORDER BY started_at DESC LIMIT 20", (service.settings.mode,)
    ).fetchall()
    runs, jobs = [], []
    for run in raw_runs:
        manifest = run["manifest"] or {}
        result = manifest.get("result") or {}
        source = manifest.get("source") or manifest.get("request", {}).get("source", "qbcc")
        projected = job_projection({"job_id": run["run_id"], "run_id": run["run_id"], "source": source,
            "state": manifest.get("phase", run["state"]), "reason_codes": manifest.get("reason_codes", []),
            "result": manifest.get("result"), "started_at": run["started_at"], "finished_at": run["finished_at"]})
        if manifest.get("kind") in {"qbcc_live_job", "abr_live_job"}:
            jobs.append(projected)
        runs.append(
            {
                "run_id": run["run_id"],
                "source": source,
                "status": run["state"],
                "started_at": run["started_at"],
                "selected": result.get("counts", {}).get("selected"),
                "reports": None,
                "phase": projected["phase"],
                "result": projected["result"],
                "error_code": projected["error_code"],
                "reason_codes": projected["reason_codes"],
            }
        )
    from abr_engine.live.abr import admission_reasons as abr_admission_reasons

    abr_reasons = abr_admission_reasons(conn, service.settings, now)
    sources = []
    for source in ("qbcc", "abr"):
        row = (
            conn.execute(
                "SELECT c.*,s.manifest FROM source_cursor c LEFT JOIN source_snapshot s USING(snapshot_id) "
                "WHERE c.source=%s",
                (source,),
            ).fetchone()
            or {}
        )
        manifest = row.get("manifest") or {}
        capability = "abr" if source == "abr" else "collection"
        source_reasons = abr_reasons if source == "abr" else gate_reasons(conn, service.settings, capability, now)
        sources.append(
            {
                "source": source,
                "capability": capability,
                "can_run": worker_available and not source_reasons,
                "reason_codes": source_reasons,
                "status": "accepted" if row.get("snapshot_id") else "not_collected",
                "last_success_at": row.get("last_success_at"),
                "source_published_at": manifest.get("source_published_at") or manifest.get("publisher_timestamp")
                or manifest.get("publisher_modified_at"),
                "publisher_extract_time": manifest.get("publisher_extract_time"),
                "record_count": manifest.get("record_count"),
                "baseline": manifest.get("baseline"),
                "classification": manifest.get("classification"),
            }
        )
    setup = [
        {
            "id": "engine",
            "label": "Australian engine",
            "status": "connected",
            "detail": "Connected to the actual private database. No demonstration businesses are added.",
        }
    ]
    website_policy = website_collection_policy(conn, service.settings, now)
    for capability, label in [
        ("collection", "Business source collection"),
        ("website_collection", "Website contact collection"),
        ("crm", "GoHighLevel hand-off"),
        ("abr", "Broader ABR discovery"),
    ]:
        reasons = gate_reasons(conn, service.settings, capability, now)
        if capability == "website_collection":
            reasons = website_policy["reason_codes"]
        elif capability == "crm":
            reasons = crm_reasons
        elif capability == "abr":
            reasons = abr_reasons
        setup.append(
            {
                "id": capability,
                "label": label,
                "status": "blocked" if reasons else "approved",
                "detail": "Required evidence: " + ", ".join(reasons)
                if reasons
                else "Phone numbers only, from manually reviewed own-business websites, for internal research."
                if capability == "website_collection"
                else "Complete ABR register observations only. The first import is a baseline; classification and lead qualification remain disabled."
                if capability == "abr"
                else "Current capability evidence is recorded.",
            }
        )
    setup.append(
        {
            "id": "worker",
            "label": "Source run worker",
            "status": "connected" if worker_available else "blocked",
            "detail": "Uses the same approved source pipeline as the server schedule."
            if worker_available
            else "Source run worker is not configured.",
        }
    )
    total = conn.execute(
        "SELECT count(*) AS n FROM lead_entity l JOIN business_group b USING(group_id) WHERE b.merged_into_group_id IS NULL"
    ).fetchone()["n"]
    selected = conn.execute(
        "SELECT count(*) AS n FROM worklist_row WHERE worklist_id=(SELECT worklist_id FROM worklist ORDER BY week DESC LIMIT 1)"
    ).fetchone()["n"]
    review = conn.execute(
        "SELECT count(DISTINCT lead_id) AS n FROM candidate_queue WHERE state IN ('needs_review','pending_enrichment')"
    ).fetchone()["n"]
    month = now.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m")
    budget = conn.execute("SELECT cap,frozen FROM budget_month WHERE month=%s", (month,)).fetchone()
    service.audit(conn, actor.actor_id, "dashboard_read", "workspace", {"record_count": len(leads)})
    return json_safe(
        {
            "mode": service.settings.mode,
            "outreach": "disabled",
            "website_collection_policy": website_policy,
            "settings": settings,
            "scopes": sorted(actor.scopes),
            "run_enabled": worker_available,
            "worklist_csv": "/api/abn-lead-gen/worklist.csv" if selected else None,
            "summary": {
                "total_leads": total,
                "selected": selected,
                "needs_review": review,
                "last_run_at": raw_runs[0]["started_at"] if raw_runs else None,
            },
            "leads": leads,
            "runs": runs,
            "sources": sources,
            "setup": setup,
            "budget": {
                "effective_cap_micro_aud": min(
                    settings["monthly_cap_micro_aud"],
                    budget["cap"] if budget else settings["monthly_cap_micro_aud"],
                ),
                "frozen": bool(budget and budget["frozen"]),
            },
            "active_job": next((job for job in jobs if job["state"] in {"queued", "running"}), None),
            "latest_job": jobs[0] if jobs else None,
            "operational_notices": [
                {
                    "code": "LATEST_RECORDS_LIMIT",
                    "count": total - len(leads),
                    "message": "The dashboard shows the 200 most recent businesses.",
                }
            ]
            if total > len(leads)
            else [],
        }
    )
