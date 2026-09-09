"""Short-lived signed identities. Public fixture keys cannot authenticate live environments."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from abr_engine.control.service import DomainError


@dataclass(frozen=True)
class Actor:
    actor_id: str
    scopes: frozenset[str]

    def require(self, *scopes):
        if not self.scopes.intersection(scopes):
            raise DomainError("FORBIDDEN", 403)


def authenticate(header, service) -> Actor:
    if not header or not header.startswith("Bearer "):
        raise DomainError("UNAUTHENTICATED", 401)
    try:
        claims = jwt.decode(header[7:], service.keys.signing_key, algorithms=["HS256"],
                            audience=service.settings.audience, issuer=service.settings.issuer,
                            options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        if claims["exp"] - claims["iat"] > 900 or not isinstance(claims.get("scopes"), list):
            raise ValueError("Invalid lifetime/scope")
        return Actor(claims["sub"], frozenset(claims["scopes"]))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise DomainError("UNAUTHENTICATED", 401) from None


def fixture_token(service, actor="fixture-reviewer", scopes=None) -> str:
    if service.settings.mode != "fixture":
        raise DomainError("FIXTURE_ONLY", 403)
    now = datetime.now(UTC)
    return jwt.encode({"sub": actor, "scopes": scopes or ["operator", "reviewer", "compliance"],
                       "iat": now, "exp": now + timedelta(minutes=15), "iss": service.settings.issuer,
                       "aud": service.settings.audience}, service.keys.signing_key, algorithm="HS256")
