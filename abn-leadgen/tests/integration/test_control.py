from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from abr_engine.control.api import create_app
from abr_engine.control.auth import fixture_token
from abr_engine.control.service import DomainError
from abr_engine.db import transaction
from abr_engine.enrich.budget import BudgetError, reserve, settle, upper_micro_aud
from abr_engine.export.worklist import build_worklist, report_context
from abr_engine.fixture import CONTENT, seed_contact, seed_policy


def ready(db, service):
    seed_policy(db, service)
    return seed_contact(db, service)


def relevance(db, service, seeded, state="pass"):
    contact = seeded["contact"]
    return service.relevance(db, {"contact_id": contact["contact_id"], "channel": "email",
                                 "campaign_id": "fixture-campaign", "template_id": "fixture-template",
                                 "content_sha256": CONTENT, "policy_version": service.current_policy(db)["version"],
                                 "state": state, "role_evidence_id": contact["first_provenance_id"], "reason": "Synthetic relevant role",
                                 "expected_contact_revision": contact["revision"]}, "fixture-reviewer")


def intent(db, service, seeded, actor="fixture-sender"):
    rev = relevance(db, service, seeded)
    return service.action(db, {"lead_id": seeded["lead"]["lead_id"], "contact_id": seeded["contact"]["contact_id"],
                               "channel": "email", "campaign_id": "fixture-campaign", "template_id": "fixture-template",
                               "content_sha256": CONTENT, "relevance_assessment_id": rev["assessment_id"],
                               "expected_contact_revision": seeded["contact"]["revision"], "recipient_timezone": None}, actor)


def test_positive_candidate_and_latest_unknown_blocks(db, service):
    seeded = ready(db, service)
    assert service.gate(db, seeded["contact"]["contact_id"])["allowed"]
    c = seeded["contact"]
    service.basis(db, {"contact_id": c["contact_id"], "channel": "email", "expected_revision": c["revision"],
                       "basis_type": "none", "assessment_state": "unknown", "evidence_provenance_id": c["first_provenance_id"],
                       "reason": "New uncertainty supersedes prior pass"}, "fixture-reviewer")
    assert "BASIS_NOT_CURRENT" in service.gate(db, c["contact_id"])["reason_codes"]


def test_suppression_first_denies_pending_and_preserves_event(db, service):
    seeded = ready(db, service)
    pending = intent(db, service, seeded)
    assert pending["state"] == "pending"
    service.suppress(db, {"lead_id": seeded["lead"]["lead_id"], "reason": "unsubscribe", "source": "test"}, "operator", uuid4())
    decision = service.consume(db, pending["intent_id"], {"dispatch_id": uuid4(), "content_sha256": CONTENT}, "fixture-sender")
    assert decision["decision"] == "denied"
    assert "SUPPRESSED_UNSUBSCRIBE" in decision["reason_codes"]


def test_consumption_first_preserves_inflight_and_replay_contract(db, service):
    seeded = ready(db, service)
    pending = intent(db, service, seeded)
    dispatch = {"dispatch_id": uuid4(), "content_sha256": CONTENT}
    first = service.consume(db, pending["intent_id"], dispatch, "fixture-sender")
    assert first["decision"] == "allowed"
    service.suppress(db, {"lead_id": seeded["lead"]["lead_id"], "reason": "unsubscribe", "source": "test"}, "operator", uuid4())
    replay = service.consume(db, pending["intent_id"], dispatch, "fixture-sender")
    assert replay["replayed"] and replay["checked_at"] == first["checked_at"]
    assert db.execute("SELECT state FROM action_intent WHERE intent_id=%s", (pending["intent_id"],)).fetchone()["state"] == "consumed"
    with pytest.raises(DomainError, match="ALREADY_CONSUMED"):
        service.consume(db, pending["intent_id"], {**dispatch, "dispatch_id": uuid4()}, "fixture-sender")


