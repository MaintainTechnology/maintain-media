"""New key/config boundaries; no live keys, cloud or environment-file reads."""
import base64
import importlib.util
import io
import json
import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

SPEC = importlib.util.spec_from_file_location("provision_runtime", Path(__file__).with_name("provision_runtime.py"))
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def generated():
    return {"encryption_key": Fernet.generate_key().decode(), "wrapping_key": Fernet.generate_key().decode(),
            "lookup_key": base64.urlsafe_b64encode(os.urandom(32)).decode(),
            "signing_key": "synthetic-engine-" + "e" * 43, "website_assertion_key": "synthetic-website-" + "w" * 43}


def test_all_initial_live_capabilities_remain_closed():
    config = runtime.pilot_configuration()
    assert config["mode"] == "pilot" and not any(config["capabilities"].values())
    assert "password" not in config["database_url"] and "abr_fixture" not in config["database_url"]


def test_separate_keys_are_admitted_without_persistence():
    assert len(runtime.validate_material(generated())) == 32


@pytest.mark.parametrize("field,value", [("signing_key", "short"), ("wrapping_key", "invalid"),
                                         ("website_assertion_key", "x" * 43 + "\nINJECT=yes"),
                                         ("lookup_key", "aW52YWxpZA==")])
def test_malformed_or_environment_injected_material_rejected(field, value):
    material = generated()
    material[field] = value
    with pytest.raises(ValueError):
        runtime.validate_material(material)


def test_key_reuse_is_rejected():
    material = generated()
    material["wrapping_key"] = material["encryption_key"]
    with pytest.raises(ValueError, match="SEPARATE"):
        runtime.validate_material(material)


def test_preview_never_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["runtime"])
    monkeypatch.setattr(runtime, "install", lambda *_: pytest.fail("No mutation"))
    assert runtime.main() == 0
    assert "review_only" in capsys.readouterr().out


def test_secret_bearing_exception_is_never_reflected(monkeypatch, capsys):
    from types import SimpleNamespace
    material = generated()
    monkeypatch.setattr(sys, "argv", ["runtime", "--apply"])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(material).encode())))
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    def unavailable(_):
        raise RuntimeError(json.dumps(material))
    monkeypatch.setattr(runtime, "install", unavailable)
    assert runtime.main() == 2
    result = capsys.readouterr().out
    assert "RUNTIME_INSTALLATION_UNAVAILABLE" in result
    assert not any(value in result for value in material.values())


@pytest.mark.parametrize("state,matching,expected", [("configured", True, True),
                                                    ("configuring", True, False),
                                                    ("configured", False, False)])
def test_replay_uses_only_matching_completed_public_marker(monkeypatch, state, matching, expected):
    from types import SimpleNamespace
    material = generated()
    record = {"version": 1, "mode": "pilot", "state": state,
              "material_sha256": runtime.material_digest(material) if matching else "0" * 64}
    reads = []
    class VirtualPath:
        def __init__(self, name):
            self.name = name
        def __truediv__(self, name):
            return VirtualPath(name)
        def lstat(self):
            mode = 0o640 if self.name in {"pilot.yaml", "keys.json"} else 0o600
            return SimpleNamespace(st_mode=0o100000 | mode, st_nlink=1, st_uid=0,
                                   st_gid=123, st_size=300, st_dev=1, st_ino=2)
        def stat(self):
            return self.lstat()
        def read_text(self):
            reads.append(self.name)
            assert self.name == "installation.json", "Existing secret content must never be read"
            return json.dumps(record)
    monkeypatch.setattr(runtime, "DIRECTORY", VirtualPath("directory"))
    if expected:
        assert runtime.replay_installation(material, 123)["replayed"]
    else:
        with pytest.raises(ValueError, match="MATERIAL_OR_STATE_MISMATCH"):
            runtime.replay_installation(material, 123)
    assert reads == ["installation.json"]


@pytest.fixture
def journal_files(tmp_path, monkeypatch):
    """Real file identities/links; emulate Linux owner/modes on this Windows runner."""
    from types import SimpleNamespace

    monkeypatch.setattr(runtime, "DIRECTORY", tmp_path)
    original_metadata = runtime._metadata
    original_read_bytes, original_read_text = Path.read_bytes, Path.read_text

    class MetadataPath:
        def __init__(self, path, mode, group):
            self.path, self.mode, self.group = path, mode, group
        def lstat(self):
            info = self.path.lstat()
            return SimpleNamespace(st_mode=(info.st_mode & ~0o777) | (self.mode or 0o600),
                st_nlink=info.st_nlink, st_uid=0, st_gid=self.group or 0,
                st_dev=info.st_dev, st_ino=info.st_ino, st_size=info.st_size)

    def metadata(path, **options):
        return original_metadata(MetadataPath(path, options.get("mode"), options.get("group")), **options)

    def persist(record):
        target = tmp_path / "installation.json"
        temporary = tmp_path / "public-journal-next"
        temporary.write_text(json.dumps(record))
        os.replace(temporary, target)

    def guarded_read_bytes(path, *args, **kwargs):
        assert path.name not in runtime.FILES, "Installer must not read existing private/configuration files"
        return original_read_bytes(path, *args, **kwargs)

    def guarded_read_text(path, *args, **kwargs):
        assert path.name not in runtime.FILES, "Installer must not read existing private/configuration files"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(runtime, "_metadata", metadata)
    monkeypatch.setattr(runtime, "_save_marker", persist)
    monkeypatch.setattr(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), raising=False)
    monkeypatch.setattr(os, "fchown", lambda *args: None, raising=False)
    monkeypatch.setattr(os, "fchmod", lambda *args: None, raising=False)
    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    return tmp_path, persist, original_read_bytes


