"""Infrastructure boundaries with synthetic new keys; no cloud or existing secrets."""
from __future__ import annotations

import copy
import io
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import backup_identity_client as client
import backup_infrastructure as infra
import backup_install_identity as host
import pytest
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def custody():
    return client.new_recipient()


@pytest.fixture
def material(custody):
    return {"account_id": infra.ACCOUNT, "region": infra.REGION, "deployment_id": infra.DEPLOYMENT,
        "bucket": infra.BUCKET, "access_key_id": "AKIA" + "T" * 16, "secret_access_key": "S" * 40,
        "public_recipient_pem": custody["material"]["public_recipient_pem"]}


def test_exact_private_sydney_plan_and_minimal_publisher():
    value = infra.plan()
    assert value["maximum_bytes"] == 100_000_000_000 and value["monthly_budget_usd"] == 5
    assert value["runtime_capabilities_enabled"] == [] and not value["release_approvals_created"]
    assert not value["backup_private_key_on_host"] and value["additional_servers"] == 0
    bucket = value["bucket_configuration"]
    assert all(bucket["public_access_block"].values())
    assert bucket["create"]["CreateBucketConfiguration"] == {"LocationConstraint": "ap-southeast-2"}
    assert bucket["ownership_controls"] == {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}
    assert bucket["lifecycle"]["Rules"][0]["Expiration"]["Days"] == 34
    statements = infra.publisher_policy()["Statement"]
    for item in statements:
        assert item["Effect"] == "Allow" and item["Condition"]["Bool"]["aws:SecureTransport"] == "true"
        assert item["Resource"] in {infra.BUCKET_ARN, infra.OBJECT_ARN}
        actions = [item["Action"]] if isinstance(item["Action"], str) else item["Action"]
        assert not any(action.startswith(("iam:", "s3:PutBucket", "s3:ListAll")) or "Version" in action and action != "s3:GetBucketVersioning" for action in actions)
    listing = next(item for item in statements if item["Action"] == "s3:ListBucket")
    assert listing["Condition"]["StringLike"]["s3:prefix"] == [infra.PREFIX, infra.PREFIX + "*"]
    putting = next(item for item in statements if item["Action"] == "s3:PutObject")
    assert putting["Condition"]["StringEquals"]["s3:if-none-match"] == "*"
    assert putting["Condition"]["StringEquals"]["s3:x-amz-server-side-encryption"] == "AES256"


def test_bootstrap_is_one_bucket_short_lived_and_has_no_data_or_iam_permissions():
    expires = datetime.now(UTC) + timedelta(minutes=29)
    for item in infra.bootstrap_policy(expires)["Statement"]:
        assert item["Resource"] == infra.BUCKET_ARN
        assert item["Condition"]["DateLessThan"]["aws:CurrentTime"] == expires.isoformat()
        actions = [item["Action"]] if isinstance(item["Action"], str) else item["Action"]
        assert not any(action.startswith("iam:") or action in {
            "s3:DeleteBucket", "s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:PutBucketVersioning"} for action in actions)
    for invalid in (datetime.now(UTC) - timedelta(seconds=1), datetime.now(UTC) + timedelta(minutes=31), datetime.now(UTC).replace(tzinfo=None)):
        with pytest.raises(ValueError, match="THIRTY_MINUTES"):
            infra.bootstrap_policy(invalid)


@pytest.mark.parametrize("field,value", [("secret_access_key", "s" * 39 + "\n"), ("access_key_id", "ASIA" + "T" * 16),
    ("region", "us-east-1"), ("bucket", "some-other-bucket"), ("account_id", "000000000000")])
def test_identity_rejects_wrong_target_session_key_and_ini_injection(material, field, value):
    with pytest.raises(ValueError):
        host.validate_material(material | {field: value})


def test_private_key_is_never_a_valid_host_recipient(material, custody):
    with pytest.raises(ValueError):
        host.validate_material(material | {"public_recipient_pem": custody["material"]["private_recipient_pem"]})
    produced = host.contents(material)
    assert set(produced) == set(host.FILES)
    assert all(b"PRIVATE KEY" not in value for value in produced.values())
    assert "authority" not in produced and "runtime.env" not in produced and "pilot.yaml" not in produced
    assert json.loads(produced["infrastructure.json"])["maximum_bytes"] == 100_000_000_000


