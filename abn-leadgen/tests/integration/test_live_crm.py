"""Pilot-mode authority and real HTTP transport; isolated DB and synthetic vendor only."""
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import yaml
from psycopg.types.json import Jsonb

from abr_engine.compliance.policy import REQUIRED_GATES
from abr_engine.control.service import DomainError, Service, json_safe
from abr_engine.db import transaction
from abr_engine.export.crm import approve, drain_live_one
from abr_engine.export.gohighlevel import FIELD_NAMES
from abr_engine.export.live_contract import CHECKS, live_contract
from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.ops.propagation import drain_propagation


@pytest.fixture
def live_case(settings, service, tmp_path):
    now = datetime.now(UTC)
    config = {"location_id": "syntheticLocation", "mapping_version": "synthetic-live-contract-v1",
              "field_ids": {name: "live_" + name for name in FIELD_NAMES},
              "allow_writes": True, "group_search_field": "customFields.live_group_id"}
    config_path, receipt_path = tmp_path / "ghl.yaml", tmp_path / "installation.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    receipt = {"schema_version": 1, "provider": "gohighlevel", "environment": "pilot",
               "location_id": config["location_id"], "approved_by": "synthetic-owner",
               "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
               "verified_at": (now - timedelta(seconds=10)).isoformat(),
               "expires_at": (now + timedelta(days=1)).isoformat(),
               "checks": {name: {"passed": True, "evidence_ref": "synthetic-isolated-test-only",
                                  "evidence_sha256": "a" * 64} for name in CHECKS}}
    receipt_path.write_text(yaml.safe_dump(receipt), encoding="utf-8")
    checksum = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    with transaction(settings) as conn:
        seed_policy(conn, service)
        record = seed_contact(conn, service)
        worklist, row = uuid4(), uuid4()
        conn.execute("INSERT INTO worklist(worklist_id,week) VALUES(%s,%s)", (worklist, date(2026, 9, 7)))
        gate = service.gate(conn, record["contact"]["contact_id"])
        conn.execute("INSERT INTO worklist_row(row_id,worklist_id,lead_id,decision,selected_tier,selected_signal) "
                     "VALUES(%s,%s,%s,%s,'A','qbcc_backlog')", (row, worklist, record["lead"]["lead_id"], Jsonb(json_safe(gate))))
        for scope in ("collection", "crm"):
            for name in REQUIRED_GATES[scope]:
                conn.execute("INSERT INTO release_gate(gate_name,environment,scope,revision,evidence_ref,evidence_sha256,actor_id,approved_at,expires_at) "
                             "VALUES(%s,'pilot',%s,1,'synthetic-test-only',%s,'synthetic-owner',%s,%s)",
                             (name, scope, checksum if name == "G5" else "a" * 64, now-timedelta(seconds=10), now+timedelta(days=1)))
    live_settings = settings.model_copy(update={"mode": "pilot", "key_file": tmp_path / "unused-test-key",
        "capabilities": {"collection": True, "crm": True}, "ghl_config_file": config_path,
        "ghl_installation_file": receipt_path})
    live_service = Service(live_settings, service.keys)
    with transaction(live_settings) as conn:
        approval = approve(conn, live_service, {"row_id": row, "expected_version": 1,
            "decision": "approve", "reason": "Synthetic live-path test"}, "synthetic-reviewer")
    return {"settings": live_settings, "service": live_service, "record": record, "row": row,
            "outbox": approval["outbox_id"], "config": config, "config_path": config_path,
            "receipt_path": receipt_path}


class Vendor:
    def __init__(self, case):
        self.case, self.remote, self.mutations = case, None, []
        self.timeout_create = False
        self.on_lookup = None
        self.on_update = None
        self.ignore_clear = False

    def __call__(self, request):
        path = request.url.path
        if path == "/contacts/search":
            if self.on_lookup:
                callback, self.on_lookup = self.on_lookup, None
                callback()
            return httpx.Response(200, json={"contacts": [self.remote] if self.remote else [],
                                            "total": int(self.remote is not None)})
        if request.method == "GET":
            return httpx.Response(200, json={"contact": self.remote})
        self.mutations.append((request.method, path))
        body = json.loads(request.content)
        if request.method == "POST" and path == "/contacts/":
            self.remote = {**body, "id": "remote1", "tags": ["customer:retain", *body["tags"]]}
            if self.timeout_create:
                self.timeout_create = False
                raise httpx.ReadTimeout("synthetic uncertain create")
            return httpx.Response(200, json={"contact": self.remote})
        if request.method == "PUT":
            if not self.ignore_clear:
                self.remote.update(body)
            if self.on_update:
                callback, self.on_update = self.on_update, None
                callback()
        elif path.endswith("/tags"):
            tags = set(self.remote["tags"])
            self.remote["tags"] = sorted(tags - set(body["tags"]) if request.method == "DELETE" else tags | set(body["tags"]))
        else:
            raise AssertionError("Unexpected vendor endpoint")
        return httpx.Response(200, json={"succeeded": True})


def drain(case, vendor):
    return drain_live_one(case["settings"], case["service"], case["outbox"],
                          transport=httpx.MockTransport(vendor), environ={"ABR_GHL_TOKEN": "synthetic-token"})


def stop(case):
    with transaction(case["settings"]) as conn:
        case["service"].suppress(conn, {"lead_id": case["record"]["lead"]["lead_id"],
            "reason": "unsubscribe", "source": "synthetic-test"}, "synthetic-reviewer", uuid4())


