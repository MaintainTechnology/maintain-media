from types import SimpleNamespace

import pytest

from abr_engine.ingest.common import SourceError
from abr_engine.ingest.quality import REQUIRED_FILL_FIELDS, validate_fill, weighted_fill


def member(rows, fraction):
    return SimpleNamespace(row_count=rows, field_fill=dict.fromkeys(REQUIRED_FILL_FIELDS, fraction))


def test_row_weighted_fill_stable_across_repartition():
    actual = weighted_fill([member(90, 1), member(10, 0.5)])
    assert actual["source_rows"] == 100
    assert actual["field_fill_weighted"]["postcode"] == 0.95
    assert actual == weighted_fill([member(50, 1), member(40, 1), member(10, 0.5)])


def test_missing_required_evidence_cannot_waive_check():
    actual = weighted_fill([member(100, 0.99)])
    with pytest.raises(SourceError, match="REQUIRED_FIELD_MISSING"):
        validate_fill(actual, {})
    with pytest.raises(SourceError, match="FIELD_FILL_EVIDENCE_MISMATCH"):
        validate_fill(actual, {"field_fill_weighted": {}})
    with pytest.raises(SourceError, match="FIELD_FILL_BREACH"):
        validate_fill(weighted_fill([member(100, 0.97)]), {}, weighted_fill([member(100, 1)]))
