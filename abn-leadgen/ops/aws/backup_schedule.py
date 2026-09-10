"""Nonblocking priority publisher. Timers must be separately installed and activated."""
from backup_crypto import BackupError
from backup_runtime import _admit, _publish_ledger, publication_lease

from abr_engine.control.service import DomainError
from abr_engine.db import connect
from abr_engine.ops import backup_queue


def run_worker(settings, service, authority, recipient, store, staging):
    """Coalesce attempts to a 240-second cadence; actual acknowledgment lag is measured.

    A dirty commit is visible immediately. Network work is performed by this separate
    process only; the 15-second poll never increases provider attempt frequency.
    """
    try:
        with publication_lease(staging):
            with connect(settings) as conn:
                current = backup_queue.health(conn)
                claimed = backup_queue.claim_attempt(conn)
            if not claimed:
                return {"status": "held" if current["last_error"] or current["acknowledgement_overdue"] else "coalesced",
                    "provider_operations": 0, **current}
            # Admission is repeated within _publish_ledger before upload and acknowledgment.
            _admit(settings, service, authority, recipient, store)
            receipt = _publish_ledger(settings, service, authority, recipient, store, staging)
            with connect(settings) as conn:
                current = backup_queue.health(conn)
            return {"status": "held" if current["acknowledgement_overdue"] else "acknowledged",
                "captured_generation": receipt["captured_generation"], "acknowledged": True,
                "ledger_watermark": receipt["ledger_watermark"], "object_id": receipt["object_id"], **current}
    except (DomainError, BackupError) as exc:
        if str(exc) == "BACKUP_PUBLICATION_BUSY":
            try:
                with connect(settings) as conn:
                    current = backup_queue.health(conn)
            except Exception:  # noqa: BLE001 -- unavailable DB remains a safe failed receipt
                return {"status": "held", "code": "BACKUP_PUBLISH_FAILED", "acknowledged": False}
            return {"status": "held" if current["acknowledgement_overdue"] else "deferred",
                "code": "BACKUP_PUBLICATION_BUSY", "provider_operations": 0, **current}
        code = "BACKUP_PUBLICATION_RECOVERY_REQUIRED" if str(exc) == "BACKUP_PUBLICATION_BUSY_OR_RECOVERY_REQUIRED" else "BACKUP_ADMISSION_HELD"
    except Exception:  # noqa: BLE001 -- discard provider/DB/key diagnostics at worker boundary
        code = "BACKUP_PUBLISH_FAILED"
    try:
        with connect(settings) as conn:
            backup_queue.failed(conn, code)
    except Exception:  # noqa: BLE001 -- durable systemd failure still reports unavailable DB
        code = "BACKUP_PUBLISH_FAILED"
    return {"status": "held", "code": code, "acknowledged": False}
