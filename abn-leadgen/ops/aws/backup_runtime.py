"""Real bounded native PostgreSQL/artifact backups and independent ledger publishing.

This module never approves a policy or provisions storage. Its caller supplies an
approved, current, non-secret contract and an already installed private provider.
Only the backup recipient public key is present on the source server.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast
from uuid import UUID, uuid4

from backup_crypto import BackupError, EncryptWriter, fingerprint
from backup_store import file_digest
from psycopg.conninfo import conninfo_to_dict
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from abr_engine.compliance.policy import current_gate_evidence, gate_reasons
from abr_engine.compliance.retention import _execute_gate, export_ledger
from abr_engine.db import connect
from abr_engine.ops import backup_queue


class BackupAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment_id: UUID
    record_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checked_at: AwareDatetime
    expires_at: AwareDatetime
    recipient_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    key_custody_record_id: UUID
    maximum_bytes: int = Field(default=100 * 1024**3, gt=0, le=100 * 1024**3)

    def validate_current(self, recipient):
        now = datetime.now(UTC)
        if (not self.checked_at <= now < self.expires_at or fingerprint(recipient) != self.recipient_sha256
                or self.record_id == self.key_custody_record_id):
            raise BackupError("BACKUP_AUTHORITY_OR_KEY_CUSTODY_INVALID")


class BackupPolicyBinding(BaseModel):
    """The owner's recorded policy binds referenced evidence to this exact destination."""
    model_config = ConfigDict(extra="forbid", strict=True)
    approved: Literal[True]
    deployment_id: UUID
    record_id: UUID
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    key_custody_record_id: UUID
    key_custody_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipient_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    account_id: str = Field(pattern=r"^[0-9]{12}$")
    bucket: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
    country: Literal["AU"]
    region: Literal["ap-southeast-2"]
    maximum_bytes: int = Field(gt=0, le=100_000_000_000)


def recorded_authority(conn, service, authority, recipient, store):
    if service.settings.mode == "fixture":
        return  # Isolated engineering data/provider stand-ins never establish live approvals.
    now = service.now(conn)
    reasons = gate_reasons(conn, service.settings, "backup", now)
    if reasons:
        raise BackupError("BACKUP_" + reasons[0])
    policy = service.current_policy(conn)
    if (not policy or policy["scope"] != service.settings.mode or policy["state"] != "approved"
            or not policy["approved_at"] <= now < policy["expires_at"]
            or not str(policy["actor_id"]).strip() or not str(policy["evidence_ref"]).strip()):
        raise BackupError("BACKUP_RECORDED_POLICY_REQUIRED")
    try:
        raw = policy["settings"].get("backup")
        if not isinstance(raw, dict) or raw.get("approved") is not True:
            raise ValueError("Explicit recorded approval required")
        binding = BackupPolicyBinding.model_validate_json(json.dumps(raw))
    except ValueError:
        raise BackupError("BACKUP_RECORDED_POLICY_REQUIRED") from None
    if (binding.deployment_id != authority.deployment_id or binding.record_id != authority.record_id
            or binding.evidence_sha256 != authority.sha256
            or binding.key_custody_record_id != authority.key_custody_record_id
            or binding.recipient_sha256 != authority.recipient_sha256
            or binding.recipient_sha256 != fingerprint(recipient)
            or binding.account_id != getattr(store, "account_id", None)
            or binding.bucket != getattr(store, "bucket", None)
            or binding.region != getattr(store, "region", None) or binding.country != getattr(store, "country", None)
            or store.maximum_bytes > binding.maximum_bytes or authority.maximum_bytes > binding.maximum_bytes):
        raise BackupError("BACKUP_RECORDED_TARGET_OR_CUSTODY_MISMATCH")
    rows = {row["gate_name"]: row for row in conn.execute(
        "SELECT DISTINCT ON (gate_name) * FROM release_gate WHERE environment=%s AND scope='backup' "
        "ORDER BY gate_name,revision DESC", (service.settings.mode,)).fetchall()}
    references = {
        "G1": (str(authority.record_id), authority.sha256),
        "G3": (policy["evidence_ref"], policy["settings"].get("retention", {}).get("evidence_sha256")),
        "G7": (str(authority.key_custody_record_id), binding.key_custody_sha256),
    }
    for name, (reference, checksum) in references.items():
        row = rows.get(name)
        if (not row or not current_gate_evidence(row, now) or not str(row["actor_id"]).strip()
                or row["evidence_ref"] != reference or row["evidence_sha256"] != checksum
                or authority.expires_at > row["expires_at"]):
            raise BackupError("BACKUP_" + name + "_EXACT_EVIDENCE_REQUIRED")
    if authority.expires_at > policy["expires_at"]:
        raise BackupError("BACKUP_AUTHORITY_OUTLIVES_RECORDED_POLICY")


