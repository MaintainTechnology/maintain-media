"""Offline admission and hardening regressions; no package, firewall or AWS writes."""
from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BASE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c = load("host_contract")
bootstrap = load("bootstrap_host")
verifier = load("verify_host")
IP = "8.8.8.8"  # Synthetic input only; never contacted.
RULE = f"ufw allow from {IP} to any port 22 proto tcp"


@pytest.mark.parametrize("address", ["", "0.0.0.0", "127.0.0.1", "192.168.1.1", "169.254.169.254",
                                      "8.8.8.8/0", "8.8.8.8/32", "8.8.8.8;reboot", "2001:4860:4860::8888"])
def test_only_exact_public_ipv4_is_admitted(address):
    with pytest.raises(c.HostError, match="PUBLIC_OPERATOR_IPV4_REQUIRED"):
        c.parameters(address, "ubuntu")


@pytest.mark.parametrize("user", ["root", "abr-engine", "postgres", "ubuntu;id", "--system", ""])
def test_admin_identity_cannot_be_root_service_or_shell_text(user):
    with pytest.raises(c.HostError, match="EXISTING_NONROOT_ADMIN_REQUIRED"):
        c.parameters(IP, user)


def test_missing_apply_does_not_run_host_operations(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["bootstrap", "--operator-ip", IP])
    monkeypatch.setattr(bootstrap, "apply", lambda *_: pytest.fail("No host mutation without --apply"))
    bootstrap.main()
    assert json.loads(capsys.readouterr().out)["status"] == "review_only"


def test_mismatched_ssh_connection_fails_before_identity_or_key_metadata(monkeypatch):
    monkeypatch.setitem(sys.modules, "pwd", SimpleNamespace(getpwnam=lambda _: pytest.fail("Wrong session")))
    monkeypatch.setitem(sys.modules, "grp", SimpleNamespace())
    monkeypatch.setenv("SSH_CONNECTION", "1.1.1.1 54321 10.0.0.2 22")
    monkeypatch.setenv("SUDO_USER", "ubuntu")
    with pytest.raises(c.HostError, match="CURRENT_SSH_CONNECTION"):
        c.admin_check(IP, "ubuntu", require_session=True)


def test_direct_root_or_other_sudo_user_cannot_harden_admin_ssh(monkeypatch):
    monkeypatch.setitem(sys.modules, "pwd", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "grp", SimpleNamespace())
    monkeypatch.setenv("SSH_CONNECTION", f"{IP} 54321 10.0.0.2 22")
    monkeypatch.setenv("SUDO_USER", "other-admin")
    with pytest.raises(c.HostError, match="RUN_THROUGH_EXISTING_ADMIN_SUDO_SESSION"):
        c.admin_check(IP, "ubuntu", require_session=True)


@pytest.mark.parametrize("rules", [
    "ufw allow 22/tcp", "ufw allow from 0.0.0.0/0 to any port 22 proto tcp",
    "ufw allow from 1.1.1.1 to any port 22 proto tcp", RULE + "\nufw allow 443/tcp",
])
def test_foreign_firewall_rules_require_review_without_reset(monkeypatch, rules):
    def command(args, **kwargs):
        assert args in (["ufw", "status", "verbose"], ["ufw", "show", "added"])
        return "Status: inactive" if args[1] == "status" else rules
    monkeypatch.setattr(c, "command", command)
    with pytest.raises(c.HostError, match="UNRELATED_FIREWALL_RULES"):
        c.firewall_rules_check(IP, require_active=False)


def test_ipv6_policy_must_also_deny_incoming_connections(monkeypatch):
    def command(args, **kwargs):
        if args == ["ufw", "status", "verbose"]:
            return "Status: active\nDefault: deny (incoming), allow (outgoing), deny (routed)"
        if args == ["ufw", "show", "added"]:
            return RULE
        return f"-P {args[-1]} DROP" if args[0] == "iptables" else "-P INPUT ACCEPT"
    monkeypatch.setattr(c, "command", command)
    with pytest.raises(c.HostError, match="IPV4_AND_IPV6_DEFAULT_DROP"):
        c.firewall_rules_check(IP, require_active=True)


