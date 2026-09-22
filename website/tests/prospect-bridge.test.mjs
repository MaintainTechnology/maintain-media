import test, { beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes, randomUUID } from "node:crypto";
import { bridgeFailure, forwardLeadGen, parseBridgePath } from "../src/lib/abn-lead-gen/bridge.ts";

const key = randomBytes(32).toString("base64url");
const admin = { username: "synthetic-reviewer", displayName: "Reviewer", csrfToken: "local", actorId: "user_SyntheticReviewer", scopes: ["admin", "reviewer"] };
const variables = ["ABN_ENGINE_MODE", "ABN_ENGINE_TRANSPORT", "ABN_ENGINE_ORIGIN", "ABN_ENGINE_TOKEN", "ABN_ENGINE_ASSERTION_KEY"];
let previous;
beforeEach(() => {
  previous = variables.map(name => [name, process.env[name]]);
  Object.assign(process.env, { ABN_ENGINE_MODE: "pilot", ABN_ENGINE_TRANSPORT: "remote", ABN_ENGINE_ORIGIN: "https://engine.maintainmedia.com.au", ABN_ENGINE_ASSERTION_KEY: key });
});
afterEach(() => { for (const [name, value] of previous) value === undefined ? delete process.env[name] : process.env[name] = value; });
const origin = "https://www.maintainmedia.com.au/api/abn-lead-gen/";
const abn = "51824753556";
const routes = [["prospects", abn], ["prospects", "query"], ["prospects"]];
const methods = ["GET", "POST", "POST"];
const targets = [`/api/prospects/${abn}`, "/api/prospects/query", "/v1/prospects"];

test("prospect routes allow only the explicit live read, query and save contract", () => {
  routes.forEach((parts, index) => {
    assert.equal(parseBridgePath(parts, methods[index], true), targets[index]);
    assert.throws(() => parseBridgePath(parts, methods[index], false), { code: "ROUTE_NOT_FOUND" });
    for (const method of ["GET", "HEAD", "POST", "PATCH", "DELETE", "PUT"].filter(value => value !== methods[index])) {
      assert.throws(() => parseBridgePath(parts, method, true), { code: "ROUTE_NOT_FOUND" });
    }
  });
  for (const parts of [["prospects", "51 824 753 556"], ["prospects", "123"], ["prospects", "../"], ["prospects", abn, "extra"], ["prospects", "export"], ["prospects", "send"]]) {
    for (const method of ["GET", "POST"]) assert.throws(() => parseBridgePath(parts, method, true), { code: "ROUTE_NOT_FOUND" });
  }
});

test("prospect reads, filtered lists and saves bind actor, exact body and retry identity", async () => {
  const requestId = randomUUID();
  const bodies = [undefined,
    JSON.stringify({ offset: 0, filters: { registration_date_from: "2026-09-16", registration_date_to: "2026-09-22", website_presence: "absent" } }),
    JSON.stringify({ abn, request_id: requestId, expected_revision: 1, source: "abr", snapshot_id: randomUUID(), run_id: randomUUID(), research_note: "Synthetic, reviewed research" }),
  ];
  const responses = [{ prospect: null }, { records: [], total: 0, offset: 0, limit: 50, next_offset: null },
    { prospect_id: randomUUID(), revision: 2, saved_at: "2026-09-22T03:04:05Z", expires_at: "2027-03-21T03:04:05Z" }];
  for (let index = 0; index < routes.length; index++) {
    const response = await forwardLeadGen(new Request(origin + routes[index].join("/"), {
      method: methods[index], headers: { "Content-Type": "application/json", "Idempotency-Key": requestId, Cookie: "private-browser-cookie", Authorization: "Bearer browser-session", Origin: "https://www.maintainmedia.com.au" }, body: bodies[index],
    }), routes[index], admin, async (url, init) => {
      assert.equal(url, "https://engine.maintainmedia.com.au" + targets[index]);
      assert.equal(init.method, methods[index]); assert.equal(init.body, bodies[index]);
      assert.equal(init.cache, "no-store"); assert.equal(init.redirect, "error");
      const headers = new Headers(init.headers); const token = headers.get("authorization").slice(7);
      const claims = JSON.parse(Buffer.from(token.split(".")[1], "base64url"));
      assert.equal(claims.sub, admin.actorId); assert.deepEqual(claims.scopes, admin.scopes);
      assert.equal(claims.path, targets[index]); assert.equal(claims.method, methods[index]);
      assert.equal(claims.body_sha256, createHash("sha256").update(bodies[index] || "").digest("hex"));
      assert.equal(claims.idempotency_key, index ? requestId : "");
      assert.equal(claims.request_id, headers.get("x-request-id"));
      assert.equal(headers.get("idempotency-key"), index ? requestId : null);
      assert.equal(token.split(".")[2], createHmac("sha256", key).update(token.split(".").slice(0, 2).join(".")).digest("base64url"));
      assert.equal(headers.get("cookie"), null); assert.equal(headers.get("origin"), null);
      return Response.json(responses[index]);
    });
    assert.deepEqual(await response.json(), responses[index]);
    assert.equal(response.headers.get("cache-control"), "private, no-store, max-age=0");
    assert.equal(response.headers.get("x-robots-tag"), "noindex, nofollow, noarchive");
  }
});

test("unsigned query parameters and missing save identities stop before any upstream call", async () => {
  let calls = 0;
  const fetcher = async () => { calls++; return Response.json({}); };
  for (let index = 0; index < routes.length; index++) {
    await assert.rejects(() => forwardLeadGen(new Request(origin + routes[index].join("/") + "?scope=all", {
      method: methods[index], headers: { "Content-Type": "application/json", "Idempotency-Key": randomUUID() }, body: index ? "{}" : undefined,
    }), routes[index], admin, fetcher), { code: "INVALID_INPUT", status: 422 });
  }
  await assert.rejects(() => forwardLeadGen(new Request(origin + "prospects", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  }), ["prospects"], admin, fetcher), { code: "REQUEST_IDENTIFIERS_REQUIRED" });
  assert.equal(calls, 0);
});

test("prospect restrictions retain the engine error code without private upstream detail", async () => {
  let failure;
  try {
    await forwardLeadGen(new Request(origin + `prospects/${abn}`), ["prospects", abn], admin,
      async () => Response.json({ code: "SUPPRESSED_SOURCE_IDENTITY", detail: "Private business details" }, { status: 409 }));
  } catch (error) { failure = error; }
  const response = bridgeFailure(failure);
  assert.equal(response.status, 409);
  assert.deepEqual(await response.json(), { code: "SUPPRESSED_SOURCE_IDENTITY" });
  assert.match(response.headers.get("cache-control"), /private, no-store/);
});
