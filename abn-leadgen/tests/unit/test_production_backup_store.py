import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "ops/aws"))
from backup_crypto import BackupError
from backup_store import S3Store


class FakeS3(S3Store):
    def __init__(self):
        super().__init__(Path(__file__).resolve(), "synthetic-test-bucket", uuid4(), account_id="123456789012")
        self.calls, self.responses = [], {}
        self.responses = {
            "get-bucket-location": {"LocationConstraint": "ap-southeast-2"},
            "get-public-access-block": {"PublicAccessBlockConfiguration": {key: True for key in (
                "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")}},
            "get-bucket-policy-status": {"PolicyStatus": {"IsPublic": False}},
            "get-bucket-versioning": {},
            "get-bucket-lifecycle-configuration": {"Rules": [{"Status": "Enabled", "Filter": {"Prefix": self.prefix}, "Expiration": {"Days": 34}}]},
            "list-objects-v2": {"Contents": []},
        }

    def _call(self, operation, *arguments):
        self.calls.append((operation, arguments))
        return self.responses[operation]


def test_readonly_provider_preflight():
    store = FakeS3()
    assert store.validate()["private"] is True
    assert all(operation.startswith("get-") for operation, _ in store.calls)


def test_expiry_rechecks_current_authority_before_every_delete(monkeypatch):
    store = FakeS3()
    ids = [str(uuid4()), str(uuid4())]
    monkeypatch.setattr(store, "inventory", lambda: [{"object_id": value} for value in ids])
    deleted = set()
    monkeypatch.setattr(store, "_head_allow_absent", lambda value: None if value in deleted else
        {"expires_at": (datetime.now(UTC)-timedelta(days=1)).isoformat()})
    def request(operation, *arguments):
        assert operation == "delete-object"
        deleted.add(arguments[-1].removeprefix(store.prefix))
    monkeypatch.setattr(store, "_call", request)
    admissions = []
    def admit():
        admissions.append(True)
        if len(admissions) == 2:
            raise BackupError("AUTHORITY_WITHDRAWN")
    with pytest.raises(BackupError, match="WITHDRAWN"):
        store.expire(before_delete=admit)
    assert deleted == {ids[0]} and len(admissions) == 2


@pytest.mark.parametrize("condition", ["region", "public", "versioned", "expiry"])
def test_wrong_storage_policy_rejected(condition):
    store = FakeS3()
    if condition == "region":
        store.responses["get-bucket-location"]["LocationConstraint"] = "us-east-1"
    elif condition == "public":
        store.responses["get-bucket-policy-status"]["PolicyStatus"]["IsPublic"] = True
    elif condition == "versioned":
        store.responses["get-bucket-versioning"]["Status"] = "Suspended"
    else:
        store.responses["get-bucket-lifecycle-configuration"]["Rules"][0]["Expiration"]["Days"] = 35
    with pytest.raises(BackupError):
        store.validate()


def test_inventory_rejects_foreign_key():
    store = FakeS3()
    store.responses["list-objects-v2"] = {"Contents": [{"Key": "foreign/" + str(uuid4()), "Size": 1}]}
    with pytest.raises(BackupError, match="FOREIGN"):
        store.inventory()


def test_storage_cap_prevents_upload(tmp_path):
    store = FakeS3()
    store.maximum_bytes = 1
    path = tmp_path / "encrypted"
    path.write_bytes(b"two")
    with pytest.raises(BackupError, match="CAP_REACHED"):
        store.put_verified(uuid4(), path, kind="database", expires_at=datetime.now(UTC) + timedelta(days=34))
    assert not any(operation == "put-object" for operation, _ in store.calls)


def test_large_single_object_fails_before_any_provider_request():
    store = FakeS3()
    large = SimpleNamespace(stat=lambda: SimpleNamespace(st_size=4 * 1024**3 + 1))
    with pytest.raises(BackupError, match="FOUR_GIB_LIMIT"):
        store.put_verified(uuid4(), large, kind="database", expires_at=datetime.now(UTC) + timedelta(days=34))
    assert store.calls == []


def test_expiry_only_deletes_owned_expired_object():
    store = FakeS3()
    expired, current = str(uuid4()), str(uuid4())
    now = datetime.now(UTC)
    store.responses["list-objects-v2"] = {"Contents": [{"Key": store.prefix + item, "Size": 5} for item in (expired, current)]}
    headers = {expired: {"expires_at": (now-timedelta(seconds=1)).isoformat()}, current: {"expires_at": (now+timedelta(days=1)).isoformat()}}
    store.head = lambda key: headers.get(key)
    original = store._call
    def call(operation, *arguments):
        if operation == "delete-object":
            store.calls.append((operation, arguments))
            headers.pop(arguments[-1].removeprefix(store.prefix))
            return {}
        return original(operation, *arguments)
    store._call = call
    assert store.expire(now=now)["deleted"] == [expired]
    assert current in headers


def test_readback_preserves_existing_file(tmp_path):
    store = FakeS3()
    path = tmp_path / "encrypted"
    path.write_bytes(b"encrypted sample")
    copied = path.with_name(path.name + ".remote-readback")
    copied.write_bytes(b"do not remove")
    store.responses["put-object"] = {}
    with pytest.raises(BackupError, match="READBACK_PATH_EXISTS"):
        store.put_verified(uuid4(), path, kind="database", expires_at=datetime.now(UTC) + timedelta(days=34))
    assert copied.read_bytes() == b"do not remove"


def test_only_genuine_head_not_found_code_is_absence(monkeypatch):
    import subprocess
    store = S3Store(Path(__file__).resolve(), "synthetic-test-bucket", uuid4(), account_id="123456789012")
    response = SimpleNamespace(returncode=1, stdout=b"", stderr=b"An error occurred (403) when calling the HeadObject operation: key includes 404 but access is denied")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: response)
    with pytest.raises(BackupError, match="HEAD_OBJECT_FAILED"):
        store.head(uuid4())
    response.stderr = b"An error occurred (404) when calling the HeadObject operation: Not Found"
    assert store.head(uuid4()) is None
