import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from psycopg import OperationalError
from typer.testing import CliRunner

from abr_engine.cli import app
from abr_engine.compliance.policy import REQUIRED_GATES, gate_reasons
from abr_engine.config import Settings
from abr_engine.ops.readiness import readiness_report

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def gate(name, **overrides):
    return {"gate_name": name, "environment": "pilot", "scope": "collection", "revision": 1,
            "approved_at": NOW - timedelta(days=1), "expires_at": NOW + timedelta(days=1),
            "evidence_ref": "restricted-reference", "evidence_sha256": "a" * 64, **overrides}


def test_gates_and_switches_cannot_hide_unimplemented_runtime_paths():
    config = Settings().model_copy(update={"mode": "pilot", "capabilities": {"collection": True}})
    rows = [gate(name) for name in REQUIRED_GATES["collection"]]
    result = readiness_report(config, rows, target="pilot", now=NOW)
    collection = result["checks"][0]
    assert collection["missing_gates"] == []
    assert collection["status"] == "blocked"
    assert "LIVE_PIPELINE_NOT_CONNECTED" in collection["blockers"]
    assert result["status"] == "blocked"


def test_latest_expired_revision_blocks_older_approval_and_other_environment_is_ignored():
    rows = [gate("G1"), gate("G1", revision=2, expires_at=NOW),
            gate("G2", environment="production"), gate("G3", evidence_sha256="z" * 64),
            gate("G7", approved_at=NOW + timedelta(seconds=1))]
    result = readiness_report(Settings(), rows, target="pilot", now=NOW)
    assert result["checks"][0]["approved_gates"] == []
    assert set(result["checks"][0]["missing_gates"]) == {"G1", "G2", "G3", "G7"}
    assert "restricted-reference" not in json.dumps(result)


def test_pilot_does_not_claim_abr_or_need_elapsed_pilot_expansion_gate():
    pilot = readiness_report(Settings(), [], target="pilot", now=NOW)
    production = readiness_report(Settings(), [], target="production", now=NOW)
    assert {c["capability"] for c in pilot["checks"]} == {"collection", "crm"}
    assert "G6" not in {g for c in pilot["checks"] for g in c["missing_gates"]}
    assert "G6" in production["checks"][2]["missing_gates"]


def test_database_outage_returns_redacted_blockers_without_loading_keys(monkeypatch):
    def fail(*args, **kwargs):
        raise OperationalError("password=never-print-me")
    monkeypatch.setattr("abr_engine.cli.transaction", fail)
    monkeypatch.setattr("abr_engine.cli.load_keys", lambda _: (_ for _ in ()).throw(AssertionError("no keys")))
    result = CliRunner().invoke(app, ["release-check", "--mode", "pilot"])
    assert result.exit_code == 6
    receipt = json.loads(result.stdout)
    assert receipt["database_authority_available"] is False
    assert "DATABASE_AUTHORITY_UNAVAILABLE" in receipt["checks"][0]["blockers"]
    assert "never-print-me" not in result.stdout


@pytest.mark.parametrize("invalid", [
    {"evidence_sha256": "z" * 64}, {"evidence_sha256": "A" * 64},
    {"evidence_sha256": "a" * 63}, {"evidence_ref": " \t"},
    {"approved_at": NOW + timedelta(seconds=1)}, {"expires_at": NOW},
    {"approved_at": NOW.replace(tzinfo=None)},
])
def test_live_admission_and_report_reject_the_same_invalid_evidence(invalid):
    config = Settings().model_copy(update={"mode": "pilot", "capabilities": {"collection": True}})
    rows = [gate(name, **(invalid if name == "G1" else {})) for name in REQUIRED_GATES["collection"]]

    class Authority:
        def execute(self, query, params):
            assert "DISTINCT ON (gate_name)" in query and "revision DESC" in query
            assert params == ("pilot", "collection")
            return self

        def fetchall(self):
            return rows

    assert gate_reasons(Authority(), config, "collection", NOW) == ["GATE_G1_CLOSED"]
    report = readiness_report(config, rows, target="pilot", now=NOW)
    assert report["checks"][0]["missing_gates"] == ["G1"]


def intake_args(config="private.yaml"):
    return ["sources", "stage-qbcc", "--config", config, "--file", "publisher.csv",
            "--source-sha256", "a" * 64, "--inventory-before-sha256", "b" * 64,
            "--inventory-after-sha256", "b" * 64, "--mapping-evidence-ref", "restricted-record",
            "--mapping-evidence-sha256", "c" * 64, "--retrieved-at", "2026-09-09T12:00:00Z",
            "--expected-cursor-version", "0", "--run-id", "00000000-0000-4000-8000-000000000001"]


def test_intake_cli_accepts_aware_timestamp_and_preserves_declared_mode(monkeypatch):
    from abr_engine.ingest import qbcc_review

    config = Settings().model_copy(update={"mode": "pilot"})
    monkeypatch.setattr("abr_engine.cli.load_settings", lambda path: config)

    def stage(settings, request):
        assert settings is config and settings.mode == "pilot"
        assert request.retrieved_at == datetime(2026, 9, 9, 12, tzinfo=UTC)
        assert request.run_id == UUID("00000000-0000-4000-8000-000000000001")
        return {"state": "needs_review", "accepted": False}

    monkeypatch.setattr(qbcc_review, "stage_qbcc_review", stage)
    result = CliRunner().invoke(app, intake_args())
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"state": "needs_review", "accepted": False}


def test_intake_cli_preserves_closed_reason_without_reading_input_or_keys(monkeypatch):
    from abr_engine.ingest import qbcc_review

    monkeypatch.setattr("abr_engine.cli.load_settings", lambda path: Settings())
    monkeypatch.setattr(qbcc_review, "load_keys", lambda _: (_ for _ in ()).throw(AssertionError("no keys")))
    result = CliRunner().invoke(app, intake_args())
    assert result.exit_code == 3
    assert json.loads(result.stdout)["code"] == "LIVE_QBCC_CONFIGURATION_REQUIRED"
    assert "publisher.csv" not in result.stdout


def test_intake_cli_rejects_dotenv_configuration_before_loading_it(monkeypatch):
    monkeypatch.setattr("abr_engine.cli.load_settings", lambda _: (_ for _ in ()).throw(AssertionError("no env files")))
    result = CliRunner().invoke(app, intake_args(".env.local"))
    assert result.exit_code == 2
    assert json.loads(result.stdout)["code"] == "INPUT_OR_ARTIFACT_INVALID"


def test_intake_cleanup_cli_previews_by_default_and_reports_holds_as_failure(monkeypatch):
    from abr_engine.ingest import qbcc_review

    config = Settings().model_copy(update={"mode": "pilot"})
    monkeypatch.setattr("abr_engine.cli.load_settings", lambda path: config)
    executions = []

    def cleanup(settings, *, run_id, execute):
        assert settings is config and run_id is None
        executions.append(execute)
        return {"status": "held" if execute else "preview", "decrypted_records": 0}

    monkeypatch.setattr(qbcc_review, "cleanup_qbcc_review", cleanup)
    args = ["sources", "cleanup-qbcc-review", "--config", "private.yaml"]
    preview = CliRunner().invoke(app, args)
    assert preview.exit_code == 0
    assert json.loads(preview.stdout)["status"] == "preview"
    held = CliRunner().invoke(app, args + ["--execute"])
    assert held.exit_code == 3
    assert json.loads(held.stdout)["status"] == "held"
    assert executions == [False, True]
