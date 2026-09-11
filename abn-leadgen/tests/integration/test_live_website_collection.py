"""Actual PostgreSQL and pinned crawler protocol, synthetic pages only."""

# ruff: noqa: F811 -- imported fixtures are intentionally injected by pytest.
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb
from test_live_qbcc import accepted, request_for  # noqa: F401
from test_qbcc_review_stage import live  # noqa: F401

from abr_engine.compliance.policy import REQUIRED_GATES, gate_reasons
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.enrich.crawl import Response
from abr_engine.live import enrichment, qbcc


@pytest.fixture
def website(settings, accepted, monkeypatch):
    config, _, keys, _ = accepted
    config = config.model_copy(update={"capabilities": {**config.capabilities, "website_collection": True, "retention": True}})
    payload = request_for(settings, config, keys)
    monkeypatch.setattr(enrichment, "transaction", lambda ignored: transaction(settings))
    with transaction(settings) as conn:
        service = Service(config, keys)
        now = service.now(conn)
        for gate in REQUIRED_GATES["website_collection"]:
            conn.execute(
                "INSERT INTO release_gate VALUES(%s,'pilot','website_collection',1,'synthetic-website-purpose-review',%s,'synthetic-test',%s,%s)",
                (gate, "c" * 64, now - timedelta(minutes=1), now + timedelta(hours=1)),
            )
        for gate in REQUIRED_GATES["retention"]:
            conn.execute(
                "INSERT INTO release_gate VALUES(%s,'pilot','retention',1,'synthetic-retention-review',%s,'synthetic-test',%s,%s)",
                (gate, "d" * 64, now - timedelta(minutes=1), now + timedelta(hours=1)),
            )
        conn.execute(
            "INSERT INTO policy VALUES('synthetic-phone-website-policy','approved','pilot','synthetic-only-review',"
            "'synthetic-owner',%s,%s,%s)",
            (now - timedelta(minutes=1), now + timedelta(hours=2), Jsonb({
                "website_collection": {"approved": True, "allowed_channels": ["mobile", "landline"],
                    "evidence_sha256": "c" * 64, "expires_at": (now + timedelta(hours=1)).isoformat()},
                "retention": {"approved": True, "schedule_version": "abr-v4-defaults",
                    "evidence_sha256": "d" * 64, "retain_selected_evidence": False, "restore_enabled": False},
            })),
        )
        lead_id = UUID(qbcc.review_qbcc_licence(conn, service, payload, "synthetic-reviewer")["lead_id"])
        lead = service.lead(conn, lead_id)
        identity = service.identity(
            conn,
            {
                "lead_id": lead_id,
                "expected_revision": lead["revision"],
                "registrable_domain": "synthetic-builder.com.au",
                "assessment": "approved",
                "method": "reviewed_attributes",
                "evidence_refs": {
                    "name_match": True,
                    "address_match": True,
                    "references": ["synthetic-source", "synthetic-page"],
                },
                "reason": "Synthetic reviewer corroboration",
            },
            "synthetic-reviewer",
        )
        request = {
            "request_id": uuid4(),
            "lead_id": lead_id,
            "identity_id": identity["identity_id"],
            "website_url": "https://synthetic-builder.com.au/",
            "terms_permit": True,
            "terms_evidence_ref": "synthetic-reviewed-permitted-terms",
            "terms_reviewed_at": service.now(conn),
        }

    class Transport:
        html = b'<html><title>Synthetic Builder</title><body><h1>Builder</h1><a href="mailto:hello@synthetic-builder.com.au">Contact email</a><a href="tel:+61731234567">Call</a></body></html>'

        def __init__(self):
            self.calls = []

        def request(self, url, selected_ip, **kwargs):
            self.calls.append(url)
            if url.endswith("robots.txt"):
                return Response(404, {}, b"", selected_ip)
            return Response(200, {"content-type": "text/html"}, self.html, selected_ip)

    transport = Transport()
    options = {
        "transport": transport,
        "resolver": lambda *args, **kwargs: ("1.1.1.1",),
        "sleep": lambda ignored: None,
    }
    return config, request, keys, transport, options


