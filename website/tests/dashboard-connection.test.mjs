import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Render the actual dashboard with bounded account/engine doubles. These checks
// verify connection-state controls and copy, not a real Clerk session or engine.
const require = createRequire(import.meta.url);
function compile(relativePath, imports = {}) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  });
  const compiledModule = { exports: {} };
  new Function("require", "exports", "module", outputText)(
    name => Object.hasOwn(imports, name) ? imports[name] : require(name), compiledModule.exports, compiledModule,
  );
  return compiledModule.exports;
}

const types = compile("../src/lib/abn-lead-gen/types.ts");
const readiness = compile("../src/components/abn-lead-gen/readiness.ts");
const dashboardHook = compile("../src/components/abn-lead-gen/use-dashboard.ts", {
  "@/lib/abn-lead-gen/types": types, "@clerk/nextjs": {},
});
const workflow = compile("../src/components/abn-lead-gen/live-workflow.tsx", {
  "@/lib/abn-lead-gen/types": types, "./dashboard.module.css": {}, "./use-dashboard": dashboardHook, "./readiness": readiness,
});
const UserButton = ({ children }) => React.createElement("div", null, children);
UserButton.MenuItems = function TestUserMenu({ children }) { return React.createElement("div", null, children); };
UserButton.Action = function TestUserAction({ label }) { return React.createElement("button", null, label); };
let state;
const { LeadGenDashboard } = compile("../src/components/abn-lead-gen/dashboard.tsx", {
  "next/image": props => {
    const htmlProps = { ...props };
    delete htmlProps.priority;
    return React.createElement("img", htmlProps);
  },
  "next/link": props => {
    const htmlProps = { ...props };
    delete htmlProps.prefetch;
    delete htmlProps.onNavigate;
    return React.createElement("a", htmlProps);
  },
  "@clerk/nextjs": { UserButton },
  "@/lib/abn-lead-gen/types": types,
  "./use-dashboard": { useDashboard: () => state, errorMessage: dashboardHook.errorMessage },
  "./live-workflow": workflow,
  "./readiness": readiness,
  "./dashboard.module.css": {},
});

