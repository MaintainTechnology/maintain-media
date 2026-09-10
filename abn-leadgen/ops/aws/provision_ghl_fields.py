"""Create only the 12 remaining empty, named GHL Contact field definitions.

Uses this setup's NEW DPAPI token, two fixed metadata reads, and the documented
location custom-field create endpoint. It never accesses contacts or workflows.
Folder assignment is a separate owner UI step: the pinned API omits folder ID.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from provision_ghl import LOCATION
from provision_ghl_client import TokenEscrow, local_lock
from provision_runtime_client import ordinary, verify_acl

GROUP_ID = "C17XY6QzLsYssEnb1gUz"
EXPECTED = {
    "group_id": ("ABN Engine Group ID", "TEXT"),
    "contact_id": ("ABN Engine Contact ID", "TEXT"),
    "channel": ("ABN Engine Channel", "TEXT"),
    "abn": ("ABN Engine ABN", "TEXT"),
    "signal": ("ABN Engine Signal", "TEXT"),
    "score": ("ABN Engine Score", "NUMERICAL"),
    "tier": ("ABN Engine Tier", "TEXT"),
    "industry": ("ABN Engine Industry", "TEXT"),
    "entity_class": ("ABN Engine Entity Class", "TEXT"),
    "state": ("ABN Engine State", "TEXT"),
    "website": ("ABN Engine Website", "TEXT"),
    "positioning_notes": ("ABN Engine Positioning Notes", "LARGE_TEXT"),
    "basis_summary": ("ABN Engine Basis Summary", "LARGE_TEXT"),
}
RECEIPT = Path(__file__).resolve().parents[1] / "acceptance/live-integration-20260910/ghl-field-metadata.json"
ID = re.compile(r"[A-Za-z0-9_-]{1,100}")
KEY = re.compile(r"contact\.[A-Za-z0-9_.-]{1,190}")


class MetadataFailure(RuntimeError):
    pass


def projection(name, field):
    label, data_type = EXPECTED[name]
    if (not isinstance(field, dict) or field.get("name") != label or field.get("dataType") != data_type
            or field.get("model") != "contact" or field.get("locationId") != LOCATION
            or not isinstance(field.get("id"), str) or not ID.fullmatch(field["id"])
            or not isinstance(field.get("fieldKey"), str) or not KEY.fullmatch(field["fieldKey"])
            or name == "group_id" and field["id"] != GROUP_ID):
        raise MetadataFailure("GHL_FIELD_CONTRACT_MISMATCH")
    return {"id": field["id"], "name": label, "type": data_type, "key": field["fieldKey"]}


def project_all(fields):
    if not isinstance(fields, list) or len(fields) > 2000 or any(not isinstance(item, dict) for item in fields):
        raise MetadataFailure("GHL_FIELD_METADATA_INVALID")
    result = {}
    for name, (label, _) in EXPECTED.items():
        matches = [field for field in fields if str(field.get("name", "")).strip().casefold() == label.casefold()]
        if len(matches) > 1:
            raise MetadataFailure("GHL_DUPLICATE_FIELD_NAMES")
        if matches:
            result[name] = projection(name, matches[0])
    if "group_id" not in result or len({field["id"] for field in result.values()}) != len(result):
        raise MetadataFailure("GHL_PINNED_GROUP_FIELD_REQUIRED")
    return result


class MetadataAPI:
    def __init__(self, token, *, transport=None):
        self.client = httpx.Client(base_url="https://services.leadconnectorhq.com", follow_redirects=False,
            trust_env=False, timeout=httpx.Timeout(15, connect=5), transport=transport,
            headers={"Authorization": "Bearer " + token, "Version": "2023-02-21",
                     "Accept": "application/json", "User-Agent": "MaintainMedia-MetadataInstaller/1.0"})

    def request(self, method, path, *, body=None):
        allowed = {("GET", "/locations/" + LOCATION),
                   ("GET", "/locations/" + LOCATION + "/customFields?model=contact"),
                   ("POST", "/locations/" + LOCATION + "/customFields")}
        if (method, path) not in allowed:
            raise MetadataFailure("GHL_METADATA_ENDPOINT_REFUSED")
        if method == "POST" and body not in [
                {"name": label, "dataType": kind, "model": "contact"}
                for key, (label, kind) in EXPECTED.items() if key != "group_id"]:
            raise MetadataFailure("GHL_METADATA_WRITE_REFUSED")
        try:
            with self.client.stream(method, path, json=body) as response:
                if not 200 <= response.status_code < 300:
                    raise MetadataFailure("GHL_METADATA_REQUEST_UNCONFIRMED")
                raw = bytearray()
                for part in response.iter_bytes():
                    raw.extend(part)
                    if len(raw) > 1_000_000:
                        raise MetadataFailure("GHL_METADATA_REQUEST_UNCONFIRMED")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise MetadataFailure("GHL_METADATA_REQUEST_UNCONFIRMED")
            return result
        except Exception:  # noqa: BLE001 - never reflect private token or vendor/profile response content
            raise MetadataFailure("GHL_METADATA_REQUEST_UNCONFIRMED") from None

    def read(self):
        location = self.request("GET", "/locations/" + LOCATION).get("location")
        if not isinstance(location, dict) or location.get("id") != LOCATION:
            raise MetadataFailure("GHL_LOCATION_MISMATCH")
        fields = self.request("GET", "/locations/" + LOCATION + "/customFields?model=contact")
        return project_all(fields.get("customFields"))

    def create(self, name):
        label, data_type = EXPECTED[name]
        response = self.request("POST", "/locations/" + LOCATION + "/customFields",
                                body={"name": label, "dataType": data_type, "model": "contact"})
        return projection(name, response.get("customField"))


class Journal:
    def __init__(self, path=RECEIPT):
        self.path = path

    def load(self):
        ordinary(self.path)
        if not self.path.exists():
            return {"version": 1, "location_id": LOCATION, "group_field_id": GROUP_ID, "fields": {},
                    "pending": None, "status": "preparing", "observed_at": None,
                    "folder_assignment_verified": False, "release_approved": False, "contact_calls": 0}
        if self.path.stat().st_size > 32_768:
            raise MetadataFailure("GHL_METADATA_JOURNAL_INVALID")
        record = json.loads(self.path.read_text(encoding="utf-8"))
        if (not isinstance(record, dict) or set(record) != {"version", "location_id", "group_field_id", "fields",
                "pending", "status", "observed_at", "folder_assignment_verified", "release_approved", "contact_calls"}
                or record["version"] != 1 or record["location_id"] != LOCATION
                or record["group_field_id"] != GROUP_ID or record["release_approved"] is not False
                or record["folder_assignment_verified"] is not False or record["contact_calls"] != 0
                or record["status"] not in {"preparing", "metadata_installed"}
                or record["pending"] not in {None, *set(EXPECTED).difference({"group_id"})}
                or not isinstance(record["fields"], dict) or set(record["fields"]) - EXPECTED.keys()):
            raise MetadataFailure("GHL_METADATA_JOURNAL_INVALID")
        for name, field in record["fields"].items():
            if not isinstance(field, dict) or set(field) != {"id", "name", "type", "key"}:
                raise MetadataFailure("GHL_METADATA_JOURNAL_INVALID")
            projection(name, {"id": field["id"], "name": field["name"], "dataType": field["type"],
                              "fieldKey": field["key"], "model": "contact", "locationId": LOCATION})
        return record

    def save(self, record):
        ordinary(self.path)
        stage = self.path.with_name(".ghl-field-journal-" + uuid4().hex + ".tmp")
        descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(record, stream, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(stage, self.path)
        finally:
            stage.unlink(missing_ok=True)


def install_fields(api, journal):
    record = journal.load()
    actual = api.read()
    if any(actual.get(name) != field for name, field in record["fields"].items()):
        raise MetadataFailure("GHL_EXISTING_FIELD_CHANGED")
    pending = record["pending"]
    if pending is not None and pending not in actual:
        # A prior request might still complete. Never blindly replay an uncertain create.
        raise MetadataFailure("GHL_FIELD_CREATE_UNCERTAIN_OWNER_REVIEW_REQUIRED")
    record.update(fields=actual, pending=None, status="preparing")
    journal.save(record)
    for name in EXPECTED:
        if name in record["fields"]:
            continue
        record["pending"] = name
        journal.save(record)  # Durable intent precedes every one-shot metadata mutation.
        created = api.create(name)
        current = api.read()
        if (current.get(name) != created
                or any(current.get(key) != value for key, value in record["fields"].items())):
            raise MetadataFailure("GHL_CREATED_FIELD_READBACK_UNCONFIRMED")
        record.update(fields=current, pending=None)
        journal.save(record)
    record.update(status="metadata_installed", observed_at=datetime.now(UTC).isoformat())
    journal.save(record)
    return {"status": "ghl_empty_fields_installed", "field_count": len(record["fields"]),
            "location_id": LOCATION, "contact_calls": 0, "release_approved": False,
            "folder_assignment_verified": False}


def apply():
    if os.name != "nt":
        raise MetadataFailure("WINDOWS_NEW_TOKEN_ESCROW_REQUIRED")
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or Path(local).resolve() != Path("C:/Users/dalig/AppData/Local").resolve():
        raise MetadataFailure("GHL_APPROVED_LOCAL_USER_REQUIRED")
    directory = Path(local) / "MaintainMedia/aws/new-ghl-token-escrow"
    verify_acl(directory, directory=True)
    with local_lock(directory / "handoff.lock"):
        record = TokenEscrow(directory / "maintain-media-ghl-20260911.dpapi").load()
        api = MetadataAPI(record["material"]["ABR_GHL_TOKEN"])
        try:
            return install_fields(api, Journal())
        finally:
            api.client.close()


def main():
    if sys.argv[1:] != ["--apply"]:
        print(json.dumps({"status": "review_only", "location_id": LOCATION,
                          "maximum_empty_field_creates": 12, "contact_calls": 0}))
        return 0
    try:
        print(json.dumps(apply()))
        return 0
    except Exception:  # noqa: BLE001 - no credential, personal metadata or vendor failure text in output
        print(json.dumps({"status": "blocked", "code": "GHL_FIELD_SETUP_UNCONFIRMED", "contact_calls": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
