"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth, useClerk } from "@clerk/nextjs";
import {
  type DashboardAdmin, type DashboardData, type LeadSource, type ReportKind,
  jobActive, sourceRunAllowed, safeReportURL, validDashboard, validJob, validSettings, validMutationReceipt,
} from "@/lib/abn-lead-gen/types";

const API = "/api/abn-lead-gen";
const SIGN_IN = "/sign-in";
interface DashboardState {
  data: DashboardData | null; loading: boolean; connected: boolean; configurationRequired: boolean; saving: boolean;
  running: boolean; signingOut: boolean; expired: boolean; accessDenied: boolean; error: string | null;
  settingsError: string | null; source: LeadSource; cap: string; dirty: boolean;
  saveStatus: string; toast: string | null;
}
const initialState: DashboardState = {
  data: null, loading: true, connected: false, configurationRequired: false, saving: false, running: false,
  signingOut: false, expired: false, accessDenied: false, error: null, settingsError: null,
  source: "all", cap: "", dirty: false, saveStatus: "", toast: null,
};
class RequestError extends Error {
  constructor(message: string, readonly definitive = false, readonly code = "") { super(message); }
}
class Cancelled extends Error {}
export function validationMessage(path: string) {
  if (path.endsWith("/settings")) return "Check the settings and try again. The usage limit must be between A$0 and A$150.";
  if (path.endsWith("/website-collections")) return "Check the HTTPS homepage, your site-terms evidence and its review date, then try again. Use a homepage ending in / without query parameters or a fragment.";
  return "Check the required form values and evidence, then try again. No change was confirmed.";
}
export function errorMessage(code: string, fallback: string) {
  if (code === "PRIOR_ARTIFACT_EXPIRED_REBASELINE_REQUIRED") return "The earlier ABR comparison file has expired. An authorised operator must review and explicitly establish a new baseline. This run has not treated old businesses as new leads.";
  if (code === "ABR_SOURCE_HTTP_REJECTED") return "The publisher did not return a usable ABR source file for this run. No new publication from this run was accepted. Try again after checking the source status.";
  if (code === "ABR_CLASSIFICATION_DISABLED") return "ABR source validation can run separately, but matching is still disabled until the 100-record accuracy review passes. Source records are not yet matched leads.";
  if (["SOURCE_SELECTION_REQUIRED", "EXACT_LIVE_SOURCE_REQUIRED", "ABR_SOURCE_REQUIRED"].includes(code)) return "Choose one live source in Setup—ABR or QBCC—and save the setting before starting a run.";
  if (["ABR_LIVE_CONFIGURATION_REQUIRED", "ABR_LIVE_CONFIGURATION_EXPIRED", "ABR_LIVE_CONFIGURATION_CHANGED", "ABR_EVIDENCE_BINDING_CHANGED", "ABR_OBSERVATION_POLICY_REQUIRED"].includes(code)) return "The engine cannot confirm the current ABR validation configuration and its recorded scope. The developer must check the source mapping, dated decision and retention controls before this run can proceed. This does not activate matching.";
  if (["ABR_CAPACITY_HEADROOM_REQUIRED", "ABR_EVENT_COUNT_LIMIT", "ABR_EVENT_STORAGE_LIMIT", "ABR_MEMORY_LIMIT", "ABR_PARQUET_STORAGE_LIMIT", "ABR_RUN_DEADLINE", "ABR_WORKING_STORAGE_LIMIT"].includes(code)) return "This ABR run reached a server time, memory or storage limit. The developer must review its measured capacity before retrying. A partial file is not a confirmed source result.";
  if (["ABR_RESOURCE_MAPPING_CHANGED", "ABR_MEMBER_MAPPING_CHANGED", "ABR_RESOURCE_REVALIDATION_FAILED", "ABR_SEQUENCE_INVENTORY_INVALID"].includes(code)) return "The ABR publication did not match the checked file set or changed during validation. The developer must verify the complete publisher release before retrying; an incomplete list must not replace the accepted baseline.";
  const websiteErrors: Record<string, string> = {
    SITE_TERMS_REVIEW_NOT_CURRENT: "Review this website's terms again and record when you checked them. The review must be within the last 30 days and cannot be in the future.",
    IDENTITY_NOT_CURRENT: "The business website identity needs a current approved review. Check the domain and supporting evidence, then save the identity decision again.",
    CURRENT_LICENCE_REVIEW_REQUIRED: "Check this business in the current QBCC licence register and save the matching active licence evidence before collecting its website.",
    ELIGIBLE_CANDIDATE_REQUIRED: "This business is not currently in the website review queue. Check its qualification and current source review before trying again.",
    ENRICHMENT_COOLDOWN: "This business has already had a collection attempt within the current 90-day waiting period. Review its saved evidence; a new attempt is not available yet.",
    WEBSITE_REQUEST_EXPIRED: "This website request expired before it could finish. Review the current business and site-terms evidence before submitting a new request.",
    WEBSITE_PROFILE_ERASED: "This business profile was removed under its retention or restriction rules. The website request cannot continue.",
    WEBSITE_COLLECTION_POLICY_REQUIRED: "The engine cannot confirm the current phone-only website research policy and retention limits. Refresh and check Website contact collection in Setup before submitting.",
    WEBSITE_COLLECTION_HELD: "The website could not be collected within its access, robots or page checks. Review the site manually; do not bypass its restrictions.",
    LEAD_INACTIVE_OR_SUPPRESSED: "This business is inactive or restricted. Website collection is blocked. Keep any do-not-contact restriction in place.",
    TIER_INELIGIBLE: "This business does not currently qualify for website collection. Review its qualification first.",
    GEOGRAPHY_OUTSIDE_OR_UNKNOWN: "This business is outside the approved area, or its location is not confirmed. Review the source details first.",
  };
  if (Object.hasOwn(websiteErrors, code)) return websiteErrors[code];
  if (code === "ONLY_SELECTED_TIER_A") return "Only a selected tier A business can be approved for GoHighLevel. Complete qualification and contact checks first.";
  if (code === "NO_ELIGIBLE_CONTACT") return "This business has no contact that currently passes the hand-off checks. Review its contact restrictions before requesting a GoHighLevel transfer.";
  if (["CRM_MATCH_AMBIGUOUS", "CRM_REMOTE_IDENTITY_CONFLICT", "CRM_ABN_IDENTITY_AMBIGUOUS", "CRM_REMOTE_IDENTITY_MISSING"].includes(code)) return "The engine cannot safely match this business to a GoHighLevel contact. Ask the administrator to review the existing records; do not create a duplicate or merge businesses by phone number alone.";
  if (["CRM_INSTALLATION_MISSING", "CRM_INSTALLATION_INVALID", "CRM_INSTALLATION_EXPIRED", "CRM_INSTALLATION_NOT_APPROVED"].includes(code)) return "The GoHighLevel installation or its current account approval needs to be checked. Ask the administrator to review GoHighLevel hand-off in Setup; this does not approve any business.";
  if (/^CRM_(MAPPING|PROJECTION|FIELDS|REQUIRED_FIELD|FIELD_|WEBSITE|PROVIDER_CONFIG|ENVIRONMENT)/.test(code)) return "The GoHighLevel field or account configuration does not match the approved setup. The developer must correct and verify the mapping before this hand-off can proceed.";
  if (code === "QBCC_SOURCE_HTTP_REJECTED") return "The QBCC publisher did not return a usable source file for this run. No records from this run were accepted. The developer can check the source download before retrying.";
  if (code === "ENGINE_UNAVAILABLE") return "The lead engine is unavailable. Check your connection and try again. If this continues, ask the administrator to start the engine.";
  if (code === "ENGINE_CONFIGURATION_INVALID") return "The lead engine is not connected to this website yet. Open Setup & settings to see what is needed. Runs, settings and reports will become available after the engine connection is configured.";
  if (code === "ENGINE_AUTHENTICATION_FAILED") return "The website could not verify its private connection to the lead engine. Your staff sign-in is still active. Ask the administrator to check the engine connection, then choose Try again.";
  if (code === "ENGINE_INVALID_RESPONSE") return "The engine returned an incomplete response. Your loaded data and unsaved changes are still available. Try again.";
  if (/STALE|AUTHORITY.*CHANGED/.test(code)) return "The saved review information has changed. Refresh the workspace and check the latest decisions before trying again.";
  if (/EXPIRED|ERASED|DELETED/.test(code)) return "This report has expired or was removed. Refresh the workspace to see available records.";
  if (/RUN.*ACTIVE/.test(code)) return "A run is already in progress. You can follow it in Run history.";
  if (/CSRF/.test(code)) return "Your dashboard session changed. Reload the page, then try again.";
  if (code === "REPORT_NOT_FOUND") return "This run has no report available yet. Refresh the run history after processing finishes.";
  if (code === "REVISION_CONFLICT" || code === "IDEMPOTENCY_CONFLICT") return "Another change was saved first. Refresh the business and review its latest values before saving again.";
  if (code === "FORBIDDEN") return "Your account needs an explicitly assigned reviewer role for this action. Ask your administrator to update your access.";
  if (/GATE|CAPABILITY_DISABLED|POLICY_NOT_CURRENT/.test(code)) return "This action is switched off or its required approval evidence is not current. Open Setup & settings to check the engine's reported requirements.";
  if (code === "RUN_WORKER_UNAVAILABLE") return "The source run worker is not configured. Ask the administrator to complete the source worker setup.";
  if (code === "QBCC_PILOT_SOURCE_REQUIRED") return "This worker accepted only QBCC for this request. Choose QBCC in Setup and save, or ask the developer to check the separate ABR worker and its current source approvals.";
  return fallback;
}
function incomplete(kind: string) {
  return new RequestError(kind === "settings"
    ? "The engine did not confirm the saved settings. Your changes are still available. Try saving again, or refresh to check the stored values."
    : kind === "runs" ? "The engine did not confirm the run status. Refresh to check its progress before trying again."
    : "The engine returned an incomplete workspace response. Choose Try again to reload. Your last loaded data and unsaved changes are still available.");
}
const message = (error: unknown) => error instanceof Error ? error.message : "The request could not be completed. Try again.";
const errorCode = (body: unknown): string => {
  if (!body || typeof body !== "object") return "";
  const data = body as { code?: unknown; detail?: unknown };
  if (typeof data.code === "string") return data.code;
  if (typeof data.detail === "string") return data.detail;
  if (data.detail && typeof data.detail === "object" && "code" in data.detail && typeof data.detail.code === "string") return data.detail.code;
  return "";
};

