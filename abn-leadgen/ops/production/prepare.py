"""Prepare and verify a gated single-host release; never provision a host or approve a gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, field_validator

from abr_engine.ops.capacity import CapacityPlan

ROOT = Path(__file__).resolve().parents[2]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(ClosedModel):
    record_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    checked_at: AwareDatetime
    expires_at: AwareDatetime


class Host(ClosedModel):
    hostname: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
    provider: str = Field(min_length=1, max_length=100)
    region: str = Field(min_length=1, max_length=100)
    country: Literal["AU"]
    residency: Evidence


class Capacity(ClosedModel):
    remaining_downloads: int | None = Field(default=None, ge=0)
    staged_parquet_upper_bound: int | None = Field(default=None, ge=0)
    prior_snapshot_bytes: int | None = Field(default=None, ge=0)
    new_snapshot_upper_bound: int | None = Field(default=None, ge=0)
    configured_spill_limit: int | None = Field(default=None, ge=0)
    projected_db_growth: int | None = Field(default=None, ge=0)
    projected_wal_growth: int | None = Field(default=None, ge=0)
    temporary_backup_bytes: int | None = Field(default=None, ge=0)
    existing_allocations: dict[str, int] = Field(default_factory=dict)
    measurement: Evidence | None = None


class Plan(ClosedModel):
    schema_version: Literal[1] = 1
    deployment_id: UUID
    mode: Literal["pilot", "production"] = "pilot"
    service_user: str = Field(default="abr-engine", pattern=r"^[a-z_][a-z0-9_-]{0,30}$")
    install_root: str = "/opt/abn-leadgen"
    state_root: str = "/var/lib/abr-engine"
    config_path: str = "/etc/abr-engine/config.yaml"
    environment_path: str = "/etc/abr-engine/runtime.env"
    plan_path: str = "/etc/abr-engine/deployment-plan.json"
    manifest_path: str = "/etc/abr-engine/deployment-manifest.json"
    backup_receipt_path: str = "/var/lib/abr-engine/receipts/latest-backup.json"
    host: Host | None = None
    capacity: Capacity = Field(default_factory=Capacity)
    egress_firewall: Evidence | None = None
    backup_contract: Evidence | None = None
    quarantine_restore_drill: Evidence | None = None
    linux_scheduler_drill: Evidence | None = None

    @field_validator("install_root", "state_root", "config_path", "environment_path", "plan_path", "manifest_path", "backup_receipt_path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        if (not re.fullmatch(r"/[A-Za-z0-9_./-]+", value) or ".." in PurePosixPath(value).parts
                or str(PurePosixPath(value)) != value or value in {"/", "/etc", "/var", "/opt", "/srv", "/usr", "/run"}):
            raise ValueError("A scoped absolute POSIX path without shell or systemd expansions is required")
        return value

    @field_validator("service_user")
    @classmethod
    def non_root(cls, value: str) -> str:
        if value in {"root", "nobody"}:
            raise ValueError("Dedicated non-root account required")
        return value


class BackupComponent(ClosedModel):
    kind: Literal["database", "artifacts", "suppression_erasure_ledger"]
    object_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    encrypted_bytes: int = Field(gt=0)


class BackupReceipt(ClosedModel):
    schema_version: Literal[1] = 1
    deployment_id: UUID
    backup_id: UUID
    status: Literal["complete"]
    country: Literal["AU"]
    encryption: Literal["encrypted_separate_key_custody"]
    completed_at: AwareDatetime
    expires_at: AwareDatetime
    ledger_watermark: AwareDatetime
    provider_evidence: Evidence
    components: list[BackupComponent] = Field(min_length=3, max_length=3)


def now() -> datetime:
    return datetime.now(UTC)


def load_model(filename: Path, model):
    # Only the non-secret plan, manifest and redacted backup receipt are read here.
    # Config/EnvironmentFile/key stores are never read or echoed by this tool.
    if filename.stat().st_size > 65536:
        raise ValueError("Bounded document required")
    return model.model_validate_json(filename.read_bytes())


def current_evidence(evidence: Evidence | None, instant: datetime) -> bool:
    return bool(evidence and evidence.checked_at <= instant < evidence.expires_at
                and evidence.checked_at < evidence.expires_at)


def reject_private_inventory_file(path: Path, *, directory: bool = False) -> None:
    """Check names only, before reading any candidate release artifact."""
    name, suffix = path.name.lower(), path.suffix.lower()
    private_name = re.search(
        r"(?:^|[._-])(?:secrets?|credentials?|private(?:[._-]?keys?)?|keys?|key[._-]?stores?|"
        r"service[._-]?accounts?)(?:[._-]|$)", name)
    source_suffixes = {".py", ".js", ".ts", ".md", ".sh", ".ps1", ".gs"}
    if (name.startswith(".env") or re.search(r"\.env(?:\.|$)", name)
            or suffix in {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore", ".enc", ".der"}
            or name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
            or (private_name and (directory or suffix not in source_suffixes))):
        raise ValueError("Private files are not permitted in the release inventory")


def validate_inventory_path(path: Path, root: Path, *, directory: bool = False) -> None:
    """Reject lexical private parents and links before following or reading a path."""
    relative = path.relative_to(root)
    candidates = [root, *(root.joinpath(*relative.parts[:index + 1]) for index in range(len(relative.parts)))]
    for index, candidate in enumerate(candidates):
        if index:
            reject_private_inventory_file(candidate, directory=directory or index < len(candidates) - 1)
        info = candidate.lstat()
        # Windows junctions and other reparse points need a check beyond S_ISLNK.
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked or reparse paths are not permitted in the release inventory")


def source_inventory(root: Path = ROOT) -> dict:
    def walk_error(error: OSError) -> None:
        raise error

    inventory = {}
    for directory in ("src", "migrations", "templates", "integrations", "ops/production"):
        base = root / directory
        try:
            validate_inventory_path(base, root, directory=True)
        except FileNotFoundError:
            continue
        for current, directories, files in os.walk(base, followlinks=False, onerror=walk_error):
            for child in directories:
                validate_inventory_path(Path(current) / child, root, directory=True)
            directories[:] = sorted(name for name in directories if name != "__pycache__")
            for filename in sorted(files):
                path = Path(current) / filename
                validate_inventory_path(path, root)
                if path.is_file() and path.suffix not in {".pyc", ".log"}:
                    inventory[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("uv.lock", "pyproject.toml", ".python-version", "config/qualification.yaml"):
        validate_inventory_path(root / name, root)
        inventory[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()
    return {"code_tree_sha256": digest, "lockfile_sha256": inventory["uv.lock"], "files": inventory}


def plan_blockers(plan: Plan, instant: datetime) -> list[str]:
    blockers = []
    if plan.host is None:
        blockers.append("PROVISIONED_AU_HOST_REQUIRED")
    elif not current_evidence(plan.host.residency, instant):
        blockers.append("AU_HOST_RESIDENCY_EVIDENCE_REQUIRED")
    for name in ("egress_firewall", "backup_contract", "quarantine_restore_drill", "linux_scheduler_drill"):
        if not current_evidence(getattr(plan, name), instant):
            blockers.append(name.upper() + "_EVIDENCE_REQUIRED")
    try:
        CapacityPlan.model_validate(plan.capacity.model_dump(exclude={"measurement"})).required_free_bytes()
    except ValueError:
        blockers.append("CAPACITY_BOUNDS_UNKNOWN")
    if not current_evidence(plan.capacity.measurement, instant):
        blockers.append("CAPACITY_MEASUREMENT_REQUIRED")
    return sorted(set(blockers + plan_path_blockers(plan)))


def plan_path_blockers(plan: Plan) -> list[str]:
    blockers = []
    install, state = PurePosixPath(plan.install_root), PurePosixPath(plan.state_root)
    if not install.is_relative_to("/opt") and not install.is_relative_to("/srv"):
        blockers.append("INSTALL_ROOT_MUST_BE_SCOPED_OPT_OR_SRV")
    if not state.is_relative_to("/var/lib") or state == PurePosixPath("/var/lib"):
        blockers.append("STATE_ROOT_MUST_BE_SCOPED_VAR_LIB")
    if install.is_relative_to(state) or state.is_relative_to(install):
        blockers.append("CODE_AND_WRITABLE_STATE_MUST_BE_SEPARATE")
    for field in ("config_path", "environment_path", "plan_path", "manifest_path"):
        target = PurePosixPath(getattr(plan, field))
        if target.is_relative_to(install) or target.is_relative_to(state):
            blockers.append("PRIVATE_CONFIGURATION_MUST_BE_OUTSIDE_CODE_AND_BACKUPS")
    if not PurePosixPath(plan.backup_receipt_path).is_relative_to(state):
        blockers.append("BACKUP_RECEIPT_MUST_BE_IN_STATE_ROOT")
    return sorted(set(blockers))


def backup_blockers(receipt: BackupReceipt, plan: Plan, instant: datetime) -> list[str]:
    blockers = []
    if receipt.deployment_id != plan.deployment_id:
        blockers.append("BACKUP_DEPLOYMENT_MISMATCH")
    if receipt.completed_at > instant or instant - receipt.completed_at > timedelta(hours=24):
        blockers.append("BACKUP_MISSING_OR_OLDER_THAN_24_HOURS")
    if not receipt.completed_at < receipt.expires_at <= receipt.completed_at + timedelta(days=35):
        blockers.append("BACKUP_RETENTION_EXCEEDS_35_DAYS")
    if instant >= receipt.expires_at:
        blockers.append("BACKUP_EXPIRED")
    if not receipt.completed_at - timedelta(minutes=5) <= receipt.ledger_watermark <= receipt.completed_at:
        blockers.append("BACKUP_LEDGER_CAPTURE_NOT_CURRENT")
    if {item.kind for item in receipt.components} != {"database", "artifacts", "suppression_erasure_ledger"}:
        blockers.append("BACKUP_COMPONENT_COVERAGE_INCOMPLETE")
    if not current_evidence(receipt.provider_evidence, instant):
        blockers.append("BACKUP_PROVIDER_EVIDENCE_EXPIRED")
    return blockers


def render_units(plan: Plan, tree_sha256: str) -> dict[str, str]:
    cli = plan.install_root + "/.venv/bin/abr-engine"
    python = plan.install_root + "/.venv/bin/python"
    preparer = plan.install_root + "/ops/production/prepare.py"
    preflight = f"{python} {preparer} check --plan {plan.plan_path} --manifest {plan.manifest_path}"
    common = f"""User={plan.service_user}
