import test, { beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes, randomUUID } from "node:crypto";
import { bridgeFailure, forwardLeadGen, parseBridgePath } from "../src/lib/abn-lead-gen/bridge.ts";

const key = randomBytes(32).toString("base64url");
const admin = { username: "alias-may-change", displayName: "Staff", csrfToken: "local", actorId: "user_Staff123", scopes: ["admin", "operator"] };
const variables = ["ABN_ENGINE_MODE", "ABN_ENGINE_TRANSPORT", "ABN_ENGINE_ORIGIN", "ABN_ENGINE_TOKEN", "ABN_ENGINE_ASSERTION_KEY"];
let previous;
beforeEach(() => {
  previous = variables.map(name => [name, process.env[name]]);
  Object.assign(process.env, { ABN_ENGINE_MODE: "pilot", ABN_ENGINE_TRANSPORT: "remote", ABN_ENGINE_ORIGIN: "https://engine.maintainmedia.com.au", ABN_ENGINE_ASSERTION_KEY: key });
});
afterEach(() => { for (const [name, value] of previous) value === undefined ? delete process.env[name] : process.env[name] = value; });
const decode = token => JSON.parse(Buffer.from(token.split(".")[1], "base64url"));

test("live requests bind exact staff identity, path, method, bytes and idempotency", async () => {
  const id = randomUUID(); const body = JSON.stringify({ lead_id: randomUUID(), reason: "unsubscribe" });
  let count = 0;
  const response = await forwardLeadGen(new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/suppressions", {
    method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": id, Cookie: "private-cookie", Authorization: "Bearer browser" }, body,
  }), ["suppressions"], admin, async (url, init) => {
    count++;
    assert.equal(url, "https://engine.maintainmedia.com.au/v1/suppressions");
    const headers = new Headers(init.headers); const token = headers.get("authorization").slice(7);
    const claims = decode(token);
    assert.equal(claims.sub, admin.actorId); assert.deepEqual(claims.scopes, admin.scopes);
    assert.equal(claims.method, "POST"); assert.equal(claims.path, "/v1/suppressions");
    assert.equal(claims.body_sha256, createHash("sha256").update(body).digest("hex"));
    assert.equal(claims.idempotency_key, id); assert.equal(claims.request_id, headers.get("x-request-id"));
    assert.equal(claims.exp - claims.iat, 60);
    assert.equal(token.split(".")[2], createHmac("sha256", key).update(token.split(".").slice(0, 2).join(".")).digest("base64url"));
    assert.equal(headers.get("cookie"), null); assert.equal(headers.get("origin"), null);
    assert.notEqual(token, key);
    return Response.json({ committed_at: new Date().toISOString() });
  });
  assert.equal(count, 1); assert.equal(response.status, 200);
});

test("live reads never accept fixture data or expose full server authority", async () => {
  const req = new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/dashboard");
  await assert.rejects(() => forwardLeadGen(req, ["dashboard"], admin, async () => Response.json({ mode: "fixture", outreach: "disabled", runs: [] })), { code: "ENGINE_INVALID_RESPONSE" });
  const response = await forwardLeadGen(req, ["dashboard"], admin, async () => Response.json({ mode: "pilot", outreach: "disabled", runs: [] }));
  assert.deepEqual((await response.json()).admin, { username: admin.username, displayName: admin.displayName, csrfToken: admin.csrfToken });
});

test("missing live keys, actor identity or mutation idempotency stop before network", async () => {
  let calls = 0; const fetcher = async () => { calls++; return Response.json({}); };
  const req = new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: "{}" });
  await assert.rejects(() => forwardLeadGen(req, ["settings"], admin, fetcher), { code: "REQUEST_IDENTIFIERS_REQUIRED" });
  await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/dashboard"), ["dashboard"], { ...admin, actorId: undefined }, fetcher));
  delete process.env.ABN_ENGINE_ASSERTION_KEY; process.env.ABN_ENGINE_TOKEN = key;
  await assert.rejects(() => forwardLeadGen(req, ["settings"], admin, fetcher), { code: "ENGINE_CONFIGURATION_INVALID" });
  assert.equal(calls, 0);
});

test("reflected signed assertions are rejected and cannot escape in responses", async () => {
  await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/dashboard"), ["dashboard"], admin,
    async (url, init) => Response.json({ code: "OOPS", echo: new Headers(init.headers).get("authorization") }), 500), { code: "ENGINE_INVALID_RESPONSE" });
});

