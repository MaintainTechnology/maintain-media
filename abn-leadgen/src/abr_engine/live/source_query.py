"""Validated source filters and bounded, reusable Parquet query primitives.

Only match counts per row group/date are cached, never publisher records. A
repeated query can jump to its next page without rescanning earlier records.
"""

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from threading import Lock, Semaphore
from time import monotonic
from typing import Literal

import pyarrow.compute as pc
import pyarrow.dataset as ds
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from abr_engine.control.service import DomainError

FIELDS = {
    "abr": ("abn", "main_name", "status", "status_date", "gst_status", "gst_date",
            "entity_type", "entity_class", "state", "postcode", "names_json",
            "name_hash", "semantic_hash", "source_member"),
    "qbcc": ("licence_number", "licensee_name", "abn", "financial_category",
             "original_address", "state", "postcode", "status", "entity_class", "row_digest",
             "class_types", "geography_review_required", "acn", "financial_category_description",
             "licence_review_required", "licence_grades", "licence_types"),
}
QUERY_SECONDS = 30
CACHE_SECONDS = 300
CACHE_SIZE = 32
MAX_GROUPS = 100_000
MAX_DATE_GROUP_COUNTS = 100_000
_queries = Semaphore(2)
_cache_lock = Lock()


class SourceFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    query: str | None = Field(default=None, max_length=200)
    state: Literal["QLD", "NSW", "VIC", "TAS", "SA", "WA", "NT", "ACT", "AAT"] | None = None
    postcode: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    status: str | None = Field(default=None, max_length=30)
    gst_status: str | None = Field(default=None, max_length=30)
    entity_type: str | None = Field(default=None, max_length=80)
    entity_class: str | None = Field(default=None, max_length=80)
    financial_category: str | None = Field(default=None, max_length=30)
    status_date_from: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    status_date_to: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @field_validator("*", mode="before")
    @classmethod
    def trim_empty(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if any(ord(char) < 32 for char in value):
                raise ValueError("Control characters are not accepted")
            return value or None
        return value

    @field_validator("status_date_from", "status_date_to")
    @classmethod
    def valid_calendar_date(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def ordered_date_range(self):
        if (self.status_date_from and self.status_date_to
                and date.fromisoformat(self.status_date_from) > date.fromisoformat(self.status_date_to)):
            raise ValueError("Status date range must start on or before its end")
        return self


def normalized_filters(source, value=None):
    if source not in FIELDS:
        raise DomainError("INVALID_INPUT", 422)
    try:
        filters = value if isinstance(value, SourceFilters) else SourceFilters.model_validate({} if value is None else value)
    except ValidationError:
        raise DomainError("INVALID_SOURCE_FILTERS", 422) from None
    if ((source == "abr" and filters.financial_category)
            or (source == "qbcc" and (filters.gst_status or filters.entity_type
                                     or filters.status_date_from or filters.status_date_to))):
        raise DomainError("INVALID_SOURCE_FILTERS", 422)
    if filters.status and filters.status not in ({"ACT", "CAN", "UNKNOWN"} if source == "abr" else {"UNKNOWN"}):
        raise DomainError("INVALID_SOURCE_FILTERS", 422)
    if filters.gst_status and filters.gst_status not in {"ACT", "NON", "CAN", "NONE", "UNKNOWN"}:
        raise DomainError("INVALID_SOURCE_FILTERS", 422)
    return filters


def normalized_sort(source, value="source_order"):
    if value not in {"source_order", "status_date_desc"} or (source != "abr" and value != "source_order"):
        raise DomainError("INVALID_SOURCE_SORT", 422)
    return value


def _name_value_pattern(value):
    # names_json is a canonical object of arrays, including empty BN/TRD/OTN
    # arrays. Search only array string values so those keys never become names.
    # Token boundaries also keep escaped quotes/backslashes inside their value.
    literal = re.escape(json.dumps(value, ensure_ascii=False)[1:-1])
    token = r'(?:[^"\\]|\\.)*'
    return r'(?:\[|,)\s*"' + token + literal + token + r'"\s*(?:,|\])'


def filter_expression(source, filters):
    filters = normalized_filters(source, filters)
    expression = None
    for field, value in filters.model_dump(exclude_none=True).items():
        if field == "query":
            identifier = re.sub(r"[\s-]", "", value)
            if re.fullmatch(r"[0-9]{11}", identifier):
                term = ds.field("abn") == identifier
                if source == "qbcc":
                    term = term | (ds.field("licence_number") == identifier)
            elif source == "qbcc" and re.fullmatch(r"[0-9]{1,20}", identifier):
                term = ds.field("licence_number") == identifier
                if len(identifier) == 9:
                    term = term | (ds.field("acn") == identifier)
            else:
                name = "main_name" if source == "abr" else "licensee_name"
                alternate = (pc.match_substring_regex(ds.field("names_json"), _name_value_pattern(value), ignore_case=True)
                             if source == "abr" else pc.match_substring(ds.field("licence_number"), value, ignore_case=True))
                term = pc.match_substring(ds.field(name), value, ignore_case=True) | alternate
        elif field in {"status_date_from", "status_date_to"}:
            # ABR stores a date32 status commencement date, which can also be a
            # reactivation date. Typed bounds preserve Parquet statistics pruning;
            # callers must explicitly request ACT when reviewing recent activity.
            bound = date.fromisoformat(value)
            term = (ds.field("status_date") >= bound if field == "status_date_from"
                    else ds.field("status_date") <= bound)
        elif field == "gst_status" and value in {"NONE", "UNKNOWN"}:
            term = ds.field(field).is_null() | ds.field(field).isin(["", "NONE", "UNKNOWN"])
        elif field == "status" and value == "UNKNOWN" and source == "abr":
            term = ds.field(field).is_null() | ds.field(field).isin(["", "UNKNOWN"])
        else:
            term = ds.field(field) == value
        expression = term if expression is None else expression & term
    return expression


def _check_group(group):
    info = group.row_groups[0]
    if info.num_rows > 1_048_576 or info.total_byte_size > 256 * 1024**2:
        raise DomainError("SOURCE_ROW_GROUP_TOO_LARGE", 409)


def _group_fragments(paths, expression, check):
    groups_seen = 0
    for path_index, path in enumerate(paths):
        check()
        dataset = ds.dataset(str(path), format="parquet")
        for fragment in dataset.get_fragments():
            check()
            for group in fragment.split_by_row_group(filter=expression):
                check()
                groups_seen += 1
                if groups_seen > MAX_GROUPS:
                    raise DomainError("SOURCE_QUERY_TOO_LARGE", 409)
                _check_group(group)
                yield path_index, group
        check()


def iter_filtered_batches(paths, source, filters, check):
    """Stream all matching parsed columns, checking even empty row groups."""
    expression = filter_expression(source, filters)
    for _, group in _group_fragments(paths, expression, check):
        for batch in group.scanner(columns=list(FIELDS[source]), filter=expression,
                                   batch_size=2000, use_threads=False,
                                   batch_readahead=1, fragment_readahead=1).to_batches():
            check()
            if batch.num_rows:
                yield batch
            check()
        check()


@dataclass(frozen=True)
class QueryCounts:
    created_at: float
    groups: tuple[tuple[int, int, int], ...]

    @property
    def total(self):
        return sum(row[2] for row in self.groups)


_counts: OrderedDict[tuple, QueryCounts] = OrderedDict()


@dataclass(frozen=True)
class QueryDateCounts:
    created_at: float
    # Date, file index, row-group ID, matching row count. Stable source order is
    # preserved within a date, including records with no published status date.
    groups: tuple[tuple[date | None, int, int, int], ...]

    @property
    def total(self):
        return sum(row[3] for row in self.groups)


_date_counts: OrderedDict[tuple, QueryDateCounts] = OrderedDict()


def _cached_counts(key, cache=None):
    cache = _counts if cache is None else cache
    with _cache_lock:
        for stale in [item for item, value in cache.items() if monotonic() - value.created_at > CACHE_SECONDS]:
            del cache[stale]
        value = cache.get(key)
        if value:
            cache.move_to_end(key)
        return value


def _match_counts(paths, expression, key, check):
    cached = _cached_counts(key)
    if cached is not None:
        return cached
    if not _queries.acquire(timeout=2):
        raise DomainError("SOURCE_QUERY_BUSY", 503)
    try:
        cached = _cached_counts(key)
        if cached is not None:
            return cached
        matches = []
        for path_index, group in _group_fragments(paths, expression, check):
            count = group.count_rows(filter=expression, batch_size=2000, use_threads=False,
                                     batch_readahead=1, fragment_readahead=1)
            check()
            if count:
                matches.append((path_index, group.row_groups[0].id, count))
        counted = QueryCounts(monotonic(), tuple(matches))
        with _cache_lock:
            _counts[key] = counted
            _counts.move_to_end(key)
            while len(_counts) > CACHE_SIZE:
                _counts.popitem(last=False)
        return counted
    finally:
        _queries.release()


def _match_date_counts(paths, expression, key, check):
    cached = _cached_counts(key, _date_counts)
    if cached is not None:
        return cached
    if not _queries.acquire(timeout=2):
        raise DomainError("SOURCE_QUERY_BUSY", 503)
    try:
        cached = _cached_counts(key, _date_counts)
        if cached is not None:
            return cached
        matches = []
        for path_index, group in _group_fragments(paths, expression, check):
            per_date = {}
            # Read only the sort column plus columns needed by the predicate;
            # grouping dates avoids materializing millions of publisher rows.
            for batch in group.scanner(columns=["status_date"], filter=expression,
                                       batch_size=2000, use_threads=False,
                                       batch_readahead=1, fragment_readahead=1).to_batches():
                check()
                for entry in pc.value_counts(batch.column(0)).to_pylist():
                    value = entry["values"]
                    if value is not None and type(value) is not date:
                        raise DomainError("SOURCE_SCHEMA_UNAVAILABLE", 409)
                    per_date[value] = per_date.get(value, 0) + entry["counts"]
                if len(matches) + len(per_date) > MAX_DATE_GROUP_COUNTS:
                    raise DomainError("SOURCE_QUERY_TOO_LARGE", 409)
            matches.extend((value, path_index, group.row_groups[0].id, count)
                           for value, count in per_date.items())
            check()
        # Python's stable sort keeps file/row-group order for ties. Null dates
        # sort last; no records are discarded to make the ordering affordable.
        matches.sort(key=lambda row: (row[0] is not None, row[0] or date.min), reverse=True)
        counted = QueryDateCounts(monotonic(), tuple(matches))
        with _cache_lock:
            _date_counts[key] = counted
            _date_counts.move_to_end(key)
            # Cap the whole cache as well as each query, independently of the
            # existing unsorted count cache.
            while (len(_date_counts) > CACHE_SIZE
                   or sum(len(value.groups) for value in _date_counts.values()) > MAX_DATE_GROUP_COUNTS):
                _date_counts.popitem(last=False)
        return counted
    finally:
        _queries.release()


def filtered_page(paths, source, filters, *, offset, limit, seals, check=None, sort="source_order"):
    filters = normalized_filters(source, filters)
    sort = normalized_sort(source, sort)
    started = monotonic()

    def checkpoint():
        if monotonic() - started > QUERY_SECONDS:
            raise DomainError("SOURCE_QUERY_TIMEOUT", 504)
        if check:
            check()

    expression = filter_expression(source, filters)
    key = (source, filters.model_dump_json(), tuple((str(path), seals[str(path)]) for path in paths))
    if sort == "status_date_desc":
        counted = _match_date_counts(paths, expression, key, checkpoint)
        groups = counted.groups
    else:
        counted = _match_counts(paths, expression, key, checkpoint)
        groups = ((None, *group) for group in counted.groups)
    rows, skip, remaining = [], offset, limit
    for status_date, path_index, group_id, count in groups:
        checkpoint()
        if skip >= count:
            skip -= count
            continue
        fragment = next(ds.dataset(str(paths[path_index]), format="parquet").get_fragments())
        group = fragment.subset(row_group_ids=[group_id])
        predicate = expression
        if sort == "status_date_desc":
            day = ds.field("status_date").is_null() if status_date is None else ds.field("status_date") == status_date
            predicate = day if expression is None else expression & day
        for batch in group.scanner(columns=list(FIELDS[source]), filter=predicate,
                                   batch_size=2000, use_threads=False,
                                   batch_readahead=1, fragment_readahead=1).to_batches():
            checkpoint()
            if skip >= batch.num_rows:
                skip -= batch.num_rows
                continue
            take = min(remaining, batch.num_rows - skip)
            rows.extend(batch.slice(skip, take).to_pylist())
            skip, remaining = 0, remaining - take
            if not remaining:
                break
        if not remaining:
            break
    checkpoint()
    next_offset = offset + len(rows)
    return {"records": rows, "total": counted.total,
            "next_offset": next_offset if next_offset < counted.total else None}
