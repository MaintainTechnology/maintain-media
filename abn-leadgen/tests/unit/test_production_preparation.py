"""Production preparation invariants; all host/core/provider boundaries are fake."""
import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

SCRIPT = Path(__file__).resolve().parents[2] / "ops/production/prepare.py"
spec = importlib.util.spec_from_file_location("production_preparation", SCRIPT)
assert spec and spec.loader
ops = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ops
spec.loader.exec_module(ops)
NOW = datetime(2026, 9, 9, 10, tzinfo=UTC)


def evidence(**changes):
    return {"record_id": str(uuid4()), "sha256": "a" * 64,
            "checked_at": (NOW - timedelta(days=1)).isoformat(),
            "expires_at": (NOW + timedelta(days=1)).isoformat(), **changes}


def plan(**changes):
    payload = {"deployment_id": str(uuid4()), **changes}
    return ops.Plan.model_validate_json(json.dumps(payload))


def complete_plan(**changes):
    capacity = {key: 10 for key in ops.Capacity.model_fields if key not in {"measurement", "existing_allocations"}}
    capacity.update({"measurement": evidence(), "existing_allocations": {"already_on_disk": 100_000}})
    return plan(host={"hostname": "approved-host", "provider": "test-only", "region": "test-au",
                      "country": "AU", "residency": evidence()}, capacity=capacity,
                egress_firewall=evidence(), backup_contract=evidence(), quarantine_restore_drill=evidence(),
                linux_scheduler_drill=evidence(), **changes)


def backup(target, **changes):
    payload = {"deployment_id": str(target.deployment_id), "backup_id": str(uuid4()), "status": "complete",
               "country": "AU", "encryption": "encrypted_separate_key_custody", "completed_at": NOW.isoformat(),
               "expires_at": (NOW + timedelta(days=35)).isoformat(), "ledger_watermark": NOW.isoformat(),
               "provider_evidence": evidence(), "components": [
                   {"kind": kind, "object_id": str(uuid4()), "sha256": "b" * 64, "encrypted_bytes": 100}
                   for kind in ("database", "artifacts", "suppression_erasure_ledger")], **changes}
    return ops.BackupReceipt.model_validate_json(json.dumps(payload))


def manifest(target):
    return {"deployment_id": str(target.deployment_id), "code_tree_sha256": "a" * 64,
            "plan_sha256": hashlib.sha256(target.model_dump_json().encode()).hexdigest()}


def core_payload(mode="pilot"):
    return {"status": "ready", "configured_mode": mode, "target_mode": mode,
            "database_authority_available": True, "checks": [
                {"capability": name, "status": "ready", "missing_gates": [], "blockers": []}
                for name in (["collection", "crm", "abr"] if mode == "production" else ["collection", "crm"])]}


def write_plan(tmp_path, target):
    filename = tmp_path / "plan.json"
    filename.write_text(target.model_dump_json(), encoding="utf-8")
    return filename


@pytest.mark.parametrize("field,value", [
    ("database_url", "must-not-accept-secret"), ("approved_gates", ["G1"]),
    ("environment_path", "/etc/abr-engine/%n.env"), ("install_root", "/opt/../etc/engine"),
    ("config_path", "/etc/abr;touch/file"), ("service_user", "root"), ("service_user", "nobody"),
    ("state_root", "/var/lib/engine/"), ("install_root", "/opt"),
])
def test_plan_rejects_secrets_approval_assertions_and_unsafe_paths(field, value):
    with pytest.raises(ValidationError):
        plan(**{field: value})


def test_example_is_explicitly_incomplete_and_capacity_uses_existing_formula():
    example = ops.load_model(SCRIPT.parent / "deployment-plan.example.json", ops.Plan)
    assert {"PROVISIONED_AU_HOST_REQUIRED", "CAPACITY_BOUNDS_UNKNOWN", "BACKUP_CONTRACT_EVIDENCE_REQUIRED"} <= set(ops.plan_blockers(example, NOW))
    target = complete_plan()
    assert ops.plan_blockers(target, NOW) == []
    measured = ops.CapacityPlan.model_validate(target.capacity.model_dump(exclude={"measurement"}))
    assert measured.required_free_bytes() == 80 + 25 * 1024**3
    changed = target.model_copy(update={"capacity": target.capacity.model_copy(update={"remaining_downloads": None})})
    assert "CAPACITY_BOUNDS_UNKNOWN" in ops.plan_blockers(changed, NOW)


