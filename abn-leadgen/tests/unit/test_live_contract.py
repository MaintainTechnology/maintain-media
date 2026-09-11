"""Non-secret installation boundaries without database or external sockets."""
import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import yaml

from abr_engine.control.service import DomainError
from abr_engine.export.gohighlevel import FIELD_NAMES, workflow_inventory_digest
from abr_engine.export.live_contract import CHECKS, read_installation


@pytest.fixture
def packet(tmp_path):
    now = datetime.now(UTC)
    config = {"location_id": "syntheticLocation", "mapping_version": "synthetic-v1",
              "field_ids": {name: "live_" + name for name in FIELD_NAMES}, "allow_writes": True,
              "allowed_channels": ["email", "phone"],
              "workflow_inventory_sha256": workflow_inventory_digest({"workflows": []}, "syntheticLocation"),
              "group_search_field": "customFields.live_group_id"}
    config_file, installation_file = tmp_path / "config.yaml", tmp_path / "installation.yaml"
    config_file.write_text(yaml.safe_dump(config), encoding="utf-8")
    installation = {"schema_version": 1, "provider": "gohighlevel", "environment": "pilot",
        "location_id": config["location_id"], "config_sha256": hashlib.sha256(config_file.read_bytes()).hexdigest(),
        "approved_by": "synthetic-reviewer", "verified_at": now.isoformat(),
        "expires_at": (now+timedelta(days=1)).isoformat(), "checks": {name: {"passed": True,
        "evidence_ref": "synthetic-contract-test", "evidence_sha256": "a"*64} for name in CHECKS}}
    installation_file.write_text(yaml.safe_dump(installation), encoding="utf-8")
    settings = SimpleNamespace(mode="pilot", ghl_config_file=config_file, ghl_installation_file=installation_file)
    return settings, installation


def test_exact_hash_and_real_mapping_id_packet(packet):
    settings, _ = packet
    config, receipt, checksum = read_installation(settings)
    assert config.location_id == receipt.location_id == "syntheticLocation"
    assert checksum == hashlib.sha256(settings.ghl_installation_file.read_bytes()).hexdigest()


@pytest.mark.parametrize("change", [
    {"checks": {}}, {"approved_by": " "}, {"provider": "other"},
    {"location_id": "wrongLocation"}, {"environment": "production"},
    {"config_sha256": "b"*64}, {"verified_at": "2026-09-01T00:00:00"},
    {"expires_at": "2020-01-01T00:00:00Z"}, {"invented_approval_flag": True},
])
def test_missing_mismatched_and_unbounded_evidence_rejected(packet, change):
    settings, receipt = packet
    settings.ghl_installation_file.write_text(yaml.safe_dump({**receipt, **change}), encoding="utf-8")
    with pytest.raises(DomainError, match="CRM_INSTALLATION_INVALID"):
        read_installation(settings)


def test_unverified_check_cannot_be_activated(packet):
    settings, receipt = packet
    receipt["checks"]["workflow_isolation"]["passed"] = False
    settings.ghl_installation_file.write_text(yaml.safe_dump(receipt), encoding="utf-8")
    with pytest.raises(DomainError, match="CRM_INSTALLATION_INVALID"):
        read_installation(settings)


def test_env_named_input_is_never_read(packet, monkeypatch):
    settings, _ = packet
    settings.ghl_config_file = settings.ghl_config_file.with_name(".env.yaml")
    # A nonexistent .env file must be rejected by its name, before reading it.
    with pytest.raises(DomainError, match="CRM_INSTALLATION_INVALID"):
        read_installation(settings)


def test_missing_paths_cannot_select_fixture_or_ambient_credentials():
    with pytest.raises(DomainError, match="CRM_INSTALLATION_MISSING"):
        read_installation(SimpleNamespace(mode="pilot"))
