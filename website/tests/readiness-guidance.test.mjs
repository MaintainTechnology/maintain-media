import test from "node:test";
import assert from "node:assert/strict";
import { readinessGuidance, websiteCollectionGuidance } from "../src/components/abn-lead-gen/readiness.ts";

const blocked = (id, detail = "Required evidence: CAPABILITY_DISABLED") => ({ id, label: id, status: "blocked", detail });
const copy = result => [result.summary, result.note, ...result.steps.flatMap(step => [step.owner, step.action])].join(" ");

test("disabled QBCC guidance names source/privacy and developer steps without imposing later ABR gates", () => {
  const input = Object.freeze(blocked("collection"));
  const result = readinessGuidance(input, "pilot");
  assert.equal(result.ready, false);
  assert.equal(result.statusLabel, "Blocked");
  assert.match(copy(result), /Business owner or authorised delegate/);
  assert.match(copy(result), /owner-authorised QBCC scope/);
  assert.match(copy(result), /Website collection and vendor hand-off have separate controls/);
  assert.match(result.note, /Approval details have not been checked/);
  assert.doesNotMatch(copy(result), /100-record|four measured|approved already|approval is missing/i);
  assert.equal(result.technicalDetail, input.detail);
  assert.equal(input.status, "blocked");
});

test("disabled CRM points to account/vendor and suppression tests without claiming contact access", () => {
  const result = readinessGuidance(blocked("crm"), "production");
  assert.match(result.summary, /GoHighLevel is switched off/);
  assert.match(copy(result), /terms and countries/);
  assert.match(copy(result), /duplicate handling and do-not-contact updates/);
  assert.match(copy(result), /authorised delegate/);
  assert.match(copy(result), /Approve each eligible, selected tier A business separately/);
  assert.doesNotMatch(copy(result), /installed successfully|token missing|contact access granted|sign in again/i);
  for (const code of ["GATE_G1_CLOSED", "GATE_G5_CLOSED"]) {
    const detail = copy(readinessGuidance(blocked("crm", `Required evidence: ${code}`), "pilot"));
    assert.match(detail, /authorised delegate/);
    assert.doesNotMatch(detail, /privacy adviser|\bJon\b/);
  }
});

test("broader ABR explains its separate pilot decision and matching review", () => {
  const result = readinessGuidance(blocked("abr"), "pilot");
  assert.match(copy(result), /early ABR validation decision/);
  assert.match(copy(result), /before the later measured pilot finishes/);
  assert.doesNotMatch(copy(result), /four measured weeks|Jon/);
  assert.match(copy(result), /100-record matching review/);
  assert.match(copy(result), /before activating classification/);
  assert.match(copy(result), /Verify the live ABR feed/);
  assert.equal(result.ready, false);
});

