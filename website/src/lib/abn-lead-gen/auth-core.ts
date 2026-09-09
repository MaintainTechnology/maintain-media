import { createHash, createHmac, randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";

export const ADMIN_COOKIE = "maintain_abn_admin";
const SESSION_SECONDS = 8 * 60 * 60;
const USERNAME = /^[a-z0-9][a-z0-9_.@-]{2,127}$/;
const HASH = /^scrypt\$32768\$8\$3\$([a-f0-9]{32})\$([a-f0-9]{128})$/;
const DUMMY_HASH = `scrypt$32768$8$3$${"0".repeat(32)}$${"0".repeat(128)}`;

export class AuthError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, status: number) {
    super(code);
    this.name = "AuthError";
    this.code = code;
    this.status = status;
  }
}

export type AdminSession = {
  username: string;
  displayName: string;
  csrfToken: string;
};

export type AdminAccount = {
  username: string;
  displayName: string;
  passwordHash: string;
  enabled: boolean;
  role: string;
};

export type AdminConfiguration = {
  sessionSecret: string;
  accounts: AdminAccount[];
};

type SessionClaims = {
  v: 1;
  username: string;
  iat: number;
  exp: number;
  nonce: string;
  credentials: string;
};

type Attempt = { count: number; until: number };
type AuthRuntime = { attempts: Map<string, Attempt>; activeLogins: number };
const globalAuth = globalThis as typeof globalThis & { __maintainAbnAuth?: AuthRuntime };
const runtime = (globalAuth.__maintainAbnAuth ??= { attempts: new Map(), activeLogins: 0 });

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseAdminConfiguration(value: unknown): AdminConfiguration {
  if (!object(value) || typeof value.sessionSecret !== "string"
    || value.sessionSecret.length < 32 || value.sessionSecret.length > 512
    || !Array.isArray(value.accounts) || value.accounts.length === 0 || value.accounts.length > 1000) {
    throw new AuthError("ADMIN_AUTH_NOT_CONFIGURED", 503);
  }
  const usernames = new Set<string>();
  const accounts: AdminAccount[] = [];
  for (const account of value.accounts) {
    if (!object(account) || typeof account.username !== "string" || !USERNAME.test(account.username)
      || usernames.has(account.username) || typeof account.displayName !== "string"
      || !account.displayName.trim() || account.displayName.length > 100
      || typeof account.passwordHash !== "string" || !HASH.test(account.passwordHash)
      || typeof account.enabled !== "boolean" || typeof account.role !== "string"
      || !account.role || account.role.length > 32) {
      throw new AuthError("ADMIN_AUTH_NOT_CONFIGURED", 503);
    }
    usernames.add(account.username);
    accounts.push(account as AdminAccount);
  }
  return { sessionSecret: value.sessionSecret, accounts };
}

/** Re-read on each request so disabled users, role changes and password resets take effect immediately. */
export async function readAdminConfiguration(): Promise<AdminConfiguration> {
  try {
    const accounts = process.env.ABN_ADMIN_ACCOUNTS_JSON;
    const secret = process.env.ABN_ADMIN_SESSION_SECRET;
    if (accounts !== undefined || secret !== undefined) {
      return parseAdminConfiguration({ accounts: JSON.parse(accounts ?? "null"), sessionSecret: secret });
    }
    const data = await readFile(path.join(process.cwd(), ".local", "admin-auth.json"), "utf8");
    if (data.length > 1024 * 1024) throw new Error("Configuration is too large");
    return parseAdminConfiguration(JSON.parse(data));
  } catch {
    throw new AuthError("ADMIN_AUTH_NOT_CONFIGURED", 503);
  }
}

