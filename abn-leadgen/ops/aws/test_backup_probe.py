"""Synthetic encrypted provider protocol, never AWS credentials or cloud I/O."""
import io
import json
from pathlib import Path

import backup_probe as probe
import pytest
from backup_crypto import BackupError, decrypt_stream
from backup_infrastructure import ACCOUNT, BUCKET, PREFIX, REGION
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


class SyntheticS3:
    def __init__(self):
        self.objects, self.calls, self.prepared = {}, [], []
        self.uncertain_put = self.corrupt_readback = self.retain_delete = False
        self.absent_head_403 = self.all_head_403 = False
        self.uploaded = []
    def journal(self, record):
        self.prepared.append(record)
        return True
    def call(self, operation, *arguments):
        self.calls.append(operation)
        def arg(name):
            return arguments[arguments.index(name) + 1]
        assert arg("--region") == REGION and arg("--expected-bucket-owner") == ACCOUNT
        assert arg("--bucket") == BUCKET and arg("--endpoint-url") == "https://s3.ap-southeast-2.amazonaws.com"
        if operation == "get-bucket-location":
            return {"LocationConstraint": REGION}
        if operation == "get-public-access-block":
            return {"PublicAccessBlockConfiguration": {k: True for k in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")}}
        if operation == "get-bucket-policy-status":
            return {"PolicyStatus": {"IsPublic": False}}
        if operation == "get-bucket-versioning":
            return {}
        if operation == "get-bucket-lifecycle-configuration":
            return {"Rules": [{"Status": "Enabled", "Filter": {"Prefix": PREFIX}, "Expiration": {"Days": 34}}]}
        if operation == "list-objects-v2":
            values = [{"Key": name, "Size": len(value["bytes"])} for name, value in self.objects.items()
                if name.startswith(arg("--prefix"))]
            return {"Name": BUCKET, "Prefix": arg("--prefix"), "IsTruncated": False,
                "KeyCount": len(values), "Contents": values}
        object_key = arg("--key")
        if operation == "put-object":
            assert self.prepared and PREFIX + self.prepared[-1]["object_id"] == object_key
            assert arg("--if-none-match") == "*" and arg("--server-side-encryption") == "AES256"
            assert object_key not in self.objects
            content = Path(arg("--body")).read_bytes()
            self.objects[object_key] = {"bytes": content, "metadata": json.loads(arg("--metadata"))}
            self.uploaded.append(content)
            if self.uncertain_put:
                raise RuntimeError("Synthetic uncertain result with PRIVATE debug output")
            return {}
        if operation == "head-object":
            value = self.objects.get(object_key)
            if self.all_head_403 or self.absent_head_403 and value is None:
                raise BackupError("SYNTHETIC_HEAD_FORBIDDEN")
            return None if value is None else {"ContentLength": len(value["bytes"]),
                "Metadata": value["metadata"], "ETag": value["metadata"]["sha256"]}
        if operation == "get-object":
            content = self.objects[object_key]["bytes"]
            Path(arguments[-1]).write_bytes(b"corrupt" if self.corrupt_readback else content)
            return {}
        if operation == "delete-object":
            if not self.retain_delete:
                self.objects.pop(object_key)
            return {}
        raise AssertionError("Unexpected synthetic provider operation")


def test_encrypted_nonce_roundtrip_and_exact_delete_without_database(key, tmp_path):
    provider = SyntheticS3()
    result = probe.run_probe(probe.ProbeStore(provider.call), key, tmp_path, record_prepared=provider.journal)
    assert result["status"] == "verified_deleted" and not result["production_backup_accepted"]
    assert not result["business_data_used"] and not result["database_accessed"] and not result["release_approvals_created"]
    assert provider.objects == {} and len(provider.uploaded) == 1 and not list(tmp_path.iterdir())
    assert b"engineering-nonce" not in provider.uploaded[0]
    plain = io.BytesIO()
    decrypt_stream(io.BytesIO(provider.uploaded[0]), plain, key, maximum=4096)
    payload = json.loads(plain.getvalue())
    assert set(payload) == {"schema", "nonce", "deployment_id", "business_data"} and payload["business_data"] is False
    assert provider.calls[-2:] == ["delete-object", "head-object"]


def test_no_put_without_durable_public_journal_ack(key, tmp_path):
    provider = SyntheticS3()
    with pytest.raises(BackupError, match="DURABLE_JOURNAL"):
        probe.run_probe(probe.ProbeStore(provider.call), key, tmp_path, record_prepared=lambda _: None)
    assert not provider.objects and "put-object" not in provider.calls and not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["uncertain_put", "corrupt_readback"])
def test_uncertain_or_corrupt_probe_cleans_only_recorded_object(key, tmp_path, failure):
    provider = SyntheticS3()
    setattr(provider, failure, True)
    with pytest.raises(BackupError):
        probe.run_probe(probe.ProbeStore(provider.call), key, tmp_path, record_prepared=provider.journal)
    assert provider.prepared and not provider.objects and not list(tmp_path.iterdir())
    assert "delete-object" in provider.calls


def test_failed_deletion_never_returns_success_and_retains_recovery_record(key, tmp_path):
    provider = SyntheticS3()
    provider.retain_delete = True
    store = probe.ProbeStore(provider.call)
    with pytest.raises(BackupError, match="DELETE_NOT_CONFIRMED"):
        probe.run_probe(store, key, tmp_path, record_prepared=provider.journal)
    assert len(provider.objects) == 1 and len(provider.prepared) == 1 and not list(tmp_path.iterdir())
    provider.retain_delete = False
    assert probe.cleanup_probe(store, provider.prepared[0])["deleted"]
    assert not provider.objects


def test_recovery_refuses_changed_ciphertext_ownership(key, tmp_path):
    provider = SyntheticS3()
    provider.retain_delete = True
    store = probe.ProbeStore(provider.call)
    with pytest.raises(BackupError):
        probe.run_probe(store, key, tmp_path, record_prepared=provider.journal)
    provider.retain_delete = False
    provider.objects[PREFIX + provider.prepared[0]["object_id"]]["metadata"]["sha256"] = "0" * 64
    before = provider.calls.count("delete-object")
    with pytest.raises(BackupError, match="OWNERSHIP_MISMATCH"):
        probe.cleanup_probe(store, provider.prepared[0])
    assert len(provider.objects) == 1 and provider.calls.count("delete-object") == before


def test_probe_adapter_refuses_other_bucket_or_prefix_before_provider():
    provider = SyntheticS3()
    store = probe.ProbeStore(provider.call)
    with pytest.raises(BackupError, match="SCOPE"):
        store._call("put-object", "--bucket", "other", "--key", "other/123")
    with pytest.raises(BackupError, match="SCOPE"):
        store._call("delete-object", "--bucket", BUCKET, "--key", "other/123")
    assert provider.calls == []


def test_prefix_conditioned_head_403_uses_exact_authorized_list_to_prove_absence(key, tmp_path):
    provider = SyntheticS3()
    provider.absent_head_403 = True
    result = probe.run_probe(probe.ProbeStore(provider.call), key, tmp_path, record_prepared=provider.journal)
    assert result["delete_absence_verified"] and not provider.objects
    assert provider.calls[-3:] == ["delete-object", "head-object", "list-objects-v2"]


def test_head_403_for_present_object_never_becomes_absence_or_authorizes_delete(key, tmp_path):
    provider = SyntheticS3()
    provider.all_head_403 = True
    with pytest.raises(BackupError, match="HEAD_FORBIDDEN"):
        probe.run_probe(probe.ProbeStore(provider.call), key, tmp_path, record_prepared=provider.journal)
    assert len(provider.objects) == 1 and "delete-object" not in provider.calls