def propagate(case, vendor):
    return drain_propagation(case["settings"], case["service"], transport=httpx.MockTransport(vendor),
                             environ={"ABR_GHL_TOKEN": "synthetic-token"})


def test_live_create_then_stop_verified_and_unrelated_tags_preserved(live_case):
    vendor = Vendor(live_case)
    assert drain(live_case, vendor)["state"] == "succeeded"
    assert vendor.remote["dnd"] is True
    with transaction(live_case["settings"]) as conn:
        saved = conn.execute("SELECT location_id FROM crm_identity").fetchone()
        assert saved["location_id"] == "syntheticLocation"
    stop(live_case)
    result = propagate(live_case, vendor)
    assert result["mode"] == "pilot" and result["notifications_sent"] == 0
    assert result["results"][0]["state"] == "succeeded"
    assert vendor.remote["name"] is vendor.remote["email"] is vendor.remote["phone"] is None
    assert vendor.remote["tags"] == ["customer:retain", "maintain-media:suppressed"]
    assert all(field["fieldValue"] is None for field in vendor.remote["customFields"]
               if field["id"] != "live_group_id")


def test_live_uncertain_create_reconciles_without_second_create(live_case):
    vendor = Vendor(live_case)
    vendor.timeout_create = True
    assert drain(live_case, vendor)["state"] == "uncertain"
    with transaction(live_case["settings"]) as conn:
        conn.execute("UPDATE crm_outbox SET next_attempt_at=NULL")
    assert drain(live_case, vendor)["state"] == "succeeded"
    assert vendor.mutations == [("POST", "/contacts/")]


def test_live_suppression_during_lookup_blocks_all_writes(live_case):
    vendor = Vendor(live_case)
    vendor.on_lookup = lambda: stop(live_case)
    assert drain(live_case, vendor)["state"] == "blocked"
    assert vendor.mutations == []


def test_mapping_drift_refuses_before_vendor_access(live_case):
    live_case["config_path"].write_text(live_case["config_path"].read_text()+"\n# changed\n")
    with pytest.raises(DomainError, match="CRM_INSTALLATION_INVALID"):
        drain(live_case, lambda _: pytest.fail("Must not access vendor"))


def test_g5_latest_revocation_refuses_before_vendor_access(live_case):
    with transaction(live_case["settings"]) as conn:
        conn.execute("UPDATE release_gate SET expires_at=clock_timestamp()-interval '1 second', "
                     "approved_at=clock_timestamp()-interval '2 seconds' WHERE gate_name='G5'")
    with pytest.raises(DomainError):
        drain(live_case, lambda _: pytest.fail("Must not access vendor"))


def test_live_stop_stays_pending_when_vendor_does_not_clear_fields(live_case):
    vendor = Vendor(live_case)
    assert drain(live_case, vendor)["state"] == "succeeded"
    stop(live_case)
    vendor.ignore_clear = True
    result = propagate(live_case, vendor)
    assert result["results"][0]["state"] == "retry"
    with transaction(live_case["settings"]) as conn:
        row = conn.execute("SELECT completed_at,last_error_code FROM propagation_outbox").fetchone()
        assert row["completed_at"] is None and row["last_error_code"] == "PROPAGATION_UPDATE_UNCONFIRMED"


def test_disabled_collection_does_not_prevent_removal(live_case):
    vendor = Vendor(live_case)
    assert drain(live_case, vendor)["state"] == "succeeded"
    stop(live_case)
    live_case["settings"].capabilities.update(collection=False, crm=False)
    with transaction(live_case["settings"]) as conn:
        live_contract(conn, live_case["service"], removal_only=True)
    assert propagate(live_case, vendor)["results"][0]["state"] == "succeeded"


def test_revocation_between_field_update_and_tags_stops_next_mutation(live_case):
    vendor = Vendor(live_case)
    assert drain(live_case, vendor)["state"] == "succeeded"
    stop(live_case)
    def revoke():
        with transaction(live_case["settings"]) as conn:
            conn.execute("UPDATE release_gate SET expires_at=clock_timestamp()-interval '1 second', "
                         "approved_at=clock_timestamp()-interval '2 seconds' WHERE gate_name='G5'")
    vendor.on_update = revoke
    assert propagate(live_case, vendor)["results"][0]["state"] == "retry"
    assert vendor.mutations == [("POST", "/contacts/"), ("PUT", "/contacts/remote1")]


def test_retry_after_persists_in_durable_schedule(live_case):
    vendor = Vendor(live_case)
    def handler(request):
        if request.method == "POST" and request.url.path == "/contacts/":
            return httpx.Response(429, headers={"Retry-After": "3600"}, json={"error": "not logged"})
        return vendor(request)
    assert drain(live_case, handler)["state"] == "uncertain"
    with transaction(live_case["settings"]) as conn:
        row = conn.execute("SELECT next_attempt_at-clock_timestamp() AS delay FROM crm_outbox").fetchone()
        assert row["delay"].total_seconds() > 3590


def test_current_g5_must_bind_exact_installation_receipt(live_case):
    with transaction(live_case["settings"]) as conn:
        conn.execute("UPDATE release_gate SET evidence_sha256=%s WHERE gate_name='G5'", ("f"*64,))
    with pytest.raises(DomainError, match="CRM_INSTALLATION_NOT_APPROVED"):
        drain(live_case, lambda _: pytest.fail("Must not access vendor"))
