"""Install newly generated runtime keys from stdin on the owned empty engine.

Reads no existing environment file or provider credential. Outputs status only.
The operator must escrow the newly generated input separately before this step.
"""
import base64
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

DIRECTORY = Path("/etc/abr-engine")
FIELDS = {"encryption_key", "lookup_key", "signing_key", "wrapping_key", "website_assertion_key"}


def material_digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def configured_receipt(data, *, replayed=False):
    return {"status": "private_runtime_configured", "mode": "pilot", "fixture_keys_used": False,
            "initial_capabilities_enabled": [], "release_approvals_created": False,
            "material_sha256": material_digest(data), "replayed": replayed}


def _metadata(path, *, mode=None, group=None, empty=False, links=(1,)):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink not in links or info.st_uid != 0
            or (mode is not None and stat.S_IMODE(info.st_mode) != mode)
            or (mode is None and stat.S_IMODE(info.st_mode) not in {0o600, 0o640})
            or (group is not None and info.st_gid != group) or (not empty and info.st_size == 0)):
        raise ValueError("RUNTIME_METADATA_MISMATCH")
    return {"device": info.st_dev, "inode": info.st_ino, "size": info.st_size}


def _read_marker(data):
    marker = DIRECTORY / "installation.json"
    info = _metadata(marker, mode=0o600)
    if info["size"] > 8192:
        raise ValueError("RUNTIME_MARKER_INVALID")
    record = json.loads(marker.read_text())
    if (not isinstance(record, dict) or record.get("version") not in {1, 2}
            or record.get("state") not in {"configuring", "configured"} or record.get("mode") != "pilot"
            or not isinstance(record.get("material_sha256"), str)
            or not hmac.compare_digest(record["material_sha256"], material_digest(data))):
        raise ValueError("RUNTIME_MATERIAL_OR_STATE_MISMATCH")
    if record["version"] == 2:
        if (not re.fullmatch(r"[0-9a-f]{32}", record.get("installation_id", ""))
                or not isinstance(record.get("files"), dict)
                or set(record["files"]) - FILES.keys()):
            raise ValueError("RUNTIME_MARKER_INVALID")
        for name, entry in record["files"].items():
            if (not isinstance(entry, dict) or entry.get("state") not in {"writing", "prepared", "published"}
                    or entry.get("staging_name") != _stage_name(record, name)
                    or entry.get("identity") is not None and (
                        set(entry["identity"]) != {"device", "inode"}
                        or any(type(value) is not int or value < 0 for value in entry["identity"].values()))
                    or entry["state"] != "writing" and (
                        entry.get("identity") is None or type(entry.get("size")) is not int or entry["size"] <= 0)):
                raise ValueError("RUNTIME_MARKER_INVALID")
    return record


def _same_file(path, entry, mode, group, *, links=(1,)):
    info = _metadata(path, mode=mode, group=group if mode == 0o640 else None, links=links)
    if ({key: info[key] for key in ("device", "inode")} != entry["identity"]
            or info["size"] != entry["size"]):
        raise ValueError("RUNTIME_FILE_IDENTITY_MISMATCH")
    return info


def replay_installation(data, group):
    """Check public journal/file metadata only; never read an existing secret."""
    record = _read_marker(data)
    if record["state"] != "configured":
        raise ValueError("RUNTIME_MATERIAL_OR_STATE_MISMATCH")
    for name, mode in FILES.items():
        if record["version"] == 2:
            if name not in record["files"] or record["files"][name]["state"] != "published":
                raise ValueError("RUNTIME_MARKER_INVALID")
            _same_file(DIRECTORY / name, record["files"][name], mode, group)
        else:
            _metadata(DIRECTORY / name, mode=mode, group=group if mode == 0o640 else None)
    return configured_receipt(data, replayed=True)


FILES = {"keys.json": 0o640, "runtime.env": 0o600, "pilot.yaml": 0o640}


def _stage_name(record, name):
    return ".runtime-" + record["installation_id"] + "-" + name + ".pending"


