from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pyarrow.parquet as pq
import pytest

from abr_engine.classify.rules import classify, load_rules
from abr_engine.diff.events import diff_snapshots, iter_events
from abr_engine.ingest.abr_download import ArchiveResource, download_resource, ingest_archives
from abr_engine.ingest.abr_parse import ABRMapping, parse_xml
from abr_engine.ingest.common import SourceError, canonical_json, normalize_abn
from abr_engine.ingest.qbcc import parse_qbcc, qbcc_events, write_qbcc_parquet
from abr_engine.ingest.snapshots import content_identity
from abr_engine.qualify.abr import completed_months, qualify_abr, target_geography
from abr_engine.qualify.queue import QueueItem, can_reactivate, score, select_worklist


def abn(index=0):
    found = []
    for number in range(10000000000, 10000010000):
        try:
            found.append(normalize_abn(str(number)))
        except SourceError:
            continue
        if len(found) > index:
            return found[index]
    raise AssertionError("ABN fixture generation failed")


def record(
    index=0, *, status="ACT", gst="NONE", name="Example &amp; Sons", status_date="2024-01-31", names=""
):
    gst_xml = "<GST/>" if gst == "NONE" else f'<GST status="{gst}" date="2026-09-01"/>'
    return (
        f'<ABR><ABN date="{status_date}" status="{status}">{abn(index)}</ABN>{gst_xml}'
        f"<EntityType>COMPANY</EntityType><MainName>{name}</MainName><State>QLD</State>"
        f"<Postcode>4000</Postcode><Names>{names}</Names></ABR>"
    )


def xml(records, *, generation="fixture-1", sequence=1, count=None, namespace=""):
    ns = f' xmlns="{namespace}"' if namespace else ""
    return (
        f'<Transfer error="false"{ns}><TransferInfo><FileSequenceNumber>{sequence}</FileSequenceNumber>'
        f"<RecordCount>{len(records) if count is None else count}</RecordCount>"
        f"<ExtractTime>2026-09-08T00:00:00</ExtractTime><FixtureGeneration>{generation}</FixtureGeneration>"
        f"</TransferInfo>{''.join(records)}</Transfer>"
    )


def parsed(tmp_path, name, content, **kwargs):
    path = tmp_path / f"{name}.xml"
    path.write_text(content, encoding="utf-8")
    return parse_xml(path, tmp_path / name, **kwargs)


def test_streaming_namespace_entities_empty_gst_and_readback(tmp_path):
    result = parsed(
        tmp_path,
        "namespaced",
        xml([record(names="<BN>Z Plumbing</BN><BN>A &#38; B Plumbing</BN>")], namespace="urn:fixture"),
        mapping=ABRMapping.fixture("urn:fixture"),
        batch_size=1,
    )
    row = pq.read_table(result.parquet_path).to_pylist()[0]
    assert row["main_name"] == "Example & Sons"
    assert row["gst_status"] == "NONE"
    assert json.loads(row["names_json"])["BN"] == ["A & B Plumbing", "Z Plumbing"]
    assert result.row_count == 1
    assert result.header["extract_time"] == "2026-09-08T00:00:00"  # no invented timezone
    assert pq.ParquetFile(result.parquet_path).metadata.row_group(0).column(0).compression == "ZSTD"


@pytest.mark.parametrize(
    "content,code",
    [
        (xml([record()], count=2), "RECORD_COUNT_MISMATCH"),
        (xml([record(), record()]), "DUPLICATE_ABN"),
        (xml([record(status="UNKNOWN")]), "UNKNOWN_ENUM"),
        (xml([record()]).replace(abn(), "12345678901"), "INVALID_ABN"),
        (xml([record()]).replace("<State>QLD</State>", "<State/>"), "REQUIRED_FIELD_MISSING"),
        (xml([record()]).replace("<EntityType>COMPANY", "<EntityType>NEW_ENUM"), "UNKNOWN_ENTITY_TYPE"),
        (xml([record()], generation=""), "GENERATION_UNPROVABLE"),
        ('<!DOCTYPE Transfer [<!ENTITY e SYSTEM "file:///etc/passwd">]>' + xml([record()]), "UNSAFE_XML"),
        ("<!DOCTYPE Transfer>" + xml([record()]), "UNSAFE_XML"),
    ],
)
def test_parser_rejects_invalid_sources(tmp_path, content, code):
    with pytest.raises(SourceError, match=code):
        parsed(tmp_path, "invalid", content)
    assert not (tmp_path / "invalid" / "records.parquet").exists()


