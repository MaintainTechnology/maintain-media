"""Installer boundaries and transactional migrations against isolated local PG16."""
import importlib.util
import json
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

SPEC = importlib.util.spec_from_file_location("provision_database", Path(__file__).with_name("provision_database.py"))
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_review_only_never_touches_database(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["provision_database", "provision"])
    monkeypatch.setattr(installer, "psql", lambda *_: pytest.fail("No database access"))
    assert installer.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "review_only"


@pytest.mark.parametrize("filename,contents,code", [
    ("unknown.sql", "SELECT 1;", "UNEXPECTED_MIGRATION_FILE"),
    ("001_foundation.sql", "\\! whoami", "PSQL_METACOMMAND_REFUSED"),
    ("001_foundation.sql", "", "MIGRATION_SIZE_INVALID"),
    ("002_next.sql", "SELECT 1;", "FOUNDATION_MIGRATION_REQUIRED"),
])
def test_inventory_rejects_untrusted_inputs(tmp_path, filename, contents, code):
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / filename).write_text(contents)
    with pytest.raises(installer.DatabaseSetupError, match=code):
        installer.migration_inventory(tmp_path)


def test_real_migration_inventory_contains_no_client_commands():
    inventory = installer.migration_inventory(Path(__file__).resolve().parents[2])
    assert len(inventory) >= 26
    assert inventory[-1][0] == "026_backup_ledger_queue.sql"
    assert len({name for name, _, _ in inventory}) == len(inventory)


def test_database_failure_does_not_expose_sql_or_stderr(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(installer.subprocess, "run", lambda *_a, **_k:
                        SimpleNamespace(returncode=1, stdout="private", stderr="private"))
    with pytest.raises(installer.DatabaseSetupError, match="^DATABASE_OPERATION_FAILED$"):
        installer.psql("private")


@pytest.mark.parametrize("name,digest", [("'; DROP DATABASE x; --", "a" * 64),
                                         ("001_foundation.sql", "'; --")])
def test_migration_sql_rejects_interpolated_identifiers(name, digest):
    with pytest.raises(installer.DatabaseSetupError, match="MIGRATION_IDENTITY_INVALID"):
        installer.migration_sql([(name, digest, "SELECT 1;")])


@pytest.fixture
def pg():
    # Fixed synthetic local database only. Never resolve a live config or secret.
    connection = psycopg.connect("postgresql://abr_fixture:abr_fixture@127.0.0.1:55432/abr_fixture", autocommit=True)
    schema = "abr_install_test_" + uuid4().hex
    connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
    try:
        yield connection, schema
    finally:
        connection.execute("ROLLBACK")
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        connection.close()


def run_migrations(pg, migrations, runtime_role="abr_fixture"):
    connection, schema = pg
    statement = installer.migration_sql(migrations)
    # Keep the production SQL execution and checksum control flow; substitute
    # only the static identities/schema with the isolated fixture namespace.
    statement = statement.replace("ROLE abr_engine_owner", "ROLE abr_fixture")
    statement = statement.replace('TO "abr-engine"', 'TO "' + runtime_role + '"')
    statement = statement.replace('FROM "abr-engine"', 'FROM "' + runtime_role + '"')
    statement = statement.replace("IN SCHEMA public", "IN SCHEMA " + schema)
    connection.execute(statement)


def test_real_restricted_runtime_commits_dirty_trigger_without_queue_delete_or_gate_write(pg):
    connection, schema = pg
    role = "abr_queue_test_" + uuid4().hex
    connection.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
    try:
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(role)))
        inventory = installer.migration_inventory(Path(__file__).resolve().parents[2])
        run_migrations(pg, inventory, runtime_role=role)
        privileges = connection.execute("SELECT has_table_privilege(%s,'backup_ledger_state','SELECT'),"
            "has_table_privilege(%s,'backup_ledger_state','UPDATE'),"
            "has_table_privilege(%s,'backup_ledger_state','INSERT,DELETE,TRUNCATE,REFERENCES,TRIGGER'),"
            "has_table_privilege(%s,'release_gate','INSERT,UPDATE,DELETE')", (role, role, role, role)).fetchone()
        assert privileges == (True, True, False, False)
        connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        connection.execute("BEGIN")
        connection.execute("INSERT INTO business_group(group_id) VALUES(%s)", (uuid4(),))
        connection.execute("COMMIT")
        assert connection.execute("SELECT generation FROM backup_ledger_state").fetchone()[0] == 2
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("DELETE FROM backup_ledger_state")
    finally:
        connection.execute("ROLLBACK")
        connection.execute("RESET ROLE")
        connection.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


