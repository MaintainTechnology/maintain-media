import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from psycopg import OperationalError
from typer.testing import CliRunner

from abr_engine.cli import app
from abr_engine.compliance.policy import REQUIRED_GATES, gate_reasons
from abr_engine.config import Settings
from abr_engine.ops.readiness import RUNTIME_CHECKS, readiness_report

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def gate(name, **overrides):
    return {"gate_name": name, "environment": "pilot", "scope": "collection", "revision": 1,
            "approved_at": NOW - timedelta(days=1), "expires_at": NOW + timedelta(days=1),
            "evidence_ref": "restricted-reference", "evidence_sha256": "a" * 64, **overrides}


def observed(capability="collection", **overrides):
    return {"environment": "pilot", "capability": capability, "revision": 1,
            "observed_at": NOW-timedelta(hours=1), "expires_at": NOW+timedelta(hours=1),
            "evidence_ref": "private-runtime-observation", "evidence_sha256": "b"*64,
            "checks": {name: True for name in RUNTIME_CHECKS[capability]}, **overrides}


def test_gates_and_switches_do_not_prove_installed_runtime():
    config = Settings().model_copy(update={"mode": "pilot", "capabilities": {"collection": True}})
    rows = [gate(name) for name in REQUIRED_GATES["collection"]]
    result = readiness_report(config, rows, target="pilot", now=NOW)
    collection = result["checks"][0]
    assert collection["missing_gates"] == []
    assert collection["status"] == "blocked"
    assert collection["implementation_status"] == "implemented"
    assert "LIVE_PIPELINE_NOT_CONNECTED" not in collection["blockers"]
    assert "LIVE_RUNTIME_EVIDENCE_UNVERIFIED" in collection["blockers"]
    assert collection["runtime"]["status"] == "unverified"
    assert result["target_service_installed"] is None and result["production_installed"] is None
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
    assert {c["capability"] for c in pilot["checks"]} == {"collection", "crm", "sheets"}
    assert "G6" not in {g for c in pilot["checks"] for g in c["missing_gates"]}
    abr = next(check for check in production["checks"] if check["capability"] == "abr")
    assert "G6" in abr["missing_gates"]
    assert "ABR_QUALIFICATION_RELEASE_PENDING" in abr["blockers"]


def test_verified_pilot_observations_and_current_approvals_are_distinct_requirements():
    capabilities = ("collection", "crm", "sheets")
    settings = Settings().model_copy(update={"mode": "pilot", "capabilities": dict.fromkeys(capabilities, True)})
    rows = [gate(name, scope=capability) for capability in capabilities for name in REQUIRED_GATES[capability]]
    receipts = [observed(capability) for capability in capabilities]
    result = readiness_report(settings, rows, target="pilot", now=NOW, runtime_evidence=receipts)
    assert result["status"] == "ready"
    assert result["target_service_installed"] is True and result["production_installed"] is None
    assert {check["implementation_status"] for check in result["checks"]} == {"implemented"}
    assert {check["runtime"]["status"] for check in result["checks"]} == {"verified"}
    text = json.dumps(result)
    assert "private-runtime-observation" not in text and "b"*64 not in text and "restricted-reference" not in text

    unapproved = readiness_report(settings, [], target="pilot", now=NOW, runtime_evidence=receipts)
    assert unapproved["status"] == "blocked" and unapproved["target_service_installed"] is True
    assert unapproved["checks"][0]["runtime"]["status"] == "verified"
    assert "GATE_G1_CLOSED" in unapproved["checks"][0]["blockers"]
    disabled = readiness_report(Settings(), rows, target="pilot", now=NOW, runtime_evidence=receipts)
    assert disabled["status"] == "blocked"
    assert "CAPABILITY_DISABLED" in disabled["checks"][0]["blockers"]
    assert "TARGET_ENVIRONMENT_NOT_CONFIGURED" in disabled["checks"][0]["blockers"]


