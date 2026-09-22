"""Search correctness, bounded pagination and export use one source predicate."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from abr_engine.config import Settings
from abr_engine.control.service import DomainError
from abr_engine.live import source_query as query
from abr_engine.live import source_records as browse


@pytest.fixture
def source_files(tmp_path):
    paths = []
    for part in range(2):
        path = tmp_path / f"part-{part}.parquet"
        records = [{**dict.fromkeys(query.FIELDS["abr"], ""), "abn": str(51824753000 + index),
                    "main_name": f"Synthetic {'Builder' if index % 2 else 'Painter'} {index}",
                    "names_json": json.dumps({"BN": ["Alternate Roofing"] if index == 17 else [],
                                              "TRD": [], "OTN": [], "MAIN": []}, separators=(",", ":")),
                    "state": "QLD" if index % 3 else "NSW", "postcode": "4000",
                    "status": "ACT", "gst_status": "ACT" if index % 4 else "NON",
                    "entity_type": "PRV", "entity_class": "company"}
                   for index in range(part * 100, (part + 1) * 100)]
        pq.write_table(pa.Table.from_pylist(records), path, row_group_size=20)
        paths.append(path)
    return paths


def page(paths, filters, offset=0):
    return query.filtered_page(paths, "abr", filters, offset=offset, limit=50,
                               seals={str(path): browse._identity(path) for path in paths})


def test_exact_abn_ignores_formatting_and_alternate_name_search(source_files):
    exact = page(source_files, {"query": "51 824 753 017"})
    assert exact["total"] == 1 and exact["records"][0]["abn"] == "51824753017"
    alternate = page(source_files, {"query": "roofing"})
    assert alternate["total"] == 1 and alternate["records"][0]["abn"] == "51824753017"


def test_alternate_name_search_matches_values_not_json_keys_or_syntax(tmp_path):
    path = tmp_path / "names.parquet"
    names = [[], ["BN Roofing"], ['A "Quoted" Name'], [r"Back\slash"], ["Café [.*] Works"]]
    rows = [{**dict.fromkeys(query.FIELDS["abr"], ""), "abn": str(index),
             "names_json": json.dumps({"BN": values, "TRD": [], "OTN": [], "MAIN": []},
                                      ensure_ascii=False, separators=(",", ":"))}
            for index, values in enumerate(names)]
    pq.write_table(pa.Table.from_pylist(rows), path)
    for text, expected in (("BN", ["1"]), ("TRD", []), ("OTN", []), ("MAIN", []),
                           ("[]", []), ('"Quoted"', ["2"]), (r"Back\slash", ["3"]),
                           ("café [.*]", ["4"])):
        result = page([path], {"query": text})
        assert [row["abn"] for row in result["records"]] == expected
        exported = [row["abn"] for batch in query.iter_filtered_batches([path], "abr", {"query": text}, lambda: None)
                    for row in batch.to_pylist()]
        assert exported == expected


def test_cached_count_skips_full_scan_on_next_page(source_files, monkeypatch):
    first = page(source_files, {"query": "BUILDER"})
    assert first["total"] == 100 and first["next_offset"] == 50
    monkeypatch.setattr(query, "_group_fragments", lambda *args: pytest.fail("cached query rescanned source"))
    second = page(source_files, {"query": "BUILDER"}, offset=50)
    assert second["total"] == 100 and second["next_offset"] is None
    assert {row["abn"] for row in first["records"]}.isdisjoint(row["abn"] for row in second["records"])


def test_combined_filters_page_matches_streamed_export(source_files):
    filters = query.SourceFilters(query="Builder", state="QLD", postcode="4000", gst_status="ACT",
                                  entity_type="PRV", entity_class="company")
    first = page(source_files, filters)
    checks = []
    exported = [row for batch in query.iter_filtered_batches(source_files, "abr", filters,
                                                            lambda: checks.append(True))
                for row in batch.to_pylist()]
    assert len(exported) == first["total"]
    assert exported[:50] == first["records"]
    assert checks and len(checks) > len(source_files)
    assert set(exported[0]) == set(query.FIELDS["abr"])


def test_no_matches_still_checks_cancellation(source_files):
    checks = []
    assert list(query.iter_filtered_batches(source_files, "abr", query.SourceFilters(query="Absent"),
                                             lambda: checks.append(True))) == []
    assert len(checks) >= 10


def test_qbcc_exact_formatted_licence_and_acn_search(tmp_path):
    path = tmp_path / "qbcc.parquet"
    record = {**dict.fromkeys(query.FIELDS["qbcc"], ""), "licence_number": "123456",
              "licensee_name": "Synthetic Builder", "abn": "51824753556", "acn": "123456789",
              "class_types": ["Builder"], "licence_grades": ["Contractor"],
              "licence_types": [{"code": "T", "description": "Trade Contractor"}],
              "geography_review_required": False, "licence_review_required": True}
    pq.write_table(pa.Table.from_pylist([record]), path)
    for lookup in ("123 456", "123 456 789", "51 824 753 556", "BUILDER"):
        rows = [row for batch in query.iter_filtered_batches([path], "qbcc", {"query": lookup}, lambda: None)
                for row in batch.to_pylist()]
        assert rows == [record]


def test_not_supplied_gst_preserves_non_registered_as_distinct_state(tmp_path):
    path = tmp_path / "gst.parquet"
    rows = [{**dict.fromkeys(query.FIELDS["abr"], ""), "abn": str(index), "gst_status": status}
            for index, status in enumerate([None, "", "NONE", "UNKNOWN", "NON", "ACT", "CAN"])]
    pq.write_table(pa.Table.from_pylist(rows), path)
    for marker in ("NONE", "UNKNOWN"):
        result = page([path], {"gst_status": marker})
        assert result["total"] == 4
        assert {row["gst_status"] for row in result["records"]} == {None, "", "NONE", "UNKNOWN"}
        assert query.normalized_filters("abr", {"gst_status": marker}).gst_status == marker
    assert page([path], {"gst_status": "NON"})["total"] == 1


@pytest.mark.parametrize("source,filters", [
    ("abr", {"financial_category": "7"}), ("qbcc", {"gst_status": "ACT"}),
    ("qbcc", {"status": "active"}), ("abr", {"postcode": "400"}),
    ("abr", {"state": "DROP TABLE"}), ("abr", {"query": "x" * 201}),
    ("abr", {"private_column": "x"}), ("abr", {"query": 51824753017}),
])
def test_filters_reject_unknown_fields_invalid_types_and_wrong_source(source, filters):
    with pytest.raises(DomainError, match="INVALID_SOURCE_FILTERS"):
        query.normalized_filters(source, filters)


@pytest.mark.parametrize("filters", [
    {"status_date_from": "2026-02-29"}, {"status_date_to": "2026-09-31"},
    {"status_date_from": "0000-01-01"}, {"status_date_to": "2026-13-01"},
    {"status_date_from": "20260922"}, {"status_date_to": "2026-9-22"},
    {"status_date_from": "2026-09-22T00:00:00Z"}, {"status_date_to": 20260922},
    {"status_date_from": "2026-09-22", "status_date_to": "2026-09-16"},
])
def test_status_date_filters_reject_invalid_calendar_dates_and_reversed_ranges(filters):
    with pytest.raises(DomainError, match="INVALID_SOURCE_FILTERS"):
        query.normalized_filters("abr", filters)


@pytest.mark.parametrize("field", ["status_date_from", "status_date_to"])
def test_status_date_filters_are_abr_only_and_keep_canonical_iso_strings(field):
    with pytest.raises(DomainError, match="INVALID_SOURCE_FILTERS"):
        query.normalized_filters("qbcc", {field: "2024-02-29"})
    filters = query.normalized_filters("abr", {field: " 2024-02-29 "})
    assert filters.model_dump(exclude_none=True) == {field: "2024-02-29"}
    assert query.normalized_filters("abr", {field: " "}).model_dump(exclude_none=True) == {}


@pytest.fixture
def dated_source_file(tmp_path):
    path = tmp_path / "dates.parquet"
    dates = [date(2010, 1, 1), None, date(2026, 9, 15), date(2026, 9, 16),
             date(2026, 9, 18), date(2026, 9, 22), date(2026, 9, 23)]
    records = [{**dict.fromkeys(query.FIELDS["abr"], ""), "abn": str(index),
                "status_date": value, "status": "CAN" if index == 4 else "ACT"}
               for index, value in enumerate(dates)]
    pq.write_table(pa.Table.from_pylist(records), path, row_group_size=1)
    return path


@pytest.mark.parametrize("filters,expected", [
    ({"status_date_from": "2026-09-16", "status_date_to": "2026-09-22", "status": "ACT"}, ["3", "5"]),
    ({"status_date_from": "2026-09-16", "status_date_to": "2026-09-22"}, ["3", "4", "5"]),
    ({"status_date_from": "2026-09-22", "status_date_to": "2026-09-22"}, ["5"]),
    ({"status_date_from": "2026-09-22"}, ["5", "6"]),
    ({"status_date_to": "2026-09-16"}, ["0", "2", "3"]),
    ({"status_date_from": "2026-10-01"}, []),
])
def test_status_date_range_is_inclusive_excludes_missing_dates_and_matches_export(
    dated_source_file, filters, expected,
):
    result = page([dated_source_file], filters)
    assert [row["abn"] for row in result["records"]] == expected
    assert result["total"] == len(expected)
    exported = [row for batch in query.iter_filtered_batches([dated_source_file], "abr", filters, lambda: None)
                for row in batch.to_pylist()]
    assert exported == result["records"]


def test_status_date_filter_prunes_unrelated_row_groups_and_keeps_bounded_projection(
    dated_source_file, monkeypatch,
):
    filters = {"status_date_from": "2026-09-16", "status_date_to": "2026-09-22", "status": "ACT"}
    groups = list(query._group_fragments([dated_source_file], query.filter_expression("abr", filters), lambda: None))
    assert [group.row_groups[0].id for _, group in groups] == [3, 5]
    result = query.filtered_page([dated_source_file], "abr", filters, offset=0, limit=1,
                                 seals={str(dated_source_file): browse._identity(dated_source_file)})
    assert result["total"] == 2 and result["next_offset"] == 1
    assert set(result["records"][0]) == set(query.FIELDS["abr"])
    monkeypatch.setattr(query, "_group_fragments", lambda *args: pytest.fail("date-filtered query rescanned source"))
    second = query.filtered_page([dated_source_file], "abr", filters, offset=1, limit=1,
                                 seals={str(dated_source_file): browse._identity(dated_source_file)})
    assert second["records"][0]["abn"] == "5" and second["next_offset"] is None


def test_search_deadline_stops_before_another_group(source_files, monkeypatch):
    times = iter([0, 31])
    monkeypatch.setattr(query, "monotonic", lambda: next(times, 31))
    query._counts.clear()
    with pytest.raises(DomainError, match="SOURCE_QUERY_TIMEOUT"):
        page(source_files, {"query": "Builder"})


def test_filtered_reader_reports_matching_and_source_totals(source_files):
    artifacts = [{"local_path": str(path), "byte_count": path.stat().st_size,
                  "verified_at": datetime.now(UTC) + timedelta(seconds=1)} for path in source_files]
    result = {"source": "abr", "source_state": "available", "total": 200,
              "offset": 0, "records": []}
    browse._read_page(Settings(output_dir=Path(source_files[0]).parent), result, artifacts,
                      query.SourceFilters(query="Builder"))
    assert result["total"] == 100 and result["source_total"] == 200
    assert result["records"][0]["source_member"] == ""


@pytest.fixture
def mixed_date_files(tmp_path):
    paths, records = [], []
    for part in range(2):
        path = tmp_path / f"mixed-dates-{part}.parquet"
        rows = [{**dict.fromkeys(query.FIELDS["abr"], ""), "abn": str(index),
                 "status_date": None if index % 11 == 0 else date(2026, 9, 16 + index % 7),
                 "status": "CAN" if index % 5 == 0 else "ACT", "state": "QLD"}
                for index in range(part * 125, (part + 1) * 125)]
        pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=23)
        paths.append(path)
        records.extend(rows)
    return paths, records


@pytest.mark.parametrize("filters", [{}, {"status": "ACT", "status_date_from": "2026-09-18",
                                      "status_date_to": "2026-09-22"}])
def test_newest_sort_is_global_stable_and_complete_across_pages_and_files(mixed_date_files, filters):
    paths, records = mixed_date_files
    expected = [row for row in records if not filters or (row["status"] == "ACT"
                and row["status_date"] is not None
                and date(2026, 9, 18) <= row["status_date"] <= date(2026, 9, 22))]
    expected.sort(key=lambda row: row["status_date"] or date.min, reverse=True)
    actual, offset = [], 0
    while offset is not None:
        result = query.filtered_page(paths, "abr", filters, offset=offset, limit=50,
                                     seals={str(path): browse._identity(path) for path in paths},
                                     sort="status_date_desc")
        assert result["total"] == len(expected)
        actual.extend(result["records"])
        offset = result["next_offset"]
    assert actual == expected
    assert len({row["abn"] for row in actual}) == len(expected)
    # Explicitly prove the first page includes later source files, not merely a
    # reordered first source page, and includes ties across row-group boundaries.
    assert any(int(row["abn"]) >= 125 for row in actual[:50])
    assert actual[0]["status_date"] == date(2026, 9, 22)
    if not filters:
        assert actual[-1]["status_date"] is None
    exported = [row for batch in query.iter_filtered_batches(paths, "abr", filters, lambda: None)
                for row in batch.to_pylist()]
    assert exported == [row for row in records if row in expected]
    assert page(paths, filters)["records"] == exported[:50]


def test_newest_sort_reuses_counts_and_reader_preserves_source_total(mixed_date_files, monkeypatch):
    paths, _ = mixed_date_files
    seals = {str(path): browse._identity(path) for path in paths}
    first = query.filtered_page(paths, "abr", {}, offset=0, limit=50, seals=seals, sort="status_date_desc")
    monkeypatch.setattr(query, "_group_fragments", lambda *args: pytest.fail("sorted page rescanned source"))
    second = query.filtered_page(paths, "abr", {}, offset=50, limit=50, seals=seals, sort="status_date_desc")
    assert first["total"] == second["total"] == 250
    assert {row["abn"] for row in first["records"]}.isdisjoint(row["abn"] for row in second["records"])
    artifacts = [{"local_path": str(path), "byte_count": path.stat().st_size,
                  "verified_at": datetime.now(UTC) + timedelta(seconds=1)} for path in paths]
    result = {"source": "abr", "source_state": "available", "total": 250, "offset": 50, "records": []}
    browse._read_page(Settings(output_dir=paths[0].parent), result, artifacts, sort="status_date_desc")
    assert result["records"] == second["records"]
    assert result["total"] == result["source_total"] == 250


def test_newest_counts_key_changes_with_snapshot_identity(mixed_date_files, monkeypatch):
    paths, _ = mixed_date_files
    seals = {str(path): browse._identity(path) for path in paths}
    query.filtered_page(paths, "abr", {}, offset=0, limit=50, seals=seals, sort="status_date_desc")
    scans = []
    original = query._group_fragments

    def observed(*args):
        scans.append(True)
        return original(*args)

    monkeypatch.setattr(query, "_group_fragments", observed)
    seals[str(paths[0])] = (*seals[str(paths[0])][:-1], seals[str(paths[0])][-1] + 1)
    query.filtered_page(paths, "abr", {}, offset=0, limit=50, seals=seals, sort="status_date_desc")
    assert scans


def test_newest_sort_enforces_aggregate_count_bound_and_checks_deadline(mixed_date_files, monkeypatch):
    paths, _ = mixed_date_files
    seals = {str(path): browse._identity(path) for path in paths}
    monkeypatch.setattr(query, "MAX_DATE_GROUP_COUNTS", 1)
    with pytest.raises(DomainError, match="SOURCE_QUERY_TOO_LARGE"):
        query.filtered_page(paths, "abr", {}, offset=0, limit=50, seals=seals, sort="status_date_desc")
    monkeypatch.setattr(query, "MAX_DATE_GROUP_COUNTS", 100_000)
    times = iter([0, 31])
    monkeypatch.setattr(query, "monotonic", lambda: next(times, 31))
    with pytest.raises(DomainError, match="SOURCE_QUERY_TIMEOUT"):
        query.filtered_page(paths, "abr", {}, offset=0, limit=50, seals=seals, sort="status_date_desc")


@pytest.mark.parametrize("source,sort", [("qbcc", "status_date_desc"), ("abr", "newest"), ("abr", None)])
def test_invalid_sort_is_rejected_before_reading(source, sort):
    with pytest.raises(DomainError, match="INVALID_SOURCE_SORT"):
        query.filtered_page([], source, {}, offset=0, limit=50, seals={}, sort=sort)


def test_sort_api_contract_is_optional_and_rejects_unrecognized_order():
    from pydantic import ValidationError

    from abr_engine.live.api import SourceRecordQuery

    assert SourceRecordQuery(source="abr").sort == "source_order"
    assert SourceRecordQuery(source="abr", sort="status_date_desc").sort == "status_date_desc"
    with pytest.raises(ValidationError):
        SourceRecordQuery(source="abr", sort="score")