function equal(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

function sign(value: string, secret: string): string {
  return createHmac("sha256", secret).update(value).digest("base64url");
}

function credentialVersion(account: AdminAccount): string {
  return createHash("sha256").update(account.passwordHash).digest("base64url");
}

export function issueAdminToken(account: AdminAccount, config: AdminConfiguration, now = Date.now()): string {
  if (account.role !== "admin" || !account.enabled) throw new AuthError("INVALID_CREDENTIALS", 401);
  const iat = Math.floor(now / 1000);
  const payload: SessionClaims = {
    v: 1, username: account.username, iat, exp: iat + SESSION_SECONDS,
    nonce: randomBytes(32).toString("base64url"), credentials: credentialVersion(account),
  };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${encoded}.${sign(encoded, config.sessionSecret)}`;
}

export function verifyAdminToken(token: string | undefined, config: AdminConfiguration, now = Date.now()): AdminSession | null {
  if (!token || token.length > 2048 || !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}$/.test(token)) return null;
  try {
    const [encoded, signature] = token.split(".");
    if (!equal(signature, sign(encoded, config.sessionSecret))) return null;
    const payload: unknown = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    if (!object(payload) || payload.v !== 1 || typeof payload.username !== "string"
      || !USERNAME.test(payload.username) || !Number.isSafeInteger(payload.iat) || !Number.isSafeInteger(payload.exp)
      || typeof payload.iat !== "number" || typeof payload.exp !== "number"
      || payload.iat > Math.floor(now / 1000) + 30 || payload.exp <= Math.floor(now / 1000)
      || payload.exp <= payload.iat || payload.exp - payload.iat > SESSION_SECONDS
      || typeof payload.nonce !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(payload.nonce)
      || typeof payload.credentials !== "string") return null;
    const account = config.accounts.find((item) => item.username === payload.username);
    if (!account || !account.enabled || account.role !== "admin"
      || !equal(payload.credentials, credentialVersion(account))) return null;
    return {
      username: account.username,
      displayName: account.displayName,
      csrfToken: sign(`csrf\0${token}`, config.sessionSecret),
    };
  } catch {
    return null;
  }
}

export function cookieToken(request: Request): string | undefined {
  const cookies = request.headers.get("cookie")?.split(";") ?? [];
  const matches = cookies.map((item) => item.trim()).filter((item) => item.startsWith(`${ADMIN_COOKIE}=`));
  // Ambiguous duplicate cookies must not select an attacker-controlled value by ordering.
  if (matches.length !== 1) return undefined;
  return matches[0].slice(ADMIN_COOKIE.length + 1);
}

export function adminOrigin(request: Request): string {
  try {
    const configured = process.env.ABN_ADMIN_ORIGIN;
    const internal = new URL(request.url);
    const origin = new URL(configured || internal.origin);
    const local = (hostname: string) => ["localhost", "127.0.0.1", "[::1]"].includes(hostname);
    if (!["http:", "https:"].includes(origin.protocol) || origin.username || origin.password
      || (configured && (origin.pathname !== "/" || origin.search || origin.hash))
      || (origin.protocol === "http:" && !local(origin.hostname))) throw new Error("Invalid origin");
    const rawHost = request.headers.get("host");
    let browserHost: URL | null = null;
    if (rawHost !== null) {
      // Next may normalize request.url to localhost even when the browser used 127.0.0.1.
      // Only a syntactically valid Host is considered; forwarded host/proto are never trusted.
      if (!rawHost || /[\s\\/@?#]/.test(rawHost)) throw new Error("Invalid host");
      browserHost = new URL(`${origin.protocol}//${rawHost}`);
      if (browserHost.username || browserHost.password || browserHost.port === "0"
        || browserHost.pathname !== "/" || browserHost.search || browserHost.hash) throw new Error("Invalid host");
    }
    if (configured) {
      // A managed reverse proxy can retain its internal loopback Host. Any public Host
      // must match the explicitly configured canonical host; Origin must still match exactly.
      if (browserHost && !local(browserHost.hostname) && browserHost.host !== origin.host) throw new Error("Invalid host");
      return origin.origin;
    }
    const browserOrigin = browserHost ?? origin;
    if (!local(internal.hostname) || !local(browserOrigin.hostname)) throw new Error("Canonical origin required");
    return browserOrigin.origin;
  } catch {
    throw new AuthError("ADMIN_ORIGIN_INVALID", 503);
  }
}

export function assertSameOrigin(request: Request): void {
  const origin = request.headers.get("origin");
  if (origin !== adminOrigin(request) || request.headers.get("sec-fetch-site") === "cross-site") {
    throw new AuthError("SAME_ORIGIN_REQUIRED", 403);
  }
}

export function authorizeAdminRequest(request: Request, config: AdminConfiguration, mutation = false): AdminSession {
  const session = verifyAdminToken(cookieToken(request), config);
  if (!session) throw new AuthError("ADMIN_SIGN_IN_REQUIRED", 401);
  if (mutation) {
    assertSameOrigin(request);
    if (!equal(request.headers.get("x-admin-csrf") ?? "", session.csrfToken)) {
      throw new AuthError("ADMIN_CSRF_REQUIRED", 403);
    }
  }
  return session;
}

export async function readSmallJson(request: Request): Promise<Record<string, unknown>> {
  if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") {
    throw new AuthError("JSON_REQUIRED", 415);
  }
  if (Number(request.headers.get("content-length")) > 4096) throw new AuthError("BODY_TOO_LARGE", 413);
  const reader = request.body?.getReader();
  if (!reader) throw new AuthError("INVALID_INPUT", 400);
  const parts: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 4096) {
        await reader.cancel();
        throw new AuthError("BODY_TOO_LARGE", 413);
      }
      parts.push(value);
    }
    const value: unknown = JSON.parse(Buffer.concat(parts).toString("utf8"));
    if (!object(value)) throw new Error("Object required");
    return value;
  } catch (error) {
    if (error instanceof AuthError) throw error;
    throw new AuthError("INVALID_INPUT", 400);
  } finally {
    reader.releaseLock();
  }
}

