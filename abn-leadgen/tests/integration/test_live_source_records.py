"""Real accepted snapshots and baseline runs are visible without producing leads."""
# ruff: noqa: F811 -- pytest fixtures are intentionally imported by name.

import csv
import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_live_abr_runtime import prepared, run  # noqa: F401
from test_live_qbcc import accepted  # noqa: F401
from test_qbcc_review_stage import live  # noqa: F401
from test_qbcc_review_stage import live as source_live  # noqa: F401

from abr_engine.control.auth import Actor
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.ingest.common import digest_file
from abr_engine.ingest.qbcc_review import stage_qbcc_review
from abr_engine.live import api, qbcc
from abr_engine.live import source_records as browse


def test_completed_abr_baseline_and_exact_run_browsing_leave_qualification_unchanged(
    settings, prepared, monkeypatch,
):
    runtime, _, _, keys = prepared
    receipt = run(runtime)
    assert receipt["state"] == "complete"
    monkeypatch.setattr(browse, "transaction", lambda ignored: transaction(settings))
    service = Service(runtime.settings, keys)
    result = browse.list_source_records(runtime.settings, service, source="abr",
                                        requested_run=str(receipt["job_id"]), actor="synthetic-reviewer")
    assert result["total"] == 1 and result["baseline"] and result["source_state"] == "available"
    assert result["records"][0]["main_name"] == "Synthetic Construction"
    assert result["records"][0]["abn"] == "51824753556"
    assert result["records"][0]["status_date"] == "2018-01-31"
    assert result["next_offset"] is None and result["run_id"] == receipt["job_id"]
    latest = browse.list_source_records(runtime.settings, service, source="abr", actor="synthetic-reviewer")
    assert latest["snapshot_id"] == result["snapshot_id"]
    filtered = browse.list_source_records(runtime.settings, service, source="abr", actor="synthetic-reviewer",
                                          filters={"query": "51 824 753 556", "state": "QLD"},
                                          sort="status_date_desc")
    assert filtered["total"] == 1 and filtered["source_total"] == 1
    assert filtered["sort"] == "status_date_desc" and latest["sort"] == "source_order"
    assert filtered["filters"] == {"query": "51 824 753 556", "state": "QLD"}
    assert set(filtered["records"][0]) == set(filtered["columns"]) == set(browse.FIELDS["abr"])
    assert filtered["publisher_extract_time"] == "2026-09-09T12:20:57"
    missing = browse.list_source_records(runtime.settings, service, source="abr", actor="synthetic-reviewer",
                                         filters={"gst_status": "UNKNOWN"})
    assert missing["total"] == 1 and missing["records"][0]["gst_status"] == "NONE"
    assert missing["filters"] == {"gst_status": "UNKNOWN"}
    with transaction(settings) as conn:
        for table in ("abr_event", "lead_entity", "candidate_queue", "qbcc_source_review"):
            assert conn.execute(f"SELECT count(*) n FROM {table}").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM audit_event WHERE action='source_records_read'").fetchone()["n"] == 4
    with pytest.raises(DomainError, match="SOURCE_RUN_NOT_FOUND"):
        browse.list_source_records(runtime.settings, service, source="qbcc",
                                   requested_run=str(receipt["job_id"]), actor="synthetic-reviewer")


def test_qbcc_live_job_intake_indirection_and_noop_receipt(settings, accepted, monkeypatch):
    config, request, keys, receipt = accepted
    monkeypatch.setattr(browse, "transaction", lambda ignored: transaction(settings))
    service = Service(config, keys)
    # Actual live jobs store acceptance in result; they do not own the snapshot.
    job_id = uuid4()
    with transaction(settings) as conn:
        conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) "
                     "VALUES(%s,'pilot','synthetic','synthetic','complete',%s)",
                     (job_id, Jsonb({"kind": "qbcc_live_job", "result": {**receipt, "noop": True}})))
    for requested in (str(request.run_id), str(job_id), "latest"):
        result = browse.list_source_records(config, service, source="qbcc", requested_run=requested,
                                            actor="synthetic-reviewer")
        assert result["total"] == 1 and result["records"][0]["licence_number"] == "SYNTHETIC-1"
        assert result["records"][0]["status"] == "UNKNOWN"
        assert result["snapshot_id"] == receipt["snapshot_id"]
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM qbcc_source_review").fetchone()["n"] == 0


