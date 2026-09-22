import test from "node:test";
import assert from "node:assert/strict";
import { australianToday, recentDates, emptyProspect, validProspect, validProspectPage } from "../src/lib/abn-lead-gen/prospects.ts";
import { validMutationReceipt } from "../src/lib/abn-lead-gen/types.ts";

const seed = {
  abn: "51824753556", business_name: "Synthetic new business", source: "abr",
  snapshot_id: "38c74a7c-3859-4bc2-9c18-278951ef9872", run_id: "a471ba37-e0cb-4fa6-9868-3c1fc00684a6",
};
const record = (patch = {}) => ({ ...emptyProspect(seed), revision: 1, saved_at: "2026-09-22T03:04:05Z", ...patch });
const page = (patch = {}) => ({ records: [record()], total: 1, offset: 0, limit: 50, next_offset: null, ...patch });

test("the seven-day window follows Brisbane midnight, including both boundary dates", () => {
  assert.equal(australianToday(new Date("2026-09-21T13:59:59.999Z")), "2026-09-21");
  assert.equal(australianToday(new Date("2026-09-21T14:00:00.000Z")), "2026-09-22");
  const window = recentDates(7, new Date("2026-09-21T14:00:00.000Z"));
  assert.deepEqual(window, { from: "2026-09-16", to: "2026-09-22" });
  const inWindow = date => date >= window.from && date <= window.to;
  assert.equal(inWindow("2026-09-15"), false);
  assert.equal(inWindow("2026-09-16"), true);
  assert.equal(inWindow("2026-09-22"), true);
  assert.equal(inWindow("2026-09-23"), false);
  assert.equal((Date.parse(window.to) - Date.parse(window.from)) / 86_400_000 + 1, 7);
});

test("recent dates cross month, year and leap-year boundaries without using browser timezone", () => {
  assert.deepEqual(recentDates(7, new Date("2026-01-01T00:00:00Z")), { from: "2025-12-26", to: "2026-01-01" });
  assert.deepEqual(recentDates(7, new Date("2024-03-01T00:00:00Z")), { from: "2024-02-24", to: "2024-03-01" });
  assert.deepEqual(recentDates(7, new Date("2026-03-01T00:00:00Z")), { from: "2026-02-23", to: "2026-03-01" });
});

test("new research keeps missing publisher contact details unknown and registration unverified", () => {
  const empty = emptyProspect(seed);
  assert.deepEqual([empty.website_presence, empty.email_presence, empty.social_presence], ["unknown", "unknown", "unknown"]);
  assert.equal(empty.registration_date, null);
  assert.equal(empty.contact_stage, "not_contacted");
  assert.equal(validProspect(empty), false, "an unsaved draft is not a saved server record");
  assert.equal(validProspect(record()), true);
  assert.equal(validProspect(record({ website_presence: "absent", evidence_ref: "Business owner confirmed by phone" })), true);
});

test("saved research requires strict identity, timestamps and enum types", () => {
  for (const patch of [
    { abn: "not-an-abn" }, { source: ["abr"] }, { run_id: undefined }, { run_id: "../source" },
    { snapshot_id: "latest" }, { saved_at: "not-a-date" }, { revision: 0 }, { revision: 1.5 },
    { website_presence: ["absent"] }, { email_presence: null }, { contact_stage: ["follow_up"] },
  ]) assert.equal(validProspect(record(patch)), false, JSON.stringify(patch));
});

test("saved registration and follow-up dates must be real calendar dates", () => {
  for (const value of ["2026-02-29", "2026-09-31", "0000-01-01", "2026-9-22", "20260922", 20260922]) {
    assert.equal(validProspect(record({ registration_date: value, registration_evidence_ref: "ABN history" })), false, String(value));
    assert.equal(validProspect(record({ follow_up_on: value })), false, String(value));
  }
  assert.equal(validProspect(record({ registration_date: "2024-02-29", registration_evidence_ref: "ABN history" })), true);
});

test("saved pages reject impossible counts, duplicate businesses and broken pagination", () => {
  assert.equal(validProspectPage(page(), 0), true);
  assert.equal(validProspectPage(page({ records: [], total: 0 }), 0), true);
  assert.equal(validProspectPage(page({ records: [], total: 5, offset: 50 }), 50), true);
  for (const response of [
    page({ total: -1 }), page({ total: 0 }), page({ offset: 50 }), page({ limit: 100 }),
    page({ total: 51 }), page({ total: 51, next_offset: 50 }),
    page({ records: [record(), record()], total: 2 }),
    page({ records: [record({ source: "other" })] }),
  ]) assert.equal(validProspectPage(response, 0), false, JSON.stringify(response));
});

test("a prospect save has an identity-bound durable receipt before the shared request completes", () => {
  const receipt = { prospect_id: seed.snapshot_id, revision: 1, saved_at: "2026-09-22T03:04:05Z", expires_at: "2027-03-21T03:04:05Z" };
  assert.equal(validMutationReceipt("prospects", receipt), true);
  for (const patch of [{ prospect_id: "invalid" }, { revision: 0 }, { revision: 1.5 }, { saved_at: "not-a-date" }, { expires_at: "not-a-date" }]) {
    assert.equal(validMutationReceipt("prospects", { ...receipt, ...patch }), false, JSON.stringify(patch));
  }
});
