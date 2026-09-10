"""Bounded durable replication intent; never contacts a provider in a restriction transaction."""
from datetime import datetime

from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError


def state(conn):
    value = conn.execute("SELECT * FROM backup_ledger_state WHERE singleton").fetchone()
    if value is None:
        raise DomainError("BACKUP_QUEUE_MIGRATION_REQUIRED", 503)
    return value


def claim_attempt(conn):
    """At most one attempt per 240 seconds, across concurrent workers/restarts."""
    return conn.execute(
        "UPDATE backup_ledger_state SET last_attempt_at=clock_timestamp() WHERE singleton "
        "AND (last_attempt_at IS NULL OR last_attempt_at <= clock_timestamp()-interval '240 seconds') "
        "RETURNING generation,acknowledged_generation,last_attempt_at"
    ).fetchone()


def acknowledge(conn, generation, receipt):
    # Closed receipt, no caller/provider text. Snapshot generation alone may be acknowledged.
    safe = {key: receipt[key] for key in ("object_id", "sha256", "encrypted_bytes", "ledger_watermark")}
    row = conn.execute(
        "UPDATE backup_ledger_state SET acknowledged_generation=GREATEST(acknowledged_generation,%s),"
        "pending_since=CASE WHEN generation=%s THEN NULL ELSE pending_since END,"
        "last_acknowledged_at=clock_timestamp(),last_receipt=%s,last_error=NULL,consecutive_failures=0 "
        "WHERE singleton AND generation>=%s RETURNING acknowledged_generation,generation",
        (generation, generation, Jsonb(safe), generation),
    ).fetchone()
    if row is None:
        raise DomainError("BACKUP_QUEUE_ACKNOWLEDGEMENT_INVALID", 503)
    return row


def failed(conn, code):
    # Never store a provider or exception body, even if it resembles a code.
    safe = code if code in {"BACKUP_ADMISSION_HELD", "BACKUP_PUBLICATION_RECOVERY_REQUIRED", "BACKUP_PUBLISH_FAILED"} else "BACKUP_PUBLISH_FAILED"
    conn.execute("UPDATE backup_ledger_state SET last_error=%s,consecutive_failures=LEAST(consecutive_failures::bigint+1,2147483647) WHERE singleton", (safe,))


def health(conn):
    row = state(conn)
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    age = max(0, int((now-row["pending_since"]).total_seconds())) if row["pending_since"] else 0
    acknowledged_age = max(0, int((now-row["last_acknowledged_at"]).total_seconds())) if row["last_acknowledged_at"] else None
    snapshot_age = None
    if row["last_receipt"]:
        watermark = datetime.fromisoformat(row["last_receipt"]["ledger_watermark"])
        if watermark.tzinfo is None:
            raise DomainError("BACKUP_QUEUE_WATERMARK_INVALID", 503)
        snapshot_age = max(0, int((now-watermark).total_seconds()))
    return {"pending": row["generation"] > row["acknowledged_generation"], "pending_seconds": age,
        "acknowledgement_age_seconds": acknowledged_age, "last_error": row["last_error"],
        "snapshot_age_seconds": snapshot_age,
        "acknowledgement_overdue": age > 300 or acknowledged_age is not None and acknowledged_age > 300
            or snapshot_age is not None and snapshot_age > 300}
