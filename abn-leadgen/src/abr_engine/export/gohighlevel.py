"""Bounded HighLevel HTTP transport; production outbox activation is a separate gate.

No endpoint here sends messages or enrols a workflow. Contact/tag writes can still
trigger account automations: a caller must supply a current authority check which
also verifies the account's reviewed automation isolation. There is no default
write guard, automatic credential discovery, contact upsert, or create retry.
"""
from __future__ import annotations

import copy
import json
import os
import random
import re
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from abr_engine.control.service import DomainError
from abr_engine.export.crm import MAPPED_FIELDS

BASE_URL = "https://services.leadconnectorhq.com"
FIELD_NAMES = MAPPED_FIELDS | {"group_id", "contact_id", "channel"}
OWNED_TAGS = {"maintain-media:candidate", "maintain-media:suppressed"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
MAX_RESPONSE_BYTES = 2_000_000


class GHLConfig(BaseModel):
    """Non-secret account contract. Never accept a configurable credential host."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    location_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    mapping_version: str = Field(min_length=1, max_length=80)
    api_version: Literal["2023-02-21"] = "2023-02-21"
    field_ids: dict[str, str]
    token_env: str = Field(default="ABR_GHL_TOKEN", pattern=r"^ABR_GHL_[A-Z0-9_]+$")
    allow_writes: bool = False
    # Account contract must have a real custom-field search receipt before writes.
    group_search_field: str

    @model_validator(mode="after")
    def contract(self):
        if set(self.field_ids) != FIELD_NAMES:
            raise ValueError("GHL requires exactly the documented engine field mapping")
        ids = list(self.field_ids.values())
        if (self.location_id.startswith("REPLACE_") or len(set(ids)) != len(ids)
                or any(not ID_RE.fullmatch(v) or v.startswith(("fixture_", "REPLACE_")) for v in ids)):
            raise ValueError("GHL field IDs must be unique real account IDs")
        if self.group_search_field != "customFields." + self.field_ids["group_id"]:
            raise ValueError("GHL search must use the mapped group identity field")
        return self


def load_config(path: Path) -> GHLConfig:
    """Read only the explicitly provided non-secret integration YAML."""
    if path.name.startswith(".env") or path.suffix not in {".yaml", ".yml"}:
        raise ValueError("Provide the non-secret GHL YAML configuration")
    if path.stat().st_size > 32_768:
        raise ValueError("GHL configuration too large")
    return GHLConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class GHLRetryableError(OSError):
    """Only closed codes and numeric delay escape the transport, never API bodies."""

    def __init__(self, code: str, retry_after: int = 0):
        super().__init__(code)
        self.code, self.retry_after = code, retry_after


def retry_seconds(value: str | None, *, now: datetime | None = None) -> int:
    if value is None:
        return 0
    try:
        if value.isdigit():
            return min(86_400, int(value))
        instant = parsedate_to_datetime(value)
        return min(86_400, max(0, int((instant - (now or datetime.now(UTC))).total_seconds())))
    except (ValueError, TypeError, OverflowError):
        return 0


class GoHighLevel:
    """Protocol-compatible transport with identity-checked, DND-only projections.

    ``write_guard`` must check current outbox approval/version, suppression,
    installation receipts, and automation isolation immediately before EACH HTTP
    mutation. It receives no provider-controlled authority. CLI fixture workers do
    not construct this class until their live propagation path is also installed.
    """

    def __init__(self, config: GHLConfig, token: SecretStr, *,
                 write_guard: Callable[[], None] | None = None,
                 transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        raw_token = token.get_secret_value()
        if not raw_token or any(c.isspace() for c in raw_token):
            raise DomainError("GHL_TOKEN_MISSING_OR_INVALID", 503)
        self.config, self.write_guard, self.sleep = config, write_guard, sleep
        self.client = httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(15, connect=5),
            follow_redirects=False, trust_env=False, transport=transport,
            headers={"Authorization": "Bearer " + raw_token, "Version": config.api_version,
                     "Accept": "application/json", "User-Agent": "MaintainMedia-LeadEngine/1.0"})

    @classmethod
    def from_environment(cls, config: GHLConfig, *, environ: Mapping[str, str] | None = None, **kwargs):
        """Accept an injected process secret; deliberately does not load .env files."""
        values = os.environ if environ is None else environ
        return cls(config, SecretStr(values.get(config.token_env, "")), **kwargs)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _request(self, method: str, path: str, *, body=None, params=None,
                 mutation=False, request_id=None) -> dict:
        # All paths are constructed locally, never from next-page/provider URLs.
        if not path.startswith("/") or path.startswith("//") or ":" in path or "?" in path:
            raise DomainError("GHL_PATH_INVALID", 409)
        attempts = 1 if mutation else 3
        for attempt in range(attempts):
            if mutation:
                if not self.config.allow_writes or self.write_guard is None:
                    raise DomainError("GHL_WRITES_NOT_CERTIFIED", 409)
                self.write_guard()
            try:
                with self.client.stream(method, path, json=body, params=params,
                        headers={"X-Request-ID": str(UUID(request_id))} if request_id else None) as response:
                    # Do not read or expose provider error bodies, redirects or tokens.
                    if response.status_code == 429 or response.status_code >= 500:
                        delay = retry_seconds(response.headers.get("Retry-After"))
                        if mutation or attempt == attempts - 1 or delay > 10:
                            raise GHLRetryableError("GHL_RATE_LIMITED" if response.status_code == 429 else "GHL_UNAVAILABLE", delay)
                        self.sleep(max(delay, (2 ** attempt) + random.uniform(0, .25)))
                        continue
                    if not 200 <= response.status_code < 300:
                        raise DomainError("GHL_AUTH_REJECTED" if response.status_code in {401, 403}
                                          else "GHL_REQUEST_REJECTED", 409)
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise GHLRetryableError("GHL_RESPONSE_TOO_LARGE")
                try:
                    data = json.loads(raw)
                except (ValueError, UnicodeDecodeError, RecursionError):
                    raise GHLRetryableError("GHL_RESPONSE_INVALID") from None
                if not isinstance(data, dict):
                    raise GHLRetryableError("GHL_RESPONSE_INVALID")
                return data
            except httpx.HTTPError:
                if mutation or attempt == attempts - 1:
                    raise GHLRetryableError("GHL_TRANSPORT_UNCERTAIN") from None
                self.sleep((2 ** attempt) + random.uniform(0, .25))
        raise GHLRetryableError("GHL_UNAVAILABLE")

    @staticmethod
    def _id(value) -> str:
        if not isinstance(value, str) or not ID_RE.fullmatch(value):
            raise DomainError("GHL_REMOTE_ID_INVALID", 409)
        return value

    def _contact(self, contact, *, expected_id=None) -> dict:
        if not isinstance(contact, dict) or contact.get("locationId") != self.config.location_id:
            raise DomainError("GHL_REMOTE_LOCATION_CONFLICT", 409)
        actual_id = self._id(contact.get("id"))
        if expected_id and actual_id != expected_id:
            raise DomainError("GHL_REMOTE_IDENTITY_CONFLICT", 409)
        if not isinstance(contact.get("customFields"), list):
            raise DomainError("GHL_REMOTE_FIELDS_MISSING", 409)
        return contact

    def _fields(self, contact) -> dict:
        fields = {}
        for item in contact["customFields"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in fields:
                raise DomainError("GHL_REMOTE_FIELDS_INVALID", 409)
            fields[item["id"]] = item.get("value", item.get("fieldValue"))
        return fields

    def preflight(self) -> dict:
        """Two metadata reads; never creates contacts, fields, tags or workflows."""
        loc = self._request("GET", f"/locations/{self.config.location_id}").get("location")
        if not isinstance(loc, dict) or loc.get("id") != self.config.location_id:
            raise DomainError("GHL_REMOTE_LOCATION_CONFLICT", 409)
        items = self._request("GET", f"/locations/{self.config.location_id}/customFields",
                              params={"model": "contact"}).get("customFields")
        if not isinstance(items, list):
            raise DomainError("GHL_REMOTE_FIELDS_INVALID", 409)
        fields = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in fields:
                raise DomainError("GHL_REMOTE_FIELDS_INVALID", 409)
            fields[item["id"]] = item
        missing, invalid = [], []
        for name, field_id in self.config.field_ids.items():
            item = fields.get(field_id)
            if item is None:
                missing.append(name)
            elif (item.get("model") != "contact" or item.get("locationId") != self.config.location_id
                    or item.get("dataType") not in ({"NUMERICAL"} if name == "score" else {"TEXT", "LARGE_TEXT"})):
                invalid.append(name)
        return {"provider": "gohighlevel", "api_version": self.config.api_version,
                "location_verified": True, "fields_verified": not missing and not invalid,
                "missing_fields": sorted(missing), "invalid_fields": sorted(invalid),
                "writes_performed": 0, "messages_sent": 0,
                "ready_for_production": False,
                "pending": ["isolated_account_workflow_review", "group_search_sandbox_receipt",
                            "duplicate_uncertain_create_suppression_receipts", "live_worker_and_propagation_wiring"]}

    def find_group(self, group_id):
        group_id = str(UUID(group_id))
        data = self._request("POST", "/contacts/search", body={"locationId": self.config.location_id,
            "page": 1, "pageLimit": 100,
            "filters": [{"field": self.config.group_search_field, "operator": "eq", "value": group_id}]})
        items, total = data.get("contacts"), data.get("total")
        if not isinstance(items, list) or type(total) is not int or total != len(items) or total > 100:
            raise DomainError("GHL_SEARCH_INCOMPLETE", 409)
        ids = []
        for item in items:
            contact = self._contact(item)
            if self._fields(contact).get(self.config.field_ids["group_id"]) != group_id:
                raise DomainError("GHL_SEARCH_IDENTITY_CONFLICT", 409)
            ids.append(contact["id"])
        if len(ids) != len(set(ids)):
            raise DomainError("GHL_SEARCH_IDENTITY_CONFLICT", 409)
        return ids

    def fetch(self, remote_id):
        remote_id = self._id(remote_id)
        contact = self._contact(self._request("GET", f"/contacts/{remote_id}").get("contact"), expected_id=remote_id)
        raw = self._fields(contact)
        fields = {name: raw.get(field_id) for name, field_id in self.config.field_ids.items()}
        try:
            group_id = str(UUID(fields["group_id"]))
        except (ValueError, TypeError, AttributeError):
            raise DomainError("GHL_REMOTE_IDENTITY_CONFLICT", 409) from None
        channel = fields["channel"]
        if channel not in {"email", "phone", None}:
            raise DomainError("GHL_REMOTE_CHANNEL_INVALID", 409)
        tags = contact.get("tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise DomainError("GHL_REMOTE_TAGS_INVALID", 409)
        payload = {**fields, "group_id": group_id,
            "business_name": contact.get("name"), "endpoint": contact.get(channel) if channel else None,
            "tags": tags, "custom_field_map_version": self.config.mapping_version,
            "custom_fields": [{"id": self.config.field_ids[name], "value": fields[name]}
                               for name in sorted(MAPPED_FIELDS)] + [
                                   {"id": self.config.field_ids["group_id"], "value": group_id}]}
        if "maintain-media:suppressed" in tags:
            payload["outreach_blocked"] = contact.get("dnd") is True
        return {"group_id": group_id, "payload": payload, "provider_dnd": contact.get("dnd") is True}

    def _body(self, payload, *, creating=False):
        if payload.get("custom_field_map_version") != self.config.mapping_version:
            raise DomainError("GHL_MAPPING_REVISION_CHANGED", 409)
        group_id = str(UUID(payload["group_id"]))
        stopped = payload.get("outreach_blocked") is True
        if not stopped and (payload.get("tier") != "A" or payload.get("channel") not in {"email", "phone"}
                            or not isinstance(payload.get("endpoint"), str) or not payload["endpoint"]):
            raise DomainError("GHL_CANDIDATE_INVALID", 409)
        if not stopped and (not isinstance(payload.get("business_name"), str)
                            or not payload["business_name"].strip() or len(payload["business_name"]) > 300):
            raise DomainError("GHL_CANDIDATE_INVALID", 409)
        tags = payload.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise DomainError("GHL_TAG_INVALID", 409)
        if any(tag.startswith("maintain-media:") and tag not in OWNED_TAGS for tag in tags):
            raise DomainError("GHL_TAG_INVALID", 409)
        if stopped and "maintain-media:suppressed" not in tags:
            raise DomainError("GHL_SUPPRESSION_TAG_REQUIRED", 409)
        if not stopped and set(tags) & OWNED_TAGS != {"maintain-media:candidate"}:
            raise DomainError("GHL_CANDIDATE_TAG_REQUIRED", 409)
        values = {name: payload.get(name) for name in FIELD_NAMES}
        values["group_id"] = group_id
        if not stopped:
            if set(MAPPED_FIELDS) - payload.keys():
                raise DomainError("GHL_CANDIDATE_INVALID", 409)
            if (type(values["score"]) is not int or not 0 <= values["score"] <= 100
                    or values["state"] not in {"QLD", "NSW"}
                    or not isinstance(values["signal"], str) or not values["signal"]):
                raise DomainError("GHL_CANDIDATE_INVALID", 409)
            for name in MAPPED_FIELDS - {"score"}:
                value = values[name]
                if value is not None and (not isinstance(value, str) or len(value) > 2000):
                    raise DomainError("GHL_CANDIDATE_INVALID", 409)
            if values["abn"] is not None and not re.fullmatch(r"[0-9]{11}", values["abn"]):
                raise DomainError("GHL_CANDIDATE_INVALID", 409)
            if values["positioning_notes"] is not None and len(values["positioning_notes"]) > 400:
                raise DomainError("GHL_CANDIDATE_INVALID", 409)
            if values["website"] is not None:
                website = urlparse(values["website"])
                if website.scheme not in {"http", "https"} or not website.hostname or website.username or website.password:
                    raise DomainError("GHL_CANDIDATE_INVALID", 409)
            try:
                values["contact_id"] = str(UUID(values["contact_id"]))
            except (ValueError, TypeError, AttributeError):
                raise DomainError("GHL_CONTACT_ID_INVALID", 409) from None
        elif (any(values[name] is not None for name in FIELD_NAMES - {"group_id"})
              or payload.get("endpoint") is not None or payload.get("business_name") is not None):
            raise DomainError("GHL_SUPPRESSION_NOT_CLEARED", 409)
        body = {"name": payload.get("business_name"), "dnd": True,
                "email": payload.get("endpoint") if payload.get("channel") == "email" else None,
                "phone": payload.get("endpoint") if payload.get("channel") == "phone" else None,
                "customFields": [{"id": self.config.field_ids[name], "fieldValue": values[name]}
                                 for name in sorted(FIELD_NAMES)]}
        if creating:
            body.update(locationId=self.config.location_id, source="Maintain Media reviewed candidate",
                        tags=sorted(set(tags) & OWNED_TAGS))
        return body

    def create(self, group_id, payload, request_id):
        if str(UUID(group_id)) != payload.get("group_id"):
            raise DomainError("GHL_REMOTE_IDENTITY_CONFLICT", 409)
        # No upsert: an endpoint match may belong to another business. Verify the
        # returned group/location, never adopt a provider endpoint-only match.
        data = self._request("POST", "/contacts/", body=self._body(payload, creating=True),
                             mutation=True, request_id=request_id)
        contact = data.get("contact")
        if not isinstance(contact, dict) or contact.get("locationId") != self.config.location_id:
            raise DomainError("GHL_REMOTE_LOCATION_CONFLICT", 409)
        remote_id = self._id(contact.get("id"))
        # Create responses can be sparse. Read back the full remote record before
        # reporting a verified identity; an unavailable read remains uncertain.
        after = self.fetch(remote_id)
        if after["group_id"] != group_id:
            raise DomainError("GHL_REMOTE_IDENTITY_CONFLICT", 409)
        if not after["provider_dnd"]:
            raise DomainError("GHL_DND_NOT_CONFIRMED", 409)
        return remote_id

    def update(self, remote_id, payload, request_id):
        remote_id = self._id(remote_id)
        before = self.fetch(remote_id)
        if before["group_id"] != payload.get("group_id"):
            raise DomainError("GHL_REMOTE_IDENTITY_CONFLICT", 409)
        if "maintain-media:suppressed" in before["payload"]["tags"] and payload.get("outreach_blocked") is not True:
            raise DomainError("GHL_SUPPRESSION_REVERSAL_FORBIDDEN", 409)
        # Never put tags in PUT: HighLevel replaces the complete list there.
        self._request("PUT", f"/contacts/{remote_id}", body=self._body(copy.deepcopy(payload)),
                      mutation=True, request_id=request_id)
        current = set(before["payload"]["tags"]) & OWNED_TAGS
        desired = set(payload.get("tags", [])) & OWNED_TAGS
        for method, tags in (("DELETE", current - desired), ("POST", desired - current)):
            if tags:
                self._request(method, f"/contacts/{remote_id}/tags", body={"tags": sorted(tags)},
                              mutation=True, request_id=request_id)
