from uuid import uuid4

import pytest

from abr_engine.control.service import DomainError
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.qualify.identity import merge_groups


def merge_data(service, db, a, b):
    source, target = service.lead(db, a["lead"]["lead_id"]), service.lead(db, b["lead"]["lead_id"])
    return {"source_lead_id": source["lead_id"], "target_lead_id": target["lead_id"],
            "source_revision": source["revision"], "target_revision": target["revision"],
            "evidence_refs": ["fixture-registry-link", "fixture-reviewed-address"], "reason": "Reviewed same business"}


def test_merge_preserves_history_and_future_alias_lookup(db, service):
    seed_policy(db, service)
    a, b = seed_contact(db, service, alias="11223344"), seed_contact(db, service, alias="22334455")
    result = merge_groups(db, service, merge_data(service, db, a, b), "reviewer")
    assert result["canonical_group_id"] == b["lead"]["group_id"]
    assert not service.gate(db, a["contact"]["contact_id"])["allowed"]
    assert service.gate(db, b["contact"]["contact_id"])["allowed"]
    again = service.create_lead(db, name="Same source", source="qbcc", alias="11223344")
    assert again["lead_id"] == b["lead"]["lead_id"]
    assert db.execute("SELECT count(*) n FROM collection_provenance").fetchone()["n"] == 2


@pytest.mark.parametrize("when", ["before", "after"])
def test_merge_optout_propagates_to_every_member_and_future_alias(db, service, when):
    seed_policy(db, service)
    a, b = seed_contact(db, service, alias="11223344"), seed_contact(db, service, alias="22334455")
    def stop():
        service.suppress(db, {"lead_id": a["lead"]["lead_id"], "reason": "unsubscribe", "source": "fixture"}, "operator", uuid4())
    if when == "before":
        stop()
    merge_groups(db, service, merge_data(service, db, a, b), "reviewer")
    if when == "after":
        stop()
    for item in (a, b):
        assert "SUPPRESSED_UNSUBSCRIBE" in service.gate(db, item["contact"]["contact_id"])["reason_codes"]
        value = service.keys.decrypt(item["contact"]["encrypted_value"])
        assert service.restricted(db, uuid4(), service.keys.matches("email", value))
    with pytest.raises(DomainError, match="SUPPRESSED_SOURCE_IDENTITY"):
        service.create_lead(db, name="Suppressed", source="qbcc", alias="11223344")


def test_merge_blocks_stale_evidence_and_remote_identity(db, service):
    seed_policy(db, service)
    a, b = seed_contact(db, service), seed_contact(db, service)
    data = merge_data(service, db, a, b)
    with pytest.raises(DomainError, match="REVISION_CONFLICT"):
        merge_groups(db, service, {**data, "source_revision": 999}, "reviewer")
    with pytest.raises(DomainError, match="MERGE_CORROBORATION_REQUIRED"):
        merge_groups(db, service, {**data, "evidence_refs": ["same", "same"]}, "reviewer")
    db.execute("INSERT INTO crm_identity(location_id,group_id,remote_id) VALUES('fixture',%s,'remote')", (a["lead"]["group_id"],))
    with pytest.raises(DomainError, match="REMOTE_MERGE_RECONCILIATION_REQUIRED"):
        merge_groups(db, service, data, "reviewer")
