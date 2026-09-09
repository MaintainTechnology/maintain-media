import json
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest

from abr_engine.compliance.retention import erase_profile, minimise_database_evidence
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.qualify.identity import merge_groups


def test_merge_evidence_expires_while_minimal_graph_and_holds_survive(db, service):
    now = service.now(db)
    rows = []
    for age in (91, 89, 91):
        source, target, merge = uuid4(), uuid4(), uuid4()
        db.execute("INSERT INTO business_group(group_id) VALUES(%s),(%s)", (source, target))
        db.execute("UPDATE business_group SET merged_into_group_id=%s WHERE group_id=%s", (target, source))
        db.execute("INSERT INTO group_merge(merge_id,source_group_id,target_group_id,actor_id,evidence_encrypted,reviewed_at) VALUES(%s,%s,%s,'reviewer',%s,%s)",
            (merge, source, target, service.keys.encrypt('Identifying registry references'), now-timedelta(days=age)))
        rows.append((source, target, merge))
    db.execute("INSERT INTO retention_hold VALUES(%s,'merge',%s,'reviewer','Retain scoped evidence',%s)", (uuid4(), str(rows[2][2]), now+timedelta(days=30)))
    assert minimise_database_evidence(db, service, now=now, execute=False)["merge_evidence"] == 1
    assert minimise_database_evidence(db, service, now=now, execute=True)["merge_evidence"] == 1
    for index, (source, target, merge) in enumerate(rows):
        row = db.execute("SELECT * FROM group_merge WHERE merge_id=%s", (merge,)).fetchone()
        assert bool(row["evidence_erased_at"]) == (index == 0)
        assert (row["evidence_encrypted"] is None) == (index == 0)
        assert service.canonical_group(db, source) == target
    assert minimise_database_evidence(db, service, now=now, execute=True)["merge_evidence"] == 0
    for statement in ("DELETE FROM group_merge WHERE merge_id=%s",
        "UPDATE group_merge SET evidence_encrypted='restore',evidence_erased_at=NULL WHERE merge_id=%s",
        "UPDATE group_merge SET actor_id='changed' WHERE merge_id=%s"):
        with pytest.raises(psycopg.errors.RaiseException), db.transaction():
            db.execute("SET LOCAL abr.retention_delete='on'")
            db.execute(statement, (rows[0][2],))


def test_merge_evidence_cannot_be_erased_early_or_fabricated_missing(db, service):
    source, target = uuid4(), uuid4()
    db.execute("INSERT INTO business_group(group_id) VALUES(%s),(%s)", (source, target))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO group_merge(merge_id,source_group_id,target_group_id,actor_id,evidence_encrypted) VALUES(%s,%s,%s,'reviewer',NULL)", (uuid4(), source, target))
    merge = uuid4()
    db.execute("INSERT INTO group_merge(merge_id,source_group_id,target_group_id,actor_id,evidence_encrypted) VALUES(%s,%s,%s,'reviewer','ciphertext')", (merge, source, target))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SET LOCAL abr.retention_delete='on'")
        db.execute("UPDATE group_merge SET evidence_encrypted=NULL,evidence_erased_at=clock_timestamp() WHERE merge_id=%s", (merge,))


def test_selected_profile_archive_preserves_available_merge_review(db, service):
    seed_policy(db, service)
    a, b = seed_contact(db, service), seed_contact(db, service)
    now = service.now(db)
    build_worklist(db, service, now.date()-timedelta(days=now.weekday()))
    merged = merge_groups(db, service, {"source_lead_id": a["lead"]["lead_id"], "target_lead_id": b["lead"]["lead_id"],
        "source_revision": service.lead(db, a["lead"]["lead_id"])["revision"],
        "target_revision": service.lead(db, b["lead"]["lead_id"])["revision"],
        "evidence_refs": ["reviewed-register", "reviewed-address"], "reason": "Same business"}, "reviewer")
    erase_profile(db, service, a["lead"]["group_id"])
    archive = db.execute("SELECT * FROM restricted_evidence_archive WHERE group_id=%s", (a["lead"]["group_id"],)).fetchone()
    payload = json.loads(service.keys.decrypt(archive["encrypted_payload"]))
    assert payload["merges"][0]["merge_id"] == str(merged["merge_id"])
    evidence = json.loads(service.keys.decrypt(payload["merges"][0]["evidence_encrypted"]))
    assert evidence["refs"] == ["reviewed-register", "reviewed-address"]
