"""Real file identities and injected journal faults; synthetic content only."""
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import provision_private_files as private
import pytest


@pytest.fixture
def files(tmp_path, monkeypatch):
    root, second = tmp_path / "root", tmp_path / "systemd"
    root.mkdir()
    second.mkdir()
    instance = private.OwnedFiles(root, "sheets-installation.json",
        {"environment": (root / "sheets.env", 0o600), "registry": (root / "sheets.pending.yaml", 0o600),
         "dropin": (second / "75-sheets.conf", 0o644)}, {"host": "synthetic", "workbook": "test"})
    contents = {"environment": b"NEW_SYNTHETIC_SECRET=example", "registry": b"enabled: false", "dropin": b"[Service]"}
    modes = {}
    native_lstat, native_read = Path.lstat, Path.read_bytes
    def lstat(path):
        info = native_lstat(path)
        mode = modes.get(info.st_ino, 0o755 if stat.S_ISDIR(info.st_mode) else 0o600)
        return SimpleNamespace(st_mode=stat.S_IFMT(info.st_mode) | mode, st_uid=0, st_gid=0,
            st_nlink=info.st_nlink, st_ino=info.st_ino, st_dev=info.st_dev, st_size=info.st_size)
    def read(path):
        assert path == instance.marker, "Never read existing secret/configuration bytes"
        return native_read(path)
    def persist(record):
        stage = root / "public-journal-next"
        stage.write_text(json.dumps(record))
        os.replace(stage, instance.marker)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), raising=False)
    monkeypatch.setattr(os, "fchmod", lambda fd, mode: modes.update({os.fstat(fd).st_ino: mode}), raising=False)
    monkeypatch.setattr(private, "sync_directory", lambda _: None)
    monkeypatch.setattr(instance, "_save", persist)
    return instance, contents, persist, native_read


@pytest.mark.parametrize("boundary", range(1, 15))
@pytest.mark.parametrize("after", [False, True])
def test_journal_interruption_recovers_each_owned_inode(files, monkeypatch, boundary, after):
    instance, contents, persist, read = files
    calls = 0
    def interrupted(record):
        nonlocal calls
        calls += 1
        if calls == boundary and not after:
            raise OSError("Synthetic crash")
        persist(record)
        if calls == boundary and after:
            raise OSError("Synthetic crash")
    monkeypatch.setattr(instance, "_save", interrupted)
    with pytest.raises(OSError):
        instance._install(contents, "a" * 64)
    owned = {name: path.stat().st_ino for name, (path, _) in instance.targets.items() if path.exists()}
    monkeypatch.setattr(instance, "_save", persist)
    assert instance._install(contents, "a" * 64)["material_sha256"] == "a" * 64
    for name, (path, _) in instance.targets.items():
        assert read(path) == contents[name]
        assert path.stat().st_nlink == 1
        if name in owned:
            assert path.stat().st_ino == owned[name]
    assert instance._install(contents, "a" * 64)["replayed"]


@pytest.mark.parametrize("operation", ["link", "fchmod"])
def test_link_and_mode_interruption_recover(files, monkeypatch, operation):
    instance, contents, _, _ = files
    native = getattr(os, operation)
    interrupted = False
    def fail(*args, **kwargs):
        nonlocal interrupted
        result = native(*args, **kwargs)
        if not interrupted:
            interrupted = True
            raise OSError("Synthetic post-operation crash")
        return result
    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(OSError):
        instance._install(contents, "a" * 64)
    monkeypatch.setattr(os, operation, native)
    assert instance._install(contents, "a" * 64)


def test_existing_files_changed_identity_and_material_are_refused(files):
    instance, contents, _, read = files
    target = instance.targets["environment"][0]
    target.write_bytes(b"unrelated")
    with pytest.raises(ValueError, match="EXISTING_FILE"):
        instance._install(contents, "a" * 64)
    assert read(target) == b"unrelated"
    target.unlink()
    instance._install(contents, "a" * 64)
    with pytest.raises(ValueError, match="MATERIAL_MISMATCH"):
        instance._install(contents, "b" * 64)
    instance.identity["host"] = "changed"
    with pytest.raises(ValueError, match="MATERIAL_MISMATCH"):
        instance._install(contents, "a" * 64)


def test_replaced_published_inode_is_never_repaired(files):
    instance, contents, _, read = files
    instance._install(contents, "a" * 64)
    target = instance.targets["environment"][0]
    other = target.with_name("replacement")
    other.write_bytes(b"unrelated")
    os.replace(other, target)
    with pytest.raises(ValueError, match="INODE_MISMATCH"):
        instance._install(contents, "a" * 64)
    assert read(target) == b"unrelated"


def test_changed_static_content_with_same_material_cannot_report_replayed(files):
    instance, contents, _, read = files
    instance._install(contents, "a" * 64)
    changed = dict(contents, dropin=b"[Service]\nChanged=true")
    with pytest.raises(ValueError, match="MATERIAL_MISMATCH"):
        instance._install(changed, "a" * 64)
    assert read(instance.targets["dropin"][0]) == contents["dropin"]


def test_configuration_rejects_marker_traversal_duplicate_target_and_unsafe_mode(tmp_path):
    target = tmp_path / "new.env"
    for marker, targets in [("../unsafe.json", {"one": (target, 0o600)}),
                            ("safe.json", {"one": (target, 0o600), "two": (target, 0o600)}),
                            ("safe.json", {"one": (target, 0o666)})]:
        with pytest.raises(ValueError):
            private.OwnedFiles(tmp_path, marker, targets, {"target": "synthetic"})
