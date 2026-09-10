"""Provision the one private engine database on the approved Ubuntu host.

No credentials, source rows, gates, environment files or business data are read.
PostgreSQL peer authentication binds the runtime to its locked OS service user.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path

DATABASE = "abr_leadgen"
OWNER = "abr_engine_owner"
RUNTIME = "abr-engine"
MARKER = Path("/var/lib/abr-host-bootstrap/database.json")


class DatabaseSetupError(ValueError):
    pass


def psql(query: str, database: str = "postgres") -> str:
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", "psql", "-X", "-A", "-t", "-q",
         "-v", "ON_ERROR_STOP=1", "-d", database], input=query, text=True,
        capture_output=True, check=False, timeout=180,
    )
    if result.returncode:
        raise DatabaseSetupError("DATABASE_OPERATION_FAILED")
    return result.stdout.strip()


def marker_value() -> dict:
    return {"version": 1, "hostname": socket.gethostname(), "database": DATABASE,
            "owner": OWNER, "runtime": RUNTIME}


def safe_regular(path: Path) -> None:
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise DatabaseSetupError("SYMLINK_REFUSED")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DatabaseSetupError("REGULAR_UNLINKED_FILE_REQUIRED")


def admit() -> bool:
    if getattr(os, "geteuid", lambda: -1)() != 0:
        raise DatabaseSetupError("ROOT_REQUIRED")
    parent = MARKER.parent
    if (any(part.is_symlink() for part in (parent, *parent.parents))
            or not parent.is_dir() or parent.stat().st_uid != 0
            or stat.S_IMODE(parent.stat().st_mode) & 0o022):
        raise DatabaseSetupError("APPROVED_HOST_FOUNDATION_REQUIRED")
    owned = MARKER.exists()
    if owned:
        safe_regular(MARKER)
        if (MARKER.stat().st_size > 2048 or MARKER.stat().st_uid != 0
                or stat.S_IMODE(MARKER.stat().st_mode) != 0o600
                or json.loads(MARKER.read_text()) != marker_value()):
            raise DatabaseSetupError("DATABASE_MARKER_MISMATCH")
    existing = psql("SELECT datname FROM pg_database WHERE datname='abr_leadgen';")
    roles = psql("SELECT rolname FROM pg_roles WHERE rolname IN ('abr_engine_owner','abr-engine');")
    if not owned and (existing or roles):
        raise DatabaseSetupError("EXISTING_DATABASE_OR_ROLES_REFUSED")
    version = psql("SHOW server_version_num;")
    if not version.isdigit() or int(version) // 10000 != 16:
        raise DatabaseSetupError("POSTGRESQL_16_REQUIRED")
    return owned


def verify_roles() -> None:
    for name in (OWNER, RUNTIME):
        role = psql("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls, "
                    f"rolpassword IS NULL FROM pg_authid WHERE rolname='{name}';")
        if role != ("t|f|f|f|f|f|t" if name == RUNTIME else "f|f|f|f|f|f|t"):
            raise DatabaseSetupError("EXISTING_ROLE_CONTRACT_MISMATCH")
        if psql("SELECT count(*) FROM pg_auth_members WHERE member="
                f"(SELECT oid FROM pg_roles WHERE rolname='{name}');") != "0":
            raise DatabaseSetupError("UNEXPECTED_ROLE_MEMBERSHIP")


def provision() -> dict:
    owned = admit()
    if not owned:
        fd = os.open(MARKER, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(marker_value(), stream, sort_keys=True)
    # Static identifiers only. An interrupted owned setup can add only missing
    # objects; existing roles are verified, never silently elevated or reset.
    for name, clause in ((OWNER, "NOLOGIN"), (RUNTIME, "LOGIN")):
        exists = psql(f"SELECT 1 FROM pg_roles WHERE rolname='{name}';")
        if not exists:
            psql(f'CREATE ROLE "{name}" {clause} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;')
    verify_roles()
    if not psql("SELECT 1 FROM pg_database WHERE datname='abr_leadgen';"):
        psql('CREATE DATABASE abr_leadgen OWNER abr_engine_owner ENCODING \'UTF8\' TEMPLATE template0;')
    if psql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='abr_leadgen';") != OWNER:
        raise DatabaseSetupError("DATABASE_OWNER_MISMATCH")
    psql('REVOKE ALL ON DATABASE abr_leadgen FROM PUBLIC; GRANT CONNECT ON DATABASE abr_leadgen TO "abr-engine";')
    psql('REVOKE ALL ON SCHEMA public FROM PUBLIC; ALTER SCHEMA public OWNER TO abr_engine_owner; '
         'GRANT USAGE ON SCHEMA public TO "abr-engine";', DATABASE)
    return {"status": "private_database_provisioned", "database": DATABASE,
            "runtime": RUNTIME, "authentication": "unix_socket_peer", "password_created": False,
            "source_records_created": False, "release_approvals_created": False}


def migration_inventory(root: Path) -> list[tuple[str, str, str]]:
    directory = root / "migrations"
    if directory.is_symlink() or not directory.is_dir():
        raise DatabaseSetupError("MIGRATION_DIRECTORY_REQUIRED")
    result = []
    for file in sorted(directory.iterdir()):
        if not re.fullmatch(r"[0-9]{3}_[a-z0-9_]+\.sql", file.name):
            raise DatabaseSetupError("UNEXPECTED_MIGRATION_FILE")
        safe_regular(file)
        content = file.read_bytes()
        if not content or len(content) > 2_000_000:
            raise DatabaseSetupError("MIGRATION_SIZE_INVALID")
        # psql metacommands could escape the scoped SQL transaction. These files
        # are reviewed migrations, but the installer refuses client commands too.
        text = content.decode("utf-8")
        if re.search(r"(?m)^\s*\\", text):
            raise DatabaseSetupError("PSQL_METACOMMAND_REFUSED")
        result.append((file.name, hashlib.sha256(content).hexdigest(), text))
    if not result or result[0][0] != "001_foundation.sql":
        raise DatabaseSetupError("FOUNDATION_MIGRATION_REQUIRED")
    return result


def migration_sql(migrations: list[tuple[str, str, str]]) -> str:
    for name, digest, _ in migrations:
        if not re.fullmatch(r"[0-9]{3}_[a-z0-9_]+\.sql", name) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise DatabaseSetupError("MIGRATION_IDENTITY_INVALID")
    if not migrations:
        raise DatabaseSetupError("FOUNDATION_MIGRATION_REQUIRED")
    names = ",".join("'" + item[0] + "'" for item in migrations)
    statements = [
        "BEGIN; SET LOCAL ROLE abr_engine_owner; SET LOCAL statement_timeout='120s';",
        "SET LOCAL standard_conforming_strings=on;",
        "SELECT pg_advisory_xact_lock(546145551010);",
        "CREATE TABLE IF NOT EXISTS schema_migration (name text PRIMARY KEY,digest text NOT NULL);",
        "LOCK TABLE schema_migration IN EXCLUSIVE MODE;",
        "DO $inventory$ BEGIN IF EXISTS (SELECT 1 FROM schema_migration WHERE name NOT IN ("
        + names + ")) THEN RAISE EXCEPTION 'UNKNOWN_APPLIED_MIGRATION'; END IF; END $inventory$;",
    ]
    for name, digest, content in migrations:
        # Checks and application share one transaction and lock. Escape the SQL
        # as a literal so migration text cannot terminate this control block.
        if not re.fullmatch(r"[0-9]{3}_[a-z0-9_]+\.sql", name) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise DatabaseSetupError("MIGRATION_IDENTITY_INVALID")
        body = content.replace("'", "''")
        tag = "$migration_" + digest + "$"
        if tag in content:
            raise DatabaseSetupError("MIGRATION_DELIMITER_COLLISION")
        statements.append(f"""DO {tag}
