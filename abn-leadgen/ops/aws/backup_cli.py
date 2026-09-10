"""Operator entry point; installation/approvals remain explicit and separate."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path

from backup_crypto import BackupError, public_key
from backup_restore import restore_backup
from backup_runtime import BackupAuthority, _admit, create_backup, publication_lease, publish_ledger
from backup_schedule import run_worker
from backup_store import S3Store
from cryptography.hazmat.primitives import serialization

from abr_engine.compliance.keys import load_keys
from abr_engine.config import load_settings
from abr_engine.control.service import DomainError, Service


def write_receipt(directory, name, result):
    if not directory.is_absolute() or not directory.is_dir() or directory.resolve() != directory:
        raise BackupError("BACKUP_RECEIPT_DIRECTORY_REQUIRED")
    if (directory / name).is_symlink():
        raise BackupError("BACKUP_RECEIPT_SYMLINK_REFUSED")
    handle, temporary = tempfile.mkstemp(prefix=".receipt-", dir=directory)
    try:
        with os.fdopen(handle, "w") as output:
            json.dump(result, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, directory / name)
        if os.name != "nt":
            fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["create", "ledger", "worker", "expire", "restore"])
    for name in ("config", "authority", "aws-cli", "public-key", "staging", "receipts"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--pg-bin", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--private-key-encrypted", action="store_true")
    parser.add_argument("--minimum-ledger-watermark")
    args = parser.parse_args()
    filename = "latest-" + {"create": "backup", "ledger": "ledger", "worker": "ledger-worker", "expire": "expiry", "restore": "restore"}[args.operation] + ".json"
    try:
        if not args.receipts.is_absolute() or not args.receipts.is_dir() or args.receipts.resolve() != args.receipts:
            raise BackupError("BACKUP_RECEIPT_DIRECTORY_REQUIRED")
        if args.config.suffix not in {".yaml", ".yml"} or args.config.name.startswith(".env"):
            raise BackupError("BACKUP_YAML_CONFIGURATION_REQUIRED")
        if args.authority.stat().st_size > 65536 or args.public_key.stat().st_size > 16384:
            raise BackupError("BACKUP_DOCUMENT_SIZE_LIMIT")
        authority = BackupAuthority.model_validate_json(args.authority.read_bytes())
        recipient = public_key(args.public_key.read_bytes())
        settings = load_settings(args.config)
        service = Service(settings, load_keys(settings))
        # The one-bucket installation budget is decimal 100 GB. An older authority
        # permitting 100 GiB must not raise that operator-selected storage ceiling.
        store = S3Store(args.aws_cli, args.bucket, authority.deployment_id,
            account_id=args.account_id, maximum_bytes=min(authority.maximum_bytes, 100_000_000_000))
        if args.operation == "create":
            if args.pg_bin is None:
                raise BackupError("BACKUP_POSTGRES_RUNTIME_REQUIRED")
            result = create_backup(settings, service, authority, recipient, store, args.staging, args.pg_bin)
        elif args.operation == "ledger":
            result = publish_ledger(settings, service, authority, recipient, store, args.staging)
        elif args.operation == "worker":
            result = run_worker(settings, service, authority, recipient, store, args.staging)
        elif args.operation == "expire":
            _admit(settings, service, authority, recipient, store)
            with publication_lease(args.staging, wait_seconds=120):
                result = store.expire(before_delete=lambda: _admit(settings, service, authority, recipient, store))
            _admit(settings, service, authority, recipient, store)
        else:
            if args.pg_bin is None or args.private_key is None or args.receipt is None or not args.minimum_ledger_watermark:
                raise BackupError("RESTORE_CUSTODY_RECEIPT_AND_CURRENT_WATERMARK_REQUIRED")
            if args.private_key.stat().st_size > 16384 or args.receipt.stat().st_size > 65536:
                raise BackupError("BACKUP_DOCUMENT_SIZE_LIMIT")
            password = getpass.getpass("Backup custody key password: ").encode() if args.private_key_encrypted else None
            key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=password)
            result = restore_backup(settings, service.keys, authority, key, store, json.loads(args.receipt.read_bytes()),
                args.staging, args.pg_bin, minimum_ledger_watermark=args.minimum_ledger_watermark)
        write_receipt(args.receipts, filename, result)
        print(json.dumps({"status": result.get("status", "complete"), "operation": args.operation, "receipt": filename}))
        return 3 if result.get("status") == "held" else 0
    except DomainError as exc:
        code = exc.code
    except BackupError as exc:
        code = str(exc)
    except Exception:  # noqa: BLE001 -- provider/DB/key diagnostics must never expose private data
        code = "BACKUP_OPERATION_FAILED"
    result = {"status": "held", "operation": args.operation, "code": code}
    try:
        write_receipt(args.receipts, filename, result)
    except Exception:  # noqa: BLE001 -- failure is still visible as a nonzero systemd result
        result["receipt_write"] = "failed"
    print(json.dumps(result))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
