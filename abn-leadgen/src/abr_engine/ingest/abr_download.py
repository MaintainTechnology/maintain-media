"""Archive validation and coherent offline publication staging.

Live HTTP discovery is deliberately gated on an approved publisher mapping.
Injected transport download support validates range/validator semantics and never
uses credentials or a default live URL.
"""

from __future__ import annotations

import random
import re
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import duckdb

from abr_engine.ops.analytical import analytical_guard

from .abr_parse import ABRMapping, ParsedMember, parse_xml
from .common import SourceError, digest_file
from .snapshots import content_identity


@dataclass(frozen=True)
class ArchiveResource:
    resource_id: str
    part_label: str
    path: Path
    member_labels: dict[str, str]
    resource_url: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    declared_size: int | None = None


@dataclass(frozen=True)
class Publication:
    content_digest: str
    members: tuple[ParsedMember, ...]
    manifest: dict


def _inventory(items: list[dict]) -> list[tuple]:
    entries = [
        (x["resource_id"], x["part_label"], x.get("etag"), x.get("last_modified"), x.get("declared_size"))
        for x in items
    ]
    if len({(x[0], x[1]) for x in entries}) != len(entries):
        raise SourceError("DUPLICATE_RESOURCE")
    return sorted(entries, key=lambda x: (x[0], x[1]))


