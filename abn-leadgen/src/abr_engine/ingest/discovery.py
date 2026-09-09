"""Explicit publisher-contract discovery composition; no default network adapter.

This entry point is fixture development only. A real publisher contract and live
G1/G6-authorised adapter remain separate obligations, not a boolean bypass here.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .abr_download import ArchiveResource, Publication, download_resource, ingest_archives
from .abr_parse import ABRMapping
from .common import SourceError, digest_file


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DiscoveredResource(Closed):
    resource_id: str = Field(min_length=1, max_length=256)
    part_label: str = Field(min_length=1, max_length=256)
    resource_url: str = Field(min_length=1, max_length=2048)
    member_labels: dict[str, str] = Field(min_length=1, max_length=1000)
    etag: str | None = Field(max_length=512)
    last_modified: str | None = Field(max_length=512)
    declared_size: int | None = Field(ge=1)
    expected_sha256: str | None = Field(pattern="^[a-f0-9]{64}$")


class DiscoverySnapshot(Closed):
    dataset_id: str = Field(min_length=1, max_length=256)
    generation: str = Field(min_length=1, max_length=256)
    published_at: str | None
    required_parts: list[str] = Field(min_length=1, max_length=1000)
    expected_sequences: list[int] = Field(min_length=1, max_length=1000)
    resources: list[DiscoveredResource] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def complete_inventory(self):
        parts = [r.part_label for r in self.resources]
        if (
            len(set(self.required_parts)) != len(self.required_parts)
            or len(set(parts)) != len(parts)
            or set(parts) != set(self.required_parts)
            or len({r.resource_id for r in self.resources}) != len(self.resources)
            or len({r.resource_url for r in self.resources}) != len(self.resources)
            or len(set(self.expected_sequences)) != len(self.expected_sequences)
            or any(n < 1 for n in self.expected_sequences)
        ):
            raise ValueError("incomplete or duplicated inventory")
        for resource in self.resources:
            labels = list(resource.member_labels.values())
            if any(not key or not value for key, value in resource.member_labels.items()) or len(
                set(labels)
            ) != len(labels):
                raise ValueError("invalid member labels")
        if self.published_at is not None:
            value = datetime.fromisoformat(self.published_at)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("publisher timestamp must have a timezone")
        return self


class PublisherMapping(Closed):
    """Exact top-level publisher fields, supplied by a reviewed fixture contract.

    Keys are our closed model fields; values are the exact publisher keys. No
    fuzzy lookup, assumed part count, inferred member names or default URLs.
    """

    version: str = Field(min_length=1, max_length=128)
    approval_reference: str = Field(min_length=1, max_length=256)
    fixture_only: Literal[True] = True
    dataset_id: str = Field(min_length=1, max_length=256)
    metadata_url: str = Field(min_length=1, max_length=2048)
    licence_reference: str = Field(min_length=1, max_length=1024)
    allowed_hosts: list[str] = Field(min_length=1, max_length=32)
    publication_fields: dict[str, str]
    resource_fields: dict[str, str]

    @model_validator(mode="after")
    def exact_fields(self):
        for fields, model in (
            (self.publication_fields, DiscoverySnapshot),
            (self.resource_fields, DiscoveredResource),
        ):
            if (
                set(fields) != set(model.model_fields)
                or len(set(fields.values())) != len(fields)
                or any(not value for value in fields.values())
            ):
                raise ValueError("mapping must define every field exactly once")
        self.validate_url(self.metadata_url)
        return self

    def validate_url(self, value: str) -> None:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname not in self.allowed_hosts
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise SourceError("DISCOVERY_URL_UNAPPROVED")

    def decode(self, payload: dict) -> DiscoverySnapshot:
        def project(value, fields):
            if not isinstance(value, dict) or set(value) != set(fields.values()):
                raise SourceError("DISCOVERY_SCHEMA_MISMATCH")
            return {key: value[field] for key, field in fields.items()}

        try:
            decoded = project(payload, self.publication_fields)
            if not isinstance(decoded["resources"], list):
                raise SourceError("DISCOVERY_SCHEMA_MISMATCH")
            decoded["resources"] = [project(row, self.resource_fields) for row in decoded["resources"]]
            snapshot = DiscoverySnapshot.model_validate(decoded)
            if snapshot.dataset_id != self.dataset_id:
                raise SourceError("DISCOVERY_DATASET_MISMATCH")
            for resource in snapshot.resources:
                self.validate_url(resource.resource_url)
            return snapshot
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, SourceError):
                raise
            raise SourceError("DISCOVERY_SCHEMA_MISMATCH") from None


def _encoded(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def discover_publication(
    attempt_dir: Path,
    *,
    contract: PublisherMapping,
    mapping: ABRMapping,
    metadata_reader: Callable,
    transport: Callable,
    production: bool = False,
    max_metadata_bytes: int = 1024 * 1024,
    max_download_bytes: int = 16 * 1024**3,
    max_resource_bytes: int = 8 * 1024**3,
    sleep: Callable = time.sleep,
    jitter: Callable = random.random,
) -> Publication:
    """Discover -> download all parts -> reread -> ingest, or hold atomically.

    ``metadata_reader(url, connect_timeout=10, read_timeout=20, max_bytes=N)``
    returns the publisher JSON object and must enforce the supplied I/O bounds.
    The object is also byte-bounded here. Metadata response validators are
    explicitly unavailable in this reader contract; ZIP headers are not a
    substitute. A live adapter must capture actual metadata response headers.
    The ZIP transport follows
    ``download_resource``'s injected context-manager protocol. Each metadata
    request and each ZIP has at most five attempts; metadata drift holds before
    parsing. A caller restarts with a new exclusive attempt directory. No state
    promotion occurs here, and unapproved live mode always fails before I/O.
    """
    if production:
        raise SourceError("LIVE_DISCOVERY_DISABLED")
    mapping.validate(False)
    if min(max_metadata_bytes, max_download_bytes, max_resource_bytes) <= 0:
        raise SourceError("INVALID_DISCOVERY_LIMIT")
    # Revalidate even a deliberately model_construct'ed instance before I/O.
    contract = PublisherMapping.model_validate(contract.model_dump())
    attempt_dir.mkdir(parents=True, exist_ok=False)

    def read_metadata() -> tuple[DiscoverySnapshot, str, str]:
        for attempt in range(5):
            try:
                raw = metadata_reader(
                    contract.metadata_url, connect_timeout=10, read_timeout=20, max_bytes=max_metadata_bytes
                )
                encoded = _encoded(raw)
                if len(encoded) > max_metadata_bytes:
                    raise SourceError("DISCOVERY_METADATA_SIZE_LIMIT")
                snapshot = contract.decode(raw)
                return snapshot, hashlib.sha256(encoded).hexdigest(), datetime.now(UTC).isoformat()
            except OSError:
                if attempt == 4:
                    raise SourceError("DISCOVERY_ATTEMPTS_EXHAUSTED") from None
                sleep(2**attempt + jitter())
            except (ValueError, TypeError) as exc:
                if isinstance(exc, SourceError):
                    raise
                raise SourceError("DISCOVERY_SCHEMA_MISMATCH") from None
        raise AssertionError("unreachable")

    before, before_digest, retrieved_at = read_metadata()
    if sum(r.declared_size or 0 for r in before.resources) > max_download_bytes:
        raise SourceError("DOWNLOAD_SIZE_LIMIT")
    resources, receipts = [], []
    total_bytes = 0
    for index, resource in enumerate(sorted(before.resources, key=lambda row: row.part_label)):
        observations: dict[str, str | None] = {}

        @contextmanager
        def checked_transport(url, _resource=resource, _observations=observations, **kwargs):
            with transport(url, **kwargs) as response:
                if response.status_code in (200, 206):
                    headers = {key.lower(): value for key, value in response.headers.items()}
                    for field in ("etag", "last_modified"):
                        actual = headers.get(field.replace("_", "-"))
                        expected = getattr(_resource, field)
                        if expected is not None and expected != actual:
                            raise SourceError("DISCOVERY_RESPONSE_VALIDATOR_MISMATCH")
                        _observations[field] = actual
                yield response

        remaining = min(max_resource_bytes, max_download_bytes - total_bytes)
        if remaining <= 0 or (resource.declared_size is not None and resource.declared_size > remaining):
            raise SourceError("DOWNLOAD_SIZE_LIMIT")
        started = datetime.now(UTC).isoformat()
        path = download_resource(
            resource.resource_url,
            attempt_dir / f"resource-{index:04}.zip",
            transport=checked_transport,
            expected_sha256=resource.expected_sha256,
            max_bytes=remaining,
            sleep=sleep,
            jitter=jitter,
        )
        actual_size = path.stat().st_size
        if resource.declared_size is not None and actual_size != resource.declared_size:
            raise SourceError("DOWNLOAD_LENGTH_MISMATCH")
        total_bytes += actual_size
        resources.append(
            ArchiveResource(
                resource.resource_id,
                resource.part_label,
                path,
                resource.member_labels,
                resource.resource_url,
                observations.get("etag"),
                observations.get("last_modified"),
                actual_size,
            )
        )
        receipts.append(
            {
                "resource_id": resource.resource_id,
                "retrieved_at": started,
                "completed_at": datetime.now(UTC).isoformat(),
                "download_sha256": digest_file(path),
                "size_bytes": actual_size,
                "response_validators": dict(observations),
            }
        )
    after, after_digest, reread_at = read_metadata()
    # Raw metadata order/extra changes conservatively hold as schema/generation
    # drift; no cached bytes can be silently relabelled as a fresh occurrence.
    if before_digest != after_digest:
        raise SourceError("INVENTORY_CHANGED_DURING_DOWNLOAD")
    inventory = [resource.model_dump() for resource in before.resources]
    publication = ingest_archives(
        resources,
        attempt_dir / "parsed",
        mapping=mapping,
        inventory_before=inventory,
        inventory_after=[resource.model_dump() for resource in after.resources],
        required_parts=set(before.required_parts),
        expected_sequences=set(before.expected_sequences),
    )
    if publication.manifest["generation"] != before.generation:
        raise SourceError("DISCOVERY_INNER_GENERATION_MISMATCH")
    manifest = {
        **publication.manifest,
        "discovery": {
            "fixture_only": True,
            "dataset_id": contract.dataset_id,
            "metadata_url": contract.metadata_url,
            "licence_reference": contract.licence_reference,
            "contract_version": contract.version,
            "approval_reference": contract.approval_reference,
            "contract_sha256": hashlib.sha256(_encoded(contract.model_dump())).hexdigest(),
            "retrieved_at": retrieved_at,
            "reread_at": reread_at,
            "published_at": before.published_at,
            "metadata_before_sha256": before_digest,
            "metadata_after_sha256": after_digest,
            "metadata_response_validators": {
                "status": "unavailable",
                "etag": None,
                "last_modified": None,
            },
            "inventory": inventory,
            "downloads": receipts,
        },
    }
    with (attempt_dir / "publication.json").open("xb") as output:
        output.write(_encoded(manifest))
    return replace(publication, manifest=manifest)
