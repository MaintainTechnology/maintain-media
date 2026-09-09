"""Local dashboard checks exercise real PostgreSQL and real fixture runs."""

import csv
import io
import json
import threading
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, digest
from abr_engine.dashboard.api import create_app
from abr_engine.dashboard.models import RunRequest
from abr_engine.dashboard.service import Dashboard
from abr_engine.db import transaction
from abr_engine.enrich.worker import SyntheticProvider
from abr_engine.export.report import worklist_rows
from abr_engine.export.worklist import report_context
from abr_engine.pipeline import execute, process_lock


@pytest.fixture
def dashboard_app(settings, tmp_path):
    config = settings.model_copy(update={"output_dir": tmp_path})
    app = create_app(config)
    yield app
    if app.state.dashboard.thread:
        app.state.dashboard.thread.join(timeout=60)
        assert not app.state.dashboard.thread.is_alive()


def client(app):
    return TestClient(app, base_url="http://127.0.0.1:8767", client=("127.0.0.1", 51000))


def headers(http):
    response = http.get("/api/dashboard")
    assert response.status_code == 200, response.text
    return {"Origin": "http://127.0.0.1:8767", "X-Dashboard-CSRF": response.json()["csrf_token"]}


def test_saved_settings_change_real_run_and_survive_restart(dashboard_app, monkeypatch):
    original_tariff = SyntheticProvider.tariff

    def priced_fixture(self, stage, now):
        return {**original_tariff(self, stage, now), "native_upper_bound": "1"}

    # Exercise the actual budget boundary with a quoted cost; normal synthetic runs cost zero.
    monkeypatch.setattr(SyntheticProvider, "tariff", priced_fixture)
    http = client(dashboard_app)
    auth = headers(http)
    saved = http.patch("/api/settings", json={"default_source": "qbcc", "monthly_cap_micro_aud": 0}, headers=auth)
    assert saved.status_code == 200 and saved.json()["monthly_cap_micro_aud"] == 0
    dashboard = dashboard_app.state.dashboard
    restarted = Dashboard(dashboard.settings)
    assert restarted.preferences().monthly_cap_micro_aud == 0
    assert restarted.preferences().default_source == "qbcc"
    request_id = str(uuid4())
    response = http.post("/api/runs", json={"request_id": request_id}, headers=auth)
    assert response.status_code == 202, response.text
    job = response.json()
    dashboard.thread.join(timeout=60)
    assert not dashboard.thread.is_alive()
    completed = http.get(f"/api/jobs/{request_id}").json()
    assert completed["state"] == "complete", completed
    with transaction(dashboard.settings) as conn:
        run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (job["run_id"],)).fetchone()
        expected = dashboard.settings.model_copy(update={"monthly_cap_micro_aud": 0})
        assert run["config_digest"] == digest(expected.model_dump())
        assert set(run["manifest"]["result"]["sources"]) == {"qbcc"}
        assert run["manifest"]["result"]["counts"]["live_api_calls"] == 0
        assert any(item.get("reason") == "BUDGET_STOP" for item in run["manifest"]["result"]["enrichment"])
    duplicate = http.post("/api/runs", json={"request_id": request_id}, headers=auth)
    assert duplicate.status_code == 202 and duplicate.json()["run_id"] == job["run_id"]
    conflict = http.post("/api/runs", json={"request_id": request_id, "source": "abr"}, headers=auth)
    assert conflict.status_code == 409
    state = http.get("/api/dashboard").json()
    assert state["summary"]["total_leads"] >= 2
    assert any(lead["abn"] and len(lead["abn"]) == 11 for lead in state["leads"])
    assert "encrypted" not in json.dumps(state) and "database_url" not in json.dumps(state)


