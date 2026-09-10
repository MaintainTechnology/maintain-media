"""One-use localhost handoff for a NEW private-integration token.

No browser DOM/clipboard extraction, plaintext file, credential discovery, .env
read, shell argument token, vendor request, or service start. Only --receive
opens the password form; --resume replays this helper's own encrypted record.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import sys
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from provision_ghl import HOST, LOCATION, digest, validate_material
from provision_runtime_client import dpapi, ordinary, secure_directory, verify_acl

REMOTE = ("sudo /usr/bin/python3 "
          "/home/ubuntu/abn-host-bootstrap-20260910/provision_ghl.py --apply")
MAX_BODY = 4096
LIFETIME = 600


class HandoffFailure(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_record(record):
    if (not isinstance(record, dict) or set(record) != {"version", "purpose", "host", "location", "material",
                                                       "material_sha256"}
            or record["version"] != 1 or record["purpose"] != "maintain-media-new-ghl-token"
            or record["host"] != HOST or record["location"] != LOCATION
            or not isinstance(record["material_sha256"], str)
            or not hmac.compare_digest(record["material_sha256"], digest(record["material"]))):
        raise HandoffFailure("GHL_ESCROW_TARGET_MISMATCH")
    return record


class TokenEscrow:
    """Immutable, separately named DPAPI record containing only the NEW token."""

    stage_prefix = ".new-ghl-"

    def __init__(self, path):
        self.path = path

    def validate(self, record):
        return validate_record(record)

    def make_record(self, material):
        validate_material(material)
        return {"version": 1, "purpose": "maintain-media-new-ghl-token", "host": HOST, "location": LOCATION,
                "material": material, "material_sha256": digest(material)}

    def load(self):
        verify_acl(self.path.parent, directory=True)
        verify_acl(self.path)
        if self.path.stat().st_size > 16_384:
            raise HandoffFailure("GHL_ESCROW_SIZE_INVALID")
        return self.validate(json.loads(dpapi(self.path.read_bytes(), decrypt=True)))

    def save_new(self, material):
        record = self.validate(self.make_record(material))
        verify_acl(self.path.parent, directory=True)
        ordinary(self.path)
        if self.path.exists():
            raise HandoffFailure("GHL_ESCROW_ALREADY_EXISTS_USE_RESUME")
        encrypted = dpapi(canonical(record))
        stage = self.path.with_name(self.stage_prefix + secrets.token_hex(16) + ".dpapi.tmp")
        descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                verify_acl(stage)
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            # Same-volume, non-replacing publication; no remote work before durable escrow.
            os.link(stage, self.path)
        finally:
            stage.unlink(missing_ok=True)
        verify_acl(self.path)
        return record


def ssh_command(base):
    ssh = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/OpenSSH/ssh.exe"
    identity = base / "keys/abn-leadgen-sydney-20260910"
    known_hosts = base / "known_hosts"
    for path in (ssh, identity, known_hosts):
        ordinary(path)
        if not path.is_file():
            raise HandoffFailure("GHL_PINNED_SSH_REQUIRED")
    # Credential/pin contents are consumed by OpenSSH, never read by this helper.
    return [str(ssh), "-F", "NUL", "-i", str(identity), "-o", "UserKnownHostsFile=" + str(known_hosts),
            "-o", "GlobalKnownHostsFile=NUL", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ForwardAgent=no",
            "-o", "KexAlgorithms=curve25519-sha256", "-o", "HostKeyAlgorithms=ssh-ed25519",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15", HOST, REMOTE]


def run_remote(command, material):
    import subprocess

    try:
        response = subprocess.run(command, input=canonical(material), capture_output=True,
            timeout=90, shell=False, check=False, creationflags=0x08000000 if os.name == "nt" else 0)
        if len(response.stdout) > 16_384 or len(response.stderr) > 16_384:
            raise HandoffFailure("GHL_REMOTE_UNCONFIRMED")
        receipt = json.loads(response.stdout)
        if (response.returncode != 0 or not isinstance(receipt, dict)
                or receipt.get("status") != "ghl_credential_installed" or receipt.get("location_id") != LOCATION
                or receipt.get("material_sha256") != digest(material)
                or any(receipt.get(field) is not False for field in
                       ("services_started", "services_reloaded", "capabilities_changed", "release_approvals_created"))
                or receipt.get("vendor_calls") != 0):
            raise HandoffFailure("GHL_REMOTE_UNCONFIRMED")
    except Exception:  # noqa: BLE001 - subprocess output/exception can contain the token; never reflect it
        raise HandoffFailure("GHL_REMOTE_UNCONFIRMED") from None
    return {"status": "ghl_credential_installed", "location_id": LOCATION, "services_started": False,
            "capabilities_changed": False, "vendor_calls": 0}


def accept_new(token, escrow, command, *, runner=run_remote):
    record = escrow.save_new(validate_material({"ABR_GHL_TOKEN": token}))
    return runner(command, record["material"])


def resume(escrow, command, *, runner=run_remote):
    return runner(command, escrow.load()["material"])


@contextmanager
def local_lock(path):
    import msvcrt

    ordinary(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        verify_acl(path)
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        acquired = True
        yield
    finally:
        if acquired:
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        os.close(descriptor)


class Handoff:
    def __init__(self, accept, *, clock=time.monotonic, lifetime=LIFETIME):
        if not 1 <= lifetime <= LIFETIME:
            raise HandoffFailure("GHL_HANDOFF_LIFETIME_INVALID")
        self.accept, self.clock = accept, clock
        self.deadline = clock() + lifetime
        self.path = "/" + secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.origin = ""
        self.consumed = False
        self.result = None
        self.completed_at = None

    def alive(self):
        return self.clock() < self.deadline


def handler_for(handoff):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MaintainMediaLocal"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *_):
            pass

        def reply(self, status, message, *, location=None):
            body = message.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            # Native form POST uses Origin:null under no-referrer (Fetch Standard).
            # Keep cross-origin referrers suppressed while retaining our exact-origin check.
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; form-action 'self'; "
                             "frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Connection", "close")
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def send_error(self, code, message=None, explain=None):
            self.reply(code, "Request refused.")

        def correct_host(self):
            return self.headers.get_all("Host", []) == [handoff.origin.removeprefix("http://")]

        def do_GET(self):
            if not self.correct_host():
                return self.reply(403, "Request refused.")
            if self.path == handoff.path + "/result" and handoff.consumed:
                text = ("The new token is installed. Service activation and approvals remain separate."
                        if handoff.result and handoff.result.get("status") == "ghl_credential_installed"
                        else "Installation is not confirmed. Use the saved encrypted handoff to retry; "
                             "do not generate another token.")
                return self.reply(200, text)
            if self.path != handoff.path or not handoff.alive() or handoff.consumed:
                return self.reply(410, "This handoff is unavailable.")
            return self.reply(200, '<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Maintain Media GoHighLevel setup</title><body><h1>Connect GoHighLevel</h1>'
                '<p>Paste only the new Maintain Media private-integration token. '
                'This form saves it privately and installs it on the configured Sydney service.</p>'
                '<form method="post" action="' + handoff.path + '" autocomplete="off">'
                '<input type="hidden" name="csrf" value="' + handoff.csrf + '">'
                '<label>New private-integration token <input type="password" name="token" '
                'required minlength="32" maxlength="2048" autocomplete="off" spellcheck="false"></label>'
                '<button type="submit">Save and install token</button></form>'
                '<p>No leads are imported and no messages are sent by this setup.</p></body></html>')

        def do_POST(self):
            if (not self.correct_host() or self.headers.get_all("Origin", []) != [handoff.origin]
                    or self.path != handoff.path
                    or self.headers.get_all("Content-Type", []) != ["application/x-www-form-urlencoded"]
                    or self.headers.get_all("Transfer-Encoding", [])
                    or len(self.headers.get_all("Content-Length", [])) != 1):
                return self.reply(403, "Request refused.")
            if not handoff.alive() or handoff.consumed:
                return self.reply(410, "This handoff is unavailable.")
            try:
                length_text = self.headers["Content-Length"]
                length = int(length_text)
                if str(length) != length_text or not 1 <= length <= MAX_BODY:
                    return self.reply(413, "Request refused.")
                body = self.rfile.read(length)
                if len(body) != length or not handoff.alive():
                    return self.reply(410, "This handoff is unavailable.")
                form = parse_qs(body.decode("utf-8", errors="strict"), strict_parsing=True,
                                max_num_fields=2, encoding="utf-8", errors="strict")
                if (set(form) != {"csrf", "token"} or any(len(values) != 1 for values in form.values())
                        or not hmac.compare_digest(form["csrf"][0], handoff.csrf)):
                    return self.reply(403, "Request refused.")
                token = form["token"][0]
                validate_material({"ABR_GHL_TOKEN": token})
            except Exception:  # noqa: BLE001 - malformed secret-bearing inputs never escape
                return self.reply(400, "Request refused.")
            handoff.consumed = True  # One valid submission, even if remote installation is uncertain.
            try:
                handoff.result = handoff.accept(token)
            except Exception:  # noqa: BLE001 - no token/provider/exception content in HTTP or console
                handoff.result = {"status": "blocked", "code": "GHL_HANDOFF_UNCONFIRMED"}
            finally:
                handoff.completed_at = handoff.clock()
                del token, form, body
            return self.reply(303, "Handoff processed.", location=handoff.path + "/result")

    return Handler


def serve_once(accept):
    handoff = Handoff(accept)
    with HTTPServer(("127.0.0.1", 0), handler_for(handoff)) as server:
        handoff.origin = "http://127.0.0.1:" + str(server.server_port)
        server.timeout = 1
        print(json.dumps({"status": "awaiting_new_token", "url": handoff.origin + handoff.path,
                          "expires_in_seconds": LIFETIME}), flush=True)
        while ((not handoff.consumed and handoff.alive())
               or handoff.completed_at is not None and handoff.clock() < handoff.completed_at + 15):
            server.handle_request()
    return handoff.result or {"status": "blocked", "code": "GHL_HANDOFF_EXPIRED"}


def apply(mode):
    if os.name != "nt":
        raise HandoffFailure("WINDOWS_USER_DPAPI_REQUIRED")
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or Path(local).resolve() != Path("C:/Users/dalig/AppData/Local").resolve():
        raise HandoffFailure("GHL_APPROVED_LOCAL_USER_REQUIRED")
    base = Path(local) / "MaintainMedia/aws"
    command = ssh_command(base)
    directory = base / "new-ghl-token-escrow"
    secure_directory(directory)
    escrow = TokenEscrow(directory / "maintain-media-ghl-20260911.dpapi")
    with local_lock(directory / "handoff.lock"):
        if mode == "--resume":
            return resume(escrow, command)
        if escrow.path.exists():
            raise HandoffFailure("GHL_ESCROW_ALREADY_EXISTS_USE_RESUME")
        return serve_once(lambda token: accept_new(token, escrow, command))


def main():
    if sys.argv[1:] not in (["--receive"], ["--resume"]):
        print(json.dumps({"status": "review_only", "host": HOST, "location_id": LOCATION,
                          "receiver_started": False, "vendor_calls": 0}))
        return 0
    try:
        result = apply(sys.argv[1])
        print(json.dumps(result), flush=True)
        return 0 if result.get("status") == "ghl_credential_installed" else 2
    except Exception:  # noqa: BLE001 - no secrets/provider output or exception text on terminal
        print(json.dumps({"status": "blocked", "code": "GHL_HANDOFF_UNCONFIRMED",
                          "resume": "Retry --resume only if this handoff saved its encrypted token."}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
