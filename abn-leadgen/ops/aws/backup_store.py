"""Private Sydney S3 backup object operations through the official AWS CLI.

No bucket, policy, lifecycle or paid service is created here. Those must already
be independently approved and installed. Object keys are opaque UUIDs under the
single deployment prefix; same-name objects are never overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from backup_crypto import BackupError


def file_digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


class S3Store:
    country = "AU"
    region = "ap-southeast-2"

    def __init__(self, executable: Path, bucket: str, deployment_id: UUID, *, account_id: str, maximum_bytes=100 * 1024**3):
        if not executable.is_absolute() or not executable.is_file() or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
            raise BackupError("BACKUP_STORE_CONFIGURATION_INVALID")
        self.executable, self.bucket = executable, bucket
        if not re.fullmatch(r"[0-9]{12}", account_id) or not 1 <= maximum_bytes <= 100 * 1024**3:
            raise BackupError("BACKUP_STORE_CONFIGURATION_INVALID")
        self.account_id = account_id
        self.prefix = f"abn-backup/{UUID(str(deployment_id))}/"
        self.maximum_bytes = maximum_bytes

    def _call(self, operation, *arguments):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_ENDPOINT_URL") and k not in {"AWS_CA_BUNDLE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"}}
        env["AWS_PAGER"] = ""
        try:
            result = subprocess.run([str(self.executable), "s3api", operation, "--region", self.region,
                "--endpoint-url", "https://s3.ap-southeast-2.amazonaws.com", "--expected-bucket-owner", self.account_id,
                "--output", "json", "--no-cli-pager", *map(str, arguments)],
                env=env, capture_output=True, timeout=900, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (OSError, subprocess.TimeoutExpired):
            raise BackupError("BACKUP_PROVIDER_UNAVAILABLE") from None
        if result.returncode:
            provider_error = re.search(rb"An error occurred \(([A-Za-z0-9]+)\)", result.stderr)
            if operation == "head-object" and provider_error and provider_error.group(1) in {b"404", b"NotFound", b"NoSuchKey"}:
                return None
            raise BackupError("BACKUP_PROVIDER_" + operation.upper().replace("-", "_") + "_FAILED")
        if len(result.stdout) > 8 * 1024**2:
            raise BackupError("BACKUP_PROVIDER_RESPONSE_LIMIT")
        try:
            return json.loads(result.stdout or b"{}")
        except (ValueError, UnicodeError):
            raise BackupError("BACKUP_PROVIDER_RESPONSE_INVALID") from None

    def validate(self):
        location = self._call("get-bucket-location", "--bucket", self.bucket)
        public = self._call("get-public-access-block", "--bucket", self.bucket)["PublicAccessBlockConfiguration"]
        policy = self._call("get-bucket-policy-status", "--bucket", self.bucket)["PolicyStatus"]
        versioning = self._call("get-bucket-versioning", "--bucket", self.bucket)
        lifecycle = self._call("get-bucket-lifecycle-configuration", "--bucket", self.bucket)["Rules"]
        if location.get("LocationConstraint") != self.region or not all(public.get(k) is True for k in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")) or policy.get("IsPublic") is not False:
            raise BackupError("PRIVATE_SYDNEY_BACKUP_BUCKET_REQUIRED")
        if versioning.get("Status"):
            raise BackupError("BACKUP_UNVERSIONED_BUCKET_REQUIRED")
        if not any(rule.get("Status") == "Enabled" and rule.get("Filter", {}).get("Prefix", rule.get("Prefix")) == self.prefix
                   and 1 <= rule.get("Expiration", {}).get("Days", 1000) <= 34 for rule in lifecycle):
            raise BackupError("BACKUP_EXPIRY_BACKSTOP_REQUIRED")
        return {"region": self.region, "country": self.country, "private": True, "lifecycle_days_max": 34}

    def _key(self, object_id):
        return self.prefix + str(UUID(str(object_id)))

    def inventory(self):
        objects, token = [], None
        while True:
            args = ["--bucket", self.bucket, "--prefix", self.prefix, "--max-keys", "1000", "--no-paginate"]
            if token:
                args += ["--continuation-token", token]
            result = self._call("list-objects-v2", *args)
            for item in result.get("Contents", []):
                try:
                    identifier = UUID(item["Key"].removeprefix(self.prefix))
                    if item["Key"] != self._key(identifier) or type(item["Size"]) is not int or item["Size"] < 0:
                        raise ValueError
                except ValueError:
                    raise BackupError("BACKUP_FOREIGN_OBJECT_IN_PREFIX") from None
                objects.append({"object_id": str(identifier), "bytes": item["Size"]})
            if len(objects) > 100_000:
                raise BackupError("BACKUP_INVENTORY_LIMIT")
            if not result.get("IsTruncated"):
                return objects
            token = result.get("NextContinuationToken")
            if not token:
                raise BackupError("BACKUP_INVENTORY_INCOMPLETE")

    def head(self, object_id):
        result = self._call("head-object", "--bucket", self.bucket, "--key", self._key(object_id))
        if result is None:
            return None
        return {"bytes": result["ContentLength"], "etag": result["ETag"], "sha256": result.get("Metadata", {}).get("sha256"),
            "expires_at": result.get("Metadata", {}).get("expires-at"), "kind": result.get("Metadata", {}).get("kind"),
            "ledger_watermark": result.get("Metadata", {}).get("ledger-watermark")}

    def put_verified(self, object_id, source: Path, *, kind: str, expires_at: datetime, ledger_watermark: str | None = None):
        if (expires_at.tzinfo is None or not datetime.now(UTC) < expires_at <= datetime.now(UTC) + timedelta(days=35)
            or kind not in {"database", "artifacts", "suppression_erasure_ledger", "receipt"}):
            raise BackupError("BACKUP_OBJECT_METADATA_INVALID")
        # This bounded single-host implementation deliberately has no multipart state.
        if source.stat().st_size > 4 * 1024**3:
            raise BackupError("BACKUP_SINGLE_OBJECT_FOUR_GIB_LIMIT")
        copied = source.with_name(source.name + ".remote-readback")
        if copied.exists() or copied.is_symlink():
            raise BackupError("BACKUP_READBACK_PATH_EXISTS")
        if sum(item["bytes"] for item in self.inventory()) + source.stat().st_size > self.maximum_bytes:
            raise BackupError("BACKUP_STORAGE_CAP_REACHED")
        digest = file_digest(source)
        metadata = {"sha256": digest, "kind": kind, "expires-at": expires_at.isoformat()}
        if ledger_watermark:
            metadata["ledger-watermark"] = ledger_watermark
        self._call("put-object", "--bucket", self.bucket, "--key", self._key(object_id), "--body", source,
            "--if-none-match", "*", "--server-side-encryption", "AES256", "--metadata", json.dumps(metadata))
        try:
            self.get_verified(object_id, copied, digest, source.stat().st_size)
        finally:
            copied.unlink(missing_ok=True)
        return {"object_id": str(object_id), "sha256": digest, "encrypted_bytes": source.stat().st_size, "kind": kind}

    def get_verified(self, object_id, destination, expected_digest, expected_size):
        head = self.head(object_id)
        if (not head or head["sha256"] != expected_digest or head["bytes"] != expected_size
            or expected_size > self.maximum_bytes or destination.exists() or destination.is_symlink()):
            raise BackupError("BACKUP_REMOTE_INTEGRITY_MISMATCH")
        self._call("get-object", "--bucket", self.bucket, "--key", self._key(object_id), "--if-match", head["etag"], destination)
        if destination.stat().st_size != expected_size or file_digest(destination) != expected_digest:
            raise BackupError("BACKUP_REMOTE_READBACK_MISMATCH")
        return destination

    def expire(self, *, now=None, before_delete=None):
        now = now or datetime.now(UTC)
        deleted = []
        for item in self.inventory():
            head = self._head_allow_absent(item["object_id"])
            if head is None:
                continue  # A lifecycle deletion may race the earlier inventory.
            if not head["expires_at"]:
                raise BackupError("BACKUP_EXPIRY_OWNERSHIP_UNKNOWN")
            due = datetime.fromisoformat(head["expires_at"])
            if due.tzinfo is None:
                raise BackupError("BACKUP_EXPIRY_INVALID")
            if due > now:
                continue
            if before_delete is not None:
                before_delete()
            self._call("delete-object", "--bucket", self.bucket, "--key", self._key(item["object_id"]))
            if self._head_allow_absent(item["object_id"]) is not None:
                raise BackupError("BACKUP_EXPIRY_NOT_CONFIRMED")
            deleted.append(item["object_id"])
        return {"deleted": deleted, "checked_at": now.isoformat()}

    def _head_allow_absent(self, object_id):
        try:
            return self.head(object_id)
        except BackupError:
            # HeadObject has no prefix argument. An IAM prefix-conditioned
            # ListBucket grant can mask missing objects as 403. A 403 alone is
            # never absence: prove it with this separately authorized exact list.
            key = self._key(object_id)
            result = self._call("list-objects-v2", "--bucket", self.bucket, "--prefix", key,
                "--max-keys", "1", "--no-paginate")
            if (result.get("Name") == self.bucket and result.get("Prefix") == key
                    and result.get("IsTruncated") is False and type(result.get("KeyCount")) is int
                    and result["KeyCount"] == 0 and result.get("Contents", []) == []):
                return None
            raise

    def delete_verified(self, object_id, expected_digest, expected_size):
        """Delete one durably recorded owned object, including uncertain PUT recovery."""
        head = self._head_allow_absent(object_id)
        if head is None:
            return {"deleted": True, "already_absent": True}
        if head["sha256"] != expected_digest or head["bytes"] != expected_size:
            raise BackupError("BACKUP_DELETE_OWNERSHIP_MISMATCH")
        self._call("delete-object", "--bucket", self.bucket, "--key", self._key(object_id))
        if self._head_allow_absent(object_id) is not None:
            raise BackupError("BACKUP_DELETE_NOT_CONFIRMED")
        return {"deleted": True, "already_absent": False}
