"""Full permitted publisher transport composition; no external sockets or real rows."""

# ruff: noqa: F811 -- imported pytest fixture is intentionally injected by name.
from uuid import uuid4

import httpx
import pytest
from test_qbcc_review_stage import live as source_live  # noqa: F401

from abr_engine.control.service import DomainError
from abr_engine.db import transaction
from abr_engine.ingest.catalogue import CATALOGUES
from abr_engine.ingest.qbcc_review import SOURCE_URL
from abr_engine.live import qbcc, runtime


@pytest.fixture
def prepared(settings, source_live, monkeypatch):
    config, request, keys = source_live
    for module in (qbcc, runtime):
        monkeypatch.setattr(module, "transaction", lambda ignored: transaction(settings))
        original_lock = module._session_lock
        monkeypatch.setattr(
            module, "_session_lock", lambda ignored, key, original=original_lock: original(settings, key)
        )
    content = request.input_path.read_bytes()
    calls = []
    payload = {
        "success": True,
        "result": {
            "id": CATALOGUES["qbcc"].dataset_id,
            "license_id": "CC-BY-4.0",
            "license_title": "Creative Commons Attribution 4.0",
            "resources": [
                {
                    "id": runtime.RESOURCE_ID,
                    "url": SOURCE_URL,
                    "format": "CSV",
                    "size": len(content),
                    "last_modified": "2026-08-01T00:00:00Z",
                }
            ],
        },
    }

    def respond(request):
        calls.append(str(request.url))
        if str(request.url) == CATALOGUES["qbcc"].endpoint:
            return httpx.Response(200, json=payload)
        assert str(request.url) == SOURCE_URL
        return httpx.Response(
            200,
            headers={"content-length": str(len(content)), "etag": '"synthetic-v1"'},
            stream=httpx.ByteStream(content),
        )

    adapter = runtime.QBCCRuntime(config, transport=httpx.MockTransport(respond), sleep=lambda ignored: None)
    return adapter, calls, payload, content, keys


def test_complete_real_composition_from_http_to_unknown_review_list(settings, prepared):
    adapter, calls, _, _, keys = prepared
    request = {"source": "qbcc", "request_id": str(uuid4())}
    job = adapter.submit_run(request, "synthetic-reviewer")
    assert job["state"] == "queued" and calls == []
    done = adapter.execute_job(job["job_id"])
    assert done["state"] == "complete" and done["result"]["accepted"]
    assert done["result"]["candidates"] == 0 and done["result"]["events"] == 1
    assert len(calls) == 3
    assert adapter.submit_run(request, "synthetic-reviewer")["state"] == "complete"
    assert adapter.execute_job(job["job_id"])["state"] == "complete" and len(calls) == 3
    from abr_engine.control.service import Service

    with transaction(settings) as conn:
        rows = qbcc.list_qbcc_reviews(conn, Service(adapter.settings, keys))
        assert rows["total"] == 1 and rows["rows"][0]["publisher_status"] == "UNKNOWN"


@pytest.mark.parametrize("gate", ["G1", "G2", "G3", "G7", "capability"])
def test_no_http_or_key_loading_when_job_admission_is_closed(settings, prepared, monkeypatch, gate):
    adapter, calls, _, _, _ = prepared
    if gate == "capability":
        adapter.settings = adapter.settings.model_copy(update={"capabilities": {}})
    else:
        with transaction(settings) as conn:
            conn.execute("DELETE FROM release_gate WHERE gate_name=%s", (gate,))

    def forbidden(*args, **kwargs):
        raise AssertionError("key or HTTP before approval")

    monkeypatch.setattr(runtime, "load_keys", forbidden)
    job = adapter.submit_run({"request_id": str(uuid4())}, "synthetic-reviewer")
    assert job["state"] == "held" and job["reason_codes"]
    assert adapter.execute_job(job["job_id"])["state"] == "held" and calls == []


def test_revoked_gate_after_admission_prevents_collection(settings, prepared):
    adapter, calls, _, _, _ = prepared
    job = adapter.submit_run({}, "synthetic-reviewer")
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE gate_name='G1'")
    assert adapter.execute_job(job["job_id"])["reason_codes"] == ["GATE_G1_CLOSED"]
    assert calls == []


