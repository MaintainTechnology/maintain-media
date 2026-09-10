"""Prepare a NEW Sheets key pair, then show it once for the owner UI transfer.

The initial loopback page contains no credential values. Only an exact-origin,
CSRF-bound form POST reveals the newly escrowed pair. No existing key cache,
environment file, browser profile or Google connector is read. The caller must
keep the actual owner's Script Properties ENABLED=false when transferring.
"""
from __future__ import annotations

import hmac
import html
import json
import os
import secrets
import sys
from http.server import HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from provision_ghl_client import (
    REMOTE as GHL_REMOTE,
)
from provision_ghl_client import (
    Handoff,
    TokenEscrow,
    canonical,
    handler_for,
    local_lock,
    ssh_command,
)
from provision_runtime_client import run_process, secure_directory
from provision_sheets import API_BASE_URL, HOST, IDENTITY, SHEET_ID, SPREADSHEET_ID, digest, validate_material

REMOTE = "sudo /usr/bin/python3 /home/ubuntu/abn-host-bootstrap-20260910/provision_sheets.py --apply"


class SheetsSetupFailure(RuntimeError):
    pass


class SheetsEscrow(TokenEscrow):
    """Reuse the reviewed non-replacing DPAPI storage with a separate exact contract."""

    stage_prefix = ".new-sheets-"

    def validate(self, record):
        if (not isinstance(record, dict) or set(record) != {"version", "identity", "material", "material_sha256"}
                or record["version"] != 1 or record["identity"] != IDENTITY
                or not isinstance(record["material_sha256"], str)
                or not hmac.compare_digest(record["material_sha256"], digest(record["material"]))):
            raise SheetsSetupFailure("SHEETS_ESCROW_TARGET_MISMATCH")
        return record

    def make_record(self, material):
        validate_material(material)
        return {"version": 1, "identity": dict(IDENTITY), "material": material, "material_sha256": digest(material)}


def fresh_material():
    return {"ABR_SHEETS_SIGNING_KEY": secrets.token_urlsafe(48),
            "ABR_SHEETS_BRIDGE_SECRET": secrets.token_urlsafe(48)}


def command_for(base):
    command = ssh_command(base)  # Same reviewed host-key pin and disabled ambient SSH configuration.
    if command[-2:] != [HOST, GHL_REMOTE]:
        raise SheetsSetupFailure("SHEETS_PINNED_TARGET_MISMATCH")
    return [*command[:-1], REMOTE]


def remote_prepare(command, material, *, runner=run_process):
    try:
        response = runner(command, data=canonical(material), timeout=90)
        receipt = json.loads(response.stdout)
        if (response.returncode != 0 or not isinstance(receipt, dict)
                or receipt.get("status") != "sheets_key_preparation_installed"
                or receipt.get("spreadsheet_id") != SPREADSHEET_ID or receipt.get("sheet_id") != SHEET_ID
                or receipt.get("material_sha256") != digest(material)
                or any(receipt.get(key) is not False for key in (
                    "script_properties_installed", "script_enabled", "registry_enabled", "settings_changed",
                    "services_started", "services_reloaded", "capabilities_changed", "release_approvals_created"))
                or receipt.get("vendor_calls") != 0):
            raise SheetsSetupFailure("SHEETS_REMOTE_PREPARATION_UNCONFIRMED")
    except Exception:  # noqa: BLE001 - subprocess output or unexpected errors must never expose key values
        raise SheetsSetupFailure("SHEETS_REMOTE_PREPARATION_UNCONFIRMED") from None


def coordinate(escrow, command, *, prepare=remote_prepare):
    record = escrow.load() if escrow.path.exists() else escrow.save_new(fresh_material())
    prepare(command, record["material"])  # Both targets always use this same durable pair on recovery.
    return record


