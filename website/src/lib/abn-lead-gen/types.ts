export type LeadSource = "all" | "abr" | "qbcc";
export type ReportKind = "html" | "csv" | "markdown";
export type DashboardView = "leads" | "runs" | "setup";
export interface DashboardAdmin { username: string; displayName: string; csrfToken: string }
export interface RunSettings { default_source: LeadSource; monthly_cap_micro_aud: number }
export interface Lead {
  group_id?: string; revision?: number; row_id?: string | null; row_version?: number | null;
  worklist_id?: string | null; outcome?: string | null; approval_state?: string | null;
  outcome_details?: { attempts?: number; invitation_state?: string; invitation_evidence_ref?: string | null; notes?: string; occurred_at?: string };
  contacts?: { contact_id: string; channel: string; revision: number; provenance_id: string; allowed: boolean; reason_codes: string[] }[];
  website_identity?: { identity_id: string; registrable_domain: string; assessment: string; expires_at: string } | null;
  lead_id: string; source: string; business_name?: string | null; abn?: string | null;
  location?: string | null; first_observed_at?: string | null; signal?: string | null;
  state?: string | null; next_action?: string | null; tier?: "A" | "B" | "C" | null;
  score?: number | null; reason_codes?: string[] | null;
}
export interface Job {
  job_id?: string; run_id?: string | null; state: string; source: string; error_code?: string | null;
}
export interface EngineRun {
  run_id: string; source: string; status: string; started_at?: string | null;
  selected?: number | null; reports?: Partial<Record<ReportKind, string | null>> | null;
}
export interface DashboardData {
  mode: "fixture" | "pilot" | "production"; outreach: "disabled"; settings: RunSettings;
  scopes?: string[]; run_enabled?: boolean; worklist_csv?: string | null;
  summary: { total_leads: number; selected: number; needs_review: number; last_run_at?: string | null };
  leads: Lead[]; runs: EngineRun[];
  sources: { source: string; status: string; last_success_at?: string | null; source_published_at?: string | null }[];
  setup: { id?: string; label: string; status: string; detail: string }[];
  active_job?: Job | null; latest_job?: Job | null;
  budget?: { effective_cap_micro_aud: number; frozen: boolean } | null;
  operational_notices?: { code: string; message: string; count: number }[];
}

