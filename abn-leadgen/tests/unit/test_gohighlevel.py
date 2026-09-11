"""HTTP contract tests; only httpx MockTransport, never real vendor writes."""
import copy
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from abr_engine.control.service import DomainError
from abr_engine.export.crm import MAPPED_FIELDS
from abr_engine.export.gohighlevel import (
    FIELD_NAMES,
    GHLConfig,
    GHLRetryableError,
    GoHighLevel,
    retry_seconds,
    workflow_inventory_digest,
)


@pytest.fixture
def config():
    ids = {name: "field_" + name for name in FIELD_NAMES}
    return GHLConfig(location_id="location_1", mapping_version="reviewed-2026-09-09",
                     field_ids=ids, group_search_field="customFields.field_group_id",
                     allowed_channels=["email", "phone"],
                     workflow_inventory_sha256=workflow_inventory_digest({"workflows": []}, "location_1"))


@pytest.fixture
def payload(config):
    return {"group_id": str(uuid4()), "contact_id": str(uuid4()), "business_name": "Synthetic Company",
            "endpoint": "hello@example.test", "channel": "email", "abn": "51824753556",
            "signal": "QBCC category", "score": 90, "tier": "A", "industry": "construction",
            "entity_class": "company", "state": "QLD", "website": "https://example.test",
            "positioning_notes": None, "basis_summary": "Reviewed test evidence",
            "tags": ["maintain-media:candidate"], "custom_field_map_version": config.mapping_version}


def contact(config, payload, **updates):
    return {"id": "remote_1", "locationId": config.location_id, "name": payload["business_name"],
            "email": payload["endpoint"], "phone": None, "dnd": True,
            "tags": ["unrelated:keep", *payload["tags"]],
            "customFields": [{"id": config.field_ids[name], "value": payload[name]} for name in FIELD_NAMES],
            **updates}


def provider(config, handler, **kwargs):
    def with_inventory(request):
        if request.url.path == "/workflows/":
            return httpx.Response(200, json={"workflows": []})
        return handler(request)
    return GoHighLevel(config, SecretStr("synthetic-not-a-real-token"),
                       transport=httpx.MockTransport(with_inventory), sleep=lambda _: None, **kwargs)


def test_readonly_metadata_preflight_never_promises_production(config):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        assert request.headers["Version"] == "2023-02-21"
        assert request.url.host == "services.leadconnectorhq.com"
        if request.url.path.endswith("customFields"):
            return httpx.Response(200, json={"customFields": [
                {"id": field_id, "model": "contact", "locationId": config.location_id,
                 "dataType": "NUMERICAL" if name == "score" else "TEXT"}
                for name, field_id in config.field_ids.items()]})
        return httpx.Response(200, json={"location": {"id": config.location_id}})

    with provider(config, handler) as client:
        result = client.preflight()
    assert result["fields_verified"] and result["location_verified"]
    assert not result["ready_for_production"]
    assert result["writes_performed"] == result["messages_sent"] == 0
    assert seen == [("GET", "/locations/location_1"), ("GET", "/locations/location_1/customFields")]


def test_preflight_detects_wrong_type_and_missing_fields(config):
    def handler(request):
        if request.url.path.endswith("customFields"):
            return httpx.Response(200, json={"customFields": [{"id": config.field_ids["score"],
                "model": "contact", "locationId": config.location_id, "dataType": "TEXT"}]})
        return httpx.Response(200, json={"location": {"id": config.location_id}})
    with provider(config, handler) as client:
        result = client.preflight()
    assert not result["fields_verified"] and result["invalid_fields"] == ["score"]
    assert len(result["missing_fields"]) == 12


@pytest.mark.parametrize("change", [{"field_ids": {}}, {"location_id": "../other"},
    {"group_search_field": "email"}, {"base_url": "https://attacker.test"}, {"api_version": "v3"}])
def test_closed_nonsecret_configuration(config, change):
    with pytest.raises(ValidationError):
        GHLConfig.model_validate({**config.model_dump(), **change})


def test_no_ambient_token_fallback(config):
    with pytest.raises(DomainError, match="GHL_TOKEN_MISSING"):
        GoHighLevel.from_environment(config, environ={"GHL_TOKEN": "unapproved-other-account-token"})


def test_group_search_checks_exact_identity_and_complete_response(config, payload):
    def handler(request):
        body = json.loads(request.content)
        assert body == {"locationId": config.location_id, "page": 1, "pageLimit": 100,
            "filters": [{"field": config.group_search_field, "operator": "eq", "value": payload["group_id"]}]}
        return httpx.Response(200, json={"contacts": [contact(config, payload)], "total": 1})
    with provider(config, handler) as client:
        assert client.find_group(payload["group_id"]) == ["remote_1"]


