"""Fixture dashboard projections and durable, serialized local run admission.

Run and report authority stays in the existing PostgreSQL pipeline. Local JSON
contains preferences and job receipts only, never contact data or credentials.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from abr_engine.compliance.keys import load_keys
from abr_engine.config import Settings
from abr_engine.control.service import DomainError, Service, json_safe
from abr_engine.dashboard.models import DashboardSettings, RunRequest, SettingsPatch
from abr_engine.db import transaction
from abr_engine.export.report import CSV_FIELDS, ReportContext, _csv_cell, _markdown, safe_rows, worklist_rows
from abr_engine.export.worklist import report_context
from abr_engine.pipeline import _report_fingerprint, execute, process_lock, safe_root


def instant() -> str:
    return datetime.now(UTC).isoformat()


def dashboard_report(context: ReportContext, kind: str) -> bytes:
    """Render a contact-masked dashboard copy without altering private artifacts.

    The caller must first verify stored bytes and current report authority. Shared
    projections and escaping retain the canonical row identities and safe markup.
    """
    masked = "Masked — contact hidden in dashboard"
    if kind == "csv":
        rows = worklist_rows(context)
        for row in rows:
            row["safe_contact_view"] = masked
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows({key: _csv_cell(value) for key, value in row.items()} for row in rows)
        return stream.getvalue().encode("utf-8-sig")
    rows = safe_rows(context)
    for row in rows:
        row["contact"] = masked
    templates = Path(__file__).resolve().parents[3] / "templates"
    env = Environment(loader=FileSystemLoader(templates), undefined=StrictUndefined,
                      autoescape=select_autoescape(default=True) if kind == "html" else False)
    env.filters["md"] = _markdown
    name = "report.html.j2" if kind == "html" else "report.md.j2"
    payload = env.get_template(name).render(rows=rows, run_id=str(context.run_id), mode=context.mode,
                                           generated_at=context.generated_at.isoformat()).encode("utf-8")
    route = f"/api/reports/{context.run_id}/csv".encode()
    if kind == "html":
        return payload.replace(b'href="worklist.csv"', b'href="' + route + b'"')
    return payload.replace(b"](worklist.csv)", b"](" + route + b")")


class Dashboard:
    def __init__(self, settings: Settings):
        if settings.mode != "fixture":
            raise ValueError("Dashboard requires fixture mode")
        # Revalidate even Settings.model_copy(update=...) callers before opening authority.
        self.settings = Settings.model_validate(settings.model_dump())
        self.service = Service(self.settings, load_keys(self.settings))
        self.root = safe_root(self.settings)
        self.local = self.root / "dashboard" / settings.schema_name
        self.local.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.local / "jobs").mkdir(exist_ok=True, mode=0o700)
        self.guard = threading.RLock()
        self.thread: threading.Thread | None = None

    def _read(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            if path.stat().st_size > 65536:
                raise ValueError("oversize")
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TypeError("object required")
            return value
        except (OSError, ValueError, TypeError):
            raise DomainError("DASHBOARD_STATE_UNAVAILABLE", 503) from None

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def preferences(self) -> DashboardSettings:
        raw = self._read(self.local / "settings.json")
        if raw is None:
            return DashboardSettings(monthly_cap_micro_aud=self.settings.monthly_cap_micro_aud)
        try:
            return DashboardSettings.model_validate(raw)
        except ValueError:
            raise DomainError("DASHBOARD_SETTINGS_INVALID", 503) from None

    def save_preferences(self, patch: SettingsPatch) -> dict:
        if any(getattr(patch, key) is None for key in patch.model_fields_set):
            raise DomainError("INVALID_SETTINGS", 422)
        with self.guard, process_lock(self.local / "settings.lock"):
            values = self.preferences().model_dump()
            values.update(patch.model_dump(exclude_unset=True))
            preferences = DashboardSettings.model_validate(values)
            self._write(self.local / "settings.json", preferences.model_dump())
            return preferences.model_dump()

    def _job_path(self, job_id: UUID) -> Path:
        return self.local / "jobs" / (str(job_id) + ".json")

    def _read_job(self, job_id: UUID) -> dict[str, Any] | None:
        try:
            job = self._read(self._job_path(job_id))
            if job is None:
                return None
            if (job.get("job_id") != str(job_id)
                    or job.get("state") not in {"queued", "running", "complete", "held", "failed", "interrupted"}
                    or job.get("source") not in {"all", "abr", "qbcc"}
                    or not isinstance(job.get("run_id"), str)):
                raise ValueError("invalid receipt")
            UUID(job["run_id"])
            for field in ("started_at", "finished_at", "error_code"):
                if job.get(field) is not None and not isinstance(job[field], str):
                    raise ValueError("invalid receipt")
            return job
        except (DomainError, ValueError, TypeError):
            raise DomainError("DASHBOARD_JOB_INVALID", 503) from None

    def job(self, job_id: UUID) -> dict:
        job = self._read_job(job_id)
        if not job:
            raise DomainError("JOB_NOT_FOUND", 404)
        if job["state"] in {"queued", "running"}:
            try:
                with process_lock(self.local / "run.lock"):
                    # The worker may have completed after the first read. Only the
                    # current receipt under the lock can authorize an interruption.
                    current = self._read_job(job_id)
                    if current is None:
                        raise DomainError("JOB_NOT_FOUND", 404)
                    job = current
                    if job["state"] in {"queued", "running"}:
                        job.update(state="interrupted", error_code="RUN_INTERRUPTED", finished_at=instant())
                        self._write(self._job_path(job_id), job)
            except DomainError as exc:
                if exc.code != "PROCESS_STAGE_LOCK_BUSY":
                    raise
        return job

    def recent_jobs(self, *, notices: list[dict] | None = None) -> list[dict]:
        paths = []
        unavailable = 0
        for path in (self.local / "jobs").glob("*.json"):
            try:
                paths.append((path.stat().st_mtime, path))
            except OSError:
                unavailable += 1
        jobs = []
        for _, path in sorted(paths, reverse=True)[:100]:
            try:
                jobs.append(self.job(UUID(path.stem)))
            except (DomainError, ValueError, OSError):
                unavailable += 1
        if unavailable and notices is not None:
            notices.append({"code": "DASHBOARD_JOB_RECEIPTS_UNAVAILABLE", "count": unavailable,
                            "message": f"{unavailable} local run receipt(s) could not be read. "
                            "Other results remain available. Keep the receipts for troubleshooting."})
        return sorted(jobs, key=lambda job: job.get("started_at") or "", reverse=True)

    def active_job(self) -> dict | None:
        return next((job for job in self.recent_jobs() if job["state"] in {"queued", "running"}), None)

    def submit(self, request: RunRequest) -> dict:
        with self.guard:
            previous = self._read_job(request.request_id)
            if previous:
                if request.source is not None and previous["source"] != request.source:
                    raise DomainError("REQUEST_ID_CONFLICT", 409)
                return self.job(request.request_id)
            # Take the OS lock before acknowledging admission, including across app instances.
            lease = process_lock(self.local / "run.lock")
            try:
                lease.__enter__()
            except DomainError:
                raise DomainError("RUN_ALREADY_ACTIVE", 409) from None
            worker_owns_lease = False
            try:
                # A different instance may have admitted and completed this request
                # between our first lookup and acquiring the process lock.
                previous = self._read_job(request.request_id)
                if previous:
                    if request.source is not None and previous["source"] != request.source:
                        raise DomainError("REQUEST_ID_CONFLICT", 409)
                    return previous
                preferences = self.preferences()
                run_settings = Settings.model_validate({
                    **self.settings.model_dump(),
                    "monthly_cap_micro_aud": preferences.monthly_cap_micro_aud,
                })
                # Database readiness is checked before returning a successful admission.
                with transaction(run_settings) as conn:
                    self.service.personal_data_access(conn)
                job: dict[str, Any] = {"job_id": str(request.request_id), "run_id": str(uuid4()), "state": "queued",
                       "source": request.source or preferences.default_source, "started_at": instant(),
                       "finished_at": None, "error_code": None,
                       "monthly_cap_micro_aud": preferences.monthly_cap_micro_aud}
                self._write(self._job_path(request.request_id), job)

                def work():
                    try:
                        job["state"] = "running"
                        self._write(self._job_path(request.request_id), job)
                        result = execute(run_settings, Service(run_settings, load_keys(run_settings)),
                                         source=job["source"], run_id=UUID(job["run_id"]))
                        job["state"] = result["status"]
                    except Exception as exc:  # noqa: BLE001 - bounded, redacted job failure receipt
                        job["state"] = "failed"
                        job["error_code"] = exc.code if isinstance(exc, DomainError) else "RUN_FAILED"
                    finally:
                        job["finished_at"] = instant()
                        try:
                            self._write(self._job_path(request.request_id), job)
                        finally:
                            lease.__exit__(None, None, None)

                self.thread = threading.Thread(target=work, name="fixture-dashboard-run", daemon=True)
                self.thread.start()
                worker_owns_lease = True
                return dict(job)
            finally:
                if not worker_owns_lease:
                    lease.__exit__(None, None, None)

    def state(self) -> dict:
        preferences = self.preferences()
        with transaction(self.settings) as conn:
            self.service.personal_data_access(conn)
            records = conn.execute(
                "SELECT l.*,q.state AS queue_state,q.stage_data FROM lead_entity l "
                "LEFT JOIN LATERAL (SELECT state,stage_data FROM candidate_queue WHERE lead_id=l.lead_id "
                "ORDER BY last_qualifying_at DESC,candidate_id LIMIT 1) q ON true "
                "ORDER BY l.last_qualifying_at DESC,l.lead_id LIMIT 200"
            ).fetchall()
            leads = []
            for row in records:
                link = conn.execute(
                    "SELECT encrypted_identifier FROM lead_source_link WHERE group_id=%s AND source_type='abn' "
                    "ORDER BY linked_at DESC LIMIT 1", (row["group_id"],)
                ).fetchone()
                abn = self.service.keys.decrypt(link["encrypted_identifier"]) if link else None
                reasons = self.service.restricted(conn, row["group_id"])
                contacts = conn.execute("SELECT contact_id FROM contact_record WHERE lead_id=%s", (row["lead_id"],)).fetchall()
                gates = [self.service.gate(conn, contact["contact_id"]) for contact in contacts]
                if not gates:
                    reasons.append("NO_CONTACT")
                elif not any(gate["allowed"] for gate in gates):
                    reasons.extend(code for gate in gates for code in gate["reason_codes"])
                enrichment_reason = (row["stage_data"] or {}).get("enrichment_reason")
                if enrichment_reason:
                    reasons.append(enrichment_reason)
                leads.append({"lead_id": row["lead_id"], "business_name": row["display_name"], "abn": abn,
                              "source": row["source"], "signal": row["signal"], "tier": row["tier"],
                              "score": row["score"], "state": row["queue_state"] or row["lifecycle"],
                              "lifecycle": row["lifecycle"], "first_observed_at": row["first_qualified_at"],
                              "last_observed_at": row["last_qualifying_at"], "region": row["state"],
                              "postcode": row["postcode"], "location": " ".join(filter(None, [row["state"], row["postcode"]])) or None,
                              "reason_codes": sorted(set(reasons)),
                              "next_action": "Review current identity and contact restrictions"})
            raw_runs = conn.execute("SELECT * FROM pipeline_run WHERE mode='fixture' ORDER BY started_at DESC LIMIT 20").fetchall()
            runs = []
            for run in raw_runs:
                manifest = run["manifest"] or {}
                result = manifest.get("result", {})
                available = bool(result.get("artifacts"))
                runs.append({"run_id": run["run_id"], "status": run["state"],
                             "source": manifest.get("request", {}).get("source", "all"),
                             "started_at": run["started_at"], "finished_at": run["finished_at"],
                             "selected": result.get("counts", {}).get("selected", 0),
                             "reports": {kind: f"/api/reports/{run['run_id']}/{kind}" for kind in ("html", "csv", "markdown")} if available else None})
            source_rows = conn.execute(
                "SELECT c.*,s.manifest FROM source_cursor c LEFT JOIN source_snapshot s USING(snapshot_id)"
            ).fetchall()
            source_by_name = {row["source"]: row for row in source_rows}
            sources = []
            for source in ("abr", "qbcc"):
                cursor = source_by_name.get(source, {})
                manifest = cursor.get("manifest") or {}
                sources.append({"source": source, "status": "fixture_ready" if cursor.get("snapshot_id") else "not_run",
                                "last_success_at": cursor.get("last_success_at"), "snapshot_id": cursor.get("snapshot_id"),
                                "source_published_at": manifest.get("publisher_timestamp") or manifest.get("effective_date")})
            counts = conn.execute("SELECT count(*) AS total_leads FROM lead_entity").fetchone()
            selected_row = conn.execute("SELECT count(*) AS n FROM worklist_row WHERE worklist_id=(SELECT worklist_id FROM worklist ORDER BY week DESC LIMIT 1)").fetchone()
            review_row = conn.execute("SELECT count(DISTINCT lead_id) AS n FROM candidate_queue WHERE state='needs_review'").fetchone()
            assert counts is not None and selected_row is not None and review_row is not None
            selected, review = selected_row["n"], review_row["n"]
            month = self.service.now(conn).astimezone(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m")
            ledger = conn.execute("SELECT cap,reserved,settled,frozen FROM budget_month WHERE month=%s", (month,)).fetchone()
            budget = {"month": month, "configured_cap_micro_aud": preferences.monthly_cap_micro_aud,
                      "effective_cap_micro_aud": min(preferences.monthly_cap_micro_aud, ledger["cap"]) if ledger else preferences.monthly_cap_micro_aud,
                      "reserved_micro_aud": ledger["reserved"] if ledger else 0,
                      "settled_micro_aud": ledger["settled"] if ledger else 0,
                      "frozen": ledger["frozen"] if ledger else False}
        notices: list[dict] = []
        jobs = self.recent_jobs(notices=notices)
        active = next((job for job in jobs if job["state"] in {"queued", "running"}), None)
        interrupted = {job["run_id"] for job in jobs if job["state"] == "interrupted"}
        for run in runs:
            if str(run["run_id"]) in interrupted and run["status"] == "running":
                run["pipeline_status"] = run["status"]
                run["status"] = "interrupted"
        return json_safe({"mode": "fixture", "outreach": "disabled", "settings": preferences.model_dump(), "budget": budget,
                          "summary": {"total_leads": counts["total_leads"], "selected": selected,
                                      "needs_review": review, "last_run_at": runs[0]["started_at"] if runs else None},
                          "leads": leads, "leads_limit": 200, "runs": runs, "sources": sources,
                          "setup": [
                              {"id": "database", "label": "Local database", "status": "ready", "detail": "Isolated fixture PostgreSQL is connected."},
                              {"id": "sources", "label": "Business sources", "status": "fixture", "detail": "Runs use synthetic ABR and QBCC files. Current live ABNs are not connected."},
                              {"id": "rules", "label": "Qualification rules", "status": "pending", "detail": "Live rules approval and a 100-record precision review are pending."},
                              {"id": "integrations", "label": "Sheets and CRM", "status": "pending", "detail": "Private Google Sheets and GoHighLevel setup require real account mappings and certification."},
                              {"id": "release", "label": "Production readiness", "status": "pending", "detail": "Source, provider, hosting and pilot approvals remain pending. Outreach is disabled."}],
                          "active_job": active, "job": active, "latest_job": jobs[0] if jobs else None,
                          "operational_notices": notices})

    def report(self, run_id: UUID, kind: str) -> tuple[bytes, str, str]:
        names = {"html": ("report.html", "text/html"), "csv": ("worklist.csv", "text/csv"),
                 "markdown": ("report.md", "text/markdown")}
        if kind not in names:
            raise DomainError("REPORT_NOT_FOUND", 404)
        filename, media = names[kind]
        with transaction(self.settings) as conn:
            self.service.personal_data_access(conn)
            run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s AND mode='fixture'", (run_id,)).fetchone()
            result = (run["manifest"] or {}).get("result", {}) if run else {}
            value = result.get("artifacts", {}).get(kind)
            if not value:
                raise DomainError("REPORT_NOT_FOUND", 404)
            path = Path(value).resolve()
            report_root = (self.root / "reports" / str(run_id)).resolve()
            if (not report_root.is_relative_to(self.root) or not path.is_relative_to(report_root)
                    or path.name != filename or path.parent.parent != report_root):
                raise DomainError("REPORT_NOT_FOUND", 404)
            artifact = conn.execute(
                "SELECT * FROM artifact_manifest WHERE run_id=%s AND local_path=%s AND source='report' "
                "AND artifact_class='report' AND state='referenced' FOR SHARE", (run_id, str(path))
            ).fetchone()
            if not artifact or not path.is_file():
                raise DomainError("REPORT_UNAVAILABLE", 410)
            # Read bounded bytes while authority locks remain held. Do not stream an unchecked path later.
            if path.stat().st_size > 8 * 1024 * 1024:
                raise DomainError("REPORT_TOO_LARGE", 409)
            payload = path.read_bytes()
            checksum = hashlib.sha256(payload).hexdigest()
            if (checksum != artifact["content_digest"] or len(payload) != artifact["byte_count"]
                    or checksum != result.get("artifact_digests", {}).get(str(path))):
                raise DomainError("REPORT_INTEGRITY_FAILURE", 409)
            context = (report_context(conn, self.service, UUID(result["worklist_id"]), run_id)
                       if result.get("worklist_id") else ReportContext(run_id=run_id, generated_at=self.service.now(conn), authorised_operator=True))
            if result.get("report_authority_digest") != _report_fingerprint(context):
                raise DomainError("REPORT_STALE_RUN_AGAIN", 409)
            return dashboard_report(context, kind), media, filename
