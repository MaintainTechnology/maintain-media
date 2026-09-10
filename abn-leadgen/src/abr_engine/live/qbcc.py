"""Accept publisher snapshots, then qualify only individually reviewed licences.

Publisher status remains UNKNOWN in immutable source bytes. A reviewer decision
is separate evidence, bound to the current snapshot and exact semantic row hash.
No contact endpoint or outreach permission is manufactured by this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid5

import pyarrow.parquet as pq
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import gate_reasons
from abr_engine.control.service import DomainError, Service, digest, json_safe
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError, digest_file
from abr_engine.ingest.qbcc import PUBLISHER_VERSION, QBCCMapping, parse_qbcc, write_qbcc_parquet
from abr_engine.ingest.qbcc_review import (
    MAX_FILE_BYTES,
    QBCCReviewRequest,
    _approved,
    _configured,
    _ordinary_path,
    _replay_verified,
)
from abr_engine.ops.promotion import (
    _matching_alias_groups,
    declare_artifact,
    promote,
    source_lock_key,
    verify_artifact,
)
from abr_engine.pipeline import _session_lock, process_lock, safe_root
from abr_engine.qualify.abr import qualify_qbcc
from abr_engine.qualify.queue import score


class QBCCLicenceReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: UUID
    snapshot_id: UUID
    licence_number: str = Field(min_length=1, max_length=80)
    row_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["active", "suspended", "cancelled", "inactive", "unknown"]
    identity_match: bool = Field(strict=True)
    reviewed_at: datetime
    evidence_ref: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def explicit_evidence(self):
        if self.reviewed_at.tzinfo is None or not self.evidence_ref.strip():
            raise ValueError("Aware review time and evidence reference are required")
        if self.licence_number != self.licence_number.strip():
            raise ValueError("Exact source licence number is required")
        return self


def _access(conn, service):
    _configured(service.settings)
    service.personal_data_access(conn)
    reasons = gate_reasons(conn, service.settings, "collection", service.now(conn))
    if reasons:
        raise DomainError(reasons[0], 403, {"reason_codes": reasons})


def _cursor(conn):
    return conn.execute(
        "SELECT c.version,s.* FROM source_cursor c JOIN source_snapshot s USING(snapshot_id) "
        "WHERE c.source='qbcc' AND s.source='qbcc' AND s.state='committed' FOR SHARE OF c,s"
    ).fetchone()


def _snapshot_paths(conn, settings, snapshot):
    paths = [Path(p) for p in snapshot["manifest"].get("parquet_paths", [])]
    if len(paths) != 1 or snapshot["manifest"].get("schema_version") != PUBLISHER_VERSION:
        raise DomainError("PUBLISHER_SNAPSHOT_REQUIRED", 409)
    root = safe_root(settings)
    for path in paths:
        _ordinary_path(path)
        if not path.is_absolute() or not path.resolve().is_relative_to(root):
            raise DomainError("ARTIFACT_PATH_OUTSIDE_STORAGE", 409)
        row = conn.execute(
            "SELECT * FROM artifact_manifest WHERE snapshot_id=%s AND local_path=%s AND state='referenced'",
            (snapshot["snapshot_id"], str(path)),
        ).fetchone()
        if (
            not row
            or not path.is_file()
            or path.stat().st_size > MAX_FILE_BYTES
            or path.stat().st_size != row["byte_count"]
            or digest_file(path) != row["content_digest"]
        ):
            raise DomainError("ACCEPTED_ARTIFACT_UNAVAILABLE_OR_CHANGED", 409)
    return paths


def _rows(paths):
    for path in paths:
        with pq.ParquetFile(path) as table:
            for batch in table.iter_batches(batch_size=2000):
                yield from batch.to_pylist()


def accept_qbcc_snapshot(settings, intake_run_id: UUID, expected_cursor_version: int, actor: str) -> dict:
    """Accept one already approved intake, preserving source UNKNOWN status.

    Approval is checked before keys/files and again in the commit transaction.
    Failure never moves the cursor. A committed retry returns its exact receipt.
    """
    _configured(settings)
    if not actor.strip() or expected_cursor_version < 0:
        raise SourceError("INVALID_ACCEPTANCE_REQUEST")
    with transaction(settings) as conn:
        reasons = gate_reasons(conn, settings, "collection", Service.now(conn))
        if reasons:
            raise SourceError(reasons[0])
    service = Service(settings, load_keys(settings))
    root = safe_root(settings)
    with (
        process_lock(root / "qbcc-review.lock"),
        _session_lock(settings, source_lock_key("qbcc-acceptance-writer", settings.schema_name)),
    ):
        with transaction(settings) as conn:
            _access(conn, service)
            run = conn.execute(
                "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (intake_run_id,)
            ).fetchone()
            if not run or run["mode"] != settings.mode or run["manifest"].get("kind") != "qbcc_review_intake":
                raise SourceError("QBCC_INTAKE_REQUIRED")
            manifest = run["manifest"]
            accepted = manifest.get("acceptance_receipt")
            if accepted:
                if accepted["expected_cursor_version"] != expected_cursor_version:
                    raise SourceError("INTAKE_REPLAY_CONFLICT")
                return {**accepted, "replayed": True}
            if manifest.get("intake_state") != "needs_review" or run["state"] != "held":
                raise SourceError("QBCC_INTAKE_NOT_READY")
            observation = conn.execute(
                "SELECT * FROM source_observation WHERE observation_id=%s",
                (uuid5(intake_run_id, "qbcc-review-observation"),),
            ).fetchone()
            if not observation:
                raise SourceError("QBCC_SOURCE_OBSERVATION_REQUIRED")
            directory = root / "staging" / "qbcc" / str(intake_run_id)
            raw, normalized = directory / "publisher.csv", directory / "publisher.parquet"
            request = QBCCReviewRequest(
                run_id=intake_run_id,
                input_path=raw,
                source_sha256=manifest["source_sha256"],
                inventory_before_sha256=manifest["inventory_before_sha256"],
                inventory_after_sha256=manifest["inventory_after_sha256"],
                mapping_evidence_ref=manifest["mapping_evidence_ref"],
                mapping_evidence_sha256=manifest["mapping_evidence_sha256"],
                retrieved_at=observation["observed_at"],
                expected_cursor_version=expected_cursor_version,
            )
            _approved(conn, settings, request)
            _replay_verified(conn, intake_run_id, raw, MAX_FILE_BYTES)
            prior = _cursor(conn)
            if prior:
                _snapshot_paths(conn, settings, prior)
            declare_artifact(conn, intake_run_id, "qbcc", normalized, artifact_class="snapshot")
        # A deterministic normalized artifact may survive a rolled-back promotion.
        # Its declared ownership remains durable, so retries never adopt foreign files.
        with transaction(settings) as conn:
            _access(conn, service)
            _approved(conn, settings, request)
            _replay_verified(conn, intake_run_id, raw, MAX_FILE_BYTES)
            parsed = parse_qbcc(
                raw,
                mapping=QBCCMapping.publisher(approved_evidence=request.mapping_evidence_ref),
                production=True,
            )
            if parsed.source_sha256 != request.source_sha256:
                raise SourceError("SOURCE_DIGEST_MISMATCH")
            artifact = conn.execute(
                "SELECT * FROM artifact_manifest WHERE run_id=%s AND local_path=%s FOR UPDATE",
                (intake_run_id, str(normalized.resolve())),
            ).fetchone()
            if not artifact:
                raise SourceError("ARTIFACT_NOT_OWNED")
            if normalized.exists():
                if artifact["state"] != "verified":
                    raise SourceError("PARTIAL_NORMALIZED_ARTIFACT_REQUIRES_RECOVERY")
                verify_artifact(conn, intake_run_id, "qbcc", normalized)
            else:
                write_qbcc_parquet(parsed, normalized)
                verify_artifact(conn, intake_run_id, "qbcc", normalized)
        with transaction(settings) as conn:
            _access(conn, service)
            _approved(conn, settings, request)
            source_manifest = {
                "snapshot_id": str(uuid5(intake_run_id, "accepted-qbcc-snapshot")),
                "observation_id": str(uuid5(intake_run_id, "accepted-qbcc-observation")),
                "observed_at": observation["observed_at"].isoformat(),
                "schema_version": PUBLISHER_VERSION,
                "parser_version": PUBLISHER_VERSION,
                "content_digest": parsed.source_sha256,
                "generation": request.inventory_before_sha256,
                "coherence": "validated",
                "observation_kind": "publisher_revalidation",
                "approved_mapping_evidence": request.mapping_evidence_ref,
                "inventory_before_digest": request.inventory_before_sha256,
                "inventory_after_digest": request.inventory_after_sha256,
                "publisher_revalidation_evidence": "approved_operator_supplied_digest",
                "source_url": manifest["source_url"],
                "publisher_modified_at": manifest.get("publisher_receipt", {}).get("publisher_last_modified"),
                "publisher_etag": manifest.get("publisher_receipt", {}).get("etag"),
                "licence_reference": manifest.get("publisher_receipt", {}).get(
                    "licence_reference", request.mapping_evidence_ref
                ),
                "publisher_receipt": manifest.get("publisher_receipt"),
                "quarantined_records": len(parsed.quarantined),
                "record_count": len(parsed.records),
                "publisher_status": "UNKNOWN",
            }
            result = promote(
                conn,
                service,
                intake_run_id,
                "qbcc",
                source_manifest,
                [normalized],
                expected_version=expected_cursor_version,
            )
            if not result["noop"]:
                for row in parsed.records:
                    groups = _matching_alias_groups(conn, service, "qbcc", row["licence_number"])
                    leads = (
                        conn.execute(
                            "SELECT * FROM lead_entity WHERE group_id=ANY(%s)", (list(groups),)
                        ).fetchall()
                        if groups
                        else []
                    )
                    for lead in leads:
                        if lead["fields"].get("source_row_digest") == row["row_digest"]:
                            continue
                        service.licence(
                            conn,
                            {
                                "lead_id": lead["lead_id"],
                                "licence_number": row["licence_number"],
                                "status": "unknown",
                                "identity_match": False,
                                "reviewed_at": service.now(conn),
                                "evidence_ref": f"snapshot:{result['snapshot_id']}:changed_source_evidence",
                            },
                            "source-promotion",
                        )
                        conn.execute(
                            "UPDATE candidate_queue SET state='needs_review' WHERE lead_id=%s AND state NOT IN ('suppressed','exported','disqualified')",
                            (lead["lead_id"],),
                        )
            # The publisher's missing status does not erase its discovery backlog.
            # These are source observations only; candidate creation remains zero.
            if not result["noop"] and not prior:
                for row in parsed.records:
                    if row["financial_category"] in ("1", "2"):
                        event_id = uuid5(UUID(result["snapshot_id"]), f"{row['licence_number']}:icp_backlog")
                        inserted = conn.execute(
                            "INSERT INTO qbcc_event(event_id,snapshot_id,licence_number,event_type,payload,detected_at) "
                            "VALUES(%s,%s,%s,'icp_backlog',%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                            (
                                event_id,
                                result["snapshot_id"],
                                row["licence_number"],
                                Jsonb({"before": None, "after": row}),
                                observation["observed_at"],
                            ),
                        ).fetchone()
                        result["events"] += bool(inserted)
            if not result["noop"]:
                conn.execute(
                    "UPDATE artifact_manifest SET state='referenced',snapshot_id=%s WHERE run_id=%s AND state='verified'",
                    (result["snapshot_id"], intake_run_id),
                )
            receipt = {
                **result,
                "accepted": True,
                "source": "qbcc",
                "state": "complete",
                "expected_cursor_version": expected_cursor_version,
                "licence_review_required": True,
            }
            current_row = conn.execute(
                "SELECT manifest FROM pipeline_run WHERE run_id=%s", (intake_run_id,)
            ).fetchone()
            assert current_row is not None
            current = current_row["manifest"]
            current.update(intake_state="accepted", acceptance_receipt=receipt)
            current["promotion_results"]["qbcc"] = result
            conn.execute(
                "UPDATE pipeline_run SET state='complete',manifest=%s,finished_at=clock_timestamp(),heartbeat_at=clock_timestamp() WHERE run_id=%s",
                (Jsonb(current), intake_run_id),
            )
            service.audit(
                conn,
                actor,
                "qbcc_snapshot_accepted",
                result["snapshot_id"],
                {"run_id": intake_run_id, "candidates": result["candidates"]},
            )
            return receipt


def _latest_review(conn, service, licence):
    records = []
    for version, token in service.keys.matches("qbcc", licence):
        row = conn.execute(
            "SELECT * FROM qbcc_source_review WHERE alias_token=%s AND key_version=%s ORDER BY reviewed_at DESC,review_seq DESC LIMIT 1",
            (token, version),
        ).fetchone()
        if row:
            records.append(row)
    return max(records, key=lambda r: (r["reviewed_at"], r["review_seq"])) if records else None


def list_qbcc_reviews(conn, service, limit=100, offset=0) -> dict:
    if not 1 <= limit <= 100 or not 0 <= offset <= 1_000_000:
        raise DomainError("INVALID_PAGINATION")
    service.personal_data_access(conn)
    snapshot = _cursor(conn)
    if not snapshot:
        return {
            "snapshot_id": None,
            "source_observed_at": None,
            "publisher_modified_at": None,
            "source_state": "not_collected",
            "total": 0,
            "rows": [],
            "reason_codes": gate_reasons(conn, service.settings, "collection", service.now(conn)),
        }
    _access(conn, service)
    items, total = [], 0
    for row in _rows(_snapshot_paths(conn, service.settings, snapshot)):
        if row["financial_category"] not in ("1", "2"):
            continue
        index, total = total, total + 1
        if not offset <= index < offset + limit:
            continue
        review = _latest_review(conn, service, row["licence_number"])
        current = bool(
            review
            and review["row_digest"] == row["row_digest"]
            and service.now(conn) < review["reviewed_at"] + timedelta(days=30)
        )
        items.append(
            {
                **{
                    k: row[k]
                    for k in (
                        "licence_number",
                        "licensee_name",
                        "abn",
                        "financial_category",
                        "original_address",
                        "state",
                        "postcode",
                        "row_digest",
                    )
                },
                "snapshot_id": str(snapshot["snapshot_id"]),
                "publisher_status": row["status"],
                "review_status": review["status"] if current else "needs_review",
                "reviewed_at": review["reviewed_at"] if review else None,
                "review_id": review["review_id"] if review else None,
                "lead_id": review["lead_id"] if review else None,
                "reason_codes": review["receipt"]["reason_codes"]
                if current
                else ["CURRENT_LICENCE_REVIEW_REQUIRED"],
            }
        )
    return json_safe(
        {
            "snapshot_id": snapshot["snapshot_id"],
            "source_observed_at": snapshot["manifest"]["observed_at"],
            "publisher_modified_at": snapshot["manifest"].get("publisher_modified_at"),
            "source_state": "accepted",
            "total": total,
            "rows": items,
        }
    )


def review_qbcc_licence(conn, service, data: dict, actor: str) -> dict:
    request = QBCCLicenceReview.model_validate(data)
    if not actor.strip():
        raise DomainError("ACTOR_REQUIRED", 403)
    with conn.transaction():
        _access(conn, service)
        body_digest = digest({**request.model_dump(mode="json"), "actor": actor})
        replay = conn.execute(
            "SELECT * FROM qbcc_source_review WHERE review_id=%s", (request.request_id,)
        ).fetchone()
        if replay:
            if replay["request_digest"] != body_digest:
                raise DomainError("IDEMPOTENCY_CONFLICT", 409)
            return {**replay["receipt"], "replayed": True}
        now = service.now(conn)
        if not now - timedelta(days=30) < request.reviewed_at <= now:
            raise DomainError("CURRENT_LICENCE_REVIEW_REQUIRED", 409)
        snapshot = _cursor(conn)
        if not snapshot or snapshot["snapshot_id"] != request.snapshot_id:
            raise DomainError("STALE_SOURCE_SNAPSHOT", 409)
        row = next(
            (
                r
                for r in _rows(_snapshot_paths(conn, service.settings, snapshot))
                if r["licence_number"] == request.licence_number
            ),
            None,
        )
        if not row or row["row_digest"] != request.row_digest:
            raise DomainError("SOURCE_ROW_MISMATCH", 409)
        latest = _latest_review(conn, service, request.licence_number)
        if latest and request.reviewed_at < latest["reviewed_at"]:
            raise DomainError("NEWER_LICENCE_REVIEW_EXISTS", 409)
        event = conn.execute(
            "SELECT * FROM qbcc_event WHERE licence_number=%s AND event_type IN ('icp_backlog','new','category_changed') "
            "AND payload->'after'->>'financial_category'=%s ORDER BY detected_at DESC,event_id LIMIT 1",
            (request.licence_number, row["financial_category"]),
        ).fetchone()
        reasons = []
        if not request.identity_match:
            reasons.append("LICENCE_IDENTITY_NOT_CONFIRMED")
        if request.status != "active":
            reasons.append("LICENCE_NOT_ACTIVE")
        qualification = qualify_qbcc(
            {**row, "status": request.status.upper()}, event["event_type"] if event else "none"
        )
        reasons.extend(qualification.reason_codes)
        groups = _matching_alias_groups(conn, service, "qbcc", request.licence_number)
        if row.get("abn"):
            groups |= _matching_alias_groups(conn, service, "abn", row["abn"])
        for group in groups:
            reasons.extend(service.restricted(conn, group))
        if len(groups) > 1:
            reasons.append("IDENTITY_MERGE_REVIEW_REQUIRED")
        leads = (
            conn.execute("SELECT * FROM lead_entity WHERE group_id=ANY(%s)", (list(groups),)).fetchall()
            if groups
            else []
        )
        lead = leads[0] if len(leads) == 1 else None
        if lead and lead["lifecycle"] != "active":
            reasons.append("LEAD_INACTIVE")
        if lead and lead["source"] != "qbcc":
            reasons.append("CROSS_SOURCE_PROFILE_REVIEW_REQUIRED")
        if not reasons:
            assert event is not None
            lead = service.create_lead(
                conn,
                name=row["licensee_name"],
                source="qbcc",
                alias=request.licence_number,
                abn=row.get("abn"),
                state=row["state"],
                postcode=row["postcode"],
                tier="A",
                signal={
                    "icp_backlog": "qbcc_backlog",
                    "new": "qbcc_new",
                    "category_changed": "qbcc_category_changed",
                }[event["event_type"]],
                score=score(
                    source="qbcc",
                    tier="A",
                    geography=True,
                    category=row["financial_category"],
                    company=False,
                    provisional=True,
                ),
                event_key=str(event["event_id"]),
                fields={
                    "financial_category": row["financial_category"],
                    "entity_class": "unknown",
                    "original_address": row["original_address"],
                    "source_snapshot_id": str(snapshot["snapshot_id"]),
                    "source_row_digest": row["row_digest"],
                    "source_observed_at": snapshot["manifest"]["observed_at"],
                    "licence_review_id": str(request.request_id),
                },
            )
            conn.execute(
                "UPDATE lead_entity SET display_name=%s,state=%s,postcode=%s,fields=fields||%s,revision=revision+1 WHERE lead_id=%s",
                (
                    row["licensee_name"],
                    row["state"],
                    row["postcode"],
                    Jsonb(
                        {
                            "financial_category": row["financial_category"],
                            "source_row_digest": row["row_digest"],
                            "original_address": row["original_address"],
                            "source_snapshot_id": str(snapshot["snapshot_id"]),
                            "source_observed_at": snapshot["manifest"]["observed_at"],
                            "licence_review_id": str(request.request_id),
                        }
                    ),
                    lead["lead_id"],
                ),
            )
            conn.execute(
                "UPDATE candidate_queue SET state='pending_enrichment' WHERE lead_id=%s AND event_key=%s AND state='needs_review'",
                (lead["lead_id"], str(event["event_id"])),
            )
        # Every negative current review removes existing pending action authority.
        for existing in leads:
            service.invalidate(conn, existing["lead_id"])
            if request.status != "active" or not request.identity_match:
                conn.execute(
                    "UPDATE candidate_queue SET state='needs_review' WHERE lead_id=%s AND state NOT IN ('exported','suppressed','disqualified')",
                    (existing["lead_id"],),
                )
            if request.status in ("suspended", "cancelled", "inactive"):
                reason = "cancellation" if request.status == "cancelled" else "source_inactive"
                service.suppress(
                    conn,
                    {
                        "group_id": existing["group_id"],
                        "reason": reason,
                        "source": "qbcc_review",
                        "entity_only": True,
                    },
                    actor,
                    request.request_id,
                )
        known_licence = bool(_matching_alias_groups(conn, service, "qbcc", request.licence_number))
        if lead and known_licence:
            service.licence(
                conn,
                {
                    "lead_id": lead["lead_id"],
                    "licence_number": request.licence_number,
                    "status": request.status,
                    "identity_match": request.identity_match,
                    "reviewed_at": request.reviewed_at,
                    "evidence_ref": request.evidence_ref,
                },
                actor,
            )
        receipt = json_safe(
            {
                "review_id": request.request_id,
                "lead_id": lead["lead_id"] if lead else None,
                "group_id": lead["group_id"] if lead else None,
                "state": "pending_enrichment" if not reasons else "needs_review",
                "reason_codes": sorted(set(reasons)),
                "enrichment_eligible": not reasons,
                "export_eligible": False,
                "replayed": False,
            }
        )
        conn.execute(
            "INSERT INTO qbcc_source_review(review_id,snapshot_id,row_digest,alias_token,key_version,status,identity_match,evidence_encrypted,actor_id,reviewed_at,lead_id,request_digest,receipt) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                request.request_id,
                snapshot["snapshot_id"],
                row["row_digest"],
                service.keys.token("qbcc", request.licence_number),
                service.keys.active_version,
                request.status,
                request.identity_match,
                service.keys.encrypt(request.evidence_ref),
                actor,
                request.reviewed_at,
                lead["lead_id"] if lead else None,
                body_digest,
                Jsonb(receipt),
            ),
        )
        service.audit(
            conn,
            actor,
            "qbcc_source_reviewed",
            request.request_id,
            {"snapshot_id": snapshot["snapshot_id"], "state": receipt["state"]},
        )
        return receipt