def test_current_evidence_never_accepts_future_or_expired_records():
    for change in ({"checked_at": NOW + timedelta(seconds=1)}, {"expires_at": NOW}):
        item = ops.Evidence.model_validate_json(json.dumps(evidence(**{k: v.isoformat() for k, v in change.items()})))
        assert ops.current_evidence(item, NOW) is False
    target = complete_plan()
    target.host.residency.expires_at = NOW
    assert "AU_HOST_RESIDENCY_EVIDENCE_REQUIRED" in ops.plan_blockers(target, NOW)


def test_code_state_and_private_configuration_are_separate():
    target = plan(config_path="/var/lib/abr-engine/config.yaml", backup_receipt_path="/etc/receipts/backup.json")
    assert {"PRIVATE_CONFIGURATION_MUST_BE_OUTSIDE_CODE_AND_BACKUPS", "BACKUP_RECEIPT_MUST_BE_IN_STATE_ROOT"} <= set(ops.plan_blockers(target, NOW))


def test_pilot_cannot_enable_abr_and_all_live_services_are_explicitly_gated():
    target = plan()
    units = ops.render_units(target, "b" * 64)
    assert len(units) == 11
    assert "abr-live-abr.service" not in units and "abr-live-abr.timer" not in units
    assert "Mon *-*-* 00:00:00 UTC" in units["abr-live-qbcc.timer"]
    for name in ("qbcc", "retention", "api"):
        unit = units[f"abr-live-{name}.service"]
        assert "ExecStartPre=" in unit and " --scope monitor" not in unit
        assert "--config /etc/abr-engine/config.yaml" in unit
        if name != "qbcc":
            assert "--mode pilot" in unit
        assert "User=abr-engine" in unit and "ProtectSystem=strict" in unit
    assert "--scope monitor" in units["abr-live-monitor.service"]
    assert "alarms check --config" in units["abr-live-monitor.service"]
    assert "verify-backup" in units["abr-live-backup-check.service"]
    assert "backup drill" not in "".join(units.values())
    assert "alarms drain" not in "".join(units.values())
    assert "--execute" in units["abr-live-retention.service"]
    production = ops.render_units(plan(mode="production"), "b" * 64)
    assert len(production) == 13
    assert "00,06,12,18:00:00 UTC" in production["abr-live-abr.timer"]
    for name in ("abr", "qbcc"):
        assert "/usr/bin/flock -n -E 4 /run/abr-engine/pipeline.lock" in production[f"abr-live-{name}.service"]
        if name == "abr":
            assert "--mode production" in production[f"abr-live-{name}.service"]
        else:
            assert "live-schedule-weekly --config /etc/abr-engine/config.yaml" in production[f"abr-live-{name}.service"]


@pytest.mark.parametrize("mode", ["pilot", "production"])
def test_qbcc_review_cleanup_has_a_narrow_daily_schedule_independent_of_collection_gates(mode):
    units = ops.render_units(plan(mode=mode), "b" * 64)
    cleanup = units["abr-live-qbcc-review-cleanup.service"]
    assert "ExecStart=/opt/abn-leadgen/.venv/bin/abr-engine sources cleanup-qbcc-review --config /etc/abr-engine/config.yaml --execute\n" in cleanup
    assert "--scope monitor" in cleanup
    assert "--mode" not in cleanup and "--run-id" not in cleanup
    assert "User=abr-engine" in cleanup and "ProtectSystem=strict" in cleanup
    timer = units["abr-live-qbcc-review-cleanup.timer"]
    assert "OnCalendar=*-*-* 03:05:00 UTC" in timer and "Persistent=true" in timer
    assert "Unit=abr-live-qbcc-review-cleanup.service" in timer
    # Narrow intake cleanup does not relax the existing general retention gate.
    assert "--scope monitor" not in units["abr-live-retention.service"]
    assert f"retention run --execute --config /etc/abr-engine/config.yaml --mode {mode}" in units["abr-live-retention.service"]


