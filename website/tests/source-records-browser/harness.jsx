// This entry is bundled only by check.mjs and served on loopback. It is not an
// application route and never starts Next, Clerk, or a live engine connection.
import { createRoot } from "react-dom/client";
import { LeadGenDashboard } from "../../src/components/abn-lead-gen/dashboard";
import { australianToday, recentDates, emptyProspect } from "../../src/lib/abn-lead-gen/prospects";

export const ABR_RUN = "2f634182-1111-4111-8111-111111111111";
export const QBCC_RUN = "692faa4e-2222-4222-8222-222222222222";
const snapshot = "33333333-3333-4333-8333-333333333333";
const observed = "2026-09-14T10:48:00Z";
const abrRecord = index => ({
  abn: String(10000000000 + index), main_name: `Synthetic ABR business ${index + 1}`,
  status: "ACT", status_date: index < 2 ? recentDates(7).from : index === 2 ? australianToday() : "2025-01-02", gst_status: index === 51 ? "NONE" : "ACT", gst_date: index === 51 ? "" : "2025-01-03",
  entity_type: "PRV", entity_class: "company", state: index % 2 ? "NSW" : "QLD", postcode: index % 2 ? "2000" : "4000",
  names_json: index === 0 ? JSON.stringify({ BN: ["Synthetic registered business name"], TRD: ["Synthetic trading name"] }) : "{}",
  name_hash: "a".repeat(64), semantic_hash: "b".repeat(64), source_member: "20260914_Public01.xml",
});
const qbccRecord = index => ({
  licence_number: String(1000000 + index), licensee_name: `Synthetic QBCC business ${index + 1}`,
  abn: String(20000000000 + index), financial_category: "2", financial_category_description: "Category 2",
  original_address: "Synthetic address, Brisbane", state: "QLD", postcode: "4000", status: "UNKNOWN",
  acn: String(600000000 + index), entity_class: "unknown", row_digest: "c".repeat(64),
  class_types: ["Builder - Low Rise", "Carpentry"], geography_review_required: false,
  licence_review_required: true, licence_grades: ["Contractor"],
  licence_types: [{ code: "B", description: "Builder" }],
});
const runFor = source => source === "abr" ? ABR_RUN : QBCC_RUN;
const harness = globalThis.sourceHarness = {
  requests: [], pending: [], downloads: [], delay: false, mode: "available", error: null, sourceErrors: {}, sourceModes: {}, qbccMissingAbn: false, prospects: {}, saveError: null, researchError: null, freshAll: false,
  release() { for (const complete of this.pending.splice(0)) complete(); },
};
HTMLFormElement.prototype.submit = function captureLocalDownload() {
  harness.downloads.push({ action: this.action, method: this.method, fields: Object.fromEntries(new FormData(this)) });
};
const dashboard = {
  mode: "production", outreach: "disabled", run_enabled: true, scopes: ["operator", "reviewer"],
  settings: { default_source: "abr", monthly_cap_micro_aud: 0 },
  summary: { total_leads: 1, selected: 0, needs_review: 1, last_run_at: observed },
  leads: [{ lead_id: ABR_RUN, abn: '51824753556', business_name: 'Previously reviewed business', source: 'qbcc', score: 100, tier: 'A' }],
  runs: [
    { run_id: ABR_RUN, source: "abr", status: "complete", started_at: observed,
      result: { baseline: true, events: 0, candidates: 0, classification: "disabled", record_count: 52 } },
    { run_id: QBCC_RUN, source: "qbcc", status: "complete", started_at: "2026-09-11T04:47:00Z" },
  ],
  sources: ["abr", "qbcc"].map(source => ({ source, status: "accepted", can_run: true,
    reason_codes: [], record_count: 52, baseline: source === "abr", classification: "disabled",
    last_success_at: observed, source_published_at: observed })),
  setup: [], active_job: null, latest_job: null, budget: null,
};
harness.engine = {
  data: dashboard, connected: true, loading: false, configurationRequired: false,
  saving: false, running: false, signingOut: false, expired: false, accessDenied: false,
  error: null, settingsError: null, source: "abr", cap: "0", dirty: false, saveStatus: "", toast: null,
  refresh: async () => {}, beginRun: async () => {}, logout: async () => {},
  editSettings: () => {}, discardSettings: () => {}, saveSettings: async () => {}, openReport: async () => {},
  async request(path, options) {
    harness.requests.push({ path, options: options || null });
    const body = options?.body ? JSON.parse(options.body) : {};
    if (path === "prospects/query") {
      if (harness.researchError) throw new Error(harness.researchError);
      const filters = body.filters || {};
      const records = Object.values(harness.prospects).filter(row => (!body.abns || body.abns.includes(row.abn)) && Object.entries(filters).every(([key, value]) => {
        if (!value) throw new Error("Empty filter values must be omitted");
        if (key === "query") return `${row.business_name} ${row.abn}`.toLowerCase().includes(value.toLowerCase());
        if (key === "registration_date_from") return row.registration_date && row.registration_date >= value;
        if (key === "registration_date_to") return row.registration_date && row.registration_date <= value;
        if (key === "follow_up_due") return row.follow_up_on && row.follow_up_on <= value;
        return row[key] === value;
      }));
      return { records: records.slice(body.offset, body.offset + 50), total: records.length, offset: body.offset, limit: 50, next_offset: body.offset + 50 < records.length ? body.offset + 50 : null };
    }
    if (/^prospects\/\d{11}$/.test(path)) return { prospect: harness.prospects[path.split('/')[1]] || null };
    if (path === "prospects") {
      if (harness.saveError) throw new Error(harness.saveError);
      if ('prospect_id' in body || 'contact_permission' in body || 'state' in body) throw new Error("Unexpected read-only save fields");
      const prior = harness.prospects[body.abn];
      if (body.expected_revision !== (prior?.revision || 0)) throw new Error("Revision conflict");
      const { request_id, expected_revision, ...values } = body;
      harness.prospects[body.abn] = { ...emptyProspect(values), ...values, revision: expected_revision + 1, saved_at: new Date().toISOString(), prospect_id: snapshot, state: 'QLD', postcode: '4000', contact_permission: 'not_assessed' };
      return { revision: expected_revision + 1, saved_at: harness.prospects[body.abn].saved_at, prospect_id: snapshot };
    }
    if (path === "source-exports") return {
      download_url: "https://abn-engine.maintainmedia.com.au/api/source-exports/download", download_token: "synthetic-local-download-ticket-0123456789",
      expires_at: new Date(Date.now() + 60_000).toISOString(), source: body.source,
      run_id: body.run_id === "latest" ? runFor(body.source) : body.run_id, snapshot_id: snapshot,
      columns: Object.keys((body.source === "abr" ? abrRecord : qbccRecord)(0)),
    };
    if (path !== "source-records/query") throw new Error(`Unexpected mock read: ${path}`);
    const { source, run_id: run = "latest", offset = 0, filters = {}, sort = "source_order" } = body;
    const state = harness.sourceModes[source] || harness.mode;
    const failure = harness.sourceErrors[source] || harness.error;
    const all = Array.from({ length: 52 }, (_, index) => (source === "abr" ? abrRecord : qbccRecord)(index));
    if (source === "qbcc" && harness.qbccMissingAbn) all[0].abn = null;
    if (source === "abr" && harness.freshAll) for (const [index, row] of all.entries()) { if (index > 2) row.status_date = recentDates(20).from; }
    const enteredQuery = (filters.query || "").trim().toLowerCase();
    const query = /^[\d\s]+$/.test(enteredQuery) ? enteredQuery.replace(/\s/g, "") : enteredQuery;
    const matching = all.filter(row => (!query || [row.abn, row.main_name, row.names_json, row.licensee_name, row.acn, row.licence_number]
      .some(value => String(value || "").toLowerCase().includes(query)))
      && Object.entries(filters).every(([key, value]) => key === "query" || !value || value === "all" || (key === "status_date_from" ? row.status_date >= value : key === "status_date_to" ? row.status_date <= value : String(row[key] || "") === value)));
    if (sort === "status_date_desc") matching.sort((a, b) => b.status_date.localeCompare(a.status_date));
    const rows = state === "available" ? matching : [];
    const response = {
      source, run_id: run === "latest" ? runFor(source) : run, snapshot_id: snapshot,
      source_state: state, source_observed_at: observed, publisher_modified_at: observed,
      publisher_extract_time: source === "abr" ? "20260914180000" : null,
      baseline: source === "abr", total: rows.length, source_total: state === "available" ? 52 : 0,
      columns: Object.keys((source === "abr" ? abrRecord : qbccRecord)(0)),
      limit: 50, filters: Object.fromEntries(Object.entries(filters).filter(([, value]) => value)), offset, sort,
      next_offset: offset + 50 < rows.length ? offset + 50 : null,
      records: rows.slice(offset, offset + 50),
    };
    if (harness.delay) await new Promise(resolve => harness.pending.push(resolve));
    if (failure) throw new Error(failure);
    return response;
  },
};
createRoot(document.getElementById("root")).render(<LeadGenDashboard admin={{ username: "synthetic-review@example.invalid", displayName: "Local UI check", csrfToken: "local-synthetic-only" }} />);