@pytest.mark.parametrize("failure", ["wrong_location", "wrong_identity", "duplicate_id", "truncated", "missing_total"])
def test_search_never_uses_partial_or_endpoint_only_match(config, payload, failure):
    row = contact(config, payload)
    body = {"contacts": [row], "total": 1}
    if failure == "wrong_location":
        row["locationId"] = "someone_else"
    elif failure == "wrong_identity":
        row["customFields"] = []
    elif failure == "duplicate_id":
        body = {"contacts": [row, row], "total": 2}
    elif failure == "truncated":
        body["total"] = 2
    else:
        body.pop("total")
    with provider(config, lambda _: httpx.Response(200, json=body)) as client, pytest.raises(DomainError):
        client.find_group(payload["group_id"])


def test_fetch_reconstructs_owned_projection_without_unrelated_fields(config, payload):
    raw = contact(config, payload)
    raw["customFields"].append({"id": "unrelated", "value": "never copied"})
    with provider(config, lambda _: httpx.Response(200, json={"contact": raw})) as client:
        result = client.fetch("remote_1")
    assert result["group_id"] == payload["group_id"]
    assert all(result["payload"][key] == value for key, value in payload.items() if key != "tags")
    assert result["payload"]["tags"] == ["unrelated:keep", "maintain-media:candidate"]
    assert "unrelated" not in {v["id"] for v in result["payload"]["custom_fields"]}


@pytest.mark.parametrize("allow,guard", [(False, None), (True, None), (False, lambda: None)])
def test_writes_require_both_enablement_and_current_authority(config, payload, allow, guard):
    calls = []
    with (provider(config.model_copy(update={"allow_writes": allow}), lambda r: calls.append(r), write_guard=guard) as client,
          pytest.raises(DomainError, match="GHL_WRITES_NOT_CERTIFIED")):
        client.create(payload["group_id"], payload, str(uuid4()))
    assert not calls


def test_create_is_dnd_and_readback_verified_even_with_sparse_response(config, payload):
    seen = []
    guards = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["dnd"] is True and body["phone"] is None
            assert body["email"] == payload["endpoint"]
            assert set(body) == {"name", "email", "phone", "dnd", "customFields", "locationId", "source", "tags"}
            assert all("fieldValue" in field and "value" not in field for field in body["customFields"])
            return httpx.Response(201, json={"contact": {"id": "remote_1", "locationId": config.location_id}})
        return httpx.Response(200, json={"contact": contact(config, payload)})

    with provider(config.model_copy(update={"allow_writes": True}), handler,
                  write_guard=lambda: guards.append(True)) as client:
        assert client.create(payload["group_id"], payload, str(uuid4())) == "remote_1"
    assert seen == [("POST", "/contacts/"), ("GET", "/contacts/remote_1")]
    assert len(guards) == 2


@pytest.mark.parametrize("mode", ["timeout", "server_error", "rate_limit", "redirect", "bad_json"])
def test_create_never_retries_and_sanitizes_failure(config, payload, mode):
    calls = []

    def handler(request):
        calls.append(request)
        if mode == "timeout":
            raise httpx.ReadTimeout("secret-token-and-personal-response")
        if mode == "bad_json":
            return httpx.Response(201, text="secret-token-and-personal-response")
        return httpx.Response({"server_error": 503, "rate_limit": 429, "redirect": 302}[mode],
            headers={"Location": "https://attacker.test", "Retry-After": "30"}, text="secret-token-and-personal-response")

    with (provider(config.model_copy(update={"allow_writes": True}), handler, write_guard=lambda: None) as client,
          pytest.raises((DomainError, GHLRetryableError)) as error):
        client.create(payload["group_id"], payload, str(uuid4()))
    assert len(calls) == 1
    assert "secret-token" not in str(error.value)


def test_read_retries_rate_limit_then_succeeds(config, payload):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "1"}) if len(calls) == 1 else httpx.Response(
            200, json={"contact": contact(config, payload)})
    with provider(config, handler) as client:
        assert client.fetch("remote_1")["group_id"] == payload["group_id"]
    assert len(calls) == 2


def test_long_rate_limit_is_returned_without_blocking_or_request_retry(config):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"})
    with provider(config, handler) as client, pytest.raises(GHLRetryableError) as error:
        client.preflight()
    assert error.value.retry_after == 3600 and len(calls) == 1


