"""New backup key custody and pinned stdin installation; no AWS provider commands.

--prepare accepts only a newly created publisher credential from stdin and saves
two separate current-user DPAPI escrows. --install resumes that owned escrow and
sends only the publisher credential and RSA public recipient to the fixed host.
Default invocation does neither. Never use this to import existing .env files.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from backup_crypto import fingerprint
from backup_infrastructure import ACCOUNT, BUCKET, DEPLOYMENT, MAXIMUM_BYTES, REGION
from backup_install_identity import validate_material
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SCHEMA = "abr-new-backup-dpapi-escrow-v1"
BASE = Path("C:/Users/dalig/AppData/Local/MaintainMedia/aws")
HOST = "ubuntu@3.104.119.142"
REMOTE = ("sudo env PYTHONPATH=/opt/abn-leadgen/src /opt/abn-leadgen/.venv/bin/python "
          "/opt/abn-leadgen/ops/aws/backup_install_identity.py --apply")


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def validate_state(state):
    if (not isinstance(state, dict) or set(state) != {"schema", "deployment_id", "kind", "stage", "material", "material_sha256"}
            or state["schema"] != SCHEMA or state["deployment_id"] != DEPLOYMENT
            or state["kind"] not in {"private_recipient", "publisher_identity"}
            or state["stage"] not in {"prepared", "remote_pending", "complete"}
            or state["material_sha256"] != digest(state["material"])):
        raise ValueError("BACKUP_ESCROW_TARGET_OR_MATERIAL_MISMATCH")
    material = state["material"]
    if state["kind"] == "publisher_identity":
        validate_material(material)
    else:
        if (state["stage"] != "prepared" or not isinstance(material, dict)
                or set(material) != {"private_recipient_pem", "public_recipient_pem"}
                or any(not isinstance(value, str) for value in material.values())):
            raise ValueError("BACKUP_PRIVATE_CUSTODY_INVALID")
        key = serialization.load_pem_private_key(material["private_recipient_pem"].encode("ascii"), password=None)
        if (not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 3072
                or key.public_key().public_bytes(serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo).decode() != material["public_recipient_pem"]):
            raise ValueError("BACKUP_PRIVATE_CUSTODY_INVALID")
    return state


def helper():
    """Reuse reviewed DPAPI/ACL/recovery primitives in an isolated module namespace."""
    spec = importlib.util.spec_from_file_location("_backup_new_dpapi", Path(__file__).with_name("provision_runtime_client.py"))
    if spec is None or spec.loader is None:
        raise ValueError("BACKUP_CUSTODY_RUNTIME_UNAVAILABLE")
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ENTROPY = b"MaintainMedia/ABN/new-backup-custody/983c39eb/v1"
    module.validate_state = validate_state
    return module


def state(kind, material):
    return validate_state({"schema": SCHEMA, "deployment_id": DEPLOYMENT, "kind": kind,
        "stage": "prepared", "material": material, "material_sha256": digest(material)})


def new_recipient():
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    return state("private_recipient", {
        "private_recipient_pem": key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        "public_recipient_pem": key.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo).decode()})


def prepare(credentials, private_escrow, identity_escrow):
    if (not isinstance(credentials, dict) or set(credentials) != {"AccessKeyId", "SecretAccessKey"}
            or any(not isinstance(value, str) for value in credentials.values())):
        raise ValueError("NEW_PUBLISHER_CREDENTIAL_REQUIRED")
    # Recover a completed first encrypted write before deciding to generate keys.
    private_escrow.recover()
    private = private_escrow.load() if private_escrow.path.exists() else new_recipient()
    if private["kind"] != "private_recipient":
        raise ValueError("BACKUP_PRIVATE_CUSTODY_INVALID")
    if not private_escrow.path.exists():
        private_escrow.save(private)
    material = {"account_id": ACCOUNT, "region": REGION, "deployment_id": DEPLOYMENT, "bucket": BUCKET,
        "access_key_id": credentials["AccessKeyId"], "secret_access_key": credentials["SecretAccessKey"],
        "public_recipient_pem": private["material"]["public_recipient_pem"]}
    proposed = state("publisher_identity", material)
    identity_escrow.recover()
    if identity_escrow.path.exists():
        current = identity_escrow.load()
        if current["kind"] != "publisher_identity" or current["material_sha256"] != proposed["material_sha256"]:
            raise ValueError("BACKUP_EXISTING_CREDENTIAL_ROTATION_REQUIRES_REVIEW")
    else:
        identity_escrow.save(proposed)
    return {"status": "new_backup_material_escrowed", "deployment_id": DEPLOYMENT,
        "escrow": "two_current_user_dpapi_files", "recipient_sha256": fingerprint(validate_material(material)),
        "material_sha256": digest(material), "provider_operations": 0, "host_installed": False}


def command(module):
    ssh = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/OpenSSH/ssh.exe"
    identity, known_hosts = BASE / "keys/abn-leadgen-sydney-20260910", BASE / "known_hosts"
    for path in (ssh, identity, known_hosts):
        module.ordinary(path)
        if not path.is_file():
            raise ValueError("BACKUP_PINNED_SSH_REQUIRED")
    return [str(ssh), "-F", "NUL", "-i", str(identity), "-o", "UserKnownHostsFile=" + str(known_hosts),
        "-o", "GlobalKnownHostsFile=NUL", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no",
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ForwardAgent=no",
        "-o", "KexAlgorithms=curve25519-sha256", "-o", "HostKeyAlgorithms=ssh-ed25519",
        "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15", HOST, REMOTE]


def install(private_escrow, identity_escrow, ssh_command, runner):
    private_escrow.recover()
    identity_escrow.recover()
    private, identity = private_escrow.load(), identity_escrow.load()
    if private["kind"] != "private_recipient" or identity["kind"] != "publisher_identity":
        raise ValueError("BACKUP_ESCROW_KIND_MISMATCH")
    material = identity["material"]
    if material["public_recipient_pem"] != private["material"]["public_recipient_pem"]:
        raise ValueError("BACKUP_RECIPIENT_CUSTODY_MISMATCH")
    identity["stage"] = "remote_pending"
    identity_escrow.save(identity)
    response = runner(ssh_command, data=canonical(material), timeout=180)
    try:
        receipt = json.loads(response.stdout)
    except (ValueError, TypeError):
        raise ValueError("BACKUP_REMOTE_INSTALLATION_UNCONFIRMED") from None
    if (response.returncode != 0 or not isinstance(receipt, dict)
            or receipt.get("status") != "private_backup_identity_installed"
            or receipt.get("deployment_id") != DEPLOYMENT or receipt.get("bucket") != BUCKET
            or receipt.get("maximum_bytes") != MAXIMUM_BYTES
            or receipt.get("material_sha256") != identity["material_sha256"]
            or receipt.get("recipient_sha256") != fingerprint(validate_material(material))
            or receipt.get("private_backup_key_on_host") is not False
            or receipt.get("runtime_capabilities_enabled") != []
            or receipt.get("release_approvals_created") is not False or receipt.get("services_enabled") is not False):
        raise ValueError("BACKUP_REMOTE_INSTALLATION_UNCONFIRMED")
    identity["stage"] = "complete"
    identity_escrow.save(identity)
    # Never reflect unrecognized provider/SSH fields, even alongside a valid receipt.
    public_fields = {"status", "deployment_id", "bucket", "maximum_bytes", "material_sha256", "recipient_sha256",
        "private_backup_key_on_host", "runtime_capabilities_enabled", "release_approvals_created", "services_enabled"}
    return {name: receipt[name] for name in public_fields} | {
        "custody": "separate_current_user_dpapi", "provider_operations": 0}


def main():
    if sys.argv[1:] not in [["--prepare"], ["--install"]]:
        print(json.dumps({"status": "review_only", "provider_operations": 0, "external_mutations": False,
            "bucket": BUCKET, "private_key_sent_to_host": False}))
        return 0
    try:
        if os.name != "nt" or Path(os.environ.get("LOCALAPPDATA", "")).resolve() != BASE.parents[1].resolve():
            raise ValueError("BACKUP_WINDOWS_CUSTODIAN_REQUIRED")
        module = helper()
        directory = BASE / "backup-key-escrow-983c39eb"
        module.secure_directory(directory)
        private = module.Escrow(directory / "private-recipient.dpapi")
        identity = module.Escrow(directory / "publisher-identity.dpapi")
        with module.coordinator_lock(directory / "coordinator.lock"):
            if sys.argv[1] == "--prepare":
                raw = sys.stdin.buffer.read(4097)
                if len(raw) > 4096:
                    raise ValueError("BACKUP_CREDENTIAL_INPUT_LIMIT")
                receipt = prepare(json.loads(raw), private, identity)
            else:
                receipt = install(private, identity, command(module), module.run_process)
        print(json.dumps(receipt))
        return 0
    except Exception:  # noqa: BLE001 -- confidential input/native output may never appear in diagnostics
        print(json.dumps({"status": "held", "code": "BACKUP_CUSTODY_OR_INSTALLATION_UNCONFIRMED",
            "recovery": "Keep the new DPAPI escrow and reconcile the same credential; do not generate replacements."}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
