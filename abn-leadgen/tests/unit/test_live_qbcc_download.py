"""Only the publisher's exact single attachment redirect is permitted."""

import hashlib

import httpx
import pytest

from abr_engine.ingest.common import SourceError
from abr_engine.ingest.qbcc_review import SOURCE_URL
from abr_engine.live import runtime

ATTACHMENT = runtime.ATTACHMENT_URL + "?ETag=" + "a1" * 16


def test_single_publisher_redirect_preserves_bytes_hash_and_provenance(tmp_path):
    calls, checks = [], []
    content = "\ufeffLicence Number,Licensee Name\r\n123,Synthetic\r\n".encode("utf-16-le")

    def respond(request):
        calls.append(str(request.url))
        assert len(checks) == len(calls)
        assert request.headers["accept"] == "text/csv"
        assert request.headers["accept-encoding"] == "identity"
        assert "authorization" not in request.headers
        if str(request.url) == SOURCE_URL:
            return httpx.Response(302, headers={"location": ATTACHMENT})
        assert str(request.url) == ATTACHMENT
        return httpx.Response(
            200, headers={"content-length": str(len(content)), "etag": '"publisher-validator"'},
            stream=httpx.ByteStream(content),
        )

    path = tmp_path / "owned.csv"
    receipt = runtime.download_qbcc(
        path, transport=httpx.MockTransport(respond), authority=lambda: checks.append("current")
    )
    assert calls == [SOURCE_URL, ATTACHMENT] and path.read_bytes() == content
    assert receipt["source_sha256"] == hashlib.sha256(content).hexdigest()
    assert receipt["byte_count"] == len(content) and receipt["attempts"] == 1
    assert receipt["source_url"] == SOURCE_URL and receipt["response_url"] == ATTACHMENT
    assert receipt["redirect_count"] == 1 and receipt["etag"] == '"publisher-validator"'


@pytest.mark.parametrize("target", [
    ATTACHMENT.replace("https:", "http:"),
    ATTACHMENT.replace("www.data.qld.gov.au", "evil.example"),
    ATTACHMENT.replace("www.data.qld.gov.au", "www.data.qld.gov.au.evil.example"),
    ATTACHMENT.replace("www.data.qld.gov.au", "user@www.data.qld.gov.au"),
    ATTACHMENT.replace("www.data.qld.gov.au", "www.data.qld.gov.au:443"),
    ATTACHMENT.replace(runtime.RESOURCE_ID, "00000000-0000-0000-0000-000000000000"),
    ATTACHMENT.replace("/resources/", "/resources/../resources/"),
    ATTACHMENT.replace("builder-contractor", "%62uilder-contractor"),
    ATTACHMENT + "#fragment",
    ATTACHMENT + "&token=extra",
    ATTACHMENT + "&ETag=" + "b" * 32,
    ATTACHMENT + " ",
    ATTACHMENT.replace("?ETag=", "?etag="),
    runtime.ATTACHMENT_URL,
    runtime.ATTACHMENT_URL + "?ETag=not-a-validator",
    runtime.ATTACHMENT_URL + "?ETag=" + "a" * 31,
    runtime.ATTACHMENT_URL + "?ETag=" + "a" * 33,
    runtime.ATTACHMENT_URL + "?ETag=%61" + "a" * 31,
    ATTACHMENT.removeprefix("https://www.data.qld.gov.au"),
])
def test_nonexact_redirect_never_issues_second_http(tmp_path, target):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": target})

    with pytest.raises(SourceError, match="QBCC_SOURCE_REDIRECT_REJECTED"):
        runtime.download_qbcc(tmp_path / "owned.csv", transport=httpx.MockTransport(respond))
    assert calls == [SOURCE_URL] and not (tmp_path / "owned.csv").exists()


@pytest.mark.parametrize("locations", [[], [("location", ATTACHMENT), ("location", ATTACHMENT)]])
def test_missing_or_multiple_location_headers_rejected(tmp_path, locations):
    with pytest.raises(SourceError, match="QBCC_SOURCE_REDIRECT_REJECTED"):
        runtime.download_qbcc(
            tmp_path / "owned.csv",
            transport=httpx.MockTransport(lambda _: httpx.Response(302, headers=locations)),
        )