Group={plan.service_user}
WorkingDirectory={plan.install_root}
EnvironmentFile={plan.environment_path}
RuntimeDirectory=abr-engine
RuntimeDirectoryPreserve=yes
StateDirectory={PurePosixPath(plan.state_root).relative_to('/var/lib') if PurePosixPath(plan.state_root).is_relative_to('/var/lib') else 'abr-engine'}
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
ReadWritePaths={plan.state_root} /run/abr-engine
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
"""
    units = {}
    # An ABR timer cannot be accidentally enabled from a QBCC-only pilot bundle.
    for source in (("abr", "qbcc") if plan.mode == "production" else ("qbcc",)):
        units[f"abr-live-{source}.service"] = f"""# Prepared code tree: {tree_sha256}; uninstalled and release-gated.
[Unit]
Description=Maintain Media {source.upper()} controlled source run
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
{common}ExecStartPre={preflight}
ExecStart=/usr/bin/flock -n -E 4 /run/abr-engine/pipeline.lock {cli} run --source {source} --config {plan.config_path} --mode {plan.mode}
SuccessExitStatus=4
TimeoutStartSec=6h
MemoryMax=2G
CPUQuota=200%
"""
        calendar = "*-*-* 00,06,12,18:00:00 UTC" if source == "abr" else "Mon *-*-* 00:00:00 UTC"
        units[f"abr-live-{source}.timer"] = f"""[Unit]