@pytest.mark.parametrize(("routed", "forwarding", "ipv4_policy", "ipv6_policy", "error"), [
    ("disabled", "0\n0", "DROP", "DROP", None),
    ("deny", "1\n1", "DROP", "DROP", None),
    ("disabled", "1\n0", "DROP", "DROP", "DISABLED_ROUTING_KERNEL_STATE_MISMATCH"),
    ("disabled", "0\n1", "DROP", "DROP", "DISABLED_ROUTING_KERNEL_STATE_MISMATCH"),
    ("disabled", "0", "DROP", "DROP", "DISABLED_ROUTING_KERNEL_STATE_MISMATCH"),
    ("disabled", "0\n0", "ACCEPT", "DROP", "IPV4_AND_IPV6_ROUTED_DROP_REQUIRED"),
    ("disabled", "0\n0", "DROP", "ACCEPT", "IPV4_AND_IPV6_ROUTED_DROP_REQUIRED"),
    ("deny", "1\n1", "DROP", "ACCEPT", "IPV4_AND_IPV6_ROUTED_DROP_REQUIRED"),
    ("allow", "0\n0", "DROP", "DROP", "FIREWALL_DEFAULTS_INVALID"),
])
def test_routed_status_requires_matching_kernel_and_drop_policies(
        monkeypatch, routed, forwarding, ipv4_policy, ipv6_policy, error):
    def command(args, **kwargs):
        if args == ["ufw", "status", "verbose"]:
            return f"Status: active\nDefault: deny (incoming), allow (outgoing), {routed} (routed)"
        if args == ["ufw", "show", "added"]:
            return RULE
        if args == ["sysctl", "-n", "net.ipv4.ip_forward", "net.ipv6.conf.all.forwarding"]:
            return forwarding
        if args[0] in {"iptables", "ip6tables"} and args[1] == "-S":
            policy = "DROP" if args[2] == "INPUT" else (ipv4_policy if args[0] == "iptables" else ipv6_policy)
            return f"-P {args[2]} {policy}"
        pytest.fail(f"Unexpected command: {args}")
    monkeypatch.setattr(c, "command", command)
    if error:
        with pytest.raises(c.HostError, match=error):
            c.firewall_rules_check(IP, require_active=True)
    else:
        c.firewall_rules_check(IP, require_active=True)


@pytest.mark.parametrize("row", ["15|127.0.0.1|5432|0|0", "16|*|5432|0|0", "16|localhost|5432|0|0",
                                  "16|127.0.0.1|55432|0|0", "16|127.0.0.1|5432|1|0", "16|127.0.0.1|5432|0|1"])
def test_database_verification_rejects_wrong_runtime_binding_or_application_data(monkeypatch, row):
    monkeypatch.setattr(c, "command", lambda *args, **kwargs: row)
    with pytest.raises(c.HostError, match="POSTGRES_FOUNDATION_POLICY"):
        c.database_check()


def test_database_checks_only_read_catalogue_counts_and_no_secret_values(monkeypatch):
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        return "16|127.0.0.1|5432|0|0"
    monkeypatch.setattr(c, "command", command)
    c.database_check()
    query = calls[0][-1]
    assert query.startswith("SELECT ") and "left(rolname,3) <> 'pg_'" in query
    assert "pg_authid" not in query and "rolpassword" not in query


@pytest.mark.parametrize("rows", ["16 main 5432 online postgres /data /log", "15 main 5432 online postgres /data /log"])
def test_unowned_database_cluster_is_never_adopted(monkeypatch, rows):
    monkeypatch.setattr(c.shutil, "which", lambda _: "/usr/bin/pg_lsclusters")
    monkeypatch.setattr(c, "command", lambda *args, **kwargs: rows)
    with pytest.raises(c.HostError, match="EXISTING_OR_UNEXPECTED_POSTGRES_CLUSTER"):
        c.cluster_check(owned=False)


@pytest.mark.parametrize("listener", [
    "LISTEN 0 128 0.0.0.0:5432 0.0.0.0:*", "LISTEN 0 128 127.0.0.1:8767 0.0.0.0:*",
    "LISTEN 0 128 [::]:443 [::]:*", "LISTEN 0 128 0.0.0.0:8080 0.0.0.0:*",
])
def test_engine_or_unexpected_public_ports_fail_foundation_check(monkeypatch, listener):
    monkeypatch.setattr(c, "command", lambda args, **kwargs: "" if args[0] == "systemctl" else listener)
    with pytest.raises(c.HostError, match="UNEXPECTED_PUBLIC_OR_ENGINE_TCP_LISTENER"):
        c.inactive_engine_check()


