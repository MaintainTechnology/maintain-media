"""Synthetic gateway/inner-dashboard boundary checks; no database or network I/O."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from abr_engine.config import Settings
from abr_engine.dashboard import api, gateway

ORIGIN = "https://engine.maintainmedia.com.au"
TOKEN = "synthetic_fixture_token_" + "x" * 43


@pytest.fixture
def receiver(monkeypatch):
    class SyntheticDashboard:
        def __init__(self, settings):
            self.settings = settings

        def state(self):
            return {"mode": "fixture", "outreach": "disabled", "runs": []}

        def save_preferences(self, data):
            return data.model_dump(exclude_none=True)

        def submit(self, data):
            return {"state": "queued", "request_id": str(data.request_id), "mode": "fixture"}

        def job(self, job_id):
            return {"job_id": str(job_id), "state": "complete"}

        def report(self, run_id, kind):
            return b"masked fixture report", "text/csv", "fixture.csv"

    monkeypatch.setattr(api, "Dashboard", SyntheticDashboard)
    return gateway.create_gateway(Settings(), origin=ORIGIN, token=TOKEN)


def client(app, peer="127.0.0.1"):
    return TestClient(app, base_url=ORIGIN, client=(peer, 44000))


def auth(**extra):
    return {"Authorization": "Bearer " + TOKEN, **extra}


def test_reads_need_service_token_before_disclosing_route(receiver):
    http = client(receiver)
    for path in ("/api/dashboard", "/api/settings", "/", "/v1/openapi.json"):
        response = http.get(path)
        assert response.status_code == 401
        assert response.json() == {"code": "GATEWAY_UNAUTHENTICATED"}
        assert "no-store" in response.headers["cache-control"]
    for token in ("Bearer wrong", "bearer " + TOKEN, "Bearer " + TOKEN + "x"):
        assert http.get("/api/dashboard", headers={"Authorization": token}).status_code == 401
    response = http.get("/api/dashboard", headers=auth())
    assert response.status_code == 200
    assert response.json()["mode"] == "fixture"
    assert response.json()["outreach"] == "disabled"
    assert TOKEN not in response.text


def test_only_actual_local_proxy_and_exact_public_host_are_accepted(receiver):
    assert client(receiver, "203.0.113.9").get("/api/dashboard", headers=auth()).status_code == 403
    http = client(receiver)
    for host in ("127.0.0.1:8768", "evil.com", "engine.maintainmedia.com.au:8443"):
        assert http.get("/api/dashboard", headers=auth(Host=host)).status_code == 403
    assert http.get("/api/dashboard", headers=auth(**{"X-Forwarded-Host": "evil.com"})).status_code == 200
    assert http.get("/api/dashboard", headers=auth(Host="evil.com", **{
        "X-Forwarded-Host": "engine.maintainmedia.com.au"})).status_code == 403


def test_mutation_requires_external_origin_and_real_inner_csrf(receiver):
    http = client(receiver)
    csrf = http.get("/api/dashboard", headers=auth()).json()["csrf_token"]
    body = {"default_source": "qbcc"}
    assert http.patch("/api/settings", json=body, headers=auth()).status_code == 403
    for origin in ("null", "https://evil.com", "http://127.0.0.1:8767"):
        assert http.patch("/api/settings", json=body, headers=auth(Origin=origin)).status_code == 403
    response = http.patch("/api/settings", json=body, headers=auth(Origin=ORIGIN))
    assert response.status_code == 403
    assert response.json()["code"] == "DASHBOARD_CSRF_REQUIRED"
    valid = auth(Origin=ORIGIN, **{"X-Dashboard-CSRF": csrf})
    assert http.patch("/api/settings", json=body, headers=valid).json() == body
    assert http.patch("/api/settings", json=body, headers={**valid, "Sec-Fetch-Site": "cross-site"}).status_code == 403
    response = http.post("/api/runs", json={"request_id": str(uuid4())}, headers=valid)
    assert response.status_code == 202
    assert response.json()["mode"] == "fixture"


def test_inner_body_and_model_limits_still_apply(receiver):
    http = client(receiver)
    csrf = http.get("/api/dashboard", headers=auth()).json()["csrf_token"]
    valid = auth(Origin=ORIGIN, **{"X-Dashboard-CSRF": csrf})
    assert http.patch("/api/settings", content="{}", headers=valid).status_code == 415
    assert http.patch("/api/settings", json={"mode": "production"}, headers=valid).status_code == 422
    assert http.patch("/api/settings", json={"large": "x" * 4096}, headers=valid).status_code == 413


@pytest.mark.parametrize("path", [
    "/", "/report.html", "/assets/dashboard.js", "/v1/suppressions",
    "/api/dashboard?next=private", "/api/jobs/invalid", "/api/dashboard/../settings",
    "/api/%64ashboard", "/api/%E2%9C%93", "/api/reports/" + str(uuid4()) + "/json",
])
def test_gateway_is_not_an_open_proxy_or_public_html_server(receiver, path):
    response = client(receiver).get(path, headers=auth())
    assert response.status_code == 404


def test_uuid_job_and_report_routes_are_preserved(receiver):
    http = client(receiver)
    job_id = str(uuid4())
    assert http.get("/api/jobs/" + job_id, headers=auth()).json()["job_id"] == job_id
    assert http.get("/api/reports/" + job_id + "/csv", headers=auth()).text == "masked fixture report"
    assert http.delete("/api/jobs/" + job_id, headers=auth()).status_code == 404


def test_ambiguous_security_headers_are_rejected(receiver):
    response = client(receiver).get("/api/dashboard", headers=[
        ("Authorization", "Bearer " + TOKEN), ("Authorization", "Bearer wrong"),
    ])
    assert response.status_code == 400


def test_credentials_and_forwarded_identity_do_not_reach_inner_app():
    observed = {}

    async def inner(scope, receive, send):
        observed.update(scope)
        await JSONResponse({"ok": True})(scope, receive, send)

    receiver = gateway.DashboardGateway(inner, ORIGIN, TOKEN)
    response = client(receiver).get("/api/dashboard", headers=auth(**{
        "Cookie": "session=private", "X-Forwarded-For": "203.0.113.1",
        "X-Bridge-Actor": "owner", "Origin": ORIGIN,
    }))
    assert response.status_code == 200
    headers = dict(observed["headers"])
    assert headers[b"host"] == b"127.0.0.1:8767"
    assert headers[b"origin"] == b"http://127.0.0.1:8767"
    assert not {b"authorization", b"cookie", b"x-forwarded-for", b"x-bridge-actor"}.intersection(headers)


@pytest.mark.parametrize("origin", [
    "", "http://engine.maintainmedia.com.au", "https://localhost", "https://127.0.0.1",
    "https://[::1]", "https://engine.local", "https://engine.home.arpa", "https://engine.test",
    "https://a:secret@engine.maintainmedia.com.au", ORIGIN + "/api", ORIGIN + "?key=x",
    ORIGIN + "#part", ORIGIN + ":8443", " https://engine.maintainmedia.com.au",
])
def test_invalid_gateway_origins_fail_before_inner_construction(monkeypatch, origin):
    monkeypatch.setattr(gateway, "create_app", lambda _: pytest.fail("Must validate origin before app startup"))
    with pytest.raises(ValueError, match="GATEWAY_ORIGIN_INVALID"):
        gateway.create_gateway(Settings(), origin=origin, token=TOKEN)


@pytest.mark.parametrize("token", ["", "x" * 42, "x" * 257, "x" * 43 + " ", "x" * 43 + "\n", "x" * 43 + "+"])
def test_invalid_gateway_tokens_fail_before_inner_construction(monkeypatch, token):
    monkeypatch.setattr(gateway, "create_app", lambda _: pytest.fail("Must validate token before app startup"))
    with pytest.raises(ValueError, match="GATEWAY_TOKEN_INVALID"):
        gateway.create_gateway(Settings(), origin=ORIGIN, token=token)


@pytest.mark.parametrize("mode", ["pilot", "production"])
def test_gateway_cannot_start_with_live_settings(monkeypatch, tmp_path, mode):
    monkeypatch.setattr(gateway, "create_app", lambda _: pytest.fail("Must not construct a live dashboard"))
    settings = Settings(mode=mode, key_file=Path(tmp_path) / "unused")
    with pytest.raises(ValueError, match="GATEWAY_FIXTURE_ONLY"):
        gateway.create_gateway(settings, origin=ORIGIN, token=TOKEN)


def test_entrypoint_binds_loopback_and_disables_forwarded_peer_trust(receiver, monkeypatch):
    import uvicorn

    observed = {}
    monkeypatch.setattr("sys.argv", ["gateway", "--port", "8768"])
    monkeypatch.setenv("ABN_ENGINE_ORIGIN", ORIGIN)
    monkeypatch.setenv("ABN_ENGINE_TOKEN", TOKEN)
    monkeypatch.setattr(gateway, "load_settings", lambda _: Settings())
    monkeypatch.setattr(gateway, "create_gateway", lambda *args, **kwargs: receiver)
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: observed.update(kwargs))
    gateway.main()
    assert observed == {"host": "127.0.0.1", "port": 8768, "proxy_headers": False, "access_log": False}
