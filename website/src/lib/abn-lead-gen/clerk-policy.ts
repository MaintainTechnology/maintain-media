import { createHmac, timingSafeEqual } from "node:crypto";
import type { AdminSession } from "./auth-core";

/** Inputs must come from verified Clerk server APIs, never a browser-supplied user object. */
export type ClerkSessionIdentity = {
  userId: string | null;
  sessionId: string | null;
};

/** The same public error contract used by the existing private API bridge. */
export class ClerkPolicyError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, status: number) {
    super(code);
    this.name = "ClerkPolicyError";
    this.code = code;
    this.status = status;
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function verifiedIdentity(identity: ClerkSessionIdentity | null): asserts identity is {
  userId: string; sessionId: string;
} {
  if (!identity || typeof identity.userId !== "string" || !/^user_[A-Za-z0-9]{1,200}$/.test(identity.userId)
    || typeof identity.sessionId !== "string" || !/^sess_[A-Za-z0-9]{1,200}$/.test(identity.sessionId)) {
    throw new ClerkPolicyError("ADMIN_SIGN_IN_REQUIRED", 401);
  }
}

/** A stable per-session token, independent of Clerk's frequently refreshed session JWT. */
export function createClerkCsrfToken(identity: ClerkSessionIdentity | null, secret: string | undefined): string {
  verifiedIdentity(identity);
  if (typeof secret !== "string" || secret !== secret.trim() || /[\r\n\0]/.test(secret)
    || Buffer.byteLength(secret, "utf8") < 32 || Buffer.byteLength(secret, "utf8") > 4096) {
    throw new ClerkPolicyError("ADMIN_AUTH_NOT_CONFIGURED", 503);
  }
  return createHmac("sha256", secret)
    .update(`maintain-media:abn-admin:csrf:v1\0${identity.userId}\0${identity.sessionId}`)
    .digest("base64url");
}

function label(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const result = value.trim();
  return result && result.length <= 200 && !/[\u0000-\u001f\u007f]/.test(result) ? result : null;
}

/** Only current, server-managed application authority grants access to the shared workspace. */
export function authorizeClerkAdmin(
  identity: ClerkSessionIdentity | null,
  user: unknown,
  secret: string | undefined,
): AdminSession {
  verifiedIdentity(identity);
  if (!record(user) || user.id !== identity.userId || user.banned !== false || user.locked !== false
    || !record(user.publicMetadata) || user.publicMetadata.role !== "admin"
    || (user.publicMetadata.enabled !== undefined && user.publicMetadata.enabled !== true)
    || (user.publicMetadata.disabled !== undefined && user.publicMetadata.disabled !== false)) {
    throw new ClerkPolicyError("ADMIN_ACCESS_REQUIRED", 403);
  }
  const username = label(user.username) ?? identity.userId;
  const name = [label(user.firstName), label(user.lastName)].filter(Boolean).join(" ");
  const assigned = user.publicMetadata.leadGenScopes;
  const allowed = new Set(["reviewer", "owner", "compliance"]);
  if (assigned !== undefined && (!Array.isArray(assigned) || assigned.some(scope => typeof scope !== "string" || !allowed.has(scope)))) {
    throw new ClerkPolicyError("ADMIN_ACCESS_REQUIRED", 403);
  }
  return {
    actorId: identity.userId,
    scopes: ["admin", "operator", ...new Set(assigned as string[] | undefined)],
    username,
    displayName: label(user.fullName) ?? label(name) ?? username,
    csrfToken: createClerkCsrfToken(identity, secret),
  };
}

/** Call the existing same-origin guard as well before admitting a mutation. */
export function assertClerkCsrf(request: Request, session: AdminSession): void {
  const actual = request.headers.get("x-admin-csrf") ?? "";
  const expected = session.csrfToken;
  if (!/^[A-Za-z0-9_-]{43}$/.test(actual) || !/^[A-Za-z0-9_-]{43}$/.test(expected)
    || !timingSafeEqual(Buffer.from(actual), Buffer.from(expected))) {
    throw new ClerkPolicyError("ADMIN_CSRF_REQUIRED", 403);
  }
}
