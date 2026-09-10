import test, { beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { createServer } from "node:http";
import { once } from "node:events";
import { engineOrigin, forwardLeadGen, parseBridgePath, readJsonBody, bridgeFailure } from "../src/lib/abn-lead-gen/bridge.ts";

const admin = { username: "test-admin", displayName: "Test admin", csrfToken: "web-token" };
const id = "12345678-1234-1234-1234-123456789abc";
const json = (value, status = 200) => Response.json(value, { status });
const remoteOrigin = "https://engine.maintainmedia.com.au";
const serviceToken = randomBytes(32).toString("base64url");
const environmentKeys = ["ABN_ENGINE_TRANSPORT", "ABN_ENGINE_ORIGIN", "ABN_ENGINE_TOKEN", "VERCEL", "VERCEL_ENV"];
let originalEnvironment;

beforeEach(() => {
  originalEnvironment = new Map(environmentKeys.map(key => [key, process.env[key]]));
  for (const key of environmentKeys) delete process.env[key];
});
afterEach(() => {
  for (const [key, value] of originalEnvironment) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

function remoteEnvironment() {
  process.env.ABN_ENGINE_TRANSPORT = "remote";
  process.env.ABN_ENGINE_ORIGIN = remoteOrigin;
  process.env.ABN_ENGINE_TOKEN = serviceToken;
}

test("only explicit endpoints and methods can reach the engine", () => {
  assert.equal(parseBridgePath(["dashboard"], "GET"), "/api/dashboard");
  assert.equal(parseBridgePath(["runs"], "POST"), "/api/runs");
  assert.equal(parseBridgePath(["settings"], "PATCH"), "/api/settings");
  assert.equal(parseBridgePath(["reports", id, "csv"], "GET"), `/api/reports/${id}/csv`);
  for (const parts of [["..", "settings"], ["reports", id, "manifest"], ["reports", "not-a-uuid", "html"], ["http://evil.test"], ["assets", "settings.json"]]) {
    assert.throws(() => parseBridgePath(parts, "GET"), { code: "ROUTE_NOT_FOUND" });
  }
  assert.throws(() => parseBridgePath(["settings"], "GET"));
  assert.throws(() => parseBridgePath(["dashboard"], "POST"));
});

test("local transport cannot use a remote host, credential URL or arbitrary path", () => {
  const original = process.env.ABN_ENGINE_ORIGIN;
  try {
    for (const value of ["https://evil.test", "http://127.0.0.1.evil.test", "http://admin:pass@localhost:8767", "http://localhost:8767/private", "http://localhost:8767/?x=y", "http://localhost:0"]) {
      process.env.ABN_ENGINE_ORIGIN = value;
      assert.throws(engineOrigin, { code: "ENGINE_CONFIGURATION_INVALID" });
    }
    process.env.ABN_ENGINE_ORIGIN = "http://127.0.0.1:8767";
    assert.equal(engineOrigin(), "http://127.0.0.1:8767");
  } finally {
    if (original === undefined) delete process.env.ABN_ENGINE_ORIGIN;
    else process.env.ABN_ENGINE_ORIGIN = original;
  }
});

test("hosted deployments require explicit remote transport and complete credentials before network I/O", async () => {
  const request = new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/dashboard");
  let calls = 0;
  for (const hosted of [{ VERCEL: "1" }, { VERCEL_ENV: "production" }, { VERCEL_ENV: "preview" }]) {
    for (const key of ["VERCEL", "VERCEL_ENV"]) delete process.env[key];
    Object.assign(process.env, hosted);
    await assert.rejects(() => forwardLeadGen(request, ["dashboard"], admin, async () => { calls += 1; return json({}); }), { code: "ENGINE_CONFIGURATION_INVALID" });
  }
  for (const values of [
    { ABN_ENGINE_TRANSPORT: "remote" },
    { ABN_ENGINE_TRANSPORT: "remote", ABN_ENGINE_ORIGIN: remoteOrigin },
    { ABN_ENGINE_TRANSPORT: "unrecognized", ABN_ENGINE_ORIGIN: remoteOrigin, ABN_ENGINE_TOKEN: serviceToken },
  ]) {
    for (const key of ["ABN_ENGINE_TRANSPORT", "ABN_ENGINE_ORIGIN", "ABN_ENGINE_TOKEN"]) delete process.env[key];
    Object.assign(process.env, values);
    await assert.rejects(() => forwardLeadGen(request, ["dashboard"], admin, async () => { calls += 1; return json({}); }), { code: "ENGINE_CONFIGURATION_INVALID" });
  }
  assert.equal(calls, 0);
  remoteEnvironment();
  assert.equal(engineOrigin(), remoteOrigin);
});

test("remote origin requires a public HTTPS DNS origin and a separate strong service token", () => {
  remoteEnvironment();
  for (const value of [
    "http://engine.maintainmedia.com.au", "https://127.0.0.1", "https://10.0.0.5", "https://169.254.169.254",
    "https://[::1]", "https://[fd00::1]", "https://localhost", "https://engine.local", "https://engine.internal",
    "https://engine.test", "https://engine.home.arpa", "https://engine", "https://engine.123", "https://bad_name.com.au",
    "https://engine.maintainmedia.com.au:8443", "https://user:pass@engine.maintainmedia.com.au",
    `${remoteOrigin}/private`, `${remoteOrigin}/./`, `${remoteOrigin}/?key=value`, `${remoteOrigin}#fragment`,
    ` ${remoteOrigin}`, `${remoteOrigin}\n`, `${remoteOrigin}\\private`, `${remoteOrigin}.`, "",
  ]) {
    process.env.ABN_ENGINE_ORIGIN = value;
    assert.throws(engineOrigin, { code: "ENGINE_CONFIGURATION_INVALID" });
  }
  process.env.ABN_ENGINE_ORIGIN = remoteOrigin;
  for (const token of [undefined, "", "x".repeat(42), "x".repeat(257), ` ${serviceToken}`, `${serviceToken}\n`, `${serviceToken.slice(0,20)}\0broken`, `Bearer ${serviceToken}`]) {
    if (token === undefined) delete process.env.ABN_ENGINE_TOKEN;
    else process.env.ABN_ENGINE_TOKEN = token;
    assert.throws(engineOrigin, { code: "ENGINE_CONFIGURATION_INVALID" });
  }
  process.env.ABN_ENGINE_TOKEN = serviceToken;
  for (const origin of [remoteOrigin, `${remoteOrigin}/`, `${remoteOrigin}:443/`]) {
    process.env.ABN_ENGINE_ORIGIN = origin;
    assert.equal(engineOrigin(), remoteOrigin);
  }
});

test("mutation bodies must be bounded JSON objects", async () => {
  const request = (body, contentType = "application/json") => new Request("http://localhost/api", { method: "POST", headers: { "Content-Type": contentType }, body });
  for (const body of ["[]", "null", "broken"]) await assert.rejects(() => readJsonBody(request(body)), { code: "INVALID_INPUT" });
  await assert.rejects(() => readJsonBody(request("{}", "text/plain")), { code: "JSON_REQUIRED" });
  await assert.rejects(() => readJsonBody(request(JSON.stringify({ value: "a".repeat(4200) }))), { code: "BODY_TOO_LARGE" });
});

test("dashboard hides upstream CSRF and rewrites only allowed report URLs", async () => {
  const response = await forwardLeadGen(new Request("http://localhost/api/abn-lead-gen/dashboard"), ["dashboard"], admin, async () => json({ mode: "fixture", outreach: "disabled", csrf_token: "engine-secret", runs: [{ reports: { html: `/api/reports/${id}/html`, csv: "https://evil.test/private", markdown: "../../private" } }] }));
  const data = await response.json();
  assert.equal(data.csrf_token, undefined);
  assert.equal(data.admin.csrfToken, "web-token");
  assert.equal(data.runs[0].reports.html, `/api/abn-lead-gen/reports/${id}/html`);
  assert.equal(data.runs[0].reports.csv, null);
  assert.equal(data.runs[0].reports.markdown, null);
  assert.match(response.headers.get("Cache-Control"), /no-store/);
});

test("writes use a fresh server-side token and never forward browser credentials", async () => {
  const calls = [];
  const request = new Request("http://localhost/api/abn-lead-gen/runs", { method: "POST", headers: { "Content-Type": "application/json", Cookie: "secret=cookie", Authorization: "secret", Origin: "http://localhost", "X-Admin-CSRF": "web-token" }, body: JSON.stringify({ request_id: id, source: "all" }) });
  const result = await forwardLeadGen(request, ["runs"], admin, async (url, init) => {
    calls.push({ url, init });
    return calls.length === 1 ? json({ mode: "fixture", outreach: "disabled", csrf_token: "engine-only" }) : json({ state: "queued" }, 202);
  });
  assert.equal(result.status, 202);
  assert.equal(calls[1].init.headers.get("X-Dashboard-CSRF"), "engine-only");
  assert.equal(calls[1].init.headers.get("Origin"), engineOrigin());
  assert.equal(calls[1].init.headers.get("Cookie"), null);
  assert.equal(calls[1].init.headers.get("Authorization"), null);
  assert.equal(calls[1].init.redirect, "error");
});

test("remote calls authenticate both CSRF preflight and mutation without forwarding browser credentials", async () => {
  remoteEnvironment();
  const calls = [];
  const request = new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/runs", { method: "POST", headers: {
    "Content-Type": "application/json", Cookie: "browser-cookie", Authorization: "Bearer browser-token",
    Origin: "https://www.maintainmedia.com.au", "X-Admin-CSRF": "web-token",
  }, body: JSON.stringify({ request_id: id, source: "all" }) });
  const response = await forwardLeadGen(request, ["runs"], admin, async (url, init) => {
    calls.push({ url, init });
    return calls.length === 1 ? json({ mode: "fixture", outreach: "disabled", csrf_token: "engine-only" }) : json({ state: "queued" }, 202);
  });
  assert.equal(response.status, 202);
  assert.deepEqual(calls.map(call => call.url), [`${remoteOrigin}/api/dashboard`, `${remoteOrigin}/api/runs`]);
  for (const { init } of calls) {
    assert.equal(init.headers.get("Authorization"), `Bearer ${serviceToken}`);
    for (const name of ["Cookie", "Host", "X-Admin-CSRF"]) assert.equal(init.headers.get(name), null);
    assert.equal(init.cache, "no-store");
    assert.equal(init.redirect, "error");
    assert.ok(init.signal instanceof AbortSignal);
  }
  assert.equal(calls[0].init.headers.get("Origin"), null);
  assert.equal(calls[1].init.headers.get("Origin"), remoteOrigin);
  assert.equal(calls[1].init.headers.get("X-Dashboard-CSRF"), "engine-only");
  assert.equal((await response.text()).includes(serviceToken), false);
});