@pytest.mark.parametrize("boundary", range(1, 15))
@pytest.mark.parametrize("after", [False, True])
def test_each_partial_journal_boundary_resumes_original_keys_without_secret_reads(journal_files, monkeypatch, boundary, after):
    root, persist, read_generated = journal_files
    material = generated()
    lookup = runtime.validate_material(material)
    calls = 0

    def interrupted(record):
        nonlocal calls
        calls += 1
        if calls == boundary and not after:
            raise OSError("Synthetic process interruption")
        persist(record)
        if calls == boundary and after:
            raise OSError("Synthetic process interruption")

    monkeypatch.setattr(runtime, "_save_marker", interrupted)
    with pytest.raises(OSError, match="Synthetic process interruption"):
        runtime._install_material(material, lookup, 123)
    # Any existing final inode must survive recovery, not be replaced.
    prior = {name: (root / name).stat().st_ino for name in runtime.FILES if (root / name).exists()}
    monkeypatch.setattr(runtime, "_save_marker", persist)
    receipt = runtime._install_material(material, lookup, 123)
    assert receipt["material_sha256"] == runtime.material_digest(material)
    assert all((root / name).stat().st_ino == inode for name, inode in prior.items())
    assert runtime.replay_installation(material, 123)["replayed"]
    assert all((root / name).stat().st_nlink == 1 for name in runtime.FILES)
    assert not list(root.glob(".runtime-*.pending"))
    # Inspect only these newly generated synthetic outputs as a test, not helper I/O.
    envelope = json.loads(read_generated(root / "keys.json"))
    recovered = json.loads(Fernet(material["wrapping_key"].encode()).decrypt(envelope["payload"].encode()))
    assert recovered["encryption_key"] == material["encryption_key"]
    assert recovered["signing_key"] == material["signing_key"]
    assert base64.b64decode(recovered["lookup_keys"]["1"]) == lookup
    assert read_generated(root / "runtime.env") == runtime._contents(material, lookup)["runtime.env"]


def test_partial_staging_write_can_be_rebuilt_only_on_its_owned_inode(journal_files, monkeypatch):
    root, persist, read_generated = journal_files
    material = generated()
    calls = 0

    def interrupted(record):
        nonlocal calls
        calls += 1
        persist(record)
        if calls == 3:
            raise OSError("Stopped after owning empty inode")

    monkeypatch.setattr(runtime, "_save_marker", interrupted)
    with pytest.raises(OSError):
        runtime._install_material(material, runtime.validate_material(material), 123)
    record = json.loads((root / "installation.json").read_text())
    stage = root / record["files"]["keys.json"]["staging_name"]
    stage.write_bytes(b"incomplete synthetic encrypted stream")
    owned_inode = stage.stat().st_ino
    monkeypatch.setattr(runtime, "_save_marker", persist)
    runtime._install_material(material, runtime.validate_material(material), 123)
    assert (root / "keys.json").stat().st_ino == owned_inode
    assert json.loads(read_generated(root / "keys.json"))["format"] == "fernet-v1"


def test_same_name_unrelated_file_and_different_material_are_never_overwritten(journal_files, monkeypatch):
    root, persist, read_generated = journal_files
    material = generated()
    calls = 0

    def interrupted(record):
        nonlocal calls
        calls += 1
        persist(record)
        if calls == 4:
            raise OSError("Prepared, not yet published")

    monkeypatch.setattr(runtime, "_save_marker", interrupted)
    with pytest.raises(OSError):
        runtime._install_material(material, runtime.validate_material(material), 123)
    (root / "keys.json").write_bytes(b"unrelated file")
    monkeypatch.setattr(runtime, "_save_marker", persist)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        runtime._install_material(material, runtime.validate_material(material), 123)
    assert read_generated(root / "keys.json") == b"unrelated file"
    different = generated()
    with pytest.raises(ValueError, match="MATERIAL_OR_STATE_MISMATCH"):
        runtime._install_material(different, runtime.validate_material(different), 123)
    assert read_generated(root / "keys.json") == b"unrelated file"


def test_legacy_partial_final_files_have_no_ownership_proof_and_remain_untouched(journal_files):
    root, persist, read_generated = journal_files
    material = generated()
    persist({"version": 1, "mode": "pilot", "state": "configuring", "material_sha256": runtime.material_digest(material)})
    (root / "runtime.env").write_bytes(b"unknown old contents")
    with pytest.raises(ValueError, match="LEGACY_PARTIAL_INSTALLATION_NEEDS_REVIEW"):
        runtime._install_material(material, runtime.validate_material(material), 123)
    assert read_generated(root / "runtime.env") == b"unknown old contents"


@pytest.mark.parametrize("change", [{"st_uid": 1}, {"st_nlink": 2}, {"st_mode": 0o100644},
                                   {"st_mode": 0o120600}, {"st_gid": 999}, {"st_size": 0}])
def test_native_metadata_policy_rejects_unsafe_files(change):
    from types import SimpleNamespace
    info = {"st_mode": 0o100640, "st_uid": 0, "st_gid": 123, "st_nlink": 1,
            "st_size": 20, "st_dev": 1, "st_ino": 2} | change
    path = SimpleNamespace(lstat=lambda: SimpleNamespace(**info))
    with pytest.raises(ValueError, match="METADATA_MISMATCH"):
        runtime._metadata(path, mode=0o640, group=123)
