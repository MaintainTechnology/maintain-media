"use client";

import { useEffect, useRef, useState } from "react";
import { dateLabel, formatABN, humanize } from "@/lib/abn-lead-gen/types";
import { recentDates, type ProspectSeed } from "@/lib/abn-lead-gen/prospects";
import { ProspectEditor } from "./prospects";
import type { DashboardController } from "./use-dashboard";
import styles from "./dashboard.module.css";

export type RecordSource = "abr" | "qbcc";
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
type SourceRecord = Record<string, JsonValue>;
type SourceFilters = Partial<Record<"query" | "state" | "postcode" | "status" | "gst_status" | "entity_type" | "entity_class" | "financial_category" | "status_date_from" | "status_date_to", string>>;
export type SourceRecordPage = {
  source: RecordSource; run_id: string | null; snapshot_id: string | null;
  source_state: "available" | "not_collected" | "expired";
  source_observed_at: string | null; publisher_modified_at: string | null; publisher_extract_time: string | null;
  baseline: boolean; total: number; source_total: number; limit: number; offset: number;
  sort?: "source_order" | "status_date_desc";
  next_offset: number | null; records: SourceRecord[]; columns: string[]; filters: SourceFilters;
};
const cls = (...names: string[]) => names.map(name => styles[name]).filter(Boolean).join(" ");
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;
const uuid = (value: unknown) => typeof value === "string" && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value);
const fields: Record<RecordSource, string[]> = {
  abr: ["abn", "main_name", "status", "status_date", "gst_status", "gst_date", "entity_type", "entity_class", "state", "postcode", "names_json", "name_hash", "semantic_hash", "source_member"],
  qbcc: ["licence_number", "licensee_name", "abn", "financial_category", "original_address", "state", "postcode", "status", "entity_class", "row_digest", "class_types", "geography_review_required", "acn", "financial_category_description", "licence_review_required", "licence_grades", "licence_types"],
};
const clean = (filters: SourceFilters): SourceFilters => Object.fromEntries(Object.entries(filters).filter(([, value]) => value?.trim()).map(([key, value]) => [key, value!.trim()]));
const sameFilters = (left: SourceFilters, right: SourceFilters) => JSON.stringify(Object.entries(clean(left)).sort()) === JSON.stringify(Object.entries(clean(right)).sort());
const jsonValue = (value: unknown, depth = 0): boolean => value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "number" && Number.isFinite(value)
  || depth < 8 && (Array.isArray(value) ? value.every(item => jsonValue(item, depth + 1)) : object(value) && Object.values(value).every(item => jsonValue(item, depth + 1)));
