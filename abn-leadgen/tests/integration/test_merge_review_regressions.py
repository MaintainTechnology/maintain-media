"""Independent merge review: actual PostgreSQL, no remote sends or fabricated receipts."""
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest

from abr_engine.compliance.retention import erase_profile, export_ledger, replay_ledger, restore_quarantine
from abr_engine.control.service import DomainError
from abr_engine.export.crm import approve
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.qualify.identity import merge_groups


def pair(db, service):
    seed_policy(db, service)
    return (seed_contact(db, service, alias="11223344"), seed_contact(db, service, alias="22334455"))


def merge(db, service, source, target, refs=None):
    a = service.lead(db, source["lead"]["lead_id"])
    b = service.lead(db, target["lead"]["lead_id"])
    return merge_groups(db, service, {
        "source_lead_id": a["lead_id"], "target_lead_id": b["lead_id"],
        "source_revision": a["revision"], "target_revision": b["revision"],
        "evidence_refs": refs if refs is not None else ["registry-record", "reviewed-address"],
        "reason": "Reviewed corroborating source records",
    }, "independent-reviewer")


@pytest.mark.parametrize("reverse", [False, True])
def test_canonical_identity_and_licence_accept_preserved_family_alias(db, service, reverse):
    a, b = pair(db, service)
    source, target, alias = (b, a, "22334455") if reverse else (a, b, "11223344")
    merge(db, service, source, target)
    canonical = service.create_lead(db, name="Same reviewed business", source="qbcc", alias=alias)
    assert canonical["lead_id"] == target["lead"]["lead_id"]
    now = service.now(db)
    service.identity(db, {"lead_id": canonical["lead_id"], "expected_revision": canonical["revision"],
        "registrable_domain": "example.com", "assessment": "approved", "method": "exact_identifier",
        "evidence_refs": {"source_identifier": alias, "page_identifier": alias,
            "html": f"<p>QBCC licence {alias}</p>", "page_url": "https://example.com/",
            "captured_at": now.isoformat()}, "reason": "Fresh exact source alias review"}, "reviewer")
    service.licence(db, {"lead_id": canonical["lead_id"], "licence_number": alias, "status": "active",
        "identity_match": True, "evidence_ref": "new-source-licence-review", "reviewed_at": now}, "reviewer")
    assert db.execute("SELECT group_id FROM lead_source_link WHERE encrypted_identifier=%s",
        (db.execute("SELECT encrypted_identifier FROM lead_source_link WHERE group_id=%s",
        (source["lead"]["group_id"],)).fetchone()["encrypted_identifier"],)).fetchone()["group_id"] == source["lead"]["group_id"]


@pytest.mark.parametrize("refs", [["", " "], ["same", " same "]])
def test_merge_requires_distinct_nonblank_evidence(db, service, refs):
    a, b = pair(db, service)
    with pytest.raises(DomainError, match="MERGE_CORROBORATION_REQUIRED"):
        merge(db, service, a, b, refs)


@pytest.mark.parametrize("reverse", [False, True])
def test_erased_merged_member_preserves_future_business_and_endpoint_stops(db, service, reverse):
    a, b = pair(db, service)
    source, target = (b, a) if reverse else (a, b)
    merge(db, service, source, target)
    service.suppress(db, {"lead_id": target["lead"]["lead_id"], "reason": "unsubscribe", "source": "fixture"}, "operator", uuid4())
    erase_profile(db, service, source["lead"]["group_id"])
    assert service.canonical_group(db, source["lead"]["group_id"]) == target["lead"]["group_id"]
    for alias in ("11223344", "22334455"):
        with pytest.raises(DomainError, match="SUPPRESSED_SOURCE_IDENTITY"):
            service.create_lead(db, name="New name", source="qbcc", alias=alias)
    for item in (a, b):
        endpoint = service.keys.decrypt(item["contact"]["encrypted_value"])
        assert "SUPPRESSED_UNSUBSCRIBE" in service.restricted(db, uuid4(), service.keys.matches("email", endpoint))
    # Newly discovered endpoints on the canonical business remain suppressed by the family.
    assert "SUPPRESSED_UNSUBSCRIBE" in service.restricted(db, target["lead"]["group_id"], service.keys.matches("email", "new@example.com"))


def test_latest_ledger_restores_merge_before_matching_source_alias(db, service):
    a, b = pair(db, service)
    class OldBackup(Exception):
        pass
    with pytest.raises(OldBackup), db.transaction():
        merge(db, service, a, b)
        service.suppress(db, {"lead_id": b["lead"]["lead_id"], "reason": "unsubscribe", "source": "fixture"}, "operator", uuid4())
        encrypted = export_ledger(db, service)
        payload = json.loads(service.keys.decrypt(encrypted))
        raise OldBackup
    assert service.canonical_group(db, a["lead"]["group_id"]) == a["lead"]["group_id"]
    restore_quarantine(db)
    replay_ledger(db, service, encrypted, expected_digest=hashlib.sha256(encrypted.encode()).hexdigest(), latest_watermark=payload["exported_at"])
    assert service.canonical_group(db, a["lead"]["group_id"]) == b["lead"]["group_id"]
    for alias in ("11223344", "22334455"):
        with pytest.raises(DomainError, match="SUPPRESSED_SOURCE_IDENTITY"):
            service.create_lead(db, name="Restored alias", source="qbcc", alias=alias)
    assert db.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()["value"] is True


def test_merge_invalidates_pending_crm_on_both_members(db, service):
    a, b = pair(db, service)
    today = service.now(db).date()
    build_worklist(db, service, today - timedelta(days=today.weekday()))
    rows = db.execute("SELECT row_id,version FROM worklist_row").fetchall()
    assert len(rows) == 2
    for row in rows:
        approve(db, service, {"row_id": row["row_id"], "expected_version": row["version"], "decision": "approve"}, "reviewer")
    merge(db, service, a, b)
    assert {row["state"] for row in db.execute("SELECT state FROM crm_outbox").fetchall()} == {"blocked"}


@pytest.mark.parametrize("state", ["inflight", "uncertain"])
def test_merge_rejects_dispatched_crm_without_changing_graph(db, service, state):
    a, b = pair(db, service)
    today = service.now(db).date()
    build_worklist(db, service, today - timedelta(days=today.weekday()))
    row = db.execute("SELECT row_id,version FROM worklist_row WHERE lead_id=%s", (a["lead"]["lead_id"],)).fetchone()
    approve(db, service, {"row_id": row["row_id"], "expected_version": row["version"], "decision": "approve"}, "reviewer")
    db.execute("UPDATE crm_outbox SET state=%s", (state,))
    with pytest.raises(DomainError, match="REMOTE_MERGE_RECONCILIATION_REQUIRED"):
        merge(db, service, a, b)
    assert service.canonical_group(db, a["lead"]["group_id"]) == a["lead"]["group_id"]