@pytest.fixture
def journal_files(tmp_path, monkeypatch):
    """Real identities/links while emulating Linux ownership on Windows."""
    monkeypatch.setattr(host, "DIRECTORY", tmp_path)
    module = host.publisher()
    native_metadata = module._metadata
    raw_read_text, raw_read_bytes = Path.read_text, Path.read_bytes

    class MetadataPath:
        def __init__(self, path, mode, group):
            self.path, self.mode, self.group = path, mode, group
        def lstat(self):
            info = self.path.lstat()
            return SimpleNamespace(st_mode=(info.st_mode & ~0o777) | (self.mode or 0o600),
                st_nlink=info.st_nlink, st_uid=0, st_gid=self.group or 0,
                st_dev=info.st_dev, st_ino=info.st_ino, st_size=info.st_size)

    def metadata(path, **options):
        return native_metadata(MetadataPath(path, options.get("mode"), options.get("group")), **options)
    def persist(record):
        temporary = tmp_path / "public-journal-next"
        temporary.write_text(json.dumps(record))
        os.replace(temporary, tmp_path / "installation.json")
    def guarded_text(path, *args, **kwargs):
        assert path.name not in host.FILES, "Must not read existing credential/configuration contents"
        return raw_read_text(path, *args, **kwargs)
    def guarded_bytes(path, *args, **kwargs):
        assert path.name not in host.FILES, "Must not read existing credential/configuration contents"
        return raw_read_bytes(path, *args, **kwargs)
    monkeypatch.setattr(module, "_metadata", metadata)
    monkeypatch.setattr(module, "_save_marker", persist)
    monkeypatch.setattr(Path, "read_text", guarded_text)
    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)
    monkeypatch.setattr(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), raising=False)
    monkeypatch.setattr(os, "fchown", lambda *args: None, raising=False)
    monkeypatch.setattr(os, "fchmod", lambda *args: None, raising=False)
    return module, persist, raw_read_bytes


@pytest.mark.parametrize("boundary", range(1, 23))
@pytest.mark.parametrize("after", [False, True])
def test_partial_publication_recovers_same_inode_without_secret_reads(material, journal_files, monkeypatch, boundary, after):
    module, persist, read_generated = journal_files
    count = 0
    def interrupt(record):
        nonlocal count
        count += 1
        if count == boundary and not after:
            raise OSError("Synthetic interruption")
        persist(record)
        if count == boundary and after:
            raise OSError("Synthetic interruption")
    monkeypatch.setattr(module, "_save_marker", interrupt)
    with pytest.raises(OSError, match="Synthetic"):
        host.install_material(material, 123, module)
    prior = {name: (host.DIRECTORY / name).stat().st_ino for name in host.FILES if (host.DIRECTORY / name).exists()}
    monkeypatch.setattr(module, "_save_marker", persist)
    result = host.install_material(material, 123, module)
    assert result["status"] == "private_backup_identity_installed" and result["services_enabled"] is False
    assert all((host.DIRECTORY / name).stat().st_ino == inode for name, inode in prior.items())
    assert all(read_generated(host.DIRECTORY / name) == content for name, content in host.contents(material).items())
    assert host.install_material(material, 123, module)["replayed"]
    assert not list(host.DIRECTORY.glob(".runtime-*.pending"))


def test_unrelated_files_and_changed_identity_are_never_overwritten(material, journal_files):
    module, _, read_generated = journal_files
    target = host.DIRECTORY / "credentials"
    target.write_bytes(b"unrelated synthetic file")
    with pytest.raises(ValueError, match="UNRELATED"):
        host.install_material(material, 123, module)
    assert read_generated(target) == b"unrelated synthetic file"
    target.unlink()
    host.install_material(material, 123, module)
    inode = target.stat().st_ino
    with pytest.raises(ValueError, match="MATERIAL_OR_STATE_MISMATCH"):
        host.install_material(material | {"secret_access_key": "N" * 40}, 123, module)
    assert target.stat().st_ino == inode


class MemoryEscrow:
    def __init__(self, data=None):
        self.data, self.saves = copy.deepcopy(data), []
        self.path = SimpleNamespace(exists=lambda: self.data is not None)
    def recover(self):
        pass
    def load(self):
        return client.validate_state(copy.deepcopy(self.data))
    def save(self, value):
        self.data = copy.deepcopy(client.validate_state(value))
        self.saves.append(copy.deepcopy(value))


