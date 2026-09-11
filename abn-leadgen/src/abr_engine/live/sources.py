"""Exact live-source routing; ABR is admitted here and executed by its own worker."""
from uuid import UUID

from abr_engine.control.service import DomainError
from abr_engine.db import transaction
from abr_engine.live.abr import ABRRuntime
from abr_engine.live.runtime import QBCCRuntime


class SourceRuntime:
    def __init__(self, settings, **kwargs):
        self.settings = settings
        self.runtimes: dict[str, QBCCRuntime | ABRRuntime] = {"qbcc": QBCCRuntime(settings, **kwargs), "abr": ABRRuntime(settings, **kwargs)}

    def submit_run(self, payload, actor):
        source = payload.get("source", "qbcc")
        if source not in ("qbcc", "abr"):
            raise DomainError("EXACT_LIVE_SOURCE_REQUIRED", 422)
        return self.runtimes[source].submit_run(payload, actor)

    def _runtime(self, job_id):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT manifest FROM pipeline_run WHERE run_id=%s AND mode=%s",
                               (UUID(str(job_id)), self.settings.mode)).fetchone()
            kind = row["manifest"].get("kind") if row else None
        source = {"qbcc_live_job": "qbcc", "abr_live_job": "abr"}.get(kind) if isinstance(kind, str) else None
        if source is None:
            raise DomainError("NOT_FOUND", 404)
        return self.runtimes[source]

    def get_job(self, job_id):
        return self._runtime(job_id).get_job(job_id)

    def kick_job(self, job_id):
        runtime = self._runtime(job_id)
        # A multi-hour import must never occupy the web process/background task.
        return runtime.get_job(job_id) if isinstance(runtime, ABRRuntime) else runtime.execute_job(job_id)
