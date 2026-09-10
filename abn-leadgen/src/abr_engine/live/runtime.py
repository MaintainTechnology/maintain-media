"""Durable, gate-first QBCC jobs shared by the staff API and scheduled CLI.

Only the approved official catalogue resource is accepted. The transport never
follows redirects or inherits local proxy credentials. A worker crash is visible
and recoverable; a successful intake/acceptance is replayed without a download.
"""

from __future__ import annotations

import hashlib
import os
import random
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import httpx
from psycopg.types.json import Jsonb

from abr_engine import __version__
from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import gate_reasons
from abr_engine.control.service import DomainError, Service, digest, json_safe
from abr_engine.db import lock, transaction
from abr_engine.ingest.catalogue import inspect_catalogue
from abr_engine.ingest.common import SourceError, digest_file
from abr_engine.ingest.qbcc_review import (
    MAX_FILE_BYTES,
    SOURCE_URL,
    QBCCReviewRequest,
    _configured,
    _ordinary_path,
    stage_qbcc_review,
)
from abr_engine.live.qbcc import accept_qbcc_snapshot
from abr_engine.ops.promotion import declare_artifact, source_lock_key, verify_artifact
from abr_engine.pipeline import _session_lock, process_lock, safe_root

RESOURCE_ID = "25608781-b28c-44f8-8545-0ab18d84082f"


def _publisher_resource(metadata):
    resources = metadata["resources"]
    selected = [r for r in resources if r["resource_id"] == RESOURCE_ID]
    if len(selected) != 1 or selected[0]["url"] != SOURCE_URL or selected[0]["format"] != "CSV":
        raise SourceError("QBCC_RESOURCE_MAPPING_CHANGED")
    if selected[0]["declared_size"] is not None and selected[0]["declared_size"] > MAX_FILE_BYTES:
        raise SourceError("SOURCE_SIZE_LIMIT")
    return selected[0]