def test_update_preserves_unrelated_tags_and_checks_guard_before_each_mutation(config, payload):
    seen, guards = [], []
    stopped = copy.deepcopy(payload)
    for key in MAPPED_FIELDS | {"business_name", "endpoint", "channel", "contact_id"}:
        stopped[key] = None
    stopped.update(tags=["unrelated:keep", "maintain-media:suppressed"], outreach_blocked=True)

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"contact": contact(config, payload)})
        body = json.loads(request.content)
        if request.method == "PUT":
            assert "tags" not in body and body["dnd"] is True
            assert body["name"] is None and body["phone"] is None and body["email"] is None
            assert body["firstName"] is body["lastName"] is None
            assert "companyName" not in body
            assert [x for x in body["customFields"] if x["fieldValue"] is not None] == [
                {"id": config.field_ids["group_id"], "fieldValue": payload["group_id"]}]
        else:
            assert body == {"tags": ["maintain-media:candidate" if request.method == "DELETE" else "maintain-media:suppressed"]}
        return httpx.Response(200, json={"succeeded": True})

    with provider(config.model_copy(update={"allow_writes": True}), handler,
                  write_guard=lambda: guards.append(True)) as client:
        client.update("remote_1", stopped, str(uuid4()))
    assert seen == [("GET", "/contacts/remote_1"), ("PUT", "/contacts/remote_1"),
                    ("DELETE", "/contacts/remote_1/tags"), ("POST", "/contacts/remote_1/tags")]
    assert len(guards) == 6


def test_authority_revocation_between_update_and_tag_change_stops(config, payload):
    raw = contact(config, payload, tags=[])
    seen, checks = [], []
    def guard():
        checks.append(True)
        if len(checks) > 2:
            raise DomainError("APPROVAL_REVOKED", 409)
    def handler(request):
        seen.append(request.method)
        return httpx.Response(200, json={"contact": raw} if request.method == "GET" else {"succeeded": True})
    with (provider(config.model_copy(update={"allow_writes": True}), handler, write_guard=guard) as client,
          pytest.raises(DomainError, match="APPROVAL_REVOKED")):
        client.update("remote_1", payload, str(uuid4()))
    assert seen == ["GET", "PUT"]


def test_suppressed_remote_is_never_reopened(config, payload):
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"contact": contact(config, payload, tags=["maintain-media:suppressed"])})
    with (provider(config.model_copy(update={"allow_writes": True}), handler, write_guard=lambda: None) as client,
          pytest.raises(DomainError, match="GHL_SUPPRESSION_REVERSAL_FORBIDDEN")):
        client.update("remote_1", payload, str(uuid4()))
    assert calls == ["GET"]


def test_create_dnd_readback_must_be_true(config, payload):
    def handler(request):
        return httpx.Response(200, json={"contact": contact(config, payload, dnd=False)})
    with (provider(config.model_copy(update={"allow_writes": True}), handler, write_guard=lambda: None) as client,
          pytest.raises(DomainError, match="GHL_DND_NOT_CONFIRMED")):
        client.create(payload["group_id"], payload, str(uuid4()))


def test_retry_after_numeric_date_and_malformed():
    assert retry_seconds("22") == 22
    assert retry_seconds("Wed, 09 Sep 2026 12:00:05 GMT", now=datetime(2026, 9, 9, 12, tzinfo=UTC)) == 5
    assert retry_seconds("never") == 0
    assert retry_seconds("999999999") == 86400


def test_deep_json_response_is_sanitized(config):
    deeply_nested = b'{"nested":' + b'[' * 10_000 + b'0' + b']' * 10_000 + b'}'
    with (provider(config, lambda _: httpx.Response(200, content=deeply_nested)) as client,
          pytest.raises(GHLRetryableError, match="GHL_RESPONSE_INVALID")):
        client.preflight()


def test_suppression_cannot_keep_business_name(config, payload):
    stopped = copy.deepcopy(payload)
    for key in MAPPED_FIELDS | {"endpoint", "channel", "contact_id"}:
        stopped[key] = None
    stopped.update(tags=["maintain-media:suppressed"], outreach_blocked=True)
    calls = []
    with (provider(config, lambda request: calls.append(request)) as client,
          pytest.raises(DomainError, match="GHL_SUPPRESSION_NOT_CLEARED")):
        client._body(stopped)
    assert not calls


