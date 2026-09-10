"""Pilot-mode finite deletion requires independent current evidenced approval."""

# ruff: noqa: F811 -- imported fixtures are intentionally injected by pytest.
import hashlib
import json
from datetime import timedelta
from uuid import UUID

import pytest
from psycopg.types.json import Jsonb
from test_live_qbcc import accepted, request_for  # noqa: F401
from test_qbcc_review_stage import live  # noqa: F401

from abr_engine.compliance.retention import (
    erase_profile,
    export_ledger,
    replay_ledger,
    restore_quarantine,
    retention_run,
)
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.live import qbcc


@pytest.fixture
def approved_retention(settings, accepted):
    config, _, keys, _ = accepted
    payload = request_for(settings, config, keys)
    config = config.model_copy(update={"capabilities": {"collection": True, "retention": True}})
    with transaction(settings) as conn:
        service = Service(config, keys)
        lead = qbcc.review_qbcc_licence(conn, service, payload, "synthetic-reviewer")
        now = service.now(conn)
        for gate in ("G1", "G3", "G7"):
            conn.execute(
                "INSERT INTO release_gate VALUES(%s,'pilot','retention',1,'synthetic-retention-approval',%s,'synthetic-owner',%s,%s)",
                (gate, "c" * 64, now - timedelta(minutes=1), now + timedelta(hours=1)),
            )
        conn.execute(
            "INSERT INTO policy VALUES('synthetic-live-retention-policy','approved','pilot','synthetic-only-approval','synthetic-owner',%s,%s,%s)",
            (
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
                Jsonb(
                    {
                        "retention": {
                            "approved": True,
                            "schedule_version": "abr-v4-defaults",
                            "evidence_sha256": "d" * 64,
                            "restore_enabled": True,
                        }
                    }
                ),
            ),
        )
    return config, keys, UUID(lead["group_id"])


def test_positive_pilot_retention_deletes_due_profile_after_collection_withdrawn(
    settings, approved_retention
):
    config, keys, _ = approved_retention
    config = config.model_copy(update={"capabilities": {"retention": True}})
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE scope='collection'")
        conn.execute("UPDATE lead_entity SET last_qualifying_at=clock_timestamp()-interval '181 days'")
        service = Service(config, keys)
        result = retention_run(conn, service, now=service.now(conn), execute=True)
        assert result["profiles"][0]["state"] == "primary_complete"
        assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) n FROM suppression_alias").fetchone()["n"] > 0


@pytest.mark.parametrize(
    "failure", ["capability", "gate", "revoked", "policy", "policy_scope", "hash", "quarantine", "future"]
)
def test_missing_or_revoked_retention_authority_cannot_delete(settings, approved_retention, failure):
    config, keys, group = approved_retention
    if failure == "capability":
        config = config.model_copy(update={"capabilities": {}})
    with transaction(settings) as conn:
        service = Service(config, keys)
        now = service.now(conn)
        if failure == "gate":
            conn.execute("DELETE FROM release_gate WHERE scope='retention' AND gate_name='G1'")
        elif failure == "revoked":
            conn.execute(
                "INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,actor_id,approved_at+interval '1 day',expires_at+interval '1 day' FROM release_gate WHERE scope='retention' AND gate_name='G1'"
            )
        elif failure in ("policy", "policy_scope", "hash"):
            conn.execute(
                "INSERT INTO policy VALUES('synthetic-newer-policy',%s,%s,'synthetic-ref','synthetic-owner',%s,%s,%s)",
                (
                    "withdrawn" if failure == "policy" else "approved",
                    "synthetic" if failure == "policy_scope" else "pilot",
                    now,
                    now + timedelta(hours=1),
                    Jsonb(
                        {
                            "retention": {
                                "approved": True,
                                "schedule_version": "abr-v4-defaults",
                                "evidence_sha256": "not-a-hash" if failure == "hash" else "e" * 64,
                            }
                        }
                    ),
                ),
            )
        elif failure == "quarantine":
            restore_quarantine(conn)
        with pytest.raises(DomainError):
            erase_profile(conn, service, group, now=now + timedelta(days=100) if failure == "future" else now)
        assert conn.execute("SELECT count(*) n FROM lead_entity").fetchone()["n"] == 1


def test_verified_ledger_restore_can_minimise_while_remaining_quarantined(settings, approved_retention):
    config, keys, _ = approved_retention
    with transaction(settings) as conn:
        service = Service(config, keys)
        encrypted = export_ledger(conn, service)
        payload = json.loads(keys.decrypt(encrypted))
        restore_quarantine(conn)
        receipt = replay_ledger(
            conn,
            service,
            encrypted,
            expected_digest=hashlib.sha256(encrypted.encode()).hexdigest(),
            latest_watermark=payload["exported_at"],
        )
        assert receipt["state"] == "ledger_reconciled"
        assert conn.execute("SELECT value FROM system_state WHERE name='restore_quarantine'").fetchone()[
            "value"
        ]
        with pytest.raises(DomainError, match="AUTHORITY_QUARANTINED"):
            retention_run(conn, service, now=service.now(conn), execute=True)
