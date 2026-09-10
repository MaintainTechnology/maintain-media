"""Live-mode exact backup approval binding in isolated PG; no provider calls."""
import copy
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb
from test_production_backup_runtime import setup_backup

from abr_engine.compliance.keys import KeyStore
from abr_engine.control.service import DomainError, Service
from abr_engine.db import connect

sys.path.insert(0, str(Path(__file__).parents[2] / "ops/aws"))
import backup_runtime as runtime
from backup_crypto import BackupError
from backup_restore import restore_backup


@pytest.fixture
def live_backup(settings, tmp_path, monkeypatch):
    key, authority, store, staging = setup_backup(tmp_path)
    store.maximum_bytes = authority.maximum_bytes = 100_000_000_000
    store.account_id, store.bucket = "111111111111", "synthetic-backup-policy-test"
    store.region, store.country = "ap-southeast-2", "AU"
    calls = []
    monkeypatch.setattr(store, "validate", lambda: calls.append("provider_validate"))
    keypath = tmp_path / "synthetic-managed-engine-keys.json"
    keys = KeyStore(Fernet.generate_key(), {1: os.urandom(32)}, signing_key=os.urandom(32).hex(),
        path=keypath, wrapping_key=Fernet.generate_key())
    keys.save()
    config = settings.model_copy(update={"mode": "pilot", "database_url": "postgresql://synthetic@localhost/backup_test",
        "capabilities": {"retention": True, "backup": True}, "key_file": keypath})
    service = Service(config, keys)
    monkeypatch.setattr(runtime, "connect", lambda _settings: connect(settings))
    with connect(settings) as conn:
        now = service.now(conn)
        authority.expires_at = now + timedelta(minutes=30)
        binding = {"approved": True, "deployment_id": str(authority.deployment_id),
            "record_id": str(authority.record_id), "evidence_sha256": authority.sha256,
            "key_custody_record_id": str(authority.key_custody_record_id), "key_custody_sha256": "c" * 64,
            "recipient_sha256": authority.recipient_sha256, "account_id": store.account_id,
            "bucket": store.bucket, "country": "AU", "region": "ap-southeast-2", "maximum_bytes": store.maximum_bytes}
        policy = {"retention": {"approved": True, "schedule_version": "abr-v4-defaults",
            "evidence_sha256": "d" * 64, "restore_enabled": True}, "backup": binding}
        conn.execute("INSERT INTO policy VALUES('synthetic-backup-policy','approved','pilot','synthetic-retention-document',"
            "'synthetic-owner',%s,%s,%s)", (now-timedelta(minutes=1), now+timedelta(hours=1), Jsonb(policy)))
        for scope in ("retention", "backup"):
            for gate in ("G1", "G3", "G7"):
                ref, checksum = {
                    "G1": (str(authority.record_id), authority.sha256),
                    "G3": ("synthetic-retention-document", "d" * 64),
                    "G7": (str(authority.key_custody_record_id), "c" * 64),
                }[gate]
                conn.execute("INSERT INTO release_gate VALUES(%s,'pilot',%s,1,%s,%s,'synthetic-owner',%s,%s)",
                    (gate, scope, ref, checksum, now-timedelta(minutes=1), now+timedelta(hours=1)))
    return config, service, key, authority, store, staging, calls, policy


def test_current_exact_registry_binding_permits_real_encrypted_ledger_publication(live_backup):
    config, service, key, authority, store, staging, calls, _ = live_backup
    result = runtime.publish_ledger(config, service, authority, key.public_key(), store, staging)
    assert result["kind"] == "suppression_erasure_ledger" and len(store.objects) == 1
    assert len(calls) >= 3 and {p.name for p in staging.iterdir()} <= {"publication-v2.lock"}
    assert b"suppression_event" not in (store.root / result["object_id"]).read_bytes()


@pytest.mark.parametrize("failure", ["disabled", "missing_gate", "newer_revoked", "wrong_environment", "G1_id", "G1_hash",
    "G3_hash", "G7_id", "G7_hash", "actor", "policy_missing", "policy_withdrawn", "policy_false", "policy_numeric", "policy_extra",
    "policy_bucket", "policy_account", "policy_region", "policy_recipient", "policy_custody", "policy_cap", "authority_expiry"])
