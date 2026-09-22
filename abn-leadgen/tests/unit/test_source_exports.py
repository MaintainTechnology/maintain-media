"""CSV fidelity, cancellation and one-use capabilities without a database."""

import asyncio
import csv
import io
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from starlette.requests import ClientDisconnect

from abr_engine.control.service import DomainError
from abr_engine.live import source_exports as exports
from abr_engine.live.source_query import FIELDS, SourceFilters


def ticket(*, actor="user_Synthetic", expires=120, filters=None, artifacts=None, total=0):
    return exports.Ticket(actor, "https://www.maintainmedia.com.au", expires, str(uuid4()),
                          {"source": "qbcc", "snapshot_id": uuid4(), "total": total},
                          artifacts or [], {}, filters or SourceFilters())


def test_tickets_are_origin_bound_one_use_expiring_and_limit_concurrent_disclosure():
    now = [0]
    store = exports.TicketStore(clock=lambda: now[0])
    first = ticket()
    raw = store.put(first)
    second = ticket(actor="user_Second")
    second_raw = store.put(second)
    assert raw not in store.pending and all(isinstance(key, bytes) for key in store.pending)
    with pytest.raises(DomainError, match="SOURCE_EXPORT_ORIGIN_REQUIRED"):
        store.consume(raw, "https://attacker.invalid")
    assert store.consume(raw, first.origin) is first
    with pytest.raises(DomainError, match="SOURCE_EXPORT_TICKET_EXPIRED"):
        store.consume(raw, first.origin)
    with pytest.raises(DomainError, match="SOURCE_EXPORT_BUSY"):
        store.put(ticket(actor="user_Third"))
    with pytest.raises(DomainError, match="SOURCE_EXPORT_BUSY"):
        store.consume(second_raw, second.origin)
    store.release(first)
    assert store.consume(second_raw, second.origin) is second
    store.release(first)  # An old completion cannot release another actor's lease.
    assert store.active == {second.actor: second.export_id}
    store.release(second)
    expired = store.put(ticket())
    now[0] = 121
    with pytest.raises(DomainError, match="SOURCE_EXPORT_TICKET_EXPIRED"):
        store.consume(expired, first.origin)
    assert not store.pending


def test_ticket_capacity_and_production_origins_are_closed():
    store = exports.TicketStore(clock=lambda: 0)
    store.put(ticket())
    store.put(ticket())
    with pytest.raises(DomainError, match="SOURCE_EXPORT_TICKET_LIMIT"):
        store.put(ticket())
    for origin in ("http://www.maintainmedia.com.au", "https://attacker.invalid", "https://www.maintainmedia.com.au/path"):
        with pytest.raises(ValidationError):
            exports.SourceExportRequest(source="abr", client_origin=origin)
    with pytest.raises(ValidationError):
        exports.SourceExportRequest(source="abr", run_id="../", client_origin="https://www.maintainmedia.com.au")


@pytest.mark.parametrize("value,expected", [
    (None, ""), (False, "false"), (51824753556, "51824753556"),
    ("=HYPERLINK(1)", "'=HYPERLINK(1)"), ("  +SUM(1)", "'  +SUM(1)"),
    ("\tformula", "'\tformula"), ("Ordinary, quoted\nname", "Ordinary, quoted\nname"),
    ([{"code": "B", "description": "Builder"}], '[{"code":"B","description":"Builder"}]'),
])
def test_csv_cells_preserve_nested_values_and_neutralize_spreadsheet_formulas(value, expected):
    assert exports.csv_cell(value) == expected


def test_arrow_csv_preserves_quoted_newlines_unicode_and_formula_safety():
    values = [None, "Plain name", '=HYPERLINK("unsafe")', "\tvalue", "  +SUM(1)", "@formula", "\u00a0=1",
              'Quoted "name", new\nline', "—日本"]
    batch = pa.record_batch({"name": values, "flag": [True] * len(values), "nested": [[{"code": "B"}]] * len(values)})
    parsed = list(csv.reader(io.StringIO(exports._csv_batch(batch, ("name", "flag", "nested")).decode())))
    assert [row[0] for row in parsed] == [exports.csv_cell(value) for value in values]
    assert all(row[1:] == ["true", '[{"code":"B"}]'] for row in parsed)


def test_csv_batch_coalescing_remains_bounded_across_scan_group_edges():
    batches = [pa.record_batch({"value": list(range(1501))}), pa.record_batch({"value": list(range(20_000))})]
    output = list(exports._export_batches(iter(batches)))
    assert [batch.num_rows for batch in output] == [10_000, 10_000, 1501]
    assert sum(batch.num_rows for batch in output) == 21_501


def test_csv_coalescing_flushes_before_byte_limit_and_keeps_large_single_batch(monkeypatch):
    monkeypatch.setattr(exports, "EXPORT_BATCH_BYTES", 100)
    batches = [pa.record_batch({"value": ["x" * width]}) for width in (60, 60, 120, 20)]
    output = list(exports._export_batches(iter(batches)))
    assert [batch.num_rows for batch in output] == [1, 1, 1, 1]
    assert [batch.column(0)[0].as_py() for batch in output] == ["x" * width for width in (60, 60, 120, 20)]


