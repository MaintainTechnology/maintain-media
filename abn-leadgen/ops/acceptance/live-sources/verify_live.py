"""Capture final local checks without reading dotenv or credential inventories."""

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "final-verification-v2"
spec = importlib.util.spec_from_file_location("live_preparation", ROOT / "ops/production/prepare.py")
assert spec and spec.loader
preparation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preparation
spec.loader.exec_module(preparation)


def inventory():
    result = preparation.source_inventory(ROOT)
    files = dict(result["files"])
    for path in sorted((ROOT / "tests").rglob("*.py")):
        preparation.validate_inventory_path(path, ROOT)
        files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"files": files, "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def main():
    OUT.mkdir(exist_ok=False)
    before = inventory()
    (OUT / "source-before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    commands = [
        ["uv", "run", "--frozen", "ruff", "check", "src", "tests", "ops"],
        ["uv", "run", "--frozen", "mypy", "src/abr_engine"],
        ["uv", "run", "--frozen", "mypy", "--follow-imports=silent", "ops/production/prepare.py"],
        ["uv", "run", "--frozen", "pytest", "-q", "--junitxml=" + str(OUT / "pytest.xml")],
    ]
    checks = []
    for index, command in enumerate(commands, 1):
        started = time.monotonic()
        log = OUT / f"check-{index}.log"
        with log.open("w", encoding="utf-8") as stream:
            try:
                completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                           timeout=1800, check=False, shell=False)
                code = completed.returncode
            except (OSError, subprocess.TimeoutExpired):
                code = 124
                stream.write("Check unavailable or exceeded its bounded deadline.\n")
        item = {"command": command, "exit_code": code, "seconds": round(time.monotonic() - started, 2),
                "log": log.name}
        checks.append(item)
        print(json.dumps(item), flush=True)
    after = inventory()
    unchanged = before == after
    passed = unchanged and all(check["exit_code"] == 0 for check in checks)
    result = {"status": "passed" if passed else "failed", "checked_at": datetime.now(UTC).isoformat(),
              "source_and_python_tests_unchanged": unchanged, "inventory_sha256": before["sha256"],
              "commands": checks, "python": platform.python_version(), "platform": platform.platform(),
              "scope": "Local engineering checks; synthetic data and mocked vendor I/O. No live release or installation."}
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
