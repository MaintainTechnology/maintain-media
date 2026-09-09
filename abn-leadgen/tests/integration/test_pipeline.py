"""Faults at actual source/report boundaries; real PostgreSQL authority."""

from pathlib import Path
from uuid import uuid4

import pytest

from abr_engine.compliance.keys import load_keys
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.pipeline import execute, process_lock


@pytest.fixture
def pipeline_context(settings, tmp_path):
    config = settings.model_copy(update={"output_dir": tmp_path})
    return config, Service(config, load_keys(config))


def test_complete_fixture_and_replay_keep_authority_and_provenance(pipeline_context):
    settings, service = pipeline_context
    run_id = uuid4()
    result = execute(settings, service, "all", run_id)
    assert result["status"] == "complete", result
    assert result["counts"]["selected"] == 1
    assert [entry["status"] for entry in result["enrichment"]] == ["complete", "complete"]
    assert result["counts"]["selected"] >= 1 and result["counts"]["live_api_calls"] == 0
    assert result["sources"]["abr"]["validation"]["declared_rows"] == 3
    assert result["sources"]["abr"]["validation"]["source_rows"] == 3
    assert result["sources"]["abr"]["validation"]["field_fill_weighted"]["postcode"] == 1
    assert result["sources"]["qbcc"]["validation"]["quarantined_rows"] == 2
    assert result["resource_sample"]["sampled_peak_rss_bytes"] > 0
    assert result["resource_sample"]["full_scale_certified"] is False
    assert all(Path(p).is_file() for p in result["artifacts"].values())
    with transaction(settings) as conn:
        run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (run_id,)).fetchone()
        assert set(run["manifest"]["promotion_results"]) == {"abr", "qbcc"}
        assert (
            conn.execute("SELECT count(*) AS n FROM enrichment_operation WHERE state='complete'").fetchone()[
                "n"
            ]
            == 6
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM budget_reservation WHERE state='settled' AND actual=0"
            ).fetchone()["n"]
            == 6
        )
        assert (
            conn.execute(
                "SELECT min(q.score) AS score FROM candidate_queue q JOIN worklist_row w ON q.candidate_id=w.candidate_id"
            ).fetchone()["score"]
            == 100
        )
        assert all(s["status"] == "validated" for s in run["manifest"]["source_stages"].values())
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM artifact_manifest WHERE run_id=%s AND local_path IS NULL",
                (run_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM artifact_manifest WHERE run_id=%s AND local_path LIKE '%%events.parquet' AND artifact_class='snapshot'",
                (run_id,),
            ).fetchone()["n"]
            == 1
        )
        before = conn.execute("SELECT count(*) AS n FROM source_promotion").fetchone()["n"]
    assert execute(settings, service, "all", run_id) == result
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_promotion").fetchone()["n"] == before


def test_complete_replay_rechecks_current_policy_and_masks_new_bundle(pipeline_context):
    settings, service = pipeline_context
    run_id = uuid4()
    first = execute(settings, service, "qbcc", run_id)
    with transaction(settings) as conn:
        before = conn.execute("SELECT count(*) AS n FROM source_promotion").fetchone()["n"]
        conn.execute("UPDATE policy SET expires_at=clock_timestamp()-interval '1 second'")
    second = execute(settings, service, "qbcc", run_id)
    assert first["artifact_digests"] != second["artifact_digests"]
    assert first["report_authority_digest"] != second["report_authority_digest"]
    assert "Masked" in Path(second["artifacts"]["csv"]).read_text(encoding="utf-8-sig")
    assert Path(first["artifacts"]["csv"]).exists()
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_promotion").fetchone()["n"] == before


