"""Actual authenticated API + PostgreSQL + accepted synthetic ABR source evidence."""
# ruff: noqa: F811 -- imported pytest fixtures are deliberately injected by name.

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_live_abr_runtime import prepared, run  # noqa: F401
from test_live_dashboard import KEY, headers
from test_qbcc_review_stage import live as source_live  # noqa: F401

from abr_engine.compliance.keys import KeyStore
from abr_engine.compliance.retention import erase_profile, minimise_database_evidence
from abr_engine.control import api as control_api
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.live import api, prospects, source_records
from abr_engine.live.auth import WebsiteAuthority


@pytest.fixture
def research(settings, prepared, monkeypatch):
    runtime, _, _, keys = prepared
    receipt = run(runtime)
    assert receipt["state"] == "complete"
    for module in (api, control_api, prospects, source_records):
        monkeypatch.setattr(module, "transaction", lambda ignored: transaction(settings))
    monkeypatch.setattr(control_api, "load_keys", lambda ignored: keys)
    app = api.create_live_app(runtime.settings, authority=WebsiteAuthority(KEY))
    body = {"request_id": str(uuid4()), "abn": "51824753556", "expected_revision": 0,
            "source": "abr", "run_id": receipt["job_id"], "snapshot_id": receipt["result"]["snapshot_id"],
            "business_name": "Untrusted caller name"}
    with TestClient(app) as client:
        yield client, body, app.state.service


def post(client, path, body, scopes=None):
    signed, content = headers(path, "POST", body, key=body.get("request_id"), scopes=scopes)
    return client.post(path, content=content, headers=signed)


def get(client, abn="51824753556", scopes=None):
    path = "/api/prospects/" + abn
    signed, _ = headers(path, scopes=scopes)
    return client.get(path, headers=signed)


def test_saved_research_survives_requests_encrypts_private_fields_and_cannot_qualify(settings, research):
    client, body, service = research
    assert get(client).json() == {"prospect": None}
    result = post(client, "/v1/prospects", body)
    assert result.status_code == 201, result.text
    assert result.json()["revision"] == 1 and "abn" not in result.json()
    record = get(client).json()["prospect"]
    assert record["business_name"] == "Synthetic Construction" and record["state"] == "QLD"
    assert record["website_presence"] == "unknown" and record["registration_date"] is None
    assert record["contact_permission"] == "not_assessed"
    changed = {**body, "request_id": str(uuid4()), "expected_revision": 1,
               "run_id": str(uuid4()),
               "website_presence": "absent", "email_presence": "present", "email": "hello@example.com",
               "evidence_ref": "Synthetic owner check", "research_note": "Private synthetic note",
               "contact_stage": "follow_up", "follow_up_on": "2026-09-23"}
    assert post(client, "/v1/prospects", changed).status_code == 201
    assert get(client).json()["prospect"]["research_note"] == changed["research_note"]
    assert get(client).json()["prospect"]["run_id"] == body["run_id"]
    replay = post(client, "/v1/prospects", changed)
    assert replay.status_code == 200 and replay.json()["revision"] == 2
    assert post(client, "/v1/prospects", {**changed, "request_id": str(uuid4())}).status_code == 409
    with transaction(settings) as conn:
        raw = conn.execute("SELECT * FROM prospect_research").fetchone()
        assert changed["email"] not in json.dumps(raw, default=str)
        assert changed["research_note"] not in json.dumps(raw, default=str)
        assert json.loads(service.keys.decrypt(raw["payload_encrypted"]))["email"] == changed["email"]
        assert "hello@example.com" not in json.dumps(conn.execute("SELECT * FROM idempotency_receipt").fetchall(), default=str)
        for table in ("lead_entity", "candidate_queue", "contact_record", "crm_outbox"):
            assert conn.execute(f"SELECT count(*) n FROM {table}").fetchone()["n"] == 0


