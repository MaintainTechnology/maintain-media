"""Real PG16 dump/restore, synthetic data, local stand-in for private object provider."""
import hashlib
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from abr_engine.compliance.retention import erase_profile
from abr_engine.config import ROOT
from abr_engine.control.service import Service
from abr_engine.db import connect
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.promotion import declare_artifact, verify_artifact

sys.path.insert(0, str(Path(__file__).parents[2] / "ops/aws"))
from backup_crypto import BackupError, fingerprint
from backup_restore import restore_backup
from backup_runtime import BackupAuthority, create_backup, latest_ledger, publish_ledger


class LocalObjects:
    """Tests only: no provider verification or Australian residency is asserted."""
    maximum_bytes = 100 * 1024**3

    def __init__(self, root, deployment):
        self.root, self.objects = root, {}
        self.prefix = f"abn-backup/{deployment}/"
        root.mkdir()

    def validate(self):
        return {"synthetic_local_provider": True}

    def inventory(self):
        return [{"object_id": key, "bytes": row["bytes"]} for key, row in self.objects.items()]

    def head(self, key):
        return self.objects.get(str(key))

    def put_verified(self, key, path, *, kind, expires_at, ledger_watermark=None):
        key = str(key)
        assert key not in self.objects
        shutil.copyfile(path, self.root / key)
        content = (self.root / key).read_bytes()
        assert content == path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        self.objects[key] = {"bytes": len(content), "sha256": digest, "kind": kind,
            "expires_at": expires_at.isoformat(), "ledger_watermark": ledger_watermark, "etag": digest}
        return {"object_id": key, "sha256": digest, "encrypted_bytes": len(content), "kind": kind}

    def get_verified(self, key, destination, digest, size):
        content = (self.root / str(key)).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest or len(content) != size:
            raise BackupError("TEST_REMOTE_MISMATCH")
        assert not destination.exists()
        destination.write_bytes(content)
        return destination


