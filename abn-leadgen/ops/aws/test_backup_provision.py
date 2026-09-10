"""Provider simulation exercises the real ownership and recovery orchestration."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import backup_identity_client as custody
import backup_provision as cloud
import pytest


class Journal:
    def __init__(self):
        self.value = cloud.fresh_record()
        self.history = []
    def load(self):
        return deepcopy(self.value)
    def save(self, value):
        cloud.validate_record(value)
        self.value = deepcopy(value)
        self.history.append(deepcopy(value))


class Escrow:
    def __init__(self, path):
        self.path, self.value = path, None
    def recover(self):
        pass
    def load(self):
        return deepcopy(self.value)
    def save(self, value):
        self.value = deepcopy(custody.validate_state(value))
        self.path.write_bytes(b"synthetic encrypted marker")


class Provider:
    def __init__(self):
        self.users, self.bucket_state, self.operations = {}, None, []
        self.temporary = self.publisher_credentials = None
        self.fail_after, self.keys_created, self.account = None, 0, cloud.ACCOUNT
        self.denials = 0
    def done(self, service, operation, params, result):
        self.operations.append((service, operation, deepcopy(params)))
        if self.fail_after == (service, operation):
            self.fail_after = None
            raise cloud.ProviderFailure("unknown confidential response")
        return deepcopy(result)
    def owner(self, service, operation, params=None):
        if service == "sts":
            assert operation == "get-caller-identity"
            return {"Account": self.account}
        assert service == "iam", "Owner must never perform S3"
        params = params or {}
        name = params.get("UserName")
        user = self.users.get(name)
        if operation == "create-user":
            assert user is None, "No duplicate IAM creation"
            detail = {"UserId": "AIDA" + f"{len(self.operations):017d}", "UserName": name,
                "Path": params["Path"], "Arn": f"arn:aws:iam::{cloud.ACCOUNT}:user{params['Path']}{name}", "Tags": params["Tags"]}
            self.users[name] = {"details": detail, "policies": {}, "keys": [], "groups": [], "attached": [], "login": False}
            result = {"User": detail}
        elif user is None:
            raise cloud.ProviderFailure("NoSuchEntity")
        elif operation == "get-user":
            result = {"User": user["details"]}
        elif operation == "put-user-policy":
            user["policies"][params["PolicyName"]] = cloud.policy_document(params["PolicyDocument"])
            result = {}
        elif operation == "get-user-policy":
            result = {"PolicyDocument": user["policies"][params["PolicyName"]]}
        elif operation == "list-user-policies":
            result = {"PolicyNames": list(user["policies"])}
        elif operation == "list-attached-user-policies":
            result = {"AttachedPolicies": user["attached"]}
        elif operation == "list-groups-for-user":
            result = {"Groups": user["groups"]}
        elif operation == "get-login-profile":
            if not user["login"]:
                raise cloud.ProviderFailure("NoSuchEntity")
            result = {"LoginProfile": {}}
        elif operation == "create-access-key":
            assert not user["keys"], "No second active key"
            self.keys_created += 1
            key = {"UserName": name, "AccessKeyId": "AKIA" + f"{self.keys_created:016d}", "SecretAccessKey": "S" * 40, "Status": "Active"}
            user["keys"].append(key)
            result = {"AccessKey": key}
        elif operation == "list-access-keys":
            result = {"AccessKeyMetadata": [{k: key[k] for k in ("UserName", "AccessKeyId", "Status")} for key in user["keys"]]}
        elif operation == "delete-access-key":
            user["keys"] = [key for key in user["keys"] if key["AccessKeyId"] != params["AccessKeyId"]]
            result = {}
        elif operation == "delete-user-policy":
            user["policies"].pop(params["PolicyName"], None)
            result = {}
        elif operation == "delete-user":
            assert not user["keys"] and not user["policies"]
            del self.users[name]
            result = {}
        else:
            raise AssertionError(operation)
        return self.done(service, operation, params, result)
    def token(self, key):
        return {"AccessKeyId": "ASIA" + "0" * 16, "SecretAccessKey": "T" * 40,
            "SessionToken": "synthetic", "user": key["UserName"]}
    def identity(self, key):
        if "user" in key:
            name = key["user"]
        else:
            name = next(name for name, user in self.users.items()
                if any(k["AccessKeyId"] == key["AccessKeyId"] for k in user["keys"]))
        return {"Account": cloud.ACCOUNT, "Arn": self.users[name]["details"]["Arn"]}
    def bootstrap(self, operation, params):
        assert params["Bucket"] == cloud.BUCKET
        if self.users[self.temporary["user"]]["policies"][cloud.TEMP_POLICY] == cloud.DENY:
            self.operations.append(("s3api-denied", operation, deepcopy(params)))
            raise cloud.ProviderFailure("AccessDenied")
        if self.denials:
            self.denials -= 1
            raise cloud.ProviderFailure("AccessDenied")
        bucket = self.bucket_state
        if operation == "create-bucket":
            assert bucket is None
            self.bucket_state = {"tags": {}, "versioning": {}, "location": cloud.REGION, "configuration": {}}
            result = {"Location": "/" + cloud.BUCKET}
        elif bucket is None:
            raise cloud.ProviderFailure("NoSuchBucket")
        elif operation == "get-bucket-location":
            result = {"LocationConstraint": bucket["location"]}
        elif operation == "get-bucket-tagging":
            if not bucket["tags"]:
                raise cloud.ProviderFailure("NoSuchTagSet")
            result = {"TagSet": [{"Key": k, "Value": v} for k, v in bucket["tags"].items()]}
        elif operation == "put-bucket-tagging":
            bucket["tags"] = {t["Key"]: t["Value"] for t in params["Tagging"]["TagSet"]}
            result = {}
        elif operation == "get-bucket-versioning":
            result = bucket["versioning"]
        elif operation == "get-bucket-policy-status":
            result = {"PolicyStatus": {"IsPublic": False}}
        elif operation.startswith("put-"):
            bucket["configuration"][operation.removeprefix("put-")] = {k: v for k, v in params.items() if k != "Bucket"}
            result = {}
        elif operation.startswith("get-"):
            result = bucket["configuration"][operation.removeprefix("get-")]
            if operation == "get-bucket-lifecycle-configuration":
                result = result["LifecycleConfiguration"]
        else:
            raise AssertionError(operation)
        return self.done("s3api", operation, params, result)


@pytest.fixture
def setup(tmp_path):
    provider, journal = Provider(), Journal()
    private, identity = Escrow(tmp_path / "private.dpapi"), Escrow(tmp_path / "publisher.dpapi")
    def make():
        return cloud.Coordinator(provider, journal, private, identity, sleep=lambda _: None)
    return provider, journal, private, identity, make


def installed(private, identity):
    assert private.path.exists() and identity.path.exists()
    return {"status": "private_backup_identity_installed", "extra_secret": "do not reflect"}


def publisher_creates(provider):
    return sum(op[1] == "create-access-key" and op[2].get("UserName") == cloud.USER for op in provider.operations)


def test_complete_and_replay_keep_one_bucket_and_key_without_activation(setup):
    provider, journal, private, identity, make = setup
    def host(p, i):
        assert set(provider.users) == {cloud.USER}, "Temporary identity must be removed before SSH"
        return installed(p, i)
    receipt = make().apply(install_host=host)
    assert receipt["bootstrap_removed"] and receipt["s3_revocation_verified"] and receipt["s3_previously_allowed_read"]
    assert receipt["runtime_capabilities_enabled"] == [] and not receipt["release_approvals_created"]
    assert receipt["monthly_budget_usd"] == 5 and receipt["maximum_bytes"] == 100_000_000_000
    assert "do not reflect" not in str(receipt) and "S" * 40 not in str(journal.value)
    prior = deepcopy(identity.value), deepcopy(private.value)
    make().apply(install_host=host)
    assert prior == (identity.value, private.value)
    assert publisher_creates(provider) == 1
    assert sum(op[0:2] == ("s3api", "create-bucket") for op in provider.operations) == 1
    assert private.value["material"]["private_recipient_pem"] not in str(identity.value)


def test_wrong_account_has_no_mutations(setup):
    provider, _, _, _, make = setup
    provider.account = "123456789012"
    with pytest.raises(cloud.Held, match="OWNER_ACCOUNT"):
        make().apply(install_host=installed)
    assert provider.operations == []


@pytest.mark.parametrize("wrong", ["untagged", "foreign_tag", "versioned", "region"])
def test_existing_or_changed_bucket_is_not_repaired(setup, wrong):
    provider, _, _, _, make = setup
    if wrong != "untagged":
        make().apply(install_host=installed)
        if wrong == "foreign_tag":
            provider.bucket_state["tags"]["ProvisioningId"] = "foreign"
        elif wrong == "versioned":
            provider.bucket_state["versioning"] = {"Status": "Enabled"}
        else:
            provider.bucket_state["location"] = "us-east-1"
    else:
        provider.bucket_state = {"tags": {}, "location": cloud.REGION}
    count = len(provider.operations)
    with pytest.raises(cloud.Held):
        make().apply(install_host=installed)
    assert not any(op[0] == "s3api" and op[1].startswith(("put-", "create-")) for op in provider.operations[count:])


def test_unknown_create_never_duplicates_or_tags_unconfirmed_bucket(setup):
    provider, journal, _, _, make = setup
    provider.fail_after = ("s3api", "create-bucket")
    with pytest.raises(cloud.Held):
        make().apply(install_host=installed)
    assert journal.value["bucket_state"] == "create_requested"
    with pytest.raises(cloud.Held, match="OWNERSHIP_UNCONFIRMED"):
        make().apply(install_host=installed)
    assert sum(op[0:2] == ("s3api", "create-bucket") for op in provider.operations) == 1
    assert provider.bucket_state["tags"] == {}


def test_known_owned_partial_configuration_resumes(setup):
    provider, _, _, _, make = setup
    provider.fail_after = ("s3api", "put-bucket-encryption")
    with pytest.raises(cloud.Held):
        make().apply(install_host=installed)
    assert make().apply(install_host=installed)["host_installed"]


def test_known_unescrowed_key_is_removed_immediately_no_silent_replacement(setup, monkeypatch):
    provider, journal, _, identity, make = setup
    original = custody.prepare
    def fail(*args):
        raise OSError("synthetic custody failure")
    monkeypatch.setattr(custody, "prepare", fail)
    with pytest.raises(cloud.Held, match="CUSTODY_UNCONFIRMED"):
        make().apply(install_host=installed)
    assert journal.value["publisher_state"] == "key_lost" and not identity.path.exists()
    assert provider.users[cloud.USER]["keys"] == []
    monkeypatch.setattr(custody, "prepare", original)
    with pytest.raises(cloud.Held, match="EXPLICIT_RESUME"):
        make().apply(install_host=installed)
    assert publisher_creates(provider) == 1
    assert make().apply(install_host=installed, resume_lost_key=True)["host_installed"]
    assert publisher_creates(provider) == 2


def test_post_escrow_crash_keeps_key_and_private_recipient(setup, monkeypatch):
    provider, _, _, identity, make = setup
    original = custody.prepare
    def fail_after(*args):
        original(*args)
        raise OSError("synthetic post-custody crash")
    monkeypatch.setattr(custody, "prepare", fail_after)
    with pytest.raises(cloud.Held, match="CUSTODY_UNCONFIRMED"):
        make().apply(install_host=installed)
    prior = deepcopy(identity.value)
    monkeypatch.setattr(custody, "prepare", original)
    make().apply(install_host=installed)
    assert prior == identity.value and publisher_creates(provider) == 1


@pytest.mark.parametrize("defect", ["tags", "user_id", "policy", "attached", "groups", "login", "extra_key"])
def test_changed_publisher_authority_is_not_repaired(setup, defect):
    provider, _, _, _, make = setup
    make().apply(install_host=installed)
    user = provider.users[cloud.USER]
    if defect == "tags":
        user["details"]["Tags"].append({"Key": "Foreign", "Value": "yes"})
    elif defect == "user_id":
        user["details"]["UserId"] = "AIDA" + "Z" * 17
    elif defect == "policy":
        user["policies"][cloud.POLICY] = cloud.DENY
    elif defect in {"attached", "groups"}:
        user[defect] = ["unexpected"]
    elif defect == "login":
        user["login"] = True
    else:
        user["keys"].append({"AccessKeyId": "AKIA" + "9" * 16, "UserName": cloud.USER, "Status": "Active"})
    before = deepcopy(user)
    with pytest.raises(cloud.Held):
        make().apply(install_host=installed)
    assert provider.users[cloud.USER] == before


def test_unknown_ssh_replays_same_custody(setup):
    _, journal, private, identity, make = setup
    def fail(*_):
        raise OSError("unknown ssh outcome")
    with pytest.raises(OSError):
        make().apply(install_host=fail)
    assert not journal.value["host_installed"] and journal.value["bootstrap"]["state"] == "removed"
    prior = deepcopy(private.value), deepcopy(identity.value)
    make().apply(install_host=installed)
    assert prior == (private.value, identity.value)


def test_interrupted_session_retains_deny_until_original_expiry(setup):
    provider, journal, _, _, make = setup
    instance = make()
    instance.bootstrap_start()
    name = journal.value["bootstrap"]["name"]
    provider.temporary = None
    with pytest.raises(cloud.Held, match="WAIT_FOR_ORIGINAL_EXPIRY"):
        make().bootstrap_finish(interrupted=True)
    assert provider.users[name]["policies"][cloud.TEMP_POLICY] == cloud.DENY
    assert provider.users[name]["keys"] == []
    instance = make()
    instance.clock = lambda: datetime.now(UTC) + timedelta(minutes=31)
    instance.bootstrap_finish(interrupted=True)
    assert name not in provider.users


def test_known_denial_propagation_reads_retry_without_repeating_mutations(setup):
    provider, _, _, _, make = setup
    provider.denials = 3
    assert make().apply(install_host=installed)["host_installed"]
    assert sum(op[0:2] == ("s3api", "create-bucket") for op in provider.operations) == 1
    assert publisher_creates(provider) == 1


def test_isolated_environment_and_no_secret_argv():
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'{"Account":"052530979168"}', stderr=b"")
    aws = cloud.ScopedAWS(runner=run, environ={"PATH": "safe", "AWS_ENDPOINT_URL": "https://bad", "AWS_ROLE_ARN": "bad",
        "AWS_SHARED_CREDENTIALS_FILE": "unrelated", "https_proxy": "bad", "AWS_SECRET_ACCESS_KEY": "do not use"})
    aws.identity({"AccessKeyId": "AKIA" + "1" * 16, "SecretAccessKey": "S" * 40})
    command, options = calls[0]
    assert "S" * 40 not in str(command) and "AKIA" not in str(command)
    env = options["env"]
    assert env["AWS_SHARED_CREDENTIALS_FILE"] == cloud.os.devnull and env["AWS_MAX_ATTEMPTS"] == "1"
    assert not any(k in env for k in ("AWS_ROLE_ARN", "https_proxy", "AWS_ENDPOINT_URL"))
    with pytest.raises(cloud.Held, match="OUTSIDE_STS_IAM"):
        aws.owner("s3api", "create-bucket", {"Bucket": cloud.BUCKET})


def probe_args():
    return ["--region", cloud.REGION, "--endpoint-url", cloud.ENDPOINT, "--expected-bucket-owner", cloud.ACCOUNT,
        "--bucket", cloud.BUCKET, "--key", cloud.PREFIX + "d0458d88-e9a1-44bc-ae5f-5ecb4f86dbd3"]


@pytest.mark.parametrize("stderr, expected", [(b"An error occurred (404) when calling HeadObject: absent", None),
    (b"An error occurred (AccessDenied) when calling HeadObject: 404", "BACKUP_PUBLISHER_ACCESS_DENIED"),
    (b"secret=synthetic confidential value", "BACKUP_PUBLISHER_PROVIDER_UNCONFIRMED")])
def test_only_actual_head_not_found_means_absent(stderr, expected):
    aws = cloud.ScopedAWS(runner=lambda *a, **kw: SimpleNamespace(returncode=1, stdout=b"", stderr=stderr))
    aws.publisher_credentials = {"AccessKeyId": "synthetic", "SecretAccessKey": "private"}
    if expected is None:
        assert aws.publisher_call("head-object", *probe_args()) is None
    else:
        with pytest.raises(cloud.BackupError, match=expected):
            aws.publisher_call("head-object", *probe_args())


@pytest.mark.parametrize("change", ["bucket", "region", "owner", "endpoint", "prefix", "extra", "duplicate"])
def test_probe_cannot_escape_scope(change):
    aws = cloud.ScopedAWS(runner=lambda *a, **kw: pytest.fail("Provider must not be called"))
    args = probe_args()
    indexes = {"bucket": 7, "region": 1, "owner": 5, "endpoint": 3, "prefix": 9}
    if change in indexes:
        args[indexes[change]] = "foreign"
    else:
        args.extend(["--profile", "owner"] if change == "extra" else ["--bucket", cloud.BUCKET])
    with pytest.raises(cloud.Held):
        aws.publisher_call("head-object", *args)


def test_journal_cannot_target_foreign_iam_user():
    record = cloud.fresh_record()
    record["bootstrap"] = {"name": "unrelated", "nonce": "a" * 32, "state": "reserved",
        "expires_at": datetime.now(UTC).isoformat(), "positive_probe": False, "revocation_verified": False}
    with pytest.raises(cloud.Held, match="JOURNAL_INVALID"):
        cloud.validate_record(record)


def test_default_is_review_only(monkeypatch, capsys):
    monkeypatch.setattr(__import__("sys"), "argv", ["backup_provision.py"])
    monkeypatch.setattr(cloud, "ScopedAWS", lambda: pytest.fail("No provider construction"))
    assert cloud.main() == 0
    assert '"provider_operations": 0' in capsys.readouterr().out


@pytest.mark.parametrize("operation", ["create-user", "put-user-policy", "create-access-key"])
def test_unknown_bootstrap_mutation_preserves_deny_and_owned_reconciliation(setup, operation):
    provider, journal, _, _, make = setup
    provider.fail_after = ("iam", operation)
    with pytest.raises(cloud.Held):
        make().apply(install_host=installed)
    entry = journal.value["bootstrap"]
    assert provider.users[entry["name"]]["policies"][cloud.TEMP_POLICY] == cloud.DENY
    assert not provider.users[entry["name"]]["keys"]
    assert provider.bucket_state is None
    count = len(provider.users)
    with pytest.raises(cloud.Held, match="WAIT_FOR_ORIGINAL_EXPIRY"):
        make().apply(install_host=installed)
    assert len(provider.users) == count


def test_probe_receipt_extra_field_and_false_production_claim_rejected():
    receipt = {"schema": "abr-synthetic-backup-storage-probe-v1", "status": "verified_deleted",
        "object_id": "d0458d88-e9a1-44bc-ae5f-5ecb4f86dbd3", "deployment_id": cloud.DEPLOYMENT,
        "bucket": cloud.BUCKET, "region": cloud.REGION, "encrypted_upload_readback": True,
        "decrypted_nonce_verified": True, "delete_absence_verified": True, "business_data_used": False,
        "database_accessed": False, "release_approvals_created": False, "production_backup_accepted": False,
        "completed_at": datetime.now(UTC).isoformat()}
    assert cloud.validate_probe_record(receipt, receipt=True) == receipt
    for modified in (dict(receipt, extra_secret="confidential"), dict(receipt, production_backup_accepted=True)):
        with pytest.raises(cloud.Held, match="RECEIPT_INVALID"):
            cloud.validate_probe_record(modified, receipt=True)


def test_changed_configuration_cannot_replay_journal():
    record = cloud.fresh_record()
    record["configuration_sha256"] = "0" * 64
    with pytest.raises(cloud.Held, match="JOURNAL_INVALID"):
        cloud.validate_record(record)


def test_exact_uuid_prefix_list_is_allowed_but_no_partial_uuid():
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=b'{"KeyCount":0}', stderr=b"")
    aws = cloud.ScopedAWS(runner=runner)
    aws.publisher_credentials = {"AccessKeyId": "synthetic", "SecretAccessKey": "private"}
    args = probe_args()[:8] + ["--prefix", cloud.PREFIX + "d0458d88-e9a1-44bc-ae5f-5ecb4f86dbd3"]
    assert aws.publisher_call("list-objects-v2", *args) == {"KeyCount": 0}
    assert len(calls) == 1
    args[-1] = cloud.PREFIX + "d045"
    with pytest.raises(cloud.Held, match="LIST_OUTSIDE_PREFIX"):
        aws.publisher_call("list-objects-v2", *args)


@pytest.mark.parametrize("change", ["attached", "groups", "policy", "login"])
def test_temporary_extra_authority_retains_deny_before_cleanup(setup, change):
    provider, journal, _, _, make = setup
    instance = make()
    instance.bootstrap_start()
    name = journal.value["bootstrap"]["name"]
    user = provider.users[name]
    if change == "policy":
        user["policies"]["unrelated"] = cloud.publisher_policy()
    elif change == "login":
        user["login"] = True
    else:
        user[change] = ["unrelated"]
    with pytest.raises(cloud.Held, match="EXTRA_AUTHORITY_RETAIN_DENY"):
        instance.bootstrap_finish()
    assert user["policies"][cloud.TEMP_POLICY] == cloud.DENY and name in provider.users


def test_inspection_only_uses_read_policy_and_reports_order_without_bucket_writes(setup):
    provider, _, _, _, make = setup
    make().apply(install_host=installed)
    policy = provider.bucket_state["configuration"]["bucket-policy"]["Policy"]
    value = cloud.policy_document(policy)
    value["Statement"][0]["Resource"].reverse()
    provider.bucket_state["configuration"]["bucket-policy"]["Policy"] = cloud.json.dumps(value)
    count = len(provider.operations)
    result = make().inspect()
    assert {"path": "/Statement/0/Resource", "difference": "same_members_different_order"} in result["checks"]["bucket_policy"]["differences"]
    assert result["bucket_mutations"] == 0 and result["object_operations"] == 0 and result["s3_revocation_verified"]
    operations = provider.operations[count:]
    assert not any(service == "s3api" and operation.startswith(("put-", "create-", "delete-", "list-")) for service, operation, _ in operations)
    policies = [cloud.policy_document(params["PolicyDocument"]) for service, operation, params in operations
        if service == "iam" and operation == "put-user-policy"]
    allowed = policies[0]["Statement"]
    assert all(action.startswith("s3:Get") for statement in allowed for action in statement["Action"])


def test_public_configuration_diagnostics_never_reflect_unknown_values_or_keys():
    secret = "synthetic confidential value"
    result = cloud.public_differences({"Policy": {"Resource": ["expected"]}}, {"Policy": {"Resource": [secret], secret: True}})
    assert secret not in str(result)


@pytest.mark.parametrize("types", [["SSE-C"], ["NONE"], []])
def test_encryption_detail_projects_only_documented_enums(types):
    value = {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
        "BucketKeyEnabled": False, "BlockedEncryptionTypes": {"EncryptionType": types}}]}
    detail = cloud.public_encryption_detail(value)
    assert detail["rules"][0]["blocked_types"] == types
    assert detail["rules"][0]["unknown_rule_fields_count"] == 0
    secret = "synthetic confidential"
    value["Rules"][0]["BlockedEncryptionTypes"]["EncryptionType"] = [secret]
    value["Rules"][0][secret] = secret
    assert secret not in str(cloud.public_encryption_detail(value))


def test_actual_sse_c_blocked_default_is_accepted_and_recorded(setup, monkeypatch):
    provider, _, _, _, make = setup
    original = provider.bootstrap
    def observed(operation, params):
        value = original(operation, params)
        if operation == "get-bucket-encryption":
            rule = value["ServerSideEncryptionConfiguration"]["Rules"][0]
            rule.update(BucketKeyEnabled=False, BlockedEncryptionTypes={"EncryptionType": ["SSE-C"]})
        return value
    monkeypatch.setattr(provider, "bootstrap", observed)
    result = make().apply(install_host=installed)
    assert result["encryption_observation"]["rules"][0]["blocked_types"] == ["SSE-C"]
    assert cloud.bucket_configuration()["encryption"] == {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}


@pytest.mark.parametrize("change", ["none", "empty", "unknown", "extra", "kms", "bucket_key_true", "outer_extra"])
def test_encryption_normalization_refuses_weakened_or_unknown_configuration(change):
    expected = cloud.bucket_configuration()["encryption"]
    actual = deepcopy(expected)
    rule = actual["Rules"][0]
    rule.update(BucketKeyEnabled=False, BlockedEncryptionTypes={"EncryptionType": ["SSE-C"]})
    if change in {"none", "empty", "unknown"}:
        rule["BlockedEncryptionTypes"]["EncryptionType"] = {"none": ["NONE"], "empty": [], "unknown": ["unknown"]}[change]
    elif change == "extra":
        rule["BlockedEncryptionTypes"]["unknown"] = "do not ignore"
    elif change == "kms":
        rule["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] = "aws:kms"
    elif change == "bucket_key_true":
        rule["BucketKeyEnabled"] = True
    else:
        actual["unknown"] = True
    assert cloud.normalize_encryption(actual) != expected


def synthetic_probe_receipt():
    return {"schema": "abr-synthetic-backup-storage-probe-v1", "status": "verified_deleted",
        "object_id": "d0458d88-e9a1-44bc-ae5f-5ecb4f86dbd3", "deployment_id": cloud.DEPLOYMENT,
        "bucket": cloud.BUCKET, "region": cloud.REGION, "encrypted_upload_readback": True,
        "decrypted_nonce_verified": True, "delete_absence_verified": True, "business_data_used": False,
        "database_accessed": False, "release_approvals_created": False, "production_backup_accepted": False,
        "completed_at": datetime.now(UTC).isoformat()}


def test_probe_only_reuses_completed_custody_with_readonly_iam_no_host_or_new_keys(setup):
    provider, journal, private, identity, make = setup
    make().apply(install_host=installed)
    identity.value["stage"] = "complete"  # Real custody.install writes this after exact remote receipt.
    prior = deepcopy(private.value), deepcopy(identity.value), deepcopy(journal.value["bootstrap"])
    count = len(provider.operations)
    result = make().probe_only(lambda _: synthetic_probe_receipt())
    assert result["iam_mutations"] == 0 and result["keys_created_or_rotated"] == 0 and result["host_operations"] == 0
    assert prior == (private.value, identity.value, journal.value["bootstrap"])
    assert all(service == "iam" and operation.startswith(("get-", "list-")) for service, operation, _ in provider.operations[count:])
    assert publisher_creates(provider) == 1


@pytest.mark.parametrize("defect", ["not_installed", "wrong_key", "extra_policy", "custody_incomplete"])
def test_probe_only_refuses_incomplete_or_changed_authority_without_mutating(setup, defect):
    provider, journal, _, identity, make = setup
    make().apply(install_host=installed)
    identity.value["stage"] = "complete"
    if defect == "not_installed":
        journal.value["host_installed"] = False
    elif defect == "wrong_key":
        provider.users[cloud.USER]["keys"][0]["AccessKeyId"] = "AKIA" + "9" * 16
    elif defect == "extra_policy":
        provider.users[cloud.USER]["policies"]["extra"] = cloud.DENY
    else:
        identity.value["stage"] = "remote_pending"
    count = len(provider.operations)
    with pytest.raises(cloud.Held):
        make().probe_only(lambda _: pytest.fail("Probe must not execute"))
    assert all(service == "iam" and operation.startswith(("get-", "list-")) for service, operation, _ in provider.operations[count:])


def test_publisher_metadata_read_retries_definite_denial_but_mutation_does_not():
    calls, waits = [], []
    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1, stdout=b"", stderr=b"An error occurred (AccessDenied): private text")
    aws = cloud.ScopedAWS(runner=runner, sleep=waits.append)
    aws.publisher_credentials = {"AccessKeyId": "synthetic", "SecretAccessKey": "private"}
    with pytest.raises(cloud.BackupError, match="PUBLISHER_ACCESS_DENIED"):
        aws.publisher_call("get-bucket-location", *probe_args()[:8])
    assert len(calls) == 8 and len(waits) == 7
    calls.clear()
    waits.clear()
    args = probe_args() + ["--body", "synthetic.enc", "--if-none-match", "*", "--server-side-encryption", "AES256"]
    with pytest.raises(cloud.BackupError, match="PUBLISHER_ACCESS_DENIED"):
        aws.publisher_call("put-object", *args)
    assert len(calls) == 1 and waits == []


def test_probe_staging_accepts_only_same_acl_verified_virtualized_directory(tmp_path, monkeypatch):
    from pathlib import Path
    base = tmp_path / "Local/MaintainMedia/aws"
    logical = base / "backup-key-escrow-983c39eb"
    actual = base.parents[1] / "Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/MaintainMedia/aws/backup-key-escrow-983c39eb"
    actual.mkdir(parents=True)
    monkeypatch.setattr(custody, "BASE", base)
    old_resolve, old_stat = Path.resolve, Path.stat
    monkeypatch.setattr(Path, "resolve", lambda p, **kw: actual if p == logical else old_resolve(p, **kw))
    monkeypatch.setattr(Path, "stat", lambda p, **kw: old_stat(actual if p == logical else p, **kw))
    seen = []
    module = SimpleNamespace(ordinary=lambda p: seen.append(("ordinary", p)),
        verify_acl=lambda p, **kw: seen.append(("acl", p, kw["directory"])))
    assert cloud.probe_staging(logical, module) == actual
    assert ("ordinary", logical) in seen and ("ordinary", actual) in seen
    assert ("acl", logical, True) in seen and ("acl", actual, True) in seen
    monkeypatch.setattr(cloud.os.path, "samestat", lambda *a: False)
    with pytest.raises(cloud.Held, match="IDENTITY_MISMATCH"):
        cloud.probe_staging(logical, module)


def test_probe_staging_refuses_outside_location_or_reparse_metadata(tmp_path, monkeypatch):
    from pathlib import Path
    base = tmp_path / "Local/MaintainMedia/aws"
    logical = base / "backup-key-escrow-983c39eb"
    outside = tmp_path / "unrelated"
    outside.mkdir()
    monkeypatch.setattr(custody, "BASE", base)
    old_resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda p, **kw: outside if p == logical else old_resolve(p, **kw))
    module = SimpleNamespace(ordinary=lambda _: None, verify_acl=lambda *a, **kw: None)
    with pytest.raises(cloud.Held, match="OUTSIDE_CUSTODY"):
        cloud.probe_staging(logical, module)
    def refuse_reparse(_):
        raise ValueError("REPARSE_PATH_REFUSED")
    module.ordinary = refuse_reparse
    with pytest.raises(ValueError, match="REPARSE_PATH_REFUSED"):
        cloud.probe_staging(logical, module)
