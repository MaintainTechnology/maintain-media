"""Durable, bounded official ABR observations; this lane never qualifies leads.

Full files remain private artifacts. A first coherent publication is a baseline,
and only later complete publications produce changes. Publication authority is
checked before network calls, throughout parsing, and in the commit transaction.
"""
from __future__ import annotations

import re
import shutil
import time
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import httpx
import psutil
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from abr_engine import __version__
from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import gate_reasons
from abr_engine.control.service import DomainError, Service, digest, json_safe
from abr_engine.db import lock, transaction
from abr_engine.diff.events import diff_snapshots
from abr_engine.ingest.abr_download import ArchiveResource, download_resource, ingest_archives
from abr_engine.ingest.abr_parse import SCHEMA_VERSION
from abr_engine.ingest.abr_public import PUBLIC_PARSER_VERSION, public_mapping
from abr_engine.ingest.catalogue import CATALOGUES, inspect_catalogue
from abr_engine.ingest.common import SourceError, digest_file
from abr_engine.ops.promotion import declare_artifact, promote, source_lock_key, verify_artifact
from abr_engine.pipeline import _session_lock, process_lock, safe_root

GIB = 1024**3
_RESOURCE = re.compile(
    r"https://data\.gov\.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/"
    r"resource/([0-9a-f-]{36})/download/public_split_([1-9][0-9]{0,2})_([1-9][0-9]{0,2})\.zip"
)
_MEMBER = re.compile(r"([0-9]{8})_Public([0-9]{2,3})\.xml")


