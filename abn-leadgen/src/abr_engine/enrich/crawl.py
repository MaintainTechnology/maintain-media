"""Bounded static crawler with one-resolution, public-IP-pinned connections.

The transport never consults proxy environment variables and performs no retries.
Production deployment additionally requires the host egress firewall release gate.
"""

import hashlib
import http.client
import ipaddress
import queue
import socket
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from protego import Protego

from abr_engine.enrich.identity import registrable_domain

MAX_BYTES = 2 * 1024 * 1024
USER_AGENT = "MaintainMediaEvidenceBot/1.0"


class CrawlBlocked(ValueError):
    pass


def public_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise CrawlBlocked("IP_INVALID") from exc
    effective = (
        address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped else address
    )
    if not effective.is_global or effective.is_multicast or effective.is_reserved or effective.is_unspecified:
        raise CrawlBlocked("IP_NOT_PUBLIC")
    # Transition mechanisms can encapsulate forbidden IPv4 destinations.
    if isinstance(address, ipaddress.IPv6Address) and (address.sixtofour or address.teredo):
        raise CrawlBlocked("IP_TRANSITION_UNSUPPORTED")
    return str(address)


def validate_url(url: str) -> str:
    if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        raise CrawlBlocked("URL_INVALID")
    try:
        parsed = urlsplit(url)
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise CrawlBlocked("URL_INVALID") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
    ):
        raise CrawlBlocked("URL_FORBIDDEN")
    if "%" in host:
        raise CrawlBlocked("HOST_INVALID")
    try:
        ascii_host = host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise CrawlBlocked("HOST_INVALID") from exc
    authority = f"[{ascii_host}]" if ":" in ascii_host else ascii_host
    if port:
        authority += f":{port}"
    return urlunsplit((parsed.scheme, authority, parsed.path or "/", parsed.query, ""))


def resolve_public(hostname: str, timeout: float = 20) -> tuple[str, ...]:
    """Bound DNS waiting; a tardy resolver thread cannot initiate a connection."""
    result: queue.Queue = queue.Queue(maxsize=1)

    def resolve() -> None:
        try:
            result.put(
                tuple(item[4][0] for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM))
            )
        except (OSError, UnicodeError) as exc:
            result.put(exc)

    threading.Thread(target=resolve, daemon=True).start()
    try:
        values = result.get(timeout=max(0, timeout))
    except queue.Empty as exc:
        raise CrawlBlocked("DNS_DEADLINE") from exc
    if isinstance(values, Exception):
        raise CrawlBlocked("DNS_FAILED") from values
    if not values:
        raise CrawlBlocked("DNS_EMPTY")
    return tuple(sorted({public_ip(value) for value in values}))


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
    peer_ip: str


class Transport(Protocol):
    def request(self, url: str, selected_ip: str, *, deadline: float, max_bytes: int) -> Response: ...


