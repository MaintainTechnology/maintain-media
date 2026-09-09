"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const icon = (name, extra = "") => `<svg class="icon ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const humanize = (value) => ({
  qbcc_backlog:"QBCC discovery backlog",qbcc_new:"New QBCC observation",qbcc_category_changed:"QBCC category changed",
  abn_new:"New ABN observation",gst_registered:"GST registration observed",fixture_ready:"Demo data ready",not_run:"Not processed yet",
  BASIS_NOT_CURRENT:"Contact permission needs review",EMAIL_NOT_VERIFIED:"Email has not been verified",NO_CONTACT:"No contact details recorded",
}[value] || String(value || "Unknown").replace(/_/g, " ").replace(/^./, (letter) => letter.toUpperCase()));
const sourceName = (value) => value === "all" ? "ABR + QBCC" : String(value || "Unknown").toUpperCase();
const dateLabel = (value, compact = false) => {
  if (typeof value === "string") value = value.replace(/^(\d{4}-\d{2}-\d{2}) /,"$1T");
  if (!value || Number.isNaN(Date.parse(value))) return "Not recorded";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Intl.DateTimeFormat("en-AU",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"}).format(new Date(value));
  return new Intl.DateTimeFormat("en-AU", {day:"numeric",month:"short",...(compact ? {} : {year:"numeric"}),hour:"numeric",minute:"2-digit"}).format(new Date(value));
};
const formatABN = (value) => value && /^\d{11}$/.test(value) ? value.replace(/^(\d{2})(\d{3})(\d{3})(\d{3})$/, "$1 $2 $3 $4") : value || "Not recorded";
const state = {data:null,selected:null,dirty:false,loading:false,loadPromise:null,refreshQueued:false,manualQueued:false,mutationGeneration:0,saving:false,running:false,requestId:null,requestSource:null,actionError:null,toastTimer:null,pollTimer:null};
const isRecord = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const optionalString = (value) => value == null || typeof value === "string";
const countValue = (value) => Number.isSafeInteger(value) && value >= 0;
const invalidResponse = (kind = "dashboard") => new Error(kind === "settings"
  ? "The engine did not confirm the saved settings. Your changes are still available. Try saving again, or refresh to check the stored values."
  : kind === "run" ? "The engine did not confirm the run status. Refresh to check its progress before trying again."
  : `The engine returned an incomplete workspace response. Choose Try again to reload.${state.data ? " Your last loaded data and unsaved changes are still available." : ""}`);

function validSettings(settings) {
  return isRecord(settings) && ["all","abr","qbcc"].includes(settings.default_source) && countValue(settings.monthly_cap_micro_aud) && settings.monthly_cap_micro_aud <= 150000000;
}
function validJob(job) {
  return isRecord(job) && typeof job.state === "string" && typeof job.source === "string" && optionalString(job.error_code);
}
function validateDashboard(data) {
  // Check the complete render contract before replacing the last usable snapshot.
  const valid = isRecord(data) && data.mode === "fixture" && data.outreach === "disabled"
    && typeof data.csrf_token === "string" && data.csrf_token.length > 0 && validSettings(data.settings)
    && isRecord(data.summary) && ["total_leads","selected","needs_review"].every((key) => countValue(data.summary[key])) && optionalString(data.summary.last_run_at)
    && Array.isArray(data.leads) && data.leads.every((lead) => isRecord(lead) && typeof lead.lead_id === "string" && typeof lead.source === "string"
      && ["business_name","abn","location","first_observed_at","signal","state","next_action"].every((key) => optionalString(lead[key]))
      && (lead.tier == null || ["A","B","C"].includes(lead.tier)) && (lead.score == null || Number.isFinite(lead.score))
      && (lead.reason_codes == null || Array.isArray(lead.reason_codes) && lead.reason_codes.every((reason) => typeof reason === "string")))
    && Array.isArray(data.runs) && data.runs.every((run) => isRecord(run) && ["run_id","source","status"].every((key) => typeof run[key] === "string")
      && optionalString(run.started_at) && (run.selected == null || countValue(run.selected))
      && (run.reports == null || isRecord(run.reports) && ["html","csv","markdown"].every((key) => optionalString(run.reports[key]))))
    && Array.isArray(data.sources) && data.sources.every((source) => isRecord(source) && typeof source.source === "string" && typeof source.status === "string" && optionalString(source.last_success_at) && optionalString(source.source_published_at))
    && Array.isArray(data.setup) && data.setup.every((item) => isRecord(item) && ["label","status","detail"].every((key) => typeof item[key] === "string"))
    && [data.active_job,data.latest_job].every((job) => job == null || validJob(job))
    && (data.budget == null || isRecord(data.budget) && countValue(data.budget.effective_cap_micro_aud) && typeof data.budget.frozen === "boolean")
    && (data.operational_notices == null || Array.isArray(data.operational_notices) && data.operational_notices.every((notice) => isRecord(notice) && typeof notice.code === "string" && typeof notice.message === "string" && countValue(notice.count)));
  if (!valid) throw invalidResponse();
  return data;
}

function updateDataControls() {
  $$("#lead-search, #source-filter, #tier-filter").forEach((input) => { input.disabled = !state.data; });
  $$("#default-source, #monthly-cap").forEach((input) => { input.disabled = !state.data || state.saving; });
  $("#save-settings").disabled = !state.data || !state.dirty || state.saving;
  $("#reset-settings").disabled = !state.data || !state.dirty || state.saving;
  $("#settings-form").setAttribute("aria-busy",String(!state.data || state.saving));
  if (!state.data) $$(".run-button").forEach((button) => { button.disabled = true; });
}

function renderOperationalNotices() {
  const notices = state.data.operational_notices || [];
  const panel = $("#operational-notices");
  const signature = JSON.stringify(notices);
  const content = notices.map((notice) => `<div class="notice run-notice">${icon("info")}<p>${escapeHTML(notice.message)}</p></div>`).join("");
  if (panel.dataset.noticeSignature !== signature) {
    panel.innerHTML = content;
    panel.dataset.noticeSignature = signature;
  }
  panel.hidden = !notices.length;
}

function showError(message) {
  $("#error-text").textContent = message;
  $("#error-banner").hidden = false;
}
function clearError() { $("#error-banner").hidden = true; }
function toast(message) {
  clearTimeout(state.toastTimer);
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  state.toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 6500);
}
function errorMessage(code, fallback) {
  const messages = {
    REPORT_STALE:"This report needs to be refreshed. Run the demo again to create a report using current review decisions.",
    ARTIFACT_STALE:"This report is out of date. Run the demo again to create a current report.",
    REPORT_NOT_FOUND:"This run has no report available yet. Refresh the run history after processing finishes.",
    RUN_ALREADY_ACTIVE:"A run is already in progress. You can follow it in Run history.",
    DASHBOARD_RUN_ACTIVE:"A run is already in progress. You can follow it in Run history.",
    CSRF_REQUIRED:"Your dashboard session changed. Refresh the page, then try again.",
    INVALID_CSRF:"Your dashboard session changed. Refresh the page, then try again.",
    DASHBOARD_CSRF:"Your dashboard session changed. Refresh the page, then try again.",
    DASHBOARD_CSRF_REQUIRED:"Your dashboard session changed. Refresh the page, then try again.",
  };
  if (messages[code]) return messages[code];
  if (/STALE|AUTHORITY.*CHANGED/.test(code || "")) return messages.REPORT_STALE;
  if (/EXPIRED|ERASED|DELETED/.test(code || "")) return "This report has expired or was removed. Refresh the workspace to see available records.";
  return fallback;
}
async function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const headers = {Accept:"application/json",...(options.body ? {"Content-Type":"application/json","X-Dashboard-CSRF":state.data?.csrf_token || ""} : {})};
    const response = await fetch(url, {...options,headers,signal:controller.signal,cache:"no-store"});
    const data = await response.json();
    if (!response.ok) {
      const code = data?.code || data?.detail?.code || (typeof data?.detail === "string" ? data.detail : "");
      const error = new Error(errorMessage(code, response.status === 422 ? "Check the values and try again. The usage limit must be between A$0 and A$150." : `The request could not be completed (${response.status}). Refresh the workspace and try again.`));
      error.definitiveRejection = [400,401,403,404,409,415,422,429].includes(response.status);
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The engine took too long to respond. Refresh to check its status before trying again.");
    if (error instanceof SyntaxError) throw invalidResponse(url === "/api/settings" ? "settings" : url === "/api/runs" ? "run" : "dashboard");
    if (error instanceof TypeError) throw new Error("The local engine is not reachable. Open Start-Dashboard.cmd, then try again.");
    throw error;
  } finally { clearTimeout(timeout); }
}