test("review routes are explicit and unavailable to the fixture bridge", () => {
  assert.equal(parseBridgePath(["qbcc-reviews", "100"], "GET", true), "/api/qbcc-reviews/100");
  assert.equal(parseBridgePath(["worklist-rows", randomUUID()], "PATCH", true).startsWith("/v1/"), true);
  for (const parts of [["qbcc-reviews", "-1"], ["qbcc-reviews", "../"], ["action-intents"], ["deletions"]]) assert.throws(() => parseBridgePath(parts, "POST", true));
  assert.throws(() => parseBridgePath(["suppressions"], "POST"));
});

test("source browsing permits only live read routes with bounded signed pagination", () => {
  for (const source of ["abr", "qbcc"]) {
    for (const run of ["latest", randomUUID()]) {
      for (const offset of ["0", "50", "99999999", "100000000"]) {
        const parts = ["source-records", source, run, offset];
        assert.equal(parseBridgePath(parts, "GET", true), `/api/${parts.join("/")}`);
        for (const method of ["HEAD", "POST", "PATCH", "DELETE"]) assert.throws(() => parseBridgePath(parts, method, true), { code: "ROUTE_NOT_FOUND" });
        assert.throws(() => parseBridgePath(parts, "GET", false), { code: "ROUTE_NOT_FOUND" });
      }
    }
  }
  for (const parts of [
    ["source-records", "other", "latest", "0"],
    ["source-records", "ABR", "latest", "0"],
    ["source-records", "abr", "all", "0"],
    ["source-records", "abr", "../../dashboard", "0"],
    ["source-records", "abr", "latest"],
    ...["-1", "01", "1.5", "1e2", "100000001", "1000000000", "%30"].map(offset => ["source-records", "abr", "latest", offset]),
  ]) assert.throws(() => parseBridgePath(parts, "GET", true), { code: "ROUTE_NOT_FOUND" });
});

test("source pages retain staff scopes, private caching and exact request binding", async () => {
  const actor = { ...admin, scopes: ["admin", "reviewer"] };
  for (const [source, run, offset] of [["abr", "latest", "0"], ["qbcc", randomUUID(), "50"]]) {
    const path = `/api/source-records/${source}/${run}/${offset}`;
    const payload = { source, run_id: run === "latest" ? randomUUID() : run, source_state: "available",
      total: 102, offset: Number(offset), limit: 50, next_offset: Number(offset) + 50,
      records: [{ entity_name: "Example source record" }] };
    const response = await forwardLeadGen(new Request(`https://www.maintainmedia.com.au/api/abn-lead-gen/source-records/${source}/${run}/${offset}`, {
      headers: { Cookie: "browser-cookie", Authorization: "Bearer browser", "Idempotency-Key": randomUUID() },
    }), ["source-records", source, run, offset], actor, async (url, init) => {
      assert.equal(url, `https://engine.maintainmedia.com.au${path}`);
      assert.equal(init.method, "GET"); assert.equal(init.body, undefined);
      assert.equal(init.cache, "no-store"); assert.equal(init.redirect, "error");
      const headers = new Headers(init.headers);
      const claims = decode(headers.get("authorization").slice(7));
      assert.equal(claims.path, path); assert.equal(claims.method, "GET");
      assert.equal(claims.sub, actor.actorId); assert.deepEqual(claims.scopes, actor.scopes);
      assert.equal(claims.body_sha256, createHash("sha256").update("").digest("hex"));
      assert.equal(claims.idempotency_key, ""); assert.equal(headers.get("idempotency-key"), null);
      assert.equal(headers.get("cookie"), null); assert.equal(headers.get("origin"), null);
      return Response.json(payload);
    });
    assert.deepEqual(await response.json(), payload);
    assert.equal(response.headers.get("cache-control"), "private, no-store, max-age=0");
    assert.equal(response.headers.get("x-robots-tag"), "noindex, nofollow, noarchive");
  }
});

test("source browse query parameters are refused before a network call", async () => {
  let calls = 0;
  for (const query of ["?offset=50", "?limit=100", "?run_id=" + randomUUID(), "?unused=1"]) {
    await assert.rejects(() => forwardLeadGen(new Request(`https://www.maintainmedia.com.au/api/abn-lead-gen/source-records/abr/latest/0${query}`),
      ["source-records", "abr", "latest", "0"], admin, async () => { calls++; return Response.json({}); }), { code: "INVALID_INPUT", status: 422 });
  }
  assert.equal(calls, 0);
});