class ABRLiveConfig(BaseModel):
    """Only an explicitly reviewed, finite observation scope can be installed."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    operation: Literal["observe_only"]
    source_scope_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime
    max_download_bytes: int = Field(default=2 * GIB, gt=0, le=2 * GIB)
    max_expanded_bytes: int = Field(default=16 * GIB, gt=0, le=16 * GIB)
    max_parquet_bytes: int = Field(default=8 * GIB, gt=0, le=8 * GIB)
    max_event_bytes: int = Field(default=4 * GIB, gt=0, le=4 * GIB)
    max_events: int = Field(default=100_000, ge=0, le=100_000)
    max_working_bytes: int = Field(default=48 * GIB, ge=48 * GIB, le=48 * GIB)
    free_headroom_bytes: int = Field(default=25 * GIB, ge=25 * GIB, le=25 * GIB)
    max_rss_bytes: int = Field(default=2 * GIB, gt=0, le=2 * GIB)
    max_seconds: int = Field(default=21_600, ge=60, le=21_600)


def load_config(settings) -> ABRLiveConfig:
    path = settings.abr_config_file
    if settings.mode not in {"pilot", "production"} or path is None:
        raise SourceError("ABR_LIVE_CONFIGURATION_REQUIRED")
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
            raise ValueError("invalid configuration file")
        for parent in path.parents:
            if parent.is_symlink():
                raise ValueError("symlinked configuration")
        config = ABRLiveConfig.model_validate_json(path.read_bytes())
        if config.expires_at.tzinfo is None:
            raise ValueError("timezone required")
        return config
    except (OSError, ValueError, ValidationError):
        raise SourceError("ABR_LIVE_CONFIGURATION_REQUIRED") from None


def admission_reasons(conn, settings, now, config=None) -> list[str]:
    reasons = gate_reasons(conn, settings, "abr", now)
    if reasons:
        return reasons
    reasons = gate_reasons(conn, settings, "retention", now)
    if reasons:
        return reasons
    try:
        config = config or load_config(settings)
        if not now < config.expires_at:
            return ["ABR_LIVE_CONFIGURATION_EXPIRED"]
        gates = {row["gate_name"]: row for row in conn.execute(
            "SELECT DISTINCT ON(gate_name) * FROM release_gate WHERE environment=%s AND scope='abr' "
            "ORDER BY gate_name,revision DESC", (settings.mode,),
        ).fetchall()}
        if (gates["G1"]["evidence_sha256"] != config.source_scope_evidence_sha256
                or gates["G2"]["evidence_sha256"] != config.mapping_evidence_sha256):
            return ["ABR_EVIDENCE_BINDING_CHANGED"]
        policy = conn.execute("SELECT * FROM policy ORDER BY approved_at DESC,version DESC LIMIT 1").fetchone()
        values = policy["settings"] if policy and isinstance(policy["settings"], dict) else {}
        purpose, retention = values.get("abr", {}), values.get("retention", {})
        if not isinstance(purpose, dict) or not isinstance(retention, dict):
            return ["ABR_OBSERVATION_POLICY_REQUIRED"]
        expiry = datetime.fromisoformat(purpose.get("expires_at", ""))
        retention_gate = conn.execute("SELECT evidence_sha256 FROM release_gate WHERE environment=%s "
            "AND scope='retention' AND gate_name='G1' ORDER BY revision DESC LIMIT 1", (settings.mode,)).fetchone()
        if not (policy and policy["state"] == "approved" and policy["scope"] == settings.mode
                and policy["approved_at"] <= now < policy["expires_at"]
                and policy["evidence_ref"] and policy["actor_id"]
                and purpose.get("approved") is True and purpose.get("operation") == "observe_only"
                and purpose.get("evidence_sha256") == config.source_scope_evidence_sha256
                and purpose.get("classification_enabled") is False
                and expiry.tzinfo is not None and now < expiry <= policy["expires_at"]
                and config.expires_at <= expiry
                and retention.get("approved") is True
                and retention.get("schedule_version") == "abr-v4-defaults"
                and retention_gate and retention.get("evidence_sha256") == retention_gate["evidence_sha256"]
                and retention.get("retain_selected_evidence") is False):
            return ["ABR_OBSERVATION_POLICY_REQUIRED"]
    except SourceError as exc:
        return [exc.code]
    except (ValueError, TypeError, KeyError):
        return ["ABR_OBSERVATION_POLICY_REQUIRED"]
    return []


def publication_resources(metadata: dict) -> list[dict]:
    """Accept only the official dataset's complete, non-overlapping split ranges."""
    output = []
    sequences: set[int] = set()
    if metadata.get("dataset_id") != CATALOGUES["abr"].dataset_id:
        raise SourceError("ABR_RESOURCE_MAPPING_CHANGED")
    for resource in metadata["resources"]:
        match = _RESOURCE.fullmatch(resource["url"])
        if not match or match[1] != resource["resource_id"] or resource["format"] != "ZIP":
            raise SourceError("ABR_RESOURCE_MAPPING_CHANGED")
        start, end = int(match[2]), int(match[3])
        if start > end or end > 999:
            raise SourceError("ABR_RESOURCE_MAPPING_CHANGED")
        members = set(range(start, end + 1))
        if sequences & members:
            raise SourceError("ABR_SEQUENCE_INVENTORY_INVALID")
        sequences |= members
        output.append({**resource, "part_label": f"{start:03}-{end:03}", "sequences": members})
    if not output or sequences != set(range(1, max(sequences) + 1)):
        raise SourceError("ABR_SEQUENCE_INVENTORY_INVALID")
    return sorted(output, key=lambda r: r["part_label"])