Description=Maintain Media {source.upper()} controlled discovery schedule
Conflicts=abr-engine-{source}.timer

[Timer]
OnCalendar={calendar}
Persistent=true
RandomizedDelaySec=120
Unit=abr-live-{source}.service

[Install]
WantedBy=timers.target
"""
    commands = {
        "monitor": (f"{cli} alarms check --config {plan.config_path} --mode {plan.mode}", "*-*-* *:*:00 UTC", "120", "512M"),
        "qbcc-review-cleanup": (f"{cli} sources cleanup-qbcc-review --config {plan.config_path} --execute", "*-*-* 03:05:00 UTC", "1h", "512M"),
        "retention": (f"{cli} retention run --execute --config {plan.config_path} --mode {plan.mode}", "*-*-* 03:20:00 UTC", "1h", "2G"),
    }
    for name, (command, calendar, timeout, memory) in commands.items():
        service_preflight = preflight + (" --scope monitor" if name in {"monitor", "qbcc-review-cleanup"} else "")
        units[f"abr-live-{name}.service"] = f"""[Unit]
Description=Maintain Media controlled {name}
After=postgresql.service

[Service]
Type=oneshot
{common}ExecStartPre={service_preflight}
ExecStart={command}
TimeoutStartSec={timeout}
MemoryMax={memory}
"""
        units[f"abr-live-{name}.timer"] = f"""[Unit]
