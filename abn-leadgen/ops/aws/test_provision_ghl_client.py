"""Synthetic local form, target binding, stdin and real Windows DPAPI tests."""
import http.client
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import HTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

DIRECTORY = Path(__file__).parent
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location("ghl_client", DIRECTORY / "provision_ghl_client.py")
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)

TOKEN = "pit-synthetic-" + "z" * 40


@pytest.fixture
def form():
    received = []
    now = [100.0]
    handoff = client.Handoff(lambda token: received.append(token) or {"status": "ghl_credential_installed"},
                             clock=lambda: now[0], lifetime=10)
    server = HTTPServer(("127.0.0.1", 0), client.handler_for(handoff))
    handoff.origin = "http://127.0.0.1:" + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method="GET", *, path=None, headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
        connection.request(method, path or handoff.path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result

    yield handoff, received, now, request
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def post_options(handoff, **changes):
    result = {"headers": {"Origin": handoff.origin, "Content-Type": "application/x-www-form-urlencoded"},
              "body": urlencode({"csrf": handoff.csrf, "token": TOKEN})}
    result.update(changes)
    return result


def test_form_has_no_external_assets_and_one_valid_submission_is_consumed(form):
    handoff, received, _, request = form
    status, headers, body = request()
    assert status == 200 and 'type="password"' in body
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "no-store" in headers["Cache-Control"] and "same-origin" == headers["Referrer-Policy"]
    assert TOKEN not in body and "<script" not in body
    status, headers, body = request("POST", **post_options(handoff))
    assert status == 303 and received == [TOKEN] and TOKEN not in body
    assert headers["Location"] == handoff.path + "/result"
    assert request(path=headers["Location"])[0] == 200
    assert request("POST", **post_options(handoff))[0] == 410
    assert request()[0] == 410 and received == [TOKEN]


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Host": "evil.example"},
                                      {"Origin": "null"}, {"Content-Type": "application/json"},
                                      {"Transfer-Encoding": "chunked"}])
def test_wrong_origin_host_or_request_format_never_consumes_token(form, headers):
    handoff, received, _, request = form
    options = post_options(handoff)
    options["headers"].update(headers)
    assert request("POST", **options)[0] == 403
    assert received == [] and not handoff.consumed


@pytest.mark.parametrize("body", ["csrf=wrong&token=" + TOKEN,
    "csrf={csrf}&token=" + TOKEN + "&token=" + TOKEN,
    "csrf={csrf}&token=" + TOKEN + "&extra=yes", "csrf={csrf}&token=short"])
def test_malformed_forms_or_duplicate_fields_fail_closed(form, body):
    handoff, received, _, request = form
    options = post_options(handoff, body=body.replace("{csrf}", handoff.csrf))
    assert request("POST", **options)[0] in {400, 403}
    assert not handoff.consumed and received == []


def test_expired_oversized_and_query_string_requests_are_rejected(form):
    handoff, received, now, request = form
    assert request("POST", **post_options(handoff, body="x" * (client.MAX_BODY + 1)))[0] == 413
    assert request(path=handoff.path + "?x=1")[0] == 410
    now[0] = handoff.deadline
    assert request("POST", **post_options(handoff))[0] == 410
    assert request()[0] == 410 and received == []


def test_secret_bearing_callback_exception_has_generic_result_and_no_second_attempt(form, capsys):
    handoff, _, _, request = form
    handoff.accept = lambda _: (_ for _ in ()).throw(ValueError(TOKEN))
    assert request("POST", **post_options(handoff))[0] == 303
    status, _, body = request(path=handoff.path + "/result")
    assert status == 200 and "not confirmed" in body and TOKEN not in body
    assert request("POST", **post_options(handoff))[0] == 410
    assert TOKEN not in capsys.readouterr().out + capsys.readouterr().err


def test_escrow_precedes_remote_io_and_resume_reuses_only_saved_material():
    events = []
    record = {"material": {"ABR_GHL_TOKEN": TOKEN}}

    class Escrow:
        def save_new(self, material):
            events.append("encrypted")
            assert material == record["material"]
            return record

        def load(self):
            events.append("own encrypted record loaded")
            return record

    def runner(command, material):
        assert events[-1] in {"encrypted", "own encrypted record loaded"}
        assert command == ["pinned-ssh"] and material == record["material"]
        events.append("stdin")
        return {"status": "ghl_credential_installed"}

    client.accept_new(TOKEN, Escrow(), ["pinned-ssh"], runner=runner)
    client.resume(Escrow(), ["pinned-ssh"], runner=runner)
    assert events == ["encrypted", "stdin", "own encrypted record loaded", "stdin"]


def receipt():
    return {"status": "ghl_credential_installed", "location_id": client.LOCATION,
            "material_sha256": client.digest({"ABR_GHL_TOKEN": TOKEN}), "services_started": False,
            "services_reloaded": False, "capabilities_changed": False,
            "release_approvals_created": False, "vendor_calls": 0}


