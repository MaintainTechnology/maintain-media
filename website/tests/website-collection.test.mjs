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
const policy = { allowed_channels: ["mobile", "landline"], reason_codes: [], expires_at: "2099-01-01T00:00:00Z" };
const lead = { lead_id: id, source: "qbcc", revision: 1, website_identity: { identity_id: id, registrable_domain: "example.test", assessment: "approved", expires_at: policy.expires_at } };
function nodes(value) {
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value)) return value.flatMap(nodes);
  return [value, ...nodes(value.props?.children)];
}
function harness({ savedLead = lead, allowedPolicy = policy, scopes = ["reviewer"] } = {}) {
  const values = [], effects = [], calls = [];
  let cursor = 0;
  const hooks = { ...React,
    useState(initial) { const index = cursor++; if (!(index in values)) values[index] = initial; return [values[index], next => { values[index] = typeof next === "function" ? next(values[index]) : next; }]; },
    useRef(initial) { const index = cursor++; return values[index] ??= { current: initial }; },
    useEffect(effect) { effects.push(effect); },
  };
  const { LeadActions } = compile("../src/components/abn-lead-gen/live-workflow.tsx", {
    react: hooks, "@/lib/abn-lead-gen/types": types, "./dashboard.module.css": {}, "./use-dashboard": errors, "./readiness": guidance,
  });
  const engine = { data: { mode: "pilot", scopes, website_collection_policy: allowedPolicy }, connected: true,
    async request(endpoint, options) { calls.push({ endpoint, options }); return { job_id: id, run_id: id, state: options ? "queued" : "complete", source: "qbcc" }; }, async refresh() {} };
  const render = () => { cursor = 0; effects.length = 0; return LeadActions({ lead: savedLead, engine }); };
  return { render, effects, calls, values };
}
const collectionForm = tree => nodes(tree).find(node => node.type === "form" && nodes(node).some(child => child.type === "legend" && child.props.children === "Checked phone-only website collection"));

test("a current reviewed business exposes an explicit phone-only form with required evidence", () => {
  const form = collectionForm(harness().render());
  assert.ok(form);
  assert.equal(form.props.children.props.disabled, false);
  const inputs = nodes(form).filter(node => node.type === "input");
  for (const name of ["website_url", "terms_permit", "terms_evidence_ref", "terms_reviewed_at"]) assert.equal(inputs.find(node => node.props.name === name).props.required, true);
  assert.equal(inputs.find(node => node.props.name === "website_url").props.defaultValue, "https://example.test/");
  assert.equal(inputs.find(node => node.props.name === "terms_permit").props.defaultChecked, undefined);
  for (const allowedPolicy of [null, { ...policy, allowed_channels: [] }, { ...policy, allowed_channels: ["email"] }]) {
    const held = harness({ allowedPolicy });
    assert.equal(collectionForm(held.render()).props.children.props.disabled, true);
  }
  assert.equal(collectionForm(harness({ scopes: ["admin", "operator"] }).render()), undefined);
});

test("a reviewer can inspect collected phone evidence without an email permission form", () => {
  const fixture = harness({ savedLead: { ...lead, contacts: [{ contact_id: id, provenance_id: id, channel: "landline", revision: 1, allowed: false, reason_codes: ["DNCR_NOT_CURRENT"] }] } });
  const html = renderToStaticMarkup(fixture.render());
  assert.match(html, /Review phone evidence/);
  assert.match(html, /Open private captured evidence/);
  assert.match(html, /does not establish permission to call/);
  assert.doesNotMatch(html, /Record-level permission assessment|Save permission assessment/);
  assert.doesNotMatch(renderToStaticMarkup(harness({ savedLead: { ...lead, contacts: [{ contact_id: id, provenance_id: id, channel: "landline", revision: 1 }] }, scopes: ["admin"] }).render()), /Open private captured evidence/);
});

test("submission binds the actual business and identity, retains dated terms and sends no channel override", async () => {
  const fixture = harness();
  const form = collectionForm(fixture.render());
  const input = { website_url: "https://example.test/", terms_permit: "on", terms_evidence_ref: "Checked public terms receipt", terms_reviewed_at: "2026-09-11T09:10" };
  const original = globalThis.FormData;
  globalThis.FormData = class { get(name) { return input[name]; } };
  try { await form.props.onSubmit({ preventDefault() {}, currentTarget: {} }); }
  finally { globalThis.FormData = original; }
  assert.equal(fixture.calls[0].endpoint, "website-collections");
  const body = JSON.parse(fixture.calls[0].options.body);
  assert.equal(body.lead_id, id);
  assert.equal(body.identity_id, id);
  assert.equal(body.terms_permit, true);
  assert.equal(body.terms_evidence_ref, input.terms_evidence_ref);
  assert.equal(body.terms_reviewed_at, new Date(input.terms_reviewed_at).toISOString());
  assert.match(body.request_id, /^[a-f0-9-]{36}$/);
  assert.deepEqual(Object.keys(body).sort(), ["identity_id", "lead_id", "request_id", "terms_evidence_ref", "terms_permit", "terms_reviewed_at", "website_url"]);
  assert.equal(collectionForm(fixture.render()).props.children.props.disabled, true);
});

test("an invalid terms date is shown as a form error without a request or uncaught RangeError", async () => {
  const fixture = harness();
  const original = globalThis.FormData;
  globalThis.FormData = class { get() { return "invalid"; } };
  try { await collectionForm(fixture.render()).props.onSubmit({ preventDefault() {}, currentTarget: {} }); }
  finally { globalThis.FormData = original; }
  assert.equal(fixture.calls.length, 0);
  assert.match(renderToStaticMarkup(fixture.render()), /Enter a valid date and time/);
});

