import { australianToday, recentDates, type Prospect } from "./prospects.ts";

export type DiscoveryMode = "recent7" | "recent30" | "no_website" | "needs_research" | "reviewed";
export const defaultDiscoveryMode: DiscoveryMode = "recent30";
export type DiscoverySearch = { query: string; state: string };
export const discoveryModes: { id: DiscoveryMode; label: string; description: string }[] = [
  { id: "recent7", label: "New · 7 days", description: "Recent ABN activity" },
  { id: "recent30", label: "New · 30 days", description: "A wider starting point" },
  { id: "no_website", label: "No website", description: "Confirmed in saved research" },
  { id: "needs_research", label: "Website unchecked", description: "Saved businesses to investigate" },
  { id: "reviewed", label: "Reviewed leads", description: "Existing qualification & hand-off" },
];
export function discoveryRequest(mode: DiscoveryMode, search: DiscoverySearch, offset = 0, run = "latest", now = new Date()) {
  if (mode === "reviewed") return null;
  if (mode === "recent7" || mode === "recent30") {
    const range = recentDates(mode === "recent7" ? 7 : 30, now);
    return { endpoint: "source-records/query", body: {
      source: "abr" as const, run_id: run, offset, sort: "status_date_desc" as const,
      filters: { status: "ACT", status_date_from: range.from, status_date_to: range.to,
        ...(search.query.trim() ? { query: search.query.trim() } : {}), ...(search.state ? { state: search.state } : {}) },
    } };
  }
  return { endpoint: "prospects/query", body: { offset, filters: {
    website_presence: mode === "no_website" ? "absent" : "unknown",
    ...(search.query.trim() ? { query: search.query.trim() } : {}),
  } } };
}
export function publicationAgeDays(published: string | null, now = new Date()): number | null {
  if (!published || !Number.isFinite(Date.parse(published))) return null;
  const today = Date.parse(australianToday(now));
  const date = /^\d{4}-\d{2}-\d{2}$/.test(published) ? published : australianToday(new Date(published));
  return Math.floor((today - Date.parse(date)) / 86_400_000);
}
export function researchSummary(prospect: Prospect | undefined, available: boolean) {
  if (!available) return { website: "Research unavailable", contact: "Open research to check", tone: "unknown" };
  return { website: prospect?.website_presence === "absent" ? "No website · confirmed"
    : prospect?.website_presence === "present" ? "Website found" : "Website not checked",
    contact: prospect?.phone || prospect?.email ? "Contact detail saved" : "Find a contact route",
    tone: prospect?.website_presence || "unknown" };
}
