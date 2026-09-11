"""Real pilot-mode retention, isolated PostgreSQL and synthetic website jobs."""
# ruff: noqa: F811
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from test_live_website_collection import accepted, live, website  # noqa: F401

from abr_engine.compliance.retention import erase_profile, minimise_database_evidence
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.live import enrichment
from abr_engine.live.dashboard import dashboard_state


@pytest.mark.parametrize("case", ["expired", "recent", "run_hold", "group_hold"])
def test_private_website_requests_expire_without_worker_but_respect_holds(settings, website, case):
    config, request, keys, transport, _ = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    with transaction(settings) as conn:
        service = Service(config, keys)
        now = service.now(conn)
        if case != "recent":
            conn.execute("UPDATE pipeline_run SET started_at=%s WHERE run_id=%s", (now-timedelta(hours=25), job["job_id"]))
        if case.endswith("hold"):
            group = service.lead(conn, request["lead_id"])["group_id"]
            kind, identifier = ("run", job["job_id"]) if case == "run_hold" else ("group", group)
            conn.execute("INSERT INTO retention_hold VALUES(%s,%s,%s,'synthetic-owner','Scoped test hold',%s)",
                         (uuid4(), kind, str(identifier), now+timedelta(days=1)))
        # Closing collection must not prevent separately approved deletion.
        service.settings = config.model_copy(update={"capabilities": {"retention": True}})
        expected = int(case == "expired")
        assert minimise_database_evidence(conn, service, now=now)["website_requests"] == expected
        result = minimise_database_evidence(conn, service, now=now, execute=True)
        assert result["website_requests"] == expected
        manifest = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (job["job_id"],)).fetchone()["manifest"]
        assert ("request_encrypted" in manifest) is not bool(expected)
        if expected:
            assert manifest["phase"] == "held" and manifest["reason_codes"] == ["WEBSITE_REQUEST_EXPIRED"]
            assert minimise_database_evidence(conn, service, now=now, execute=True)["website_requests"] == 0
    assert transport.calls == []


@pytest.mark.parametrize("held", [False, True])
def test_suppressed_profile_erasure_removes_recent_private_request_or_holds_all(settings, website, held):
    config, request, keys, transport, _ = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    with transaction(settings) as conn:
        service = Service(config, keys)
        lead = service.lead(conn, request["lead_id"])
        service.suppress(conn, {"lead_id": lead["lead_id"], "reason": "manual", "source": "synthetic"}, "synthetic-reviewer", uuid4())
        if held:
            conn.execute("INSERT INTO retention_hold VALUES(%s,'run',%s,'synthetic-owner','Scoped job hold',%s)",
                         (uuid4(), job["job_id"], service.now(conn)+timedelta(days=1)))
            with pytest.raises(DomainError, match="SCOPED_RETENTION_HOLD"):
                erase_profile(conn, service, lead["group_id"])
        else:
            erase_profile(conn, service, lead["group_id"])
        manifest = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (job["job_id"],)).fetchone()["manifest"]
        assert ("request_encrypted" in manifest) is held
        assert conn.execute("SELECT count(*) n FROM suppression_event").fetchone()["n"] > 0
        if not held:
            assert manifest["reason_codes"] == ["WEBSITE_PROFILE_ERASED"]
            assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 0
    assert transport.calls == []


@pytest.mark.parametrize("hold", [None, "contact", "provenance"])
def test_phone_pilot_selected_row_does_not_extend_capture_or_create_seven_year_archive(settings, website, hold):
    config, request, keys, _, _ = website
    with transaction(settings) as conn:
        service = Service(config, keys)
        now = service.now(conn)
        lead = service.lead(conn, request["lead_id"])
        contact = service.add_contact(conn, lead_id=lead["lead_id"], channel="landline", value="+61731234567",
            identity_id=request["identity_id"], source_url=request["website_url"], excerpt="Synthetic phone",
            actor="synthetic-reviewer", capture={"html": "<html>Synthetic phone</html>", "captured_at": now-timedelta(days=91),
                "collector_version": "synthetic-retention-test", "robots_result": "allowed", "terms_scope": "synthetic",
                "method": "synthetic-historical-capture"})
        worklist_id = uuid4()
        conn.execute("INSERT INTO worklist(worklist_id,week) VALUES(%s,%s)", (worklist_id, now.date()))
        # Historical row is synthetic setup, not an assertion of live export authority.
        conn.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,decision,selected_tier,selected_signal) "
                     "VALUES(%s,%s,%s,%s,'A','synthetic')", (uuid4(), worklist_id, lead["lead_id"], Jsonb({"contact_id": str(contact["contact_id"])})))
        if hold:
            identifier = contact["contact_id"] if hold == "contact" else contact["first_provenance_id"]
            conn.execute("INSERT INTO retention_hold VALUES(%s,%s,%s,'synthetic-owner','Scoped capture hold',%s)",
                         (uuid4(), hold, str(identifier), now+timedelta(days=1)))
            assert minimise_database_evidence(conn, service, now=now, execute=True)["page_bodies"] == 0
            assert conn.execute("SELECT encrypted_capture FROM collection_provenance").fetchone()["encrypted_capture"]
            with pytest.raises(DomainError, match="SCOPED_RETENTION_HOLD"):
                erase_profile(conn, service, lead["group_id"])
            return
        assert minimise_database_evidence(conn, service, now=now, execute=True)["page_bodies"] == 1
        assert conn.execute("SELECT encrypted_capture FROM collection_provenance").fetchone()["encrypted_capture"] is None
        erase_profile(conn, service, lead["group_id"])
        assert conn.execute("SELECT count(*) n FROM restricted_evidence_archive").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM suppression_alias").fetchone()["n"] > 0


@pytest.mark.parametrize("reviewer", [True, False])
def test_dashboard_restores_only_safe_scoped_job_and_actual_channel_policy(settings, website, reviewer):
    config, request, keys, _, _ = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    with transaction(settings) as conn:
        actor = SimpleNamespace(actor_id="synthetic-reviewer", scopes={"admin", "reviewer"} if reviewer else {"admin"})
        result = dashboard_state(conn, Service(config, keys), actor)
        assert result["website_collection_policy"]["allowed_channels"] == ["mobile", "landline"]
        saved = result["leads"][0]["website_job"]
        assert saved["job_id"] == job["job_id"] if reviewer else saved is None
        assert "request_encrypted" not in str(result) and "terms_reviewed_at" not in str(result)
