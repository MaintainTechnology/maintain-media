"""Durable weekly QBCC admission and separately gated finite maintenance.

Scheduling admits one request for the current UTC week. Existing source workers
perform its work; a scheduler never creates synthetic data or bypasses review.
"""
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.retention import retention_run
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError
from abr_engine.ingest.qbcc_review import _configured, cleanup_qbcc_review
from abr_engine.live.abr_cleanup import reconcile_attempts
from abr_engine.live.artifact_retention import run_artifact_retention
from abr_engine.live.runtime import QBCCRuntime

ACTOR = "scheduler:qbcc-weekly-v1"
NAMESPACE = uuid5(NAMESPACE_URL, "https://maintainmedia.com.au/abn-lead-gen/schedules/qbcc/v1")


def weekly_identity(settings, instant: datetime):
    if instant.tzinfo is None:
        raise ValueError("Timezone-aware scheduler time required")
    current = instant.astimezone(UTC)
    monday = (current - timedelta(days=current.weekday())).date()
    identifier = uuid5(NAMESPACE, f"{settings.mode}:{settings.schema_name}:{settings.issuer}:{monday.isoformat()}")
    return identifier, monday.isoformat()


def submit_weekly(settings, *, runtime=None):
    _configured(settings, collection=False)
    with transaction(settings) as conn:
        instant = Service.now(conn)
    identifier, week = weekly_identity(settings, instant)
    adapter = runtime or QBCCRuntime(settings)
    receipt = adapter.submit_run({"source": "qbcc", "request_id": str(identifier)}, ACTOR)
    return {"status": "held" if receipt["state"] in {"held", "failed"} else "complete",
        "operation": "weekly_qbcc_admission", "week_start_utc": week,
        "execution": "existing_source_worker", "job": receipt}


def maintenance(settings, *, kind: str, execute=False):
    """Explicit live config, DB time, preview default; zero source/vendor calls."""
    if kind not in {"review-staging", "retention"}:
        raise ValueError("Unknown maintenance kind")
    _configured(settings, collection=False)
    try:
        if kind == "review-staging":
            result = cleanup_qbcc_review(settings, execute=execute)
        else:
            service = Service(settings, load_keys(settings))
            # Neither namespace reconciliation nor full-file hashing may hold
            # the staff control lock. Each final file action re-admits authority.
            namespaces = reconcile_attempts(settings, execute=execute)
            with transaction(settings) as conn:
                now = Service.now(conn)
            artifacts = run_artifact_retention(service, now=now, execute=execute)
            with transaction(settings) as conn:
                service.personal_data_access(conn)
                result = retention_run(conn, service, now=Service.now(conn), execute=execute, skip_artifacts=True)
            result['artifacts'] = artifacts
            result['abr_namespaces'] = namespaces
            if (namespaces['status'] in {'held', 'complete_with_holds'}
                    or any(item['state'] == 'held' for item in artifacts)):
                result['status'] = 'complete_with_holds'
        held = result["status"] in {"held", "complete_with_holds"}
        return {"status": "held" if held else "complete" if execute else "preview",
            "operation": kind, "execute": execute, "result": result,
            "external_and_backups": "separate_receipts_required"}
    except (SourceError, DomainError) as error:
        return {"status": "held", "operation": kind, "execute": execute, "reason_codes": [error.code]}
