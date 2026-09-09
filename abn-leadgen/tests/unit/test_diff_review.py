"""Independent range-join review using synthetic canonical-shaped Parquet rows."""
import json
from datetime import UTC, date, datetime
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from abr_engine.diff.events import diff_snapshots, iter_events
from abr_engine.ingest.abr_parse import SCHEMA
from abr_engine.ingest.common import SourceError


def row(abn, **change):
    return {"abn": str(abn), "status": "ACT", "status_date": date(2026, 1, 1),
        "gst_status": "NONE", "gst_date": date(2026, 1, 2), "entity_type": "COMPANY",
        "entity_class": "company", "main_name": "Synthetic", "names_json": "{}", "state": "QLD",
        "postcode": "4000", "name_hash": "old", "semantic_hash": "synthetic", "source_member": "fixture", **change}


def parquet(tmp_path, name, rows, schema=SCHEMA):
    path = tmp_path / name
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, row_group_size=10000)
    return path


def run(tmp_path, previous, current, **kwargs):
    return diff_snapshots(previous, current, tmp_path / "events.parquet", snapshot_id=str(uuid4()),
        observed_at=datetime(2026, 9, 8, tzinfo=UTC), **kwargs)


def test_range_join_emits_multiple_events_and_preserves_boundaries(tmp_path):
    low, middle, high = "10000000000", "55000000000", "99999999999"
    before = [row(low), row(middle, status="CAN"), row(high)]
    after = [row(low, status="CAN", gst_status="ACT", name_hash="new"),
        row(middle, gst_status="ACT"), row("99999999998")]
    result = run(tmp_path, [parquet(tmp_path, "old.parquet", before)], [parquet(tmp_path, "new.parquet", after)])
    events = list(iter_events(result.path))
    assert {(e["abn"], e["event_type"]) for e in events} == {
        (low, "abn_cancelled"), (low, "gst_registered"), (low, "name_changed"),
        (middle, "abn_reactivated"), (middle, "gst_registered"),
        (high, "abn_disappeared"), ("99999999998", "abn_new")}
    assert len({e["event_id"] for e in events}) == result.event_count == 7
    for event in events:
        if event["event_type"] == "abn_disappeared":
            assert event["quarantined"] and event["after_json"] is None
        elif event["event_type"] == "abn_new":
            assert event["before_json"] is None
        else:
            assert json.loads(event["before_json"])["abn"] == event["abn"]


def test_adaptive_skew_subdivision_keeps_every_key_once(tmp_path):
    # More than the actual 200k threshold concentrated into a tiny numeric range,
    # plus a far-edge outlier: repeated empty range subdivision must lose no keys.
    rows = [row(10000000000 + i) for i in range(200001)] + [row(99999999999)]
    before = parquet(tmp_path, "old.parquet", rows)
    changed = {rows[0]["abn"], rows[99999]["abn"], rows[100000]["abn"], rows[-2]["abn"], rows[-1]["abn"]}
    for item in rows:
        if item["abn"] in changed:
            item["name_hash"] = "changed"
    after = parquet(tmp_path, "new.parquet", rows)
    result = run(tmp_path, [before], [after])
    events = list(iter_events(result.path))
    assert len(events) == 5
    assert {e["abn"] for e in events} == changed
    assert {e["event_type"] for e in events} == {"name_changed"}


@pytest.mark.parametrize("baseline", [True, False])
def test_baseline_and_noop_write_readable_empty_outputs(tmp_path, baseline):
    current = parquet(tmp_path, "current.parquet", [row(10000000000)])
    result = run(tmp_path, None if baseline else [current], [current])
    assert result.event_count == 0 and list(iter_events(result.path)) == []
    assert "event_id" in pq.ParquetFile(result.path).schema.names


def test_schema_rebaseline_is_explicit_and_never_emits_new_signals(tmp_path):
    previous = parquet(tmp_path, "old.parquet", [row(10000000000)])
    current = parquet(tmp_path, "new.parquet", [row(99999999999)], SCHEMA.with_metadata({b"parser_version": b"new"}))
    with pytest.raises(SourceError, match="PARSER_SCHEMA_REBASELINE_REQUIRED"):
        run(tmp_path, [previous], [current])
    assert not (tmp_path / "events.parquet").exists()
    assert run(tmp_path, [previous], [current], rebaseline=True).event_count == 0


def test_duplicate_cross_part_key_rejected_before_output(tmp_path):
    old = parquet(tmp_path, "old.parquet", [row(10000000000)])
    first = parquet(tmp_path, "first.parquet", [row(10000000000)])
    second = parquet(tmp_path, "second.parquet", [row(10000000000)])
    with pytest.raises(SourceError, match="DUPLICATE_ABN"):
        run(tmp_path, [old], [first, second])
    assert not (tmp_path / "events.parquet").exists()


def test_failed_final_writer_removes_partial_output_for_retry(tmp_path, monkeypatch):
    old = parquet(tmp_path, "old.parquet", [row(10000000000)])
    new = parquet(tmp_path, "new.parquet", [row(10000000000, name_hash="changed")])
    real_write = pq.ParquetWriter.write_batch
    def fail_after_write(self, batch, *args, **kwargs):
        real_write(self, batch, *args, **kwargs)
        raise OSError("Synthetic final storage failure")
    monkeypatch.setattr(pq.ParquetWriter, "write_batch", fail_after_write)
    with pytest.raises(OSError, match="Synthetic final storage failure"):
        run(tmp_path, [old], [new])
    assert not (tmp_path / "events.parquet").exists(), "Failed diff must not leave an apparently valid partial event artifact"
    assert not list(tmp_path.glob("events.parquet.part-*"))
    monkeypatch.setattr(pq.ParquetWriter, "write_batch", real_write)
    assert run(tmp_path, [old], [new]).event_count == 1
