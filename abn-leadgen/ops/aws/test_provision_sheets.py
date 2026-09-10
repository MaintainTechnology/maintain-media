"""New key and disabled registry contracts; no secret store or vendor calls."""
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

SPEC = importlib.util.spec_from_file_location("provision_sheets", Path(__file__).with_name("provision_sheets.py"))
sheets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sheets)


def material():
    return {"ABR_SHEETS_SIGNING_KEY": "a" * 64, "ABR_SHEETS_BRIDGE_SECRET": "b" * 64}


@pytest.mark.parametrize("invalid", [
    {"ABR_SHEETS_SIGNING_KEY": "a" * 64},
    {**material(), "ABR_SHEETS_BRIDGE_SECRET": "a" * 64},
    {**material(), "ABR_SHEETS_SIGNING_KEY": "short"},
    {**material(), "ABR_SHEETS_SIGNING_KEY": "a" * 63 + "\n"},
    {**material(), "ABR_SHEETS_SIGNING_KEY": "a" * 63 + "$"},
    {**material(), "ENABLE_SHEETS": "true"},
])
def test_only_two_distinct_safe_new_keys_are_admitted(invalid):
    with pytest.raises(ValueError, match="PAIR_INVALID"):
        sheets.validate_material(invalid)


def test_preparation_draft_is_explicitly_disabled_and_cannot_authenticate():
    from abr_engine.control.sheets_auth import BridgeRegistry

    draft = sheets.draft_registry()
    assert not draft["enabled"] and draft["sheet_id"] == 2107750955
    assert draft["owner_email"] == "jeph@quotemax.com.au"
    assert draft["editors"] == {draft["owner_email"]: []}
    assert draft["approved_by"] == "" and draft["verified_at"] is None
    with pytest.raises(ValidationError):
        BridgeRegistry.model_validate(draft)


def test_exact_new_files_never_include_active_settings_or_worker_dropins():
    values = sheets.contents(material())
    assert set(values) == {"environment", "registry", "api_dropin"}
    assert json.loads(values["registry"]) == sheets.draft_registry()
    assert values["environment"].count(b"\n") == 2
    assert values["api_dropin"] == b"[Service]\nEnvironmentFile=/etc/abr-engine/sheets.env\n"
    paths = [str(path) for path, _ in sheets.targets().values()]
    assert all("pilot.yaml" not in path and "runtime.env" not in path and "ghl.env" not in path for path in paths)
    assert sum(".service.d" in path for path in paths) == 1
    assert [mode for _, mode in sheets.targets().values()] == [0o600, 0o600, 0o644]


def test_wrapper_uses_exact_reviewed_publication_contract(monkeypatch):
    class OwnedFiles:
        def __init__(self, **options):
            assert options["marker_name"] == "sheets-installation.json"
            assert options["targets"] == sheets.targets()
            assert options["identity"] == {key: str(value) for key, value in sheets.IDENTITY.items()}

        def install(self, content, digest):
            assert content == sheets.contents(material()) and digest == sheets.digest(material())
            return {"replayed": True, "material_sha256": digest}

    monkeypatch.setitem(sys.modules, "provision_private_files", SimpleNamespace(OwnedFiles=OwnedFiles))
    receipt = sheets.install(material())
    assert receipt["replayed"] and receipt["vendor_calls"] == 0
    assert not any(receipt[key] for key in ("script_enabled", "registry_enabled", "settings_changed",
        "services_started", "services_reloaded", "capabilities_changed", "release_approvals_created"))


def test_default_does_not_generate_keys_or_install(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sheets"])
    monkeypatch.setattr(sheets, "install", lambda *_: pytest.fail("No install in preview"))
    assert sheets.main() == 0
    assert "review_only" in capsys.readouterr().out


def test_secret_bearing_failure_never_leaves_cli(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sheets", "--apply"])
    monkeypatch.setattr(sheets.os, "name", "posix")
    monkeypatch.setattr(sheets.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(material()).encode())))
    monkeypatch.setattr(sheets, "install", lambda *_: (_ for _ in ()).throw(ValueError(material())))
    assert sheets.main() == 2
    output = capsys.readouterr().out
    assert "SHEETS_PREPARATION_UNCONFIRMED" in output
    assert all(value not in output for value in material().values())