class PinnedTransport:
    def __init__(self, *, ssl_context: ssl.SSLContext | None = None):
        self.context = ssl_context or ssl.create_default_context()
        if not self.context.check_hostname or self.context.verify_mode != ssl.CERT_REQUIRED:
            raise CrawlBlocked("TLS_VERIFICATION_REQUIRED")

    def request(self, url: str, selected_ip: str, *, deadline: float, max_bytes: int = MAX_BYTES) -> Response:
        if not self.context.check_hostname or self.context.verify_mode != ssl.CERT_REQUIRED:
            raise CrawlBlocked("TLS_VERIFICATION_REQUIRED")
        url = validate_url(url)
        selected_ip = public_ip(selected_ip)
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.socket(socket.AF_INET6 if ":" in selected_ip else socket.AF_INET, socket.SOCK_STREAM)
        holder = [sock]

        def abort() -> None:
            try:
                holder[0].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            holder[0].close()

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            sock.close()
            raise CrawlBlocked("REQUEST_DEADLINE")
        timer = threading.Timer(remaining, abort)
        timer.daemon = True
        timer.start()
        try:
            sock.settimeout(remaining)
            # Numeric IP passed directly to socket.connect: no second hostname resolution.
            sock.connect((selected_ip, port))
            if ipaddress.ip_address(sock.getpeername()[0]) != ipaddress.ip_address(selected_ip):
                raise CrawlBlocked("PEER_MISMATCH")
            if parsed.scheme == "https":
                sock = self.context.wrap_socket(
                    sock, server_hostname=parsed.hostname, do_handshake_on_connect=False
                )
                holder[0] = sock
                sock.do_handshake()
            if ipaddress.ip_address(sock.getpeername()[0]) != ipaddress.ip_address(selected_ip):
                raise CrawlBlocked("PEER_MISMATCH")
            path = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
            request = f"GET {path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nUser-Agent: {USER_AGENT}\r\nAccept: text/html,text/plain\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode("ascii"))
            response = http.client.HTTPResponse(sock)
            response.begin()
            headers = {key.lower(): value for key, value in response.getheaders()}
            if headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
                raise CrawlBlocked("ENCODING_UNSUPPORTED")
            try:
                length = int(headers["content-length"]) if "content-length" in headers else None
            except ValueError as exc:
                raise CrawlBlocked("LENGTH_INVALID") from exc
            if length is not None and (length < 0 or length > max_bytes):
                raise CrawlBlocked("RESPONSE_TOO_LARGE")
            body = response.read(max_bytes + 1)
            if length is not None and not response.chunked and len(body) != length:
                raise CrawlBlocked("LENGTH_MISMATCH")
            if time.monotonic() >= deadline:
                raise CrawlBlocked("REQUEST_DEADLINE")
            if len(body) > max_bytes:
                raise CrawlBlocked("RESPONSE_TOO_LARGE")
            return Response(response.status, headers, body, selected_ip)
        except (OSError, http.client.HTTPException, UnicodeError) as exc:
            raise CrawlBlocked("TRANSPORT_FAILED") from exc
        finally:
            timer.cancel()
            holder[0].close()


@dataclass(frozen=True)
class Page:
    url: str
    html: str
    sha256: str
    robots_decision: str = "allowed"


@dataclass
class CrawlResult:
    pages: list[Page] = field(default_factory=list)
    requests: int = 0
    reason: str = "complete"
    terms_assessment: str = "unknown"