def test_private_rsa_never_crosses_ssh_boundary_and_uncertain_retry_reuses_material(material, custody):
    private, identity = MemoryEscrow(custody), MemoryEscrow()
    credentials = {"AccessKeyId": material["access_key_id"], "SecretAccessKey": material["secret_access_key"]}
    client.prepare(credentials, private, identity)
    sends = []
    def runner(command, data, timeout):
        assert command == ["pinned-synthetic-ssh"] and timeout == 180
        assert b"PRIVATE KEY" not in data and b"private_recipient" not in data
        assert private.data["material"]["private_recipient_pem"].encode() not in data
        sends.append(data)
        if len(sends) == 1:
            raise TimeoutError("Synthetic uncertain completion")
        return SimpleNamespace(returncode=0, stdout=json.dumps(host.receipt(json.loads(data), host.publisher(), replayed=True)).encode())
    with pytest.raises(TimeoutError):
        client.install(private, identity, ["pinned-synthetic-ssh"], runner)
    assert identity.data["stage"] == "remote_pending"
    assert client.install(private, identity, ["pinned-synthetic-ssh"], runner)["services_enabled"] is False
    assert sends[0] == sends[1] and identity.data["stage"] == "complete"
    assert not private.saves
    with pytest.raises(ValueError, match="ROTATION"):
        client.prepare(credentials | {"SecretAccessKey": "N" * 40}, private, identity)


def test_own_escrow_cannot_be_swapped_or_claimed_for_another_deployment(material, custody):
    private, identity = MemoryEscrow(custody), MemoryEscrow(client.state("publisher_identity", material))
    with pytest.raises(ValueError, match="KIND_MISMATCH"):
        client.install(identity, private, [], lambda *_: pytest.fail("No external call"))
    with pytest.raises(ValueError, match="TARGET_OR_MATERIAL"):
        client.validate_state(custody | {"deployment_id": "00000000-0000-0000-0000-000000000000"})


def test_remote_valid_receipt_with_extra_secret_field_is_not_reflected(material, custody):
    private, identity = MemoryEscrow(custody), MemoryEscrow(client.state("publisher_identity", material))
    returned = host.receipt(material, host.publisher(), replayed=False) | {
        "provider_debug": material["secret_access_key"], "extra_private": custody["material"]["private_recipient_pem"]}
    result = client.install(private, identity, [], lambda *_args, **_kwargs:
        SimpleNamespace(returncode=0, stdout=json.dumps(returned).encode()))
    assert "provider_debug" not in result and "extra_private" not in result
    assert material["secret_access_key"] not in json.dumps(result) and "PRIVATE KEY" not in json.dumps(result)


@pytest.fixture
def directory_files(tmp_path, monkeypatch):
    """Real directory/journal with Linux modes/owner emulated on Windows."""
    target = tmp_path / "backup"
    monkeypatch.setattr(host, "DIRECTORY", target)
    module = host.publisher()
    native_lstat, native_mkdir, native_metadata = Path.lstat, Path.mkdir, module._metadata
    mode = {"value": 0o700, "group": 0}
    failure = {"at": None, "after": False}
    events = []
    def boundary(label, action):
        if failure["at"] == label and not failure["after"]:
            raise OSError("Synthetic directory interruption")
        value = action()
        events.append(label)
        if failure["at"] == label and failure["after"]:
            raise OSError("Synthetic directory interruption")
        return value
    def mkdir(path, *args, **kwargs):
        if path != target:
            return native_mkdir(path, *args, **kwargs)
        return boundary("mkdir", lambda: native_mkdir(path, *args, **kwargs))
    def chown(path, user, group):
        assert path == target and user == 0
        return boundary("chown", lambda: mode.update(group=group))
    def chmod(path, value, *args, **kwargs):
        assert path == target
        return boundary("chmod", lambda: mode.update(value=value))
    def lstat(path, *args, **kwargs):
        info = native_lstat(path, *args, **kwargs)
        if path != target:
            return info
        return SimpleNamespace(st_mode=(info.st_mode & ~0o777) | mode["value"], st_nlink=info.st_nlink,
            st_uid=0, st_gid=mode["group"], st_dev=info.st_dev, st_ino=info.st_ino, st_size=info.st_size,
            st_file_attributes=getattr(info, "st_file_attributes", 0))
    def metadata(path, **options):
        info = native_lstat(path)
        virtual = SimpleNamespace(lstat=lambda: SimpleNamespace(st_mode=(info.st_mode & ~0o777) | options["mode"],
            st_nlink=info.st_nlink, st_uid=0, st_gid=0, st_dev=info.st_dev, st_ino=info.st_ino, st_size=info.st_size))
        return native_metadata(virtual, **options)
    def save(record, _module):
        def write():
            if record["state"] == "ready":
                assert events[-1] == "sync_directory", "Child permission fsync must precede ready journal"
            temporary = tmp_path / "public-directory-journal-next"
            temporary.write_bytes(infra.canonical(record))
            os.replace(temporary, tmp_path / ".backup-directory-983c39eb.json")
        label = "ready" if record["state"] == "ready" else "reserve" if record["identity"] is None else "own_inode"
        return boundary(label, write)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "chmod", chmod)
    monkeypatch.setattr(os, "chown", chown, raising=False)
    monkeypatch.setattr(module, "_metadata", metadata)
    monkeypatch.setattr(host, "save_directory_record", save)
    monkeypatch.setattr(host, "sync_directory", lambda path: boundary("sync_directory", lambda: None))
    return target, module, failure, mode


