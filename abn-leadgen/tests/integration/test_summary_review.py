"""Independent R34/R35 database reproductions; explicit synthetic isolated schema."""
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from psycopg import sql

from abr_engine.compliance.keys import load_keys
from abr_engine.config import Settings
from abr_engine.control.service import Service
from abr_engine.db import connect, migrate
from abr_engine.fixture import seed_policy
from abr_engine.ops.summary import operational_summary


@pytest.fixture
def authority():
    schema = "abr_test_" + uuid4().hex
    settings = Settings(schema_name=schema)
    with connect(Settings()) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    migrate(settings)
    conn = connect(settings)
    service = Service(settings, load_keys(settings))
    seed_policy(conn, service)
    run = uuid4()
    conn.execute("INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state) VALUES(%s,'fixture','review','review','running')", (run,))
    try:
        yield conn, service, run
    finally:
        conn.rollback()
        conn.close()
        with connect(Settings()) as cleanup:
            cleanup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_past_budget_exhaustion_does_not_report_current_stop(authority):
    conn, service, run = authority
    end = service.now(conn)
    current_month = end.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m")
    conn.execute("INSERT INTO budget_month(month,cap,reserved,settled,frozen) VALUES('2000-01',150000000,0,150000000,true)")
    conn.execute("INSERT INTO budget_month(month,cap,reserved,settled,frozen) VALUES(%s,150000000,0,0,false)", (current_month,))
    result = operational_summary(conn, service, run, end-timedelta(days=1), end)
    assert "budget_stop" not in result["alarms"]


def test_expired_policy_emits_alarm(authority):
    conn, service, run = authority
    end = service.now(conn) + timedelta(days=91)
    result = operational_summary(conn, service, run, end-timedelta(days=1), end)
    assert "policy_expired" in result["alarms"]


def test_completed_propagation_does_not_alarm(authority):
    conn, service, run = authority
    end = service.now(conn)
    conn.execute("INSERT INTO propagation_outbox(outbox_id,reason,state,created_at,completed_at) VALUES(%s,'fixture','succeeded',%s,%s)",
                 (uuid4(), end-timedelta(hours=1), end-timedelta(minutes=50)))
    result = operational_summary(conn, service, run, end-timedelta(days=1), end)
    assert "suppression_propagation_delayed" not in result["alarms"]


def test_pending_propagation_alarms_once(authority):
    conn, service, run = authority
    end = service.now(conn)
    conn.execute("INSERT INTO propagation_outbox(outbox_id,reason,state,created_at) VALUES(%s,'fixture','pending',%s)",
                 (uuid4(), end-timedelta(seconds=61)))
    for _ in range(2):
        result = operational_summary(conn, service, run, end-timedelta(days=1), end)
        assert "suppression_propagation_delayed" in result["alarms"]
    assert conn.execute("SELECT count(*) AS n FROM alarm_outbox WHERE run_id=%s AND code='suppression_propagation_delayed'", (run,)).fetchone()["n"] == 1