def test_real_pinned_protocol_creates_contact_evidence_without_permission(settings, website):
    config, request, keys, transport, options = website
    result = enrichment.collect_website(config, request, "synthetic-reviewer", **options)
    assert result["status"] == "complete" and result["contacts_created"] == 1
    assert len(transport.calls) == 2 and not result["export_eligible"]
    with transaction(settings) as conn:
        service = Service(config, keys)
        contacts = conn.execute("SELECT * FROM contact_record").fetchall()
        assert all(c["verification_status"] == "unverified" for c in contacts)
        assert {c["channel"] for c in contacts} == {"landline"}
        assert all(not service.gate(conn, c["contact_id"])["allowed"] for c in contacts)
        evidence = conn.execute("SELECT * FROM collection_provenance").fetchall()
        assert all(service.keys.decrypt(e["encrypted_capture"]).startswith("<html>") for e in evidence)
        # Incidental email text stays in the encrypted source page; it is never
        # extracted into a contact record, lookup token or email evidence row.
        assert all("mailto:" in service.keys.decrypt(e["encrypted_capture"]) for e in evidence)
        assert all(e["channel"] == "landline" for e in evidence)
        assert conn.execute("SELECT state FROM candidate_queue").fetchone()["state"] == "needs_review"
    assert enrichment.collect_website(config, request, "synthetic-reviewer", **options)["replayed"]
    assert len(transport.calls) == 2


def test_async_admission_persists_before_network_then_erases_request(settings, website):
    config, request, _, transport, options = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    assert job["state"] == "queued" and transport.calls == []
    with transaction(settings) as conn:
        row = conn.execute(
            "SELECT manifest FROM pipeline_run WHERE run_id=%s", (request["request_id"],)
        ).fetchone()
        assert "request_encrypted" in row["manifest"] and "website_url" not in str(row["manifest"])
    result = enrichment.execute_website_collection(config, job["job_id"], **options)
    assert result["state"] == "complete" and result["result"]["contacts_created"] == 1
    with transaction(settings) as conn:
        assert (
            "request_encrypted"
            not in conn.execute(
                "SELECT manifest FROM pipeline_run WHERE run_id=%s", (request["request_id"],)
            ).fetchone()["manifest"]
        )


@pytest.mark.parametrize("failure", ["gate", "identity", "suppression", "licence"])
def test_missing_authority_prevents_all_crawler_requests(settings, website, failure):
    config, request, keys, transport, options = website
    with transaction(settings) as conn:
        service = Service(config, keys)
        if failure == "gate":
            conn.execute("DELETE FROM release_gate WHERE gate_name='G1'")
        elif failure == "identity":
            lead = service.lead(conn, request["lead_id"])
            service.identity(
                conn,
                {
                    "lead_id": lead["lead_id"],
                    "expected_revision": lead["revision"],
                    "registrable_domain": "synthetic-builder.com.au",
                    "assessment": "rejected",
                    "method": "reviewed_attributes",
                    "evidence_refs": {},
                    "reason": "Synthetic rejection",
                },
                "synthetic-reviewer",
            )
        elif failure == "licence":
            service.licence(
                conn,
                {
                    "lead_id": request["lead_id"],
                    "licence_number": "SYNTHETIC-1",
                    "status": "unknown",
                    "identity_match": False,
                    "reviewed_at": service.now(conn),
                    "evidence_ref": "synthetic-rejection",
                },
                "synthetic-reviewer",
            )
        else:
            lead = service.lead(conn, request["lead_id"])
            service.suppress(
                conn,
                {
                    "group_id": lead["group_id"],
                    "reason": "manual",
                    "source": "synthetic",
                    "entity_only": True,
                },
                "synthetic-reviewer",
                uuid4(),
            )
    with pytest.raises(DomainError):
        enrichment.collect_website(config, request, "synthetic-reviewer", **options)
    assert transport.calls == []


def test_revocation_during_fetch_discards_every_contact(settings, website):
    config, request, _, transport, options = website
    original = transport.request

    def revoke(url, *args, **kwargs):
        response = original(url, *args, **kwargs)
        if not url.endswith("robots.txt"):
            with transaction(settings) as conn:
                conn.execute("DELETE FROM release_gate WHERE gate_name='G1'")
        return response

    transport.request = revoke
    with pytest.raises(DomainError, match="GATE_G1_CLOSED"):
        enrichment.collect_website(config, request, "synthetic-reviewer", **options)
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0


def test_stricter_site_terms_are_held_without_creating_contacts(settings, website):
    config, request, _, transport, options = website
    transport.html = b"<html><body>Automated access is prohibited. Do not scrape this website.</body></html>"
    with pytest.raises(DomainError, match="WEBSITE_COLLECTION_HELD"):
        enrichment.collect_website(config, request, "synthetic-reviewer", **options)
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0


