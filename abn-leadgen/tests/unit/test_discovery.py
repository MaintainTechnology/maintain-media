"""Real ZIP/parser composition with injected publisher metadata and HTTP faults."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError

from abr_engine.ingest.abr_parse import ABRMapping
from abr_engine.ingest.common import SourceError
from abr_engine.ingest.discovery import (
    DiscoveredResource,
    DiscoverySnapshot,
    PublisherMapping,
    discover_publication,
)


class Response:
    def __init__(self, status, headers, blocks):
        self.status_code, self.headers, self.blocks = status, headers, blocks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        for block in self.blocks:
            if isinstance(block, Exception):
                raise block
            yield block


@pytest.fixture
def source():
    contract = PublisherMapping(
        version="synthetic-publisher-v1",
        approval_reference="fixture-contract-review",
        dataset_id="synthetic-only",
        metadata_url="https://source.invalid/metadata.json",
        licence_reference="fixture-generated-no-live-source",
        allowed_hosts=["source.invalid"],
        publication_fields={key: "publisher_" + key for key in DiscoverySnapshot.model_fields},
        resource_fields={key: "zip_" + key for key in DiscoveredResource.model_fields},
    )
    root = ET.fromstring((Path(__file__).parents[1] / "fixtures/abr/abr_baseline.xml").read_bytes())
    rows = root.findall("ABR")
    binaries, resources = {}, []
    for index, records in enumerate((rows[:2], rows[2:]), 1):
        part = deepcopy(root)
        for row in part.findall("ABR"):
            part.remove(row)
        part.extend(deepcopy(records))
        part.find("TransferInfo/RecordCount").text = str(len(records))
        part.find("TransferInfo/FileSequenceNumber").text = str(index)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"member-{index}.xml", ET.tostring(part))
        url = f"https://source.invalid/part-{index}.zip"
        binaries[url] = buffer.getvalue()
        resources.append(
            {
                "resource_id": f"resource-{index}",
                "part_label": f"part-{index}",
                "resource_url": url,
                "member_labels": {f"member-{index}.xml": f"member-{index}"},
                "etag": f'"part-{index}"',
                "last_modified": None,
                "declared_size": len(binaries[url]),
                "expected_sha256": hashlib.sha256(binaries[url]).hexdigest(),
            }
        )
    metadata = {
        "dataset_id": "synthetic-only",
        "generation": "fixture-1",
        "published_at": None,
        "required_parts": ["part-1", "part-2"],
        "expected_sequences": [1, 2],
        "resources": [{contract.resource_fields[k]: v for k, v in r.items()} for r in resources],
    }
    return contract, {contract.publication_fields[k]: v for k, v in metadata.items()}, binaries


def execute(tmp_path, source, *, metadata_reader=None, transport=None, name="attempt", **kwargs):
    contract, metadata, binaries = source

    def default_transport(url, **options):
        index = url.split("part-")[1].split(".")[0]
        return Response(
            200, {"ETag": f'"part-{index}"', "Content-Length": str(len(binaries[url]))}, [binaries[url]]
        )

    return discover_publication(
        tmp_path / name,
        contract=contract,
        mapping=ABRMapping.fixture(),
        metadata_reader=metadata_reader or (lambda *a, **kw: metadata),
        transport=transport or default_transport,
        sleep=lambda _: None,
        jitter=lambda: 0,
        **kwargs,
    )


def test_all_parts_download_resume_reread_and_real_parser_manifest(tmp_path, source):
    _, metadata, binaries = source
    calls, reads = [], []

    def read(url, **options):
        reads.append((url, options))
        return deepcopy(metadata)

    def transport(url, **options):
        calls.append((url, options))
        body = binaries[url]
        etag = '"part-1"' if "part-1" in url else '"part-2"'
        headers = {"ETag": etag, "Content-Length": str(len(body))}
        if len(calls) == 1:
            return Response(200, headers, [body[:100], TimeoutError("synthetic interrupted")])
        if "Range" in options["headers"]:
            return Response(
                206, {"ETag": etag, "Content-Range": f"bytes 100-{len(body) - 1}/{len(body)}"}, [body[100:]]
            )
        return Response(200, headers, [body])

    result = execute(tmp_path, source, metadata_reader=read, transport=transport)
    assert sum(member.row_count for member in result.members) == 3
    assert len(reads) == 2 and len(calls) == 3
    assert calls[1][1]["headers"]["If-Range"] == '"part-1"'
    assert calls[1][1]["headers"]["Range"] == "bytes=100-"
    assert all(options["connect_timeout"] == 10 and options["read_timeout"] == 20 for _, options in reads)
    saved = json.loads((tmp_path / "attempt/publication.json").read_text())
    assert saved == result.manifest
    evidence = saved["discovery"]
    assert evidence["published_at"] is None  # never manufacture a publisher timestamp
    assert evidence["metadata_response_validators"] == {
        "status": "unavailable",
        "etag": None,
        "last_modified": None,
    }
    assert evidence["metadata_before_sha256"] == evidence["metadata_after_sha256"]
    assert len(evidence["inventory"]) == len(evidence["downloads"]) == 2
    for index, receipt in enumerate(evidence["downloads"]):
        assert (
            receipt["download_sha256"]
            == hashlib.sha256((tmp_path / f"attempt/resource-{index:04}.zip").read_bytes()).hexdigest()
        )
    with pytest.raises(FileExistsError):
        execute(tmp_path, source)


@pytest.mark.parametrize("change", ["generation", "url", "members", "etag", "published_at"])
def test_metadata_drift_holds_before_parse_then_fresh_attempt_recovers(tmp_path, source, change):
    _, metadata, _ = source
    after = deepcopy(metadata)
    if change == "generation":
        after["publisher_generation"] = "other"
    elif change == "published_at":
        after["publisher_published_at"] = "2026-09-08T00:00:00Z"
    else:
        key, value = {
            "url": ("zip_resource_url", "https://source.invalid/replaced.zip"),
            "members": ("zip_member_labels", {"replacement.xml": "member-1"}),
            "etag": ("zip_etag", '"replacement"'),
        }[change]
        after["publisher_resources"][0][key] = value
    reads = iter([metadata, after])
    with pytest.raises(SourceError, match="INVENTORY_CHANGED_DURING_DOWNLOAD"):
        execute(tmp_path, source, metadata_reader=lambda *a, **kw: next(reads))
    assert not (tmp_path / "attempt/parsed").exists()
    assert not (tmp_path / "attempt/publication.json").exists()
    assert execute(tmp_path, source, name="fresh").manifest["coherence"] == "validated"


@pytest.mark.parametrize("change", ["missing", "duplicate", "bad_host", "schema", "dataset"])
def test_invalid_inventory_never_downloads(tmp_path, source, change):
    contract, metadata, binaries = source
    metadata = deepcopy(metadata)
    resources = metadata["publisher_resources"]
    if change == "missing":
        resources.pop()
    elif change == "duplicate":
        resources[1]["zip_resource_id"] = resources[0]["zip_resource_id"]
    elif change == "bad_host":
        resources[0]["zip_resource_url"] = "https://unapproved.invalid/part.zip"
    elif change == "schema":
        metadata["surprise"] = True
    else:
        metadata["publisher_dataset_id"] = "different-dataset"
    calls = []
    with pytest.raises(SourceError):
        execute(tmp_path, (contract, metadata, binaries), transport=lambda *a, **kw: calls.append(a))
    assert calls == []


def test_response_metadata_binding_and_aggregate_limit(tmp_path, source):
    calls = []

    def wrong(url, **kwargs):
        calls.append(url)
        return Response(200, {"ETag": '"different"'}, [b"not trusted"])

    with pytest.raises(SourceError, match="DISCOVERY_RESPONSE_VALIDATOR_MISMATCH"):
        execute(tmp_path, source, transport=wrong)
    assert len(calls) == 1 and not (tmp_path / "attempt/publication.json").exists()
    calls.clear()
    with pytest.raises(SourceError, match="DOWNLOAD_SIZE_LIMIT"):
        execute(tmp_path, source, name="bounded", transport=wrong, max_download_bytes=10)
    assert calls == []


def test_digest_and_inner_generation_cannot_be_faked_by_metadata(tmp_path, source):
    contract, metadata, binaries = source
    bad = deepcopy(metadata)
    bad["publisher_resources"][0]["zip_expected_sha256"] = "0" * 64
    with pytest.raises(SourceError, match="DOWNLOAD_DIGEST_MISMATCH"):
        execute(tmp_path, (contract, bad, binaries), name="hash")
    bad = deepcopy(metadata)
    bad["publisher_generation"] = "different-inner-generation"
    with pytest.raises(SourceError, match="DISCOVERY_INNER_GENERATION_MISMATCH"):
        execute(tmp_path, (contract, bad, binaries), name="inner")
    assert not (tmp_path / "inner/publication.json").exists()


def test_bounded_metadata_retry_and_no_live_or_schema_bypass(tmp_path, source):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise TimeoutError()

    with pytest.raises(SourceError, match="DISCOVERY_ATTEMPTS_EXHAUSTED"):
        execute(tmp_path, source, metadata_reader=unavailable)
    assert len(calls) == 5
    with pytest.raises(SourceError, match="LIVE_DISCOVERY_DISABLED"):
        execute(tmp_path, source, name="live", metadata_reader=unavailable, production=True)
    assert len(calls) == 5 and not (tmp_path / "live").exists()
    contract, _, _ = source
    data = contract.model_dump()
    data["resource_fields"].pop("expected_sha256")
    with pytest.raises(ValidationError):
        PublisherMapping.model_validate(data)


def test_source_labels_never_control_local_paths(tmp_path, source):
    contract, metadata, binaries = source
    metadata = deepcopy(metadata)
    metadata["publisher_resources"][0]["zip_resource_id"] = "../../outside"
    execute(tmp_path, (contract, metadata, binaries))
    assert sorted(path.name for path in (tmp_path / "attempt").glob("*.zip")) == [
        "resource-0000.zip",
        "resource-0001.zip",
    ]
    assert not (tmp_path / "outside").exists()


def test_unknown_lengths_still_share_actual_download_byte_cap(tmp_path, source):
    contract, metadata, binaries = source
    metadata = deepcopy(metadata)
    for resource in metadata["publisher_resources"]:
        resource["zip_declared_size"] = None
    total = sum(len(value) for value in binaries.values())
    with pytest.raises(SourceError, match="DOWNLOAD_SIZE_LIMIT"):
        execute(tmp_path, (contract, metadata, binaries), max_download_bytes=total - 1)
    assert (tmp_path / "attempt/resource-0000.zip").exists()
    assert not (tmp_path / "attempt/resource-0001.zip").exists()
    assert not (tmp_path / "attempt/parsed").exists()
    assert not (tmp_path / "attempt/publication.json").exists()


def test_download_exhaustion_never_parses_or_rereads_metadata(tmp_path, source):
    calls, reads = [], []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise TimeoutError()

    def read(*args, **kwargs):
        reads.append(1)
        return source[1]

    with pytest.raises(SourceError, match="DOWNLOAD_ATTEMPTS_EXHAUSTED"):
        execute(tmp_path, source, metadata_reader=read, transport=unavailable)
    assert len(calls) == 5 and len(reads) == 1
    assert not (tmp_path / "attempt/parsed").exists()
    assert not (tmp_path / "attempt/publication.json").exists()
