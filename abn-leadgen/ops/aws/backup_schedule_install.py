"""Review or install exact dormant backup units; never enables, starts or approves them."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from backup_infrastructure import ACCOUNT, BUCKET

UNIT_ROOT = Path("/etc/systemd/system")
STATE_ROOT = Path("/var/lib/abr-engine")
TMPFILES = Path("/etc/tmpfiles.d/abr-engine-backup.conf")
TMP_CONTENT = "d /var/lib/abr-engine/backup-staging 0700 abr-engine abr-engine -\nd /var/lib/abr-engine/backup-receipts 0700 abr-engine abr-engine -\n"
native_os: Any = os  # Linux-only installer primitives are absent from Windows type stubs.


class ScheduleError(ValueError):
    pass


def units():
    values = {}
    for name, operation, calendar in (("daily", "create", "*-*-* 02:00:00 UTC"),
            ("ledger", "worker", "*-*-* *:0/4:00 UTC"), ("expiry", "expire", "*-*-* 03,15:00:00 UTC")):
        base = "abr-engine-backup-" + name
        args = (f"{operation} --config /etc/abr-engine/pilot.yaml --authority /etc/abr-engine/backup/authority.json "
            "--aws-cli /usr/local/bin/aws --public-key /etc/abr-engine/backup/public-recipient.pem "
            "--staging /var/lib/abr-engine/backup-staging --receipts /var/lib/abr-engine/backup-receipts "
            f"--bucket {BUCKET} --account-id {ACCOUNT}")
        if operation == "create":
            args += " --pg-bin /usr/lib/postgresql/16/bin"
        values[base + ".service"] = f"""[Unit]
Description=Gated ABN {name} backup operation
After=postgresql.service
Requires=postgresql.service
OnFailure=abr-engine-backup-alert.service

[Service]
Type=oneshot
Slice=abr-engine.slice
User=abr-engine
Group=abr-engine
WorkingDirectory=/opt/abn-leadgen
Environment=PYTHONPATH=/opt/abn-leadgen/src
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile=/etc/abr-engine/runtime.env
EnvironmentFile=/etc/abr-engine/backup/identity.env
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
CapabilityBoundingSet=
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths=/var/lib/abr-engine/backup-staging /var/lib/abr-engine/backup-receipts
TasksMax=64
LimitNOFILE=2048
MemoryMax={"2G" if name == "daily" else "512M"}
ExecStart=/opt/abn-leadgen/.venv/bin/python /opt/abn-leadgen/ops/aws/backup_cli.py {args}
TimeoutStartSec={"30min" if name == "daily" else "10min"}
"""
        poll = "OnBootSec=30s\nOnUnitActiveSec=15s\n" if name == "ledger" else ""
        values[base + ".timer"] = f"""[Unit]
Description=Separately enabled ABN {name} backup schedule

[Timer]
OnCalendar={calendar}
{poll}Persistent=true
AccuracySec=1s
RandomizedDelaySec=0
Unit={base}.service

[Install]
WantedBy=timers.target
"""
    values["abr-engine-backup-alert.service"] = """[Unit]
Description=Record local ABN backup failure alarm