def test_large_record_and_canary_hold(tmp_path):
    with pytest.raises(SourceError, match="RECORD_SIZE_LIMIT"):
        parsed(tmp_path, "large", xml([record(name="X" * 200000)]), max_record_bytes=1024)
    with pytest.raises(SourceError, match="FIELD_FILL_BREACH"):
        parsed(tmp_path, "fill", xml([record()]), baseline_field_fill={"state": 0.95})


@pytest.mark.parametrize(
    "content,code",
    [
        (xml([record()]).replace("<MainName>", "<MainName unexpected='x'>"), "UNKNOWN_SCHEMA_ATTRIBUTE"),
        (xml([record()]).replace("</ABR>", "<Unexpected>new</Unexpected></ABR>"), "UNKNOWN_SCHEMA_FIELD"),
        (xml([record()]).replace("</ABR>", "<State>NSW</State></ABR>"), "DUPLICATE_SCHEMA_FIELD"),
        (xml([record()]).replace("2026-09-08T00:00:00", "unknown"), "INVALID_EXTRACT_TIME"),
        (xml([record()]).replace("<GST/>", '<GST date="2026-09-01"/>'), "GST_DATE_WITHOUT_STATUS"),
    ],
)
def test_schema_drift_is_held(tmp_path, content, code):
    with pytest.raises(SourceError, match=code):
        parsed(tmp_path, "schema", content)


def test_header_text_depth_and_utf16_doctype_bounded(tmp_path):
    with pytest.raises(SourceError, match="RECORD_SIZE_LIMIT"):
        parsed(tmp_path, "huge-header", xml([record()], generation="X" * 300000), max_record_bytes=1024)
    with pytest.raises(SourceError, match="XML_DEPTH_LIMIT"):
        parsed(tmp_path, "deep", xml(["<ABR>" + "<X>" * 80 + "</X>" * 80 + "</ABR>"]))
    path = tmp_path / "utf16.xml"
    path.write_bytes(
        ('<?xml version="1.0" encoding="utf-16"?><!DOCTYPE Transfer>' + xml([record()])).encode("utf-16")
    )
    with pytest.raises(SourceError, match="UNSAFE_XML"):
        parse_xml(path, tmp_path / "utf16")


def test_production_fixture_mapping_blocked(tmp_path):
    with pytest.raises(SourceError, match="SOURCE_MAPPING_UNAPPROVED"):
        parsed(tmp_path, "live", xml([record()]), production=True)


def test_exact_content_projection_and_compression_independence():
    parts = [
        {
            "part_label": "a",
            "members": [{"member_label": "x", "uncompressed_sha256": "a" * 64}],
            "etag": "ignore",
        }
    ]
    expected = hashlib.sha256(
        canonical_json(
            {
                "identity_version": 1,
                "parts": [
                    {"part_label": "a", "members": [{"member_label": "x", "uncompressed_sha256": "a" * 64}]}
                ],
            }
        ).encode()
    ).hexdigest()
    assert content_identity(parts) == expected
    parts[0]["etag"] = "different"
    assert content_identity(parts) == expected
    with pytest.raises(SourceError, match="DUPLICATE_PART_LABEL"):
        content_identity(parts * 2)


def archive(tmp_path, name, content, *, compression=zipfile.ZIP_DEFLATED, member="part.xml"):
    path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(path, "w", compression=compression) as z:
        z.writestr(member, content)
    return ArchiveResource(name, "part", path, {member: "stable-member"})


def ingest(tmp_path, resource, directory="stage", **kwargs):
    inventory = [{"resource_id": resource.resource_id, "part_label": resource.part_label}]
    return ingest_archives(
        [resource],
        tmp_path / directory,
        mapping=ABRMapping.fixture(),
        inventory_before=inventory,
        inventory_after=kwargs.pop("inventory_after", inventory),
        required_parts={"part"},
        expected_sequences={1},
        **kwargs,
    )


def test_archives_recompressed_same_identity(tmp_path):
    a = archive(tmp_path, "a", xml([record()]))
    b = archive(tmp_path, "b", xml([record()]), compression=zipfile.ZIP_STORED)
    pa, pb = ingest(tmp_path, a, "a-stage"), ingest(tmp_path, b, "b-stage")
    assert pa.content_digest == pb.content_digest
    assert pa.manifest["resources"][0]["download_sha256"] != pb.manifest["resources"][0]["download_sha256"]