def _admit(settings, service, authority, recipient, store, *, restoring=False):
    authority.validate_current(recipient)
    if store.prefix != f"abn-backup/{authority.deployment_id}/" or store.maximum_bytes > authority.maximum_bytes:
        raise BackupError("BACKUP_DEPLOYMENT_OR_CAP_MISMATCH")
    with connect(settings) as conn:
        _execute_gate(conn, service, restoring=restoring)
        service.authority(conn)
        recorded_authority(conn, service, authority, recipient, store)
    store.validate()


def private_work(root: Path) -> Path:
    if not root.is_absolute() or not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise BackupError("BACKUP_PRIVATE_STAGING_ROOT_REQUIRED")
    if os.name != "nt" and root.stat().st_mode & 0o077:
        raise BackupError("BACKUP_STAGING_PERMISSIONS_INVALID")
    work = root / str(uuid4())
    work.mkdir(mode=0o700, exist_ok=False)
    return work


def _new_file(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def _pg_env(database_url):
    parsed = conninfo_to_dict(database_url)
    # Do not inherit a different database, service file, arbitrary libpq options,
    # password passfile or the host's command-line environment overrides.
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    names = {"host": "PGHOST", "hostaddr": "PGHOSTADDR", "port": "PGPORT", "dbname": "PGDATABASE",
             "user": "PGUSER", "password": "PGPASSWORD", "sslmode": "PGSSLMODE",
             "sslrootcert": "PGSSLROOTCERT"}
    if set(parsed) - names.keys():
        raise BackupError("BACKUP_LIBPQ_CONFIGURATION_UNSUPPORTED")
    env.update({names[k]: str(v) for k, v in parsed.items() if v is not None})
    env.update(PGCONNECT_TIMEOUT="5", PGOPTIONS="-c statement_timeout=240000")
    return env


def native(binary, operation, *args, env=None, timeout=300):
    executable = Path(binary) / (operation + (".exe" if os.name == "nt" else ""))
    if not executable.is_absolute() or not executable.is_file():
        raise BackupError("BACKUP_POSTGRES_RUNTIME_REQUIRED")
    try:
        result = subprocess.run([str(executable), *map(str, args)], env=env,
            stdout=subprocess.DEVNULL if operation == "pg_ctl" else subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=timeout, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired):
        raise BackupError("BACKUP_NATIVE_OPERATION_FAILED") from None
    if result.returncode:
        raise BackupError("BACKUP_NATIVE_OPERATION_FAILED")
    return result.stdout or b""


def dump_encrypted(settings, binary, snapshot, destination, recipient, maximum):
    if b" 16." not in native(binary, "pg_dump", "--version"):
        raise BackupError("BACKUP_POSTGRES_16_REQUIRED")
    executable = Path(binary) / ("pg_dump.exe" if os.name == "nt" else "pg_dump")
    process = subprocess.Popen([str(executable), "--format=custom", "--no-owner", "--no-acl",
        "--schema", settings.schema_name, "--snapshot", snapshot], env=_pg_env(settings.database_url),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    errors = []
    pipe = process.stdout
    assert pipe is not None
    def transfer():
        try:
            with _new_file(destination) as target:
                encrypted = EncryptWriter(target, recipient, maximum=maximum)
                while chunk := pipe.read(1024 * 1024):
                    encrypted.write(chunk)
                encrypted.finish()
        except Exception:  # noqa: BLE001 -- worker must kill the producer without exposing data in diagnostics
            errors.append("BACKUP_DUMP_ENCRYPTION_FAILED")
            process.kill()
    worker = threading.Thread(target=transfer, daemon=True)
    worker.start()
    try:
        process.wait(timeout=300)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        errors.append("BACKUP_DUMP_DEADLINE")
    finally:
        worker.join(timeout=15)
    if process.returncode or errors or worker.is_alive():
        raise BackupError("BACKUP_DATABASE_DUMP_FAILED")


def _artifact_path(root, value):
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or not path.is_relative_to(root) or path == root
        or not path.resolve(strict=True).is_relative_to(root) or path.resolve(strict=True) != path):
        raise BackupError("BACKUP_ARTIFACT_PATH_INVALID")
    for candidate in [root, *reversed(list(path.parents)[:len(path.relative_to(root).parts) - 1]), path]:
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BackupError("BACKUP_LINKED_ARTIFACT_FORBIDDEN")
    relative = path.relative_to(root)
    if any(part.startswith(".env") or re.search(r"(?:^|[._-])(?:keys?|credentials?|secrets?|wrapping)(?:[._-]|$)", part.lower())
           or Path(part).suffix.lower() in {".pem", ".p12", ".pfx", ".jks", ".keystore"} for part in relative.parts):
        raise BackupError("BACKUP_PRIVATE_KEY_PATH_FORBIDDEN")
    if not path.is_file():
        raise BackupError("BACKUP_ARTIFACT_MISSING")
    return path, relative.as_posix()


def artifacts_encrypted(conn, root, destination, recipient, maximum):
    root = root.resolve()
    rows = conn.execute("SELECT local_path,content_digest,byte_count FROM artifact_manifest "
        "WHERE state IN ('verified','referenced') AND artifact_class<>'backup' ORDER BY artifact_id").fetchall()
    entries: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row["local_path"]:
            raise BackupError("BACKUP_ARTIFACT_LOCATION_UNKNOWN")
        path, relative = _artifact_path(root, row["local_path"])
        if path.stat().st_size != row["byte_count"] or file_digest(path) != row["content_digest"]:
            raise BackupError("BACKUP_ARTIFACT_INTEGRITY_MISMATCH")
        entry = {"relative_path": relative, "sha256": row["content_digest"], "bytes": row["byte_count"]}
        if relative in entries and entries[relative] != entry:
            raise BackupError("BACKUP_ARTIFACT_INVENTORY_CONFLICT")
        entries[relative] = entry
    manifest = {"version": 1, "original_root": str(root), "entries": list(entries.values())}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > 16 * 1024**2 or sum(row["bytes"] for row in entries.values()) > maximum:
        raise BackupError("BACKUP_ARTIFACT_CAP_REACHED")
    with _new_file(destination) as target:
        encrypted = EncryptWriter(target, recipient, maximum=maximum)
        # Tar's write-stream mode only calls write/flush; it does not require seeking.
        with tarfile.open(fileobj=cast(BinaryIO, encrypted), mode="w|", format=tarfile.PAX_FORMAT) as archive:
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mode = len(encoded), 0o600
            archive.addfile(info, io.BytesIO(encoded))
            for entry in entries.values():
                path, _ = _artifact_path(root, root / entry["relative_path"])
                info = tarfile.TarInfo("files/" + entry["relative_path"])
                info.size, info.mode = entry["bytes"], 0o600
                checksum = hashlib.sha256()
                class VerifiedReader:
                    def __init__(self, stream, digest):
                        self.stream, self.digest = stream, digest
                    def read(self, count=-1):
                        content = self.stream.read(count)
                        self.digest.update(content)
                        return content
                with path.open("rb") as source:
                    archive.addfile(info, VerifiedReader(source, checksum))
                if checksum.hexdigest() != entry["sha256"] or file_digest(path) != entry["sha256"]:
                    raise BackupError("BACKUP_ARTIFACT_CHANGED_DURING_CAPTURE")
        encrypted.finish()
    return manifest


def _publish_ledger(settings, service, authority, recipient, store, staging_root):
    """Independently replicate current restrictions; failure is a failed receipt.

    Call after committed restrictions/deletions and from the same service timer.
    A success never establishes that a later, unacknowledged commit was replicated.
    """
    _admit(settings, service, authority, recipient, store)
    work = private_work(staging_root)
    path = work / "ledger.enc"
    try:
        with connect(settings) as conn:
            conn.commit()
            conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            generation = backup_queue.state(conn)["generation"]
            # Conservative lower bound on snapshot time, before any control-lock wait.
            snapshot_row = conn.execute("SELECT transaction_timestamp() AS started").fetchone()
            if snapshot_row is None:
                raise BackupError("BACKUP_DATABASE_SNAPSHOT_UNAVAILABLE")
            snapshot_time = snapshot_row["started"]
            ledger = export_ledger(conn, service, exported_at=snapshot_time)
            watermark = json.loads(service.keys.decrypt(ledger))["exported_at"]
        content = ledger.encode()
        if len(content) > 64 * 1024**2:
            raise BackupError("BACKUP_LEDGER_LIMIT")
        with _new_file(path) as target:
            encrypted = EncryptWriter(target, recipient, maximum=64 * 1024**2)
            encrypted.write(content)
            encrypted.finish()
        expires = min(datetime.now(UTC) + timedelta(days=34), authority.expires_at)
        _admit(settings, service, authority, recipient, store)
        component = store.put_verified(uuid4(), path, kind="suppression_erasure_ledger",
            expires_at=expires, ledger_watermark=watermark)
        _admit(settings, service, authority, recipient, store)
        receipt = {**component, "ledger_watermark": watermark, "inner_sha256": hashlib.sha256(content).hexdigest(),
            "captured_generation": generation}
        with connect(settings) as conn:
            backup_queue.acknowledge(conn, generation, receipt)
        return receipt
    finally:
        path.unlink(missing_ok=True)
        work.rmdir()


def _create_backup(settings, service, authority, recipient, store, staging_root, binary):
    _admit(settings, service, authority, recipient, store)
    work = private_work(staging_root)
    paths = [work / "database.enc", work / "artifacts.enc", work / "receipt.enc"]
    expires = min(datetime.now(UTC) + timedelta(days=34), authority.expires_at)
    try:
        with connect(settings) as conn:
            conn.commit()
            conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot_row = conn.execute("SELECT pg_export_snapshot() AS snapshot").fetchone()
            if snapshot_row is None:
                raise BackupError("BACKUP_DATABASE_SNAPSHOT_UNAVAILABLE")
            snapshot = snapshot_row["snapshot"]
            dump_encrypted(settings, binary, snapshot, paths[0], recipient, authority.maximum_bytes)
            artifacts_encrypted(conn, settings.output_dir, paths[1], recipient, authority.maximum_bytes)
        components = []
        for kind, path in zip(("database", "artifacts"), paths[:2], strict=True):
            with publication_lease(staging_root, wait_seconds=120):
                _admit(settings, service, authority, recipient, store)
                components.append(store.put_verified(uuid4(), path, kind=kind, expires_at=expires))
        latest = publish_ledger(settings, service, authority, recipient, store, staging_root, wait_seconds=120)
        components.append({key: latest[key] for key in ("kind", "object_id", "sha256", "encrypted_bytes")})
        completed = datetime.now(UTC)
        if completed - datetime.fromisoformat(latest["ledger_watermark"]) > timedelta(minutes=5):
            raise BackupError("BACKUP_LATEST_LEDGER_TOO_OLD")
        _admit(settings, service, authority, recipient, store)
        receipt = {"schema_version": 1, "deployment_id": str(authority.deployment_id), "backup_id": str(uuid4()),
            "status": "complete", "country": "AU", "encryption": "encrypted_separate_key_custody",
            "completed_at": completed.isoformat(), "expires_at": expires.isoformat(),
            "ledger_watermark": latest["ledger_watermark"], "provider_evidence": {
                "record_id": str(authority.record_id), "sha256": authority.sha256,
                "checked_at": authority.checked_at.isoformat(), "expires_at": authority.expires_at.isoformat()},
            "components": components}
        # Preserve the recovery inventory independently of the primary host too.
        with _new_file(paths[2]) as target:
            encrypted = EncryptWriter(target, recipient, maximum=65536)
            encrypted.write(json.dumps(receipt, sort_keys=True).encode())
            encrypted.finish()
        with publication_lease(staging_root, wait_seconds=120):
            _admit(settings, service, authority, recipient, store)
            store.put_verified(uuid4(), paths[2], kind="receipt", expires_at=expires)
        _admit(settings, service, authority, recipient, store)
        # A receipt is returned only after every real object was uploaded and read back.
        return receipt
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        work.rmdir()


@contextmanager
def publication_lease(staging_root, *, capture=False, wait_seconds=0):
    """One publisher; nonblocking OS lock releases on process death, never unlink its inode."""
    if not staging_root.is_absolute() or not staging_root.is_dir() or staging_root.resolve() != staging_root:
        raise BackupError("BACKUP_PRIVATE_STAGING_ROOT_REQUIRED")
    if (staging_root / "publication.lock").exists():
        # Older releases used an exclusive file, whose owner must first be reconciled.
        raise BackupError("BACKUP_PUBLICATION_BUSY_OR_RECOVERY_REQUIRED") from None
    path = staging_root / ("capture-v2.lock" if capture else "publication-v2.lock")
    if path.is_symlink():
        raise BackupError("BACKUP_PUBLICATION_LOCK_INVALID")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise BackupError("BACKUP_PUBLICATION_LOCK_INVALID")
        if not 0 <= wait_seconds <= 120:
            raise BackupError("BACKUP_LEASE_WAIT_INVALID")
        deadline = time.monotonic() + wait_seconds
        while not locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    if info.st_size == 0:
                        os.write(fd, b"0")
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    native_lock: Any = fcntl
                    native_lock.flock(fd, native_lock.LOCK_EX | native_lock.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise BackupError("BACKUP_CAPTURE_BUSY" if capture else "BACKUP_PUBLICATION_BUSY") from None
                time.sleep(min(0.25, max(0, deadline-time.monotonic())))
        yield
    finally:
        if locked:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                native_lock.flock(fd, native_lock.LOCK_UN)
        os.close(fd)


def publish_ledger(settings, service, authority, recipient, store, staging_root, *, wait_seconds=0):
    with publication_lease(staging_root, wait_seconds=wait_seconds):
        return _publish_ledger(settings, service, authority, recipient, store, staging_root)


def create_backup(settings, service, authority, recipient, store, staging_root, binary):
    # Local dump/capture cannot monopolize the independent restriction publisher.
    # Each provider upload owns the shared lock; one upload is not preemptible.
    with publication_lease(staging_root, capture=True):
        return _create_backup(settings, service, authority, recipient, store, staging_root, binary)


def latest_ledger(store, *, minimum_watermark: str, now=None):
    """Provider inventory is independent of the older database being restored.

    Caller must supply the known acknowledged watermark from incident evidence.
    This cannot prove zero data loss during an unreplicated primary-host failure.
    """
    store.validate()
    now = now or datetime.now(UTC)
    minimum = datetime.fromisoformat(minimum_watermark)
    if minimum.tzinfo is None:
        raise BackupError("BACKUP_CURRENT_LEDGER_WATERMARK_REQUIRED")
    candidates = []
    for item in store.inventory():
        head = store.head(item["object_id"])
        if head and head["kind"] == "suppression_erasure_ledger":
            watermark = datetime.fromisoformat(head["ledger_watermark"])
            expiry = datetime.fromisoformat(head["expires_at"])
            if watermark.tzinfo is None or expiry.tzinfo is None or watermark > now:
                raise BackupError("BACKUP_LEDGER_METADATA_INVALID")
            if expiry > now:
                candidates.append({**head, "object_id": item["object_id"], "watermark": watermark})
    if not candidates or max(row["watermark"] for row in candidates) < minimum:
        raise BackupError("BACKUP_CURRENT_LEDGER_UNAVAILABLE")
    return max(candidates, key=lambda row: (row["watermark"], row["object_id"]))
