"""Exact content identity and immutable local manifest sealing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .common import SourceError, canonical_json, digest_file


def content_identity(parts: list[dict]) -> str:
    labels: set[str] = set()
    projection = []
    for part in sorted(parts, key=lambda p: p["part_label"].encode("utf-8")):
        label = part["part_label"]
        if not label or label in labels:
            raise SourceError("DUPLICATE_PART_LABEL")
        labels.add(label)
        member_labels: set[str] = set()
        members = []
        for member in sorted(part["members"], key=lambda m: m["member_label"].encode("utf-8")):
            name, digest = member["member_label"], member["uncompressed_sha256"]
            if not name or name in member_labels:
                raise SourceError("DUPLICATE_MEMBER_LABEL")
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise SourceError("INVALID_CONTENT_DIGEST")
            member_labels.add(name)
            members.append({"member_label": name, "uncompressed_sha256": digest})
        if not members:
            raise SourceError("EMPTY_PART")
        projection.append({"part_label": label, "members": members})
    if not projection:
        raise SourceError("EMPTY_INVENTORY")
    return hashlib.sha256(canonical_json({"identity_version": 1, "parts": projection}).encode()).hexdigest()


def seal_manifest(path: Path, manifest: dict, artifacts: list[Path]) -> str:
    """Exclusive create; the caller registers ownership before invoking this writer."""
    manifest = {
        **manifest,
        "artifacts": [
            {"path": str(p), "sha256": digest_file(p), "bytes": p.stat().st_size} for p in artifacts
        ],
    }
    data = canonical_json(manifest).encode()
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        import os

        os.fsync(stream.fileno())
    if json.loads(path.read_text(encoding="utf-8")) != manifest:
        raise SourceError("MANIFEST_READBACK_FAILED")
    return hashlib.sha256(data).hexdigest()


def current_content_noop(
    *,
    current_digest: str | None,
    incoming_digest: str,
    current_parser: str | None,
    incoming_parser: str,
    current_schema: str | None,
    incoming_schema: str,
) -> bool:
    return (
        current_digest == incoming_digest
        and current_parser == incoming_parser
        and current_schema == incoming_schema
    )
