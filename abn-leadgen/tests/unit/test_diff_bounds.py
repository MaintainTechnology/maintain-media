"""Finite materialized comparison of synthetic records only."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from abr_engine.diff.events import diff_snapshots
from abr_engine.ingest.abr_parse import SCHEMA
from abr_engine.ingest.common import SourceError


def inputs(tmp_path, count=2):
    rows = [{"abn": str(10000000000 + index), "status": "ACT", "status_date": date(2026, 1, 1),
             "gst_status": "NONE", "gst_date": None, "entity_type": "COMPANY", "entity_class": "company",
             "main_name": "Synthetic", "names_json": "{}", "state": "QLD", "postcode": "4000",
             "name_hash": "old", "semantic_hash": "old", "source_member": "fixture"}
            for index in range(count)]
    before, after = tmp_path / "before.parquet", tmp_path / "after.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), before)
    pq.write_table(pa.Table.from_pylist([{**row, "name_hash": "new"} for row in rows], schema=SCHEMA), after)
    return [before], [after]


def run(tmp_path, previous, current, **kwargs):
    return diff_snapshots(previous, current, tmp_path / "events.parquet", snapshot_id=str(uuid4()),
                          observed_at=datetime.now(UTC), **kwargs)


def test_event_limit_refuses_before_any_output_is_materialized(tmp_path, monkeypatch):
    before, after = inputs(tmp_path)
    def forbidden_writer(*args, **kwargs):
        raise AssertionError("Over-budget event relation must be refused before materialization")
    monkeypatch.setattr(pq, "ParquetWriter", forbidden_writer)
    with pytest.raises(SourceError, match="ABR_EVENT_COUNT_LIMIT"):
        run(tmp_path, before, after, max_events=1)
    assert not (tmp_path / "events.parquet").exists()
    assert not list(tmp_path.glob("events.parquet.part-*"))


def test_exact_event_cap_and_progress_preserve_complete_output(tmp_path):
    before, after = inputs(tmp_path)
    progress, checks = [], []
    result = run(tmp_path, before, after, max_events=2, max_output_bytes=1_000_000,
                 progress=progress.append, authority=lambda: checks.append("authority"),
                 check=lambda: checks.append("budget"))
    assert result.event_count == pq.ParquetFile(result.path).metadata.num_rows == 2
    assert progress == [{"event_count": 2}]
    assert checks.count("authority") > 10 and checks.count("budget") > 10


def test_output_limit_cleans_incomplete_materialization(tmp_path):
    before, after = inputs(tmp_path)
    with pytest.raises(SourceError, match="ABR_EVENT_STORAGE_LIMIT"):
        run(tmp_path, before, after, max_output_bytes=1)
    assert not (tmp_path / "events.parquet").exists()
    assert not list(tmp_path.glob("events.parquet.part-*"))


def test_authority_withdrawal_during_output_stops_before_valid_receipt(tmp_path):
    before, after = inputs(tmp_path)
    withdrawn = False
    def progress(_):
        nonlocal withdrawn
        withdrawn = True
    def authority():
        if withdrawn:
            raise SourceError("GATE_G1_CLOSED")
    with pytest.raises(SourceError, match="GATE_G1_CLOSED"):
        run(tmp_path, before, after, authority=authority, progress=progress)
    assert not (tmp_path / "events.parquet").exists()


def test_baseline_emits_zero_with_zero_event_budget(tmp_path):
    _, after = inputs(tmp_path)
    result = run(tmp_path, None, after, max_events=0, max_output_bytes=100_000)
    assert result.event_count == 0


def test_preexisting_part_is_never_deleted(tmp_path):
    before, after = inputs(tmp_path)
    part = tmp_path / "events.parquet.part-10000000000-10000000001"
    part.write_bytes(b"unrelated preserved file")
    with pytest.raises(SourceError, match="DIFF_PART_ALREADY_EXISTS"):
        run(tmp_path, before, after)
    assert part.read_bytes() == b"unrelated preserved file"
