"""One-command fixture propagation evidence in an isolated disposable PG schema."""
import hashlib
import json
import platform
import subprocess
import sys
import time
from uuid import uuid4

import yaml
from psycopg import sql

from abr_engine.compliance.keys import load_keys
from abr_engine.config import ROOT, Settings
from abr_engine.control.service import Service
from abr_engine.db import connect, migrate
from abr_engine.export.mock_provider import PersistentMockCRM
from abr_engine.fixture import seed_contact, seed_policy


def main():
    drill_id = uuid4()
    schema = "abr_test_" + drill_id.hex
    settings = Settings(schema_name=schema)
    service = Service(settings, load_keys(settings))
    evidence = ROOT / "ops/acceptance" / f"propagation-drill-{drill_id}.json"
    config = evidence.with_suffix(".fixture.yaml")
    with connect(Settings()) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        migrate(settings)
        config.write_text(yaml.safe_dump(settings.model_dump(mode="json")))
        with connect(settings) as conn:
            seed_policy(conn, service)
            record = seed_contact(conn, service)
        provider = PersistentMockCRM(settings, service.keys)
        group = str(record["lead"]["group_id"])
        remote_id = provider.create(group, {"group_id": group, "endpoint": "synthetic@example.com",
            "tags": ["maintain-media:candidate", "fixture-customer-owned"], "custom_fields": []}, str(drill_id))
        with connect(settings) as conn:
            conn.execute("INSERT INTO crm_identity VALUES('fixture',%s,%s,clock_timestamp())", (group, remote_id))
            service.suppress(conn, {"lead_id": record["lead"]["lead_id"], "reason": "unsubscribe", "source": "fixture-drill"}, "fixture-operator", uuid4())
        command = [sys.executable, "-m", "abr_engine.cli", "propagation", "drain", "--mode", "fixture", "--config", str(config)]
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60, check=True)
        elapsed = time.perf_counter()-started
        result = json.loads(completed.stdout)
        assert result["notifications_sent"] == 0 and result["results"][0]["state"] == "succeeded"
        remote = provider.fetch(remote_id)["payload"]
        assert remote["endpoint"] is None and remote["outreach_blocked"]
        assert remote["tags"] == ["fixture-customer-owned", "maintain-media:suppressed"]
        with connect(settings) as conn:
            row = conn.execute("SELECT completed_at,receipt,extract(epoch FROM(completed_at-created_at)) elapsed FROM propagation_outbox").fetchone()
            assert row is not None
            assert row["completed_at"] and row["receipt"]["verified_remote_records"] == 1
            count = conn.execute("SELECT count(*) n FROM suppression_event").fetchone()
            assert count is not None and count["n"] > 0
        payload = {"status": "passed", "mode": "fixture", "command": command, "exit_code": completed.returncode,
            "cli_elapsed_seconds": elapsed, "enqueue_to_verified_completion_seconds": float(row["elapsed"]),
            "result": result, "checks": {"endpoint_cleared": True, "approved_suppressed_tag": True,
                "unrelated_tag_retained": True, "update_fetched_and_verified": True, "optout_ledger_preserved": True},
            "lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
            "worker_sha256": hashlib.sha256((ROOT / "src/abr_engine/ops/propagation.py").read_bytes()).hexdigest(),
            "schema_cleanup": "complete", "python": platform.python_version(), "platform": platform.platform(),
            "limits": "One synthetic local PostgreSQL/mock worker. No Google/GHL provider, notification or production latency certification."}
    finally:
        config.unlink(missing_ok=True)
        assert schema.startswith("abr_test_") and len(schema) == 41
        with connect(Settings()) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    evidence.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"status": "passed", "evidence": str(evidence), "seconds": float(row["elapsed"])}))


if __name__ == "__main__":
    main()