def test_unexpected_crawler_exception_is_safe_background_failure(website, monkeypatch):
    config, request, _, _, _ = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")

    def failure(*args, **kwargs):
        raise RuntimeError("synthetic-secret-sentinel-must-not-escape")

    monkeypatch.setattr(enrichment, "collect_website", failure)
    result = enrichment.execute_website_collection(config, job["job_id"])
    assert result["state"] == "failed" and result["reason_codes"] == ["WEBSITE_COLLECTION_FAILED"]
    assert "sentinel" not in str(result)


def withdraw_website(settings):
    with transaction(settings) as conn:
        now = Service.now(conn)
        conn.execute(
            "INSERT INTO release_gate VALUES('G1','pilot','website_collection',2,'synthetic-withdrawal',%s,'synthetic-test',%s,%s)",
            ("d" * 64, now - timedelta(hours=2), now - timedelta(hours=1)),
        )


@pytest.mark.parametrize("entry", ["submit", "execute"])
@pytest.mark.parametrize("failure", ["missing", "expired", "wrong_scope", "hash", "email", "archive", "retention"])
def test_live_phone_policy_is_required_before_keys_or_network(settings, website, monkeypatch, entry, failure):
    config, request, _, transport, options = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer") if entry == "execute" else None
    with transaction(settings) as conn:
        if failure == "missing":
            conn.execute("UPDATE policy SET settings=settings-'website_collection'")
        elif failure == "expired":
            conn.execute("UPDATE policy SET settings=jsonb_set(settings,'{website_collection,expires_at}',to_jsonb((clock_timestamp()-interval '1 second')::text))")
        elif failure == "wrong_scope":
            conn.execute("UPDATE policy SET scope='production'")
        elif failure == "retention":
            conn.execute("DELETE FROM release_gate WHERE scope='retention' AND gate_name='G1'")
        else:
            path, value = {"hash": ("{website_collection,evidence_sha256}", "e" * 64),
                           "email": ("{website_collection,allowed_channels}", ["email", "mobile", "landline"]),
                           "archive": ("{retention,retain_selected_evidence}", True)}[failure]
            conn.execute("UPDATE policy SET settings=jsonb_set(settings,%s,%s)", (path, Jsonb(value)))
    def forbidden(*args, **kwargs):
        raise AssertionError("key/DNS/HTTP before current phone-only policy")
    monkeypatch.setattr(enrichment, "load_keys", forbidden)
    options["resolver"] = forbidden
    reason = "GATE_G1_CLOSED" if failure == "retention" else "WEBSITE_COLLECTION_POLICY_REQUIRED"
    if job:
        result = enrichment.execute_website_collection(config, job["job_id"], **options)
        assert result["state"] == "held" and result["reason_codes"] == [reason]
    else:
        with pytest.raises(DomainError, match=reason):
            enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    assert transport.calls == []


@pytest.mark.parametrize("change", ["withdrawn", "channels", "request_expired"])
def test_current_policy_or_job_withdrawal_during_response_discards_contacts(settings, website, change):
    config, request, _, transport, options = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    original = transport.request
    def changed(*args, **kwargs):
        response = original(*args, **kwargs)
        with transaction(settings) as conn:
            if change == "withdrawn":
                conn.execute("INSERT INTO policy SELECT 'synthetic-newer-withdrawal','withdrawn',scope,evidence_ref,actor_id,"
                             "clock_timestamp(),expires_at,settings FROM policy ORDER BY approved_at DESC LIMIT 1")
            elif change == "channels":
                conn.execute("UPDATE policy SET settings=jsonb_set(settings,'{website_collection,allowed_channels}','[\"email\"]')")
            else:
                conn.execute("UPDATE pipeline_run SET started_at=clock_timestamp()-interval '25 hours' WHERE run_id=%s", (job["job_id"],))
        return response
    transport.request = changed
    result = enrichment.execute_website_collection(config, job["job_id"], **options)
    expected = "WEBSITE_REQUEST_EXPIRED" if change == "request_expired" else "WEBSITE_COLLECTION_POLICY_REQUIRED"
    assert result["state"] == "held" and result["reason_codes"] == [expected]
    assert len(transport.calls) == 1
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0
        assert "request_encrypted" not in conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (job["job_id"],)).fetchone()["manifest"]


@pytest.mark.parametrize("settings_value", [[], None, {"website_collection": []}, {"website_collection": {}, "retention": []}])
def test_malformed_policy_json_returns_typed_hold_before_network(settings, website, settings_value):
    config, request, _, transport, _ = website
    with transaction(settings) as conn:
        conn.execute("UPDATE policy SET settings=%s", (Jsonb(settings_value),))
    with pytest.raises(DomainError, match="WEBSITE_COLLECTION_POLICY_REQUIRED"):
        enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    assert transport.calls == []


