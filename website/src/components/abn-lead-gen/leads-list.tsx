"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { dateLabel, formatABN, humanize, type LeadSource } from "@/lib/abn-lead-gen/types";
import type { ProspectSeed } from "@/lib/abn-lead-gen/prospects";
import { ProspectEditor } from "./prospects";
import { validSourceRecordPage, type RecordSource, type SourceRecordPage } from "./source-records";
import type { DashboardController } from "./use-dashboard";
import styles from "./dashboard.module.css";

const cls = (...names: string[]) => names.map(name => styles[name]).filter(Boolean).join(" ");
type PageState = { page?: SourceRecordPage; busy: boolean; error?: string };
type SourceRecord = SourceRecordPage["records"][number];
type Selection = { source: RecordSource; row: SourceRecord; page: SourceRecordPage };
const sourcesFor = (source: LeadSource): RecordSource[] => source === "all" ? ["abr", "qbcc"] : [source];
const rowKey = (source: RecordSource, row: SourceRecord) => `${source}:${source === "abr" ? row.abn : row.licence_number}`;
const nameFor = (source: RecordSource, row: SourceRecord) => String(row[source === "abr" ? "main_name" : "licensee_name"] || "Name not recorded");

export function LeadsList({ engine, active, reviewed, attribution }: { engine: DashboardController; active: boolean; reviewed: ReactNode; attribution: ReactNode }) {
  const [view, setView] = useState<"all" | "reviews">("all");
  const [source, setSource] = useState<LeadSource>("all");
  const [query, setQuery] = useState("");
  const [applied, setApplied] = useState("");
  const [pages, setPages] = useState<Partial<Record<RecordSource, PageState>>>({});
  const [selected, setSelected] = useState<Selection | null>(null);
  const [research, setResearch] = useState<ProspectSeed | null>(null);
  const [notice, setNotice] = useState("");
  const generation = useRef(0);
  const request = useRef(engine.request);
  const detail = useRef<HTMLElement>(null);
  const connected = engine.connected && !engine.signingOut;
  const allowed = !!engine.data?.scopes?.some(scope => ["admin", "reviewer", "compliance"].includes(scope));
  const visibleSources = sourcesFor(source);
  const busy = visibleSources.some(item => pages[item]?.busy);
  useEffect(() => { request.current = engine.request; }, [engine.request]);

  async function load(sources: RecordSource[], search: string, paging?: { source: RecordSource; offset: number; run: string }) {
    if (!connected || !allowed || !active) return;
    const id = ++generation.current;
    const filters = search.trim() ? { query: search.trim() } : {};
    if (!paging) { setSelected(null); setApplied(search.trim()); }
    setPages(previous => Object.fromEntries(sourcesFor("all").map(item => [item, sources.includes(item)
      ? { ...(paging ? previous[item] : {}), busy: true } : previous[item]])));
    await Promise.allSettled(sources.map(async item => {
      const offset = paging?.offset || 0;
      const run = paging?.run || "latest";
      try {
        const value = await request.current("source-records/query", { method: "POST", body: JSON.stringify({ source: item, run_id: run, offset, filters, sort: "source_order" }) });
        if (!validSourceRecordPage(value, item, run, offset, filters)) throw new Error("The business list response could not be verified. Try again.");
        if (generation.current !== id) return;
        setPages(previous => ({ ...previous, [item]: { page: value, busy: false } }));
        if (paging) setSelected(null);
      } catch (failure) {
        if (generation.current === id) setPages(previous => ({ ...previous, [item]: { ...previous[item], busy: false,
          error: failure instanceof Error ? failure.message : "These businesses could not be loaded. Try again." } }));
      }
    }));
  }
  useEffect(() => {
    const requestGeneration = generation;
    const timer = setTimeout(() => {
      if (!active) setResearch(null);
      if (!allowed) { setPages({}); setSelected(null); }
      else if (active && connected && view === "all") void load(sourcesFor(source), applied);
    }, 0);
    return () => { clearTimeout(timer); requestGeneration.current++; };
    // Explicit search and source changes load their own pages; a reconnect refreshes them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, connected, allowed, view]);
  function changeSource(next: LeadSource) { setSource(next); void load(sourcesFor(next), applied); }
  function choose(value: Selection) {
    setSelected(value);
    if (window.matchMedia("(max-width:700px)").matches) requestAnimationFrame(() => detail.current?.scrollIntoView({ block: "nearest" }));
  }
  const firstPage = visibleSources.map(item => pages[item]?.page).find(page => page?.records.length);
  const chosen = selected && visibleSources.includes(selected.source) ? selected : firstPage ? { source: firstPage.source, page: firstPage, row: firstPage.records[0] } : null;
  const scored = chosen && /^\d{11}$/.test(String(chosen.row.abn)) ? engine.data?.leads.find(lead => lead.source === chosen.source && lead.abn === chosen.row.abn) : undefined;
  const seed: ProspectSeed | null = chosen && /^\d{11}$/.test(String(chosen.row.abn)) && chosen.page.snapshot_id && chosen.page.run_id
    ? { abn: String(chosen.row.abn), business_name: nameFor(chosen.source, chosen.row), source: chosen.source, snapshot_id: chosen.page.snapshot_id, run_id: chosen.page.run_id } : null;

  return <section aria-label="Leads list." className={cls("view")}>
    <div className={cls("section-heading")}><div><h2>Leads list.</h2><p>Explore collected businesses at any score. Qualification is optional for browsing.</p></div><span className={cls("discovery-no-score")}>No minimum tier or score</span></div>
    <div className={cls("source-switch")} role="group" aria-label="Lead list view">
      <button className={cls("button", "secondary")} aria-pressed={view === "all"} onClick={() => setView("all")}>All businesses</button>
      <button className={cls("button", "secondary")} aria-pressed={view === "reviews"} onClick={() => setView("reviews")}>Qualification reviews</button>
    </div>
    <div hidden={view !== "reviews"}>{reviewed}</div>
    {active && view === "all" && <>
      <p className={cls("source-page-note")}>ABR and QBCC publications are listed separately, 50 records per source. The same business may appear in both. Use New · 7 days or New · 30 days above for recent ABN activity.</p>
      {!allowed && engine.data && <p role="status">A reviewer account is needed to browse collected businesses. Qualification reviews remain available.</p>}
      {!connected && <p role="status">Connect the engine to load the business list.</p>}
      <div className={cls("source-switch")} role="group" aria-label="Lead list sources">{(["all", "abr", "qbcc"] as const).map(item => <button key={item} className={cls("button", "secondary")} aria-pressed={source === item} disabled={!connected || !allowed || busy} onClick={() => changeSource(item)}>{item === "all" ? "All sources" : item.toUpperCase()}</button>)}</div>
      <form className={cls("lead-browse-search")} onSubmit={event => { event.preventDefault(); void load(visibleSources, query); }}>
        <label>Search lead list<input type="search" placeholder="Business name, ABN or QBCC licence…" maxLength={200} value={query} disabled={!connected || !allowed || busy} onChange={event => setQuery(event.target.value)} /></label>
        <button className={cls("button", "primary")} disabled={!connected || !allowed || busy}>Search businesses</button>
        <button type="button" className={cls("button", "secondary")} disabled={!connected || !allowed || busy} onClick={() => { setQuery(""); void load(visibleSources, ""); }}>Clear search</button>
      </form>
      {query.trim() !== applied && <p className={cls("source-page-note")}>Search changed. Choose Search businesses to apply it.</p>}
      {notice && <p role="status">{notice} <a href="#prospects">Open Saved prospects →</a></p>}
      <div className={cls("review-workspace")}>
        <div className={cls("lead-list-area")}>
          {visibleSources.map(item => { const state = pages[item]; const page = state?.page; return <section key={item} aria-label={`${item.toUpperCase()} businesses`} aria-busy={state?.busy || false}>
            <div className={cls("lead-source-heading")}><h3>{item.toUpperCase()} businesses</h3><span>{page ? `${page.total.toLocaleString("en-AU")} source records` : "Collected publication"}</span></div>
            {state?.busy && <p role="status" className={cls("list-footer")}>Loading {item.toUpperCase()} businesses…</p>}
            {state?.error && <p role="alert" className={cls("field-error")}>{state.error}{page && " Previous results are still shown."} <button className={cls("button", "secondary", "small")} disabled={busy || !connected || !allowed} onClick={() => void load([item], applied, page ? { source: item, offset: page.offset, run: page.run_id || "latest" } : undefined)}>Retry {item.toUpperCase()}</button></p>}
            {page && <>
              <div className={cls("lead-list")}>
                {page.records.map(row => { const known = /^\d{11}$/.test(String(row.abn)) ? engine.data?.leads.find(lead => lead.source === item && lead.abn === row.abn) : undefined; return <button type="button" key={rowKey(item, row)} className={cls("lead-row")} aria-pressed={!!chosen && rowKey(chosen.source, chosen.row) === rowKey(item, row)} onClick={() => choose({ source: item, row, page })}>
                  <span><span className={cls("lead-name")}>{nameFor(item, row)}</span><span className={cls("lead-subline")}>{item.toUpperCase()} · {row.abn ? `ABN ${formatABN(String(row.abn))}` : `Licence ${row.licence_number}`} · {[row.state, row.postcode].filter(Boolean).join(" ")}</span></span>
                  <span className={cls("lead-qualification")}><span className={cls("tier-badge")}>{known?.tier ? `Tier ${known.tier}` : "Source candidate"}</span><span className={cls("score")}>{typeof known?.score === "number" ? `${known.score}/100` : "No score required"}</span></span>
                </button>; })}
                {!page.records.length && <div className={cls("empty-state")}><h4>{page.source_state === "expired" ? "Publication expired" : page.source_state === "not_collected" ? "No accepted publication" : "No businesses match this search"}</h4><p>{page.source_state === "available" ? "Try another name, ABN or licence number." : "Check Source records and Run history for an available publication."}</p></div>}
              </div>
              <div className={cls("lead-source-footer")}><p>{page.records.length ? `${page.offset + 1}–${page.offset + page.records.length} of ${page.total.toLocaleString("en-AU")}` : "0 records shown"} · Source order</p><div className={cls("form-actions")}>
                <button className={cls("button", "secondary", "small")} disabled={busy || !connected || !allowed || !page.offset} onClick={() => void load([item], applied, { source: item, offset: page.offset - 50, run: page.run_id || "latest" })}>Previous {item.toUpperCase()} 50</button>
                <button className={cls("button", "secondary", "small")} disabled={busy || !connected || !allowed || page.next_offset === null} onClick={() => void load([item], applied, { source: item, offset: page.next_offset!, run: page.run_id || "latest" })}>Next {item.toUpperCase()} 50</button>
              </div></div>
            </>}
          </section>; })}
        </div>
        <section ref={detail} className={cls("lead-detail")} aria-label="Selected business details">
          {chosen ? <><div className={cls("detail-top")}><span>Business details</span><span className={cls("tier-badge")}>{scored?.tier ? `Tier ${scored.tier} · ${scored.score ?? "—"}/100` : "Source candidate"}</span></div>
            <h3 className={cls("detail-name")}>{nameFor(chosen.source, chosen.row)}</h3><p className={cls("detail-abn")}>{chosen.row.abn ? `ABN ${formatABN(String(chosen.row.abn))}` : "ABN not supplied"}</p>
            <dl className={cls("detail-facts")}><div><dt>Source</dt><dd>{chosen.source.toUpperCase()}</dd></div><div><dt>Location</dt><dd>{[chosen.row.state, chosen.row.postcode].filter(Boolean).join(" ") || "Not recorded"}</dd></div><div><dt>Publisher status</dt><dd>{humanize(String(chosen.row.status || "Not recorded"))}</dd></div><div><dt>{chosen.source === "abr" ? "ABN status from" : "Licence number"}</dt><dd>{chosen.source === "abr" ? dateLabel(String(chosen.row.status_date || "")) : String(chosen.row.licence_number)}</dd></div></dl>
            <div className={cls("review-next")}><h4>Research this business</h4><p>Check its website, email and social presence, then save your findings. A score is not required to start research.</p><button className={cls("button", "primary")} disabled={!seed || !connected || !allowed} onClick={() => setResearch(seed)}>Research selected business</button>{!seed && <p>A valid ABN and accepted publication are needed to save research.</p>}</div>
            <p className={cls("source-page-note")}>Imported {dateLabel(chosen.page.source_observed_at)}. Publisher dates and status do not prove first registration or permission to contact.</p>
          </> : <div className={cls("detail-placeholder")}><h3>Select a business</h3><p>Browse either source to inspect a business and begin research.</p></div>}
        </section>
      </div>
      {attribution}
    </>}
    {research && active && view === "all" && <ProspectEditor key={research.abn} seed={research} engine={engine} onClose={() => setResearch(null)} onSaved={() => setNotice("Research saved.")} />}
  </section>;
}
