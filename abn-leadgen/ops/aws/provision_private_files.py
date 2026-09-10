"""Publish fixed new root-owned files without reading or replacing existing secrets.

Extraction of the reviewed GHL inode journal protocol. Existing GHL wrappers and
their installation markers remain unchanged. This module performs no service,
database or provider operations and creates no parent directory.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


def directory(path):
    for item in (path, *path.parents):
        info = item.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise ValueError("PRIVATE_DIRECTORY_UNTRUSTED")


def metadata(path, mode, *, empty=False, links=(1,)):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != mode or info.st_nlink not in links
            or not empty and info.st_size == 0):
        raise ValueError("PRIVATE_FILE_METADATA_MISMATCH")
    return {"device": info.st_dev, "inode": info.st_ino, "size": info.st_size}


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class OwnedFiles:
    def __init__(self, directory: Path, marker_name: str, targets: dict[str, tuple[Path, int]],
                 identity: dict[str, str]):
        if (not directory.is_absolute() or directory.resolve() != directory
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,70}\.json", marker_name)
                or not isinstance(identity, dict) or not identity or len(identity) > 20
                or any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 100 or len(v) > 500
                       for k, v in identity.items())
                or not isinstance(targets, dict) or not 1 <= len(targets) <= 20):
            raise ValueError("PRIVATE_PUBLICATION_CONFIGURATION_INVALID")
        self.directory, self.marker = directory, directory / marker_name
        self.lock = directory / (marker_name.removesuffix(".json") + ".lock")
        self.identity, self.targets = dict(identity), dict(targets)
        for name, (path, mode) in targets.items():
            if (not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name) or not path.is_absolute()
                    or path.parent.resolve() != path.parent or path.name.startswith(".")
                    or mode not in {0o600, 0o644} or path in {self.marker, self.lock}):
                raise ValueError("PRIVATE_PUBLICATION_TARGET_INVALID")
        if len({path for path, _ in targets.values()}) != len(targets):
            raise ValueError("PRIVATE_PUBLICATION_TARGET_INVALID")

    @contextmanager
    def _locked(self):
        import fcntl
        descriptor = os.open(self.lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            metadata(self.lock, 0o600, empty=True)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(descriptor)

    def _binding(self, contents):
        return {"identity": self.identity,
                "targets": {name: {"path": str(path), "mode": mode,
                    "content_sha256": hashlib.sha256(contents[name]).hexdigest()}
                    for name, (path, mode) in self.targets.items()}}

    def _save(self, record):
        if self.marker.exists() or self.marker.is_symlink():
            metadata(self.marker, 0o600)
        stage = self.directory / (".owned-journal-" + uuid4().hex + ".pending")
        descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(stage, self.marker)
            sync_directory(self.directory)
        finally:
            stage.unlink(missing_ok=True)

    def _load(self, material_sha256, contents):
        if metadata(self.marker, 0o600)["size"] > 32_768:
            raise ValueError("PRIVATE_JOURNAL_INVALID")
        record = json.loads(self.marker.read_bytes())  # Own public journal only.
        if (not isinstance(record, dict) or set(record) != {"version", "binding", "material_sha256", "installation_id", "state", "files"}
                or record["version"] != 1 or record["binding"] != self._binding(contents)
                or not isinstance(record["material_sha256"], str)
                or not hmac.compare_digest(record["material_sha256"], material_sha256)
                or not isinstance(record["installation_id"], str)
                or not re.fullmatch(r"[a-f0-9]{32}", record["installation_id"])
                or record["state"] not in {"installing", "installed"}
                or not isinstance(record["files"], dict) or set(record["files"]) - self.targets.keys()):
            raise ValueError("PRIVATE_JOURNAL_OR_MATERIAL_MISMATCH")
        for entry in record["files"].values():
            if (not isinstance(entry, dict) or set(entry) != {"state", "identity", "size"}
                    or entry["state"] not in {"writing", "prepared", "published"}
                    or entry["identity"] is not None and (not isinstance(entry["identity"], dict)
                        or set(entry["identity"]) != {"device", "inode"}
                        or any(type(v) is not int or v < 0 for v in entry["identity"].values()))
                    or type(entry["size"]) is not int or entry["size"] < 0
                    or entry["state"] != "writing" and (entry["identity"] is None or entry["size"] == 0)):
                raise ValueError("PRIVATE_JOURNAL_INVALID")
        return record

    def _same(self, path, entry, mode, *, links=(1,)):
        actual = metadata(path, mode, links=links)
        if ({k: actual[k] for k in ("device", "inode")} != entry["identity"] or actual["size"] != entry["size"]):
            raise ValueError("PRIVATE_OWNED_INODE_MISMATCH")

    def _publish(self, record, name, content):
        target, mode = self.targets[name]
        stage = target.with_name(".owned-" + record["installation_id"] + "-" + target.name + ".pending")
        entry = record["files"].get(name)
        if entry is None:
            if any(p.exists() or p.is_symlink() for p in (target, stage)):
                raise ValueError("PRIVATE_EXISTING_FILE_REFUSED")
            entry = {"state": "writing", "identity": None, "size": 0}
            record["files"][name] = entry
            self._save(record)
        if entry["state"] == "writing":
            if target.exists() or target.is_symlink():
                raise ValueError("PRIVATE_EXISTING_FILE_REFUSED")
            if not stage.exists() and not stage.is_symlink():
                if entry["identity"] is not None:
                    raise ValueError("PRIVATE_OWNED_INODE_MISSING")
                descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                sync_directory(stage.parent)
            stage_mode = stat.S_IMODE(stage.lstat().st_mode)
            if stage_mode not in {0o600, mode}:
                raise ValueError("PRIVATE_FILE_METADATA_MISMATCH")
            info = metadata(stage, stage_mode, empty=True)
            identity = {k: info[k] for k in ("device", "inode")}
            if entry["identity"] is None:
                if info["size"] != 0 or stage_mode != 0o600:
                    raise ValueError("PRIVATE_UNOWNED_STAGE_REFUSED")
                entry["identity"] = identity
                self._save(record)
            elif entry["identity"] != identity:
                raise ValueError("PRIVATE_OWNED_INODE_MISMATCH")
            descriptor = os.open(stage, os.O_WRONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "wb") as stream:
                actual = os.fstat(stream.fileno())
                if {"device": actual.st_dev, "inode": actual.st_ino} != identity:
                    raise ValueError("PRIVATE_OWNED_INODE_MISMATCH")
                stream.truncate(0)
                stream.write(content)
                stream.flush()
                os.fchmod(stream.fileno(), mode)
                os.fsync(stream.fileno())
            entry.update(state="prepared", size=len(content))
            self._save(record)
        if entry["state"] == "prepared":
            if target.exists() or target.is_symlink():
                self._same(target, entry, mode, links=(1, 2))
            else:
                self._same(stage, entry, mode)
                os.link(stage, target, follow_symlinks=False)
                sync_directory(target.parent)
            if stage.exists() or stage.is_symlink():
                self._same(stage, entry, mode, links=(2,))
                stage.unlink()
                sync_directory(target.parent)
            self._same(target, entry, mode)
            entry["state"] = "published"
            self._save(record)
        self._same(target, entry, mode)

    def _install(self, contents, material_sha256):
        if self.marker.exists() or self.marker.is_symlink():
            record = self._load(material_sha256, contents)
        else:
            if any(p.exists() or p.is_symlink() for p, _ in self.targets.values()):
                raise ValueError("PRIVATE_EXISTING_FILE_REFUSED")
            record = {"version": 1, "binding": self._binding(contents), "material_sha256": material_sha256,
                      "installation_id": uuid4().hex, "state": "installing", "files": {}}
            self._save(record)
        replayed = record["state"] == "installed"
        if replayed and (set(record["files"]) != self.targets.keys()
                         or any(e["state"] != "published" for e in record["files"].values())):
            raise ValueError("PRIVATE_JOURNAL_INVALID")
        for name, content in contents.items():
            self._publish(record, name, content)
        if not replayed:
            record["state"] = "installed"
            self._save(record)
        return {"replayed": replayed, "material_sha256": material_sha256}

    def install(self, contents: dict[str, bytes], material_sha256: str):
        if (not isinstance(contents, dict) or set(contents) != self.targets.keys()
                or any(not isinstance(v, bytes) or not 1 <= len(v) <= 65_536 for v in contents.values())
                or not isinstance(material_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", material_sha256)):
            raise ValueError("PRIVATE_CONTENT_OR_DIGEST_INVALID")
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("PRIVATE_LINUX_ROOT_REQUIRED")
        directory(self.directory)
        for target, _ in self.targets.values():
            directory(target.parent)
        with self._locked():
            return self._install(contents, material_sha256)