test("website collection has its own decision and cannot inherit QBCC approval", () => {
  const result = readinessGuidance(blocked("website_collection"), "pilot");
  assert.equal(result.ready, false);
  assert.match(copy(result), /QBCC approval alone does not approve website collection or email harvesting/);
  assert.match(copy(result), /business identity, current licence and each site's terms/);
  assert.match(copy(result), /Business owner or authorised delegate/);
  assert.match(result.note, /Approval details have not been checked/);
  assert.doesNotMatch(copy(result), /100-record|four measured/);
  const gate = copy(readinessGuidance(blocked("website_collection", "Required evidence: GATE_G1_CLOSED"), "pilot"));
  assert.match(gate, /authorised delegate/);
  assert.match(gate, /phone-only website research decision/);
  assert.doesNotMatch(gate, /privacy adviser/);
});

test("phone-only submission needs the current explicit policy, not a readiness label", () => {
  const policy = { allowed_channels: ["mobile", "landline"], reason_codes: [], expires_at: "2099-01-01T00:00:00Z" };
  const result = websiteCollectionGuidance({ mode: "pilot", website_collection_policy: policy });
  assert.equal(result.enabled, true);
  assert.match(result.summary, /Email extraction is disabled/);
  assert.match(result.summary, /does not establish permission to call/);
  for (const entry of [undefined, { ...policy, allowed_channels: [] }, { ...policy, allowed_channels: ["email"] },
    { ...policy, allowed_channels: ["mobile", "landline", "email"] }, { ...policy, allowed_channels: ["mobile", "mobile"] },
    { ...policy, reason_codes: ["GATE_G1_CLOSED"] }, { ...policy, expires_at: null }, { ...policy, expires_at: "2000-01-01T00:00:00Z" }]) {
    const held = websiteCollectionGuidance({ mode: "pilot", website_collection_policy: entry, setup: [{ id: "website_collection", status: "approved" }] });
    assert.equal(held.enabled, false);
    assert.match(held.summary, /not currently confirmed/);
  }
  const fixture = websiteCollectionGuidance({ mode: "fixture", website_collection_policy: policy });
  assert.equal(fixture.enabled, false);
  assert.match(fixture.summary, /Synthetic/);
});

test("specific engine gates explain only the checks actually reported, including renewed evidence", () => {
  const result = readinessGuidance(blocked("crm", "Required evidence: GATE_G5_CLOSED, GATE_G7_CLOSED"), "pilot");
  assert.equal(result.note, "");
  assert.equal(result.steps.length, 2);
  assert.match(copy(result), /current hand-off approval/);
  assert.match(copy(result), /final release decision/);
  assert.doesNotMatch(copy(result), /switched off|GATE_G1|100-record|four measured/);
  assert.match(result.technicalDetail, /GATE_G5_CLOSED, GATE_G7_CLOSED/);
});

test("additional unknown checks remain unverified and retain exact engine detail", () => {
  const input = blocked("collection", "Required evidence: CAPABILITY_DISABLED, NEW_CHECK, GATE_G1_CLOSED");
  const result = readinessGuidance(input, "pilot");
  assert.equal(result.ready, false);
  assert.equal(result.note, "");
  assert.equal(result.steps.length, 2);
  assert.match(copy(result), /meaning has not been verified here/);
  assert.match(copy(result), /Check or renew the recorded QBCC-only source decision/);
  assert.equal(result.technicalDetail, input.detail);
  const unknownOnly = readinessGuidance(blocked("collection", "Required evidence: RUNTIME_UNAVAILABLE"), "pilot");
  assert.equal(unknownOnly.summary, "This feature is waiting for required checks.");
  assert.doesNotMatch(unknownOnly.summary, /approval/);
});

test("responsibility is role-based and a current owner-authorised collection state stays authoritative", () => {
  for (const id of ["collection", "crm", "website_collection", "abr"]) {
    for (const detail of ["Required evidence: CAPABILITY_DISABLED", "Required evidence: GATE_G1_CLOSED, GATE_G2_CLOSED, GATE_G3_CLOSED, GATE_G4_CLOSED, GATE_G5_CLOSED, GATE_G6_CLOSED, GATE_G7_CLOSED"]) {
      assert.doesNotMatch(copy(readinessGuidance(blocked(id, detail), "pilot")), /\bJon\b|Pepper/);
    }
  }
  const result = readinessGuidance({ id: "collection", label: "Business source collection", status: "approved", detail: "Owner-authorised QBCC-only pilot is current." }, "pilot");
  assert.equal(result.ready, true);
  assert.equal(result.summary, "Owner-authorised QBCC-only pilot is current.");
  assert.equal(result.steps.length, 0);
  assert.equal(result.note, "");
});

test("unknown IDs cannot borrow readiness guidance by label or inherited object property", () => {
  for (const id of [undefined, "future", "constructor", "toString"]) {
    const result = readinessGuidance({ ...blocked(id), label: "Business source collection" }, "pilot");
    assert.equal(result.summary, "This feature is switched off.");
    assert.match(copy(result), /Identify this feature/);
    assert.doesNotMatch(copy(result), /QBCC|GoHighLevel|100-record/);
  }
});

test("ready/unknown states and fixture responses keep their actual engine descriptions", () => {
  for (const status of ["approved", "connected", "unknown", "future_status", "toString"]) {
    const input = { id: "crm", label: "CRM", status, detail: "Engine's current observation." };
    const result = readinessGuidance(input, "pilot");
    assert.equal(result.summary, input.detail);
    assert.equal(result.ready, ["approved", "connected"].includes(status));
    assert.equal(result.steps.length, 0);
    if (!["approved", "connected"].includes(status)) assert.equal(result.statusLabel, "Not verified");
  }
  const fixture = readinessGuidance(blocked("collection"), "fixture");
  assert.equal(fixture.summary, "Required evidence: CAPABILITY_DISABLED");
  assert.equal(fixture.steps.length, 0);
});

test("non-code backend explanations are preserved instead of guessed into an approval", () => {
  for (const detail of ["Licence service is unavailable.", "Required evidence: unexpected lower-case detail", "Required evidence: "]) {
    const result = readinessGuidance(blocked("collection", detail), "pilot");
    assert.equal(result.summary, detail);
    assert.equal(result.ready, false);
    assert.match(result.steps[0].action, /Check the engine details/);
    assert.equal(result.technicalDetail, "");
  }
});
