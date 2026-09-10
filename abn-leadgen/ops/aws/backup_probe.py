"""Bounded synthetic S3 storage probe; no source/DB access or release approvals.

The approved coordinator supplies only its NEW scoped publisher adapter and RSA
custodian key in memory. Default CLI invocation is review-only. This operation
is engineering storage verification, never a production BackupReceipt.
"""
from __future__ import annotations

import io
import json
import os
import re
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from backup_crypto import BackupError, EncryptWriter, decrypt_stream, fingerprint
from backup_infrastructure import ACCOUNT, BUCKET, DEPLOYMENT, MAXIMUM_BYTES, PREFIX, REGION, canonical
from backup_store import S3Store, file_digest
from cryptography.hazmat.primitives.asymmetric import rsa

RECORD_FIELDS = {"schema", "deployment_id", "bucket", "object_id", "sha256", "encrypted_bytes", "recipient_sha256"}


class ProbeStore(S3Store):
    """Use the coordinator's in-memory scoped CLI; never inspect a credential file."""
    def __init__(self, provider_call):
        self.bucket, self.prefix, self.account_id = BUCKET, PREFIX, ACCOUNT
        self.maximum_bytes, self._provider_call = MAXIMUM_BYTES, provider_call

    def _call(self, operation, *arguments):
        allowed = {"get-bucket-location", "get-public-access-block", "get-bucket-policy-status", "get-bucket-versioning",
            "get-bucket-lifecycle-configuration", "list-objects-v2", "head-object", "put-object", "get-object", "delete-object"}
        if (operation not in allowed or self.bucket != BUCKET or self.prefix != PREFIX or self.account_id != ACCOUNT
                or "--bucket" not in arguments or arguments[arguments.index("--bucket") + 1] != BUCKET):
            raise BackupError("SYNTHETIC_PROBE_SCOPE_MISMATCH")
        if "--key" in arguments:
            key = str(arguments[arguments.index("--key") + 1])
            if not key.startswith(PREFIX) or key != PREFIX + str(UUID(key.removeprefix(PREFIX))):
                raise BackupError("SYNTHETIC_PROBE_SCOPE_MISMATCH")
        try:
            return self._provider_call(operation, "--region", REGION, "--endpoint-url",
                "https://s3.ap-southeast-2.amazonaws.com", "--expected-bucket-owner", ACCOUNT, *arguments)
        except BackupError:
            raise
        except Exception:  # noqa: BLE001 -- new-credential provider diagnostics must not escape
            raise BackupError("SYNTHETIC_PROBE_PROVIDER_UNCONFIRMED") from None


def _target(store):
    if (store.bucket != BUCKET or store.prefix != PREFIX or store.account_id != ACCOUNT
            or store.region != REGION or store.country != "AU" or store.maximum_bytes != MAXIMUM_BYTES):
        raise BackupError("SYNTHETIC_PROBE_SCOPE_MISMATCH")


def cleanup_probe(store, record):
    """A failed/killed probe may remove only its journaled exact digest/size object."""
    _target(store)
    if (not isinstance(record, dict) or set(record) != RECORD_FIELDS
            or record["schema"] != "abr-synthetic-backup-probe-object-v1"
            or record["deployment_id"] != DEPLOYMENT or record["bucket"] != BUCKET
            or type(record["encrypted_bytes"]) is not int or not 1 <= record["encrypted_bytes"] <= 16384
            or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
            or not re.fullmatch(r"[a-f0-9]{64}", record["recipient_sha256"])
            or str(UUID(record["object_id"])) != record["object_id"]):
        raise BackupError("SYNTHETIC_PROBE_JOURNAL_INVALID")
    return store.delete_verified(record["object_id"], record["sha256"], record["encrypted_bytes"])


def run_probe(store, private_recipient, staging_root, *, record_prepared):
    """record_prepared must fsync the public object record, then return True.

    Root/operator has separately authorized the one-bucket storage expense. This
    does not call _admit, install authority or read any business database. A
    storage probe cannot pass source/privacy/retention or production restore gates.
    """
    _target(store)
    if not isinstance(private_recipient, rsa.RSAPrivateKey) or private_recipient.key_size < 3072:
        raise BackupError("SYNTHETIC_PROBE_CUSTODY_REQUIRED")
    root = Path(staging_root)
    if (not root.is_absolute() or not root.is_dir() or root.resolve() != root
            or any(stat.S_ISLNK(path.lstat().st_mode) or getattr(path.lstat(), "st_file_attributes", 0) & 0x400
                for path in (root, *root.parents))
            or os.name != "nt" and root.stat().st_mode & 0o077):
        raise BackupError("SYNTHETIC_PROBE_PRIVATE_STAGING_REQUIRED")
    store.validate()
    identifier = str(uuid4())
    work = root / identifier
    work.mkdir(mode=0o700)
    encrypted, readback = work / "synthetic.enc", work / "readback.enc"
    record, attempted, removed = None, False, False
    try:
        payload = canonical({"schema": "abr-engineering-nonce-only-v1", "nonce": identifier,
            "deployment_id": DEPLOYMENT, "business_data": False})
        with os.fdopen(os.open(encrypted, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
            cipher = EncryptWriter(output, private_recipient.public_key(), maximum=4096)
            cipher.write(payload)
            cipher.finish()
            os.fsync(output.fileno())
        record = {"schema": "abr-synthetic-backup-probe-object-v1", "deployment_id": DEPLOYMENT,
            "bucket": BUCKET, "object_id": identifier, "sha256": file_digest(encrypted),
            "encrypted_bytes": encrypted.stat().st_size, "recipient_sha256": fingerprint(private_recipient)}
        if record_prepared(dict(record)) is not True:
            raise BackupError("SYNTHETIC_PROBE_DURABLE_JOURNAL_REQUIRED")
        attempted = True  # Uncertain provider success still requires owned-object reconciliation.
        store.put_verified(identifier, encrypted, kind="artifacts", expires_at=datetime.now(UTC) + timedelta(hours=1))
        store.get_verified(identifier, readback, record["sha256"], record["encrypted_bytes"])
        with readback.open("rb") as source:
            recovered = io.BytesIO()
            decrypt_stream(source, recovered, private_recipient, maximum=4096)
        if recovered.getvalue() != payload:
            raise BackupError("SYNTHETIC_PROBE_ROUNDTRIP_MISMATCH")
        cleanup_probe(store, record)
        removed = True
        return {"schema": "abr-synthetic-backup-storage-probe-v1", "status": "verified_deleted",
            "object_id": identifier, "deployment_id": DEPLOYMENT, "bucket": BUCKET, "region": REGION,
            "encrypted_upload_readback": True, "decrypted_nonce_verified": True, "delete_absence_verified": True,
            "business_data_used": False, "database_accessed": False, "release_approvals_created": False,
            "production_backup_accepted": False, "completed_at": datetime.now(UTC).isoformat()}
    finally:
        try:
            if attempted and not removed and record is not None:
                cleanup_probe(store, record)
        finally:
            for path in (encrypted, encrypted.with_name(encrypted.name + ".remote-readback"), readback):
                path.unlink(missing_ok=True)
            work.rmdir()


if __name__ == "__main__":
    print(json.dumps({"status": "review_only", "provider_operations": 0,
        "scope": "approved_coordinator_synthetic_nonce_only", "production_backup_accepted": False}))