def test_missing_revoked_or_mismatched_record_never_reaches_provider(settings, live_backup, failure):
    config, service, key, authority, store, staging, calls, policy = live_backup
    with connect(settings) as conn:
        if failure == "disabled":
            config = config.model_copy(update={"capabilities": {"retention": True}})
            service = Service(config, service.keys)
        elif failure == "missing_gate":
            conn.execute("DELETE FROM release_gate WHERE scope='backup' AND gate_name='G7'")
        elif failure == "newer_revoked":
            conn.execute("INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,actor_id,"
                "approved_at+interval '2 days',expires_at+interval '2 days' FROM release_gate WHERE scope='backup' AND gate_name='G1'")
        elif failure == "wrong_environment":
            conn.execute("UPDATE release_gate SET environment='production' WHERE scope='backup'")
        elif failure.startswith(("G1", "G3", "G7")):
            gate, field = failure.split("_")
            column = "evidence_ref" if field == "id" else "evidence_sha256"
            replacement = str(uuid4()) if field == "id" else "e" * 64
            conn.execute("UPDATE release_gate SET " + column + "=%s WHERE scope='backup' AND gate_name=%s", (replacement, gate))
        elif failure == "actor":
            conn.execute("UPDATE release_gate SET actor_id='' WHERE scope='backup' AND gate_name='G7'")
        elif failure == "policy_withdrawn":
            conn.execute("UPDATE policy SET state='withdrawn'")
        elif failure == "authority_expiry":
            authority.expires_at += timedelta(days=2)
        else:
            revised = copy.deepcopy(policy)
            if failure == "policy_missing":
                del revised["backup"]
            else:
                field, replacement = {
                    "policy_false": ("approved", False), "policy_numeric": ("approved", 1), "policy_extra": ("invented", True),
                    "policy_bucket": ("bucket", "different-bucket"), "policy_account": ("account_id", "222222222222"),
                    "policy_region": ("region", "us-east-1"), "policy_recipient": ("recipient_sha256", "e" * 64),
                    "policy_custody": ("key_custody_record_id", str(uuid4())), "policy_cap": ("maximum_bytes", 100),
                }[failure]
                revised["backup"][field] = replacement
            conn.execute("UPDATE policy SET settings=%s", (Jsonb(revised),))
    with pytest.raises((BackupError, DomainError)):
        runtime.publish_ledger(config, service, authority, key.public_key(), store, staging)
    assert calls == [] and store.objects == {} and {p.name for p in staging.iterdir()} <= {"publication-v2.lock"}


def test_gate_revoked_during_encryption_blocks_provider_upload(settings, live_backup, monkeypatch):
    config, service, key, authority, store, staging, calls, _ = live_backup
    original = runtime.EncryptWriter.finish
    def revoke(writer):
        result = original(writer)
        with connect(settings) as conn:
            conn.execute("DELETE FROM release_gate WHERE scope='backup' AND gate_name='G1'")
        return result
    monkeypatch.setattr(runtime.EncryptWriter, "finish", revoke)
    with pytest.raises(BackupError, match="BACKUP_GATE_G1_CLOSED"):
        runtime.publish_ledger(config, service, authority, key.public_key(), store, staging)
    assert len(calls) == 1 and not store.objects and {p.name for p in staging.iterdir()} <= {"publication-v2.lock"}


def test_live_restore_resolves_current_registry_before_any_provider_inventory(settings, live_backup, monkeypatch):
    config, service, key, authority, store, staging, calls, _ = live_backup
    with connect(settings) as conn:
        now = service.now(conn)
        conn.execute("DELETE FROM release_gate WHERE scope='backup' AND gate_name='G7'")
    # Synthetic schema-valid historical receipt; it confers no current authority.
    receipt = {"schema_version": 1, "deployment_id": str(authority.deployment_id), "backup_id": str(uuid4()),
        "status": "complete", "country": "AU", "encryption": "encrypted_separate_key_custody",
        "completed_at": now.isoformat(), "expires_at": authority.expires_at.isoformat(), "ledger_watermark": now.isoformat(),
        "provider_evidence": {"record_id": str(authority.record_id), "sha256": authority.sha256,
            "checked_at": authority.checked_at.isoformat(), "expires_at": authority.expires_at.isoformat()},
        "components": [{"kind": kind, "object_id": str(uuid4()), "sha256": "b" * 64, "encrypted_bytes": 20}
            for kind in ("database", "artifacts", "suppression_erasure_ledger")]}
    monkeypatch.setattr(store, "inventory", lambda: pytest.fail("Current custody must precede provider inventory"))
    with pytest.raises(BackupError, match="BACKUP_GATE_G7_CLOSED"):
        restore_backup(config, service.keys, authority, key, store, receipt, staging, Path("not-used"),
            minimum_ledger_watermark=now.isoformat())
    assert calls == [] and {p.name for p in staging.iterdir()} <= {"publication-v2.lock"}