def test_only_stdin_contains_new_token_and_console_receipt_excludes_it(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(receipt()).encode(), stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)
    result = client.run_remote(["fixed-ssh"], {"ABR_GHL_TOKEN": TOKEN})
    assert TOKEN not in repr(result) and "material_sha256" not in result
    command, options = calls[0]
    assert TOKEN not in repr(command) and json.loads(options["input"])["ABR_GHL_TOKEN"] == TOKEN
    assert options["shell"] is False and options["creationflags"] == (0x08000000 if os.name == "nt" else 0)


@pytest.mark.parametrize("change", [{"location_id": "wrong"}, {"services_started": True},
                                    {"material_sha256": "0" * 64}, {"vendor_calls": 1}])
def test_unbound_or_activating_remote_receipt_is_rejected(monkeypatch, change):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0,
        stdout=json.dumps({**receipt(), **change}).encode(), stderr=TOKEN.encode()))
    with pytest.raises(client.HandoffFailure, match="^GHL_REMOTE_UNCONFIRMED$"):
        client.run_remote(["fixed"], {"ABR_GHL_TOKEN": TOKEN})


def test_default_and_secret_bearing_cli_errors_never_echo_token(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ghl-client"])
    monkeypatch.setattr(client, "apply", lambda *_: pytest.fail("No receiver by default"))
    assert client.main() == 0 and "review_only" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["ghl-client", "--receive"])
    monkeypatch.setattr(client, "apply", lambda *_: (_ for _ in ()).throw(ValueError(TOKEN)))
    assert client.main() == 2
    output = capsys.readouterr().out
    assert TOKEN not in output and "GHL_HANDOFF_UNCONFIRMED" in output


@pytest.mark.skipif(os.name != "nt", reason="Actual current-user Windows DPAPI and ACL verification")
def test_actual_separate_escrow_is_encrypted_user_only_and_never_replaced(tmp_path):
    directory = tmp_path / "only-new-ghl-token"
    client.secure_directory(directory)
    escrow = client.TokenEscrow(directory / "synthetic.dpapi")
    original = escrow.save_new({"ABR_GHL_TOKEN": TOKEN})
    assert TOKEN.encode() not in escrow.path.read_bytes()
    assert escrow.load() == original
    client.verify_acl(directory, directory=True)
    client.verify_acl(escrow.path)
    assert escrow.path.stat().st_nlink == 1
    with pytest.raises(client.HandoffFailure, match="ALREADY_EXISTS"):
        escrow.save_new({"ABR_GHL_TOKEN": "pit-other-" + "b" * 40})
    assert escrow.load() == original
    bad = dict(original, location="wrong")
    with pytest.raises(client.HandoffFailure, match="TARGET_MISMATCH"):
        client.validate_record(bad)


@pytest.mark.parametrize("legacy_policy", [True, False])
@pytest.mark.skipif(not os.environ.get("ABR_GHL_TEST_CHROMIUM"),
                    reason="Native regression requires an explicit isolated Chromium executable")
def test_native_browser_form_referrer_policy_preserves_exact_origin_check(legacy_policy):
    """Real Chromium reproduces the old null-Origin failure and verifies the fix.

    Reuses the installed Playwright CLI's browser library in a brand-new headless
    context. No persistent browser profile, actual token or vendor I/O is used.
    """
    module = Path(os.environ.get("ABR_GHL_TEST_PLAYWRIGHT_MODULE", str(
        Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@playwright/cli/node_modules/playwright")))
    node = shutil.which("node")
    if node is None or not (module / "package.json").is_file():
        pytest.skip("Native regression needs an installed Playwright library and its Chromium browser")
    accepted, origins = [], []
    handoff = client.Handoff(lambda token: accepted.append(token) or {"status": "ghl_credential_installed"})
    base_handler = client.handler_for(handoff)

    class RecordingHandler(base_handler):
        def send_header(self, key, value):
            if legacy_policy and key == "Referrer-Policy":
                value = "no-referrer"
            return super().send_header(key, value)

        def do_POST(self):
            origins.append(self.headers.get("Origin"))  # Synthetic request; never record its body/token.
            return super().do_POST()

    server = HTTPServer(("127.0.0.1", 0), RecordingHandler)
    handoff.origin = "http://127.0.0.1:" + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = [node, str(DIRECTORY / "ghl_form_browser.cjs"), str(module), handoff.origin + handoff.path]
        if os.environ.get("ABR_GHL_TEST_CHROMIUM"):
            command.append(os.environ["ABR_GHL_TEST_CHROMIUM"])
        response = subprocess.run(command, capture_output=True, timeout=40,
                                  creationflags=0x08000000 if os.name == "nt" else 0, check=False)
        assert response.returncode == 0, "Native synthetic browser check failed"
        result = json.loads(response.stdout)
        if legacy_policy:
            assert result["status"] == 403 and origins == ["null"] and not accepted
        else:
            assert result["status"] == 200 and origins == [handoff.origin] and accepted == [TOKEN]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