export function validSourceRecordPage(value: unknown, source: RecordSource, run: string, offset: number, filters: SourceFilters = {}, sort = "source_order"): value is SourceRecordPage {
  return object(value) && value.source === source && ["available", "not_collected", "expired"].includes(String(value.source_state))
    && (value.sort || "source_order") === sort
    && (value.run_id === null || uuid(value.run_id)) && (run === "latest" || value.run_id === run)
    && (value.snapshot_id === null || uuid(value.snapshot_id))
    && [value.source_observed_at, value.publisher_modified_at, value.publisher_extract_time].every(item => item === null || typeof item === "string")
    && typeof value.baseline === "boolean" && count(value.total) && count(value.source_total) && value.total <= value.source_total && value.limit === 50 && value.offset === offset
    && (value.next_offset === null || value.next_offset === offset + 50 && value.next_offset < value.total)
    && object(value.filters) && Object.values(value.filters).every(item => typeof item === "string") && sameFilters(value.filters as SourceFilters, filters)
    && Array.isArray(value.columns) && value.columns.length === fields[source].length && new Set(value.columns).size === value.columns.length && fields[source].every(key => (value.columns as unknown[]).includes(key))
    && Array.isArray(value.records) && value.records.length <= 50 && value.records.every(row => object(row)
      && (source === "abr" ? typeof row.abn === "string" && typeof row.main_name === "string" : typeof row.licence_number === "string" && typeof row.licensee_name === "string")
      && Object.keys(row).length === (value.columns as string[]).length && (value.columns as string[]).every(key => Object.hasOwn(row, key)) && Object.values(row).every(item => jsonValue(item)));
}
const labels: Record<string, string> = {
  abn: "ABN", main_name: "Business name", licensee_name: "Licensee", licence_number: "Licence number", acn: "ACN",
  status: "Publisher status", status_date: "Status from", gst_status: "GST status", gst_date: "GST from",
  entity_type: "Entity type code", entity_class: "Entity class", names_json: "All published names", state: "State", postcode: "Postcode",
  financial_category: "Financial category", financial_category_description: "Category description", original_address: "Published address",
  licence_types: "Licence types", licence_grades: "Licence grades", class_types: "Licence classes", geography_review_required: "Location review required",
  licence_review_required: "Licence review required", source_member: "Source file", name_hash: "Name hash", semantic_hash: "Record hash", row_digest: "Record hash",
};
const statusLabel = (value: JsonValue | undefined) => ({ ACT: "Active", CAN: "Cancelled", NON: "Not registered", NONE: "Not supplied", UNKNOWN: "Not supplied" }[String(value)] || humanize(String(value || "")));
function Value({ value }: { value: JsonValue | undefined }) {
  if (value == null || value === "") return <>—</>;
  if (typeof value === "boolean") return <>{value ? "Yes" : "No"}</>;
  if (Array.isArray(value)) return value.length ? <ul className={cls("source-cell-list")}>{value.map((item, index) => <li key={index}><Value value={item} /></li>)}</ul> : <>None recorded</>;
  if (typeof value === "object") return <dl className={cls("source-cell-details")}>{Object.entries(value).map(([key, item]) => <div key={key}><dt>{humanize(key)}</dt><dd><Value value={item} /></dd></div>)}</dl>;
  return <>{String(value)}</>;
}
function RecordCell({ row, field, source }: { row: SourceRecord; field: string; source: RecordSource }) {
  const value = row[field];
  if (field === "abn" && typeof value === "string" && /^\d{11}$/.test(value)) return <><span className={cls("source-identifier")}>{formatABN(value)}</span><a href={`https://abr.business.gov.au/ABN/View?id=${value}`} target="_blank" rel="noreferrer">Check current ABN ↗</a></>;
  if (field === "status" || field === "gst_status") return <>{field === "gst_status" && value === "ACT" ? "Registered" : statusLabel(value)}<span>{String(value || "")}</span>{source === "qbcc" && field === "status" && <a href="https://my.qbcc.qld.gov.au/s/qbcc-licensee-register" target="_blank" rel="noreferrer">Check current licence ↗</a>}</>;
  if (field === "names_json" && typeof value === "string") {
    let names: JsonValue = value;
    try { names = JSON.parse(value) as JsonValue; } catch { /* Keep the stored text if it cannot be parsed. */ }
    return <Value value={names} />;
  }
  return <Value value={value} />;
}
export function SourceRecordTable({ data }: { data: SourceRecordPage }) {
  const name = data.source === "abr" ? "main_name" : "licensee_name";
  const columns = [name, ...data.columns.filter(field => field !== name)];
  return <div className={cls("source-table-wrap")} role="region" aria-label={`${data.source.toUpperCase()} source records table`} tabIndex={0}>
    <table className={cls("source-table")}><caption className={cls("sr-only")}>{data.source.toUpperCase()} parsed source records · all {columns.length} stored fields</caption>
      <thead><tr>{columns.map(field => <th key={field} scope="col" title={field}>{field === "status" && data.source === "abr" ? "ABN status" : labels[field] || humanize(field)}</th>)}</tr></thead>
      <tbody>{data.records.map((row, index) => <tr key={`${String(row.abn || row.licence_number)}:${index}`}>{columns.map(field => field === name
        ? <th key={field} scope="row"><strong><RecordCell row={row} field={field} source={data.source} /></strong></th>
        : <td key={field} data-field={field}><RecordCell row={row} field={field} source={data.source} /></td>)}</tr>)}</tbody>
    </table>
  </div>;
}

