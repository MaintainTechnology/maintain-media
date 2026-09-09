import assert from "node:assert/strict";
import { createHmac, randomBytes, scryptSync } from "node:crypto";
import { execFile } from "node:child_process";
import { copyFile, mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import {
  ADMIN_COOKIE, AuthError, adminCookie, adminOrigin, authenticatePassword, authorizeAdminRequest,
  cookieToken, issueAdminToken, loginResponse, logoutResponse, parseAdminConfiguration,
  readAdminConfiguration, readSmallJson, verifyAdminToken, verifyPassword,
} from "../src/lib/abn-lead-gen/auth-core.ts";

const password = "test-only-strong-password-2026";
const salt = randomBytes(16);
const hash = scryptSync(password, salt, 64, { N: 32768, r: 8, p: 3, maxmem: 64 * 1024 * 1024 });
const account = { username: "test-admin", displayName: "Test Admin", passwordHash: `scrypt$32768$8$3$${salt.toString("hex")}$${hash.toString("hex")}`, enabled: true, role: "admin" };
const config = { sessionSecret: randomBytes(48).toString("base64url"), accounts: [account] };
const origin = "http://127.0.0.1:3000";
const env = {
  ABN_ADMIN_ACCOUNTS_JSON: process.env.ABN_ADMIN_ACCOUNTS_JSON,
  ABN_ADMIN_SESSION_SECRET: process.env.ABN_ADMIN_SESSION_SECRET,
  ABN_ADMIN_ORIGIN: process.env.ABN_ADMIN_ORIGIN,
};

function request(path, options = {}) {
  return new Request(`${origin}${path}`, options);
}

function jsonRequest(body, headers = {}) {
  return request("/api/abn-lead-gen/auth/login", { method: "POST", headers: { "content-type": "application/json", origin, ...headers }, body: JSON.stringify(body) });
}

function signedClaims(claims) {
  const encoded = Buffer.from(JSON.stringify(claims)).toString("base64url");
  const signature = createHmac("sha256", config.sessionSecret).update(encoded).digest("base64url");
  return `${encoded}.${signature}`;
}

test("admin authentication and request boundaries", async (t) => {
  process.env.ABN_ADMIN_ACCOUNTS_JSON = JSON.stringify(config.accounts);
  process.env.ABN_ADMIN_SESSION_SECRET = config.sessionSecret;
  delete process.env.ABN_ADMIN_ORIGIN;
  t.after(() => {
    for (const [key, value] of Object.entries(env)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });

  await t.test("registry rejects malformed, duplicate and weak configuration", () => {
    for (const candidate of [null, {}, { ...config, sessionSecret: "short" }, { ...config, accounts: [] },
      { ...config, accounts: [account, account] }, { ...config, accounts: [{ ...account, passwordHash: "plaintext" }] },
      { ...config, accounts: [{ ...account, enabled: "true" }] }]) {
      assert.throws(() => parseAdminConfiguration(candidate), (error) => error instanceof AuthError && error.status === 503);
    }
    assert.deepEqual(parseAdminConfiguration(config), config);
  });

  await t.test("missing or partial environment configuration fails closed", async () => {
    delete process.env.ABN_ADMIN_SESSION_SECRET;
    await assert.rejects(readAdminConfiguration(), { code: "ADMIN_AUTH_NOT_CONFIGURED", status: 503 });
    process.env.ABN_ADMIN_SESSION_SECRET = config.sessionSecret;
  });

  await t.test("signed admin cookie verifies without exposing its secret or password hash", () => {
    const token = issueAdminToken(account, config);
    const session = verifyAdminToken(token, config);
    assert.equal(session.username, account.username);
    assert.equal(session.displayName, account.displayName);
    assert.match(session.csrfToken, /^[A-Za-z0-9_-]{43}$/);
    assert.equal(JSON.stringify(session).includes(config.sessionSecret), false);
    assert.equal(JSON.stringify(session).includes(account.passwordHash), false);
    assert.equal(verifyAdminToken(token, config).csrfToken, session.csrfToken);
    assert.notEqual(verifyAdminToken(issueAdminToken(account, config), config).csrfToken, session.csrfToken);
  });

  await t.test("malformed, forged, expired and future tokens are rejected", () => {
    const token = issueAdminToken(account, config);
    const claims = JSON.parse(Buffer.from(token.split(".")[0], "base64url").toString("utf8"));
    for (const invalid of [undefined, "", "bad", "a.b", "%".repeat(4000), `${token}x`, `${token.slice(0, -1)}!`,
      signedClaims(null), signedClaims({}), signedClaims({ ...claims, username: "other-admin" }),
      signedClaims({ ...claims, exp: claims.iat - 1 }), signedClaims({ ...claims, exp: claims.exp + 1 }),
      signedClaims({ ...claims, iat: claims.iat + 600, exp: claims.exp + 600 }),
      signedClaims({ ...claims, nonce: null }), signedClaims({ ...claims, credentials: "wrong" })]) {
      assert.equal(verifyAdminToken(invalid, config), null);
    }
    assert.equal(verifyAdminToken(token, config, Date.now() + 8 * 60 * 60 * 1000 + 1000), null);
    assert.equal(verifyAdminToken(token, { ...config, sessionSecret: randomBytes(48).toString("hex") }), null);
  });

  await t.test("disabled users, removed users, changed roles and password resets revoke access", () => {
    const token = issueAdminToken(account, config);
    for (const accounts of [[], [{ ...account, enabled: false }], [{ ...account, role: "viewer" }],
      [{ ...account, passwordHash: account.passwordHash.replace(/.$/, account.passwordHash.endsWith("0") ? "1" : "0") }]]) {
      assert.equal(verifyAdminToken(token, { ...config, accounts }), null);
    }
    assert.throws(() => issueAdminToken({ ...account, role: "viewer" }, config), { status: 401 });
  });

  await t.test("cookie parsing rejects duplicates and does not accept similarly named cookies", () => {
    const token = issueAdminToken(account, config);
    assert.equal(cookieToken(request("/", { headers: { cookie: `${ADMIN_COOKIE}=${token}` } })), token);
    assert.equal(cookieToken(request("/", { headers: { cookie: `${ADMIN_COOKIE}=first; ${ADMIN_COOKIE}=second` } })), undefined);
    assert.equal(cookieToken(request("/", { headers: { cookie: `${ADMIN_COOKIE}_fake=${token}` } })), undefined);
  });

  await t.test("every mutation requires current admin, same origin and session-bound CSRF", () => {
    const token = issueAdminToken(account, config);
    const session = verifyAdminToken(token, config);
    const validHeaders = { cookie: `${ADMIN_COOKIE}=${token}`, origin, "x-admin-csrf": session.csrfToken };
    assert.equal(authorizeAdminRequest(request("/api/settings", { method: "PATCH", headers: validHeaders }), config, true).username, account.username);
    assert.throws(() => authorizeAdminRequest(request("/api/settings"), config), { status: 401 });
    for (const changed of [{ origin: "https://attacker.example" }, { origin: "" }, { "sec-fetch-site": "cross-site" },
      { "x-admin-csrf": "" }, { "x-admin-csrf": verifyAdminToken(issueAdminToken(account, config), config).csrfToken }]) {
      assert.throws(() => authorizeAdminRequest(request("/api/settings", { method: "PATCH", headers: { ...validHeaders, ...changed } }), config, true), { status: 403 });
    }
    assert.equal(authorizeAdminRequest(request("/api/dashboard", { headers: { cookie: validHeaders.cookie } }), config).username, account.username);
  });

  await t.test("cookie attributes protect JavaScript access and add Secure on HTTPS", () => {
    const localCookie = adminCookie("token", request("/"));
    assert.match(localCookie, /HttpOnly; SameSite=Strict; Max-Age=28800/);
    assert.equal(localCookie.includes("Secure"), false);
    process.env.ABN_ADMIN_ORIGIN = "https://maintainmedia.com.au";
    assert.match(adminCookie("token", new Request("https://maintainmedia.com.au/")), /; Secure$/);
    delete process.env.ABN_ADMIN_ORIGIN;
    assert.match(adminCookie("", request("/"), true), /Max-Age=0/);
    assert.throws(() => adminCookie("token", new Request("http://public.example/")), { status: 503 });
  });

  await t.test("Next internal URL normalization preserves the exact validated loopback browser origin", async () => {
    for (const host of ["127.0.0.1:3001", "localhost:3001", "[::1]:3001"]) {
      const normalized = new Request("http://localhost:3001/api/abn-lead-gen/auth/login", {
        method: "POST", headers: { host, origin: `http://${host}`, "content-type": "application/json" },
        body: JSON.stringify({ username: account.username, password: "wrong" }),
      });
      assert.equal(adminOrigin(normalized), `http://${host}`);
      const response = await loginResponse(normalized);
      assert.equal(response.status, 401);
    }
    for (const host of ["evil.example:3001", "127.0.0.1.evil.example:3001", "user@localhost:3001", "localhost:3001/evil", "localhost:0"]) {
      assert.throws(() => adminOrigin(new Request("http://localhost:3001/", { headers: { host } })), { code: "ADMIN_ORIGIN_INVALID" });
    }
    assert.equal(adminOrigin(new Request("http://localhost:3001/", {
      headers: { host: "127.0.0.1:3001", "x-forwarded-host": "evil.example", "x-forwarded-proto": "https" },
    })), "http://127.0.0.1:3001");
    const mismatched = new Request("http://localhost:3001/api/abn-lead-gen/auth/login", {
      method: "POST", headers: { host: "127.0.0.1:3001", origin: "http://localhost:3001", "content-type": "application/json" },
      body: JSON.stringify({ username: account.username, password }),
    });
    assert.equal((await loginResponse(mismatched)).status, 403);
    // Reset this real test account's failed attempts with a successful authentication.
    await authenticatePassword(account.username, password, config);
  });

  await t.test("configured HTTPS reverse-proxy origin is canonical and rejects hostile public hosts", async () => {
    process.env.ABN_ADMIN_ORIGIN = "https://maintainmedia.com.au";
    const normalized = new Request("http://localhost:3001/api/abn-lead-gen/auth/login", {
      method: "POST", headers: { host: "localhost:3001", origin: "https://maintainmedia.com.au", "content-type": "application/json", "x-forwarded-host": "evil.example" },
      body: JSON.stringify({ username: account.username, password }),
    });
    const success = await loginResponse(normalized);
    assert.equal(success.status, 200);
    assert.match(success.headers.get("set-cookie"), /; Secure$/);
    assert.throws(() => adminOrigin(new Request("http://localhost:3001/", { headers: { host: "evil.example" } })), { code: "ADMIN_ORIGIN_INVALID" });
    delete process.env.ABN_ADMIN_ORIGIN;
  });

  await t.test("request bodies require bounded JSON objects", async () => {
    await assert.rejects(readSmallJson(new Request(`${origin}/`, { method: "POST", body: "x" })), { status: 415 });
    await assert.rejects(readSmallJson(jsonRequest([])), { status: 400 });
    await assert.rejects(readSmallJson(jsonRequest({ value: "a".repeat(4097) })), { status: 413 });
    const malformed = request("/", { method: "POST", headers: { "content-type": "application/json" }, body: "{" });
    await assert.rejects(readSmallJson(malformed), { status: 400 });
  });

  await t.test("sign-in rejects invalid credentials generically and issues an admin cookie", async () => {
    const wrong = await loginResponse(jsonRequest({ username: account.username, password: "incorrect" }));
    assert.equal(wrong.status, 401);
    const unknown = await loginResponse(jsonRequest({ username: "unknown-admin", password: "incorrect" }));
    assert.deepEqual(await unknown.json(), await wrong.json());
    assert.equal(wrong.headers.get("set-cookie"), null);
    const success = await loginResponse(jsonRequest({ username: " TEST-ADMIN ", password }));
    assert.equal(success.status, 200);
    assert.deepEqual(await success.json(), { ok: true });
    assert.match(success.headers.get("set-cookie"), /^maintain_abn_admin=/);
    assert.equal(success.headers.get("cache-control"), "no-store");
  });

  await t.test("login and logout reject cross-origin requests; logout clears a valid cookie", async () => {
    const rejected = await loginResponse(jsonRequest({ username: account.username, password }, { origin: "https://attacker.example" }));
    assert.equal(rejected.status, 403);
    const token = issueAdminToken(account, config);
    const headers = { origin, cookie: `${ADMIN_COOKIE}=${token}`, "x-admin-csrf": verifyAdminToken(token, config).csrfToken };
    const missingCsrf = await logoutResponse(request("/logout", { method: "POST", headers: { origin, cookie: headers.cookie } }));
    assert.equal(missingCsrf.status, 403);
    const crossOrigin = await logoutResponse(request("/logout", { method: "POST", headers: { ...headers, origin: "https://attacker.example" } }));
    assert.equal(crossOrigin.status, 403);
    const success = await logoutResponse(request("/logout", { method: "POST", headers }));
    assert.equal(success.status, 200);
    assert.deepEqual(await success.json(), { ok: true });
    assert.match(success.headers.get("set-cookie"), /Max-Age=0/);
  });

  await t.test("current environment account changes are checked at each request", async () => {
    const token = issueAdminToken(account, config);
    process.env.ABN_ADMIN_ACCOUNTS_JSON = JSON.stringify([{ ...account, enabled: false }]);
    assert.equal(verifyAdminToken(token, await readAdminConfiguration()), null);
    const disabled = await loginResponse(jsonRequest({ username: account.username, password }));
    assert.equal(disabled.status, 401);
    process.env.ABN_ADMIN_ACCOUNTS_JSON = JSON.stringify([{ ...account, role: "viewer" }]);
    const nonAdmin = await loginResponse(jsonRequest({ username: account.username, password }));
    assert.equal(nonAdmin.status, 401);
    process.env.ABN_ADMIN_ACCOUNTS_JSON = JSON.stringify(config.accounts);
  });

  await t.test("throttling rejects repeated attempts and provides retry guidance", async () => {
    const username = "throttled-admin";
    for (let attempt = 0; attempt < 5; attempt++) {
      await assert.rejects(authenticatePassword(username, "bad", config), { status: 401 });
    }
    const limited = await loginResponse(jsonRequest({ username, password: "bad" }));
    assert.equal(limited.status, 429);
    assert.equal(limited.headers.get("retry-after"), "900");
  });
});

test("account CLI provisions, resets and disables multiple local admins without printing credentials", async () => {
  const temporaryRoot = await mkdtemp(path.join(tmpdir(), "maintain-admin-cli-"));
  const scripts = path.join(temporaryRoot, "scripts");
  await mkdir(scripts);
  const commandPath = path.join(scripts, "admin-account.mjs");
  await copyFile(fileURLToPath(new URL("../scripts/admin-account.mjs", import.meta.url)), commandPath);
  const childEnvironment = { ...process.env };
  delete childEnvironment.ABN_ADMIN_ACCOUNTS_JSON;
  delete childEnvironment.ABN_ADMIN_SESSION_SECRET;
  delete childEnvironment.ABN_ADMIN_NEW_PASSWORD;
  const run = (args, additions = {}) => promisify(execFile)(process.execPath, [commandPath, ...args], {
    cwd: temporaryRoot, env: { ...childEnvironment, ...additions }, timeout: 15000,
  });
  const readConfig = async () => JSON.parse(await readFile(path.join(temporaryRoot, ".local", "admin-auth.json"), "utf8"));
  try {
    const created = await run(["create", "--username", "first-admin", "--name", "First Admin"]);
    const firstConfig = parseAdminConfiguration(await readConfig());
    const access = JSON.parse(await readFile(path.join(temporaryRoot, ".local", "admin-access.txt"), "utf8"));
    assert.equal(access.username, "first-admin");
    assert.equal(await verifyPassword(access.password, firstConfig.accounts[0].passwordHash), true);
    for (const privateValue of [access.password, firstConfig.sessionSecret, firstConfig.accounts[0].passwordHash]) {
      assert.equal(created.stdout.includes(privateValue), false);
      assert.equal(created.stderr.includes(privateValue), false);
    }
    await assert.rejects(run(["create", "--username", "first-admin"]));
    assert.deepEqual(parseAdminConfiguration(await readConfig()), firstConfig);
    await run(["create", "--username", "second-admin"]);
    const secondConfig = parseAdminConfiguration(await readConfig());
    assert.equal(secondConfig.accounts.length, 2);
    assert.equal(secondConfig.sessionSecret, firstConfig.sessionSecret);
    const existingToken = issueAdminToken(secondConfig.accounts[0], secondConfig);
    await run(["disable", "--username", "first-admin"]);
    const disabled = parseAdminConfiguration(await readConfig());
    assert.equal(disabled.accounts[0].enabled, false);
    assert.equal(verifyAdminToken(existingToken, disabled), null);
    await run(["reset", "--username", "first-admin"]);
    const reset = parseAdminConfiguration(await readConfig());
    assert.equal(reset.accounts[0].enabled, false);
    assert.notEqual(reset.accounts[0].passwordHash, firstConfig.accounts[0].passwordHash);
    await run(["enable", "--username", "first-admin"]);
    const enabled = parseAdminConfiguration(await readConfig());
    assert.equal(enabled.accounts[0].enabled, true);
    assert.equal(verifyAdminToken(existingToken, enabled), null);
    await assert.rejects(run(["reset", "--username", "first-admin"], { ABN_ADMIN_NEW_PASSWORD: "short" }));
    assert.deepEqual(parseAdminConfiguration(await readConfig()), enabled);
    const listed = await run(["list"]);
    assert.equal(JSON.parse(listed.stdout).length, 2);
    assert.equal(listed.stdout.includes("passwordHash"), false);
    assert.equal(listed.stdout.includes("sessionSecret"), false);
  } finally {
    // The only recursive cleanup target is the unique test directory created above.
    assert.equal(path.dirname(path.resolve(temporaryRoot)), path.resolve(tmpdir()));
    assert.match(path.basename(temporaryRoot), /^maintain-admin-cli-/);
    await rm(temporaryRoot, { recursive: true, force: true });
  }
});
