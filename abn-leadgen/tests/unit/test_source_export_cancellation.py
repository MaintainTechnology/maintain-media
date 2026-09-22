"""Cancellation while waiting for the shared worker pool must release the export."""

import os
import subprocess
import sys
from pathlib import Path


def test_cancelled_export_waiting_for_worker_releases_lease():
    # A subprocess bounds this regression: the broken implementation leaves a
    # shielded thread waiting forever, which cannot be stopped by a task timeout.
    source = Path(__file__).resolve().parents[2] / "src"
    environment = {**os.environ, "PYTHONPATH": str(source)}
    script = r'''
import anyio
from types import SimpleNamespace
from abr_engine.live import source_exports as exports
print("imports ready", flush=True)

async def scenario():
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 1
    await limiter.acquire()
    state = {"released": False, "task_finished": False}
    scopes, entered = [], anyio.Event()

    def chunks(*args):
        yield b"header"

    exports.csv_chunks = chunks
    store = SimpleNamespace(release=lambda ticket: state.update(released=True))

    async def consume():
        with anyio.CancelScope() as scope:
            scopes.append(scope)
            entered.set()
            async for piece in exports.stream_export(None, None, store, None):
                pass
        state["task_finished"] = True

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(consume)
        await entered.wait()
        await anyio.sleep(0.05)
        scopes[0].cancel()
        await anyio.sleep(0.05)
        limiter.release()
        with anyio.fail_after(2):
            while not state["task_finished"]:
                await anyio.sleep(0.01)
    assert state == {"released": True, "task_finished": True}, state

anyio.run(scenario)
'''
    completed = subprocess.run(
        [sys.executable, "-c", script], env=environment,
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_cancelled_download_preflight_releases_consumed_ticket():
    source = Path(__file__).resolve().parents[2] / "src"
    environment = {**os.environ, "PYTHONPATH": str(source)}
    script = r'''
import anyio
from types import SimpleNamespace
from uuid import uuid4
from fastapi import FastAPI
from abr_engine.live import source_exports as exports
print("imports ready", flush=True)

async def scenario():
    app = FastAPI()
    exports.register_export_routes(app, None, None, None)
    exports._current = lambda *args: None
    store = app.state.source_export_tickets
    ticket = exports.Ticket("synthetic", "https://www.maintainmedia.com.au", store.clock() + 120,
                            str(uuid4()), {"source": "abr", "snapshot_id": uuid4(), "total": 0},
                            [], {}, exports.SourceFilters())
    token = store.put(ticket)
    endpoint = next(route.endpoint for route in app.routes if route.path == "/api/source-exports/download")
    request = SimpleNamespace(url=SimpleNamespace(query=""),
        headers={"content-type": "application/x-www-form-urlencoded", "origin": ticket.origin},
        state=SimpleNamespace(raw_body=("ticket=" + token).encode()))
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 1
    await limiter.acquire()
    scopes, entered, completed = [], anyio.Event(), anyio.Event()

    async def download():
        with anyio.CancelScope() as scope:
            scopes.append(scope)
            entered.set()
            await endpoint(request)
        completed.set()

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(download)
        await entered.wait()
        await anyio.sleep(0.05)
        assert store.active, "The ticket must be consumed before cancelling preflight"
        scopes[0].cancel()
        await anyio.sleep(0.05)
        limiter.release()
        with anyio.fail_after(2):
            await completed.wait()
    assert not store.active, "Cancelled preflight retained the only export lease"

anyio.run(scenario)
'''
    completed = subprocess.run(
        [sys.executable, "-c", script], env=environment,
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