def test_latest_failed_runtime_observation_and_database_outage_block_release():
    bad = observed(revision=2, checks={name: name != "backup_restore" for name in RUNTIME_CHECKS["collection"]})
    result = readiness_report(Settings(), [], target="pilot", now=NOW, runtime_evidence=[observed(), bad],
                              database_available=False)
    current = result["checks"][0]
    assert current["runtime"]["status"] == "failed"
    assert current["runtime"]["failed_checks"] == ["backup_restore"]
    assert "LIVE_RUNTIME_CHECK_FAILED" in current["blockers"]
    assert "DATABASE_AUTHORITY_UNAVAILABLE" in current["blockers"]


def test_website_enabling_requires_separate_current_evidence_and_source_readiness():
    capabilities = ("collection", "crm", "sheets", "website_collection")
    config = Settings().model_copy(update={"mode": "pilot", "capabilities": dict.fromkeys(capabilities, True)})
    rows = [gate(name, scope=cap) for cap in capabilities if cap != "website_collection" for name in REQUIRED_GATES[cap]]
    receipts = [observed(cap) for cap in capabilities]
    report = readiness_report(config, rows, target="pilot", now=NOW, runtime_evidence=receipts)
    website = next(c for c in report["checks"] if c["capability"] == "website_collection")
    assert website["missing_gates"] == ["G1", "G3", "G7"] and report["status"] == "blocked"
    rows.extend(gate(name, scope="website_collection") for name in REQUIRED_GATES["website_collection"])
    assert readiness_report(config, rows, target="pilot", now=NOW, runtime_evidence=receipts)["status"] == "ready"
    config.capabilities["collection"] = False
    report = readiness_report(config, rows, target="pilot", now=NOW, runtime_evidence=receipts)
    assert "DEPENDENCY_COLLECTION_BLOCKED" in report["checks"][-1]["blockers"]


@pytest.mark.parametrize("changes", [
    {"expires_at": NOW}, {"observed_at": NOW+timedelta(seconds=1)},
    {"observed_at": NOW.replace(tzinfo=None)}, {"evidence_ref": " "},
    {"evidence_sha256": "z"*64}, {"checks": {name: "passed" for name in RUNTIME_CHECKS["collection"]}},
    {"checks": {}}, {"revision": True}, {"revision": "2"}, {"extra_field": "private-never-reflect"},
])
def test_invalid_newer_observation_cannot_fall_back_to_old_runtime_proof(changes):
    receipts = [observed(), observed(**{"revision": 2, **changes})]
    result = readiness_report(Settings(), [], target="pilot", now=NOW, runtime_evidence=receipts)
    assert result["checks"][0]["runtime"]["status"] == "unverified"
    assert result["target_service_installed"] is None
    assert "private-never-reflect" not in json.dumps(result)


def test_observation_requires_matching_target_and_unique_revision():
    for receipts in ([observed(environment="production")], [observed(), observed()]):
        result = readiness_report(Settings(), [], target="pilot", now=NOW, runtime_evidence=receipts)
        assert result["checks"][0]["runtime"]["status"] == "unverified"


def test_receipt_can_use_iso_dates_but_cannot_approve_abr_generation_mapping():
    capabilities = ("collection", "crm", "sheets", "abr")
    config = Settings().model_copy(update={"mode": "production", "capabilities": dict.fromkeys(capabilities, True)})
    rows = [gate(name, environment="production", scope=cap) for cap in capabilities for name in REQUIRED_GATES[cap]]
    receipts = [observed(cap, environment="production", observed_at=(NOW-timedelta(hours=1)).isoformat(),
                         expires_at=(NOW+timedelta(hours=1)).isoformat()) for cap in capabilities]
    result = readiness_report(config, rows, target="production", now=NOW, runtime_evidence=receipts)
    assert result["status"] == "blocked" and result["production_installed"] is True
    abr = next(check for check in result["checks"] if check["capability"] == "abr")
    assert abr["blockers"] == ["ABR_QUALIFICATION_RELEASE_PENDING"]
    assert abr["implementation_status"] == "observe_only_implemented"


def test_declared_production_mode_does_not_claim_installation():
    config = Settings().model_copy(update={"mode": "production", "capabilities": {"collection": True}})
    result = readiness_report(config, [], target="production", now=NOW)
    assert result["production_installed"] is None and result["target_service_installed"] is None


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