const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const optionalString = (value: unknown) => value == null || typeof value === "string";
const count = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const uuid = (value: unknown) => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export const isSource = (value: unknown): value is LeadSource => value === "all" || value === "abr" || value === "qbcc";
export function validSettings(value: unknown): value is RunSettings {
  return record(value) && isSource(value.default_source) && count(value.monthly_cap_micro_aud) && Number(value.monthly_cap_micro_aud) <= 150000000;
}
export function validJob(value: unknown): value is Job {
  return record(value) && uuid(value.job_id) && uuid(value.run_id) && typeof value.state === "string"
    && ["queued", "running", "complete", "held", "failed", "interrupted"].includes(value.state)
    && isSource(value.source) && optionalString(value.error_code);
}
export function validMutationReceipt(endpoint: string, value: unknown): boolean {
  if (endpoint === "settings") return validSettings(value);
  if (endpoint === "runs" || endpoint === "website-collections") return validJob(value);
  if (!record(value)) return false;
  if (endpoint === "suppressions") return uuid(value.receipt_id) && uuid(value.suppression_id) && typeof value.committed_at === "string" && Number.isFinite(Date.parse(value.committed_at));
  if (endpoint.startsWith("worklist-rows/")) return uuid(value.row_id) && count(value.version) && Number(value.version) > 0 && typeof value.saved_at === "string" && typeof value.status === "string";
  if (endpoint === "qbcc-reviews") return uuid(value.review_id) && typeof value.state === "string";
  if (endpoint === "identity-assessments") return uuid(value.identity_id) && count(value.assessment_seq) && typeof value.expires_at === "string";
  if (endpoint === "basis-assessments") return uuid(value.basis_id) && count(value.assessment_seq) && typeof value.expires_at === "string";
  if (endpoint === "crm-approvals") return value.state === "rejected" || uuid(value.approval_id) && uuid(value.outbox_id) && typeof value.state === "string";
  if (endpoint === "operator-activities") return uuid(value.activity_id) && typeof value.saved_at === "string";
  return false;
}
export function validDashboard(value: unknown): value is DashboardData {
  return record(value) && ["fixture", "pilot", "production"].includes(String(value.mode)) && value.outreach === "disabled" && validSettings(value.settings)
    && (value.mode === "fixture" || typeof value.run_enabled === "boolean" && Array.isArray(value.scopes) && value.scopes.every(scope => typeof scope === "string"))
    && record(value.summary) && ["total_leads", "selected", "needs_review"].every(key => count((value.summary as Record<string, unknown>)[key])) && optionalString(value.summary.last_run_at)
    && Array.isArray(value.leads) && value.leads.every(lead => record(lead) && typeof lead.lead_id === "string" && typeof lead.source === "string"
      && ["business_name", "abn", "location", "first_observed_at", "signal", "state", "next_action"].every(key => optionalString(lead[key]))
      && (lead.tier == null || ["A", "B", "C"].includes(String(lead.tier))) && (lead.score == null || typeof lead.score === "number" && Number.isFinite(lead.score))
      && (lead.reason_codes == null || Array.isArray(lead.reason_codes) && lead.reason_codes.every(reason => typeof reason === "string")))
    && Array.isArray(value.runs) && value.runs.every(run => record(run) && ["run_id", "source", "status"].every(key => typeof run[key] === "string")
      && optionalString(run.started_at) && (run.selected == null || count(run.selected))
      && (run.reports == null || record(run.reports) && ["html", "csv", "markdown"].every(key => optionalString((run.reports as Record<string, unknown>)[key]))))
    && Array.isArray(value.sources) && value.sources.every(source => record(source) && typeof source.source === "string" && typeof source.status === "string" && optionalString(source.last_success_at) && optionalString(source.source_published_at))
    && Array.isArray(value.setup) && value.setup.every(item => record(item) && ["label", "status", "detail"].every(key => typeof item[key] === "string"))
    && [value.active_job, value.latest_job].every(job => job == null || validJob(job))
    && (value.budget == null || record(value.budget) && count(value.budget.effective_cap_micro_aud) && typeof value.budget.frozen === "boolean")
    && (value.operational_notices == null || Array.isArray(value.operational_notices) && value.operational_notices.every(notice => record(notice) && typeof notice.code === "string" && typeof notice.message === "string" && count(notice.count)));
}
export function safeReportURL(url: unknown): string | null {
  if (url === "/api/abn-lead-gen/worklist.csv") return url;
  return typeof url === "string" && /^\/api\/abn-lead-gen\/reports\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/(html|csv|markdown)$/.test(url) ? url : null;
}
export const jobActive = (job?: Job | null) => !!job && ["running", "queued", "pending"].includes(job.state);
export const sourceName = (value?: string | null) => value === "all" ? "ABR + QBCC" : (value || "Unknown").toUpperCase();
export function humanize(value?: string | null): string {
  const labels: Record<string, string> = {
    qbcc_backlog: "QBCC discovery backlog", qbcc_new: "New QBCC observation", qbcc_category_changed: "QBCC category changed",
    abn_new: "New ABN observation", gst_registered: "GST registration observed", fixture_ready: "Demo data ready", not_run: "Not processed yet",
    BASIS_NOT_CURRENT: "Contact permission needs review", EMAIL_NOT_VERIFIED: "Email has not been verified", NO_CONTACT: "No contact details recorded",
  };
  return labels[value || ""] || (value || "Unknown").replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());
}
export function dateLabel(value?: string | null, compact = false) {
  if (!value) return "Not recorded";
  const normalized = value.replace(/^(\d{4}-\d{2}-\d{2}) /, "$1T");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat("en-AU", /^\d{4}-\d{2}-\d{2}$/.test(normalized)
    ? { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }
    : { day: "numeric", month: "short", ...(compact ? {} : { year: "numeric" }), hour: "numeric", minute: "2-digit" }).format(date);
}
export function formatABN(value?: string | null) {
  return value && /^\d{11}$/.test(value) ? value.replace(/^(\d{2})(\d{3})(\d{3})(\d{3})$/, "$1 $2 $3 $4") : value || "Not recorded";
}
