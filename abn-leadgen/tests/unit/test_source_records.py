"""Bounded pagination reads selected row groups, never the whole ABR dataset."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from abr_engine.config import Settings
from abr_engine.control.service import DomainError
from abr_engine.live import source_records as browse


def make_artifacts(tmp_path):
    artifacts = []
    for part in range(2):
        path = tmp_path / f"part-{part}.parquet"
        rows = [{**dict.fromkeys(browse.FIELDS["abr"], ""), "abn": str(10000000000 + i),
                 "main_name": f"Synthetic {i}", "private_internal_field": "must not be disclosed"}
                for i in range(part * 200, (part + 1) * 200)]
        pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=25)
        artifacts.append({"artifact_id": uuid4(), "local_path": str(path), "byte_count": path.stat().st_size,
                          "verified_at": datetime.now(UTC) + timedelta(seconds=1)})
    return artifacts


@pytest.mark.parametrize("offset,expected_groups,next_offset", [
    (175, [(0, [7]), (1, [0])], 225),
    (350, [(1, [6]), (1, [7])], None),
    (400, [], None),
])
def test_footer_pagination_skips_prior_files_and_row_groups(tmp_path, monkeypatch, offset,
                                                         expected_groups, next_offset):
    artifacts = make_artifacts(tmp_path)
    original = pq.ParquetFile
    reads = []

    class ObservedFile:
        def __init__(self, path):
            self.part = int(path.stem.split("-")[1])
            self.table = original(path)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.table.close()

        def __getattr__(self, name):
            return getattr(self.table, name)

        def iter_batches(self, **kwargs):
            reads.append((self.part, kwargs["row_groups"]))
            assert "private_internal_field" not in kwargs["columns"]
            return self.table.iter_batches(**kwargs)

    monkeypatch.setattr(pq, "ParquetFile", ObservedFile)
    result = {"source": "abr", "source_state": "available", "total": 400,
              "offset": offset, "records": []}
    browse._read_page(Settings(output_dir=tmp_path), result, artifacts)
    assert reads == expected_groups
    assert result["next_offset"] == next_offset
    assert [row["main_name"] for row in result["records"]] == [
        f"Synthetic {i}" for i in range(offset, min(offset + 50, 400))]
    assert all("private_internal_field" not in row for row in result["records"])


def test_changed_file_is_refused_before_any_parquet_read(tmp_path, monkeypatch):
    artifacts = make_artifacts(tmp_path)
    artifacts[0]["verified_at"] = datetime(2000, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(pq, "ParquetFile", lambda *args: pytest.fail("changed file was opened"))
    with pytest.raises(DomainError, match="SOURCE_ARTIFACT_CHANGED"):
        browse._read_page(Settings(output_dir=tmp_path),
                          {"source": "abr", "source_state": "available"}, artifacts)


def test_outside_storage_refused_before_any_parquet_read(tmp_path, monkeypatch):
    artifacts = make_artifacts(tmp_path)
    monkeypatch.setattr(pq, "ParquetFile", lambda *args: pytest.fail("outside file was opened"))
    with pytest.raises(DomainError, match="ARTIFACT_PATH_OUTSIDE_STORAGE"):
        browse._read_page(Settings(output_dir=tmp_path / "managed"),
                          {"source": "abr", "source_state": "available"}, artifacts)
