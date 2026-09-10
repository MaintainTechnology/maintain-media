"""Coordinator recovery/security tests. No cloud, SSH or Vercel execution."""
import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

DIRECTORY = Path(__file__).parent
RUNTIME_SPEC = importlib.util.spec_from_file_location("provision_runtime", DIRECTORY / "provision_runtime.py")
runtime = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(runtime)
sys.modules["provision_runtime"] = runtime
SPEC = importlib.util.spec_from_file_location("runtime_client", DIRECTORY / "provision_runtime_client.py")
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


class MemoryEscrow:
    def __init__(self, path):
        self.path, self.state, self.stages = path, None, []

    def recover(self):
        pass

    def load(self):
        return copy.deepcopy(self.state)

    def save(self, state):
        client.validate_state(state)
        self.state = copy.deepcopy(state)
        self.stages.append(state["stage"])
        self.path.touch()  # Existence only; no plaintext secret persistence.


def remote_receipt(state):
    return SimpleNamespace(returncode=0, stdout=json.dumps({"status": "private_runtime_configured",
        "mode": "pilot", "fixture_keys_used": False, "initial_capabilities_enabled": [],
        "release_approvals_created": False, "material_sha256": state["material_sha256"]}).encode(), stderr=b"")


def test_fresh_keys_are_separate_and_bundle_is_bound_to_exact_targets():
    state = client.fresh_state()
    assert client.validate_state(state) == state
    assert len(set(state["material"].values())) == 5
    for field, value in [("project", "other"), ("host", "other"), ("mode", "production"),
                         ("material_sha256", "0" * 64), ("stage", "unknown")]:
        changed = copy.deepcopy(state)
        changed[field] = value
        with pytest.raises(client.ProvisionFailure):
            client.validate_state(changed)


def test_escrow_precedes_external_io_and_only_website_key_reaches_vercel(tmp_path):
    escrow = MemoryEscrow(tmp_path / "escrow")
    calls = []

    def runner(command, *, data, timeout):
        assert escrow.path.exists()
        calls.append((command, data, timeout, escrow.state["stage"]))
        return remote_receipt(escrow.state) if command == ["ssh"] else SimpleNamespace(returncode=0)

    result = client.coordinate(escrow, ["ssh"], ["vercel"], runner=runner)
    assert result["status"] == "runtime_keys_installed" and not result["website_connection_enabled"]
    assert calls[0][3] == "remote_pending" and calls[1][3] == "vercel_pending"
    assert json.loads(calls[0][1]) == escrow.state["material"]
    assert calls[1][1] == escrow.state["material"]["website_assertion_key"].encode()
    assert escrow.stages == ["prepared", "remote_pending", "remote_ready", "vercel_pending", "complete"]
    assert not escrow.path.read_bytes()


def test_uncertain_remote_result_reuses_original_escrow_and_never_updates_vercel(tmp_path, monkeypatch):
    escrow = MemoryEscrow(tmp_path / "escrow")
    sent = []

    def uncertain(command, *, data, timeout):
        sent.append(data)
        raise client.ProvisionFailure("COMMAND_RESULT_UNCONFIRMED")

    with pytest.raises(client.ProvisionFailure):
        client.coordinate(escrow, ["ssh"], ["vercel"], runner=uncertain)
    assert escrow.state["stage"] == "remote_pending"
    monkeypatch.setattr(client, "fresh_state", lambda: pytest.fail("Recovery must reuse original material"))

    def resumed(command, *, data, timeout):
        if command == ["ssh"]:
            assert data == sent[0]
            return remote_receipt(escrow.state)
        return SimpleNamespace(returncode=0)

    assert client.coordinate(escrow, ["ssh"], ["vercel"], runner=resumed)["stage"] == "complete"


@pytest.mark.parametrize("response", [b"not json", b"[]", b'{"status":"private_runtime_configured"}'])
def test_incomplete_remote_receipt_never_installs_a_website_key(tmp_path, response):
    escrow = MemoryEscrow(tmp_path / "escrow")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=response)

    with pytest.raises(client.ProvisionFailure, match="REMOTE_INSTALLATION_UNCONFIRMED"):
        client.coordinate(escrow, ["ssh"], ["vercel"], runner=runner)
    assert calls == [["ssh"]] and escrow.state["stage"] == "remote_pending"


def test_vercel_retry_preserves_exact_key_and_does_not_repeat_remote_install(tmp_path):
    escrow = MemoryEscrow(tmp_path / "escrow")
    sent = []

    def initial(command, *, data, timeout):
        if command == ["ssh"]:
            return remote_receipt(escrow.state)
        sent.append(data)
        return SimpleNamespace(returncode=1)

    with pytest.raises(client.ProvisionFailure, match="VERCEL_INSTALLATION_UNCONFIRMED"):
        client.coordinate(escrow, ["ssh"], ["vercel"], runner=initial)
    assert escrow.state["stage"] == "vercel_pending"

    def resumed(command, *, data, timeout):
        assert command == ["vercel"] and data == sent[0]
        return SimpleNamespace(returncode=0)

    client.coordinate(escrow, ["ssh"], ["vercel"], runner=resumed)
    client.coordinate(escrow, ["ssh"], ["vercel"], runner=lambda *a, **k: pytest.fail("Completed replay has no writes"))


