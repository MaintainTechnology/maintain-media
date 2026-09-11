"""Approved publisher-file intake, held for review; never an accepted snapshot.

This path has no transport, qualification, contact, candidate or cursor writer.
The retained raw register and encrypted review projection are owned by the
existing artifact manifest and expire as unreferenced held staging after 7 days.
"""

from __future__ import annotations

import hashlib
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid5

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abr_engine import __version__
from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import REQUIRED_GATES, current_gate_evidence
from abr_engine.compliance.retention import _held
from abr_engine.config import ROOT, Settings
from abr_engine.control.service import Service, digest
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError, canonical_json
from abr_engine.ingest.qbcc import PUBLISHER_VERSION, QBCCMapping, parse_qbcc
from abr_engine.ops.promotion import _object_key, declare_artifact, source_lock_key, verify_artifact
from abr_engine.pipeline import _session_lock, process_lock, safe_root

MAX_FILE_BYTES = 512 * 1024**2
MAX_ROWS = 1_000_000
MAX_REVIEW_BYTES = 1024**3
SOURCE_URL = (
    "https://www.data.qld.gov.au/dataset/980b6499-c0b4-491b-ba9c-1c7506368a50/"
    "resource/25608781-b28c-44f8-8545-0ab18d84082f/download/"
    "builder-contractor-qbcc-licensee-register.csv"
)
SHA = r"^[0-9a-f]{64}$"


class QBCCReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: UUID
    input_path: Path
    source_sha256: str = Field(pattern=SHA)
    inventory_before_sha256: str = Field(pattern=SHA)
    inventory_after_sha256: str = Field(pattern=SHA)
    mapping_evidence_ref: str = Field(min_length=1, max_length=500)
    mapping_evidence_sha256: str = Field(pattern=SHA)
    retrieved_at: datetime
    expected_cursor_version: int = Field(ge=0, le=2**63 - 1, strict=True)

    @model_validator(mode="after")
    def coherent_receipt(self):
        if self.retrieved_at.tzinfo is None:
            raise ValueError("An aware retrieval timestamp is required")
        if self.inventory_before_sha256 != self.inventory_after_sha256:
            raise ValueError("Publisher inventory changed during retrieval")
        if not self.mapping_evidence_ref.strip():
            raise ValueError("Mapping evidence is required")
        return self


def _configured(settings, *, collection=True):
    try:
        db = conninfo_to_dict(settings.database_url)
    except (ProgrammingError, ValueError, TypeError):
        raise SourceError("LIVE_QBCC_CONFIGURATION_REQUIRED") from None
    username, database = db.get("user"), db.get("dbname")
    if not isinstance(username, str) or not isinstance(database, str):
        raise SourceError("LIVE_QBCC_CONFIGURATION_REQUIRED")
    if (
        settings.mode == "fixture"
        or not username
        or not database
        or username == "abr_fixture"
        or database == "abr_fixture"
        or db.get("service")
        or any(marker in database for marker in ("=", "://", "/"))
    ):
        raise SourceError("LIVE_QBCC_CONFIGURATION_REQUIRED")
    if collection and not settings.capabilities.get("collection"):
        raise SourceError("CAPABILITY_DISABLED")
    if not settings.key_file or not settings.key_file.is_absolute():
        raise SourceError("MANAGED_KEY_STORE_REQUIRED")


def _ordinary_path(path, *, csv_input=False):
    """Metadata only: reject credential paths and Windows reparse/symlink hops."""
    if csv_input and (
        path.suffix.lower() != ".csv"
        or any(
            part.lower().startswith(".env")
            or part.lower() in {".ssh", ".aws", ".azure", ".gnupg", "credentials", "secrets", ".codex"}
            for part in path.parts
        )
    ):
        raise SourceError("QBCC_INPUT_PATH_NOT_ALLOWED")
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise SourceError("QBCC_REPARSE_PATH_NOT_ALLOWED")
        if entry == path and csv_input and not stat.S_ISREG(info.st_mode):
            raise SourceError("QBCC_INPUT_PATH_NOT_ALLOWED")


