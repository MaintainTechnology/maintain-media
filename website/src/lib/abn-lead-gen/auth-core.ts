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
  actorId?: string;
  scopes?: string[];
  username: string;
  displayName: string;
  csrfToken: string;
};

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

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function privateHeaders(): Record<string, string> {
  return { "Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow", "X-Frame-Options": "DENY" };
}

export function authFailure(error: unknown): Response {
  const fault = error instanceof AuthError ? error : new AuthError("ADMIN_AUTH_UNAVAILABLE", 503);
  const messages: Record<string, string> = {
    ADMIN_AUTH_NOT_CONFIGURED: "Clerk sign-in needs to be configured on this server.",
    ADMIN_ORIGIN_INVALID: "The admin workspace address needs to be configured correctly.",
    ADMIN_AUTH_UNAVAILABLE: "Admin access is temporarily unavailable. Try again shortly.",
    ADMIN_SIGN_IN_REQUIRED: "Sign in to continue.",
    ADMIN_ACCESS_REQUIRED: "Your account needs Maintain Media administrator access.",
    SAME_ORIGIN_REQUIRED: "Open the admin workspace from this website and try again.",
    ADMIN_CSRF_REQUIRED: "Your session changed. Refresh the page and try again.",
    INVALID_INPUT: "Check the submitted values and try again.",
  };
  return Response.json({ code: fault.code, message: messages[fault.code] ?? "The request could not be completed. Refresh and try again." }, {
    status: fault.status, headers: privateHeaders(),
  });
}

/** Legacy credentials and cookies are intentionally never inspected or accepted. */
export function retiredPasswordAuthResponse(): Response {
  return Response.json({ code: "CLERK_AUTH_REQUIRED", message: "Local password authentication has been retired. Use Maintain Media Clerk sign-in and account controls.", signInUrl: "/sign-in" }, {
    status: 410, headers: privateHeaders(),
  });
}
