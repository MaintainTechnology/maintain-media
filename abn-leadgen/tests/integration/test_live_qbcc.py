"""Live-mode admission, actual PostgreSQL transactions, synthetic publisher bytes."""
# ruff: noqa: F811 -- imported pytest fixture is intentionally injected by name.

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from test_qbcc_review_stage import live  # noqa: F401

from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError
from abr_engine.ingest.qbcc_review import stage_qbcc_review
from abr_engine.live import qbcc


@pytest.fixture
def accepted(settings, live, monkeypatch):
    config, request, keys = live
    monkeypatch.setattr(qbcc, "transaction", lambda ignored: transaction(settings))
    original_lock = qbcc._session_lock
    monkeypatch.setattr(qbcc, "_session_lock", lambda ignored, key: original_lock(settings, key))
    stage_qbcc_review(config, request)
    result = qbcc.accept_qbcc_snapshot(config, request.run_id, 0, "synthetic-reviewer")
    return config, request, keys, result


def request_for(settings, config, keys, **updates):
    with transaction(settings) as conn:
        service = Service(config, keys)
        rows = qbcc.list_qbcc_reviews(conn, service)
        row = rows["rows"][0]
        return {
            "request_id": uuid4(),
            "snapshot_id": UUID(rows["snapshot_id"]),
            "licence_number": row["licence_number"],
            "row_digest": row["row_digest"],
            "status": "active",
            "identity_match": True,
            "reviewed_at": service.now(conn),
            "evidence_ref": "synthetic-current-official-check",
            **updates,
        }


def test_accepted_source_unknown_backlog_no_qualified_candidate_then_positive_review(settings, accepted):
    config, request, keys, result = accepted
    assert result["accepted"] and result["events"] == 1 and result["candidates"] == 0
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM candidate_queue").fetchone()["n"] == 0
        rows = qbcc.list_qbcc_reviews(conn, Service(config, keys))
        assert rows["rows"][0]["publisher_status"] == "UNKNOWN"
        assert rows["rows"][0]["review_status"] == "needs_review"
    payload = request_for(settings, config, keys)
    with transaction(settings) as conn:
        review = qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")
        assert review["enrichment_eligible"] and not review["export_eligible"]
        assert conn.execute("SELECT state FROM candidate_queue").fetchone()["state"] == "pending_enrichment"
        assert conn.execute("SELECT count(*) AS n FROM contact_record").fetchone()["n"] == 0
        assert conn.execute("SELECT status FROM licence_review").fetchone()["status"] == "active"
        assert conn.execute("SELECT count(*) AS n FROM qbcc_event").fetchone()["n"] == 1
    assert qbcc.accept_qbcc_snapshot(config, request.run_id, 0, "synthetic-reviewer")["replayed"]


@pytest.mark.parametrize(
    "status,identity",
    [("unknown", True), ("active", False), ("suspended", True), ("cancelled", True), ("inactive", True)],
)
def test_negative_check_never_creates_lead_or_candidate(settings, accepted, status, identity):
    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys, status=status, identity_match=identity)
    with transaction(settings) as conn:
        result = qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")
        assert not result["enrichment_eligible"] and result["lead_id"] is None
        assert conn.execute("SELECT count(*) AS n FROM lead_entity").fetchone()["n"] == 0


def test_review_replay_and_changed_body_conflict(settings, accepted):
    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)
    with transaction(settings) as conn:
        service = Service(config, keys)
        first = qbcc.review_qbcc_licence(conn, service, payload, "synthetic-reviewer")
        assert qbcc.review_qbcc_licence(conn, service, payload, "synthetic-reviewer")["replayed"]
        with pytest.raises(DomainError, match="IDEMPOTENCY_CONFLICT"):
            qbcc.review_qbcc_licence(conn, service, {**payload, "status": "unknown"}, "synthetic-reviewer")
        assert conn.execute("SELECT count(*) AS n FROM candidate_queue").fetchone()["n"] == 1
        assert first["lead_id"]


@pytest.mark.parametrize(
    "failure", ["stale_snapshot", "row_hash", "old_time", "future_time", "gates", "tamper"]
)
def test_invalid_review_cannot_change_authority(settings, accepted, failure):
    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)
    if failure == "stale_snapshot":
        payload["snapshot_id"] = uuid4()
    elif failure == "row_hash":
        payload["row_digest"] = "f" * 64
    elif failure == "old_time":
        payload["reviewed_at"] -= timedelta(days=31)
    elif failure == "future_time":
        payload["reviewed_at"] += timedelta(hours=1)
    elif failure == "gates":
        with transaction(settings) as conn:
            conn.execute("DELETE FROM release_gate WHERE gate_name='G1'")
    elif failure == "tamper":
        next(config.output_dir.rglob("publisher.parquet")).write_bytes(b"tampered")
    with transaction(settings) as conn:
        with pytest.raises(DomainError):
            qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")
        assert conn.execute("SELECT count(*) AS n FROM qbcc_source_review").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM candidate_queue").fetchone()["n"] == 0


def test_negative_after_positive_blocks_candidate_and_older_positive(settings, accepted):
    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)
    with transaction(settings) as conn:
        qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")
    negative = request_for(settings, config, keys, status="cancelled")
    with transaction(settings) as conn:
        service = Service(config, keys)
        qbcc.review_qbcc_licence(conn, service, negative, "synthetic-reviewer")
        assert conn.execute("SELECT state FROM candidate_queue").fetchone()["state"] == "suppressed"
        with pytest.raises(DomainError, match="NEWER_LICENCE_REVIEW_EXISTS"):
            qbcc.review_qbcc_licence(conn, service, {**payload, "request_id": uuid4()}, "synthetic-reviewer")
    later = request_for(settings, config, keys)
    with transaction(settings) as conn:
        result = qbcc.review_qbcc_licence(conn, Service(config, keys), later, "synthetic-reviewer")
        assert not result["enrichment_eligible"] and "SUPPRESSED_CANCELLATION" in result["reason_codes"]


