"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { dateLabel, formatABN } from "@/lib/abn-lead-gen/types";
import { defaultDiscoveryMode, discoveryModes, discoveryRequest, publicationAgeDays, researchSummary, type DiscoveryMode, type DiscoverySearch } from "@/lib/abn-lead-gen/latest-leads";
import { validProspectPage, stageLabels, type Prospect, type ProspectPage, type ProspectSeed } from "@/lib/abn-lead-gen/prospects";
import { validSourceRecordPage, type SourceRecordPage } from "./source-records";
import { ProspectEditor } from "./prospects";
import type { DashboardController } from "./use-dashboard";
import styles from "./dashboard.module.css";

const cls = (...names: string[]) => names.map(name => styles[name]).filter(Boolean).join(" ");
type Results = { kind: "source"; page: SourceRecordPage; research: Prospect[]; researchAvailable: boolean }
  | { kind: "saved"; page: ProspectPage };
const emptySearch = { query: "", state: "" };
const failureText = (failure: unknown) => failure instanceof Error ? failure.message : "These businesses could not be loaded. Please try again.";

export function LatestLeadsView({ engine, reviewed, active = true }: { engine: DashboardController; reviewed: (active: boolean) => ReactNode; active?: boolean }) {
  const [mode, setMode] = useState<DiscoveryMode>(defaultDiscoveryMode);
  const [draft, setDraft] = useState<DiscoverySearch>(emptySearch);
  const [applied, setApplied] = useState<DiscoverySearch>(emptySearch);
  const [results, setResults] = useState<Results | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ProspectSeed | null>(null);
  const request = useRef(engine.request);
  const generation = useRef({ id: 0 });
  const connected = engine.connected && !engine.signingOut;
  const canReadResearch = !!engine.data?.scopes?.some(scope => ["admin", "reviewer", "compliance"].includes(scope));
  const recent = mode === "recent7" || mode === "recent30";
  useEffect(() => { request.current = engine.request; }, [engine.request]);

  async function load(nextMode: DiscoveryMode, search: DiscoverySearch, offset = 0, run = "latest") {
    const query = discoveryRequest(nextMode, search, offset, run);
    const id = ++generation.current.id;
    if (!query || !canReadResearch) { setBusy(false); return; }
    setBusy(true); setError(null); setResearchError(null);
    try {
      const result = await request.current(query.endpoint, { method: "POST", body: JSON.stringify(query.body) });
      if (generation.current.id !== id) return;
      if (query.endpoint === "source-records/query") {
        const filters = query.body.filters as SourceRecordPage["filters"];
        if (!validSourceRecordPage(result, "abr", run, offset, filters, "status_date_desc")) throw new Error("The recent-business response could not be verified. Refresh to try again.");
        setResults({ kind: "source", page: result, research: [], researchAvailable: result.records.length === 0 });
        setApplied(search);
        if (result.records.length && canReadResearch) {
          try {
            const abns = result.records.map(row => String(row.abn));
            const research = await request.current("prospects/query", { method: "POST", body: JSON.stringify({ offset: 0, filters: {}, abns }) });
            if (!validProspectPage(research, 0) || research.next_offset !== null || research.records.some(row => !abns.includes(row.abn))) throw new Error("Saved research could not be verified.");
            if (generation.current.id === id) setResults({ kind: "source", page: result, research: research.records, researchAvailable: true });
          } catch (failure) {
            if (generation.current.id === id) setResearchError(`${failureText(failure)} Recent businesses are still listed; website status is unavailable until research loads.`);
          }
        }
      } else {
        if (!validProspectPage(result, offset)) throw new Error("The saved-business response could not be verified. Refresh to try again.");
        setResults({ kind: "saved", page: result }); setApplied(search);
      }
    } catch (failure) { if (generation.current.id === id) setError(failureText(failure)); }
    finally { if (generation.current.id === id) setBusy(false); }
  }
  useEffect(() => {
    const state = generation.current;
    const timer = setTimeout(() => {
      if (!active) setSelected(null);
      if (!canReadResearch) { setResults(null); setResearchError(null); setBusy(false); }
      else if (connected && active) void load(mode, applied);
    }, 0);
    return () => { clearTimeout(timer); state.id++; };
    // Navigation and filters issue their own queries. Reconnection refreshes the chosen focus.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, canReadResearch, active]);
  function changeMode(next: DiscoveryMode) {
    generation.current.id++; setMode(next); setDraft(emptySearch); setApplied(emptySearch); setResults(null); setError(null); setResearchError(null);
    if (connected) void load(next, emptySearch);
  }
  const currentRun = results?.kind === "source" ? results.page.run_id || "latest" : "latest";
  const rows = results?.kind === "source" ? results.page.records.map(row => ({
    seed: { abn: String(row.abn), business_name: String(row.main_name), source: "abr" as const, snapshot_id: results.page.snapshot_id!, run_id: results.page.run_id! },
    location: [row.state, row.postcode].filter(Boolean).join(" "), statusDate: String(row.status_date || ""),
    research: results.research.find(item => item.abn === row.abn), researchAvailable: results.researchAvailable,
  })) : results?.page.records.map(row => ({ seed: row, location: "", statusDate: "", research: row, researchAvailable: true })) || [];
  const publication = results?.kind === "source" ? results.page : null;
  const age = publicationAgeDays(publication?.publisher_modified_at || null);
  const dirty = draft.query.trim() !== applied.query.trim() || draft.state !== applied.state;
  const forbidden = !!engine.data && mode !== "reviewed" && !canReadResearch;

  return <section id="view-leads" className={cls("view")} hidden={!active} aria-labelledby="discovery-title">
    <div className={cls("page-heading")}><div><span className={cls("prospect-eyebrow")}>Find your next conversation</span><h1 id="discovery-title">Latest leads.</h1><p>Start with a new business or a gap in their website presence. Research comes before a score.</p></div><div className={cls("heading-actions")}><button className={cls("button", "secondary")} disabled={!connected || busy || mode === "reviewed" || forbidden} onClick={() => void load(mode, applied)}>{busy ? "Loading…" : "Refresh leads"}</button></div></div>
    <div className={cls("discovery-focus")} role="group" aria-label="Choose lead focus">{discoveryModes.map(item => <button key={item.id} type="button" className={cls("discovery-focus-button")} aria-pressed={mode === item.id} onClick={() => changeMode(item.id)}><strong>{item.label}</strong><span>{item.description}</span></button>)}</div>
    <div hidden={mode !== "reviewed"}>{reviewed(active && mode === "reviewed")}</div>
    {active && mode !== "reviewed" && <>
      <div className={cls("discovery-context")}><p>{recent ? <>Active ABNs with a status date in the last {mode === "recent7" ? 7 : 30} days. No minimum score, tier, email or social requirement.</> : mode === "no_website" ? <>Businesses with a confirmed missing website in saved research, at any age. Having email or social media does not exclude them.</> : <>Saved businesses whose website presence is still unknown. Recent ABNs that have not been researched are also available under New · 7 days.</>}</p><a href="#sources">Browse all source records ↗</a></div>
      {!connected && <p role="status" className={cls("notice")}>{engine.loading ? "Connecting to the engine…" : "The engine is not connected. No new business data has been loaded. Refresh the workspace or check Setup."}</p>}
      {forbidden && <p role="status" className={cls("notice")}>A reviewer account is needed to browse source records and saved website research. Your existing reviewed leads remain available above.</p>}
      <form className={cls("discovery-search")} onSubmit={event => { event.preventDefault(); void load(mode, draft); }}>
        <label>Business name or ABN<input type="search" placeholder="Search this lead focus…" maxLength={200} value={draft.query} disabled={!connected || busy || forbidden} onChange={event => setDraft({ ...draft, query: event.target.value })} /></label>
        {recent && <label>State / territory<select aria-label="Discovery state" value={draft.state} disabled={!connected || busy || forbidden} onChange={event => setDraft({ ...draft, state: event.target.value })}><option value="">All locations</option>{["QLD", "NSW", "VIC", "SA", "WA", "TAS", "NT", "ACT", "AAT"].map(state => <option key={state}>{state}</option>)}</select></label>}
        <button className={cls("button", "primary")} type="submit" disabled={!connected || busy || forbidden}>Search leads</button>
        {(draft.query || draft.state) && <button className={cls("button", "secondary")} type="button" disabled={!connected || busy} onClick={() => { setDraft(emptySearch); void load(mode, emptySearch); }}>Clear search</button>}
      </form>
      {dirty && <p className={cls("source-page-note")}>Search changed. Apply it to update the results.</p>}
      {publication && <div className={cls("discovery-publication")} data-stale={age !== null && age >= (mode === "recent7" ? 7 : 30)}><p><strong>{age !== null && age >= (mode === "recent7" ? 7 : 30) ? "Publication predates this window" : "Source coverage"}</strong> · Published {dateLabel(publication.publisher_modified_at)} · Imported {dateLabel(publication.source_observed_at)}</p><p>ABR publishes weekly. Registrations after this publication are not included. The status date can be a reactivation; verify first registration in research.</p></div>}
      {error && <p role="alert" className={cls("field-error")}>{error}{results && " The last successful results are still shown."} <button type="button" className={cls("button", "secondary", "small")} disabled={!connected || busy} onClick={() => void load(mode, applied, results?.page.offset || 0, currentRun)}>Try again</button></p>}
      {researchError && <p role="status" className={cls("discovery-research-notice")}>{researchError}</p>}
      <div aria-busy={busy}>
        <div className={cls("section-heading", "discovery-results-heading")}><div><h2>{results ? `${results.page.total.toLocaleString("en-AU")} ${recent ? "recent candidates" : "saved businesses"}` : "Businesses to explore"}</h2><p>{recent ? "Newest ABN status date first · Full publication search" : "Most recently researched first · Saved research only"}</p></div><span className={cls("discovery-no-score")}>No score threshold</span></div>
        {busy && !results && <p role="status">Finding businesses for this lead focus…</p>}
        {publication?.source_state === "expired" ? <div className={cls("empty-state")}><h3>This source publication has expired.</h3><p>Choose a retained publication in Source records or inspect Run history.</p><a href="#sources">Open Source records →</a></div>
          : publication?.source_state === "not_collected" ? <div className={cls("empty-state")}><h3>No accepted ABR publication yet.</h3><p>Check source setup to load discovery records. Existing reviewed leads remain available above.</p><a href="#setup">Open Setup →</a></div>
          : results && !rows.length ? <div className={cls("empty-state", "discovery-empty")}><h3>{recent ? "No recent businesses in these results." : mode === "no_website" ? "No confirmed website gaps saved yet." : "No unchecked businesses saved yet."}</h3><p>{recent ? "The date window is based on today in Brisbane. Try 30 days or browse source records; an older publication may not cover this week." : "Open a recent business and save its research. A missing website field is not proof the business has no website."}</p><div className={cls("form-actions")}><button type="button" className={cls("button", "secondary")} onClick={() => changeMode(recent ? "recent30" : "recent7")}>{recent ? "Try last 30 days" : "Find recent businesses"}</button><a className={cls("button", "secondary")} href="#sources">Browse source records</a></div></div>
          : !!rows.length && <div className={cls("discovery-list")}>
            <div className={cls("discovery-row", "discovery-list-header")}><span>Business</span><span>Why it is here</span><span>Website & contact</span><span>Next step</span></div>
            {rows.map(({ seed, location, statusDate, research, researchAvailable }) => {
              const summary = researchSummary(research, researchAvailable);
              return <article key={seed.abn} className={cls("discovery-row")}>
                <div><h3>{seed.business_name}</h3><p>ABN {formatABN(seed.abn)}</p><small>{location || seed.source.toUpperCase()}</small></div>
                <div><span className={cls("discovery-reason")}>{recent ? "Recent ABN activity" : mode === "no_website" ? "Website opportunity" : "Research opportunity"}</span><p>{recent ? `Active since ${dateLabel(statusDate, true)}` : research?.registration_date ? `First registered ${dateLabel(research.registration_date, true)}` : "Any business age"}</p><small>{recent && !research?.registration_date ? "First registration unverified" : recent ? `First registered ${dateLabel(research?.registration_date, true)}` : "No score required"}</small></div>
                <div><span className={cls("discovery-website")} data-presence={summary.tone}>{summary.website}</span><p>{summary.contact}</p><small className={cls("discovery-contact-stage")} data-stage={research?.contact_stage}>{research ? stageLabels[research.contact_stage] : researchAvailable ? "No contact history saved" : "Contact history unavailable"}</small></div>
                <div><button className={cls("button", "secondary", "small")} disabled={!connected || !canReadResearch || !!selected || !seed.snapshot_id || !seed.run_id} onClick={() => setSelected(seed)}>{research ? "Open research" : "Research business"}</button><small>{research?.contact_stage === "follow_up" && research.follow_up_on ? `Follow up ${dateLabel(research.follow_up_on, true)}` : "Check fit & contact options"}</small></div>
              </article>;
            })}
          </div>}
        {results && <div className={cls("source-pagination")}><p role="status">{rows.length ? `${results.page.offset + 1}–${results.page.offset + rows.length} of ${results.page.total.toLocaleString("en-AU")}` : "0 businesses shown"}</p><div className={cls("form-actions")}><button className={cls("button", "secondary", "small")} disabled={!connected || busy || !results.page.offset} onClick={() => void load(mode, applied, results.page.offset - 50, currentRun)}>Previous 50</button><button className={cls("button", "secondary", "small")} disabled={!connected || busy || results.page.next_offset === null} onClick={() => void load(mode, applied, results.page.next_offset!, currentRun)}>Next 50</button></div></div>}
      </div>
      <p className={cls("source-page-note")}>These are prospects to investigate. Open research to check digital presence, save contact details and plan a conversation. Contact permission is reviewed separately.</p>
    </>}
    {selected && active && <ProspectEditor key={selected.abn} seed={selected} engine={engine} onClose={() => setSelected(null)} onSaved={() => void load(mode, applied, results?.page.offset || 0, currentRun)} />}
  </section>;
}
