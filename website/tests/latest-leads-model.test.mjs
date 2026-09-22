import test from "node:test";
import assert from "node:assert/strict";
import { discoveryRequest, publicationAgeDays, researchSummary } from "../src/lib/abn-lead-gen/latest-leads.ts";
import { emptyProspect } from "../src/lib/abn-lead-gen/prospects.ts";

const now = new Date("2026-09-21T14:00:00.000Z");
const search = { query: "", state: "" };
const seed = {
  abn: "51824753556", business_name: "Synthetic business", source: "abr",
  snapshot_id: "38c74a7c-3859-4bc2-9c18-278951ef9872", run_id: "a471ba37-e0cb-4fa6-9868-3c1fc00684a6",
};

test("recent discovery reads active source businesses without score or digital-presence gates", () => {
  const request = discoveryRequest("recent7", search, 0, "latest", now);
  assert.equal(request.endpoint, "source-records/query");
  assert.equal(request.body.source, "abr");
  assert.equal(request.body.sort, "status_date_desc");
  assert.deepEqual(request.body.filters, {
    status: "ACT", status_date_from: "2026-09-16", status_date_to: "2026-09-22",
  });
  assert.equal(request.body.run_id, "latest");
  assert.equal(request.body.offset, 0);
});

test("widening discovery reaches the full thirty-day window and retains the applied search", () => {
  const request = discoveryRequest("recent30", { query: "  New electrical  ", state: "QLD" }, 0, "latest", now);
  assert.deepEqual(request.body.filters, {
    status: "ACT", status_date_from: "2026-08-24", status_date_to: "2026-09-22",
    query: "New electrical", state: "QLD",
  });
});

test("discovery pagination stays on the accepted publication and keeps the global date sort", () => {
  const request = discoveryRequest("recent7", { query: "  51 824 753 556  ", state: "NSW" }, 50, seed.run_id, now);
  assert.equal(request.body.run_id, seed.run_id);
  assert.equal(request.body.offset, 50);
  assert.equal(request.body.sort, "status_date_desc");
  assert.equal(request.body.filters.query, "51 824 753 556");
  assert.equal(request.body.filters.state, "NSW");
});

test("No website includes saved businesses regardless of age, email, social presence or score", () => {
  const request = discoveryRequest("no_website", { query: "  Electrical  ", state: "QLD" }, 50, seed.run_id, now);
  assert.equal(request.endpoint, "prospects/query");
  assert.deepEqual(request.body, {
    offset: 50, filters: { website_presence: "absent", query: "Electrical" },
  });
});

test("website-unknown discovery is distinct from confirmed website absence", () => {
  const request = discoveryRequest("needs_research", { query: "   ", state: "" }, 0, "latest", now);
  assert.equal(request.endpoint, "prospects/query");
  assert.deepEqual(request.body.filters, { website_presence: "unknown" });
  assert.equal(discoveryRequest("reviewed", search, 0, "latest", now), null);
});

test("publication age follows Brisbane calendar days across midnight", () => {
  assert.equal(publicationAgeDays("2026-09-21T13:59:59.999Z", now), 1);
  assert.equal(publicationAgeDays("2026-09-21T14:00:00.000Z", now), 0);
  assert.equal(publicationAgeDays("2026-09-14", now), 8);
  assert.equal(publicationAgeDays("2026-09-16", now), 6);
  assert.equal(publicationAgeDays("2025-12-31", new Date("2026-01-01T00:00:00Z")), 1);
});

test("missing or unreadable publication dates never appear as a fresh publication", () => {
  assert.equal(publicationAgeDays(null, now), null);
  assert.equal(publicationAgeDays("", now), null);
  assert.equal(publicationAgeDays("not a date", now), null);
});

test("unsaved and unknown research never imply that the business has no website", () => {
  const expected = { website: "Website not checked", contact: "Find a contact route", tone: "unknown" };
  assert.deepEqual(researchSummary(undefined, true), expected);
  assert.deepEqual(researchSummary(emptyProspect(seed), true), expected);
});

test("website findings and saved contact routes have independent evidence", () => {
  const absent = { ...emptyProspect(seed), website_presence: "absent", email_presence: "present", email: "owner@example.invalid" };
  assert.deepEqual(researchSummary(absent, true), {
    website: "No website · confirmed", contact: "Contact detail saved", tone: "absent",
  });
  const present = { ...emptyProspect(seed), website_presence: "present", website_url: "https://example.invalid" };
  assert.deepEqual(researchSummary(present, true), {
    website: "Website found", contact: "Find a contact route", tone: "present",
  });
  assert.equal(researchSummary({ ...emptyProspect(seed), phone: "0400 000 000" }, true).contact, "Contact detail saved");
  assert.equal(researchSummary({ ...emptyProspect(seed), social_url: "https://example.invalid/profile" }, true).contact, "Find a contact route");
});

test("research lookup failure is shown explicitly instead of inferring missing digital presence", () => {
  const expected = { website: "Research unavailable", contact: "Open research to check", tone: "unknown" };
  assert.deepEqual(researchSummary(undefined, false), expected);
  assert.deepEqual(researchSummary({ ...emptyProspect(seed), website_presence: "absent", phone: "0400 000 000" }, false), expected);
});