def test_subprocess_uses_stdin_no_shell_and_hides_windows_helper(monkeypatch):
    seen = []
    monkeypatch.setattr(client.subprocess, "run", lambda command, **kwargs: seen.append((command, kwargs))
                        or SimpleNamespace(returncode=0, stdout=b"ok", stderr=b""))
    client.run_process(["fixed", "arguments"], data=b"synthetic-secret", timeout=2)
    command, options = seen[0]
    assert b"synthetic-secret" not in command
    assert options["input"] == b"synthetic-secret" and options["shell"] is False
    assert options["creationflags"] == (0x08000000 if os.name == "nt" else 0)


def test_preview_and_unexpected_errors_do_not_generate_or_echo_keys(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["coordinator"])
    monkeypatch.setattr(client, "apply", lambda: pytest.fail("Preview cannot install"))
    assert client.main() == 0
    assert "review_only" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["coordinator", "--apply"])
    monkeypatch.setattr(client, "apply", lambda: (_ for _ in ()).throw(ValueError("sentinel-private-value")))
    assert client.main() == 2
    output = capsys.readouterr().out
    assert "sentinel-private-value" not in output and "RUNTIME_COORDINATOR_UNCONFIRMED" in output


@pytest.mark.skipif(os.name != "nt", reason="Real current-user Windows DPAPI and ACL test")
def test_actual_dpapi_escrow_is_user_only_encrypted_and_recovers_initial_atomic_write(tmp_path):
    directory = tmp_path / "new-user-only"
    client.secure_directory(directory)
    escrow = client.Escrow(directory / "synthetic.dpapi")
    state = client.fresh_state()
    escrow.save(state)
    encrypted = escrow.path.read_bytes()
    assert all(value.encode() not in encrypted for value in state["material"].values())
    assert escrow.load() == state
    temporary = escrow.path.with_name(escrow.path.name + ".next")
    os.replace(escrow.path, temporary)
    escrow.recover()
    assert not temporary.exists() and escrow.load() == state
    # A saved pending step can safely resume from the older durable state.
    state["stage"] = "remote_pending"
    temporary.write_bytes(client.dpapi(client.canonical(state)))
    escrow.recover()
    assert not temporary.exists() and escrow.load()["stage"] == "prepared"


@pytest.mark.skipif(os.name != "nt", reason="Read-only metadata preflight for the specified Windows tools")
def test_fixed_targets_and_strict_ssh_pins_are_present_without_reading_contents():
    base = Path(os.environ["LOCALAPPDATA"]) / "MaintainMedia/aws"
    ssh, vercel = client.commands(base)
    assert ssh[1:3] == ["-F", "NUL"]
    assert ssh[-2:] == [client.HOST, client.REMOTE]
    for option in ("BatchMode=yes", "IdentitiesOnly=yes", "ForwardAgent=no", "StrictHostKeyChecking=yes",
                   "KexAlgorithms=curve25519-sha256", "HostKeyAlgorithms=ssh-ed25519",
                   "GlobalKnownHostsFile=NUL", "ClearAllForwardings=yes", "RequestTTY=no"):
        assert option in ssh
    assert vercel == [str(client.NODE), str(client.VERCEL), "env", "add", "ABN_ENGINE_ASSERTION_KEY", "production",
                      "--project", client.PROJECT, "--scope", client.SCOPE, "--yes", "--force", "--sensitive"]
    assert not any(name in vercel for name in ("ABN_ENGINE_MODE", "ABN_ENGINE_ORIGIN", "ABN_ENGINE_TRANSPORT"))


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows crash-release file locking")
def test_os_lock_excludes_another_process_and_releases_after_process_is_killed(tmp_path):
    directory = tmp_path / "exclusive-user-only"
    client.secure_directory(directory)
    lock = directory / "coordinator.lock"
    lock.touch()  # A marker left by an older interrupted process is recoverable.
    script = ("import sys; from pathlib import Path; "
              "sys.path.insert(0,sys.argv[1]); import provision_runtime_client as c; "
              "lease=c.coordinator_lock(Path(sys.argv[2])); lease.__enter__(); "
              "print('locked',flush=True); sys.stdin.read()")
    child = subprocess.Popen([sys.executable, "-c", script, str(DIRECTORY), str(lock)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        assert child.stdout.readline().strip() == b"locked"
        with pytest.raises(client.ProvisionFailure, match="COORDINATOR_ALREADY_ACTIVE"), client.coordinator_lock(lock):
            pytest.fail("Two coordinators must never run concurrently")
    finally:
        child.kill()
        child.communicate(timeout=10)
    with client.coordinator_lock(lock):
        assert lock.exists()
