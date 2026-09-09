"""Serializable enrichment transitions for use inside the durable worker transaction.

The caller must persist each returned state and provider receipt under the lead lease;
this module never invokes a provider or treats a budget hold as exhausted discovery.
"""

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb

from abr_engine.db import transaction
from abr_engine.enrich.budget import BudgetError, reserve, settle, upper_micro_aud
from abr_engine.qualify.policy import policy_metadata
from abr_engine.qualify.queue import score


@dataclass(frozen=True)
class Eligibility:
    tier: str
    state: str | None
    postcode: str | None
    suppressed: bool
    collection_approved: bool
    geography_conflicting: bool = False


@dataclass(frozen=True)
class AttemptState:
    attempt_id: str
    status: Literal["pending", "running", "complete", "exhausted", "blocked"] = "pending"
    completed_stages: tuple[str, ...] = ()
    receipts: tuple[tuple[str, str], ...] = ()
    finished_at: datetime | None = None
    next_eligible_at: datetime | None = None
    reason: str | None = None


def enrichment_block(candidate: Eligibility, previous: AttemptState | None, *, now: datetime) -> str | None:
    if now.tzinfo is None:
        raise ValueError("UTC_REQUIRED")
    if candidate.suppressed:
        return "SUPPRESSED"
    if candidate.tier not in {"A", "B"}:
        return "TIER_INELIGIBLE"
    if (
        candidate.geography_conflicting
        or not candidate.postcode
        or len(candidate.postcode) != 4
        or not candidate.postcode.isascii()
        or not candidate.postcode.isdigit()
    ):
        return "GEOGRAPHY_UNKNOWN"
    if candidate.state != "QLD" and not (candidate.state == "NSW" and "2450" <= candidate.postcode <= "2490"):
        return "GEOGRAPHY_INELIGIBLE"
    if not candidate.collection_approved:
        return "COLLECTION_POLICY_BLOCKED"
    if previous and previous.next_eligible_at and now < previous.next_eligible_at:
        return "ENRICHMENT_COOLDOWN"
    return None


def stage_needed(state: AttemptState, stage: str) -> bool:
    return state.status not in {"complete", "exhausted"} and stage not in state.completed_stages


def complete_stage(state: AttemptState, stage: str, receipt_id: str) -> AttemptState:
    if not stage or not receipt_id:
        raise ValueError("STAGE_RECEIPT_REQUIRED")
    existing = dict(state.receipts)
    if stage in existing:
        if existing[stage] != receipt_id:
            raise ValueError("STAGE_RECEIPT_CONFLICT")
        return state
    if state.status in {"complete", "exhausted"}:
        raise ValueError("ATTEMPT_CLOSED")
    return replace(
        state,
        status="running",
        completed_stages=state.completed_stages + (stage,),
        receipts=state.receipts + ((stage, receipt_id),),
        reason=None,
    )


def interrupt(state: AttemptState, reason: str) -> AttemptState:
    if reason not in {"BUDGET_STOP", "QUOTA_STOP", "BILLING_UNCERTAIN"}:
        raise ValueError("INTERRUPTION_REASON_INVALID")
    if state.status in {"complete", "exhausted"}:
        raise ValueError("ATTEMPT_CLOSED")
    return replace(state, status="blocked", reason=reason)


def finish(state: AttemptState, *, now: datetime, exhausted: bool = False) -> AttemptState:
    if now.tzinfo is None:
        raise ValueError("UTC_REQUIRED")
    if state.status in {"complete", "exhausted"}:
        return state
    if state.reason in {"BUDGET_STOP", "QUOTA_STOP", "BILLING_UNCERTAIN"}:
        raise ValueError("INTERRUPTED_NOT_EXHAUSTED")
    return replace(
        state,
        status="exhausted" if exhausted else "complete",
        finished_at=now,
        next_eligible_at=now + timedelta(days=90),
        reason=None,
    )


STAGES = ("lookup", "crawl", "verify")


@dataclass(frozen=True)
class ProviderResult:
    """Transport facts only. No result grants contact permission."""

    state: Literal["complete", "exhausted", "quota", "uncertain"]
    actual: int | None
    receipt: str | None
    payload: dict | None = None


