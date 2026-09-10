"""Synthetic filesystem tests only; never contact a host or read project secrets."""

import importlib.util
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("prepare_release", Path(__file__).with_name("prepare_release.py"))
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    for name in release.FIXED | {"src/abr_engine/extra.py", "migrations/002_workflows.sql"}:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic public content\n", encoding="utf-8")
    return root


def write_archive(tmp_path, data):
    path = tmp_path / "input.tar.gz"
    path.write_bytes(data)
    return path, release.digest(data)


def repack(files, manifest=None, extra=None):
    _, generated = release.make_archive(files)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, data in [(release.MANIFEST, release.canonical(manifest or generated)), *files.items()]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if extra:
            member, data = extra
            archive.addfile(member, io.BytesIO(data) if data is not None else None)
    return stream.getvalue()


def test_archive_roundtrip_is_deterministic_and_inactive(project, tmp_path):
    first = release.build(project, tmp_path / "first")
    second = release.build(project, tmp_path / "second")
    assert first == second
    archive = tmp_path / "first/release.tar.gz"
    manifest, files = release.verify(archive, first["archive_sha256"])
    assert manifest["runtime"] == "dormant"
    assert files["config/fixture.yaml"] == b"mode: fixture\n"
    target = tmp_path / "installed"
    target.mkdir()
    receipt = release.extract(archive, first["archive_sha256"], target)
    assert receipt["services_started"] is False
    assert (target / "src/abr_engine/cli.py").read_bytes() == files["src/abr_engine/cli.py"]
    assert json.loads((target / release.MANIFEST).read_text()) == manifest


@pytest.mark.parametrize("name", [".env", ".env.local", "config/live.yaml", "config/fixture.yaml",
    "secrets/service-account.json", "var/source.csv", "ops/aws/account.json",
    "src/abr_engine/.env.production", "src/abr_engine/private.pem", "tests/fixtures/real.csv"])
def test_excluded_inputs_are_not_read_even_if_present(project, name, monkeypatch):
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("must never be read", encoding="utf-8")
    original = Path.read_bytes

    def guarded(candidate):
        assert candidate != path, "excluded private input was read"
        return original(candidate)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    files = release.inventory(project)
    if name in release.GENERATED:
        assert files[name] == release.GENERATED[name]
    else:
        assert name not in files


@pytest.mark.parametrize("name", ["../uv.lock", "/uv.lock", "src/../uv.lock", "src//abr_engine/a.py",
    "src\\abr_engine\\a.py", "C:/uv.lock", "src/abr_engine/.env.py", "src/abr_engine/x.pem"])
def test_hostile_path_names_are_rejected_before_read(project, name):
    assert not release.public_name(name)
    with pytest.raises(release.ReleaseError, match="NOT_ALLOWLISTED"):
        release.read_public(project, name)


def test_existing_output_and_project_output_refused(project, tmp_path):
    output = tmp_path / "exists"
    output.mkdir()
    with pytest.raises(release.ReleaseError, match="ALREADY_EXISTS"):
        release.build(project, output)
    with pytest.raises(release.ReleaseError, match="OUTSIDE_PROJECT"):
        release.build(project, project / "package")


