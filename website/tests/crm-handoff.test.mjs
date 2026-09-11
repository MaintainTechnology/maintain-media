import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
function compile(path, imports = {}) {
  const { outputText } = ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  });
  const compiledModule = { exports: {} };
  new Function("require", "exports", "module", outputText)(name => Object.hasOwn(imports, name) ? imports[name] : require(name), compiledModule.exports, compiledModule);
  return compiledModule.exports;
}
const types = compile("../src/lib/abn-lead-gen/types.ts");
const guidance = compile("../src/components/abn-lead-gen/readiness.ts");
const errors = compile("../src/components/abn-lead-gen/use-dashboard.ts", { "@clerk/nextjs": {}, "@/lib/abn-lead-gen/types": types });
const id = "00000000-0000-4000-8000-000000000001";
const base = { state: "awaiting_review", can_approve: true, can_reject: true, reason_codes: [], outbox_id: null, updated_at: null };
function nodes(value) {
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value)) return value.flatMap(nodes);
  return [value, ...nodes(value.props?.children)];
}
function setup({ lead = { lead_id: id, source: "qbcc", row_id: id, row_version: 3, crm_handoff: base }, reviewer = true } = {}) {
  const values = [], saves = [];
  let index = 0;
  const hooks = { ...React, useState(initial) { const slot = index++; if (!(slot in values)) values[slot] = initial; return [values[slot], value => { values[slot] = value; }]; } };
  const { CrmReview } = compile("../src/components/abn-lead-gen/live-workflow.tsx", {
    react: hooks, "@/lib/abn-lead-gen/types": types, "./dashboard.module.css": {}, "./use-dashboard": errors, "./readiness": guidance,
  });
  const props = { lead, reviewer, disabled: false, expectedVersion: 3, async save(endpoint, body) { saves.push({ endpoint, body }); } };
  return { props, saves, render() { index = 0; return CrmReview(props); } };
}
const form = tree => nodes(tree).find(node => node.type === "form");
async function submit(tree, decision) {
  const original = globalThis.FormData;
  globalThis.FormData = class { get(name) { return name === "decision" ? decision : "Reviewed current evidence for this business"; } };
  try { await form(tree).props.onSubmit({ preventDefault() {}, currentTarget: {} }); }
  finally { globalThis.FormData = original; }
}

test("current unselected phone-evidence business explains the missing step without an approval form", () => {
  const fixture = setup({ lead: { lead_id: id, source: "qbcc", row_id: null, crm_handoff: { ...base, state: "not_selected", can_approve: false, can_reject: false, reason_codes: ["ONLY_SELECTED_TIER_A", "NO_ELIGIBLE_CONTACT"] } } });
  const tree = fixture.render(), html = renderToStaticMarkup(tree);
  assert.match(html, /Not selected for hand-off/);
  assert.match(html, /Complete its qualification and contact checks/);
  assert.match(html, /does not approve every business/);
  assert.doesNotMatch(html, /Save CRM decision|Hand-off verified/);
  assert.equal(form(tree), undefined);
});

test("a reviewer explicitly submits the selected row and opening version, without a dispatch call", async () => {
  const fixture = setup();
  const tree = fixture.render();
  assert.equal(form(tree).props.children.props.disabled, false);
  assert.equal(nodes(tree).find(node => node.type === "select").props.defaultValue, "");
  assert.equal(nodes(tree).find(node => node.type === "textarea").props.required, true);
  fixture.props.lead = { ...fixture.props.lead, row_version: 4 };
  await submit(fixture.render(), "approve");
  assert.deepEqual(fixture.saves, [{ endpoint: "crm-approvals", body: { row_id: id, expected_version: 3, decision: "approve", reason: "Reviewed current evidence for this business" } }]);
});

test("withdrawn eligibility blocks a stale approve choice while still allowing the engine's reject action", async () => {
  const fixture = setup();
  fixture.props.lead = { ...fixture.props.lead, crm_handoff: { ...base, state: "blocked", can_approve: false, can_reject: true, reason_codes: ["GATE_G5_CLOSED"] } };
  const tree = fixture.render();
  assert.equal(nodes(tree).find(node => node.type === "option" && node.props.value === "approve").props.disabled, true);
  await submit(tree, "approve");
  assert.equal(fixture.saves.length, 0);
  assert.match(renderToStaticMarkup(fixture.render()), /not available under the current engine checks/);
  await submit(fixture.render(), "reject");
  assert.equal(fixture.saves[0].body.decision, "reject");
});

test("missing or unrecognised status cannot activate approval from row presence or boolean flags alone", () => {
  for (const status of [null, { ...base, state: "future_provider_state" }]) {
    const tree = setup({ lead: { lead_id: id, source: "qbcc", row_id: id, row_version: 3, crm_handoff: status } }).render();
    assert.equal(form(tree).props.children.props.disabled, true);
    assert.match(renderToStaticMarkup(tree), /Hand-off not verified/);
  }
  const noRole = setup({ reviewer: false }).render();
  assert.equal(form(noRole), undefined);
  assert.match(renderToStaticMarkup(noRole), /explicitly assigned reviewer role/);
});

test("queued, uncertain and confirmed results remain distinct and never claim outreach", () => {
  for (const state of ["pending", "inflight", "retry", "uncertain", "blocked", "dead_letter"]) {
    const result = guidance.crmHandoffGuidance({ ...base, state, can_approve: false });
    assert.notEqual(result.label, "Hand-off verified");
    assert.equal(result.canApprove, false);
  }
  assert.match(guidance.crmHandoffGuidance({ ...base, state: "uncertain" }).detail, /reconcile.*before another create/);
  const succeeded = guidance.crmHandoffGuidance({ ...base, state: "succeeded", can_approve: false });
  assert.equal(succeeded.label, "Hand-off verified");
  assert.match(succeeded.detail, /does not mean that a message was sent or that a call is permitted/);
  assert.match(guidance.crmHandoffGuidance({ ...base, state: "rejected" }).detail, /does not say.*earlier completed transfer.*removed/);
});

test("CRM error codes explain installation, eligibility and identity problems rather than report expiry", () => {
  for (const code of ["CRM_INSTALLATION_EXPIRED", "CRM_MAPPING_REVISION_CHANGED", "CRM_MATCH_AMBIGUOUS", "CRM_REMOTE_IDENTITY_CONFLICT", "ONLY_SELECTED_TIER_A", "NO_ELIGIBLE_CONTACT"]) {
    const text = errors.errorMessage(code, "Fallback");
    assert.notEqual(text, "Fallback");
    assert.doesNotMatch(text, /This report|Run the demo/);
  }
});

test("CRM projection validation keeps unknown future state readable but refuses malformed authority or identifiers", () => {
  assert.equal(types.validCrmHandoff(base), true);
  assert.equal(types.validCrmHandoff({ ...base, state: "future" }), true);
  for (const bad of [{ ...base, can_approve: "true" }, { ...base, reason_codes: "none" }, { ...base, outbox_id: "https://untrusted.test/contact" }, { ...base, updated_at: 0 }]) assert.equal(types.validCrmHandoff(bad), false);
});