def test_http_client_rejects_control_character_redirect_before_attachment(tmp_path):
    # httpx validates Location before yielding even with follow_redirects=False.
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": ATTACHMENT + "\n"})

    with pytest.raises(SourceError, match="QBCC_SOURCE_HTTP_REJECTED"):
        runtime.download_qbcc(
            tmp_path / "owned.csv", transport=httpx.MockTransport(respond), sleep=lambda _: None
        )
    assert calls == [SOURCE_URL] and not (tmp_path / "owned.csv").exists()


def test_second_redirect_is_never_followed(tmp_path):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": ATTACHMENT})

    with pytest.raises(SourceError, match="QBCC_SOURCE_HTTP_REJECTED"):
        runtime.download_qbcc(tmp_path / "owned.csv", transport=httpx.MockTransport(respond))
    assert calls == [SOURCE_URL, ATTACHMENT] and not (tmp_path / "owned.csv").exists()


def test_withdrawal_prevents_second_request_and_file_creation(tmp_path):
    calls = []

    def authority():
        if calls:
            raise SourceError("GATE_G1_CLOSED")

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": ATTACHMENT})

    with pytest.raises(SourceError, match="GATE_G1_CLOSED"):
        runtime.download_qbcc(
            tmp_path / "owned.csv", transport=httpx.MockTransport(respond), authority=authority
        )
    assert calls == [SOURCE_URL] and not (tmp_path / "owned.csv").exists()


def test_attachment_retry_restarts_publisher_and_rechecks_each_request(tmp_path):
    calls, checks = [], []

    def respond(request):
        calls.append(str(request.url))
        assert len(checks) == len(calls)
        if str(request.url) == SOURCE_URL:
            return httpx.Response(302, headers={"location": ATTACHMENT})
        return httpx.Response(503 if len(calls) == 2 else 200, stream=httpx.ByteStream(b"ok"))

    receipt = runtime.download_qbcc(
        tmp_path / "owned.csv", transport=httpx.MockTransport(respond),
        authority=lambda: checks.append("current"), sleep=lambda _: None,
    )
    assert calls == [SOURCE_URL, ATTACHMENT, SOURCE_URL, ATTACHMENT]
    assert receipt["attempts"] == 2 and (tmp_path / "owned.csv").read_bytes() == b"ok"


def test_five_total_retry_attempts_and_fixed_https_target(tmp_path):
    calls = []

    def failure(request):
        calls.append(str(request.url))
        return httpx.Response(503)

    with pytest.raises(SourceError, match="QBCC_SOURCE_UNAVAILABLE"):
        runtime.download_qbcc(
            tmp_path / "owned.csv", transport=httpx.MockTransport(failure), sleep=lambda _: None
        )
    assert calls == [SOURCE_URL] * 5


@pytest.mark.parametrize("failure", ["redirect", "size", "length", "encoding"])
def test_transfer_rejects_bad_or_ambiguous_source(tmp_path, monkeypatch, failure):
    def response(request):
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/"})
        if failure == "size":
            return httpx.Response(200, headers={"content-length": "100"}, stream=httpx.ByteStream(b"x"))
        if failure == "encoding":
            return httpx.Response(200, headers={"content-encoding": "gzip"})
        return httpx.Response(200, headers={"content-length": "3"}, stream=httpx.ByteStream(b"a"))

    monkeypatch.setattr(runtime, "MAX_FILE_BYTES", 10)
    with pytest.raises(SourceError):
        runtime.download_qbcc(tmp_path / "owned.csv", transport=httpx.MockTransport(response))


def test_stream_bound_without_declared_length(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "MAX_FILE_BYTES", 2)
    with pytest.raises(SourceError, match="SOURCE_SIZE_LIMIT"):
        runtime.download_qbcc(
            tmp_path / "owned.csv",
            transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=httpx.ByteStream(b"abc"))),
        )