class Budget:
    def __init__(self, root, directory, config, *, clock=time.monotonic, run=None):
        self.root, self.directory, self.config = root, directory, config
        self.run = run
        self.clock, self.started = clock, clock()
        self.peak_rss = 0

    def check(self, *, initial=False):
        if self.clock() - self.started > self.config.max_seconds:
            raise SourceError("ABR_RUN_DEADLINE")
        self.peak_rss = max(self.peak_rss, psutil.Process().memory_info().rss)
        if self.peak_rss > self.config.max_rss_bytes:
            raise SourceError("ABR_MEMORY_LIMIT")
        required = self.config.free_headroom_bytes + (self.config.max_working_bytes if initial else 0)
        if shutil.disk_usage(self.root).free < required:
            raise SourceError("ABR_CAPACITY_HEADROOM_REQUIRED")
        from abr_engine.live.abr_cleanup import MAX_ATTEMPTS, MAX_FILES, _namespace, _safe

        directories = [self.directory]
        if self.run is not None:
            entries = self.run['manifest'].get('attempt_namespaces')
            if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ATTEMPTS:
                raise SourceError('ABR_NAMESPACE_INVALID')
            directories = [_namespace(self.root, self.run, entry)[0] for entry in entries]
            if len(set(directories)) != len(directories) or self.directory not in directories:
                raise SourceError('ABR_NAMESPACE_INVALID')
        working_bytes, inspected, sizes = 0, 0, []
        for directory in directories:
            for path in directory.rglob("*"):
                inspected += 1
                if inspected > MAX_ATTEMPTS * MAX_FILES:
                    raise SourceError('ABR_RECONCILIATION_LIMIT')
                try:
                    _safe(path, self.root, directory=path.is_dir())
                    if path.is_file():
                        size = path.stat().st_size
                        working_bytes += size
                        if directory == self.directory:
                            sizes.append((path, size))
                except FileNotFoundError:
                    continue  # The materializer may just have removed a completed part.
                if working_bytes > self.config.max_working_bytes:
                    raise SourceError("ABR_WORKING_STORAGE_LIMIT")
        if sum(size for path, size in sizes if path.name.startswith("records.parquet")) > self.config.max_parquet_bytes:
            raise SourceError("ABR_PARQUET_STORAGE_LIMIT")
        if sum(size for path, size in sizes if path.name == "events.parquet") > self.config.max_event_bytes:
            raise SourceError("ABR_EVENT_STORAGE_LIMIT")


class GuardedTransport(httpx.BaseTransport):
    def __init__(self, transport, authority):
        self.owned = transport is None
        self.transport = transport or httpx.HTTPTransport(retries=0)
        self.authority = authority

    def handle_request(self, request):
        self.authority()
        return self.transport.handle_request(request)

    def close(self):
        # An injected transport belongs to its caller and may serve the next phase.
        if self.owned:
            self.transport.close()


@contextmanager
def _transport_errors():
    try:
        yield
    except httpx.TransportError:
        # The archive downloader owns its five-attempt/validator-aware retry.
        raise OSError("ABR source transport unavailable") from None


