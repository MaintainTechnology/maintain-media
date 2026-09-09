"""Real PostgreSQL + temporary owned files; remote and backup completion stays pending."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from abr_engine.compliance.retention import (
    artifact_retention,
    erase_profile,
    export_ledger,
    minimise_database_evidence,
    preview,
    replay_ledger,
    restore_quarantine,
    retention_deadline,
    retention_run,
)
from abr_engine.control.service import DomainError, Service
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import seed_contact, seed_policy


def seed(db, service, *, selected=False, phone=False):
    seed_policy(db, service)
    record = seed_contact(db, service, alias="9999991", phone=phone)
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
    db.execute("SET CONSTRAINTS ALL DEFERRED")
    if selected:
        today = service.now(db).date()
        result = build_worklist(db, service, today - timedelta(days=today.weekday()))
        assert result["selected"] == 1
    return record


def suppress(db, service, record):
    service.suppress(
        db,
        {"lead_id": record["lead"]["lead_id"], "reason": "unsubscribe", "source": "synthetic-request"},
        "fixture-operator",
        uuid4(),
    )


def test_profile_erasure_removes_active_plaintext_and_keeps_matching_aliases(db, service):
    record = seed(db, service)
    suppress(db, service, record)
    group = record["lead"]["group_id"]
    result = erase_profile(db, service, group)
    assert result["state"] == "primary_complete" and result["external_and_backup"] == "pending"
    for table in (
        "lead_entity",
        "lead_source_link",
        "contact_record",
        "collection_provenance",
        "domain_identity",
        "contact_basis",
    ):
        assert db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
    ledger = service.keys.decrypt(export_ledger(db, service))
    assert "9999991" not in ledger and record["lead"]["display_name"] not in ledger
    service.keys.rotate(2, b"R" * 32, conn=db)
    with pytest.raises(DomainError, match="SUPPRESSED_SOURCE_IDENTITY"):
        service.create_lead(db, name="New synthetic name", source="qbcc", alias="9999991")
    assert db.execute("SELECT count(*) AS n FROM suppression_alias").fetchone()["n"] == 1
    assert db.execute("SELECT count(*) AS n FROM suppression_event").fetchone()["n"] >= 2


def test_retention_trigger_cannot_remove_optout_and_remote_state_not_completed(db, service):
    record = seed(db, service)
    group = record["lead"]["group_id"]
    db.execute(
        "INSERT INTO crm_identity(location_id,group_id,remote_id) VALUES('fixture',%s,'opaque-remote-id')",
        (group,),
    )
    suppress(db, service, record)
    erase_profile(db, service, group)
    assert (
        db.execute("SELECT state FROM deletion_job WHERE group_id=%s", (group,)).fetchone()["state"]
        == "primary_complete"
    )
    assert db.execute("SELECT 1 FROM crm_identity WHERE group_id=%s", (group,)).fetchone()
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SET LOCAL abr.retention_delete='on'")
        db.execute("DELETE FROM suppression_event")


def test_selected_archive_retains_identity_and_permission_with_original_clock(db, service):
    record = seed(db, service, selected=True)
    before = service.now(db)
    suppress(db, service, record)
    erase_profile(db, service, record["lead"]["group_id"], now=before + timedelta(days=40))
    archive = db.execute("SELECT * FROM restricted_evidence_archive").fetchone()
    evidence = json.loads(service.keys.decrypt(archive["encrypted_payload"]))
    assert evidence["identity"] and evidence["licence"] and evidence["basis"] and evidence["provenance"]
    assert {"relevance", "actions", "outcomes", "washes"} <= evidence.keys()
    assert archive["retained_until"] <= retention_deadline("selected_evidence", before)
    erase_profile(db, service, record["lead"]["group_id"], now=before + timedelta(days=41))
    assert db.execute("SELECT count(*) AS n FROM restricted_evidence_archive").fetchone()["n"] == 1


def test_scoped_hold_blocks_erasure_without_assuming_review_date_waives_it(db, service):
    record = seed(db, service)
    group = record["lead"]["group_id"]
    now = service.now(db)
    db.execute(
        "INSERT INTO retention_hold VALUES(%s,'group',%s,'fixture-owner','Scoped synthetic dispute',%s)",
        (uuid4(), str(group), now - timedelta(days=1)),
    )
    with pytest.raises(DomainError, match="SCOPED_RETENTION_HOLD"):
        erase_profile(db, service, group)
    assert service.lead(db, record["lead"]["lead_id"])


def test_direct_live_erasure_denied_even_if_caller_skips_retention_run(db, service, tmp_path):
    record = seed(db, service)
    live = Service(
        service.settings.model_copy(update={"mode": "pilot", "key_file": tmp_path / "keys.enc"}), service.keys
    )
    with pytest.raises(DomainError, match="RETENTION_POLICY_RELEASE_PENDING"):
        erase_profile(db, live, record["lead"]["group_id"])


def test_suppression_30_days_and_unworked_180_days_do_not_use_crawl_time(db, service):
    record = seed(db, service)
    now = service.now(db)
    assert preview(db, service, now) == []
    assert len(preview(db, service, now + timedelta(days=180))) == 1
    suppress(db, service, record)
    assert preview(db, service, now + timedelta(days=29)) == []
    assert len(preview(db, service, now + timedelta(days=31))) == 1


def ledger_args(db, service):
    encrypted = export_ledger(db, service)
    payload = json.loads(service.keys.decrypt(encrypted))
    return encrypted, {
        "expected_digest": hashlib.sha256(encrypted.encode()).hexdigest(),
        "latest_watermark": payload["exported_at"],
    }


def test_replay_requires_quarantine_digest_and_watermark_and_never_reopens(db, service):
    record = seed(db, service)
    encrypted, args = ledger_args(db, service)
    with pytest.raises(DomainError, match="RESTORE_MUST_BE_QUARANTINED"):
        replay_ledger(db, service, encrypted, **args)
    restore_quarantine(db)
    with pytest.raises(DomainError, match="LEDGER_DIGEST_MISMATCH"):
        replay_ledger(db, service, encrypted, **(args | {"expected_digest": "0" * 64}))
    with pytest.raises(DomainError, match="LATEST_LEDGER_WATERMARK_REQUIRED"):
        replay_ledger(db, service, encrypted, **(args | {"latest_watermark": "old"}))
    result = replay_ledger(db, service, encrypted, **args)
    assert result["outbound"] == "quarantined"
    assert (
        db.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()["value"]
        is True
    )
    assert "AUTHORITY_QUARANTINED" in service.gate(db, record["contact"]["contact_id"])["reason_codes"]


def test_restore_replays_newer_optout_into_pre_optout_state(db, service):
    record = seed(db, service)

    # Capture latest ledger within a rollback savepoint, reproducing an old backup's DB state.
    class OldBackup(Exception):
        pass

    with pytest.raises(OldBackup), db.transaction():
        suppress(db, service, record)
        encrypted, args = ledger_args(db, service)
        raise OldBackup
    assert not service.restricted(db, record["lead"]["group_id"])
    restore_quarantine(db)
    replay_ledger(db, service, encrypted, **args)
    assert service.restricted(db, record["lead"]["group_id"])
    assert (
        db.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()["value"]
        is True
    )


def test_restore_alias_conflict_fails_instead_of_silently_reconciling(db, service):
    record = seed(db, service)
    encrypted, _ = ledger_args(db, service)
    payload = json.loads(service.keys.decrypt(encrypted))
    other = str(uuid4())
    payload["groups"].append({"group_id": other, "restriction_revision": 0, "merged_into_group_id": None})
    payload["aliases"][0]["group_id"] = other
    conflicting = service.keys.encrypt(json.dumps(payload))
    restore_quarantine(db)
    with pytest.raises(DomainError, match="RESTORE_LEDGER_CONFLICT"), db.transaction():
        replay_ledger(
            db,
            service,
            conflicting,
            expected_digest=hashlib.sha256(conflicting.encode()).hexdigest(),
            latest_watermark=payload["exported_at"],
        )
    assert db.execute("SELECT count(*) AS n FROM restore_receipt").fetchone()["n"] == 0
    assert (
        db.execute("SELECT group_id FROM suppression_alias").fetchone()["group_id"]
        == record["lead"]["group_id"]
    )


@pytest.mark.parametrize("conflict", ["different_target", "cycle"])
def test_restore_rejects_conflicting_or_cyclic_merge_edges(db, service, conflict):
    record = seed(db, service)
    a, b, c = record["lead"]["group_id"], uuid4(), uuid4()
    for group in (b, c):
        db.execute("INSERT INTO business_group(group_id) VALUES(%s)", (group,))
    db.execute("UPDATE business_group SET merged_into_group_id=%s WHERE group_id=%s", (b, a))
    encrypted, _ = ledger_args(db, service)
    payload = json.loads(service.keys.decrypt(encrypted))
    for group in payload["groups"]:
        if conflict == "different_target" and group["group_id"] == str(a):
            group["merged_into_group_id"] = str(c)
        if conflict == "cycle" and group["group_id"] == str(b):
            group["merged_into_group_id"] = str(a)
    encrypted = service.keys.encrypt(json.dumps(payload))
    restore_quarantine(db)
    with pytest.raises(DomainError, match="RESTORE_LEDGER_CONFLICT"), db.transaction():
        replay_ledger(db, service, encrypted, expected_digest=hashlib.sha256(encrypted.encode()).hexdigest(),
            latest_watermark=payload["exported_at"])
    assert service.canonical_group(db, a) == b
    assert db.execute("SELECT count(*) AS n FROM restore_receipt").fetchone()["n"] == 0


def test_restore_runs_overdue_profile_deletion_before_reconciled_receipt(db, service):
    record = seed(db, service)
    db.execute(
        "UPDATE lead_entity SET last_qualifying_at=clock_timestamp()-interval '181 days' WHERE lead_id=%s",
        (record["lead"]["lead_id"],),
    )
    encrypted, args = ledger_args(db, service)
    restore_quarantine(db)
    replay_ledger(db, service, encrypted, **args)
    assert db.execute("SELECT count(*) AS n FROM lead_entity").fetchone()["n"] == 0
    assert (
        db.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()["value"]
        is True
    )


@pytest.mark.parametrize(
    "kind,days",
    [
        ("raw", 30),
        ("snapshot", 90),
        ("page", 90),
        ("backup", 35),
        ("report", 90),
        ("manifest", 90),
        ("orphan", 7),
    ],
)
def test_finite_artifact_schedule(kind, days):
    now = datetime(2026, 9, 8, tzinfo=UTC)
    assert retention_deadline(kind, now) == now + timedelta(days=days)


def test_minimal_metrics_use_calendar_months_and_unknown_kind_is_held():
    assert retention_deadline("event", datetime(2024, 2, 29, tzinfo=UTC)) == datetime(2026, 2, 28, tzinfo=UTC)
    with pytest.raises(DomainError, match="RETENTION_CLASS_UNKNOWN"):
        retention_deadline("unclassified", datetime(2026, 1, 1, tzinfo=UTC))


@pytest.mark.parametrize("erase", [False, True])
def test_enrichment_result_erasure_preserves_minimal_paid_receipt(db, service, erase):
    from abr_engine.enrich.budget import reserve, settle
    record = seed(db, service)
    now = service.now(db)
    operation, attempt = uuid4(), uuid4()
    reserved = reserve(db, operation_id=operation, now=now, amount=0, tariff={
        "version": "fixture", "fx_date": now.date().isoformat(), "currency": "AUD",
        "native_upper_bound": "0", "fx": "1", "tax_rate": "0"})
    settle(db, reserved["reservation_id"], 0, "opaque-fixture-receipt")
    candidate = db.execute("SELECT candidate_id FROM candidate_queue WHERE lead_id=%s", (record["lead"]["lead_id"],)).fetchone()["candidate_id"]
    db.execute("INSERT INTO enrichment_attempt(attempt_id,lead_id,group_id,candidate_id,state,started_at,finished_at) VALUES(%s,%s,%s,%s,'complete',%s,%s)",
        (attempt, record["lead"]["lead_id"], record["lead"]["group_id"], candidate, now - timedelta(days=91), now - timedelta(days=91)))
    db.execute("INSERT INTO enrichment_operation(operation_id,attempt_id,stage,provider_version,state,reservation_id,receipt_ref,encrypted_result,completed_at) VALUES(%s,%s,'lookup','fixture','complete',%s,'opaque-fixture-receipt',%s,%s)",
        (operation, attempt, reserved["reservation_id"], service.keys.encrypt("synthetic provider body"), now - timedelta(days=91)))
    if erase:
        erase_profile(db, service, record["lead"]["group_id"])
        retained = db.execute("SELECT * FROM enrichment_attempt WHERE attempt_id=%s", (attempt,)).fetchone()
        assert retained["lead_id"] is None and retained["candidate_id"] is None and retained["erased_at"]
    else:
        result = minimise_database_evidence(db, service, now=now, execute=True)
        assert result["enrichment_results"] == 1
    result = db.execute("SELECT * FROM enrichment_operation WHERE operation_id=%s", (operation,)).fetchone()
    assert result["encrypted_result"] is None and result["state"] == "complete"
    assert result["receipt_ref"] == "opaque-fixture-receipt" and result["reservation_id"] == reserved["reservation_id"]
    assert db.execute("SELECT state FROM budget_reservation WHERE reservation_id=%s", (reserved["reservation_id"],)).fetchone()["state"] == "settled"


def test_provenance_hold_prevents_profile_erasure_without_group_hold(db, service):
    record = seed(db, service)
    db.execute("INSERT INTO retention_hold(hold_id,object_type,object_id,owner,reason,review_at) VALUES(%s,'provenance',%s,'fixture-owner','specific evidence hold',clock_timestamp()+interval '30 days')",
        (uuid4(), str(record["contact"]["first_provenance_id"])))
    with pytest.raises(DomainError, match="SCOPED_RETENTION_HOLD"):
        erase_profile(db, service, record["lead"]["group_id"])
    assert db.execute("SELECT encrypted_capture FROM collection_provenance WHERE provenance_id=%s", (record["contact"]["first_provenance_id"],)).fetchone()["encrypted_capture"]


def test_redacted_ops_records_expire_at90days_with_scoped_holds(db, service):
    run_id = uuid4()
    db.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','complete')", (run_id,))
    now = service.now(db)
    observations, alarms = [], []
    for index, days in enumerate((91, 89, 91)):
        observation, alarm = uuid4(), uuid4()
        observations.append(observation)
        alarms.append(alarm)
        db.execute("INSERT INTO ops_observation VALUES(%s,%s,'qbcc',%s,%s,'{}')", (observation, run_id, now-timedelta(days=days), str(index)*64))
        db.execute("INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload,state) VALUES(%s,%s,'fixture',%s,'{}','delivered')", (alarm, run_id, str(index)))
        db.execute("INSERT INTO ops_mock_delivery VALUES(%s,%s,'{}')", (alarm, now-timedelta(days=days)))
    for kind, identifier in (("observation", observations[2]), ("alarm", alarms[2])):
        db.execute("INSERT INTO retention_hold VALUES(%s,%s,%s,'fixture-owner','preserve scoped record',%s)", (uuid4(), kind, str(identifier), now+timedelta(days=30)))
    result = minimise_database_evidence(db, service, now=now, execute=True)
    assert result["operational_records"] == {"observations": 1, "mock_deliveries": 1}
    assert {r["observation_id"] for r in db.execute("SELECT observation_id FROM ops_observation")} == set(observations[1:])
    assert {r["alarm_id"] for r in db.execute("SELECT alarm_id FROM ops_mock_delivery")} == set(alarms[1:])
    assert db.execute("SELECT count(*) n FROM alarm_outbox WHERE state='delivered'").fetchone()["n"] == 3


def artifact(db, service, path, kind, *, snapshot=False, age=91):
    now = service.now(db)
    run = uuid4()
    db.execute(
        "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','test','test','complete')",
        (run,),
    )
    snapshot_id = None
    if snapshot:
        content_id, snapshot_id = uuid4(), uuid4()
        db.execute(
            "INSERT INTO source_content VALUES(%s,'abr',%s,'fixture','fixture',%s)",
            (content_id, hashlib.sha256(path.read_bytes()).hexdigest(), str(path)),
        )
        db.execute(
            "INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,'abr',%s,4,'{}','committed')",
            (snapshot_id, content_id),
        )
        db.execute("INSERT INTO source_cursor(source,snapshot_id,version) VALUES('abr',%s,4)", (snapshot_id,))
    artifact_id = uuid4()
    db.execute(
        "INSERT INTO artifact_manifest(artifact_id,run_id,snapshot_id,source,object_key,content_digest,byte_count,created_at,verified_at,state,local_path,artifact_class) "
        "VALUES(%s,%s,%s,'abr',%s,%s,%s,%s,%s,'referenced',%s,%s)",
        (
            artifact_id,
            run,
            snapshot_id,
            f"staging/abr/{run}/{path.name}",
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
            now - timedelta(days=age),
            now - timedelta(days=age),
            str(path.resolve()),
            kind,
        ),
    )
    return artifact_id


def test_owned_expired_snapshot_bytes_deleted_cursor_invalidated_with_version_preserved(
    db, service, tmp_path
):
    service.settings = service.settings.model_copy(update={"output_dir": tmp_path})
    path = tmp_path / "snapshot.parquet"
    path.write_bytes(b"synthetic-snapshot")
    aid = artifact(db, service, path, "snapshot", snapshot=True)
    planned = artifact_retention(db, service, now=service.now(db), execute=False)
    assert planned[0]["state"] == "due" and path.exists()
    result = artifact_retention(db, service, now=service.now(db), execute=True)
    assert result[0]["state"] == "deleted" and not path.exists()
    cursor = db.execute("SELECT * FROM source_cursor WHERE source='abr'").fetchone()
    assert cursor["snapshot_id"] is None and cursor["version"] == 5
    assert db.execute("SELECT value FROM system_state WHERE name='history_gap:abr'").fetchone()["value"][
        "requires_baseline"
    ]
    assert (
        db.execute("SELECT state FROM artifact_manifest WHERE artifact_id=%s", (aid,)).fetchone()["state"]
        == "deleted"
    )


@pytest.mark.parametrize("unsafe", ["outside", "changed", "hold"])
def test_artifact_deletion_rejects_wrong_root_changed_bytes_and_hold(db, service, tmp_path, unsafe):
    root = tmp_path / "owned"
    root.mkdir()
    service.settings = service.settings.model_copy(update={"output_dir": root})
    path = (tmp_path if unsafe == "outside" else root) / "raw.zip"
    path.write_bytes(b"synthetic-raw")
    aid = artifact(db, service, path, "raw")
    if unsafe == "changed":
        path.write_bytes(b"tampered-data")
    if unsafe == "hold":
        db.execute(
            "INSERT INTO retention_hold VALUES(%s,'artifact',%s,'fixture-owner','Evidence hold',clock_timestamp())",
            (uuid4(), str(aid)),
        )
    results = artifact_retention(db, service, now=service.now(db), execute=True)
    assert results[0]["state"] == "held" and path.exists()


def test_backup_schedule_does_not_claim_provider_expiry_receipt(db, service, tmp_path):
    service.settings = service.settings.model_copy(update={"output_dir": tmp_path})
    path = tmp_path / "synthetic-backup.dump"
    path.write_bytes(b"synthetic-backup")
    artifact(db, service, path, "backup", age=34)
    result = retention_run(db, service, now=service.now(db), execute=True)
    assert path.exists()
    assert result["external_and_backups"] == "separate_receipts_required"


def test_ordinary_page_ciphertext_erased_after_90_days_with_provenance_retained(db, service):
    record = seed(db, service)
    now = service.now(db)
    provenance = record["contact"]["first_provenance_id"]
    before = db.execute(
        "SELECT * FROM collection_provenance WHERE provenance_id=%s", (provenance,)
    ).fetchone()
    result = minimise_database_evidence(db, service, now=now + timedelta(days=91), execute=False)
    assert result["page_bodies"] == 1
    assert db.execute(
        "SELECT encrypted_capture FROM collection_provenance WHERE provenance_id=%s", (provenance,)
    ).fetchone()["encrypted_capture"]
    result = minimise_database_evidence(db, service, now=now + timedelta(days=91), execute=True)
    after = db.execute("SELECT * FROM collection_provenance WHERE provenance_id=%s", (provenance,)).fetchone()
    assert result["page_bodies"] == 1
    assert after["encrypted_capture"] is None and after["encrypted_excerpt"] is None
    assert after["capture_erased_at"] and after["capture_sha256"] == before["capture_sha256"]
    assert after["source_url"] == before["source_url"]
    assert "CONTACT_EVIDENCE_ERASED" in service.gate(db, record["contact"]["contact_id"])["reason_codes"]
    assert (
        minimise_database_evidence(db, service, now=now + timedelta(days=92), execute=True)["page_bodies"]
        == 0
    )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SET LOCAL abr.retention_delete='on'")
        db.execute(
            "UPDATE collection_provenance SET encrypted_capture=%s,encrypted_excerpt=%s,capture_erased_at=NULL WHERE provenance_id=%s",
            (before["encrypted_capture"], before["encrypted_excerpt"], provenance),
        )


def test_page_erasure_cannot_rewrite_provenance_or_remove_fresh_capture(db, service):
    record = seed(db, service)
    provenance = record["contact"]["first_provenance_id"]
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SET LOCAL abr.retention_delete='on'")
        db.execute(
            "UPDATE collection_provenance SET encrypted_capture=NULL,encrypted_excerpt=NULL,capture_erased_at=clock_timestamp() WHERE provenance_id=%s",
            (provenance,),
        )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("SET LOCAL abr.retention_delete='on'")
        db.execute(
            "UPDATE collection_provenance SET encrypted_capture=NULL,encrypted_excerpt=NULL,capture_erased_at=clock_timestamp()+interval '91 days',source_url='https://example.com/forged' WHERE provenance_id=%s",
            (provenance,),
        )


def test_selected_page_capture_and_restricted_archive_survive_ordinary_90_day_purge(db, service):
    record = seed(db, service, selected=True)
    now = service.now(db)
    result = minimise_database_evidence(db, service, now=now + timedelta(days=91), execute=True)
    assert result["page_bodies"] == 0
    assert db.execute("SELECT encrypted_capture FROM collection_provenance").fetchone()["encrypted_capture"]
    erase_profile(db, service, record["lead"]["group_id"], now=now + timedelta(days=92))
    archived = db.execute("SELECT encrypted_payload FROM restricted_evidence_archive").fetchone()
    assert json.loads(service.keys.decrypt(archived["encrypted_payload"]))["provenance"][0][
        "encrypted_capture"
    ]


def event_snapshot(db, source):
    content, snapshot = uuid4(), uuid4()
    db.execute(
        "INSERT INTO source_content VALUES(%s,%s,%s,'fixture','fixture','synthetic-retention-only')",
        (content, source, hashlib.sha256(str(content).encode()).hexdigest()),
    )
    db.execute(
        "INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,%s,%s,0,'{}','committed')",
        (snapshot, source, content),
    )
    return snapshot


def test_full_source_identifiers_purged_to_minimal_counts_then_metrics_expire(db, service):
    now = service.now(db)
    abr = event_snapshot(db, "abr")
    qbcc = event_snapshot(db, "qbcc")
    for number in ("51824753556", "53004085616"):
        db.execute(
            "INSERT INTO abr_event VALUES(%s,%s,%s,'abn_new',%s,%s)",
            (
                uuid4(),
                abr,
                number,
                Jsonb({"name": "Synthetic private business", "abn": number}),
                now - timedelta(days=91),
            ),
        )
    db.execute(
        "INSERT INTO abr_event VALUES(%s,%s,'51824753556','gst_registered','{}',%s)",
        (uuid4(), abr, now - timedelta(days=89)),
    )
    db.execute(
        "INSERT INTO qbcc_event VALUES(%s,%s,'9999991','new',%s,%s)",
        (
            uuid4(),
            qbcc,
            Jsonb({"name": "Synthetic private business", "licence": "9999991"}),
            now - timedelta(days=91),
        ),
    )
    result = minimise_database_evidence(db, service, now=now, execute=True)
    assert result["full_source_events"] == {"abr": 2, "qbcc": 1}
    assert db.execute("SELECT count(*) AS n FROM abr_event").fetchone()["n"] == 1
    assert db.execute("SELECT count(*) AS n FROM qbcc_event").fetchone()["n"] == 0
    metrics = db.execute("SELECT * FROM retained_event_metric ORDER BY source").fetchall()
    assert [r["event_count"] for r in metrics] == [2, 1]
    text = json.dumps(metrics, default=str)
    assert "51824753556" not in text and "9999991" not in text and "Synthetic private business" not in text
    assert all(
        set(r) == {"source", "observed_day", "event_type", "event_count", "retained_until"} for r in metrics
    )
    minimise_database_evidence(db, service, now=now, execute=True)
    assert (
        sum(r["event_count"] for r in db.execute("SELECT event_count FROM retained_event_metric").fetchall())
        == 3
    )
    minimise_database_evidence(
        db, service, now=retention_deadline("event", now) + timedelta(days=1), execute=True
    )
    assert db.execute("SELECT count(*) AS n FROM retained_event_metric").fetchone()["n"] == 0


def test_snapshot_scoped_hold_preserves_full_events_without_aggregating_twice(db, service):
    now = service.now(db)
    snapshot = event_snapshot(db, "abr")
    db.execute(
        "INSERT INTO abr_event VALUES(%s,%s,'51824753556','abn_new','{}',%s)",
        (uuid4(), snapshot, now - timedelta(days=91)),
    )
    db.execute(
        "INSERT INTO retention_hold VALUES(%s,'snapshot',%s,'fixture-owner','Scoped record hold',%s)",
        (uuid4(), str(snapshot), now + timedelta(days=30)),
    )
    result = minimise_database_evidence(db, service, now=now, execute=True)
    assert result["full_source_events"]["abr"] == 0
    assert db.execute("SELECT count(*) AS n FROM abr_event").fetchone()["n"] == 1
