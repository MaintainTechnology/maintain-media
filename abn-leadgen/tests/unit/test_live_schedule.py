import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from abr_engine.cli import app
from abr_engine.config import Settings
from abr_engine.live.schedule import weekly_identity


def test_week_identity_uses_utc_monday_and_replays_current_week():
    settings = Settings()
    monday = datetime(2026, 9, 7, tzinfo=UTC)
    first, week = weekly_identity(settings, monday)
    assert week == "2026-09-07"
    assert weekly_identity(settings, monday+timedelta(days=6, hours=23))[0] == first
    assert weekly_identity(settings, monday-timedelta(microseconds=1))[0] != first
    assert weekly_identity(settings, monday+timedelta(days=7))[0] != first
    same_in_sydney = monday.astimezone(timezone(timedelta(hours=10)))
    assert weekly_identity(settings, same_in_sydney)[0] == first
    assert weekly_identity(settings.model_copy(update={"mode": "pilot"}), monday)[0] != first
    with pytest.raises(ValueError, match="Timezone"):
        weekly_identity(settings, datetime(2026, 9, 7))  # noqa: DTZ001 -- explicitly test naive-time rejection


@pytest.mark.parametrize("command", ["live-schedule-weekly", "live-maintenance"])
def test_live_scheduled_cli_refuses_dotenv_before_loading(command, monkeypatch):
    monkeypatch.setattr("abr_engine.cli.load_settings", lambda _: pytest.fail("Must not load an env file"))
    args = [command, "--config", ".env.local"]
    if command == "live-maintenance":
        args += ["--kind", "retention"]
    assert CliRunner().invoke(app, args).exit_code == 2


def test_maintenance_cli_preview_default_and_held_nonzero(monkeypatch):
    from abr_engine.live import schedule
    settings = Settings().model_copy(update={"mode": "pilot"})
    monkeypatch.setattr("abr_engine.cli.load_settings", lambda _: settings)
    executions = []
    def operation(actual, *, kind, execute):
        assert actual is settings and kind == "retention"
        executions.append(execute)
        return {"status": "held" if execute else "preview"}
    monkeypatch.setattr(schedule, "maintenance", operation)
    args = ["live-maintenance", "--config", "private.yaml", "--kind", "retention"]
    assert CliRunner().invoke(app, args).exit_code == 0
    held = CliRunner().invoke(app, args+["--execute"])
    assert held.exit_code == 3 and json.loads(held.stdout)["status"] == "held"
    assert executions == [False, True]


def test_weekly_cli_held_job_is_visible_and_not_reported_as_success(monkeypatch):
    from abr_engine.live import schedule
    monkeypatch.setattr("abr_engine.cli.load_settings", lambda _: Settings())
    monkeypatch.setattr(schedule, "submit_weekly", lambda _: {"status": "held", "job": {"reason_codes": ["GATE_G1_CLOSED"]}})
    result = CliRunner().invoke(app, ["live-schedule-weekly", "--config", "private.yaml"])
    assert result.exit_code == 3 and "GATE_G1_CLOSED" in result.stdout


def test_new_systemd_units_keep_admission_and_maintenance_separate_from_workers():
    root = Path(__file__).parents[2] / "ops/aws"
    for name, command in [("qbcc-weekly", "live-schedule-weekly"), ("qbcc-review-cleanup", "live-maintenance --kind review-staging --execute"),
                          ("retention", "live-maintenance --kind retention --execute")]:
        service = (root / f"abr-engine-{name}.service").read_text()
        timer = (root / f"abr-engine-{name}.timer").read_text()
        assert command in service and "--config /etc/abr-engine/pilot.yaml" in service
        assert "User=abr-engine" in service and "RestrictAddressFamilies=AF_UNIX" in service
        assert "Persistent=true" in timer and f"Unit=abr-engine-{name}.service" in timer
        assert "Conflicts=" in timer
        conflicts = next(line.split("=", 1)[1].split() for line in timer.splitlines() if line.startswith("Conflicts="))
        assert f"abr-engine-{name}.timer" not in conflicts
    assert "OnCalendar=Mon *-*-* 00:00:00 UTC" in (root / "abr-engine-qbcc-weekly.timer").read_text()
    assert "--lane source" in (root / "abr-engine-worker.service").read_text()
    assert "--lane control" in (root / "abr-engine-control.service").read_text()
    assert "live-schedule-weekly" not in (root / "abr-engine-worker.service").read_text()
