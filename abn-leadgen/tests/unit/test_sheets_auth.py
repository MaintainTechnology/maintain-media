"""Signed editor identities and executable Apps Script/Python token interoperability."""
import hashlib
import hmac
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from starlette.requests import Request

from abr_engine.control.service import DomainError
from abr_engine.control.sheets_auth import (
    AUDIENCE,
    BRIDGE_SUBJECT,
    ISSUER,
    BridgeRegistry,
    authenticate_sheets_request,
)

KEYS = {"ABR_SHEETS_SIGNING_KEY": "synthetic-signing-material-" + "a"*32,
        "ABR_SHEETS_BRIDGE_SECRET": "synthetic-bridge-material-" + "b"*32}


@pytest.fixture
def registry():
    now = datetime.now(UTC)
    return BridgeRegistry(schema_version=1, enabled=True, spreadsheet_id="syntheticBook123", sheet_id=0,
        owner_email="reviewer@example.test",
        approved_by="synthetic-owner", evidence_ref="synthetic-isolated-fixture", evidence_sha256="a"*64,
        verified_at=now-timedelta(seconds=5), expires_at=now+timedelta(days=1),
        editors={"reviewer@example.test": ["operator"]})


def signed_request(registry, *, change=None, token=None, path=None, method="PATCH", body=b'{}',
                   actor="reviewer@example.test", stamp=None, signature=None, query=b""):
    now = datetime.now(UTC)
    path = path or "/v1/worklist-rows/" + str(uuid4())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": BRIDGE_SUBJECT,
        "iat": int(now.timestamp()), "exp": int(now.timestamp())+60, "method": method, "path": path,
        "body_sha256": hashlib.sha256(body).hexdigest(), "editor": actor,
        "spreadsheet_id": registry.spreadsheet_id, "sheet_id": registry.sheet_id, **(change or {})}
    token = token or jwt.encode(claims, KEYS["ABR_SHEETS_SIGNING_KEY"], algorithm="HS256")
    stamp = stamp or now.isoformat()
    key = str(uuid4())
    canonical = f"{method}\n{path}\n{stamp}\n{actor}\n{key}\n{body.decode()}"
    signature = signature or hmac.new(KEYS["ABR_SHEETS_BRIDGE_SECRET"].encode(), canonical.encode(), hashlib.sha256).hexdigest()
    headers = {"authorization": "Bearer " + token, "x-bridge-actor": actor, "idempotency-key": key,
               "x-bridge-timestamp": stamp, "x-bridge-signature": signature}
    request = Request({"type": "http", "method": method, "path": path, "query_string": query,
        "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
        "scheme": "https", "server": ("engine.example.test", 443)})
    request.state.raw_body = body
    return request


def test_actual_editor_limited_scopes_and_immediate_suppression(registry):
    for method, path in [("PATCH", "/v1/worklist-rows/" + str(uuid4())), ("POST", "/v1/suppressions")]:
        actor = authenticate_sheets_request(signed_request(registry, method=method, path=path), registry, environ=KEYS)
        assert actor.actor_id == "reviewer@example.test" and actor.scopes == frozenset({"operator"})


def test_only_exact_empty_get_worklist_is_permitted(registry):
    request = signed_request(registry, method="GET", path="/v1/sheets/worklist", body=b"")
    assert authenticate_sheets_request(request, registry, environ=KEYS).actor_id == "reviewer@example.test"
    for path, body in [("/v1/sheets/worklist", b'{}'), ("/v1/sheets/worklist/", b""), ("/api/dashboard", b"")]:
        with pytest.raises(DomainError, match="SHEETS_REQUEST_UNAUTHENTICATED"):
            authenticate_sheets_request(signed_request(registry, method="GET", path=path, body=body), registry, environ=KEYS)


@pytest.mark.parametrize("change", [
    {"sub": "website-admin"}, {"iss": "maintain-media-website"}, {"aud": "abr-engine-live"},
    {"method": "POST"}, {"path": "/v1/policy"}, {"body_sha256": "a"*64},
    {"editor": "other@example.test"}, {"spreadsheet_id": "otherBook"}, {"sheet_id": 1},
    {"sheet_id": False}, {"exp": 9999999999}, {"iat": False},
])
def test_wrong_scope_identity_workbook_body_and_lifetime_fail(registry, change):
    with pytest.raises(DomainError, match="SHEETS_REQUEST_UNAUTHENTICATED"):
        authenticate_sheets_request(signed_request(registry, change=change), registry, environ=KEYS)


@pytest.mark.parametrize("kwargs", [{"actor": "unmapped@example.test"}, {"signature": "0"*64},
    {"stamp": "2020-01-01T00:00:00Z"}, {"path": "/v1/policy", "method": "POST"}, {"query": b"other=true"}])
def test_unmapped_stale_forged_and_unapproved_routes_fail(registry, kwargs):
    with pytest.raises(DomainError):
        authenticate_sheets_request(signed_request(registry, **kwargs), registry, environ=KEYS)


def test_no_key_fallback_and_no_shared_key_material(registry):
    request = signed_request(registry)
    for keys in ({}, {"ABR_SHEETS_SIGNING_KEY": "x"*32, "ABR_SHEETS_BRIDGE_SECRET": "x"*32}):
        with pytest.raises(DomainError, match="SHEETS_AUTH_NOT_CONFIGURED"):
            authenticate_sheets_request(request, registry, environ=keys)


def test_apps_script_mints_a_token_python_verifies(registry):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for actual Apps Script parity test")
    path = "/v1/worklist-rows/" + str(uuid4())
    source = Path(__file__).resolve().parents[2] / "integrations/sheets_bridge.gs"
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const params=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx={Utilities:{Charset:{UTF_8:'utf8'},DigestAlgorithm:{SHA_256:'sha256'},
 base64EncodeWebSafe:value=>Buffer.from(typeof value==='string'?value:Uint8Array.from(value)).toString('base64url'),
 computeDigest:(_,value)=>Array.from(crypto.createHash('sha256').update(value).digest()),
 computeHmacSha256Signature:(value,key)=>Array.from(crypto.createHmac('sha256',key).update(value).digest())}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const properties={getProperty:key=>({WORKLIST_SHEET_ID:'0',SPREADSHEET_ID:'syntheticBook123'})[key]};
process.stdout.write(ctx.serviceToken_('patch',params.path,'{}','reviewer@example.test',params.key,properties));
"""
    completed = subprocess.run([node, "-e", harness, str(source)], capture_output=True, text=True,
        input=json.dumps({"path": path, "key": KEYS["ABR_SHEETS_SIGNING_KEY"]}), timeout=15, check=True)
    actor = authenticate_sheets_request(signed_request(registry, path=path, token=completed.stdout),
                                        registry, environ=KEYS)
    assert actor.actor_id == "reviewer@example.test"
