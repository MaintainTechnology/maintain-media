"""Regression evidence for control-review-1, at real PostgreSQL control boundaries."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb

from abr_engine.compliance.keys import KeyStore, load_keys
from abr_engine.compliance.wash import create_batch, import_receipt
from abr_engine.config import Settings
from abr_engine.control.service import DomainError, Service, digest
from abr_engine.enrich.budget import BudgetError, reserve, upper_micro_aud


def policy(db, service):
    now = service.now(db)
    version = "review-regression-" + uuid4().hex
    settings = {
        "holiday_calendar": {
            "from": (now - timedelta(days=2)).date().isoformat(),
            "to": (now + timedelta(days=100)).date().isoformat(),
            "localities": ["Brisbane"],
            "holidays": [],
            "evidence_ref": "synthetic-reviewed-calendar",
        }
    }
    db.execute(
        "INSERT INTO policy(version,state,scope,evidence_ref,actor_id,approved_at,expires_at,settings) "
        "VALUES(%s,'approved','collection','synthetic-policy','reviewer',%s,%s,%s)",
        (version, now, now + timedelta(days=90), Jsonb(settings)),
    )
    return version


def lead_identity(db, service, *, fields=None):
    alias = str(1000000 + uuid4().int % 8999999)
    lead = service.create_lead(
        db,
        name="Synthetic Control Review",
        source="qbcc",
        alias=alias,
        state="QLD",
        postcode="4000",
        tier="A",
        fields=fields or {},
    )
    now = service.now(db)
    identity = service.identity(
        db,
        {
            "lead_id": lead["lead_id"],
            "expected_revision": lead["revision"],
            "registrable_domain": "example.com",
            "assessment": "approved",
            "method": "exact_identifier",
            "evidence_refs": {
                "source_identifier": alias,
                "page_identifier": alias,
                "page_url": "https://example.com/",
                "html": f"<p>QBCC {alias}</p>",
                "captured_at": now.isoformat(),
                "references": ["synthetic-register", "synthetic-capture"],
            },
            "reason": "Exact synthetic source licence displayed on captured page",
        },
        "reviewer",
    )
    service.licence(
        db,
        {
            "lead_id": lead["lead_id"],
            "licence_number": alias,
            "status": "active",
            "identity_match": True,
            "evidence_ref": "synthetic-licence-review",
            "reviewed_at": now,
        },
        "reviewer",
    )
    return lead, identity


def contact_args(db, service, lead, identity, *, channel="email", value=None):
    now = service.now(db)
    value = value or "candidate-" + uuid4().hex + "@example.com"
    html = f"<html><h1>Synthetic business</h1><p>{value}</p></html>"
    return {
        "lead_id": lead["lead_id"],
        "channel": channel,
        "value": value,
        "identity_id": identity["identity_id"],
        "source_url": "https://example.com/contact",
        "excerpt": value,
        "actor": "reviewer",
        "verification": "deliverable",
        "verified_at": now,
        "capture": {
            "html": html,
            "captured_at": now,
            "collector_version": "fixture-v1",
            "robots_result": "allowed",
            "terms_scope": "home/contact/terms inspected; policy reviewed",
            "method": "static",
        },
    }


def seeded_contact(db, service, *, channel="email", value=None, fields=None):
    version = policy(db, service)
    lead, identity = lead_identity(db, service, fields=fields)
    args = contact_args(db, service, lead, identity, channel=channel, value=value)
    contact = service.add_contact(db, **args)
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
    db.execute("SET CONSTRAINTS ALL DEFERRED")
    return lead, contact, version, args


def passing_express(db, service, contact):
    return service.basis(
        db,
        {
            "contact_id": contact["contact_id"],
            "channel": "email",
            "expected_revision": contact["revision"],
            "basis_type": "express",
            "assessment_state": "pass",
            "evidence_provenance_id": contact["first_provenance_id"],
            "express_scope": "Synthetic marketing email permission",
            "express_evidence": {
                "source_ref": "synthetic-consent-record",
                "consented_at": service.now(db).isoformat(),
                "campaign_ids": ["fixture-campaign"],
                "withdrawal_state": "active",
            },
            "reason": "Recorded express permission source and scope",
        },
        "reviewer",
    )


def wash_clear(db, service, value):
    batch = create_batch(db, service, [value])
    records = [{"phone": value, "result": "clear", "washed_at": service.now(db).isoformat()}]
    receipt = {
        "format": "maintain-fixture-wash-v1",
        "account": "synthetic-manual-wash",
        "batch_digest": batch["digest"],
        "records_digest": digest(records),
        "count": 1,
    }
    import_receipt(db, service, batch["batch_id"], records, receipt, "operator")


def test_express_pass_without_scope_rejected_at_service_boundary(db, service):
    _, contact, _, _ = seeded_contact(db, service)
    with pytest.raises((DomainError, psycopg.errors.CheckViolation)), db.transaction():
        service.basis(
            db,
            {
                "contact_id": contact["contact_id"],
                "channel": "email",
                "expected_revision": contact["revision"],
                "basis_type": "express",
                "assessment_state": "pass",
                "evidence_provenance_id": contact["first_provenance_id"],
                "reason": "Missing express scope",
            },
            "reviewer",
        )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM contact_basis WHERE contact_id=%s", (contact["contact_id"],)
        ).fetchone()["n"]
        == 0
    )


@pytest.mark.parametrize("kind", ["inferred", "express"])
def test_sql_null_required_basis_cannot_commit(db, service, kind):
    _, contact, version, _ = seeded_contact(db, service)
    now = service.now(db)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            "INSERT INTO contact_basis(basis_id,contact_id,channel,state,basis_type,provenance_id,limbs,express_scope,reason,actor_id,policy_version,assessed_at,expires_at) "
            "VALUES(%s,%s,'email','pass',%s,%s,NULL,NULL,'Missing evidence','reviewer',%s,%s,%s)",
            (
                uuid4(),
                contact["contact_id"],
                kind,
                contact["first_provenance_id"],
                version,
                now,
                now + timedelta(days=30),
            ),
        )


def test_valid_express_pass_without_inferred_limbs_allows_candidate(db, service):
    _, contact, _, _ = seeded_contact(db, service)
    passing_express(db, service, contact)
    gate = service.gate(db, contact["contact_id"])
    assert gate["allowed"], gate["reason_codes"]


@pytest.mark.parametrize(
    "case", ["missing", "future", "withdrawn", "unknown", "empty_source", "empty_campaigns"]
)
def test_express_pass_requires_current_explicit_consent_evidence(db, service, case):
    _, contact, _, _ = seeded_contact(db, service)
    now = service.now(db)
    evidence = {
        "source_ref": "synthetic-consent-record",
        "consented_at": now.isoformat(),
        "campaign_ids": ["fixture-campaign"],
        "withdrawal_state": "active",
    }
    if case == "future":
        evidence["consented_at"] = (now + timedelta(days=1)).isoformat()
    elif case in {"withdrawn", "unknown"}:
        evidence["withdrawal_state"] = case
    elif case == "empty_source":
        evidence["source_ref"] = ""
    elif case == "empty_campaigns":
        evidence["campaign_ids"] = []
    data = {
        "contact_id": contact["contact_id"],
        "channel": "email",
        "expected_revision": contact["revision"],
        "basis_type": "express",
        "assessment_state": "pass",
        "evidence_provenance_id": contact["first_provenance_id"],
        "express_scope": "Synthetic marketing email permission",
        "reason": "Incomplete consent evidence",
    }
    if case != "missing":
        data["express_evidence"] = evidence
    with pytest.raises((DomainError, psycopg.errors.CheckViolation)), db.transaction():
        service.basis(db, data, "reviewer")
    assert not service.gate(db, contact["contact_id"])["allowed"]


@pytest.mark.parametrize("campaign,allowed", [("fixture-campaign", True), ("unrelated-campaign", False)])
def test_express_consent_scope_rechecked_for_exact_action_campaign(db, service, campaign, allowed):
    lead, contact, version, _ = seeded_contact(db, service)
    passing_express(db, service, contact)
    current = service.contact(db, contact["contact_id"])
    content_hash = hashlib.sha256(b"synthetic-approved-template").hexdigest()
    db.execute(
        "UPDATE policy SET settings=settings || %s WHERE version=%s",
        (
            Jsonb(
                {
                    "approved_content": {
                        "fixture-campaign:fixture-template": content_hash,
                        "unrelated-campaign:fixture-template": content_hash,
                    }
                }
            ),
            version,
        ),
    )
    assessment_id = uuid4()
    now = service.now(db)
    db.execute(
        "INSERT INTO relevance_assessment(assessment_id,contact_id,channel,campaign_id,template_id,content_sha256,policy_version,state,role_evidence_id,reason,actor_id,assessed_at,expires_at) "
        "VALUES(%s,%s,'email',%s,'fixture-template',%s,%s,'pass',%s,'Synthetic message review','reviewer',%s,%s)",
        (
            assessment_id,
            contact["contact_id"],
            campaign,
            content_hash,
            version,
            contact["first_provenance_id"],
            now,
            now + timedelta(hours=1),
        ),
    )
    gate = service.gate(
        db,
        contact["contact_id"],
        action={
            "lead_id": lead["lead_id"],
            "contact_id": contact["contact_id"],
            "channel": "email",
            "campaign_id": campaign,
            "template_id": "fixture-template",
            "content_sha256": content_hash,
            "relevance_assessment_id": assessment_id,
            "expected_contact_revision": current["revision"],
        },
    )
    assert gate["allowed"] is allowed, gate["reason_codes"]
    if not allowed:
        assert any(
            "SCOPE" in reason or "CAMPAIGN" in reason or "EXPRESS" in reason
            for reason in gate["reason_codes"]
        )


@pytest.mark.parametrize("change", [{}, {"robots_result": "denied"}, {"terms_scope": ""}])
def test_incomplete_capture_never_creates_contact(db, service, change):
    lead, identity = lead_identity(db, service)
    args = contact_args(db, service, lead, identity)
    args["capture"] = (args["capture"] | change) if change else {}
    with pytest.raises(DomainError), db.transaction():
        service.add_contact(db, **args)
    assert (
        db.execute(
            "SELECT count(*) AS n FROM contact_record WHERE lead_id=%s", (lead["lead_id"],)
        ).fetchone()["n"]
        == 0
    )


def test_capture_retains_real_full_content_digest_and_ciphertext(db, service):
    _, contact, _, args = seeded_contact(db, service)
    evidence = db.execute(
        "SELECT * FROM collection_provenance WHERE provenance_id=%s", (contact["first_provenance_id"],)
    ).fetchone()
    assert service.keys.decrypt(evidence["encrypted_capture"]) == args["capture"]["html"]
    assert evidence["content_sha256"] == hashlib.sha256(args["capture"]["html"].encode()).hexdigest()
    assert evidence["content_sha256"] != hashlib.sha256(args["excerpt"].encode()).hexdigest()
    assert evidence["terms_scope"] == args["capture"]["terms_scope"]


def test_closed_live_collection_gate_blocks_before_contact_write(db, service, tmp_path):
    lead, identity = lead_identity(db, service)
    args = contact_args(db, service, lead, identity)
    live = Service(Settings(mode="pilot", key_file=tmp_path / "separate-keys.enc"), service.keys)
    with pytest.raises(DomainError, match="COLLECTION_GATE_CLOSED"), db.transaction():
        live.add_contact(db, **args)
    assert (
        db.execute(
            "SELECT count(*) AS n FROM contact_record WHERE lead_id=%s", (lead["lead_id"],)
        ).fetchone()["n"]
        == 0
    )


def test_wrong_domain_capture_cannot_satisfy_provenance(db, service):
    lead, identity = lead_identity(db, service)
    args = contact_args(db, service, lead, identity) | {"source_url": "https://unrelated.net/contact"}
    with pytest.raises((DomainError, psycopg.errors.CheckViolation)), db.transaction():
        service.add_contact(db, **args)


def test_endpoint_only_optout_schedules_each_shared_remote_group(db, service):
    value = "shared-" + uuid4().hex + "@example.com"
    first, c1, _, _ = seeded_contact(db, service, value=value)
    second, c2, _, _ = seeded_contact(db, service, value=value)
    groups = {first["group_id"], second["group_id"]}
    for group in groups:
        db.execute(
            "INSERT INTO crm_identity(location_id,group_id,remote_id) VALUES('synthetic-location',%s,%s)",
            (group, uuid4().hex),
        )
    service.suppress(
        db,
        {"endpoint": value, "channel": "email", "reason": "unsubscribe", "source": "synthetic-request"},
        "operator",
        uuid4(),
    )
    assert not service.gate(db, c1["contact_id"])["allowed"]
    assert not service.gate(db, c2["contact_id"])["allowed"]
    propagated = {
        r["group_id"]
        for r in db.execute("SELECT group_id FROM propagation_outbox WHERE state='pending'").fetchall()
    }
    scheduled = {
        r["group_id"]
        for r in db.execute("SELECT group_id FROM deletion_job WHERE state='pending'").fetchall()
    }
    assert groups <= propagated
    assert groups <= scheduled
    # Endpoint reuse never grants authority to merge these unrelated businesses.
    assert (
        db.execute(
            "SELECT count(*) AS n FROM business_group WHERE group_id=ANY(%s)", (list(groups),)
        ).fetchone()["n"]
        == 2
    )


def test_unknown_phone_timezone_cannot_export_even_with_current_wash(db, service):
    _, contact, _, _ = seeded_contact(db, service, channel="mobile", value="0412 345 678")
    wash_clear(db, service, "0412 345 678")
    gate = service.gate(db, contact["contact_id"])
    assert not gate["allowed"]
    assert any("TIMEZONE" in reason or "LOCALITY" in reason for reason in gate["reason_codes"])


def test_confirmed_phone_candidate_with_calendar_and_wash_allowed(db, service):
    _, contact, _, _ = seeded_contact(
        db,
        service,
        channel="mobile",
        value="0412 345 678",
        fields={
            "recipient_timezone": "Australia/Brisbane",
            "locality": "Brisbane",
            "timezone_reviewed": True,
        },
    )
    wash_clear(db, service, "0412 345 678")
    gate = service.gate(db, contact["contact_id"])
    assert gate["allowed"], gate["reason_codes"]


def test_nonempty_but_invalid_iana_timezone_is_still_blocked(db, service):
    _, contact, _, _ = seeded_contact(
        db,
        service,
        channel="mobile",
        value="0412 345 678",
        fields={"recipient_timezone": "Not/AnIanaZone", "locality": "Brisbane", "timezone_reviewed": True},
    )
    wash_clear(db, service, "0412 345 678")
    gate = service.gate(db, contact["contact_id"])
    assert not gate["allowed"]
    assert any("TIMEZONE" in reason for reason in gate["reason_codes"])


def test_calling_calendar_invalid_dates_cannot_masquerade_as_coverage(service):
    lead = {
        "fields": {
            "recipient_timezone": "Australia/Brisbane",
            "locality": "Brisbane",
            "timezone_reviewed": True,
        }
    }
    invalid = {
        "settings": {
            "holiday_calendar": {
                "from": "0000",
                "to": "9999",
                "localities": ["Brisbane"],
                "holidays": [],
                "evidence_ref": "synthetic-calendar",
            }
        }
    }
    reasons = service.calling_reasons(
        lead, invalid, {"recipient_timezone": "Australia/Brisbane"}, datetime(2026, 9, 8, tzinfo=UTC)
    )
    assert reasons
    assert any("CALENDAR" in reason or "HOLIDAY" in reason for reason in reasons)


def test_retention_override_cannot_delete_suppression_ledger(db, service):
    service.suppress(
        db,
        {
            "endpoint": "erased@example.com",
            "channel": "email",
            "reason": "unsubscribe",
            "source": "synthetic-request",
        },
        "operator",
        uuid4(),
    )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SET LOCAL abr.retention_delete='on'")
        db.execute("DELETE FROM suppression_event WHERE reason='unsubscribe'")


@pytest.mark.parametrize("references", [["one-reference"], ["same", "same"], "truthy-string"])
def test_identity_two_attributes_require_distinct_reference_objects(db, service, references):
    lead = service.create_lead(db, name="Synthetic", source="qbcc", alias=str(uuid4().int % 10000000))
    with pytest.raises(DomainError), db.transaction():
        service.identity(
            db,
            {
                "lead_id": lead["lead_id"],
                "expected_revision": lead["revision"],
                "registrable_domain": "example.com",
                "assessment": "approved",
                "method": "reviewed_attributes",
                "evidence_refs": {"name_match": True, "address_match": True, "references": references},
                "reason": "Insufficient independent corroboration",
            },
            "reviewer",
        )


@pytest.mark.parametrize(
    "capture",
    [
        {},
        {"page_url": "https://unrelated.net/", "html": "<p>QBCC 9999991</p>"},
        {"page_url": "https://example.com/", "html": "<script>9999991</script>"},
    ],
)
def test_exact_identity_requires_real_identifier_in_matching_domain_capture(db, service, capture):
    lead = service.create_lead(db, name="Synthetic", source="qbcc", alias="9999991")
    evidence = {
        "source_identifier": "9999991",
        "page_identifier": "9999991",
        "captured_at": service.now(db).isoformat(),
    } | capture
    with pytest.raises(DomainError), db.transaction():
        service.identity(
            db,
            {
                "lead_id": lead["lead_id"],
                "expected_revision": lead["revision"],
                "registrable_domain": "example.com",
                "assessment": "approved",
                "method": "exact_identifier",
                "evidence_refs": evidence,
                "reason": "Exact identifier has no matching captured page",
            },
            "reviewer",
        )


def tariff(now):
    return {
        "version": "synthetic-v1",
        "currency": "AUD",
        "fx_date": now.date().isoformat(),
        "native_upper_bound": "1",
        "fx": "1",
        "tax_rate": "0.1",
    }


def test_budget_rejects_understated_amount_and_missing_price(db, service):
    now = service.now(db)
    with pytest.raises(BudgetError), db.transaction():
        reserve(db, operation_id=uuid4(), now=now, amount=0, tariff=tariff(now))
    with pytest.raises(BudgetError), db.transaction():
        reserve(
            db,
            operation_id=uuid4(),
            now=now,
            amount=0,
            tariff={"version": "v1", "currency": "AUD", "fx_date": now.date().isoformat()},
        )
    assert db.execute("SELECT count(*) AS n FROM budget_reservation").fetchone()["n"] == 0


def test_budget_valid_tariff_has_positive_reservation(db, service):
    now = service.now(db)
    amount = upper_micro_aud("1", "1", "0.1")
    receipt = reserve(db, operation_id=uuid4(), now=now, amount=amount, tariff=tariff(now))
    assert receipt["amount"] == 1_210_000


def new_keys(*, wrapping_key=None):
    return KeyStore(Fernet.generate_key(), {1: b"L" * 32}, signing_key="S" * 40, wrapping_key=wrapping_key)


def test_short_and_reused_key_material_rejected():
    with pytest.raises(ValueError, match="256-bit"):
        KeyStore(Fernet.generate_key(), {1: b"x"}, signing_key="S" * 40)
    enc = Fernet.generate_key()
    with pytest.raises(ValueError, match="separate"):
        KeyStore(enc, {1: base64.urlsafe_b64decode(enc)}, signing_key="S" * 40)
    with pytest.raises(ValueError, match="Active key"):
        KeyStore(enc, {2: b"L" * 32}, active_version=1, signing_key="S" * 40)


def test_encrypted_key_rotation_survives_reload_and_prior_is_lookup_only(tmp_path):
    wrapping = Fernet.generate_key()
    store = new_keys(wrapping_key=wrapping)
    path = tmp_path / "key-store.enc"
    store.save(path)
    old_token = store.token("email", "synthetic@example.com")
    store.rotate(2, b"N" * 32)
    loaded = load_keys(Settings(mode="pilot", key_file=path), wrapping_key=wrapping)
    assert loaded.active_version == 2
    assert (1, old_token) in loaded.matches("email", "synthetic@example.com")
    assert loaded.token("email", "synthetic@example.com") != old_token
    with pytest.raises(ValueError, match="lookup-only"):
        loaded.token("email", "synthetic@example.com", 1)
    assert b"lookup_keys" not in path.read_bytes() and store.encryption_key not in path.read_bytes()


def test_stale_key_store_writer_does_not_overwrite_rotation(tmp_path):
    wrapping = Fernet.generate_key()
    store = new_keys(wrapping_key=wrapping)
    path = tmp_path / "key-store.enc"
    store.save(path)
    stale = load_keys(Settings(mode="pilot", key_file=path), wrapping_key=wrapping)
    store.rotate(2, b"N" * 32)
    with pytest.raises(ValueError, match="changed"):
        stale.rotate(3, b"Z" * 32)
    assert stale.active_version == 1 and 3 not in stale.lookup_keys
    assert load_keys(Settings(mode="pilot", key_file=path), wrapping_key=wrapping).active_version == 2


def test_live_plaintext_key_store_is_rejected(tmp_path):
    path = tmp_path / "unwrapped.json"
    path.write_text('{"encryption_key":"synthetic-unwrapped"}')
    with pytest.raises(ValueError, match="encrypted envelope"):
        load_keys(Settings(mode="pilot", key_file=path), wrapping_key=Fernet.generate_key())


def test_retirement_of_unused_prior_key_persists(db, tmp_path):
    wrapping = Fernet.generate_key()
    store = new_keys(wrapping_key=wrapping)
    path = tmp_path / "key-store.enc"
    store.save(path)
    store.rotate(2, b"N" * 32, conn=db)
    store.retire(1, db)
    assert set(load_keys(Settings(mode="pilot", key_file=path), wrapping_key=wrapping).lookup_keys) == {2}


def test_missing_retained_key_freezes_before_future_source_matching(db, service):
    service.suppress(
        db,
        {
            "endpoint": "erased@example.com",
            "channel": "email",
            "reason": "unsubscribe",
            "source": "synthetic-request",
        },
        "operator",
        uuid4(),
    )
    incomplete = KeyStore(Fernet.generate_key(), {2: b"N" * 32}, active_version=2, signing_key="S" * 40)
    with pytest.raises(ValueError, match="Authority frozen"):
        incomplete.validate_dependencies(db)
    assert incomplete.compromised
    incomplete_service = Service(service.settings, incomplete)
    with pytest.raises(ValueError, match="Authority frozen"):
        incomplete_service.create_lead(db, name="Future synthetic", source="qbcc", alias="9999997")


def test_retained_suppression_key_cannot_be_retired_after_rotation(db, service):
    service.suppress(
        db,
        {
            "endpoint": "erased@example.com",
            "channel": "email",
            "reason": "unsubscribe",
            "source": "synthetic-request",
        },
        "operator",
        uuid4(),
    )
    old_tokens = service.keys.matches("email", "erased@example.com")
    service.keys.rotate(2, b"N" * 32, conn=db)
    with pytest.raises(ValueError, match="depend"):
        service.keys.retire(1, db)
    assert set(old_tokens) <= set(service.keys.matches("email", "erased@example.com"))


def test_same_version_replacement_material_cannot_silently_lose_optout(db, service):
    service.suppress(
        db,
        {
            "endpoint": "erased@example.com",
            "channel": "email",
            "reason": "unsubscribe",
            "source": "synthetic-request",
        },
        "operator",
        uuid4(),
    )
    changed = KeyStore(Fernet.generate_key(), {1: b"X" * 32}, signing_key="S" * 40)
    with pytest.raises(ValueError, match="known version"):
        changed.validate_dependencies(db)
    assert changed.compromised
