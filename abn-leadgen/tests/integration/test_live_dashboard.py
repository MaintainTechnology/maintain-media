"""Live HTTP contracts against isolated PostgreSQL using explicitly synthetic keys and rows."""
import hashlib
import json
import time
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from abr_engine.control import api as control_api
from abr_engine.db import transaction
from abr_engine.live.api import create_live_app
from abr_engine.live.auth import WebsiteAuthority

KEY = "synthetic-only-website-assertion-" + "k" * 43


def headers(path, method="GET", body=None, *, actor="user_Staff123", scopes=None, key=None):
    body_bytes = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
    request_id, idempotency = str(uuid4()), (key or str(uuid4())) if method != "GET" else ""
    now = int(time.time())
    claims = {"iss": "maintain-media-website", "aud": "abr-engine-live", "sub": actor,
              "scopes": scopes or ["admin", "operator"], "iat": now, "exp": now + 60,
              "jti": str(uuid4()), "method": method, "path": path,
              "body_sha256": hashlib.sha256(body_bytes).hexdigest(),
              "request_id": request_id, "idempotency_key": idempotency}
    return {"Authorization": "Bearer " + jwt.encode(claims, KEY, algorithm="HS256"),
            "X-Request-ID": request_id, "Idempotency-Key": idempotency, "Content-Type": "application/json"}, body_bytes


@pytest.fixture
def live_client(settings, service, monkeypatch):
    monkeypatch.setattr(control_api, "load_keys", lambda _: service.keys)
    live = settings.model_copy(update={"mode": "pilot"})
    app = create_live_app(live, authority=WebsiteAuthority(KEY))
    with TestClient(app) as client:
        yield client, live


def test_actual_empty_database_reports_live_empty_and_closed_capabilities(live_client):
    client, _ = live_client
    assert client.get("/api/dashboard").status_code == 401
    signed, _ = headers("/api/dashboard")
    response = client.get("/api/dashboard", headers=signed)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mode"] == "pilot" and data["leads"] == []
    assert data["summary"]["total_leads"] == 0 and data["runs"] == []
    assert data["outreach"] == "disabled"
    assert not data["run_enabled"]
    assert next(row for row in data["setup"] if row["id"] == "collection")["status"] == "blocked"
    website = next(row for row in data["setup"] if row["id"] == "website_collection")
    assert website["status"] == "blocked" and website["detail"] == "Required evidence: CAPABILITY_DISABLED"


def test_real_stored_business_is_visible_and_optout_commits_with_clerk_actor(live_client, service):
    client, settings = live_client
    with transaction(settings) as conn:
        lead = service.create_lead(conn, name="Synthetic acceptance builder", source="qbcc", alias="SYNTH-101")
    signed, _ = headers("/api/dashboard")
    data = client.get("/api/dashboard", headers=signed).json()
    assert data["summary"]["total_leads"] == 1
    assert data["leads"][0]["business_name"] == "Synthetic acceptance builder"
    assert data["leads"][0]["reason_codes"] == ["NO_CONTACT"]
    assert data["leads"][0]["crm_handoff"] is None
    signed, _ = headers("/api/dashboard", scopes=["admin", "reviewer"])
    reviewed = client.get("/api/dashboard", headers=signed).json()["leads"][0]["crm_handoff"]
    assert reviewed["state"] == "not_selected"
    assert reviewed["can_approve"] is reviewed["can_reject"] is False
    assert set(reviewed["reason_codes"]) == {"ONLY_SELECTED_TIER_A", "CAPABILITY_DISABLED"}
    payload = {"lead_id": str(lead["lead_id"]), "reason": "unsubscribe", "source": "staff_dashboard",
               "requested_at": "2026-09-01T00:00:00Z"}
    key = str(uuid4())
    signed, encoded = headers("/v1/suppressions", "POST", payload, key=key)
    response = client.post("/v1/suppressions", headers=signed, content=encoded)
    assert response.status_code == 201, response.text
    again = client.post("/v1/suppressions", headers=signed, content=encoded)
    assert again.status_code == 200 and again.json() == response.json()
    with transaction(settings) as conn:
        rows = conn.execute("SELECT actor_id,reason FROM suppression_event WHERE request_id=%s", (key,)).fetchall()
        assert rows and all(row["actor_id"] == "user_Staff123" for row in rows)
        assert conn.execute("SELECT lifecycle FROM lead_entity WHERE lead_id=%s", (lead["lead_id"],)).fetchone()["lifecycle"] == "suppressed"


def test_settings_are_real_persisted_idempotent_and_reviewer_cannot_administer(live_client):
    client, settings = live_client
    payload = {"default_source": "qbcc", "monthly_cap_micro_aud": 20_000_000}
    signed, encoded = headers("/api/settings", "PATCH", payload, scopes=["reviewer"])
    assert client.patch("/api/settings", headers=signed, content=encoded).status_code == 403
    key = str(uuid4())
    signed, encoded = headers("/api/settings", "PATCH", payload, key=key)
    response = client.patch("/api/settings", headers=signed, content=encoded)
    assert response.status_code == 200 and response.json() == payload
    assert client.patch("/api/settings", headers=signed, content=encoded).json() == payload
    with transaction(settings) as conn:
        assert conn.execute("SELECT value FROM system_state WHERE name='live_dashboard_settings'").fetchone()["value"] == payload
        assert conn.execute("SELECT count(*) AS n FROM audit_event WHERE action='dashboard_settings_changed'").fetchone()["n"] == 1


