"""Official field/enum contract, entirely synthetic licence rows and no network."""

import csv
import io
from dataclasses import replace

import pyarrow.parquet as pq
import pytest

from abr_engine.ingest.common import SourceError
from abr_engine.ingest.qbcc import (
    PUBLISHER_CATEGORIES,
    QBCCMapping,
    parse_qbcc,
    qbcc_events,
    write_qbcc_parquet,
)
from abr_engine.qualify.abr import qualify_qbcc


def row(**changes):
    return {
        "licence_number": "fixture-123",
        "licensee_name": "Synthetic Example Builder",
        "acn": "000000000",
        "abn": "",
        "original_address": "1 Example Street QLD 4000",
        "licence_type_description": "Trade Contractor",
        "licence_type_code": "T",
        "financial_category_description": "Category 1",
        "financial_category": "1",
        "licence_grade": "Contractor",
        "class_type": "Builder",
        **changes,
    }


def source(tmp_path, rows, *, headers=None):
    columns = QBCCMapping.publisher().columns
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers or columns.values())
    writer.writerows([[record[key] for key in columns] for record in rows])
    path = tmp_path / "synthetic-publisher-schema.csv"
    path.write_bytes(b"\xff\xfe" + stream.getvalue().encode("utf-16-le"))
    return path


def parse(path):
    return parse_qbcc(path, mapping=QBCCMapping.publisher())


def test_real_schema_does_not_invent_active_status_or_company_and_roundtrips(tmp_path):
    result = parse(source(tmp_path, [row(), row(class_type="Carpenter")]))
    assert result.row_count == 2 and len(result.records) == 1
    record = result.records[0]
    assert record["status"] == "UNKNOWN"
    assert record["entity_class"] == "unknown"  # Even with ACN present.
    assert record["licence_review_required"] is True
    assert record["abn"] is None
    assert record["class_types"] == ["Builder", "Carpenter"]
    assert record["financial_category"] == "1"
    assert record["financial_category_description"] == "Category 1"
    assert not qualify_qbcc(record, "icp_backlog").enrichment_eligible
    assert list(qbcc_events(None, result)) == []
    stored = pq.read_table(write_qbcc_parquet(result, tmp_path / "source.parquet")).to_pylist()[0]
    assert stored == record


def test_class_related_licence_types_and_grades_collapse_deterministically(tmp_path):
    records = [
        row(),
        row(
            licence_type_code="B",
            licence_type_description="Builder",
            licence_grade="Nominee",
            class_type="Carpenter",
        ),
    ]
    first = parse(source(tmp_path, records)).records[0]
    second = parse(source(tmp_path, list(reversed(records)))).records[0]
    assert first == second
    assert first["licence_grades"] == ["Contractor", "Nominee"]
    assert len(first["licence_types"]) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"financial_category": "2", "financial_category_description": "Category 2"},
        {"original_address": "2 Different Street NSW 2450"},
        {"abn": "51824753556"},
        {"acn": "999999999"},
    ],
)
def test_conflicting_business_identity_is_quarantined(tmp_path, changes):
    result = parse(source(tmp_path, [row(), row(**changes)]))
    assert not result.records
    assert "CONFLICTING_LICENCE_FIELDS" in result.quarantined[0]["reason_codes"]


@pytest.mark.parametrize("category,description", PUBLISHER_CATEGORIES.items())
def test_observed_category_pairs_are_preserved_not_reclassified(tmp_path, category, description):
    result = parse(
        source(tmp_path, [row(financial_category=category, financial_category_description=description)])
    )
    assert result.records[0]["financial_category"] == category
    assert not result.quarantined
    assert result.category_counts == {category: 1}


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"financial_category": "FUTURE"}, "UNKNOWN_FINANCIAL_CATEGORY"),
        ({"financial_category_description": "Category 2"}, "FINANCIAL_CATEGORY_DESCRIPTION_MISMATCH"),
        ({"abn": "12345678901"}, "INVALID_ABN"),
    ],
)
def test_unknown_enum_mismatch_and_invalid_abn_fail_closed(tmp_path, changes, reason):
    result = parse(source(tmp_path, [row(**changes)]))
    assert not result.records and reason in result.quarantined[0]["reason_codes"]


def test_schema_version_and_production_mapping_are_explicit(tmp_path):
    path = source(tmp_path, [row()])
    with pytest.raises(SourceError, match="QBCC_HEADER_MISMATCH"):
        parse_qbcc(path)  # No automatic switch from the synthetic contract.
    with pytest.raises(SourceError, match="SOURCE_MAPPING_UNAPPROVED"):
        parse_qbcc(path, mapping=QBCCMapping.publisher(), production=True)
    changed = replace(QBCCMapping.publisher(), columns={"licence_number": "Other"})
    with pytest.raises(SourceError, match="QBCC_MAPPING_VERSION_MISMATCH"):
        parse_qbcc(path, mapping=changed)


def test_publisher_reordered_header_encoding_and_bad_address_remain_strict(tmp_path):
    headers = list(QBCCMapping.publisher().columns.values())
    path = source(tmp_path, [row()], headers=list(reversed(headers)))
    with pytest.raises(SourceError, match="HEADER_MISMATCH"):
        parse(path)
    path.write_text(",".join(headers), encoding="utf-8")
    with pytest.raises(SourceError, match="BOM_REQUIRED"):
        parse(path)
    result = parse(source(tmp_path, [row(original_address="Street QLD 4000 extra")]))
    assert result.records[0]["geography_review_required"] is True
