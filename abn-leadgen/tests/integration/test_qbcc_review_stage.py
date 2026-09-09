"""Live intake authority boundaries on isolated PostgreSQL, synthetic file rows."""

import csv
import io
import json
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb

from abr_engine.compliance.keys import KeyStore
from abr_engine.compliance.retention import artifact_retention
from abr_engine.config import Settings
from abr_engine.control.service import Service
from abr_engine.db import transaction
from abr_engine.ingest import qbcc_review as stage
from abr_engine.ingest.common import SourceError, digest_file
from abr_engine.ingest.qbcc import QBCCMapping


@pytest.fixture
def live(settings, tmp_path, monkeypatch):
    keypath = tmp_path / "new-test-only-key-store.json"
    keys = KeyStore(
        Fernet.generate_key(),
        {1: os.urandom(32)},
        signing_key=os.urandom(32).hex(),
        path=keypath,
        wrapping_key=Fernet.generate_key(),
    )
    keys.save()
    config = settings.model_copy(
        update={
            "mode": "pilot",
            "database_url": "postgresql://synthetic@localhost/synthetic_test",
            "capabilities": {"collection": True},
            "key_file": keypath,
            "output_dir": tmp_path / "managed",
        }
    )
    monkeypatch.setenv("ABR_KEYSTORE_WRAPPING_KEY", keys.wrapping_key.decode())
    # Only the connection transport is redirected to the test's isolated schema.
    # All release gates and service checks run on real PostgreSQL unchanged.
    monkeypatch.setattr(stage, "transaction", lambda ignored: transaction(settings))
    original_lock = stage._session_lock
    monkeypatch.setattr(stage, "_session_lock", lambda ignored, key: original_lock(settings, key))
    with transaction(settings) as conn:
        now = Service.now(conn)
        for gate in ("G1", "G2", "G3", "G7"):
            conn.execute(
                "INSERT INTO release_gate VALUES(%s,'pilot','collection',1,'synthetic-mapping-evidence',%s,'synthetic-test',%s,%s)",
                (gate, "a" * 64, now - timedelta(minutes=1), now + timedelta(hours=1)),
            )
    data = io.StringIO(newline="")
    writer = csv.writer(data)
    writer.writerow(QBCCMapping.publisher().columns.values())
    writer.writerow(
        [
            "SYNTHETIC-1",
            "Synthetic Private Builder",
            "000000000",
            "",
            "1 Synthetic Street QLD 4000",
            "Trade Contractor",
            "T",
            "Category 1",
            "1",
            "Contractor",
            "Builder",
        ]
    )
    source = tmp_path / "synthetic-publisher.csv"
    source.write_bytes(b"\xff\xfe" + data.getvalue().encode("utf-16-le"))
    request = stage.QBCCReviewRequest(
        run_id=uuid4(),
        input_path=source,
        source_sha256=digest_file(source),
        inventory_before_sha256="b" * 64,
        inventory_after_sha256="b" * 64,
        mapping_evidence_ref="synthetic-mapping-evidence",
        mapping_evidence_sha256="a" * 64,
        retrieved_at=now,
        expected_cursor_version=0,
    )
    return config, request, keys


def snapshot(settings):
    with transaction(settings) as conn:
        tables = (
            "lead_entity",
            "candidate_queue",
            "contact_record",
            "qbcc_event",
            "source_cursor",
            "source_snapshot",
            "suppression_alias",
            "policy",
        )
        return {name: conn.execute(f"SELECT count(*) AS n FROM {name}").fetchone()["n"] for name in tables}


def test_approved_file_stages_encrypted_unknown_without_candidate_or_cursor(settings, live):
    config, request, keys = live
    before = snapshot(settings)
    result = stage.stage_qbcc_review(config, request)
    assert result["state"] == "needs_review" and result["accepted"] is False
    assert result["review_record_count"] == 1 and result["candidates_created"] == 0
    assert snapshot(settings) == before
    with transaction(settings) as conn:
        run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request.run_id,)).fetchone()
        assert run["state"] == "held"
        rows = conn.execute("SELECT * FROM artifact_manifest WHERE run_id=%s", (request.run_id,)).fetchall()
        assert len(rows) == 2 and all(r["state"] == "verified" for r in rows)
        assert "Synthetic Private Builder" not in json.dumps(run["manifest"])
        assert conn.execute("SELECT count(*) AS n FROM source_observation").fetchone()["n"] == 1
    review = config.output_dir / "staging" / "qbcc" / str(request.run_id) / "review.encrypted.jsonl"
    assert "Synthetic Private Builder" not in review.read_text()
    item = json.loads(keys.decrypt(json.loads(review.read_text())["payload"]))
    assert item["record"]["status"] == "UNKNOWN" and item["record"]["entity_class"] == "unknown"
    assert item["tier"] is None and item["enrichment_eligible"] is False and item["export_eligible"] is False


