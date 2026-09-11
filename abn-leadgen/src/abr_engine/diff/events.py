"""Full outer join with fully materialized event output, not a count benchmark."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

import duckdb
import pyarrow.parquet as pq

from abr_engine.ingest.common import SourceError
from abr_engine.ops.analytical import analytical_guard


@dataclass(frozen=True)
class DiffResult:
    path: Path
    event_count: int


def diff_snapshots(
    previous: list[Path] | None,
    current: list[Path],
    output_path: Path,
    *,
    snapshot_id: str,
    observed_at: datetime,
    previous_snapshot_id: str | None = None,
    rebaseline: bool = False,
    max_spill_bytes: int = 8 * 1024**3,
    threads: int = 3,
    authority: Callable[[], object] | None = None,
    check: Callable[[], object] | None = None,
    progress: Callable[[dict], object] | None = None,
    max_events: int | None = None,
    max_output_bytes: int | None = None,
) -> DiffResult:
    UUID(snapshot_id)
    if type(threads) is not int or not 1 <= threads <= 3:
        raise ValueError("Invalid analytical thread limit")
    if max_events is not None and (type(max_events) is not int or max_events < 0):
        raise ValueError("Invalid analytical event limit")
    if max_output_bytes is not None and (type(max_output_bytes) is not int or max_output_bytes <= 0):
        raise ValueError("Invalid analytical output limit")
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone aware")
    if not current or output_path.exists():
        raise SourceError("MISSING_INPUT_OR_OUTPUT_EXISTS")
    versions = [pq.ParquetFile(path).schema_arrow.metadata for path in (previous or []) + current]
    if any(v != versions[0] for v in versions) and not rebaseline:
        raise SourceError("PARSER_SCHEMA_REBASELINE_REQUIRED")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    emitted = 0

    def bounded_check():
        if check is not None:
            check()
        if max_output_bytes is not None:
            total = 0
            for path in (output_path, *output_path.parent.glob(output_path.name + ".part-*")):
                try:
                    total += path.stat().st_size
                except FileNotFoundError:
                    continue  # A completed part can be removed between checks.
            if total > max_output_bytes:
                raise SourceError("ABR_EVENT_STORAGE_LIMIT")

    def checkpoint():
        active_check()
        if authority is not None:
            authority()

    def execute(query, parameters=None):
        checkpoint()
        result = con.execute(query, parameters) if parameters is not None else con.execute(query)
        checkpoint()
        return result

    def _materialize():
        nonlocal emitted
        execute("SET memory_limit='512MB'")
        execute("SET threads=?", [threads])
        execute("SET preserve_insertion_order=false")
        execute("SET temp_directory=?", [str(output_path.parent / "diff-spill")])
        execute("SET max_temp_directory_size=?", [f"{max_spill_bytes}B"])
        con.from_parquet([str(p) for p in current]).create_view("all_current_rows")
        if previous and not rebaseline:
            con.from_parquet([str(p) for p in previous]).create_view("all_previous_rows")
        else:
            execute("CREATE VIEW all_previous_rows AS SELECT * FROM all_current_rows WHERE false")
        for name in ("all_previous_rows", "all_current_rows"):
            if execute(f"SELECT abn FROM {name} GROUP BY abn HAVING count(*)>1 LIMIT 1").fetchone():
                raise SourceError("DUPLICATE_ABN")
        execute(
            "CREATE TABLE context(snapshot_id VARCHAR, previous_snapshot_id VARCHAR, observed_at TIMESTAMPTZ, enabled BOOLEAN)"
        )
        execute(
            "INSERT INTO context VALUES (?,?,?,?)",
            [snapshot_id, previous_snapshot_id, observed_at, bool(previous) and not rebaseline],
        )
        # Every event is output; one ABN may generate several independent events.
        query = """
        WITH paired AS (
          SELECT coalesce(c.abn,p.abn) abn, p.status ps,c.status cs,p.gst_status pg,c.gst_status cg,
            p.abn pabn,c.abn cabn,p.name_hash pn,c.name_hash cn,
            c.status_date status_date,c.gst_date gst_date,
            CASE WHEN p.abn IS NOT NULL THEN to_json(p) END before_json,
            CASE WHEN c.abn IS NOT NULL THEN to_json(c) END after_json
          FROM previous_rows p FULL OUTER JOIN current_rows c ON p.abn=c.abn
          WHERE p.abn IS NULL OR c.abn IS NULL OR p.status!=c.status
             OR p.gst_status!=c.gst_status OR p.name_hash!=c.name_hash
        )
        SELECT CAST(md5(snapshot_id || ':' || abn || ':' || event_type) AS UUID)::VARCHAR event_id,
          snapshot_id,previous_snapshot_id,abn,event_type,observed_at,
          CASE WHEN event_type IN ('gst_registered','gst_cancelled') THEN gst_date
               WHEN event_type IN ('abn_new','abn_cancelled','abn_reactivated') THEN status_date END effective_date,
          before_json,after_json,event_type='abn_disappeared' quarantined
        FROM paired CROSS JOIN context
        CROSS JOIN LATERAL (VALUES
          ('abn_new',pabn IS NULL AND cs='ACT'),
          ('abn_cancelled',ps='ACT' AND cs='CAN'),
          ('abn_reactivated',ps='CAN' AND cs='ACT'),
          ('gst_registered',pabn IS NOT NULL AND pg!='ACT' AND cg='ACT'),
          ('gst_cancelled',pabn IS NOT NULL AND pg='ACT' AND cg!='ACT'),
          ('name_changed',pabn IS NOT NULL AND cabn IS NOT NULL AND pn!=cn),
          ('abn_disappeared',pabn IS NOT NULL AND cabn IS NULL)
        ) events(event_type,emitted)
        WHERE enabled AND emitted ORDER BY abn,event_type
        """
        # Each join is bounded to at most 400k rows per side. Numeric ABN ranges preserve
        # exact whole-set semantics, including absent keys and simultaneous event types.
        # Adaptive subdivision handles skew; Parquet row-group statistics prune ordered sources.
        bounds = execute("SELECT min(abn),max(abn) FROM (SELECT abn FROM all_previous_rows UNION ALL SELECT abn FROM all_current_rows)").fetchone()
        assert bounds is not None
        ranges = [(int(bounds[0]), int(bounds[1]))] if bounds[0] is not None and previous and not rebaseline else []
        writer = None
        try:
            while ranges:
                checkpoint()
                low, high = ranges.pop()
                predicate = f"abn BETWEEN '{low:011d}' AND '{high:011d}'"
                counts = []
                for name in ("all_previous_rows", "all_current_rows"):
                    count_row = execute(f"SELECT count(*) FROM {name} WHERE {predicate}").fetchone()
                    assert count_row is not None
                    counts.append(count_row[0])
                if max(counts) > 400000 and low < high:
                    middle = (low + high) // 2
                    ranges.extend([(middle + 1, high), (low, middle)])
                    continue
                for side in ("previous", "current"):
                    execute(f"CREATE OR REPLACE VIEW {side}_rows AS SELECT * FROM all_{side}_rows WHERE {predicate}")
                if max_events is not None:
                    count_row = execute(f"SELECT count(*) FROM ({query}) prospective_events").fetchone()
                    assert count_row is not None
                    if emitted + count_row[0] > max_events:
                        raise SourceError("ABR_EVENT_COUNT_LIMIT")
                part = output_path.parent / (output_path.name + f".part-{low}-{high}")
                if part.exists():
                    raise SourceError("DIFF_PART_ALREADY_EXISTS")
                try:
                    escaped = str(part).replace("'", "''")
                    execute(f"COPY ({query}) TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)")
                    with pq.ParquetFile(part) as parquet:
                        if writer is None:
                            writer = pq.ParquetWriter(output_path, parquet.schema_arrow, compression="zstd")
                        for batch in parquet.iter_batches(batch_size=10000):
                            checkpoint()
                            emitted += batch.num_rows
                            if max_events is not None and emitted > max_events:
                                raise SourceError("ABR_EVENT_COUNT_LIMIT")
                            writer.write_batch(batch)
                            checkpoint()
                            if progress is not None:
                                progress({"event_count": emitted})
                finally:
                    part.unlink(missing_ok=True)
            if writer is None:
                for side in ("previous", "current"):
                    execute(f"CREATE OR REPLACE VIEW {side}_rows AS SELECT * FROM all_{side}_rows WHERE false")
                escaped = str(output_path).replace("'", "''")
                execute(f"COPY ({query}) TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        finally:
            if writer:
                writer.close()
        checkpoint()
        with pq.ParquetFile(output_path) as result:
            for _ in result.iter_batches(batch_size=10000):
                checkpoint()
            if result.metadata.num_rows != emitted:
                raise SourceError("DIFF_OUTPUT_COUNT_MISMATCH")
            return DiffResult(output_path, result.metadata.num_rows)

    try:
        watcher_check = bounded_check if check is not None or max_output_bytes is not None else None
        with analytical_guard(con, watcher_check) as active_check:
            return _materialize()
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    finally:
        con.close()


def iter_events(path: Path, batch_size: int = 50000) -> Iterator[dict]:
    if not 1 <= batch_size <= 50000:
        raise ValueError("invalid batch size")
    with pq.ParquetFile(path) as parquet:
        for batch in parquet.iter_batches(batch_size=batch_size):
            yield from batch.to_pylist()