def test_closed_acceptance_precedes_keys_and_files(settings, live, monkeypatch):
    config, request, _ = live
    monkeypatch.setattr(qbcc, "transaction", lambda ignored: transaction(settings))
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE gate_name='G2'")

    def forbidden(*args, **kwargs):
        raise AssertionError("I/O before authority")

    monkeypatch.setattr(qbcc, "load_keys", forbidden)
    with pytest.raises(SourceError, match="GATE_G2_CLOSED"):
        qbcc.accept_qbcc_snapshot(config, request.run_id, 0, "synthetic-reviewer")


def test_acceptance_failed_commit_retries_owned_artifact(settings, live, monkeypatch):
    config, request, _ = live
    monkeypatch.setattr(qbcc, "transaction", lambda ignored: transaction(settings))
    original_lock = qbcc._session_lock
    monkeypatch.setattr(qbcc, "_session_lock", lambda ignored, key: original_lock(settings, key))
    stage_qbcc_review(config, request)
    original = qbcc.promote

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise SourceError("SYNTHETIC_CRASH_BEFORE_COMMIT")

    monkeypatch.setattr(qbcc, "promote", fail)
    with pytest.raises(SourceError, match="SYNTHETIC_CRASH"):
        qbcc.accept_qbcc_snapshot(config, request.run_id, 0, "synthetic-reviewer")
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_snapshot").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM qbcc_event").fetchone()["n"] == 0
    monkeypatch.setattr(qbcc, "promote", original)
    assert qbcc.accept_qbcc_snapshot(config, request.run_id, 0, "synthetic-reviewer")["accepted"]


def test_review_lookup_key_cannot_retire_until_finite_unselected_evidence_expires(settings, accepted):
    import os

    from abr_engine.compliance.retention import minimise_database_evidence

    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys, status="unknown")
    with transaction(settings) as conn:
        qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")
        keys.rotate(2, os.urandom(32), conn)
        with pytest.raises(ValueError, match="Retained restrictions"):
            keys.retire(1, conn)
        fixture_service = Service(settings, keys)
        now = fixture_service.now(conn)
        before = minimise_database_evidence(conn, fixture_service, now=now + timedelta(days=89), execute=True)
        assert before["qbcc_source_reviews"] == 0
        after = minimise_database_evidence(conn, fixture_service, now=now + timedelta(days=91), execute=True)
        assert after["qbcc_source_reviews"] == 1
        keys.retire(1, conn)
        assert 1 not in keys.lookup_keys


def test_profile_erasure_preserves_minimal_suppression_aliases(settings, accepted):
    from abr_engine.compliance.retention import erase_profile

    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)
    with transaction(settings) as conn:
        service = Service(config, keys)
        result = qbcc.review_qbcc_licence(conn, service, payload, "synthetic-reviewer")
        service.suppress(
            conn,
            {
                "group_id": UUID(result["group_id"]),
                "reason": "manual",
                "source": "synthetic-test",
                "entity_only": True,
            },
            "synthetic-reviewer",
            uuid4(),
        )
        erase_profile(conn, Service(settings, keys), UUID(result["group_id"]))
        assert conn.execute("SELECT count(*) n FROM qbcc_source_review").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM suppression_alias").fetchone()["n"] > 0
        assert conn.execute("SELECT count(*) n FROM suppression_event").fetchone()["n"] > 0


def test_source_review_hold_prevents_profile_erasure(settings, accepted):
    from abr_engine.compliance.retention import erase_profile

    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)
    with transaction(settings) as conn:
        result = qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")
        conn.execute(
            "INSERT INTO retention_hold VALUES(%s,'qbcc_review',%s,'synthetic-owner','synthetic-hold',clock_timestamp()+interval '1 day')",
            (uuid4(), result["review_id"]),
        )
        with pytest.raises(DomainError, match="SCOPED_RETENTION_HOLD"):
            erase_profile(conn, Service(settings, keys), UUID(result["group_id"]))


def test_same_review_concurrent_requests_qualify_exactly_once(settings, accepted):
    from concurrent.futures import ThreadPoolExecutor

    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)

    def submit():
        with transaction(settings) as conn:
            return qbcc.review_qbcc_licence(conn, Service(config, keys), payload, "synthetic-reviewer")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(r["replayed"] for r in results) == [False, True]
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM candidate_queue").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) n FROM qbcc_source_review").fetchone()["n"] == 1


def test_raw_thirty_day_expiry_does_not_discard_ninety_day_accepted_cursor(settings, accepted):
    from abr_engine.compliance.retention import artifact_retention
    config, _, keys, result = accepted
    with transaction(settings) as conn:
        service = Service(settings.model_copy(update={"output_dir": config.output_dir}), keys)
        expired = artifact_retention(conn, service, now=service.now(conn) + timedelta(days=31), execute=True)
        assert sum(item["state"] == "deleted" for item in expired) == 1
        cursor = conn.execute("SELECT * FROM source_cursor WHERE source='qbcc'").fetchone()
        assert str(cursor["snapshot_id"]) == result["snapshot_id"] and cursor["version"] == 1
        assert qbcc.list_qbcc_reviews(conn, Service(config, keys))["total"] == 1