def test_browser_boundary_and_closed_settings(dashboard_app):
    http = client(dashboard_app)
    auth = headers(http)
    assert http.get("/api/dashboard/health").json()["service"] == "abn-leadgen-dashboard"
    for origin in ("https://evil.invalid", "null", "http://localhost:8767"):
        hostile = {**auth, "Origin": origin}
        assert http.patch("/api/settings", json={"default_source": "abr"}, headers=hostile).status_code == 403
    assert http.patch("/api/settings", json={"default_source": "abr"}).status_code == 403
    assert http.get("/api/dashboard", headers={"Host": "evil.invalid"}).status_code == 403
    assert http.get("/api/dashboard", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    remote = TestClient(dashboard_app, base_url="http://127.0.0.1:8767", client=("192.168.0.8", 52000))
    assert remote.get("/api/dashboard").status_code == 403
    for invalid in ({"mode": "production"}, {"monthly_cap_micro_aud": 150_000_001},
                    {"monthly_cap_micro_aud": -1}, {"monthly_cap_micro_aud": True},
                    {"monthly_cap_micro_aud": "100"}, {"default_source": "live"},
                    {"database_url": "forbidden"}, {"monthly_cap_micro_aud": None}):
        assert http.patch("/api/settings", json=invalid, headers=auth).status_code == 422
    assert http.patch("/api/settings", content="x" * 4097,
                      headers={**auth, "Content-Type": "application/json"}).status_code == 413
    assert http.patch("/api/settings", content="default_source=abr", headers=auth).status_code == 415
    assert http.get("/assets/api.py").status_code == 404
    assert http.get("/var/reports/anything").status_code == 404
    with pytest.raises(ValueError, match="fixture"):
        create_app(dashboard_app.state.dashboard.settings.model_copy(update={"mode": "production"}))


def test_run_lock_deduplicates_across_dashboard_instances(dashboard_app, monkeypatch):
    dashboard = dashboard_app.state.dashboard
    second = Dashboard(dashboard.settings)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def bounded_fixture(settings, service, source, run_id):
        calls.append(run_id)
        entered.set()
        assert release.wait(10)
        return {"status": "complete"}

    monkeypatch.setattr("abr_engine.dashboard.service.execute", bounded_fixture)
    request = RunRequest(request_id=uuid4(), source="abr")
    try:
        first = dashboard.submit(request)
        assert entered.wait(5)
        assert second.submit(request)["run_id"] == first["run_id"]
        with pytest.raises(DomainError, match="RUN_ALREADY_ACTIVE"):
            second.submit(RunRequest(request_id=uuid4()))
        assert len(calls) == 1
    finally:
        release.set()
        dashboard.thread.join(timeout=10)
    assert second.job(request.request_id)["state"] == "complete"
    assert second.state()["latest_job"]["state"] == "complete"

    def failing_fixture(*args, **kwargs):
        raise RuntimeError("private exception details must not enter API receipts")

    monkeypatch.setattr("abr_engine.dashboard.service.execute", failing_fixture)
    failed = dashboard.submit(RunRequest(request_id=uuid4()))
    dashboard.thread.join(timeout=10)
    state = second.state()
    assert state["active_job"] is None
    assert state["latest_job"]["job_id"] == failed["job_id"]
    assert state["latest_job"]["state"] == "failed" and state["latest_job"]["error_code"] == "RUN_FAILED"
    assert "private exception" not in json.dumps(state)


def test_interrupted_job_is_explicit_and_never_replayed(dashboard_app):
    dashboard = dashboard_app.state.dashboard
    job_id = uuid4()
    value = {"job_id": str(job_id), "run_id": str(uuid4()), "state": "running", "source": "abr"}
    dashboard._write(dashboard._job_path(job_id), value)
    with transaction(dashboard.settings) as conn:
        conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','running')", (value["run_id"],))
    with process_lock(dashboard.local / "run.lock"):
        assert dashboard.job(job_id)["state"] == "running"
    interrupted = dashboard.job(job_id)
    assert interrupted["state"] == "interrupted" and interrupted["error_code"] == "RUN_INTERRUPTED"
    assert dashboard.submit(RunRequest(request_id=job_id))["state"] == "interrupted"
    state = dashboard.state()
    assert state["latest_job"]["state"] == "interrupted" and state["active_job"] is None
    assert state["runs"][0]["status"] == "interrupted"
    assert state["runs"][0]["pipeline_status"] == "running"


@pytest.mark.parametrize("finished_state", ["complete", "failed"])
def test_job_completion_between_receipt_read_and_lock_is_preserved(dashboard_app, monkeypatch, finished_state):
    dashboard = dashboard_app.state.dashboard
    job_id = uuid4()
    pending = {"job_id": str(job_id), "run_id": str(uuid4()), "state": "running", "source": "abr"}
    dashboard._write(dashboard._job_path(job_id), pending)
    read = dashboard._read_job
    reads = 0

    def worker_finishes_after_read(identifier):
        nonlocal reads
        snapshot = read(identifier)
        reads += 1
        if reads == 1:
            dashboard._write(dashboard._job_path(identifier), {**pending, "state": finished_state})
        return snapshot

    monkeypatch.setattr(dashboard, "_read_job", worker_finishes_after_read)
    assert dashboard.job(job_id)["state"] == finished_state
    assert read(job_id)["state"] == finished_state


def test_receipt_removed_before_job_lock_is_not_resurrected(dashboard_app, monkeypatch):
    dashboard = dashboard_app.state.dashboard
    job_id = uuid4()
    dashboard._write(dashboard._job_path(job_id), {
        "job_id": str(job_id), "run_id": str(uuid4()), "state": "running", "source": "abr",
    })
    read = dashboard._read_job

    def remove_after_read(identifier):
        snapshot = read(identifier)
        dashboard._job_path(identifier).unlink(missing_ok=True)
        return snapshot

    monkeypatch.setattr(dashboard, "_read_job", remove_after_read)
    with pytest.raises(DomainError, match="JOB_NOT_FOUND"):
        dashboard.job(job_id)
    assert not dashboard._job_path(job_id).exists()


@pytest.mark.parametrize("source, expected_error", [("abr", None), ("qbcc", "REQUEST_ID_CONFLICT")])
def test_submit_rechecks_idempotency_after_acquiring_process_lock(dashboard_app, monkeypatch, source, expected_error):
    dashboard = dashboard_app.state.dashboard
    request = RunRequest(request_id=uuid4(), source=source)
    finished = {"job_id": str(request.request_id), "run_id": str(uuid4()), "state": "complete", "source": "abr"}
    read = dashboard._read_job
    reads = 0

    def competing_instance_finishes_after_lookup(identifier):
        nonlocal reads
        snapshot = read(identifier)
        reads += 1
        if reads == 1:
            dashboard._write(dashboard._job_path(identifier), finished)
        return snapshot

    monkeypatch.setattr(dashboard, "_read_job", competing_instance_finishes_after_lookup)
    monkeypatch.setattr("abr_engine.dashboard.service.execute", lambda *args, **kwargs: pytest.fail("Request replayed"))
    if expected_error:
        with pytest.raises(DomainError, match=expected_error):
            dashboard.submit(request)
    else:
        assert dashboard.submit(request) == finished
    assert dashboard.thread is None
    assert read(request.request_id) == finished
    with process_lock(dashboard.local / "run.lock"):
        pass


def test_invalid_job_receipts_leave_other_results_available_with_notice(dashboard_app):
    dashboard = dashboard_app.state.dashboard
    invalid_ids = [uuid4() for _ in range(5)]
    invalid = ["{incomplete", "[]", "{}", json.dumps({"state": []}), json.dumps({"job_id": "private-data"})]
    for identifier, payload in zip(invalid_ids, invalid, strict=True):
        dashboard._job_path(identifier).write_text(payload, encoding="utf-8")
    unknown_name = dashboard.local / "jobs" / "invalid-name.json"
    unknown_name.write_text("{}", encoding="utf-8")
    good_id = uuid4()
    good = {"job_id": str(good_id), "run_id": str(uuid4()), "state": "complete", "source": "abr"}
    dashboard._write(dashboard._job_path(good_id), good)
    http = client(dashboard_app)
    state = http.get("/api/dashboard")
    assert state.status_code == 200
    assert state.json()["latest_job"] == good
    notices = state.json()["operational_notices"]
    assert notices[0]["code"] == "DASHBOARD_JOB_RECEIPTS_UNAVAILABLE"
    assert notices[0]["count"] == 6
    assert "private-data" not in state.text
    for identifier in invalid_ids:
        response = http.get(f"/api/jobs/{identifier}")
        assert response.status_code == 503 and response.json()["code"] == "DASHBOARD_JOB_INVALID"
        assert dashboard._job_path(identifier).exists()
    assert unknown_name.exists()


def test_report_integrity_scope_deletion_and_current_authority(dashboard_app):
    dashboard = dashboard_app.state.dashboard
    result = execute(dashboard.settings, dashboard.service, source="qbcc")
    run_id = UUID(result["run_id"])
    http = client(dashboard_app)
    report = http.get(f"/api/reports/{run_id}/html")
    assert report.status_code == 200, report.text
    assert f'href="/api/reports/{run_id}/csv"' in report.text
    csv = http.get(f"/api/reports/{run_id}/csv")
    assert csv.status_code == 200 and "attachment" in csv.headers["Content-Disposition"]
    assert http.get(f"/api/reports/{run_id}/manifest").status_code == 404
    assert http.get(f"/api/reports/{uuid4()}/csv").status_code == 404
    path = Path(result["artifacts"]["csv"])
    original = path.read_bytes()
    path.write_bytes(original + b"corrupted")
    assert http.get(f"/api/reports/{run_id}/csv").json()["code"] == "REPORT_INTEGRITY_FAILURE"
    path.write_bytes(original)
    with transaction(dashboard.settings) as conn:
        conn.execute("UPDATE artifact_manifest SET state='deleted' WHERE local_path=%s", (str(path),))
    assert http.get(f"/api/reports/{run_id}/csv").status_code == 410
    with transaction(dashboard.settings) as conn:
        conn.execute("UPDATE policy SET expires_at=clock_timestamp()-interval '1 second'")
    stale = http.get(f"/api/reports/{run_id}/html")
    assert stale.status_code == 409 and stale.json()["code"] == "REPORT_STALE_RUN_AGAIN"
    with transaction(dashboard.settings) as conn:
        record = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (run_id,)).fetchone()
        manifest = record["manifest"]
        manifest["result"]["artifacts"]["html"] = str(dashboard.local / "settings.json")
        conn.execute("UPDATE pipeline_run SET manifest=%s WHERE run_id=%s", (Jsonb(manifest), run_id))
    assert http.get(f"/api/reports/{run_id}/html").status_code == 404
    with transaction(dashboard.settings) as conn:
        conn.execute("INSERT INTO system_state(name,value) VALUES('restore_quarantine','true') ON CONFLICT(name) DO UPDATE SET value='true'")
    assert http.get("/api/dashboard").json()["code"] == "AUTHORITY_QUARANTINED"
    assert http.get(f"/api/reports/{run_id}/html").status_code == 503


