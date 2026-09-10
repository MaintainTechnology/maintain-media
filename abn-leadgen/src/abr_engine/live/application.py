"""Production-only application assembly; no environment files or fixture fallback."""
import os

import psycopg

from abr_engine.config import Settings
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction


def build_application(settings: Settings, *, environ=None):
    from abr_engine.control.sheets_auth import SheetsAuthority
    from abr_engine.live.api import create_live_app
    from abr_engine.live.auth import WebsiteAuthority
    from abr_engine.live.runtime import QBCCRuntime

    if settings.mode not in {"pilot", "production"}:
        raise ValueError("Explicit live settings required")
    values = os.environ if environ is None else environ
    authority = WebsiteAuthority(values.get("ABN_ENGINE_ASSERTION_KEY", ""))
    runtime = QBCCRuntime(settings)
    sheets = SheetsAuthority(settings.sheets_bridge_file) if settings.sheets_bridge_file else None
    return create_live_app(settings, authority=authority, submit_run=runtime.submit_run,
                           get_job=runtime.get_job, execute_job=runtime.execute_job,
                           sheets_authority=sheets)


def worker_tick(settings: Settings, *, lane_group="all") -> dict:
    """Recover durable requested jobs and pending removals. Never invent a run."""
    from abr_engine.compliance.keys import load_keys
    from abr_engine.export.crm import drain_live_one
    from abr_engine.ingest.common import SourceError
    from abr_engine.live.enrichment import execute_pending_websites
    from abr_engine.live.runtime import QBCCRuntime
    from abr_engine.ops.propagation import drain_propagation

    if settings.mode not in {"pilot", "production"}:
        raise ValueError("Explicit live settings required")
    if lane_group not in {"all", "source", "control"}:
        raise ValueError("Unknown worker lane")
    service = Service(settings, load_keys(settings))
    # Each worker revalidates authority at the actual I/O boundary. Revoked
    # acquisition may still require current approved suppression propagation.
    def lane(operation):
        try:
            return operation()
        except (DomainError, SourceError) as error:
            return {"status": "held", "code": error.code}
        except (ValueError, OSError, psycopg.Error):
            return {"status": "unavailable", "code": "WORKER_LANE_UNAVAILABLE"}

    # Removals take priority. Each lane is isolated so a closed vendor gate or
    # failed acquisition cannot stop another lane's necessary recovery work.
    result = {}
    if lane_group != "source":
        result["propagation"] = lane(lambda: drain_propagation(settings, service, limit=10))
    if lane_group != "control":
        result["source_jobs"] = lane(lambda: QBCCRuntime(settings).execute_pending(limit=1))
        result["website_jobs"] = lane(lambda: execute_pending_websites(settings, limit=1))
    if lane_group == "source":
        return result
    with transaction(settings) as conn:
        candidates = conn.execute(
            "SELECT outbox_id FROM crm_outbox WHERE (state IN ('pending','retry','uncertain','inflight') "
            "OR (state='blocked' AND operation_kind IN ('create','update'))) "
            "AND (next_attempt_at IS NULL OR next_attempt_at<=now()) "
            "AND (lease_until IS NULL OR lease_until<=now()) "
            "ORDER BY next_attempt_at NULLS FIRST,outbox_id LIMIT 10"
        ).fetchall()
    receipts = []
    for row in candidates:
        receipts.append(lane(lambda row=row: drain_live_one(settings, service, row["outbox_id"])))
    result["crm"] = receipts
    return result
