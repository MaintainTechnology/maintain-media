"""Synthetic record values, actual separately pinned publisher XML structure."""

import json
from datetime import date

import pyarrow.parquet as pq
import pytest

from abr_engine.ingest.abr_parse import parse_xml
from abr_engine.ingest.abr_public import PUBLIC_PARSER_VERSION, public_mapping
from abr_engine.ingest.common import SourceError


def record(
    *,
    abn="51824753556",
    gst='<GST status="ACT" GSTStatusFromDate="20200101"/>',
    individual=False,
    postcode="4000",
    state="QLD",
):
    name = (
        '<LegalEntity><IndividualName type="LGL"><GivenName>Fixture</GivenName>'
        "<GivenName>Only</GivenName><FamilyName>Person</FamilyName></IndividualName>"
        if individual
        else '<MainEntity><NonIndividualName type="MN"><NonIndividualNameText>Fixture &amp; Test Pty Ltd</NonIndividualNameText></NonIndividualName>'
    )
    return (
        f'<ABR recordLastUpdatedDate="20260909" replaced="N"><ABN status="ACT" ABNStatusFromDate="20180131">{abn}</ABN>'
        f"<EntityType><EntityTypeInd>{'IND' if individual else 'PRV'}</EntityTypeInd><EntityTypeText>Fixture entity</EntityTypeText></EntityType>"
        + name
        + f"<BusinessAddress><AddressDetails><State>{state}</State><Postcode>{postcode}</Postcode></AddressDetails></BusinessAddress>"
        + ("</LegalEntity>" if individual else "</MainEntity>")
        + gst
        + '<OtherEntity><NonIndividualName type="BN"><NonIndividualNameText>Fixture Plumbing</NonIndividualNameText></NonIndividualName></OtherEntity>'
        '<OtherEntity><NonIndividualName type="OTN"><NonIndividualNameText>Old Fixture</NonIndividualNameText></NonIndividualName></OtherEntity></ABR>'
    )


def document(body=None, *, count=1, sequence=1, extracted="2026-09-09T12:20:57"):
    return (
        '<?xml version="1.0"?><Transfer error="none" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="BulkExtract.xsd"><TransferInfo>'
        f"<FileSequenceNumber>{sequence}</FileSequenceNumber><RecordCount>{count}</RecordCount>"
        f"<ExtractTime>{extracted}</ExtractTime></TransferInfo>"
        + (record() if body is None else body)
        + "</Transfer>"
    )


def parse(tmp_path, xml, **kwargs):
    path = tmp_path / "20260909_Public01.xml"
    path.write_text(xml, encoding="utf-8")
    return parse_xml(
        path,
        tmp_path / "parsed",
        mapping=public_mapping("synthetic-source-contract-test"),
        production=True,
        **kwargs,
    )


def test_actual_structure_maps_values_and_distinct_parser_metadata(tmp_path):
    result = parse(tmp_path, document())
    row = pq.read_table(result.parquet_path).to_pylist()[0]
    assert row["main_name"] == "Fixture & Test Pty Ltd"
    assert row["status_date"] == date(2018, 1, 31) and row["gst_date"] == date(2020, 1, 1)
    assert row["entity_class"] == "company"
    assert json.loads(row["names_json"]) == {
        "BN": ["Fixture Plumbing"],
        "TRD": [],
        "OTN": ["Old Fixture"],
        "MAIN": ["Fixture & Test Pty Ltd"],
    }
    assert pq.read_schema(result.parquet_path).metadata[b"parser_version"] == PUBLIC_PARSER_VERSION.encode()
    assert result.header["generation"] == "20260909:2026-09-09T12:20:57"
    assert result.header["extract_timezone"] == "absent"


@pytest.mark.parametrize("gst", ["", "<GST/>", '<GST status="" GSTStatusFromDate=""/>'])
def test_empty_gst_is_not_active(tmp_path, gst):
    result = parse(tmp_path, document(record(gst=gst)))
    row = pq.read_table(result.parquet_path).to_pylist()[0]
    assert row["gst_status"] == "NONE" and row["gst_date"] is None


def test_individual_legal_name_and_unknown_geography_are_preserved(tmp_path):
    result = parse(tmp_path, document(record(individual=True, postcode="FOREIGN-12345", state="")))
    row = pq.read_table(result.parquet_path).to_pylist()[0]
    assert row["main_name"] == "Fixture Only Person" and row["entity_class"] == "individual"
    assert row["state"] is None and row["postcode"] == "FOREIGN-12345"


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.replace('error="none"', 'error="false"'),
        lambda x: x.replace("BulkExtract.xsd", "https://evil.example/schema.xsd"),
        lambda x: x.replace("<RecordCount>1</RecordCount>", "<RecordCount>2</RecordCount>"),
        lambda x: x.replace("<FileSequenceNumber>1", "<FileSequenceNumber>2"),
        lambda x: x.replace("2026-09-09T12:20:57", "2026-09-10T12:20:57"),
        lambda x: x.replace("<EntityTypeInd>PRV", "<EntityTypeInd>ZZZ"),
        lambda x: x.replace('status="ACT" GSTStatusFromDate', 'status="MAYBE" GSTStatusFromDate'),
        lambda x: x.replace(' GSTStatusFromDate="20200101"', ""),
        lambda x: x.replace("<State>QLD</State>", "<State>ZZZ</State>"),
        lambda x: x.replace("<OtherEntity>", "<Unexpected/> <OtherEntity>", 1),
        lambda x: x.replace("51824753556", "11111111111"),
        lambda x: x.replace("<ABR recordLastUpdatedDate", '<ABR malicious="true" recordLastUpdatedDate'),
        lambda x: x.replace(
            '<?xml version="1.0"?>',
            '<?xml version="1.0"?><!DOCTYPE Transfer [<!ENTITY x SYSTEM "file:///etc/passwd">]>',
        ),
    ],
)
def test_rejects_unreviewed_or_inconsistent_input_without_promoted_output(tmp_path, change):
    with pytest.raises(SourceError):
        parse(tmp_path, change(document()))
    assert not (tmp_path / "parsed" / "records.parquet").exists()