def _approved(conn, settings, request, *, replay=False):
    """Run before any input/key read and again before recording usable intake."""
    now = Service.now(conn)
    rows = conn.execute(
        "SELECT DISTINCT ON(gate_name) * FROM release_gate WHERE environment=%s "
        "AND scope='collection' ORDER BY gate_name,revision DESC",
        (settings.mode,),
    ).fetchall()
    valid = {r["gate_name"]: r for r in rows if current_gate_evidence(r, now)}
    for gate in sorted(REQUIRED_GATES["collection"]):
        if gate not in valid:
            raise SourceError("GATE_" + gate + "_CLOSED")
    mapping = valid["G2"]
    if (
        mapping["evidence_ref"] != request.mapping_evidence_ref
        or mapping["evidence_sha256"] != request.mapping_evidence_sha256
    ):
        raise SourceError("QBCC_MAPPING_APPROVAL_MISMATCH")
    if not replay and not now - timedelta(hours=24) <= request.retrieved_at <= now + timedelta(minutes=5):
        raise SourceError("QBCC_RETRIEVAL_RECEIPT_STALE")
    cursor = conn.execute("SELECT * FROM source_cursor WHERE source='qbcc'").fetchone()
    if (cursor["version"] if cursor else 0) != request.expected_cursor_version:
        raise SourceError("STALE_SOURCE_CURSOR")
    return {r["gate_name"]: r["revision"] for r in valid.values()}