@pytest.mark.parametrize(
    "failure",
    [
        "fixture",
        "fixture_db",
        "capability",
        "G1",
        "G2",
        "G3",
        "G7",
        "malformed_hash",
        "mapping",
        "scope",
        "future_latest",
    ],
)
def test_closed_authority_precedes_keys_and_input(settings, live, monkeypatch, failure):
    config, request, _ = live
    if failure == "fixture":
        config = config.model_copy(update={"mode": "fixture"})
    elif failure == "fixture_db":
        config = config.model_copy(update={"database_url": settings.database_url})
    elif failure == "capability":
        config = config.model_copy(update={"capabilities": {}})
    else:
        with transaction(settings) as conn:
            if failure in {"G1", "G2", "G3", "G7"}:
                conn.execute("DELETE FROM release_gate WHERE gate_name=%s", (failure,))
            elif failure == "malformed_hash":
                conn.execute("UPDATE release_gate SET evidence_sha256=%s WHERE gate_name='G1'", ("x" * 64,))
            elif failure == "mapping":
                conn.execute("UPDATE release_gate SET evidence_ref='different-mapping' WHERE gate_name='G2'")
            elif failure == "scope":
                conn.execute("UPDATE release_gate SET scope='crm' WHERE gate_name='G1'")
            else:
                conn.execute(
                    "INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,actor_id,approved_at+interval '2 hours',expires_at+interval '2 hours' FROM release_gate WHERE gate_name='G1'"
                )
    request.input_path.unlink()

    def forbidden(*args, **kwargs):
        raise AssertionError("key loading preceded authority")

    monkeypatch.setattr(stage, "load_keys", forbidden)
    with pytest.raises(SourceError):
        stage.stage_qbcc_review(config, request)
    assert not config.output_dir.exists()
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM pipeline_run").fetchone()["n"] == 0


def test_replay_never_rereads_source_and_detects_artifact_tampering(settings, live):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    request.input_path.unlink()
    assert stage.stage_qbcc_review(config, request)["replayed"] is True
    changed = request.model_copy(update={"source_sha256": "f" * 64})
    with pytest.raises(SourceError, match="INTAKE_REPLAY_CONFLICT"):
        stage.stage_qbcc_review(config, changed)
    review = config.output_dir / "staging" / "qbcc" / str(request.run_id) / "review.encrypted.jsonl"
    review.write_text("tampered")
    with pytest.raises(SourceError, match="VERIFIED_ARTIFACT_CHANGED"):
        stage.stage_qbcc_review(config, request)


@pytest.mark.parametrize("failure", ["digest", "parser", "limit"])
def test_failed_intake_keeps_owned_artifacts_but_no_observation(settings, live, monkeypatch, failure):
    config, request, _ = live
    if failure == "digest":
        request = request.model_copy(update={"source_sha256": "f" * 64})
    elif failure == "parser":
        request.input_path.write_bytes(b"not a publisher CSV")
        request = request.model_copy(update={"source_sha256": digest_file(request.input_path)})
    else:
        monkeypatch.setattr(stage, "MAX_FILE_BYTES", 1)
    before = snapshot(settings)
    with pytest.raises(SourceError):
        stage.stage_qbcc_review(config, request)
    assert snapshot(settings) == before
    with transaction(settings) as conn:
        assert conn.execute("SELECT state FROM pipeline_run").fetchone()["state"] == "failed"
        assert conn.execute("SELECT count(*) AS n FROM source_observation").fetchone()["n"] == 0
    with pytest.raises(SourceError, match="INTAKE_REQUIRES_NEW_ATTEMPT"):
        stage.stage_qbcc_review(config, request)


def test_gate_revoked_during_parse_prevents_usable_intake(settings, live, monkeypatch):
    config, request, _ = live
    original = stage.parse_qbcc

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        with transaction(settings) as conn:
            conn.execute("DELETE FROM release_gate WHERE gate_name='G1'")
        return result

    monkeypatch.setattr(stage, "parse_qbcc", revoke)
    with pytest.raises(SourceError, match="GATE_G1_CLOSED"):
        stage.stage_qbcc_review(config, request)
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_observation").fetchone()["n"] == 0
        assert conn.execute("SELECT state FROM pipeline_run").fetchone()["state"] == "failed"


