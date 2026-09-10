"""Synthetic setup display and shared escrow tests; no provider operations."""
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
SPEC = importlib.util.spec_from_file_location("sheets_client", DIRECTORY / "provision_sheets_client.py")
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)

MATERIAL = {"ABR_SHEETS_SIGNING_KEY": "s" * 64, "ABR_SHEETS_BRIDGE_SECRET": "h" * 64}


@pytest.fixture
def display():
    now = [100.0]
    handoff = client.Handoff(lambda _: None, clock=lambda: now[0], lifetime=10)
    server = HTTPServer(("127.0.0.1", 0), client.display_handler(handoff, MATERIAL))
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

    yield handoff, now, request
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def options(handoff, **changes):
    result = {"headers": {"Origin": handoff.origin, "Content-Type": "application/x-www-form-urlencoded"},
              "body": urlencode({"csrf": handoff.csrf})}
    result.update(changes)
    return result


def test_initial_page_contains_only_load_control_then_values_are_visible_once(display):
    handoff, _, request = display
    status, headers, body = request()
    assert status == 200 and "Load new setup values" in body
    assert all(value not in body for value in MATERIAL.values())
    assert "SERVICE_SIGNING_KEY" not in body and "BRIDGE_SECRET" not in body
    assert headers["Referrer-Policy"] == "same-origin" and "no-store" in headers["Cache-Control"]
    status, _, body = request("POST", **options(handoff))
    assert status == 200 and all(value in body for value in MATERIAL.values())
    assert 'name="ENABLED" type="text" readonly autocomplete="off" spellcheck="false" value="false"' in body
    assert 'name="SERVICE_SIGNING_KEY" type="text" readonly' in body
    assert 'name="BRIDGE_SECRET" type="text" readonly' in body and 'type="password"' not in body
    assert all(value not in handoff.origin + handoff.path for value in MATERIAL.values())
    assert request()[0] == 410 and request("POST", **options(handoff))[0] == 410
    status, _, body = request("POST", path=handoff.path + "/clear", **options(handoff))
    assert status == 200 and all(value not in body for value in MATERIAL.values())
    assert not handoff.result["google_transfer_verified"] and not handoff.result["script_enabled"]


@pytest.mark.parametrize("headers", [{"Host": "evil.example"}, {"Origin": "null"},
    {"Origin": "https://evil.example"}, {"Content-Type": "application/json"}, {"Transfer-Encoding": "chunked"}])
def test_untrusted_request_never_reveals_or_consumes_values(display, headers):
    handoff, _, request = display
    payload = options(handoff)
    payload["headers"].update(headers)
    status, _, body = request("POST", **payload)
    assert status == 403 and all(value not in body for value in MATERIAL.values()) and not handoff.consumed


@pytest.mark.parametrize("body", ["csrf=wrong", "csrf={csrf}&extra=1", "csrf={csrf}&csrf={csrf}", "x" * 257])
def test_bad_csrf_duplicate_fields_and_oversized_body_are_closed(display, body):
    handoff, _, request = display
    status, _, result = request("POST", **options(handoff, body=body.replace("{csrf}", handoff.csrf)))
    assert status in {400, 403, 413} and not handoff.consumed
    assert all(value not in result for value in MATERIAL.values())


def test_expiry_and_wrong_path_never_reveal_values(display):
    handoff, now, request = display
    assert request(path=handoff.path + "?ignored=1")[0] == 410
    assert request("POST", path=handoff.path + "/clear", **options(handoff))[0] == 410
    now[0] = handoff.deadline
    status, _, result = request("POST", **options(handoff))
    assert status == 410 and not handoff.consumed
    assert all(value not in result for value in MATERIAL.values())


def test_same_pair_is_escrowed_before_io_and_reused_on_recovery(tmp_path, monkeypatch):
    events = []
    record = {"material": MATERIAL}

    class Escrow:
        path = tmp_path / "encrypted-presence"

        def save_new(self, value):
            assert value == MATERIAL
            self.path.touch()
            events.append("saved")
            return record

        def load(self):
            events.append("loaded")
            return record

    monkeypatch.setattr(client, "fresh_material", lambda: MATERIAL)

    def prepare(command, material):
        assert Escrow.path.exists() and material == MATERIAL and command == ["pinned"]
        events.append("stdin")

    client.coordinate(Escrow(), ["pinned"], prepare=prepare)
    monkeypatch.setattr(client, "fresh_material", lambda: pytest.fail("Do not rotate on retry"))
    client.coordinate(Escrow(), ["pinned"], prepare=prepare)
    assert events == ["saved", "stdin", "loaded", "stdin"]


