"""Install only new escrowed S3 credentials/public recipient, from private stdin.

Default is review only. No AWS calls, environment reads, approval writes, existing
secret reads, runtime changes or service activation are performed here.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from backup_crypto import fingerprint, public_key
from backup_infrastructure import ACCOUNT, BUCKET, DEPLOYMENT, MAXIMUM_BYTES, REGION, canonical, plan
from cryptography.hazmat.primitives import serialization

DIRECTORY = Path("/etc/abr-engine/backup")
FIELDS = {"account_id", "region", "deployment_id", "bucket", "access_key_id", "secret_access_key", "public_recipient_pem"}
FILES = {"credentials": 0o640, "aws-config": 0o640, "public-recipient.pem": 0o640,
         "identity.env": 0o600, "infrastructure.json": 0o640}
# These primitives run only on the Linux host; Windows type stubs omit them.
native_os: Any = os


def publisher():
    """Isolate the existing inode-journal helper; never alter runtime module globals."""
    spec = importlib.util.spec_from_file_location("_backup_private_publication", Path(__file__).with_name("provision_runtime.py"))
    if spec is None or spec.loader is None:
        raise ValueError("BACKUP_INSTALLER_RUNTIME_UNAVAILABLE")
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DIRECTORY, module.FILES = DIRECTORY, FILES
    return module


def validate_material(data):
    if (not isinstance(data, dict) or set(data) != FIELDS
            or any(not isinstance(value, str) for value in data.values())
            or any(data[key] != value for key, value in {
                "account_id": ACCOUNT, "region": REGION, "deployment_id": DEPLOYMENT, "bucket": BUCKET}.items())
            or not re.fullmatch(r"AKIA[A-Z0-9]{16}", data["access_key_id"])
            or not re.fullmatch(r"[A-Za-z0-9/+=]{40}", data["secret_access_key"])):
        raise ValueError("BACKUP_NEW_IDENTITY_INPUT_INVALID")
    key = public_key(data["public_recipient_pem"].encode("ascii"))
    if key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode() != data["public_recipient_pem"]:
        raise ValueError("BACKUP_CANONICAL_PUBLIC_RECIPIENT_REQUIRED")
    return key


def contents(data):
    validate_material(data)
    return {
        "credentials": ("[abn-backup]\naws_access_key_id = " + data["access_key_id"]
                        + "\naws_secret_access_key = " + data["secret_access_key"] + "\n").encode(),
        "aws-config": ("[profile abn-backup]\nregion = " + REGION
                       + "\noutput = json\nretry_mode = standard\nmax_attempts = 2\n").encode(),
        "public-recipient.pem": data["public_recipient_pem"].encode(),
        "identity.env": b"AWS_PROFILE=abn-backup\nAWS_CONFIG_FILE=/etc/abr-engine/backup/aws-config\n"
                        b"AWS_SHARED_CREDENTIALS_FILE=/etc/abr-engine/backup/credentials\n"
                        b"AWS_EC2_METADATA_DISABLED=true\n",
        "infrastructure.json": canonical({"schema": "abr-installed-backup-identity-v1", "account_id": ACCOUNT,
            "region": REGION, "deployment_id": DEPLOYMENT, "bucket": BUCKET, "maximum_bytes": MAXIMUM_BYTES,
            "authority_installed": False, "services_enabled": False, "runtime_capabilities_enabled": [],
            "recipient_sha256": fingerprint(validate_material(data))}),
    }


def receipt(data, module, *, replayed):
    return {"status": "private_backup_identity_installed", "replayed": replayed,
        "deployment_id": DEPLOYMENT, "bucket": BUCKET, "maximum_bytes": MAXIMUM_BYTES,
        "recipient_sha256": fingerprint(validate_material(data)), "material_sha256": module.material_digest(data),
        "private_backup_key_on_host": False, "runtime_capabilities_enabled": [],
        "release_approvals_created": False, "services_enabled": False}


def install_material(data, group, module):
    validate_material(data)
    marker = DIRECTORY / "installation.json"
    replayed = marker.exists() or marker.is_symlink()
    record = module._read_marker(data) if replayed else None
    if record is not None and record["version"] != 2:
        raise ValueError("BACKUP_INSTALLATION_JOURNAL_INVALID")
    if record is None:
        if any((DIRECTORY / name).exists() or (DIRECTORY / name).is_symlink() for name in FILES):
            raise ValueError("UNRELATED_BACKUP_FILE_REFUSED")
        record = {"version": 2, "state": "configuring", "mode": "pilot",
            "material_sha256": module.material_digest(data), "installation_id": uuid4().hex, "files": {}}
        module._save_marker(record)
    if record["state"] != "configured":
        for name, content in contents(data).items():
            module._publish_file(record, name, content, group)
        record["state"] = "configured"
        module._save_marker(record)
    # Validate immutable public inode/size journal, never read back secret files.
    for name, mode in FILES.items():
        entry = record["files"].get(name)
        if not entry or entry["state"] != "published":
            raise ValueError("BACKUP_INSTALLATION_JOURNAL_INVALID")
        module._same_file(DIRECTORY / name, entry, mode, group)
    return receipt(data, module, replayed=replayed)


@contextmanager
def directory_lease(module):
    import fcntl

    locks: Any = fcntl
    path = DIRECTORY.parent / ".backup-directory-983c39eb.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | native_os.O_NOFOLLOW, 0o600)
    try:
        module._metadata(path, mode=0o600, empty=True)
        locks.flock(descriptor, locks.LOCK_EX | locks.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | native_os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_directory_record(record, module):
    path = DIRECTORY.parent / ".backup-directory-983c39eb.json"
    if path.exists() or path.is_symlink():
        module._metadata(path, mode=0o600)
    temporary = path.with_name(".backup-directory-" + uuid4().hex + ".pending")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | native_os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(DIRECTORY.parent)
    finally:
        temporary.unlink(missing_ok=True)


def establish_directory(group, module):
    marker = DIRECTORY.parent / ".backup-directory-983c39eb.json"
    if marker.exists() or marker.is_symlink():
        if module._metadata(marker, mode=0o600)["size"] > 2048:
            raise ValueError("BACKUP_DIRECTORY_JOURNAL_INVALID")
        record = json.loads(marker.read_bytes())
        if (not isinstance(record, dict) or set(record) != {"version", "deployment_id", "directory", "state", "identity"}
                or record["version"] != 1 or record["deployment_id"] != DEPLOYMENT
                or record["directory"] != str(DIRECTORY) or record["state"] not in {"reserved", "ready"}
                or record["identity"] is not None and (not isinstance(record["identity"], dict)
                    or set(record["identity"]) != {"device", "inode"}
                    or any(type(value) is not int or value < 0 for value in record["identity"].values()))):
            raise ValueError("BACKUP_DIRECTORY_JOURNAL_INVALID")
    else:
        if DIRECTORY.exists() or DIRECTORY.is_symlink():
            raise ValueError("UNRELATED_BACKUP_DIRECTORY_REFUSED")
        record = {"version": 1, "deployment_id": DEPLOYMENT, "directory": str(DIRECTORY),
            "state": "reserved", "identity": None}
        save_directory_record(record, module)  # Exclusive parent lease; reserve before mkdir.
    if not DIRECTORY.exists() and not DIRECTORY.is_symlink():
        if record["identity"] is not None or record["state"] != "reserved":
            raise ValueError("BACKUP_DIRECTORY_IDENTITY_MISMATCH")
        DIRECTORY.mkdir(mode=0o700)
    info = DIRECTORY.lstat()
    identity = {"device": info.st_dev, "inode": info.st_ino}
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid not in {0, group}
            or stat.S_IMODE(info.st_mode) not in {0o700, 0o750}
            or record["identity"] is not None and record["identity"] != identity):
        raise ValueError("BACKUP_DIRECTORY_IDENTITY_MISMATCH")
    if record["state"] == "ready":
        if record["identity"] != identity or info.st_gid != group or stat.S_IMODE(info.st_mode) != 0o750:
            raise ValueError("BACKUP_PRIVATE_DIRECTORY_REQUIRED")
        return
    # A reserved path can recover only while empty and root-private. Nothing has
    # been installed yet; other pre-existing paths were refused before reservation.
    if any(DIRECTORY.iterdir()):
        raise ValueError("BACKUP_PARTIAL_DIRECTORY_NOT_EMPTY")
    if record["identity"] is None:
        if stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("BACKUP_DIRECTORY_IDENTITY_MISMATCH")
        record["identity"] = identity
        save_directory_record(record, module)  # Own the inode before chown/chmod.
    native_os.chown(DIRECTORY, 0, group)
    DIRECTORY.chmod(0o750)
    final = DIRECTORY.lstat()
    if ({"device": final.st_dev, "inode": final.st_ino} != identity or final.st_uid != 0
            or final.st_gid != group or stat.S_IMODE(final.st_mode) != 0o750):
        raise ValueError("BACKUP_DIRECTORY_IDENTITY_MISMATCH")
    sync_directory(DIRECTORY)  # Durable child permissions must precede the ready parent journal.
    record["state"] = "ready"
    save_directory_record(record, module)


def private_directory(group):
    parent = DIRECTORY.parent
    for path in (parent, *parent.parents):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise ValueError("BACKUP_PRIVATE_PARENT_REQUIRED")
    module = publisher()
    with directory_lease(module):
        establish_directory(group, module)


def install(data):
    import grp

    from provision_database import admit, verify_roles

    validate_material(data)
    if not admit():
        raise ValueError("OWNED_ENGINE_DATABASE_REQUIRED")
    verify_roles()
    groups: Any = grp
    group = groups.getgrnam("abr-engine").gr_gid
    private_directory(group)
    module = publisher()
    with module._installation_lock():
        return install_material(data, group, module)


def main():
    if sys.argv[1:] != ["--apply"]:
        print(json.dumps({"status": "review_only", "provider_operations": 0,
            "host_directory": str(DIRECTORY), "maximum_bytes": plan()["maximum_bytes"]}))
        return 0
    try:
        if getattr(os, "geteuid", lambda: -1)() != 0:
            raise ValueError("ROOT_REQUIRED")
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:
            raise ValueError("BACKUP_STDIN_SIZE_LIMIT")
        print(json.dumps(install(json.loads(raw))))
        return 0
    except Exception:  # noqa: BLE001 -- secret-bearing stdin must not appear in provider/native errors
        print(json.dumps({"status": "held", "code": "BACKUP_IDENTITY_INSTALLATION_UNAVAILABLE"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
