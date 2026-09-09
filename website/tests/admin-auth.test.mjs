import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { registerHooks } from "node:module";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import * as authCore from "../src/lib/abn-lead-gen/auth-core.ts";

// The application uses Next's extensionless TypeScript resolution. This test-only loader
// resolves the same modules for Node's native strip-types runner; authentication is never bypassed.
registerHooks({ resolve(specifier, context, nextResolve) {
  if (context.parentURL?.endsWith("/clerk-access-service.ts") && ["./auth-core", "./clerk-policy"].includes(specifier)) {
    return nextResolve(`${specifier}.ts`, context);
  }
  return nextResolve(specifier, context);
} });
const { resolveClerkAdminAccess, requireAdminAccess, authorizeClerkRequest } = await import("../src/lib/abn-lead-gen/clerk-access-service.ts");
const { AuthError, adminOrigin, assertSameOrigin, authFailure, readSmallJson, retiredPasswordAuthResponse } = authCore;
const origin = "http://127.0.0.1:3001";
const identity = { userId: "user_Admin123", sessionId: "sess_Current123" };
const secret = randomBytes(32).toString("base64url");
const makeRequest = (headers = {}, method = "PATCH") => new Request(`${origin}/api/abn-lead-gen/settings`, {
  method, headers: { host: "127.0.0.1:3001", origin, ...headers },
});
function fixture() {
  const calls = [];
  const state = {
    identity: { ...identity },
    session: { id: identity.sessionId, userId: identity.userId, status: "active", expireAt: Date.now() + 60_000, abandonAt: Date.now() + 60_000 },
    user: { id: identity.userId, banned: false, locked: false, username: "admin", fullName: "Maintain Admin", publicMetadata: { role: "admin" } },
  };
  const backend = {
    authenticate: async () => { calls.push(["auth"]); return state.identity; },
    getSession: async id => { calls.push(["session", id]); return state.session; },
    getUser: async id => { calls.push(["user", id]); return state.user; },
    secret,
  };
  return { calls, state, backend };
}

test("signed-out and malformed identities cannot trigger backend account access", async () => {
  for (const input of [null, { userId: null, sessionId: null }, { ...identity, sessionId: null }, { ...identity, userId: "invalid" }]) {
    const { backend, state, calls } = fixture();
    state.identity = input;
    assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "signed-out" });
    assert.deepEqual(calls, [["auth"]]);
  }
});

test("verified identity uses current server session and user before returning a minimal admin DTO", async () => {
  const { backend, calls } = fixture();
  const access = await resolveClerkAdminAccess(backend);
  assert.equal(access.status, "admin");
  assert.deepEqual(Object.keys(access.admin).sort(), ["csrfToken", "displayName", "username"]);
  assert.equal(access.admin.displayName, "Maintain Admin");
  assert.match(access.admin.csrfToken, /^[A-Za-z0-9_-]{43}$/);
  assert.deepEqual(calls, [["auth"], ["session", identity.sessionId], ["user", identity.userId]]);
  assert.equal(JSON.stringify(access).includes(secret), false);
  assert.equal(JSON.stringify(access).includes(identity.sessionId), false);
});

test("each request rechecks role and session rather than retaining cached admin privilege", async () => {
  const { backend, state, calls } = fixture();
  assert.equal((await resolveClerkAdminAccess(backend)).status, "admin");
  state.user.publicMetadata.role = "member";
  assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "forbidden" });
  state.user.publicMetadata.role = "admin";
  state.session.status = "revoked";
  assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "signed-out" });
  assert.equal(calls.filter(([kind]) => kind === "user").length, 3);
  assert.equal(calls.filter(([kind]) => kind === "session").length, 3);
});

test("only an active session belonging to this verified user and session can enter", async () => {
  for (const status of ["revoked", "expired", "ended", "removed", "abandoned", "pending", "unknown", "Active"]) {
    const { backend, state } = fixture();
    state.session.status = status;
    assert.equal((await resolveClerkAdminAccess(backend)).status, "signed-out");
  }
  for (const change of [{ id: "sess_Other123" }, { userId: "user_Other123" }]) {
    const { backend, state } = fixture();
    Object.assign(state.session, change);
    assert.equal((await resolveClerkAdminAccess(backend)).status, "signed-out");
  }
});

