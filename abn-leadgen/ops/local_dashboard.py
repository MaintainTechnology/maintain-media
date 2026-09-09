"""Manage the private fixture dashboard without installing a system service.

The recorded PID, creation time, command and working directory must all match
before stopping a process. A listener started elsewhere is never taken over.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

import psutil

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
APP = "abr_engine.dashboard.api:create_app"
SERVICE = "abn-leadgen-dashboard"


class DashboardError(RuntimeError):
    """An actionable local setup or ownership error."""


def paths(port: int) -> tuple[Path, Path, Path]:
    prefix = RUNTIME / f"dashboard-{port}"
    return prefix.with_suffix(".json"), prefix.with_suffix(".log"), prefix.with_suffix(".lock")


def command(port: int) -> list[str]:
    return [sys.executable, "-m", "uvicorn", APP, "--factory", "--host", "127.0.0.1",
            "--port", str(port), "--no-access-log"]


@contextmanager
def control_lock(path: Path):
    """Kernel-held lock releases automatically even after an interrupted start."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DashboardError("Another dashboard start or stop is in progress; try again shortly.") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def load_state(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def owned_process(state: dict[str, Any] | None, port: int) -> psutil.Process | None:
    """Reject stale or edited metadata, recycled PIDs and foreign commands."""
    if not state or state.get("service") != SERVICE or state.get("port") != port:
        return None
    if state.get("root") != str(ROOT) or type(state.get("pid")) is not int:
        return None
    if type(state.get("created")) not in (float, int):
        return None
    try:
        process = psutil.Process(state["pid"])
        if abs(process.create_time() - state["created"]) > 0.01:
            return None
        arguments = process.cmdline()
        expected = command(port)
        if not arguments or Path(arguments[0]).resolve() != Path(expected[0]).resolve():
            return None
        if arguments[1:] != expected[1:] or Path(process.cwd()).resolve() != ROOT:
            return None
        return process if process.is_running() else None
    except (psutil.Error, OSError, ValueError):
        return None


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def healthy(port: int) -> bool:
    try:
        # Ignore ambient proxy configuration for this strictly local service.
        with build_opener(ProxyHandler({})).open(
            f"http://127.0.0.1:{port}/api/dashboard/health", timeout=2,
        ) as response:
            payload = json.loads(response.read(4097))
            return (response.status == 200 and isinstance(payload, dict)
                    and payload.get("service") == SERVICE and payload.get("mode") == "fixture"
                    and payload.get("status") == "ready")
    except (URLError, OSError, ValueError):
        return False


