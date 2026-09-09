"""Same-origin, loopback-only fixture UI; no production authentication bypass."""

from __future__ import annotations

import hmac
import ipaddress
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from abr_engine.config import Settings, load_settings
from abr_engine.control.service import DomainError
from abr_engine.dashboard.models import RunRequest, SettingsPatch
from abr_engine.dashboard.service import Dashboard
from abr_engine.db import transaction


def loopback(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value == "localhost"


def create_app(settings: Settings | None = None) -> FastAPI:
    dashboard = Dashboard(settings or load_settings())
    app = FastAPI(title="Maintain Media ABN dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.dashboard = dashboard
    token = secrets.token_urlsafe(32)
    static = Path(__file__).parent / "static"

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        client = request.client.host if request.client else ""
        try:
            host = urlsplit("http://" + request.headers.get("host", ""))
            host_valid = bool(host.hostname and loopback(host.hostname) and host.port != 0
                              and not host.username and not host.password and not host.path and not host.query)
        except ValueError:
            host_valid = False
        origin = request.headers.get("origin")
        expected_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if not host_valid or not loopback(client):
            return JSONResponse({"code": "LOOPBACK_ONLY"}, status_code=403)
        if (origin and origin != expected_origin) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"code": "SAME_ORIGIN_REQUIRED"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if origin != expected_origin or not hmac.compare_digest(request.headers.get("x-dashboard-csrf", "").encode(), token.encode()):
                return JSONResponse({"code": "DASHBOARD_CSRF_REQUIRED"}, status_code=403)
            if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                return JSONResponse({"code": "JSON_REQUIRED"}, status_code=415)
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 4096:
                    return JSONResponse({"code": "BODY_TOO_LARGE"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"code": exc.code, "message": exc.code.replace("_", " ").lower()}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"code": "INVALID_INPUT", "message": "Check the source and budget fields."}, status_code=422)

    @app.exception_handler(psycopg.Error)
    async def database_error(request, exc):
        return JSONResponse({"code": "DATABASE_UNAVAILABLE", "message": "The local database is unavailable. Start the dashboard launcher again."}, status_code=503)

    @app.exception_handler(OSError)
    async def storage_error(request, exc):
        return JSONResponse({"code": "LOCAL_STORAGE_UNAVAILABLE", "message": "The requested local file is unavailable. Refresh the dashboard or run the fixture again."}, status_code=503)

    @app.get("/api/dashboard/health")
    def health():
        with transaction(dashboard.settings) as conn:
            conn.execute("SELECT 1")
        return {"status": "ready", "mode": "fixture", "service": "abn-leadgen-dashboard"}

    @app.get("/api/dashboard")
    def state():
        return {**dashboard.state(), "csrf_token": token}

    @app.patch("/api/settings")
    def settings_update(data: SettingsPatch):
        return dashboard.save_preferences(data)

    @app.post("/api/runs", status_code=202)
    def run(data: RunRequest):
        return dashboard.submit(data)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: UUID):
        return dashboard.job(job_id)

    @app.get("/api/reports/{run_id}/{kind}")
    def report(run_id: UUID, kind: str):
        payload, media, filename = dashboard.report(run_id, kind)
        headers = {} if kind == "html" else {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(payload, media_type=media, headers=headers)

    @app.get("/")
    @app.get("/report.html")
    def index():
        return FileResponse(static / "index.html", media_type="text/html")

    @app.get("/assets/{filename}")
    def asset(filename: str):
        allowed = {"dashboard.css": "text/css", "dashboard.js": "text/javascript", "logo.svg": "image/svg+xml",
                   "albert-sans.ttf": "font/ttf", "OFL.txt": "text/plain"}
        if filename not in allowed or not (static / filename).is_file():
            raise DomainError("ASSET_NOT_FOUND", 404)
        return FileResponse(static / filename, media_type=allowed[filename])

    return app