def setup_backup(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = datetime.now(UTC)
    authority = BackupAuthority(deployment_id=uuid4(), record_id=uuid4(), sha256="a" * 64,
        checked_at=now-timedelta(minutes=1), expires_at=now+timedelta(days=40),
        recipient_sha256=fingerprint(key), key_custody_record_id=uuid4())
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    return key, authority, LocalObjects(tmp_path / "objects", authority.deployment_id), staging


def test_real_dump_restore_replays_post_backup_erasure_and_keeps_quarantine(settings, service, tmp_path):
    key, authority, store, staging = setup_backup(tmp_path)
    artifacts = tmp_path / "source-artifacts"
    artifacts.mkdir()
    settings = settings.model_copy(update={"output_dir": artifacts})
    service = Service(settings, service.keys)
    with connect(settings) as conn:
        seed_policy(conn, service)
        record = seed_contact(conn, service)
        run_id = uuid4()
        conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','backup-test','synthetic','complete')", (run_id,))
        source = artifacts / "source.parquet"
        declare_artifact(conn, run_id, "qbcc", source, artifact_class="snapshot")
        source.write_bytes(b"actual synthetic artifact bytes")
        row = verify_artifact(conn, run_id, "qbcc", source)
        conn.execute("UPDATE artifact_manifest SET state='referenced' WHERE artifact_id=%s", (row["artifact_id"],))
        old_raw = artifacts / "expired-source.csv"
        declare_artifact(conn, run_id, "qbcc", old_raw, artifact_class="raw")
        old_raw.write_bytes(b"synthetic raw data due for retention")
        raw = verify_artifact(conn, run_id, "qbcc", old_raw)
        conn.execute("UPDATE artifact_manifest SET state='referenced',created_at=clock_timestamp()-interval '31 days' WHERE artifact_id=%s", (raw["artifact_id"],))
    receipt = create_backup(settings, service, authority, key.public_key(), store, staging, ROOT / ".runtime/pgsql/bin")
    assert {row["kind"] for row in receipt["components"]} == {"database", "artifacts", "suppression_erasure_ledger"}
    with connect(settings) as conn:
        service.suppress(conn, {"lead_id": record["lead"]["lead_id"], "reason": "unsubscribe", "source": "after-backup-test"}, "fixture", uuid4())
        erase_profile(conn, service, record["lead"]["group_id"])
    current = publish_ledger(settings, service, authority, key.public_key(), store, staging)
    assert current["ledger_watermark"] > receipt["ledger_watermark"]
    observed = []
    def inspect(conn, restored):
        # Restored schema includes the queue; ledger replay schedules independent replication.
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        queue = conn.execute("SELECT generation,acknowledged_generation FROM backup_ledger_state").fetchone()
        assert queue["generation"] > queue["acknowledged_generation"]
        assert conn.execute("SELECT 1 FROM lead_entity WHERE lead_id=%s", (record["lead"]["lead_id"],)).fetchone() is None
        assert "SUPPRESSED_UNSUBSCRIBE" in restored.restricted(conn, record["lead"]["group_id"])
        path = Path(conn.execute("SELECT local_path FROM artifact_manifest WHERE artifact_id=%s", (row["artifact_id"],)).fetchone()["local_path"])
        assert path.read_bytes() == source.read_bytes()
        assert path != source
        removed = conn.execute("SELECT state,local_path FROM artifact_manifest WHERE artifact_id=%s", (raw["artifact_id"],)).fetchone()
        assert removed["state"] == "deleted" and not Path(removed["local_path"]).exists()
        assert old_raw.exists()
        observed.append(True)
    result = restore_backup(settings, service.keys, authority, key, store, receipt, staging, ROOT / ".runtime/pgsql/bin",
        minimum_ledger_watermark=current["ledger_watermark"], inspect=inspect)
    assert observed and result["outbound"] == "quarantined" and result["cluster"] == "stopped"
    assert not list(Path(result["work_directory"]).glob("*.plain"))
    assert not (Path(result["work_directory"]) / "cluster/postmaster.pid").exists()


def test_missing_current_ledger_refuses_restore(tmp_path):
    _, _, store, _ = setup_backup(tmp_path)
    with pytest.raises(BackupError, match="CURRENT_LEDGER_UNAVAILABLE"):
        latest_ledger(store, minimum_watermark=datetime.now(UTC).isoformat())


def test_expired_authority_no_dump_or_upload(settings, service, tmp_path):
    key, authority, store, staging = setup_backup(tmp_path)
    authority.expires_at = datetime.now(UTC)-timedelta(seconds=1)
    with pytest.raises(BackupError, match="AUTHORITY"):
        create_backup(settings, service, authority, key.public_key(), store, staging, ROOT / ".runtime/pgsql/bin")
    assert store.objects == {} and not [p for p in staging.iterdir() if p.name != "capture-v2.lock"]


def test_gate_withdrawn_after_dump_does_not_upload(settings, service, tmp_path, monkeypatch):
    import backup_runtime
    key, authority, store, staging = setup_backup(tmp_path)
    admitted = []
    original = backup_runtime._admit
    def admission(*args):
        admitted.append(True)
        if len(admitted) > 1:
            raise BackupError("TEST_APPROVAL_WITHDRAWN")
        original(*args)
    monkeypatch.setattr(backup_runtime, "_admit", admission)
    monkeypatch.setattr(backup_runtime, "dump_encrypted", lambda settings, binary, snapshot, path, recipient, maximum: path.write_bytes(b"synthetic encrypted dump"))
    monkeypatch.setattr(backup_runtime, "artifacts_encrypted", lambda conn, root, path, recipient, maximum: path.write_bytes(b"synthetic encrypted archive"))
    with pytest.raises(BackupError, match="APPROVAL_WITHDRAWN"):
        create_backup(settings, service, authority, key.public_key(), store, staging, ROOT / ".runtime/pgsql/bin")
    assert not store.objects and {p.name for p in staging.iterdir()} <= {"capture-v2.lock", "publication-v2.lock"}


def test_single_publisher_lock_rejects_overlap(tmp_path):
    from backup_runtime import publication_lease
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    with publication_lease(staging), pytest.raises(BackupError, match="PUBLICATION_BUSY"), publication_lease(staging):
        raise AssertionError("A second publisher entered")
    assert [p.name for p in staging.iterdir()] == ["publication-v2.lock"]
    with publication_lease(staging):
        pass  # Persistent inode is unlocked and reusable; deleting it would allow races.