def test_generic_admin_cannot_make_reviewer_assessment_or_source_read(live_client):
    client, _ = live_client
    signed, _ = headers("/api/qbcc-reviews")
    assert client.get("/api/qbcc-reviews", headers=signed).status_code == 403
    payload = {"lead_id": str(uuid4()), "licence_number": "SYNTH-1", "status": "active", "identity_match": True,
               "evidence_ref": "synthetic-check", "reviewed_at": "2026-09-01T00:00:00Z"}
    signed, encoded = headers("/v1/licence-reviews", "POST", payload)
    assert client.post("/v1/licence-reviews", headers=signed, content=encoded).status_code == 403


def test_source_rows_cannot_bypass_closed_collection_approval(live_client):
    client, _ = live_client
    signed, _ = headers("/api/qbcc-reviews", scopes=["admin", "operator", "reviewer"])
    response = client.get("/api/qbcc-reviews", headers=signed)
    assert response.status_code in {200, 403}
    if response.status_code == 200:
        assert response.json()["rows"] == []
    else:
        assert "GATE" in response.json()["code"] or "CAPABILITY" in response.json()["code"]


def test_restore_quarantine_hides_business_data(live_client):
    client, settings = live_client
    with transaction(settings) as conn:
        conn.execute("UPDATE system_state SET value=%s WHERE name='restore_quarantine'", (Jsonb(True),))
    signed, _ = headers("/api/dashboard")
    response = client.get("/api/dashboard", headers=signed)
    assert response.status_code == 503 and response.json()["code"] == "AUTHORITY_QUARANTINED"


def test_request_assertion_cannot_be_replayed_to_another_mutation(live_client):
    client, _ = live_client
    payload = {"default_source": "qbcc"}
    signed, encoded = headers("/api/settings", "PATCH", payload)
    response = client.patch("/api/settings", headers=signed, content=encoded + b" ")
    assert response.status_code == 401
    assert client.get("/api/dashboard", headers=signed).status_code == 401


def test_sheet_headers_cannot_select_an_unconfigured_alternate_authority(live_client):
    client, _ = live_client
    signed, _ = headers("/api/dashboard")
    signed["X-Bridge-Actor"] = "spoof@example.test"
    assert client.get("/api/dashboard", headers=signed).status_code == 401


def test_saved_cap_constrains_actual_paid_reservations_without_erasing_prior_spend(settings, service):
    from abr_engine.enrich.budget import BudgetError, reserve
    from abr_engine.live.dashboard import save_preferences

    with transaction(settings) as conn:
        now = service.now(conn)
        tariff = {"version": "synthetic-v1", "fx_date": now.date().isoformat(), "currency": "AUD",
                  "native_upper_bound": "2", "fx": "1", "tax_rate": "0"}
        operation = uuid4()
        first = reserve(conn, operation_id=operation, now=now, amount=2_200_000, tariff=tariff)
        save_preferences(conn, service, {"monthly_cap_micro_aud": 0}, "user_Staff123")
        replay = reserve(conn, operation_id=operation, now=now, amount=2_200_000, tariff=tariff)
        assert replay["reservation_id"] == first["reservation_id"]
    with pytest.raises(BudgetError, match="BUDGET_STOP"), transaction(settings) as conn:
        reserve(conn, operation_id=uuid4(), now=now, amount=2_200_000, tariff=tariff, cap=150_000_000)
    with transaction(settings) as conn:
        assert conn.execute("SELECT reserved FROM budget_month").fetchone()["reserved"] == 2_200_000


def test_sheet_pull_requires_dedicated_installed_authority(settings, service, monkeypatch, tmp_path):
    from abr_engine.control import sheets_auth
    from abr_engine.control.auth import Actor
    from abr_engine.export import sheets

    monkeypatch.setattr(control_api, "load_keys", lambda _: service.keys)
    registry = object()
    selected_path = tmp_path / "synthetic-registry.yaml"
    live = settings.model_copy(update={"mode": "pilot", "sheets_bridge_file": selected_path})
    observed = []
    monkeypatch.setattr(sheets_auth, "load_bridge_registry", lambda path: registry if path == selected_path else None)
    monkeypatch.setattr(sheets, "pull_worklist", lambda config, svc, actor, selected: observed.append(
        (config, actor.actor_id, selected)
    ) or {"disclosure_allowed": False, "rows": [], "reason_codes": ["GATE_G5_CLOSED"]})
    app = create_live_app(live, authority=WebsiteAuthority(KEY), sheets_authority=lambda request: Actor(
        "named.editor@example.test", frozenset({"operator"})
    ))
    with TestClient(app) as client:
        signed, _ = headers("/v1/sheets/worklist", scopes=["admin", "operator", "owner"])
        assert client.get("/v1/sheets/worklist", headers=signed).status_code == 401
        assert not observed
        response = client.get("/v1/sheets/worklist", headers={"X-Bridge-Actor": "named.editor@example.test"})
        assert response.status_code == 200 and response.json()["rows"] == []
        assert observed == [(live, "named.editor@example.test", registry)]


def test_sheet_pull_is_closed_when_unconfigured(live_client):
    client, _ = live_client
    signed, _ = headers("/v1/sheets/worklist")
    assert client.get("/v1/sheets/worklist", headers=signed).status_code == 401
    signed["X-Bridge-Actor"] = "spoof@example.test"
    assert client.get("/v1/sheets/worklist", headers=signed).status_code == 401