@pytest.mark.parametrize("member", ["../part.xml", "/part.xml", "nested.zip", "C:part.xml", "dir\\part.xml"])
def test_unsafe_archive_member(tmp_path, member):
    with pytest.raises(SourceError, match="UNSAFE_ARCHIVE_MEMBER|MEMBER_INVENTORY_MISMATCH"):
        ingest(tmp_path, archive(tmp_path, "bad", xml([record()]), member=member))


def test_inventory_change_and_generation_mismatch(tmp_path):
    a = archive(tmp_path, "a", xml([record()]))
    with pytest.raises(SourceError, match="INVENTORY_CHANGED"):
        ingest(tmp_path, a, inventory_after=[{"resource_id": "changed", "part_label": "part"}])
    b = archive(tmp_path, "b", xml([record(1)], generation="other", sequence=2), member="second.xml")
    b = replace(b, part_label="second")
    inventory = [{"resource_id": r.resource_id, "part_label": r.part_label} for r in [a, b]]
    with pytest.raises(SourceError, match="GENERATION_UNPROVABLE"):
        ingest_archives(
            [a, b],
            tmp_path / "mixed",
            mapping=ABRMapping.fixture(),
            inventory_before=inventory,
            inventory_after=inventory,
            required_parts={"part", "second"},
            expected_sequences={1, 2},
        )


def test_full_diff_baseline_multi_events_disappearance_and_recurrence(tmp_path):
    a = parsed(tmp_path, "a", xml([record(0), record(1), record(2, status="CAN")]))
    b = parsed(tmp_path, "b", xml([record(0, gst="ACT", name="Renamed"), record(2), record(3, gst="ACT")]))
    baseline = diff_snapshots(
        None,
        [a.parquet_path],
        tmp_path / "baseline.parquet",
        snapshot_id=str(uuid4()),
        observed_at=datetime.now(UTC),
    )
    assert baseline.event_count == 0
    sid = str(uuid4())
    result = diff_snapshots(
        [a.parquet_path],
        [b.parquet_path],
        tmp_path / "diff.parquet",
        snapshot_id=sid,
        observed_at=datetime.now(UTC),
    )
    events = list(iter_events(result.path))
    assert {(r["abn"], r["event_type"]) for r in events} == {
        (abn(0), "gst_registered"),
        (abn(0), "name_changed"),
        (abn(1), "abn_disappeared"),
        (abn(2), "abn_reactivated"),
        (abn(3), "abn_new"),
    }
    assert result.event_count == 5
    assert next(e for e in events if e["event_type"] == "abn_disappeared")["quarantined"]
    retry = diff_snapshots(
        [a.parquet_path],
        [b.parquet_path],
        tmp_path / "retry.parquet",
        snapshot_id=sid,
        observed_at=datetime.now(UTC),
    )
    assert [r["event_id"] for r in iter_events(retry.path)] == [r["event_id"] for r in events]
    recurrence = diff_snapshots(
        [b.parquet_path],
        [a.parquet_path],
        tmp_path / "recurrence.parquet",
        snapshot_id=str(uuid4()),
        observed_at=datetime.now(UTC),
    )
    assert recurrence.event_count > 0
    same = diff_snapshots(
        [a.parquet_path],
        [a.parquet_path],
        tmp_path / "same.parquet",
        snapshot_id=str(uuid4()),
        observed_at=datetime.now(UTC),
    )
    assert same.event_count == 0


def test_name_reordering_semantic_noop(tmp_path):
    a = parsed(tmp_path, "a", xml([record(names="<BN>Z Ltd</BN><BN>A Ltd</BN>")]))
    b = parsed(tmp_path, "b", xml([record(names="<BN>A Ltd</BN><BN>Z Ltd</BN>")]))
    result = diff_snapshots(
        [a.parquet_path],
        [b.parquet_path],
        tmp_path / "out.parquet",
        snapshot_id=str(uuid4()),
        observed_at=datetime.now(UTC),
    )
    assert result.event_count == 0


def qbcc_file(tmp_path, rows, name="qbcc.csv"):
    import csv
    import io

    from abr_engine.ingest.qbcc import QBCCMapping

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(QBCCMapping.fixture().columns.values())
    writer.writerows(rows)
    path = tmp_path / name
    path.write_bytes(b"\xff\xfe" + stream.getvalue().encode("utf-16-le"))
    return path


