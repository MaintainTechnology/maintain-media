"""Metadata-only GHL setup contracts; all HTTP traffic is synthetic."""
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

DIRECTORY = Path(__file__).parent
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location("ghl_fields", DIRECTORY / "provision_ghl_fields.py")
fields = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fields)


def field(name, *, identifier=None):
    label, data_type = fields.EXPECTED[name]
    return {"id": identifier or (fields.GROUP_ID if name == "group_id" else "synthetic_" + name),
            "name": label, "dataType": data_type, "fieldKey": "contact.abn_engine_" + name,
            "locationId": fields.LOCATION, "model": "contact"}


class Provider:
    def __init__(self):
        self.values = [field("group_id"), {"name": "unrelated-private-field-sentinel"}]
        self.calls = []
        self.uncertain = None
        self.accept_uncertain = False

    def transport(self, request):
        assert request.url.host == "services.leadconnectorhq.com"
        assert request.headers["Version"] == "2023-02-21"
        assert "/contacts" not in request.url.path and "/workflows" not in request.url.path
        self.calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/locations/" + fields.LOCATION:
            return httpx.Response(200, json={"location": {"id": fields.LOCATION, "email": "private-sentinel"}})
        if request.method == "GET":
            assert request.url.path == "/locations/" + fields.LOCATION + "/customFields"
            assert str(request.url.query, "ascii") == "model=contact"
            return httpx.Response(200, json={"customFields": self.values})
        assert request.method == "POST" and request.url.path == "/locations/" + fields.LOCATION + "/customFields"
        body = json.loads(request.content)
        assert set(body) == {"name", "dataType", "model"} and body["model"] == "contact"
        name = next(key for key, (label, _) in fields.EXPECTED.items() if label == body["name"])
        created = field(name)
        if self.uncertain == name:
            if self.accept_uncertain:
                self.values.append(created)
            raise httpx.ReadTimeout("private-token-sentinel", request=request)
        self.values.append(created)
        return httpx.Response(201, json={"customField": created})

    def api(self):
        return fields.MetadataAPI("synthetic-token", transport=httpx.MockTransport(self.transport))


def test_exact_twelve_empty_fields_are_created_and_safe_receipt_is_replayable(tmp_path):
    provider = Provider()
    journal = fields.Journal(tmp_path / "metadata.json")
    result = fields.install_fields(provider.api(), journal)
    assert result["field_count"] == 13 and result["contact_calls"] == 0 and not result["release_approved"]
    assert sum(method == "POST" for method, _ in provider.calls) == 12
    receipt = journal.path.read_text()
    assert "sentinel" not in receipt and "synthetic-token" not in receipt and "parentId" not in receipt
    assert len(journal.load()["fields"]) == 13
    fields.install_fields(provider.api(), journal)
    assert sum(method == "POST" for method, _ in provider.calls) == 12


@pytest.mark.parametrize("change", [{"id": "wrong"}, {"dataType": "NUMERICAL"},
                                    {"model": "opportunity"}, {"locationId": "wrong"},
                                    {"name": "abn engine group id"}])
def test_pinned_first_field_mismatch_blocks_before_any_field_creation(tmp_path, change):
    provider = Provider()
    provider.values[0].update(change)
    with pytest.raises(fields.MetadataFailure):
        fields.install_fields(provider.api(), fields.Journal(tmp_path / "metadata.json"))
    assert all(method == "GET" for method, _ in provider.calls)


def test_existing_conflicting_or_duplicate_remaining_field_is_never_modified(tmp_path):
    provider = Provider()
    provider.values.extend([field("score"), field("score", identifier="another-id")])
    with pytest.raises(fields.MetadataFailure, match="DUPLICATE"):
        fields.install_fields(provider.api(), fields.Journal(tmp_path / "metadata.json"))
    assert all(method == "GET" for method, _ in provider.calls)


@pytest.mark.parametrize("accepted", [False, True])
def test_uncertain_create_is_never_blindly_reissued(tmp_path, accepted):
    provider = Provider()
    provider.uncertain = "contact_id"
    provider.accept_uncertain = accepted
    journal = fields.Journal(tmp_path / "metadata.json")
    with pytest.raises(fields.MetadataFailure, match="UNCONFIRMED"):
        fields.install_fields(provider.api(), journal)
    assert journal.load()["pending"] == "contact_id"
    assert sum(method == "POST" for method, _ in provider.calls) == 1
    provider.uncertain = None
    if accepted:
        assert fields.install_fields(provider.api(), journal)["field_count"] == 13
        assert sum(method == "POST" for method, _ in provider.calls) == 12
    else:
        with pytest.raises(fields.MetadataFailure, match="OWNER_REVIEW_REQUIRED"):
            fields.install_fields(provider.api(), journal)
        assert sum(method == "POST" for method, _ in provider.calls) == 1


def test_changed_existing_field_after_installation_is_not_overwritten(tmp_path):
    provider = Provider()
    journal = fields.Journal(tmp_path / "metadata.json")
    fields.install_fields(provider.api(), journal)
    provider.values[2]["id"] = "changed-field-id"
    with pytest.raises(fields.MetadataFailure, match="CHANGED"):
        fields.install_fields(provider.api(), journal)
    assert sum(method == "POST" for method, _ in provider.calls) == 12


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/contacts/", {}),
    ("GET", "/locations/other", None),
    ("POST", "/locations/" + fields.LOCATION + "/customFields", {"name": "unapproved"}),
    ("POST", "/locations/" + fields.LOCATION + "/customFields", {"name": "ABN Engine Group ID",
        "dataType": "TEXT", "model": "contact"}),
])
def test_api_rejects_contacts_wrong_location_and_unapproved_or_first_field_creates(method, path, body):
    api = fields.MetadataAPI("synthetic", transport=httpx.MockTransport(lambda *_: pytest.fail("No request")))
    with pytest.raises(fields.MetadataFailure, match="REFUSED"):
        api.request(method, path, body=body)


def test_preview_never_reads_new_escrow_and_secret_bearing_errors_are_generic(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fields"])
    monkeypatch.setattr(fields, "apply", lambda: pytest.fail("No provider I/O in preview"))
    assert fields.main() == 0 and "review_only" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["fields", "--apply"])
    monkeypatch.setattr(fields, "apply", lambda: (_ for _ in ()).throw(ValueError("private-token-sentinel")))
    assert fields.main() == 2
    output = capsys.readouterr().out
    assert "private-token-sentinel" not in output and "GHL_FIELD_SETUP_UNCONFIRMED" in output
