import { AuthError, assertSameOrigin, type AdminSession } from "./auth-core";
import { authorizeClerkAdmin, assertClerkCsrf, ClerkPolicyError, type ClerkSessionIdentity } from "./clerk-policy";

export type AdminAccess =
  | { status: "admin"; admin: AdminSession }
  | { status: "signed-out" }
  | { status: "forbidden" }
  | { status: "unavailable"; code: "ADMIN_AUTH_UNAVAILABLE" | "ADMIN_AUTH_NOT_CONFIGURED" };

/** Production supplies only Clerk's verified auth and server SDK methods. Tests replace this I/O boundary. */
export type ClerkAccessBackend = {
  authenticate: () => Promise<ClerkSessionIdentity | null>;
  getSession: (id: string) => Promise<unknown>;
  getUser: (id: string) => Promise<unknown>;
  secret: string | undefined;
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function readCurrentAccess(backend: ClerkAccessBackend): Promise<AdminAccess> {
  const identity = await backend.authenticate();
  if (!identity?.userId || !identity.sessionId) return { status: "signed-out" };
  if (!/^user_[A-Za-z0-9]{1,200}$/.test(identity.userId) || !/^sess_[A-Za-z0-9]{1,200}$/.test(identity.sessionId)) {
    return { status: "signed-out" };
  }
  let session: unknown;
  let user: unknown;
  try {
    [session, user] = await Promise.all([backend.getSession(identity.sessionId), backend.getUser(identity.userId)]);
  } catch (error) {
    // A deleted Clerk user/session cannot retain access. Other provider errors are outages, not valid sessions.
    if (record(error) && error.status === 404) return { status: "signed-out" };
    throw error;
  }
  if (!record(session) || typeof session.status !== "string"
    || typeof session.expireAt !== "number" || !Number.isFinite(session.expireAt)
    || typeof session.abandonAt !== "number" || !Number.isFinite(session.abandonAt)) {
    return { status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" };
  }
  if (session.id !== identity.sessionId || session.userId !== identity.userId || session.status !== "active"
    || session.expireAt <= Date.now() || session.abandonAt <= Date.now()) {
    return { status: "signed-out" };
  }
  return { status: "admin", admin: authorizeClerkAdmin(identity, user, backend.secret) };
}

/** Bound provider waiting and expose only known errors, never SDK responses, keys or stack traces. */
export async function resolveClerkAdminAccess(backend: ClerkAccessBackend, timeoutMs = 8000): Promise<AdminAccess> {
  let deadline: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      readCurrentAccess(backend),
      new Promise<never>((_, reject) => {
        deadline = setTimeout(() => reject(new Error("Clerk lookup deadline")), timeoutMs);
      }),
    ]);
  } catch (error) {
    if (error instanceof ClerkPolicyError) {
      if (error.status === 401) return { status: "signed-out" };
      if (error.status === 403) return { status: "forbidden" };
      if (error.code === "ADMIN_AUTH_NOT_CONFIGURED") return { status: "unavailable", code: error.code };
    }
    return { status: "unavailable", code: "ADMIN_AUTH_UNAVAILABLE" };
  } finally {
    clearTimeout(deadline);
  }
}

export function requireAdminAccess(access: AdminAccess): AdminSession {
  if (access.status === "admin") return access.admin;
  if (access.status === "signed-out") throw new AuthError("ADMIN_SIGN_IN_REQUIRED", 401);
  if (access.status === "forbidden") throw new AuthError("ADMIN_ACCESS_REQUIRED", 403);
  throw new AuthError(access.code, 503);
}

export function authorizeClerkRequest(request: Request, access: AdminAccess, mutation = false): AdminSession {
  const admin = requireAdminAccess(access);
  if (mutation) {
    assertSameOrigin(request);
    try { assertClerkCsrf(request, admin); }
    catch { throw new AuthError("ADMIN_CSRF_REQUIRED", 403); }
  }
  return admin;
}