def test_missing_required_file_refuses_release(project, tmp_path):
    (project / "uv.lock").unlink()
    with pytest.raises(FileNotFoundError):
        release.build(project, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_source_drift_is_refused_before_output(project, tmp_path, monkeypatch):
    original = release.inventory
    calls = 0

    def moving(root):
        nonlocal calls
        calls += 1
        result = original(root)
        if calls == 2:
            result["uv.lock"] = b"changed"
        return result

    monkeypatch.setattr(release, "inventory", moving)
    with pytest.raises(release.ReleaseError, match="SOURCE_CHANGED"):
        release.build(project, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_archive_digest_is_independently_required(project, tmp_path):
    data, _ = release.make_archive(release.inventory(project))
    path, _ = write_archive(tmp_path, data)
    with pytest.raises(release.ReleaseError, match="DIGEST_MISMATCH"):
        release.verify(path, "0" * 64)
    with pytest.raises(release.ReleaseError, match="TRUSTED_ARCHIVE"):
        release.verify(path, "not-a-hash")


@pytest.mark.parametrize("kind", ["traversal", "duplicate", "symlink", "hardlink", "directory"])
def test_invalid_archive_members_refused(project, tmp_path, kind):
    files = release.inventory(project)
    name = "../outside" if kind == "traversal" else "src/abr_engine/extra.py"
    member = tarfile.TarInfo(name)
    data = b""
    if kind in {"symlink", "hardlink", "directory"}:
        member.name = "src/abr_engine/unsafe.py"
        member.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                       "directory": tarfile.DIRTYPE}[kind]
        member.linkname = "../../outside"
        data = None
    raw = repack(files, extra=(member, data))
    path, sha = write_archive(tmp_path, raw)
    with pytest.raises(release.ReleaseError, match="MEMBER_REFUSED"):
        release.verify(path, sha)


@pytest.mark.parametrize("kind", ["hash", "size", "origin", "duplicate", "missing", "runtime"])
def test_manifest_corruption_is_refused(project, tmp_path, kind):
    files = release.inventory(project)
    _, manifest = release.make_archive(files)
    if kind in {"hash", "size", "origin"}:
        field = {"hash": "sha256", "size": "size", "origin": "origin"}[kind]
        manifest["files"][0][field] = {"hash": "0" * 64, "size": -1, "origin": "live"}[kind]
    elif kind == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif kind == "missing":
        manifest["files"].pop()
    else:
        manifest["runtime"] = "production"
    path, sha = write_archive(tmp_path, repack(files, manifest))
    with pytest.raises(release.ReleaseError, match="MANIFEST"):
        release.verify(path, sha)


def test_generated_configuration_cannot_be_promoted(project, tmp_path):
    files = release.inventory(project)
    files["config/fixture.yaml"] = b"mode: production\n"
    path, sha = write_archive(tmp_path, repack(files))
    with pytest.raises(release.ReleaseError, match="OFFLINE_CONFIGURATION_CHANGED"):
        release.verify(path, sha)


def test_nonempty_destination_never_overwritten(project, tmp_path):
    raw, _ = release.make_archive(release.inventory(project))
    path, sha = write_archive(tmp_path, raw)
    target = tmp_path / "installed"
    target.mkdir()
    keep = target / "keep"
    keep.write_text("preserve")
    with pytest.raises(release.ReleaseError, match="EMPTY_EXISTING_DESTINATION"):
        release.extract(path, sha, target)
    assert keep.read_text() == "preserve"


def test_symlink_source_and_destination_refused(project, tmp_path):
    target = tmp_path / "alias"
    try:
        target.symlink_to(project, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit creating symlinks")
    with pytest.raises(release.ReleaseError, match="LINK_OR_REPARSE"):
        release.inventory(target)
    raw, _ = release.make_archive(release.inventory(project))
    path, sha = write_archive(tmp_path, raw)
    with pytest.raises(release.ReleaseError, match="LINK_OR_REPARSE"):
        release.extract(path, sha, target)


def test_reparse_point_metadata_is_rejected(project, monkeypatch):
    original = Path.lstat

    def reparse(path):
        if path == project:
            class Junction:
                st_mode = 0o40755
                st_file_attributes = 0x400
            return Junction()
        return original(path)

    monkeypatch.setattr(Path, "lstat", reparse)
    with pytest.raises(release.ReleaseError, match="LINK_OR_REPARSE"):
        release.no_links(project)


def test_hardlink_cannot_disguise_private_input_as_python_source(project, tmp_path, monkeypatch):
    private = tmp_path / ".env.synthetic"
    private.write_text("must never be read", encoding="utf-8")
    alias = project / "src/abr_engine/alias.py"
    os.link(private, alias)
    original = Path.read_bytes

    def guarded(path):
        assert path not in {private, alias}, "private hard-link alias was read"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    with pytest.raises(release.ReleaseError, match="SOURCE_HARDLINK_REFUSED"):
        release.inventory(project)


def test_builder_obeys_verifier_aggregate_and_member_limits(project, monkeypatch):
    files = release.inventory(project)
    monkeypatch.setattr(release, "LIMIT", sum(map(len, files.values())) + 1)
    with pytest.raises(release.ReleaseError, match="EXPANSION_LIMIT"):
        release.make_archive(files)
    monkeypatch.setattr(release, "LIMIT", 32 * 1024 * 1024)
    monkeypatch.setattr(release, "MAX_FILES", len(files) - 1)
    with pytest.raises(release.ReleaseError, match="EXPANSION_LIMIT"):
        release.make_archive(files)