def test_qbcc_collapse_missing_abn_conflict_quarantine_and_backlog(tmp_path):
    result = parse_qbcc(
        qbcc_file(
            tmp_path,
            [
                [
                    "1",
                    "Fixture Builder",
                    "",
                    "1",
                    "1 Example Street QLD 4000",
                    "Builder",
                    "ACTIVE",
                    "company",
                ],
                [
                    "1",
                    "Fixture Builder",
                    "",
                    "1",
                    "1 Example Street QLD 4000",
                    "Carpenter",
                    "ACTIVE",
                    "company",
                ],
                ["2", "Conflict", abn(), "1", "Street QLD 4000", "Builder", "ACTIVE", "company"],
                ["2", "Conflict", abn(), "2", "Street QLD 4000", "Builder", "ACTIVE", "company"],
                ["3", "Bad tail", abn(1), "2", "Street QLD 4000 extra", "Builder", "ACTIVE", "company"],
            ],
        )
    )
    assert len(result.records) == 2 and len(result.quarantined) == 1
    assert result.records[0]["abn"] is None
    assert result.records[0]["class_types"] == ["Builder", "Carpenter"]
    assert result.records[1]["geography_review_required"]
    assert len(list(qbcc_events(None, result))) == 2
    assert list(qbcc_events(result, result)) == []
    assert pq.read_table(write_qbcc_parquet(result, tmp_path / "qbcc.parquet")).num_rows == 2


