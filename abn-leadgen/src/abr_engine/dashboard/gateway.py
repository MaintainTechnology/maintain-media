"""Authenticated TLS-proxy entry point for the synthetic dashboard only.

The ordinary dashboard remains loopback-only. This separate entry point never
enables live mode, accepts browser credentials or trusts forwarded identity.
"""

from __future__ import annotations

import argparse
import hmac
import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from abr_engine.config import Settings, load_settings
from abr_engine.dashboard.api import create_app, loopback

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_READ = re.compile(rf"/api/(?:dashboard(?:/health)?|jobs/{_UUID}|reports/{_UUID}/(?:html|csv|markdown))")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43,256}")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ERROR_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}


def public_origin(value: str) -> str:
    """Require one explicit public HTTPS DNS origin; no credential-bearing URLs."""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        labels = host.split(".")
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path not in {"", "/"} or parsed.port not in {None, 443}
                or len(host) > 253 or len(labels) < 2
                or not all(_DNS_LABEL.fullmatch(label) for label in labels)
                or not re.fullmatch(r"[a-z]{2,63}", labels[-1])
                or labels[-1] in {"localhost", "local", "internal", "lan", "home", "test", "invalid", "example", "onion"}
                or host == "home.arpa" or host.endswith(".home.arpa")):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        canonical = f"https://{host}"
        if value not in {canonical, canonical + "/", canonical + ":443", canonical + ":443/"}:
            raise ValueError
        return canonical
    except (ValueError, TypeError, AttributeError):
        raise ValueError("GATEWAY_ORIGIN_INVALID") from None


class DashboardGateway:
    """A service-token boundary before the unchanged local fixture application."""

    def __init__(self, app: ASGIApp, origin: str, token: str):
        self._app = app
        self._origin = public_origin(origin)
        self._authority = urlsplit(self._origin).netloc.encode("ascii")
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            raise ValueError("GATEWAY_TOKEN_INVALID")
        self._authorization = ("Bearer " + token).encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return

        async def reject(code: str, status: int) -> None:
            response = JSONResponse({"code": code}, status_code=status, headers=_ERROR_HEADERS)
            await response(scope, receive, send)

        # Uvicorn must run with proxy_headers=False so this is the actual socket peer.
        client = scope.get("client")
        if not client or not loopback(client[0]):
            await reject("GATEWAY_PROXY_REQUIRED", 403)
            return
        headers: dict[bytes, bytes] = {}
        for name, value in scope.get("headers", []):
            name = name.lower()
            if name in headers:
                await reject("GATEWAY_HEADERS_INVALID", 400)
                return
            headers[name] = value
        if not hmac.compare_digest(headers.get(b"authorization", b""), self._authorization):
            await reject("GATEWAY_UNAUTHENTICATED", 401)
            return
        if headers.get(b"host") != self._authority:
            await reject("GATEWAY_HOST_INVALID", 403)
            return
        origin = headers.get(b"origin")
        mutation = scope["method"] in {"POST", "PATCH"}
        if ((origin is not None and origin != self._origin.encode("ascii"))
                or (mutation and origin is None)
                or headers.get(b"sec-fetch-site") == b"cross-site"):
            await reject("SAME_ORIGIN_REQUIRED", 403)
            return
        path = scope["path"]
        allowed = ((scope["method"] == "GET" and _READ.fullmatch(path))
                   or (scope["method"] == "POST" and path == "/api/runs")
                   or (scope["method"] == "PATCH" and path == "/api/settings"))
        if (not allowed or not path.isascii() or scope.get("query_string")
                or scope.get("raw_path", path.encode("ascii")) != path.encode("ascii")):
            await reject("ROUTE_NOT_FOUND", 404)
            return

        # This is in-process routing, not an HTTP relay or a publicly reachable
        # copy of port 8767. Only the checked service request gets the local scope.
        forwarded = [(b"host", b"127.0.0.1:8767")]
        for name in (b"accept", b"content-type", b"content-length", b"x-dashboard-csrf"):
            if name in headers:
                forwarded.append((name, headers[name]))
        if origin is not None:
            forwarded.append((b"origin", b"http://127.0.0.1:8767"))
        internal = {**scope, "scheme": "http", "server": ("127.0.0.1", 8767),
                    "client": ("127.0.0.1", 0), "headers": forwarded}
        await self._app(internal, receive, send)


def create_gateway(settings: Settings, *, origin: str, token: str) -> DashboardGateway:
    # Validate configuration before constructing the application or opening files.
    if settings.mode != "fixture":
        raise ValueError("GATEWAY_FIXTURE_ONLY")
    public_origin(origin)
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise ValueError("GATEWAY_TOKEN_INVALID")
    return DashboardGateway(create_app(settings), origin, token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Private authenticated synthetic dashboard TLS gateway")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("GATEWAY_PORT_INVALID")
        gateway = create_gateway(load_settings(args.config),
                                 origin=os.environ.get("ABN_ENGINE_ORIGIN", ""),
                                 token=os.environ.get("ABN_ENGINE_TOKEN", ""))
    except (ValueError, OSError):
        parser.exit(2, "Gateway configuration rejected. Check fixture mode, HTTPS origin and private token.\n")
    import uvicorn

    uvicorn.run(gateway, host="127.0.0.1", port=args.port, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
