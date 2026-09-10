"""Restore into a newly initialized loopback-only, stopped-by-default quarantine.

Never accepts an active database target or opens outbound services. Keys are
supplied by the separate restore custodian, not recovered from the data backup.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import socket
import sys
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from backup_crypto import BackupError, decrypt_stream
from backup_runtime import _admit, _new_file, latest_ledger, native, private_work
from backup_store import file_digest
from psycopg.types.json import Jsonb

from abr_engine.compliance.retention import (
    _RESTORE_RECONCILING,
    artifact_retention,
    replay_ledger,
    restore_quarantine,
)
from abr_engine.control.service import Service
from abr_engine.db import connect


def extract_artifacts(plain, destination, *, maximum):
    """No tar extraction helpers: accept exact regular files from the first manifest."""
    destination.mkdir(mode=0o700, exist_ok=False)
    with tarfile.open(plain, mode="r|") as archive:
        member = archive.next()
        if not member or member.name != "manifest.json" or not member.isfile() or member.size > 16 * 1024**2:
            raise BackupError("RESTORE_ARTIFACT_MANIFEST_REQUIRED")
        manifest_stream = archive.extractfile(member)
        if manifest_stream is None:
            raise BackupError("RESTORE_ARTIFACT_MANIFEST_REQUIRED")
        manifest = json.load(manifest_stream)
        if set(manifest) != {"version", "original_root", "entries"} or manifest["version"] != 1:
            raise BackupError("RESTORE_ARTIFACT_MANIFEST_INVALID")
        expected = {}
        total = 0
        for entry in manifest["entries"]:
            relative = PurePosixPath(entry["relative_path"])
            if (relative.is_absolute() or ".." in relative.parts or not relative.parts or ":" in str(relative)
                or "\\" in str(relative) or relative.as_posix() != entry["relative_path"]
                or entry["relative_path"] in expected or type(entry["bytes"]) is not int or entry["bytes"] < 0):
                raise BackupError("RESTORE_ARTIFACT_PATH_INVALID")
            total += entry["bytes"]
            expected[entry["relative_path"]] = entry
        if total > maximum:
            raise BackupError("RESTORE_ARTIFACT_CAP_REACHED")
        seen = set()
        while member := archive.next():
            relative_name = member.name.removeprefix("files/")
            if member.name != "files/" + relative_name or relative_name not in expected or relative_name in seen or not member.isfile():
                raise BackupError("RESTORE_UNDECLARED_ARTIFACT")
            entry = expected[relative_name]
            if member.size != entry["bytes"]:
                raise BackupError("RESTORE_ARTIFACT_SIZE_MISMATCH")
            target = destination / relative_name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            artifact_stream = archive.extractfile(member)
            if artifact_stream is None:
                raise BackupError("RESTORE_ARTIFACT_MISSING")
            with _new_file(target) as output, artifact_stream as source:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            if file_digest(target) != entry["sha256"]:
                raise BackupError("RESTORE_ARTIFACT_DIGEST_MISMATCH")
            seen.add(relative_name)
        if seen != expected.keys():
            raise BackupError("RESTORE_ARTIFACT_MISSING")
    return manifest


def _remap(conn, original, target):
    original = Path(original)
    if not original.is_absolute() or ".." in original.parts:
        raise BackupError("RESTORE_ORIGINAL_ROOT_INVALID")
    def value(item):
        if isinstance(item, str):
            candidate = Path(item)
            if candidate.is_absolute() and candidate.is_relative_to(original):
                if ".." in candidate.parts:
                    raise BackupError("RESTORE_DATABASE_ARTIFACT_PATH_INVALID")
                remapped = target / candidate.relative_to(original)
                if not remapped.resolve().is_relative_to(target.resolve()):
                    raise BackupError("RESTORE_DATABASE_ARTIFACT_PATH_INVALID")
                return str(remapped)
        if isinstance(item, list):
            return [value(child) for child in item]
        if isinstance(item, dict):
            return {key: value(child) for key, child in item.items()}
        return item
    for row in conn.execute("SELECT artifact_id,local_path FROM artifact_manifest WHERE local_path IS NOT NULL"):
        path = Path(row["local_path"])
        if not path.is_absolute() or not path.is_relative_to(original):
            raise BackupError("RESTORE_DATABASE_ARTIFACT_PATH_INVALID")
        conn.execute("UPDATE artifact_manifest SET local_path=%s WHERE artifact_id=%s", (value(str(path)), row["artifact_id"]))
    for row in conn.execute("SELECT snapshot_id,manifest FROM source_snapshot"):
        conn.execute("UPDATE source_snapshot SET manifest=%s WHERE snapshot_id=%s", (Jsonb(value(row["manifest"])), row["snapshot_id"]))
    for row in conn.execute("SELECT content_id,artifact_ref FROM source_content"):
        try:
            reference = json.loads(row["artifact_ref"])
        except ValueError:
            reference = row["artifact_ref"]
        updated = value(reference)
        conn.execute("UPDATE source_content SET artifact_ref=%s WHERE content_id=%s",
            (json.dumps(updated) if isinstance(updated, (list, dict)) else updated, row["content_id"]))


def restore_backup(settings, keys, authority, private_key, store, receipt, staging_root, binary,
                   *, minimum_ledger_watermark, inspect=None):
    """Actual native restore/replay drill; returned cluster remains stopped and quarantined.

    minimum_ledger_watermark must come from current independent incident evidence.
    A caller callback can inspect the isolated restored connection in tests/drills;
    no activation operation is implemented by this module.
    """
    from importlib.util import module_from_spec, spec_from_file_location
    if inspect is not None and settings.mode != "fixture":
        raise BackupError("RESTORE_INSPECTION_CALLBACK_FIXTURE_ONLY")
    schema = spec_from_file_location("abr_backup_receipt_contract", Path(__file__).parents[1] / "production/prepare.py")
    if schema is None or schema.loader is None:
        raise BackupError("RESTORE_RECEIPT_SCHEMA_UNAVAILABLE")
    module = module_from_spec(schema)
    sys.modules[schema.name] = module
    schema.loader.exec_module(module)
    validated = module.BackupReceipt.model_validate_json(json.dumps(receipt))
    authority.validate_current(private_key.public_key())
    if (validated.deployment_id != authority.deployment_id or not validated.completed_at <= datetime.now(UTC) < validated.expires_at
        or validated.expires_at - validated.completed_at > timedelta(days=35)
        or not validated.provider_evidence.checked_at <= validated.completed_at < validated.provider_evidence.expires_at
        or {row.kind for row in validated.components} != {"database", "artifacts", "suppression_erasure_ledger"}
        or len({row.object_id for row in validated.components}) != 3
        or store.prefix != f"abn-backup/{authority.deployment_id}/"):
        raise BackupError("RESTORE_RECEIPT_INVALID_OR_EXPIRED")
    # Resolve the custodian's current control registry, never authority copied from
    # the historical database being restored. Unavailable current authority holds.
    current_service = Service(settings, keys)
    _admit(settings, current_service, authority, private_key.public_key(), store, restoring=True)
    latest = latest_ledger(store, minimum_watermark=minimum_ledger_watermark)
    if latest["watermark"] < validated.ledger_watermark:
        raise BackupError("RESTORE_LEDGER_PREDATES_BACKUP")
    work = private_work(staging_root)
    cluster, artifacts = work / "cluster", work / "artifacts"
    encrypted_paths, plain_paths = [], []
    started = False
    try:
        objects = {row.kind: row.model_dump(mode="json") for row in validated.components if row.kind != "suppression_erasure_ledger"}
        objects["suppression_erasure_ledger"] = {"object_id": latest["object_id"], "sha256": latest["sha256"], "encrypted_bytes": latest["bytes"]}
        for kind, component in objects.items():
            encrypted, plain = work / (kind + ".enc"), work / (kind + ".plain")
            encrypted_paths.append(encrypted)
            plain_paths.append(plain)
            _admit(settings, current_service, authority, private_key.public_key(), store, restoring=True)
            store.get_verified(component["object_id"], encrypted, component["sha256"], component["encrypted_bytes"])
            with encrypted.open("rb") as source, _new_file(plain) as target:
                decrypt_stream(source, target, private_key,
                    maximum=64 * 1024**2 if kind == "suppression_erasure_ledger" else authority.maximum_bytes)
        manifest = extract_artifacts(work / "artifacts.plain", artifacts, maximum=authority.maximum_bytes)
        password = "abr_fixture" if settings.mode == "fixture" else secrets.token_urlsafe(48)
        username = "abr_fixture" if settings.mode == "fixture" else "abr_restore"
        password_file = work / "init-password"
        with _new_file(password_file) as output:
            output.write(password.encode() + b"\n")
        try:
            native(binary, "initdb", "-D", cluster, "-U", username, "--pwfile", password_file,
                "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C")
        finally:
            password_file.unlink(missing_ok=True)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with (cluster / "postgresql.conf").open("a") as output:
            output.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nmax_connections=10\nshared_buffers='32MB'\n")
        started = True
        native(binary, "pg_ctl", "-D", cluster, "-l", work / "postgres.log", "-w", "start")
        from backup_runtime import _pg_env
        url = f"postgresql://{username}:{password}@127.0.0.1:{port}/{username}"
        env = _pg_env(url)
        native(binary, "createdb", username, env=env)
        native(binary, "pg_restore", "-d", username, "--no-owner", "--no-acl", "--exit-on-error",
            "--single-transaction", work / "database.plain", env=env)
        restored_settings = type(settings).model_validate(settings.model_copy(update={"database_url": url, "output_dir": artifacts}).model_dump())
        restored_service = Service(restored_settings, keys)
        with connect(restored_settings) as conn:
            restore_quarantine(conn)
            _remap(conn, manifest["original_root"], artifacts)
        ledger = (work / "suppression_erasure_ledger.plain").read_text()
        watermark = json.loads(keys.decrypt(ledger))["exported_at"]
        if watermark != latest["ledger_watermark"]:
            raise BackupError("RESTORE_LEDGER_WATERMARK_MISMATCH")
        with connect(restored_settings) as conn:
            result = replay_ledger(conn, restored_service, ledger,
                expected_digest=hashlib.sha256(ledger.encode()).hexdigest(), latest_watermark=watermark)
            token = _RESTORE_RECONCILING.set(True)
            try:
                artifact_result = artifact_retention(conn, restored_service, now=restored_service.now(conn), execute=True)
            finally:
                _RESTORE_RECONCILING.reset(token)
            if any(row["state"] == "held" for row in artifact_result):
                raise BackupError("RESTORE_ARTIFACT_RETENTION_HELD")
            quarantine = conn.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()
            if quarantine is None or quarantine["value"] is not True:
                raise BackupError("RESTORE_QUARANTINE_LOST")
            if inspect:
                inspect(conn, restored_service)
        # Detect a concurrent newer ledger before reporting reconciliation.
        _admit(settings, current_service, authority, private_key.public_key(), store, restoring=True)
        checked = latest_ledger(store, minimum_watermark=watermark)
        if checked["object_id"] != latest["object_id"]:
            raise BackupError("RESTORE_NEWER_LEDGER_REQUIRES_REPLAY")
        return {"status": "restored_quarantined", "work_directory": str(work), "cluster": "stopped",
            "restore_id": str(result["restore_id"]), "ledger_watermark": watermark,
            "backup_id": str(validated.backup_id), "outbound": "quarantined", "release": "owner_review_required"}
    finally:
        try:
            if started:
                native(binary, "pg_ctl", "-D", cluster, "-w", "stop", "-m", "fast")
        finally:
            for path in plain_paths + encrypted_paths:
                path.unlink(missing_ok=True)