def test_qbcc_wrong_encoding_and_header(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Licence Number,Name\n1,Example", encoding="utf-8")
    with pytest.raises(SourceError, match="BOM_REQUIRED"):
        parse_qbcc(path)
    path.write_bytes(b"\xff\xfe" + "Licence Number,Name".encode("utf-16-le"))
    with pytest.raises(SourceError, match="HEADER_MISMATCH"):
        parse_qbcc(path)


def test_rules_priority_sort_literals_otn_and_gate(tmp_path):
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text(
        'version: synthetic-v1\nfixture_only: true\nrules:\n- rule_id: plumber\n  industry: Plumbing\n  pattern: "PLUMB"\n- rule_id: builder\n  industry: Building\n  pattern: "BUILD"\n',
        encoding="utf-8",
    )
    rules = load_rules(rule_file)
    assert classify({"BN": ["Z Plumbing", "A Builder"], "MAIN": ["Plumber"]}, rules).industry == "Building"
    assert classify({"MAIN": ["plumber"], "TRD": ["Builder"]}, rules).confidence == "medium"
    assert classify({"OTN": ["Plumber"]}, rules).industry == "Unclassified"
    assert classify({"BN": [" Plumbing & Building "]}, rules).rule_id == "plumber"
    with pytest.raises(SourceError, match="CLASSIFIER_DISABLED"):
        load_rules(rule_file, production=True)


@pytest.mark.parametrize(
    "start,end,months",
    [
        (date(2024, 1, 31), date(2024, 2, 29), 1),
        (date(2024, 1, 31), date(2024, 2, 28), 0),
        (date(2023, 1, 31), date(2023, 2, 28), 1),
        (date(2027, 1, 1), date(2026, 1, 1), None),
    ],
)
def test_completed_months(start, end, months):
    assert completed_months(start, end) == months


def test_tiering_does_not_infer_new_business_or_turnover():
    row = {
        "status": "ACT",
        "status_date": "2024-09-08",
        "gst_status": "ACT",
        "entity_class": "company",
        "state": "QLD",
        "postcode": "4000",
    }
    assert qualify_abr(row, {"gst_registered"}, date(2026, 9, 8)).tier == "A"
    assert qualify_abr(row, {"abn_new"}, date(2026, 9, 8), confidence="high").tier == "B"
    assert qualify_abr(row, {"abn_new"}, date(2026, 9, 8)).tier == "C"
    assert qualify_abr(row, {"abn_reactivated"}, date(2026, 9, 8)).tier is None
    assert not qualify_abr(
        {**row, "status_date": "2027-01-01"}, {"gst_registered"}, date(2026, 9, 8)
    ).enrichment_eligible
    assert target_geography("NSW", "2450") and target_geography("NSW", "2490")
    assert not target_geography("NSW", "2491") and not target_geography("QLD", None)


def test_200_to_60_fairness_dedup_expiry_and_total_order():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    items = [
        QueueItem(
            f"{i:04}",
            f"g{i:04}",
            now - timedelta(days=50 if i < 10 else 1),
            10 if i < 10 else 100,
            10 if i < 10 else 100,
        )
        for i in range(200)
    ]
    result = select_worklist(list(reversed(items)), now)
    assert len(result.selected) == 60 and len(result.excluded) == 140
    assert [r.lead_id for r in result.selected[:10]] == [f"{i:04}" for i in range(10)]
    assert [r.lead_id for r in result.selected] == [r.lead_id for r in select_worklist(items, now).selected]
    duplicate = replace(items[50], lead_id="duplicate", group_id=items[0].group_id)
    expired = replace(items[0], lead_id="expired", first_qualified_at=now - timedelta(weeks=8))
    blocked = replace(items[0], lead_id="suppressed", suppressed=True)
    final = select_worklist([*items, duplicate, expired, blocked], now)
    assert len({r.group_id for r in final.selected}) == 60
    assert final.excluded["expired"] == "QUEUE_EXPIRED" and final.excluded["suppressed"] == "SUPPRESSED"
    deferred = replace(items[0], state="deferred", last_qualifying_event="old")
    assert can_reactivate(deferred, "new") and not can_reactivate(deferred, "old")
    assert not can_reactivate(replace(deferred, suppressed=True), "new")
    assert (
        score(source="abr", tier="A", confidence="high", geography=True, company=True, deliverable_email=True)
        == 100
    )
    assert (
        score(
            source="qbcc",
            tier="A",
            category="2",
            geography=True,
            company=True,
            deliverable_email=True,
            provisional=True,
        )
        == 95
    )


class Response:
    def __init__(self, status, headers, blocks):
        self.status_code, self.headers, self.blocks = status, headers, blocks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        for block in self.blocks:
            if isinstance(block, Exception):
                raise block
            yield block


def test_download_strong_validator_resume_and_size_hash(tmp_path):
    calls = []
    responses = iter(
        [
            Response(200, {"ETag": '"v1"', "Content-Length": "6"}, [b"abc", OSError("interrupted")]),
            Response(206, {"ETag": '"v1"', "Content-Range": "bytes 3-5/6"}, [b"def"]),
        ]
    )

    def transport(url, **kwargs):
        calls.append(kwargs)
        return next(responses)

    result = download_resource(
        "https://source.invalid/fixture.zip",
        tmp_path / "result.zip",
        transport=transport,
        expected_sha256=hashlib.sha256(b"abcdef").hexdigest(),
        sleep=lambda _: None,
    )
    assert result.read_bytes() == b"abcdef"
    assert calls[1]["headers"]["Range"] == "bytes=3-" and calls[1]["headers"]["If-Range"] == '"v1"'
    assert calls[0]["connect_timeout"] == 10 and calls[0]["read_timeout"] == 20


@pytest.mark.parametrize("first_etag,second_status", [('W/"weak"', 200), ('"strong"', 200)])
def test_download_weak_validator_or_200_restarts(tmp_path, first_etag, second_status):
    responses = iter(
        [
            Response(200, {"ETag": first_etag, "Content-Length": "6"}, [b"old", TimeoutError()]),
            Response(second_status, {"ETag": '"new"', "Content-Length": "6"}, [b"newnew"]),
        ]
    )
    path = download_resource(
        "https://source.invalid/f.zip",
        tmp_path / "out.zip",
        transport=lambda *a, **kw: next(responses),
        sleep=lambda _: None,
    )
    assert path.read_bytes() == b"newnew"


def test_download_bad_resume_and_attempt_limit(tmp_path):
    responses = iter(
        [
            Response(200, {"ETag": '"v1"', "Content-Length": "6"}, [b"abc", OSError()]),
            Response(206, {"ETag": '"other"', "Content-Range": "bytes 3-5/6"}, [b"def"]),
        ]
    )
    with pytest.raises(SourceError, match="INVALID_RESUME_RANGE"):
        download_resource(
            "https://source.invalid/f.zip",
            tmp_path / "bad.zip",
            transport=lambda *a, **kw: next(responses),
            sleep=lambda _: None,
        )
    assert not (tmp_path / "bad.zip").exists()
    calls = []

    def down(*a, **kw):
        calls.append(1)
        raise TimeoutError()

    with pytest.raises(SourceError, match="DOWNLOAD_ATTEMPTS_EXHAUSTED"):
        download_resource(
            "https://source.invalid/f.zip", tmp_path / "fail.zip", transport=down, sleep=lambda _: None
        )
    assert len(calls) == 5