export function SourceRecords({ engine, source, initialRun = "latest" }: { engine: DashboardController; source: RecordSource; initialRun?: string }) {
  const [run, setRun] = useState(initialRun);
  const [data, setData] = useState<SourceRecordPage | null>(null);
  const [draft, setDraft] = useState<SourceFilters>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [downloadNote, setDownloadNote] = useState<string | null>(null);
  const [layout, setLayout] = useState<"fields" | "prospects">("fields");
  const [selected, setSelected] = useState<ProspectSeed | null>(null);
  const generation = useRef({ id: 0 });
  const mounted = useRef(false);
  const request = useRef(engine.request);
  useEffect(() => { request.current = engine.request; }, [engine.request]);
  const connected = engine.connected && !engine.signingOut;
  const runs = engine.data?.runs.filter(item => item.source === source && item.status === "complete") || [];
  const label = source.toUpperCase();
  async function load(selectedRun: string, offset: number, filters: SourceFilters = {}) {
    const current = ++generation.current.id;
    setBusy(true); setError(null); setDownloadNote(null);
    const selectedFilters = clean(filters);
    try {
      const response = await request.current("source-records/query", { method: "POST", body: JSON.stringify({ source, run_id: selectedRun, offset, filters: selectedFilters }) });
      if (!validSourceRecordPage(response, source, selectedRun, offset, selectedFilters)) throw new Error("The source records response is incomplete. Please refresh the records.");
      if (mounted.current && current === generation.current.id) setData(response);
    } catch (failure) {
      if (mounted.current && current === generation.current.id) setError(failure instanceof Error ? failure.message : "Source records could not be loaded. Please try again.");
    } finally { if (mounted.current && current === generation.current.id) setBusy(false); }
  }
  useEffect(() => {
    const state = generation.current;
    mounted.current = true;
    return () => { mounted.current = false; state.id++; };
  }, []);
  useEffect(() => {
    if (!connected) return;
    const state = generation.current;
    const timer = setTimeout(() => { void load(run, 0, draft); }, 0);
    return () => { clearTimeout(timer); state.id++; };
    // The active source view is mounted on entry; reconnect also refreshes it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected]);
  async function download(filtered: boolean) {
    if (!data?.run_id || !data.snapshot_id) return;
    const current = generation.current.id;
    setExporting(true); setError(null); setDownloadNote(null);
    try {
      const response = await request.current("source-exports", { method: "POST", body: JSON.stringify({ source, run_id: data.run_id, filters: filtered ? data.filters : {} }) });
      if (!object(response) || response.source !== source || response.run_id !== data.run_id || response.snapshot_id !== data.snapshot_id
        || response.download_url !== "https://abn-engine.maintainmedia.com.au/api/source-exports/download"
        || typeof response.download_token !== "string" || !/^[A-Za-z0-9_-]{32,256}$/.test(response.download_token)
        || typeof response.expires_at !== "string" || !Number.isFinite(Date.parse(response.expires_at)) || Date.parse(response.expires_at) <= Date.now()) throw new Error("The download could not be verified. Please try again.");
      if (!mounted.current || current !== generation.current.id) return;
      const form = document.createElement("form");
      form.method = "POST"; form.action = response.download_url; form.target = "_blank"; form.hidden = true; form.rel = "noopener";
      const ticket = document.createElement("input"); ticket.type = "hidden"; ticket.name = "ticket"; ticket.value = response.download_token;
      form.append(ticket); document.body.append(form);
      try { form.submit(); } finally { form.remove(); }
      setDownloadNote(`Download requested for ${(filtered ? data.total : data.source_total).toLocaleString("en-AU")} records. Check your browser’s downloads for completion. Large ABR exports can take several minutes.`);
    } catch (failure) {
      if (mounted.current && current === generation.current.id) setError(failure instanceof Error ? failure.message : "The CSV download could not be started.");
    } finally { if (mounted.current) setExporting(false); }
  }
  function input(field: keyof SourceFilters, value: string) { setDraft(previous => ({ ...previous, [field]: value })); }
  function select(field: keyof SourceFilters, title: string, options: [string, string][]) {
    return <label htmlFor={`${source}-filter-${field}`}>{title}<select id={`${source}-filter-${field}`} value={draft[field] || ""} onChange={event => input(field, event.target.value)}><option value="">All</option>{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>;
  }
  const dirty = data && !sameFilters(draft, data.filters);
  const filtered = data && Object.keys(data.filters).length > 0;
  function recent(days: number) {
    const dates = recentDates(days);
    const next = { ...draft, status: "ACT", status_date_from: dates.from, status_date_to: dates.to };
    setDraft(next); setLayout("prospects"); void load(data?.run_id || run, 0, next);
  }
  return <section id={`${source}-source-records`} className={cls("settings-section", "source-review-section")} aria-labelledby={`${source}-source-title`}>
    <div className={cls("section-heading")}><div><h2 id={`${source}-source-title`}>{label} source review</h2>
      <p>{source === "abr" ? "ABN and GST registration as recorded in this publication. Use Check current ABN to review today’s registration in ABN Lookup." : "All collected financial categories and licence details. Current licence status needs a check in the QBCC register."}</p></div>
      <button type="button" className={cls("button", "secondary")} disabled={busy || !connected} onClick={() => void load(run, 0, data?.filters || {})}>{busy ? "Loading…" : "Refresh records"}</button>
    </div>
    {source === "abr" && <div className={cls("prospect-discovery")}>
      <div><span className={cls("prospect-eyebrow")}>Find businesses in their first days</span><h3>Recent ABN registrations to research</h3><p>Start with recent active-status dates, then verify first registration and digital presence.</p></div>
      <div className={cls("source-switch")} role="group" aria-label="Recent ABN date filters">{[7, 14, 30].map(days => {
        const dates = recentDates(days);
        return <button key={days} type="button" className={cls("button", "secondary")} disabled={!connected || busy} aria-pressed={data?.filters.status === "ACT" && data.filters.status_date_from === dates.from && data.filters.status_date_to === dates.to} onClick={() => recent(days)}>Last {days} days</button>;
      })}<a className={cls("button", "secondary")} href="#prospects">Saved prospects →</a></div>
      <p className={cls("source-page-note")}>Includes registrations and possible reactivations. The last 7 days means today plus the previous 6 days, in Brisbane time. Confirm the original registration before marking a business as new.</p>
    </div>}
    <div className={cls("source-record-controls")}><label htmlFor={`${source}-record-run`}>Source run<select id={`${source}-record-run`} value={run} disabled={!connected} onChange={event => {
      const next = event.target.value; generation.current.id++; setRun(next); setData(null); setError(null); void load(next, 0, draft);
    }}><option value="latest">Latest accepted {label} publication</option>{initialRun !== "latest" && !runs.some(item => item.run_id === initialRun) && <option value={initialRun}>{initialRun.slice(0, 8)}</option>}{runs.map(item => <option key={item.run_id} value={item.run_id}>{dateLabel(item.started_at, true)} · {item.run_id.slice(0, 8)}{item.result?.baseline ? " · Baseline" : ""}</option>)}</select></label>
      <p>{data ? `${data.source_total.toLocaleString("en-AU")} records in this source publication` : connected ? "Loading the accepted publication automatically…" : "Waiting for the engine connection…"}</p>
    </div>
    <form className={cls("source-filter-form")} onSubmit={event => { event.preventDefault(); void load(data?.run_id || run, 0, draft); }}>
      <fieldset disabled={!connected || busy}><legend className={cls("sr-only")}>Filter {label} source records</legend>
        <label className={cls("source-query")} htmlFor={`${source}-source-query`}>Search by ABN, business name{source === "qbcc" ? " or licence number" : ""}<input id={`${source}-source-query`} type="search" autoComplete="off" maxLength={200} value={draft.query || ""} onChange={event => input("query", event.target.value)} placeholder="Enter an ABN or business name…" /></label>
        {select("state", "State / territory", ["QLD", "NSW", "VIC", "SA", "WA", "TAS", "NT", "ACT", "AAT"].map(value => [value, value]))}
        <label htmlFor={`${source}-filter-postcode`}>Postcode<input id={`${source}-filter-postcode`} inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={draft.postcode || ""} onChange={event => input("postcode", event.target.value)} placeholder="All postcodes" /></label>
        {source === "abr" ? <>
          {select("status", "ABN status", [["ACT", "Active"], ["CAN", "Cancelled"]])}
          {select("gst_status", "GST status", [["ACT", "Registered"], ["NON", "Not registered"], ["CAN", "Cancelled"], ["NONE", "Not supplied"]])}
          <label htmlFor="abr-filter-status_date_from">ABN status date from<input id="abr-filter-status_date_from" type="date" max={draft.status_date_to || undefined} value={draft.status_date_from || ""} onChange={event => input("status_date_from", event.target.value)} /></label>
          <label htmlFor="abr-filter-status_date_to">ABN status date to<input id="abr-filter-status_date_to" type="date" min={draft.status_date_from || undefined} value={draft.status_date_to || ""} onChange={event => input("status_date_to", event.target.value)} /></label>
          <label htmlFor="abr-filter-entity_type">Entity type code<input id="abr-filter-entity_type" maxLength={80} value={draft.entity_type || ""} onChange={event => input("entity_type", event.target.value.toUpperCase())} placeholder="e.g. PRV" /></label>
        </> : select("financial_category", "Financial category", ["1", "2", "3", "4", "5", "6", "7", "SC2", "SCT1", "N/A", "EMRSC1", "EMRSC2", "EMR1-2", "EMR3-7"].map(value => [value, /^[1-7]$/.test(value) ? `Category ${value}` : value]))}
        {source === "abr" && select("entity_class", "Entity class", [["company", "Company"], ["trust", "Trust"], ["individual", "Individual"], ["other", "Other"]])}
        <div className={cls("form-actions", "source-filter-actions")}><button type="submit" className={cls("button", "primary")}>Apply filters</button><button type="button" className={cls("button", "secondary")} onClick={() => { setDraft({}); void load(data?.run_id || run, 0, {}); }}>Clear filters</button></div>
      </fieldset>
      <p className={cls("source-page-note")}>{dirty ? "Filters changed. Apply them to update the table and filtered download." : "An 11-digit ABN finds exact matches. Names also match other published ABR names. Add a state or postcode to narrow a broad search."}</p>
    </form>
    {error && <p role="alert" className={cls("field-error")}>{error}{data && " The table still shows the last successfully loaded results."}</p>}
    {downloadNote && <p role="status">{downloadNote}</p>}
    <div aria-busy={busy}>
      {!data && busy && <p role="status">Loading {label} source records…</p>}
      {data && <>
        <p className={cls("source-page-note")}>Published: {dateLabel(data.publisher_modified_at)}{!data.publisher_modified_at && data.publisher_extract_time && <> · Publisher extract time: {data.publisher_extract_time} (timezone not supplied)</>} · Imported: {dateLabel(data.source_observed_at)}{data.run_id && <> · Run {data.run_id.slice(0, 8)}</>}{data.baseline && <> · Reference baseline; zero new-business events and zero leads</>}</p>
        {source === "abr" && data.filters.status_date_from && <p className={cls("source-page-note")}>Active window: {data.filters.status_date_from} – {data.filters.status_date_to || "any date"}. Results reflect this publication only; registrations after its publication are not covered. ABR publishes the bulk extract weekly.</p>}
        {data.source_state === "available" && <>
          {source === "abr" && <div className={cls("source-switch")} role="group" aria-label="Record display"><button type="button" className={cls("button", "secondary")} aria-pressed={layout === "prospects"} onClick={() => setLayout("prospects")}>Prospect view</button><button type="button" className={cls("button", "secondary")} aria-pressed={layout === "fields"} onClick={() => setLayout("fields")}>All stored fields</button></div>}
          <div className={cls("source-export-actions")}><p>{data.columns.length} stored fields · Scroll across the table to see every column.</p><div className={cls("form-actions")}>
            <button type="button" className={cls("button", "secondary")} disabled={!connected || busy || exporting || !data.run_id || !data.source_total} onClick={() => void download(false)}>Download all CSV</button>
            <button type="button" className={cls("button", "secondary")} disabled={!connected || busy || exporting || !data.run_id || !data.total || !filtered || !!dirty} onClick={() => void download(true)}>Download filtered CSV</button>
          </div></div>
          <p className={cls("source-page-note")}>CSV downloads include all matching rows and stored fields. Apply filters first for a smaller file. Nested licence details are preserved as JSON in CSV cells.</p>
        </>}
        {data.source_state === "expired" ? <p role="status">The source records for this publication are no longer retained. Its run receipt remains available. Choose a more recent accepted publication.</p>
          : data.source_state === "not_collected" ? <p role="status">No current accepted {label} publication is available. Check Run history for completed runs and retained records.</p>
            : !data.records.length ? <p role="status">No source records match these filters. Clear the filters or try another ABN.</p> : source === "abr" && layout === "prospects" ? <div className={cls("prospect-list")}>
              <div className={cls("prospect-list-caption")}><span>Business / ABN</span><span>Registration signal</span><span>Next step</span></div>
              {data.records.map(row => <article key={String(row.abn)} className={cls("prospect-row")}><div><strong>{String(row.main_name)}</strong><small>ABN {formatABN(String(row.abn))} · {String(row.state)} {String(row.postcode)}</small></div><div>{statusLabel(row.status)} since {String(row.status_date || "date not supplied")}<small>First registration needs verification</small></div><div><button type="button" className={cls("button", "secondary", "small")} disabled={!connected || busy || !data.snapshot_id || !data.run_id || !!selected} onClick={() => setSelected({ abn: String(row.abn), business_name: String(row.main_name), source, snapshot_id: data.snapshot_id!, run_id: data.run_id! })}>Research business</button><small>Review website, email & social</small></div></article>)}
            </div> : <SourceRecordTable data={data} />}
        {data.source_state === "available" && <div className={cls("source-pagination")}>
          <p role="status">{data.records.length ? `Showing ${(data.offset + 1).toLocaleString("en-AU")}–${(data.offset + data.records.length).toLocaleString("en-AU")} of ${data.total.toLocaleString("en-AU")}${filtered ? " matching records" : ""}` : "0 records shown"}</p>
          <div className={cls("form-actions")}><button type="button" className={cls("button", "secondary", "small")} disabled={busy || !connected || data.offset === 0} onClick={() => void load(data.run_id || run, Math.max(0, data.offset - 50), data.filters)}>Previous 50</button>
            <button type="button" className={cls("button", "secondary", "small")} disabled={busy || !connected || data.next_offset === null} onClick={() => { if (data.next_offset !== null) void load(data.run_id || run, data.next_offset, data.filters); }}>Next 50</button></div>
        </div>}
      </>}
    </div>
    {selected && <ProspectEditor key={selected.abn} seed={selected} engine={engine} onClose={() => setSelected(null)} />}
  </section>;
}
