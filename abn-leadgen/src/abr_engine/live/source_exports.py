"""One-use, origin-bound source CSV downloads streamed directly by the engine.

Tickets exist only in this process and contain no public URL. The trusted website
obtains a ticket with its staff assertion, then submits it in a browser POST body.
Every CSV batch is checked before disclosure; no control transaction spans a
yield and no full CSV or publisher archive is copied into memory or storage.
"""

import csv
import hashlib
import io
import json
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import anyio
import psycopg
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as arrow_csv
from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from abr_engine.control.service import DomainError, json_safe
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError
from abr_engine.live import source_records as browse
from abr_engine.live.source_query import SourceFilters, iter_filtered_batches, normalized_filters

TICKET_SECONDS = 120
EXPORT_SECONDS = 7200
MAX_TICKETS = 100
MAX_ACTOR_TICKETS = 2
MAX_ACTIVE_EXPORTS = 1
EXPORT_BATCH_ROWS = 10_000
EXPORT_BATCH_BYTES = 16 * 1024 * 1024
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
WEBSITE_ORIGINS = frozenset({"https://www.maintainmedia.com.au", "https://maintainmedia.com.au"})


class SourceExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["abr", "qbcc"]
    run_id: str = "latest"
    filters: SourceFilters = Field(default_factory=SourceFilters)
    client_origin: str

    @field_validator("run_id")
    @classmethod
    def valid_run(cls, value):
        if value != "latest":
            value = str(UUID(value))
        return value

    @field_validator("client_origin")
    @classmethod
    def valid_origin(cls, value):
        parsed = urlsplit(value)
        if (value not in WEBSITE_ORIGINS or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.path or parsed.query or parsed.fragment
                or value != "https://" + parsed.netloc):
            raise ValueError("HTTPS website origin required")
        return value


@dataclass
class Ticket:
    actor: str
    origin: str
    expires: float
    export_id: str
    plan: dict
    artifacts: list
    seals: dict
    filters: SourceFilters


@dataclass
class TicketStore:
    clock: object = time.time
    pending: dict = field(default_factory=dict)
    active: dict = field(default_factory=dict)
    lock: object = field(default_factory=threading.Lock)

    def _prune(self):
        now = self.clock()
        self.pending = {key: ticket for key, ticket in self.pending.items() if ticket.expires > now}

    def put(self, ticket):
        with self.lock:
            self._prune()
            if len(self.active) >= MAX_ACTIVE_EXPORTS or ticket.actor in self.active:
                raise DomainError("SOURCE_EXPORT_BUSY", 429)
            if len(self.pending) >= MAX_TICKETS or sum(t.actor == ticket.actor for t in self.pending.values()) >= MAX_ACTOR_TICKETS:
                raise DomainError("SOURCE_EXPORT_TICKET_LIMIT", 429)
            token = secrets.token_urlsafe(32)
            self.pending[hashlib.sha256(token.encode()).digest()] = ticket
            return token

    def consume(self, token, origin):
        if not TOKEN_PATTERN.fullmatch(token):
            raise DomainError("SOURCE_EXPORT_TICKET_EXPIRED", 410)
        with self.lock:
            self._prune()
            key = hashlib.sha256(token.encode()).digest()
            ticket = self.pending.get(key)
            if ticket is None:
                raise DomainError("SOURCE_EXPORT_TICKET_EXPIRED", 410)
            if origin != ticket.origin:
                raise DomainError("SOURCE_EXPORT_ORIGIN_REQUIRED", 403)
            if len(self.active) >= MAX_ACTIVE_EXPORTS or ticket.actor in self.active:
                raise DomainError("SOURCE_EXPORT_BUSY", 429)
            del self.pending[key]
            self.active[ticket.actor] = ticket.export_id
            return ticket

    def release(self, ticket):
        with self.lock:
            if self.active.get(ticket.actor) == ticket.export_id:
                del self.active[ticket.actor]


def _current(settings, service, ticket):
    """Short authority/ledger transaction, always closed before yielding bytes."""
    with transaction(settings) as conn:
        service.personal_data_access(conn)
        snapshot = conn.execute("SELECT state FROM source_snapshot WHERE snapshot_id=%s",
                                (ticket.plan["snapshot_id"],)).fetchone()
        if not snapshot or snapshot["state"] != "committed":
            raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
        rows = conn.execute("SELECT * FROM artifact_manifest WHERE artifact_id=ANY(%s)",
                            ([row["artifact_id"] for row in ticket.artifacts],)).fetchall()
        current = {row["artifact_id"]: row for row in rows}
        for old in ticket.artifacts:
            row = current.get(old["artifact_id"])
            if not row or any(row[key] != old[key] for key in (
                "state", "content_digest", "byte_count", "verified_at", "snapshot_id", "local_path",
            )):
                raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    for filename, identity in ticket.seals.items():
        if browse._identity(Path(filename)) != identity:
            raise DomainError("SOURCE_ARTIFACT_CHANGED", 409)