def test_source_binding_auth_and_quarantine_hold_before_disclosure(settings, research):
    client, body, _ = research
    assert client.get("/api/prospects/51824753556").status_code == 401
    assert client.post("/api/prospects/query", json={"abns": [body["abn"]]}).status_code == 401
    assert get(client, scopes=["operator"]).status_code == 403
    assert post(client, "/api/prospects/query", {"abns": [body["abn"]]}, scopes=["operator"]).status_code == 403
    assert post(client, "/v1/prospects", body, scopes=["compliance"]).status_code == 403
    invalid = {**body, "request_id": str(uuid4()), "abn": "99999999999"}
    assert post(client, "/v1/prospects", invalid).json()["code"] == "PROSPECT_SOURCE_MISMATCH"
    assert post(client, "/v1/prospects", {**body, "snapshot_id": str(uuid4())}).status_code == 409
    assert post(client, "/v1/prospects", body).status_code == 201
    with transaction(settings) as conn:
        conn.execute("UPDATE system_state SET value='true' WHERE name='restore_quarantine'")
    assert get(client).status_code == 503
    assert post(client, "/api/prospects/query", {}).status_code == 503
    assert post(client, "/api/prospects/query", {"abns": [body["abn"]]}).status_code == 503
    assert post(client, "/v1/prospects", body).status_code == 503


def test_batch_returns_only_requested_saved_research_with_filters_and_pagination(research):
    client, body, _ = research
    batch = {"offset": 0, "filters": {}, "abns": [body["abn"], "11111111111"]}
    assert post(client, "/api/prospects/query", batch).json()["records"] == []
    body.update(website_presence="absent", evidence_ref="Synthetic manual research")
    assert post(client, "/v1/prospects", body).status_code == 201
    result = post(client, "/api/prospects/query", batch)
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total"] == 1 and page["limit"] == 50 and page["next_offset"] is None
    assert [row["abn"] for row in page["records"]] == [body["abn"]]
    assert page["records"][0]["website_presence"] == "absent"
    assert page["records"][0]["contact_permission"] == "not_assessed"
    assert post(client, "/api/prospects/query", {"abns": ["11111111111"]}).json()["records"] == []
    assert post(client, "/api/prospects/query", {**batch, "offset": 1}).json() == {
        "records": [], "total": 1, "offset": 1, "limit": 50, "next_offset": None}
    for filters, total in [({"website_presence": "absent"}, 1), ({"website_presence": "present"}, 0),
                           ({"query": "Construction"}, 1), ({"query": "unrelated"}, 0),
                           ({"query": body["abn"]}, 1), ({"query": "11111111111"}, 0)]:
        assert post(client, "/api/prospects/query", {**batch, "filters": filters}).json()["total"] == total


def test_verified_first_registration_filters_are_distinct_from_source_status_dates(settings, research):
    client, body, service = research
    with transaction(settings) as conn:
        today = service.now(conn).date()
    body.update(website_presence="absent", evidence_ref="Synthetic manual research",
                registration_date=str(today), registration_evidence_ref="Synthetic original registration history")
    assert post(client, "/v1/prospects", body).status_code == 201
    query = {"filters": {"website_presence": "absent", "registration_date_from": str(today - timedelta(days=6)),
                         "registration_date_to": str(today)}}
    result = post(client, "/api/prospects/query", query)
    assert result.status_code == 200 and result.json()["total"] == 1
    assert result.json()["records"][0]["registration_date"] == str(today)
    assert post(client, "/api/prospects/query", {"filters": {"website_presence": "unknown"}}).json()["total"] == 0
    assert post(client, "/api/prospects/query", {"filters": {"query": "Construction"}}).json()["total"] == 1
    assert post(client, "/api/prospects/query", {"filters": {"query": "51 824-753 556"}}).json()["total"] == 1
    assert post(client, "/api/prospects/query", {"filters": {"query": "unrelated"}}).json()["total"] == 0
    future = {**body, "request_id": str(uuid4()), "expected_revision": 1, "registration_date": str(today + timedelta(days=2))}
    assert post(client, "/v1/prospects", future).json()["code"] == "REGISTRATION_DATE_IN_FUTURE"


def test_suppression_retention_and_expiry_cover_research_without_lead_creation(settings, research):
    client, body, live_service = research
    assert post(client, "/v1/prospects", body).status_code == 201
    fixture_service = Service(settings, live_service.keys)
    with transaction(settings) as conn:
        row = conn.execute("SELECT * FROM prospect_research").fetchone()
        fixture_service.suppress(conn, {"group_id": row["group_id"], "reason": "unsubscribe", "source": "synthetic"}, "test", uuid4())
    assert get(client).status_code == 409
    assert post(client, "/api/prospects/query", {}).json()["records"] == []
    assert post(client, "/api/prospects/query", {"abns": [body["abn"]]}).json()["records"] == []
    with transaction(settings) as conn:
        now = fixture_service.now(conn)
        preview = minimise_database_evidence(conn, fixture_service, now=now + timedelta(days=31))
        assert preview["prospect_research"] == 1
        erase_profile(conn, fixture_service, row["group_id"])
        assert conn.execute("SELECT count(*) n FROM prospect_research").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM suppression_alias").fetchone()["n"] == 1
    assert post(client, "/v1/prospects", {**body, "request_id": str(uuid4())}).json()["code"] == "SUPPRESSED_SOURCE_IDENTITY"


