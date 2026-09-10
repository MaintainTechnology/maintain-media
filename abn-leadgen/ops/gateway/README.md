# Private Vercel gateway preparation

This is a working, separately authenticated receiver for the website's remote
**synthetic dashboard** transport. It does not connect real QBCC/ABR data, change
release gates, enable pilot/production startup or supply an Australian server.
No gateway has been deployed by these instructions.

The website already checks Clerk admin access before forwarding requests. The
gateway checks a separate service token and forwards only the small dashboard
API allowlist to the existing fixture application, inside the same process.
Browser cookies, bearer credentials and asserted editor identities do not pass
through to that application. Real `/v1` reviewer/owner permissions and signed
actual-editor mapping remain a separate live integration requirement.

## Configuration on a provisioned host

Use an isolated fixture database and the existing locked Python 3.12 environment.
Supply these through the host's private process environment and Vercel's private
server environment; never put the token in a `NEXT_PUBLIC_` variable, URL, command
argument, repository, Sheet cell or browser:

- `ABN_ENGINE_ORIGIN`: the exact lowercase public HTTPS origin of the TLS gateway,
  without an API path, query or fragment. Only standard HTTPS port 443 is accepted.
- `ABN_ENGINE_TOKEN`: the same randomly generated service token at both ends. Use
  at least 32 random bytes encoded as base64url (43 characters) or hex (64
  characters); the accepted alphabet is letters, digits, `_` and `-`, up to 256
  characters. Rotate both copies together. Example or repeated-character test
  tokens are not deployment secrets.
- On Vercel only, set `ABN_ENGINE_TRANSPORT=remote`.

The command below reads process environment variables; it does not load `.env`
files. Do not run it on an inferred or unapproved host.

```bash
uv run --frozen python -m abr_engine.dashboard.gateway --config config/fixture.yaml --port 8768
```

The gateway binds **127.0.0.1 only**. Keep both 8767 and 8768 private. A separately
installed TLS reverse proxy on the same host terminates HTTPS on 443 and forwards
to 8768 while preserving the exact external `Host` header and mutation `Origin`.
Proxy access/error logs must omit Authorization, cookies, request bodies and
business data. Do not enable Uvicorn forwarded-header trust: the gateway verifies
the actual connection came from a local proxy and ignores forwarded identity.
The public certificate, proxy configuration, firewall and token custody need
their own host acceptance checks before exposing the authenticated gateway.

All routes, including health, require `Authorization: Bearer <service token>`.
Reads accept `/api/dashboard`, `/api/dashboard/health`, UUID job paths and UUID
report paths with `html`, `csv` or `markdown` suffixes. Mutations accept only
`PATCH /api/settings` and `POST /api/runs`. They require the exact gateway origin
and a current `X-Dashboard-CSRF` value obtained from the authenticated dashboard
response. Query strings, unknown routes, public HTML, assets, live control
endpoints, mismatched hosts/origins, duplicate headers and direct remote socket
connections are rejected. The existing JSON/body/model limits remain in force.

One gateway process holds the current CSRF token and serialized run coordinator.
Use one worker and avoid independent parallel copies against the same fixture
storage. A restart changes the CSRF token; the website obtains a fresh token for
each mutation and safely surfaces a failed request if a restart races that read.

## Verification

```bash
uv run --frozen pytest tests/unit/test_dashboard_gateway.py -q
```

These tests exercise the real inner HTTP boundary with a synthetic dashboard
service and no database or external network. They check authentication before
route disclosure, direct-access rejection, host/origin/CSRF, request limits,
credential isolation, route restrictions and fixture-only loopback startup.
They do not prove a public TLS endpoint, live data, a connected Vercel deployment,
staff permissions, Google Sheets, GoHighLevel, backups or measured pilot results.
