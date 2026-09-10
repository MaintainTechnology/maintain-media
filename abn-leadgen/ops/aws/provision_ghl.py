"""Install one newly supplied GHL token from stdin; never read existing secrets.

This root-only Linux helper creates its own environment file and three systemd
drop-ins. It does not reload/start services, contact a vendor, or change gates.
Its journal permits same-token recovery without replacing an existing final file.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

LOCATION = "xHZFHMOE476t5CxY9vCG"
HOST = "ubuntu@3.104.119.142"
DIRECTORY = Path("/etc/abr-engine")
SYSTEMD = Path("/etc/systemd/system")
UNITS = ("abr-engine-api.service", "abr-engine-worker.service", "abr-engine-control.service")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.~+/=-]{32,2048}")


def validate_material(data):
    if (not isinstance(data, dict) or set(data) != {"ABR_GHL_TOKEN"}
            or not isinstance(data["ABR_GHL_TOKEN"], str)
            or not TOKEN_PATTERN.fullmatch(data["ABR_GHL_TOKEN"])):
        raise ValueError("GHL_NEW_TOKEN_INVALID")
    return data


def digest(data):
    validate_material(data)
    return hashlib.sha256(json.dumps({"host": HOST, "location": LOCATION, "material": data},
                                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def targets():
    return {"environment": (DIRECTORY / "ghl.env", 0o600),
            **{unit: (SYSTEMD / (unit + ".d") / "70-maintain-media-ghl.conf", 0o644) for unit in UNITS}}


def contents(data):
    return {"environment": ("ABR_GHL_TOKEN=" + data["ABR_GHL_TOKEN"] + "\n").encode(),
            **{unit: b"[Service]\nEnvironmentFile=/etc/abr-engine/ghl.env\n" for unit in UNITS}}


def _directory(path):
    """Reject links and non-root-writable parent hops before creating private files."""
    for entry in (path, *path.parents):
        info = entry.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise ValueError("GHL_DIRECTORY_UNTRUSTED")


def _file(path, mode, *, empty=False, links=(1,)):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != mode or info.st_nlink not in links
            or (not empty and info.st_size == 0)):
        raise ValueError("GHL_FILE_METADATA_MISMATCH")
    return {"device": info.st_dev, "inode": info.st_ino, "size": info.st_size}


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _lock():
    import fcntl

    path = DIRECTORY / "ghl-installation.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        _file(path, 0o600, empty=True)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def _save(record):
    target = DIRECTORY / "ghl-installation.json"
    if target.exists() or target.is_symlink():
        _file(target, 0o600)
    stage = DIRECTORY / (".ghl-journal-" + uuid4().hex + ".tmp")
    descriptor = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stage, target)
        _sync_directory(DIRECTORY)
    finally:
        stage.unlink(missing_ok=True)


def _stage(record, name):
    target, _ = targets()[name]
    return target.with_name(".ghl-" + record["installation_id"] + "-" + target.name + ".pending")


def _load(data):
    path = DIRECTORY / "ghl-installation.json"
    if _file(path, 0o600)["size"] > 16_384:
        raise ValueError("GHL_JOURNAL_INVALID")
    record = json.loads(path.read_text())  # Only this helper's non-secret journal is read.
    if (not isinstance(record, dict) or set(record) != {"version", "host", "location", "material_sha256",
                                                       "installation_id", "state", "files"}
            or record["version"] != 1 or record["host"] != HOST or record["location"] != LOCATION
            or record["state"] not in {"installing", "installed"}
            or not isinstance(record["material_sha256"], str)
            or not hmac.compare_digest(record["material_sha256"], digest(data))
            or not isinstance(record["installation_id"], str)
            or not re.fullmatch(r"[a-f0-9]{32}", record["installation_id"])
            or not isinstance(record["files"], dict) or set(record["files"]) - targets().keys()):
        raise ValueError("GHL_JOURNAL_OR_TOKEN_MISMATCH")
    for entry in record["files"].values():
        if (not isinstance(entry, dict) or set(entry) != {"state", "identity", "size"}
                or entry["state"] not in {"writing", "prepared", "published"}
                or entry["identity"] is not None and (
                    not isinstance(entry["identity"], dict) or set(entry["identity"]) != {"device", "inode"}
                    or any(type(value) is not int or value < 0 for value in entry["identity"].values()))
                or type(entry["size"]) is not int or entry["size"] < 0
                or entry["state"] != "writing" and (entry["identity"] is None or entry["size"] == 0)):
            raise ValueError("GHL_JOURNAL_INVALID")
    return record


def _same(path, entry, mode, *, links=(1,)):
    actual = _file(path, mode, links=links)
    if ({key: actual[key] for key in ("device", "inode")} != entry["identity"]
            or actual["size"] != entry["size"]):
        raise ValueError("GHL_OWNED_INODE_MISMATCH")


def _publish(record, name, content):
    target, mode = targets()[name]
    stage = _stage(record, name)
    entry = record["files"].get(name)
    if entry is None:
        if any(path.exists() or path.is_symlink() for path in (target, stage)):
            raise ValueError("GHL_EXISTING_FILE_REFUSED")
        entry = {"state": "writing", "identity": None, "size": 0}
        record["files"][name] = entry
        _save(record)
    if entry["state"] == "writing":
        if target.exists() or target.is_symlink():
            raise ValueError("GHL_EXISTING_FILE_REFUSED")
        if not stage.exists() and not stage.is_symlink():
            if entry["identity"] is not None:
                raise ValueError("GHL_OWNED_INODE_MISSING")
            descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            _sync_directory(stage.parent)
        # A crash can follow chmod/fsync but precede the prepared journal write.
        # Only this reserved inode may be rebuilt, with either permitted stage mode.
        stage_mode = stat.S_IMODE(stage.lstat().st_mode)
        if stage_mode not in {0o600, mode}:
            raise ValueError("GHL_FILE_METADATA_MISMATCH")
        info = _file(stage, stage_mode, empty=True)
        identity = {key: info[key] for key in ("device", "inode")}
        if entry["identity"] is None:
            if info["size"] != 0:
                raise ValueError("GHL_UNOWNED_STAGE_REFUSED")
            entry["identity"] = identity
            _save(record)  # Record the new inode before any credential bytes are written.
        elif entry["identity"] != identity:
            raise ValueError("GHL_OWNED_INODE_MISMATCH")
        descriptor = os.open(stage, os.O_WRONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "wb") as stream:
            actual = os.fstat(stream.fileno())
            if {"device": actual.st_dev, "inode": actual.st_ino} != identity:
                raise ValueError("GHL_OWNED_INODE_MISMATCH")
            stream.truncate(0)  # Same journal-owned staging inode; no final secret is read/replaced.
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        entry.update(state="prepared", size=len(content))
        _save(record)
    if entry["state"] == "prepared":
        if target.exists() or target.is_symlink():
            _same(target, entry, mode, links=(1, 2))
        else:
            _same(stage, entry, mode)
            os.link(stage, target, follow_symlinks=False)  # Never replace an existing final file.
            _sync_directory(target.parent)
        if stage.exists() or stage.is_symlink():
            _same(stage, entry, mode, links=(2,))
            stage.unlink()
            _sync_directory(target.parent)
        _same(target, entry, mode)
        entry["state"] = "published"
        _save(record)
    _same(target, entry, mode)


def _install(data):
    marker = DIRECTORY / "ghl-installation.json"
    if marker.exists() or marker.is_symlink():
        record = _load(data)
    else:
        if any(path.exists() or path.is_symlink() for path, _ in targets().values()):
            raise ValueError("GHL_EXISTING_FILE_REFUSED")
        record = {"version": 1, "host": HOST, "location": LOCATION, "material_sha256": digest(data),
                  "installation_id": uuid4().hex, "state": "installing", "files": {}}
        _save(record)
    replayed = record["state"] == "installed"
    if replayed and (set(record["files"]) != targets().keys()
                     or any(entry["state"] != "published" for entry in record["files"].values())):
        raise ValueError("GHL_JOURNAL_INVALID")
    for name, content in contents(data).items():
        _publish(record, name, content)
    if not replayed:
        record["state"] = "installed"
        _save(record)
    return {"status": "ghl_credential_installed", "location_id": LOCATION, "material_sha256": digest(data),
            "replayed": replayed, "services_started": False, "services_reloaded": False,
            "capabilities_changed": False, "release_approvals_created": False, "vendor_calls": 0}


def install(data):
    validate_material(data)
    _directory(DIRECTORY)
    _directory(SYSTEMD)
    for unit in UNITS:
        info = (SYSTEMD / unit).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise ValueError("GHL_EXPECTED_UNIT_MISSING")
        parent = SYSTEMD / (unit + ".d")
        parent.mkdir(mode=0o755, exist_ok=True)
        _directory(parent)
        _sync_directory(parent)
        _sync_directory(SYSTEMD)
    with _lock():
        return _install(data)


def main():
    if sys.argv[1:] != ["--apply"]:
        print(json.dumps({"status": "review_only", "host": HOST, "location_id": LOCATION,
                          "vendor_calls": 0, "services_started": False}))
        return 0
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("LINUX_ROOT_REQUIRED")
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError("GHL_INPUT_TOO_LARGE")
        print(json.dumps(install(validate_material(json.loads(raw)))))
        return 0
    except Exception:  # noqa: BLE001 - credential boundary never reflects exception/input/provider content
        print(json.dumps({"status": "blocked", "code": "GHL_INSTALLATION_UNCONFIRMED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
