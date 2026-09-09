import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import {
  authorizeClerkAdmin, assertClerkCsrf, createClerkCsrfToken,
} from "../src/lib/abn-lead-gen/clerk-policy.ts";

const identity = { userId: "user_Authorised123", sessionId: "sess_Current123" };
const secret = randomBytes(32).toString("base64url");
const user = {
  id: identity.userId, username: "maintain-admin", firstName: "Maintain", lastName: "Admin",
  banned: false, locked: false, publicMetadata: { role: "admin" },
};
const denied = { code: "ADMIN_ACCESS_REQUIRED", status: 403 };
const signedOut = { code: "ADMIN_SIGN_IN_REQUIRED", status: 401 };
const mutation = token => new Request("http://127.0.0.1:3001/api/abn-lead-gen/settings", {
  method: "PATCH", headers: token === undefined ? {} : { "X-Admin-CSRF": token },
});

test("absent or malformed verified session identity cannot authorize an admin", () => {
  for (const session of [null, {}, { userId: null, sessionId: null },
    { ...identity, sessionId: null }, { ...identity, userId: null },
    { ...identity, userId: "attacker" }, { ...identity, sessionId: "sess_invalid\n" }]) {
    assert.throws(() => authorizeClerkAdmin(session, user, secret), signedOut);
  }
});

test("only exact server-managed admin metadata grants access", () => {
  for (const role of [undefined, null, "member", "Admin", " admin", "org:admin", ["admin"], true]) {
    assert.throws(() => authorizeClerkAdmin(identity, {
      ...user, publicMetadata: { role }, unsafeMetadata: { role: "admin" },
    }, secret), denied);
  }
  for (const publicMetadata of [undefined, null, [], "admin"]) {
    assert.throws(() => authorizeClerkAdmin(identity, { ...user, publicMetadata }, secret), denied);
  }
  assert.throws(() => authorizeClerkAdmin(identity, {
    ...user, publicMetadata: {}, privateMetadata: { role: "admin" }, unsafeMetadata: { role: "admin" },
  }, secret), denied);
});

test("banned, locked, disabled and malformed safety flags fail closed", () => {
  for (const field of ["banned", "locked"]) {
    for (const value of [true, undefined, null, "false", 0]) {
      assert.throws(() => authorizeClerkAdmin(identity, { ...user, [field]: value }, secret), denied);
    }
  }
  for (const publicMetadata of [
    { role: "admin", enabled: false }, { role: "admin", enabled: "true" },
    { role: "admin", enabled: null }, { role: "admin", disabled: true },
    { role: "admin", disabled: "false" }, { role: "admin", disabled: null },
  ]) assert.throws(() => authorizeClerkAdmin(identity, { ...user, publicMetadata }, secret), denied);
  assert.ok(authorizeClerkAdmin(identity, {
    ...user, publicMetadata: { role: "admin", enabled: true, disabled: false },
  }, secret).csrfToken);
});

test("missing user and mismatched backend identity cannot borrow another user's role", () => {
  for (const backendUser of [null, undefined, [], {}, { ...user, id: "user_Other123" }]) {
    assert.throws(() => authorizeClerkAdmin(identity, backendUser, secret), denied);
  }
});

test("admin DTO exposes only bounded labels and the derived token", () => {
  const session = authorizeClerkAdmin(identity, {
    ...user, primaryEmailAddress: { emailAddress: "private@example.test" },
    privateMetadata: { secret: "private value" }, unsafeMetadata: { role: "member" },
  }, secret);
  assert.deepEqual(Object.keys(session).sort(), ["csrfToken", "displayName", "username"]);
  assert.equal(session.username, "maintain-admin");
  assert.equal(session.displayName, "Maintain Admin");
  assert.match(session.csrfToken, /^[A-Za-z0-9_-]{43}$/);
  const serialised = JSON.stringify(session);
  for (const hidden of [secret, identity.sessionId, "private@example.test", "private value"]) {
    assert.equal(serialised.includes(hidden), false);
  }
  assert.equal(authorizeClerkAdmin(identity, { ...user, fullName: "  Full Name  " }, secret).displayName, "Full Name");
  const invalidLabels = { ...user, username: "x".repeat(201), firstName: "na\nme", lastName: null, fullName: "\0" };
  assert.equal(authorizeClerkAdmin(identity, invalidLabels, secret).displayName, identity.userId);
});

test("CSRF is stable in a session and isolated by session, user and secret", () => {
  const token = createClerkCsrfToken(identity, secret);
  assert.equal(createClerkCsrfToken({ ...identity }, secret), token);
  assert.notEqual(createClerkCsrfToken({ ...identity, sessionId: "sess_Another123" }, secret), token);
  assert.notEqual(createClerkCsrfToken({ ...identity, userId: "user_Another123" }, secret), token);
  assert.notEqual(createClerkCsrfToken(identity, randomBytes(32).toString("base64url")), token);
});

test("missing, short or malformed server secrets fail closed without echoing a secret", () => {
  for (const invalid of [undefined, "", "x".repeat(31), ` ${secret}`, `${secret}\n`, `${secret}\0`, "x".repeat(4097)]) {
    assert.throws(() => authorizeClerkAdmin(identity, user, invalid), {
      code: "ADMIN_AUTH_NOT_CONFIGURED", status: 503, message: "ADMIN_AUTH_NOT_CONFIGURED",
    });
  }
});

test("mutation token validation rejects omissions, tampering and a different session", () => {
  const session = authorizeClerkAdmin(identity, user, secret);
  assert.doesNotThrow(() => assertClerkCsrf(mutation(session.csrfToken), session));
  const changed = `${session.csrfToken[0] === "a" ? "b" : "a"}${session.csrfToken.slice(1)}`;
  for (const token of [undefined, "", "short", changed, "x".repeat(4097),
    createClerkCsrfToken({ ...identity, sessionId: "sess_Other123" }, secret)]) {
    assert.throws(() => assertClerkCsrf(mutation(token), session), { code: "ADMIN_CSRF_REQUIRED", status: 403 });
  }
  assert.throws(() => assertClerkCsrf(mutation("x".repeat(43)), { ...session, csrfToken: "" }), { code: "ADMIN_CSRF_REQUIRED", status: 403 });
});