def run_setup(arguments: list[str], log: Path, timeout: int) -> None:
    with log.open("a", encoding="utf-8") as output:
        output.write(f"\nSetup: {' '.join(arguments[1:])}\n")
        output.flush()
        try:
            result = subprocess.run(arguments, cwd=ROOT, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout, check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            raise DashboardError(f"Local setup timed out. See {log}") from exc
    if result.returncode:
        raise DashboardError(f"Local setup failed (exit {result.returncode}). See {log}")


def bootstrap(log: Path) -> None:
    from abr_engine.config import load_settings

    settings = load_settings(ROOT / "config" / "fixture.yaml", mode="fixture")
    if urlparse(settings.database_url).port != 55432:
        raise DashboardError("The local dashboard requires the isolated fixture database on port 55432.")
    binary = RUNTIME / "pgsql" / "bin" / "pg_ctl.exe"
    if os.name != "nt":
        raise DashboardError("This bootstrap supports Windows; provision PostgreSQL separately on other hosts.")
    if not binary.exists() and not (RUNTIME / "postgresql.zip").exists():
        raise DashboardError("PostgreSQL 16 is missing. Provision .runtime/postgresql.zip as described in README.md.")
    run_setup([sys.executable, str(ROOT / "ops" / "local_postgres.py"), "start"], log, 75)
    run_setup([sys.executable, "-m", "abr_engine.cli", "db", "migrate", "--mode", "fixture"], log, 90)


def terminate_owned(state: dict[str, Any] | None, port: int) -> bool:
    process = owned_process(state, port)
    if process is None:
        return False
    try:
        process.terminate()
        process.wait(timeout=10)
    except psutil.NoSuchProcess:
        pass
    except psutil.TimeoutExpired:
        process = owned_process(state, port)
        if process is None:
            return False
        process.kill()
        process.wait(timeout=5)
    return True


def start(port: int, wait_seconds: float = 45) -> dict[str, Any]:
    state_path, log, _ = paths(port)
    state = load_state(state_path)
    existing = owned_process(state, port)
    bootstrapped = False
    if existing:
        if healthy(port):
            return {"status": "ready", "mode": "fixture", "url": f"http://127.0.0.1:{port}/",
                    "pid": existing.pid, "already_running": True}
        # A stopped fixture database is recoverable without replacing the page's
        # process. Bootstrap only our isolated database, then reassess ownership.
        bootstrap(log)
        bootstrapped = True
        existing = owned_process(state, port)
        if existing:
            if healthy(port):
                return {"status": "ready", "mode": "fixture", "url": f"http://127.0.0.1:{port}/",
                        "pid": existing.pid, "already_running": True, "recovered": True}
            if not terminate_owned(state, port):
                raise DashboardError("Dashboard ownership changed during recovery; nothing else was stopped.")
            state_path.unlink(missing_ok=True)
    if port_in_use(port):
        raise DashboardError(f"Port {port} is already in use by another process. It has been left running. "
                             "Close its owning application or choose another --port.")
    if not bootstrapped:
        bootstrap(log)
    # Recheck after setup: another program may have claimed this port meanwhile.
    if port_in_use(port):
        raise DashboardError(f"Port {port} became occupied during setup. The existing listener has been left running.")
    with log.open("a", encoding="utf-8") as output:
        options: dict[str, Any] = {"cwd": ROOT, "stdin": subprocess.DEVNULL, "stdout": output,
                                  "stderr": subprocess.STDOUT, "close_fds": True}
        if os.name == "nt":
            options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True
        child = subprocess.Popen(command(port), **options)
    try:
        process = psutil.Process(child.pid)
        state = {"service": SERVICE, "root": str(ROOT), "port": port,
                 "pid": child.pid, "created": process.create_time()}
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(state_path)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise DashboardError(f"Dashboard exited during startup. See {log}")
            if healthy(port) and owned_process(state, port):
                return {"status": "ready", "mode": "fixture", "url": f"http://127.0.0.1:{port}/",
                        "pid": child.pid, "already_running": False, "log": str(log)}
            time.sleep(0.25)
        raise DashboardError(f"Dashboard did not become ready within {wait_seconds:g} seconds. See {log}")
    except (DashboardError, OSError, psutil.Error):
        terminate_owned(state, port)
        state_path.unlink(missing_ok=True)
        raise


def stop(port: int) -> dict[str, Any]:
    state_path, _, _ = paths(port)
    state = load_state(state_path)
    if terminate_owned(state, port):
        state_path.unlink(missing_ok=True)
        return {"status": "stopped", "database": "left_running"}
    if port_in_use(port):
        raise DashboardError(f"Port {port} is owned by another process; nothing was stopped.")
    state_path.unlink(missing_ok=True)
    return {"status": "stopped", "already_stopped": True, "database": "left_running"}


def status(port: int) -> dict[str, Any]:
    state_path, log, _ = paths(port)
    process = owned_process(load_state(state_path), port)
    if process:
        return {"status": "ready" if healthy(port) else "unhealthy", "mode": "fixture", "pid": process.pid,
                "url": f"http://127.0.0.1:{port}/", "log": str(log)}
    return {"status": "port_in_use" if port_in_use(port) else "stopped", "owned": False,
            "url": f"http://127.0.0.1:{port}/"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop"])
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    try:
        with control_lock(paths(args.port)[2]):
            result = {"start": start, "status": status, "stop": stop}[args.action](args.port)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in {"ready", "stopped"} else 1
    except (DashboardError, OSError, ValueError, psutil.Error) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
