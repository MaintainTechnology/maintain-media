"""Request-bound, short-lived staff assertions from the trusted website server."""

import hashlib
import re
from dataclasses import dataclass, field
from uuid import UUID

import jwt

from abr_engine.control.auth import Actor
from abr_engine.control.service import DomainError

SCOPES = frozenset({"admin", "operator", "reviewer", "owner", "compliance"})


@dataclass(frozen=True)
class WebsiteAuthority:
    key: str = field(repr=False)
    issuer: str = "maintain-media-website"
    audience: str = "abr-engine-live"

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,256}", self.key):
            raise ValueError("Dedicated 256-bit website assertion key required")

    def __call__(self, request) -> Actor:
        header = request.headers.get("authorization", "")
        try:
            if not header.startswith("Bearer ") or len(header) > 8192:
                raise ValueError("header")
            claims = jwt.decode(
                header[7:],
                self.key,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": [
                        "sub",
                        "iss",
                        "aud",
                        "iat",
                        "exp",
                        "jti",
                        "scopes",
                        "method",
                        "path",
                        "body_sha256",
                        "request_id",
                        "idempotency_key",
                    ]
                },
            )
            if (
                type(claims["iat"]) is not int
                or type(claims["exp"]) is not int
                or not 0 < claims["exp"] - claims["iat"] <= 60
                or not re.fullmatch(r"user_[A-Za-z0-9]{1,200}", claims["sub"])
                or not isinstance(claims["scopes"], list)
                or not claims["scopes"]
                or not all(isinstance(s, str) for s in claims["scopes"])
                    or not set(claims["scopes"]) <= SCOPES
                    or any(not isinstance(claims[name], str) for name in ("jti", "request_id", "idempotency_key"))
            ):
                raise ValueError("identity")
            UUID(claims["jti"])
            UUID(claims["request_id"])
            mutation = request.method not in {"GET", "HEAD"}
            if mutation:
                UUID(claims["idempotency_key"])
            elif claims["idempotency_key"]:
                raise ValueError("read key")
            body = getattr(request.state, "raw_body", b"")
            if (
                claims["method"] != request.method
                or claims["path"] != request.url.path
                or request.url.query
                or claims["body_sha256"] != hashlib.sha256(body).hexdigest()
                or claims["request_id"] != request.headers.get("x-request-id", "")
                or claims["idempotency_key"] != request.headers.get("idempotency-key", "")
            ):
                raise ValueError("request binding")
            return Actor(claims["sub"], frozenset(claims["scopes"]))
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
            raise DomainError("UNAUTHENTICATED", 401) from None