def test_existing_source_cursor_is_preserved_and_stale_receipt_rejected(settings, live):
    config, request, _ = live
    with transaction(settings) as conn:
        conn.execute("INSERT INTO source_cursor(source,version) VALUES('qbcc',3)")
    with pytest.raises(SourceError, match="STALE_SOURCE_CURSOR"):
        stage.stage_qbcc_review(config, request)
    request = request.model_copy(update={"expected_cursor_version": 3})
    stage.stage_qbcc_review(config, request)
    with transaction(settings) as conn:
        assert conn.execute("SELECT version FROM source_cursor").fetchone()["version"] == 3


def test_intake_has_existing_seven_day_artifact_retention(settings, live):
    config, request, keys = live
    stage.stage_qbcc_review(config, request)
    with transaction(settings) as conn:
        result = artifact_retention(conn, Service(config, keys), now=Service.now(conn) + timedelta(days=8))
    assert len(result) == 2 and all(item["state"] == "due" for item in result)


def test_preexisting_directory_is_not_adopted(settings, live):
    config, request, _ = live
    directory = config.output_dir / "staging" / "qbcc" / str(request.run_id)
    directory.mkdir(parents=True)
    foreign = directory / "publisher.csv"
    foreign.write_text("user owned file")
    with pytest.raises(SourceError, match="ARTIFACT_ALREADY_EXISTS"):
        stage.stage_qbcc_review(config, request)
    assert foreign.read_text() == "user owned file"
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM artifact_manifest").fetchone()["n"] == 0


def test_quarantine_blocks_input_before_copy(settings, live):
    config, request, _ = live
    with transaction(settings) as conn:
        conn.execute("UPDATE system_state SET value=%s WHERE name='restore_quarantine'", (Jsonb(True),))
    with pytest.raises(Exception, match="AUTHORITY_QUARANTINED"):
        stage.stage_qbcc_review(config, request)
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM artifact_manifest").fetchone()["n"] == 0


def expire(settings, request, *, crashed=False):
    with transaction(settings) as conn:
        conn.execute(
            "UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '8 days' WHERE run_id=%s",
            (request.run_id,),
        )
        if crashed:
            conn.execute(
                "UPDATE pipeline_run SET state='running',heartbeat_at=clock_timestamp()-interval '8 days',manifest=%s WHERE run_id=%s",
                (Jsonb({"kind": "qbcc_review_intake", "intake_state": "writing"}), request.run_id),
            )
            conn.execute(
                "UPDATE artifact_manifest SET state='writing',content_digest='',byte_count=0 WHERE run_id=%s",
                (request.run_id,),
            )


def test_actual_expired_cleanup_remains_possible_after_collection_permission_removed(settings, live):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    expire(settings, request)
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate")
    config = config.model_copy(update={"capabilities": {}})
    dry = stage.cleanup_qbcc_review(config, run_id=request.run_id)
    assert dry["runs"][0]["state"] == "due"
    result = stage.cleanup_qbcc_review(config, run_id=request.run_id, execute=True)
    assert result["runs"][0]["state"] == "deleted" and result["runs"][0]["deleted_files"] == 2
    assert request.input_path.exists()  # The caller-owned input is never removed.
    again = stage.cleanup_qbcc_review(config, run_id=request.run_id, execute=True)
    assert again["runs"] == []
    with transaction(settings) as conn:
        assert {r["state"] for r in conn.execute("SELECT state FROM artifact_manifest")} == {"deleted"}


@pytest.mark.parametrize("blocked", ["artifact_hold", "run_hold", "changed_bytes", "fresh_writer"])
def test_cleanup_holds_changed_or_protected_artifacts(settings, live, blocked):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    expire(settings, request)
    with transaction(settings) as conn:
        artifact = conn.execute("SELECT * FROM artifact_manifest ORDER BY artifact_id LIMIT 1").fetchone()
        if blocked.endswith("hold"):
            conn.execute(
                "INSERT INTO retention_hold VALUES(%s,%s,%s,'synthetic-owner','synthetic-hold',clock_timestamp()+interval '1 day')",
                (
                    uuid4(),
                    "artifact" if blocked == "artifact_hold" else "run",
                    str(artifact["artifact_id"] if blocked == "artifact_hold" else request.run_id),
                ),
            )
        elif blocked == "fresh_writer":
            conn.execute("UPDATE pipeline_run SET state='running',heartbeat_at=clock_timestamp()")
    if blocked == "changed_bytes":
        from pathlib import Path

        Path(artifact["local_path"]).write_text("changed")
    result = stage.cleanup_qbcc_review(config, execute=True)
    assert result["runs"][0]["state"] == ("retained" if blocked == "fresh_writer" else "held")
    assert result["runs"][0]["deleted_files"] == 0


