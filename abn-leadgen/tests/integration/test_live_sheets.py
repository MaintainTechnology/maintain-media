"""Real pilot-mode worklist projection; synthetic gates only in isolated test schemas."""
import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from psycopg.types.json import Jsonb

from abr_engine.compliance.policy import REQUIRED_GATES
from abr_engine.control.auth import Actor
from abr_engine.control.service import DomainError, Service, json_safe
from abr_engine.control.sheets_auth import load_bridge_registry
from abr_engine.db import transaction
from abr_engine.export.report import CSV_FIELDS
from abr_engine.export.sheets import pull_worklist
from abr_engine.fixture import seed_contact, seed_policy


@pytest.fixture
def sheets_case(settings, service, tmp_path):
    now = datetime.now(UTC)
    config = {"schema_version": 1, "enabled": True, "spreadsheet_id": "syntheticBook123", "sheet_id": 42,
              "owner_email": "owner@example.test", "approved_by": "synthetic-owner",
              "evidence_ref": "synthetic-test-only", "evidence_sha256": "a"*64,
              "verified_at": (now-timedelta(seconds=10)).isoformat(),
              "expires_at": (now+timedelta(days=1)).isoformat(),
              "editors": {"owner@example.test": ["reviewer"], "worker@example.test": ["operator"]}}
    path = tmp_path / "sheets.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with transaction(settings) as conn:
        seed_policy(conn, service)
        record = seed_contact(conn, service)
        worklist_id, row_id = uuid4(), uuid4()
        conn.execute("INSERT INTO worklist(worklist_id,week) VALUES(%s,%s)", (worklist_id, date(2026, 9, 7)))
        gate = service.gate(conn, record["contact"]["contact_id"])
        gate["contact_id"] = str(record["contact"]["contact_id"])
        conn.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,decision,selected_tier,selected_signal) "
                     "VALUES(%s,%s,%s,%s,'A','qbcc_backlog')", (row_id, worklist_id, record["lead"]["lead_id"], Jsonb(json_safe(gate))))
        conn.execute("INSERT INTO worklist_assignment(worklist_id,actor_id) VALUES(%s,'worker@example.test')", (worklist_id,))
        for scope in ("sheets", "collection"):
            for name in REQUIRED_GATES[scope]:
                conn.execute("INSERT INTO release_gate(gate_name,environment,scope,revision,evidence_ref,evidence_sha256,actor_id,approved_at,expires_at) "
                             "VALUES(%s,'pilot',%s,1,'synthetic-test-only',%s,'synthetic-owner',%s,%s)",
                             (name, scope, checksum if name == "G5" else "a"*64, now-timedelta(seconds=10), now+timedelta(days=1)))
    config_settings = settings.model_copy(update={"mode": "pilot", "key_file": tmp_path/"unused-synthetic-key",
        "capabilities": {"collection": True, "sheets": True}, "sheets_bridge_file": path})
    return {"settings": config_settings, "service": Service(config_settings, service.keys), "path": path,
            "registry": load_bridge_registry(path), "row_id": row_id, "worklist_id": worklist_id,
            "record": record, "actor": Actor("owner@example.test", frozenset({"reviewer"}))}


def pull(case):
    return pull_worklist(case["settings"], case["service"], case["actor"], case["registry"])


def test_live_pull_closed_projection_actual_worklist_and_suppression(sheets_case):
    result = pull(sheets_case)
    assert result["disclosure_allowed"] is True and len(result["rows"]) == 1
    assert result["worklist_id"] == str(sheets_case["worklist_id"])
    row = result["rows"][0]
    assert set(row) == set(CSV_FIELDS) and row["row_id"] == str(sheets_case["row_id"])
    assert "encrypted_value" not in str(result) and "endpoint_token" not in str(result)
    assert row["safe_contact_view"] != "Masked — contact blocked"
    assert row["occurred_at"] == "" and row["row_version"] == 1
    with transaction(sheets_case["settings"]) as conn:
        sheets_case["service"].suppress(conn, {"lead_id": sheets_case["record"]["lead"]["lead_id"],
            "reason": "unsubscribe", "source": "synthetic-test"}, "synthetic-reviewer", uuid4())
    after = pull(sheets_case)
    assert after["rows"][0]["safe_contact_view"] == "Masked — contact blocked"
    assert after["rows"][0]["gate_label"] == "Do not contact"