Description=Maintain Media controlled {name} schedule
{('Conflicts=abr-engine-monitor.timer' + chr(10)) if name == 'monitor' else ''}
[Timer]
OnCalendar={calendar}
Persistent=true
Unit=abr-live-{name}.service

[Install]
WantedBy=timers.target
"""
    units["abr-live-api.service"] = f"""[Unit]
Description=Maintain Media private control API (live implementation required)
After=network-online.target postgresql.service
StartLimitIntervalSec=120
StartLimitBurst=3

[Service]
Type=simple
{common}ExecStartPre={preflight}
ExecStart={cli} serve --port 8766 --config {plan.config_path} --mode {plan.mode}
Restart=on-failure
RestartSec=10
TimeoutStartSec=120
MemoryMax=512M

[Install]
WantedBy=multi-user.target
"""
    units["abr-live-backup-check.service"] = f"""[Unit]
Description=Verify independently created AU backup receipt (does not create backups)

[Service]
Type=oneshot
{common}ExecStart={python} {preparer} verify-backup --plan {plan.plan_path} --receipt {plan.backup_receipt_path}
TimeoutStartSec=30
MemoryMax=256M
"""
    units["abr-live-backup-check.timer"] = """[Unit]
Description=Verify current AU backup coverage every hour

[Timer]
OnCalendar=*-*-* *:15:00 UTC
Persistent=true
Unit=abr-live-backup-check.service

