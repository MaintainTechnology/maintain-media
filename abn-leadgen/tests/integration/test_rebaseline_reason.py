import json

from typer.testing import CliRunner

from abr_engine import cli
from abr_engine.control.service import Service
from abr_engine.db import transaction


def test_cli_rebaseline_preserves_exact_reason_and_emits_zero_events(
    settings, service, tmp_path, monkeypatch
):
    config = settings.model_copy(update={"output_dir": tmp_path})
    scoped_service = Service(config, service.keys)
    monkeypatch.setattr(cli, "context", lambda *args: (config, scoped_service))
    reason = "Legacy pre011 fixture artifact metadata requires an explicit verified baseline"
    response = CliRunner().invoke(cli.app, ["baseline", "abr", reason, "--mode", "fixture", "--json"])
    assert response.exit_code == 0, response.output
    result = json.loads(response.output)
    assert result["status"] == "complete" and result["sources"]["abr"]["events"] == 0
    with transaction(config) as conn:
        snapshot = conn.execute(
            "SELECT manifest FROM source_snapshot WHERE snapshot_id=%s",
            (result["sources"]["abr"]["snapshot_id"],),
        ).fetchone()["manifest"]
        request = conn.execute(
            "SELECT manifest FROM pipeline_run WHERE run_id=%s", (result["run_id"],)
        ).fetchone()["manifest"]["request"]
        assert snapshot["rebaseline_reason"] == request["rebaseline_reason"] == reason
        assert conn.execute("SELECT count(*) n FROM abr_event").fetchone()["n"] == 0
    resumed = CliRunner().invoke(cli.app, ["resume", result["run_id"], "--mode", "fixture", "--json"])
    assert resumed.exit_code == 0 and json.loads(resumed.output) == result


def test_cli_rebaseline_rejects_empty_reason_before_run(settings, service, monkeypatch):
    monkeypatch.setattr(cli, "context", lambda *args: (settings, service))
    response = CliRunner().invoke(cli.app, ["baseline", "abr", "short", "--mode", "fixture"])
    assert response.exit_code != 0
    with transaction(settings) as conn:
        assert conn.execute("SELECT count(*) n FROM pipeline_run").fetchone()["n"] == 0
