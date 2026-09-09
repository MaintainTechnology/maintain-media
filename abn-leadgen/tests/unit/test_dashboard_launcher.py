"""Process ownership fences and idempotency for the local dashboard launcher."""
import importlib.util
import json
import socket
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "ops" / "local_dashboard.py"
SPEC = importlib.util.spec_from_file_location("local_dashboard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "RUNTIME", tmp_path)
    return tmp_path


def test_corrupt_state_is_never_process_authority(runtime):
    state_path, _, _ = launcher.paths(8767)
    state_path.write_text("{incomplete", encoding="utf-8")
    assert launcher.load_state(state_path) is None
    assert launcher.owned_process(None, 8767) is None
    state_path.write_text("[]", encoding="utf-8")
    assert launcher.load_state(state_path) is None


def test_recycled_pid_and_foreign_command_are_not_owned(monkeypatch):
    class Process:
        def create_time(self):
            return 100.0

        def cmdline(self):
            return launcher.command(8767)

        def cwd(self):
            return str(launcher.ROOT)

        def is_running(self):
            return True

    process = Process()
    monkeypatch.setattr(launcher.psutil, "Process", lambda _: process)
    state = {"service": launcher.SERVICE, "root": str(launcher.ROOT), "port": 8767,
             "pid": 12345, "created": 99.0}
    assert launcher.owned_process(state, 8767) is None
    state["created"] = 100.0
    assert launcher.owned_process(state, 8767) is process
    monkeypatch.setattr(process, "cmdline", lambda: [launcher.sys.executable, "-m", "http.server", "8767"])
    assert launcher.owned_process(state, 8767) is None


def test_stop_never_terminates_a_foreign_listener(runtime, monkeypatch):
    monkeypatch.setattr(launcher, "owned_process", lambda *_: None)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(launcher.DashboardError, match="nothing was stopped"):
            launcher.stop(port)
        assert listener.getsockname()[1] == port
        assert launcher.port_in_use(port)


def test_start_leaves_existing_listener_and_skips_bootstrap(runtime, monkeypatch):
    def unexpected_setup(_):
        pytest.fail("A port collision must be checked before database setup")

    monkeypatch.setattr(launcher, "bootstrap", unexpected_setup)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(launcher.DashboardError, match="already in use"):
            launcher.start(listener.getsockname()[1])


def test_repeated_start_reuses_healthy_owned_dashboard(runtime, monkeypatch):
    class Process:
        pid = 12345

    monkeypatch.setattr(launcher, "owned_process", lambda *_: Process())
    monkeypatch.setattr(launcher, "healthy", lambda _: True)
    monkeypatch.setattr(launcher, "bootstrap", lambda _: pytest.fail("Must reuse the existing process"))
    result = launcher.start(8767)
    assert result["already_running"] is True
    assert result["pid"] == 12345


def test_start_recovers_database_without_replacing_owned_dashboard(runtime, monkeypatch):
    class Process:
        pid = 12345

    checks = iter([False, True])
    setup = []
    monkeypatch.setattr(launcher, "owned_process", lambda *_: Process())
    monkeypatch.setattr(launcher, "healthy", lambda _: next(checks))
    monkeypatch.setattr(launcher, "bootstrap", lambda log: setup.append(log))
    monkeypatch.setattr(launcher, "terminate_owned", lambda *_: pytest.fail("Recovered process must stay running"))
    result = launcher.start(8767)
    assert len(setup) == 1
    assert result["status"] == "ready" and result["already_running"] is True and result["recovered"] is True
    assert result["pid"] == 12345


def test_recovery_rechecks_ownership_before_stopping_anything(runtime, monkeypatch):
    checks = iter([object(), None])
    monkeypatch.setattr(launcher, "owned_process", lambda *_: next(checks))
    monkeypatch.setattr(launcher, "healthy", lambda _: False)
    monkeypatch.setattr(launcher, "bootstrap", lambda _: None)
    monkeypatch.setattr(launcher, "port_in_use", lambda _: True)
    monkeypatch.setattr(launcher, "terminate_owned", lambda *_: pytest.fail("Unowned process must stay running"))
    with pytest.raises(launcher.DashboardError, match="already in use"):
        launcher.start(8767)


def test_unhealthy_owned_dashboard_is_restarted_after_database_recovery(runtime, monkeypatch):
    class Process:
        pid = 12345

        def create_time(self):
            return 100.0

        def poll(self):
            return None

    checks = iter([False, False, True])
    stopped, setup, spawned = [], [], []
    monkeypatch.setattr(launcher, "owned_process", lambda *_: Process())
    monkeypatch.setattr(launcher, "healthy", lambda _: next(checks))
    monkeypatch.setattr(launcher, "bootstrap", lambda log: setup.append(log))
    monkeypatch.setattr(launcher, "port_in_use", lambda _: False)
    monkeypatch.setattr(launcher, "terminate_owned", lambda *args: stopped.append(args) or True)
    monkeypatch.setattr(launcher.psutil, "Process", lambda _: Process())
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: spawned.append(args) or Process())
    result = launcher.start(8767)
    assert len(setup) == len(stopped) == len(spawned) == 1
    assert result["status"] == "ready" and result["already_running"] is False
    assert launcher.load_state(launcher.paths(8767)[0])["pid"] == 12345


def test_stopping_stopped_dashboard_cleans_only_stale_receipt(runtime, monkeypatch):
    state_path, log, _ = launcher.paths(8767)
    state_path.write_text(json.dumps({"pid": 12345}), encoding="utf-8")
    log.write_text("preserve troubleshooting history", encoding="utf-8")
    monkeypatch.setattr(launcher, "port_in_use", lambda _: False)
    assert launcher.stop(8767)["already_stopped"] is True
    assert not state_path.exists()
    assert log.read_text(encoding="utf-8") == "preserve troubleshooting history"


def test_concurrent_control_is_rejected_and_lock_releases(runtime):
    lock_path = launcher.paths(8767)[2]
    with (
        launcher.control_lock(lock_path),
        pytest.raises(launcher.DashboardError, match="in progress"),
        launcher.control_lock(lock_path),
    ):
        pytest.fail("Concurrent launcher entered the critical section")
    with launcher.control_lock(lock_path):
        pass
