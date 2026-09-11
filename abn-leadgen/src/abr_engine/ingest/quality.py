"""Closed, row-weighted publication quality across member repartition."""

from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from abr_engine.ingest.abr_parse import ABRMapping
from abr_engine.ingest.common import SourceError

REQUIRED_FILL_FIELDS = ABRMapping.fixture().required_fields


def weighted_fill(members) -> dict:
    total = sum(member.row_count for member in members)
    if total <= 0 or any(set(member.field_fill) != set(REQUIRED_FILL_FIELDS) for member in members):
        raise SourceError("FIELD_FILL_EVIDENCE_MISSING")
    return {
        "source_rows": total,
        "field_fill_weighted": {
            field: sum(member.row_count * member.field_fill[field] for member in members) / total
            for field in REQUIRED_FILL_FIELDS
        },
    }


def parquet_fill(paths: list[Path], *, check=None) -> dict:
    """Verify the actual publication columns; no whole-register Python objects."""
    con = duckdb.connect()
    try:
        con.execute("SET memory_limit='512MB'")
        con.execute("SET threads=2")
        con.execute("SET max_temp_directory_size='8GB'")
        projection = ",".join(
            f"sum(CASE WHEN {field} IS NOT NULL AND CAST({field} AS VARCHAR)<>'' THEN 1 ELSE 0 END)"
            for field in REQUIRED_FILL_FIELDS
        )
        from abr_engine.ops.analytical import analytical_guard

        with analytical_guard(con, check):
            row = con.execute(
                f"SELECT count(*),{projection} FROM read_parquet(?)", [[str(path) for path in paths]]
            ).fetchone()
        if not row or row[0] <= 0:
            raise SourceError("FIELD_FILL_EVIDENCE_MISSING")
        result = {
            "source_rows": row[0],
            "field_fill_weighted": {
                field: row[index + 1] / row[0] for index, field in enumerate(REQUIRED_FILL_FIELDS)
            },
        }
        from abr_engine.ingest.abr_public import PUBLIC_SCHEMA

        if all(pq.read_schema(path).equals(PUBLIC_SCHEMA, check_metadata=True) for path in paths):
            result["source_contract"] = "abr-public-v1"
        return result
    finally:
        con.close()


def validate_fill(actual: dict, declared: dict, previous: dict | None = None) -> None:
    stated = declared.get("field_fill_weighted")
    if stated is not None and (
        not isinstance(stated, dict)
        or set(stated) != set(REQUIRED_FILL_FIELDS)
        or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in stated.values())
        or any(
            abs(stated[field] - actual["field_fill_weighted"][field]) > 1e-9 for field in REQUIRED_FILL_FIELDS
        )
    ):
        raise SourceError("FIELD_FILL_EVIDENCE_MISMATCH")
    if declared.get("source_rows") is not None and declared["source_rows"] != actual["source_rows"]:
        raise SourceError("FIELD_FILL_EVIDENCE_MISMATCH")
    if previous and any(
        abs(actual["field_fill_weighted"][field] - previous["field_fill_weighted"][field]) > 0.0200000001
        for field in REQUIRED_FILL_FIELDS
    ):
        raise SourceError("FIELD_FILL_BREACH")
    # Public XSD strings allow empty names/geography. A manifest label alone
    # cannot grant that allowance: every actual Parquet schema must match too.
    nullable = set()
    if (
        actual.get("source_contract") == "abr-public-v1"
        and declared.get("parser_version") == "abr-public-v1"
        and declared.get("mapping_version") == "abn-lookup-public-20260911-v1"
    ):
        nullable = {"main_name", "state", "postcode"}
    if any(value != 1 for field, value in actual["field_fill_weighted"].items() if field not in nullable):
        raise SourceError("REQUIRED_FIELD_MISSING")
