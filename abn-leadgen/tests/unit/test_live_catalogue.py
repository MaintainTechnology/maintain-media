import json
from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest
from typer.testing import CliRunner

from abr_engine.cli import app
from abr_engine.ingest.catalogue import CATALOGUES, decode_catalogue, inspect_catalogue
from abr_engine.ingest.common import SourceError


def payload(source="qbcc"):
    return {"success": True, "result": {
        "id": CATALOGUES[source].dataset_id, "license_id": "CC-BY-4.0" if source == "qbcc" else "cc-by",
        "license_title": "Creative Commons Attribution", "resources": [
            {"id": "published-resource", "format": CATALOGUES[source].resource_format,
             "url": "https://www.data.qld.gov.au/dataset/source/download.csv",
             "size": "1024", "last_modified": "2026-05-18T05:14:43"},
            {"id": "readme", "format": "PDF", "url": "https://example.invalid/never-follow"}],
        "maintainer_email": "never-return@example.invalid", "records": [{"business": "never-return"}],
    }}


@pytest.mark.parametrize("source", ["qbcc", "abr"])
def test_inspection_observes_metadata_without_downloading_row_resources(source):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=payload(source), headers={"etag": '"metadata-v1"'})
    observed = inspect_catalogue(source, transport=httpx.MockTransport(respond))
    assert calls == [CATALOGUES[source].endpoint]
    assert observed["resources"][0]["declared_size"] == 1024
    assert observed["register_rows_downloaded"] == 0
    assert observed["business_data_accepted"] is False
    assert observed["coherence"] == "not_established"
    assert len(observed["metadata_sha256"]) == 64
    assert "never-return" not in json.dumps(observed)


def test_transient_metadata_requests_retry_but_auth_errors_and_redirects_do_not():
    attempts = []
    def respond(request):
        attempts.append(request.url)
        return httpx.Response(503 if len(attempts) < 3 else 200, json=payload())
    inspect_catalogue("qbcc", transport=httpx.MockTransport(respond), sleep=lambda _: None)
    assert len(attempts) == 3
    for status in (302, 401, 403):
        attempts.clear()
        def reject(request, status=status):
            attempts.append(request.url)
            return httpx.Response(status, headers={"location": "https://example.invalid"})
        with pytest.raises(SourceError, match="CATALOGUE_HTTP_REJECTED"):
            inspect_catalogue("qbcc", transport=httpx.MockTransport(reject))
        assert len(attempts) == 1


def test_timeouts_stop_at_five_attempts_and_never_leak_provider_error():
    attempts = []
    def fail(request):
        attempts.append(request.url)
        raise httpx.ReadTimeout("do-not-expose-credentials")
    with pytest.raises(SourceError, match="^CATALOGUE_UNAVAILABLE$"):
        inspect_catalogue("abr", transport=httpx.MockTransport(fail), sleep=lambda _: None)
    assert len(attempts) == 5


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["result"].update(id="wrong"), "DATASET_MISMATCH"),
    (lambda p: p["result"].update(license_id="unreviewed"), "LICENCE_REVIEW_REQUIRED"),
    (lambda p: p["result"].update(resources=[]), "INVENTORY_INVALID"),
    (lambda p: p["result"]["resources"].append(deepcopy(p["result"]["resources"][0])), "INVENTORY_INVALID"),
    (lambda p: p["result"]["resources"][0].update(size=-1), "RESOURCE_SIZE_INVALID"),
    (lambda p: p["result"]["resources"][0].update(size="9" * 5000), "RESOURCE_SIZE_INVALID"),
    (lambda p: p["result"]["resources"][0].update(size=2 ** 64), "RESOURCE_SIZE_INVALID"),
    (lambda p: p["result"]["resources"][0].update(url="https://user:secret@example.invalid/"), "RESOURCE_URL_INVALID"),
])
def test_unknown_or_unsafe_publisher_data_is_held(mutation, code):
    data = payload()
    mutation(data)
    with pytest.raises(SourceError, match=code):
        decode_catalogue("qbcc", data, retrieved_at=datetime.now(UTC), metadata_digest="a" * 64)


def test_response_size_and_json_shape_are_bounded():
    for response, code in [
        (httpx.Response(200, headers={"content-length": "99999999"}), "SIZE_LIMIT"),
        (httpx.Response(200, headers={"content-length": "9" * 5000}), "SIZE_LIMIT"),
        (httpx.Response(200, json=[]), "INVALID_JSON"),
        (httpx.Response(200, content=b"{"), "INVALID_JSON"),
        (httpx.Response(200, content=b"[" * 10000 + b"]" * 10000), "INVALID_JSON"),
    ]:
        with pytest.raises(SourceError, match=code):
            inspect_catalogue("abr", transport=httpx.MockTransport(lambda _, response=response: response))


def test_human_readable_size_is_preserved_without_inventing_an_exact_byte_length():
    data = payload()
    data["result"]["resources"][0]["size"] = "72.6 MiB"
    observed = decode_catalogue("qbcc", data, retrieved_at=datetime.now(UTC), metadata_digest="a" * 64)
    resource = observed["resources"][0]
    assert resource["declared_size"] is None
    assert resource["publisher_size_label"] == "72.6 MiB"


def test_cli_failure_is_actionable_and_redacted(monkeypatch):
    def fail(source):
        raise SourceError("CATALOGUE_UNAVAILABLE")
    monkeypatch.setattr("abr_engine.ingest.catalogue.inspect_catalogue", fail)
    result = CliRunner().invoke(app, ["sources", "inspect", "--source", "qbcc"])
    assert result.exit_code == 3
    assert json.loads(result.stdout)["register_rows_downloaded"] == 0
