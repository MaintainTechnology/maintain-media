"""Synthetic installation/recovery tests; no cloud, token cache or vendor I/O."""
import importlib.util
import io
import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location("provision_ghl", Path(__file__).with_name("provision_ghl.py"))
ghl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ghl)


def material():
    return {"ABR_GHL_TOKEN": "pit-synthetic-" + "a" * 40}


@pytest.mark.parametrize("value", ["short", "x" * 40 + "\nNEW=value", "a" * 40 + "'", "$" + "a" * 40,
                                    "x" * 2049, None, 12])
def test_token_cannot_inject_environment_configuration(value):
    with pytest.raises(ValueError):
        ghl.validate_material({"ABR_GHL_TOKEN": value})


def test_only_one_exact_environment_variable_is_allowed():
    with pytest.raises(ValueError):
        ghl.validate_material({**material(), "ENABLE_CRM": "true"})
    values = ghl.contents(material())
    assert values["environment"] == ("ABR_GHL_TOKEN=" + material()["ABR_GHL_TOKEN"] + "\n").encode()
    assert set(values) == {"environment", *ghl.UNITS}
    assert all(b"EnvironmentFile=/etc/abr-engine/ghl.env" in values[unit] for unit in ghl.UNITS)
    assert "runtime.env" not in repr(ghl.targets())


def test_preview_does_not_read_stdin_or_mutate(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ghl"])
    monkeypatch.setattr(ghl, "install", lambda *_: pytest.fail("No install in review"))
    assert ghl.main() == 0
    assert "review_only" in capsys.readouterr().out


def test_secret_bearing_failure_never_reaches_console(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ghl", "--apply"])
    monkeypatch.setattr(ghl.os, "name", "posix")
    monkeypatch.setattr(ghl.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(material()).encode())))
    monkeypatch.setattr(ghl, "install", lambda *_: (_ for _ in ()).throw(ValueError(material())))
    assert ghl.main() == 2
    output = capsys.readouterr().out
    assert "GHL_INSTALLATION_UNCONFIRMED" in output and material()["ABR_GHL_TOKEN"] not in output


@pytest.fixture
def files(tmp_path, monkeypatch):
    """Real file/NTFS hard-link identities with Linux owner/mode emulation."""
    directory, systemd = tmp_path / "private", tmp_path / "systemd"
    directory.mkdir()
    systemd.mkdir()
    monkeypatch.setattr(ghl, "DIRECTORY", directory)
    monkeypatch.setattr(ghl, "SYSTEMD", systemd)
    for unit in ghl.UNITS:
        (systemd / (unit + ".d")).mkdir()
    modes = {}
    original_lstat, original_read_text, original_read_bytes = Path.lstat, Path.read_text, Path.read_bytes

    def lstat(path):
        info = original_lstat(path)
        mode = modes.get(info.st_ino, 0o755 if stat.S_ISDIR(info.st_mode) else 0o600)
        return SimpleNamespace(st_mode=stat.S_IFMT(info.st_mode) | mode, st_uid=0, st_gid=0,
            st_nlink=info.st_nlink, st_ino=info.st_ino, st_dev=info.st_dev, st_size=info.st_size)

    def chmod(descriptor, mode):
        modes[os.fstat(descriptor).st_ino] = mode

    def persist(record):
        target = directory / "ghl-installation.json"
        temporary = directory / "test-public-journal-next"
        temporary.write_text(json.dumps(record))
        os.replace(temporary, target)

    def guarded_text(path, *args, **kwargs):
        assert path.name == "ghl-installation.json", "No existing environment/configuration reads"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "read_text", guarded_text)
    monkeypatch.setattr(Path, "read_bytes", lambda *_: pytest.fail("No existing secret reads"))
    monkeypatch.setattr(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), raising=False)
    monkeypatch.setattr(os, "fchmod", chmod, raising=False)
    monkeypatch.setattr(ghl, "_sync_directory", lambda *_: None)
    monkeypatch.setattr(ghl, "_save", persist)
    return directory, persist, original_read_bytes


