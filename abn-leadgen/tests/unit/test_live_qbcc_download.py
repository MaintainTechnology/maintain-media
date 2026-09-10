"""Bounded publisher transfer cannot follow redirects or accept incomplete bytes."""

import httpx
import pytest

from abr_engine.ingest.common import SourceError
from abr_engine.ingest.qbcc_review import SOURCE_URL
from abr_engine.live import runtime


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