[Install]
WantedBy=timers.target
"""
    return units


def root_owned_read_only(paths: list[Path]) -> bool:
    """Validate file and directory metadata, including every writable ancestor."""
    inspected: set[Path] = set()
    try:
        for path in paths:
            resolved = path.resolve(strict=True)
            for candidate in (path, *path.parents, resolved, *resolved.parents):
                if candidate in inspected:
                    continue
                inspected.add(candidate)
                info = candidate.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    return False
        return True
    except OSError:
        return False


def release_ownership_blockers(plan: Plan, inventory: dict) -> list[str]:
    """Metadata only for private configuration; never load its contents."""
    blockers = []
    private_files = [Path(name) for name in
                     (plan.config_path, plan.environment_path, plan.plan_path, plan.manifest_path)]
    for path in private_files:
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o037:
                blockers.append("PRIVATE_CONFIGURATION_PERMISSIONS_REQUIRED")
            if not os.access(path, os.R_OK):
                blockers.append("PRIVATE_CONFIGURATION_NOT_READABLE_BY_SERVICE")
        except OSError:
            blockers.append("PRIVATE_CONFIGURATION_NOT_PROVISIONED")
    if not root_owned_read_only(private_files):
        blockers.append("ROOT_OWNED_PRIVATE_CONFIGURATION_REQUIRED")
    code = Path(plan.install_root)
    venv = code / ".venv"
    # Locked metadata alone does not stop a writable installed dependency changing code.
    code_files = [code / name for name in inventory["files"]]
    try:
        dependencies = list(venv.rglob("*"))
        if any(path.is_symlink() and path.is_dir() for path in dependencies):
            blockers.append("EXTERNAL_DEPENDENCY_DIRECTORIES_NOT_SUPPORTED")
        if not root_owned_read_only([code, venv, *code_files, *dependencies]):
            blockers.append("ROOT_OWNED_IMMUTABLE_CODE_REQUIRED")
    except OSError:
        blockers.append("ROOT_OWNED_IMMUTABLE_CODE_REQUIRED")
    return sorted(set(blockers))


def machine_blockers(plan: Plan, instant: datetime, manifest: dict, *, monitor_only: bool = False) -> list[str]:
    # Monitoring must remain able to record expired policy/backup/capacity alarms.
    # It still requires the declared provisioned host, immutable code and private access.
    blockers = plan_path_blockers(plan) if monitor_only else plan_blockers(plan, instant)
    if platform.system() != "Linux":
        blockers.append("TARGET_LINUX_HOST_REQUIRED")
    if plan.host is None or plan.host.hostname.lower() not in {socket.gethostname().lower(), socket.getfqdn().lower()}:
        blockers.append("CURRENT_MACHINE_IS_NOT_PROVISIONED_TARGET")
    if platform.python_version_tuple()[:2] != ("3", "12"):
        blockers.append("PYTHON_312_REQUIRED")
    inventory = source_inventory()
    if manifest.get("code_tree_sha256") != inventory["code_tree_sha256"]:
        blockers.append("RELEASE_CODE_TREE_CHANGED")
    if manifest.get("deployment_id") != str(plan.deployment_id):
        blockers.append("RELEASE_MANIFEST_DEPLOYMENT_MISMATCH")
    if hashlib.sha256(plan.model_dump_json().encode()).hexdigest() != manifest.get("plan_sha256"):
        blockers.append("DEPLOYMENT_PLAN_CHANGED_RECOMPILE_REQUIRED")
    if not Path("/run/systemd/system").is_dir():
        blockers.append("SYSTEMD_HOST_REQUIRED")
    if ROOT.resolve() != Path(plan.install_root).resolve():
        blockers.append("RELEASE_NOT_RUNNING_FROM_DECLARED_INSTALL_ROOT")
    if not Path(plan.state_root).is_dir():
        blockers.append("PRIVATE_STATE_ROOT_NOT_PROVISIONED")
    elif not monitor_only:
        try:
            required = CapacityPlan.model_validate(plan.capacity.model_dump(exclude={"measurement"})).required_free_bytes()
            if shutil.disk_usage(plan.state_root).free < required:
                blockers.append("DISK_CAPACITY_BELOW_BOUNDS_PLUS_25_GIB")
        except ValueError:
            pass  # The precise unknown-capacity blocker is already present.
    if platform.system() == "Linux":
        import pwd

        try:
            # These POSIX APIs are deliberately unavailable on the Windows preparer.
            account = pwd.getpwnam(plan.service_user)  # type: ignore[attr-defined]
            if os.geteuid() != account.pw_uid or account.pw_uid == 0:  # type: ignore[attr-defined]
                blockers.append("DEDICATED_SERVICE_IDENTITY_REQUIRED")
        except KeyError:
            blockers.append("DEDICATED_SERVICE_IDENTITY_NOT_PROVISIONED")
        blockers.extend(release_ownership_blockers(plan, inventory))
        if plan.host and plan.host.hostname.lower() in {socket.gethostname().lower(), socket.getfqdn().lower()}:
            try:
                version = subprocess.run(["/usr/lib/postgresql/16/bin/pg_dump", "--version"], capture_output=True, timeout=5, check=False)
                if version.returncode or not re.search(rb"\b16\.\d+", version.stdout):
                    blockers.append("POSTGRESQL_16_RUNTIME_REQUIRED")
            except (OSError, subprocess.TimeoutExpired):
                blockers.append("POSTGRESQL_16_RUNTIME_REQUIRED")
    if not monitor_only:
        try:
            receipt = load_model(Path(plan.backup_receipt_path), BackupReceipt)
            blockers.extend(backup_blockers(receipt, plan, instant))
        except (OSError, ValueError, ValidationError):
            blockers.append("CURRENT_BACKUP_RECEIPT_REQUIRED")
    return sorted(set(blockers))


def release_check(plan: Plan) -> tuple[list[str], dict]:
    command = [plan.install_root + "/.venv/bin/abr-engine", "release-check", "--config", plan.config_path, "--mode", plan.mode]
    try:
        result = subprocess.run(command, capture_output=True, timeout=60, check=False, shell=False)
        payload = json.loads(result.stdout) if len(result.stdout) <= 65536 else None
        if not isinstance(payload, dict):
            raise TypeError("Invalid release receipt")
        checks = payload.get("checks")
        receipt = {"exit_code": result.returncode, "stdout_sha256": hashlib.sha256(result.stdout).hexdigest()}
        if result.returncode != 0 or payload.get("status") != "ready" or not isinstance(checks, list) or not checks:
            return ["CORE_RELEASE_CHECK_BLOCKED"], receipt
        expected = {"collection", "crm"} | ({"abr"} if plan.mode == "production" else set())
        if (payload.get("configured_mode") != plan.mode or payload.get("target_mode") != plan.mode
                or payload.get("database_authority_available") is not True
                or any(not isinstance(check, dict) or check.get("status") != "ready"
                       or check.get("blockers") != [] or check.get("missing_gates") != [] for check in checks)
                or any(not isinstance(check.get("capability"), str) for check in checks)
                or len(checks) != len(expected)
                or {check.get("capability") for check in checks} != expected):
            return ["CORE_RELEASE_CHECK_INCOMPLETE"], receipt
        return [], receipt
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return ["CORE_RELEASE_CHECK_UNAVAILABLE"], {"status": "unavailable"}


def emit(value: dict, destination: Path | None = None):
    encoded = json.dumps(value, indent=2) + "\n"
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render", help="Write an uninstalled, approval-gated release bundle")
    render.add_argument("--plan", required=True, type=Path)
    render.add_argument("--output", required=True, type=Path)
    check = sub.add_parser("check", help="Check the actual provisioned host plus current core release authority")
    check.add_argument("--plan", required=True, type=Path)
    check.add_argument("--manifest", required=True, type=Path)
    check.add_argument("--receipt", type=Path)
    check.add_argument("--scope", choices=("live", "monitor"), default="live")
    backup = sub.add_parser("verify-backup", help="Validate redacted backup receipt coverage/freshness; does not create or restore backups")
    backup.add_argument("--plan", required=True, type=Path)
    backup.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        plan = load_model(args.plan, Plan)
        instant = now()
        if args.command == "render":
            inventory = source_inventory()
            args.output.mkdir(parents=True, exist_ok=False)
            units = args.output / "systemd"
            units.mkdir()
            for name, content in render_units(plan, inventory["code_tree_sha256"]).items():
                (units / name).write_text(content, encoding="utf-8", newline="\n")
            manifest = {"schema_version": 1, "deployment_id": str(plan.deployment_id), "prepared_at": instant.isoformat(),
                        "status": "prepared_not_deployed", "production_installed": False,
                        "plan_sha256": hashlib.sha256(plan.model_dump_json().encode()).hexdigest(), **inventory,
                        "blockers": plan_blockers(plan, instant) + ["TARGET_HOST_AND_CURRENT_CORE_RELEASE_CHECK_REQUIRED"],
                        "backup_creation": "external_provider_not_implemented_by_this_bundle",
                        "source_and_api_commands": "exist_but_live_implementations_are_release_blockers"}
            (args.output / "deployment-plan.json").write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
            emit(manifest, args.output / "deployment-manifest.json")
            return 0
        if args.command == "verify-backup":
            receipt = load_model(args.receipt, BackupReceipt)
            blockers = backup_blockers(receipt, plan, instant)
            emit({"status": "blocked" if blockers else "receipt_valid", "blockers": blockers,
                  "scope": "Receipt structure and age only; no remote objects read, restore run or backup created.", "production_installed": False})
            return 6 if blockers else 0
        if args.manifest.stat().st_size > 2_000_000:
            raise ValueError("Bounded manifest required")
        manifest = json.loads(args.manifest.read_bytes())
        if not isinstance(manifest, dict):
            raise TypeError("Invalid manifest")
        monitor_only = args.scope == "monitor"
        blockers = machine_blockers(plan, instant, manifest, monitor_only=monitor_only)
        authority = {"status": "not_checked_monitor_scope" if monitor_only else "not_checked_host_prerequisites_blocked"}
        if not blockers and not monitor_only:
            failures, authority = release_check(plan)
            blockers.extend(failures)
        receipt = {"receipt_id": str(uuid4()), "checked_at": instant.isoformat(),
                   "status": "blocked" if blockers else ("host_integrity_ready" if monitor_only else "ready"),
                   "deployment_id": str(plan.deployment_id), "blockers": blockers, "core_release_check": authority,
                   "production_installed": False, "source_or_vendor_requests": 0,
                   "scope": "monitor_host_integrity_only" if monitor_only else "host_and_current_release_authority"}
        emit(receipt, args.receipt)
        return 6 if blockers else 0
    except (OSError, ValueError, TypeError, ValidationError):
        emit({"status": "blocked", "code": "DEPLOYMENT_INPUT_OR_ARTIFACT_INVALID", "production_installed": False})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
