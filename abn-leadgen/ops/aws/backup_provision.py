"""Approved one-bucket coordinator. Default is review-only; root runs --apply.

Owner credentials are consumed only by the official CLI for STS identity and IAM.
S3 configuration uses an expiring, disposable principal. New publisher material
goes directly into the reviewed DPAPI custody helper, then pinned SSH stdin.
No source, database, release-authority or service activation is performed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from uuid import UUID, uuid4

import backup_identity_client as custody
from backup_crypto import BackupError
from backup_infrastructure import (
    ACCOUNT,
    BUCKET,
    DEPLOYMENT,
    MAXIMUM_BYTES,
    PREFIX,
    REGION,
    TAGS,
    USER,
    USER_ARN,
    USER_PATH,
    bootstrap_policy,
    bucket_configuration,
    canonical,
    publisher_policy,
)

SCHEMA = "abr-one-bucket-provisioning-v1"
POLICY = "AbnPrivateBackupPublisher"
TEMP_POLICY = "AbnOneBucketThirtyMinutes"
DENY = {"Version": "2012-10-17", "Statement": [{"Effect": "Deny", "Action": "*", "Resource": "*"}]}
ENDPOINT = "https://s3.ap-southeast-2.amazonaws.com"
AWS_EXE = Path("C:/Users/dalig/AppData/Local/Programs/Amazon/AWSCLIV2/aws.exe")
OWNER_PROFILE = "maintain-media-deploy"
ERRORS = {"NoSuchEntity", "NoSuchBucket", "NoSuchTagSet", "AccessDenied", "AccessDeniedException",
          "InvalidClientTokenId", "ExpiredToken", "InvalidAccessKeyId", "NotFound", "404",
          "BucketAlreadyExists", "BucketAlreadyOwnedByYou", "EntityAlreadyExists"}
IAM_OPERATIONS = {"get-user", "create-user", "list-user-policies", "get-user-policy", "put-user-policy",
    "delete-user-policy", "list-attached-user-policies", "list-groups-for-user", "get-login-profile",
    "list-access-keys", "create-access-key", "delete-access-key", "delete-user"}


PUBLIC_HELD_CODES = frozenset({
    "PROBE_STAGING_IDENTITY_MISMATCH",
    "PROBE_STAGING_PATH_OUTSIDE_CUSTODY",
    "INSPECTION_FLAGS_INVALID",
    "PROBE_REQUIRES_COMPLETED_INSTALLATION",
    "BOOTSTRAP_EXTRA_AUTHORITY_RETAIN_DENY",
    'APPROVED_WINDOWS_CUSTODIAN_REQUIRED',
    'BOOTSTRAP_DENY_PROPAGATION_UNCONFIRMED',
    'BOOTSTRAP_DENY_UNCONFIRMED',
    'BOOTSTRAP_IDENTITY_MISMATCH',
    'BOOTSTRAP_KEYS_REMAIN',
    'BOOTSTRAP_OPERATION_OUTSIDE_ONE_BUCKET',
    'BUCKET_CONFIGURATION_READBACK_MISMATCH',
    'BUCKET_CREATE_OUTCOME_REQUIRES_RECONCILIATION',
    'BUCKET_OWNERSHIP_UNCONFIRMED',
    'BUCKET_PUBLIC_POLICY_REFUSED',
    'BUCKET_REGION_READBACK_MISMATCH',
    'BUCKET_TAG_READBACK_MISMATCH',
    'EXISTING_IAM_USER_REFUSED',
    'EXISTING_OR_NON_SYDNEY_BUCKET_REFUSED',
    'HOST_INSTALLATION_UNCONFIRMED',
    'IAM_OWNERSHIP_MISMATCH',
    'INTERRUPTED_BOOTSTRAP_DENIED_WAIT_FOR_ORIGINAL_EXPIRY',
    'LOST_KEY_REPLACEMENT_REQUIRES_EXPLICIT_RESUME',
    'OFFICIAL_AWS_CLI_REQUIRED',
    'OWNER_ACCOUNT_MISMATCH',
    'OWNER_OPERATION_OUTSIDE_STS_IAM',
    'PROVISIONING_JOURNAL_INVALID',
    'PUBLISHER_ARGUMENT_INVALID',
    'PUBLISHER_BOUNDARY_MISMATCH',
    'PUBLISHER_CONSOLE_PASSWORD_REFUSED',
    'PUBLISHER_CUSTODY_UNCONFIRMED',
    'PUBLISHER_ENCRYPTED_CREATE_ONLY',
    'PUBLISHER_ESCROW_KEY_MISMATCH',
    'PUBLISHER_EXISTING_KEY_OR_MISSING_ESCROW_REFUSED',
    'PUBLISHER_EXTRA_PERMISSIONS_REFUSED',
    'PUBLISHER_IDENTITY_MISMATCH',
    'PUBLISHER_LIST_OUTSIDE_PREFIX',
    'PUBLISHER_OBJECT_OUTSIDE_PREFIX',
    'PUBLISHER_OPERATION_OUTSIDE_ONE_BUCKET',
    'PUBLISHER_POLICY_MISMATCH',
    'PUBLISHER_UNESCROWED_KEY_CLEANUP_UNCONFIRMED',
    'PUBLISHER_UNEXPECTED_KEYS_REFUSED',
    'SCOPED_CREDENTIAL_REQUIRED',
    'SYNTHETIC_PROBE_RECEIPT_INVALID',
    'UNESCROWED_KEY_REMOVED_EXPLICIT_RESUME_REQUIRED',
    'VERSIONED_BUCKET_REFUSED',
})


PUBLIC_BACKUP_ERRORS = frozenset({
    'BACKUP_AUTHENTICATION_FAILED',
    'BACKUP_DELETE_NOT_CONFIRMED',
    'BACKUP_DELETE_OWNERSHIP_MISMATCH',
    'BACKUP_ENCRYPTION_CONFIGURATION_INVALID',
    'BACKUP_EXPIRY_BACKSTOP_REQUIRED',
    'BACKUP_EXPIRY_INVALID',
    'BACKUP_EXPIRY_NOT_CONFIRMED',
    'BACKUP_EXPIRY_OWNERSHIP_UNKNOWN',
    'BACKUP_FOREIGN_OBJECT_IN_PREFIX',
    'BACKUP_FORMAT_INVALID',
    'BACKUP_FRAME_INVALID',
    'BACKUP_HEADER_LIMIT',
    'BACKUP_INVENTORY_INCOMPLETE',
    'BACKUP_INVENTORY_LIMIT',
    'BACKUP_OBJECT_METADATA_INVALID',
    'BACKUP_PLAINTEXT_LIMIT',
    'BACKUP_PRIVATE_KEY_REQUIRED',
    'BACKUP_PROVIDER_',
    'BACKUP_PROVIDER_RESPONSE_INVALID',
    'BACKUP_PROVIDER_RESPONSE_LIMIT',
    'BACKUP_PROVIDER_UNAVAILABLE',
    'BACKUP_PUBLISHER_ACCESS_DENIED',
    'BACKUP_PUBLISHER_PROVIDER_UNCONFIRMED',
    'BACKUP_READBACK_PATH_EXISTS',
    'BACKUP_RECIPIENT_MISMATCH',
    'BACKUP_REMOTE_INTEGRITY_MISMATCH',
    'BACKUP_REMOTE_READBACK_MISMATCH',
    'BACKUP_RSA_3072_OR_STRONGER_REQUIRED',
    'BACKUP_SINGLE_OBJECT_FOUR_GIB_LIMIT',
    'BACKUP_STORAGE_CAP_REACHED',
    'BACKUP_STORE_CONFIGURATION_INVALID',
    'BACKUP_STREAM_ALREADY_FINISHED',
    'BACKUP_TRAILING_BYTES',
    'BACKUP_TRUNCATED',
    'BACKUP_UNVERSIONED_BUCKET_REQUIRED',
    'PRIVATE_SYDNEY_BACKUP_BUCKET_REQUIRED',
    'SYNTHETIC_PROBE_CUSTODY_REQUIRED',
    'SYNTHETIC_PROBE_DURABLE_JOURNAL_REQUIRED',
    'SYNTHETIC_PROBE_JOURNAL_INVALID',
    'SYNTHETIC_PROBE_PRIVATE_STAGING_REQUIRED',
    'SYNTHETIC_PROBE_PROVIDER_UNCONFIRMED',
    'SYNTHETIC_PROBE_ROUNDTRIP_MISMATCH',
    'SYNTHETIC_PROBE_SCOPE_MISMATCH',
})


class Held(RuntimeError):
    """Only fixed codes are ever surfaced to the operator."""


class ProviderFailure(Held):
    def __init__(self, code):
        self.code = code if code in ERRORS else "PROVIDER_RESULT_UNCONFIRMED"
        super().__init__(self.code)


def clean_environment(environ, credentials=None):
    """Do not let shell/profile endpoint, role, metadata or proxy overrides redirect credentials."""
    excluded = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "REQUESTS_CA_BUNDLE",
                "CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR", "BOTO_CONFIG"}
    env = {k: v for k, v in environ.items() if not k.upper().startswith("AWS_") and k.upper() not in excluded}
    env.update(AWS_PAGER="", AWS_MAX_ATTEMPTS="1", AWS_EC2_METADATA_DISABLED="true",
               AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true", AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION)
    if credentials is not None:
        env.update(AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull,
                   AWS_ACCESS_KEY_ID=credentials["AccessKeyId"], AWS_SECRET_ACCESS_KEY=credentials["SecretAccessKey"])
        if credentials.get("SessionToken"):
            env["AWS_SESSION_TOKEN"] = credentials["SessionToken"]
    return env


class ScopedAWS:
    """Bounded version of deploy_session.Session.call with fixed targets and closed errors."""
    def __init__(self, executable=AWS_EXE, *, runner=subprocess.run, environ=None, sleep=time.sleep):
        self.executable, self.runner = str(executable), runner
        self.environ = dict(os.environ if environ is None else environ)
        self.temporary = None
        self.publisher_credentials = None
        self.calls = 0
        self.sleep = sleep

    def _call(self, service, operation, params=None, *, credentials=None, owner=False, arguments=()):
        command = [self.executable, service, operation, "--region", REGION, "--output", "json",
                   "--no-cli-pager", "--cli-connect-timeout", "10", "--cli-read-timeout", "25"]
        if owner:
            command += ["--profile", OWNER_PROFILE]
        elif credentials is None:
            raise Held("SCOPED_CREDENTIAL_REQUIRED")
        if service == "s3api":
            command += ["--endpoint-url", ENDPOINT]
        if params:
            command += ["--cli-input-json", json.dumps(params)]  # Public configuration only; keys are environment-only.
        command += list(map(str, arguments))
        self.calls += 1
        try:
            response = self.runner(command, env=clean_environment(self.environ, None if owner else credentials),
                capture_output=True, timeout=90, check=False, shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (OSError, subprocess.SubprocessError):
            raise ProviderFailure("PROVIDER_RESULT_UNCONFIRMED") from None
        if len(response.stdout) > 2_000_000 or len(response.stderr) > 65_536:
            raise ProviderFailure("PROVIDER_RESULT_UNCONFIRMED")
        if response.returncode:
            match = re.search(rb"An error occurred \(([A-Za-z0-9]+)\)", response.stderr)
            raise ProviderFailure(match.group(1).decode() if match else "PROVIDER_RESULT_UNCONFIRMED")
        try:
            result = json.loads(response.stdout or b"{}")
            if not isinstance(result, dict):
                raise TypeError
            return result
        except (ValueError, TypeError, UnicodeError):
            raise ProviderFailure("PROVIDER_RESULT_UNCONFIRMED") from None

    def owner(self, service, operation, params=None):
        if not (service == "sts" and operation == "get-caller-identity" or service == "iam" and operation in IAM_OPERATIONS):
            raise Held("OWNER_OPERATION_OUTSIDE_STS_IAM")
        return self._call(service, operation, params, owner=True)

    def token(self, credentials):
        return self._call("sts", "get-session-token", {"DurationSeconds": 1800}, credentials=credentials)["Credentials"]

    def identity(self, credentials):
        return self._call("sts", "get-caller-identity", credentials=credentials)

    def bootstrap(self, operation, params=None):
        allowed = {"create-bucket", "get-bucket-location", "get-bucket-tagging", "put-bucket-tagging",
            "put-public-access-block", "get-public-access-block", "put-bucket-ownership-controls",
            "get-bucket-ownership-controls", "put-bucket-encryption", "get-bucket-encryption",
            "put-bucket-lifecycle-configuration", "get-bucket-lifecycle-configuration", "put-bucket-policy",
            "get-bucket-policy", "get-bucket-policy-status", "get-bucket-versioning", "list-objects-v2"}
        if operation not in allowed or not params or params.get("Bucket") != BUCKET:
            raise Held("BOOTSTRAP_OPERATION_OUTSIDE_ONE_BUCKET")
        params = dict(params)
        if operation != "create-bucket":
            params["ExpectedBucketOwner"] = ACCOUNT
        return self._call("s3api", operation, params, credentials=self.temporary)

    def publisher_call(self, operation, *arguments):
        """Adapter used by backup_probe.ProbeStore; genuine head 404 alone means absent."""
        args = list(map(str, arguments))
        for flag, expected in (("--region", REGION), ("--endpoint-url", ENDPOINT), ("--expected-bucket-owner", ACCOUNT)):
            if args.count(flag) != 1 or args.index(flag) + 1 >= len(args) or args[args.index(flag) + 1] != expected:
                raise Held("PUBLISHER_BOUNDARY_MISMATCH")
            index = args.index(flag)
            del args[index:index + 2]
        options = {"--bucket", "--key", "--prefix", "--max-keys", "--continuation-token", "--body", "--if-none-match",
                   "--server-side-encryption", "--metadata", "--if-match"}
        values: dict[str, str] = {}
        positional = []
        index = 0
        while index < len(args):
            value = args[index]
            if value == "--no-paginate":
                if value in values:
                    raise Held("PUBLISHER_ARGUMENT_INVALID")
                values[value] = "true"
                index += 1
            elif value in options and index + 1 < len(args):
                if value in values or args[index + 1].startswith("--"):
                    raise Held("PUBLISHER_ARGUMENT_INVALID")
                values[value] = args[index + 1]
                index += 2
            elif value.startswith("--"):
                raise Held("PUBLISHER_ARGUMENT_INVALID")
            else:
                positional.append(value)
                index += 1
        allowed = {"get-bucket-location", "get-public-access-block", "get-bucket-policy-status", "get-bucket-versioning",
            "get-bucket-lifecycle-configuration", "list-objects-v2", "head-object", "put-object", "get-object", "delete-object"}
        if operation not in allowed or values.get("--bucket") != BUCKET or len(positional) != int(operation == "get-object"):
            raise Held("PUBLISHER_OPERATION_OUTSIDE_ONE_BUCKET")
        if operation in {"head-object", "put-object", "get-object", "delete-object"}:
            key = values.get("--key", "")
            try:
                if not key.startswith(PREFIX) or key != PREFIX + str(UUID(key.removeprefix(PREFIX))):
                    raise ValueError
            except ValueError:
                raise Held("PUBLISHER_OBJECT_OUTSIDE_PREFIX") from None
        if operation == "list-objects-v2" and values.get("--prefix") != PREFIX:
            prefix = values.get("--prefix", "")
            try:
                if not prefix.startswith(PREFIX) or prefix != PREFIX + str(UUID(prefix.removeprefix(PREFIX))):
                    raise ValueError
            except ValueError:
                raise Held("PUBLISHER_LIST_OUTSIDE_PREFIX") from None
        if operation == "put-object" and (values.get("--if-none-match") != "*" or values.get("--server-side-encryption") != "AES256"):
            raise Held("PUBLISHER_ENCRYPTED_CREATE_ONLY")
        for attempt in range(8):
            try:
                return self._call("s3api", operation, credentials=self.publisher_credentials,
                    arguments=("--expected-bucket-owner", ACCOUNT, *args))
            except ProviderFailure as error:
                if operation == "head-object" and error.code in {"404", "NotFound"}:
                    return None
                if error.code in {"AccessDenied", "AccessDeniedException", "InvalidClientTokenId", "InvalidAccessKeyId"}:
                    if operation in {"get-bucket-location", "get-public-access-block", "get-bucket-policy-status",
                            "get-bucket-versioning", "get-bucket-lifecycle-configuration"} and attempt < 7:
                        self.sleep(2)
                        continue
                    raise BackupError("BACKUP_PUBLISHER_ACCESS_DENIED") from None
                raise BackupError("BACKUP_PUBLISHER_PROVIDER_UNCONFIRMED") from None


def fresh_record():
    return {"schema": SCHEMA, "account_id": ACCOUNT, "deployment_id": DEPLOYMENT, "bucket": BUCKET,
        "configuration_sha256": hashlib.sha256(canonical({"bucket": bucket_configuration(), "publisher": publisher_policy()})).hexdigest(),
        "provisioning_id": str(uuid4()), "created_at": datetime.now(UTC).isoformat(), "bootstrap": None,
        "bucket_state": "new", "publisher_state": "new", "publisher_user_id": None,
        "publisher_key_sha256": None, "host_installed": False, "probe_record": None, "probe_receipt": None}


def validate_record(record):
    if (not isinstance(record, dict) or set(record) != set(fresh_record())
            or record["schema"] != SCHEMA or record["account_id"] != ACCOUNT
            or record["deployment_id"] != DEPLOYMENT or record["bucket"] != BUCKET
            or record["configuration_sha256"] != fresh_record()["configuration_sha256"]
            or str(UUID(record["provisioning_id"])) != record["provisioning_id"]
            or record["bucket_state"] not in {"new", "create_requested", "created", "tagged", "configured"}
            or record["publisher_state"] not in {"new", "create_requested", "created", "policy_verified", "key_requested", "key_lost", "escrowed"}
            or type(record["host_installed"]) is not bool):
        raise Held("PROVISIONING_JOURNAL_INVALID")
    entry = record["bootstrap"]
    if entry is not None and (not isinstance(entry, dict)
            or set(entry) != {"name", "nonce", "expires_at", "state", "positive_probe", "revocation_verified"}
            or not isinstance(entry["nonce"], str) or not re.fullmatch(r"[a-f0-9]{32}", entry["nonce"])
            or entry["name"] != "abn-backup-setup-" + entry["nonce"][:20]
            or entry["state"] not in {"reserved", "active", "revoked", "removed"}
            or type(entry["positive_probe"]) is not bool or type(entry["revocation_verified"]) is not bool
            or datetime.fromisoformat(entry["expires_at"]).tzinfo is None):
        raise Held("PROVISIONING_JOURNAL_INVALID")
    if (record["publisher_user_id"] is not None and not re.fullmatch(r"[A-Z0-9]{16,32}", record["publisher_user_id"])
            or record["publisher_key_sha256"] is not None and not re.fullmatch(r"[a-f0-9]{64}", record["publisher_key_sha256"])):
        raise Held("PROVISIONING_JOURNAL_INVALID")
    for field in ("probe_record", "probe_receipt"):
        if record[field] is not None:
            validate_probe_record(record[field], receipt=field == "probe_receipt")
    return record


def validate_probe_record(value, *, receipt):
    """Closed projection of this task's public engineering receipt, never a production approval."""
    common = {"schema", "deployment_id", "bucket", "object_id"}
    fields = common | ({"status", "region", "encrypted_upload_readback", "decrypted_nonce_verified",
        "delete_absence_verified", "business_data_used", "database_accessed", "release_approvals_created",
        "production_backup_accepted", "completed_at"} if receipt else {"sha256", "encrypted_bytes", "recipient_sha256"})
    if (not isinstance(value, dict) or set(value) != fields or value["deployment_id"] != DEPLOYMENT
            or value["bucket"] != BUCKET or str(UUID(value["object_id"])) != value["object_id"]):
        raise Held("SYNTHETIC_PROBE_RECEIPT_INVALID")
    if receipt:
        if (value["schema"] != "abr-synthetic-backup-storage-probe-v1" or value["status"] != "verified_deleted"
                or value["region"] != REGION or datetime.fromisoformat(value["completed_at"]).tzinfo is None
                or any(value[k] is not True for k in ("encrypted_upload_readback", "decrypted_nonce_verified", "delete_absence_verified"))
                or any(value[k] is not False for k in ("business_data_used", "database_accessed", "release_approvals_created", "production_backup_accepted"))):
            raise Held("SYNTHETIC_PROBE_RECEIPT_INVALID")
    elif (value["schema"] != "abr-synthetic-backup-probe-object-v1" or type(value["encrypted_bytes"]) is not int
            or not 1 <= value["encrypted_bytes"] <= 16384
            or any(not isinstance(value[k], str) or not re.fullmatch(r"[a-f0-9]{64}", value[k]) for k in ("sha256", "recipient_sha256"))):
        raise Held("SYNTHETIC_PROBE_RECEIPT_INVALID")
    return value


