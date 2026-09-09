from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from abr_engine.control.api import create_app
from abr_engine.control.auth import fixture_token
from abr_engine.db import transaction
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import CONTENT, seed_contact, seed_policy


def headers(service, actor="fixture-operator"):
    return {"authorization": "Bearer " + fixture_token(service, actor, ["operator"]),
            "idempotency-key": str(uuid4()), "x-request-id": str(uuid4())}


def test_phone_creation_and_consumption_require_current_assignment(settings, service):
    with transaction(settings) as c:
        policy = seed_policy(c, service)
        seeded = seed_contact(c, service, phone=True)
        today = service.now(c).date()
        worklist = build_worklist(c, service, today-timedelta(days=today.weekday()))
    client = TestClient(create_app(settings))
    body = {"lead_id": str(seeded["lead"]["lead_id"]), "contact_id": str(seeded["contact"]["contact_id"]),
            "channel": "phone", "campaign_id": "fixture-campaign", "template_id": "fixture-template", "content_sha256": CONTENT,
            "expected_contact_revision": 1, "script_policy_version": policy, "recipient_timezone": "Australia/Brisbane"}
    denied = client.post("/v1/action-intents", json=body, headers=headers(service, "unassigned-operator"))
    assert denied.status_code == 404, denied.text
    response = client.post("/v1/action-intents", json=body, headers=headers(service))
    assert response.status_code == 201, response.text
    with transaction(settings) as c:
        c.execute("DELETE FROM worklist_assignment WHERE worklist_id=%s", (worklist["worklist_id"],))
    result = client.post(f"/v1/action-intents/{response.json()['intent_id']}/consume", json={"dispatch_id": str(uuid4()), "content_sha256": CONTENT}, headers=headers(service))
    assert result.status_code == 404, result.text


def test_activity_binding_and_correction_chain(settings, service):
    with transaction(settings) as c:
        seed_policy(c, service)
        seed_contact(c, service)
        now = service.now(c)
        worklist = build_worklist(c, service, now.date()-timedelta(days=now.weekday()))
        outsider = seed_contact(c, service)
    client = TestClient(create_app(settings))
    body = {"activity_id": str(uuid4()), "worklist_id": str(worklist["worklist_id"]), "lead_id": str(outsider["lead"]["lead_id"]),
            "category": "research", "started_at": now.isoformat(), "ended_at": now.isoformat()}
    assert client.post("/v1/operator-activities", json=body, headers=headers(service)).status_code == 404
    body["lead_id"] = None
    assert client.post("/v1/operator-activities", json=body, headers=headers(service)).status_code == 201
    corrected = {**body, "activity_id": str(uuid4()), "correction_of": body["activity_id"]}
    assert client.post("/v1/operator-activities", json=corrected, headers=headers(service)).status_code == 201
    branched = {**corrected, "activity_id": str(uuid4())}
    assert client.post("/v1/operator-activities", json=branched, headers=headers(service)).status_code == 409