def issue_export(settings, service, store, body, actor):
    filters = normalized_filters(body.source, body.filters)
    with transaction(settings) as conn:
        plan, artifacts = browse._plan(conn, service, body.source, body.run_id, 0)
    if plan["source_state"] != "available" or not plan["snapshot_id"]:
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
    # Offset at the end verifies the retained files and all footers without
    # reading any source rows or doing a filtered count during ticket creation.
    try:
        seals = browse._read_page(settings, {**plan, "offset": plan["total"], "records": []}, artifacts)
    except (OSError, pa.ArrowException, SourceError):
        raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409) from None
    ticket = Ticket(actor, body.client_origin, store.clock() + TICKET_SECONDS, str(uuid4()),
                    plan, artifacts, seals, filters)
    _current(settings, service, ticket)
    with transaction(settings) as conn:
        service.audit(conn, actor, "source_export_requested", ticket.export_id,
                      {"source": body.source, "run_id": plan["run_id"], "snapshot_id": plan["snapshot_id"],
                       "filtered": bool(filters.model_dump(exclude_defaults=True))})
    token = store.put(ticket)
    return json_safe({"download_token": token, "expires_at": datetime.fromtimestamp(ticket.expires, UTC),
                      "export_id": ticket.export_id, "source": body.source, "run_id": plan["run_id"],
                      "snapshot_id": plan["snapshot_id"], "columns": list(browse.FIELDS[body.source]),
                      "total_source_records": plan["total"], "filters": filters.model_dump(exclude_none=True)})


def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict, bool)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    # Quoting alone does not prevent spreadsheet formula evaluation.
    if text[:1] in ("\t", "\r", "\n") or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _csv_piece(rows):
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _csv_batch(batch, columns):
    """Arrow formats scalar columns without millions of Python row dictionaries."""
    arrays = []
    for name in columns:
        values = batch.column(name)
        kind = values.type
        if pa.types.is_nested(kind):
            values = pa.array([csv_cell(value) for value in values.to_pylist()], type=pa.string())
        else:
            values = pc.fill_null(pc.cast(values, pa.string()), "")
            formula = pc.or_(pc.match_substring_regex(values, r"^[\t\r\n]"),
                             pc.match_substring_regex(pc.utf8_trim_whitespace(values), r"^[=+\-@]"))
            values = pc.if_else(formula, pc.binary_join_element_wise("'", values, ""), values)
        arrays.append(values)
    output = pa.BufferOutputStream()
    arrow_csv.write_csv(pa.RecordBatch.from_arrays(arrays, names=list(columns)), output,
                        write_options=arrow_csv.WriteOptions(include_header=False))
    return output.getvalue().to_pybytes()


def _export_batches(batches):
    """Bound coalescing by rows and bytes; one scanner batch may exceed bytes."""
    pending, rows, size = [], 0, 0
    for batch in batches:
        offset = 0
        while offset < batch.num_rows:
            take = min(batch.num_rows - offset, EXPORT_BATCH_ROWS - rows)
            piece = batch.slice(offset, take)
            if pending and size + piece.nbytes > EXPORT_BATCH_BYTES:
                yield pa.Table.from_batches(pending).combine_chunks().to_batches()[0]
                pending, rows, size = [], 0, 0
                continue
            pending.append(piece)
            rows += take
            size += piece.nbytes
            offset += take
            if rows == EXPORT_BATCH_ROWS or size >= EXPORT_BATCH_BYTES:
                yield pa.Table.from_batches(pending).combine_chunks().to_batches()[0]
                pending, rows, size = [], 0, 0
    if pending:
        yield pa.Table.from_batches(pending).combine_chunks().to_batches()[0]