test("expired or abandoned sessions are rejected even if a stale response says active", async () => {
  for (const field of ["expireAt", "abandonAt"]) {
    const { backend, state } = fixture();
    state.session[field] = Date.now() - 1;
    assert.equal((await resolveClerkAdminAccess(backend)).status, "signed-out");
  }
});

test("incomplete backend session data fails closed as unavailable", async () => {
  for (const session of [null, {}, [], { status: "active" },
    { id: identity.sessionId, userId: identity.userId, status: "active", expireAt: Infinity, abandonAt: Date.now() + 60_000 }]) {
    const { backend, state } = fixture();
    state.session = session;
    assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" });
  }
});

test("deleted provider records lose access and provider faults never expose raw errors", async () => {
  for (const method of ["getSession", "getUser"]) {
    const { backend } = fixture();
    backend[method] = async () => { throw { status: 404, message: "private provider error" }; };
    assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "signed-out" });
    for (const status of [401, 403, 429, 500, 503]) {
      backend[method] = async () => { throw { status, message: `private provider error ${secret}` }; };
      const access = await resolveClerkAdminAccess(backend);
      assert.deepEqual(access, { status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" });
      assert.equal(JSON.stringify(access).includes(secret), false);
    }
  }
  const { backend } = fixture();
  backend.authenticate = async () => { throw new Error(`configuration details ${secret}`); };
  assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" });
});

test("a stalled auth or provider lookup returns an unavailable result within its deadline", async () => {
  for (const method of ["authenticate", "getSession", "getUser"]) {
    const { backend } = fixture();
    backend[method] = () => new Promise(() => {});
    assert.deepEqual(await resolveClerkAdminAccess(backend, 10), { status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" });
  }
});

test("policy denials remain forbidden and do not grant access from unsafe metadata", async () => {
  for (const changes of [
    { id: "user_Other123" }, { banned: true }, { locked: true },
    { publicMetadata: { role: "member" }, unsafeMetadata: { role: "admin" } },
    { publicMetadata: { role: "admin", disabled: true } },
  ]) {
    const { backend, state } = fixture();
    Object.assign(state.user, changes);
    assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "forbidden" });
  }
});

test("missing server CSRF secret is an unavailable configuration, not an authorized session", async () => {
  const { backend } = fixture();
  backend.secret = undefined;
  assert.deepEqual(await resolveClerkAdminAccess(backend), { status: "unavailable", code: "ADMIN_AUTH_NOT_CONFIGURED" });
});

