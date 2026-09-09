import json
from pathlib import Path

import pytest

from abr_engine.compliance.retention import artifact_retention
from abr_engine.control.service import DomainError
from abr_engine.db import connect
from abr_engine.ops.backup import run_fixture_drill


def test_native_pg_dump_restore_replays_latest_ledger(settings, service, tmp_path):
    service.settings = settings.model_copy(update={"output_dir": tmp_path})
    result = run_fixture_drill(service.settings, service)
    assert result["status"] == "fixture_drill_complete"
    assert all(result["checks"].values())
    assert result["restore"]["outbound"] == "quarantined"
    assert result["external_backup_expiry_and_release"] == "pending"
    archive = Path(result["backup_path"])
    assert archive.is_file() and not archive.read_bytes().startswith(b"PGDMP")
    assert not (archive.parent / "snapshot.dump").exists()
    assert not (archive.parent / "cluster").exists()
    receipt = json.loads((archive.parent / "drill-receipt.json").read_text())
    assert receipt["production_gate"] == "closed"
    with connect(settings) as conn:
        artifacts = conn.execute("SELECT artifact_class,state FROM artifact_manifest WHERE run_id=%s", (result["drill_id"],)).fetchall()
        assert len(artifacts) == 4
        assert {(r["artifact_class"], r["state"]) for r in artifacts} == {("backup", "referenced")}
        conn.execute("UPDATE artifact_manifest SET created_at=clock_timestamp()-interval '36 days' WHERE run_id=%s", (result["drill_id"],))
        deleted = artifact_retention(conn, service, now=service.now(conn), execute=True)
        assert len(deleted) == 4 and all(row["state"] == "deleted" for row in deleted)
        assert not archive.exists()


def test_live_restore_drill_refused_before_native_process(settings, service):
    settings = settings.model_copy(update={"mode": "production"})
    with pytest.raises(DomainError, match="LIVE_BACKUP_RESTORE_APPROVAL_PENDING"):
        run_fixture_drill(settings, service, binary=Path("not-present"))
