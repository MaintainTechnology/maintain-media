"""Minimise profiles; keep restriction identity and separately justified encrypted evidence.

Restore reconciliation accepts a separately preserved authenticated latest restriction ledger.
An old backup alone cannot prove that all more recent opt-outs have been replayed.
"""

import hashlib
import json
import re
from calendar import monthrange
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, json_safe

_RESTORE_RECONCILING = ContextVar("abr_restore_reconciling", default=False)


def _execute_gate(conn, service, *, now=None, restoring=False):
    """Collection withdrawal cannot veto separately approved finite deletion."""
    if service.settings.mode == "fixture":
        return
    if not service.settings.capabilities.get("retention"):
        raise DomainError("RETENTION_POLICY_RELEASE_PENDING", 403)
    from abr_engine.compliance.policy import gate_reasons
    from abr_engine.ingest.qbcc_review import _configured
    _configured(service.settings, collection=False)
    if not service.keys.path or not service.keys.wrapping_key:
        raise DomainError("MANAGED_KEY_STORE_REQUIRED", 403)
    service.authority(conn)
    current = service.now(conn)
    if now is not None and (now.tzinfo is None or now > current + timedelta(seconds=1)):
        raise DomainError("RETENTION_FUTURE_TIME_FORBIDDEN", 403)
    reasons = gate_reasons(conn, service.settings, "retention", current)
    if reasons:
        raise DomainError(reasons[0], 403)
    policy = service.current_policy(conn)
    retention = policy["settings"].get("retention", {}) if policy else {}
    if (not policy or policy["scope"] != service.settings.mode or policy["state"] != "approved"
        or not policy["approved_at"] <= current < policy["expires_at"]
        or not str(policy["evidence_ref"]).strip() or not str(policy["actor_id"]).strip()
        or retention.get("approved") is not True or retention.get("schedule_version") != "abr-v4-defaults"
        or not isinstance(retention.get("evidence_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", retention["evidence_sha256"])):
        raise DomainError("RETENTION_POLICY_RELEASE_PENDING", 403)
    flags = {row["name"]: row["value"] for row in conn.execute("SELECT name,value FROM system_state WHERE name IN ('restore_quarantine','key_compromised')")}
    if service.keys.compromised or flags.get("key_compromised"):
        raise DomainError("AUTHORITY_QUARANTINED", 503)
    if flags.get("restore_quarantine") and not ((restoring or _RESTORE_RECONCILING.get()) and retention.get("restore_enabled") is True):
        raise DomainError("AUTHORITY_QUARANTINED", 503)


def _months(value, count):
    year, month = divmod(value.year * 12 + value.month - 1 + count, 12)
    return value.replace(year=year, month=month + 1, day=min(value.day, monthrange(year, month + 1)[1]))


def retention_deadline(kind: str, created_at: datetime) -> datetime:
    if created_at.tzinfo is None:
        raise DomainError("RETENTION_TIME_INVALID")
    days = {
        "raw": 30,
        "raw_source": 30,
        "snapshot": 90,
        "full_event": 90,
        "page": 90,
        "report": 90,
        "manifest": 90,
        "backup": 35,
        "orphan": 7,
        "profile": 180,
        "suppressed_profile": 30,
    }
    if kind in days:
        return created_at + timedelta(days=days[kind])
    if kind in {"event", "metric"}:
        return _months(created_at, 24)
    if kind == "selected_evidence":
        return _months(created_at, 84)
    raise DomainError("RETENTION_CLASS_UNKNOWN")


def _held(conn, kind, identifier):
    return (
        conn.execute(
            "SELECT 1 FROM retention_hold WHERE object_type=%s AND object_id=%s", (kind, str(identifier))
        ).fetchone()
        is not None
    )


def _evidence(conn, service, lead_id, contacts):
    group_id = service.lead(conn, lead_id)["group_id"]
    family = service.group_family(conn, group_id)
    evidence = {
        "merges": conn.execute("SELECT * FROM group_merge WHERE (source_group_id=ANY(%s) OR target_group_id=ANY(%s)) AND evidence_encrypted IS NOT NULL", (family, family)).fetchall(),
        "contacts": contacts,
        "provenance": conn.execute(
            "SELECT * FROM collection_provenance WHERE lead_id=%s", (lead_id,)
        ).fetchall(),
        "identity": conn.execute("SELECT * FROM domain_identity WHERE lead_id=%s", (lead_id,)).fetchall(),
        "licence": conn.execute("SELECT * FROM licence_review WHERE lead_id=%s", (lead_id,)).fetchall(),
        "qbcc_source_reviews": conn.execute("SELECT * FROM qbcc_source_review WHERE lead_id=%s", (lead_id,)).fetchall(),
        "basis": conn.execute(
            "SELECT b.* FROM contact_basis b JOIN contact_record c USING(contact_id) WHERE c.lead_id=%s",
            (lead_id,),
        ).fetchall(),
        "relevance": conn.execute(
            "SELECT r.* FROM relevance_assessment r JOIN contact_record c USING(contact_id) WHERE c.lead_id=%s",
            (lead_id,),
        ).fetchall(),
        "actions": conn.execute("SELECT * FROM action_intent WHERE lead_id=%s", (lead_id,)).fetchall(),
        "outcomes": conn.execute(
            "SELECT o.* FROM outcome_event o JOIN worklist_row w USING(row_id) WHERE w.lead_id=%s", (lead_id,)
        ).fetchall(),
    }
    tokens = {
        token
        for c in contacts
        if c["channel"] != "email"
        for _, token in service.keys.matches("phone", service.keys.decrypt(c["encrypted_value"]))
    }
    evidence["washes"] = conn.execute(
        "SELECT * FROM dnc_wash WHERE endpoint_token=ANY(%s)", (list(tokens),)
    ).fetchall()
    moments: list[datetime] = []
    for rows in evidence.values():
        for row in rows:
            moments.extend(
                value
                for key, value in row.items()
                if key
                in {"assessed_at", "reviewed_at", "checked_at", "occurred_at", "created_at", "collected_at"}
                and isinstance(value, datetime)
            )
            if row.get("decision") and row["decision"].get("checked_at"):
                moments.append(datetime.fromisoformat(row["decision"]["checked_at"]))
    return evidence, max(moments) if moments else None


def preview(conn, service, now):
    service.authority(conn)
    if now.tzinfo is None:
        raise DomainError("RETENTION_TIME_INVALID")
    return conn.execute(
        "SELECT DISTINCT l.lead_id,l.group_id FROM lead_entity l LEFT JOIN deletion_job d USING(group_id) "
        "WHERE l.last_qualifying_at<=%s OR (d.requested_at<=%s AND d.primary_done_at IS NULL)",
        (now - timedelta(days=180), now - timedelta(days=30)),
    ).fetchall()


def _profile_held(conn, group_id):
    return _held(conn, "group", group_id) or bool(conn.execute("""SELECT 1 FROM retention_hold h WHERE
      (h.object_type='provenance' AND h.object_id IN(SELECT p.provenance_id::text FROM collection_provenance p JOIN lead_entity l USING(lead_id) WHERE l.group_id=%s))
      OR (h.object_type='contact' AND h.object_id IN(SELECT c.contact_id::text FROM contact_record c JOIN lead_entity l USING(lead_id) WHERE l.group_id=%s))
      OR (h.object_type='enrichment_operation' AND h.object_id IN(SELECT o.operation_id::text FROM enrichment_operation o JOIN enrichment_attempt a USING(attempt_id) JOIN lead_entity l USING(lead_id) WHERE l.group_id=%s))
      OR (h.object_type='qbcc_review' AND h.object_id IN(SELECT r.review_id::text FROM qbcc_source_review r JOIN lead_entity l USING(lead_id) WHERE l.group_id=%s))
      LIMIT 1""", (group_id,)*4).fetchone())


def erase_profile(conn, service, group_id, *, actor="compliance", now=None):
    _execute_gate(conn, service, now=now)
    service.authority(conn)
    now = now or service.now(conn)
    if now.tzinfo is None:
        raise DomainError("RETENTION_TIME_INVALID")
    if _profile_held(conn, group_id):
        raise DomainError("SCOPED_RETENTION_HOLD", 409)
    leads = conn.execute("SELECT * FROM lead_entity WHERE group_id=%s", (group_id,)).fetchall()
    for lead in leads:
        lead_id = lead["lead_id"]
        from abr_engine.ops.pilot_facts import retain_profile_metrics
        retain_profile_metrics(conn, service, lead_id, now=now)
        service.invalidate(conn, lead_id)
        contacts = conn.execute("SELECT * FROM contact_record WHERE lead_id=%s", (lead_id,)).fetchall()
        selected = conn.execute("SELECT 1 FROM worklist_row WHERE lead_id=%s", (lead_id,)).fetchone()
        # Archive only selected contact/basis/action evidence with a distinct restricted purpose.
        if selected:
            evidence, last_relevant = _evidence(conn, service, lead_id, contacts)
            if last_relevant and retention_deadline("selected_evidence", last_relevant) > now:
                encrypted = service.keys.encrypt(json.dumps(json_safe(evidence)))
                conn.execute(
                    "INSERT INTO restricted_evidence_archive(archive_id,group_id,purpose,encrypted_payload,retained_until) VALUES(%s,%s,%s,%s,%s)",
                    (
                        uuid4(),
                        group_id,
                        "Selected contact and permission defence; fixture policy pending live approval",
                        encrypted,
                        retention_deadline("selected_evidence", last_relevant),
                    ),
                )
        conn.execute("SET LOCAL abr.retention_delete='on'")
        conn.execute("SET CONSTRAINTS ALL DEFERRED")
        conn.execute("DELETE FROM action_intent WHERE lead_id=%s", (lead_id,))
        conn.execute(
            "DELETE FROM relevance_assessment WHERE contact_id IN(SELECT contact_id FROM contact_record WHERE lead_id=%s)",
            (lead_id,),
        )
        conn.execute(
            "DELETE FROM contact_basis WHERE contact_id IN(SELECT contact_id FROM contact_record WHERE lead_id=%s)",
            (lead_id,),
        )
        conn.execute("DELETE FROM collection_provenance WHERE lead_id=%s", (lead_id,))
        conn.execute("DELETE FROM contact_record WHERE lead_id=%s", (lead_id,))
        conn.execute("DELETE FROM domain_identity WHERE lead_id=%s", (lead_id,))
        conn.execute("DELETE FROM licence_review WHERE lead_id=%s", (lead_id,))
        conn.execute("DELETE FROM qbcc_source_review WHERE lead_id=%s", (lead_id,))
        conn.execute(
            "DELETE FROM outcome_event WHERE row_id IN(SELECT row_id FROM worklist_row WHERE lead_id=%s)",
            (lead_id,),
        )
        conn.execute("DELETE FROM crm_outbox WHERE lead_id=%s", (lead_id,))
        conn.execute("UPDATE operator_activity SET lead_id=NULL WHERE lead_id=%s", (lead_id,))
        conn.execute("DELETE FROM worklist_row WHERE lead_id=%s", (lead_id,))
        conn.execute("UPDATE enrichment_operation SET encrypted_result=NULL WHERE attempt_id IN(SELECT attempt_id FROM enrichment_attempt WHERE lead_id=%s)", (lead_id,))
        conn.execute("UPDATE enrichment_attempt SET lead_id=NULL,candidate_id=NULL,erased_at=%s,lease_owner=NULL,lease_until=NULL WHERE lead_id=%s", (now, lead_id))
        conn.execute("DELETE FROM candidate_queue WHERE lead_id=%s", (lead_id,))
        conn.execute("DELETE FROM lead_entity WHERE lead_id=%s", (lead_id,))
    conn.execute("DELETE FROM lead_source_link WHERE group_id=%s", (group_id,))
    # External identity remains until verified external deletion; job never falsely says complete.
    conn.execute(
        "UPDATE deletion_job SET state='primary_complete',primary_done_at=%s,backup_expiry_at=%s WHERE group_id=%s AND primary_done_at IS NULL",
        (now, now + timedelta(days=35), group_id),
    )
    conn.execute("SET LOCAL abr.retention_delete='off'")
    service.audit(conn, actor, "profile_erased", group_id, {"profiles": len(leads)})
    return {"group_id": group_id, "state": "primary_complete", "external_and_backup": "pending"}


def retention_run(conn, service, *, now, execute=False):
    rows = preview(conn, service, now)
    if not execute:
        return {
            "status": "preview",
            "due_groups": [str(r["group_id"]) for r in rows],
            "artifacts": artifact_retention(conn, service, now=now, execute=False),
            "database_evidence": minimise_database_evidence(conn, service, now=now, execute=False),
        }
    _execute_gate(conn, service, now=now)
    results, held = [], []
    for row in rows:
        if _profile_held(conn, row["group_id"]):
            held.append(str(row["group_id"]))
        else:
            results.append(erase_profile(conn, service, row["group_id"], now=now))
    conn.execute(
        "DELETE FROM restricted_evidence_archive WHERE retained_until<=%s AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE (h.object_type='group' AND h.object_id=restricted_evidence_archive.group_id::text) OR (h.object_type='archive' AND h.object_id=restricted_evidence_archive.archive_id::text))",
        (now,),
    )
    artifacts = artifact_retention(conn, service, now=now, execute=True)
    database_evidence = minimise_database_evidence(conn, service, now=now, execute=True)
    return {
        "status": "complete_with_holds"
        if held or any(a["state"] == "held" for a in artifacts)
        else "primary_retention_complete",
        "profiles": results,
        "held_groups": held,
        "artifacts": artifacts,
        "database_evidence": database_evidence,
        "external_and_backups": "separate_receipts_required",
    }


def minimise_database_evidence(conn, service, *, now, execute=False):
    """Finite ordinary captures and full source events; metrics contain no identity."""
    service.authority(conn)
    if execute:
        _execute_gate(conn, service, now=now)
    from abr_engine.ops.pilot_facts import expire_metrics
    pilot_metrics = expire_metrics(conn, now=now, execute=execute)
    page_predicate = """p.capture_erased_at IS NULL AND p.collected_at<=%s
      AND NOT EXISTS(SELECT 1 FROM worklist_row w WHERE w.decision->>'contact_id'=p.contact_id::text)
      AND NOT EXISTS(SELECT 1 FROM action_intent a WHERE a.contact_id=p.contact_id AND a.state='consumed')
      AND NOT EXISTS(SELECT 1 FROM retention_hold h JOIN lead_entity l ON l.lead_id=p.lead_id
        WHERE (h.object_type='group' AND h.object_id=l.group_id::text)
           OR (h.object_type='provenance' AND h.object_id=p.provenance_id::text))"""
    cutoff = now - timedelta(days=90)
    qbcc_review_predicate = """r.created_at<=%s
      AND NOT EXISTS(SELECT 1 FROM worklist_row w WHERE w.lead_id=r.lead_id)
      AND NOT EXISTS(SELECT 1 FROM action_intent a WHERE a.lead_id=r.lead_id AND a.state='consumed')
      AND NOT EXISTS(SELECT 1 FROM retention_hold h LEFT JOIN lead_entity l ON l.lead_id=r.lead_id WHERE
        (h.object_type='qbcc_review' AND h.object_id=r.review_id::text)
        OR (h.object_type='snapshot' AND h.object_id=r.snapshot_id::text)
        OR (h.object_type='group' AND h.object_id=l.group_id::text))"""
    qbcc_reviews = conn.execute("SELECT count(*) n FROM qbcc_source_review r WHERE " + qbcc_review_predicate, (cutoff,)).fetchone()["n"]
    if execute:
        conn.execute("SET LOCAL abr.retention_delete='on'")
        conn.execute("DELETE FROM qbcc_source_review r WHERE " + qbcc_review_predicate, (cutoff,))
        conn.execute("SET LOCAL abr.retention_delete='off'")
    cost_hold = "NOT EXISTS(SELECT 1 FROM retention_hold h WHERE h.object_type='cost_statement' AND h.object_id=c.statement_id::text)"
    cost_receipts = conn.execute("SELECT count(*) n FROM cost_statement c WHERE encrypted_evidence IS NOT NULL AND imported_at<=%s AND " + cost_hold, (cutoff,)).fetchone()["n"]
    cost_metrics = conn.execute("SELECT count(*) n FROM cost_statement c WHERE period_end<=%s AND " + cost_hold, (_months(now, -24),)).fetchone()["n"]
    if execute:
        conn.execute("SET LOCAL abr.retention_delete='on'")
        conn.execute("UPDATE cost_statement c SET encrypted_evidence=NULL,evidence_erased_at=%s WHERE encrypted_evidence IS NOT NULL AND imported_at<=%s AND " + cost_hold, (now, cutoff))
        conn.execute("DELETE FROM cost_statement c WHERE period_end<=%s AND " + cost_hold, (_months(now, -24),))
        conn.execute("SET LOCAL abr.retention_delete='off'")
    merge_predicate = """m.evidence_encrypted IS NOT NULL AND m.reviewed_at<=%s
      AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE
        (h.object_type='merge' AND h.object_id=m.merge_id::text)
        OR (h.object_type='group' AND h.object_id IN(m.source_group_id::text,m.target_group_id::text)))"""
    merges = conn.execute("SELECT count(*) n FROM group_merge m WHERE " + merge_predicate, (cutoff,)).fetchone()["n"]
    if execute:
        conn.execute("SET LOCAL abr.retention_delete='on'")
        conn.execute("UPDATE group_merge m SET evidence_encrypted=NULL,evidence_erased_at=%s WHERE " + merge_predicate, (now, cutoff))
        conn.execute("SET LOCAL abr.retention_delete='off'")
    operational_counts = {}
    operational_queries = {
        "observations": ("ops_observation", "observed_at", "o.run_id", "o.observation_id", "observation"),
        "mock_deliveries": ("ops_mock_delivery", "delivered_at", "(SELECT run_id FROM alarm_outbox a WHERE a.alarm_id=o.alarm_id)", "o.alarm_id", "alarm"),
    }
    for label, (table, timestamp, run_ref, object_ref, kind) in operational_queries.items():
        operational_predicate = f"o.{timestamp}<=%s AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE (h.object_type='run' AND h.object_id=({run_ref})::text) OR (h.object_type=%s AND h.object_id={object_ref}::text))"
        operational_counts[label] = conn.execute(f"SELECT count(*) AS n FROM {table} o WHERE " + operational_predicate, (cutoff, kind)).fetchone()["n"]
        if execute:
            conn.execute(f"DELETE FROM {table} o WHERE " + operational_predicate, (cutoff, kind))
    operation_predicate = """o.encrypted_result IS NOT NULL AND COALESCE(o.completed_at,a.started_at)<=%s
      AND NOT EXISTS(SELECT 1 FROM retention_hold h LEFT JOIN lead_entity l ON l.lead_id=a.lead_id
        WHERE (h.object_type='group' AND h.object_id=l.group_id::text)
           OR (h.object_type='enrichment_operation' AND h.object_id=o.operation_id::text))"""
    operations = conn.execute("SELECT count(*) AS n FROM enrichment_operation o JOIN enrichment_attempt a USING(attempt_id) WHERE " + operation_predicate, (cutoff,)).fetchone()["n"]
    if execute:
        conn.execute("UPDATE enrichment_operation o SET encrypted_result=NULL FROM enrichment_attempt a WHERE a.attempt_id=o.attempt_id AND " + operation_predicate, (cutoff,))
    pages = conn.execute(
        "SELECT count(*) AS n FROM collection_provenance p WHERE " + page_predicate, (cutoff,)
    ).fetchone()["n"]
    if execute:
        conn.execute("SET LOCAL abr.retention_delete='on'")
        conn.execute(
            "UPDATE collection_provenance p SET encrypted_capture=NULL,encrypted_excerpt=NULL,capture_erased_at=%s WHERE "
            + page_predicate,
            (now, cutoff),
        )
        conn.execute("SET LOCAL abr.retention_delete='off'")
    event_counts = {}
    allowed_types = [
        "abn_new",
        "abn_cancelled",
        "abn_reactivated",
        "gst_registered",
        "gst_cancelled",
        "name_changed",
        "abn_disappeared",
        "icp_backlog",
        "new",
        "category_changed",
    ]
    for source, table in (("abr", "abr_event"), ("qbcc", "qbcc_event")):
        predicate = sql.SQL("""e.detected_at<=%s AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE
          (h.object_type='source' AND h.object_id=%s) OR (h.object_type='snapshot' AND h.object_id=e.snapshot_id::text)
          OR (h.object_type='event' AND h.object_id=e.event_id::text))""")
        event_counts[source] = conn.execute(
            sql.SQL("SELECT count(*) AS n FROM {} e WHERE ").format(sql.Identifier(table)) + predicate,
            (cutoff, source),
        ).fetchone()["n"]
        if execute:
            # Removal and aggregate addition are one statement/transaction. Retrying adds
            # no counts because only freshly deleted rows feed the grouped projection.
            conn.execute(
                sql.SQL("""WITH removed AS (DELETE FROM {} e WHERE """).format(sql.Identifier(table))
                + predicate
                + sql.SQL("""
              RETURNING event_type,detected_at), grouped AS (
                SELECT (detected_at AT TIME ZONE 'UTC')::date observed_day,
                       CASE WHEN event_type=ANY(%s) THEN event_type ELSE 'unknown' END event_type,count(*) event_count
                FROM removed GROUP BY 1,2)
              INSERT INTO retained_event_metric(source,observed_day,event_type,event_count,retained_until)
              SELECT %s,observed_day,event_type,event_count,(observed_day::timestamp+interval '24 months') AT TIME ZONE 'UTC' FROM grouped
              ON CONFLICT(source,observed_day,event_type) DO UPDATE SET event_count=retained_event_metric.event_count+EXCLUDED.event_count"""),
                (cutoff, source, allowed_types, source),
            )
    expired_metrics = conn.execute(
        "SELECT count(*) AS n FROM retained_event_metric WHERE retained_until<=%s", (now,)
    ).fetchone()["n"]
    if execute:
        conn.execute(
            "DELETE FROM retained_event_metric WHERE retained_until<=%s AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE h.object_type='metric' AND h.object_id=retained_event_metric.source||':'||retained_event_metric.observed_day::text||':'||retained_event_metric.event_type)",
            (now,),
        )
    return {
        "page_bodies": pages,
        "qbcc_source_reviews": qbcc_reviews,
        "expired_pilot_metrics": pilot_metrics,
        "enrichment_results": operations,
        "merge_evidence": merges,
        "cost_receipts": cost_receipts,
        "expired_cost_metrics": cost_metrics,
        "operational_records": operational_counts,
        "full_source_events": event_counts,
        "expired_metrics": expired_metrics,
        "state": "minimised" if execute else "preview",
    }


def artifact_retention(conn, service, *, now, execute=False):
    """Delete only explicitly classified, verified manifest-owned single files."""
    service.authority(conn)
    if execute:
        _execute_gate(conn, service, now=now)
    from abr_engine.ops.promotion import source_lock_key
    from abr_engine.pipeline import safe_root

    root = safe_root(service.settings)
    schema = conn.execute("SELECT current_schema() AS schema").fetchone()["schema"]
    rows = conn.execute(
        "SELECT a.*,r.state AS run_state FROM artifact_manifest a JOIN pipeline_run r USING(run_id) WHERE a.state<>'deleted' ORDER BY a.created_at,a.artifact_id"
    ).fetchall()
    results = []
    for row in rows:
        item = {"artifact_id": str(row["artifact_id"]), "state": "retained"}
        try:
            orphan = row["state"] in {"writing", "orphan"} or (
                row["snapshot_id"] is None
                and row["state"] == "verified"
                and row["run_state"] in {"failed", "held"}
            )
            kind = "orphan" if orphan else row.get("artifact_class")
            due = retention_deadline(kind, row["created_at"])
            item["due_at"] = due.isoformat()
            if now < due:
                continue
            if (
                row["run_state"] == "running"
                or _held(conn, "artifact", row["artifact_id"])
                or (row["snapshot_id"] and _held(conn, "snapshot", row["snapshot_id"]))
            ):
                raise DomainError("ARTIFACT_ACTIVE_OR_HELD")
            if not row.get("local_path"):
                raise DomainError("ARTIFACT_LOCATION_UNAVAILABLE")
            if not row["object_key"].startswith(f"staging/{row['source']}/{row['run_id']}/"):
                raise DomainError("ARTIFACT_OWNERSHIP_MISMATCH")
            path = Path(row["local_path"])
            if not path.is_absolute() or not path.resolve().is_relative_to(root) or path.resolve() == root:
                raise DomainError("ARTIFACT_OUTSIDE_RETENTION_ROOT")
            path = path.resolve()
            for other in rows:
                if other["artifact_id"] == row["artifact_id"] or not other.get("local_path"):
                    continue
                if Path(other["local_path"]).resolve() == path and (
                    other["run_state"] == "running"
                    or now < retention_deadline(other.get("artifact_class"), other["created_at"])
                ):
                    raise DomainError("ARTIFACT_STILL_REFERENCED")
            if path.exists():
                if not path.is_file() or path.stat().st_size != row["byte_count"]:
                    raise DomainError("ARTIFACT_SIZE_MISMATCH")
                checksum = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        checksum.update(chunk)
                if checksum.hexdigest() != row["content_digest"]:
                    raise DomainError("ARTIFACT_DIGEST_MISMATCH")
            if not execute:
                item["state"] = "due"
                continue
            if not conn.execute(
                "SELECT pg_try_advisory_xact_lock(%s) AS acquired", (source_lock_key(row["source"], schema),)
            ).fetchone()["acquired"]:
                raise DomainError("SOURCE_STAGE_LOCK_BUSY")
            conn.execute(
                "SELECT artifact_id FROM artifact_manifest WHERE artifact_id=%s FOR UPDATE",
                (row["artifact_id"],),
            )
            conn.execute(
                "UPDATE artifact_manifest SET state='deleting',deletion_reason='finite_retention' WHERE artifact_id=%s",
                (row["artifact_id"],),
            )
            if row["snapshot_id"] and row.get("artifact_class") == "snapshot":
                cleared = conn.execute(
                    "UPDATE source_cursor SET snapshot_id=NULL,version=version+1 WHERE snapshot_id=%s RETURNING source",
                    (row["snapshot_id"],),
                ).fetchall()
                for cursor in cleared:
                    conn.execute(
                        "INSERT INTO system_state(name,value) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                        (
                            "history_gap:" + cursor["source"],
                            Jsonb(
                                {
                                    "reason": "accepted_snapshot_retention_expired",
                                    "expired_at": now.isoformat(),
                                    "requires_baseline": True,
                                }
                            ),
                        ),
                    )
            path.unlink(missing_ok=True)
            conn.execute(
                "UPDATE artifact_manifest SET state='deleted' WHERE artifact_id=%s", (row["artifact_id"],)
            )
            item["state"] = "deleted"
        except (DomainError, OSError) as exc:
            item.update(
                state="held", reason=exc.code if isinstance(exc, DomainError) else "ARTIFACT_IO_FAILURE"
            )
        finally:
            results.append(item)
    return results


