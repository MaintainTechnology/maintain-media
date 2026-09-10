"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { UserButton } from "@clerk/nextjs";
import {
  type DashboardAdmin, type DashboardView, type Lead, type LeadSource, type ReportKind,
  dateLabel, formatABN, humanize, jobActive, safeReportURL, sourceName,
} from "@/lib/abn-lead-gen/types";
import { useDashboard, type DashboardController } from "./use-dashboard";
import { LeadActions, SourceReviews } from "./live-workflow";
import { readinessGuidance } from "./readiness";
import styles from "./dashboard.module.css";

const cx = (...names: string[]) => names.map(name => `${styles[name] || ""} ${name}`).join(" ");
type IconName = "leads" | "clock" | "settings" | "arrow" | "refresh" | "search" | "download" | "check" | "info" | "file" | "play" | "logout";
function Icon({ name }: { name: IconName }) {
  const shapes = {
    leads: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    settings: <><path d="M4 7h16M4 17h16" /><rect x="7" y="4" width="4" height="6" rx="1" /><rect x="14" y="14" width="4" height="6" rx="1" /></>,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    refresh: <path d="M20 7v5h-5M4 17v-5h5M6.5 6.5A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.5 5.5" />,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    download: <path d="M12 3v12m-4-4 4 4 4-4M4 16v4h16v-4" />,
    check: <path d="m5 12 4 4L19 6" />,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></>,
    file: <path d="M14 3H5v18h14V8l-5-5v5h5M8 12h8m-8 4h6" />,
    play: <path d="m8 5 11 7-11 7Z" />,
    logout: <path d="M10 4H4v16h6M10 12h10m-4-4 4 4-4 4" />,
  };
  return <svg className={cx("icon")} viewBox="0 0 24 24" aria-hidden="true">{shapes[name]}</svg>;
}
function RunButton({ engine }: { engine: DashboardController }) {
  const active = engine.running || jobActive(engine.data?.active_job);
  return <button type="button" className={cx("button", "primary", "run-button")} disabled={!engine.connected || !engine.data || engine.data.run_enabled === false || active || engine.saving || engine.signingOut} onClick={() => void engine.beginRun()}><Icon name={active ? "clock" : "play"} /><span>{active ? "Run in progress" : engine.data ? engine.data.mode === "fixture" ? "Run demo" : engine.data.run_enabled ? "Check source updates" : "Source worker required" : "Connect engine to run"}</span></button>;
}
function WorkspaceBadge({ engine }: { engine: DashboardController }) {
  return <span className={cx("mode-badge")}>{engine.data ? engine.data.mode === "fixture" ? engine.connected ? "Demo data" : "Sample data · Offline" : engine.connected ? "Live workspace" : "Stored data · Offline" : engine.loading ? "Checking connection" : "Engine not connected"}</span>;
}
function RefreshButton({ engine, small = false }: { engine: DashboardController; small?: boolean }) {
  return <button type="button" className={cx("button", "secondary", "refresh-button", ...(small ? ["small"] : []))} disabled={engine.loading || engine.signingOut} onClick={() => void engine.refresh(true)}><Icon name="refresh" />{engine.loading ? "Refreshing…" : "Refresh"}</button>;
}
function Detail({ lead }: { lead?: Lead }) {
  if (!lead) return <div className={cx("detail-placeholder")}><Icon name="file" /><h3>A little context goes a long way.</h3><p>Select a business to see its source, qualification and next review step.</p></div>;
  const facts = [["Source", sourceName(lead.source)], ["Location", lead.location || "Not recorded"], ["First qualified", dateLabel(lead.first_observed_at, true)], ["Signal", humanize(lead.signal)]];
  return <>
    <div className={cx("detail-top")}><span>Business details</span><span className={cx("tier-badge")}>{lead.tier ? `Tier ${lead.tier} · ${lead.score ?? "—"}/100` : "Awaiting qualification"}</span></div>
    <h3 className={cx("detail-name")}>{lead.business_name || "Name not recorded"}</h3><p className={cx("detail-abn")}>ABN {formatABN(lead.abn)}</p>
    <dl className={cx("detail-facts")}>{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <div className={cx("review-next")}><h4>Next review step</h4><p>{lead.next_action || "Review the current business identity and contact restrictions."}</p>{!!lead.reason_codes?.length && <ul className={cx("reason-list")}>{lead.reason_codes.map((reason, index) => <li key={`${reason}-${index}`}>{humanize(reason)}</li>)}</ul>}</div>
    <div className={cx("detail-status")}><Icon name="info" /><span>{humanize(lead.state)} · Outreach disabled</span></div>
  </>;
}
function LeadsView({ engine, hidden }: { engine: DashboardController; hidden: boolean }) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [tier, setTier] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const detailRef = useRef<HTMLElement>(null);
  const normalized = query.trim().toLowerCase();
  const abnQuery = normalized.replace(/\s/g, "");
  const all = engine.data?.leads || [];
  const leads = all.filter(lead => (!normalized || (lead.business_name || "").toLowerCase().includes(normalized) || !!abnQuery && (lead.abn || "").includes(abnQuery)) && (source === "all" || lead.source.toLowerCase() === source) && (tier === "all" || lead.tier === tier));
  const chosen = leads.find(lead => lead.lead_id === selected) || leads[0];
  const latest = engine.data?.runs.find(run => safeReportURL(run.reports?.csv));
  const latestCSV = engine.data?.mode === "fixture" ? latest?.reports?.csv : engine.data?.worklist_csv;
  function selectLead(lead: Lead) {
    setSelected(lead.lead_id);
    if (window.matchMedia("(max-width:700px)").matches) requestAnimationFrame(() => detailRef.current?.scrollIntoView({ block: "nearest", behavior: window.matchMedia("(prefers-reduced-motion:reduce)").matches ? "instant" : "smooth" }));
  }
  function clearFilters() { setQuery(""); setSource("all"); setTier("all"); searchRef.current?.focus(); }
  return <section id="view-leads" className={cx("view")} hidden={hidden} aria-labelledby="leads-title">
    <div className={cx("page-heading")}><div><h1 id="leads-title">Latest businesses.<br className={cx("desktop-break")} /> Clearer next steps.</h1><p>Review the latest businesses collected by your engine.</p></div><div className={cx("heading-actions")}><RefreshButton engine={engine} /><RunButton engine={engine} /></div></div>
    <div className={cx("demo-note")}><Icon name="info" /><p>{engine.data ? engine.data.mode === "fixture" ? "These are sample businesses from the demo engine. " : "This workspace shows records saved in your Australian engine. Collection and hand-off follow the approval checks in Setup. " : engine.loading ? "Checking the engine connection. " : "The engine is not connected. No business data has been loaded. "}<a href="#setup">View current setup <span aria-hidden="true">→</span></a></p></div>
    <div className={cx("summary-strip")} aria-label="Lead summary"><div><span>Businesses in engine</span><strong id="total-leads">{engine.data?.summary.total_leads ?? "—"}</strong></div><div><span>Selected for review</span><strong id="selected-leads">{engine.data?.summary.selected ?? "—"}</strong></div><div><span>Needs review</span><strong id="review-leads">{engine.data?.summary.needs_review ?? "—"}</strong></div><div className={cx("last-run-stat")}><span>Latest run</span><strong id="last-run">{engine.data ? engine.data.summary.last_run_at ? dateLabel(engine.data.summary.last_run_at, true) : "No runs yet" : "—"}</strong></div></div>
    <div className={cx("section-heading")}><div><h2>Latest leads <span className={cx("count-label")} id="lead-count">{engine.data ? `(${leads.length})` : ""}</span></h2><p>Most recently qualified first. Select a business to inspect its details.</p></div><button type="button" className={cx("button", "secondary", "small", "export-latest")} disabled={!engine.connected || engine.signingOut || !safeReportURL(latestCSV)} onClick={() => { if (latestCSV) void engine.openReport(latestCSV, "csv"); }}><Icon name="download" />Export latest CSV</button></div>
    <div className={cx("filters")}><label className={cx("search-field")}><Icon name="search" /><span className={cx("sr-only")}>Search businesses or ABNs</span><input id="lead-search" ref={searchRef} disabled={!engine.data} type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search business name or ABN…" autoComplete="off" /></label><label className={cx("filter-field")}><span>Source</span><select id="source-filter" disabled={!engine.data} value={source} onChange={event => setSource(event.target.value)}><option value="all">All sources</option><option value="abr">ABR</option><option value="qbcc">QBCC</option></select></label><label className={cx("filter-field")}><span>Tier</span><select id="tier-filter" disabled={!engine.data} value={tier} onChange={event => setTier(event.target.value)}><option value="all">All tiers</option><option value="A">Tier A</option><option value="B">Tier B</option><option value="C">Tier C</option></select></label></div>
    <div className={cx("review-workspace")}><div className={cx("lead-list-area")}><div className={cx("list-heading")}><span>Business / source</span><span>Qualification</span></div><div id="lead-list" className={cx("lead-list")} aria-label="Businesses" aria-busy={!engine.data && engine.loading}>
      {!engine.data ? engine.loading ? <>{[0, 1, 2].map(index => <div key={index} className={cx("skeleton-row")} />)}</> : <div className={cx("empty-state")}><h3>The engine is not connected.</h3><p>Open Setup & settings to review the connection steps. If the engine has already been configured, choose Refresh to check again.</p></div> : leads.length ? leads.map(lead => <button type="button" key={lead.lead_id} className={cx("lead-row")} data-lead-id={lead.lead_id} aria-pressed={lead.lead_id === chosen?.lead_id} onClick={() => selectLead(lead)}><span><span className={cx("lead-name")}>{lead.business_name || "Name not recorded"}</span><span className={cx("lead-subline")}>{sourceName(lead.source)}<span className={cx("separator")} aria-hidden="true">·</span>{lead.abn ? `ABN ${formatABN(lead.abn)}` : "ABN not recorded"}</span></span><span className={cx("lead-qualification")}><span className={cx("tier-badge", `tier-${(lead.tier || "").toLowerCase()}`)}>{lead.tier ? `Tier ${lead.tier}` : "Unscored"}</span><span className={cx("score")}>{typeof lead.score === "number" ? `${lead.score}/100` : "Score pending"}</span></span></button>) : <div className={cx("empty-state")}><h3>{all.length ? "No businesses match these filters." : "Your review list starts with a run."}</h3><p>{all.length ? "Try another name or ABN, or clear the filters to see every stored business." : (engine.data.mode === "fixture" ? "Run the demo to collect sample businesses and prepare a review list." : "No businesses have been qualified yet. Review the source checks below or open Setup to see what is required.")}</p><button type="button" id="empty-action" className={cx("button", "secondary", ...(!all.length ? ["run-button"] : []))} disabled={!all.length && (!engine.connected || engine.data.run_enabled === false || engine.signingOut || engine.running || engine.saving || jobActive(engine.data.active_job))} onClick={() => all.length ? clearFilters() : void engine.beginRun()}>{all.length ? "Clear filters" : engine.data.mode === "fixture" ? "Run demo" : "Check source updates"}</button></div>}
    </div><div className={cx("list-footer")} id="list-footer">{engine.data ? `${leads.length} of ${all.length} loaded businesses · ${engine.data.mode === "fixture" ? "Sample data" : "Stored records"}` : engine.loading ? "Loading your workspace…" : "Waiting for the engine"}</div></div><section ref={detailRef} id="lead-detail" className={cx("lead-detail")} aria-label="Business details"><Detail lead={chosen} />{chosen && engine.data?.mode !== "fixture" && <LeadActions key={`${chosen.lead_id}:${chosen.row_id || "unselected"}`} lead={chosen} engine={engine} />}</section></div>
    {engine.data && engine.data.mode !== "fixture" && <SourceReviews engine={engine} />}
    <div className={cx("source-footnote")}><Icon name="info" /><p>ABR and QBCC records help find candidates. They do not establish revenue, buying intent or permission to contact. Contact details stay hidden in this dashboard.</p></div>
  </section>;
}
function RunsView({ engine, hidden }: { engine: DashboardController; hidden: boolean }) {
  const job = engine.data?.active_job || (engine.running ? { state: "queued", source: engine.data?.settings.default_source } : engine.data?.latest_job);
  const active = jobActive(job && { ...job, source: job.source || "all" });
  return <section id="view-runs" className={cx("view")} hidden={hidden} aria-labelledby="runs-title">
    <div className={cx("page-heading")}><div><h1 id="runs-title">Every run, in one place.</h1><p>Follow the engine’s progress and open the reports it creates.</p></div><RunButton engine={engine} /></div>
    <div id="active-run" className={cx("notice", "run-notice")} hidden={!job} aria-live="polite">{job && <><Icon name={active ? "clock" : job.state === "complete" ? "check" : "info"} /><div><strong>{active ? "The engine is working on your run." : job.state === "complete" ? "Your run is complete." : "Your run needs attention."}</strong><p>{sourceName(job.source)} · {humanize(job.state)}{"error_code" in job && job.error_code ? ` · ${humanize(job.error_code)}. Review the setup and retry.` : active ? ". This page updates automatically." : ". Refresh to see the latest results."}</p></div></>}</div>
    <div className={cx("section-heading")}><div><h2>Recent runs</h2><p>Reports reflect the selected worklist for that run.</p></div><RefreshButton engine={engine} small /></div>
    <div className={cx("runs-table-wrap")}><table className={cx("runs-table")}><thead><tr><th scope="col">Run</th><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Selected</th><th scope="col">Reports</th></tr></thead><tbody id="run-list">{engine.data?.runs.map(run => <tr key={run.run_id}><td><span className={cx("run-date")}>{dateLabel(run.started_at, true)}</span><span className={cx("run-id")} title={run.run_id}>{run.run_id.slice(0, 8)}</span></td><td>{sourceName(run.source)}</td><td><span className={cx("state-badge", `state-${run.status}`)}>{run.status === "complete" && <Icon name="check" />}{humanize(run.status)}</span></td><td>{run.selected ?? "—"}</td><td>{run.reports && safeReportURL(run.reports.html) ? <div className={cx("report-actions")}>{(["html", "csv", "markdown"] as ReportKind[]).map(kind => {
      const url = safeReportURL(run.reports?.[kind]);
      return url ? <button key={kind} type="button" className={cx("button", "small", "secondary", "report-link")} disabled={!engine.connected || engine.signingOut} data-kind={kind} onClick={() => void engine.openReport(url, kind)}><Icon name={kind === "html" ? "file" : "download"} />{kind === "html" ? "Report" : kind === "csv" ? "CSV" : "Markdown"}</button> : null;
    })}</div> : <span className={cx("table-muted")}>{["running", "pending", "queued"].includes(run.status) ? "Preparing report" : "No current report"}</span>}</td></tr>)}</tbody></table>
      {!engine.data && <div className={cx("empty-state")}><p>{engine.loading ? "Loading run history…" : "Run history will appear when the engine reconnects."}</p></div>}
      <div id="runs-empty" className={cx("empty-state")} hidden={!engine.data || !!engine.data.runs.length}><h3>Your first run starts here.</h3><p>{engine.data?.mode === "fixture" ? "Run the demo to process sample data and generate a review worklist." : "Source processing receipts appear here after an approved run. Check Setup for any missing approvals."}</p><RunButton engine={engine} /></div>
    </div>
  </section>;
}
function SetupView({ engine, hidden }: { engine: DashboardController; hidden: boolean }) {
  const budget = engine.data?.budget;
  const disabled = !engine.connected || !engine.data || engine.saving || engine.signingOut;
  return <section id="view-setup" className={cx("view")} hidden={hidden} aria-labelledby="setup-title">
    <div className={cx("page-heading")}><div><h1 id="setup-title">Make the engine work for you.</h1><p>Set your run defaults and see how your workspace is connected.</p></div><WorkspaceBadge engine={engine} /></div>
    <div className={cx("settings-layout")}><div><section className={cx("settings-section")} aria-labelledby="defaults-title"><h2 id="defaults-title">Run defaults</h2><p>Shared across this admin workspace. Changes apply to the next dashboard run.</p>
      <form id="settings-form" aria-busy={engine.loading || engine.saving} onSubmit={event => { event.preventDefault(); void engine.saveSettings(); }}>
        <div className={cx("form-field")}><label htmlFor="default-source">Data source</label><select id="default-source" name="default_source" disabled={disabled} value={engine.source} onChange={event => engine.editSettings(event.target.value as LeadSource, engine.cap)}><option value="all">ABR + QBCC</option><option value="abr">Australian Business Register (ABR)</option><option value="qbcc">QBCC contractor register</option></select><p className={cx("field-hint")}>{engine.data ? (engine.data.mode === "fixture" ? "Choose which sample source to process when you run the demo." : "The first live source is QBCC. Broader ABR processing needs its live feed completed and tested, followed by the pilot and release decisions.") : "Connect the engine before choosing a data source."}</p></div>
        <div className={cx("form-field")}><label htmlFor="monthly-cap">Monthly enrichment usage limit</label><div className={cx("money-input")}><span>A$</span><input id="monthly-cap" name="monthly_cap" type="number" inputMode="decimal" min="0" max="150" step="0.01" required disabled={disabled} value={engine.cap} onChange={event => engine.editSettings(engine.source, event.target.value)} aria-describedby="cap-hint settings-error" aria-invalid={!!engine.settingsError} /></div><p className={cx("field-hint")} id="cap-hint">A$0–150. Limits enrichment usage. Available after the engine connects.</p></div>
        <p id="settings-error" className={cx("field-error")} role="alert" hidden={!engine.settingsError}>{engine.settingsError}</p><div className={cx("form-actions")}><button className={cx("button", "primary")} id="save-settings" type="submit" disabled={disabled || !engine.dirty}>{engine.saving ? "Saving…" : "Save changes"}</button><button className={cx("button", "secondary")} id="reset-settings" type="button" disabled={disabled || !engine.dirty} onClick={engine.discardSettings}>Discard changes</button><span id="save-status" className={cx("save-status")} role="status">{engine.saveStatus}</span></div>
      </form></section>
      <p id="budget-note" className={cx("field-hint")}>{budget ? `Effective limit this month: ${new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" }).format(budget.effective_cap_micro_aud / 1e6)}${budget.frozen ? " (frozen)" : ""}. An existing monthly budget can keep this below your saved limit. ${engine.data?.mode === "fixture" ? "Demo runs use free synthetic enrichment." : "Paid enrichment still requires current approval and available budget."}` : "Connect the engine to see its stored usage limits. No budget information has been loaded."}</p>
      <section className={cx("settings-section")} aria-labelledby="sources-title"><h2 id="sources-title">Data sources</h2><p>Publication and processing dates come from the engine’s stored records.</p><div id="source-list" className={cx("source-list")}>{engine.data?.sources.length ? engine.data.sources.map(source => <article key={source.source} className={cx("source-item")}><div className={cx("source-item-heading")}><h3>{source.source === "abr" ? "Australian Business Register" : "QBCC contractor register"}</h3><span className={cx("state-badge")}>{humanize(source.status)}</span></div><p>Last processed: {dateLabel(source.last_success_at)}<br />Source published: {dateLabel(source.source_published_at)}</p></article>) : <p className={cx("field-hint")}>{engine.data ? (engine.data.mode === "fixture" ? "No accepted source snapshots yet. Run the demo to load sample sources." : "No accepted source snapshots yet. Review the current approval checks before running source collection.") : "Source information will appear when the engine connects."}</p>}</div></section>
    </div><aside className={cx("setup-aside")}><section aria-labelledby="readiness-title"><div className={cx("section-heading")}><h2 id="readiness-title">Workspace readiness</h2><Icon name="settings" /></div><div id="setup-list">{engine.data?.setup.map((item, index) => {
      const guidance = readinessGuidance(item, engine.data!.mode);
      return <article key={item.id || `${item.label}-${index}`} className={cx("setup-item", ...(guidance.ready ? ["ready"] : []))}><Icon name={guidance.ready ? "check" : "info"} /><div><div className={cx("setup-item-heading")}><h3>{item.label}</h3><span className={cx("setup-status")}>{guidance.statusLabel}</span></div><p>{guidance.summary}</p>{guidance.note && <p className={cx("setup-note")}>{guidance.note}</p>}{!!guidance.steps.length && <div className={cx("setup-next")}><h4>Next step · who can help</h4><dl>{guidance.steps.map((step, stepIndex) => <div key={stepIndex}><dt>{step.owner}</dt><dd>{step.action}</dd></div>)}</dl></div>}{guidance.technicalDetail && <details className={cx("setup-details")}><summary>Engine check details</summary><p>{guidance.technicalDetail}</p></details>}</div></article>;
    })}{!engine.data && <p className={cx("field-hint")}>{engine.loading ? "Checking the engine connection…" : "The engine is not connected. Its sources, integrations and release status have not been verified."}</p>}</div></section><div className={cx("setup-explainer")}><h3>{engine.data && engine.data.mode !== "fixture" ? "What you can do now" : engine.data ? "Ready for real businesses?" : "Connect the lead engine"}</h3>{engine.data && engine.data.mode !== "fixture" ? <><p>Review each blocked item with the person named above. The developer can enable its approved scope after the required decisions and setup tests are recorded.</p><p>Saving run defaults does not switch on collection or GoHighLevel hand-off. Refresh the page after setup changes to see the latest engine checks. Outreach stays disabled.</p></> : <><p>The hosted dashboard needs an Australian engine service with its database and backups, then a secure connection between that service and this website.</p><p>Live collection also needs approved source access, verified Google Sheet and GoHighLevel connections, matching accuracy checks and a completed release review.</p><p>Run and report controls stay unavailable while disconnected. You can still review setup, refresh the connection or sign out. Outreach stays disabled.</p></>}</div></aside></div>
  </section>;
}