def test_metadata_change_after_download_never_moves_cursor(settings, prepared):
    adapter, calls, payload, content, _ = prepared

    def changed(request):
        calls.append(str(request.url))
        if str(request.url) == SOURCE_URL:
            payload["result"]["resources"][0]["last_modified"] = "2026-08-02T00:00:00Z"
            return httpx.Response(200, stream=httpx.ByteStream(content))
        return httpx.Response(200, json=payload)

    adapter.transport = httpx.MockTransport(changed)
    job = adapter.submit_run({}, "synthetic-reviewer")
    result = adapter.execute_job(job["job_id"])
    assert result["reason_codes"] == ["INVENTORY_CHANGED_DURING_DOWNLOAD"]
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM source_cursor").fetchone()["n"] == 0


def test_changed_resource_url_never_downloads_or_redirects(settings, prepared):
    adapter, calls, payload, _, _ = prepared
    payload["result"]["resources"][0]["url"] = "https://169.254.169.254/forbidden.csv"
    job = adapter.submit_run({}, "synthetic-reviewer")
    assert adapter.execute_job(job["job_id"])["reason_codes"] == ["QBCC_RESOURCE_MAPPING_CHANGED"]
    assert calls == [CATALOGUES["qbcc"].endpoint]


def test_unchanged_second_publication_is_noop(settings, prepared):
    adapter, calls, _, _, _ = prepared
    first = adapter.execute_job(adapter.submit_run({}, "synthetic-reviewer")["job_id"])
    second = adapter.execute_job(adapter.submit_run({}, "synthetic-reviewer")["job_id"])
    assert first["result"]["snapshot_id"] == second["result"]["snapshot_id"]
    assert second["result"]["noop"] and len(calls) == 6
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM qbcc_event").fetchone()["n"] == 1


def test_pending_cli_worker_uses_same_durable_job(settings, prepared):
    adapter, _, _, _, _ = prepared
    job = adapter.submit_run({}, "synthetic-reviewer")
    assert adapter.execute_pending()[0]["job_id"] == job["job_id"]
    assert adapter.execute_pending() == []


def test_recovery_after_accepted_intake_does_not_download_again(settings, prepared):
    adapter, calls, _, _, _ = prepared
    job = adapter.submit_run({}, "synthetic-reviewer")
    done = adapter.execute_job(job["job_id"])
    with transaction(settings) as conn:
        conn.execute(
            "UPDATE pipeline_run SET state='running',heartbeat_at=clock_timestamp()-interval '2 hours',manifest=jsonb_set(manifest,'{phase}','\"accepting\"') WHERE run_id=%s",
            (job["job_id"],),
        )
    recovered = adapter.execute_pending()[0]
    assert recovered["result"]["snapshot_id"] == done["result"]["snapshot_id"] and len(calls) == 3


def test_wrong_source_or_idempotency_actor_is_rejected(prepared):
    adapter, _, _, _, _ = prepared
    with pytest.raises(DomainError, match="QBCC_PILOT_SOURCE_REQUIRED"):
        adapter.submit_run({"source": "abr"}, "synthetic-reviewer")
    request = {"request_id": str(uuid4())}
    adapter.submit_run(request, "synthetic-reviewer")
    with pytest.raises(DomainError, match="IDEMPOTENCY_CONFLICT"):
        adapter.submit_run(request, "another-user")


def test_unexpected_provider_error_becomes_safe_failed_job(prepared, monkeypatch):
    adapter, _, _, _, _ = prepared
    job = adapter.submit_run({}, "synthetic-reviewer")

    def failure(*args, **kwargs):
        raise RuntimeError("synthetic-secret-sentinel-must-not-escape")

    monkeypatch.setattr(runtime, "inspect_catalogue", failure)
    result = adapter.execute_job(job["job_id"])
    assert result["state"] == "failed" and result["reason_codes"] == ["QBCC_JOB_FAILED"]
    assert "sentinel" not in str(result)