@pytest.mark.parametrize("business_name", [None, [], "", " ", "a" * 301])
def test_candidate_business_name_must_be_bounded_plain_text(config, payload, business_name):
    payload["business_name"] = business_name
    calls = []
    with (provider(config, lambda request: calls.append(request)) as client,
          pytest.raises(DomainError, match="GHL_CANDIDATE_INVALID")):
        client.create(payload["group_id"], payload, str(uuid4()))
    assert not calls


def workflow(**updates):
    return {"id": "workflow_1", "locationId": "location_1", "status": "draft",
            "version": 2, "updatedAt": "2026-09-11T00:00:00Z", **updates}


@pytest.mark.parametrize("response", [
    {}, {"workflows": None}, {"workflows": [], "nextPage": 2},
    {"workflows": [workflow(locationId="other")]},
    {"workflows": [workflow(), workflow()]},
    {"workflows": [workflow(version=True)]}, {"workflows": [workflow(version=0)]},
    {"workflows": [workflow(updatedAt="2026-09-11")]},
    {"workflows": [workflow(status="published")]}, {"workflows": [workflow(status="unknown")]},
])
def test_workflow_inventory_rejects_incomplete_or_active_account(response):
    with pytest.raises(DomainError, match="GHL_WORKFLOW"):
        workflow_inventory_digest(response, "location_1")


def test_workflow_digest_is_order_and_timestamp_representation_stable():
    first = {"workflows": [workflow(), workflow(id="workflow_2")]}
    second = {"workflows": [workflow(id="workflow_2", updatedAt="2026-09-11T00:00:00+00:00"),
                            workflow(name="Unhashed private name")], "traceId": "not_authority"}
    assert workflow_inventory_digest(first, "location_1") == workflow_inventory_digest(second, "location_1")


@pytest.mark.parametrize("response,code", [
    ({"workflows": [workflow()]}, "GHL_WORKFLOW_INVENTORY_CHANGED"),
    ({"workflows": [workflow(status="published")]}, "GHL_WORKFLOW_NOT_ISOLATED"),
    ({"workflows": [], "nextPage": 2}, "GHL_WORKFLOW_INVENTORY_INVALID"),
])
def test_workflow_guard_prevents_any_mutation(config, payload, response, code):
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        assert request.url.params["locationId"] == config.location_id
        return httpx.Response(200, json=response)
    with (GoHighLevel(config.model_copy(update={"allow_writes": True}), SecretStr("synthetic-token"),
                      transport=httpx.MockTransport(handler), write_guard=lambda: None) as client,
          pytest.raises(DomainError, match=code)):
        client.create(payload["group_id"], payload, str(uuid4()))
    assert seen == [("GET", "/workflows/")]


def test_phone_only_contract_refuses_email_before_any_http(config, payload):
    calls = []
    with (provider(config.model_copy(update={"allow_writes": True, "allowed_channels": ["phone"]}),
                   lambda request: calls.append(request), write_guard=lambda: None) as client,
          pytest.raises(DomainError, match="GHL_CHANNEL_NOT_APPROVED")):
        client.create(payload["group_id"], payload, str(uuid4()))
    assert calls == []


@pytest.mark.parametrize("change", [{"allowed_channels": []}, {"allowed_channels": ["phone", "phone"]},
    {"allowed_channels": ["sms"]}, {"workflow_inventory_sha256": None}])
def test_live_write_configuration_requires_explicit_scope_and_inventory(config, change):
    with pytest.raises(ValidationError):
        GHLConfig.model_validate({**config.model_dump(), "allow_writes": True, **change})


@pytest.mark.parametrize("name", [None, "", "absent"])
def test_fetch_recovers_provider_split_name_without_unrelated_company(config, payload, name):
    raw = contact(config, payload, firstName="Synthetic", lastName="Company", companyName="Unrelated account company")
    if name == "absent":
        raw.pop("name")
    else:
        raw["name"] = name
    with provider(config, lambda _: httpx.Response(200, json={"contact": raw})) as client:
        assert client.fetch("remote_1")["payload"]["business_name"] == payload["business_name"]


def test_fetch_does_not_hide_remaining_split_name_after_incomplete_clear(config, payload):
    raw = contact(config, payload, name=None, firstName="Synthetic", lastName=None)
    with provider(config, lambda _: httpx.Response(200, json={"contact": raw})) as client:
        assert client.fetch("remote_1")["payload"]["business_name"] == "Synthetic"
    raw.update(firstName="", lastName="", companyName="Unrelated account company")
    with provider(config, lambda _: httpx.Response(200, json={"contact": raw})) as client:
        assert client.fetch("remote_1")["payload"]["business_name"] is None