def test_fresh_ubuntu_scoped_resolver_and_ssh_listeners_pass(monkeypatch):
    listeners = ("LISTEN 0 4096 127.0.0.53%lo:53 0.0.0.0:*\n"
                 "LISTEN 0 4096 127.0.0.54:53 0.0.0.0:*\n"
                 "LISTEN 0 4096 0.0.0.0:22 0.0.0.0:*\n"
                 "LISTEN 0 4096 [::]:22 [::]:*")
    monkeypatch.setattr(c, "command", lambda args, **kwargs: "" if args[0] == "systemctl" else listeners)
    c.inactive_engine_check()


@pytest.mark.parametrize("endpoint", [
    "0.0.0.0%lo:53", "10.0.0.1%eth0:53", "[fe80::1%eth0]:53",
    "127.0.0.1%lo:8767", "[::1%lo]:8768", "0.0.0.0%lo:5432",
])
def test_interface_suffix_cannot_bypass_public_or_engine_listener_restrictions(monkeypatch, endpoint):
    monkeypatch.setattr(c, "command", lambda args, **kwargs: "" if args[0] == "systemctl"
                        else f"LISTEN 0 128 {endpoint} 0.0.0.0:*")
    with pytest.raises(c.HostError, match="UNEXPECTED_PUBLIC_OR_ENGINE_TCP_LISTENER"):
        c.inactive_engine_check(allow_owned_postgres_ipv6=True)


@pytest.mark.parametrize("endpoint", [
    "localhost%lo:53", "127.0.0.53%:53", "127.0.0.53%lo%other:53",
    "127.0.0.53%lo/other:53", "127.0.0.53%abcdefghijklmnop:53", "127.0.0.53%..:22",
])
def test_malformed_interface_scopes_are_not_accepted(monkeypatch, endpoint):
    monkeypatch.setattr(c, "command", lambda args, **kwargs: "" if args[0] == "systemctl"
                        else f"LISTEN 0 128 {endpoint} 0.0.0.0:*")
    with pytest.raises(c.HostError, match="TCP_LISTENER_OUTPUT_INVALID"):
        c.inactive_engine_check()


def test_installed_engine_timer_prevents_foundation_pass(monkeypatch):
    monkeypatch.setattr(c, "command", lambda *args, **kwargs: "abr-live-qbcc.timer disabled enabled")
    with pytest.raises(c.HostError, match="ENGINE_UNITS_ALREADY_INSTALLED"):
        c.inactive_engine_check()


def test_owned_resume_after_apt_accepts_default_ipv6_loopback_but_verifier_does_not(monkeypatch):
    monkeypatch.setattr(c, "command", lambda args, **kwargs: "" if args[0] == "systemctl"
                        else "LISTEN 0 128 [::1]:5432 [::]:*")
    c.inactive_engine_check(allow_owned_postgres_ipv6=True)
    with pytest.raises(c.HostError, match="POSTGRES_NONLOOPBACK_LISTENER"):
        c.inactive_engine_check()
    monkeypatch.setattr(c, "command", lambda args, **kwargs: "" if args[0] == "systemctl"
                        else "LISTEN 0 128 [::]:5432 [::]:*")
    with pytest.raises(c.HostError, match="UNEXPECTED_PUBLIC_OR_ENGINE_TCP_LISTENER"):
        c.inactive_engine_check(allow_owned_postgres_ipv6=True)


def test_matching_postgresql_managed_file_can_resume_with_group_read_mode(tmp_path, monkeypatch):
    target = tmp_path / "managed.conf"
    target.write_text("managed\n", encoding="utf-8")
    original = Path.stat
    monkeypatch.setattr(c, "no_links", lambda _: None)
    monkeypatch.setattr(Path, "stat", lambda path, **kwargs:
                        SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_gid=42, st_size=8)
                        if path == target else original(path, **kwargs))
    assert bootstrap.managed_file(target, "managed\n", gid=42, mode=0o640) is False
    with pytest.raises(c.HostError, match="MANAGED_FILE_CHANGED_REVIEW_REQUIRED"):
        bootstrap.managed_file(target, "replace\n", gid=42, mode=0o640)
    assert target.read_text() == "managed\n"