def ingest_archives(
    resources: list[ArchiveResource],
    staging_dir: Path,
    *,
    mapping: ABRMapping,
    inventory_before: list[dict],
    inventory_after: list[dict],
    required_parts: set[str],
    expected_sequences: set[int],
    max_uncompressed_bytes: int = 16 * 1024**3,
    max_members: int = 1000,
    max_compression_ratio: int = 1000,
    production: bool = False,
    authority: Callable[[], object] | None = None,
    progress: Callable[[dict], object] | None = None,
) -> Publication:
    mapping.validate(production)
    if authority is not None:
        authority()
    if _inventory(inventory_before) != _inventory(inventory_after):
        raise SourceError("INVENTORY_CHANGED_DURING_DOWNLOAD")
    if {r.part_label for r in resources} != required_parts or len(resources) != len(required_parts):
        raise SourceError("INCOMPLETE_PART_INVENTORY")
    if {(r.resource_id, r.part_label) for r in resources} != {
        (x[0], x[1]) for x in _inventory(inventory_before)
    }:
        raise SourceError("RESOURCE_INVENTORY_MISMATCH")
    staging_dir.mkdir(parents=True, exist_ok=False)
    parsed: list[ParsedMember] = []
    parts, evidence, sequences, generations, extract_times = [], [], set(), set(), set()
    member_names: set[str] = set()
    expanded, member_count = 0, 0
    for resource_index, resource in enumerate(sorted(resources, key=lambda r: r.part_label)):
        if resource.declared_size is not None and resource.path.stat().st_size != resource.declared_size:
            raise SourceError("DOWNLOAD_LENGTH_MISMATCH")
        members, archive_evidence = [], []
        with zipfile.ZipFile(resource.path) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(set(names)) != len(names):
                raise SourceError("DUPLICATE_ARCHIVE_MEMBER")
            if set(names) != set(resource.member_labels):
                raise SourceError("MEMBER_INVENTORY_MISMATCH")
            for member_index, info in enumerate(infos):
                if authority is not None:
                    authority()
                name = info.filename
                if name in member_names:
                    raise SourceError("DUPLICATE_ARCHIVE_MEMBER")
                member_names.add(name)
                safe = PurePosixPath(name)
                if (
                    info.flag_bits & 1
                    or "\\" in name
                    or ":" in name
                    or safe.is_absolute()
                    or ".." in safe.parts
                    or info.is_dir()
                    or safe.suffix.lower() != ".xml"
                    or (info.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise SourceError("UNSAFE_ARCHIVE_MEMBER")
                expanded += info.file_size
                member_count += 1
                if (
                    expanded > max_uncompressed_bytes
                    or member_count > max_members
                    or info.file_size > max(1, info.compress_size) * max_compression_ratio
                ):
                    raise SourceError("ARCHIVE_EXPANSION_LIMIT")
                member_dir = staging_dir / f"resource-{resource_index}" / f"member-{member_index}"
                member_dir.mkdir(parents=True)
                extracted = member_dir / "source.xml"
                actual = 0
                with archive.open(info) as source, extracted.open("xb") as destination:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        actual += len(chunk)
                        if actual > info.file_size or actual > max_uncompressed_bytes:
                            raise SourceError("ARCHIVE_EXPANSION_LIMIT")
                        destination.write(chunk)
                        if authority is not None and actual % (64 * 1024 * 1024) == 0:
                            authority()
                if actual != info.file_size:
                    raise SourceError("MEMBER_LENGTH_MISMATCH")
                result = parse_xml(
                    extracted, member_dir, mapping=mapping, production=production, member_name=name,
                    authority=authority, progress=progress,
                )
                parsed.append(result)
                sequence = int(result.header["sequence"])
                if sequence in sequences:
                    raise SourceError("DUPLICATE_SEQUENCE")
                sequences.add(sequence)
                generations.add(result.header["generation"])
                extract_times.add(result.header["extract_time"])
                members.append(
                    {"member_label": resource.member_labels[name], "uncompressed_sha256": result.sha256}
                )
                archive_evidence.append(
                    {
                        "name": name,
                        "content_sha256": result.sha256,
                        "crc32": f"{info.CRC:08x}",
                        "declared_record_count": result.row_count,
                        "header": result.header,
                        "first_abn": result.first_abn,
                        "last_abn": result.last_abn,
                    }
                )
        parts.append({"part_label": resource.part_label, "members": members})
        evidence.append(
            {
                "resource_id": resource.resource_id,
                "part_label": resource.part_label,
                "resource_url": resource.resource_url,
                "etag": resource.etag,
                "last_modified": resource.last_modified,
                "declared_size": resource.declared_size,
                "download_sha256": digest_file(resource.path),
                "members": archive_evidence,
            }
        )
    if sequences != expected_sequences or len(generations) != 1 or len(extract_times) != 1:
        raise SourceError("GENERATION_UNPROVABLE")
    con = duckdb.connect()
    try:
        with analytical_guard(con, authority) as checkpoint:
            con.execute("SET memory_limit='512MB'")
            con.execute("SET threads=2")
            con.execute("SET max_temp_directory_size='8GB'")
            con.execute("SET temp_directory=?", [str(staging_dir / "spill")])
            checkpoint()
            duplicate = con.execute(
                "SELECT abn FROM read_parquet(?) GROUP BY abn HAVING count(*)>1 LIMIT 1",
                [[str(m.parquet_path) for m in parsed]],
            ).fetchone()
            checkpoint()
            if duplicate:
                raise SourceError("DUPLICATE_ABN_ACROSS_MEMBERS")
    finally:
        con.close()
    from abr_engine.ingest.quality import weighted_fill

    quality = weighted_fill(parsed)
    if authority is not None:
        authority()
    digest = content_identity(parts)
    return Publication(
        digest,
        tuple(parsed),
        {
            "manifest_version": 1,
            "source": "abr",
            "mapping_version": mapping.version,
            "content_digest": digest,
            "identity_parts": parts,
            "resources": evidence,
            "coherence": "validated",
            "generation": next(iter(generations)),
            "extract_time": next(iter(extract_times)),
            **quality,
        },
    )


def download_resource(
    url: str,
    target: Path,
    *,
    transport: Callable,
    expected_sha256: str | None = None,
    max_bytes: int = 8 * 1024**3,
    sleep: Callable = time.sleep,
    jitter: Callable = random.random,
) -> Path:
    """Transport(url, headers, connect_timeout, read_timeout) returns a context
    manager with status_code, headers and iter_bytes(); five total attempts.
    No default transport exists: caller must supply an approved adapter.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SourceError("SOURCE_HTTPS_REQUIRED")
    if target.exists():
        raise SourceError("ARTIFACT_ALREADY_EXISTS")
    partial = target.with_suffix(target.suffix + ".partial")
    # Never trust a previous process's partial bytes without its validator record.
    partial.unlink(missing_ok=True)
    validator: str | None = None
    total_length: int | None = None
    expected_response: int | None = None
    for attempt in range(5):
        offset = partial.stat().st_size if partial.exists() and validator else 0
        headers = {"Accept-Encoding": "identity"}
        if offset and validator is not None:
            headers.update({"Range": f"bytes={offset}-", "If-Range": validator})
        try:
            with transport(url, headers=headers, connect_timeout=10, read_timeout=20) as response:
                h = {k.lower(): v for k, v in response.headers.items()}
                etag = h.get("etag")
                strong = etag if etag and etag.startswith('"') and etag.endswith('"') else None
                if response.status_code == 206:
                    match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", h.get("content-range", ""))
                    if not offset or not match or int(match[1]) != offset or strong != validator:
                        raise SourceError("INVALID_RESUME_RANGE")
                    start, end, total = map(int, match.groups())
                    if end < start or end >= total or (total_length is not None and total != total_length):
                        raise SourceError("INVALID_RESUME_RANGE")
                    total_length = total
                    expected_response = end - start + 1
                elif response.status_code == 200:
                    offset = 0
                    total_length = int(h["content-length"]) if "content-length" in h else None
                    expected_response = total_length
                else:
                    raise OSError("source response unavailable")
                if h.get("content-encoding", "identity").lower() != "identity":
                    raise SourceError("UNEXPECTED_CONTENT_ENCODING")
                validator = strong
                received = 0
                with partial.open("ab" if offset else "wb") as output:
                    for block in response.iter_bytes():
                        received += len(block)
                        if offset + received > max_bytes:
                            raise SourceError("DOWNLOAD_SIZE_LIMIT")
                        output.write(block)
                if expected_response is not None and received != expected_response:
                    raise OSError("incomplete download")
                if total_length is not None and offset + received != total_length:
                    raise OSError("incomplete download")
                if expected_sha256 and digest_file(partial) != expected_sha256:
                    raise SourceError("DOWNLOAD_DIGEST_MISMATCH")
                partial.rename(target)
                return target
        except (OSError, TimeoutError):
            if attempt == 4:
                raise SourceError("DOWNLOAD_ATTEMPTS_EXHAUSTED") from None
            sleep(2**attempt + jitter())
        except SourceError:
            partial.unlink(missing_ok=True)
            raise
    raise AssertionError("unreachable")