def _allowed(conn, service, lead):
    quarantined = conn.execute(
        "SELECT 1 FROM system_state WHERE name IN ('restore_quarantine','key_compromised') AND value='true'::jsonb LIMIT 1"
    ).fetchone()
    if service.keys.compromised or quarantined:
        return "AUTHORITY_QUARANTINED"
    policy = service.current_policy(conn)
    now = service.now(conn)
    reason = enrichment_block(
        Eligibility(
            lead["tier"],
            lead["state"],
            lead["postcode"],
            bool(service.restricted(conn, lead["group_id"])),
            bool(
                policy
                and policy["scope"] == "synthetic"
                and policy["state"] == "approved"
                and policy["approved_at"] <= now < policy["expires_at"]
            ),
        ),
        None,
        now=now,
    )
    if reason:
        return reason
    if lead["lifecycle"] != "active" or service.canonical_group(conn, lead["group_id"]) != lead["group_id"]:
        return "LEAD_INACTIVE"
    return None


def _block(conn, attempt, owner, reason):
    conn.execute(
        "UPDATE enrichment_attempt SET state='blocked',reason=%s,lease_owner=NULL,lease_until=NULL "
        "WHERE attempt_id=%s AND lease_owner=%s",
        (reason, attempt, owner),
    )
    conn.execute(
        "UPDATE candidate_queue SET lease_owner=NULL,lease_until=NULL,stage_data=stage_data||%s "
        "WHERE candidate_id=(SELECT candidate_id FROM enrichment_attempt WHERE attempt_id=%s) AND lease_owner=%s",
        (Jsonb({"enrichment_reason": reason}), attempt, owner),
    )
    return {"status": "blocked", "reason": reason, "attempt_id": str(attempt)}


def heartbeat(settings, attempt_id, owner) -> bool:
    with transaction(settings) as conn:
        row = conn.execute(
            "UPDATE enrichment_attempt SET lease_until=clock_timestamp()+interval '120 seconds' "
            "WHERE attempt_id=%s AND lease_owner=%s AND lease_until>clock_timestamp() AND state='running' "
            "RETURNING candidate_id,lease_until",
            (attempt_id, owner),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE candidate_queue SET lease_until=%s WHERE candidate_id=%s AND lease_owner=%s",
            (row["lease_until"], row["candidate_id"], owner),
        )
        return True


