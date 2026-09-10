"""Short-lived request-bound Sheets identity, separate from website/admin credentials."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import jwt
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from abr_engine.control.auth import Actor
from abr_engine.control.service import DomainError

ISSUER = "maintain-media-sheets"
AUDIENCE = "abr-engine-sheets"
BRIDGE_SUBJECT = "private-worklist-bridge"


class BridgeRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    enabled: Literal[True]
    spreadsheet_id: str = Field(pattern=r"^[A-Za-z0-9_-]{10,150}$")
    sheet_id: int = Field(ge=0, le=2_147_483_647)
    owner_email: str
    approved_by: str = Field(min_length=1, max_length=200)
    evidence_ref: str = Field(min_length=1, max_length=1000)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_at: datetime
    expires_at: datetime
    editors: dict[str, list[Literal["operator", "reviewer", "compliance"]]]

    @model_validator(mode="after")
    def named_editors(self):
        if (not self.editors or self.owner_email not in self.editors
                or self.verified_at.tzinfo is None or self.expires_at.tzinfo is None
                or self.expires_at <= self.verified_at or not self.approved_by.strip()
                or not self.evidence_ref.strip() or any(not scopes or len(scopes) != len(set(scopes))
                    or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
                    or email != email.lower() for email, scopes in self.editors.items())):
            raise ValueError("A dated private workbook and named editor registry are required")
        return self


def load_bridge_registry(path: Path) -> BridgeRegistry:
    try:
        if (not path.is_absolute() or path.name.startswith(".env") or path.suffix not in {".yaml", ".yml"}
                or path.stat().st_size > 32_768):
            raise ValueError("Invalid non-secret bridge registry")
        registry = BridgeRegistry.model_validate(yaml.safe_load(path.read_bytes()))
        if not registry.verified_at <= datetime.now(UTC) < registry.expires_at:
            raise ValueError("Expired bridge installation")
    except (OSError, ValueError, TypeError, ValidationError, yaml.YAMLError):
        raise DomainError("SHEETS_INSTALLATION_NOT_CURRENT", 401) from None
    return registry


def authenticate_sheets_request(request, registry: BridgeRegistry, *, environ=None) -> Actor:
    """Validate both service capability and actual editor; never returns admin/bridge scopes."""
    values = os.environ if environ is None else environ
    key = values.get("ABR_SHEETS_SIGNING_KEY", "")
    secret = values.get("ABR_SHEETS_BRIDGE_SECRET", "")
    if (len(key.encode()) < 32 or len(secret.encode()) < 32 or key == secret
            or not registry.verified_at <= datetime.now(UTC) < registry.expires_at):
        raise DomainError("SHEETS_AUTH_NOT_CONFIGURED", 401)
    try:
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            raise ValueError("Bearer required")
        claims = jwt.decode(header[7:], key, algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
            options={"require": ["iss", "aud", "sub", "iat", "exp", "method", "path", "body_sha256",
                                 "editor", "spreadsheet_id", "sheet_id"]})
        raw = request.state.raw_body
        editor = request.headers.get("x-bridge-actor", "")
        path, method = request.url.path, request.method
        if (type(claims["exp"]) is not int or type(claims["iat"]) is not int
                or not 0 < claims["exp"]-claims["iat"] <= 60 or claims["sub"] != BRIDGE_SUBJECT
                or claims["method"] != method or claims["path"] != path
                or claims["body_sha256"] != hashlib.sha256(raw).hexdigest()
                or claims["editor"] != editor or editor not in registry.editors
                or claims["spreadsheet_id"] != registry.spreadsheet_id
                or type(claims["sheet_id"]) is not int or claims["sheet_id"] != registry.sheet_id
                or request.url.query
                or not ((method == "GET" and path == "/v1/sheets/worklist" and not raw)
                        or (method == "POST" and path == "/v1/suppressions")
                        or (method == "PATCH" and re.fullmatch(r"/v1/worklist-rows/[0-9a-f-]{36}", path)))):
            raise ValueError("Request binding mismatch")
        stamp = request.headers.get("x-bridge-timestamp", "")
        instant = datetime.fromisoformat(stamp)
        if instant.tzinfo is None or abs((datetime.now(UTC)-instant).total_seconds()) > 60:
            raise ValueError("Stale bridge signature")
        message = "\n".join([method, path, stamp, editor,
                            request.headers.get("idempotency-key", ""), raw.decode("utf-8")])
        signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, request.headers.get("x-bridge-signature", "")):
            raise ValueError("Invalid bridge signature")
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        raise DomainError("SHEETS_REQUEST_UNAUTHENTICATED", 401) from None
    return Actor(editor, frozenset(registry.editors[editor]))


class SheetsAuthority:
    """Reload editor/installation revocation for every request; secrets remain process-only."""
    def __init__(self, registry_path: Path, *, environ=None):
        self.path, self.environ = registry_path, environ

    def __call__(self, request):
        return authenticate_sheets_request(request, load_bridge_registry(self.path), environ=self.environ)
