import test, { beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes, randomUUID } from "node:crypto";
import { forwardLeadGen, parseBridgePath } from "../src/lib/abn-lead-gen/bridge.ts";

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
