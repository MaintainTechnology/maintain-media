"""Bounded operator contract test against the authorised Maintain Media account.

Only synthetic records, an ACMA fictional phone, and engine-owned IDs are used.
No environment file, token output, messaging, upsert or workflow mutation exists.
The durable journal stops uncertain/repeated creates; resume is read-only until a
specific remaining step is reviewed. This is not production lead qualification.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from provision_ghl_client import TokenEscrow
from pydantic import SecretStr

from abr_engine.control.service import DomainError
from abr_engine.export.crm import MAPPED_FIELDS
from abr_engine.export.gohighlevel import MAX_RESPONSE_BYTES, GHLConfig, GoHighLevel

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "ops/acceptance/live-integration-20260910"
JOURNAL = OUTPUT / "ghl-account-contract-journal-20260911.json"
LOCATION = "xHZFHMOE476t5CxY9vCG"
PHONE = "+61755500911"
ACMA = "https://www.acma.gov.au/phone-numbers-use-tv-shows-films-and-creative-works"
METADATA = OUTPUT / "ghl-live-metadata-workflows-20260911.json"
UNRELATED_TAG = "abn-installation-test-preserve-20260911"


def now():
    return datetime.now(UTC).isoformat()


def save(journal, *, initial=False):
    stage = JOURNAL if initial else JOURNAL.with_name(".ghl-contract-" + uuid4().hex + ".tmp")
    descriptor = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(journal, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not initial:
        stage.replace(JOURNAL)


def payload(group, contact, suffix):
    values = {key: None for key in MAPPED_FIELDS}
    values.update(group_id=group, contact_id=contact, channel="phone", endpoint=PHONE,
                  business_name="ABN INSTALLATION TEST " + suffix + " - NOT A BUSINESS",
                  signal="SYNTHETIC ACCOUNT CONTRACT TEST", score=90, tier="A", state="QLD",
                  industry="Synthetic test", entity_class="Synthetic test", website="https://example.invalid",
                  positioning_notes="Synthetic installation check; never contact or enrol.",
                  basis_summary="Fictional data only; no real person, DNCR or qualification evidence claimed.",
                  tags=["maintain-media:candidate"], custom_field_map_version="maintain-media-ghl-v1")
    return values


class ObservedTransport(httpx.BaseTransport):
    def __init__(self, journal):
        self.inner = httpx.HTTPTransport(retries=0)
        self.journal = journal
        self.lose_next_create_response = False

    def handle_request(self, request):
        path, method = request.url.path, request.method
        if request.url.host != "services.leadconnectorhq.com":
            raise RuntimeError("FIXED_VENDOR_HOST_REQUIRED")
        ids = {item["remote_id"] for item in self.journal["records"].values() if item.get("remote_id")}
        allowed = ((method, path) in {("GET", "/workflows/"), ("POST", "/contacts/search"),
                    ("GET", "/locations/" + LOCATION), ("GET", "/locations/" + LOCATION + "/customFields"),
                    ("POST", "/contacts/")} or
                   any(path == "/contacts/" + remote and method in {"GET", "PUT", "DELETE"} or
                       path == "/contacts/" + remote + "/tags" and method in {"POST", "DELETE"}
                       for remote in ids))
        # The SDK's post-create fetch is permitted only after the actual returned
        # ID has been journalled by this boundary; never follow vendor URLs.
        if not allowed:
            raise RuntimeError("TEST_ENDPOINT_REFUSED")
        mutation = method in {"POST", "PUT", "DELETE"} and path != "/contacts/search"
        if mutation:
            self.journal["mutation_attempts"] += 1
            if self.journal["mutation_attempts"] > 24:
                raise RuntimeError("TEST_MUTATION_BOUND_EXCEEDED")
        self.journal["pending_request"] = {"method": method, "path": path, "at": now()}
        save(self.journal)
        streamed = self.inner.handle_request(request)
        try:
            raw = bytearray()
            for chunk in streamed.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("TEST_RESPONSE_TOO_LARGE")
            headers = {key: value for key, value in streamed.headers.items()
                       if key.lower() not in {"content-encoding", "content-length"}}
            response = httpx.Response(streamed.status_code, headers=headers, content=bytes(raw), request=request)
        finally:
            streamed.close()
        entry = {"method": method, "path": path, "status": response.status_code, "at": now()}
        self.journal["requests"].append(entry)
        self.journal["pending_request"] = None
        if method == "POST" and path == "/contacts/" and 200 <= response.status_code < 300:
            body, actual = json.loads(request.content), response.json().get("contact", {})
            current = self.journal["active_case"]
            if actual.get("locationId") != LOCATION or not isinstance(actual.get("id"), str):
                raise RuntimeError("CREATED_RECORD_UNCONFIRMED")
            group_field = self.journal["config"]["field_ids"]["group_id"]
            requested_group = next(item["fieldValue"] for item in body["customFields"] if item["id"] == group_field)
            if requested_group != self.journal["records"][current]["group_id"]:
                raise RuntimeError("SYNTHETIC_GROUP_MISMATCH")
            self.journal["records"][current]["remote_id"] = actual["id"]
        save(self.journal)
        if method == "POST" and path == "/contacts/" and self.lose_next_create_response and response.status_code == 201:
            self.lose_next_create_response = False
            response.close()
            raise httpx.ReadTimeout("SIMULATED_RESPONSE_LOSS", request=request)
        return response

    def close(self):
        self.inner.close()


def build_config():
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    fields = {key: value["id"] for key, value in metadata["fields"].items()}
    return GHLConfig(location_id=LOCATION, mapping_version="maintain-media-ghl-v1", field_ids=fields,
                     group_search_field="customFields." + fields["group_id"], allow_writes=True,
                     allowed_channels=["phone"], workflow_inventory_sha256=metadata["workflow_inventory_sha256"])


def guard(journal):
    if datetime.now(UTC).timestamp() - datetime.fromisoformat(journal["started_at"]).timestamp() > 1800:
        raise RuntimeError("ACCOUNT_TEST_WINDOW_EXPIRED")
    if journal["active_case"] not in journal["records"]:
        raise RuntimeError("SYNTHETIC_CASE_REQUIRED")


def verify_payload(actual, expected):
    for key in MAPPED_FIELDS | {"group_id", "contact_id", "channel", "endpoint", "business_name"}:
        if actual["payload"].get(key) != expected.get(key):
            raise RuntimeError("FIELD_READBACK_MISMATCH_" + key)
    if not actual["provider_dnd"]:
        raise RuntimeError("DND_READBACK_FAILED")
    if set(actual["payload"]["tags"]) & {"maintain-media:candidate", "maintain-media:suppressed"} != set(expected["tags"]):
        raise RuntimeError("OWNED_TAGS_READBACK_FAILED")


def execute(*, resume_mapping=False):
    if JOURNAL.exists() and not resume_mapping:
        raise RuntimeError("EXISTING_TEST_JOURNAL_REVIEW_REQUIRED")
    config = build_config()
    journal = {"schema_version": 1, "location_id": LOCATION, "synthetic_only": True,
               "started_at": now(), "config": config.model_dump(), "fictional_phone_source": ACMA,
               "active_case": "mapping", "records": {}, "requests": [], "checks": {},
               "mutation_attempts": 0, "pending_request": None, "messages_sent": 0, "status": "running"}
    if resume_mapping:
        journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
        if (journal.get("status") != "review_required" or journal.get("active_case") != "mapping"
                or journal.get("error", {}).get("code") != "FIELD_READBACK_MISMATCH_business_name"
                or journal.get("mutation_attempts") != 1 or journal.get("checks") != {"metadata": True}
                or journal.get("config") != config.model_dump()
                or not journal["records"]["mapping"].get("remote_id")
                or any(journal["records"][case].get("remote_id") for case in ["collision", "uncertain"])):
            raise RuntimeError("MAPPING_RESUME_PRECONDITION_FAILED")
        journal.setdefault("reviewed_failures", []).append(journal.pop("error"))
        journal["status"] = "running"
        save(journal)
    else:
        for case in ["mapping", "collision", "uncertain"]:
            journal["records"][case] = {"group_id": str(uuid4()), "contact_id": str(uuid4()), "remote_id": None}
        save(journal, initial=True)
    token = TokenEscrow(Path("C:/Users/dalig/AppData/Local/MaintainMedia/aws/new-ghl-token-escrow/maintain-media-ghl-20260911.dpapi")).load()["material"]["ABR_GHL_TOKEN"]
    transport = ObservedTransport(journal)
    api = GoHighLevel(config, SecretStr(token), write_guard=lambda: guard(journal), transport=transport)
    try:
        metadata = api.preflight()
        if not metadata["fields_verified"] or not metadata["location_verified"]:
            raise RuntimeError("METADATA_MISMATCH")
        api.verify_workflow_isolation()
        journal["checks"]["metadata"] = True
        # Empty group and exact reserved-number search before any create. Do not
        # touch a pre-existing account record even if it uses a fictional number.
        item = journal["records"]["mapping"]
        first = payload(item["group_id"], item["contact_id"], "MAPPING")
        if not resume_mapping:
            for case in journal["records"].values():
                if api.find_group(case["group_id"]):
                    raise RuntimeError("PREEXISTING_SYNTHETIC_GROUP")
            response = api._request("POST", "/contacts/search", body={"locationId": LOCATION, "page": 1,
                "pageLimit": 100, "filters": [{"field": "phone", "operator": "eq", "value": PHONE}]})
            if response.get("total") != 0 or response.get("contacts") != []:
                raise RuntimeError("PREEXISTING_FICTIONAL_ENDPOINT")
            remote = api.create(item["group_id"], first, str(uuid4()))
        else:
            remote = item["remote_id"]
        verify_payload(api.fetch(remote), first)
        if api.find_group(item["group_id"]) != [remote]:
            raise RuntimeError("GROUP_SEARCH_READBACK_FAILED")
        journal["checks"]["group_search"] = True
        api._request("POST", f"/contacts/{remote}/tags", body={"tags": [UNRELATED_TAG]}, mutation=True)
        journal["active_case"] = "collision"
        collision = journal["records"]["collision"]
        try:
            api.create(collision["group_id"], payload(collision["group_id"], collision["contact_id"], "COLLISION"), str(uuid4()))
        except DomainError as exc:
            journal["collision_result"] = {"error_type": type(exc).__name__, "code": getattr(exc, "code", "UNCONFIRMED")}
            last = journal["requests"][-1]
            if (getattr(exc, "code", "") != "GHL_REQUEST_REJECTED" or last["method"] != "POST"
                    or last["path"] != "/contacts/" or last["status"] not in {400, 409}):
                raise RuntimeError("DUPLICATE_REJECTION_UNCONFIRMED") from None
        else:
            raise RuntimeError("DUPLICATE_CREATE_NOT_REJECTED")
        verify_payload(api.fetch(remote), first)
        if api.find_group(collision["group_id"]) or api.find_group(item["group_id"]) != [remote]:
            raise RuntimeError("DUPLICATE_IDENTITY_NOT_PRESERVED")
        journal["checks"]["duplicate_no_overwrite"] = True
        journal["active_case"] = "mapping"
        stopped = {key: None for key in MAPPED_FIELDS | {"contact_id", "channel", "endpoint", "business_name"}}
        stopped.update(group_id=item["group_id"], outreach_blocked=True,
                       tags=["maintain-media:suppressed"], custom_field_map_version=config.mapping_version)
        api.update(remote, stopped, str(uuid4()))
        final = api.fetch(remote)
        verify_payload(final, stopped)
        raw = api._request("GET", f"/contacts/{remote}")["contact"]
        if any(raw.get(key) not in {None, ""} for key in ["name", "firstName", "lastName", "companyName", "email", "phone"]):
            raise RuntimeError("PROVIDER_IDENTITY_FIELDS_NOT_CLEARED")
        if UNRELATED_TAG not in final["payload"]["tags"] or "maintain-media:candidate" in final["payload"]["tags"]:
            raise RuntimeError("UNRELATED_TAG_NOT_PRESERVED")
        journal["checks"].update(suppression_clear=True, unrelated_tags=True)
        save(journal)
        # The first record's phone is now absent. Simulate a lost successful
        # response, then reconcile by group with no second create attempt.
        journal["active_case"] = "uncertain"
        item = journal["records"]["uncertain"]
        uncertain = payload(item["group_id"], item["contact_id"], "UNCERTAIN RESPONSE")
        transport.lose_next_create_response = True
        try:
            api.create(item["group_id"], uncertain, str(uuid4()))
        except Exception as exc:
            if getattr(exc, "code", "") != "GHL_TRANSPORT_UNCERTAIN":
                raise
        else:
            raise RuntimeError("UNCERTAIN_RESPONSE_NOT_SIMULATED")
        matches = api.find_group(item["group_id"])
        if matches != [item["remote_id"]]:
            raise RuntimeError("UNCERTAIN_CREATE_RECONCILIATION_FAILED")
        verify_payload(api.fetch(matches[0]), uncertain)
        journal["checks"]["uncertain_create"] = True
        api.verify_workflow_isolation()
        journal["checks"]["workflow_isolation"] = True
        journal["status"] = "contract_passed_cleanup_pending"
        save(journal)
        return {"status": journal["status"], "checks": journal["checks"], "journal": str(JOURNAL)}
    except Exception as exc:  # noqa: BLE001 - durably hold every uncertain outcome without reflecting provider bodies
        journal["status"] = "review_required"
        journal["error"] = {"type": type(exc).__name__, "code": getattr(exc, "code", str(exc) if isinstance(exc, RuntimeError) else "ACCOUNT_CONTRACT_UNCONFIRMED")}
        save(journal)
        return {"status": "review_required", "error": journal["error"], "checks": journal["checks"]}
    finally:
        api.close()


def finish_uncertain():
    """Read-only reconciliation after the provider's search index catches up."""
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    creates = [r["status"] for r in journal["requests"] if r["method"] == "POST" and r["path"] == "/contacts/"]
    if (journal.get("status") != "review_required"
            or journal.get("error", {}).get("code") != "UNCERTAIN_CREATE_RECONCILIATION_FAILED"
            or journal.get("active_case") != "uncertain" or creates not in [[201, 400, 201], [201, 409, 201]]
            or not journal["records"]["uncertain"].get("remote_id")):
        raise RuntimeError("READ_ONLY_RECONCILIATION_PRECONDITION_FAILED")
    config = build_config()
    if config.model_dump() != journal["config"]:
        raise RuntimeError("TEST_CONFIGURATION_CHANGED")
    token = TokenEscrow(Path("C:/Users/dalig/AppData/Local/MaintainMedia/aws/new-ghl-token-escrow/maintain-media-ghl-20260911.dpapi")).load()["material"]["ABR_GHL_TOKEN"]
    with GoHighLevel(config, SecretStr(token), transport=ObservedTransport(journal)) as api:
        item = journal["records"]["uncertain"]
        if api.find_group(item["group_id"]) != [item["remote_id"]]:
            raise RuntimeError("UNCERTAIN_CREATE_STILL_HELD")
        verify_payload(api.fetch(item["remote_id"]), payload(item["group_id"], item["contact_id"], "UNCERTAIN RESPONSE"))
        api.verify_workflow_isolation()
        journal.setdefault("reviewed_failures", []).append(journal.pop("error"))
        journal["checks"].update(uncertain_create=True, workflow_isolation=True)
        journal["index_delay_observation"] = {"immediate_search_found_record": False,
            "later_reconciliation_verified_at": now(), "additional_create_attempts": 0,
            "maximum_index_latency_measured": False}
        journal["status"] = "contract_passed_cleanup_pending"
        save(journal)
        return {"status": journal["status"], "checks": journal["checks"], "additional_create_attempts": 0}