def receipt():
    return {"status": "sheets_key_preparation_installed", "material_sha256": client.digest(MATERIAL),
        "spreadsheet_id": client.SPREADSHEET_ID, "sheet_id": client.SHEET_ID,
        **{key: False for key in ("script_properties_installed", "script_enabled", "registry_enabled",
            "settings_changed", "services_started", "services_reloaded", "capabilities_changed",
            "release_approvals_created")}, "vendor_calls": 0}


@pytest.mark.parametrize("change", [None, {"registry_enabled": True}, {"settings_changed": True},
                                    {"sheet_id": 0}, {"material_sha256": "0" * 64}])
def test_remote_response_is_bound_to_pair_workbook_and_disabled_state(change):
    def runner(command, *, data, timeout):
        assert json.loads(data) == MATERIAL and all(value not in str(command) for value in MATERIAL.values())
        return SimpleNamespace(returncode=0, stdout=json.dumps({**receipt(), **(change or {})}).encode())
    if change is None:
        assert client.remote_prepare(["pinned"], MATERIAL, runner=runner) is None
    else:
        with pytest.raises(client.SheetsSetupFailure, match="UNCONFIRMED"):
            client.remote_prepare(["pinned"], MATERIAL, runner=runner)


def test_fresh_pair_is_distinct_and_subprocess_target_is_only_reviewed_sheets_helper(monkeypatch):
    value = client.fresh_material()
    assert len(set(value.values())) == 2 and all(len(key) == 64 for key in value.values())
    monkeypatch.setattr(client, "ssh_command", lambda _: ["ssh", "pins", client.HOST, client.GHL_REMOTE])
    assert client.command_for("unused") == ["ssh", "pins", client.HOST, client.REMOTE]
    monkeypatch.setattr(client, "ssh_command", lambda _: ["ssh", "other-host", client.GHL_REMOTE])
    with pytest.raises(client.SheetsSetupFailure, match="TARGET_MISMATCH"):
        client.command_for("unused")


def test_default_and_unexpected_errors_do_not_print_new_keys(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sheets-client"])
    monkeypatch.setattr(client, "apply", lambda: pytest.fail("Preview cannot prepare"))
    assert client.main() == 0 and "review_only" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["sheets-client", "--prepare"])
    monkeypatch.setattr(client, "apply", lambda: (_ for _ in ()).throw(ValueError(MATERIAL)))
    assert client.main() == 2
    result = capsys.readouterr().out
    assert all(value not in result for value in MATERIAL.values()) and "UNCONFIRMED" in result


@pytest.mark.skipif(os.name != "nt", reason="Actual current-user DPAPI and ACL test")
def test_new_sheets_pair_uses_separate_real_encrypted_non_replacing_store(tmp_path):
    directory = tmp_path / "only-new-sheets"
    client.secure_directory(directory)
    escrow = client.SheetsEscrow(directory / "synthetic-pair.dpapi")
    original = escrow.save_new(MATERIAL)
    assert all(value.encode() not in escrow.path.read_bytes() for value in MATERIAL.values())
    assert escrow.load() == original and original["identity"] == client.IDENTITY
    with pytest.raises(Exception, match="ALREADY_EXISTS"):
        escrow.save_new(client.fresh_material())
    assert escrow.load() == original
    changed = dict(original, identity={**client.IDENTITY, "script_id": "wrong"})
    with pytest.raises(client.SheetsSetupFailure, match="TARGET_MISMATCH"):
        escrow.validate(changed)


@pytest.mark.skipif(not os.environ.get("ABR_GHL_TEST_CHROMIUM"),
                    reason="Native regression requires an explicit isolated Chromium executable")
def test_native_browser_initial_secret_absence_reveal_and_clear(display):
    handoff, _, _ = display
    module = Path(os.environ.get("ABR_GHL_TEST_PLAYWRIGHT_MODULE", str(
        Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@playwright/cli/node_modules/playwright")))
    node = shutil.which("node")
    if node is None or not (module / "package.json").is_file():
        pytest.skip("Native regression needs the installed Playwright library")
    response = subprocess.run([node, str(DIRECTORY / "sheets_setup_browser.cjs"), str(module),
        handoff.origin + handoff.path, os.environ["ABR_GHL_TEST_CHROMIUM"]], capture_output=True,
        timeout=40, check=False, creationflags=0x08000000 if os.name == "nt" else 0)
    assert response.returncode == 0, "Native synthetic display check failed"
    assert json.loads(response.stdout) == {"initial_clear": True, "pair_matches": True, "rendered_readonly": True,
                                          "final_clear": True, "secret_request_body": False}