def test_invalid_new_ssh_policy_rolls_back_only_its_file_and_never_reloads(tmp_path, monkeypatch):
    target = tmp_path / "00-abr-host.conf"
    foreign = tmp_path / "50-cloud-init.conf"
    foreign.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(c, "SSH_CONFIG", target)
    def install(path, content):
        path.write_text(content, encoding="utf-8")
        return True
    def reject(*args):
        raise c.HostError("EFFECTIVE_SSH_POLICY_MISMATCH")
    monkeypatch.setattr(bootstrap, "managed_file", install)
    monkeypatch.setattr(c, "ssh_check", reject)
    monkeypatch.setattr(c, "command", lambda *_: pytest.fail("Invalid SSH config must not reload"))
    with pytest.raises(c.HostError, match="EFFECTIVE_SSH_POLICY_MISMATCH"):
        bootstrap.install_ssh_policy(IP, "ubuntu")
    assert not target.exists()
    assert foreign.read_text() == "preserve"


def test_wrong_host_apply_fails_before_posix_imports_or_installation(monkeypatch):
    def reject():
        raise c.HostError("ROOT_REQUIRED")
    monkeypatch.setattr(c, "platform_check", reject)
    monkeypatch.setattr(c, "command", lambda *_: pytest.fail("No OS command on rejected host"))
    with pytest.raises(c.HostError, match="ROOT_REQUIRED"):
        bootstrap.apply(IP, "ubuntu")


def test_ssh_effective_policy_overrides_are_detected_before_reload(monkeypatch):
    output = c.ssh_text("ubuntu").lower().replace("passwordauthentication no", "passwordauthentication yes") + "port 22\n"
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        return output if "-T" in args else ""
    monkeypatch.setattr(c, "command", command)
    with pytest.raises(c.HostError, match="EFFECTIVE_SSH_POLICY_MISMATCH"):
        c.ssh_check(IP, "ubuntu")
    assert all("reload" not in args for args in calls)


@pytest.mark.parametrize("changed", [
    ("authenticationmethods publickey", "authenticationmethods any"),
    ("authenticationmethods publickey", "authenticationmethods publickey,password"),
    ("gssapiauthentication no", "gssapiauthentication yes"),
    ("hostbasedauthentication no", "hostbasedauthentication yes"),
])
def test_non_key_only_ssh_methods_fail_effective_verification(monkeypatch, changed):
    output = c.ssh_text("ubuntu").lower().replace(*changed) + "port 22\n"
    monkeypatch.setattr(c, "command", lambda args, **kwargs: output if "-T" in args else "")
    with pytest.raises(c.HostError, match="EFFECTIVE_SSH_POLICY_MISMATCH"):
        c.ssh_check(IP, "ubuntu")


def test_root_match_override_is_checked_separately_from_admin(monkeypatch):
    output = c.ssh_text("ubuntu").lower() + "port 22\n"
    def command(args, **kwargs):
        if "-T" not in args:
            return ""
        return output.replace("permitrootlogin no", "permitrootlogin yes") if "user=root," in args[-1] else output
    monkeypatch.setattr(c, "command", command)
    with pytest.raises(c.HostError, match="EFFECTIVE_SSH_POLICY_MISMATCH"):
        c.ssh_check(IP, "ubuntu")


def test_existing_application_files_are_not_removed_or_overwritten(tmp_path):
    target = tmp_path / "existing-app"
    target.mkdir()
    sentinel = target / "business-record.json"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(c.HostError, match="EXISTING_APPLICATION_CONTENT_REFUSED"):
        bootstrap.directory(target, 0, 0, 0o750)
    assert sentinel.read_text() == "keep"


def test_verifier_fails_closed_before_nonlinux_runtime_checks(monkeypatch):
    def reject():
        raise c.HostError("ROOT_REQUIRED")
    monkeypatch.setattr(c, "platform_check", reject)
    monkeypatch.setattr(verifier, "runtime_check", lambda: pytest.fail("No dependent checks"))
    result = verifier.verify(IP, "ubuntu")
    assert result["status"] == "blocked"
    assert result["live_engine_enabled"] is False
    assert result["capacity_certified"] is False
    assert len(result["checks"]) == 1


def test_bootstrap_contains_no_cloud_or_application_startup_commands():
    # This guards the bounded installation authority; the behavioural tests above
    # independently verify the actual admission and access boundaries.
    source = (BASE / "bootstrap_host.py").read_text(encoding="utf-8")
    for prohibited in ('["aws"', '"ufw", "reset"', '"createdb"', '"createuser"',
                       '"uvicorn"', '"abr-engine", "run"', '"systemctl", "enable"'):
        assert prohibited not in source
