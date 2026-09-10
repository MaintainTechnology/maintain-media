#!/usr/bin/env python3
"""Explicit, bounded bootstrap of one fresh Ubuntu 24.04 host; no engine startup."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

import host_contract as c

PG_TEXT = "# Managed ABR host foundation.\nlisten_addresses = '127.0.0.1'\nport = 5432\npassword_encryption = 'scram-sha-256'\n"


def emit(stage: str) -> None:
    print(json.dumps({"stage": stage, "live_engine_enabled": False}), flush=True)


def managed_file(path: Path, text: str, *, gid: int = 0, mode: int = 0o600) -> bool:
    """Install only new managed files; never overwrite foreign or changed content."""
    c.no_links(path)
    if path.exists():
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != gid
                or stat.S_IMODE(info.st_mode) != mode or info.st_size > 4096
                or path.read_text(encoding="utf-8") != text):
            raise c.HostError("MANAGED_FILE_CHANGED_REVIEW_REQUIRED")
        return False
    descriptor, temporary = tempfile.mkstemp(prefix=".abr-host-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        os.fchown(descriptor, 0, gid)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def directory(path: Path, uid: int, gid: int, mode: int) -> None:
    c.no_links(path)
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise c.HostError("EXISTING_APPLICATION_CONTENT_REFUSED")
    path.mkdir(mode=mode, exist_ok=True)
    os.chown(path, uid, gid)
    path.chmod(mode)


def admission(operator_ip: str, admin_user: str) -> bool:
    c.platform_check()
    import grp
    import pwd

    c.admin_check(operator_ip, admin_user, require_session=True)
    owned = c.marker_check(operator_ip, admin_user)
    for path in (c.INSTALL, c.CONFIG, c.STATE):
        c.no_links(path)
        if path.exists() and (not owned or not path.is_dir() or any(path.iterdir())):
            raise c.HostError("FRESH_EMPTY_APPLICATION_DIRECTORIES_REQUIRED")
    for path in (c.SSH_CONFIG, c.PG_CONFIG):
        c.no_links(path)
        if path.exists() and not owned:
            raise c.HostError("FOREIGN_MANAGED_CONFIGURATION_REFUSED")
    for lookup in (pwd.getpwnam, grp.getgrnam):
        try:
            lookup(c.SERVICE)
        except KeyError:
            continue
        if not owned:
            raise c.HostError("EXISTING_SERVICE_IDENTITY_REFUSED")
    c.cluster_check(owned=owned)
    if __import__("shutil").which("ufw"):
        c.firewall_rules_check(operator_ip, require_active=False)
    # Ubuntu's fresh cluster initially listens on both localhost families. Allow
    # only this safe default during our own interrupted installation, not in the
    # completed foundation verifier or for a foreign cluster.
    c.inactive_engine_check(allow_owned_postgres_ipv6=owned)
    return owned


def install_ssh_policy(operator_ip: str, admin_user: str) -> None:
    created = managed_file(c.SSH_CONFIG, c.ssh_text(admin_user))
    try:
        c.ssh_check(operator_ip, admin_user)
    except Exception:
        if created:
            c.SSH_CONFIG.unlink()
        raise
    c.command(["systemctl", "reload", "ssh.service"])


def apply(operator_ip: str, admin_user: str) -> None:
    c.platform_check()
    import fcntl
    import grp
    import pwd

    admission(operator_ip, admin_user)
    lock_path = "/run/lock/abr-host-bootstrap.lock"
    with os.fdopen(os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "w") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise c.HostError("ANOTHER_BOOTSTRAP_IS_RUNNING") from None
        # Recheck after acquiring the lock. A second process must not race admission.
        admission(operator_ip, admin_user)
        c.no_links(c.MARKER.parent)
        if not c.MARKER.parent.exists():
            c.MARKER.parent.mkdir(mode=0o700)
        info = c.MARKER.parent.stat()
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
            raise c.HostError("BOOTSTRAP_DIRECTORY_PERMISSIONS_INVALID")
        managed_file(c.MARKER, json.dumps(c.marker_expected(operator_ip, admin_user), sort_keys=True) + "\n")

        emit("installing_distribution_runtime")
        c.command(["apt-get", "update"], timeout=600)
        c.command(["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "--yes", "--no-install-recommends",
                   "python3.12", "python3.12-venv", "postgresql-16", "postgresql-client-16", "ufw"], timeout=1200)
        c.cluster_check(owned=True)
        c.command(["systemctl", "start", "postgresql@16-main.service"])
        c.fresh_database_check()

        emit("preparing_private_identity_and_directories")
        try:
            account = pwd.getpwnam(c.SERVICE)
        except KeyError:
            c.command(["useradd", "--system", "--user-group", "--home-dir", str(c.STATE),
                       "--no-create-home", "--shell", "/usr/sbin/nologin", c.SERVICE])
            account = pwd.getpwnam(c.SERVICE)
        service_group = grp.getgrnam(c.SERVICE)
        if account.pw_uid == 0 or account.pw_gid != service_group.gr_gid or account.pw_shell != "/usr/sbin/nologin":
            raise c.HostError("SERVICE_IDENTITY_CHANGED_REVIEW_REQUIRED")
        directory(c.INSTALL, 0, service_group.gr_gid, 0o750)
        directory(c.CONFIG, 0, service_group.gr_gid, 0o750)
        directory(c.STATE, account.pw_uid, service_group.gr_gid, 0o700)

        emit("restricting_postgresql_to_loopback")
        # root-owned, postgres-group readable: PostgreSQL does not run as root.
        c.no_links(c.PG_CONFIG)
        c.PG_CONFIG.parent.mkdir(mode=0o755, exist_ok=True)
        pg_group = grp.getgrnam("postgres").gr_gid
        managed_file(c.PG_CONFIG, PG_TEXT, gid=pg_group, mode=0o640)
        c.command(["pg_ctlcluster", "16", "main", "restart"])
        c.database_check()

        emit("checking_and_reloading_ssh_policy")
        install_ssh_policy(operator_ip, admin_user)

        emit("restricting_inbound_ssh_to_current_operator")
        c.firewall_rules_check(operator_ip, require_active=False)
        c.command(["ufw", "default", "deny", "incoming"])
        c.command(["ufw", "default", "allow", "outgoing"])
        c.command(["ufw", "default", "deny", "routed"])
        c.command(["ufw", "allow", "from", operator_ip, "to", "any", "port", "22", "proto", "tcp"])
        c.command(["ufw", "--force", "enable"])
        c.firewall_rules_check(operator_ip, require_active=True)
        emit("bootstrap_applied_run_independent_verification_and_second_ssh_login")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-ip", required=True)
    parser.add_argument("--admin-user", default="ubuntu")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        operator_ip, admin_user = c.parameters(args.operator_ip, args.admin_user)
        if not args.apply:
            print(json.dumps({"status": "review_only", "apply_required": True,
                              "scope": "Ubuntu24.04 Python3.12 PostgreSQL16 private identity SSH firewall",
                              "live_engine_enabled": False}))
            return
        apply(operator_ip, admin_user)
    except (c.HostError, OSError) as error:
        # Native errors can contain private paths. Only our bounded codes are shown.
        code = str(error) if isinstance(error, c.HostError) else "HOST_FILESYSTEM_OPERATION_FAILED"
        print(json.dumps({"status": "blocked", "code": code, "live_engine_enabled": False}), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
