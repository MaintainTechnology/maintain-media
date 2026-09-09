"""Bounded fixture DB-loss drill. Restores the existing dashboard before exiting."""
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8767"


def command(script, action):
    result = subprocess.run([sys.executable, str(ROOT / "ops" / script), action], cwd=ROOT,
                            capture_output=True, text=True, timeout=120, check=False)
    if result.returncode and not (script == "local_dashboard.py" and action == "status"):
        raise RuntimeError(f"{script} {action} failed: {result.stdout} {result.stderr}")
    return result.stdout


def main():
    before = json.loads(command("local_dashboard.py", "status"))
    assert before["status"] == "ready", before
    with httpx.Client(base_url=BASE, trust_env=False, timeout=10) as http:
        initial = http.get("/api/dashboard").json()
        assert initial["mode"] == "fixture" and initial["active_job"] is None
        try:
            command("local_postgres.py", "stop")
            unavailable = http.get("/api/dashboard")
            assert unavailable.status_code == 503
            assert unavailable.json()["code"] == "DATABASE_UNAVAILABLE"
            unhealthy = json.loads(command("local_dashboard.py", "status"))
            assert unhealthy["status"] == "unhealthy" and unhealthy["pid"] == before["pid"]
            recovered = json.loads(command("local_dashboard.py", "start"))
            assert recovered["status"] == "ready" and recovered["recovered"] is True
            assert recovered["pid"] == before["pid"], "Recovered DB should reuse the page's existing process"
            after = http.get("/api/dashboard")
            assert after.status_code == 200
            assert after.json()["settings"] == initial["settings"]
            assert [lead["lead_id"] for lead in after.json()["leads"]] == [lead["lead_id"] for lead in initial["leads"]]
            result = {"status": "passed", "checked_at": datetime.now(UTC).isoformat(),
                      "database_loss_status": unavailable.status_code, "recovery": recovered,
                      "settings_preserved": True, "lead_records_preserved": True,
                      "scope": "Existing isolated Windows fixture DB and loopback dashboard"}
            target = ROOT / "ops" / "acceptance" / "dashboard-recovery.json"
            target.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
        finally:
            # Even a failed assertion must not leave the user's fixture database stopped.
            command("local_dashboard.py", "start")


if __name__ == "__main__":
    main()
