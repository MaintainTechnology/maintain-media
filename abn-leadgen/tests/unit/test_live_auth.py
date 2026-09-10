"""Adversarial request-bound website assertions; no network or database."""
import hashlib
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest

from abr_engine.control.service import DomainError
from abr_engine.live.auth import WebsiteAuthority

KEY = "synthetic-website-key-" + "x" * 43


def signed(*, change=None, method="POST", body=b'{"lead_id":"opaque"}'):
    request_id, key = str(uuid4()), str(uuid4()) if method == "POST" else ""
    now = int(time.time())
    claims = {"iss": "maintain-media-website", "aud": "abr-engine-live", "sub": "user_Human123",
              "iat": now, "exp": now + 60, "jti": str(uuid4()), "scopes": ["operator"],
              "method": method, "path": "/v1/suppressions", "request_id": request_id,
              "idempotency_key": key, "body_sha256": hashlib.sha256(body).hexdigest()}
    claims.update(change or {})
    request = SimpleNamespace(headers={"authorization": "Bearer " + jwt.encode(claims, KEY, algorithm="HS256"),
        "idempotency-key": key, "x-request-id": request_id}, method=method,
        url=SimpleNamespace(path="/v1/suppressions", query=""), state=SimpleNamespace(raw_body=body))
    return request


def test_valid_actor_has_actual_clerk_subject_and_explicit_scopes():
    actor = WebsiteAuthority(KEY)(signed())
    assert actor.actor_id == "user_Human123"
    assert actor.scopes == {"operator"}
    with pytest.raises(DomainError, match="FORBIDDEN"):
        actor.require("reviewer")


@pytest.mark.parametrize("change", [
    {"iss": "other"}, {"aud": "fixture"}, {"sub": "friendly-name"}, {"sub": None},
    {"scopes": ["sender"]}, {"scopes": [None]}, {"scopes": "admin"}, {"scopes": []},
    {"exp": int(time.time()) + 901}, {"iat": "1"}, {"exp": 1}, {"jti": "bad"},
    {"body_sha256": "0" * 64}, {"method": "GET"}, {"path": "/v1/crm-approvals"},
    {"request_id": str(uuid4())}, {"idempotency_key": str(uuid4())},
    {"jti": 123}, {"request_id": 123}, {"idempotency_key": None},
])
def test_claim_tampering_or_excess_authority_rejected(change):
    with pytest.raises(DomainError, match="UNAUTHENTICATED"):
        WebsiteAuthority(KEY)(signed(change=change))


def test_replay_to_changed_body_route_or_query_is_rejected():
    for field in ("body", "path", "query"):
        request = signed()
        if field == "body":
            request.state.raw_body += b" "
        else:
            setattr(request.url, field, "/different" if field == "path" else "offset=1")
        with pytest.raises(DomainError, match="UNAUTHENTICATED"):
            WebsiteAuthority(KEY)(request)


def test_fixture_or_other_service_key_cannot_authenticate():
    with pytest.raises(DomainError, match="UNAUTHENTICATED"):
        WebsiteAuthority("different-material-" + "z" * 43)(signed())


def test_read_token_needs_no_idempotency_key_but_still_binds_request():
    assert WebsiteAuthority(KEY)(signed(method="GET", body=b"")).actor_id == "user_Human123"