@contextmanager
def no_database(_):
    yield object()


def test_filtered_csv_uses_shared_arrow_filters_and_all_parsed_fields(tmp_path, monkeypatch):
    path = tmp_path / "source.parquet"
    rows = []
    for index in range(4501):
        row = dict.fromkeys(FIELDS["qbcc"], "")
        row.update({"licence_number": str(index), "licensee_name": "=Untrusted" if index == 0 else f"Company {index}",
                    "abn": "51824753556", "state": "QLD" if index % 2 == 0 else "NSW", "status": "UNKNOWN",
                    "licence_types": [{"code": "B", "description": "Builder"}], "class_types": ["A", "B"],
                    "licence_grades": ["CONTRACTOR"], "geography_review_required": False,
                    "licence_review_required": True})
        rows.append(row)
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=2000)
    current = ticket(filters=SourceFilters(state="QLD"), artifacts=[{"local_path": str(path)}], total=len(rows))
    checks, audits = [], []
    monkeypatch.setattr(exports, "_current", lambda *args: checks.append(True))
    monkeypatch.setattr(exports, "transaction", no_database)
    service = SimpleNamespace(audit=lambda *args: audits.append(args))
    chunks = list(exports.csv_chunks(None, service, current, threading.Event()))
    parsed = list(csv.DictReader(io.StringIO(b"".join(chunks).decode("utf-8-sig"))))
    assert len(parsed) == 2251 and len(chunks) >= 2 and len(checks) >= len(chunks)
    assert list(parsed[0]) == list(FIELDS["qbcc"])
    assert parsed[0]["licensee_name"] == "'=Untrusted"
    assert json.loads(parsed[0]["licence_types"]) == [{"code": "B", "description": "Builder"}]
    assert parsed[0]["geography_review_required"] == "false"
    assert all(row["state"] == "QLD" for row in parsed)
    assert audits[-1][2] == "source_export_completed" and audits[-1][-1]["rows"] == 2251


@pytest.mark.parametrize("stop", ["cancel", "deadline", "authority", "wrong_count"])
def test_interrupted_export_never_records_completion(monkeypatch, stop):
    current = ticket(total=1)
    audits = []
    monkeypatch.setattr(exports, "transaction", no_database)
    monkeypatch.setattr(exports, "iter_filtered_batches", lambda *args: iter(()))
    valid = [True]

    def authorize(*args):
        if not valid[0]:
            raise DomainError("AUTHORITY_QUARANTINED", 503)

    monkeypatch.setattr(exports, "_current", authorize)
    cancelled, now = threading.Event(), [0]
    iterator = exports.csv_chunks(None, SimpleNamespace(audit=lambda *args: audits.append(args)), current, cancelled, clock=lambda: now[0])
    assert next(iterator).startswith(b"\xef\xbb\xbf")
    if stop == "cancel":
        cancelled.set()
    elif stop == "deadline":
        now[0] = exports.EXPORT_SECONDS + 1
    elif stop == "authority":
        valid[0] = False
    with pytest.raises(DomainError):
        next(iterator)
    assert audits[-1][2] == "source_export_interrupted"


@pytest.mark.parametrize("failed_message", ["http.response.start", "http.response.body"])
def test_transport_disconnect_closes_stream_and_releases_lease(monkeypatch, failed_message):
    closed = []

    def chunks(*args):
        try:
            yield b"header\r\n"
            yield b"record\r\n"
        finally:
            closed.append(True)

    monkeypatch.setattr(exports, "csv_chunks", chunks)
    store = exports.TicketStore(clock=lambda: 0)
    current = ticket()
    store.consume(store.put(current), current.origin)

    async def scenario():
        response = exports.SourceCSVResponse(exports.stream_export(None, None, store, current), store=store, ticket=current)

        async def send(message):
            if message["type"] == failed_message:
                raise OSError("client disconnected")

        async def receive():
            return {"type": "http.disconnect"}

        with pytest.raises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)

    asyncio.run(scenario())
    assert not store.active
    assert bool(closed) is (failed_message == "http.response.body")


@pytest.mark.parametrize("stalled_message", ["http.response.start", "http.response.body"])
def test_stalled_transport_has_deadline_and_releases_export_lease(monkeypatch, stalled_message):
    monkeypatch.setattr(exports, "EXPORT_SECONDS", 5)
    closed = []

    def chunks(*args):
        try:
            yield b"header\n"
            yield b"record\n"
        finally:
            closed.append(True)

    monkeypatch.setattr(exports, "csv_chunks", chunks)
    store = exports.TicketStore(clock=lambda: 0)
    current = ticket()
    store.consume(store.put(current), current.origin)

    async def scenario():
        # Exercise a stalled network send after the worker is available, rather
        # than making cold thread startup race a very short synthetic deadline.
        await anyio.to_thread.run_sync(lambda: None)
        response = exports.SourceCSVResponse(exports.stream_export(None, None, store, current), store=store, ticket=current)

        async def send(message):
            if message["type"] == stalled_message:
                await anyio.sleep_forever()

        async def receive():
            return {"type": "http.disconnect"}

        with pytest.raises(TimeoutError):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)

    asyncio.run(scenario())
    assert not store.active
    assert bool(closed) is (stalled_message == "http.response.body")
