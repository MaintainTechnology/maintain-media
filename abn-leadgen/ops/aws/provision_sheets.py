"""Prepare NEW Sheets credentials and a disabled draft, with no activation.

Root Linux helper accepts only the freshly escrowed pair on stdin. It never
reads existing environment files, updates live settings, starts a service,
contacts Google, grants actor scopes, or creates a release-gate decision.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HOST = "ubuntu@3.104.119.142"
API_BASE_URL = "https://abn-engine.maintainmedia.com.au"
SPREADSHEET_ID = "1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58"
SHEET_ID = 2107750955
SCRIPT_ID = "1DzYHoVQ_X2_CoC6Dw4LaTXaXAYPRWBH2qPc34rEpY8nKtOGJFR2ZOmdn"
OWNER = "jeph@quotemax.com.au"
DIRECTORY = Path("/etc/abr-engine")
SYSTEMD = Path("/etc/systemd/system")
KEYS = {"ABR_SHEETS_SIGNING_KEY", "ABR_SHEETS_BRIDGE_SECRET"}
IDENTITY = {"purpose": "maintain-media-new-sheets-keys", "host": HOST, "api_base_url": API_BASE_URL,
            "spreadsheet_id": SPREADSHEET_ID, "sheet_id": SHEET_ID, "script_id": SCRIPT_ID, "owner": OWNER}


def validate_material(material):
    if (not isinstance(material, dict) or set(material) != KEYS
            or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{64}", value)
                   for value in material.values()) or len(set(material.values())) != 2):
        raise ValueError("SHEETS_NEW_KEY_PAIR_INVALID")
    return material


def digest(material):
    validate_material(material)
    return hashlib.sha256(json.dumps({"identity": IDENTITY, "material": material}, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def draft_registry():
    # Deliberately invalid as BridgeRegistry: key installation is not actor/G5 approval.
    return {"schema_version": 1, "enabled": False, "spreadsheet_id": SPREADSHEET_ID, "sheet_id": SHEET_ID,
            "owner_email": OWNER, "approved_by": "", "evidence_ref": "", "evidence_sha256": "",
            "verified_at": None, "expires_at": None, "editors": {OWNER: []}}


def contents(material):
    validate_material(material)
    return {"environment": "".join(key + "=" + material[key] + "\n" for key in sorted(KEYS)).encode(),
            "registry": (json.dumps(draft_registry(), sort_keys=True, indent=2) + "\n").encode(),
            "api_dropin": b"[Service]\nEnvironmentFile=/etc/abr-engine/sheets.env\n"}


def targets():
    return {"environment": (DIRECTORY / "sheets.env", 0o600),
            "registry": (DIRECTORY / "sheets-bridge.pending.yaml", 0o600),
            "api_dropin": (SYSTEMD / "abr-engine-api.service.d/75-maintain-media-sheets.conf", 0o644)}


def install(material):
    # Import only after input validation; default review does not load platform-specific helpers.
    from provision_private_files import OwnedFiles

    validate_material(material)
    installer = OwnedFiles(directory=DIRECTORY, marker_name="sheets-installation.json",
                           targets=targets(), identity={key: str(value) for key, value in IDENTITY.items()})
    installed = installer.install(contents(material), digest(material))
    return {"status": "sheets_key_preparation_installed", "material_sha256": digest(material),
            "spreadsheet_id": SPREADSHEET_ID, "sheet_id": SHEET_ID, "replayed": installed["replayed"],
            "script_properties_installed": False, "script_enabled": False, "registry_enabled": False,
            "settings_changed": False, "services_started": False, "services_reloaded": False,
            "capabilities_changed": False, "release_approvals_created": False, "vendor_calls": 0}


def main():
    if sys.argv[1:] != ["--apply"]:
        print(json.dumps({"status": "review_only", "host": HOST, "spreadsheet_id": SPREADSHEET_ID,
                          "script_enabled": False, "registry_enabled": False, "vendor_calls": 0}))
        return 0
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("LINUX_ROOT_REQUIRED")
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ValueError("SHEETS_INPUT_TOO_LARGE")
        print(json.dumps(install(validate_material(json.loads(raw)))))
        return 0
    except Exception:  # noqa: BLE001 - never reflect keys, provider data or exception details
        print(json.dumps({"status": "blocked", "code": "SHEETS_PREPARATION_UNCONFIRMED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