@pytest.mark.parametrize("boundary", range(1, 19))
@pytest.mark.parametrize("after", [False, True])
def test_each_interrupted_public_journal_boundary_resumes_same_token(files, monkeypatch, boundary, after):
    _, persist, read_generated = files
    calls = 0

    def interrupt(record):
        nonlocal calls
        calls += 1
        if calls == boundary and not after:
            raise OSError("Synthetic interruption")
        persist(record)
        if calls == boundary and after:
            raise OSError("Synthetic interruption")

    monkeypatch.setattr(ghl, "_save", interrupt)
    with pytest.raises(OSError, match="Synthetic interruption"):
        ghl._install(material())
    before = {name: path.stat().st_ino for name, (path, _) in ghl.targets().items() if path.exists()}
    monkeypatch.setattr(ghl, "_save", persist)
    receipt = ghl._install(material())
    assert receipt["status"] == "ghl_credential_installed"
    assert not receipt["capabilities_changed"] and not receipt["services_started"]
    for name, (path, _) in ghl.targets().items():
        assert read_generated(path) == ghl.contents(material())[name]
        assert path.stat().st_nlink == 1
        if name in before:
            assert path.stat().st_ino == before[name]
    assert ghl._install(material())["replayed"]


def test_existing_unrelated_environment_is_preserved_and_never_read(files):
    _, _, read_generated = files
    target = ghl.targets()["environment"][0]
    target.write_bytes(b"unrelated-private-data")
    with pytest.raises(ValueError, match="EXISTING_FILE"):
        ghl._install(material())
    assert read_generated(target) == b"unrelated-private-data"


def test_replay_rejects_different_new_token(files):
    ghl._install(material())
    with pytest.raises(ValueError, match="TOKEN_MISMATCH"):
        ghl._install({"ABR_GHL_TOKEN": "pit-different-" + "b" * 40})


def test_unexpected_replacement_of_published_file_is_not_overwritten(files):
    ghl._install(material())
    target = ghl.targets()["environment"][0]
    replacement = target.with_name("synthetic-replacement")
    replacement.write_bytes(b"unrelated")
    os.replace(replacement, target)
    with pytest.raises(ValueError, match="INODE_MISMATCH"):
        ghl._install(material())


def test_crash_immediately_after_publication_link_is_recoverable(files, monkeypatch):
    original_link = os.link
    happened = False

    def interrupted(source, target, **kwargs):
        nonlocal happened
        original_link(source, target, **kwargs)
        if not happened:
            happened = True
            raise OSError("Synthetic link crash")

    monkeypatch.setattr(os, "link", interrupted)
    with pytest.raises(OSError, match="Synthetic link crash"):
        ghl._install(material())
    monkeypatch.setattr(os, "link", original_link)
    assert ghl._install(material())["status"] == "ghl_credential_installed"


def test_crash_after_mode_change_before_prepared_record_is_recoverable(files, monkeypatch):
    chmod = os.fchmod
    happened = False

    def interrupted(descriptor, mode):
        nonlocal happened
        chmod(descriptor, mode)
        if mode == 0o644 and not happened:
            happened = True
            raise OSError("Synthetic chmod crash")

    monkeypatch.setattr(os, "fchmod", interrupted)
    with pytest.raises(OSError, match="Synthetic chmod crash"):
        ghl._install(material())
    monkeypatch.setattr(os, "fchmod", chmod)
    assert ghl._install(material())["status"] == "ghl_credential_installed"


def test_stage_parent_is_synced_before_durable_inode_ownership(files, monkeypatch):
    _, persist, _ = files
    synced = set()
    prior = {}
    monkeypatch.setattr(ghl, "_sync_directory", lambda path: synced.add(path))

    def save(record):
        for name, entry in record["files"].items():
            if entry["identity"] is not None and prior.get(name) is None:
                assert ghl._stage(record, name).parent in synced
            prior[name] = entry["identity"]
        persist(record)

    monkeypatch.setattr(ghl, "_save", save)
    assert ghl._install(material())["status"] == "ghl_credential_installed"