function navigate() {
  const view = ["leads","runs","setup"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "leads";
  $$(".view").forEach((section) => { section.hidden = section.id !== `view-${view}`; });
  $$("[data-view]").forEach((link) => {
    if (link.dataset.view === view) link.setAttribute("aria-current","page");
    else link.removeAttribute("aria-current");
  });
  $("#breadcrumb-current").textContent = {leads:"Latest leads",runs:"Run history",setup:"Setup & settings"}[view];
  document.title = `${$("#breadcrumb-current").textContent} · ABN Lead Engine`;
}

function filteredLeads() {
  const query = $("#lead-search").value.trim().toLowerCase();
  const source = $("#source-filter").value;
  const tier = $("#tier-filter").value;
  return (state.data?.leads || []).filter((lead) => {
    const nameMatch = String(lead.business_name || "").toLowerCase().includes(query);
    const abnMatch = query.replace(/\s/g, "") && String(lead.abn || "").includes(query.replace(/\s/g, ""));
    return (!query || nameMatch || abnMatch) && (source === "all" || String(lead.source).toLowerCase() === source) && (tier === "all" || lead.tier === tier);
  });
}

function renderLeads() {
  if (!state.data) return;
  const focusedLead = document.activeElement?.closest("[data-lead-id]")?.dataset.leadId;
  const leads = filteredLeads();
  const total = state.data?.leads?.length || 0;
  $("#lead-count").textContent = `(${leads.length})`;
  $("#lead-list").setAttribute("aria-busy","false");
  $("#list-footer").textContent = `${leads.length} of ${total} stored businesses · Sample data`;
  if (!leads.some((lead) => lead.lead_id === state.selected)) state.selected = leads[0]?.lead_id || null;
  $("#lead-list").innerHTML = leads.length ? leads.map((lead) => `<button class="lead-row" data-lead-id="${escapeHTML(lead.lead_id)}" aria-pressed="${lead.lead_id === state.selected}"><span><span class="lead-name">${escapeHTML(lead.business_name || "Name not recorded")}</span><span class="lead-subline">${escapeHTML(sourceName(lead.source))}<span class="separator" aria-hidden="true">·</span>${lead.abn ? `ABN ${escapeHTML(formatABN(lead.abn))}` : "ABN not recorded"}</span></span><span class="lead-qualification"><span class="tier-badge tier-${escapeHTML(String(lead.tier || "").toLowerCase())}">${lead.tier ? `Tier ${escapeHTML(lead.tier)}` : "Unscored"}</span><span class="score">${Number.isFinite(lead.score) ? `${lead.score}/100` : "Score pending"}</span></span></button>`).join("") : `<div class="empty-state"><h3>${total ? "No businesses match these filters." : "Your review list starts with a run."}</h3><p>${total ? "Try another name or ABN, or clear the filters to see every stored business." : "Run the demo to collect sample businesses and prepare a review list."}</p><button class="button secondary" id="empty-action">${total ? "Clear filters" : "Run demo"}</button></div>`;
  $("#empty-action")?.addEventListener("click", () => {
    if (!total) return beginRun();
    $("#lead-search").value = ""; $("#source-filter").value = "all"; $("#tier-filter").value = "all"; renderLeads(); $("#lead-search").focus();
  });
  if (!total) {
    $("#empty-action").classList.add("run-button");
    $("#empty-action").disabled = state.running || state.saving || ["running","queued","pending"].includes(state.data.active_job?.state);
  }
  renderDetail(leads.find((lead) => lead.lead_id === state.selected));
  if (focusedLead) $$(".lead-row").find((row) => row.dataset.leadId === focusedLead)?.focus({preventScroll:true});
}

function renderDetail(lead) {
  const panel = $("#lead-detail");
  if (!lead) {
    panel.innerHTML = `<div class="detail-placeholder">${icon("file","large-icon")}<h3>A little context goes a long way.</h3><p>Select a business to see its source, qualification and next review step.</p></div>`;
    return;
  }
  const facts = [["Source",sourceName(lead.source)],["Location",lead.location || "Not recorded"],["First qualified",dateLabel(lead.first_observed_at,true)],["Signal",humanize(lead.signal)]];
  panel.innerHTML = `<div class="detail-top"><span>Business details</span><span class="tier-badge">${lead.tier ? `Tier ${escapeHTML(lead.tier)} · ${escapeHTML(lead.score ?? "—")}/100` : "Awaiting qualification"}</span></div><h3 class="detail-name">${escapeHTML(lead.business_name || "Name not recorded")}</h3><p class="detail-abn">ABN ${escapeHTML(formatABN(lead.abn))}</p><dl class="detail-facts">${facts.map(([name,value]) => `<div><dt>${name}</dt><dd>${escapeHTML(value)}</dd></div>`).join("")}</dl><div class="review-next"><h4>Next review step</h4><p>${escapeHTML(lead.next_action || "Review the current business identity and contact restrictions.")}</p>${lead.reason_codes?.length ? `<ul class="reason-list">${lead.reason_codes.map((reason) => `<li>${escapeHTML(humanize(reason))}</li>`).join("")}</ul>` : ""}</div><div class="detail-status">${icon("info")}<span>${escapeHTML(humanize(lead.state))} · Outreach disabled</span></div>`;
}

function safeReportURL(url) {
  return typeof url === "string" && /^\/api\/reports\/[0-9a-f-]{36}\/(html|csv|markdown)$/.test(url) ? url : null;
}
function renderRuns() {
  const focusedReport = document.activeElement?.closest(".report-link")?.getAttribute("href");
  const runs = state.data.runs || [];
  $("#runs-empty").hidden = Boolean(runs.length);
  $("#run-list").innerHTML = runs.map((run) => `<tr><td><span class="run-date">${escapeHTML(dateLabel(run.started_at,true))}</span><span class="run-id" title="${escapeHTML(run.run_id)}">${escapeHTML(String(run.run_id).slice(0,8))}</span></td><td>${escapeHTML(sourceName(run.source))}</td><td><span class="state-badge state-${escapeHTML(run.status)}">${run.status === "complete" ? icon("check") : ""}${escapeHTML(humanize(run.status))}</span></td><td>${escapeHTML(run.selected ?? "—")}</td><td>${run.reports && safeReportURL(run.reports.html) ? `<div class="report-actions"><a class="button small secondary report-link" href="${safeReportURL(run.reports.html)}" data-kind="html" target="_blank" rel="noopener">${icon("file")}Report</a>${safeReportURL(run.reports.csv) ? `<a class="button small secondary report-link" href="${safeReportURL(run.reports.csv)}" data-kind="csv" download>${icon("download")}CSV</a>` : ""}</div>` : `<span class="table-muted">${["running","pending","queued"].includes(run.status) ? "Preparing report" : "No current report"}</span>`}</td></tr>`).join("");
  const latest = runs.find((run) => safeReportURL(run.reports?.csv));
  if (focusedReport) $$(".report-link").find((link) => link.getAttribute("href") === focusedReport)?.focus({preventScroll:true});
  $$(".export-latest").forEach((button) => { button.disabled = !latest; button.dataset.url = latest?.reports?.csv || ""; });
  const job = state.data.active_job || (state.running ? {state:"queued",source:state.requestSource || state.data.settings.default_source} : state.data.latest_job);
  const active = job && ["running","queued","pending"].includes(job.state);
  $("#active-run").hidden = !job;
  if (job) $("#active-run").innerHTML = `${icon(active ? "clock" : job.state === "complete" ? "check" : "info")}<div><strong>${active ? "The engine is working on your run." : job.state === "complete" ? "Your run is complete." : "Your run needs attention."}</strong><p>${escapeHTML(sourceName(job.source))} · ${escapeHTML(humanize(job.state))}${job.error_code ? ` · ${escapeHTML(humanize(job.error_code))}. Review the setup and retry.` : active ? ". This page updates automatically." : ". Refresh to see the latest results."}</p></div>`;
  $$(".run-button").forEach((button) => {
    button.disabled = Boolean(active || state.running || state.saving || !state.data);
    button.innerHTML = `${icon(active || state.running ? "clock" : "play")}<span>${active || state.running ? "Run in progress" : "Run demo"}</span>`;
  });
  return Boolean(active);
}

function renderSetup() {
  if (!state.dirty && !state.saving) fillSettings();
  const budget = state.data.budget;
  if (budget) {
    const effective = new Intl.NumberFormat("en-AU",{style:"currency",currency:"AUD"}).format(budget.effective_cap_micro_aud / 1e6);
    $("#budget-note").textContent = `Effective limit this month: ${effective}${budget.frozen ? " (frozen)" : ""}. An existing monthly budget can keep this below your saved limit. Demo runs use free synthetic enrichment.`;
  }
  $("#source-list").innerHTML = (state.data.sources || []).map((source) => `<article class="source-item"><div class="source-item-heading"><h3>${sourceName(source.source) === "ABR" ? "Australian Business Register" : "QBCC contractor register"}</h3><span class="state-badge">${escapeHTML(humanize(source.status))}</span></div><p>Last processed: ${escapeHTML(dateLabel(source.last_success_at))}<br>Source published: ${escapeHTML(dateLabel(source.source_published_at))}</p></article>`).join("") || '<p class="field-hint">No accepted source snapshots yet. Run the demo to load sample sources.</p>';
  $("#setup-list").innerHTML = (state.data.setup || []).map((item) => {
    const ready = ["ready","complete","connected","available"].includes(item.status);
    return `<article class="setup-item ${ready ? "ready" : ""}">${icon(ready ? "check" : "info")}<div><h3>${escapeHTML(item.label)}</h3><p>${escapeHTML(item.detail)}</p></div></article>`;
  }).join("");
}
function fillSettings() {
  $("#default-source").value = state.data.settings.default_source;
  $("#monthly-cap").value = (state.data.settings.monthly_cap_micro_aud / 1e6).toFixed(2);
  updateDirty();
}
function updateDirty() {
  if (!state.data) return;
  const cap = $("#monthly-cap").value;
  state.dirty = $("#default-source").value !== state.data.settings.default_source || cap === "" || Math.round(Number(cap) * 1e6) !== state.data.settings.monthly_cap_micro_aud;
  $("#save-settings").disabled = !state.dirty || state.saving;
  $("#reset-settings").disabled = !state.dirty || state.saving;
  $("#save-status").textContent = state.dirty ? "Unsaved changes" : "";
  if (state.dirty) $("#settings-error").hidden = true;
}

function loadDashboard(manual = false) {
  state.refreshQueued = true;
  state.manualQueued = state.manualQueued || manual;
  if (!state.loadPromise) {
    state.loadPromise = (async () => {
      // A mutation or explicit refresh during an existing GET must receive a fresh snapshot.
      while (state.refreshQueued) {
        const nextManual = state.manualQueued;
        state.refreshQueued = false;
        state.manualQueued = false;
        await refreshDashboard(nextManual);
      }
    })().finally(() => { state.loadPromise = null; });
  }
  return state.loadPromise;
}

async function refreshDashboard(manual) {
  state.loading = true;
  clearTimeout(state.pollTimer);
  $$(".refresh-button").forEach((button) => { button.disabled = true; });
  try {
    const previousJob = state.data?.active_job;
    const generation = state.mutationGeneration;
    const data = validateDashboard(await request("/api/dashboard"));
    if (generation !== state.mutationGeneration) {
      state.refreshQueued = true;
      state.manualQueued = state.manualQueued || manual;
      return;
    }
    state.data = data;
    if (!state.actionError || manual) { clearError(); state.actionError = null; }
    $("#connection-dot").className = "status-dot ready";
    $("#connection-label").textContent = "Engine connected";
    const summary = state.data.summary;
    $("#total-leads").textContent = summary.total_leads ?? "—";
    $("#selected-leads").textContent = summary.selected ?? "—";
    $("#review-leads").textContent = summary.needs_review ?? "—";
    $("#last-run").textContent = summary.last_run_at ? dateLabel(summary.last_run_at,true) : "No runs yet";
    $("#nav-count").textContent = summary.total_leads ?? "0";
    renderLeads();
    const active = renderRuns();
    renderSetup();
    renderOperationalNotices();
    if (previousJob && ["running","queued","pending"].includes(previousJob.state) && state.data.latest_job?.state === "complete") toast("Run complete. Your latest leads and reports are ready.");
    else if (manual) toast("Workspace refreshed.");
    state.pollTimer = setTimeout(() => { if (!document.hidden) loadDashboard(); }, active ? 2500 : 30000);
  } catch (error) {
    showError(error.message);
    $("#connection-dot").className = "status-dot failed";
    $("#connection-label").textContent = "Engine unavailable";
    if (!state.data) {
      $("#lead-list").innerHTML = '<div class="empty-state"><h3>The engine is not connected.</h3><p>Open Start-Dashboard.cmd on this computer, then choose Try again.</p></div>';
      $("#lead-list").setAttribute("aria-busy","false");
      $("#list-footer").textContent = "Waiting for the local engine";
      $$(".run-button").forEach((button) => { button.disabled = true; });
    }
    state.pollTimer = setTimeout(() => { if (!document.hidden) loadDashboard(); },10000);
  } finally {
    state.loading = false;
    updateDataControls();
    $$(".refresh-button").forEach((button) => { button.disabled = false; });
  }
}

async function beginRun() {
  if (!state.data || state.running || state.saving || ["running","queued","pending"].includes(state.data.active_job?.state)) return;
  state.running = true;
  if (!state.requestId) { state.requestId = crypto.randomUUID(); state.requestSource = state.data.settings.default_source; }
  let failure = null;
  state.actionError = null;
  clearError();
  renderRuns();
  try {
    const job = await request("/api/runs", {method:"POST",body:JSON.stringify({source:state.requestSource,request_id:state.requestId})});
    if (!validJob(job)) throw invalidResponse("run");
    state.mutationGeneration++;
    state.data.active_job = job;
    state.requestId = null;
    state.requestSource = null;
    location.hash = "runs";
    toast("Demo run started. Follow its progress here.");
  } catch (error) {
    failure = error.message;
    if (error.definitiveRejection) { state.requestId = null; state.requestSource = null; }
  }
  finally { state.running = false; renderRuns(); await loadDashboard(); if (failure) { state.actionError = failure; showError(failure); } }
}

async function saveSettings(event) {
  event.preventDefault();
  if (!state.data || state.saving || !state.dirty) return;
  const cap = $("#monthly-cap").value;
  if (cap === "" || !Number.isFinite(Number(cap)) || Number(cap) < 0 || Number(cap) > 150) {
    $("#settings-error").textContent = "Enter an amount from A$0 to A$150.";
    $("#settings-error").hidden = false;
    $("#monthly-cap").focus();
    return;
  }
  state.saving = true;
  state.mutationGeneration++;
  $("#save-settings").textContent = "Saving…";
  $("#save-settings").disabled = true;
  $("#reset-settings").disabled = true;
  $("#default-source").disabled = true;
  $("#monthly-cap").disabled = true;
  $("#settings-error").hidden = true;
  renderRuns();
  try {
    const settings = await request("/api/settings",{method:"PATCH",body:JSON.stringify({default_source:$("#default-source").value,monthly_cap_micro_aud:Math.round(Number(cap) * 1e6)})});
    if (!validSettings(settings)) throw invalidResponse("settings");
    state.mutationGeneration++;
    state.data.settings = settings;
    state.dirty = false;
    $("#save-status").textContent = "Saved for the next run";
    toast("Run defaults saved on this computer.");
  } catch (error) {
    $("#settings-error").textContent = error.message;
    $("#settings-error").hidden = false;
  } finally {
    state.saving = false;
    $("#save-settings").textContent = "Save changes";
    $("#save-settings").disabled = !state.dirty;
    $("#reset-settings").disabled = !state.dirty;
    $("#default-source").disabled = false;
    $("#monthly-cap").disabled = false;
    updateDataControls();
    renderRuns();
    if (!state.dirty) await loadDashboard();
  }
}

async function openReport(url, kind) {
  if (!safeReportURL(url)) return;
  const reportWindow = kind === "html" ? window.open("about:blank","_blank") : null;
  if (reportWindow) { reportWindow.opener = null; reportWindow.document.title = "Opening report"; reportWindow.document.body.textContent = "Checking this report…"; }
  try {
    const response = await fetch(url,{cache:"no-store",signal:AbortSignal.timeout(20000)});
    if (!response.ok) {
      const data = await response.json();
      throw new Error(errorMessage(data.code || data.detail, "This report is unavailable. Refresh the workspace or run the demo to create a current report."));
    }
    if (kind === "html") {
      if (reportWindow) reportWindow.location.replace(url);
      else window.location.assign(url);
    } else {
      const objectURL = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectURL;
      anchor.download = "worklist.csv";
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(objectURL),30000);
      toast("Worklist CSV downloaded.");
    }
  } catch (error) {
    reportWindow?.close();
    state.actionError = error.name === "TimeoutError" ? "The report took too long to load. Refresh the workspace and try again."
      : error instanceof SyntaxError ? "The engine returned an incomplete report response. Refresh the workspace and try opening the report again."
      : error instanceof TypeError ? "The local engine is not reachable. Open Start-Dashboard.cmd, then try opening the report again."
      : error.message;
    showError(state.actionError);
    window.scrollTo({top:0,behavior:"instant"});
  }
}