FOUNDATION = ("001_foundation.sql", "a" * 64,
              ("CREATE TABLE release_gate(id int); CREATE TABLE policy(id int); "
               "CREATE TABLE suppression_event(id int); CREATE TABLE suppression_alias(id int); "
               "CREATE TABLE backup_ledger_state(singleton boolean); "
               "CREATE TABLE result(value text); INSERT INTO result VALUES('owner''s value');"))


def test_real_pg_migration_applies_and_replays_without_duplicate(pg):
    run_migrations(pg, [FOUNDATION])
    run_migrations(pg, [FOUNDATION])
    assert pg[0].execute("SELECT * FROM result").fetchall() == [("owner's value",)]
    assert pg[0].execute("SELECT count(*) FROM schema_migration").fetchone()[0] == 1


def test_real_pg_changed_migration_rolls_back_later_work(pg):
    run_migrations(pg, [FOUNDATION])
    changed = (FOUNDATION[0], "b" * 64, FOUNDATION[2])
    with pytest.raises(psycopg.Error, match="APPLIED_MIGRATION_CHANGED"):
        run_migrations(pg, [changed, ("002_extra.sql", "c" * 64, "CREATE TABLE should_not_exist(id int);")])
    pg[0].execute("ROLLBACK")
    assert pg[0].execute("SELECT to_regclass('should_not_exist')").fetchone()[0] is None
    assert pg[0].execute("SELECT count(*) FROM result").fetchone()[0] == 1


def test_real_pg_failed_new_migration_rolls_back_entire_install(pg):
    with pytest.raises(psycopg.Error):
        run_migrations(pg, [FOUNDATION, ("002_invalid.sql", "b" * 64, "SELECT undefined_column;")])
    pg[0].execute("ROLLBACK")
    assert pg[0].execute("SELECT to_regclass('result')").fetchone()[0] is None
    assert pg[0].execute("SELECT to_regclass('schema_migration')").fetchone()[0] is None


def test_real_pg_rejects_older_release_against_newer_schema(pg):
    run_migrations(pg, [FOUNDATION, ("002_next.sql", "b" * 64, "CREATE TABLE newer(id int);")])
    with pytest.raises(psycopg.Error, match="UNKNOWN_APPLIED_MIGRATION"):
        run_migrations(pg, [FOUNDATION])
    pg[0].execute("ROLLBACK")
    assert pg[0].execute("SELECT count(*) FROM schema_migration").fetchone()[0] == 2


@pytest.mark.parametrize("role_value,memberships,code", [
    ("t|t|f|f|f|f|t", "0", "EXISTING_ROLE_CONTRACT_MISMATCH"),
    ("t|f|f|f|f|t|t", "0", "EXISTING_ROLE_CONTRACT_MISMATCH"),
    ("t|f|f|f|f|f|t", "1", "UNEXPECTED_ROLE_MEMBERSHIP"),
])
def test_runtime_escalation_fails_before_migrations(monkeypatch, role_value, memberships, code):
    def query(statement, *_):
        if "pg_authid" in statement:
            return "f|f|f|f|f|f|t" if "abr_engine_owner" in statement else role_value
        if "pg_auth_members" in statement:
            return "0" if "abr_engine_owner" in statement else memberships
        pytest.fail("Unexpected SQL during role verification")
    monkeypatch.setattr(installer, "psql", query)
    with pytest.raises(installer.DatabaseSetupError, match=code):
        installer.verify_roles()