test("remote transport retains fixture-only dashboard and mutation checks", async () => {
  remoteEnvironment();
  for (const payload of [{ mode: "live", outreach: "disabled" }, { mode: "fixture", outreach: "enabled" }]) {
    for (const method of ["GET", "POST"]) {
      let calls = 0;
      const request = new Request("https://www.maintainmedia.com.au/api", method === "GET" ? {} : {
        method, headers: { "Content-Type": "application/json" }, body: "{}",
      });
      await assert.rejects(() => forwardLeadGen(request, method === "GET" ? ["dashboard"] : ["runs"], admin, async () => {
        calls += 1;
        return json({ ...payload, csrf_token: "engine-only", runs: [] });
      }), { code: "ENGINE_INVALID_RESPONSE" });
      assert.equal(calls, 1);
    }
  }
});

test("remote authentication failures and reflected credentials cannot leak through errors or reports", async () => {
  remoteEnvironment();
  for (const upstream of [
    () => json({ code: "UNAUTHORIZED", message: `private ${serviceToken}` }, 401),
    () => json({ mode: "fixture", outreach: "disabled", runs: [], diagnostic: serviceToken }),
    () => new Response(JSON.stringify({ mode: "fixture", outreach: "disabled", runs: [], diagnostic: serviceToken })
      .replace(serviceToken, [...serviceToken].map(character => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`).join("")),
      { headers: { "Content-Type": "application/json" } }),
    () => { throw new Error(`TLS failure at ${remoteOrigin} with ${serviceToken}`); },
  ]) {
    let failure;
    try { await forwardLeadGen(new Request("https://www.maintainmedia.com.au/api"), ["dashboard"], admin, async () => upstream()); }
    catch (error) { failure = error; }
    assert.ok(failure);
    const publicError = await bridgeFailure(failure).text();
    assert.equal(publicError.includes(serviceToken), false);
    assert.equal(publicError.includes(remoteOrigin), false);
  }
  await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api"), ["reports", id, "csv"], admin,
    async () => new Response(`diagnostic\n${serviceToken}`, { headers: { "Content-Type": "text/csv" } })), { code: "ENGINE_INVALID_RESPONSE" });
});

test("service authentication failures do not expire Clerk sessions or hide business permission failures", async () => {
  remoteEnvironment();
  for (const [code, status] of [["GATEWAY_UNAUTHENTICATED", 401], ["GATEWAY_HOST_INVALID", 403],
    ["GATEWAY_PROXY_REQUIRED", 403], ["SAME_ORIGIN_REQUIRED", 403], ["DASHBOARD_CSRF_REQUIRED", 403]]) {
    await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api"), ["dashboard"], admin,
      async () => json({ code }, status)), { code: "ENGINE_AUTHENTICATION_FAILED", status: 503 });
  }
  await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api"), ["reports", id, "csv"], admin,
    async () => json({ code: "REPORT_ACCESS_DENIED" }, 403)), { code: "REPORT_ACCESS_DENIED", status: 403 });
});

test("an upstream redirect fails without sending the credential to a redirect target", async () => {
  remoteEnvironment();
  const paths = [];
  const server = createServer((request, response) => {
    paths.push(request.url);
    response.writeHead(302, { Location: "/credential-leak" });
    response.end();
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const fixtureUrl = `http://127.0.0.1:${server.address().port}/redirect`;
  try {
    await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api"), ["dashboard"], admin,
      async (_url, init) => fetch(fixtureUrl, init)), { code: "ENGINE_UNAVAILABLE" });
    assert.deepEqual(paths, ["/redirect"]);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});

test("report formats preserve downloads, masked text and protected nested links", async () => {
  for (const kind of ["html", "csv", "markdown"]) {
    const media = kind === "html" ? "text/html" : kind === "csv" ? "text/csv" : "text/markdown";
    const body = kind === "html" ? `<a href="/api/reports/${id}/csv">CSV</a> Masked — contact hidden in dashboard`
      : kind === "markdown" ? `[CSV](/api/reports/${id}/csv) Masked — contact hidden in dashboard` : "business_name,safe_contact_view\r\nSample,Masked — contact hidden in dashboard\r\n";
    const response = await forwardLeadGen(new Request("http://localhost/api"), ["reports", id, kind], admin, async () => new Response(body, { headers: { "Content-Type": media } }));
    const text = await response.text();
    assert.match(text, /contact hidden in dashboard/);
    if (kind !== "csv") assert.ok(text.includes(`/api/abn-lead-gen/reports/${id}/csv`));
    if (kind !== "html") assert.match(response.headers.get("Content-Disposition"), /attachment/);
    else assert.match(response.headers.get("Content-Security-Policy"), /default-src 'none'/);
  }
});

test("stale reports, malformed upstream and outages fail without sensitive errors", async () => {
  await assert.rejects(() => forwardLeadGen(new Request("http://localhost/api"), ["reports", id, "csv"], admin, async () => json({ code: "REPORT_STALE_RUN_AGAIN", message: "private/path" }, 409)), { code: "REPORT_STALE_RUN_AGAIN", status: 409 });
  await assert.rejects(() => forwardLeadGen(new Request("http://localhost/api"), ["dashboard"], admin, async () => new Response("private html")), { code: "ENGINE_INVALID_RESPONSE" });
  await assert.rejects(() => forwardLeadGen(new Request("http://localhost/api"), ["dashboard"], admin, async () => { throw new Error("private/path/password"); }), { code: "ENGINE_UNAVAILABLE" });
  const response = bridgeFailure(new Error("private/path/password"));
  assert.deepEqual(await response.json(), { code: "ENGINE_UNAVAILABLE" });
});

test("uppercase UUID requests retain the report's canonical protected CSV link", async () => {
  for (const kind of ["html", "markdown"]) {
    const payload = kind === "html" ? `<a href="/api/reports/${id}/csv">CSV</a>` : `[CSV](/api/reports/${id}/csv)`;
    const response = await forwardLeadGen(new Request("http://localhost/api"), ["reports", id.toUpperCase(), kind], admin, async () => new Response(payload, { headers: { "Content-Type": kind === "html" ? "text/html" : "text/markdown" } }));
    assert.ok((await response.text()).includes(`/api/abn-lead-gen/reports/${id}/csv`));
  }
});
