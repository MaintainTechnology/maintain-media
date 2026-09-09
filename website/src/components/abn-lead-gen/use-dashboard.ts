"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth, useClerk } from "@clerk/nextjs";
import {
  type DashboardAdmin, type DashboardData, type LeadSource, type ReportKind,
  jobActive, safeReportURL, validDashboard, validJob, validSettings,
} from "@/lib/abn-lead-gen/types";

const API = "/api/abn-lead-gen";
const SIGN_IN = "/sign-in";
interface DashboardState {
  data: DashboardData | null; loading: boolean; connected: boolean; saving: boolean;
  running: boolean; signingOut: boolean; expired: boolean; accessDenied: boolean; error: string | null;
  settingsError: string | null; source: LeadSource; cap: string; dirty: boolean;
  saveStatus: string; toast: string | null;
}
const initialState: DashboardState = {
  data: null, loading: true, connected: false, saving: false, running: false,
  signingOut: false, expired: false, accessDenied: false, error: null, settingsError: null,
  source: "all", cap: "", dirty: false, saveStatus: "", toast: null,
};
class RequestError extends Error {
  constructor(message: string, readonly definitive = false) { super(message); }
}
class Cancelled extends Error {}
function errorMessage(code: string, fallback: string) {
  if (code === "ENGINE_UNAVAILABLE") return "The lead engine is unavailable. Check your connection and try again. If this continues, ask the administrator to start the engine.";
  if (code === "ENGINE_CONFIGURATION_INVALID") return "The website’s engine connection needs setup. Ask the administrator to check the engine configuration, then try again.";
  if (code === "ENGINE_INVALID_RESPONSE") return "The engine returned an incomplete response. Your loaded data and unsaved changes are still available. Try again.";
  if (/STALE|AUTHORITY.*CHANGED/.test(code)) return "This report needs to be refreshed. Run the demo again to create a report using current review decisions.";
  if (/EXPIRED|ERASED|DELETED/.test(code)) return "This report has expired or was removed. Refresh the workspace to see available records.";
  if (/RUN.*ACTIVE/.test(code)) return "A run is already in progress. You can follow it in Run history.";
  if (/CSRF/.test(code)) return "Your dashboard session changed. Reload the page, then try again.";
  if (code === "REPORT_NOT_FOUND") return "This run has no report available yet. Refresh the run history after processing finishes.";
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
          ? "Check the values and try again. The usage limit must be between A$0 and A$150."
          : `The request could not be completed (${response.status}). Refresh the workspace and try again.`), [400, 403, 404, 409, 415, 422, 429].includes(response.status));
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
    const { body } = await fetchChecked(`${API}/${endpoint}`, options, "json");
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
          commit({ data, connected: true, error: explicit ? null : rt.actionError,
            ...(clean ? { source: data.settings.default_source, cap: (data.settings.monthly_cap_micro_aud / 1e6).toFixed(2) } : {}) });
          if (explicit) rt.actionError = null;
          if (jobActive(previous) && data.latest_job?.state === "complete") notify("Run complete. Your latest leads and reports are ready.");
          else if (explicit) notify("Workspace refreshed.");
        } catch (error) {
          if (error instanceof Cancelled) break;
          commit({ connected: false, error: message(error) });
        } finally {
          if (rt.mounted && rt.epoch === epoch && !rt.state.expired) commit({ loading: false });
        }
      }
    })().finally(() => {
      if (rt.epoch !== epoch) return;
      rt.loading = null;
      if (!rt.mounted || rt.state.expired || rt.state.signingOut) return;
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
    if (!data || runtime.current.state.saving) return;
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
    if (!current.data || !current.dirty || current.saving || current.expired) return;
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
    if (!current.data || current.running || current.saving || current.expired || jobActive(current.data.active_job)) return;
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
      notify(job.state === "complete" ? "Your run is complete. The reports are ready." : "Demo run started. Follow its progress here.");
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
    if (!safeReportURL(url) || runtime.current.state.expired) return;
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
  return { ...state, refresh, editSettings, discardSettings, saveSettings, beginRun, openReport, logout };
}
export type DashboardController = ReturnType<typeof useDashboard>;
