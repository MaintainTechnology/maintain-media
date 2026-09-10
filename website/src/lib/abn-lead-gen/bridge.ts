/** Server bridge for the fixture engine. Remote transport does not enable live data. */
import "server-only";
import { isIP } from "node:net";
import { randomUUID } from "node:crypto";
import { staffAssertion } from "./assertion.ts";

export type BridgeAdmin = { username: string; displayName: string; csrfToken: string; actorId?: string; scopes?: string[] };
export class BridgeError extends Error {
  code: string;
  status: number;
  constructor(code: string, status: number) {
    super(code);
    this.code = code;
    this.status = status;
  }
}

const uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const reportPath = new RegExp(`^/api/reports/(${uuid})/(html|csv|markdown)$`, "i");
const sitePrefix = "/api/abn-lead-gen";
export const privateHeaders = {
  "Cache-Control": "private, no-store, max-age=0",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow, noarchive",
  "Cross-Origin-Resource-Policy": "same-origin",
  "X-Frame-Options": "DENY",
};

export function parseBridgePath(parts: string[], method: string, live = false): string {
  const joined = parts.join("/");
  if (live) {
    if (method === "POST" && joined === "website-collections") return "/v1/website-collections";
    if (method === "GET" && new RegExp(`^website-jobs/${uuid}$`, "i").test(joined)) return `/api/${joined}`;
    if (["GET", "HEAD"].includes(method) && joined === "worklist.csv") return "/api/worklist.csv";
    if (method === "GET" && new RegExp(`^evidence/${uuid}$`, "i").test(joined)) return `/v1/${joined}`;
    if (method === "GET" && /^qbcc-reviews(?:\/(?:0|[1-9][0-9]{0,5}))?$/.test(joined)) return `/api/${joined}`;
    if (method === "POST" && ["suppressions", "crm-approvals", "identity-assessments", "licence-reviews", "basis-assessments", "qbcc-reviews", "operator-activities"].includes(joined)) return `/v1/${joined}`;
    if (method === "PATCH" && new RegExp(`^worklist-rows/${uuid}$`, "i").test(joined)) return `/v1/${joined}`;
  }
  const reads = joined === "dashboard" || new RegExp(`^jobs/${uuid}$`, "i").test(joined)
    || new RegExp(`^reports/${uuid}/(html|csv|markdown)$`, "i").test(joined);
  if ((method === "GET" || method === "HEAD") && reads) return `/api/${joined}`;
  if (method === "PATCH" && joined === "settings") return "/api/settings";
  if (method === "POST" && joined === "runs") return "/api/runs";
  throw new BridgeError("ROUTE_NOT_FOUND", 404);
}

type EngineConnection = { origin: string; token?: string; mode: "fixture" | "pilot" | "production" };

function engineConnection(): EngineConnection {
  try {
    const transport = process.env.ABN_ENGINE_TRANSPORT ?? "local";
    const mode = process.env.ABN_ENGINE_MODE ?? "fixture";
    if (!["fixture", "pilot", "production"].includes(mode)) throw new Error();
    const hosted = process.env.VERCEL === "1" || Boolean(process.env.VERCEL_ENV);
    if (transport !== "local" && transport !== "remote") throw new Error();
    // A hosted deployment must never silently try its own localhost as the engine.
    if (hosted && transport !== "remote") throw new Error();
    const raw = process.env.ABN_ENGINE_ORIGIN ?? (transport === "local" ? "http://127.0.0.1:8767" : "");
    if (raw !== raw.trim() || !/^https?:\/\/[^/?#\\\s]+\/?$/.test(raw)) throw new Error();
    const value = new URL(raw);
    if (value.username || value.password || value.pathname !== "/" || value.search || value.hash
      || value.port === "0") throw new Error();
    if (transport === "local") {
      if (mode !== "fixture") throw new Error();
      if (value.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(value.hostname)) throw new Error();
      return { origin: value.origin, mode };
    }
    const labels = value.hostname.split(".");
    const reserved = /(?:^|\.)(?:localhost|local|internal|lan|home|test|invalid|example|onion)$|(?:^|\.)home\.arpa$/;
    if (value.protocol !== "https:" || (value.port && value.port !== "443")
      || isIP(value.hostname.replace(/^\[|\]$/g, "")) || value.hostname.length > 253 || labels.length < 2 || reserved.test(value.hostname)
      || !/^[a-z]{2,63}$/.test(labels.at(-1) ?? "")
      || labels.some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) throw new Error();
    const token = mode === "fixture" ? process.env.ABN_ENGINE_TOKEN : process.env.ABN_ENGINE_ASSERTION_KEY;
    // Use a separately generated 32-byte (or longer) base64url service token.
    if (!token || token !== token.trim() || !/^[A-Za-z0-9_-]{43,256}$/.test(token)) throw new Error();
    return { origin: value.origin, token, mode: mode as EngineConnection["mode"] };
  } catch { throw new BridgeError("ENGINE_CONFIGURATION_INVALID", 503); }
}

export function engineOrigin(): string {
  return engineConnection().origin;
}

async function boundedText(input: Request | Response, limit: number): Promise<string> {
  if (Number(input.headers.get("content-length")) > limit) throw new BridgeError("BODY_TOO_LARGE", 413);
  const reader = input.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new BridgeError("BODY_TOO_LARGE", 413);
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks).toString("utf8");
}

export async function readJsonBody(request: Request, limit = 4096): Promise<string> {
  if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") {
    throw new BridgeError("JSON_REQUIRED", 415);
  }
  const text = await boundedText(request, limit);
  try {
    const value = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
  } catch { throw new BridgeError("INVALID_INPUT", 422); }
  return text;
}

