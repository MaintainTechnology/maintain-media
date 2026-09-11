"""Build/verify/extract a public dormant-engine archive; stdlib only, no network."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import tarfile
from pathlib import Path, PurePosixPath

SCHEMA = "abr-dormant-release-v1"
MANIFEST = "RELEASE-MANIFEST.json"
LIMIT = 32 * 1024 * 1024
MAX_FILES = 999  # Plus one manifest member; shared with archive verification.
GENERATED = {"config/fixture.yaml": b"mode: fixture\n"}
FIXED = frozenset({
    "pyproject.toml", "uv.lock", ".python-version", "config/qualification.yaml",
    "config/sources/abr-public.xsd", "config/sources/abr-public-mapping.json",
    "src/abr_engine/__init__.py", "src/abr_engine/cli.py", "src/abr_engine/config.py",
    "migrations/001_foundation.sql",
    "integrations/crm_fields.yaml", "templates/report.html.j2", "templates/report.md.j2",
    "templates/worklist_schema.json", "tests/conftest.py",
    "tests/unit/test_qualification_policy.py", "tests/unit/test_publication_quality.py",
    "tests/unit/test_qbcc_publisher.py", "tests/unit/test_live_readiness.py",
    "tests/unit/test_dashboard_gateway.py", "ops/aws/prepare_release.py",
    "ops/aws/test_prepare_release.py", "ops/aws/release-install.md",
    "ops/aws/backup_crypto.py", "ops/aws/backup_runtime.py", "ops/aws/backup_store.py",
    "ops/aws/backup_restore.py", "ops/aws/backup_cli.py", "ops/aws/backup-operations.md",
    "ops/aws/backup_schedule.py", "ops/aws/backup_schedule_install.py",
    "ops/aws/backup-auth-lightsail.md", "ops/aws/schedule-and-maintenance.md",
    "ops/production/prepare.py", "ops/aws/backup_infrastructure.py",
    "ops/aws/backup_install_identity.py", "ops/aws/provision_runtime.py", "ops/aws/provision_database.py",
    "ops/aws/provision_private_files.py", "ops/aws/provision_sheets.py",
    "ops/aws/abr-engine-api.service", "ops/aws/abr-engine-worker.service",
    "ops/aws/abr-engine-worker.timer", "ops/aws/abr-engine-control.service",
    "ops/aws/abr-engine-control.timer", "ops/aws/abr-engine.slice",
    "ops/aws/abr-engine-qbcc-weekly.service", "ops/aws/abr-engine-qbcc-weekly.timer",
    "ops/aws/abr-engine-qbcc-review-cleanup.service", "ops/aws/abr-engine-qbcc-review-cleanup.timer",
    "ops/aws/abr-engine-retention.service", "ops/aws/abr-engine-retention.timer",
    "ops/aws/abr-engine-abr-worker.service", "ops/aws/abr-engine-abr-worker.timer",
    "src/abr_engine/dashboard/static/OFL.txt", "src/abr_engine/dashboard/static/logo.svg",
    "src/abr_engine/dashboard/static/index.html", "src/abr_engine/dashboard/static/dashboard.js",
    "src/abr_engine/dashboard/static/dashboard.css", "src/abr_engine/dashboard/static/albert-sans.ttf",
})
PRIVATE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore", ".enc", ".der"}


class ReleaseError(ValueError):
    """Closed release admission; messages intentionally omit file contents."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def public_name(name: str) -> bool:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", name):
        return False
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if any(part.lower().startswith(".env") or Path(part).suffix.lower() in PRIVATE_SUFFIXES
           for part in parts):
        return False
    if name in FIXED or name in GENERATED:
        return True
    return bool(re.fullmatch(r"src/abr_engine/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\.py", name)
                or re.fullmatch(r"migrations/[0-9]{3}_[A-Za-z0-9_]+\.sql", name))


