"""Hardened streaming XML -> bounded, zstd-compressed Arrow batches.

The fixture mapping is intentionally NOT an assertion about the live ABR schema.
Namespace-aware ElementTree paths come from a reviewed mapping. No source field
is discovered by fuzzy tag matching or silently promoted to an active enum.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO

import pyarrow as pa
import pyarrow.parquet as pq
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import DefusedXMLParser, iterparse

from .common import SourceError, canonical_json, canonical_name, digest_file, normalize_abn, ordered_names

PARSER_VERSION = "fixture-abr-v1"
SCHEMA_VERSION = "business-state-v1"
SCHEMA = pa.schema(
    [
        ("abn", pa.string()),
        ("status", pa.string()),
        ("status_date", pa.date32()),
        ("gst_status", pa.string()),
        ("gst_date", pa.date32()),
        ("entity_type", pa.string()),
        ("entity_class", pa.string()),
        ("main_name", pa.string()),
        ("names_json", pa.string()),
        ("state", pa.string()),
        ("postcode", pa.string()),
        ("name_hash", pa.string()),
        ("semantic_hash", pa.string()),
        ("source_member", pa.string()),
    ],
    metadata={b"schema_version": SCHEMA_VERSION.encode(), b"parser_version": PARSER_VERSION.encode()},
)


@dataclass(frozen=True)
class ABRMapping:
    version: str
    root_tag: str
    record_tag: str
    header_tag: str
    fields: dict[str, str]
    header_fields: dict[str, str]
    name_paths: dict[str, str]
    entity_classes: dict[str, str]
    success_values: tuple[str, ...] = ("false",)
    fixture_only: bool = True
    approved_evidence: str | None = None
    root_error_attribute: str = "error"
    required_fields: tuple[str, ...] = (
        "abn",
        "status",
        "status_date",
        "entity_type",
        "main_name",
        "state",
        "postcode",
    )

    @classmethod
    def fixture(cls, namespace: str = "") -> ABRMapping:
        n = f"{{{namespace}}}" if namespace else ""
        return cls(
            version="synthetic-abr-mapping-v1",
            root_tag=f"{n}Transfer",
            record_tag=f"{n}ABR",
            header_tag=f"{n}TransferInfo",
            fields={
                "abn": f"{n}ABN",
                "status": f"{n}ABN/@status",
                "status_date": f"{n}ABN/@date",
                "gst_status": f"{n}GST/@status",
                "gst_date": f"{n}GST/@date",
                "entity_type": f"{n}EntityType",
                "main_name": f"{n}MainName",
                "state": f"{n}State",
                "postcode": f"{n}Postcode",
            },
            header_fields={
                "sequence": f"{n}FileSequenceNumber",
                "record_count": f"{n}RecordCount",
                "extract_time": f"{n}ExtractTime",
                "generation": f"{n}FixtureGeneration",
            },
            name_paths={t: f"{n}Names/{n}{t}" for t in ("BN", "TRD", "OTN")},
            entity_classes={"COMPANY": "company", "TRUST": "trust", "INDIVIDUAL": "individual"},
        )

    def validate(self, production: bool) -> None:
        if production and (self.fixture_only or not self.approved_evidence):
            raise SourceError("SOURCE_MAPPING_UNAPPROVED")
        if not self.version or not self.header_fields.get("generation"):
            raise SourceError("GENERATION_UNPROVABLE")


@dataclass(frozen=True)
class ParsedMember:
    parquet_path: Path
    row_count: int
    sha256: str
    parquet_sha256: str
    header: dict[str, str]
    field_fill: dict[str, float]
    first_abn: str | None
    last_abn: str | None
    mapping_version: str


@dataclass
class _BoundedReader:
    stream: BinaryIO
    limit: int
    total: int = 0
    record_start: int = 0

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(min(65536, size) if size >= 0 else 65536)
        self.total += len(data)
        if self.total - self.record_start > self.limit + 65536:
            raise SourceError("RECORD_SIZE_LIMIT")
        return data


class _SizedParser(DefusedXMLParser):
    """Bound text/attributes/depth during parser callbacks, before tree growth.

    Reader bounds alone cannot constrain a huge transfer header or root text.
    These callbacks also cover those regions and use the secure parser's normal
    entity/DTD restrictions. No parser payload is exposed through diagnostics.
    """

    def __init__(self, limit: int):
        super().__init__(forbid_dtd=True, forbid_entities=True, forbid_external=True)
        self.limit = limit
        self.unit_bytes = 0
        self.depth = 0
        original_data = self.parser.CharacterDataHandler

        def bounded_data(data):
            self._charge(len(data.encode("utf-8")))
            original_data(data)

        self.parser.CharacterDataHandler = bounded_data

    def _charge(self, amount: int):
        self.unit_bytes += amount
        if self.unit_bytes > self.limit:
            raise SourceError("RECORD_SIZE_LIMIT")

    def _start(self, tag, attr_list):
        self.depth += 1
        if self.depth > 64:
            raise SourceError("XML_DEPTH_LIMIT")
        if self.depth == 2:
            self.unit_bytes = 0
        self._charge(len(tag.encode("utf-8")) + sum(len(v.encode("utf-8")) for v in attr_list))
        return super()._start(tag, attr_list)

    def _end(self, tag):
        result = super()._end(tag)
        self.depth -= 1
        if self.depth == 1:
            self.unit_bytes = 0
        return result


def _value(element, path: str) -> str:
    if "/@" in path:
        child_path, attr = path.rsplit("/@", 1)
        child = element.find(child_path)
        return child.get(attr, "").strip() if child is not None else ""
    child = element.find(path)
    return "".join(child.itertext()).strip() if child is not None else ""


def _date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SourceError("INVALID_SOURCE_DATE") from exc


def _validate_structure(element, paths: list[str]) -> None:
    """Reject unknown fields, attributes and duplicate singleton fields.

    Schema paths use Clark notation. Slashes inside namespace URIs must not be
    interpreted as XPath separators. Repeated names are the only list paths.
    """
    allowed: dict[tuple[str, ...], set[str]] = {(): set()}
    list_paths: set[tuple[str, ...]] = set()
    for source_path in paths:
        parts = tuple(re.findall(r"(?:\{[^}]*\})?[^/]+", source_path))
        attribute = parts[-1][1:] if parts[-1].startswith("@") else None
        if attribute:
            parts = parts[:-1]
        for length in range(1, len(parts) + 1):
            allowed.setdefault(parts[:length], set())
        if attribute:
            allowed[parts].add(attribute)
        # The fixture's BN/TRD/OTN fields are explicitly repeated name nodes.
        if parts and parts[-1].rsplit("}", 1)[-1] in ("BN", "TRD", "OTN"):
            list_paths.add(parts)

    def visit(node, prefix):
        if set(node.attrib) - allowed.get(prefix, set()):
            raise SourceError("UNKNOWN_SCHEMA_ATTRIBUTE")
        seen: set[str] = set()
        for child in node:
            child_path = (*prefix, child.tag)
            if child_path not in allowed:
                raise SourceError("UNKNOWN_SCHEMA_FIELD")
            if child.tag in seen and child_path not in list_paths:
                raise SourceError("DUPLICATE_SCHEMA_FIELD")
            seen.add(child.tag)
            visit(child, child_path)

    visit(element, ())


def _record(element, mapping: ABRMapping, member_name: str) -> dict:
    _validate_structure(element, [*mapping.fields.values(), *mapping.name_paths.values()])
    values = {key: _value(element, path) for key, path in mapping.fields.items()}
    if any(not values.get(key) for key in mapping.required_fields):
        raise SourceError("REQUIRED_FIELD_MISSING")
    abn = normalize_abn(values["abn"])
    status = values["status"]
    gst = values.get("gst_status") or "NONE"
    if gst == "NONE" and values.get("gst_date"):
        raise SourceError("GST_DATE_WITHOUT_STATUS")
    if status not in ("ACT", "CAN") or gst not in ("ACT", "CAN", "NONE"):
        raise SourceError("UNKNOWN_ENUM")
    if values["entity_type"] not in mapping.entity_classes:
        raise SourceError("UNKNOWN_ENTITY_TYPE")
    state = values.get("state") or None
    postcode = values.get("postcode") or None
    if state and state not in ("QLD", "NSW", "VIC", "TAS", "SA", "WA", "NT", "ACT", "OTHER"):
        raise SourceError("UNKNOWN_STATE")
    if postcode and (len(postcode) != 4 or not postcode.isascii() or not postcode.isdigit()):
        raise SourceError("INVALID_POSTCODE")
    names = {
        kind: ordered_names(["".join(e.itertext()).strip() for e in element.findall(path)])
        for kind, path in mapping.name_paths.items()
    }
    names["MAIN"] = ordered_names([values["main_name"]])
    canonical_names = {
        kind: [canonical_name(v) for v in names.get(kind, [])] for kind in ("BN", "MAIN", "TRD", "OTN")
    }
    name_hash = hashlib.sha256(canonical_json(canonical_names).encode()).hexdigest()
    row = {
        "abn": abn,
        "status": status,
        "status_date": _date(values["status_date"]),
        "gst_status": gst,
        "gst_date": _date(values.get("gst_date", "")),
        "entity_type": values["entity_type"],
        "entity_class": mapping.entity_classes[values["entity_type"]],
        "main_name": values["main_name"],
        "names_json": canonical_json(names),
        "state": state,
        "postcode": postcode,
        "name_hash": name_hash,
    }
    semantic = {
        k: (v.isoformat() if isinstance(v, date) else v)
        for k, v in row.items()
        if k not in ("main_name", "names_json")
    }
    row["semantic_hash"] = hashlib.sha256(canonical_json(semantic).encode()).hexdigest()
    row["source_member"] = member_name
    return row


def parse_xml(
    path: str | Path,
    output_dir: str | Path,
    *,
    mapping: ABRMapping | None = None,
    batch_size: int = 50000,
    max_record_bytes: int = 2 * 1024 * 1024,
    baseline_field_fill: dict[str, float] | None = None,
    production: bool = False,
    member_name: str | None = None,
) -> ParsedMember:
    mapping = mapping or ABRMapping.fixture()
    mapping.validate(production)
    if not 1 <= batch_size <= 50000 or max_record_bytes < 1024:
        raise ValueError("invalid batch/record bound")
    path, output_dir = Path(path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "records.parquet"
    stage = output_dir / "records.parquet.writing"
    if target.exists() or stage.exists():
        raise SourceError("ARTIFACT_ALREADY_EXISTS")
    db_path = output_dir / "uniqueness.sqlite"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE seen(abn TEXT PRIMARY KEY)")
    writer = pq.ParquetWriter(stage, SCHEMA, compression="zstd")
    count = 0
    header: dict[str, str] = {}
    batch: list[dict] = []
    filled = dict.fromkeys(mapping.required_fields, 0)
    first = last = None
    stack = []
    try:
        with path.open("rb") as stream:
            reader = _BoundedReader(stream, max_record_bytes)
            for event, element in iterparse(
                reader, events=("start", "end"), parser=_SizedParser(max_record_bytes)
            ):
                if event == "start":
                    stack.append(element)
                    if len(stack) == 1 and (
                        element.tag != mapping.root_tag
                        or element.get(mapping.root_error_attribute) not in mapping.success_values
                        or set(element.attrib) != {mapping.root_error_attribute}
                    ):
                        raise SourceError("UNKNOWN_SCHEMA_OR_TRANSFER_ERROR")
                    if element.tag == mapping.record_tag:
                        if len(stack) != 2:
                            raise SourceError("UNKNOWN_RECORD_STRUCTURE")
                        reader.record_start = max(0, reader.total - 65536)
                    continue
                if element.tag == mapping.header_tag:
                    if header or len(stack) != 2:
                        raise SourceError("DUPLICATE_OR_INVALID_HEADER")
                    header = {key: _value(element, value) for key, value in mapping.header_fields.items()}
                    _validate_structure(element, list(mapping.header_fields.values()))
                    if any(
                        not header.get(k) for k in ("sequence", "record_count", "extract_time", "generation")
                    ):
                        raise SourceError("GENERATION_UNPROVABLE")
                    if not header["sequence"].isdigit() or not header["record_count"].isdigit():
                        raise SourceError("INVALID_HEADER_COUNT")
                    try:
                        datetime.fromisoformat(header["extract_time"])
                    except ValueError as exc:
                        raise SourceError("INVALID_EXTRACT_TIME") from exc
                elif element.tag == mapping.record_tag:
                    if not header:
                        raise SourceError("HEADER_REQUIRED_BEFORE_RECORDS")
                    row = _record(element, mapping, member_name or path.name)
                    # Reader bounds stop oversized records before unbounded growth; this
                    # final check also catches a record entirely in the current buffer.
                    from xml.etree.ElementTree import tostring

                    if len(tostring(element)) > max_record_bytes:
                        raise SourceError("RECORD_SIZE_LIMIT")
                    try:
                        con.execute("INSERT INTO seen VALUES (?)", (row["abn"],))
                    except sqlite3.IntegrityError as exc:
                        raise SourceError("DUPLICATE_ABN") from exc
                    for key in filled:
                        filled[key] += int(row.get(key) is not None and row.get(key) != "")
                    first = row["abn"] if first is None else min(first, row["abn"])
                    last = row["abn"] if last is None else max(last, row["abn"])
                    count += 1
                    batch.append(row)
                    if len(batch) >= batch_size:
                        writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
                        batch.clear()
                    reader.record_start = reader.total
                elif len(stack) == 2:
                    raise SourceError("UNKNOWN_ROOT_CHILD")
                if len(stack) == 2:
                    stack[-2].remove(element)
                    element.clear()
                    reader.record_start = reader.total
                stack.pop()
        if not header or count != int(header["record_count"]):
            raise SourceError("RECORD_COUNT_MISMATCH")
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
        writer.close()
        fill = {key: value / count if count else 0.0 for key, value in filled.items()}
        if baseline_field_fill and any(
            abs(fill.get(k, 0) - v) > 0.0200000001 for k, v in baseline_field_fill.items()
        ):
            raise SourceError("FIELD_FILL_BREACH")
        with pq.ParquetFile(stage) as readback:
            if readback.metadata.num_rows != count or not readback.schema_arrow.equals(
                SCHEMA, check_metadata=True
            ):
                raise SourceError("ARTIFACT_READBACK_FAILED")
            for _ in readback.iter_batches(batch_size=batch_size):
                pass
        stage.rename(target)
        return ParsedMember(
            target, count, digest_file(path), digest_file(target), header, fill, first, last, mapping.version
        )
    except DefusedXmlException as exc:
        raise SourceError("UNSAFE_XML") from exc
    finally:
        writer.close()
        con.close()
        db_path.unlink(missing_ok=True)
        stage.unlink(missing_ok=True)
