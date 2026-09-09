"""Small authenticated control service; not a marketing sender or general dashboard."""
import hashlib
import hmac
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg.types.json import Jsonb

from abr_engine.compliance.keys import load_keys
from abr_engine.config import Settings, load_settings
from abr_engine.control import models as m
from abr_engine.control.auth import authenticate
from abr_engine.control.service import DomainError, Service, digest, json_safe
from abr_engine.db import transaction
from abr_engine.export.crm import approve


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    service = Service(settings, load_keys(settings))
    app = FastAPI(title="Maintain Media Lead Engine", version="1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    rate: defaultdict[tuple[str, str], deque[float]] = defaultdict(deque)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        from abr_engine.ops.monitor import record_control_failure
        try:
            record_control_failure(settings, exc.code)
        except psycopg.Error:
            pass  # An alarm failure must never replace the authoritative failed-request response.
        return JSONResponse({"code": exc.code, "message": exc.code.replace("_", " ").lower(),
                             "request_id": request.headers.get("x-request-id"), "retryable": exc.status in {429, 503},
                             "details": json_safe(exc.details)}, status_code=exc.status,
                            headers={"Retry-After": "60"} if exc.status == 429 else None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"code": "INVALID_INPUT", "message": "Invalid fields", "retryable": False,
                             "details": {"fields": [list(e["loc"]) for e in exc.errors()]}}, status_code=422)

    @app.exception_handler(psycopg.Error)
    async def database_error(request, exc):
        status = 422 if isinstance(exc, psycopg.IntegrityError) else 503
        return JSONResponse({"code": "EVIDENCE_CONSTRAINT" if status == 422 else "AUTHORITY_UNAVAILABLE",
                             "message": "Request not saved", "retryable": status == 503, "details": {}}, status_code=status)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"code": "INVALID_EVIDENCE", "message": "Request not saved", "retryable": False, "details": {}}, status_code=422)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 65536:
                return JSONResponse({"code": "BODY_TOO_LARGE"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
        request.state.raw_body = request._body
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
        return response

    def actor_for(request, scopes):
        actor = authenticate(request.headers.get("authorization"), service)
        if "bridge" in actor.scopes:
            # No mapping/secret supplied means fail closed. Fixture tests may explicitly configure it.
            bridge = getattr(app.state, "bridge", {})
            editor = request.headers.get("x-bridge-actor", "")
            stamp = request.headers.get("x-bridge-timestamp", "")
            signature = request.headers.get("x-bridge-signature", "")
            try:
                instant = datetime.fromisoformat(stamp)
                fresh = abs((datetime.now(UTC) - instant).total_seconds()) <= 300
            except (ValueError, TypeError, OverflowError):
                fresh = False
            body = request.state.raw_body.decode("utf-8")
            message = "\n".join([request.method, request.url.path, stamp, editor,
                                  request.headers.get("idempotency-key", ""), body])
            expected = hmac.new(bridge.get("secret", "").encode(), message.encode(), hashlib.sha256).hexdigest()
            if not bridge.get("secret") or not fresh or not hmac.compare_digest(expected, signature) or editor not in bridge.get("editors", {}):
                raise DomainError("BRIDGE_SIGNATURE_OR_EDITOR", 401)
            from abr_engine.control.auth import Actor
            actor = Actor(editor, frozenset(bridge["editors"][editor]))
        actor.require(*scopes)
        # Unauthenticated requests cannot exhaust the opt-out budget. Separate stop lane per actor.
        now = time.monotonic()
        lane = "stop" if request.url.path == "/v1/suppressions" else "ordinary"
        for rate_key in list(rate):
            if not rate[rate_key] or rate[rate_key][-1] < now - 60:
                del rate[rate_key]
        entries = rate[(actor.actor_id, lane)]
        while entries and entries[0] < now - 60:
            entries.popleft()
        if len(entries) >= 600:
            raise DomainError("RATE_LIMIT", 429)
        entries.append(now)
        return actor

    def mutate(request, data, scopes, operation, status=201):
        actor = actor_for(request, scopes)
        try:
            key = UUID(request.headers.get("idempotency-key", ""))
            UUID(request.headers.get("x-request-id", ""))
        except ValueError:
            raise DomainError("REQUEST_IDENTIFIERS_REQUIRED") from None
        fingerprint = digest({"path": request.url.path, "method": request.method, "body": data})
        with transaction(settings) as conn:
            service.authority(conn)
            existing = conn.execute("SELECT * FROM idempotency_receipt WHERE actor_id=%s AND key=%s", (actor.actor_id, key)).fetchone()
            if existing:
                if existing["body_digest"] != fingerprint:
                    raise DomainError("IDEMPOTENCY_CONFLICT", 409)
                result, code = existing["receipt"], 200
            else:
                result = json_safe(operation(conn, data, actor, key))
                code = status
                conn.execute("INSERT INTO idempotency_receipt(actor_id,key,body_digest,status,receipt) VALUES(%s,%s,%s,%s,%s)",
                             (actor.actor_id, key, fingerprint, status, Jsonb(result)))
        # Exit transaction context before acknowledging durable writes.
        return JSONResponse(result, status_code=code)

    def assigned(conn, actor, *, row_id=None, worklist_id=None, contact_id=None):
        if actor.scopes.intersection({"reviewer", "compliance", "admin", "sender"}):
            return
        if row_id:
            row = conn.execute("SELECT worklist_id FROM worklist_row WHERE row_id=%s", (row_id,)).fetchone()
            worklist_id = row["worklist_id"] if row else None
        if contact_id:
            row = conn.execute("SELECT a.worklist_id FROM worklist_assignment a JOIN worklist_row r USING(worklist_id) "
                               "JOIN contact_record c USING(lead_id) WHERE c.contact_id=%s AND a.actor_id=%s LIMIT 1", (contact_id, actor.actor_id)).fetchone()
            worklist_id = row["worklist_id"] if row else None
        if not worklist_id or not conn.execute("SELECT 1 FROM worklist_assignment WHERE worklist_id=%s AND actor_id=%s", (worklist_id, actor.actor_id)).fetchone():
            raise DomainError("NOT_FOUND", 404)

    @app.get("/health")
    def health():
        with transaction(settings) as conn:
            conn.execute("SELECT 1")
        return {"status": "ready", "mode": settings.mode, "outreach": "disabled"}

    @app.get("/v1/openapi.json")
    def schema(request: Request):
        actor_for(request, ("admin", "reviewer", "operator"))
        return app.openapi()

    @app.post("/v1/suppressions")
    def suppress(data: m.Suppression, request: Request):
        return mutate(request, data.model_dump(), ("operator", "compliance"),
                      lambda c, d, a, k: service.suppress(c, d, a.actor_id, k))

    @app.post("/v1/identity-assessments")
    def identity(data: m.Identity, request: Request):
        return mutate(request, data.model_dump(), ("reviewer",), lambda c, d, a, k: service.identity(c, d, a.actor_id))

    @app.post("/v1/reviewed-merges")
    def merge(data: m.Merge, request: Request):
        from abr_engine.qualify.identity import merge_groups
        return mutate(request, data.model_dump(), ("reviewer",), lambda c, d, a, k: merge_groups(c, service, d, a.actor_id))

    @app.get("/v1/leads/{lead_id}/duplicate-hints")
    def duplicates(lead_id: UUID, request: Request):
        from abr_engine.qualify.identity import duplicate_hints
        actor = actor_for(request, ("reviewer",))
        with transaction(settings) as conn:
            hints = duplicate_hints(conn, service, lead_id)
            service.audit(conn, actor.actor_id, "duplicate_hints_reviewed", lead_id)
        return json_safe({"lead_id": lead_id, "hints": hints, "automatic_merge": False})

    @app.post("/v1/licence-reviews")
    def licence(data: m.Licence, request: Request):
        return mutate(request, data.model_dump(), ("reviewer",), lambda c, d, a, k: service.licence(c, d, a.actor_id))

    @app.post("/v1/basis-assessments")
    def basis(data: m.Basis, request: Request):
        return mutate(request, data.model_dump(), ("reviewer",), lambda c, d, a, k: service.basis(c, d, a.actor_id))

    @app.post("/v1/relevance-assessments")
    def relevance(data: m.Relevance, request: Request):
        return mutate(request, data.model_dump(), ("reviewer",), lambda c, d, a, k: service.relevance(c, d, a.actor_id))

    @app.post("/v1/action-intents")
    def action(data: m.Action, request: Request):
        def operation(conn, d, actor, key):
            assigned(conn, actor, contact_id=d["contact_id"])
            if d["channel"] == "email":
                actor.require("sender")
            return service.action(conn, d, actor.actor_id)
        return mutate(request, data.model_dump(), ("operator", "sender"), operation)

    @app.post("/v1/action-intents/{intent_id}/consume")
    def consume(intent_id: UUID, data: m.Consume, request: Request):
        def operation(c, d, a, k):
            row = c.execute("SELECT channel,contact_id FROM action_intent WHERE intent_id=%s", (intent_id,)).fetchone()
            if row:
                assigned(c, a, contact_id=row["contact_id"])
            if row and row["channel"] == "email":
                a.require("sender")
            return service.consume(c, intent_id, d, a.actor_id)
        return mutate(request, data.model_dump(), ("operator", "sender"),
                      operation, 200)

    @app.patch("/v1/worklist-rows/{row_id}")
    def outcome(row_id: UUID, data: m.Outcome, request: Request):
        def operation(c, d, a, k):
            assigned(c, a, row_id=row_id)
            return service.outcome(c, row_id, d, a.actor_id, k)
        return mutate(request, data.model_dump(), ("operator",), operation, 200)

    @app.post("/v1/crm-approvals")
    def approval(data: m.Approval, request: Request):
        return mutate(request, data.model_dump(), ("reviewer",), lambda c, d, a, k: approve(c, service, d, a.actor_id))

    @app.get("/v1/contacts/{contact_id}/check")
    def check(contact_id: UUID, request: Request):
        actor = actor_for(request, ("operator", "reviewer", "compliance"))
        with transaction(settings) as conn:
            assigned(conn, actor, contact_id=contact_id)
            result = service.gate(conn, contact_id)
            service.audit(conn, actor.actor_id, "candidate_checked", contact_id)
        return json_safe(result)

    @app.get("/v1/worklists/{worklist_id}")
    def worklist(worklist_id: UUID, request: Request):
        actor = actor_for(request, ("operator", "reviewer"))
        with transaction(settings) as conn:
            service.personal_data_access(conn)
            assigned(conn, actor, worklist_id=worklist_id)
            rows = conn.execute("SELECT r.row_id,r.worklist_id,r.lead_id,r.version,r.outcome,r.selected_tier,r.selected_signal,l.display_name "
                                "FROM worklist_row r JOIN lead_entity l USING(lead_id) WHERE worklist_id=%s ORDER BY r.row_id", (worklist_id,)).fetchall()
        return json_safe({"rows": rows})

    @app.post("/v1/operator-activities")
    def activity(data: m.Activity, request: Request):
        def operation(c, d, a, k):
            assigned(c, a, worklist_id=d["worklist_id"])
            if d["lead_id"] and not c.execute("SELECT 1 FROM worklist_row WHERE worklist_id=%s AND lead_id=%s", (d["worklist_id"], d["lead_id"])).fetchone():
                raise DomainError("NOT_FOUND", 404)
            if d["ended_at"] > service.now(c) + timedelta(minutes=5):
                raise DomainError("FUTURE_ACTIVITY")
            if d["correction_of"]:
                original = c.execute("SELECT actor_id FROM operator_activity WHERE activity_id=%s", (d["correction_of"],)).fetchone()
                if not original or original["actor_id"] != a.actor_id:
                    raise DomainError("ACTIVITY_NOT_OWNED", 403)
                if c.execute("SELECT 1 FROM operator_activity WHERE correction_of=%s", (d["correction_of"],)).fetchone():
                    raise DomainError("ACTIVITY_ALREADY_CORRECTED", 409)
            c.execute("INSERT INTO operator_activity(activity_id,actor_id,worklist_id,lead_id,category,started_at,ended_at,correction_of) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                      (d["activity_id"], a.actor_id, d["worklist_id"], d["lead_id"], d["category"], d["started_at"], d["ended_at"], d["correction_of"]))
            return {"activity_id": d["activity_id"], "saved_at": service.now(c)}
        return mutate(request, data.model_dump(), ("operator",), operation)

    @app.post("/v1/action-results")
    def action_result(data: m.ActionResult, request: Request):
        def operation(c, d, a, k):
            row = c.execute("SELECT * FROM action_intent WHERE intent_id=%s FOR UPDATE", (d["decision_id"],)).fetchone()
            if not row or row["actor_id"] != a.actor_id or row["dispatch_id"] != d["dispatch_id"]:
                raise DomainError("DISPATCH_BINDING_MISMATCH", 409)
            if row["state"] != "consumed" or d["occurred_at"] > service.now(c) + timedelta(minutes=5):
                raise DomainError("INVALID_DISPATCH_RESULT", 409)
            checked = datetime.fromisoformat(row["decision"]["checked_at"])
            if d["occurred_at"] < checked:
                raise DomainError("DISPATCH_BEFORE_CONSUMPTION", 409)
            if row["result"] and row["result"] != json_safe(d):
                raise DomainError("DISPATCH_RESULT_CONFLICT", 409)
            c.execute("UPDATE action_intent SET result=%s WHERE intent_id=%s", (Jsonb(json_safe(d)), d["decision_id"]))
            violation = d["state"] == "sent" and d["occurred_at"] > checked + timedelta(seconds=5)
            if violation:
                service.audit(c, a.actor_id, "dispatch_timing_violation", d["decision_id"])
                c.execute("INSERT INTO system_state VALUES('integration_uncertified','true') ON CONFLICT(name) DO UPDATE SET value='true'")
            return {"saved": True, "dispatch_id": d["dispatch_id"], "timing_violation": violation}
        return mutate(request, data.model_dump(), ("operator", "sender"), operation)

    @app.post("/v1/deletions")
    def deletion(data: m.Deletion, request: Request):
        def operation(c, d, a, k):
            service.suppress(c, {"lead_id": d["lead_id"], "reason": "manual", "source": "deletion_request", "requested_at": d["requested_at"]}, a.actor_id, k)
            lead = service.lead(c, d["lead_id"])
            job = c.execute("SELECT * FROM deletion_job WHERE group_id=%s ORDER BY requested_at DESC LIMIT 1", (lead["group_id"],)).fetchone()
            return {"job_id": job["job_id"], "state": job["state"], "primary_due_at": job["requested_at"] + timedelta(days=30), "backup_expiry_at": None}
        return mutate(request, data.model_dump(), ("compliance",), operation, 202)

    @app.get("/v1/deletions/{job_id}")
    def deletion_status(job_id: UUID, request: Request):
        actor_for(request, ("compliance",))
        with transaction(settings) as c:
            row = c.execute("SELECT * FROM deletion_job WHERE job_id=%s", (job_id,)).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", 404)
        return json_safe(row)

    @app.get("/v1/evidence/{provenance_id}")
    def evidence(provenance_id: UUID, request: Request):
        actor = actor_for(request, ("compliance", "reviewer"))
        with transaction(settings) as c:
            service.personal_data_access(c)
            row = c.execute("SELECT * FROM collection_provenance WHERE provenance_id=%s", (provenance_id,)).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", 404)
            if row.get("capture_erased_at"):
                raise DomainError("EVIDENCE_EXPIRED", 410)
            service.audit(c, actor.actor_id, "evidence_read", provenance_id)
            result = {"provenance_id": provenance_id, "source_url": row["source_url"], "captured_at": row["collected_at"],
                      "sha256": row["capture_sha256"], "capture_text": service.keys.decrypt(row["encrypted_capture"])}
        return json_safe(result)

    @app.post("/v1/cancellation-resolutions")
    def resolution(data: m.Resolution, request: Request):
        def operation(c, d, a, k):
            lead = service.lead(c, d["lead_id"])
            row = c.execute("SELECT * FROM suppression_event WHERE event_id=%s", (d["cancellation_event_id"],)).fetchone()
            family = service.group_family(c, lead["group_id"])
            if not row or row["group_id"] not in family or row["reason"] != "cancellation" or row["action"] != "add":
                raise DomainError("CANCELLATION_ONLY_RESOLUTION")
            source = c.execute("SELECT e.* FROM abr_event e WHERE e.event_id::text=%s AND e.event_type='abn_reactivated'", (d["positive_reactivation_evidence_ref"],)).fetchone()
            if not source or source["detected_at"] < row["committed_at"]:
                raise DomainError("REACTIVATION_EVIDENCE_REQUIRED")
            belongs = False
            for version, token in service.keys.matches("abn", source["abn"]):
                if c.execute("SELECT 1 FROM suppression_alias WHERE group_id=ANY(%s) AND alias_type='abn' AND key_version=%s AND alias_token=%s",
                             (family, version, token)).fetchone():
                    belongs = True
            if not belongs:
                raise DomainError("REACTIVATION_NOT_THIS_LEAD")
            now = service.now(c)
            c.execute("INSERT INTO suppression_event(event_id,request_id,scope,group_id,reason,action,resolves_event_id,requested_at,actor_id,source) "
                      "VALUES(%s,%s,'business',%s,'cancellation','resolve',%s,%s,%s,'reviewed-reactivation')",
                      (uuid4(), k, lead["group_id"], row["event_id"], now, a.actor_id))
            remaining = service.restricted(c, lead["group_id"])
            if not remaining:
                canonical = service.canonical_group(c, lead["group_id"])
                c.execute("UPDATE lead_entity SET lifecycle='active',revision=revision+1 WHERE group_id=%s", (canonical,))
                c.execute("UPDATE lead_entity SET lifecycle='disqualified',revision=revision+1 WHERE group_id=ANY(%s) AND group_id<>%s", (family, canonical))
            return {"remaining_reasons": remaining}
        return mutate(request, data.model_dump(), ("reviewer",), operation)

    @app.get("/unsubscribe/{token}", response_class=HTMLResponse)
    def unsubscribe_page(token: str):
        # No existence disclosure or mutation on GET; scanners cannot trigger an opt-out.
        return '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Stop contact</title><body><h1>Stop contact</h1><form method="post"><button>Confirm: do not contact me</button></form></body></html>'

    @app.post("/unsubscribe/{token}")
    def unsubscribe(token: str):
        with transaction(settings) as c:
            service.authority(c)
            row = c.execute("SELECT group_id FROM unsubscribe_token WHERE token_digest=%s", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if row:
                service.suppress(c, {"group_id": row["group_id"], "reason": "unsubscribe", "source": "unsubscribe_link"}, "unsubscribe", uuid4())
        return {"message": "Your request has been recorded if this link identifies a contact."}

    return app


app = create_app()
