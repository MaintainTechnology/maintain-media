import test from "node:test";
import assert from "node:assert/strict";
import { readinessGuidance } from "../src/components/abn-lead-gen/readiness.ts";

const blocked = (id, detail = "Required evidence: CAPABILITY_DISABLED") => ({ id, label: id, status: "blocked", detail });
const copy = result => [result.summary, result.note, ...result.steps.flatMap(step => [step.owner, step.action])].join(" ");

test("disabled QBCC guidance names source/privacy and developer steps without imposing later ABR gates", () => {
  const input = Object.freeze(blocked("collection"));
  const result = readinessGuidance(input, "pilot");
  assert.equal(result.ready, false);
  assert.equal(result.statusLabel, "Blocked");
  assert.match(copy(result), /Jon Pepper and the privacy adviser/);
  assert.match(copy(result), /QBCC source format, security, backup recovery/);
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
  assert.doesNotMatch(copy(result), /installed successfully|token missing|contact access granted|sign in again/i);
});

test("broader ABR explains its separate pilot decision and matching review", () => {
  const result = readinessGuidance(blocked("abr"), "pilot");
  assert.match(copy(result), /four measured weeks of the QBCC pilot/);
  assert.match(copy(result), /100-record matching review/);
  assert.match(copy(result), /record whether to expand/);
  assert.match(copy(result), /Complete and test the live ABR feed/);
  assert.equal(result.ready, false);
});

test("website collection has its own decision and cannot inherit QBCC approval", () => {
  const result = readinessGuidance(blocked("website_collection"), "pilot");
  assert.equal(result.ready, false);
  assert.match(copy(result), /QBCC approval does not approve this feature/);
  assert.match(copy(result), /business identity, current licence and each site's terms/);
  assert.match(result.note, /Approval details have not been checked/);
  assert.doesNotMatch(copy(result), /100-record|four measured/);
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
  assert.match(copy(result), /Record or renew the source and privacy decision/);
  assert.equal(result.technicalDetail, input.detail);
  const unknownOnly = readinessGuidance(blocked("collection", "Required evidence: RUNTIME_UNAVAILABLE"), "pilot");
  assert.equal(unknownOnly.summary, "This feature is waiting for required checks.");
  assert.doesNotMatch(unknownOnly.summary, /approval/);
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
