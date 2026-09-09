"""Bounded official catalogue inspection. Never downloads business register rows."""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from abr_engine.ingest.common import SourceError


@dataclass(frozen=True)
class Catalogue:
    endpoint: str
    dataset_id: str
    resource_format: str
    licence_ids: frozenset[str]


CATALOGUES = {
    "qbcc": Catalogue(
        "https://www.data.qld.gov.au/api/3/action/package_show?id=qbcc-licensed-contractors-register",
        "980b6499-c0b4-491b-ba9c-1c7506368a50", "CSV", frozenset({"CC-BY-4.0"}),
    ),
    "abr": Catalogue(
        "https://data.gov.au/data/api/3/action/package_show?id=abn-bulk-extract",
        "5bd7fcab-e315-42cb-8daf-50b7efc2027e", "ZIP", frozenset({"cc-by", "cc-by-3.0-au"}),
    ),
}
MAX_METADATA_BYTES = 2 * 1024 * 1024


def _text(value, *, maximum=2048):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise SourceError("CATALOGUE_INVALID_FIELD")
    return value


def _public_url(value):
    value = _text(value)
    if not value:
        raise SourceError("CATALOGUE_RESOURCE_URL_MISSING")
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.port not in (None, 443) or url.fragment):
            raise ValueError()
    except ValueError:
        raise SourceError("CATALOGUE_RESOURCE_URL_INVALID") from None
    return value


def decode_catalogue(source: str, payload: dict, *, retrieved_at: datetime, metadata_digest: str,
                     response_validators: dict | None = None) -> dict:
    """Project public metadata only; row payloads and maintainer details are excluded."""
    catalogue = CATALOGUES[source]
    dataset = payload.get("result")
    if (payload.get("success") is not True or not isinstance(dataset, dict)
            or dataset.get("id") != catalogue.dataset_id or not isinstance(dataset.get("resources"), list)):
        raise SourceError("CATALOGUE_DATASET_MISMATCH")
    resources = []
    for resource in dataset["resources"]:
        if not isinstance(resource, dict):
            raise SourceError("CATALOGUE_RESOURCE_INVALID")
        if str(resource.get("format", "")).upper() != catalogue.resource_format:
            continue
        resource_id = _text(resource.get("id"), maximum=128)
        if not resource_id:
            raise SourceError("CATALOGUE_RESOURCE_ID_MISSING")
        size = resource.get("size")
        size_label = None
        # CKAN may represent unavailable size as null/empty or a decimal string.
        if size in (None, ""):
            size = None
        elif isinstance(size, str) and size.isdecimal():
            if len(size) > 19 or not size.isascii():
                raise SourceError("CATALOGUE_RESOURCE_SIZE_INVALID")
            size = int(size)
        elif isinstance(size, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)? (?:KiB|MiB|GiB|kB|MB|GB)", size):
            # A rounded human-readable label is not an exact Content-Length.
            size_label, size = size, None
        if size is not None and (type(size) is not int or not 0 <= size <= 2 ** 63 - 1):
            raise SourceError("CATALOGUE_RESOURCE_SIZE_INVALID")
        resources.append({
            "resource_id": resource_id, "url": _public_url(resource.get("url")),
            "format": catalogue.resource_format, "declared_size": size,
            "publisher_size_label": size_label,
            "publisher_last_modified": _text(resource.get("last_modified")),
            "publisher_created": _text(resource.get("created")),
            "publisher_hash": _text(resource.get("hash")),
        })
    if not resources or len(resources) > 64 or len({r["resource_id"] for r in resources}) != len(resources):
        raise SourceError("CATALOGUE_INVENTORY_INVALID")
    licence_id = _text(dataset.get("license_id"), maximum=128)
    if licence_id not in catalogue.licence_ids:
        raise SourceError("CATALOGUE_LICENCE_REVIEW_REQUIRED")
    resources.sort(key=lambda r: r["resource_id"])
    encoded = json.dumps(resources, sort_keys=True, separators=(",", ":")).encode()
    return {
        "status": "metadata_observed", "source": source, "dataset_id": catalogue.dataset_id,
        "catalogue_url": catalogue.endpoint, "retrieved_at": retrieved_at.isoformat(),
        "metadata_sha256": metadata_digest,
        "response_validators": response_validators or {"etag": None, "last_modified": None},
        "licence": {"id": licence_id, "title": _text(dataset.get("license_title")),
                    "url": _text(dataset.get("license_url"))},
        "publisher_metadata_modified": _text(dataset.get("metadata_modified")),
        "resource_inventory_sha256": hashlib.sha256(encoded).hexdigest(), "resources": resources,
        "register_rows_downloaded": 0, "coherence": "not_established",
        "collection_approved": False, "business_data_accepted": False,
        "limitations": ["Catalogue timestamps are publisher metadata, not a coherent publication proof.",
                        "This command does not download, classify, promote or export business records."],
    }


def inspect_catalogue(source: str, *, transport: httpx.BaseTransport | None = None,
                      sleep=time.sleep, clock=time.monotonic) -> dict:
    if source not in CATALOGUES:
        raise SourceError("CATALOGUE_SOURCE_INVALID")
    started = clock()
    with httpx.Client(transport=transport, follow_redirects=False, trust_env=False,
                      timeout=httpx.Timeout(10, connect=5),
                      headers={"Accept": "application/json", "User-Agent": "MaintainMedia-SourceCheck/1.0"}) as client:
        for attempt in range(5):
            try:
                with client.stream("GET", CATALOGUES[source].endpoint) as response:
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise httpx.TransportError("retryable catalogue response")
                    if response.status_code != 200:
                        raise SourceError("CATALOGUE_HTTP_REJECTED")
                    declared = response.headers.get("content-length")
                    if declared and (len(declared) > 12 or not declared.isascii()
                                     or not declared.isdecimal() or int(declared) > MAX_METADATA_BYTES):
                        raise SourceError("CATALOGUE_SIZE_LIMIT")
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_METADATA_BYTES:
                            raise SourceError("CATALOGUE_SIZE_LIMIT")
                        if clock() - started > 60:
                            raise SourceError("CATALOGUE_DEADLINE")
                    try:
                        payload = json.loads(chunks)
                    except (ValueError, UnicodeError, RecursionError):
                        raise SourceError("CATALOGUE_INVALID_JSON") from None
                    if not isinstance(payload, dict):
                        raise SourceError("CATALOGUE_INVALID_JSON")
                    return decode_catalogue(
                        source, payload, retrieved_at=datetime.now(UTC),
                        metadata_digest=hashlib.sha256(chunks).hexdigest(),
                        response_validators={"etag": _text(response.headers.get("etag")),
                                             "last_modified": _text(response.headers.get("last-modified"))},
                    )
            except httpx.HTTPError:
                if attempt == 4 or clock() - started > 50:
                    raise SourceError("CATALOGUE_UNAVAILABLE") from None
                sleep(min(2, 0.25 * 2 ** attempt) + random.uniform(0, 0.1))
    raise SourceError("CATALOGUE_UNAVAILABLE")
