"""Materialised synthetic full-output diff workload and explicit capacity evidence."""
import hashlib
import json
import platform
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from abr_engine.config import ROOT
from abr_engine.diff.events import diff_snapshots
from abr_engine.ops.capacity import CapacityPlan, measure_callable


def benchmark(rows: int, output: Path):
    if not 100 <= rows <= 20_500_000:
        raise ValueError("Rows must be 1 through 20500000")
    output = output.resolve()
    if output.exists():
        raise ValueError("Benchmark evidence output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = ROOT / "var" / ("benchmark-" + uuid4().hex)
    # Worst-case upper bounds, no advertised host-capacity assumption.
    # Bounded fixture sizing: 10k-row output is measured before admitting the full run.
    sample = benchmark(10000, output.parent / ("sizing-" + uuid4().hex + ".json")) if rows > 10000 else None
    estimate = int(sample["output_bytes"] / 10000 * rows * 2) if sample else rows * 4096
    plan = CapacityPlan(remaining_downloads=0, staged_parquet_upper_bound=estimate,
                        prior_snapshot_bytes=0, new_snapshot_upper_bound=estimate,
                        configured_spill_limit=8*1024**3, projected_db_growth=0, projected_wal_growth=0,
                        temporary_backup_bytes=0)
    free = shutil.disk_usage(output.parent).free
    if not plan.admit(free):
        raise ValueError("CAPACITY_PREFLIGHT_FAILED")
    work.mkdir(parents=True)
    previous, current, events = work / "previous.parquet", work / "current.parquet", work / "events.parquet"
    def operation():
        con = duckdb.connect()
        try:
            con.execute("SET memory_limit='512MB'")
            con.execute("SET threads=2")
            con.execute("SET max_temp_directory_size='8GB'")
            con.execute("SET temp_directory=?", [str(work / "spill")])
            # Synthetic unique 11-digit benchmark keys, not claims of valid registered ABNs.
            # Source checksum parsing is exercised separately by parser acceptance fixtures.
            con.from_query("SELECT * FROM range(?) t(i)", params=[rows]).create_view("benchmark_numbers")
            con.execute("CREATE VIEW base AS SELECT lpad(i::VARCHAR,11,'0') abn,CASE WHEN i%100=2 THEN 'CAN' ELSE 'ACT' END status,'2024-01-31' status_date,"
                        "CASE WHEN i%100=4 THEN 'ACT' ELSE 'NONE' END gst_status,NULL::VARCHAR gst_date,'COMPANY' entity_type,'company' entity_class,"
                        "'Synthetic wide business '||repeat('name ',30)||i::VARCHAR main_name,'{}' names_json,"
                        "'QLD' state,'4000' postcode,md5(i::VARCHAR) name_hash,md5(i::VARCHAR) semantic_hash,"
                        "'synthetic' source_member FROM benchmark_numbers")
            con.execute("COPY (SELECT * FROM base WHERE CAST(abn AS BIGINT)%100 != 0) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)", [str(previous)])
            con.execute("COPY (SELECT * REPLACE (CASE WHEN CAST(abn AS BIGINT)%100=1 THEN 'CAN' WHEN CAST(abn AS BIGINT)%100=2 THEN 'ACT' ELSE status END AS status,"
                        "CASE WHEN CAST(abn AS BIGINT)%100=3 THEN 'ACT' WHEN CAST(abn AS BIGINT)%100=4 THEN 'NONE' ELSE gst_status END AS gst_status,"
                        "CASE WHEN CAST(abn AS BIGINT)%100 IN (3,4) THEN '2026-09-08' ELSE gst_date END AS gst_date,"
                        "CASE WHEN CAST(abn AS BIGINT)%100=5 THEN md5(abn) ELSE name_hash END AS name_hash) FROM base WHERE CAST(abn AS BIGINT)%100 != 6) "
                        "TO ? (FORMAT PARQUET,COMPRESSION ZSTD)", [str(current)])
        finally:
            con.close()
        return diff_snapshots([previous], [current], events, snapshot_id=str(uuid4()), observed_at=datetime.now(UTC))
    result, metrics = measure_callable(operation, rows=rows, runtime_version=platform.python_version(),
                                       output_paths=[previous, current, events])
    con = duckdb.connect()
    try:
        con.from_parquet(str(events)).create_view("events")
        event_counts = dict(con.execute("SELECT event_type,count(*) FROM events GROUP BY event_type").fetchall())
    finally:
        con.close()
    metrics.update({"event_count": result.event_count, "event_counts": event_counts, "sizing_sample": sample,
                    "admission": plan.model_dump(), "free_bytes_before": free,
                    "required_free_bytes": plan.required_free_bytes(), "lockfile_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
                    "artifact_paths": [str(previous),str(current),str(events)], "input_kind": "synthetic-wide-unique-keys",
                    "ingest_parser_measured": False, "all_event_types_measured": len(event_counts) == 7,
                    "full_scale_certified": False, "db_wal_measured": False,
                    "limitation": "Measures generation plus materialised diff, not the full source-to-CRM pipeline or approved host capacity."})
    output.write_text(json.dumps(metrics, indent=2))
    return {"status": "complete", "evidence": str(output), **metrics}