def drain_one(settings, service, provider, *, candidate_id=None, apply_result=None, fault=None):
    """Run one durable fixture attempt. Providers implement tariff, perform and reconcile.

    perform/reconcile receive operation_id, stage, prior_results and heartbeat. They must
    enforce bounded timeouts and call heartbeat at most 30 seconds apart. A crashed or
    uncertain dispatch is reconciled under the same ID; it is never silently repurchased.
    apply_result runs under the current control authority after the final receipt settles.
    """
    if settings.mode != "fixture" or getattr(provider, "fixture_only", False) is not True:
        raise ValueError("LIVE_ENRICHMENT_GATES_PENDING")
    owner = uuid4()
    with transaction(settings) as conn:
        service.authority(conn)
        query = "SELECT q.* FROM candidate_queue q JOIN lead_entity l USING(lead_id) WHERE q.state='pending_enrichment' AND (q.next_attempt_at IS NULL OR q.next_attempt_at<=clock_timestamp())"
        args = []
        if candidate_id is not None:
            query += " AND q.candidate_id=%s"
            args.append(candidate_id)
        query += " AND (q.lease_until IS NULL OR q.lease_until<=clock_timestamp()) ORDER BY q.score DESC,q.first_qualified_at,q.candidate_id LIMIT 1 FOR UPDATE OF q SKIP LOCKED"
        candidate = conn.execute(query, args).fetchone()
        if not candidate:
            return {"status": "idle"}
        if candidate["first_qualified_at"] + timedelta(weeks=8) <= service.now(conn):
            conn.execute(
                "UPDATE candidate_queue SET state='deferred',deferred_at=clock_timestamp() WHERE candidate_id=%s",
                (candidate["candidate_id"],),
            )
            return {"status": "blocked", "reason": "QUEUE_EXPIRED"}
        lead = service.lead(conn, candidate["lead_id"])
        reason = _allowed(conn, service, lead)
        if reason:
            return {"status": "blocked", "reason": reason}
        family = service.group_family(conn, lead["group_id"])
        cached = conn.execute(
            "SELECT a.* FROM enrichment_attempt a "
            "WHERE a.group_id=ANY(%s) AND next_eligible_at>clock_timestamp() "
            "ORDER BY finished_at DESC LIMIT 1",
            (family,),
        ).fetchone()
        if cached:
            return {
                "status": "cached",
                "attempt_id": str(cached["attempt_id"]),
                "reason": "ENRICHMENT_COOLDOWN",
            }
        if conn.execute(
            "SELECT 1 FROM enrichment_attempt WHERE group_id=ANY(%s) AND state IN ('running','blocked') AND lead_id IS DISTINCT FROM %s LIMIT 1",
            (family, lead["lead_id"]),
        ).fetchone():
            return {"status": "blocked", "reason": "MERGED_ATTEMPT_RECONCILIATION_REQUIRED"}
        attempt = conn.execute(
            "SELECT * FROM enrichment_attempt WHERE lead_id=%s AND state IN ('running','blocked') FOR UPDATE",
            (lead["lead_id"],),
        ).fetchone()
        if attempt and attempt["lease_until"] and attempt["lease_until"] > service.now(conn):
            return {"status": "busy"}
        now = service.now(conn)
        if not attempt:
            attempt = conn.execute(
                "INSERT INTO enrichment_attempt(attempt_id,lead_id,candidate_id,group_id,state,started_at) "
                "VALUES(%s,%s,%s,%s,'running',%s) RETURNING *",
                (uuid4(), lead["lead_id"], candidate["candidate_id"], lead["group_id"], now),
            ).fetchone()
        assert attempt is not None
        attempt_id = attempt["attempt_id"]
        conn.execute(
            "UPDATE enrichment_attempt SET state='running',reason=NULL,lease_owner=%s,lease_until=%s WHERE attempt_id=%s",
            (owner, now + timedelta(seconds=120), attempt_id),
        )
        conn.execute(
            "UPDATE candidate_queue SET lease_owner=%s,lease_until=%s WHERE candidate_id=%s",
            (owner, now + timedelta(seconds=120), attempt["candidate_id"]),
        )

    for stage in STAGES:
        with transaction(settings) as conn:
            service.authority(conn, lead["lead_id"])
            current = conn.execute(
                "SELECT * FROM enrichment_attempt WHERE attempt_id=%s FOR UPDATE", (attempt_id,)
            ).fetchone()
            if not current or current["lease_owner"] != owner or current["lease_until"] <= service.now(conn):
                return {"status": "blocked", "reason": "LEASE_LOST"}
            reason = _allowed(conn, service, service.lead(conn, lead["lead_id"]))
            if reason:
                return _block(conn, attempt_id, owner, reason)
            operation = conn.execute(
                "SELECT * FROM enrichment_operation WHERE attempt_id=%s AND stage=%s", (attempt_id, stage)
            ).fetchone()
            if operation and operation["provider_version"] != provider.version:
                return _block(conn, attempt_id, owner, "PROVIDER_VERSION_CHANGED")
            if conn.execute(
                "SELECT 1 FROM enrichment_operation WHERE attempt_id=%s AND state='complete' AND encrypted_result IS NULL LIMIT 1",
                (attempt_id,),
            ).fetchone():
                return _block(conn, attempt_id, owner, "STAGE_EVIDENCE_EXPIRED")
            saved_result = (
                json.loads(service.keys.decrypt(operation["encrypted_result"]))
                if operation and operation["state"] == "complete"
                else {}
            )
            if (
                operation
                and operation["state"] == "complete"
                and stage != STAGES[-1]
                and saved_result.get("_worker_outcome") != "exhausted"
            ):
                continue
            prior = {
                r["stage"]: json.loads(service.keys.decrypt(r["encrypted_result"]))
                for r in conn.execute(
                    "SELECT * FROM enrichment_operation WHERE attempt_id=%s AND state='complete'",
                    (attempt_id,),
                )
            }
            if not operation:
                operation_id = uuid4()
                tariff = provider.tariff(stage, service.now(conn))
                try:
                    reservation = reserve(
                        conn,
                        operation_id=operation_id,
                        now=service.now(conn),
                        amount=upper_micro_aud(
                            tariff["native_upper_bound"], tariff["fx"], tariff["tax_rate"]
                        ),
                        tariff=tariff,
                        cap=settings.monthly_cap_micro_aud,
                    )
                except BudgetError as exc:
                    if str(exc) != "BUDGET_STOP":
                        raise
                    return _block(conn, attempt_id, owner, "BUDGET_STOP")
                operation = conn.execute(
                    "INSERT INTO enrichment_operation(operation_id,attempt_id,stage,provider_version,state,reservation_id) "
                    "VALUES(%s,%s,%s,%s,'reserved',%s) RETURNING *",
                    (operation_id, attempt_id, stage, provider.version, reservation["reservation_id"]),
                ).fetchone()
        assert operation is not None
        if fault:
            fault("after_reservation_commit")
        reconcile = operation["state"] in {"dispatched", "uncertain"}
        completed = operation["state"] == "complete"
        with transaction(settings) as conn:
            service.authority(conn, lead["lead_id"])
            current = conn.execute(
                "SELECT * FROM enrichment_attempt WHERE attempt_id=%s FOR UPDATE", (attempt_id,)
            ).fetchone()
            if not current or current["lease_owner"] != owner or current["lease_until"] <= service.now(conn):
                return {"status": "blocked", "reason": "LEASE_LOST"}
            reason = _allowed(conn, service, service.lead(conn, lead["lead_id"]))
            if reason:
                return _block(conn, attempt_id, owner, reason)
            # Dispatch intent is durable before crossing the provider boundary.
            conn.execute(
                "UPDATE enrichment_operation SET state='dispatched' WHERE operation_id=%s AND state='reserved'",
                (operation["operation_id"],),
            )
        try:
            if completed:
                with transaction(settings) as conn:
                    paid = conn.execute(
                        "SELECT actual FROM budget_reservation WHERE reservation_id=%s",
                        (operation["reservation_id"],),
                    ).fetchone()
                    assert paid is not None
                restored_payload = json.loads(service.keys.decrypt(operation["encrypted_result"]))
                result = ProviderResult(
                    restored_payload.pop("_worker_outcome", "complete"),
                    paid["actual"],
                    operation["receipt_ref"],
                    restored_payload,
                )
            else:
                call = provider.reconcile if reconcile else provider.perform
                result = call(
                    operation["operation_id"], stage, prior, lambda: heartbeat(settings, attempt_id, owner)
                )
        except Exception:  # noqa: BLE001 - transport failure cannot establish billing outcome
            result = ProviderResult("uncertain", None, None)
        if fault:
            fault("after_provider_response")
        with transaction(settings) as conn:
            service.authority(conn, lead["lead_id"])
            current = conn.execute(
                "SELECT * FROM enrichment_attempt WHERE attempt_id=%s FOR UPDATE", (attempt_id,)
            ).fetchone()
            if not current or current["lease_owner"] != owner or current["lease_until"] <= service.now(conn):
                return {"status": "blocked", "reason": "LEASE_LOST"}
            settled = settle(
                conn,
                operation["reservation_id"],
                None if result.state == "uncertain" else result.actual,
                result.receipt,
            )
            if settled["state"] != "settled" or result.state == "uncertain":
                conn.execute(
                    "UPDATE enrichment_operation SET state='uncertain' WHERE operation_id=%s",
                    (operation["operation_id"],),
                )
                return _block(conn, attempt_id, owner, "BILLING_UNCERTAIN")
            if result.state == "quota":
                conn.execute(
                    "UPDATE enrichment_operation SET state='uncertain' WHERE operation_id=%s",
                    (operation["operation_id"],),
                )
                return _block(conn, attempt_id, owner, "QUOTA_STOP")
            conn.execute(
                "UPDATE enrichment_operation SET state='complete',receipt_ref=%s,encrypted_result=%s,completed_at=clock_timestamp() WHERE operation_id=%s",
                (
                    result.receipt,
                    service.keys.encrypt(
                        json.dumps({**(result.payload or {}), "_worker_outcome": result.state})
                    ),
                    operation["operation_id"],
                ),
            )
            reason = _allowed(conn, service, service.lead(conn, lead["lead_id"]))
            if reason:
                return _block(conn, attempt_id, owner, reason)
            if result.state == "exhausted" or stage == STAGES[-1]:
                if result.state != "exhausted" and apply_result:
                    apply_result(conn, service, lead["lead_id"], {**prior, stage: result.payload or {}})
                final_lead = service.lead(conn, lead["lead_id"])
                contacts = conn.execute(
                    "WITH latest AS (SELECT DISTINCT ON(registrable_domain) * FROM domain_identity WHERE lead_id=%s ORDER BY registrable_domain,assessment_seq DESC) "
                    "SELECT c.* FROM contact_record c JOIN collection_provenance p ON p.provenance_id=c.first_provenance_id "
                    "JOIN latest i ON i.registrable_domain=p.registrable_domain WHERE c.lead_id=%s AND i.assessment='approved' AND i.expires_at>clock_timestamp()",
                    (lead["lead_id"], lead["lead_id"]),
                ).fetchall()
                identity = conn.execute(
                    "SELECT 1 FROM (SELECT DISTINCT ON(registrable_domain) * FROM domain_identity WHERE lead_id=%s ORDER BY registrable_domain,assessment_seq DESC) i WHERE assessment='approved' AND expires_at>clock_timestamp() LIMIT 1",
                    (lead["lead_id"],),
                ).fetchone()
                final_score = score(
                    source=final_lead["source"],
                    tier=final_lead["tier"],
                    geography=True,
                    company=final_lead["fields"].get("entity_class") == "company",
                    category=final_lead["fields"].get("financial_category"),
                    confidence=final_lead["fields"].get("classifier_confidence", "none"),
                    deliverable_email=any(
                        c["channel"] == "email"
                        and c["verification_status"] == "deliverable"
                        and c["verified_at"]
                        and c["verified_at"] > service.now(conn) - timedelta(days=90)
                        for c in contacts
                    ),
                    phone=any(c["channel"] in {"mobile", "landline"} for c in contacts),
                    website=bool(identity),
                )
                conn.execute(
                    "UPDATE lead_entity SET score=%s WHERE lead_id=%s", (final_score, lead["lead_id"])
                )
                conn.execute(
                    "UPDATE candidate_queue SET score=%s WHERE lead_id=%s", (final_score, lead["lead_id"])
                )
                now = service.now(conn)
                conn.execute(
                    "UPDATE enrichment_attempt SET state=%s,finished_at=%s,next_eligible_at=%s,lease_owner=NULL,lease_until=NULL WHERE attempt_id=%s",
                    (
                        "exhausted" if result.state == "exhausted" else "complete",
                        now,
                        now + timedelta(days=90),
                        attempt_id,
                    ),
                )
                conn.execute(
                    "UPDATE candidate_queue SET lease_owner=NULL,lease_until=NULL,last_attempt_at=%s,attempt_count=attempt_count+1,stage_data=stage_data||%s WHERE candidate_id=%s AND lease_owner=%s",
                    (
                        now,
                        Jsonb(
                            {
                                "enrichment_attempt_id": str(attempt_id),
                                "enrichment_complete": True,
                                **policy_metadata(),
                            }
                        ),
                        current["candidate_id"],
                        owner,
                    ),
                )
                return {
                    "status": "exhausted" if result.state == "exhausted" else "complete",
                    "attempt_id": str(attempt_id),
                }
    return {"status": "blocked", "reason": "RESULT_APPLICATION_PENDING"}


class SyntheticProvider:
    """Offline transport: no credentials, sockets, contact authority or charge."""

    fixture_only = True
    version = "synthetic-provider-v1"

    def tariff(self, stage, now):
        return {
            "version": self.version,
            "fx_date": now.date().isoformat(),
            "currency": "AUD",
            "native_upper_bound": "0",
            "fx": "1",
            "tax_rate": "0",
        }

    def perform(self, operation_id, stage, prior_results, heartbeat):
        if not heartbeat():
            raise ValueError("LEASE_LOST")
        return ProviderResult(
            "complete", 0, "synthetic:" + str(operation_id), {"synthetic": True, "stage": stage}
        )

    reconcile = perform
