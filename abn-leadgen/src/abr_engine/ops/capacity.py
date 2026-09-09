"""Explicit remaining-space admission and measured callable resource samples."""

from __future__ import annotations

import math
import os
import platform
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import psutil
from pydantic import BaseModel, ConfigDict, Field

GIB = 1024**3


class CapacityPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    remaining_downloads: int | None = Field(default=None, ge=0)
    staged_parquet_upper_bound: int | None = Field(default=None, ge=0)
    prior_snapshot_bytes: int | None = Field(default=None, ge=0)
    new_snapshot_upper_bound: int | None = Field(default=None, ge=0)
    configured_spill_limit: int | None = Field(default=None, ge=0)
    projected_db_growth: int | None = Field(default=None, ge=0)
    projected_wal_growth: int | None = Field(default=None, ge=0)
    temporary_backup_bytes: int | None = Field(default=None, ge=0)
    # Existing allocations are informational only: already accounted in filesystem free.
    existing_allocations: dict[str, int] = Field(default_factory=dict)

    def required_free_bytes(self) -> int:
        amounts = [value for name, value in self.model_dump().items() if name != "existing_allocations"]
        if any(value is None for value in amounts):
            raise ValueError("unknown allocation upper bound: admission blocked")
        if any(value < 0 for value in self.existing_allocations.values()):
            raise ValueError("negative existing allocation")
        return sum(amounts) + 25 * GIB

    def admit(self, free_bytes: int) -> bool:
        if free_bytes < 0:
            raise ValueError("negative free bytes")
        return free_bytes >= self.required_free_bytes()


def estimate_upper_bytes(sample_bytes: int, sample_rows: int, target_rows: int,
                         safety_factor: float = 2.0) -> int:
    if sample_rows <= 0 or sample_bytes < 0 or target_rows < 0 or safety_factor < 2 or not math.isfinite(safety_factor):
        raise ValueError("bounded sample and finite safety factor >=2 required")
    return math.ceil(sample_bytes / sample_rows * target_rows * safety_factor)


T = TypeVar("T")


def measure_callable[T](operation: Callable[[], T], *, output_paths: list[Path] | None = None,
                     rows: int, runtime_version: str, sample_interval_seconds: float = .01) -> tuple[T, dict]:
    """Measure materialising operation, not an unconsumed lazy query or join count.

    Sampled RSS may miss short spikes. DB/WAL and spill measurements require caller-supplied
    artifacts or external metrics; this helper alone does not certify the full scale target.
    """
    if rows < 0 or not 0 < sample_interval_seconds <= 1:
        raise ValueError("invalid benchmark sample")
    process = psutil.Process(os.getpid())
    peak = [process.memory_info().rss]
    stop = threading.Event()

    def sample():
        while not stop.wait(sample_interval_seconds):
            peak[0] = max(peak[0], process.memory_info().rss)

    monitor = threading.Thread(target=sample, daemon=True)
    started = time.perf_counter()
    monitor.start()
    try:
        result = operation()
        peak[0] = max(peak[0], process.memory_info().rss)
    finally:
        elapsed = time.perf_counter() - started
        stop.set()
        monitor.join()
    materialised = sum(path.stat().st_size for path in (output_paths or []))
    return result, {"rows": rows, "elapsed_seconds": elapsed, "sampled_peak_rss_bytes": peak[0],
                    "output_bytes": materialised, "platform": platform.platform(),
                    "python": platform.python_version(), "runtime_version": runtime_version,
                    "sample_interval_seconds": sample_interval_seconds,
                    "full_scale_certified": False, "db_wal_measured": False}
