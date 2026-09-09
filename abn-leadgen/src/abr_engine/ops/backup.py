"""Bounded native PostgreSQL fixture drill; production recovery remains approval-gated."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from cryptography.fernet import Fernet
from psycopg import sql

from abr_engine.compliance.keys import load_stored_keys
from abr_engine.compliance.retention import erase_profile, export_ledger, replay_ledger, restore_quarantine
from abr_engine.config import ROOT
from abr_engine.control.service import DomainError, Service
from abr_engine.db import connect, migrate
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.promotion import declare_artifact, verify_artifact
from abr_engine.pipeline import safe_root

MAX_DUMP_BYTES = 64 * 1024 * 1024


def _native(binary: Path, name: str, *args, background=False):
    executable = binary / (name + (".exe" if os.name == "nt" else ""))
    if not executable.is_file():
        raise DomainError("POSTGRES_NATIVE_RUNTIME_UNAVAILABLE", 503)
    env = {**os.environ, "PGPASSWORD": "abr_fixture", "PGCONNECT_TIMEOUT": "5"}
    try:
        result = subprocess.run([str(executable), *map(str, args)], env=env, shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL if background else subprocess.PIPE,
            stderr=subprocess.DEVNULL if background else subprocess.PIPE, timeout=45, check=False)
    except subprocess.TimeoutExpired:
        raise DomainError("POSTGRES_NATIVE_TIMEOUT", 503) from None
    if result.returncode:
        # Database diagnostics can contain values; expose only the bounded operation name.
        raise DomainError("POSTGRES_NATIVE_FAILED_" + name.upper(), 503)
    return result.stdout


def _write(path: Path, content: bytes):
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def run_fixture_drill(settings, service, *, binary: Path | None = None) -> dict:
    """Own fresh source schema and fresh loopback cluster; never restore over an existing DB."""
    if settings.mode != "fixture" or service.settings.mode != "fixture":
        raise DomainError("LIVE_BACKUP_RESTORE_APPROVAL_PENDING", 409)
    if binary is None:
        configured_binary = os.environ.get("ABR_FIXTURE_PG_BIN")
        binary = Path(configured_binary) if configured_binary else ROOT / ".runtime/pgsql/bin"
    if not binary.is_absolute():
        raise DomainError("POSTGRES_NATIVE_PATH_MUST_BE_ABSOLUTE")
    version = _native(binary, "pg_dump", "--version").decode()
    if " 16." not in version:
        raise DomainError("POSTGRES_16_REQUIRED")
    drill_id = uuid4()
    root = safe_root(settings)
    work = (root / "backup-drills" / str(drill_id)).resolve()
    if not work.is_relative_to(root) or work == root:
        raise DomainError("BACKUP_PATH_OUTSIDE_STORAGE")
    work.mkdir(parents=True, exist_ok=False)
    schema = "abr_test_" + uuid4().hex
    source_settings = settings.model_copy(update={"schema_name": schema})
    keys = copy.deepcopy(service.keys)
    keys.path = None
    source_service = Service(source_settings, keys)
    data = work / "cluster"
    plain = work / "snapshot.dump"
    encrypted_path = work / "snapshot.dump.fernet"
    ledger_path = work / "latest-ledger.fernet"
    custody = (root / "fixture-key-custody" / str(drill_id)).resolve()
    custody.mkdir(parents=True, exist_ok=False)
    if not custody.is_relative_to(root) or custody.is_relative_to(work):
        raise DomainError("BACKUP_KEY_CUSTODY_PATH_INVALID")
    with connect(settings) as conn:
        conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','native-backup-drill','synthetic-only','running')", (drill_id,))
        for artifact_path in (encrypted_path, ledger_path, work / "latest-ledger-receipt.json", work / "drill-receipt.json"):
            declare_artifact(conn, drill_id, "backup", artifact_path, artifact_class="backup")
    started = False
    source_created = False
    try:
        with connect(settings) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        source_created = True
        migrate(source_settings)
        with connect(source_settings) as conn:
            seed_policy(conn, source_service)
            records = [seed_contact(conn, source_service, alias=str(80000001 + i)) for i in range(5)]
            source_service.suppress(conn, {"lead_id": records[1]["lead"]["lead_id"], "reason": "unsubscribe", "source": "before-backup-fixture"}, "fixture", uuid4())
            conn.execute("UPDATE lead_entity SET last_qualifying_at=clock_timestamp()-interval '181 days' WHERE lead_id=%s", (records[4]["lead"]["lead_id"],))
        parsed = urlparse(source_settings.database_url)
        _native(binary, "pg_dump", "-h", parsed.hostname, "-p", parsed.port or 5432,
            "-U", "abr_fixture", "-d", "abr_fixture", "--schema", schema,
            "--format=custom", "--no-owner", "--no-acl", "--file", plain)
        if plain.stat().st_size > MAX_DUMP_BYTES:
            raise DomainError("FIXTURE_DUMP_TOO_LARGE")
        dump_bytes = plain.read_bytes()
        _write(encrypted_path, Fernet(keys.encryption_key).encrypt(dump_bytes))
        plain.unlink()
        with connect(source_settings) as conn:
            for index in (2, 3):
                source_service.suppress(conn, {"lead_id": records[index]["lead"]["lead_id"], "reason": "unsubscribe", "source": "after-backup-fixture"}, "fixture", uuid4())
            erase_profile(conn, source_service, records[3]["lead"]["group_id"])
            keys.rotate(max(keys.lookup_keys) + 1, os.urandom(32), conn=conn)
            ledger = export_ledger(conn, source_service)
        wrapping_path = custody / "fixture-wrapping-key"
        _write(wrapping_path, Fernet.generate_key())
        keys.wrapping_key = wrapping_path.read_bytes()
        keys.save(custody / "keys.fernet")
        keys = load_stored_keys(custody / "keys.fernet", wrapping_key=wrapping_path.read_bytes())
        _write(ledger_path, ledger.encode())
        watermark = json.loads(keys.decrypt(ledger))["exported_at"]
        ledger_digest = hashlib.sha256(ledger.encode()).hexdigest()
        # Trust material is kept outside the PostgreSQL dump and never written into this receipt.
        _write(work / "latest-ledger-receipt.json", json.dumps({"sha256": ledger_digest, "watermark": watermark}).encode())
        password = work / "fixture-password"
        _write(password, b"abr_fixture\n")
        try:
            _native(binary, "initdb", "-D", data, "-U", "abr_fixture", "--pwfile", password,
                "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C")
        finally:
            password.unlink(missing_ok=True)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with (data / "postgresql.conf").open("a") as stream:
            stream.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nmax_connections=10\nshared_buffers='32MB'\n")
        started = True
        _native(binary, "pg_ctl", "-D", data, "-l", work / "postgres.log", "-w", "start", background=True)
        _native(binary, "createdb", "-h", "127.0.0.1", "-p", port, "-U", "abr_fixture", "abr_fixture")
        # Restore only into the fresh cluster which no application is configured to access.
        _write(plain, Fernet(keys.encryption_key).decrypt(encrypted_path.read_bytes()))
        try:
            _native(binary, "pg_restore", "-h", "127.0.0.1", "-p", port, "-U", "abr_fixture",
                "-d", "abr_fixture", "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction", plain)
        finally:
            plain.unlink(missing_ok=True)
        restored_settings = source_settings.model_copy(update={"database_url": f"postgresql://abr_fixture:abr_fixture@127.0.0.1:{port}/abr_fixture"})
        # Revalidate URL restrictions after constructing the fresh-cluster settings.
        restored_settings = type(settings).model_validate(restored_settings.model_dump())
        restored_service = Service(restored_settings, keys)
        with connect(restored_settings) as conn:
            restore_quarantine(conn)
        with connect(restored_settings) as conn:
            restore_result = replay_ledger(conn, restored_service, ledger_path.read_text(),
                expected_digest=ledger_digest, latest_watermark=watermark)
            quarantine = conn.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()
            if not quarantine or not quarantine["value"]:
                raise DomainError("RESTORE_QUARANTINE_LOST")
            if "AUTHORITY_QUARANTINED" not in restored_service.gate(conn, records[0]["contact"]["contact_id"])["reason_codes"]:
                raise DomainError("RESTORE_ACTION_NOT_QUARANTINED")
            for index in (1, 2, 3):
                if "SUPPRESSED_UNSUBSCRIBE" not in restored_service.restricted(conn, records[index]["lead"]["group_id"]):
                    raise DomainError("RESTORE_RESTRICTION_LOST")
                alias = str(80000001 + index)
                try:
                    restored_service.create_lead(conn, name="Restored fixture", source="qbcc", alias=alias)
                except DomainError as exc:
                    if exc.code != "SUPPRESSED_SOURCE_IDENTITY":
                        raise
                else:
                    raise DomainError("RESTORE_ALIAS_STOP_LOST")
            for index in (3, 4):
                if conn.execute("SELECT 1 FROM lead_entity WHERE lead_id=%s", (records[index]["lead"]["lead_id"],)).fetchone():
                    raise DomainError("RESTORE_ERASURE_INCOMPLETE")
        result = {"status": "fixture_drill_complete", "drill_id": str(drill_id),
            "postgres": version.strip(), "dump_bytes": len(dump_bytes), "backup_path": str(encrypted_path),
            "ledger_path": str(ledger_path), "restore": restore_result,
            "checks": {"pre_backup_optout": True, "post_backup_optout": True, "erasure_tombstone": True,
                "overdue_retention": True, "prior_lookup_version_matching": True, "persistent_key_reload": True, "outbound_quarantine": True},
            "fixture_key_custody": str(custody),
            "external_backup_expiry_and_release": "pending", "production_gate": "closed"}
        _write(work / "drill-receipt.json", json.dumps(result, default=str, indent=2).encode())
        with connect(settings) as conn:
            for artifact_path in (encrypted_path, ledger_path, work / "latest-ledger-receipt.json", work / "drill-receipt.json"):
                row = verify_artifact(conn, drill_id, "backup", artifact_path)
                conn.execute("UPDATE artifact_manifest SET state='referenced' WHERE artifact_id=%s", (row["artifact_id"],))
            conn.execute("UPDATE pipeline_run SET state='complete',finished_at=clock_timestamp() WHERE run_id=%s", (drill_id,))
        return result
    except Exception:
        with connect(settings) as conn:
            conn.execute("UPDATE pipeline_run SET state='failed',finished_at=clock_timestamp() WHERE run_id=%s", (drill_id,))
        raise
    finally:
        plain.unlink(missing_ok=True)
        if started:
            _native(binary, "pg_ctl", "-D", data, "-w", "stop", "-m", "fast", background=True)
        if data.exists():
            resolved = data.resolve()
            if resolved.parent != work or not work.is_relative_to(root):
                raise DomainError("BACKUP_CLEANUP_PATH_INVALID")
            shutil.rmtree(resolved)
        if source_created:
            assert schema.startswith("abr_test_") and len(schema) == 41
            with connect(settings) as conn:
                conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