window.addEventListener("hashchange",navigate);
$(".skip-link").addEventListener("click",(event) => { event.preventDefault(); $("#main").focus(); $("#main").scrollIntoView({block:"start",behavior:"instant"}); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) loadDashboard(); });
window.addEventListener("beforeunload", (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ""; } });
$("#lead-search").addEventListener("input",renderLeads);
$("#source-filter").addEventListener("change",renderLeads);
$("#tier-filter").addEventListener("change",renderLeads);
$("#lead-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-lead-id]");
  if (!button) return;
  state.selected = button.dataset.leadId;
  $$(".lead-row").forEach((row) => row.setAttribute("aria-pressed",row === button ? "true" : "false"));
  renderDetail(state.data.leads.find((lead) => lead.lead_id === state.selected));
  if (matchMedia("(max-width:700px)").matches) $("#lead-detail").scrollIntoView({block:"nearest",behavior:matchMedia("(prefers-reduced-motion:reduce)").matches ? "instant" : "smooth"});
});
$$(".run-button").forEach((button) => button.addEventListener("click",beginRun));
$$(".refresh-button").forEach((button) => button.addEventListener("click",() => loadDashboard(true)));
$("#retry-button").addEventListener("click",() => loadDashboard(true));
$("#settings-form").addEventListener("submit",saveSettings);
$("#settings-form").addEventListener("input",updateDirty);
$("#reset-settings").addEventListener("click",() => { state.dirty = false; fillSettings(); $("#settings-error").hidden = true; });
$("#run-list").addEventListener("click",(event) => { const link = event.target.closest(".report-link"); if (link) { event.preventDefault(); openReport(link.getAttribute("href"),link.dataset.kind); } });
$$(".export-latest").forEach((button) => button.addEventListener("click",() => openReport(button.dataset.url,"csv")));
navigate();
updateDataControls();
loadDashboard();