def display_handler(handoff, material):
    base = handler_for(handoff)  # Reuse no logs, generic errors, exact Host and corrected privacy/CSP headers.

    class Handler(base):  # type: ignore[valid-type, misc]  # Runtime factory preserves the reviewed HTTP protections.
        def do_GET(self):
            if not self.correct_host():
                return self.reply(403, "Request refused.")
            if self.path != handoff.path or not handoff.alive() or handoff.consumed:
                return self.reply(410, "This setup display is unavailable.")
            return self.reply(200, '<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Maintain Media Google setup</title><body><h1>Google Sheet connection</h1>'
                '<form method="post" action="' + handoff.path + '">'
                '<input type="hidden" name="csrf" value="' + handoff.csrf + '">'
                '<button type="submit">Load new setup values</button></form></body></html>')

        def do_POST(self):
            if (not self.correct_host() or self.headers.get_all("Origin", []) != [handoff.origin]
                    or self.path not in {handoff.path, handoff.path + "/clear"}
                    or self.headers.get_all("Content-Type", []) != ["application/x-www-form-urlencoded"]
                    or self.headers.get_all("Transfer-Encoding", [])
                    or len(self.headers.get_all("Content-Length", [])) != 1):
                return self.reply(403, "Request refused.")
            if not handoff.alive():
                return self.reply(410, "This setup display is unavailable.")
            try:
                text_length = self.headers["Content-Length"]
                length = int(text_length)
                if str(length) != text_length or not 1 <= length <= 256:
                    return self.reply(413, "Request refused.")
                raw = self.rfile.read(length)
                if len(raw) != length or not handoff.alive():
                    return self.reply(410, "This setup display is unavailable.")
                form = parse_qs(raw.decode("utf-8", errors="strict"), strict_parsing=True, max_num_fields=1)
                if (set(form) != {"csrf"} or len(form["csrf"]) != 1
                        or not hmac.compare_digest(form["csrf"][0], handoff.csrf)):
                    return self.reply(403, "Request refused.")
            except Exception:  # noqa: BLE001 - never reflect request content
                return self.reply(400, "Request refused.")
            if self.path.endswith("/clear") and handoff.consumed:
                handoff.completed_at = handoff.clock() - 30
                return self.reply(200, "Setup values cleared. Keep Google synchronization disabled.")
            if handoff.consumed or self.path != handoff.path:
                return self.reply(410, "This setup display is unavailable.")
            handoff.consumed = True
            handoff.completed_at = handoff.clock()
            handoff.result = {"status": "new_sheets_setup_values_displayed", "google_transfer_verified": False,
                              "script_enabled": False, "registry_enabled": False}
            properties = {"API_BASE_URL": API_BASE_URL, "ENABLED": "false",
                "SERVICE_SIGNING_KEY": material["ABR_SHEETS_SIGNING_KEY"],
                "BRIDGE_SECRET": material["ABR_SHEETS_BRIDGE_SECRET"]}
            # These are this setup's NEW keys, revealed only by the explicit one-use action.
            # Read-only text lets the owner UI copy rendered values without password-field redaction.
            rows = "".join('<p><label>' + name + '<input name="' + name
                + '" type="text" readonly autocomplete="off" spellcheck="false" value="'
                + html.escape(value, quote=True) + '"></label></p>'
                for name, value in properties.items())
            return self.reply(200, '<!doctype html><html lang="en"><meta charset="utf-8">'
                '<title>Maintain Media Google setup</title><body><h1>New setup values</h1>'
                '<p>Transfer only into the verified owner-only standalone script. Keep ENABLED false.</p>' + rows
                + '<form method="post" action="' + handoff.path + '/clear">'
                '<input type="hidden" name="csrf" value="' + handoff.csrf + '">'
                '<button type="submit">Clear this page</button></form></body></html>')

    return Handler


def serve_values(record):
    material = validate_material(record["material"])
    handoff = Handoff(lambda _: None)
    with HTTPServer(("127.0.0.1", 0), display_handler(handoff, material)) as server:
        handoff.origin = "http://127.0.0.1:" + str(server.server_port)
        server.timeout = 1
        print(json.dumps({"status": "server_prepared_owner_transfer_pending", "url": handoff.origin + handoff.path,
                          "expires_in_seconds": 600, "initial_page_contains_keys": False}), flush=True)
        while ((not handoff.consumed and handoff.alive())
               or handoff.completed_at is not None and handoff.clock() < handoff.completed_at + 30):
            server.handle_request()
    return handoff.result or {"status": "blocked", "code": "SHEETS_VALUE_DISPLAY_EXPIRED"}


def apply():
    if os.name != "nt":
        raise SheetsSetupFailure("WINDOWS_NEW_KEY_ESCROW_REQUIRED")
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or Path(local).resolve() != Path("C:/Users/dalig/AppData/Local").resolve():
        raise SheetsSetupFailure("SHEETS_APPROVED_LOCAL_USER_REQUIRED")
    base = Path(local) / "MaintainMedia/aws"
    command = command_for(base)
    directory = base / "new-sheets-key-escrow"
    secure_directory(directory)
    with local_lock(directory / "handoff.lock"):
        escrow = SheetsEscrow(directory / "maintain-media-sheets-20260911.dpapi")
        record = coordinate(escrow, command)
        return serve_values(record)


def main():
    if sys.argv[1:] != ["--prepare"]:
        print(json.dumps({"status": "review_only", "host": HOST, "spreadsheet_id": SPREADSHEET_ID,
                          "initial_page_contains_keys": False, "script_enabled": False, "registry_enabled": False}))
        return 0
    try:
        result = apply()
        print(json.dumps(result), flush=True)
        return 0 if result.get("status") == "new_sheets_setup_values_displayed" else 2
    except Exception:  # noqa: BLE001 - no key, subprocess output or exception text in terminal
        print(json.dumps({"status": "blocked", "code": "SHEETS_PREPARATION_UNCONFIRMED",
                          "resume": "Retain this setup's encrypted pair and rerun --prepare; do not rotate keys."}),
              flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
