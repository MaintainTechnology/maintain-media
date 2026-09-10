"""Account-bound live CRM mapping and dated installation authority.

Configuration is not approval. Every live operation reloads the non-secret files
and binds the exact installation bytes to the current G5 database decision.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from abr_engine.compliance.policy import current_gate_evidence, gate_reasons
from abr_engine.control.service import DomainError
from abr_engine.export.crm import load_field_mapping
from abr_engine.export.gohighlevel import GHLConfig, load_config

CHECKS = {"metadata", "group_search", "uncertain_create", "suppression_clear",
          "workflow_isolation", "unrelated_tags", "processor_countries"}


class InstallationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    passed: Literal[True]
    evidence_ref: str = Field(min_length=1, max_length=1000)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Installation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    provider: Literal["gohighlevel"]
    environment: Literal["pilot", "production"]
    location_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_by: str = Field(min_length=1, max_length=200)
    verified_at: datetime
    expires_at: datetime
    checks: dict[str, InstallationCheck]

    @model_validator(mode="after")
    def complete(self):
        if (set(self.checks) != CHECKS or self.verified_at.tzinfo is None
                or self.expires_at.tzinfo is None or self.expires_at <= self.verified_at
                or not self.approved_by.strip()
                or any(not check.evidence_ref.strip() for check in self.checks.values())):
            raise ValueError("Complete dated account-specific installation evidence is required")
        return self


def read_installation(settings) -> tuple[GHLConfig, Installation, str]:
    paths = [getattr(settings, name, None) for name in ("ghl_config_file", "ghl_installation_file")]
    if any(not isinstance(path, Path) or not path.is_absolute() for path in paths):
        raise DomainError("CRM_INSTALLATION_MISSING", 409)
    config_path, receipt_path = cast(list[Path], paths)
    safe_paths = (config_path, receipt_path)
    try:
        if any(path.name.startswith(".env") or path.suffix not in {".yaml", ".yml"}
               or path.stat().st_size > 65_536 for path in safe_paths):
            raise ValueError("Invalid non-secret installation file")
        # Read the config once as bytes; detect replacement during typed loading.
        config_bytes = config_path.read_bytes()
        config = load_config(config_path)
        if config_path.read_bytes() != config_bytes:
            raise ValueError("Configuration changed while loading")
        raw = receipt_path.read_bytes()
        receipt = Installation.model_validate(yaml.safe_load(raw))
        if (receipt.config_sha256 != hashlib.sha256(config_bytes).hexdigest()
                or receipt.location_id != config.location_id
                or receipt.environment != settings.mode or not config.allow_writes):
            raise ValueError("Installation does not match the enabled account contract")
    except (OSError, ValueError, TypeError, ValidationError, yaml.YAMLError):
        raise DomainError("CRM_INSTALLATION_INVALID", 409) from None
    return config, receipt, hashlib.sha256(raw).hexdigest()


def live_contract(conn, service, *, removal_only=False) -> tuple[GHLConfig, dict, str]:
    """Check before I/O; removal never reopens contact authority or needs a live candidate."""
    service.personal_data_access(conn)
    config, receipt, checksum = read_installation(service.settings)
    now = service.now(conn)
    if not receipt.verified_at <= now < receipt.expires_at:
        raise DomainError("CRM_INSTALLATION_EXPIRED", 409)
    reasons = gate_reasons(conn, service.settings, "crm", now)
    # Removing an already exported projection remains possible with acquisition
    # disabled. Hosting and the exact approved vendor account must still be valid.
    if removal_only:
        reasons = [reason for reason in reasons if reason in {"GATE_G3_CLOSED", "GATE_G5_CLOSED"}]
    if reasons:
        raise DomainError("CRM_RELEASE_GATES_CLOSED", 409, {"reasons": reasons})
    gate = conn.execute("SELECT * FROM release_gate WHERE gate_name='G5' AND environment=%s "
                        "AND scope='crm' ORDER BY revision DESC LIMIT 1", (service.settings.mode,)).fetchone()
    if (not gate or not current_gate_evidence(gate, now) or gate["evidence_sha256"] != checksum
            or gate["actor_id"] != receipt.approved_by):
        raise DomainError("CRM_INSTALLATION_NOT_APPROVED", 409)
    if removal_only:
        hosting = conn.execute("SELECT * FROM release_gate WHERE gate_name='G3' AND environment=%s "
                               "AND scope='crm' ORDER BY revision DESC LIMIT 1", (service.settings.mode,)).fetchone()
        if not hosting or not current_gate_evidence(hosting, now):
            raise DomainError("CRM_HOSTING_GATE_CLOSED", 409)
    mapping = load_field_mapping()
    mapping.update(mode=service.settings.mode, live_enabled=True, location_id=config.location_id,
                   mapping_version=config.mapping_version)
    mapping["identity"]["custom_field_id"] = config.field_ids["group_id"]
    for name, field in mapping["fields"].items():
        field["custom_field_id"] = config.field_ids[name]
    return config, mapping, checksum


def selected_mapping(conn, service) -> dict:
    return load_field_mapping() if service.settings.mode == "fixture" else live_contract(conn, service)[1]