@pytest.mark.parametrize("entry", ["submit", "collect"])
@pytest.mark.parametrize("flag", ["omitted", "disabled"])
def test_qbcc_only_configuration_cannot_load_keys_or_collect_website(settings, website, monkeypatch, entry, flag):
    config, request, _, transport, options = website
    config.capabilities.pop("website_collection")
    if flag == "disabled":
        config.capabilities["website_collection"] = False

    def forbidden(*args, **kwargs):
        raise AssertionError("Website I/O attempted without website-purpose authority")

    monkeypatch.setattr(enrichment, "load_keys", forbidden)
    options["resolver"] = forbidden
    with pytest.raises(DomainError, match="CAPABILITY_DISABLED"):
        if entry == "submit":
            enrichment.submit_website_collection(config, request, "synthetic-reviewer")
        else:
            enrichment.collect_website(config, request, "synthetic-reviewer", **options)
    assert transport.calls == []
    with transaction(settings) as conn:
        assert gate_reasons(conn, config, "collection", Service.now(conn)) == []
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0


@pytest.mark.parametrize("entry", ["submit", "execute"])
@pytest.mark.parametrize("failure", ["absent", "expired", "withdrawn", "other_environment", "disabled"])
def test_website_scope_is_current_and_not_inherited_from_qbcc(settings, website, monkeypatch, entry, failure):
    config, request, _, transport, options = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer") if entry == "execute" else None
    if failure == "withdrawn":
        withdraw_website(settings)
    elif failure == "disabled":
        config.capabilities["website_collection"] = False
    else:
        with transaction(settings) as conn:
            if failure == "absent":
                conn.execute("DELETE FROM release_gate WHERE scope='website_collection'")
            elif failure == "expired":
                conn.execute("UPDATE release_gate SET approved_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE scope='website_collection' AND gate_name='G1'")
            else:
                conn.execute("UPDATE release_gate SET environment='production' WHERE scope='website_collection'")

    def forbidden(*args, **kwargs):
        raise AssertionError("Website keys/transport loaded without current website approval")

    monkeypatch.setattr(enrichment, "load_keys", forbidden)
    options["resolver"] = forbidden
    reason = "CAPABILITY_DISABLED" if failure == "disabled" else "GATE_G1_CLOSED"
    if job:
        result = enrichment.execute_website_collection(config, job["job_id"], **options)
        assert result["state"] == "held" and reason in result["reason_codes"]
        with transaction(settings) as conn:
            manifest = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (request["request_id"],)).fetchone()["manifest"]
            assert "request_encrypted" not in manifest
    else:
        with pytest.raises(DomainError, match=reason):
            enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    assert transport.calls == []
    with transaction(settings) as conn:
        assert gate_reasons(conn, config, "collection", Service.now(conn)) == []
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0


@pytest.mark.parametrize("boundary", ["dns", "response", "content", "between_requests"])
def test_website_withdrawal_at_network_boundaries_stops_next_request_and_discards_contacts(settings, website, boundary):
    config, request, _, transport, options = website
    job = enrichment.submit_website_collection(config, request, "synthetic-reviewer")
    if boundary == "dns":
        def revoke_dns(*args, **kwargs):
            withdraw_website(settings)
            return ("1.1.1.1",)
        options["resolver"] = revoke_dns
    elif boundary in ("response", "content"):
        original = transport.request
        def revoke_response(*args, **kwargs):
            response = original(*args, **kwargs)
            if boundary == "response" or not args[0].endswith("robots.txt"):
                withdraw_website(settings)
            return response
        transport.request = revoke_response
    else:
        options["sleep"] = lambda ignored: withdraw_website(settings)
    result = enrichment.execute_website_collection(config, job["job_id"], **options)
    assert result["state"] == "held" and result["reason_codes"] == ["GATE_G1_CLOSED"]
    assert len(transport.calls) == (0 if boundary == "dns" else 2 if boundary == "content" else 1)
    with transaction(settings) as conn:
        assert gate_reasons(conn, config, "collection", Service.now(conn)) == []
        assert conn.execute("SELECT count(*) n FROM contact_record").fetchone()["n"] == 0
        manifest = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s", (request["request_id"],)).fetchone()["manifest"]
        assert "request_encrypted" not in manifest