[Service]
Type=oneshot
User=abr-engine
Group=abr-engine
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
RestrictAddressFamilies=AF_UNIX
ExecStart=/usr/bin/logger --priority daemon.err --tag abr-backup ABN-backup-operation-failed-inspect-private-receipts
"""
    return values


def run(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise ScheduleError("BACKUP_SCHEDULE_SYSTEMD_UNCONFIRMED")
    return result.stdout.strip()


def ordinary(path):
    if not path.is_absolute() or ".." in path.parts or any(item.is_symlink() for item in (path, *path.parents)):
        raise ScheduleError("BACKUP_SCHEDULE_PATH_REFUSED")
    if path.exists():
        info = path.stat()
        if (info.st_uid != 0 or info.st_mode & 0o022
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
            raise ScheduleError("BACKUP_SCHEDULE_OWNERSHIP_REFUSED")


def inactive(name):
    # show has a successful, explicit LoadState=not-found for new units.
    result = run(["systemctl", "show", name, "--property=ActiveState,UnitFileState", "--no-pager"])
    fields = dict(line.split("=", 1) for line in result.splitlines() if "=" in line)
    if fields.get("ActiveState") not in {"inactive", "failed"} or fields.get("UnitFileState", "") not in {"", "disabled", "static"}:
        raise ScheduleError("BACKUP_SCHEDULE_MUST_REMAIN_DISABLED")


def publish(path, content):
    ordinary(path.parent)
    ordinary(path)
    data = content.encode()
    if path.exists():
        if not path.is_file() or path.stat().st_nlink != 1 or path.read_bytes() != data:
            raise ScheduleError("EXISTING_BACKUP_SCHEDULE_DIFFERS")
        return
    temporary = path.with_name(".backup-unit-" + uuid4().hex)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | native_os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as output:
            native_os.fchmod(output.fileno(), 0o644)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            ordinary(path)
            if not path.is_file() or path.stat().st_nlink != 1 or path.read_bytes() != data:
                raise ScheduleError("EXISTING_BACKUP_SCHEDULE_DIFFERS") from None
        temporary.unlink()
        parent = os.open(path.parent, os.O_RDONLY | native_os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def install():
    if os.name != "posix" or getattr(os, "geteuid", lambda: -1)() != 0:
        raise ScheduleError("BACKUP_SCHEDULE_LINUX_ROOT_REQUIRED")
    import pwd
    native_pwd: Any = pwd
    identity = native_pwd.getpwnam("abr-engine")
    for directory in (UNIT_ROOT, TMPFILES.parent):
        ordinary(directory)
        if not directory.is_dir():
            raise ScheduleError("BACKUP_SCHEDULE_HOST_REQUIRED")
    # Private work directories may only be created, or reused with exact identity/mode.
    if not STATE_ROOT.is_dir() or any(item.is_symlink() for item in (STATE_ROOT, *STATE_ROOT.parents)):
        raise ScheduleError("BACKUP_SCHEDULE_HOST_REQUIRED")
    for name in ("backup-staging", "backup-receipts"):
        directory = STATE_ROOT / name
        if directory.is_symlink():
            raise ScheduleError("BACKUP_SCHEDULE_PATH_REFUSED")
        if directory.exists() and (not directory.is_dir() or directory.stat().st_uid != identity.pw_uid
                or directory.stat().st_gid != identity.pw_gid or stat.S_IMODE(directory.stat().st_mode) != 0o700):
            raise ScheduleError("BACKUP_SCHEDULE_PRIVATE_DIRECTORY_MISMATCH")
    values = units()
    for name in values:
        inactive(name)
        ordinary(UNIT_ROOT / name)
        if (UNIT_ROOT / name).exists() and (UNIT_ROOT / name).read_text() != values[name]:
            raise ScheduleError("EXISTING_BACKUP_SCHEDULE_DIFFERS")
    ordinary(TMPFILES)
    if TMPFILES.exists() and TMPFILES.read_text() != TMP_CONTENT:
        raise ScheduleError("EXISTING_BACKUP_SCHEDULE_DIFFERS")
    for name, content in values.items():
        publish(UNIT_ROOT / name, content)
    publish(TMPFILES, TMP_CONTENT)
    run(["systemd-analyze", "verify", *[str(UNIT_ROOT / name) for name in values]])
    run(["systemd-tmpfiles", "--create", str(TMPFILES)])
    for name in ("backup-staging", "backup-receipts"):
        directory = STATE_ROOT / name
        if (directory.is_symlink() or not directory.is_dir() or directory.stat().st_uid != identity.pw_uid
                or directory.stat().st_gid != identity.pw_gid or stat.S_IMODE(directory.stat().st_mode) != 0o700):
            raise ScheduleError("BACKUP_SCHEDULE_PRIVATE_DIRECTORY_MISMATCH")
    run(["systemctl", "daemon-reload"])
    for name in values:
        inactive(name)
    return {"status": "backup_schedules_installed_disabled", "units": list(values),
        "runtime_capabilities_enabled": [], "release_approvals_created": False, "provider_operations": 0,
        "external_alerts_configured": False, "local_failure_alarm": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-disabled", action="store_true")
    args = parser.parse_args()
    if not args.install_disabled:
        print(json.dumps({"status": "review_only", "units": {name: hashlib.sha256(value.encode()).hexdigest()
            for name, value in units().items()}, "provider_operations": 0, "services_enabled": False}))
        return 0
    try:
        print(json.dumps(install()))
        return 0
    except Exception:  # noqa: BLE001 -- no native diagnostics may reflect configuration material
        print(json.dumps({"status": "held", "code": "BACKUP_SCHEDULE_INSTALLATION_UNCONFIRMED", "services_enabled": False}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