export function LeadGenDashboard({ admin }: { admin: DashboardAdmin }) {
  const engine = useDashboard(admin);
  const [view, setView] = useState<DashboardView>("leads");
  useEffect(() => {
    const navigate = () => {
      const hash = window.location.hash.slice(1);
      const next = hash === "runs" || hash === "setup" ? hash : "leads";
      setView(next);
      document.title = `${{ leads: "Latest leads", runs: "Run history", setup: "Setup & settings" }[next]} · ABN Lead Engine · Maintain Media`;
    };
    const startup = setTimeout(navigate, 0);
    window.addEventListener("hashchange", navigate);
    return () => { clearTimeout(startup); window.removeEventListener("hashchange", navigate); };
  }, []);
  if (engine.expired) return <div className={cx("dashboard", "session-ended")}><Image src="/brand/logo-darkbg.svg" alt="Maintain Media" width={168} height={34} style={{ height: "auto" }} /><h1>Your admin workspace is locked.</h1><p role="alert">{engine.error}</p><a className={cx("button", "primary")} href={engine.accessDenied ? "/abn-lead-gen/access" : "/sign-in"}>{engine.accessDenied ? "View account access" : "Sign in again"} <Icon name="arrow" /></a><Link href="/">Back to Maintain Media</Link></div>;
  const label = { leads: "Latest leads", runs: "Run history", setup: "Setup & settings" }[view];
  const leaveWorkspace = (event: { preventDefault: () => void }) => {
    if (engine.dirty && !window.confirm("Discard your unsaved settings and leave the dashboard?")) event.preventDefault();
  };
  return <div className={cx("dashboard", "app-shell")}>
    <aside className={cx("sidebar")}><a className={cx("brand")} href="#leads" aria-label="Maintain Media — latest leads"><Image src="/brand/logo-darkbg.svg" alt="Maintain Media" width={168} height={34} style={{ height: "auto" }} priority /></a><div className={cx("workspace-label")}>ABN Lead Engine</div>
      <nav className={cx("navigation")} aria-label="Main navigation">{([{ view: "leads", label: "Latest leads", icon: "leads" }, { view: "runs", label: "Run history", icon: "clock" }, { view: "setup", label: "Setup & settings", icon: "settings" }] as const).map(item => <a key={item.view} href={`#${item.view}`} data-view={item.view} aria-label={item.view === "setup" ? "Setup and settings" : undefined} aria-current={view === item.view ? "page" : undefined}><Icon name={item.icon} /><span>{item.view === "setup" ? <>Setup<span className={cx("nav-long")}> & settings</span></> : item.label}</span>{item.view === "leads" && <span className={cx("nav-count")} id="nav-count">{engine.data?.summary.total_leads ?? "—"}</span>}</a>)}</nav>
      <div className={cx("sidebar-bottom")}><div className={cx("local-state")}><span id="connection-dot" className={cx("status-dot", engine.connected ? "ready" : engine.loading ? "connecting" : "failed")} /><span id="connection-label">{engine.connected ? "Engine connected" : engine.loading ? "Connecting" : engine.configurationRequired ? "Engine setup required" : "Engine unavailable"}</span></div><p>Private admin workspace<br />{engine.data ? engine.data.mode === "fixture" ? "Sample businesses only" : "Actual stored business records" : "Engine connection pending"}</p><a href="#setup" className={cx("text-link")}>View setup <Icon name="arrow" /></a><Link href="/" prefetch={false} onNavigate={leaveWorkspace} className={cx("text-link", "website-link")}>Maintain Media website <Icon name="arrow" /></Link></div>
    </aside>
    <div className={cx("main-shell")}><header className={cx("topbar")}><div className={cx("breadcrumb")}>Workspace <span>/</span> <strong id="breadcrumb-current">{label}</strong></div><div className={cx("admin-controls")}><WorkspaceBadge engine={engine} /><span className={cx("admin-name")} title={admin.username}>{admin.displayName}</span><UserButton afterSwitchSessionUrl="/abn-lead-gen/dashboard" appearance={{ elements: { userButtonPopoverActionButton__signOut: { display: "none" }, userButtonPopoverActionButton__signOutAll: { display: "none" } } }}><UserButton.MenuItems><UserButton.Action label="Sign out of workspace" labelIcon={<Icon name="logout" />} onClick={() => void engine.logout()} /></UserButton.MenuItems></UserButton><button id="admin-logout" type="button" className={cx("button", "secondary", "small")} disabled={engine.signingOut} onClick={() => void engine.logout()}><Icon name="logout" /><span>{engine.signingOut ? "Signing out…" : "Sign out"}</span></button></div></header>
      <div className={cx("content")}><div id="error-banner" className={cx("notice", "error-notice")} role="alert" hidden={!engine.error}><Icon name="info" /><p id="error-text">{engine.error}</p><button type="button" className={cx("button", "small", "secondary")} id="retry-button" disabled={engine.loading || engine.signingOut} onClick={() => void engine.refresh(true)}>Try again</button></div>
        <div id="operational-notices" role="status" aria-live="polite" aria-atomic="true" hidden={!engine.data?.operational_notices?.length}>{engine.data?.operational_notices?.map(notice => <div key={notice.code} className={cx("notice", "run-notice")}><Icon name="info" /><p>{notice.message}</p></div>)}</div>
        <LeadsView engine={engine} hidden={view !== "leads"} /><RunsView engine={engine} hidden={view !== "runs"} /><SetupView engine={engine} hidden={view !== "setup"} />
        <footer className={cx("page-footer")}><Link href="/" prefetch={false} onNavigate={leaveWorkspace}>Maintain Media <span aria-hidden="true">·</span> Back to website</Link><span>Admin workspace <span aria-hidden="true">·</span> Outreach disabled</span></footer>
      </div>
    </div>
    <div id="toast" className={cx("toast")} role="status" hidden={!engine.toast}>{engine.toast}</div>
  </div>;
}