test("a persisted active job reopens disabled and resumes its saved job identifier", async () => {
  const fixture = harness({ savedLead: { ...lead, website_job: { job_id: id, run_id: id, state: "queued", source: "qbcc" } } });
  const tree = fixture.render();
  assert.equal(collectionForm(tree).props.children.props.disabled, true);
  assert.match(renderToStaticMarkup(tree), /Website job: Queued/);
  const original = globalThis.setTimeout;
  let poll;
  globalThis.setTimeout = callback => { poll = callback; return 0; };
  try { for (const effect of fixture.effects) effect(); }
  finally { globalThis.setTimeout = original; }
  await poll();
  assert.equal(fixture.calls[0].endpoint, `website-jobs/${id}`);
  assert.match(renderToStaticMarkup(fixture.render()), /Website job: Complete/);
});

test("a newer saved active job replaces the displayed terminal local receipt", async () => {
  const savedLead = { ...lead, website_job: { job_id: id, run_id: id, state: "queued", source: "qbcc" } };
  const fixture = harness({ savedLead });
  fixture.render();
  const original = globalThis.setTimeout;
  let poll;
  globalThis.setTimeout = callback => { poll = callback; return 0; };
  try { for (const effect of fixture.effects) effect(); }
  finally { globalThis.setTimeout = original; }
  await poll();
  assert.match(renderToStaticMarkup(fixture.render()), /Website job: Complete/);
  const newerId = "00000000-0000-4000-8000-000000000002";
  savedLead.website_job = { job_id: newerId, run_id: newerId, state: "queued", source: "qbcc" };
  const next = fixture.render();
  assert.match(renderToStaticMarkup(next), /Website job: Queued/);
  assert.equal(collectionForm(next).props.children.props.disabled, true);
  globalThis.setTimeout = callback => { poll = callback; return 0; };
  try { for (const effect of fixture.effects) effect(); }
  finally { globalThis.setTimeout = original; }
  await poll();
  assert.equal(fixture.calls[1].endpoint, `website-jobs/${newerId}`);
});

test("website errors and validation explain their own review step without demo or spending instructions", () => {
  for (const code of ["SITE_TERMS_REVIEW_NOT_CURRENT", "IDENTITY_NOT_CURRENT", "CURRENT_LICENCE_REVIEW_REQUIRED", "ELIGIBLE_CANDIDATE_REQUIRED", "ENRICHMENT_COOLDOWN", "WEBSITE_REQUEST_EXPIRED", "WEBSITE_PROFILE_ERASED", "WEBSITE_COLLECTION_POLICY_REQUIRED", "WEBSITE_COLLECTION_HELD"]) {
    const message = errors.errorMessage(code, "Fallback");
    assert.notEqual(message, "Fallback");
    assert.doesNotMatch(message, /Run the demo|usage limit|This report/);
  }
  assert.match(errors.validationMessage("/api/abn-lead-gen/website-collections"), /HTTPS homepage/);
  assert.doesNotMatch(errors.validationMessage("/api/abn-lead-gen/identity-assessments"), /usage limit/);
  assert.match(errors.validationMessage("/api/abn-lead-gen/settings"), /A\$150/);
});

test("public research notice uses the existing public contact and qualified scope disclosures", () => {
  const site = compile("../src/lib/site.ts");
  const { default: Notice } = compile("../src/app/business-research-notice/page.tsx", { "@/lib/site": site });
  const html = renderToStaticMarkup(React.createElement(Notice));
  assert.match(html, /mailto:jon@maintainaudits.com.au/);
  assert.doesNotMatch(html, /jeph@|quotemax|Australian-only|legally certified/);
  for (const text of ["QBCC Licensed Contractors Register", "90 days", "180 days", "30 days", "24 hours", "not all been verified", "Email addresses are not extracted", "incidentally contain", "request access or correction", "raise a complaint"]) assert.ok(html.includes(text), text);
  assert.match(html, /does not mean that every person/);
  assert.match(html, /If an authorised reviewer separately approves an eligible record/);
  assert.match(html, /limited business summary and one reviewed phone number/);
  assert.match(html, /Do Not Disturb stays on/);
  assert.match(html, /United States and India/);
  assert.match(html, /not fully verified for our account/);
  assert.match(html, /excludes isolated backup copies/);
  assert.match(html, /not verified a fixed expiry/);
  assert.match(html, /do not claim immediate erasure from all provider backups/);
  assert.match(html, /transfer does not restart these periods/);
  assert.match(html, /Transfers to Google Sheets remain disabled/);
  assert.match(html, /does not create a seven-year/);
  assert.match(html, /href="https:\/\/www.gohighlevel.com\/sub-processors"/);
  assert.match(html, /href="https:\/\/www.gohighlevel.com\/data-processing-agreement"/);
  for (const text of ["ABN Lookup bulk extract", "ABN status and effective date", "GST status and registration date", "Names can identify individuals", "creates no new-business events or leads", "no phone numbers or email addresses", "does not authorise website collection or transfer of ABR records", "CC BY 3.0 Australia", "Abandoned source staging is removed after seven days", "does not mean that an import or matching review has passed"]) assert.ok(html.includes(text), text);
  assert.match(html, /href="https:\/\/abr.business.gov.au\/Tools\/BulkExtract"/);
  assert.match(html, /href="https:\/\/creativecommons.org\/licenses\/by\/3.0\/au\/"/);
  assert.doesNotMatch(html, /does not send records to Google Sheets or GoHighLevel/);
});