def _copy_bounded(source, target, expected):
    if not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise SourceError("SOURCE_SIZE_OR_TYPE_INVALID")
    checksum, count = hashlib.sha256(), 0
    with (
        source.open("rb") as src,
        os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as dst,
    ):
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            count += len(chunk)
            if count > MAX_FILE_BYTES:
                raise SourceError("SOURCE_SIZE_LIMIT")
            checksum.update(chunk)
            dst.write(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    if checksum.hexdigest() != expected:
        raise SourceError("SOURCE_DIGEST_MISMATCH")


def stage_qbcc_review(settings: Settings, request: QBCCReviewRequest) -> dict:
    """Stage one approved CSV using managed live keys; return only a safe receipt.

    Reuse the run UUID only for an exact successful intake replay. Failed/crashed
    attempts remain held for retention and need a new run UUID. This function
    never downloads, accepts a baseline, seeds policy, or qualifies a business.
    """
    _configured(settings)
    request_digest = digest(request.model_dump(mode="json"))
    with transaction(settings) as conn:
        prior = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request.run_id,)).fetchone()
        _approved(conn, settings, request, replay=bool(prior))
    if not prior:
        _ordinary_path(request.input_path, csv_input=True)
    # Approval precedes loading the encrypted store, touching input or storage.
    keys = load_keys(settings)
    if not keys.path or not keys.wrapping_key:
        raise SourceError("MANAGED_KEY_STORE_REQUIRED")
    service = Service(settings, keys)
    _ordinary_path(settings.output_dir if settings.output_dir.is_absolute() else ROOT / settings.output_dir)
    root = safe_root(settings)
    directory = (root / "staging" / "qbcc" / str(request.run_id)).resolve()
    if not directory.is_relative_to(root) or directory == root:
        raise SourceError("ARTIFACT_PATH_OUTSIDE_STORAGE")
    raw, review = directory / "publisher.csv", directory / "review.encrypted.jsonl"
    paths = (raw, review)
    with (
        process_lock(root / "qbcc-review.lock"),
        _session_lock(settings, source_lock_key("qbcc", settings.schema_name)),
    ):
        with transaction(settings) as conn:
            prior = conn.execute(
                "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (request.run_id,)
            ).fetchone()
            _approved(conn, settings, request, replay=bool(prior))
            service.personal_data_access(conn)
            if prior:
                manifest = prior["manifest"] or {}
                if prior["config_digest"] != request_digest or manifest.get("kind") != "qbcc_review_intake":
                    raise SourceError("INTAKE_REPLAY_CONFLICT")
                if manifest.get("intake_state") != "needs_review":
                    raise SourceError("INTAKE_REQUIRES_NEW_ATTEMPT")
                for path in paths:
                    _replay_verified(
                        conn, request.run_id, path, MAX_FILE_BYTES if path == raw else MAX_REVIEW_BYTES
                    )
                return {**manifest["receipt"], "replayed": True}
            if directory.exists():
                raise SourceError("ARTIFACT_ALREADY_EXISTS")
            conn.execute(
                "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) "
                "VALUES(%s,%s,%s,%s,'running',%s)",
                (
                    request.run_id,
                    settings.mode,
                    __version__,
                    request_digest,
                    Jsonb({"kind": "qbcc_review_intake", "intake_state": "writing"}),
                ),
            )
            declare_artifact(conn, request.run_id, "qbcc", raw, artifact_class="raw")
            declare_artifact(conn, request.run_id, "qbcc", review, artifact_class="snapshot")
        created = False
        try:
            directory.mkdir(parents=True, exist_ok=False)
            created = True
            _copy_bounded(request.input_path, raw, request.source_sha256)
            parsed = parse_qbcc(
                raw,
                mapping=QBCCMapping.publisher(approved_evidence=request.mapping_evidence_ref),
                production=True,
                max_rows=MAX_ROWS,
                max_file_bytes=MAX_FILE_BYTES,
            )
            if not parsed.row_count:
                raise SourceError("EMPTY_QBCC_REGISTER")
            with os.fdopen(
                os.open(review, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                "w",
                encoding="utf-8",
                newline="\n",
            ) as out:
                review_bytes = 0
                for state, records in (("needs_review", parsed.records), ("quarantined", parsed.quarantined)):
                    for record in records:
                        private = {
                            "review_id": str(uuid5(request.run_id, record["licence_number"])),
                            "state": state,
                            "source": "qbcc",
                            "record": record,
                            "reason_codes": record.get("reason_codes", ["CURRENT_LICENCE_REVIEW_REQUIRED"]),
                            "tier": None,
                            "enrichment_eligible": False,
                            "export_eligible": False,
                        }
                        line = (
                            canonical_json(
                                {"format": "fernet-v1", "payload": keys.encrypt(canonical_json(private))}
                            )
                            + "\n"
                        )
                        review_bytes += len(line.encode("utf-8"))
                        if review_bytes > MAX_REVIEW_BYTES:
                            raise SourceError("REVIEW_ARTIFACT_SIZE_LIMIT")
                        out.write(line)
                out.flush()
                os.fsync(out.fileno())
            receipt = {
                "run_id": str(request.run_id),
                "state": "needs_review",
                "accepted": False,
                "source": "qbcc",
                "mapping_version": PUBLISHER_VERSION,
                "raw_row_count": parsed.row_count,
                "review_record_count": len(parsed.records),
                "quarantine_record_count": len(parsed.quarantined),
                "replayed": False,
                "candidates_created": 0,
                "accepted_cursor_advanced": False,
                "retention": "unreferenced_held_staging_7_days",
            }
            with transaction(settings) as conn:
                approvals = _approved(conn, settings, request)
                service.personal_data_access(conn)
                artifacts = [verify_artifact(conn, request.run_id, "qbcc", p) for p in paths]
                manifest = {
                    "kind": "qbcc_review_intake",
                    "intake_state": "needs_review",
                    "receipt": receipt,
                    "source_url": SOURCE_URL,
                    "source_sha256": parsed.source_sha256,
                    "inventory_before_sha256": request.inventory_before_sha256,
                    "inventory_after_sha256": request.inventory_after_sha256,
                    "mapping_evidence_ref": request.mapping_evidence_ref,
                    "mapping_evidence_sha256": request.mapping_evidence_sha256,
                    "collection_gate_revisions": approvals,
                    "expected_cursor_version": request.expected_cursor_version,
                    "artifact_ids": [str(a["artifact_id"]) for a in artifacts],
                    "publisher_receipt_verified_by": "approved_operator_supplied_digest",
                    "remaining": [
                        "current_licence_and_identity_review",
                        "suppression_check_before_discovery",
                        "accepted_snapshot_promotion",
                        "qualified_worklist_wiring",
                    ],
                }
                conn.execute(
                    "INSERT INTO source_observation(observation_id,run_id,source,manifest,observed_at) VALUES(%s,%s,'qbcc',%s,%s)",
                    (
                        uuid5(request.run_id, "qbcc-review-observation"),
                        request.run_id,
                        Jsonb(manifest),
                        request.retrieved_at,
                    ),
                )
                conn.execute(
                    "UPDATE pipeline_run SET state='held',finished_at=clock_timestamp(),heartbeat_at=clock_timestamp(),manifest=%s WHERE run_id=%s",
                    (Jsonb(manifest), request.run_id),
                )
            return receipt
        except Exception:
            # Keep failed attempt ownership and verified partial bytes discoverable
            # by finite retention. Never turn a failed write into accepted intake.
            with transaction(settings) as conn:
                for path in paths:
                    if created and path.is_file():
                        verify_artifact(conn, request.run_id, "qbcc", path)
                conn.execute(
                    "UPDATE pipeline_run SET state='failed',finished_at=clock_timestamp(),manifest=%s WHERE run_id=%s",
                    (Jsonb({"kind": "qbcc_review_intake", "intake_state": "failed"}), request.run_id),
                )
            raise


def cleanup_qbcc_review(settings: Settings, *, run_id: UUID | None = None, execute: bool = False) -> dict:
    """Recover/expire only this intake's owned artifacts, without reading records.

    Collection approval expiry cannot veto deletion. Managed key/restore authority
    and explicit --execute remain required; general retention has its separate policy gate.
    A caller must install a daily invocation on the approved service host.
    """
    _configured(settings, collection=False)
    keys = load_keys(settings)
    if not keys.path or not keys.wrapping_key:
        raise SourceError("MANAGED_KEY_STORE_REQUIRED")
    service = Service(settings, keys)
    _ordinary_path(settings.output_dir if settings.output_dir.is_absolute() else ROOT / settings.output_dir)
    root = safe_root(settings)
    results = []
    with (  # noqa: SIM117 - keep the source lock lifetime visually explicit
        process_lock(root / "qbcc-review.lock"),
        _session_lock(settings, source_lock_key("qbcc", settings.schema_name)),
    ):
        with transaction(settings) as conn:
            service.personal_data_access(conn)
            now = Service.now(conn)
            # Accepted intakes belong to ordinary source/artifact retention, not
            # abandoned review staging. Exclude only the coherent terminal receipt;
            # missing receipts or inconsistent states must still be checked/held.
            runs = conn.execute(
                "SELECT * FROM pipeline_run WHERE manifest->>'kind'='qbcc_review_intake' AND mode=%s "
                "AND manifest->>'intake_state' IS DISTINCT FROM 'expired' "
                "AND NOT COALESCE(state='complete' AND manifest @> "
                "'{\"intake_state\":\"accepted\",\"acceptance_receipt\":{\"accepted\":true,"
                "\"source\":\"qbcc\",\"state\":\"complete\"}}'::jsonb, false) "
                "AND (%s::uuid IS NULL OR run_id=%s) "
                "ORDER BY COALESCE((manifest->>'cleanup_checked_at')::timestamptz,started_at),run_id LIMIT 100 FOR UPDATE",
                (settings.mode, run_id, run_id),
            ).fetchall()
            for run in runs:
                item: dict = {"run_id": str(run["run_id"]), "state": "retained", "deleted_files": 0}
                results.append(item)
                if execute:
                    conn.execute(
                        "UPDATE pipeline_run SET manifest=manifest || jsonb_build_object('cleanup_checked_at',clock_timestamp()) WHERE run_id=%s",
                        (run["run_id"],),
                    )
                directory = root / "staging" / "qbcc" / str(run["run_id"])
                expected = {str(directory / "publisher.csv"), str(directory / "review.encrypted.jsonl")}
                try:
                    _ordinary_path(directory)
                    if run["state"] == "running" and run["heartbeat_at"] > now - timedelta(hours=1):
                        item["reason"] = "INTAKE_RECOVERY_NOT_STALE"
                        continue
                    if run["state"] not in {"running", "failed", "held"}:
                        raise SourceError("INTAKE_NOT_UNREFERENCED")
                    artifacts = conn.execute(
                        "SELECT * FROM artifact_manifest WHERE run_id=%s ORDER BY artifact_id FOR UPDATE",
                        (run["run_id"],),
                    ).fetchall()
                    if len(artifacts) != 2 or {a["local_path"] for a in artifacts} != expected:
                        raise SourceError("INTAKE_ARTIFACT_OWNERSHIP_MISMATCH")
                    if conn.execute(
                        "SELECT 1 FROM artifact_manifest WHERE local_path=ANY(%s) AND run_id<>%s AND state<>'deleted' LIMIT 1",
                        (list(expected), run["run_id"]),
                    ).fetchone():
                        raise SourceError("ARTIFACT_STILL_REFERENCED")
                    if (
                        _held(conn, "run", run["run_id"])
                        or _held(conn, "pipeline_run", run["run_id"])
                        or any(_held(conn, "artifact", a["artifact_id"]) for a in artifacts)
                    ):
                        raise SourceError("ARTIFACT_ACTIVE_OR_HELD")
                    for artifact in artifacts:
                        path = Path(artifact["local_path"])
                        _ordinary_path(path)
                        if (
                            artifact["source"] != "qbcc"
                            or artifact["snapshot_id"] is not None
                            or artifact["state"] == "referenced"
                            or artifact["object_key"] != _object_key(run["run_id"], "qbcc", path)
                        ):
                            raise SourceError("INTAKE_ARTIFACT_OWNERSHIP_MISMATCH")
                        if path.exists():
                            if not path.is_file() or path.stat().st_size > MAX_REVIEW_BYTES:
                                raise SourceError("INTAKE_ARTIFACT_SIZE_INVALID")
                            if artifact["state"] == "deleted":
                                raise SourceError("DELETED_ARTIFACT_REAPPEARED")
                            if artifact["state"] != "writing" and (
                                artifact["byte_count"] != path.stat().st_size
                                or artifact["content_digest"] != _bounded_digest(path)
                            ):
                                raise SourceError("VERIFIED_ARTIFACT_CHANGED")
                    due = all(now >= a["created_at"] + timedelta(days=7) for a in artifacts)
                    if not due:
                        if run["state"] == "running" and execute:
                            conn.execute(
                                "UPDATE pipeline_run SET state='failed',finished_at=clock_timestamp(),manifest=manifest || %s WHERE run_id=%s",
                                (
                                    Jsonb({"intake_state": "failed", "recovery": "stale_writer"}),
                                    run["run_id"],
                                ),
                            )
                            item["state"] = "recovered_for_retention"
                        continue
                    item["state"] = "due"
                    if not execute:
                        continue
                    for artifact in artifacts:
                        path = Path(artifact["local_path"])
                        # Repeated execution after an interrupted unlink/DB commit
                        # safely tombstones already absent exact owned files.
                        if path.exists():
                            path.unlink()
                            item["deleted_files"] += 1
                        conn.execute(
                            "UPDATE artifact_manifest SET state='deleted',deletion_reason='qbcc_review_staging_expired' WHERE artifact_id=%s",
                            (artifact["artifact_id"],),
                        )
                    conn.execute(
                        "UPDATE pipeline_run SET state='failed',finished_at=clock_timestamp(),manifest=manifest || %s WHERE run_id=%s",
                        (Jsonb({"intake_state": "expired"}), run["run_id"]),
                    )
                    item["state"] = "deleted"
                except (SourceError, OSError) as exc:
                    item.update(
                        state="held",
                        reason=exc.code if isinstance(exc, SourceError) else "INTAKE_CLEANUP_IO_FAILURE",
                    )
    return {
        "status": "held"
        if any(item["state"] == "held" for item in results)
        else "complete"
        if execute
        else "preview",
        "kind": "qbcc_review_cleanup",
        "execute": execute,
        "runs": results,
        "schedule_installation": "operator_managed",
        "decrypted_records": 0,
    }


def _replay_verified(conn, run_id, path, max_bytes):
    _ordinary_path(path)
    artifact = conn.execute(
        "SELECT * FROM artifact_manifest WHERE object_key=%s FOR UPDATE", (_object_key(run_id, "qbcc", path),)
    ).fetchone()
    if not artifact or artifact["state"] != "verified" or artifact["snapshot_id"] is not None:
        raise SourceError("ARTIFACT_NOT_OWNED")
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise SourceError("INTAKE_ARTIFACT_SIZE_INVALID")
    if artifact["byte_count"] != path.stat().st_size or artifact["content_digest"] != _bounded_digest(
        path, max_bytes=max_bytes
    ):
        raise SourceError("VERIFIED_ARTIFACT_CHANGED")


def _bounded_digest(path, *, max_bytes=None):
    max_bytes = MAX_REVIEW_BYTES if max_bytes is None else max_bytes
    checksum, count = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            count += len(chunk)
            if count > max_bytes:
                raise SourceError("INTAKE_ARTIFACT_SIZE_INVALID")
            checksum.update(chunk)
    return checksum.hexdigest()