@pytest.mark.parametrize("point", ["after_parse", "after_stage_commit", "after_source_commit"])
def test_source_crash_resume_without_duplicate_promotions(pipeline_context, point):
    settings, service = pipeline_context
    run_id = uuid4()

    def crash(stage):
        if stage == point:
            raise OSError("synthetic injected failure")

    held = execute(settings, service, "qbcc", run_id, fault=crash)
    assert held["status"] == "held"
    with transaction(settings) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM alarm_outbox WHERE run_id=%s AND code='SOURCE_INTEGRITY_HELD'",
                (run_id,),
            ).fetchone()["n"]
            == 1
        )
        owned = conn.execute(
            "SELECT count(*) AS n FROM artifact_manifest WHERE run_id=%s AND source='qbcc'", (run_id,)
        ).fetchone()["n"]
        assert owned >= 2
    result = execute(settings, service, "all", run_id)
    assert result["status"] == "complete", result
    assert set(result["sources"]) == {"qbcc"}  # original request survives default resume
    assert result["counts"]["selected"] == 1
    with transaction(settings) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM source_promotion WHERE run_id=%s", (run_id,)).fetchone()[
                "n"
            ]
            == 1
        )
        assert conn.execute("SELECT count(*) AS n FROM qbcc_event").fetchone()["n"] == 3


@pytest.mark.parametrize("point", ["after_report_write", "after_run_result_commit"])
def test_report_crash_repairs_with_new_bundle_without_source_replay(pipeline_context, point):
    settings, service = pipeline_context
    run_id = uuid4()

    def crash(stage):
        if stage == point:
            raise OSError("synthetic report failure")

    with pytest.raises(OSError, match="synthetic report failure"):
        execute(settings, service, "qbcc", run_id, fault=crash)
    result = execute(settings, service, "all", run_id)
    assert result["status"] == "complete"
    assert all(Path(p).is_file() for p in result["artifacts"].values())
    with transaction(settings) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM source_promotion WHERE run_id=%s", (run_id,)).fetchone()[
                "n"
            ]
            == 1
        )


def test_missing_report_and_receipt_repaired_from_current_authority(pipeline_context):
    settings, service = pipeline_context
    run_id = uuid4()
    original = execute(settings, service, "qbcc", run_id)
    Path(original["manifest_path"]).unlink()
    receipt_repair = execute(settings, service, "all", run_id)
    assert receipt_repair == original and Path(original["manifest_path"]).is_file()
    Path(original["artifacts"]["csv"]).unlink()
    repaired = execute(settings, service, "all", run_id)
    assert repaired["artifacts"] != original["artifacts"]
    assert all(Path(p).is_file() for p in repaired["artifacts"].values())
    with transaction(settings) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM source_promotion WHERE run_id=%s", (run_id,)).fetchone()[
                "n"
            ]
            == 1
        )


def test_saved_input_and_process_lock_fail_closed(pipeline_context):
    settings, service = pipeline_context
    with pytest.raises(DomainError, match="UNKNOWN_SOURCE_OR_FIXTURE"):
        execute(settings, service, "unknown")
    run_id = uuid4()
    execute(settings, service, "qbcc", run_id)
    with pytest.raises(DomainError, match="RESUME_REQUEST_CHANGED"):
        execute(settings, service, "abr", run_id)
    lock_path = settings.output_dir / "locks" / settings.schema_name / f"run-{run_id}.lock"
    with process_lock(lock_path), pytest.raises(DomainError, match="PROCESS_STAGE_LOCK_BUSY"):
        execute(settings, service, "all", run_id)


def test_artifact_ownership_precedes_source_writer(pipeline_context, monkeypatch):
    from abr_engine import pipeline

    settings, service = pipeline_context
    real = pipeline.write_qbcc_parquet

    def checked(result, path):
        assert not path.exists()
        with transaction(settings) as conn:
            row = conn.execute(
                "SELECT state,artifact_class FROM artifact_manifest WHERE local_path=%s",
                (str(path.resolve()),),
            ).fetchone()
            assert row == {"state": "writing", "artifact_class": "snapshot"}
        return real(result, path)

    monkeypatch.setattr(pipeline, "write_qbcc_parquet", checked)
    assert execute(settings, service, "qbcc")["status"] == "complete"