def test_dashboard_report_masks_allowed_contacts_without_changing_private_artifacts(dashboard_app):
    dashboard = dashboard_app.state.dashboard
    result = execute(dashboard.settings, dashboard.service, source="qbcc")
    run_id = UUID(result["run_id"])
    with transaction(dashboard.settings) as conn:
        context = report_context(conn, dashboard.service, UUID(result["worklist_id"]), run_id)
    allowed_contacts = {row.candidate_endpoint for row in context.rows if row.export_allowed and row.candidate_endpoint}
    assert allowed_contacts, "Exercise a contact that the canonical private report is allowed to disclose"
    original = {kind: Path(path).read_bytes() for kind, path in result["artifacts"].items()}
    assert any(endpoint.encode() in original["csv"] for endpoint in allowed_contacts)
    http = client(dashboard_app)
    responses = {kind: http.get(f"/api/reports/{run_id}/{kind}") for kind in ("html", "csv", "markdown")}
    for kind, response in responses.items():
        assert response.status_code == 200, response.text
        assert "contact hidden in dashboard" in response.text
        assert all(endpoint not in response.text for endpoint in allowed_contacts)
        assert str(context.rows[0].row_id) in response.text
        assert Path(result["artifacts"][kind]).read_bytes() == original[kind]
    assert f'href="/api/reports/{run_id}/csv"' in responses["html"].text
    assert f"](/api/reports/{run_id}/csv)" in responses["markdown"].text
    for kind in ("csv", "markdown"):
        assert "attachment" in responses[kind].headers["Content-Disposition"]
    actual_rows = list(csv.DictReader(io.StringIO(responses["csv"].content.decode("utf-8-sig"))))
    expected_rows = worklist_rows(context)
    assert len(actual_rows) == len(expected_rows)
    for actual, expected in zip(actual_rows, expected_rows, strict=True):
        assert actual["safe_contact_view"] == "Masked — contact hidden in dashboard"
        for field in ("business_name", "source", "row_id", "worklist_id", "lead_id", "group_id", "row_version"):
            assert actual[field] == str(expected[field])