def test_duplicate_abn_refused_and_empty_complete_file_allowed(tmp_path):
    with pytest.raises(SourceError, match="DUPLICATE_ABN"):
        parse(tmp_path, document(record() + record(), count=2))


def test_empty_complete_file_has_no_records(tmp_path):
    result = parse(tmp_path, document("", count=0))
    assert result.row_count == 0


def test_authority_revocation_interrupts_batch_before_promotion(tmp_path):
    calls = []

    def authority():
        calls.append(1)
        if len(calls) == 2:
            raise SourceError("REVOKED_TEST_AUTHORITY")

    with pytest.raises(SourceError, match="REVOKED_TEST_AUTHORITY"):
        parse(tmp_path, document(), batch_size=1, authority=authority)
    assert len(calls) == 2 and not (tmp_path / "parsed" / "records.parquet").exists()


def test_progress_and_field_fill_check(tmp_path):
    progress = []
    result = parse(tmp_path, document(), batch_size=1, progress=progress.append)
    assert result.field_fill["postcode"] == 1 and [x["phase"] for x in progress] == ["parsing", "parsed"]


def test_oversized_record_and_missing_approval_block(tmp_path):
    with pytest.raises(SourceError):
        parse(tmp_path, document().replace("Fixture Plumbing", "x" * 10000), max_record_bytes=1024)
    with pytest.raises(SourceError, match="SOURCE_MAPPING_UNAPPROVED"):
        public_mapping("")


def test_utf16_doctype_is_rejected_structurally(tmp_path):
    path = tmp_path / "20260909_Public01.xml"
    xml = document().replace(
        '<?xml version="1.0"?>', '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE Transfer>'
    )
    path.write_bytes(xml.encode("utf-16"))
    with pytest.raises(SourceError, match="UNSAFE_XML"):
        parse_xml(path, tmp_path / "out", mapping=public_mapping("test"), production=True)


def test_multiname_record_in_one_buffer_still_obeys_configured_ceiling(tmp_path):
    more = "".join(
        '<OtherEntity><NonIndividualName type="BN"><NonIndividualNameText>Fixture '
        + str(i)
        + "</NonIndividualNameText></NonIndividualName></OtherEntity>"
        for i in range(40)
    )
    with pytest.raises(SourceError, match="RECORD_SIZE_LIMIT"):
        parse(tmp_path, document(record().replace("</ABR>", more + "</ABR>")), max_record_bytes=1024)


@pytest.mark.parametrize("individual", [True, False])
def test_entity_code_and_legal_name_choice_must_agree(tmp_path, individual):
    body = record(individual=individual)
    body = (
        body.replace("<EntityTypeInd>IND", "<EntityTypeInd>PRV")
        if individual
        else body.replace("<EntityTypeInd>PRV", "<EntityTypeInd>IND")
    )
    with pytest.raises(SourceError, match="ENTITY_NAME_TYPE_MISMATCH"):
        parse(tmp_path, document(body))


def test_public_quality_nullable_fields_require_actual_and_declared_contract(tmp_path):
    from abr_engine.ingest.quality import parquet_fill, validate_fill

    result = parse(tmp_path, document(record(state="", postcode="")))
    actual = parquet_fill([result.parquet_path])
    declared = {
        "parser_version": "abr-public-v1",
        "mapping_version": result.mapping_version,
        "field_fill_weighted": result.field_fill,
        "source_rows": 1,
    }
    validate_fill(actual, declared)
    with pytest.raises(SourceError, match="REQUIRED_FIELD_MISSING"):
        validate_fill(actual, {**declared, "parser_version": "fixture-abr-v1"})
    with pytest.raises(SourceError, match="REQUIRED_FIELD_MISSING"):
        validate_fill({k: v for k, v in actual.items() if k != "source_contract"}, declared)
    previous = {**actual, "field_fill_weighted": {**actual["field_fill_weighted"], "state": 1}}
    with pytest.raises(SourceError, match="FIELD_FILL_BREACH"):
        validate_fill(actual, declared, previous)


def test_field_fill_drift_holds_even_nullable_publisher_fields(tmp_path):
    with pytest.raises(SourceError, match="FIELD_FILL_BREACH"):
        parse(
            tmp_path,
            document(record(state="", postcode="")),
            baseline_field_fill={"state": 1.0, "postcode": 1.0},
        )


@pytest.mark.parametrize("field", ["Postcode", "EntityTypeText"])
@pytest.mark.parametrize("injection", ["child", "attribute"])
def test_xsd_anytype_scalars_do_not_silently_hide_unreviewed_values(tmp_path, field, injection):
    xml = document()
    xml = (
        xml.replace("</" + field + ">", "<Unexpected>ignored</Unexpected></" + field + ">")
        if injection == "child"
        else xml.replace("<" + field + ">", "<" + field + ' unknown="ignored">')
    )
    with pytest.raises(SourceError, match="UNKNOWN_SCALAR_SCHEMA"):
        parse(tmp_path, xml)