@pytest.mark.parametrize("gate", ["G1", "G3", "G5", "G7"])
def test_each_closed_disclosure_gate_returns_redaction_without_business_data(sheets_case, gate):
    with transaction(sheets_case["settings"]) as conn:
        conn.execute("UPDATE release_gate SET expires_at=clock_timestamp()-interval '1 second' "
                     "WHERE scope='sheets' AND gate_name=%s", (gate,))
    result = pull(sheets_case)
    assert result["disclosure_allowed"] is False and result["rows"] == []
    assert result["worklist_id"] is None and "business_name" not in result
    assert "GATE_"+gate+"_CLOSED" in result["reason_codes"]


def test_g5_other_account_hash_does_not_authorize_google(sheets_case):
    with transaction(sheets_case["settings"]) as conn:
        conn.execute("UPDATE release_gate SET evidence_sha256=%s WHERE scope='sheets' AND gate_name='G5'", ("f"*64,))
    result = pull(sheets_case)
    assert not result["disclosure_allowed"] and result["rows"] == []
    assert "SHEETS_INSTALLATION_NOT_APPROVED" in result["reason_codes"]


def test_owner_timer_cannot_disclose_to_unassigned_workbook_reader(sheets_case):
    with transaction(sheets_case["settings"]) as conn:
        conn.execute("DELETE FROM worklist_assignment")
    with pytest.raises(DomainError, match="SHEETS_READER_NOT_ASSIGNED"):
        pull(sheets_case)


def test_named_assigned_operator_can_read_without_reviewer_escalation(sheets_case):
    sheets_case["actor"] = Actor("worker@example.test", frozenset({"operator"}))
    assert pull(sheets_case)["disclosure_allowed"]
    sheets_case["actor"] = Actor("worker@example.test", frozenset({"reviewer"}))
    with pytest.raises(DomainError, match="SHEETS_REGISTRY_CHANGED"):
        pull(sheets_case)


def test_capability_disabled_and_registry_revocation_fail_closed(sheets_case):
    sheets_case["settings"].capabilities["sheets"] = False
    assert pull(sheets_case)["reason_codes"] == ["CAPABILITY_DISABLED"]
    text = sheets_case["path"].read_text().replace("worker@example.test:", "removed@example.test:")
    sheets_case["path"].write_text(text)
    with pytest.raises(DomainError, match="SHEETS_REGISTRY_CHANGED"):
        pull(sheets_case)


def test_quarantine_prevents_personal_data_read(sheets_case):
    with transaction(sheets_case["settings"]) as conn:
        conn.execute("INSERT INTO system_state(name,value) VALUES('restore_quarantine','true') "
                     "ON CONFLICT(name) DO UPDATE SET value='true'")
    with pytest.raises(DomainError, match="AUTHORITY_QUARANTINED"):
        pull(sheets_case)


def test_registry_removed_during_read_returns_controlled_auth_failure(sheets_case, monkeypatch):
    original = Path.read_bytes
    calls = 0

    def raced(path):
        nonlocal calls
        if path == sheets_case["path"]:
            calls += 1
            if calls == 2:
                raise FileNotFoundError("synthetic registry replacement race")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", raced)
    with pytest.raises(DomainError, match="SHEETS_REGISTRY_CHANGED"):
        pull(sheets_case)


def test_expiry_during_projection_drops_all_business_fields(sheets_case, monkeypatch):
    from abr_engine.export import sheets
    original = sheets.worklist_rows

    def expiry_after_projection(context):
        result = original(context)
        monkeypatch.setattr(sheets_case["service"], "now", lambda conn: datetime.now(UTC)+timedelta(days=2))
        return result

    monkeypatch.setattr(sheets, "worklist_rows", expiry_after_projection)
    result = pull(sheets_case)
    assert not result["disclosure_allowed"] and result["rows"] == [] and result["worklist_id"] is None
    assert result["reason_codes"] == ["SHEETS_DISCLOSURE_EXPIRED"]
