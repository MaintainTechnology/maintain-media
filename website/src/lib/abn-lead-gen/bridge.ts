/** Server bridge for the existing co-located fixture engine. Never an open proxy. */
export type BridgeAdmin = { username: string; displayName: string; csrfToken: string };
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

export function parseBridgePath(parts: string[], method: string): string {
  const joined = parts.join("/");
  const reads = joined === "dashboard" || new RegExp(`^jobs/${uuid}$`, "i").test(joined)
    || new RegExp(`^reports/${uuid}/(html|csv|markdown)$`, "i").test(joined);
  if ((method === "GET" || method === "HEAD") && reads) return `/api/${joined}`;
  if (method === "PATCH" && joined === "settings") return "/api/settings";
  if (method === "POST" && joined === "runs") return "/api/runs";
  throw new BridgeError("ROUTE_NOT_FOUND", 404);
}

export function engineOrigin(): string {
  try {
    const value = new URL(process.env.ABN_ENGINE_ORIGIN || "http://127.0.0.1:8767");
    if (value.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(value.hostname)
      || value.username || value.password || value.pathname !== "/" || value.search || value.hash
      || value.port === "0") throw new Error();
    return value.origin;
  } catch { throw new BridgeError("ENGINE_CONFIGURATION_INVALID", 503); }
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

export async function readJsonBody(request: Request): Promise<string> {
  if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") {
    throw new BridgeError("JSON_REQUIRED", 415);
  }
  const text = await boundedText(request, 4096);
  try {
    const value = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
  } catch { throw new BridgeError("INVALID_INPUT", 422); }
  return text;
}

async function engineJson(response: Response): Promise<Record<string, unknown>> {
  try {
    if (!response.headers.get("content-type")?.includes("application/json")) throw new Error();
    const value = JSON.parse(await boundedText(response, 2_000_000));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    return value;
  } catch { throw new BridgeError("ENGINE_INVALID_RESPONSE", 502); }
}

async function checkEngineError(response: Response) {
  if (response.ok) return;
  const value = await engineJson(response);
  const code = typeof value.code === "string" && /^[A-Z][A-Z0-9_]{1,95}$/.test(value.code)
    ? value.code : "ENGINE_REQUEST_FAILED";
  throw new BridgeError(code, response.status >= 400 && response.status < 600 ? response.status : 502);
}

export async function forwardLeadGen(request: Request, parts: string[], admin: BridgeAdmin, fetcher: typeof fetch = fetch): Promise<Response> {
  const path = parseBridgePath(parts, request.method);
  const origin = engineOrigin();
  const mutation = request.method === "POST" || request.method === "PATCH";
  const body = mutation ? await readJsonBody(request) : undefined;
  const headers: Record<string, string> = { Accept: "application/json" };
  const invoke = async (url: string, init?: RequestInit) => {
    try {
      return await fetcher(origin + url, { ...init, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(8000) });
    } catch { throw new BridgeError("ENGINE_UNAVAILABLE", 503); }
  };
  if (mutation) {
    const state = await invoke("/api/dashboard", { headers: { Accept: "application/json" } });
    await checkEngineError(state);
    const data = await engineJson(state);
    if (typeof data.csrf_token !== "string" || !data.csrf_token) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
    headers["Origin"] = origin;
    headers["Content-Type"] = "application/json";
    headers["X-Dashboard-CSRF"] = data.csrf_token;
  }
  // Deliberately do not forward browser cookies, authorization, host or origin.
  const upstream = await invoke(path, { method: request.method === "HEAD" ? "GET" : request.method, headers, body });
  await checkEngineError(upstream);
  const report = reportPath.exec(path);
  if (report) {
    const [, requestedRunId, kind] = report;
    const runId = requestedRunId.toLowerCase();
    const media = kind === "html" ? "text/html" : kind === "csv" ? "text/csv" : "text/markdown";
    if (!upstream.headers.get("content-type")?.startsWith(media)) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
    let payload = await boundedText(upstream, 3_000_000);
    const oldLink = `/api/reports/${runId}/csv`;
    const newLink = `${sitePrefix}/reports/${runId}/csv`;
    if (kind === "html") payload = payload.replaceAll(`href="${oldLink}"`, `href="${newLink}"`);
    if (kind === "markdown") payload = payload.replaceAll(`](${oldLink})`, `](${newLink})`);
    const responseHeaders: Record<string, string> = { ...privateHeaders, "Content-Type": `${media}; charset=utf-8` };
    if (kind === "html") responseHeaders["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
    else responseHeaders["Content-Disposition"] = `attachment; filename="${kind === "csv" ? "worklist" : "report"}-${runId}.${kind === "csv" ? "csv" : "md"}"`;
    return new Response(request.method === "HEAD" ? null : payload, { headers: responseHeaders });
  }
  const data = await engineJson(upstream);
  delete data.csrf_token;
  if (path === "/api/dashboard") {
    if (data.mode !== "fixture" || data.outreach !== "disabled" || !Array.isArray(data.runs)) throw new BridgeError("ENGINE_INVALID_RESPONSE", 502);
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
    data.admin = admin;
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