export function useDashboard(admin: DashboardAdmin) {
  const clerk = useClerk();
  const { isLoaded, isSignedIn, sessionId } = useAuth();
  const initialSession = useRef<string | null>(null);
  const [state, setState] = useState(initialState);
  const runtime = useRef({
    state: initialState, mounted: false, epoch: 0, generation: 0,
    loading: null as Promise<void> | null, queued: false, manual: false,
    poll: undefined as ReturnType<typeof setTimeout> | undefined,
    toast: undefined as ReturnType<typeof setTimeout> | undefined,
    controllers: new Set<AbortController>(),
    downloads: new Map<string, ReturnType<typeof setTimeout>>(),
    request: null as { request_id: string; source: LeadSource } | null,
    pendingWrites: new Map<string, string>(),
    actionError: null as string | null,
  });
  const commit = useCallback((patch: Partial<DashboardState>) => {
    const rt = runtime.current;
    if (!rt.mounted) return;
    rt.state = { ...rt.state, ...patch };
    setState(rt.state);
  }, []);
  const notify = useCallback((text: string) => {
    clearTimeout(runtime.current.toast);
    commit({ toast: text });
    runtime.current.toast = setTimeout(() => commit({ toast: null }), 6500);
  }, [commit]);
  const expire = useCallback((signedOut = false, accessDenied = false) => {
    const rt = runtime.current;
    rt.generation++;
    rt.request = null;
    rt.pendingWrites.clear();
    rt.queued = false;
    rt.actionError = null;
    clearTimeout(rt.poll);
    clearTimeout(rt.toast);
    rt.controllers.forEach(controller => controller.abort());
    rt.downloads.forEach((timer, url) => { clearTimeout(timer); URL.revokeObjectURL(url); });
    rt.downloads.clear();
    commit({ ...initialState, loading: false, expired: true, accessDenied,
      error: accessDenied ? "Your account no longer has admin access. Contact a Maintain Media administrator to restore access."
        : signedOut ? "You have signed out. Sign in again to open the admin workspace." : "Your account session has changed or expired. Sign in again to continue." });
  }, [commit]);
  const fetchChecked = useCallback(async (path: string, options: RequestInit = {}, format: "json" | "blob" | "none" = "none") => {
    const rt = runtime.current;
    const epoch = rt.epoch;
    const controller = new AbortController();
    rt.controllers.add(controller);
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(path, {
        ...options, credentials: "same-origin", cache: "no-store", signal: controller.signal,
        headers: { Accept: "application/json", ...(options.method ? { "Content-Type": "application/json", "X-Admin-CSRF": admin.csrfToken } : {}), ...options.headers },
      });
      if (!rt.mounted || epoch !== rt.epoch) throw new Cancelled();
      if (response.status === 401) { expire(); throw new Cancelled(); }
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        if (response.status === 403 && errorCode(body) === "ADMIN_ACCESS_REQUIRED") { expire(false, true); throw new Cancelled(); }
        throw new RequestError(errorMessage(errorCode(body), response.status === 422
          ? validationMessage(path)
          : `The request could not be completed (${response.status}). Refresh the workspace and try again.`), [400, 403, 404, 409, 415, 422, 429].includes(response.status), errorCode(body));
      }
      // Keep the abort deadline active while reading the body, not just until headers arrive.
      let body: unknown = null;
      if (format === "json") body = await response.json().catch((error: unknown) => {
        if (error instanceof SyntaxError) throw incomplete(path.split("/").at(-1) || "dashboard");
        throw error;
      });
      else if (format === "blob") body = await response.blob();
      else await response.body?.cancel();
      if (!rt.mounted || epoch !== rt.epoch || rt.state.expired) throw new Cancelled();
      return { response, body };
    } catch (error) {
      if (!rt.mounted || epoch !== rt.epoch || rt.state.expired) throw new Cancelled();
      if (error instanceof Error && error.name === "AbortError") throw new RequestError("The engine took too long to respond. Refresh to check its status before trying again.");
      if (error instanceof TypeError) throw new RequestError("The engine is not reachable. Check your connection and try again. If this continues, ask the administrator to start the engine.");
      throw error;
    } finally { clearTimeout(timeout); rt.controllers.delete(controller); }
  }, [admin.csrfToken, expire]);
  const request = useCallback(async (endpoint: string, options?: RequestInit): Promise<unknown> => {
    const rt = runtime.current;
    const epoch = rt.epoch;
    const mutation = options?.method && !["GET", "HEAD"].includes(options.method);
    const live = rt.state.data && rt.state.data.mode !== "fixture";
    let cacheKey: string | undefined;
    if (mutation && live && options) {
      cacheKey = `${endpoint}:${options.body ?? ""}`;
      let key = rt.pendingWrites.get(cacheKey);
      if (!key) {
        const data = typeof options.body === "string" ? JSON.parse(options.body) : {};
        key = typeof data.request_id === "string" ? data.request_id : crypto.randomUUID();
        rt.pendingWrites.set(cacheKey, key!);
      }
      options = { ...options, headers: { ...options.headers, "Idempotency-Key": key! } };
    }
    const { body } = await fetchChecked(`${API}/${endpoint}`, options, "json");
    if (cacheKey && !validMutationReceipt(endpoint, body)) throw new RequestError("The engine did not confirm the saved change. Your retry will use the same request identity. Refresh to check the current state before trying again.");
    if (cacheKey) rt.pendingWrites.delete(cacheKey);
    if (!rt.mounted || epoch !== rt.epoch || rt.state.expired) throw new Cancelled();
    return body;
  }, [fetchChecked]);
  const refresh = useCallback(function refreshLoop(manual = false): Promise<void> {
    const rt = runtime.current;
    if (!rt.mounted || rt.state.expired || rt.state.signingOut) return Promise.resolve();
    rt.queued = true;
    rt.manual ||= manual;
    if (rt.loading) return rt.loading;
    const epoch = rt.epoch;
    rt.loading = (async () => {
      while (rt.queued && rt.mounted && rt.epoch === epoch && !rt.state.expired) {
        const explicit = rt.manual;
        rt.queued = false;
        rt.manual = false;
        clearTimeout(rt.poll);
        commit({ loading: true });
        const generation = rt.generation;
        try {
          const data = await request("dashboard");
          if (!validDashboard(data)) throw incomplete("dashboard");
          if (generation !== rt.generation || rt.state.saving) {
            // A GET begun before a write is never allowed to roll back its confirmation.
            rt.queued = !rt.state.saving;
            rt.manual ||= explicit;
            continue;
          }
          const previous = rt.state.data?.active_job;
          const clean = !rt.state.dirty;
          if (rt.request && [data.active_job, data.latest_job].some(job => job?.job_id === rt.request?.request_id && job?.source === rt.request?.source)) rt.request = null;
          commit({ data, connected: true, configurationRequired: false, error: explicit ? null : rt.actionError,
            ...(clean ? { source: data.settings.default_source, cap: (data.settings.monthly_cap_micro_aud / 1e6).toFixed(2) } : {}) });
          if (explicit) rt.actionError = null;
          if (jobActive(previous) && previous?.job_id && previous.job_id === data.latest_job?.job_id && previous.source === data.latest_job.source && data.latest_job.state === "complete") notify(data.latest_job.source === "abr" ? "ABR source run complete. Open Run history to review its baseline or comparison result; matching is separate." : "Source run complete. Open Run history to review its result.");
          else if (explicit) notify("Workspace refreshed.");
        } catch (error) {
          if (error instanceof Cancelled) break;
          commit({ connected: false, configurationRequired: error instanceof RequestError && ["ENGINE_CONFIGURATION_INVALID", "ENGINE_AUTHENTICATION_FAILED"].includes(error.code), error: message(error) });
        } finally {
          if (rt.mounted && rt.epoch === epoch && !rt.state.expired) commit({ loading: false });
        }
      }
    })().finally(() => {
      if (rt.epoch !== epoch) return;
      rt.loading = null;
      if (!rt.mounted || rt.state.expired || rt.state.signingOut || rt.state.configurationRequired) return;
      rt.poll = setTimeout(() => { if (!document.hidden) void refreshLoop(); }, !rt.state.connected ? 10000 : jobActive(rt.state.data?.active_job) ? 2500 : 30000);
    });
    return rt.loading;
  }, [commit, notify, request]);

  useEffect(() => {
    const rt = runtime.current;
    rt.mounted = true;
    rt.epoch++;
    const startup = setTimeout(() => { void refresh(); }, 0);
    const visible = () => { if (!document.hidden) void refresh(); };
    const beforeUnload = (event: BeforeUnloadEvent) => { if (rt.state.dirty) { event.preventDefault(); event.returnValue = ""; } };
    const restored = (event: PageTransitionEvent) => { if (event.persisted) window.location.reload(); };
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("pageshow", restored);
    return () => {
      rt.mounted = false; rt.epoch++; rt.loading = null; rt.queued = false;
      clearTimeout(startup); clearTimeout(rt.poll); clearTimeout(rt.toast);
      rt.controllers.forEach(controller => controller.abort());
      rt.downloads.forEach((timer, url) => { clearTimeout(timer); URL.revokeObjectURL(url); });
      rt.downloads.clear();
      document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("pageshow", restored);
    };
  }, [expire, refresh]);

  useEffect(() => {
    if (!isLoaded) return;
    const timer = setTimeout(() => {
      // Clerk broadcasts session changes across tabs. Never keep another account's loaded leads.
      if (!isSignedIn && !state.signingOut) expire(true);
      else if (sessionId) {
        if (initialSession.current && initialSession.current !== sessionId) expire();
        initialSession.current = sessionId;
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [expire, isLoaded, isSignedIn, sessionId, state.signingOut]);

  function editSettings(source: LeadSource, cap: string) {
    const data = runtime.current.state.data;
    if (!data || !runtime.current.state.connected || runtime.current.state.saving || runtime.current.state.signingOut) return;
    const dirty = source !== data.settings.default_source || cap === "" || !Number.isFinite(Number(cap)) || Math.round(Number(cap) * 1e6) !== data.settings.monthly_cap_micro_aud;
    commit({ source, cap, dirty, settingsError: null, saveStatus: dirty ? "Unsaved changes" : "" });
  }
  function discardSettings() {
    const data = runtime.current.state.data;
    if (data) commit({ source: data.settings.default_source, cap: (data.settings.monthly_cap_micro_aud / 1e6).toFixed(2), dirty: false, settingsError: null, saveStatus: "" });
  }
  async function saveSettings() {
    const rt = runtime.current;
    const current = rt.state;
    if (!current.data || !current.connected || !current.dirty || current.saving || current.expired || current.signingOut) return;
    if (rt.request && current.source !== rt.request.source) {
      commit({ settingsError: `The earlier ${rt.request.source.toUpperCase()} run has an uncertain response. Keep that source and retry the same saved request, or refresh until its status is confirmed, before changing sources.` });
      return;
    }
    if (!/^(?:\d+)(?:\.\d{1,2})?$/.test(current.cap) || Number(current.cap) < 0 || Number(current.cap) > 150) {
      commit({ settingsError: "Enter an amount from A$0 to A$150, with no more than two decimal places." });
      return;
    }
    rt.generation++;
    commit({ saving: true, settingsError: null, saveStatus: "" });
    try {
      const settings = await request("settings", { method: "PATCH", body: JSON.stringify({ default_source: current.source, monthly_cap_micro_aud: Math.round(Number(current.cap) * 1e6) }) });
      if (!validSettings(settings)) throw incomplete("settings");
      rt.generation++;
      commit({ data: { ...rt.state.data!, settings }, source: settings.default_source, cap: (settings.monthly_cap_micro_aud / 1e6).toFixed(2), dirty: false, saveStatus: "Saved for the next run" });
      notify("Run defaults saved for this workspace.");
    } catch (error) {
      if (!(error instanceof Cancelled)) commit({ settingsError: message(error) });
    } finally {
      if (!rt.state.expired) { commit({ saving: false }); await refresh(); }
    }
  }
  async function beginRun() {
    const rt = runtime.current;
    const current = rt.state;
    if (!current.data || !current.connected || !sourceRunAllowed(current.data) || current.running || current.saving || current.expired || current.signingOut || jobActive(current.data.active_job)) return;
    if (rt.request && current.data.settings.default_source !== rt.request.source) {
      commit({ error: `An earlier ${rt.request.source.toUpperCase()} request still needs confirmation. Restore that source in Setup to retry the same request, or refresh until its status is confirmed. No new request was sent.` });
      return;
    }
    rt.request ||= { request_id: crypto.randomUUID(), source: current.data.settings.default_source };
    commit({ running: true, error: null });
    rt.actionError = null;
    let failure: string | null = null;
    try {
      const submitted = rt.request;
      const job = await request("runs", { method: "POST", body: JSON.stringify(submitted) });
      if (!validJob(job) || job.job_id !== submitted.request_id || job.source !== submitted.source) throw incomplete("runs");
      rt.generation++;
      commit({ data: { ...rt.state.data!, active_job: job } });
      rt.request = null;
      window.location.hash = "runs";
      notify(job.state === "complete" ? "Your run is complete. Refresh to see its results." : jobActive(job)
        ? current.data.mode === "fixture" ? "Demo run started. Follow its progress here." : "Source run started. Follow its progress here."
        : job.error_code ? errorMessage(job.error_code, "This source run needs attention. Open Run history to review its reported checks.") : "This source run needs attention. Open Run history to review its reported checks.");
    } catch (error) {
      if (!(error instanceof Cancelled)) failure = message(error);
      if (error instanceof RequestError && error.definitive) rt.request = null;
    } finally {
      if (!rt.state.expired) {
        commit({ running: false });
        await refresh();
        if (failure) { rt.actionError = failure; commit({ error: failure }); }
      }
    }
  }
  async function openReport(url: string, kind: ReportKind) {
    if (!safeReportURL(url) || !runtime.current.state.connected || runtime.current.state.expired || runtime.current.state.signingOut) return;
    const reportWindow = kind === "html" ? window.open("about:blank", "_blank") : null;
    if (reportWindow) { reportWindow.opener = null; reportWindow.document.title = "Opening report"; reportWindow.document.body.textContent = "Checking this report…"; }
    try {
      const { response, body } = await fetchChecked(url, {}, kind === "html" ? "none" : "blob");
      if (runtime.current.state.expired) throw new Cancelled();
      const media = response.headers.get("content-type") || "";
      if (!media.includes(kind === "html" ? "text/html" : kind === "csv" ? "text/csv" : "text/markdown")) throw new RequestError("The engine returned an incomplete report response. Refresh the workspace and try opening the report again.");
      if (kind === "html") {
        if (reportWindow) reportWindow.location.replace(url);
        else window.location.assign(url);
      } else {
        const blob = body as Blob;
        if (!runtime.current.mounted || runtime.current.state.expired) throw new Cancelled();
        const objectURL = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = objectURL; anchor.download = kind === "csv" ? "worklist.csv" : "report.md";
        anchor.click();
        runtime.current.downloads.set(objectURL, setTimeout(() => { URL.revokeObjectURL(objectURL); runtime.current.downloads.delete(objectURL); }, 30000));
        notify(kind === "csv" ? "Worklist CSV downloaded." : "Markdown report downloaded.");
      }
    } catch (error) {
      reportWindow?.close();
      if (!(error instanceof Cancelled)) {
        runtime.current.actionError = message(error);
        commit({ error: message(error) });
        document.getElementById("error-banner")?.scrollIntoView({ block: "nearest", behavior: "instant" });
      }
    }
  }
  async function logout() {
    const rt = runtime.current;
    if (rt.state.signingOut) return;
    if (rt.state.dirty && !window.confirm("Discard your unsaved settings and sign out?")) return;
    commit({ signingOut: true });
    clearTimeout(rt.poll);
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      if (!clerk.loaded) throw new RequestError("Account controls are still connecting. Try again in a moment.");
      await Promise.race([
        clerk.signOut(() => {
          // Only discard local drafts after Clerk confirms the session was ended.
          expire(true);
          window.location.replace(SIGN_IN);
        }),
        new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new RequestError("Account services took too long to respond. Your unsaved settings are still available. Try signing out again.")), 20000); }),
      ]);
    } catch (error) {
      if (!(error instanceof Cancelled) && !rt.state.expired) {
        rt.actionError = error instanceof RequestError ? `Sign-out could not be confirmed. ${error.message}` : "Sign-out could not be confirmed. Your unsaved settings are still available. Check your connection and try again.";
        commit({ signingOut: false, error: rt.actionError });
        void refresh();
      }
    } finally { clearTimeout(timeout); }
  }
  return { ...state, refresh, editSettings, discardSettings, saveSettings, beginRun, openReport, logout, request };
}
export type DashboardController = ReturnType<typeof useDashboard>;