def test_worklist_stale_optout_still_commits(db, service):
    seeded = ready(db, service)
    now = service.now(db)
    week = now.date() - timedelta(days=now.weekday())
    work = build_worklist(db, service, week)
    assert work["selected"] == 1
    row = db.execute("SELECT * FROM worklist_row WHERE worklist_id=%s", (work["worklist_id"],)).fetchone()
    data = {"expected_version": 99, "status": "do_not_contact_requested", "attempts": 0,
            "invitation_state": "unknown", "notes": "", "occurred_at": now}
    result = service.outcome(db, row["row_id"], data, "operator", uuid4())
    assert result["suppression_committed"] and result["outcome_conflict"]
    context = report_context(db, service, work["worklist_id"], uuid4())
    assert context.rows[0].candidate_endpoint is None
    assert not service.gate(db, seeded["contact"]["contact_id"])["allowed"]


def test_budget_concurrent_cap_and_uncertain_crossmonth(settings, service):
    with transaction(settings) as conn:
        now = service.now(conn)
    tariff = {"version": "fixture-tariff", "currency": "AUD", "native_upper_bound": "90", "fx": "1", "tax_rate": "0", "fx_date": now.date().isoformat()}
    amount = upper_micro_aud("90", "1")
    def attempt():
        try:
            with transaction(settings) as conn:
                return reserve(conn, operation_id=uuid4(), now=now, amount=amount, tariff=tariff)
        except BudgetError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: attempt(), range(2)))
    allowed = [r for r in rows if r]
    assert len(allowed) == 1
    with transaction(settings) as conn:
        held = settle(conn, allowed[0]["reservation_id"], None, None)
        assert held["state"] == "uncertain"
        assert held["month"] == allowed[0]["month"]
        budget = conn.execute("SELECT * FROM budget_month").fetchone()
        assert budget["reserved"] == amount and budget["settled"] == 0


def api_fixture(settings, service):
    with transaction(settings) as conn:
        seeded = ready(conn, service)
    app = create_app(settings)
    return app, TestClient(app), seeded


def headers(service, scopes=None, actor="fixture-operator", key=None):
    return {"Authorization": "Bearer " + fixture_token(service, actor, scopes or ["operator"]),
            "Idempotency-Key": str(key or uuid4()), "X-Request-ID": str(uuid4())}


def test_api_auth_idempotent_commit_and_changed_body(settings, service):
    _app, client, seeded = api_fixture(settings, service)
    body = {"lead_id": str(seeded["lead"]["lead_id"]), "reason": "unsubscribe", "source": "fixture",
            "requested_at": seeded["lead"]["first_qualified_at"].isoformat()}
    assert client.post("/v1/suppressions", json=body).status_code == 401
    assert client.post("/v1/suppressions", json=body, headers=headers(service, ["reviewer"])).status_code == 403
    h = headers(service)
    first = client.post("/v1/suppressions", json=body, headers=h)
    assert first.status_code == 201, first.text
    with transaction(settings) as conn:
        assert service.restricted(conn, seeded["lead"]["group_id"])
    repeat = client.post("/v1/suppressions", json=body, headers=h)
    assert repeat.status_code == 200 and repeat.json() == first.json()
    changed = client.post("/v1/suppressions", json={**body, "reason": "manual"}, headers=h)
    assert changed.status_code == 409
    assert "@example.com" not in first.text


def test_api_closed_schema_and_body_limit(settings, service):
    _, client, _seeded = api_fixture(settings, service)
    body = {"relevance": True}
    response = client.post("/v1/action-intents", json=body, headers=headers(service, ["sender"]))
    assert response.status_code == 422 and "input" not in response.text
    response = client.post("/v1/suppressions", content=b"x" * 65537, headers=headers(service))
    assert response.status_code == 413


def test_api_naive_bridge_timestamp_rejected(settings, service):
    app, client, seeded = api_fixture(settings, service)
    app.state.bridge = {"secret": "fixture-secret", "editors": {"editor@example.com": ["operator"]}}
    h = headers(service, ["bridge"])
    h.update({"X-Bridge-Actor": "editor@example.com", "X-Bridge-Timestamp": "2026-09-08T10:00:00", "X-Bridge-Signature": "0" * 64})
    body = {"lead_id": str(seeded["lead"]["lead_id"]), "reason": "unsubscribe", "source": "fixture",
            "requested_at": seeded["lead"]["first_qualified_at"].isoformat()}
    assert client.post("/v1/suppressions", json=body, headers=h).status_code == 401
