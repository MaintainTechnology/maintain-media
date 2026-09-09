"""Strict UTF-16LE QBCC fixture mapping with per-licence quarantine."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .common import SourceError, canonical_json, digest_file, normalize_abn


@dataclass(frozen=True)
class QBCCMapping:
    version: str
    columns: dict[str, str]
    fixture_only: bool = True
    approved_evidence: str | None = None

    @classmethod
    def fixture(cls) -> QBCCMapping:
        return cls(
            "synthetic-qbcc-v1",
            {
                "licence_number": "Licence Number",
                "licensee_name": "Licensee Name",
                "abn": "ABN",
                "financial_category": "Financial Category",
                "original_address": "Address",
                "class_type": "Licence Class",
                "status": "Status",
                "entity_class": "Entity Class",
            },
        )


@dataclass(frozen=True)
class QBCCResult:
    records: tuple[dict, ...]
    quarantined: tuple[dict, ...]
    source_sha256: str
    row_count: int
    category_counts: dict[str, int]
    mapping_version: str


def parse_address(address: str) -> tuple[str | None, str | None]:
    match = re.search(r"(?:^|[ ,\r\n])(QLD|NSW|VIC|TAS|SA|WA|NT|ACT)\s+([0-9]{4})\s*$", address)
    return (match[1], match[2]) if match else (None, None)


def parse_qbcc(
    path: Path,
    *,
    mapping: QBCCMapping | None = None,
    production: bool = False,
    max_rows: int = 1_000_000,
    max_file_bytes: int = 512 * 1024**2,
) -> QBCCResult:
    mapping = mapping or QBCCMapping.fixture()
    if production and (mapping.fixture_only or not mapping.approved_evidence):
        raise SourceError("SOURCE_MAPPING_UNAPPROVED")
    if path.stat().st_size > max_file_bytes:
        raise SourceError("SOURCE_SIZE_LIMIT")
    grouped: dict[str, list[dict]] = {}
    row_count = 0
    with path.open("rb") as raw:
        if raw.read(2) != b"\xff\xfe":
            raise SourceError("QBCC_UTF16LE_BOM_REQUIRED")
        stream = io.TextIOWrapper(raw, encoding="utf-16-le", errors="strict", newline="")
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(mapping.columns.values()):
            raise SourceError("QBCC_HEADER_MISMATCH")
        for input_row in reader:
            row_count += 1
            if row_count > max_rows:
                raise SourceError("SOURCE_ROW_LIMIT")
            if None in input_row or any(v is None for v in input_row.values()):
                raise SourceError("QBCC_COLUMN_COUNT_MISMATCH")
            row = {key: input_row[col].strip() for key, col in mapping.columns.items()}
            if not row["licence_number"] or not row["licensee_name"]:
                raise SourceError("QBCC_REQUIRED_FIELD_MISSING")
            grouped.setdefault(row["licence_number"], []).append(row)
    records: list[dict] = []
    quarantine: list[dict] = []
    counts: dict[str, int] = {}
    for licence, rows in sorted(grouped.items()):
        reasons: set[str] = set()
        for row in rows:
            try:
                row["abn"] = normalize_abn(row["abn"], optional=True)
            except SourceError:
                reasons.add("INVALID_ABN")
        fields = [k for k in mapping.columns if k != "class_type"]
        if any(len({row[key] for row in rows}) > 1 for key in fields):
            reasons.add("CONFLICTING_LICENCE_FIELDS")
        if any(row["status"] not in ("ACTIVE", "SUSPENDED", "CANCELLED", "INACTIVE") for row in rows):
            reasons.add("UNKNOWN_LICENCE_STATUS")
        if any(
            row["financial_category"] not in ("SC1", "SC2", "1", "2", "3", "4", "5", "6", "7") for row in rows
        ):
            reasons.add("UNKNOWN_FINANCIAL_CATEGORY")
        if reasons:
            quarantine.append(
                {"licence_number": licence, "reason_codes": sorted(reasons), "row_count": len(rows)}
            )
            continue
        row = {key: rows[0][key] for key in fields}
        row["class_types"] = sorted({r["class_type"] for r in rows if r["class_type"]})
        row["state"], row["postcode"] = parse_address(row["original_address"])
        row["geography_review_required"] = row["state"] is None
        row["row_digest"] = hashlib.sha256(canonical_json(row).encode()).hexdigest()
        records.append(row)
        counts[row["financial_category"]] = counts.get(row["financial_category"], 0) + 1
    return QBCCResult(
        tuple(records), tuple(quarantine), digest_file(path), row_count, counts, mapping.version
    )


def write_qbcc_parquet(result: QBCCResult, output: Path) -> Path:
    if output.exists():
        raise SourceError("ARTIFACT_ALREADY_EXISTS")
    schema = pa.schema(
        [
            (k, pa.string())
            for k in (
                "licence_number",
                "licensee_name",
                "abn",
                "financial_category",
                "original_address",
                "status",
                "entity_class",
                "state",
                "postcode",
                "row_digest",
            )
        ]
        + [("class_types", pa.list_(pa.string())), ("geography_review_required", pa.bool_())]
    )
    table = pa.Table.from_pylist(list(result.records), schema=schema)
    pq.write_table(table, output, compression="zstd")
    if pq.read_table(output).num_rows != len(result.records):
        raise SourceError("ARTIFACT_READBACK_FAILED")
    return output


def qbcc_events(previous: QBCCResult | None, current: QBCCResult):
    prior = {r["licence_number"]: r for r in previous.records} if previous else {}
    for row in current.records:
        if row["financial_category"] not in ("1", "2") or row["status"] != "ACTIVE":
            continue
        before = prior.get(row["licence_number"])
        kind = (
            "icp_backlog"
            if previous is None
            else "new"
            if before is None
            else "category_changed"
            if before["financial_category"] != row["financial_category"]
            else None
        )
        if kind:
            yield {
                "licence_number": row["licence_number"],
                "event_type": kind,
                "before": before,
                "after": row,
            }