def cleanup():
    """Clear then remove exactly the two verified synthetic installation records."""
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    expected_checks = {"metadata", "group_search", "duplicate_no_overwrite", "suppression_clear",
                       "unrelated_tags", "uncertain_create", "workflow_isolation"}
    if (journal.get("status") != "contract_passed_cleanup_pending" or set(journal["checks"]) != expected_checks
            or any(value is not True for value in journal["checks"].values())):
        raise RuntimeError("CLEANUP_PRECONDITION_FAILED")
    config = build_config()
    if config.model_dump() != journal["config"] or journal["records"]["collision"].get("remote_id"):
        raise RuntimeError("CLEANUP_CONFIGURATION_MISMATCH")
    token = TokenEscrow(Path("C:/Users/dalig/AppData/Local/MaintainMedia/aws/new-ghl-token-escrow/maintain-media-ghl-20260911.dpapi")).load()["material"]["ABR_GHL_TOKEN"]
    transport = ObservedTransport(journal)
    with GoHighLevel(config, SecretStr(token), write_guard=lambda: guard(journal), transport=transport) as api:
        for case in ["uncertain", "mapping"]:
            journal["active_case"] = case
            item = journal["records"][case]
            remote = item["remote_id"]
            before = api.fetch(remote)
            if before["group_id"] != item["group_id"] or set(before["payload"]["tags"]) - {
                    UNRELATED_TAG, "maintain-media:candidate", "maintain-media:suppressed"}:
                raise RuntimeError("CLEANUP_RECORD_CHANGED")
            stopped = {key: None for key in MAPPED_FIELDS | {"contact_id", "channel", "endpoint", "business_name"}}
            stopped.update(group_id=item["group_id"], outreach_blocked=True,
                           tags=["maintain-media:suppressed"], custom_field_map_version=config.mapping_version)
            if case == "uncertain":
                verify_payload(before, payload(item["group_id"], item["contact_id"], "UNCERTAIN RESPONSE"))
                api.update(remote, stopped, str(uuid4()))
            verify_payload(api.fetch(remote), stopped)
            raw = api._request("GET", f"/contacts/{remote}")["contact"]
            if any(raw.get(key) not in {None, ""} for key in ["name", "firstName", "lastName", "companyName", "email", "phone"]):
                raise RuntimeError("CLEANUP_CONTACT_FIELDS_NOT_CLEARED")
            journal.setdefault("cleanup", {})[case] = {"remote_id": remote, "cleared_at": now(), "deleted": False}
            save(journal)
            api._request("DELETE", f"/contacts/{remote}", mutation=True)
            # The public API reports missing contact as400. Check the actual
            # status through our fixed-ID observer; never accept an auth failure.
            try:
                api.fetch(remote)
            except DomainError as exc:
                last = journal["requests"][-1]
                if (getattr(exc, "code", "") != "GHL_REQUEST_REJECTED" or last["method"] != "GET"
                        or last["path"] != f"/contacts/{remote}" or last["status"] not in {400, 404}):
                    raise RuntimeError("CLEANUP_DELETION_UNCONFIRMED") from None
            else:
                raise RuntimeError("CLEANUP_RECORD_STILL_PRESENT")
            journal["cleanup"][case].update(deleted=True, verified_at=now())
            save(journal)
        api.verify_workflow_isolation()
        journal["status"] = "contract_passed_synthetic_contacts_removed"
        journal["finished_at"] = now()
        save(journal)
        return {"status": journal["status"], "checks": journal["checks"], "synthetic_contacts_removed": 2,
                "messages_sent": 0, "real_businesses_exported": 0}


if __name__ == "__main__":
    if sys.argv[1:] not in [["--execute"], ["--resume-mapping-readback"], ["--reconcile-only"], ["--cleanup"]]:
        print(json.dumps({"status": "review_only", "location_id": LOCATION, "synthetic_only": True,
                          "maximum_create_attempts": 3, "maximum_mutations": 24, "no_messages": True,
                          "fictional_phone_source": ACMA}))
    else:
        try:
            result = (finish_uncertain() if sys.argv[1:] == ["--reconcile-only"] else
                      cleanup() if sys.argv[1:] == ["--cleanup"] else
                      execute(resume_mapping=sys.argv[1:] == ["--resume-mapping-readback"]))
        except Exception as exc:  # noqa: BLE001 - the CLI exposes only a closed status and exception type
            result = {"status": "review_required", "type": type(exc).__name__}
        print(json.dumps(result))
        sys.exit(0 if str(result.get("status", "")).startswith("contract_passed_") else 1)