def test_crashed_partial_and_absent_owned_file_can_expire(settings, live):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    expire(settings, request, crashed=True)
    directory = config.output_dir / "staging" / "qbcc" / str(request.run_id)
    (directory / "review.encrypted.jsonl").unlink()
    (directory / "publisher.csv").write_bytes(b"partial copy")
    result = stage.cleanup_qbcc_review(config, execute=True)
    assert result["runs"][0]["state"] == "deleted" and result["runs"][0]["deleted_files"] == 1


def test_stale_writer_recovered_before_its_seven_day_expiry(settings, live):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    with transaction(settings) as conn:
        conn.execute(
            "UPDATE pipeline_run SET state='running',heartbeat_at=clock_timestamp()-interval '2 hours'"
        )
    result = stage.cleanup_qbcc_review(config, execute=True)
    assert result["runs"][0]["state"] == "recovered_for_retention"
    assert result["runs"][0]["deleted_files"] == 0


@pytest.mark.parametrize("name", [".env", "token.json", "secrets/data.csv", ".ssh/data.csv"])
def test_non_csv_and_credential_paths_rejected_before_key_loading(live, monkeypatch, name):
    config, request, _ = live
    path = request.input_path.parent / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic secret-like test data")
    request = request.model_copy(update={"input_path": path})

    def forbidden(*args, **kwargs):
        raise AssertionError("key loaded before path validation")

    monkeypatch.setattr(stage, "load_keys", forbidden)
    with pytest.raises(SourceError, match="QBCC_INPUT_PATH_NOT_ALLOWED"):
        stage.stage_qbcc_review(config, request)


def test_encrypted_output_limit_keeps_partial_artifact_deletable(settings, live, monkeypatch):
    config, request, _ = live
    monkeypatch.setattr(stage, "MAX_REVIEW_BYTES", 5)
    with pytest.raises(SourceError, match="REVIEW_ARTIFACT_SIZE_LIMIT"):
        stage.stage_qbcc_review(config, request)
    review = config.output_dir / "staging" / "qbcc" / str(request.run_id) / "review.encrypted.jsonl"
    assert review.stat().st_size <= 5
    monkeypatch.setattr(stage, "MAX_REVIEW_BYTES", 1024**3)
    expire(settings, request)
    assert stage.cleanup_qbcc_review(config, execute=True)["runs"][0]["state"] == "deleted"


def test_cleanup_fairness_does_not_starve_new_due_run_behind_100_held_attempts(settings, live):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    expire(settings, request)
    with transaction(settings) as conn:
        for _ in range(100):
            conn.execute(
                "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,started_at,manifest) VALUES(%s,'pilot','test','test','failed',clock_timestamp()-interval '10 days',%s)",
                (uuid4(), Jsonb({"kind": "qbcc_review_intake", "intake_state": "failed"})),
            )
    first = stage.cleanup_qbcc_review(config, execute=True)
    assert len(first["runs"]) == 100 and first["status"] == "held"
    assert str(request.run_id) not in {r["run_id"] for r in first["runs"]}
    second = stage.cleanup_qbcc_review(config, execute=True)
    assert any(r["run_id"] == str(request.run_id) and r["state"] == "deleted" for r in second["runs"])


def test_replay_oversized_artifact_never_uses_unbounded_verifier(live, monkeypatch):
    config, request, _ = live
    stage.stage_qbcc_review(config, request)
    monkeypatch.setattr(stage, "MAX_REVIEW_BYTES", 5)

    def forbidden(*args, **kwargs):
        raise AssertionError("unbounded artifact verifier used during replay")

    monkeypatch.setattr(stage, "verify_artifact", forbidden)
    with pytest.raises(SourceError, match="INTAKE_ARTIFACT_SIZE_INVALID"):
        stage.stage_qbcc_review(config, request)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://%61br_fixture:synthetic@127.0.0.1/private",
        "postgresql://synthetic:synthetic@127.0.0.1/%61br_fixture",
        "postgresql://synthetic:synthetic@127.0.0.1/private?user=abr_fixture",
        "postgresql://synthetic:synthetic@127.0.0.1/private?dbname=abr_fixture",
        "postgresql://synthetic:synthetic@127.0.0.1/private?service=fixture",
        "postgresql://127.0.0.1/private",
        "invalid-dsn",
    ],
)
def test_effective_fixture_dsn_rejected_before_connection_or_keys(monkeypatch, dsn, tmp_path):
    config = Settings(
        mode="pilot",
        database_url=dsn,
        key_file=tmp_path / "never-read.json",
        capabilities={"collection": True},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("I/O preceded effective configuration guard")

    monkeypatch.setattr(stage, "transaction", forbidden)
    monkeypatch.setattr(stage, "load_keys", forbidden)
    with pytest.raises(SourceError, match="LIVE_QBCC_CONFIGURATION_REQUIRED"):
        stage.stage_qbcc_review(config, None)
