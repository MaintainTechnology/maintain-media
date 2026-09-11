"""Actual local DuckDB interruption, with no network or business records."""

import threading
import time
import zipfile

import duckdb
import pytest

from abr_engine.ingest.abr_download import ArchiveResource, ingest_archives
from abr_engine.ingest.abr_parse import ABRMapping
from abr_engine.ingest.common import SourceError
from abr_engine.ops.analytical import analytical_guard


def test_budget_failure_interrupts_actual_long_query_and_preserves_reason():
    started = time.monotonic()
    query_started = threading.Event()
    calls = []

    def check():
        calls.append(threading.current_thread().name)
        if query_started.is_set() and time.monotonic() - started > 0.15:
            raise SourceError("ABR_RUN_DEADLINE")

    with duckdb.connect() as connection:
        with pytest.raises(SourceError, match="ABR_RUN_DEADLINE"), analytical_guard(connection, check):
            query_started.set()
            connection.execute("SELECT sum(i*j) FROM range(1000000) a(i), range(1000000) b(j)")
        assert connection.execute("SELECT 1").fetchone() == (1,)
    assert time.monotonic() - started < 5
    assert "abr-analytical-budget" in calls
    assert not any(thread.name == "abr-analytical-budget" for thread in threading.enumerate())


def test_failed_initial_admission_executes_no_query():
    class Unused:
        def interrupt(self):
            raise AssertionError("No watcher may start")

    def closed():
        raise SourceError("GATE_G1_CLOSED")

    with pytest.raises(SourceError, match="GATE_G1_CLOSED"), analytical_guard(Unused(), closed):
        raise AssertionError("No analytical work may begin")


def test_callbacks_are_serialized_and_stopped_after_context():
    executing = threading.Lock()
    calls = []

    def check():
        assert executing.acquire(blocking=False), "Concurrent budget/authority callbacks are unsafe"
        try:
            calls.append(time.monotonic())
            time.sleep(0.01)
        finally:
            executing.release()

    with duckdb.connect() as connection, analytical_guard(connection, check, interval=0.01) as checkpoint:
        for _ in range(5):
            checkpoint()
            connection.execute("SELECT 1")
            time.sleep(0.01)
    final_count = len(calls)
    time.sleep(0.03)
    assert final_count == len(calls)
    assert final_count >= 7


def test_original_query_error_preserved_when_checks_pass():
    with (
        duckdb.connect() as connection,
        pytest.raises(duckdb.CatalogException),
        analytical_guard(connection, lambda: None),
    ):
        connection.execute("SELECT * FROM nonexistent_synthetic_table")


def test_archive_cross_member_scan_is_interruptible(tmp_path, monkeypatch):
    """Replace only the expensive query with a long local one at its real boundary."""
    xml = ('<Transfer error="false"><TransferInfo><FileSequenceNumber>1</FileSequenceNumber>'
           '<RecordCount>1</RecordCount><ExtractTime>2026-09-08T00:00:00</ExtractTime>'
           '<FixtureGeneration>synthetic</FixtureGeneration></TransferInfo><ABR>'
           '<ABN status="ACT" date="2024-01-31">51824753556</ABN><GST/>'
           '<EntityType>COMPANY</EntityType><MainName>Synthetic Only</MainName>'
           '<State>QLD</State><Postcode>4000</Postcode><Names/></ABR></Transfer>')
    path = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("part.xml", xml)
    resource = ArchiveResource("synthetic", "one", path, {"part.xml": "member"})
    inventory = [{"resource_id": "synthetic", "part_label": "one"}]
    real_connect = duckdb.connect
    query_started = threading.Event()
    entered_at = []

    class Connection:
        def __init__(self):
            self.actual = real_connect()

        def execute(self, query, *args):
            if query.startswith("SELECT abn FROM read_parquet"):
                entered_at.append(time.monotonic())
                query_started.set()
                return self.actual.execute("SELECT sum(i*j) FROM range(1000000) a(i), range(1000000) b(j)")
            return self.actual.execute(query, *args)

        def interrupt(self):
            self.actual.interrupt()

        def close(self):
            self.actual.close()

    def authority():
        if query_started.is_set() and time.monotonic() - entered_at[0] > 0.1:
            raise SourceError("ABR_RUN_DEADLINE")

    monkeypatch.setattr(duckdb, "connect", Connection)
    with pytest.raises(SourceError, match="ABR_RUN_DEADLINE"):
        ingest_archives([resource], tmp_path / "stage", mapping=ABRMapping.fixture(),
                        inventory_before=inventory, inventory_after=inventory,
                        required_parts={"one"}, expected_sequences={1}, authority=authority)
    assert len(entered_at) == 1 and time.monotonic() - entered_at[0] < 5
