from uuid import uuid4

from fastapi.testclient import TestClient

from abr_engine.control.api import create_app
from abr_engine.control.auth import fixture_token
from abr_engine.db import transaction
from abr_engine.qualify.identity import merge_groups


def test_resolving_family_cancellation_never_reactivates_merged_source(settings, service):
    with transaction(settings) as conn:
        a = service.create_lead(conn, name="Old source", source="abr", alias="51824753556")
        b = service.create_lead(conn, name="Canonical", source="qbcc", alias="980001")
        merge_groups(conn, service, {"source_lead_id": a["lead_id"], "target_lead_id": b["lead_id"],
            "source_revision": a["revision"], "target_revision": b["revision"],
            "evidence_refs": ["source-register", "reviewed-address"], "reason": "Reviewed same business"}, "reviewer")
        service.suppress(conn, {"lead_id": a["lead_id"], "reason": "cancellation", "source": "registry"}, "fixture", uuid4())
        events = conn.execute("SELECT event_id FROM suppression_event WHERE reason='cancellation' AND action='add'").fetchall()
        content, snapshot, positive = uuid4(), uuid4(), uuid4()
        conn.execute("INSERT INTO source_content VALUES(%s,'abr',%s,'fixture','fixture','fixture')", (content, uuid4().hex))
        conn.execute("INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,'abr',%s,0,'{}','committed')", (snapshot, content))
        conn.execute("INSERT INTO abr_event VALUES(%s,%s,'51824753556','abn_reactivated','{}',clock_timestamp())", (positive, snapshot))
    client = TestClient(create_app(settings))
    for event in events:
        response = client.post("/v1/cancellation-resolutions", json={"lead_id": str(a["lead_id"]),
            "cancellation_event_id": str(event["event_id"]), "positive_reactivation_evidence_ref": str(positive),
            "reason": "Reviewed observed reactivation"}, headers={"Authorization": "Bearer " + fixture_token(service),
                "X-Request-ID": str(uuid4()), "Idempotency-Key": str(uuid4())})
        assert response.status_code == 201, response.text
    assert response.json()["remaining_reasons"] == []
    with transaction(settings) as conn:
        assert service.lead(conn, a["lead_id"])["lifecycle"] == "disqualified"
        assert service.lead(conn, b["lead_id"])["lifecycle"] == "active"
        assert service.canonical_group(conn, a["group_id"]) == b["group_id"]
