import io
import ssl

import pytest

from abr_engine.enrich.crawl import (
    MAX_BYTES,
    CrawlBlocked,
    PinnedTransport,
    Response,
    SafeCrawler,
    public_ip,
    validate_url,
)

PUBLIC = "93.184.216.34"


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, delay):
        self.now += delay


class FixtureTransport:
    def __init__(self, responses, clock):
        self.responses, self.clock, self.calls = responses, clock, []

    def request(self, url, selected_ip, *, deadline, max_bytes):
        self.calls.append((url, selected_ip, self.clock()))
        return self.responses[url]


def response(body=b"<html>Example</html>", status=200, **headers):
    return Response(status, {"content-type": "text/html"} | headers, body, PUBLIC)


def crawler(responses=None, resolver=None):
    clock = Clock()
    routes = {"https://example.com/robots.txt": response(b"User-agent: *\nDisallow:")}
    routes.update(responses or {"https://example.com/": response()})
    transport = FixtureTransport(routes, clock)
    return SafeCrawler(
        transport, resolver=resolver or (lambda host, timeout: (PUBLIC,)), clock=clock, sleep=clock.sleep
    ), transport


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
        "100.64.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:10.0.0.1",
        "2002:0a00:0001::1",
        "192.0.2.1",
    ],
)
def test_nonpublic_addresses_rejected(ip):
    with pytest.raises(CrawlBlocked):
        public_ip(ip)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://name:secret@example.com/",
        "http://example.com:8080/",
        "https://example.com/\r\nInjected:1",
        "https://example.com\\@127.0.0.1",
        "http://[fe80::1%25eth0]/",
    ],
)
def test_bad_urls_rejected(url):
    with pytest.raises(CrawlBlocked):
        validate_url(url)


def test_mixed_answers_never_reach_transport():
    c, transport = crawler(resolver=lambda host, timeout: (PUBLIC, "10.0.0.1"))
    assert c.crawl("https://example.com/").reason == "IP_NOT_PUBLIC"
    assert transport.calls == []


def test_redirect_metadata_is_blocked_before_any_unsafe_request():
    c, transport = crawler(
        {"https://example.com/": response(status=302, location="http://169.254.169.254/latest/meta-data/")}
    )
    assert c.crawl("https://example.com/").reason == "IP_NOT_PUBLIC"
    assert len(transport.calls) == 2
    assert all("169.254" not in call[0] for call in transport.calls)


def test_each_redirect_resolves_again_and_blocks_rebinding():
    answers = iter([(PUBLIC,), (PUBLIC,), ("127.0.0.1",)])
    c, transport = crawler(
        {"https://example.com/": response(status=302, location="/contact")},
        resolver=lambda host, timeout: next(answers),
    )
    assert c.crawl("https://example.com/").reason == "IP_NOT_PUBLIC"
    assert len(transport.calls) == 2


def test_peer_change_rejected_at_transport_boundary():
    c, _transport = crawler(
        {"https://example.com/": Response(200, {"content-type": "text/html"}, b"Example", "8.8.8.8")}
    )
    assert c.crawl("https://example.com/").reason == "PEER_MISMATCH"


def test_robots_wildcards_disallow_and_cache():
    c, transport = crawler(
        {"https://example.com/robots.txt": response(b"User-agent: *\nDisallow: /*?private=*\n")}
    )
    assert c.crawl("https://example.com/?private=yes").reason == "ROBOTS_DENIED"
    assert c.crawl("https://example.com/?private=again").reason == "ROBOTS_DENIED"
    assert len(transport.calls) == 1


def test_failed_robots_cached_and_site_429_stops():
    c, transport = crawler({"https://example.com/robots.txt": response(status=429)})
    assert c.crawl("https://example.com/").reason == "SITE_BLOCKED"
    assert c.crawl("https://example.com/").reason == "ROBOTS_DENIED"
    assert len(transport.calls) == 1


def test_six_page_limit_no_assets_and_domain_throttle():
    links = "".join(f"<a href='/contact{i}'>Contact {i}</a>" for i in range(10))
    routes = {
        "https://example.com/": response((links + "<img src='https://cdn.example.net/a.png'>").encode())
    }
    routes.update({f"https://example.com/contact{i}": response() for i in range(10)})
    c, transport = crawler(routes)
    result = c.crawl("https://example.com/")
    assert len(result.pages) == 6 and result.requests == 7 and result.reason == "PAGE_BUDGET"
    assert all(b[2] - a[2] >= 1 for a, b in zip(transport.calls, transport.calls[1:]))
    assert all("cdn" not in call[0] for call in transport.calls)
    assert result.terms_assessment == "unknown"


def test_redirect_and_response_budgets():
    routes = {f"https://example.com/{i}": response(status=302, location=f"/{i + 1}") for i in range(5)}
    c, transport = crawler(routes)
    assert c.crawl("https://example.com/0").reason == "REDIRECT_BUDGET"
    assert len(transport.calls) == 5
    c, _ = crawler({"https://example.com/": response(b"x" * (MAX_BYTES + 1))})
    assert c.crawl("https://example.com/").reason == "RESPONSE_TOO_LARGE"