type Sensitive = string | string[] | undefined;
async function engineText(response: Response, limit: number, token?: Sensitive): Promise<string> {
  const text = await boundedText(response, limit);
  // A misconfigured gateway must not reflect its credential into a download or API response.
  if ((Array.isArray(token) ? token : token ? [token] : []).some(secret => text.includes(secret))) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
  return text;
}

async function engineJson(response: Response, token?: Sensitive): Promise<Record<string, unknown>> {
  try {
    if (!response.headers.get("content-type")?.includes("application/json")) throw new Error();
    const value = JSON.parse(await engineText(response, 2_000_000, token));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    if ((Array.isArray(token) ? token : token ? [token] : []).some(secret => JSON.stringify(value).includes(secret))) throw new Error();
    return value;
  } catch { throw new BridgeError("ENGINE_INVALID_RESPONSE", 502); }
}

async function checkEngineError(response: Response, token?: Sensitive) {
  if (response.ok) return;
  // A failed service credential does not mean the browser's Clerk session expired.
  if (token && response.status === 401) throw new BridgeError("ENGINE_AUTHENTICATION_FAILED", 503);
  const value = await engineJson(response, token);
  const code = typeof value.code === "string" && /^[A-Z][A-Z0-9_]{1,95}$/.test(value.code)
    ? value.code : "ENGINE_REQUEST_FAILED";
  if (token && response.status === 403 && (code.startsWith("GATEWAY_")
    || code === "SAME_ORIGIN_REQUIRED" || code === "DASHBOARD_CSRF_REQUIRED")) {
    throw new BridgeError("ENGINE_AUTHENTICATION_FAILED", 503);
  }
  throw new BridgeError(code, response.status >= 400 && response.status < 600 ? response.status : 502);
}