class ABRRuntime:
    def __init__(self, settings, *, transport=None, sleep=time.sleep):
        self.settings, self.transport, self.sleep = settings, transport, sleep

    @staticmethod
    def _receipt(row):
        manifest = row["manifest"]
        return json_safe({"job_id": row["run_id"], "run_id": row["run_id"], "source": "abr",
            "state": manifest["phase"] if manifest["phase"] in {"queued", "complete", "held", "failed"} else "running",
            "phase": manifest["phase"],
            "reason_codes": manifest.get("reason_codes", []), "result": manifest.get("result"),
            "started_at": row["started_at"], "finished_at": row["finished_at"]})

    def submit_run(self, payload, actor):
        if self.settings.mode not in {"pilot", "production"}:
            raise DomainError("LIVE_MODE_REQUIRED", 422)
        if not actor.strip() or payload.get("source") != "abr":
            raise DomainError("ABR_SOURCE_REQUIRED", 422)
        request_id = UUID(str(payload.get("request_id") or payload.get("run_id") or uuid4()))
        checksum = digest({"source": "abr", "actor": actor, "request_id": str(request_id)})
        with transaction(self.settings) as conn:
            lock(conn, "abr-job:" + str(request_id))
            prior = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (request_id,)).fetchone()
            if prior:
                if prior["config_digest"] != checksum or prior["manifest"].get("kind") != "abr_live_job":
                    raise DomainError("IDEMPOTENCY_CONFLICT", 409)
                return self._receipt(prior)
            reasons = admission_reasons(conn, self.settings, Service.now(conn))
            manifest = {"kind": "abr_live_job", "source": "abr", "actor": actor,
                        "phase": "held" if reasons else "queued", "reason_codes": reasons, "result": None}
            conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) "
                         "VALUES(%s,%s,%s,%s,%s,%s)",
                         (request_id, self.settings.mode, __version__, checksum,
                          "held" if reasons else "running", Jsonb(manifest)))
            return self._receipt(conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request_id,)).fetchone())

    def get_job(self, job_id):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (UUID(str(job_id)),)).fetchone()
            if not row or row["mode"] != self.settings.mode or row["manifest"].get("kind") != "abr_live_job":
                raise DomainError("NOT_FOUND", 404)
            return self._receipt(row)

    def _record(self, job_id, **updates):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (job_id,)).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", 404)
            manifest = {**row["manifest"], **json_safe(updates)}
            phase = manifest["phase"]
            state = phase if phase in {"complete", "held", "failed"} else "running"
            conn.execute("UPDATE pipeline_run SET manifest=%s,state=%s,heartbeat_at=clock_timestamp(),"
                         "finished_at=CASE WHEN %s='running' THEN NULL ELSE clock_timestamp() END WHERE run_id=%s",
                         (Jsonb(manifest), state, state, job_id))

    def _admit(self, conn, config=None):
        if config is not None and load_config(self.settings) != config:
            raise SourceError("ABR_LIVE_CONFIGURATION_CHANGED")
        reasons = admission_reasons(conn, self.settings, Service.now(conn), config)
        if reasons:
            raise SourceError(reasons[0])
        service = Service(self.settings, load_keys(self.settings))
        service.personal_data_access(conn)
        if config is not None and load_config(self.settings) != config:
            raise SourceError("ABR_LIVE_CONFIGURATION_CHANGED")
        # The control lock prevents approval withdrawal from racing the final commit.
        reasons = admission_reasons(conn, self.settings, Service.now(conn), config)
        if reasons:
            raise SourceError(reasons[0])
        return service

    def _authority(self, config=None):
        current = load_config(self.settings)
        if config is not None and current != config:
            raise SourceError("ABR_LIVE_CONFIGURATION_CHANGED")
        with transaction(self.settings) as conn:
            conn.execute("SET LOCAL lock_timeout='2s'")
            conn.execute("SET LOCAL statement_timeout='5s'")
            self._admit(conn, current)
        return current

    def execute_job(self, job_id):
        job_id = UUID(str(job_id))
        initial = self.get_job(job_id)
        if initial["state"] in {"complete", "held", "failed"}:
            return initial
        # A process may die after the database commit but before its final receipt.
        # Recover that committed fact even when acquisition has since been withdrawn.
        with transaction(self.settings) as conn:
            saved_row = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (job_id,)).fetchone()
            if not saved_row:
                raise DomainError("NOT_FOUND", 404)
            saved = saved_row["manifest"]
        if saved.get("promotion_results", {}).get("abr") and saved.get("prepared"):
            result = self._result(saved["promotion_results"]["abr"], saved["prepared"]["manifest"])
            self._record(job_id, phase="complete", result=result, reason_codes=[])
            return self.get_job(job_id)
        try:
            config = self._authority()
            root = safe_root(self.settings)
            with (process_lock(root / "abr-live-worker.lock"),
                  _session_lock(self.settings, source_lock_key("abr-live-worker", self.settings.schema_name))):
                with transaction(self.settings) as conn:
                    row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (job_id,)).fetchone()
                    if not row:
                        raise DomainError("NOT_FOUND", 404)
                    manifest = row["manifest"]
                if manifest["phase"] in {"held", "failed", "complete"}:
                    return self._receipt(row)
                if manifest.get("prepared"):
                    result = self._commit(job_id, manifest["prepared"], config)
                else:
                    result = self._collect(job_id, root, config)
                self._record(job_id, phase="complete", result=result, reason_codes=[])
        except (DomainError, SourceError) as exc:
            if exc.code in {"SOURCE_STAGE_LOCK_BUSY", "PROCESS_STAGE_LOCK_BUSY"}:
                return self.get_job(job_id)
            self._record(job_id, phase="held", reason_codes=[exc.code])
        except Exception:  # noqa: BLE001 -- never log raw provider/database/private paths.
            self._record(job_id, phase="failed", reason_codes=["ABR_JOB_FAILED"])
        return self.get_job(job_id)

    def _collect(self, job_id, root, config):
        from abr_engine.live.abr_cleanup import reserve_attempt

        directory = reserve_attempt(self.settings, job_id, root)
        budget = self._budget(job_id, root, directory, config)
        budget.check(initial=True)
        def guard():
            budget.check()
            self._authority(config)
        last_check = 0.0
        def analytical_check():
            nonlocal last_check
            budget.check()
            if time.monotonic() - last_check >= 2:
                self._authority(config)
                last_check = time.monotonic()
        transport = GuardedTransport(self.transport, guard)
        self._record(job_id, phase="discovering")
        before = inspect_catalogue("abr", transport=transport, sleep=self.sleep)
        resources = publication_resources(before)
        with transaction(self.settings) as conn:
            cursor = conn.execute("SELECT c.*,s.manifest FROM source_cursor c LEFT JOIN source_snapshot s "
                                  "USING(snapshot_id) WHERE c.source='abr'").fetchone()
            expected_version = cursor["version"] if cursor else 0
            prior = cursor["manifest"] if cursor and cursor["snapshot_id"] else None
        previous = [Path(p) for p in prior["parquet_paths"]] if prior else None
        if previous and any(not path.is_file() for path in previous):
            raise SourceError("PRIOR_ARTIFACT_EXPIRED_REBASELINE_REQUIRED")
        known_sizes = [r["declared_size"] for r in resources if r["declared_size"] is not None]
        if sum(known_sizes) > config.max_download_bytes:
            raise SourceError("DOWNLOAD_SIZE_LIMIT")
        archives: list[ArchiveResource] = []
        receipts: list[dict] = []
        declared: list[Path] = []
        self._record(job_id, phase="downloading")
        for index, resource in enumerate(resources):
            raw = directory / f"resource-{index}.zip"
            with transaction(self.settings) as conn:
                declare_artifact(conn, job_id, "abr", raw, artifact_class="raw")
                declare_artifact(conn, job_id, "abr", raw.with_suffix(".zip.partial"), artifact_class="raw")
            observed: dict[str, str | None] = {}
            @contextmanager
            def download_transport(url, *, headers, connect_timeout, read_timeout, resource=resource, observed=observed):
                if url != resource["url"]:
                    raise SourceError("ABR_RESOURCE_MAPPING_CHANGED")
                guard()
                with _transport_errors(), httpx.Client(transport=transport, follow_redirects=False, trust_env=False,  # noqa: SIM117
                                  timeout=httpx.Timeout(read_timeout, connect=connect_timeout)) as client:
                    with client.stream("GET", url, headers={**headers, "User-Agent": "MaintainMedia-ABNEngine/1.0"}) as response:
                        if response.status_code in {429, 500, 502, 503, 504}:
                            raise OSError("ABR source temporarily unavailable")
                        if response.status_code not in {200, 206}:
                            raise SourceError("ABR_SOURCE_HTTP_REJECTED")
                        observed.update({"etag": response.headers.get("etag"),
                                         "last_modified": response.headers.get("last-modified")})
                        class BoundedResponse:
                            status_code = response.status_code
                            headers = response.headers
                            def iter_bytes(self):
                                checked = time.monotonic()
                                for block in response.iter_bytes(1024 * 1024):
                                    budget.check()
                                    if time.monotonic() - checked >= 10:
                                        guard()
                                        checked = time.monotonic()
                                    yield block
                                guard()
                        yield BoundedResponse()
            remaining = config.max_download_bytes - sum(r["byte_count"] for r in receipts)
            try:
                download_resource(resource["url"], raw, transport=download_transport, max_bytes=remaining,
                                  sleep=self.sleep, jitter=lambda: 0)
            finally:
                for path in (raw, raw.with_suffix(".zip.partial")):
                    if path.is_file():
                        with transaction(self.settings) as conn:
                            verify_artifact(conn, job_id, "abr", path, check=analytical_check)
            receipt = {"resource_id": resource["resource_id"], "source_url": resource["url"],
                       "byte_count": raw.stat().st_size, "sha256": digest_file(raw, check=analytical_check), **observed}
            receipts.append(receipt)
            if resource["declared_size"] is not None and raw.stat().st_size != resource["declared_size"]:
                raise SourceError("DOWNLOAD_LENGTH_MISMATCH")
            names = {}
            with zipfile.ZipFile(raw) as archive_file:
                infos = archive_file.infolist()
                sequences = set()
                for member_index, info in enumerate(infos):
                    match = _MEMBER.fullmatch(info.filename)
                    if not match or int(match[2]) not in resource["sequences"] or int(match[2]) in sequences:
                        raise SourceError("ABR_MEMBER_MAPPING_CHANGED")
                    sequences.add(int(match[2]))
                    names[info.filename] = f"Public{int(match[2]):03}"
                    member_dir = directory / "work" / f"resource-{index}" / f"member-{member_index}"
                    for name in ("source.xml", "records.parquet", "records.parquet.writing", "uniqueness.sqlite", "uniqueness.sqlite-journal"):
                        declared.append(member_dir / name)
                if sequences != resource["sequences"]:
                    raise SourceError("INCOMPLETE_PART_INVENTORY")
            archives.append(ArchiveResource(resource["resource_id"], resource["part_label"], raw, names,
                resource_url=resource["url"], etag=observed.get("etag"), last_modified=observed.get("last_modified"),
                declared_size=receipt["byte_count"]))
        self._record(job_id, phase="validating")
        after = inspect_catalogue("abr", transport=transport, sleep=self.sleep)
        publication_resources(after)
        if before["resource_inventory_sha256"] != after["resource_inventory_sha256"]:
            raise SourceError("INVENTORY_CHANGED_DURING_DOWNLOAD")
        # Revalidate bytes' publisher validators after all transfers, not catalogue alone.
        for archive in archives:
            guard()
            assert archive.resource_url is not None
            with httpx.Client(transport=transport, follow_redirects=False, trust_env=False, timeout=20) as client:
                response = client.head(archive.resource_url, headers={"Accept-Encoding": "identity"})
                if (response.status_code != 200 or response.headers.get("etag") != archive.etag
                        or response.headers.get("last-modified") != archive.last_modified
                        or response.headers.get("content-length") != str(archive.declared_size)
                        or not (archive.etag or archive.last_modified)):
                    raise SourceError("ABR_RESOURCE_REVALIDATION_FAILED")
        events = directory / "events.parquet"
        declared.append(events)
        with transaction(self.settings) as conn:
            for path in declared:
                declare_artifact(conn, job_id, "abr", path)
        inventory = [{"resource_id": a.resource_id, "part_label": a.part_label, "etag": a.etag,
                      "last_modified": a.last_modified, "declared_size": a.declared_size} for a in archives]
        self._record(job_id, phase="parsing")
        last_progress = 0.0
        def progress(values):
            nonlocal last_progress
            if time.monotonic() - last_progress >= 20:
                self._record(job_id, phase="parsing", progress={"member_records": values["record_count"]})
                last_progress = time.monotonic()
        try:
            publication = ingest_archives(archives, directory / "work",
                mapping=public_mapping(config.mapping_evidence_sha256), inventory_before=inventory,
                inventory_after=inventory, required_parts={a.part_label for a in archives},
                expected_sequences=set().union(*(r["sequences"] for r in resources)),
                max_uncompressed_bytes=config.max_expanded_bytes, production=True, authority=guard, progress=progress)
            guard()
            paths = [member.parquet_path for member in publication.members]
            snapshot_id, observation_id = uuid4(), uuid4()
            observed_at = datetime.now(UTC)
            self._record(job_id, phase="diffing")
            diff = diff_snapshots(previous, paths, events, snapshot_id=str(snapshot_id), observed_at=observed_at,
                previous_snapshot_id=str(cursor["snapshot_id"]) if cursor and cursor["snapshot_id"] else None, threads=2,
                authority=guard, check=analytical_check, max_events=config.max_events,
                max_output_bytes=config.max_event_bytes)
            if diff.event_count > config.max_events:
                raise SourceError("ABR_EVENT_COUNT_LIMIT")
            guard()
            manifest = {**publication.manifest, "snapshot_id": str(snapshot_id), "observation_id": str(observation_id),
                "observed_at": observed_at.isoformat(), "schema_version": SCHEMA_VERSION, "parser_version": PUBLIC_PARSER_VERSION,
                "observation_kind": "publisher_revalidation", "approved_mapping_evidence": config.mapping_evidence_sha256,
                "inventory_before_digest": before["resource_inventory_sha256"], "inventory_after_digest": after["resource_inventory_sha256"],
                "publisher_revalidation_evidence": digest({"before": before, "after": after, "receipts": receipts}),
                "publisher_metadata": {"before": before, "after": after}, "download_receipts": receipts,
                "publisher_extract_time": publication.manifest["extract_time"],
                "source_published_at": (datetime.fromisoformat(publication.manifest["extract_time"]).isoformat()
                    if datetime.fromisoformat(publication.manifest["extract_time"]).tzinfo is not None else None),
                "record_count": sum(member.row_count for member in publication.members),
                "baseline": prior is None, "classification": "disabled", "candidate_mode": "observe_only"}
            prepared = {"manifest": manifest, "parquet_paths": [str(p) for p in paths], "events_path": str(events),
                        "expected_version": expected_version, "config_digest": digest(config.model_dump(mode="json"))}
        finally:
            for path in declared:
                if path.is_file():
                    with transaction(self.settings) as conn:
                        verify_artifact(conn, job_id, "abr", path, check=analytical_check)
        self._record(job_id, phase="promoting", prepared=prepared)
        return self._commit(job_id, prepared, config, budget=budget)

    def _commit(self, job_id, prepared, config, *, budget=None):
        from abr_engine.ops.abr_analysis import prepare_analysis

        self._authority(config)
        if prepared["config_digest"] != digest(config.model_dump(mode="json")):
            raise SourceError("ABR_LIVE_CONFIGURATION_CHANGED")
        manifest = prepared["manifest"]
        root = safe_root(self.settings)
        budget = budget or self._budget(job_id, root, Path(prepared["events_path"]).parent, config)
        last_authority = 0.0
        def check():
            nonlocal last_authority
            budget.check()
            if time.monotonic() - last_authority >= 2:
                self._authority(config)
                last_authority = time.monotonic()
        check()
        # No control-authority lock is held while scanning millions of rows.
        service = Service(self.settings, load_keys(self.settings))
        with transaction(self.settings) as conn:
            analysis = prepare_analysis(conn, service, job_id, manifest,
                [Path(p) for p in prepared["parquet_paths"]], Path(prepared["events_path"]),
                prepared["expected_version"], check=check)
        with transaction(self.settings) as conn:
            result = promote(conn, service, job_id, "abr", manifest,
                [Path(p) for p in prepared["parquet_paths"]], Path(prepared["events_path"]),
                expected_version=prepared["expected_version"], candidate_mode="observe_only", analysis=analysis,
                final_authority=lambda connection: self._admit(connection, config),
                analysis_check=check, local_check=budget.check)
            if not result["noop"]:
                conn.execute("UPDATE artifact_manifest SET state='referenced',snapshot_id=%s "
                             "WHERE run_id=%s AND source='abr' AND state='verified'",
                             (result["snapshot_id"], job_id))
            return self._result(result, manifest)

    @staticmethod
    def _result(result, manifest):
        return {**result, "baseline": manifest["baseline"], "classification": "disabled",
                "record_count": manifest["record_count"], "source_published_at": manifest["source_published_at"],
                "publisher_extract_time": manifest["publisher_extract_time"]}

    def _budget(self, job_id, root, directory, config):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT run_id,started_at,manifest,clock_timestamp() observed_at FROM pipeline_run WHERE run_id=%s", (job_id,)).fetchone()
        if not row:
            raise DomainError("NOT_FOUND", 404)
        budget = Budget(root, directory, config, run=row)
        budget.started -= max(0, (row['observed_at'] - row['started_at']).total_seconds())
        return budget

    def execute_pending(self, limit=1):
        if limit != 1:
            raise DomainError("INVALID_JOB_LIMIT")
        with transaction(self.settings) as conn:
            jobs = conn.execute("SELECT run_id FROM pipeline_run WHERE mode=%s AND manifest->>'kind'='abr_live_job' "
                "AND state='running' AND (manifest->>'phase'='queued' OR heartbeat_at<%s) "
                "ORDER BY started_at,run_id LIMIT 1", (self.settings.mode, Service.now(conn) - timedelta(minutes=5))).fetchall()
        return [self.execute_job(row["run_id"]) for row in jobs]