test("live empty workspace preserves zero and blocked worker without demo claims", () => {
  const html = render({ ...fixture, mode: "pilot", run_enabled: false, scopes: ["admin", "operator"], runs: [], sources: [{ source: "qbcc", status: "not_collected" }], budget: { effective_cap_micro_aud: 0, frozen: false } }, true);
  assert.match(html, /Live workspace/);
  assert.doesNotMatch(html, /Run demo|Sample data|sample businesses|Demo runs/);
  assert.match(html, /No businesses have been qualified yet/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.match(button, /disabled/);
  assert.match(html, /explicitly assigned reviewer role/);
});

test("live reviewer can see actual worklist and optout controls with explicit evidence fields", () => {
  const html = render({ ...fixture, mode: "pilot", run_enabled: true, scopes: ["admin", "operator", "reviewer"],
    leads: [{ lead_id: runId, source: "qbcc", business_name: "Stored test business", revision: 1, row_id: runId, row_version: 1 }],
    sources: [{ source: "qbcc", status: "accepted" }] }, true);
  assert.match(html, /Stored test business/);
  assert.match(html, /Do not contact this business/);
  assert.match(html, /Save outcome/);
  assert.match(html, /Save identity review/);
  assert.match(html, /Save CRM decision/);
  assert.match(html, /Load source records/);
  assert.doesNotMatch(html, /Run demo|Sample data/);
});

test("held publisher download explains this run without hiding previously accepted records", () => {
  const previousRun = "00000000-0000-4000-8000-000000000002";
  const html = render({ ...fixture, mode: "pilot", run_enabled: true, settings: { ...fixture.settings, default_source: "qbcc" }, scopes: ["admin"],
    summary: { total_leads: 1, selected: 0, needs_review: 1 },
    leads: [{ lead_id: previousRun, source: "qbcc", business_name: "Previously accepted business" }],
    sources: [{ source: "qbcc", status: "accepted", can_run: true, reason_codes: [] }],
    latest_job: { job_id: runId, run_id: runId, source: "qbcc", state: "held", error_code: "QBCC_SOURCE_HTTP_REJECTED" },
    runs: [{ run_id: runId, source: "qbcc", status: "held" }, { run_id: previousRun, source: "qbcc", status: "complete" }],
  }, true);
  const notice = html.match(/<div id="active-run"[\s\S]*?<\/p>/)?.[0];
  assert.ok(notice);
  assert.match(notice, /publisher did not return a usable source file for this run/);
  assert.match(notice, /No records from this run were accepted/);
  assert.doesNotMatch(notice, /approval|Review the setup|QBCC SOURCE HTTP REJECTED|no business data|all records/i);
  assert.match(html, /Previously accepted business/);
  assert.match(html, /id="total-leads">1</);
  assert.match(html, /state-held/);
  assert.match(html, /state-complete/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.doesNotMatch(button, /disabled/);
});

test("request errors share the publisher explanation while other errors keep their own meaning", () => {
  assert.match(dashboardHook.errorMessage("QBCC_SOURCE_HTTP_REJECTED", "Fallback"), /No records from this run were accepted/);
  assert.match(dashboardHook.errorMessage("GATE_G1_CLOSED", "Fallback"), /required approval evidence/);
  assert.equal(dashboardHook.errorMessage("UNRECOGNISED_ERROR", "Fallback"), "Fallback");
});

test("real disabled capability rows render next steps, named owners and native expandable engine details", () => {
  const setup = ["collection", "crm", "abr"].map(id => ({ id, label: id, status: "blocked", detail: "Required evidence: CAPABILITY_DISABLED" }));
  const html = render({ ...fixture, mode: "pilot", run_enabled: false, scopes: ["admin"], runs: [], setup }, true);
  assert.equal((html.match(/<summary>Engine check details<\/summary>/g) || []).length, 3);
  assert.equal((html.match(/Next step · who can help/g) || []).length, 3);
  assert.match(html, /Collecting business records is switched off/);
  assert.match(html, /Business owner or authorised delegate/);
  assert.match(html, /Sending approved leads to GoHighLevel is switched off/);
  assert.match(html, /100-record matching review/);
  assert.match(html, /Saving run defaults does not switch on collection/);
  assert.doesNotMatch(html, /<details[^>]* open/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.match(button, /disabled/);
});

test("approved readiness remains scoped to its row and an unknown engine observation is escaped", () => {
  const html = render({ ...fixture, mode: "pilot", run_enabled: false, scopes: ["admin"], setup: [
    { id: "collection", label: "Collection", status: "approved", detail: "Current capability evidence is recorded." },
    { id: "future", label: "Future check", status: "unknown", detail: "<script>untrusted()</script>" },
  ] }, true);
  assert.match(html, /Approvals recorded/);
  assert.match(html, /Not verified/);
  assert.match(html, /&lt;script&gt;untrusted\(\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>untrusted/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.match(button, /disabled/);
});

test("stored QBCC data has publisher/licence attribution and adaptation context in both views", () => {
  const html = render({ ...fixture, mode: "pilot", run_enabled: true, scopes: ["admin"], runs: [],
    sources: [{ source: "qbcc", status: "accepted", source_published_at: "2026-09-10" }],
    setup: [{ id: "collection", label: "Business source collection", status: "approved", detail: "Current QBCC-only pilot decision." }],
  }, true);
  const source = "https://www.data.qld.gov.au/dataset/qbcc-licensed-contractors-register/resource/25608781-b28c-44f8-8545-0ab18d84082f";
  assert.equal(html.split(`href="${source}"`).length - 1, 2);
  assert.equal(html.split('href="https://creativecommons.org/licenses/by/4.0/"').length - 1, 2);
  assert.match(html, /State of Queensland \(Queensland Building and Construction Commission\)/);
  assert.match(html, /Reformatted and filtered by Maintain Media/);
  assert.match(html, /No QBCC endorsement/);
  assert.match(html, /Current QBCC-only pilot decision/);
  assert.doesNotMatch(html, /\bJon\b|Pepper/);
});

test("fixture and uncollected source states do not claim that their records came from QBCC", () => {
  for (const data of [
    { ...fixture, sources: [{ source: "qbcc", status: "accepted" }] },
    { ...fixture, mode: "pilot", scopes: [], run_enabled: true, sources: [{ source: "qbcc", status: "not_collected" }] },
  ]) {
    assert.doesNotMatch(render(data, true), /creativecommons.org|Reformatted and filtered by Maintain Media/);
  }
});

test("stored QBCC leads retain attribution after the current source snapshot has expired", () => {
  const html = render({ ...fixture, mode: "pilot", scopes: [], run_enabled: false,
    leads: [{ lead_id: runId, source: "qbcc", business_name: "Stored test record" }],
    sources: [{ source: "qbcc", status: "not_collected" }],
  }, true);
  assert.match(html, /creativecommons.org\/licenses\/by\/4.0\//);
  assert.match(html, /QBCC Licensed Contractors Register/);
});

test("permission drafts retain their opening revision across refresh and require explicit reload", async () => {
  const hookValues = [];
  let hookIndex = 0;
  const hookReact = { ...React, useState(initial) {
    const index = hookIndex++;
    if (!(index in hookValues)) hookValues[index] = initial;
    return [hookValues[index], value => { hookValues[index] = typeof value === "function" ? value(hookValues[index]) : value; }];
  } };
  const { PermissionForm } = compile("../src/components/abn-lead-gen/live-workflow.tsx", {
    react: hookReact, "@/lib/abn-lead-gen/types": types, "./dashboard.module.css": {}, "./use-dashboard": dashboardHook, "./readiness": readiness,
  });
  const contact = { contact_id: "contact-1", provenance_id: "capture-1", revision: 3, channel: "email" };
  const saves = [];
  const renderForm = revision => { hookIndex = 0; return PermissionForm({ contact: { ...contact, revision }, disabled: false, save: async (_, body) => saves.push(body) }); };
  const first = renderForm(3);
  assert.equal(first.props.children[0], false);
  const refreshed = renderForm(4);
  assert.ok(refreshed.props.children[0]);
  const originalFormData = globalThis.FormData;
  globalThis.FormData = class { get(name) { return name === "reason" ? "Checked evidence" : "unknown"; } };
  try {
    refreshed.props.children[1].props.onSubmit({ preventDefault() {}, currentTarget: {} });
    assert.equal(saves[0].expected_revision, 3);
    refreshed.props.children[0].props.children[1].props.onClick();
    const reloaded = renderForm(4);
    assert.equal(reloaded.props.children[0], false);
    reloaded.props.children[1].props.onSubmit({ preventDefault() {}, currentTarget: {} });
    assert.equal(saves[1].expected_revision, 4);
    assert.notEqual(reloaded.props.children[1].key, refreshed.props.children[1].key);
  } finally { globalThis.FormData = originalFormData; }
});
function render(data, connected, loading = false) {
  state = {
    data, connected, loading, configurationRequired: !data,
    source: "all", cap: "", dirty: true, saveStatus: "",
    refresh() {}, beginRun() {}, logout() {},
  };
  return renderToStaticMarkup(React.createElement(LeadGenDashboard, {
    admin: { username: "admin@example.test", displayName: "Test admin", csrfToken: "test" },
  }));
}
const tag = (html, id) => html.match(new RegExp(`<[^>]+id="${id}"[^>]*>`))?.[0];
const runId = "00000000-0000-4000-8000-000000000001";
const fixture = {
  mode: "fixture", summary: { total_leads: 0, selected: 0, needs_review: 0 },
  settings: { default_source: "all", monthly_cap_micro_aud: 0 },
  runs: [{ run_id: runId, source: "all", status: "complete", reports: Object.fromEntries(
    ["html", "csv", "markdown"].map(kind => [kind, `/api/abn-lead-gen/reports/${runId}/${kind}`]),
  ) }],
  leads: [], sources: [], setup: [],
};

const abrSource = { source: "abr", status: "accepted", can_run: true, reason_codes: [], capability: "abr", record_count: 12345, baseline: true, classification: "disabled", source_published_at: null, publisher_extract_time: "20260910010000" };
const abrJob = { job_id: runId, run_id: runId, source: "abr", state: "complete", phase: "complete", reason_codes: [], result: { snapshot_id: runId, baseline: true, noop: false, events: 0, candidates: 0, classification: "disabled", record_count: 12345, source_published_at: null, publisher_extract_time: "20260910010000" } };
const abrData = () => ({ ...fixture, outreach: "disabled", mode: "pilot", run_enabled: true, scopes: ["admin"], settings: { ...fixture.settings, default_source: "abr" }, sources: [abrSource], latest_job: abrJob, runs: [{ ...abrJob, status: "complete" }] });

test("accepted ABR baseline displays actual source counts and zero events, not newly formed leads", () => {
  const html = render(abrData(), true);
  assert.match(html, /ABR baseline accepted/);
  assert.match(html, /zero new-business events and zero leads/);
  assert.match(html, /12,345/);
  assert.match(html, /Matching disabled: the separate 100-record accuracy review/);
  assert.match(html, /Publisher extract time \(as supplied\): 20260910010000/);
  assert.match(html, /CC BY 3.0 Australia/);
  assert.match(html, /Source receipt only/);
  assert.doesNotMatch(html, /Preparing report|four measured weeks/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.doesNotMatch(button, /disabled/);
});

test("source-specific current checks control runs and unknown permission never borrows the other source", () => {
  for (const source of [{ ...abrSource, can_run: false }, { ...abrSource, reason_codes: ["GATE_G1_CLOSED"] }, { source: "abr", status: "accepted" }]) {
    const data = { ...abrData(), sources: [source, { ...abrSource, source: "qbcc" }] };
    assert.equal(types.sourceRunAllowed(data), false);
    const html = render(data, true);
    for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.match(button, /disabled/);
  }
  assert.equal(types.sourceRunAllowed({ ...abrData(), settings: { ...fixture.settings, default_source: "all" } }), false);
  assert.equal(types.sourceRunAllowed(fixture), true);
});

test("ABR in-progress and history-gap receipts preserve the accepted list without a false baseline", () => {
  const active = { ...abrJob, state: "running", phase: "parsing", result: null };
  let html = render({ ...abrData(), active_job: active }, true);
  assert.match(html, /engine is checking the ABR publication/);
  const notice = html.match(/<div id="active-run"[\s\S]*?<div class=" section-heading/)?.[0] || html;
  assert.doesNotMatch(notice, /ABR baseline accepted/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.match(button, /disabled/);
  html = render({ ...abrData(), latest_job: { ...abrJob, state: "held", phase: "held", result: null, error_code: "PRIOR_ARTIFACT_EXPIRED_REBASELINE_REQUIRED" } }, true);
  assert.match(html, /operator must review and explicitly establish a new baseline/);
  assert.doesNotMatch(html, /This report has expired/);
  assert.match(html, /12,345/);
});

test("completed ABR receipts distinguish actual differences, no change and unknown results", () => {
  const baseline = readiness.sourceJobGuidance(abrJob);
  assert.match(baseline.title, /baseline accepted/);
  const changed = readiness.sourceJobGuidance({ ...abrJob, result: { baseline: false, noop: false, events: 21, candidates: 0, classification: "disabled" } });
  assert.match(changed.detail, /21 registration changes observed; 0 lead candidates/);
  assert.match(changed.detail, /not proof of a newly formed business/);
  assert.match(readiness.sourceJobGuidance({ ...abrJob, result: { baseline: true, noop: true, events: 0, candidates: 0 } }).title, /unchanged/);
  for (const result of [null, {}, { baseline: true }, { noop: true }]) assert.match(readiness.sourceJobGuidance({ ...abrJob, result }).title, /result details not verified/);
});

test("source DTO accepts genuine zero counts but rejects malformed permission or receipt fields", () => {
  assert.equal(types.validDashboard(abrData()), true);
  assert.equal(types.validJob(abrJob), true);
  for (const result of [{ events: -1 }, { record_count: "12345" }, { baseline: "true" }, { candidates: 0.5 }, { publisher_extract_time: 123 }]) assert.equal(types.validJob({ ...abrJob, result }), false);
  for (const source of [{ ...abrSource, can_run: "true" }, { ...abrSource, reason_codes: "approved" }, { ...abrSource, record_count: -1 }]) assert.equal(types.validDashboard({ ...abrData(), sources: [source] }), false);
  assert.match(dashboardHook.errorMessage("EXACT_LIVE_SOURCE_REQUIRED", "fallback"), /Choose one live source/);
  const expired = dashboardHook.errorMessage("ABR_LIVE_CONFIGURATION_EXPIRED", "fallback");
  assert.match(expired, /ABR validation configuration/);
  assert.doesNotMatch(expired, /report has expired/);
});

function SourceHook(t, data) {
  const refs = [];
  const hooks = { useRef(value) { const ref = { current: value }; refs.push(ref); return ref; }, useState(value) { return [value, () => {}]; }, useCallback(callback) { return callback; }, useEffect() {} };
  const { useDashboard } = compile("../src/components/abn-lead-gen/use-dashboard.ts", { react: hooks, "@/lib/abn-lead-gen/types": types, "@clerk/nextjs": { useClerk: () => ({}), useAuth: () => ({ isLoaded: true, isSignedIn: true, sessionId: "synthetic-session" }) } });
  t.mock.method(globalThis, "setTimeout", () => 0);
  const controller = useDashboard({ csrfToken: "synthetic-csrf" });
  const runtime = refs[1].current;
  runtime.mounted = true;
  runtime.state = { ...runtime.state, connected: true, loading: false, data, source: data.settings.default_source, cap: "0" };
  return { controller, runtime };
}

test("uncertain requests retain their original source and identifier when a different default is chosen", async t => {
  const { controller, runtime } = SourceHook(t, abrData());
  const pending = { request_id: "00000000-0000-4000-8000-000000000003", source: "qbcc" };
  runtime.request = pending;
  runtime.state.dirty = true;
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => { calls++; throw new Error("unexpected request"); });
  await controller.saveSettings();
  assert.match(runtime.state.settingsError, /earlier QBCC run has an uncertain response/);
  await controller.beginRun();
  assert.match(runtime.state.error, /No new request was sent/);
  assert.equal(calls, 0);
  assert.equal(runtime.request, pending);
});

test("refresh announces completion only for the same active job and never promises baseline leads", async t => {
  const { controller, runtime } = SourceHook(t, { ...abrData(), active_job: { ...abrJob, state: "running", phase: "parsing", result: null } });
  let next = { ...abrData(), latest_job: { ...abrJob, job_id: "00000000-0000-4000-8000-000000000003", source: "qbcc" } };
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify(next), { status: 200 }));
  await controller.refresh();
  assert.doesNotMatch(runtime.state.toast || "", /run complete|leads and reports/i);
  runtime.state.data.active_job = { ...abrJob, state: "running", phase: "parsing", result: null };
  next = abrData();
  await controller.refresh();
  assert.match(runtime.state.toast, /ABR source run complete/);
  assert.match(runtime.state.toast, /baseline or comparison result; matching is separate/);
  assert.doesNotMatch(runtime.state.toast, /leads and reports are ready/);
});

test("a held admission receipt is saved and explained without announcing a started run", async t => {
  const data = { ...abrData(), latest_job: null, runs: [] };
  const { controller, runtime } = SourceHook(t, data);
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", { configurable: true, value: { location: { hash: "" } } });
  t.after(() => previousWindow ? Object.defineProperty(globalThis, "window", previousWindow) : delete globalThis.window);
  let receipt, posts = 0;
  t.mock.method(globalThis, "fetch", async (_, options) => {
    if (options.method === "POST") {
      posts++;
      const submitted = JSON.parse(options.body);
      receipt = { ...abrJob, job_id: submitted.request_id, run_id: submitted.request_id, state: "held", phase: "held", result: null, error_code: "ABR_LIVE_CONFIGURATION_EXPIRED", reason_codes: ["ABR_LIVE_CONFIGURATION_EXPIRED"] };
      return new Response(JSON.stringify(receipt), { status: 200 });
    }
    return new Response(JSON.stringify({ ...data, latest_job: receipt }), { status: 200 });
  });
  await controller.beginRun();
  assert.equal(posts, 1);
  assert.equal(runtime.state.data.latest_job.state, "held");
  assert.doesNotMatch(runtime.state.toast, /started|complete/i);
  assert.match(runtime.state.toast, /ABR validation configuration/);
  assert.equal(runtime.request, null);
});

test("a disconnected dashboard explains setup without claiming demo data was loaded", () => {
  const html = render(null, false);
  assert.match(html, /Engine not connected/);
  assert.doesNotMatch(html, />Demo data</);
  assert.match(html, /No business data has been loaded/);
  assert.match(html, /Australian engine service/);
  for (const id of ["save-settings", "default-source", "monthly-cap"]) assert.match(tag(html, id), /disabled/);
  assert.doesNotMatch(tag(html, "admin-logout"), /disabled/);
  assert.doesNotMatch(tag(html, "retry-button"), /disabled/);
  assert.match(html, /href="#setup"/);
  for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.match(button, /disabled/);
});

test("the first connection check shows loading without inventing a workspace mode", () => {
  const html = render(null, false, true);
  assert.match(html, /Checking connection/);
  assert.doesNotMatch(html, />Demo data</);
  assert.match(tag(html, "settings-form"), /aria-busy="true"/);
});

for (const connected of [false, true]) {
  test(`${connected ? "connected" : "offline"} sample records remain labelled and engine controls follow connection state`, () => {
    const html = render(fixture, connected);
    assert.match(html, connected ? />Demo data</ : /Sample data · Offline/);
    const reports = html.match(/<button[^>]+report-link[^>]*>/g);
    assert.equal(reports.length, 3);
    for (const report of reports) assert.equal(report.includes("disabled"), !connected);
    for (const id of ["save-settings", "default-source", "monthly-cap"]) assert.equal(tag(html, id).includes("disabled"), !connected);
    for (const button of html.match(/<button[^>]+run-button[^>]*>/g)) assert.equal(button.includes("disabled"), !connected);
    assert.doesNotMatch(tag(html, "admin-logout"), /disabled/);
    assert.match(html, /href="#setup"/);
  });
}
