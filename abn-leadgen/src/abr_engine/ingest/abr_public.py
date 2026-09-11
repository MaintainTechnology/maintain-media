"""Reviewed public ABN Lookup XML contract; never the non-public ABR feed.

The publisher's unmodified XSD is pinned separately. The parser makes one named
R5 compatibility allowance: an absent or completely empty GST node means unknown
registration, never active. All non-empty GST values remain strictly validated.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from lxml import etree

from abr_engine.config import ROOT

from .abr_parse import SCHEMA, ABRMapping, ParsedMember, _BoundedReader
from .common import SourceError, canonical_json, canonical_name, digest_file, normalize_abn, ordered_names

PUBLIC_PARSER_VERSION = "abr-public-v1"
XSD_SHA256 = "e19f5f991fdc3498e71faaf9f88574cab5d1d7d3cc23015c324e2f75ca45c670"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
XS = {"xs": "http://www.w3.org/2001/XMLSchema"}
MEMBER = re.compile(r"([0-9]{8})_Public([0-9]{2,4})\.xml")
PUBLIC_SCHEMA = SCHEMA.with_metadata(
    {
        b"schema_version": b"business-state-v1",
        b"parser_version": PUBLIC_PARSER_VERSION.encode(),
    }
)


@lru_cache(maxsize=1)
def _schema_contract():
    path = ROOT / "config/sources/abr-public.xsd"
    if path.is_symlink() or digest_file(path) != XSD_SHA256:
        raise SourceError("PUBLIC_SCHEMA_DIGEST_MISMATCH")
    tree = etree.parse(str(path), etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True))
    types = frozenset(
        tree.xpath(
            "//xs:simpleType[@name='EntityTypeEnum']//xs:enumeration/@value",
            namespaces=XS,
        )
    )
    # R5 deliberately accepts <GST/>; a partial/non-empty node is checked below.
    for attr in tree.xpath("//xs:complexType[@name='GSTType']//xs:attribute", namespaces=XS):
        attr.set("use", "optional")
    return etree.XMLSchema(tree), types


def public_mapping(evidence: str) -> ABRMapping:
    if not isinstance(evidence, str) or not evidence.strip():
        raise SourceError("SOURCE_MAPPING_UNAPPROVED")
    _, types = _schema_contract()
    # Conservative legal-form projection, not the tax dictionary's broad COY
    # group (which also contains partnerships and unincorporated entities).
    classes = dict.fromkeys(types, "other")
    classes.update({"PRV": "company", "PUB": "company", "IND": "individual"})
    for code in ("CMT", "CUT", "DIT", "DST", "DTT", "FHS", "FUT", "FXT", "HYT", "PQT", "PTT", "PUT", "TRT"):
        classes[code] = "trust"
    return ABRMapping(
        version="abn-lookup-public-20260911-v1",
        root_tag="Transfer",
        record_tag="ABR",
        header_tag="TransferInfo",
        fields={
            "abn": "ABN",
            "status": "ABN/@status",
            "status_date": "ABN/@ABNStatusFromDate",
            "gst_status": "GST/@status",
            "gst_date": "GST/@GSTStatusFromDate",
            "entity_type": "EntityType/EntityTypeInd",
            "main_name": "MainEntity/NonIndividualName/NonIndividualNameText",
            "state": "MainEntity/BusinessAddress/AddressDetails/State",
            "postcode": "MainEntity/BusinessAddress/AddressDetails/Postcode",
        },
        header_fields={
            "sequence": "FileSequenceNumber",
            "record_count": "RecordCount",
            "extract_time": "ExtractTime",
            "generation": "ExtractTime",
        },
        name_paths={
            kind: f"OtherEntity/NonIndividualName[@type='{kind}']/NonIndividualNameText"
            for kind in ("BN", "TRD", "OTN")
        },
        entity_classes=classes,
        success_values=("none",),
        fixture_only=False,
        approved_evidence=evidence,
        parser_version=PUBLIC_PARSER_VERSION,
        record_format=PUBLIC_PARSER_VERSION,
        required_fields=("abn", "status", "status_date", "entity_type", "main_name", "state", "postcode"),
    )


def _text(element, path):
    child = element.find(path)
    if child is None:
        return ""
    if len(child) or child.attrib:
        raise SourceError("UNKNOWN_SCALAR_SCHEMA")
    value = child.text
    return value.strip() if value else ""


def _date(raw, *, required=False):
    if not raw:
        if required:
            raise SourceError("REQUIRED_FIELD_MISSING")
        return None
    if not re.fullmatch(r"[0-9]{8}", raw):
        raise SourceError("INVALID_SOURCE_DATE")
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    except ValueError:
        raise SourceError("INVALID_SOURCE_DATE") from None


def _record(element, mapping, member_name):
    identifier = element.find("ABN")
    if identifier is None:
        raise SourceError("REQUIRED_FIELD_MISSING")
    abn = normalize_abn(identifier.text or "")
    status = identifier.get("status")
    if status not in {"ACT", "CAN"}:
        raise SourceError("UNKNOWN_ENUM")
    gst = element.find("GST")
    gst_status = gst.get("status", "") if gst is not None else ""
    gst_date = gst.get("GSTStatusFromDate", "") if gst is not None else ""
    if gst_status not in {"", "ACT", "CAN"} or bool(gst_status) != bool(gst_date):
        raise SourceError("UNKNOWN_GST_STATE")
    entity_type = _text(element, "EntityType/EntityTypeInd")
    if len(_text(element, "EntityType/EntityTypeText")) > 100:
        raise SourceError("ENTITY_TEXT_SOURCE_LENGTH_LIMIT")
    if entity_type not in mapping.entity_classes:
        raise SourceError("UNKNOWN_ENTITY_TYPE")
    company = element.find("MainEntity")
    individual = element.find("LegalEntity")
    if (company is None) == (individual is None):
        raise SourceError("INVALID_ENTITY_NAME_CHOICE")
    if (entity_type == "IND") != (individual is not None):
        raise SourceError("ENTITY_NAME_TYPE_MISMATCH")
    if company is not None:
        name_element = company.find("NonIndividualName")
        if name_element is None or name_element.get("type") != "MN":
            raise SourceError("INVALID_MAIN_NAME_TYPE")
        main_name = _text(company, "NonIndividualName/NonIndividualNameText")
        holder = company
    else:
        name_element = individual.find("IndividualName")
        if name_element is None or name_element.get("type") != "LGL":
            raise SourceError("INVALID_LEGAL_NAME_TYPE")
        parts = [
            e.text.strip()
            for e in individual.findall("IndividualName/GivenName")
            if e.text and e.text.strip()
        ]
        parts.append(_text(individual, "IndividualName/FamilyName"))
        main_name = " ".join(p for p in parts if p)
        holder = individual
    state = _text(holder, "BusinessAddress/AddressDetails/State") or None
    postcode = _text(holder, "BusinessAddress/AddressDetails/Postcode") or None
    if postcode and len(postcode) > 50:
        raise SourceError("POSTCODE_SOURCE_LENGTH_LIMIT")
    # Preserve the publisher's foreign/unknown postcode as given. Qualification
    # independently requires four ASCII digits and the approved AU geography.
    names: dict[str, list[str]] = {kind: [] for kind in ("BN", "TRD", "OTN")}
    for other in element.findall("OtherEntity/NonIndividualName"):
        kind = other.get("type")
        if kind not in names:
            raise SourceError("UNKNOWN_OTHER_NAME_TYPE")
        names[kind].append(_text(other, "NonIndividualNameText"))
    names = {kind: ordered_names(values) for kind, values in names.items()}
    names["MAIN"] = ordered_names([main_name])
    if any(len(value) > 200 for values in names.values() for value in values):
        raise SourceError("NAME_SOURCE_LENGTH_LIMIT")
    canonical_names = {
        kind: [canonical_name(v) for v in names.get(kind, [])] for kind in ("BN", "MAIN", "TRD", "OTN")
    }
    row = {
        "abn": abn,
        "status": status,
        "status_date": _date(identifier.get("ABNStatusFromDate", ""), required=True),
        "gst_status": gst_status or "NONE",
        "gst_date": _date(gst_date),
        "entity_type": entity_type,
        "entity_class": mapping.entity_classes[entity_type],
        "main_name": main_name,
        "names_json": canonical_json(names),
        "state": state,
        "postcode": postcode,
        "name_hash": hashlib.sha256(canonical_json(canonical_names).encode()).hexdigest(),
    }
    semantic = {
        k: v.isoformat() if isinstance(v, date) else v
        for k, v in row.items()
        if k not in ("main_name", "names_json")
    }
    row["semantic_hash"] = hashlib.sha256(canonical_json(semantic).encode()).hexdigest()
    row["source_member"] = member_name
    return row


class _PublicReader(_BoundedReader):
    tail = b""

    def read(self, size=-1):
        data = super().read(size)
        scan = self.tail + data
        if b"<!DOCTYPE" in scan or b"<!ENTITY" in scan:
            raise SourceError("UNSAFE_XML")
        self.tail = scan[-16:]
        return data


def parse_public_xml(
    path,
    output_dir,
    *,
    mapping,
    batch_size=50000,
    max_record_bytes=2 * 1024 * 1024,
    baseline_field_fill=None,
    member_name=None,
    authority=None,
    progress=None,
):
    mapping.validate(True)
    if not 1 <= batch_size <= 50000 or not 1024 <= max_record_bytes <= 2 * 1024 * 1024:
        raise ValueError("invalid public parser bounds")
    path, output_dir = Path(path), Path(output_dir)
    member_name = member_name or path.name
    match = MEMBER.fullmatch(member_name)
    if not match:
        raise SourceError("PUBLIC_MEMBER_NAME_UNREVIEWED")
    try:
        publication_date = _date(match[1], required=True)
    except SourceError:
        raise SourceError("PUBLIC_MEMBER_DATE_INVALID") from None
    schema, _ = _schema_contract()
    output_dir.mkdir(parents=True, exist_ok=True)
    target, stage, unique = (
        output_dir / name for name in ("records.parquet", "records.parquet.writing", "uniqueness.sqlite")
    )
    if any(p.exists() or p.is_symlink() for p in (target, stage, unique)):
        raise SourceError("ARTIFACT_ALREADY_EXISTS")
    con = sqlite3.connect(unique)
    con.execute("PRAGMA cache_size=-8192")
    con.execute("CREATE TABLE seen(abn TEXT PRIMARY KEY) WITHOUT ROWID")
    writer = pq.ParquetWriter(stage, PUBLIC_SCHEMA, compression="zstd")
    count = 0
    header: dict[str, str] = {}
    batch: list[dict] = []
    filled = dict.fromkeys(mapping.required_fields, 0)
    first = last = None
    try:
        if authority is not None:
            authority()
        with path.open("rb") as stream:
            reader = _PublicReader(stream, max_record_bytes)
            context = etree.iterparse(
                reader,
                events=("start", "end"),
                tag=("Transfer", "TransferInfo", "ABR"),
                resolve_entities=False,
                load_dtd=False,
                no_network=True,
                huge_tree=False,
                recover=False,
                schema=schema,
            )
            for event, element in context:
                if event == "start":
                    if element.tag == "Transfer":
                        if element.getroottree().docinfo.doctype:
                            raise SourceError("UNSAFE_XML")
                        if (
                            element.get("error") != "none"
                            or element.get(XSI + "noNamespaceSchemaLocation") != "BulkExtract.xsd"
                            or set(element.attrib) != {"error", XSI + "noNamespaceSchemaLocation"}
                        ):
                            raise SourceError("UNKNOWN_SCHEMA_OR_TRANSFER_ERROR")
                    continue
                if element.tag == "TransferInfo":
                    if header:
                        raise SourceError("DUPLICATE_OR_INVALID_HEADER")
                    header = {key: _text(element, value) for key, value in mapping.header_fields.items()}
                    if (
                        not header["sequence"].isascii()
                        or not header["sequence"].isdigit()
                        or int(header["sequence"]) != int(match[2])
                    ):
                        raise SourceError("PUBLIC_MEMBER_SEQUENCE_MISMATCH")
                    if not header["record_count"].isascii() or not header["record_count"].isdigit():
                        raise SourceError("INVALID_HEADER_COUNT")
                    try:
                        extracted = datetime.fromisoformat(header["extract_time"])
                    except ValueError:
                        raise SourceError("INVALID_EXTRACT_TIME") from None
                    if extracted.date() != publication_date:
                        raise SourceError("PUBLIC_MEMBER_DATE_MISMATCH")
                    # Derived evidence label, NOT an asserted publisher generation UUID.
                    header["generation"] = match[1] + ":" + header["extract_time"]
                    header["generation_basis"] = "member_date_and_exact_transfer_extract_time"
                    header["extract_timezone"] = (
                        "absent" if extracted.tzinfo is None else "publisher_supplied"
                    )
                elif element.tag == "ABR":
                    if not header:
                        raise SourceError("HEADER_REQUIRED_BEFORE_RECORDS")
                    if len(etree.tostring(element, with_tail=False)) > max_record_bytes:
                        raise SourceError("RECORD_SIZE_LIMIT")
                    row = _record(element, mapping, member_name)
                    try:
                        con.execute("INSERT INTO seen VALUES (?)", (row["abn"],))
                    except sqlite3.IntegrityError:
                        raise SourceError("DUPLICATE_ABN") from None
                    count += 1
                    first = row["abn"] if first is None else min(first, row["abn"])
                    last = row["abn"] if last is None else max(last, row["abn"])
                    for key in filled:
                        filled[key] += int(row[key] is not None and row[key] != "")
                    batch.append(row)
                    if len(batch) >= batch_size:
                        if authority is not None:
                            authority()
                        writer.write_table(pa.Table.from_pylist(batch, schema=PUBLIC_SCHEMA))
                        batch.clear()
                        if progress is not None:
                            progress({"phase": "parsing", "record_count": count})
                if element.tag != "Transfer":
                    element.clear()
                    while element.getprevious() is not None:
                        del element.getparent()[0]
                    reader.record_start = reader.total
        if not header or count != int(header["record_count"]):
            raise SourceError("RECORD_COUNT_MISMATCH")
        if authority is not None:
            authority()
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=PUBLIC_SCHEMA))
        writer.close()
        fill = {key: value / count if count else 0.0 for key, value in filled.items()}
        if baseline_field_fill and any(
            abs(fill.get(k, 0) - v) > 0.0200000001 for k, v in baseline_field_fill.items()
        ):
            raise SourceError("FIELD_FILL_BREACH")
        with pq.ParquetFile(stage) as readback:
            if readback.metadata.num_rows != count or not readback.schema_arrow.equals(
                PUBLIC_SCHEMA, check_metadata=True
            ):
                raise SourceError("ARTIFACT_READBACK_FAILED")
            for _ in readback.iter_batches(batch_size=batch_size):
                if authority is not None:
                    authority()
        if progress is not None:
            progress({"phase": "parsed", "record_count": count})
        with stage.open("r+b") as durable:
            os.fsync(durable.fileno())
        stage.rename(target)
        if os.name == "posix":
            directory_fd = os.open(output_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return ParsedMember(
            target, count, digest_file(path), digest_file(target), header, fill, first, last, mapping.version
        )
    except (etree.XMLSyntaxError, etree.XMLSchemaError):
        # Schema errors can include names/ABNs; expose only the fixed reason.
        raise SourceError("PUBLIC_XML_SCHEMA_INVALID") from None
    finally:
        writer.close()
        con.close()
        unique.unlink(missing_ok=True)
        stage.unlink(missing_ok=True)