class SafeCrawler:
    def __init__(
        self,
        transport: Transport,
        *,
        resolver: Callable = resolve_public,
        clock: Callable = time.monotonic,
        sleep: Callable = time.sleep,
    ):
        self.transport, self.resolver, self.clock, self.sleep = transport, resolver, clock, sleep
        self._last: dict[str, float] = {}
        self._robots: dict[str, tuple[float, Protego]] = {}
        self._crawl_delay: dict[str, float] = {}
        self._result = CrawlResult()

    def _request(self, url: str) -> Response:
        if self._result.requests >= 20:
            raise CrawlBlocked("REQUEST_BUDGET")
        url = validate_url(url)
        domain = registrable_domain(url)
        delay = self._last.get(domain, -1e9) + max(1, self._crawl_delay.get(domain, 1)) - self.clock()
        if delay > 0:
            self.sleep(delay)
        start = self.clock()
        values = self.resolver(urlsplit(url).hostname, timeout=20)
        if not values:
            raise CrawlBlocked("DNS_EMPTY")
        addresses = sorted({public_ip(value) for value in values})
        if self.clock() >= start + 20:
            raise CrawlBlocked("REQUEST_DEADLINE")
        self._result.requests += 1
        self._last[domain] = self.clock()
        response = self.transport.request(url, addresses[0], deadline=start + 20, max_bytes=MAX_BYTES)
        if public_ip(response.peer_ip) != addresses[0]:
            raise CrawlBlocked("PEER_MISMATCH")
        if self.clock() >= start + 20:
            raise CrawlBlocked("REQUEST_DEADLINE")
        if len(response.body) > MAX_BYTES:
            raise CrawlBlocked("RESPONSE_TOO_LARGE")
        if response.status in {403, 429}:
            raise CrawlBlocked("SITE_BLOCKED")
        return response

    def _allowed(self, url: str, domain: str) -> bool:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cache_key = parsed.hostname
        if not cache_key:
            raise CrawlBlocked("HOST_INVALID")
        cached = self._robots.get(cache_key)
        if cached and self.clock() < cached[0]:
            return cached[1].can_fetch(url, USER_AGENT)
        robots_url = origin + "/robots.txt"
        # Cache failed retrievals too: retrying an attempt cannot hammer robots.
        self._robots[cache_key] = (self.clock() + 3600, Protego.parse("User-agent: *\nDisallow: /"))
        # One robots retrieval per origin/cache period; redirects fail closed instead of
        # consuming an extra robots fetch or following a cross-host policy implicitly.
        response = self._request(robots_url)
        if response.status in {404, 410}:
            rules = ""
        elif response.status == 200:
            rules = response.body.decode("utf-8", errors="replace")
        else:
            raise CrawlBlocked("ROBOTS_UNAVAILABLE")
        robot = Protego.parse(rules)
        self._robots[cache_key] = (self.clock() + 3600, robot)
        self._crawl_delay[domain] = max(1, robot.crawl_delay(USER_AGENT) or 1)
        return robot.can_fetch(url, USER_AGENT)

    def _fetch(self, url: str, domain: str) -> tuple[str, Response]:
        for redirect in range(4):
            url = validate_url(url)
            hostname = urlsplit(url).hostname
            if not hostname:
                raise CrawlBlocked("HOST_INVALID")
            # Validate literal IPs before domain parsing; never let numeric targets reach DNS.
            try:
                ipaddress.ip_address(hostname)
            except ValueError:
                pass
            else:
                public_ip(hostname)
                raise CrawlBlocked("CONTENT_DOMAIN_MISMATCH")
            if registrable_domain(url) != domain:
                raise CrawlBlocked("CONTENT_DOMAIN_MISMATCH")
            if not self._allowed(url, domain):
                raise CrawlBlocked("ROBOTS_DENIED")
            response = self._request(url)
            if response.status not in {301, 302, 303, 307, 308}:
                return url, response
            if redirect == 3:
                raise CrawlBlocked("REDIRECT_BUDGET")
            location = response.headers.get("location")
            if not location:
                raise CrawlBlocked("REDIRECT_INVALID")
            url = urljoin(url, location)
        raise AssertionError("unreachable")

    def crawl(self, url: str, *, terms_permit: Callable[[Page], bool | None] | None = None) -> CrawlResult:
        self._result = CrawlResult()
        try:
            url = validate_url(url)
            domain = registrable_domain(url)
            pending, seen = [url], set()
            while pending and len(self._result.pages) < 6:
                requested = pending.pop(0)
                if requested in seen:
                    continue
                seen.add(requested)
                final, response = self._fetch(requested, domain)
                seen.add(final)
                if response.status != 200:
                    raise CrawlBlocked("HTTP_UNAVAILABLE")
                if "text/html" not in response.headers.get("content-type", "").lower():
                    raise CrawlBlocked("HTML_REQUIRED")
                html = response.body.decode("utf-8", errors="replace")
                page = Page(final, html, hashlib.sha256(response.body).hexdigest())
                self._result.pages.append(page)
                if terms_permit and terms_permit(page) is False:
                    self._result.terms_assessment = "restricted"
                    raise CrawlBlocked("TERMS_RESTRICTED")
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "template", "noscript"]):
                    tag.decompose()
                if not soup.get_text(" ", strip=True):
                    raise CrawlBlocked("STATIC_CONTENT_UNAVAILABLE")
                links = []
                for link in soup.find_all("a", href=True):
                    href = link.get("href")
                    if not isinstance(href, str):
                        continue
                    target = urljoin(final, href)
                    if any(
                        word in (link.get_text(" ") + " " + target).lower()
                        for word in ("contact", "about", "terms", "privacy")
                    ):
                        try:
                            target = validate_url(target)
                            if registrable_domain(target) == domain and target not in seen:
                                links.append(target)
                        except ValueError:
                            continue
                pending.extend(sorted(set(links) - set(pending)))
            if pending:
                self._result.reason = "PAGE_BUDGET"
        except (CrawlBlocked, ValueError) as exc:
            self._result.reason = str(exc)
        return self._result