def test_static_only_terms_and_stricter_robots_delay():
    c, _ = crawler({"https://example.com/": response(b"<script>document.write('content')</script>")})
    assert c.crawl("https://example.com/").reason == "STATIC_CONTENT_UNAVAILABLE"
    c, _ = crawler()
    result = c.crawl("https://example.com/", terms_permit=lambda page: False)
    assert result.reason == "TERMS_RESTRICTED" and result.terms_assessment == "restricted"
    c, transport = crawler(
        {
            "https://example.com/": response(),
            "https://example.com/robots.txt": response(b"User-agent: *\nCrawl-delay: 3\n"),
        }
    )
    assert len(c.crawl("https://example.com/").pages) == 1
    assert transport.calls[1][2] - transport.calls[0][2] == 3


class FakeSocket:
    def __init__(self, peer=PUBLIC):
        self.peer, self.target, self.written = peer, None, b""

    def settimeout(self, timeout):
        pass

    def connect(self, target):
        self.target = target

    def getpeername(self):
        return self.peer, 443

    def sendall(self, data):
        self.written += data

    def do_handshake(self):
        pass

    def makefile(self, mode):
        return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\nContent-Type: text/html\r\n\r\nExample")

    def close(self):
        pass

    def shutdown(self, how):
        pass


class TLSBoundary:
    check_hostname = True
    verify_mode = ssl.CERT_REQUIRED

    def __init__(self, fail=False):
        self.fail, self.hostname = fail, None

    def wrap_socket(self, sock, server_hostname, do_handshake_on_connect=False):
        self.hostname = server_hostname
        if self.fail:
            raise ssl.SSLCertVerificationError("fixture certificate mismatch")
        return sock


def test_real_transport_connects_pinned_numeric_ip_with_original_host_sni(monkeypatch):
    import abr_engine.enrich.crawl as module

    sock, context = FakeSocket(), TLSBoundary()
    monkeypatch.setattr(module.socket, "socket", lambda *args: sock)
    monkeypatch.setattr(
        module.socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("second DNS lookup")
    )
    result = PinnedTransport(ssl_context=context).request(
        "https://example.com/contact", PUBLIC, deadline=module.time.monotonic() + 20, max_bytes=MAX_BYTES
    )
    assert sock.target == (PUBLIC, 443)
    assert context.hostname == "example.com"
    assert b"Host: example.com\r\n" in sock.written
    assert result.body == b"Example"


def test_real_transport_rejects_certificate_mismatch_before_http(monkeypatch):
    import abr_engine.enrich.crawl as module

    sock = FakeSocket()
    monkeypatch.setattr(module.socket, "socket", lambda *args: sock)
    with pytest.raises(CrawlBlocked, match="TRANSPORT_FAILED"):
        PinnedTransport(ssl_context=TLSBoundary(fail=True)).request(
            "https://example.com/", PUBLIC, deadline=module.time.monotonic() + 20, max_bytes=MAX_BYTES
        )
    assert sock.written == b""


def test_real_transport_rejects_changed_peer_before_tls_http(monkeypatch):
    import abr_engine.enrich.crawl as module

    sock, context = FakeSocket("8.8.8.8"), TLSBoundary()
    monkeypatch.setattr(module.socket, "socket", lambda *args: sock)
    with pytest.raises(CrawlBlocked, match="PEER_MISMATCH"):
        PinnedTransport(ssl_context=context).request(
            "https://example.com/", PUBLIC, deadline=module.time.monotonic() + 20, max_bytes=MAX_BYTES
        )
    assert context.hostname is None and sock.written == b""


def test_transport_cannot_disable_certificate_validation():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(CrawlBlocked, match="TLS_VERIFICATION_REQUIRED"):
        PinnedTransport(ssl_context=context)


def test_total_twenty_request_budget_includes_robots_and_redirects():
    routes = {}
    for page in range(6):
        for hop in range(3):
            routes[f"https://example.com/contact{page}-{hop}"] = response(
                status=302, location=f"/contact{page}-{hop + 1}"
            )
        routes[f"https://example.com/contact{page}-3"] = response(
            f"<a href='/contact{page + 1}-0'>Contact</a>".encode()
        )
    c, transport = crawler(routes)
    result = c.crawl("https://example.com/contact0-0")
    assert result.reason == "REQUEST_BUDGET"
    assert len(transport.calls) == 20 and result.requests == 20


def test_deadline_includes_resolution_and_never_connects_after_expiry():
    c, transport = crawler()

    def slow_resolver(host, timeout):
        c.clock.sleep(20)
        return (PUBLIC,)

    c.resolver = slow_resolver
    assert c.crawl("https://example.com/").reason == "REQUEST_DEADLINE"
    assert transport.calls == []


def test_real_transport_rejects_truncated_body(monkeypatch):
    import abr_engine.enrich.crawl as module

    sock = FakeSocket()
    sock.makefile = lambda mode: io.BytesIO(
        b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\nContent-Type: text/html\r\n\r\nshort"
    )
    monkeypatch.setattr(module.socket, "socket", lambda *args: sock)
    with pytest.raises(CrawlBlocked, match="LENGTH_MISMATCH"):
        PinnedTransport(ssl_context=TLSBoundary()).request(
            "https://example.com/", PUBLIC, deadline=module.time.monotonic() + 20, max_bytes=MAX_BYTES
        )