@contextmanager
def _installation_lock():
    import fcntl

    path = DIRECTORY / "installation.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        _metadata(path, mode=0o600, empty=True)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)  # Kernel releases the lease even after process death.


def _save_marker(record):
    """Only called under the installation lease; replace the public journal atomically."""
    path = DIRECTORY / "installation.json"
    if path.exists() or path.is_symlink():
        _metadata(path, mode=0o600)
    temporary = DIRECTORY / (".installation-journal-" + uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_file(record, name, content, group):
    """Publish only a journal-owned inode; existing final files are never replaced."""
    target, mode = DIRECTORY / name, FILES[name]
    stage = DIRECTORY / _stage_name(record, name)
    entry = record["files"].get(name)
    if entry is None:
        if any(path.exists() or path.is_symlink() for path in (target, stage)):
            raise ValueError("UNRELATED_RUNTIME_FILE_REFUSED")
        entry = {"state": "writing", "staging_name": stage.name, "identity": None}
        record["files"][name] = entry
        _save_marker(record)  # Reserve this exact new path before creating it.
    if entry["state"] == "writing":
        if target.exists() or target.is_symlink():
            raise ValueError("UNRELATED_RUNTIME_FILE_REFUSED")
        if not stage.exists() and not stage.is_symlink():
            descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(descriptor)
            entry["identity"] = None
        info = _metadata(stage, mode=0o600 if mode == 0o600 else None, empty=True)
        identity = {key: info[key] for key in ("device", "inode")}
        if entry["identity"] is None:
            if info["size"] != 0:
                raise ValueError("UNOWNED_STAGING_FILE_REFUSED")
            entry["identity"] = identity
            _save_marker(record)  # Own the inode before the first secret byte.
        elif entry["identity"] != identity:
            raise ValueError("RUNTIME_FILE_IDENTITY_MISMATCH")
        descriptor = os.open(stage, os.O_WRONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "wb") as stream:
            opened = os.fstat(stream.fileno())
            if {"device": opened.st_dev, "inode": opened.st_ino} != identity:
                raise ValueError("RUNTIME_FILE_IDENTITY_MISMATCH")
            os.ftruncate(stream.fileno(), 0)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchown(stream.fileno(), 0, group if mode == 0o640 else 0)
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        entry.update(state="prepared", size=len(content))
        _save_marker(record)
    if entry["state"] == "prepared":
        if target.exists() or target.is_symlink():
            _same_file(target, entry, mode, group, links=(1, 2))
        else:
            _same_file(stage, entry, mode, group)
            os.link(stage, target, follow_symlinks=False)  # O_EXCL-style publication; no replacement.
        entry["state"] = "published"
        _save_marker(record)
    _same_file(target, entry, mode, group, links=(1, 2))
    if stage.exists() or stage.is_symlink():
        _same_file(stage, entry, mode, group, links=(2,))
        stage.unlink()
    _same_file(target, entry, mode, group)


def _contents(data, lookup):
    import yaml
    from cryptography.fernet import Fernet

    # The KeyStore's encrypted envelope format. All key bytes come from the same
    # supplied, escrowed bundle; only the encryption nonce is fresh on retry.
    payload = {"encryption_key": data["encryption_key"], "lookup_keys": {"1": base64.b64encode(lookup).decode()},
               "active_version": 1, "signing_key": data["signing_key"], "compromised": False}
    envelope = {"format": "fernet-v1", "payload": Fernet(data["wrapping_key"].encode()).encrypt(
        json.dumps(payload, sort_keys=True).encode()).decode()}
    return {"keys.json": json.dumps(envelope, sort_keys=True).encode(),
            "runtime.env": ("ABR_KEYSTORE_WRAPPING_KEY=" + data["wrapping_key"] + "\n"
                            "ABN_ENGINE_ASSERTION_KEY=" + data["website_assertion_key"] + "\n").encode(),
            "pilot.yaml": yaml.safe_dump(pilot_configuration(), sort_keys=True).encode()}


def _install_material(data, lookup, group):
    marker = DIRECTORY / "installation.json"
    replayed = marker.exists() or marker.is_symlink()
    if replayed:
        record = _read_marker(data)
        if record["state"] == "configured":
            return replay_installation(data, group)
        if record["version"] == 1:
            if any((DIRECTORY / name).exists() or (DIRECTORY / name).is_symlink() for name in FILES):
                raise ValueError("LEGACY_PARTIAL_INSTALLATION_NEEDS_REVIEW")
            record = None
    else:
        record = None
    if record is None:
        if any((DIRECTORY / name).exists() or (DIRECTORY / name).is_symlink() for name in FILES):
            raise ValueError("UNRELATED_RUNTIME_FILE_REFUSED")
        record = {"version": 2, "state": "configuring", "mode": "pilot", "material_sha256": material_digest(data),
                  "installation_id": uuid4().hex, "files": {}}
        _save_marker(record)
    for name, content in _contents(data, lookup).items():
        _publish_file(record, name, content, group)
    record["state"] = "configured"
    _save_marker(record)
    replay_installation(data, group)  # Verify every published inode before success.
    return configured_receipt(data, replayed=replayed)


def validate_material(data):
    from cryptography.fernet import Fernet

    if not isinstance(data, dict) or set(data) != FIELDS or any(not isinstance(v, str) for v in data.values()):
        raise ValueError("KEY_INPUT_INVALID")
    for name in ("encryption_key", "wrapping_key"):
        if len(data[name]) != 44:
            raise ValueError("KEY_INPUT_INVALID")
        Fernet(data[name].encode())
    for name in ("signing_key", "website_assertion_key"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", data[name]):
            raise ValueError("KEY_INPUT_INVALID")
    lookup = base64.b64decode(data["lookup_key"], altchars=b"-_", validate=True)
    raw = [lookup, *(base64.urlsafe_b64decode(data[name]) for name in ("encryption_key", "wrapping_key")),
           data["signing_key"].encode(), data["website_assertion_key"].encode()]
    if len(lookup) != 32 or len(set(raw)) != len(raw):
        raise ValueError("KEY_MATERIAL_MUST_BE_SEPARATE")
    return lookup


def pilot_configuration():
    return {"mode": "pilot", "database_url": "postgresql:///abr_leadgen?host=/var/run/postgresql&user=abr-engine",
            "output_dir": "/var/lib/abr-engine", "key_file": "/etc/abr-engine/keys.json",
            "monthly_cap_micro_aud": 150_000_000, "issuer": "maintain-media-engine",
            "audience": "abr-engine-private", "live_credentials": {},
            "capabilities": {"collection": False, "abr": False, "crm": False,
                             "sheets": False, "retention": False}}


def install(data):
    import grp

    from provision_database import admit, verify_roles

    lookup = validate_material(data)
    if not admit():
        raise ValueError("OWNED_DATABASE_REQUIRED")
    verify_roles()
    if (any(path.is_symlink() for path in (DIRECTORY, *DIRECTORY.parents))
            or not DIRECTORY.is_dir() or DIRECTORY.stat().st_uid != 0
            or stat.S_IMODE(DIRECTORY.stat().st_mode) & 0o022):
        raise ValueError("PRIVATE_CONFIGURATION_DIRECTORY_REQUIRED")
    group = grp.getgrnam("abr-engine").gr_gid
    with _installation_lock():
        return _install_material(data, lookup, group)


def main():
    if sys.argv[1:] != ["--apply"]:
        print(json.dumps({"status": "review_only", "scope": "new_empty_private_runtime"}))
        return 0
    try:
        if getattr(os, "geteuid", lambda: -1)() != 0:
            raise ValueError("ROOT_REQUIRED")
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError("INPUT_LIMIT")
        result = install(json.loads(raw))
        print(json.dumps(result))
        return 0
    except Exception:  # noqa: BLE001 - final secret-bearing stdin boundary; never reflect exception text
        # Even validation/OS errors must never reflect the confidential stdin.
        print(json.dumps({"status": "blocked", "code": "RUNTIME_INSTALLATION_UNAVAILABLE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
