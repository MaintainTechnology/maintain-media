#!/usr/bin/env python3
"""Read-only Ubuntu host foundation receipt; never a live-engine release approval."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import stat
from datetime import UTC, datetime

import host_contract as c


def runtime_check() -> None:
    version = c.command(["python3.12", "-c", "import sys,venv; print('.'.join(map(str,sys.version_info[:2])))"])
    if version != "3.12":
        raise c.HostError("PYTHON_3_12_REQUIRED")
    if not c.command(["/usr/lib/postgresql/16/bin/pg_dump", "--version"]).startswith("pg_dump (PostgreSQL) 16."):
        raise c.HostError("POSTGRESQL_16_CLIENT_REQUIRED")
    if c.command(["systemctl", "is-active", "postgresql@16-main.service"]) != "active":
        raise c.HostError("POSTGRESQL_SERVICE_REQUIRED")


def service_check() -> None:
    import pwd

    account = pwd.getpwnam(c.SERVICE)
    status = c.command(["passwd", "-S", c.SERVICE]).split()
    if (account.pw_uid == 0 or account.pw_shell != "/usr/sbin/nologin" or account.pw_dir != str(c.STATE)
            or len(status) < 2 or status[1] != "L"
            or c.command(["id", "-nG", c.SERVICE]).split() != [c.SERVICE]):
        raise c.HostError("LOCKED_NONLOGIN_SERVICE_IDENTITY_REQUIRED")


def directories_check() -> None:
    import pwd

    account = pwd.getpwnam(c.SERVICE)
    for path, uid, mode in ((c.INSTALL, 0, 0o750), (c.CONFIG, 0, 0o750), (c.STATE, account.pw_uid, 0o700)):
        c.no_links(path)
        info = path.stat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_gid != account.pw_gid
                or stat.S_IMODE(info.st_mode) != mode or any(path.iterdir())):
            raise c.HostError("PRIVATE_EMPTY_DIRECTORY_CONTRACT_FAILED")


def verify(operator_ip: str, admin_user: str) -> dict:
    checks = []

    def check(name, operation):
        try:
            operation()
            checks.append({"name": name, "status": "passed"})
        except (c.HostError, OSError, KeyError) as error:
            code = str(error) if isinstance(error, c.HostError) else "HOST_CHECK_UNAVAILABLE"
            checks.append({"name": name, "status": "failed", "code": code})

    def marker():
        if not c.marker_check(operator_ip, admin_user):
            raise c.HostError("BOOTSTRAP_MARKER_MISSING")

    check("ubuntu_24_04_root_systemd", c.platform_check)
    if checks[-1]["status"] == "passed":
        check("bootstrap_host_and_operator", marker)
        check("existing_admin_key_metadata", lambda: c.admin_check(operator_ip, admin_user, require_session=False))
        check("python_and_postgresql_runtime", runtime_check)
        check("locked_nonlogin_service_identity", service_check)
        check("private_empty_application_directories", directories_check)
        check("single_owned_postgresql_cluster", lambda: c.cluster_check(owned=True))
        check("loopback_postgresql_and_no_application_data", c.database_check)
        check("effective_ssh_key_only_policy", lambda: c.ssh_check(operator_ip, admin_user))
        check("operator_only_ssh_firewall", lambda: c.firewall_rules_check(operator_ip, require_active=True))
        check("no_engine_services_or_public_application_ports", c.inactive_engine_check)
    failed = any(item["status"] != "passed" for item in checks)
    observation = {}
    if not failed:
        observation = {"free_state_disk_bytes": shutil.disk_usage(c.STATE).free,
                       "physical_memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")}
    return {"status": "blocked" if failed else "host_foundation_verified", "checks": checks,
            "checked_at": datetime.now(UTC).isoformat(), "hostname": socket.gethostname(),
            "observed_resources": observation, "capacity_certified": False, "live_engine_enabled": False,
            "source_collection_enabled": False, "backups_installed": False,
            "second_ssh_login_verified": False,
            "scope": "Fresh Ubuntu foundation only; no AWS placement, live data, backup, capacity or release certification."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-ip", required=True)
    parser.add_argument("--admin-user", default="ubuntu")
    args = parser.parse_args()
    try:
        operator_ip, admin_user = c.parameters(args.operator_ip, args.admin_user)
        result = verify(operator_ip, admin_user)
        print(json.dumps(result, indent=2))
        if result["status"] != "host_foundation_verified":
            raise SystemExit(2)
    except c.HostError as error:
        print(json.dumps({"status": "blocked", "code": str(error), "live_engine_enabled": False}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