test("source browsing preserves engine permission failures without caching or exposing details", async () => {
  let failure;
  try {
    await forwardLeadGen(new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/source-records/abr/latest/0"),
      ["source-records", "abr", "latest", "0"], admin,
      async () => Response.json({ code: "FORBIDDEN", detail: "private upstream detail" }, { status: 403 }));
  } catch (error) { failure = error; }
  assert.equal(failure?.code, "FORBIDDEN");
  const response = bridgeFailure(failure);
  assert.equal(response.status, 403);
  assert.equal(response.headers.get("cache-control"), "private, no-store, max-age=0");
  assert.deepEqual(await response.json(), { code: "FORBIDDEN" });
});

test("source query and export-ticket POSTs are explicit live routes, while direct CSV bypasses the bridge", () => {
  for (const parts of [["source-records", "query"], ["source-exports"]]) {
    assert.equal(parseBridgePath(parts, "POST", true), `/api/${parts.join("/")}`);
    assert.throws(() => parseBridgePath(parts, "POST", false), { code: "ROUTE_NOT_FOUND" });
    assert.throws(() => parseBridgePath(parts, "GET", true), { code: "ROUTE_NOT_FOUND" });
  }
  assert.throws(() => parseBridgePath(["source-exports", "download"], "POST", true), { code: "ROUTE_NOT_FOUND" });
});

test("filtered source queries bind their exact request body and preserve the read response", async () => {
  const body = JSON.stringify({ source: "abr", run_id: "latest", offset: 50, filters: { state: "QLD", query: "Construction" } });
  const expected = { source: "abr", total: 80, source_total: 20510902, offset: 50, records: [] };
  const response = await forwardLeadGen(new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/source-records/query", {
    method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": randomUUID() }, body,
  }), ["source-records", "query"], admin, async (url, init) => {
    assert.equal(url, "https://engine.maintainmedia.com.au/api/source-records/query");
    assert.equal(init.body, body);
    const claims = decode(new Headers(init.headers).get("authorization").slice(7));
    assert.equal(claims.path, "/api/source-records/query");
    assert.equal(claims.body_sha256, createHash("sha256").update(body).digest("hex"));
    return Response.json(expected);
  });
  assert.deepEqual(await response.json(), expected);
  assert.match(response.headers.get("cache-control"), /private, no-store/);
});

test("export tickets use the server-observed website origin and a fixed direct engine destination", async () => {
  const token = randomBytes(32).toString("base64url");
  const request = new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/source-exports", {
    method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": randomUUID() },
    body: JSON.stringify({ source: "qbcc", run_id: "latest", filters: {}, client_origin: "https://attacker.invalid" }),
  });
  const response = await forwardLeadGen(request, ["source-exports"], admin, async (url, init) => {
    assert.equal(url, "https://engine.maintainmedia.com.au/api/source-exports");
    assert.equal(JSON.parse(init.body).client_origin, "https://www.maintainmedia.com.au");
    const claims = decode(new Headers(init.headers).get("authorization").slice(7));
    assert.equal(claims.body_sha256, createHash("sha256").update(init.body).digest("hex"));
    return Response.json({ download_token: token, expires_at: new Date(Date.now() + 120000).toISOString(),
      download_url: "https://attacker.invalid/collect" });
  });
  const data = await response.json();
  assert.equal(data.download_token, token);
  assert.equal(data.download_url, "https://engine.maintainmedia.com.au/api/source-exports/download");
  assert.match(response.headers.get("cache-control"), /private, no-store/);
});

test("unapproved export origins and malformed ticket responses are refused", async () => {
  let calls = 0;
  const options = { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": randomUUID() }, body: '{"source":"abr"}' };
  await assert.rejects(() => forwardLeadGen(new Request("https://attacker.invalid/api/abn-lead-gen/source-exports", options), ["source-exports"], admin,
    async () => { calls++; return Response.json({}); }), { code: "SOURCE_EXPORT_ORIGIN_REQUIRED" });
  assert.equal(calls, 0);
  for (const invalid of [{ download_token: "bad", expires_at: new Date().toISOString() }, { download_token: randomBytes(32).toString("base64url"), expires_at: "tomorrow" }]) {
    await assert.rejects(() => forwardLeadGen(new Request("https://www.maintainmedia.com.au/api/abn-lead-gen/source-exports", options), ["source-exports"], admin,
      async () => Response.json(invalid)), { code: "ENGINE_INVALID_RESPONSE" });
  }
});
