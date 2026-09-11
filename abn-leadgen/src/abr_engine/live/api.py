"""Live control API. An empty production database is a valid, honest workspace."""

from typing import Literal
from uuid import UUID

from fastapi import BackgroundTasks, Request
from fastapi.responses import Response

from abr_engine.control.api import create_app
from abr_engine.control.service import DomainError, json_safe
from abr_engine.dashboard.models import RunRequest, SettingsPatch
from abr_engine.db import transaction
from abr_engine.live.auth import WebsiteAuthority
from abr_engine.live.dashboard import dashboard_state, job_projection, save_preferences


class LiveRunRequest(RunRequest):
    source: Literal["qbcc", "abr"] | None = None


def create_live_app(settings, *, authority: WebsiteAuthority, submit_run=None, get_job=None,
                    execute_job=None, sheets_authority=None):
    if settings.mode not in {"pilot", "production"}:
        raise ValueError("Live API requires explicit live mode")
    def authenticate_live(request):
        if any(key.startswith("x-bridge-") for key in request.headers):
            if sheets_authority is None:
                raise DomainError("UNAUTHENTICATED", 401)
            return sheets_authority(request)
        return authority(request)

    app = create_app(settings, authenticate_request=authenticate_live)
    service = app.state.service
    actor_for, mutate = app.state.actor_for, app.state.mutate

    @app.get("/v1/sheets/worklist")
    def sheets_worklist(request: Request):
        from abr_engine.control.sheets_auth import load_bridge_registry
        from abr_engine.export.sheets import pull_worklist

        # This is a workbook-bound disclosure endpoint. A website assertion,
        # even from an owner, must never borrow the installed Sheet's authority.
        if sheets_authority is None or not settings.sheets_bridge_file or not any(
            key.startswith("x-bridge-") for key in request.headers
        ):
            raise DomainError("UNAUTHENTICATED", 401)
        actor = actor_for(request, ("operator", "reviewer", "compliance"))
        registry = load_bridge_registry(settings.sheets_bridge_file)
        return pull_worklist(settings, service, actor, registry)

    @app.get("/api/dashboard")
    def dashboard(request: Request):
        actor = actor_for(request, ("admin",))
        with transaction(settings) as conn:
            return dashboard_state(conn, service, actor, worker_available=submit_run is not None)

    @app.get("/api/worklist.csv")
    def current_worklist(request: Request):
        from abr_engine.dashboard.service import dashboard_report
        from abr_engine.export.worklist import report_context

        actor = actor_for(request, ("admin",))
        with transaction(settings) as conn:
            service.personal_data_access(conn)
            row = conn.execute("SELECT worklist_id FROM worklist ORDER BY week DESC LIMIT 1").fetchone()
            if not row:
                raise DomainError("WORKLIST_NOT_FOUND", 404)
            context = report_context(conn, service, row["worklist_id"], row["worklist_id"])
            payload = dashboard_report(context, "csv")
            service.audit(conn, actor.actor_id, "current_worklist_downloaded", row["worklist_id"])
        return Response(payload, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="current-worklist.csv"'})

    @app.patch("/api/settings")
    def preferences(data: SettingsPatch, request: Request):
        patch = data.model_dump(exclude_unset=True)
        if not patch or any(value is None for value in patch.values()):
            raise DomainError("INVALID_SETTINGS", 422)
        return mutate(
            request, patch, ("admin",), lambda c, d, a, k: save_preferences(c, service, d, a.actor_id), 200
        )

    @app.post("/api/runs", status_code=202)
    def run(data: LiveRunRequest, request: Request, background_tasks: BackgroundTasks):
        actor = actor_for(request, ("admin",))
        if str(data.request_id) != request.headers.get("idempotency-key"):
            raise DomainError("REQUEST_IDENTIFIERS_REQUIRED", 422)
        if submit_run is None:
            raise DomainError("RUN_WORKER_UNAVAILABLE", 503)
        result = submit_run(data.model_dump(exclude_none=True), actor.actor_id)
        if execute_job is not None and result.get("state") == "queued":
            background_tasks.add_task(execute_job, str(result["job_id"]))
        return job_projection(result)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: UUID, request: Request):
        actor_for(request, ("admin",))
        if get_job is None:
            raise DomainError("RUN_WORKER_UNAVAILABLE", 503)
        return job_projection(get_job(str(job_id)))

    # Import lazily at app construction; no source I/O occurs on import.
    from abr_engine.live.enrichment import (
        WebsiteCollection,
        execute_website_collection,
        get_website_collection,
        submit_website_collection,
    )
    from abr_engine.live.qbcc import QBCCLicenceReview, list_qbcc_reviews, review_qbcc_licence

    @app.post("/v1/website-collections", status_code=202)
    def website_collection(data: WebsiteCollection, request: Request, background_tasks: BackgroundTasks):
        actor = actor_for(request, ("reviewer",))
        if str(data.request_id) != request.headers.get("idempotency-key"):
            raise DomainError("REQUEST_IDENTIFIERS_REQUIRED", 422)
        result = submit_website_collection(settings, data.model_dump(), actor.actor_id)
        if result["state"] == "queued":
            background_tasks.add_task(execute_website_collection, settings, result["job_id"])
        return job_projection(result)

    @app.get("/api/website-jobs/{job_id}")
    def website_job(job_id: UUID, request: Request):
        actor_for(request, ("reviewer",))
        with transaction(settings) as conn:
            service.personal_data_access(conn)
        return job_projection(get_website_collection(settings, job_id))

    @app.get("/api/qbcc-reviews")
    @app.get("/api/qbcc-reviews/{offset}")
    def source_rows(request: Request, offset: int = 0):
        actor = actor_for(request, ("reviewer",))
        if offset < 0 or offset > 100_000:
            raise DomainError("INVALID_INPUT", 422)
        with transaction(settings) as conn:
            result = list_qbcc_reviews(conn, service, limit=100, offset=offset)
            service.audit(conn, actor.actor_id, "qbcc_source_review_read", "source", {"offset": offset})
        return json_safe(result)

    @app.post("/v1/qbcc-reviews")
    def source_review(data: QBCCLicenceReview, request: Request):
        if str(data.request_id) != request.headers.get("idempotency-key"):
            raise DomainError("REQUEST_IDENTIFIERS_REQUIRED", 422)
        return mutate(
            request,
            data.model_dump(),
            ("reviewer",),
            lambda c, d, a, k: review_qbcc_licence(c, service, d, a.actor_id),
        )

    return app
