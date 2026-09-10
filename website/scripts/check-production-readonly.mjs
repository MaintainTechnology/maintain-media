// Fixed public origin; GET/HEAD only, no cookies, tokens or mutable requests.
import { mkdir, writeFile } from "node:fs/promises";

const deploymentId = process.argv[2];
if (!/^dpl_[A-Za-z0-9]{20,60}$/.test(deploymentId || "")) throw new Error("Exact deployment ID required");
const origin = "https://www.maintainmedia.com.au";
const paths = [
  ["/", 200], ["/services", 200], ["/about", 200], ["/contact", 200],
  ["/sign-in", 200], ["/sign-up", 200],
  ["/abn-lead-gen/dashboard", 307], ["/abn-lead-gen/access", 307],
  ["/api/abn-lead-gen/dashboard", 401],
  ["/api/abn-lead-gen/dashboard", 401, "HEAD"],
  ["/api/abn-lead-gen/jobs/00000000-0000-4000-8000-000000000001", 401],
  ["/api/abn-lead-gen/reports/00000000-0000-4000-8000-000000000001/csv", 401],
];
const checks = [];
const work = [...paths];
await Promise.all(Array.from({ length: 3 }, async () => {
  while (work.length) {
    const [path, expected, method = "GET"] = work.shift();
    try {
      const response = await fetch(origin + path, { method, redirect: "manual", credentials: "omit",
        headers: { Accept: "application/json" }, signal: AbortSignal.timeout(20_000) });
      const actual = response.status;
      const privateRoute = path.startsWith("/sign-") || path.startsWith("/abn-lead-gen") || path.startsWith("/api/abn-lead-gen");
      const privacy = !privateRoute || (response.headers.get("cache-control")?.includes("private")
        && response.headers.get("cache-control")?.includes("no-store")
        && response.headers.get("x-robots-tag")?.includes("noindex")
        && response.headers.get("x-frame-options") === "DENY");
      let redirect = true;
      if (expected === 307) {
        const location = new URL(response.headers.get("location") || "", origin);
        redirect = location.origin === origin && location.pathname === "/sign-in";
      }
      let deniedBeforeEngine = true;
      if (expected === 401 && actual === 401 && method === "GET") {
        const body = await response.json();
        deniedBeforeEngine = body.code === "ADMIN_SIGN_IN_REQUIRED";
      } else await response.body?.cancel();
      checks.push({ path, method, status: actual === expected && privacy && redirect && deniedBeforeEngine ? "passed" : "failed",
        http_status: actual, expected_status: expected, private_headers: Boolean(privacy),
        local_signin_redirect: redirect, denied_before_engine: deniedBeforeEngine });
    } catch {
      checks.push({ path, method, status: "failed", reason: "HTTPS response could not be verified within deadline" });
    }
  }
}));
checks.sort((a, b) => (a.path + a.method).localeCompare(b.path + b.method));
const passed = checks.filter(row => row.status === "passed").length;
const receipt = { checked_at: new Date().toISOString(), origin, deployment_id: deploymentId,
  status: passed === checks.length ? "passed" : "failed", passed, total: checks.length,
  scope: "Public and signed-out GET/HEAD only. Alias identity requires a separate Vercel inspection. No browser login or business-data flow certified.",
  provider_mutations: false, requests_with_credentials: 0, checks };
const directory = new URL("../acceptance/vercel/", import.meta.url);
await mkdir(directory, { recursive: true });
await writeFile(new URL(deploymentId + "-http.json", directory), JSON.stringify(receipt, null, 2) + "\n", { flag: "wx" });
console.log(JSON.stringify(receipt, null, 2));
if (passed !== checks.length) process.exitCode = 1;
