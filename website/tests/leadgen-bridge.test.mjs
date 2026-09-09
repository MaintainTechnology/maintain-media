import test from "node:test";
import assert from "node:assert/strict";
import { engineOrigin, forwardLeadGen, parseBridgePath, readJsonBody, bridgeFailure } from "../src/lib/abn-lead-gen/bridge.ts";

const admin = { username: "test-admin", displayName: "Test admin", csrfToken: "web-token" };
const id = "12345678-1234-1234-1234-123456789abc";
const json = (value, status = 200) => Response.json(value, { status });

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

test("engine origin cannot be a remote host, credential URL or arbitrary path", () => {
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
    return calls.length === 1 ? json({ csrf_token: "engine-only" }) : json({ state: "queued" }, 202);
  });
  assert.equal(result.status, 202);
  assert.equal(calls[1].init.headers["X-Dashboard-CSRF"], "engine-only");
  assert.equal(calls[1].init.headers.Origin, engineOrigin());
  assert.equal(calls[1].init.headers.Cookie, undefined);
  assert.equal(calls[1].init.headers.Authorization, undefined);
  assert.equal(calls[1].init.redirect, "error");
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