class Journal:
    def __init__(self, path, module):
        self.path, self.module = path, module

    def load(self):
        self.module.ordinary(self.path)
        if not self.path.exists():
            value = fresh_record()
            self.save(value)
            return value
        self.module.verify_acl(self.path)
        if self.path.stat().st_size > 65_536:
            raise Held("PROVISIONING_JOURNAL_INVALID")
        return validate_record(json.loads(self.path.read_bytes()))  # This task's public journal only.

    def save(self, value):
        value = validate_record(value)
        self.module.ordinary(self.path)
        if self.path.exists():
            self.module.verify_acl(self.path)
        stage = self.path.with_name(".backup-public-" + uuid4().hex + ".pending")
        try:
            with stage.open("xb") as stream:
                stream.write(canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
            self.module.verify_acl(stage)
            os.replace(stage, self.path)
        finally:
            stage.unlink(missing_ok=True)


def policy_document(value):
    return json.loads(unquote(value)) if isinstance(value, str) else value


class Coordinator:
    def __init__(self, aws, journal, private_escrow, identity_escrow, *, clock=lambda: datetime.now(UTC), sleep=time.sleep):
        self.aws, self.journal, self.private, self.identity = aws, journal, private_escrow, identity_escrow
        self.clock, self.sleep = clock, sleep
        self.record = journal.load()
        self.encryption_observation = None

    def save(self):
        self.journal.save(self.record)

    @property
    def tags(self):
        return TAGS | {"ProvisioningId": self.record["provisioning_id"]}

    def owner(self, operation, **params):
        return self.aws.owner("iam", operation, params)

    def user(self, name, tags, *, expected_id=None):
        result = self.owner("get-user", UserName=name)["User"]
        expected_arn = f"arn:aws:iam::{ACCOUNT}:user{USER_PATH}{name}"
        if (result.get("Arn") != expected_arn or result.get("Path") != USER_PATH
                or {t["Key"]: t["Value"] for t in result.get("Tags", [])} != tags
                or expected_id is not None and result.get("UserId") != expected_id):
            raise Held("IAM_OWNERSHIP_MISMATCH")
        return result

    def absent_user(self, name):
        try:
            self.owner("get-user", UserName=name)
        except ProviderFailure as error:
            if error.code == "NoSuchEntity":
                return
            raise
        raise Held("EXISTING_IAM_USER_REFUSED")

    def propagating_read(self, callback):
        """Poll only definite denials of reads; never replay uncertain mutations."""
        for attempt in range(8):
            try:
                return callback()
            except ProviderFailure as error:
                if error.code not in {"AccessDenied", "AccessDeniedException", "InvalidClientTokenId", "InvalidAccessKeyId"} or attempt == 7:
                    raise
                self.sleep(2)

    def bootstrap_start(self, *, read_only=False):
        old = self.record["bootstrap"]
        if old is not None and old["state"] != "removed":
            self.bootstrap_finish(interrupted=True)
        identifier = uuid4().hex
        entry = {"name": "abn-backup-setup-" + identifier[:20], "nonce": identifier,
            "expires_at": (self.clock() + timedelta(minutes=29)).isoformat(), "state": "reserved",
            "positive_probe": False, "revocation_verified": False}
        self.record["bootstrap"] = entry
        self.save()  # Unique IAM ownership reservation precedes its creation.
        self.absent_user(entry["name"])
        tags = self.tags | {"BootstrapId": identifier}
        self.owner("create-user", UserName=entry["name"], Path=USER_PATH,
                   Tags=[{"Key": k, "Value": v} for k, v in tags.items()])
        self.user(entry["name"], tags)
        policy = bootstrap_policy(datetime.fromisoformat(entry["expires_at"]))
        if read_only:
            statement = policy["Statement"][1]
            statement["Action"] = [name for name in statement["Action"] if name.startswith("s3:Get")]
            policy["Statement"] = [statement]
        self.owner("put-user-policy", UserName=entry["name"], PolicyName=TEMP_POLICY,
                   PolicyDocument=json.dumps(policy))
        key = self.owner("create-access-key", UserName=entry["name"])["AccessKey"]
        try:
            # IAM propagation may produce a definite denial; only this known-negative STS read is polled.
            for attempt in range(6):
                try:
                    self.aws.temporary = self.aws.token(key)
                    break
                except ProviderFailure as error:
                    if error.code not in {"AccessDenied", "InvalidClientTokenId"} or attempt == 5:
                        raise
                    self.sleep(2)
        finally:
            self.owner("delete-access-key", UserName=entry["name"], AccessKeyId=key["AccessKeyId"])
            key.clear()
        actual = self.aws.identity(self.aws.temporary)
        if actual.get("Account") != ACCOUNT or actual.get("Arn") != f"arn:aws:iam::{ACCOUNT}:user{USER_PATH}{entry['name']}":
            raise Held("BOOTSTRAP_IDENTITY_MISMATCH")
        entry["state"] = "active"
        self.save()

    def bootstrap_finish(self, *, interrupted=False):
        entry = self.record["bootstrap"]
        if entry is None or entry["state"] == "removed":
            return
        try:
            self.user(entry["name"], self.tags | {"BootstrapId": entry["nonce"]})
        except ProviderFailure as error:
            if error.code == "NoSuchEntity":
                entry["state"] = "removed"
                self.save()
                return
            raise
        self.owner("put-user-policy", UserName=entry["name"], PolicyName=TEMP_POLICY, PolicyDocument=json.dumps(DENY))
        if policy_document(self.owner("get-user-policy", UserName=entry["name"], PolicyName=TEMP_POLICY)["PolicyDocument"]) != DENY:
            raise Held("BOOTSTRAP_DENY_UNCONFIRMED")
        keys = self.owner("list-access-keys", UserName=entry["name"])["AccessKeyMetadata"]
        for key in keys:
            self.owner("delete-access-key", UserName=entry["name"], AccessKeyId=key["AccessKeyId"])
        if self.owner("list-access-keys", UserName=entry["name"])["AccessKeyMetadata"]:
            raise Held("BOOTSTRAP_KEYS_REMAIN")
        if (self.owner("list-user-policies", UserName=entry["name"])["PolicyNames"] != [TEMP_POLICY]
                or self.owner("list-attached-user-policies", UserName=entry["name"])["AttachedPolicies"]
                or self.owner("list-groups-for-user", UserName=entry["name"])["Groups"]):
            raise Held("BOOTSTRAP_EXTRA_AUTHORITY_RETAIN_DENY")
        try:
            self.owner("get-login-profile", UserName=entry["name"])
        except ProviderFailure as error:
            if error.code != "NoSuchEntity":
                raise
        else:
            raise Held("BOOTSTRAP_EXTRA_AUTHORITY_RETAIN_DENY")
        if self.aws.temporary is not None and not interrupted:
            for attempt in range(10):
                try:
                    self.aws.bootstrap("get-bucket-location", {"Bucket": BUCKET})
                except ProviderFailure as error:
                    if error.code in {"AccessDenied", "AccessDeniedException", "InvalidAccessKeyId", "ExpiredToken", "InvalidClientTokenId"}:
                        entry["revocation_verified"] = True
                        break
                    raise
                if attempt == 9:
                    raise Held("BOOTSTRAP_DENY_PROPAGATION_UNCONFIRMED")
                self.sleep(2)
        elif self.clock() <= datetime.fromisoformat(entry["expires_at"]):
            self.save()
            raise Held("INTERRUPTED_BOOTSTRAP_DENIED_WAIT_FOR_ORIGINAL_EXPIRY")
        entry["state"] = "revoked"
        self.save()
        self.owner("delete-user-policy", UserName=entry["name"], PolicyName=TEMP_POLICY)
        self.owner("delete-user", UserName=entry["name"])
        self.absent_user(entry["name"])
        entry["state"] = "removed"
        self.save()
        if self.aws.temporary:
            self.aws.temporary.clear()
        self.aws.temporary = None

    def bucket_tags(self):
        try:
            result = self.aws.bootstrap("get-bucket-tagging", {"Bucket": BUCKET})
        except ProviderFailure as error:
            if error.code == "NoSuchTagSet":
                return {}
            raise
        return {t["Key"]: t["Value"] for t in result["TagSet"]}

    def bucket(self):
        state = self.record["bucket_state"]
        configuration = bucket_configuration()
        try:
            location = self.propagating_read(lambda: self.aws.bootstrap("get-bucket-location", {"Bucket": BUCKET}))
        except ProviderFailure as error:
            if error.code != "NoSuchBucket" or state != "new":
                raise Held("BUCKET_CREATE_OUTCOME_REQUIRES_RECONCILIATION") from None
            self.record["bucket_state"] = "create_requested"
            self.save()
            self.aws.bootstrap("create-bucket", configuration["create"])
            self.record["bucket_state"] = "created"
            self.save()
            state = "created"
            location = self.aws.bootstrap("get-bucket-location", {"Bucket": BUCKET})
        if state == "new" or location.get("LocationConstraint") != REGION:
            raise Held("EXISTING_OR_NON_SYDNEY_BUCKET_REFUSED")
        tags = self.bucket_tags()
        if tags != self.tags:
            if state != "created" or tags:
                raise Held("BUCKET_OWNERSHIP_UNCONFIRMED")
            self.aws.bootstrap("put-bucket-tagging", {"Bucket": BUCKET,
                "Tagging": {"TagSet": [{"Key": k, "Value": v} for k, v in self.tags.items()]}})
            if self.bucket_tags() != self.tags:
                raise Held("BUCKET_TAG_READBACK_MISMATCH")
        self.record["bucket_state"] = "tagged"
        self.save()
        if self.aws.bootstrap("get-bucket-versioning", {"Bucket": BUCKET}).get("Status"):
            raise Held("VERSIONED_BUCKET_REFUSED")
        # Setting an identical owned configuration is idempotent. No unknown bucket is repaired.
        for operation, field, key in (
            ("put-public-access-block", "PublicAccessBlockConfiguration", "public_access_block"),
            ("put-bucket-ownership-controls", "OwnershipControls", "ownership_controls"),
            ("put-bucket-encryption", "ServerSideEncryptionConfiguration", "encryption"),
            ("put-bucket-lifecycle-configuration", "LifecycleConfiguration", "lifecycle"),
            ("put-bucket-policy", "Policy", "bucket_policy")):
            value = configuration[key]
            self.aws.bootstrap(operation, {"Bucket": BUCKET, field: json.dumps(value) if field == "Policy" else value})
        checks: tuple[tuple[str, str | None, str], ...] = (
            ("get-public-access-block", "PublicAccessBlockConfiguration", "public_access_block"),
            ("get-bucket-ownership-controls", "OwnershipControls", "ownership_controls"),
            ("get-bucket-encryption", "ServerSideEncryptionConfiguration", "encryption"),
            ("get-bucket-lifecycle-configuration", None, "lifecycle"),
            ("get-bucket-policy", "Policy", "bucket_policy"))
        for operation, check_field, key in checks:
            actual = self.aws.bootstrap(operation, {"Bucket": BUCKET})
            actual = actual[check_field] if check_field else {"Rules": actual["Rules"]}
            if key == "bucket_policy":
                actual = policy_document(actual)
            if key == "encryption":
                self.encryption_observation = public_encryption_detail(actual)
                actual = normalize_encryption(actual)
            if actual != configuration[key]:
                raise Held("BUCKET_CONFIGURATION_READBACK_MISMATCH")
        if self.aws.bootstrap("get-bucket-policy-status", {"Bucket": BUCKET}).get("PolicyStatus", {}).get("IsPublic") is not False:
            raise Held("BUCKET_PUBLIC_POLICY_REFUSED")
        if self.aws.bootstrap("get-bucket-location", {"Bucket": BUCKET}).get("LocationConstraint") != REGION:
            raise Held("BUCKET_REGION_READBACK_MISMATCH")
        self.record["bootstrap"]["positive_probe"] = True
        self.record["bucket_state"] = "configured"
        self.save()

    def publisher(self, *, resume_lost_key=False):
        stage = self.record["publisher_state"]
        if stage == "new":
            self.absent_user(USER)
            self.record["publisher_state"] = "create_requested"
            self.save()
            self.owner("create-user", UserName=USER, Path=USER_PATH,
                Tags=[{"Key": k, "Value": v} for k, v in self.tags.items()])
        user = self.user(USER, self.tags, expected_id=self.record["publisher_user_id"])
        self.record["publisher_user_id"] = user["UserId"]
        if stage in {"new", "create_requested"}:
            self.record["publisher_state"] = "created"
            self.save()
        if (self.owner("list-attached-user-policies", UserName=USER)["AttachedPolicies"]
                or self.owner("list-groups-for-user", UserName=USER)["Groups"]):
            raise Held("PUBLISHER_EXTRA_PERMISSIONS_REFUSED")
        try:
            self.owner("get-login-profile", UserName=USER)
        except ProviderFailure as error:
            if error.code != "NoSuchEntity":
                raise
        else:
            raise Held("PUBLISHER_CONSOLE_PASSWORD_REFUSED")
        policies = self.owner("list-user-policies", UserName=USER)["PolicyNames"]
        if policies not in ([], [POLICY]):
            raise Held("PUBLISHER_EXTRA_PERMISSIONS_REFUSED")
        if POLICY not in policies:
            self.owner("put-user-policy", UserName=USER, PolicyName=POLICY, PolicyDocument=json.dumps(publisher_policy()))
        if policy_document(self.owner("get-user-policy", UserName=USER, PolicyName=POLICY)["PolicyDocument"]) != publisher_policy():
            raise Held("PUBLISHER_POLICY_MISMATCH")
        self.private.recover()
        self.identity.recover()
        keys = self.owner("list-access-keys", UserName=USER)["AccessKeyMetadata"]
        if self.identity.path.exists():
            material = self.identity.load()["material"]
            if len(keys) != 1 or keys[0].get("Status") != "Active" or keys[0]["AccessKeyId"] != material["access_key_id"]:
                raise Held("PUBLISHER_ESCROW_KEY_MISMATCH")
        else:
            stage = self.record["publisher_state"]
            if stage == "key_requested":
                if len(keys) > 1:
                    raise Held("PUBLISHER_UNEXPECTED_KEYS_REFUSED")
                for key in keys:
                    self.owner("delete-access-key", UserName=USER, AccessKeyId=key["AccessKeyId"])
                if self.owner("list-access-keys", UserName=USER)["AccessKeyMetadata"]:
                    raise Held("PUBLISHER_UNESCROWED_KEY_CLEANUP_UNCONFIRMED")
                self.record["publisher_state"] = "key_lost"
                self.save()
                raise Held("UNESCROWED_KEY_REMOVED_EXPLICIT_RESUME_REQUIRED")
            if stage == "key_lost" and not resume_lost_key:
                raise Held("LOST_KEY_REPLACEMENT_REQUIRES_EXPLICIT_RESUME")
            if keys or stage == "escrowed":
                raise Held("PUBLISHER_EXISTING_KEY_OR_MISSING_ESCROW_REFUSED")
            self.record["publisher_state"] = "key_requested"
            self.save()
            key = self.owner("create-access-key", UserName=USER)["AccessKey"]
            try:
                custody.prepare({"AccessKeyId": key["AccessKeyId"], "SecretAccessKey": key["SecretAccessKey"]}, self.private, self.identity)
            except Exception:  # noqa: BLE001 -- clean only a known unescrowed newly-created key; never expose original text
                self.identity.recover()
                if not self.identity.path.exists():
                    self.owner("delete-access-key", UserName=USER, AccessKeyId=key["AccessKeyId"])
                    if self.owner("list-access-keys", UserName=USER)["AccessKeyMetadata"]:
                        raise Held("PUBLISHER_UNESCROWED_KEY_CLEANUP_UNCONFIRMED") from None
                    self.record["publisher_state"] = "key_lost"
                    self.save()
                raise Held("PUBLISHER_CUSTODY_UNCONFIRMED") from None
            finally:
                key.clear()
            material = self.identity.load()["material"]
        current_keys = self.owner("list-access-keys", UserName=USER)["AccessKeyMetadata"]
        if len(current_keys) != 1 or current_keys[0].get("Status") != "Active" or current_keys[0]["AccessKeyId"] != material["access_key_id"]:
            raise Held("PUBLISHER_ESCROW_KEY_MISMATCH")
        self.record["publisher_key_sha256"] = hashlib.sha256(material["access_key_id"].encode()).hexdigest()
        self.record["publisher_state"] = "escrowed"
        self.save()
        credentials = {"AccessKeyId": material["access_key_id"], "SecretAccessKey": material["secret_access_key"]}
        actual = self.propagating_read(lambda: self.aws.identity(credentials))
        if actual.get("Account") != ACCOUNT or actual.get("Arn") != USER_ARN:
            raise Held("PUBLISHER_IDENTITY_MISMATCH")
        self.aws.publisher_credentials = credentials

    def inspect(self):
        """Only fixed owned bucket configuration reads; no objects, publisher or SSH work."""
        if self.aws.owner("sts", "get-caller-identity").get("Account") != ACCOUNT:
            raise Held("OWNER_ACCOUNT_MISMATCH")
        checks = {}
        try:
            self.bootstrap_start(read_only=True)
            location = self.propagating_read(lambda: self.aws.bootstrap("get-bucket-location", {"Bucket": BUCKET}))
            if location.get("LocationConstraint") != REGION or self.bucket_tags() != self.tags:
                raise Held("BUCKET_OWNERSHIP_UNCONFIRMED")
            self.record["bootstrap"]["positive_probe"] = True
            self.save()
            configuration = bucket_configuration()
            encryption_detail = None
            for operation, field, key in (
                ("get-public-access-block", "PublicAccessBlockConfiguration", "public_access_block"),
                ("get-bucket-ownership-controls", "OwnershipControls", "ownership_controls"),
                ("get-bucket-encryption", "ServerSideEncryptionConfiguration", "encryption"),
                ("get-bucket-lifecycle-configuration", None, "lifecycle"),
                ("get-bucket-policy", "Policy", "bucket_policy")):
                actual = self.aws.bootstrap(operation, {"Bucket": BUCKET})
                actual = actual[field] if field else {"Rules": actual["Rules"]}
                if key == "bucket_policy":
                    actual = policy_document(actual)
                if key == "encryption":
                    encryption_detail = public_encryption_detail(actual)
                    actual = normalize_encryption(actual)
                checks[key] = {"matches": actual == configuration[key],
                    "differences": public_differences(configuration[key], actual)}
            checks["versioning"] = {"matches": not bool(self.aws.bootstrap("get-bucket-versioning", {"Bucket": BUCKET}).get("Status"))}
            checks["private_policy"] = {"matches": self.aws.bootstrap("get-bucket-policy-status", {"Bucket": BUCKET}).get("PolicyStatus", {}).get("IsPublic") is False}
        finally:
            self.bootstrap_finish()
        return {"status": "owned_bucket_inspected", "bucket": BUCKET, "region": REGION, "checks": checks,
            "encryption_detail": encryption_detail,
            "bucket_mutations": 0, "publisher_mutations": 0, "object_operations": 0, "host_operations": 0,
            "bootstrap_removed": self.record["bootstrap"]["state"] == "removed",
            "s3_revocation_verified": self.record["bootstrap"]["revocation_verified"]}

    def probe_only(self, probe):
        """Resume owned completed custody with read-only IAM checks; never create or rotate keys."""
        if (not self.record["host_installed"] or self.record["bucket_state"] != "configured"
                or self.record["publisher_state"] != "escrowed" or self.record["bootstrap"] is None
                or self.record["bootstrap"]["state"] != "removed"):
            raise Held("PROBE_REQUIRES_COMPLETED_INSTALLATION")
        if self.aws.owner("sts", "get-caller-identity").get("Account") != ACCOUNT:
            raise Held("OWNER_ACCOUNT_MISMATCH")
        self.user(USER, self.tags, expected_id=self.record["publisher_user_id"])
        if (self.owner("list-attached-user-policies", UserName=USER)["AttachedPolicies"]
                or self.owner("list-groups-for-user", UserName=USER)["Groups"]
                or self.owner("list-user-policies", UserName=USER)["PolicyNames"] != [POLICY]
                or policy_document(self.owner("get-user-policy", UserName=USER, PolicyName=POLICY)["PolicyDocument"]) != publisher_policy()):
            raise Held("PUBLISHER_EXTRA_PERMISSIONS_REFUSED")
        try:
            self.owner("get-login-profile", UserName=USER)
        except ProviderFailure as error:
            if error.code != "NoSuchEntity":
                raise
        else:
            raise Held("PUBLISHER_CONSOLE_PASSWORD_REFUSED")
        self.private.recover()
        self.identity.recover()
        private, identity = self.private.load(), self.identity.load()
        material = identity["material"]
        if (identity["stage"] != "complete" or identity["kind"] != "publisher_identity"
                or private["kind"] != "private_recipient"
                or material["public_recipient_pem"] != private["material"]["public_recipient_pem"]
                or hashlib.sha256(material["access_key_id"].encode()).hexdigest() != self.record["publisher_key_sha256"]):
            raise Held("PUBLISHER_ESCROW_KEY_MISMATCH")
        keys = self.owner("list-access-keys", UserName=USER)["AccessKeyMetadata"]
        if len(keys) != 1 or keys[0].get("Status") != "Active" or keys[0]["AccessKeyId"] != material["access_key_id"]:
            raise Held("PUBLISHER_ESCROW_KEY_MISMATCH")
        credentials = {"AccessKeyId": material["access_key_id"], "SecretAccessKey": material["secret_access_key"]}
        actual = self.propagating_read(lambda: self.aws.identity(credentials))
        if actual.get("Account") != ACCOUNT or actual.get("Arn") != USER_ARN:
            raise Held("PUBLISHER_IDENTITY_MISMATCH")
        self.aws.publisher_credentials = credentials
        result = probe(self)
        validate_probe_record(result, receipt=True)
        self.record["probe_receipt"] = result
        self.save()
        return {"status": "owned_backup_probe_complete", "bucket": BUCKET, "region": REGION,
            "probe_receipt": result, "iam_mutations": 0, "bucket_configuration_mutations": 0,
            "keys_created_or_rotated": 0, "host_operations": 0, "business_data_used": False,
            "runtime_capabilities_enabled": [], "release_approvals_created": False}

    def apply(self, *, install_host, probe=None, resume_lost_key=False):
        if self.aws.owner("sts", "get-caller-identity").get("Account") != ACCOUNT:
            raise Held("OWNER_ACCOUNT_MISMATCH")
        try:
            self.bootstrap_start()
            self.bucket()
            self.publisher(resume_lost_key=resume_lost_key)
        finally:
            self.bootstrap_finish()
        # Temporary creation/configuration authority must be gone before SSH or object operations.
        receipt = install_host(self.private, self.identity)
        if receipt.get("status") != "private_backup_identity_installed":
            raise Held("HOST_INSTALLATION_UNCONFIRMED")
        self.record["host_installed"] = True
        self.save()
        if probe:
            self.record["probe_receipt"] = probe(self)
            self.save()
        return {"status": "private_backup_infrastructure_installed", "account_id": ACCOUNT, "region": REGION,
            "deployment_id": DEPLOYMENT, "bucket": BUCKET, "prefix": PREFIX, "maximum_bytes": MAXIMUM_BYTES,
            "monthly_budget_usd": 5, "cost_limit_type": "storage_cap_not_billing_hard_stop", "ownership_tags": self.tags,
            "publisher_console_password": False, "publisher_active_keys": 1, "host_installed": True,
            "bootstrap_removed": self.record["bootstrap"]["state"] == "removed",
            "s3_revocation_verified": self.record["bootstrap"]["revocation_verified"],
            "s3_previously_allowed_read": self.record["bootstrap"]["positive_probe"],
            "encryption_observation": self.encryption_observation,
            "probe_receipt": self.record["probe_receipt"], "private_backup_key_on_host": False,
            "runtime_capabilities_enabled": [], "release_approvals_created": False, "services_enabled": False}


def engineering_probe(coordinator, directory):
    from backup_probe import ProbeStore, cleanup_probe, run_probe
    from cryptography.hazmat.primitives import serialization
    store = ProbeStore(coordinator.aws.publisher_call)
    if coordinator.record["probe_record"]:
        cleanup_probe(store, coordinator.record["probe_record"])
        coordinator.record["probe_record"] = None
        coordinator.save()
    if coordinator.record["probe_receipt"]:
        return coordinator.record["probe_receipt"]
    private = coordinator.private.load()["material"]["private_recipient_pem"].encode("ascii")
    recipient = serialization.load_pem_private_key(private, password=None)
    def record_prepared(record):
        coordinator.record["probe_record"] = record
        coordinator.save()
        return True
    receipt = run_probe(store, recipient, directory, record_prepared=record_prepared)
    coordinator.record["probe_record"] = None
    coordinator.record["probe_receipt"] = receipt
    coordinator.save()
    return receipt


def probe_staging(directory, module):
    """Resolve only the same protected owned directory, including verified MSIX virtualization."""
    expected = custody.BASE / "backup-key-escrow-983c39eb"
    packaged = custody.BASE.parents[1] / "Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/MaintainMedia/aws/backup-key-escrow-983c39eb"
    if directory != expected:
        raise Held("PROBE_STAGING_PATH_OUTSIDE_CUSTODY")
    module.ordinary(directory)
    module.verify_acl(directory, directory=True)
    actual = directory.resolve(strict=True)
    if actual not in {expected, packaged} or not actual.is_dir() or actual.resolve(strict=True) != actual:
        raise Held("PROBE_STAGING_PATH_OUTSIDE_CUSTODY")
    module.ordinary(actual)  # Retains ancestor symlink and Windows reparse-point refusal.
    module.verify_acl(actual, directory=True)
    if not os.path.samestat(directory.stat(), actual.stat()):
        raise Held("PROBE_STAGING_IDENTITY_MISMATCH")
    return actual


def public_differences(expected, actual, path=""):
    """Describe shape/order differences without reflecting unknown provider text."""
    if expected == actual:
        return []
    if isinstance(expected, dict) and isinstance(actual, dict):
        result = []
        for key, value in expected.items():
            if key not in actual:
                result.append({"path": path + "/" + key, "difference": "missing_field"})
            else:
                result.extend(public_differences(value, actual[key], path + "/" + key))
        if set(actual) - set(expected):
            result.append({"path": path, "difference": "extra_fields", "count": len(set(actual) - set(expected))})
        return result[:60]
    if isinstance(expected, list) and isinstance(actual, list):
        if sorted(map(canonical, expected)) == sorted(map(canonical, actual)):
            return [{"path": path, "difference": "same_members_different_order"}]
        result = [{"path": path, "difference": "array_members_or_length_changed", "expected_count": len(expected), "actual_count": len(actual)}]
        for index, (left, right) in enumerate(zip(expected, actual)):
            result.extend(public_differences(left, right, path + "/" + str(index)))
        return result[:60]
    detail = {"path": path, "difference": "value_or_type_changed", "expected_type": type(expected).__name__, "actual_type": type(actual).__name__}
    if expected == "*" and actual == {"AWS": "*"}:
        detail["equivalence_candidate"] = "wildcard_aws_principal_object"
    if isinstance(expected, str) and expected in {"true", "false"} and type(actual) is bool:
        detail["equivalence_candidate"] = "json_boolean_for_policy_string"
    return [detail]


def public_encryption_detail(configuration):
    """Project documented nonsecret S3 enums; never reflect unknown key names or values."""
    rules = configuration.get("Rules")
    if not isinstance(rules, list) or len(rules) > 10:
        return {"shape": "unexpected"}
    result: list[dict[str, object]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            result.append({"shape": "unexpected"})
            continue
        default = rule.get("ApplyServerSideEncryptionByDefault")
        blocked = rule.get("BlockedEncryptionTypes")
        types = blocked.get("EncryptionType") if isinstance(blocked, dict) else None
        result.append({
            "default_algorithm": default.get("SSEAlgorithm") if isinstance(default, dict)
                and default.get("SSEAlgorithm") in {"AES256", "aws:kms", "aws:kms:dsse"} else "unexpected",
            "default_extra_fields_count": len(set(default) - {"SSEAlgorithm"}) if isinstance(default, dict) else None,
            "bucket_key_present": "BucketKeyEnabled" in rule,
            "bucket_key_enabled": rule.get("BucketKeyEnabled") if type(rule.get("BucketKeyEnabled")) is bool else None,
            "blocked_types_present": "BlockedEncryptionTypes" in rule,
            "blocked_types": types if isinstance(blocked, dict) and set(blocked) == {"EncryptionType"}
                and isinstance(types, list) and len(types) <= 2
                and all(isinstance(v, str) and v in {"NONE", "SSE-C"} for v in types) else "unexpected_or_absent",
            "unknown_rule_fields_count": len(set(rule) - {"ApplyServerSideEncryptionByDefault", "BucketKeyEnabled", "BlockedEncryptionTypes"}),
        })
    return {"rule_count": len(rules), "rules": result}


def normalize_encryption(configuration):
    """Allow only observed AWS defaults that preserve or strengthen exact AES256 settings.

    AWS GetBucketEncryption returned SSE-C blocking on the actual new bucket.
    Removing this extra restriction from comparison does not send an unblock or
    alter the approved PutBucketEncryption payload. NONE/empty/unknown stay unequal.
    """
    if not isinstance(configuration, dict) or set(configuration) != {"Rules"} or not isinstance(configuration["Rules"], list):
        return configuration
    rules = []
    for value in configuration["Rules"]:
        if not isinstance(value, dict):
            return configuration
        rule = dict(value)
        if rule.get("BucketKeyEnabled") is False:
            del rule["BucketKeyEnabled"]
        if rule.get("BlockedEncryptionTypes") == {"EncryptionType": ["SSE-C"]}:
            del rule["BlockedEncryptionTypes"]
        rules.append(rule)
    return {"Rules": rules}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--probe", action="store_true", help="Encrypted synthetic nonce only; no production backup approval")
    parser.add_argument("--inspect", action="store_true", help="Only public owned bucket configuration; temporary IAM still created and removed")
    parser.add_argument("--probe-only", action="store_true", help="Reuse completed host installation and new DPAPI custody; no IAM/bucket configuration/host mutations")
    parser.add_argument("--resume-lost-key", action="store_true", help="Explicitly replace a previously removed unescrowed key")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"status": "review_only", "provider_operations": 0, "bucket": BUCKET,
            "region": REGION, "monthly_budget_usd": 5, "runtime_capabilities_enabled": []}))
        return 0
    try:
        if os.name != "nt" or Path(os.environ.get("LOCALAPPDATA", "")).resolve() != custody.BASE.parents[1].resolve():
            raise Held("APPROVED_WINDOWS_CUSTODIAN_REQUIRED")
        module = custody.helper()
        module.ordinary(AWS_EXE)
        if not AWS_EXE.is_file():
            raise Held("OFFICIAL_AWS_CLI_REQUIRED")
        directory = custody.BASE / "backup-key-escrow-983c39eb"
        module.secure_directory(directory)
        private = module.Escrow(directory / "private-recipient.dpapi")
        identity = module.Escrow(directory / "publisher-identity.dpapi")
        with module.coordinator_lock(directory / "coordinator.lock"):
            aws = ScopedAWS()
            coordinator = Coordinator(aws, Journal(directory / "provider-installation.json", module), private, identity)
            if args.probe_only:
                if args.probe or args.inspect or args.resume_lost_key:
                    raise Held("INSPECTION_FLAGS_INVALID")
                receipt = coordinator.probe_only(lambda c: engineering_probe(c, probe_staging(directory, module)))
            elif args.inspect:
                if args.probe or args.resume_lost_key:
                    raise Held("INSPECTION_FLAGS_INVALID")
                receipt = coordinator.inspect()
            else:
                receipt = coordinator.apply(install_host=lambda p, i: custody.install(p, i, custody.command(module), module.run_process),
                    probe=(lambda c: engineering_probe(c, probe_staging(directory, module))) if args.probe else None,
                    resume_lost_key=args.resume_lost_key)
        print(json.dumps(receipt))
        return 0
    except Exception as error:  # noqa: BLE001 -- no provider, native or key material may appear in diagnostics
        code = str(error) if isinstance(error, (Held, BackupError)) and str(error) in PUBLIC_HELD_CODES | ERRORS | PUBLIC_BACKUP_ERRORS else "BACKUP_PROVIDER_OR_CUSTODY_UNCONFIRMED"
        print(json.dumps({"status": "held", "code": code,
            "recovery": "Preserve the owned journal and DPAPI escrow. Reconcile the same bucket and publisher; never create replacements automatically.",
            "runtime_capabilities_enabled": [], "release_approvals_created": False}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