def download_qbcc(path: Path, *, transport=None, sleep=time.sleep, clock=time.monotonic) -> dict:
    """Fixed official URL, fresh downloads only, five attempts and hard bounds."""
    _ordinary_path(path)
    started = clock()
    with httpx.Client(
        transport=transport,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(20, connect=10),
        headers={
            "Accept": "text/csv",
            "Accept-Encoding": "identity",
            "User-Agent": "MaintainMedia-ABNEngine/1.0",
        },
    ) as client:
        for attempt in range(5):
            checksum, count = hashlib.sha256(), 0
            try:
                with client.stream("GET", SOURCE_URL) as response:
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise httpx.TransportError("retryable source response")
                    if response.status_code != 200:
                        raise SourceError("QBCC_SOURCE_HTTP_REJECTED")
                    length = response.headers.get("content-length")
                    if length and (
                        len(length) > 12
                        or not length.isascii()
                        or not length.isdecimal()
                        or int(length) > MAX_FILE_BYTES
                    ):
                        raise SourceError("SOURCE_SIZE_LIMIT")
                    if response.headers.get("content-encoding", "identity") not in ("", "identity"):
                        raise SourceError("QBCC_SOURCE_ENCODING_REJECTED")
                    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
                    with os.fdopen(os.open(path, flags, 0o600), "wb") as output:
                        for chunk in response.iter_raw(1024 * 1024):
                            count += len(chunk)
                            if count > MAX_FILE_BYTES:
                                raise SourceError("SOURCE_SIZE_LIMIT")
                            if clock() - started > 600:
                                raise SourceError("QBCC_SOURCE_DEADLINE")
                            output.write(chunk)
                            checksum.update(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                    if length and int(length) != count:
                        raise SourceError("SOURCE_LENGTH_MISMATCH")
                    return {
                        "source_sha256": checksum.hexdigest(),
                        "byte_count": count,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                        "attempts": attempt + 1,
                        "etag": response.headers.get("etag"),
                        "last_modified": response.headers.get("last-modified"),
                    }
            except httpx.HTTPError:
                if attempt == 4 or clock() - started >= 580:
                    raise SourceError("QBCC_SOURCE_UNAVAILABLE") from None
                sleep(2**attempt + random.random())
    raise SourceError("QBCC_SOURCE_UNAVAILABLE")


class QBCCRuntime:
    def __init__(self, settings, *, transport=None, sleep=time.sleep):
        self.settings, self.transport, self.sleep = settings, transport, sleep

    def submit_run(self, payload: dict, actor: str) -> dict:
        _configured(self.settings, collection=False)
        if not actor.strip() or payload.get("source", "qbcc") != "qbcc":
            raise DomainError("QBCC_PILOT_SOURCE_REQUIRED", 422)
        request_id = UUID(str(payload.get("request_id") or payload.get("run_id") or uuid4()))
        body_digest = digest({"source": "qbcc", "actor": actor, "request_id": str(request_id)})
        with transaction(self.settings) as conn:
            lock(conn, "qbcc-job:" + str(request_id))
            prior = conn.execute(
                "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (request_id,)
            ).fetchone()
            if prior:
                if prior["config_digest"] != body_digest or prior["manifest"].get("kind") != "qbcc_live_job":
                    raise DomainError("IDEMPOTENCY_CONFLICT", 409)
                return self._receipt(prior)
            reasons = gate_reasons(conn, self.settings, "collection", Service.now(conn))
            manifest = {
                "kind": "qbcc_live_job",
                "source": "qbcc",
                "actor": actor,
                "phase": "held" if reasons else "queued",
                "reason_codes": reasons,
                "result": None,
            }
            conn.execute(
                "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    request_id,
                    self.settings.mode,
                    __version__,
                    body_digest,
                    "held" if reasons else "running",
                    Jsonb(manifest),
                ),
            )
            return self._receipt(
                conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request_id,)).fetchone()
            )

    @staticmethod
    def _receipt(row):
        manifest = row["manifest"]
        return json_safe(
            {
                "job_id": row["run_id"],
                "run_id": row["run_id"],
                "source": "qbcc",
                "state": manifest["phase"],
                "phase": manifest["phase"],
                "reason_codes": manifest.get("reason_codes", []),
                "result": manifest.get("result"),
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
        )

    def get_job(self, job_id: str) -> dict:
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (UUID(str(job_id)),)).fetchone()
            if not row or row["manifest"].get("kind") != "qbcc_live_job" or row["mode"] != self.settings.mode:
                raise DomainError("NOT_FOUND", 404)
            return self._receipt(row)

    def _record(self, job_id, **updates):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (job_id,)).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", 404)
            manifest = {**row["manifest"], **json_safe(updates)}
            phase = manifest["phase"]
            state = (
                "complete"
                if phase == "complete"
                else "held"
                if phase == "held"
                else "failed"
                if phase == "failed"
                else "running"
            )
            conn.execute(
                "UPDATE pipeline_run SET manifest=%s,state=%s,heartbeat_at=clock_timestamp(),finished_at=CASE WHEN %s IN ('held','failed','complete') THEN clock_timestamp() ELSE NULL END WHERE run_id=%s",
                (Jsonb(manifest), state, state, job_id),
            )

    def _authority(self):
        with transaction(self.settings) as conn:
            reasons = gate_reasons(conn, self.settings, "collection", Service.now(conn))
            if reasons:
                raise SourceError(reasons[0])
            # Managed key/restore authority also precedes every source HTTP phase.
            service = Service(self.settings, load_keys(self.settings))
            service.personal_data_access(conn)
            gates = conn.execute(
                "SELECT * FROM release_gate WHERE environment=%s AND scope='collection' AND gate_name='G2' ORDER BY revision DESC LIMIT 1",
                (self.settings.mode,),
            ).fetchone()
            cursor = conn.execute("SELECT version FROM source_cursor WHERE source='qbcc'").fetchone()
            return gates, cursor["version"] if cursor else 0

    def execute_job(self, job_id: str | UUID) -> dict:
        job_id = UUID(str(job_id))
        _configured(self.settings, collection=False)
        # Closed jobs remain inspectable; retry after approval uses a new request ID.
        initial = self.get_job(str(job_id))
        if initial["state"] in ("held", "failed", "complete"):
            return initial
        try:
            self._authority()
            root = safe_root(self.settings)
            with (
                process_lock(root / "qbcc-live-worker.lock"),
                _session_lock(self.settings, source_lock_key("qbcc-live-worker", self.settings.schema_name)),
            ):
                with transaction(self.settings) as conn:
                    row = conn.execute(
                        "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (job_id,)
                    ).fetchone()
                    if not row:
                        raise DomainError("NOT_FOUND", 404)
                    manifest = row["manifest"]
                    if manifest["phase"] in ("complete", "held", "failed"):
                        return self._receipt(row)
                if manifest.get("intake_run_id"):
                    result = accept_qbcc_snapshot(
                        self.settings,
                        UUID(manifest["intake_run_id"]),
                        manifest["expected_cursor_version"],
                        manifest["actor"],
                    )
                else:
                    result = self._collect(job_id, root, manifest["actor"])
                self._record(job_id, phase="complete", result=result, reason_codes=[])
        except (DomainError, SourceError) as exc:
            if exc.code in {"SOURCE_STAGE_LOCK_BUSY", "PROCESS_STAGE_LOCK_BUSY"}:
                return self.get_job(str(job_id))
            self._record(job_id, phase="held", reason_codes=[exc.code])
        except Exception:  # noqa: BLE001 - background boundary must not log provider/credential details.
            # Do not disclose response bodies, record data, credentials or DSNs.
            self._record(job_id, phase="failed", reason_codes=["QBCC_JOB_FAILED"])
        return self.get_job(str(job_id))

    def _collect(self, job_id, root, actor):
        mapping, cursor = self._authority()
        attempt_id = uuid4()
        intake_id = uuid5(job_id, str(attempt_id))
        directory = root / "staging" / "qbcc-download" / str(job_id) / str(attempt_id)
        raw = directory / "publisher.csv"
        with transaction(self.settings) as conn:
            declare_artifact(conn, job_id, "qbcc", raw, artifact_class="raw")
        directory.mkdir(parents=True, exist_ok=False)
        self._record(job_id, phase="discovering")
        before = inspect_catalogue("qbcc", transport=self.transport, sleep=self.sleep)
        resource = _publisher_resource(before)
        self._authority()
        self._record(job_id, phase="downloading")
        try:
            download = download_qbcc(raw, transport=self.transport, sleep=self.sleep)
        finally:
            if raw.is_file():
                with transaction(self.settings) as conn:
                    verify_artifact(conn, job_id, "qbcc", raw)
        self._authority()
        after = inspect_catalogue("qbcc", transport=self.transport, sleep=self.sleep)
        _publisher_resource(after)
        if before["resource_inventory_sha256"] != after["resource_inventory_sha256"]:
            raise SourceError("INVENTORY_CHANGED_DURING_DOWNLOAD")
        if resource["declared_size"] is not None and resource["declared_size"] != download["byte_count"]:
            raise SourceError("SOURCE_LENGTH_MISMATCH")
        if (
            resource.get("publisher_hash")
            and len(resource["publisher_hash"]) == 64
            and resource["publisher_hash"].lower() != download["source_sha256"]
        ):
            raise SourceError("SOURCE_DIGEST_MISMATCH")
        request = QBCCReviewRequest(
            run_id=intake_id,
            input_path=raw,
            source_sha256=digest_file(raw),
            inventory_before_sha256=before["resource_inventory_sha256"],
            inventory_after_sha256=after["resource_inventory_sha256"],
            mapping_evidence_ref=mapping["evidence_ref"],
            mapping_evidence_sha256=mapping["evidence_sha256"],
            retrieved_at=datetime.fromisoformat(download["retrieved_at"]),
            expected_cursor_version=cursor,
        )
        self._record(
            job_id,
            phase="staging",
            publisher_metadata={"before": before, "after": after},
            download_receipt=download,
        )
        stage_qbcc_review(self.settings, request)
        with transaction(self.settings) as conn:
            receipt = {
                "publisher_last_modified": resource["publisher_last_modified"],
                "dataset_id": before["dataset_id"],
                "resource_id": RESOURCE_ID,
                "metadata_before_sha256": before["metadata_sha256"],
                "metadata_after_sha256": after["metadata_sha256"],
                "etag": download["etag"],
                "last_modified": download["last_modified"],
                "licence_reference": before["licence"]["url"] or before["licence"]["id"],
            }
            conn.execute(
                "UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s AND manifest->>'intake_state'='needs_review'",
                (Jsonb({"publisher_receipt": receipt}), intake_id),
            )
        # Durable hand-off makes post-intake crashes replay acceptance, not collection.
        self._record(job_id, phase="accepting", intake_run_id=str(intake_id), expected_cursor_version=cursor)
        result = accept_qbcc_snapshot(self.settings, intake_id, cursor, actor)
        # The exact received metadata remains evidence, including explicitly missing fields.
        with transaction(self.settings) as conn:
            service = Service(self.settings, load_keys(self.settings))
            service.audit(
                conn, actor, "qbcc_live_job_accepted", job_id, {"snapshot_id": result["snapshot_id"]}
            )
        return result

    def execute_pending(self, limit=1):
        if not 1 <= limit <= 10:
            raise DomainError("INVALID_JOB_LIMIT")
        with transaction(self.settings) as conn:
            jobs = conn.execute(
                "SELECT run_id FROM pipeline_run WHERE mode=%s AND manifest->>'kind'='qbcc_live_job' AND state='running' "
                "AND (manifest->>'phase'='queued' OR heartbeat_at<%s) ORDER BY started_at,run_id LIMIT %s",
                (self.settings.mode, Service.now(conn) - timedelta(hours=1), limit),
            ).fetchall()
        return [self.execute_job(str(row["run_id"])) for row in jobs]