def test_inventory_includes_qualification_and_excludes_private_config(tmp_path):
    for name in ("uv.lock", "pyproject.toml", ".python-version", "config/qualification.yaml", "src/example.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original", encoding="utf-8")
    secret = tmp_path / "config/secret.yaml"
    secret.write_text("do-not-read", encoding="utf-8")
    first = ops.source_inventory(tmp_path)
    assert "config/qualification.yaml" in first["files"] and "config/secret.yaml" not in first["files"]
    (tmp_path / "config/qualification.yaml").write_text("changed", encoding="utf-8")
    assert ops.source_inventory(tmp_path)["code_tree_sha256"] != first["code_tree_sha256"]


@pytest.mark.parametrize("filename", [".env", ".env.local", "runtime.env", "runtime.env.local",
                                      "private-key.pem", "credentials.json", "production-secrets.yaml",
                                      "key-store.json", "wrapping.key", "id_ed25519"])
def test_inventory_rejects_private_files_before_reading_contents(tmp_path, monkeypatch, filename):
    secret = tmp_path / "integrations" / filename
    secret.parent.mkdir()
    secret.write_text("synthetic-never-read", encoding="utf-8")
    original_read = Path.read_bytes

    def guarded_read(path):
        assert path != secret, "Private inventory content must never be opened"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(ValueError, match="Private files are not permitted"):
        ops.source_inventory(tmp_path)


@pytest.mark.parametrize("filename", ["keys.py", "credential-setup.ps1", "secrets.md", "brand.ttf", "logo.svg", "report.html.j2"])
def test_inventory_preserves_source_modules_documentation_and_static_assets(filename):
    ops.reject_private_inventory_file(Path(filename))


@pytest.mark.parametrize("directory", [".env.d", "credentials", "nested/private-keys", "secrets.py"])
def test_inventory_rejects_sensitive_parent_before_reading_descendants(tmp_path, monkeypatch, directory):
    hidden = tmp_path / "integrations" / directory / "account.json"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("synthetic-never-read", encoding="utf-8")
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("Sensitive parent contents must not be read"))
    with pytest.raises(ValueError, match="Private files are not permitted"):
        ops.source_inventory(tmp_path)


@pytest.mark.parametrize("is_directory,reparse", [(False, False), (True, False), (False, True), (True, True)])
def test_inventory_rejects_file_and_directory_links_before_read_or_descent(tmp_path, monkeypatch, is_directory, reparse):
    # Metadata simulation is portable when Windows does not grant symlink creation.
    linked = tmp_path / "integrations" / ("public" if is_directory else "public.json")
    linked.parent.mkdir()
    if is_directory:
        linked.mkdir()
        (linked / "account.json").write_text("synthetic-never-read", encoding="utf-8")
    else:
        linked.write_text("synthetic-never-read", encoding="utf-8")
    original_lstat = Path.lstat

    def linked_lstat(path):
        if path == linked:
            return SimpleNamespace(st_mode=(stat.S_IFDIR if is_directory else stat.S_IFREG) if reparse else stat.S_IFLNK,
                                   st_file_attributes=0x400 if reparse else 0)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", linked_lstat)
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("Linked inventory content must not be read"))
    with pytest.raises(ValueError, match="Linked or reparse paths"):
        ops.source_inventory(tmp_path)


def test_backup_validates_only_current_complete_deployment_bound_metadata():
    target = plan()
    good = backup(target)
    assert ops.backup_blockers(good, target, NOW) == []
    assert "BACKUP_DEPLOYMENT_MISMATCH" in ops.backup_blockers(good, plan(), NOW)
    for changes, code in [
        ({"completed_at": NOW - timedelta(days=2)}, "BACKUP_MISSING_OR_OLDER_THAN_24_HOURS"),
        ({"completed_at": NOW + timedelta(seconds=1)}, "BACKUP_MISSING_OR_OLDER_THAN_24_HOURS"),
        ({"expires_at": NOW + timedelta(days=36)}, "BACKUP_RETENTION_EXCEEDS_35_DAYS"),
        ({"expires_at": NOW}, "BACKUP_EXPIRED"),
        ({"ledger_watermark": NOW - timedelta(minutes=6)}, "BACKUP_LEDGER_CAPTURE_NOT_CURRENT"),
        ({"ledger_watermark": NOW + timedelta(seconds=1)}, "BACKUP_LEDGER_CAPTURE_NOT_CURRENT"),
    ]:
        assert code in ops.backup_blockers(good.model_copy(update=changes), target, NOW)
    good.components[2].kind = "artifacts"
    assert "BACKUP_COMPONENT_COVERAGE_INCOMPLETE" in ops.backup_blockers(good, target, NOW)
    good.provider_evidence.expires_at = NOW
    assert "BACKUP_PROVIDER_EVIDENCE_EXPIRED" in ops.backup_blockers(good, target, NOW)


