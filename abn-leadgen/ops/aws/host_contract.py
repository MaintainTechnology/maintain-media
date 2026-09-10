"""Non-secret Ubuntu foundation checks shared by bootstrap and verification."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import socket
import stat
import subprocess
from pathlib import Path

SERVICE = "abr-engine"
INSTALL = Path("/opt/abn-leadgen")
CONFIG = Path("/etc/abr-engine")
STATE = Path("/var/lib/abr-engine")
MARKER = Path("/var/lib/abr-host-bootstrap/host.json")
SSH_CONFIG = Path("/etc/ssh/sshd_config.d/00-abr-host.conf")
PG_CONFIG = Path("/etc/postgresql/16/main/conf.d/99-abr-loopback.conf")


class HostError(RuntimeError):
    pass


def command(args: list[str], *, timeout: int = 30, check: bool = True) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise HostError("COMMAND_UNAVAILABLE_OR_TIMED_OUT:" + Path(args[0]).name) from None
    if check and result.returncode:
        raise HostError("COMMAND_FAILED:" + Path(args[0]).name)
    return result.stdout.strip()


def parameters(operator_ip: str, admin_user: str) -> tuple[str, str]:
    try:
        address = ipaddress.IPv4Address(operator_ip)
    except ValueError:
        raise HostError("PUBLIC_OPERATOR_IPV4_REQUIRED") from None
    if not address.is_global or str(address) != operator_ip:
        raise HostError("PUBLIC_OPERATOR_IPV4_REQUIRED")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", admin_user) or admin_user in {"root", SERVICE, "postgres"}:
        raise HostError("EXISTING_NONROOT_ADMIN_REQUIRED")
    return operator_ip, admin_user


def no_links(path: Path) -> None:
    for candidate in [*reversed(path.parents), path]:
        if candidate.is_symlink():
            raise HostError("SYMLINK_PATH_REFUSED")


def platform_check() -> None:
    if getattr(os, "geteuid", lambda: -1)() != 0:
        raise HostError("ROOT_REQUIRED")
    values = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip('"')
    if values.get("ID") != "ubuntu" or values.get("VERSION_ID") != "24.04":
        raise HostError("FRESH_UBUNTU_24_04_REQUIRED")
    if not Path("/run/systemd/system").is_dir():
        raise HostError("SYSTEMD_HOST_REQUIRED")


def admin_check(operator_ip: str, admin_user: str, *, require_session: bool) -> None:
    import grp
    import pwd

    if require_session:
        connection = os.environ.get("SSH_CONNECTION", "").split()
        if len(connection) != 4 or connection[0] != operator_ip or connection[3] != "22":
            raise HostError("CURRENT_SSH_CONNECTION_MUST_MATCH_OPERATOR_IPV4_AND_PORT_22")
        if os.environ.get("SUDO_USER") != admin_user:
            raise HostError("RUN_THROUGH_EXISTING_ADMIN_SUDO_SESSION")
    try:
        admin = pwd.getpwnam(admin_user)
    except KeyError:
        raise HostError("EXISTING_NONROOT_ADMIN_REQUIRED") from None
    groups = {grp.getgrgid(group).gr_name for group in os.getgrouplist(admin_user, admin.pw_gid)}
    if admin.pw_uid == 0 or "sudo" not in groups or admin.pw_shell not in {"/bin/bash", "/bin/sh", "/usr/bin/bash"}:
        raise HostError("EXISTING_SUDO_ADMIN_REQUIRED")
    ssh = Path(admin.pw_dir) / ".ssh"
    key = ssh / "authorized_keys"
    for path in (ssh, key):
        no_links(path)
        info = path.stat()
        if info.st_uid != admin.pw_uid or info.st_mode & 0o077:
            raise HostError("ADMIN_SSH_FILE_PERMISSIONS_INVALID")
    if not key.is_file() or key.stat().st_size == 0:
        raise HostError("EXISTING_ADMIN_PUBLIC_KEY_REQUIRED")


def marker_expected(operator_ip: str, admin_user: str) -> dict:
    return {"schema_version": 1, "hostname": socket.gethostname(), "operator_ipv4": operator_ip,
            "admin_user": admin_user, "scope": "ubuntu_host_foundation_only"}


def marker_check(operator_ip: str, admin_user: str) -> bool:
    no_links(MARKER)
    if not MARKER.exists():
        return False
    info = MARKER.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise HostError("BOOTSTRAP_MARKER_PERMISSIONS_INVALID")
    if info.st_size > 4096:
        raise HostError("BOOTSTRAP_MARKER_INVALID")
    try:
        stored = json.loads(MARKER.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise HostError("BOOTSTRAP_MARKER_INVALID") from None
    if stored != marker_expected(operator_ip, admin_user):
        raise HostError("BOOTSTRAP_HOST_OR_OPERATOR_CHANGED_REVIEW_REQUIRED")
    return True


def ssh_text(admin_user: str) -> str:
    return ("# Managed ABR host foundation; no application service is enabled.\n"
            "PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n"
            "PubkeyAuthentication yes\nAuthenticationMethods publickey\nGSSAPIAuthentication no\n"
            "HostbasedAuthentication no\nPermitEmptyPasswords no\nDisableForwarding yes\n"
            "X11Forwarding no\n" + f"AllowUsers {admin_user}\n")


def ssh_check(operator_ip: str, admin_user: str) -> None:
    command(["/usr/sbin/sshd", "-t"])
    expected = {"permitrootlogin": "no", "passwordauthentication": "no", "kbdinteractiveauthentication": "no",
                "pubkeyauthentication": "yes", "permitemptypasswords": "no", "disableforwarding": "yes",
                "authenticationmethods": "publickey", "gssapiauthentication": "no", "hostbasedauthentication": "no",
                "x11forwarding": "no", "allowusers": admin_user, "port": "22"}
    for user in (admin_user, "root"):
        output = command(["/usr/sbin/sshd", "-T", "-C", f"user={user},host=localhost,addr={operator_ip}"])
        values = dict(line.split(" ", 1) for line in output.splitlines() if " " in line)
        if any(values.get(key) != value for key, value in expected.items()):
            raise HostError("EFFECTIVE_SSH_POLICY_MISMATCH")


def firewall_rules_check(operator_ip: str, *, require_active: bool) -> None:
    status = command(["ufw", "status", "verbose"])
    added = [line.strip() for line in command(["ufw", "show", "added"]).splitlines()
             if line.strip().startswith("ufw ")]
    expected = f"ufw allow from {operator_ip} to any port 22 proto tcp"
    if any(line != expected for line in added) or len(added) > 1:
        raise HostError("UNRELATED_FIREWALL_RULES_REVIEW_REQUIRED")
    if require_active:
        routing_disabled = "Default: deny (incoming), allow (outgoing), disabled (routed)" in status
        routing_denied = "Default: deny (incoming), allow (outgoing), deny (routed)" in status
        if "Status: active" not in status or not (routing_disabled or routing_denied):
            raise HostError("FIREWALL_DEFAULTS_INVALID")
        if added != [expected]:
            raise HostError("OPERATOR_ONLY_SSH_RULE_REQUIRED")
        for binary in ("iptables", "ip6tables"):
            if "-P INPUT DROP" not in command([binary, "-S", "INPUT"]).splitlines():
                raise HostError("IPV4_AND_IPV6_DEFAULT_DROP_REQUIRED")
            if "-P FORWARD DROP" not in command([binary, "-S", "FORWARD"]).splitlines():
                raise HostError("IPV4_AND_IPV6_ROUTED_DROP_REQUIRED")
        # UFW reports routed traffic as disabled on an ordinary non-router host.
        # Confirm both the kernel forwarding switches and fail-closed policies;
        # the display text alone is insufficient evidence of disabled routing.
        if routing_disabled and command(["sysctl", "-n", "net.ipv4.ip_forward",
                                         "net.ipv6.conf.all.forwarding"]).splitlines() != ["0", "0"]:
            raise HostError("DISABLED_ROUTING_KERNEL_STATE_MISMATCH")
    elif "Status: active" in status:
        # Resuming a previously configured firewall is safe only with our one rule.
        if added != [expected]:
            raise HostError("ACTIVE_FOREIGN_FIREWALL_REFUSED")


def database_check() -> None:
    query = ("SELECT current_setting('server_version_num')::int / 10000, "
             "current_setting('listen_addresses'), current_setting('port'), "
             "(SELECT count(*) FROM pg_database WHERE datname NOT IN ('postgres','template0','template1')), "
             "(SELECT count(*) FROM pg_roles WHERE rolname <> 'postgres' AND left(rolname,3) <> 'pg_')")
    output = command(["runuser", "-u", "postgres", "--", "psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                      "-d", "postgres", "-c", query])
    if output != "16|127.0.0.1|5432|0|0":
        raise HostError("POSTGRES_FOUNDATION_POLICY_OR_EMPTY_DATABASE_CHECK_FAILED")


def fresh_database_check() -> None:
    query = ("SELECT (SELECT count(*) FROM pg_database WHERE datname NOT IN ('postgres','template0','template1')), "
             "(SELECT count(*) FROM pg_roles WHERE rolname <> 'postgres' AND left(rolname,3) <> 'pg_')")
    if command(["runuser", "-u", "postgres", "--", "psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                "-d", "postgres", "-c", query]) != "0|0":
        raise HostError("EXISTING_POSTGRES_APPLICATION_DATA_REFUSED")


def cluster_check(*, owned: bool) -> None:
    if not shutil.which("pg_lsclusters"):
        return
    rows = [line.split() for line in command(["pg_lsclusters", "--no-header"]).splitlines() if line.strip()]
    if rows and (not owned or len(rows) != 1 or rows[0][:2] != ["16", "main"]):
        raise HostError("EXISTING_OR_UNEXPECTED_POSTGRES_CLUSTER_REFUSED")


def inactive_engine_check(*, allow_owned_postgres_ipv6: bool = False) -> None:
    units = command(["systemctl", "list-unit-files", "--no-legend", "--no-pager"])
    if any(line.split()[0].startswith(("abr-", "abn-")) for line in units.splitlines() if line.strip()):
        raise HostError("ENGINE_UNITS_ALREADY_INSTALLED")
    for line in command(["ss", "-H", "-lnt"]).splitlines():
        fields = line.split()
        if len(fields) < 5:
            raise HostError("TCP_LISTENER_OUTPUT_INVALID")
        host, _, port = fields[3].rpartition(":")
        host = host.strip("[]")
        # Linux ss may append an interface to IPv4 as well as IPv6 addresses
        # (for example systemd-resolved's 127.0.0.53%lo). Only a numeric
        # address and a bounded interface name may use this notation; the
        # address itself still determines whether the listener is loopback.
        if "%" in host:
            address, interface = host.split("%", 1)
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", interface) or interface in {".", ".."}:
                raise HostError("TCP_LISTENER_OUTPUT_INVALID")
            try:
                host = str(ipaddress.ip_address(address))
            except ValueError:
                raise HostError("TCP_LISTENER_OUTPUT_INVALID") from None
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if port in {"8766", "8767", "8768"} or (not local and port != "22"):
            raise HostError("UNEXPECTED_PUBLIC_OR_ENGINE_TCP_LISTENER")
        if port == "5432" and host != "127.0.0.1" and not (allow_owned_postgres_ipv6 and host == "::1"):
            raise HostError("POSTGRES_NONLOOPBACK_LISTENER")