def test_prospect_hold_blocks_group_erasure_and_finite_cleanup(settings, research):
    client, body, live_service = research
    assert post(client, "/v1/prospects", body).status_code == 201
    service = Service(settings, live_service.keys)
    with transaction(settings) as conn:
        row = conn.execute("SELECT * FROM prospect_research").fetchone()
        conn.execute("INSERT INTO retention_hold VALUES(%s,'prospect',%s,'synthetic','synthetic',%s)",
                     (uuid4(), str(row["prospect_id"]), service.now(conn)))
        assert minimise_database_evidence(conn, service, now=service.now(conn) + timedelta(days=181))["prospect_research"] == 0
        with pytest.raises(DomainError, match="SCOPED_RETENTION_HOLD"):
            erase_profile(conn, service, row["group_id"])


def test_expired_research_is_hidden_cannot_be_updated_and_is_deleted_by_retention(settings, research):
    client, body, live_service = research
    assert post(client, "/v1/prospects", body).status_code == 201
    service = Service(settings, live_service.keys)
    with transaction(settings) as conn:
        conn.execute("UPDATE prospect_research SET created_at=created_at-interval '181 days',"
                     "saved_at=saved_at-interval '181 days',expires_at=expires_at-interval '181 days'")
    assert get(client).json()["code"] == "PROSPECT_RESEARCH_EXPIRED"
    assert post(client, "/api/prospects/query", {}).json()["total"] == 0
    assert post(client, "/api/prospects/query", {"abns": [body["abn"]]}).json()["total"] == 0
    changed = {**body, "request_id": str(uuid4()), "expected_revision": 1}
    assert post(client, "/v1/prospects", changed).json()["code"] == "PROSPECT_RESEARCH_EXPIRED"
    with transaction(settings) as conn:
        result = minimise_database_evidence(conn, service, now=service.now(conn), execute=True)
        assert result["prospect_research"] == 1
        assert conn.execute("SELECT count(*) n FROM prospect_research").fetchone()["n"] == 0


def test_source_gate_withdrawal_blocks_manual_research_write(settings, research):
    client, body, _ = research
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE scope='abr' AND gate_name='G3'")
    result = post(client, "/v1/prospects", body)
    assert result.status_code == 403 and result.json()["code"] == "GATE_G3_CLOSED"
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM prospect_research").fetchone()["n"] == 0


def test_lookup_rotation_preserves_research_and_retained_alias_prevents_lost_key(settings, research):
    client, body, service = research
    assert post(client, "/v1/prospects", body).status_code == 201
    with transaction(settings) as conn:
        service.keys.rotate(2, b"N" * 32, conn=conn)
        with pytest.raises(ValueError, match="depend"):
            service.keys.retire(1, conn)
        incomplete = KeyStore(service.keys.encryption_key, {2: b"N" * 32}, active_version=2,
                              signing_key=service.keys.signing_key)
        with pytest.raises(ValueError, match="unavailable lookup versions"):
            incomplete.validate_dependencies(conn)
    assert get(client).json()["prospect"]["abn"] == body["abn"]
    changed = {**body, "request_id": str(uuid4()), "expected_revision": 1, "research_note": "After rotation"}
    assert post(client, "/v1/prospects", changed).status_code == 201
    assert get(client).json()["prospect"]["research_note"] == "After rotation"
    assert post(client, "/api/prospects/query", {"filters": {"query": "51 824 753 556"}}).json()["total"] == 1
    batch = post(client, "/api/prospects/query", {"abns": [body["abn"], "11111111111"]})
    assert batch.status_code == 200 and batch.json()["total"] == 1
    assert batch.json()["records"][0]["research_note"] == "After rotation"
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM prospect_research").fetchone()["n"] == 1