export async function forwardLeadGen(request: Request, parts: string[], admin: BridgeAdmin, fetcher: typeof fetch = fetch): Promise<Response> {
  const { origin, token, mode } = engineConnection();
  const live = mode !== "fixture";
  const path = parseBridgePath(parts, request.method, live);
  const mutation = request.method === "POST" || request.method === "PATCH";
  const body = mutation ? await readJsonBody(request, live ? 65536 : 4096) : undefined;
  const secrets = token ? [token] : [];
  const requestId = randomUUID();
  const idempotencyKey = live && mutation ? request.headers.get("idempotency-key") ?? "" : "";
  if (live && mutation && !new RegExp(`^${uuid}$`, "i").test(idempotencyKey)) throw new BridgeError("REQUEST_IDENTIFIERS_REQUIRED", 422);
  const headers: Record<string, string> = { Accept: "application/json" };
  const invoke = async (url: string, init?: RequestInit) => {
    try {
      const upstreamHeaders = new Headers(init?.headers);
      if (token && live) {
        const assertion = staffAssertion(token, admin, init?.method ?? "GET", url, typeof init?.body === "string" ? init.body : "", requestId, idempotencyKey);
        secrets.push(assertion);
        upstreamHeaders.set("Authorization", `Bearer ${assertion}`);
        upstreamHeaders.set("X-Request-ID", requestId);
        if (idempotencyKey) upstreamHeaders.set("Idempotency-Key", idempotencyKey);
      } else if (token) upstreamHeaders.set("Authorization", `Bearer ${token}`);
      return await fetcher(origin + url, { ...init, headers: upstreamHeaders, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(8000) });
    } catch { throw new BridgeError("ENGINE_UNAVAILABLE", 503); }
  };
  if (mutation && !live) {
    const state = await invoke("/api/dashboard", { headers: { Accept: "application/json" } });
    await checkEngineError(state, token);
    const data = await engineJson(state, token);
    if (data.mode !== "fixture" || data.outreach !== "disabled"
      || typeof data.csrf_token !== "string" || !data.csrf_token) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
    headers["Origin"] = origin;
    headers["Content-Type"] = "application/json";
    headers["X-Dashboard-CSRF"] = data.csrf_token;
  }
  if (mutation && live) headers["Content-Type"] = "application/json";
  // Deliberately do not forward browser cookies, authorization, host or origin.
  const upstream = await invoke(path, { method: request.method === "HEAD" ? "GET" : request.method, headers, body });
  await checkEngineError(upstream, secrets.length ? secrets : undefined);
  if (path === "/api/worklist.csv") {
    if (!upstream.headers.get("content-type")?.startsWith("text/csv")) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
    const payload = await engineText(upstream, 3_000_000, secrets);
    return new Response(request.method === "HEAD" ? null : payload, { headers: { ...privateHeaders,
      "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="current-worklist.csv"' } });
  }
  const report = reportPath.exec(path);
  if (report) {
    const [, requestedRunId, kind] = report;
    const runId = requestedRunId.toLowerCase();
    const media = kind === "html" ? "text/html" : kind === "csv" ? "text/csv" : "text/markdown";
    if (!upstream.headers.get("content-type")?.startsWith(media)) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
    let payload = await engineText(upstream, 3_000_000, secrets);
    const oldLink = `/api/reports/${runId}/csv`;
    const newLink = `${sitePrefix}/reports/${runId}/csv`;
    if (kind === "html") payload = payload.replaceAll(`href="${oldLink}"`, `href="${newLink}"`);
    if (kind === "markdown") payload = payload.replaceAll(`](${oldLink})`, `](${newLink})`);
    const responseHeaders: Record<string, string> = { ...privateHeaders, "Content-Type": `${media}; charset=utf-8` };
    if (kind === "html") responseHeaders["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
    else responseHeaders["Content-Disposition"] = `attachment; filename="${kind === "csv" ? "worklist" : "report"}-${runId}.${kind === "csv" ? "csv" : "md"}"`;
    return new Response(request.method === "HEAD" ? null : payload, { headers: responseHeaders });
  }
  const data = await engineJson(upstream, secrets);
  delete data.csrf_token;
  if (path === "/api/dashboard") {
    if (data.mode !== mode || data.outreach !== "disabled" || !Array.isArray(data.runs)) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
    for (const run of data.runs) {
      if (!run || typeof run !== "object") throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
      if (run.reports && typeof run.reports === "object") {
        for (const kind of ["html", "csv", "markdown"]) {
          const link = run.reports[kind];
          run.reports[kind] = typeof link === "string" && reportPath.test(link)
            ? link.replace("/api/reports/", `${sitePrefix}/reports/`) : null;
        }
      }
    }
    data.admin = { username: admin.username, displayName: admin.displayName, csrfToken: admin.csrfToken };
  }
  return new Response(request.method === "HEAD" ? null : JSON.stringify(data), {
    status: upstream.status, headers: { ...privateHeaders, "Content-Type": "application/json" },
  });
}

export function bridgeFailure(error: unknown): Response {
  const typed = error as { code?: unknown; status?: unknown };
  const code = typeof typed?.code === "string" && /^[A-Z][A-Z0-9_]{1,95}$/.test(typed.code) ? typed.code : "ENGINE_UNAVAILABLE";
  const status = Number.isInteger(typed?.status) && Number(typed.status) >= 400 && Number(typed.status) <= 599 ? Number(typed.status) : 503;
  return Response.json({ code }, { status, headers: privateHeaders });
}
