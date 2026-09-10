// Read-only signed-out checks of the explicitly selected production website.
// Mutation routes receive unauthenticated empty requests and must deny them.
import { mkdir, writeFile } from "node:fs/promises";

const origin = "https://www.maintainmedia.com.au";
const checks = [];
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const privateResponse = (response) => {
  const cache = response.headers.get("cache-control") || "";
  assert(cache.includes("private") && cache.includes("no-store"), "Private no-store response required");
  assert((response.headers.get("x-robots-tag") || "").includes("noindex"), "Noindex required");
  assert(response.headers.get("x-frame-options") === "DENY", "Framing must be denied");
};
async function check(name, route, expected, method = "GET") {
  try {
    const mutation = ["POST", "PATCH"].includes(method);
    const response = await fetch(origin + route, {
      method, redirect: "manual", signal: AbortSignal.timeout(20_000),
      headers: { Accept: "application/json", ...(mutation ? {
        Origin: origin, "Content-Type": "application/json", "X-Admin-CSRF": "invalid-verification-token",
      } : {}) },
      ...(mutation ? { body: "{}" } : {}),
    });
    try {
      assert(response.status === expected, `Expected ${expected}; received ${response.status}`);
      if (/^\/(?:sign-|abn-lead-gen|api\/abn-lead-gen)/.test(route)) privateResponse(response);
      if (expected === 307) {
        const target = new URL(response.headers.get("location") || "", origin);
        assert(target.origin === origin && target.pathname === "/sign-in", "Expected local sign-in redirect");
      }
      if (expected === 401 && method !== "HEAD") {
        const body = await response.json();
        assert(body.code === "ADMIN_SIGN_IN_REQUIRED", "Expected denial before engine access");
      }
      checks.push({ name, status: "passed", http_status: response.status });
    } finally { await response.body?.cancel().catch(() => {}); }
  } catch (error) {
    // Never include response bodies, cookies, credentials or native fetch error details.
    const allowed = /^(Expected |Private no-store |Noindex required|Framing must be denied)/;
    checks.push({ name, status: "failed", reason: error instanceof Error && allowed.test(error.message)
      ? error.message : "Request could not be verified within the HTTPS deadline" });
  }
}
const work = [];
for (const route of ["/", "/services", "/about", "/contact", "/sign-in", "/sign-up"]) {
  work.push(() => check(`Public ${route}`, route, 200));
}
for (const route of ["/abn-lead-gen/dashboard", "/abn-lead-gen/access"]) {
  work.push(() => check(`Signed-out ${route}`, route, 307));
}
const id = "00000000-0000-4000-8000-000000000001";
for (const [method, route] of [
  ["GET", "/dashboard"], ["HEAD", "/dashboard"], ["GET", `/jobs/${id}`],
  ["GET", `/reports/${id}/html`], ["GET", `/reports/${id}/csv`],
  ["GET", `/reports/${id}/markdown`], ["HEAD", `/reports/${id}/html`],
  ["PATCH", "/settings"], ["POST", "/runs"],
]) {
  work.push(() => check(`Denied ${method} ${route}`, "/api/abn-lead-gen" + route, 401, method));
}
// Bound concurrency to avoid a burst against the authentication provider.
await Promise.all(Array.from({ length: 3 }, async () => { while (work.length) await work.shift()(); }));
checks.sort((a, b) => a.name.localeCompare(b.name));
const failed = checks.filter(check => check.status === "failed").length;
const result = {
  checked_at: new Date().toISOString(), origin, status: failed ? "failed" : "passed",
  scope: "Deployed public/auth HTTP routes and signed-out access denial only. Does not certify signed-in admin workflows, an engine connection or live lead data.",
  total: checks.length, passed: checks.length - failed, failed, checks,
};
const directory = new URL("../acceptance/vercel/", import.meta.url);
await mkdir(directory, { recursive: true });
await writeFile(new URL("production-http.json", directory), JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify(result, null, 2));
if (failed) process.exitCode = 1;