@pytest.mark.parametrize("boundary", ["reserve", "mkdir", "own_inode", "chown", "chmod", "sync_directory", "ready"])
@pytest.mark.parametrize("after", [False, True])
def test_directory_creation_interruption_recovers_only_reserved_empty_inode(directory_files, boundary, after):
    target, module, failure, mode = directory_files
    failure.update(at=boundary, after=after)
    with pytest.raises(OSError, match="Synthetic directory"):
        host.establish_directory(123, module)
    previous = target.lstat().st_ino if target.exists() else None
    failure["at"] = None
    host.establish_directory(123, module)
    assert mode == {"value": 0o750, "group": 123}
    assert previous is None or target.lstat().st_ino == previous
    record = json.loads((target.parent / ".backup-directory-983c39eb.json").read_bytes())
    assert record["state"] == "ready" and record["identity"]["inode"] == target.lstat().st_ino
    (target / "synthetic-installed-file").write_bytes(b"new synthetic file")
    host.establish_directory(123, module)  # Completed directory never needs empty-path adoption.


def test_directory_recovery_refuses_unrelated_or_nonempty_unfinished_target(directory_files):
    target, module, failure, _ = directory_files
    target.mkdir()
    with pytest.raises(ValueError, match="UNRELATED_BACKUP_DIRECTORY"):
        host.establish_directory(123, module)
    target.rmdir()
    failure.update(at="chown", after=False)
    with pytest.raises(OSError):
        host.establish_directory(123, module)
    (target / "unrelated-file").write_bytes(b"must remain")
    failure["at"] = None
    with pytest.raises(ValueError, match="PARTIAL_DIRECTORY_NOT_EMPTY"):
        host.establish_directory(123, module)
    assert (target / "unrelated-file").read_bytes() == b"must remain"


def test_review_entrypoints_never_read_stdin_or_call_install(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["review"])
    monkeypatch.setattr(host, "install", lambda *_: pytest.fail("Review only"))
    monkeypatch.setattr(client, "prepare", lambda *_: pytest.fail("Review only"))
    monkeypatch.setattr(client, "install", lambda *_: pytest.fail("Review only"))
    assert host.main() == 0 and client.main() == 0
    assert capsys.readouterr().out.count("review_only") == 2


def test_confidential_host_stdin_error_is_redacted(material, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["host", "--apply"])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(material).encode())))
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    def unavailable(_):
        raise RuntimeError(json.dumps(material))
    monkeypatch.setattr(host, "install", unavailable)
    assert host.main() == 3
    output = capsys.readouterr().out
    assert "BACKUP_IDENTITY_INSTALLATION_UNAVAILABLE" in output
    assert material["access_key_id"] not in output and material["secret_access_key"] not in output


@pytest.mark.skipif(os.name != "nt", reason="Windows CurrentUser DPAPI")
def test_new_synthetic_recipient_uses_real_user_dpapi_roundtrip(custody, tmp_path):
    module = client.helper()
    directory = tmp_path / "owned-new-backup-test"
    module.secure_directory(directory)
    escrow = module.Escrow(directory / "synthetic-private.dpapi")
    escrow.save(custody)
    raw = escrow.path.read_bytes()
    assert b"PRIVATE KEY" not in raw and custody["material"]["private_recipient_pem"].encode() not in raw
    restored = escrow.load()
    assert restored == custody
    key = serialization.load_pem_private_key(restored["material"]["private_recipient_pem"].encode(), password=None)
    assert key.key_size == 3072