export async function verifyPassword(password: string, encoded: string): Promise<boolean> {
  const match = HASH.exec(encoded);
  if (!match || password.length > 1024) return false;
  const derived = await new Promise<Buffer>((resolve, reject) => {
    scrypt(password, Buffer.from(match[1], "hex"), 64, { N: 32768, r: 8, p: 3, maxmem: 64 * 1024 * 1024 }, (error, key) => {
      if (error) reject(error);
      else resolve(key);
    });
  });
  return timingSafeEqual(derived, Buffer.from(match[2], "hex"));
}

function consumeAttempt(username: string, now: number): void {
  for (const [key, attempt] of runtime.attempts) {
    if (attempt.until <= now) runtime.attempts.delete(key);
  }
  for (const [key, limit] of [["global", 100], [`user:${username}`, 5]] as const) {
    const attempt = runtime.attempts.get(key) ?? { count: 0, until: now + 15 * 60 * 1000 };
    if (attempt.count >= limit) throw new AuthError("LOGIN_RATE_LIMITED", 429);
    attempt.count++;
    runtime.attempts.set(key, attempt);
  }
}

/** The limiter is shared by all requests in this Node process, including development reloads. */
export async function authenticatePassword(username: string, password: string, config: AdminConfiguration): Promise<AdminAccount> {
  const normalized = username.trim().toLowerCase();
  consumeAttempt(normalized, Date.now());
  if (runtime.activeLogins >= 4) throw new AuthError("LOGIN_RATE_LIMITED", 429);
  runtime.activeLogins++;
  try {
    const account = config.accounts.find((item) => item.username === normalized);
    const valid = await verifyPassword(password, account?.passwordHash ?? DUMMY_HASH);
    if (!valid || !account || account.role !== "admin" || !account.enabled) throw new AuthError("INVALID_CREDENTIALS", 401);
    runtime.attempts.delete(`user:${normalized}`);
    return account;
  } finally {
    runtime.activeLogins--;
  }
}

export function adminCookie(value: string, request: Request, remove = false): string {
  return `${ADMIN_COOKIE}=${value}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${remove ? 0 : SESSION_SECONDS}${adminOrigin(request).startsWith("https:") ? "; Secure" : ""}`;
}

export function privateHeaders(): Record<string, string> {
  return { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow" };
}

export function authFailure(error: unknown): Response {
  const fault = error instanceof AuthError ? error : new AuthError("ADMIN_AUTH_UNAVAILABLE", 503);
  const messages: Record<string, string> = {
    INVALID_CREDENTIALS: "The username or password is incorrect.",
    ADMIN_AUTH_NOT_CONFIGURED: "Admin access needs to be configured on this server.",
    ADMIN_ORIGIN_INVALID: "Admin access needs its website address configured correctly. Ask the website administrator to check setup.",
    ADMIN_AUTH_UNAVAILABLE: "Admin sign-in is temporarily unavailable. Try again shortly.",
    LOGIN_RATE_LIMITED: "Too many sign-in attempts. Try again in 15 minutes.",
    ADMIN_SIGN_IN_REQUIRED: "Sign in to continue.",
    SAME_ORIGIN_REQUIRED: "Open sign-in from this website and try again.",
    ADMIN_CSRF_REQUIRED: "Your session changed. Refresh the page and try again.",
    INVALID_INPUT: "Enter your username and password.",
  };
  return Response.json({ code: fault.code, message: messages[fault.code] ?? "The request could not be completed. Refresh and try again." }, {
    status: fault.status,
    headers: { ...privateHeaders(), ...(fault.status === 429 ? { "Retry-After": "900" } : {}) },
  });
}

export async function loginResponse(request: Request): Promise<Response> {
  try {
    assertSameOrigin(request);
    const body = await readSmallJson(request);
    if (Object.keys(body).some((key) => !["username", "password"].includes(key))
      || typeof body.username !== "string" || body.username.length > 128 || !body.username.trim()
      || typeof body.password !== "string" || !body.password || body.password.length > 1024) {
      throw new AuthError("INVALID_INPUT", 400);
    }
    const config = await readAdminConfiguration();
    const account = await authenticatePassword(body.username, body.password, config);
    const token = issueAdminToken(account, config);
    return Response.json({ ok: true }, { headers: { ...privateHeaders(), "Set-Cookie": adminCookie(token, request) } });
  } catch (error) {
    return authFailure(error);
  }
}

export async function logoutResponse(request: Request): Promise<Response> {
  try {
    authorizeAdminRequest(request, await readAdminConfiguration(), true);
    return Response.json({ ok: true }, { headers: { ...privateHeaders(), "Set-Cookie": adminCookie("", request, true) } });
  } catch (error) {
    return authFailure(error);
  }
}