def no_links(path: Path) -> None:
    """Check every existing lexical ancestor, including Windows junctions."""
    absolute = path.absolute()
    for item in (*reversed(absolute.parents), absolute):
        metadata = item.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ReleaseError("LINK_OR_REPARSE_POINT_REFUSED")


def read_public(root: Path, name: str) -> bytes:
    if not public_name(name) or name in GENERATED:
        raise ReleaseError("SOURCE_NOT_ALLOWLISTED")
    path = root.joinpath(*PurePosixPath(name).parts)
    no_links(path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > LIMIT:
        raise ReleaseError("SOURCE_NOT_REGULAR_OR_TOO_LARGE")
    if metadata.st_nlink != 1:
        raise ReleaseError("SOURCE_HARDLINK_REFUSED")
    data = path.read_bytes()
    if len(data) != metadata.st_size:
        raise ReleaseError("SOURCE_CHANGED_DURING_READ")
    return data


def inventory(root: Path) -> dict[str, bytes]:
    no_links(root)
    if not root.is_dir():
        raise ReleaseError("PROJECT_DIRECTORY_REQUIRED")
    names = set(FIXED)
    for base in ("src/abr_engine", "migrations"):
        directory = root / base
        no_links(directory)
        for current, directories, files in os.walk(directory, followlinks=False):
            directories[:] = sorted(item for item in directories if item != "__pycache__")
            for item in directories:
                no_links(Path(current) / item)
            for filename in files:
                name = (Path(current) / filename).relative_to(root).as_posix()
                if public_name(name):
                    names.add(name)
    result = {name: read_public(root, name) for name in sorted(names)}
    result.update(GENERATED)
    return dict(sorted(result.items()))


def make_archive(files: dict[str, bytes]) -> tuple[bytes, dict]:
    manifest = {"schema": SCHEMA, "runtime": "dormant", "files": [
        {"path": name, "size": len(data), "sha256": digest(data),
         "origin": "generated-offline-default" if name in GENERATED else "reviewed-source"}
        for name, data in sorted(files.items())
    ]}
    manifest_bytes = canonical(manifest)
    if len(files) > MAX_FILES or sum(map(len, files.values())) + len(manifest_bytes) > LIMIT:
        raise ReleaseError("ARCHIVE_EXPANSION_LIMIT")
    stream = io.BytesIO()
    with (
        gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive,
    ):
        for name, data in [(MANIFEST, manifest_bytes), *sorted(files.items())]:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o640, 0
            archive.addfile(info, io.BytesIO(data))
    raw = stream.getvalue()
    if len(raw) > LIMIT:
        raise ReleaseError("ARCHIVE_TOO_LARGE")
    return raw, manifest


def build(root: Path, output: Path) -> dict:
    root, output = root.absolute(), output.absolute()
    no_links(output.parent)
    if output == root or root in output.parents:
        raise ReleaseError("OUTPUT_MUST_BE_OUTSIDE_PROJECT")
    if output.exists() or output.is_symlink():
        raise ReleaseError("OUTPUT_ALREADY_EXISTS")
    files = inventory(root)
    archive, manifest = make_archive(files)
    # Re-read the same public allowlist only; do not silently package a moving tree.
    if inventory(root) != files:
        raise ReleaseError("SOURCE_CHANGED_DURING_BUILD")
    receipt = {"schema": SCHEMA, "runtime": "dormant", "archive": "release.tar.gz",
               "archive_sha256": digest(archive), "manifest_sha256": digest(canonical(manifest)),
               "file_count": len(files), "uv_lock_sha256": digest(files["uv.lock"])}
    output.mkdir(mode=0o700)
    for name, data in (("release.tar.gz", archive), ("receipt.json", canonical(receipt))):
        with (output / name).open("xb") as handle:
            handle.write(data)
        (output / name).chmod(0o444)
    return receipt


def verify(archive_path: Path, expected_sha256: str) -> tuple[dict, dict[str, bytes]]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ReleaseError("TRUSTED_ARCHIVE_SHA256_REQUIRED")
    no_links(archive_path)
    metadata = archive_path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > LIMIT:
        raise ReleaseError("ARCHIVE_NOT_REGULAR_OR_TOO_LARGE")
    raw = archive_path.read_bytes()
    if digest(raw) != expected_sha256:
        raise ReleaseError("ARCHIVE_DIGEST_MISMATCH")
    files: dict[str, bytes] = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive:
            if (not member.isfile() or member.name in files
                    or (member.name != MANIFEST and not public_name(member.name))):
                raise ReleaseError("ARCHIVE_MEMBER_REFUSED")
            total += member.size
            if member.size < 0 or total > LIMIT or len(files) > MAX_FILES:
                raise ReleaseError("ARCHIVE_EXPANSION_LIMIT")
            handle = archive.extractfile(member)
            if handle is None:
                raise ReleaseError("ARCHIVE_MEMBER_UNREADABLE")
            data = handle.read()
            if len(data) != member.size:
                raise ReleaseError("ARCHIVE_MEMBER_TRUNCATED")
            files[member.name] = data
    try:
        manifest = json.loads(files.pop(MANIFEST))
        if (not isinstance(manifest, dict) or set(manifest) != {"schema", "runtime", "files"}
                or manifest["schema"] != SCHEMA or manifest["runtime"] != "dormant"
                or not isinstance(manifest["files"], list)):
            raise ReleaseError("MANIFEST_INVALID")
        actual = {}
        for record in manifest["files"]:
            if (not isinstance(record, dict) or set(record) != {"path", "size", "sha256", "origin"}
                    or not isinstance(record["path"], str) or record["path"] in actual):
                raise ReleaseError("MANIFEST_INVALID")
            name = record["path"]
            data = files[name]
            origin = "generated-offline-default" if name in GENERATED else "reviewed-source"
            if (not public_name(name) or type(record["size"]) is not int
                    or record["size"] != len(data) or record["sha256"] != digest(data)
                    or record["origin"] != origin):
                raise ReleaseError("MANIFEST_FILE_MISMATCH")
            actual[name] = data
        if set(actual) != set(files) or not (FIXED | GENERATED.keys()) <= actual.keys():
            raise ReleaseError("MANIFEST_FILE_SET_MISMATCH")
        if any(files[name] != data for name, data in GENERATED.items()):
            raise ReleaseError("OFFLINE_CONFIGURATION_CHANGED")
        return manifest, files
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReleaseError("MANIFEST_INVALID") from error


def extract(archive_path: Path, expected_sha256: str, destination: Path) -> dict:
    manifest, files = verify(archive_path, expected_sha256)
    destination = destination.absolute()
    no_links(destination)
    if not destination.is_dir() or any(destination.iterdir()):
        raise ReleaseError("EMPTY_EXISTING_DESTINATION_REQUIRED")
    # No tar extraction API: create only verified regular files, never links or overwrite.
    for name, data in {MANIFEST: canonical(manifest), **files}.items():
        path = destination.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True, mode=0o750, exist_ok=True)
        no_links(path.parent)
        with path.open("xb") as handle:
            handle.write(data)
        path.chmod(0o640)
    return {"status": "dormant_source_extracted", "file_count": len(files),
            "archive_sha256": expected_sha256, "services_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("build")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    for name in ("verify", "extract"):
        command = commands.add_parser(name)
        command.add_argument("--archive", type=Path, required=True)
        command.add_argument("--sha256", required=True)
        if name == "extract":
            command.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build(args.root, args.output)
        elif args.command == "extract":
            result = extract(args.archive, args.sha256, args.destination)
        else:
            manifest, files = verify(args.archive, args.sha256)
            result = {"status": "dormant_release_verified", "archive_sha256": args.sha256,
                      "file_count": len(files), "manifest_sha256": digest(canonical(manifest))}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ReleaseError, OSError, tarfile.TarError, EOFError) as error:
        code = str(error) if isinstance(error, ReleaseError) else "RELEASE_IO_OR_ARCHIVE_INVALID"
        print(json.dumps({"status": "blocked", "code": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