@pytest.mark.parametrize("changes", [{"country": "US"}, {"encryption": "unencrypted"}, {"signed_url": "forbidden"}])
def test_backup_rejects_offshore_unencrypted_and_secret_url_fields(changes):
    with pytest.raises(ValidationError):
        backup(plan(), **changes)


def test_windows_or_wrong_host_cannot_invoke_core_release_check(tmp_path, monkeypatch, capsys):
    target = plan()
    filename = write_plan(tmp_path, target)
    record = tmp_path / "manifest.json"
    record.write_text(json.dumps(manifest(target)), encoding="utf-8")
    monkeypatch.setattr(ops.platform, "system", lambda: "Windows")
    monkeypatch.setattr(ops, "source_inventory", lambda: {"code_tree_sha256": "a" * 64, "files": {}})
    monkeypatch.setattr(ops, "release_check", lambda _: pytest.fail("must not contact database on this host"))
    result = ops.main(["check", "--plan", str(filename), "--manifest", str(record)])
    receipt = json.loads(capsys.readouterr().out)
    assert result == 6 and receipt["status"] == "blocked"
    assert {"TARGET_LINUX_HOST_REQUIRED", "CURRENT_MACHINE_IS_NOT_PROVISIONED_TARGET"} <= set(receipt["blockers"])
    assert receipt["source_or_vendor_requests"] == 0 and receipt["production_installed"] is False


def test_manifest_plan_and_code_drift_are_both_rejected(monkeypatch):
    target = plan()
    monkeypatch.setattr(ops.platform, "system", lambda: "Windows")
    monkeypatch.setattr(ops, "source_inventory", lambda: {"code_tree_sha256": "changed", "files": {}})
    record = manifest(target)
    record["plan_sha256"] = "changed"
    failures = ops.machine_blockers(target, NOW, record)
    assert {"RELEASE_CODE_TREE_CHANGED", "DEPLOYMENT_PLAN_CHANGED_RECOMPILE_REQUIRED"} <= set(failures)


def test_monitor_scope_does_not_read_backup_or_depend_on_expired_gates(monkeypatch):
    target = plan()
    monkeypatch.setattr(ops.platform, "system", lambda: "Windows")
    monkeypatch.setattr(ops, "source_inventory", lambda: {"code_tree_sha256": "a" * 64, "files": {}})
    monkeypatch.setattr(ops, "load_model", lambda *_: pytest.fail("monitor must not read backup receipts"))
    failures = ops.machine_blockers(target, NOW, manifest(target), monitor_only=True)
    assert "TARGET_LINUX_HOST_REQUIRED" in failures
    assert "CAPACITY_BOUNDS_UNKNOWN" not in failures and "BACKUP_CONTRACT_EVIDENCE_REQUIRED" not in failures
    assert "CURRENT_BACKUP_RECEIPT_REQUIRED" not in failures


def test_monitor_success_is_never_a_live_release_success(tmp_path, monkeypatch, capsys):
    target = plan()
    filename = write_plan(tmp_path, target)
    record = tmp_path / "manifest.json"
    record.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ops, "machine_blockers", lambda *_, **kw: [] if kw["monitor_only"] else ["test"])
    monkeypatch.setattr(ops, "release_check", lambda _: pytest.fail("monitor never checks live release gates"))
    assert ops.main(["check", "--scope", "monitor", "--plan", str(filename), "--manifest", str(record)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "host_integrity_ready" and receipt["production_installed"] is False


def test_immutable_paths_reject_writable_ancestors_and_service_owned_children(tmp_path, monkeypatch):
    child = tmp_path / "nested/code.py"
    child.parent.mkdir()
    child.write_text("test", encoding="utf-8")
    original_stat = Path.stat

    def fake_stat(path, **kwargs):
        original_stat(path, **kwargs)  # Retain actual existence and symlink resolution behavior.
        bad = path == child.parent
        return SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | (0o775 if bad else 0o755))

    monkeypatch.setattr(Path, "stat", fake_stat)
    assert ops.root_owned_read_only([child]) is False
    monkeypatch.setattr(Path, "stat", lambda path, **_: SimpleNamespace(st_uid=1000 if path == child else 0, st_mode=stat.S_IFREG | 0o644))
    assert ops.root_owned_read_only([child]) is False
    monkeypatch.setattr(Path, "stat", lambda path, **_: SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644))
    assert ops.root_owned_read_only([child]) is True


