export type Presence = "unknown" | "present" | "absent";
export type ContactStage = "not_contacted" | "contacted" | "interested" | "follow_up" | "not_interested";
export type ProspectSeed = { abn: string; business_name: string; source: "abr" | "qbcc"; snapshot_id: string; run_id: string };
export type Prospect = ProspectSeed & {
  revision: number; saved_at: string; expires_at?: string;
  website_presence: Presence; email_presence: Presence; social_presence: Presence;
  website_url: string; email: string; phone: string; social_url: string;
  evidence_ref: string; research_note: string; contact_stage: ContactStage;
  follow_up_on: string | null; registration_date: string | null; registration_evidence_ref: string;
};
export type ProspectFilters = Partial<Record<"query" | "website_presence" | "email_presence" | "social_presence" | "contact_stage" | "registration_date_from" | "registration_date_to" | "follow_up_due", string>>;
export type ProspectPage = { records: Prospect[]; total: number; offset: number; limit: number; next_offset: number | null };
export const presenceLabels: Record<Presence, string> = { unknown: "Unknown", present: "Found", absent: "Confirmed absent" };
export const stageLabels: Record<ContactStage, string> = { not_contacted: "Not contacted", contacted: "Contacted", interested: "Interested", follow_up: "Follow up", not_interested: "Not interested" };

// A date-only ABR field needs a date-only window. Use the business's Australian
// operating timezone consistently, regardless of the staff browser's timezone.
export function australianToday(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-AU", { timeZone: "Australia/Brisbane", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  return ["year", "month", "day"].map(key => parts.find(part => part.type === key)!.value).join("-");
}
export function recentDates(days: number, now = new Date()) {
  const to = australianToday(now);
  const start = new Date(`${to}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - days + 1);
  return { from: start.toISOString().slice(0, 10), to };
}
export function emptyProspect(seed: ProspectSeed): Prospect {
  return { ...seed, revision: 0, saved_at: "", website_presence: "unknown", email_presence: "unknown", social_presence: "unknown", website_url: "", email: "", phone: "", social_url: "", evidence_ref: "", research_note: "", contact_stage: "not_contacted", follow_up_on: null, registration_date: null, registration_evidence_ref: "" };
}
export function validProspect(value: unknown): value is Prospect {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return typeof row.abn === "string" && /^\d{11}$/.test(row.abn)
    && typeof row.business_name === "string" && (row.source === "abr" || row.source === "qbcc")
    && typeof row.snapshot_id === "string" && /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(row.snapshot_id)
    && typeof row.run_id === "string" && (row.run_id === "latest" || /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(row.run_id))
    && Number.isSafeInteger(row.revision) && Number(row.revision) > 0 && typeof row.saved_at === "string" && Number.isFinite(Date.parse(row.saved_at))
    && ["website_presence", "email_presence", "social_presence"].every(key => typeof row[key] === "string" && Object.hasOwn(presenceLabels, row[key]))
    && typeof row.contact_stage === "string" && Object.hasOwn(stageLabels, row.contact_stage)
    && ["website_url", "email", "phone", "social_url", "evidence_ref", "research_note", "registration_evidence_ref"].every(key => typeof row[key] === "string")
    && [row.follow_up_on, row.registration_date].every(date => date === null || typeof date === "string" && /^[1-9]\d{3}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(date)) && new Date(date).toISOString().slice(0, 10) === date);
}
export function validProspectPage(value: unknown, offset: number): value is ProspectPage {
  if (!value || typeof value !== "object") return false;
  const page = value as ProspectPage;
  return Array.isArray(page.records) && page.records.length === Math.min(50, Math.max(0, page.total - offset)) && page.records.every(validProspect)
    && new Set(page.records.map(row => row.abn)).size === page.records.length
    && Number.isSafeInteger(page.total) && page.total >= page.records.length && page.offset === offset && page.limit === 50
    && page.next_offset === (offset + 50 < page.total ? offset + 50 : null);
}
