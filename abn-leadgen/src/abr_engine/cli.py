"""Operator CLI; JSON outputs contain receipts and counts, never contact values."""
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

import duckdb
import psycopg
import typer
from pydantic import ValidationError

from abr_engine.compliance.keys import load_keys
from abr_engine.config import load_settings
from abr_engine.control.auth import fixture_token
from abr_engine.control.service import DomainError, Service, json_safe
from abr_engine.db import migrate, transaction
from abr_engine.pipeline import execute

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
db_app = typer.Typer()
app.add_typer(db_app, name="db")
work_app = typer.Typer()
app.add_typer(work_app, name="worklist")
wash_app = typer.Typer()
app.add_typer(wash_app, name="wash")
retention_app = typer.Typer()
app.add_typer(retention_app, name="retention")
crm_app = typer.Typer()
app.add_typer(crm_app, name="crm")
backup_app = typer.Typer()
app.add_typer(backup_app, name="backup")
alarms_app = typer.Typer()
app.add_typer(alarms_app, name="alarms")
propagation_app = typer.Typer()
app.add_typer(propagation_app, name="propagation")


def output(value):
    typer.echo(json.dumps(json_safe(value), indent=2))


def context(config: Path | None, mode: str):
    try:
        settings = load_settings(config, mode)
        return settings, Service(settings, load_keys(settings))
    except (ValidationError, ValueError, OSError):
        output({"status": "invalid", "code": "INVALID_CONFIGURATION"})
        raise typer.Exit(2) from None


def guarded(operation):
    try:
        result = operation()
        output(result)
        if isinstance(result, dict) and result.get("status") == "held":
            raise typer.Exit(3)
        if isinstance(result, dict) and result.get("status") == "failed":
            raise typer.Exit(5)
    except DomainError as exc:
        output({"status": "blocked", "code": exc.code})
        raise typer.Exit(6 if "PENDING" in exc.code or "DISABLED" in exc.code or "GATE" in exc.code else 2) from None
    except psycopg.Error:
        output({"status": "unavailable", "code": "DATABASE_AUTHORITY_UNAVAILABLE"})
        raise typer.Exit(5) from None
    except duckdb.Error:
        output({"status": "held", "code": "ANALYTICS_RESOURCE_OR_DATA_FAILURE"})
        raise typer.Exit(3) from None
    except (ValueError, OSError):
        output({"status": "invalid", "code": "INPUT_OR_ARTIFACT_INVALID"})
        raise typer.Exit(2) from None


@app.command("validate-config")
def validate_config(config: Path | None = None, mode: str = "fixture", json: bool = False):
    settings, _ = context(config, mode)
    output({"status": "valid", "mode": settings.mode, "live_integrations": "disabled" if not any(settings.capabilities.values()) else "gate_checks_required"})


@db_app.command("migrate")
def db_migrate(config: Path | None = None, mode: str = "fixture", json: bool = False):
    settings, _ = context(config, mode)
    guarded(lambda: {"status": "complete", "migrations": migrate(settings)})


@app.command("run")
def run(source: str = "all", config: Path | None = None, mode: str = "fixture", json: bool = False,
        run_id: UUID | None = None, abr_fixture: str = "abr_baseline"):
    settings, service = context(config, mode)
    if source not in {"qbcc", "abr", "all"} or abr_fixture not in {"abr_baseline", "abr_changed", "abr_same_date_correction", "abr_identical_republish"}:
        raise typer.BadParameter("Choose a supported source/fixture")
    guarded(lambda: execute(settings, service, source, run_id, abr_fixture=abr_fixture))


@app.command("resume")
def resume(run_id: UUID, stage: str = "all", config: Path | None = None, mode: str = "fixture", json: bool = False):
    settings, service = context(config, mode)
    if stage not in {"all", "abr", "qbcc"}:
        raise typer.BadParameter("Stage must be all, abr or qbcc")
    def operation():
        with transaction(settings) as conn:
            if not conn.execute("SELECT 1 FROM pipeline_run WHERE run_id=%s", (run_id,)).fetchone():
                raise DomainError("RUN_NOT_FOUND", 404)
        return execute(settings, service, stage, run_id)
    guarded(operation)


@app.command("token")
def token(actor: str = "fixture-reviewer", config: Path | None = None):
    _, service = context(config, "fixture")
    typer.echo(fixture_token(service, actor))


@app.command("serve")
def serve(port: int = 8766, config: Path | None = None, mode: str = "fixture"):
    settings, _ = context(config, mode)
    if settings.mode != "fixture":
        output({"code": "TLS_IDENTITY_DEPLOYMENT_GATE_REQUIRED"})
        raise typer.Exit(6)
    import uvicorn

    from abr_engine.control.api import create_app
    uvicorn.run(create_app(settings), host="127.0.0.1", port=port, access_log=False)


@work_app.command("build")
def worklist_build(week: str, config: Path | None = None, mode: str = "fixture", json: bool = False):
    from datetime import date

    from abr_engine.export.worklist import build_worklist
    settings, service = context(config, mode)
    def operation():
        with transaction(settings) as conn:
            return build_worklist(conn, service, date.fromisoformat(week))
    guarded(operation)


@wash_app.command("import")
def wash_import(file: Path, receipt: Path, batch_id: UUID, config: Path | None = None,
                mode: str = "fixture", json: bool = False):
    import json as jsonlib

    from abr_engine.compliance.wash import import_receipt
    settings, service = context(config, mode)
    def operation():
        with transaction(settings) as conn:
            return import_receipt(conn, service, batch_id, jsonlib.loads(file.read_text()),
                                  jsonlib.loads(receipt.read_text()), "fixture-operator")
    guarded(operation)