def export_ledger(conn, service, *, exported_at=None) -> str:
    service.authority(conn)
    payload = {
        "version": 1,
        "exported_at": (exported_at or service.now(conn)).isoformat(),
        "groups": conn.execute("SELECT * FROM business_group").fetchall(),
        "aliases": conn.execute("SELECT * FROM suppression_alias").fetchall(),
        "restrictions": conn.execute(
            "SELECT * FROM suppression_event ORDER BY committed_at,event_id"
        ).fetchall(),
        "deletions": conn.execute("SELECT * FROM deletion_job").fetchall(),
    }
    return service.keys.encrypt(json.dumps(json_safe(payload), sort_keys=True))


def restore_quarantine(conn):
    from abr_engine.db import lock

    lock(conn, "control-authority")
    conn.execute(
        "INSERT INTO system_state(name,value) VALUES('restore_quarantine','true') ON CONFLICT(name) DO UPDATE SET value='true'"
    )


def replay_ledger(conn, service, encrypted: str, *, expected_digest: str, latest_watermark: str):
    _execute_gate(conn, service, restoring=True)
    service.authority(conn)
    quarantined = conn.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()
    if not quarantined["value"]:
        raise DomainError("RESTORE_MUST_BE_QUARANTINED", 409)
    if hashlib.sha256(encrypted.encode()).hexdigest() != expected_digest:
        raise DomainError("LEDGER_DIGEST_MISMATCH")
    payload = json.loads(service.keys.decrypt(encrypted))
    if payload["version"] != 1 or payload["exported_at"] != latest_watermark:
        raise DomainError("LATEST_LEDGER_WATERMARK_REQUIRED")
    current_edges = {str(r["group_id"]): str(r["merged_into_group_id"]) if r["merged_into_group_id"] else None
                     for r in conn.execute("SELECT group_id,merged_into_group_id FROM business_group").fetchall()}
    edges = dict(current_edges)
    for group in payload["groups"]:
        key, target = str(group["group_id"]), group["merged_into_group_id"]
        if current_edges.get(key) and target != current_edges[key]:
            raise DomainError("RESTORE_LEDGER_CONFLICT", 409)
        edges[key] = target
    for start in edges:
        seen = set()
        cursor: str | None = start
        while cursor is not None:
            if cursor in seen or cursor not in edges:
                raise DomainError("RESTORE_LEDGER_CONFLICT", 409)
            seen.add(cursor)
            cursor = edges[cursor]
    # Dependency order and deferred group redirects preserve all minimal identity aliases.
    for group in payload["groups"]:
        conn.execute(
            "INSERT INTO business_group(group_id,restriction_revision) VALUES(%s,%s) ON CONFLICT(group_id) DO UPDATE SET restriction_revision=GREATEST(business_group.restriction_revision,EXCLUDED.restriction_revision)",
            (group["group_id"], group["restriction_revision"]),
        )
    for group in payload["groups"]:
        if group["merged_into_group_id"]:
            conn.execute(
                "UPDATE business_group SET merged_into_group_id=%s WHERE group_id=%s",
                (group["merged_into_group_id"], group["group_id"]),
            )
    for table, rows in (
        ("suppression_alias", payload["aliases"]),
        ("suppression_event", payload["restrictions"]),
        ("deletion_job", payload["deletions"]),
    ):
        for row in rows:
            keys = {
                "suppression_alias": ("alias_type", "key_version", "alias_token"),
                "suppression_event": ("event_id",),
                "deletion_job": ("job_id",),
            }[table]
            existing = conn.execute(
                sql.SQL("SELECT * FROM {} WHERE {}").format(
                    sql.Identifier(table),
                    sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in keys),
                ),
                tuple(row[k] for k in keys),
            ).fetchone()
            if existing and table != "deletion_job" and json_safe(existing) != row:
                raise DomainError("RESTORE_LEDGER_CONFLICT", 409)
            if existing and table == "deletion_job" and str(existing["group_id"]) != str(row["group_id"]):
                raise DomainError("RESTORE_LEDGER_CONFLICT", 409)
            columns = list(row)
            values = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in row.values()]
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
                sql.Identifier(table),
                sql.SQL(",").join(map(sql.Identifier, columns)),
                sql.SQL(",").join(sql.Placeholder() for _ in columns),
            )
            conn.execute(query, values)
    service.keys.validate_dependencies(conn)
    restore_token = _RESTORE_RECONCILING.set(True)
    try:
        for deleted in payload["deletions"]:
            if deleted["primary_done_at"]:
                erase_profile(conn, service, deleted["group_id"])
        for group in payload["groups"]:
            if service.restricted(conn, group["group_id"]):
                for lead in conn.execute(
                    "SELECT lead_id FROM lead_entity WHERE group_id=%s", (group["group_id"],)
                ).fetchall():
                    service.invalidate(conn, lead["lead_id"])
        overdue = retention_run(conn, service, now=service.now(conn), execute=True)
    finally:
        _RESTORE_RECONCILING.reset(restore_token)
    receipt_id = uuid4()
    conn.execute(
        "INSERT INTO restore_receipt VALUES(%s,%s,clock_timestamp(),'reconciled',%s)",
        (
            receipt_id,
            expected_digest,
            Jsonb(
                {
                    "watermark": latest_watermark,
                    "restriction_count": len(payload["restrictions"]),
                    "retention_status": overdue["status"],
                    "storage_backup_remote_release": "pending",
                }
            ),
        ),
    )
    # Intentionally stays quarantined: filesystem/remote deletion and independent release check follow.
    return {"restore_id": receipt_id, "state": "ledger_reconciled", "outbound": "quarantined"}
