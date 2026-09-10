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
const workflow = compile("../src/components/abn-lead-gen/live-workflow.tsx", {
  "@/lib/abn-lead-gen/types": types, "./dashboard.module.css": {},
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
  "./use-dashboard": { useDashboard: () => state },
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

test("real disabled capability rows render next steps, named owners and native expandable engine details", () => {
  const setup = ["collection", "crm", "abr"].map(id => ({ id, label: id, status: "blocked", detail: "Required evidence: CAPABILITY_DISABLED" }));
  const html = render({ ...fixture, mode: "pilot", run_enabled: false, scopes: ["admin"], runs: [], setup }, true);
  assert.equal((html.match(/<summary>Engine check details<\/summary>/g) || []).length, 3);
  assert.equal((html.match(/Next step · who can help/g) || []).length, 3);
  assert.match(html, /Collecting business records is switched off/);
  assert.match(html, /Jon Pepper and the privacy adviser/);
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

test("permission drafts retain their opening revision across refresh and require explicit reload", async () => {
  const hookValues = [];
  let hookIndex = 0;
  const hookReact = { ...React, useState(initial) {
    const index = hookIndex++;
    if (!(index in hookValues)) hookValues[index] = initial;
    return [hookValues[index], value => { hookValues[index] = typeof value === "function" ? value(hookValues[index]) : value; }];
  } };
  const { PermissionForm } = compile("../src/components/abn-lead-gen/live-workflow.tsx", {
    react: hookReact, "@/lib/abn-lead-gen/types": types, "./dashboard.module.css": {},
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