@app.command("baseline")
def baseline(source: str, reason: str, config: Path | None = None, mode: str = "fixture", json: bool = False):
    settings, service = context(config, mode)
    if source != "abr" or not 10 <= len(reason.strip()) <= 2000 or len(reason) > 2000:
        raise typer.BadParameter("ABR baseline requires an explicit history-gap or schema-change reason")
    guarded(lambda: execute(settings, service, "abr", rebaseline=True, rebaseline_reason=reason))


@retention_app.command("run")
def retention_run(as_of: str | None = None, execute: bool = False, config: Path | None = None,
                  mode: str = "fixture", json: bool = False):
    from datetime import datetime

    from abr_engine.compliance.retention import retention_run as apply_retention
    settings, service = context(config, mode)
    def operation():
        with transaction(settings) as conn:
            now = datetime.fromisoformat(as_of) if as_of else service.now(conn)
            if now.tzinfo is None:
                raise ValueError("Timezone required")
            return apply_retention(conn, service, now=now, execute=execute)
    guarded(operation)


@crm_app.command("drain")
def crm_drain(limit: int = 60, config: Path | None = None, mode: str = "fixture", json: bool = False):
    from abr_engine.export.crm import drain_one
    from abr_engine.export.mock_provider import PersistentMockCRM
    from abr_engine.ops.propagation import drain_propagation
    settings, service = context(config, mode)
    if not 1 <= limit <= 60:
        raise typer.BadParameter("Limit must be 1–60")
    def operation():
        if mode != "fixture":
            raise DomainError("LIVE_CRM_DISABLED", 403)
        priority_stops = drain_propagation(settings, service, limit=limit)
        with transaction(settings) as conn:
            rows = conn.execute("SELECT outbox_id FROM crm_outbox WHERE state IN ('pending','retry','uncertain','inflight') "
                                "OR (state='blocked' AND operation_kind IN ('create','update')) ORDER BY outbox_id LIMIT %s", (limit,)).fetchall()
        provider = PersistentMockCRM(settings, service.keys)
        results = [drain_one(settings, service, provider, row["outbox_id"]) for row in rows]
        return {"status": "complete", "mode": "fixture", "live_api_calls": 0,
                "priority_stops": priority_stops, "results": results,
                "followup_stops": drain_propagation(settings, service, limit=limit)}
    guarded(operation)


@app.command("benchmark")
def benchmark(output_path: Annotated[Path, typer.Option("--output")], rows: int = 20500000):
    from abr_engine.ops.benchmark import benchmark as run_benchmark
    guarded(lambda: run_benchmark(rows, output_path))


@backup_app.command("drill")
def backup_drill(config: Path | None = None, mode: str = "fixture"):
    from abr_engine.ops.backup import run_fixture_drill
    settings, service = context(config, mode)
    guarded(lambda: run_fixture_drill(settings, service))


@alarms_app.command("check")
def alarms_check(run_id: UUID | None = None, observations: Path | None = None,
                 config: Path | None = None, mode: str = "fixture"):
    from abr_engine.ops.monitor import Observation, monitor_run, persist_observation
    settings, service = context(config, mode)
    def operation():
        with transaction(settings) as conn:
            selected = run_id
            if selected is None:
                recent = conn.execute("SELECT run_id FROM pipeline_run ORDER BY started_at DESC LIMIT 1").fetchone()
                if not recent:
                    raise DomainError("RUN_NOT_FOUND", 404)
                selected = recent["run_id"]
            result = monitor_run(conn, service, selected)
            if observations:
                if observations.stat().st_size > 65536:
                    raise ValueError("Observation inventory too large")
                payload = json.loads(observations.read_text(encoding="utf-8"))
                if not isinstance(payload, list) or not 1 <= len(payload) <= 2:
                    raise ValueError("One or two closed source observations required")
                items = [Observation.model_validate(item) for item in payload]
                if any(item.run_id != selected or item.observed_at > service.now(conn) for item in items):
                    raise ValueError("Inventory run/date mismatch")
                result["imported"] = [persist_observation(conn, item) for item in items]
            return result
    guarded(operation)


@propagation_app.command("drain")
def propagation_drain(limit: int = 60, config: Path | None = None, mode: str = "fixture"):
    from abr_engine.ops.propagation import drain_propagation
    settings, service = context(config, mode)
    guarded(lambda: drain_propagation(settings, service, limit=limit))


@alarms_app.command("drain")
def alarms_drain(limit: int = 60, config: Path | None = None, mode: str = "fixture"):
    from abr_engine.ops.monitor import drain_mock
    settings, service = context(config, mode)
    guarded(lambda: drain_mock(settings, service, limit=limit))


@app.command("cost-import")
def cost_import(evidence: Path, config: Path | None = None, mode: str = "fixture"):
    """Import an explicit approved cost statement; no purchase or inferred allocation."""
    from abr_engine.ops.costs import CostStatement, import_costs
    from abr_engine.ops.summary import operational_summary
    settings, service = context(config, mode)
    def operation():
        if evidence.stat().st_size > 65536:
            raise ValueError("Cost statement too large")
        statement = CostStatement.model_validate_json(evidence.read_text(encoding="utf-8"))
        with transaction(settings) as conn:
            receipt = import_costs(conn, service, statement)
            run = conn.execute("SELECT run_id FROM pipeline_run ORDER BY started_at DESC LIMIT 1").fetchone()
            if run:
                receipt["summary"] = operational_summary(conn, service, run["run_id"], statement.period_start, statement.period_end)
            return receipt
    guarded(operation)


if __name__ == "__main__":
    app()