def csv_chunks(settings, service, ticket, cancelled, clock=time.monotonic):
    started, rows_sent, bytes_sent = clock(), 0, 0
    completed = False

    def check():
        if cancelled.is_set():
            raise DomainError("SOURCE_EXPORT_CANCELLED", 409)
        if clock() - started > EXPORT_SECONDS:
            raise DomainError("SOURCE_EXPORT_DEADLINE", 409)

    columns = browse.FIELDS[ticket.plan["source"]]
    try:
        check()
        _current(settings, service, ticket)
        header = b"\xef\xbb\xbf" + _csv_piece([columns])
        bytes_sent += len(header)
        yield header
        paths = [Path(row["local_path"]) for row in ticket.artifacts]
        batches = iter_filtered_batches(paths, ticket.plan["source"], ticket.filters, check)
        for batch in _export_batches(batches):
            check()
            chunk = _csv_batch(batch, columns)
            _current(settings, service, ticket)
            check()
            rows_sent += batch.num_rows
            bytes_sent += len(chunk)
            yield chunk
        check()
        _current(settings, service, ticket)
        if not ticket.filters.model_dump(exclude_defaults=True) and rows_sent != ticket.plan["total"]:
            raise DomainError("SOURCE_EXPORT_COUNT_CHANGED", 409)
        completed = True
    finally:
        # A failed/disconnected stream is never reported as a completed export.
        try:
            with transaction(settings) as conn:
                service.audit(conn, ticket.actor, "source_export_completed" if completed else "source_export_interrupted",
                              ticket.export_id, {"source": ticket.plan["source"], "snapshot_id": ticket.plan["snapshot_id"],
                                                 "rows": rows_sent, "bytes": bytes_sent})
        except psycopg.Error:
            logging.getLogger(__name__).warning("Source export completion audit unavailable")


@dataclass
class PieceState:
    lock: object = field(default_factory=threading.Lock)
    finished: object = field(default_factory=threading.Event)
    started: bool = False
    cancelled: bool = False


def _next_piece(iterator, state):
    with state.lock:
        if state.cancelled:
            state.finished.set()
            return None
        state.started = True
    try:
        return next(iterator)
    except StopIteration:
        return None
    finally:
        state.finished.set()


async def stream_export(settings, service, store, ticket):
    cancelled = threading.Event()
    iterator = csv_chunks(settings, service, ticket, cancelled)
    state = None
    try:
        while True:
            state = PieceState()
            piece = await anyio.to_thread.run_sync(_next_piece, iterator, state, abandon_on_cancel=True)
            if piece is None:
                break
            yield piece
    finally:
        cancelled.set()
        # Close from the worker thread after its current bounded batch returns.
        with anyio.CancelScope(shield=True):
            if state is not None:
                with state.lock:
                    state.cancelled = True
                    started = state.started
                if started:
                    await anyio.to_thread.run_sync(state.finished.wait)
            await anyio.to_thread.run_sync(iterator.close)
        store.release(ticket)


class SourceCSVResponse(StreamingResponse):
    def __init__(self, *args, store, ticket, **kwargs):
        self.store, self.ticket = store, ticket
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            with anyio.fail_after(EXPORT_SECONDS):
                await super().__call__(scope, receive, send)
        finally:
            # Also covers disconnect before StreamingResponse pulls its first chunk.
            try:
                with anyio.CancelScope(shield=True):
                    await self.body_iterator.aclose()
            finally:
                self.store.release(self.ticket)


def register_export_routes(app, settings, service, actor_for):
    store = TicketStore()
    app.state.source_export_tickets = store

    @app.post("/api/source-exports")
    def source_export(body: SourceExportRequest, request: Request):
        actor = actor_for(request, ("admin", "reviewer", "compliance"))
        return issue_export(settings, service, store, body, actor.actor_id)

    @app.post("/api/source-exports/download")
    async def source_export_download(request: Request):
        if request.url.query or request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise DomainError("SOURCE_EXPORT_FORM_REQUIRED", 415)
        raw = request.state.raw_body
        if len(raw) > 256:
            raise DomainError("SOURCE_EXPORT_FORM_REQUIRED", 415)
        try:
            fields = parse_qs(raw.decode("ascii"), strict_parsing=True, max_num_fields=1)
        except (ValueError, UnicodeError):
            raise DomainError("SOURCE_EXPORT_FORM_REQUIRED", 415) from None
        if set(fields) != {"ticket"} or len(fields["ticket"]) != 1:
            raise DomainError("SOURCE_EXPORT_FORM_REQUIRED", 415)
        ticket = store.consume(fields["ticket"][0], request.headers.get("origin", ""))
        try:
            await anyio.to_thread.run_sync(_current, settings, service, ticket)
        except (OSError, pa.ArrowException, SourceError):
            store.release(ticket)
            raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409) from None
        except BaseException:
            store.release(ticket)
            raise
        filtered = bool(ticket.filters.model_dump(exclude_defaults=True))
        filename = f"{ticket.plan['source']}-{'filtered' if filtered else 'full'}-{ticket.plan['snapshot_id']}.csv"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"',
                   "Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff",
                   "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow, noarchive",
                   "X-Source-Snapshot": str(ticket.plan["snapshot_id"]), "X-Source-Records": str(ticket.plan["total"]),
                   "X-Export-Scope": "filtered" if filtered else "full"}
        if not filtered:
            headers["X-Export-Expected-Rows"] = str(ticket.plan["total"])
        return SourceCSVResponse(stream_export(settings, service, store, ticket), store=store, ticket=ticket,
                                 media_type="text/csv; charset=utf-8",
                                 headers=headers)