test("page and request consumers preserve distinct 401, 403 and 503 failures", () => {
  for (const [access, code, status] of [
    [{ status: "signed-out" }, "ADMIN_SIGN_IN_REQUIRED", 401],
    [{ status: "forbidden" }, "ADMIN_ACCESS_REQUIRED", 403],
    [{ status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" }, "ADMIN_AUTH_UNAVAILABLE", 503],
  ]) {
    assert.throws(() => requireAdminAccess(access), error => error instanceof AuthError && error.code === code && error.status === status);
    assert.throws(() => authorizeClerkRequest(makeRequest(), access, false), { code, status });
  }
});

test("every engine mutation requires Clerk authority, exact origin and its current CSRF token", async () => {
  const previous = process.env.ABN_ADMIN_ORIGIN;
  delete process.env.ABN_ADMIN_ORIGIN;
  try {
    const { backend } = fixture();
    const access = await resolveClerkAdminAccess(backend);
    const valid = { "x-admin-csrf": access.admin.csrfToken };
    assert.equal(authorizeClerkRequest(makeRequest(valid), access, true), access.admin);
    for (const headers of [{}, { ...valid, origin: "https://evil.example" }, { ...valid, "sec-fetch-site": "cross-site" }, { "x-admin-csrf": "x".repeat(43) }]) {
      assert.throws(() => authorizeClerkRequest(makeRequest(headers), access, true), { status: 403 });
    }
    const read = makeRequest({ cookie: "maintain_abn_admin=legacy-cookie" }, "GET");
    assert.throws(() => authorizeClerkRequest(read, { status: "signed-out" }), { status: 401 });
    assert.equal(authorizeClerkRequest(read, access), access.admin);
  } finally {
    if (previous === undefined) delete process.env.ABN_ADMIN_ORIGIN; else process.env.ABN_ADMIN_ORIGIN = previous;
  }
});

test("origin checking preserves normalized loopback requests and rejects host spoofing", () => {
  const previous = process.env.ABN_ADMIN_ORIGIN;
  delete process.env.ABN_ADMIN_ORIGIN;
  try {
    for (const host of ["127.0.0.1:3001", "localhost:3001", "[::1]:3001"]) {
      const request = new Request("http://localhost:3001/api/abn-lead-gen/settings", { headers: { host, origin: `http://${host}` } });
      assert.equal(adminOrigin(request), `http://${host}`);
      assert.doesNotThrow(() => assertSameOrigin(request));
    }
    for (const host of ["evil.example:3001", "127.0.0.1.evil.example:3001", "user@localhost:3001", "localhost:3001/evil", "localhost:0"]) {
      assert.throws(() => adminOrigin(new Request("http://localhost:3001/", { headers: { host } })), { code: "ADMIN_ORIGIN_INVALID" });
    }
    assert.equal(adminOrigin(new Request("http://localhost:3001/", { headers: { host: "127.0.0.1:3001", "x-forwarded-host": "evil.example" } })), origin);
    process.env.ABN_ADMIN_ORIGIN = "https://maintainmedia.com.au";
    assert.doesNotThrow(() => assertSameOrigin(new Request("http://localhost:3001/", { headers: { host: "localhost:3001", origin: "https://maintainmedia.com.au" } })));
    assert.throws(() => adminOrigin(new Request("http://localhost:3001/", { headers: { host: "evil.example" } })), { code: "ADMIN_ORIGIN_INVALID" });
  } finally {
    if (previous === undefined) delete process.env.ABN_ADMIN_ORIGIN; else process.env.ABN_ADMIN_ORIGIN = previous;
  }
});

test("bounded JSON and private sanitized failures remain available after password removal", async () => {
  const jsonRequest = value => new Request(origin, { method: "POST", headers: { "content-type": "application/json" }, body: value });
  await assert.rejects(readSmallJson(jsonRequest("[]")), { status: 400 });
  await assert.rejects(readSmallJson(jsonRequest("{")), { status: 400 });
  await assert.rejects(readSmallJson(jsonRequest(JSON.stringify({ value: "a".repeat(4097) }))), { status: 413 });
  await assert.rejects(readSmallJson(new Request(origin, { method: "POST", body: "x" })), { status: 415 });
  assert.deepEqual(await readSmallJson(jsonRequest('{"source":"abr"}')), { source: "abr" });
  const response = authFailure(new Error(`secret=${secret}`));
  assert.equal(response.status, 503);
  assert.equal(JSON.stringify(await response.json()).includes(secret), false);
  assert.match(response.headers.get("cache-control"), /private, no-store/);
});

test("legacy password endpoints return a retirement response without issuing or clearing sessions", async () => {
  const response = retiredPasswordAuthResponse();
  assert.equal(response.status, 410);
  assert.equal(response.headers.get("set-cookie"), null);
  assert.deepEqual(await response.json(), {
    code: "CLERK_AUTH_REQUIRED",
    message: "Local password authentication has been retired. Use Maintain Media Clerk sign-in and account controls.",
    signInUrl: "/sign-in",
  });
  for (const removed of ["ADMIN_COOKIE", "issueAdminToken", "verifyAdminToken", "authenticatePassword", "readAdminConfiguration", "loginResponse", "logoutResponse"]) {
    assert.equal(authCore[removed], undefined);
  }
});

test("legacy account command exits with Clerk instructions and no provisioning side effects", async () => {
  await assert.rejects(promisify(execFile)(process.execPath, [fileURLToPath(new URL("../scripts/admin-account.mjs", import.meta.url)), "create", "--username", "obsolete"], { windowsHide: true }), error => {
    assert.equal(error.code, 1);
    assert.equal(error.stdout, "");
    assert.match(error.stderr, /Local admin passwords have been retired/);
    assert.match(error.stderr, /publicMetadata.role/);
    return true;
  });
});
