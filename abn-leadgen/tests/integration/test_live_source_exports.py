"""Authenticated one-use CSV downloads of actual accepted synthetic snapshots."""
# ruff: noqa: F811 -- pytest fixtures are intentionally imported by name.

import csv
import io

from fastapi.testclient import TestClient
from test_live_qbcc import accepted  # noqa: F401
from test_qbcc_review_stage import live  # noqa: F401

from abr_engine.control.auth import Actor
from abr_engine.db import transaction
from abr_engine.live import api
from abr_engine.live import source_exports as exports
from abr_engine.live import source_records as browse
from abr_engine.live.source_query import FIELDS

ORIGIN = "https://www.maintainmedia.com.au"


def application(config, settings, monkeypatch):
    for module in (browse, exports):
        monkeypatch.setattr(module, "transaction", lambda ignored: transaction(settings))
    role = {"scopes": frozenset({"admin"})}
    app = api.create_live_app(config, authority=lambda request: Actor("user_Synthetic", role["scopes"]))
    return app, role


def test_full_csv_ticket_is_staff_scoped_one_use_and_preserves_all_parsed_fields(settings, accepted, monkeypatch):
    config, _, _, receipt = accepted
    app, role = application(config, settings, monkeypatch)
    with TestClient(app) as client:
        body = {"source": "qbcc", "run_id": "latest", "filters": {}, "client_origin": ORIGIN}
        role["scopes"] = frozenset({"operator"})
        assert client.post("/api/source-exports", json=body).status_code == 403
        role["scopes"] = frozenset({"admin"})
        issued = client.post("/api/source-exports", json=body)
        assert issued.status_code == 200 and issued.headers["cache-control"] == "no-store"
        value = issued.json()
        assert value["snapshot_id"] == receipt["snapshot_id"] and value["columns"] == list(FIELDS["qbcc"])
        assert value["total_source_records"] == 1 and "download_url" not in value
        form = {"ticket": value["download_token"]}
        assert client.get("/api/source-exports/download").status_code == 405
        assert client.post("/api/source-exports/download?ticket=unsafe", data=form, headers={"Origin": ORIGIN}).status_code == 415
        assert client.post("/api/source-exports/download", data=form, headers={"Origin": "https://attacker.invalid"}).status_code == 403
        result = client.post("/api/source-exports/download", data=form, headers={"Origin": ORIGIN})
        assert result.status_code == 200 and result.headers["content-type"].startswith("text/csv")
        assert "qbcc-full-" in result.headers["content-disposition"]
        assert result.headers["x-export-expected-rows"] == "1" and result.headers["x-source-snapshot"] == receipt["snapshot_id"]
        assert result.headers["cache-control"] == "no-store"
        rows = list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig"))))
        assert len(rows) == 1 and list(rows[0]) == list(FIELDS["qbcc"])
        assert rows[0]["licence_number"] == "SYNTHETIC-1"
        assert client.post("/api/source-exports/download", data=form, headers={"Origin": ORIGIN}).status_code == 410
        assert app.state.source_export_tickets.active == {}
    with transaction(settings) as conn:
        counts = {row["action"]: row["n"] for row in conn.execute(
            "SELECT action,count(*) n FROM audit_event WHERE action LIKE 'source_export_%' GROUP BY action").fetchall()}
        assert counts == {"source_export_requested": 1, "source_export_completed": 1}
        for table in ("lead_entity", "qbcc_source_review", "crm_outbox"):
            assert conn.execute(f"SELECT count(*) n FROM {table}").fetchone()["n"] == 0


def test_filtered_csv_matches_query_and_does_not_claim_source_total_as_export_count(settings, accepted, monkeypatch):
    config, _, _, _ = accepted
    app, _ = application(config, settings, monkeypatch)
    filters = {"query": "Definitely no matching synthetic company"}
    with TestClient(app) as client:
        query = client.post("/api/source-records/query", json={"source": "qbcc", "run_id": "latest", "filters": filters})
        assert query.status_code == 200 and query.json()["total"] == 0
        issue = client.post("/api/source-exports", json={"source": "qbcc", "filters": filters, "client_origin": ORIGIN})
        assert issue.status_code == 200
        result = client.post("/api/source-exports/download", data={"ticket": issue.json()["download_token"]}, headers={"Origin": ORIGIN})
        assert result.status_code == 200 and result.headers["x-export-scope"] == "filtered"
        assert "x-export-expected-rows" not in result.headers
        assert list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig")))) == []


def test_retention_or_quarantine_between_ticket_and_download_fails_before_csv_headers(settings, accepted, monkeypatch):
    config, _, _, _ = accepted
    app, _ = application(config, settings, monkeypatch)
    with TestClient(app) as client:
        issue = client.post("/api/source-exports", json={"source": "qbcc", "client_origin": ORIGIN})
        assert issue.status_code == 200
        with transaction(settings) as conn:
            conn.execute("UPDATE system_state SET value='true' WHERE name='restore_quarantine'")
        result = client.post("/api/source-exports/download", data={"ticket": issue.json()["download_token"]}, headers={"Origin": ORIGIN})
        assert result.status_code == 503 and result.headers["content-type"].startswith("application/json")
        assert result.json()["code"] == "AUTHORITY_QUARANTINED" and "content-disposition" not in result.headers
        assert app.state.source_export_tickets.active == {}