def test_qbcc_source_browse_includes_categories_outside_licence_review_queue(settings, live, monkeypatch):
    config, request, keys = live
    rows = list(csv.reader(io.StringIO(request.input_path.read_text(encoding="utf-16"))))
    extra = rows[1].copy()
    extra[0], extra[1], extra[7], extra[8] = "SYNTHETIC-7", "Synthetic Category Seven", "Category 7", "7"
    output = io.StringIO(newline="")
    csv.writer(output).writerows([*rows, extra])
    request.input_path.write_text(output.getvalue(), encoding="utf-16")
    request = request.model_copy(update={"source_sha256": digest_file(request.input_path)})
    monkeypatch.setattr(qbcc, "transaction", lambda ignored: transaction(settings))
    original_lock = qbcc._session_lock
    monkeypatch.setattr(qbcc, "_session_lock", lambda ignored, key: original_lock(settings, key))
    monkeypatch.setattr(browse, "transaction", lambda ignored: transaction(settings))
    stage_qbcc_review(config, request)
    qbcc.accept_qbcc_snapshot(config, request.run_id, 0, "synthetic-reviewer")
    result = browse.list_source_records(config, Service(config, keys), source="qbcc", actor="synthetic-reviewer")
    assert result["total"] == 2
    assert {row["financial_category"] for row in result["records"]} == {"1", "7"}
    filtered = browse.list_source_records(config, Service(config, keys), source="qbcc",
                                          actor="synthetic-reviewer", filters={"financial_category": "7"})
    assert filtered["total"] == 1 and filtered["source_total"] == 2
    assert filtered["records"][0]["licence_number"] == "SYNTHETIC-7"
    assert isinstance(filtered["records"][0]["licence_types"], list)
    assert isinstance(filtered["records"][0]["licence_review_required"], bool)
    assert len(filtered["columns"]) == 17
    with transaction(settings) as conn:
        assert qbcc.list_qbcc_reviews(conn, Service(config, keys))["total"] == 1
        assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 0


def test_absent_and_expired_sources_are_distinct(settings, accepted, monkeypatch):
    config, _, keys, receipt = accepted
    monkeypatch.setattr(browse, "transaction", lambda ignored: transaction(settings))
    service = Service(config, keys)
    absent = browse.list_source_records(config, service, source="abr", actor="synthetic-reviewer")
    assert absent["source_state"] == "not_collected" and absent["total"] == 0
    with transaction(settings) as conn:
        conn.execute("UPDATE artifact_manifest SET state='deleted',deletion_reason='retention_expired' "
                     "WHERE snapshot_id=%s AND artifact_class='snapshot'", (receipt["snapshot_id"],))
    monkeypatch.setattr(browse.pq, "ParquetFile", lambda *args: pytest.fail("expired source was read"))
    expired = browse.list_source_records(config, service, source="qbcc", actor="synthetic-reviewer")
    assert expired["source_state"] == "expired" and expired["total"] == 1 and expired["records"] == []


def test_quarantine_blocks_source_files_and_rechecked_after_page(settings, accepted, monkeypatch):
    config, _, keys, _ = accepted
    monkeypatch.setattr(browse, "transaction", lambda ignored: transaction(settings))
    original = browse._read_page

    def quarantine_after_read(*args):
        seals = original(*args)
        with transaction(settings) as conn:
            conn.execute("UPDATE system_state SET value='true' WHERE name='restore_quarantine'")
        return seals

    monkeypatch.setattr(browse, "_read_page", quarantine_after_read)
    with pytest.raises(DomainError, match="AUTHORITY_QUARANTINED"):
        browse.list_source_records(config, Service(config, keys), source="qbcc", actor="synthetic-reviewer")
    monkeypatch.setattr(browse, "_read_page", lambda *args: pytest.fail("quarantined source read"))
    with pytest.raises(DomainError, match="AUTHORITY_QUARANTINED"):
        browse.list_source_records(config, Service(config, keys), source="qbcc", actor="synthetic-reviewer")


def test_api_read_scope_pagination_and_no_store(settings, accepted, monkeypatch):
    config, _, _, _ = accepted
    monkeypatch.setattr(browse, "transaction", lambda ignored: transaction(settings))
    actor = {"scopes": frozenset({"admin"})}
    app = api.create_live_app(config, authority=lambda request: Actor("user_Synthetic", actor["scopes"]))
    with TestClient(app) as client:
        result = client.get("/api/source-records/qbcc/latest/0")
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
        assert result.json()["total"] == 1
        assert result.json()["sort"] == "source_order"
        sorted_absent = client.post("/api/source-records/query", json={"source": "abr", "sort": "status_date_desc"})
        assert sorted_absent.status_code == 200
        assert sorted_absent.json()["sort"] == "status_date_desc"
        assert sorted_absent.json()["source_state"] == "not_collected"
        wrong_source = client.post("/api/source-records/query", json={"source": "qbcc", "sort": "status_date_desc"})
        assert wrong_source.status_code == 422
        assert "INVALID_SOURCE_SORT" in wrong_source.text
        assert client.post("/api/source-records/query", json={"source": "abr", "sort": "score"}).status_code == 422
        for path in ("/api/source-records/qbcc/latest/-1", "/api/source-records/qbcc/latest/100000001",
                     "/api/source-records/abr/invalid/0"):
            assert client.get(path).status_code == 422
        actor["scopes"] = frozenset({"operator"})
        assert client.get("/api/source-records/qbcc/latest/0").status_code == 403