DECLARE previous text;
BEGIN
  SELECT sm.digest INTO previous FROM schema_migration sm WHERE sm.name='{name}';
  IF FOUND THEN
    IF previous != '{digest}' THEN RAISE EXCEPTION 'APPLIED_MIGRATION_CHANGED'; END IF;
  ELSE
    EXECUTE '{body}';
    INSERT INTO schema_migration VALUES('{name}','{digest}');
  END IF;
END {tag};""")
    statements += [
        'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO "abr-engine";',
        'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO "abr-engine";',
        'REVOKE ALL ON schema_migration,release_gate,policy FROM "abr-engine";',
        'REVOKE UPDATE,DELETE ON suppression_event,suppression_alias FROM "abr-engine";',
        'REVOKE ALL ON backup_ledger_state FROM "abr-engine";',
        'GRANT SELECT,UPDATE ON backup_ledger_state TO "abr-engine";',
        'GRANT SELECT ON schema_migration,release_gate,policy TO "abr-engine";', "COMMIT;",
    ]
    return "\n".join(statements)


@contextmanager
def installation_lock():
    # The fixed, root-owned parent was checked before opening this file. A
    # second installer fails immediately instead of racing partial provisioning.
    import fcntl
    admit()
    path = MARKER.parent / "database.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            raise DatabaseSetupError("INVALID_DATABASE_LOCK")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DatabaseSetupError("DATABASE_INSTALLATION_BUSY") from error
        yield
    finally:
        os.close(fd)


def migrate(root: Path) -> dict:
    admit()
    if not MARKER.exists():
        raise DatabaseSetupError("OWNED_DATABASE_REQUIRED")
    migrations = migration_inventory(root)
    # Validate the complete release against its trusted manifest before invoking
    # this command. Applied migrations are additionally protected by DB hashes.
    if psql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='abr_leadgen';") != OWNER:
        raise DatabaseSetupError("DATABASE_OWNER_MISMATCH")
    verify_roles()
    psql(migration_sql(migrations), DATABASE)
    verify_roles()
    forbidden = psql("SELECT count(*) FROM (VALUES ('schema_migration'),('release_gate'),('policy')) AS t(name) "
                     "WHERE has_table_privilege('abr-engine',name,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER');", DATABASE)
    if forbidden != "0":
        raise DatabaseSetupError("RUNTIME_AUTHORITY_EXCEEDED")
    if psql("SELECT count(*) FROM (VALUES ('suppression_event'),('suppression_alias')) AS t(name) "
            "WHERE has_table_privilege('abr-engine',name,'UPDATE,DELETE,TRUNCATE');", DATABASE) != "0":
        raise DatabaseSetupError("SUPPRESSION_HISTORY_MUTATION_ALLOWED")
    if psql("SELECT has_table_privilege('abr-engine','backup_ledger_state','SELECT') "
            "AND has_table_privilege('abr-engine','backup_ledger_state','UPDATE') "
            "AND NOT has_table_privilege('abr-engine','backup_ledger_state','INSERT,DELETE,TRUNCATE,REFERENCES,TRIGGER');", DATABASE) != "t":
        raise DatabaseSetupError("BACKUP_QUEUE_PRIVILEGE_MISMATCH")
    if psql("SELECT has_database_privilege('abr-engine','abr_leadgen','CONNECT') "
            "AND has_schema_privilege('abr-engine','public','USAGE') "
            "AND (SELECT bool_and(has_table_privilege('abr-engine','system_state',permission)) "
            "FROM (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE')) AS p(permission));", DATABASE) != "t":
        raise DatabaseSetupError("RUNTIME_DATA_ACCESS_MISSING")
    return {"status": "production_schema_migrated", "verified": [item[0] for item in migrations],
            "total_migrations": len(migrations), "runtime_can_approve_gates": False,
            "source_records_created": False, "release_approvals_created": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["provision", "migrate"])
    parser.add_argument("--root", type=Path, default=Path("/opt/abn-leadgen"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"status": "review_only", "database": DATABASE, "action": args.action}))
        return 0
    try:
        with installation_lock():
            result = provision() if args.action == "provision" else migrate(args.root)
        print(json.dumps(result))
        return 0
    except (DatabaseSetupError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        code = str(error) if isinstance(error, DatabaseSetupError) else "DATABASE_SETUP_UNAVAILABLE"
        print(json.dumps({"status": "blocked", "code": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