@pytest.mark.parametrize("mode", ["pilot", "production"])
def test_core_check_uses_exact_supported_command_and_current_mode(mode, monkeypatch):
    target = plan(mode=mode)

    def run(command, **kwargs):
        assert command == ["/opt/abn-leadgen/.venv/bin/abr-engine", "release-check", "--config", "/etc/abr-engine/config.yaml", "--mode", mode]
        assert kwargs["shell"] is False and kwargs["timeout"] == 60
        return subprocess.CompletedProcess(command, 0, json.dumps(core_payload(mode)).encode(), b"")

    monkeypatch.setattr(ops.subprocess, "run", run)
    failures, receipt = ops.release_check(target)
    assert failures == [] and receipt["exit_code"] == 0


@pytest.mark.parametrize("mutation", ["blocked", "wrong_mode", "no_authority", "missing_capability", "duplicate", "unsafe_type", "gate", "empty", "oversized", "malformed"])
def test_core_check_never_accepts_partial_malformed_or_blocked_readiness(mutation, monkeypatch):
    payload = core_payload()
    code = 0
    if mutation == "blocked":
        payload["status"], code = "blocked", 6
    elif mutation == "wrong_mode":
        payload["configured_mode"] = "fixture"
    elif mutation == "no_authority":
        payload["database_authority_available"] = False
    elif mutation == "missing_capability":
        payload["checks"].pop()
    elif mutation == "duplicate":
        payload["checks"].append(payload["checks"][0])
    elif mutation == "unsafe_type":
        payload["checks"][0]["capability"] = []
    elif mutation == "gate":
        payload["checks"][0]["missing_gates"] = ["G1"]
    elif mutation == "empty":
        payload["checks"] = []
    encoded = b"x" * 65537 if mutation == "oversized" else b"password=never-echo" if mutation == "malformed" else json.dumps(payload).encode()
    monkeypatch.setattr(ops.subprocess, "run", lambda *_, **__: subprocess.CompletedProcess([], code, encoded, b"secret-never-echo"))
    failures, receipt = ops.release_check(plan())
    assert failures and "secret" not in json.dumps(receipt) and "password" not in json.dumps(receipt)


def test_core_timeout_is_bounded_and_redacted(monkeypatch):
    def fail(*_, **__):
        raise subprocess.TimeoutExpired("private-command", 60, output=b"private-output")

    monkeypatch.setattr(ops.subprocess, "run", fail)
    assert ops.release_check(plan()) == (["CORE_RELEASE_CHECK_UNAVAILABLE"], {"status": "unavailable"})


def test_render_does_not_overwrite_existing_release_or_claim_installation(tmp_path, monkeypatch, capsys):
    target = plan()
    filename = write_plan(tmp_path, target)
    output = tmp_path / "bundle"
    monkeypatch.setattr(ops, "source_inventory", lambda: {"code_tree_sha256": "a" * 64, "files": {}, "lockfile_sha256": "b" * 64})
    assert ops.main(["render", "--plan", str(filename), "--output", str(output)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "prepared_not_deployed" and receipt["production_installed"] is False
    assert len(list((output / "systemd").glob("*"))) == 11
    original = (output / "deployment-manifest.json").read_bytes()
    assert ops.main(["render", "--plan", str(filename), "--output", str(output)]) == 2
    assert (output / "deployment-manifest.json").read_bytes() == original


def test_document_and_receipt_size_are_bounded(tmp_path):
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * 65537)
    with pytest.raises(ValueError, match="Bounded"):
        ops.load_model(oversized, ops.Plan)
