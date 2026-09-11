"""Interrupt long local DuckDB queries when a finite run check fails.

The callback may run on the watcher thread. It must not use the watched DuckDB
connection, and any external lock/query it performs must have its own timeout.
Callbacks are serialized. Exceptions are returned to the calling thread, never
printed by the watcher. This guard does not authorize any provider operation.
"""

from contextlib import contextmanager, suppress
from threading import Event, Lock, Thread


@contextmanager
def analytical_guard(connection, check, *, interval=0.1):
    """Yield a checkpoint and interrupt an executing query on check failure.

Use the checkpoint before/after queries and output batches. The watcher also
checks during a blocking query, so a deadline or resource failure cannot wait
until a multi-hour analytical operation has finished. A failed callback must be
raised as an exception; a false return is not an admission decision.
    """
    if not 0 < interval <= 1:
        raise ValueError("Invalid analytical check interval")
    stopped, callback_lock = Event(), Lock()
    failures: list[Exception] = []

    def checkpoint():
        with callback_lock:
            if failures:
                raise failures[0]
            if check is not None:
                try:
                    check()
                except Exception as error:
                    failures.append(error)
                    raise

    def watch():
        while not stopped.wait(interval):
            try:
                checkpoint()
            except Exception:  # noqa: BLE001 -- transfer any failed run check to the caller.
                # Only the owner of this context closes the connection, after
                # the watcher has stopped. Preserve the callback's safe reason.
                with suppress(Exception):
                    connection.interrupt()
                return

    checkpoint()
    watcher = Thread(target=watch, name="abr-analytical-budget", daemon=True) if check else None
    if watcher is not None:
        watcher.start()
    try:
        yield checkpoint
        checkpoint()
    finally:
        stopped.set()
        if watcher is not None:
            watcher.join()
        if failures:
            raise failures[0]
