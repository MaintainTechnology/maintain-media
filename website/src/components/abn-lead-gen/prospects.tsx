"use client";

import { useEffect, useRef, useState } from "react";
import { formatABN, dateLabel } from "@/lib/abn-lead-gen/types";
import { australianToday, recentDates, emptyProspect, presenceLabels, stageLabels, validProspect, validProspectPage,
  type Prospect, type ProspectSeed, type ProspectFilters, type ProspectPage, type Presence, type ContactStage } from "@/lib/abn-lead-gen/prospects";
import type { DashboardController } from "./use-dashboard";
import styles from "./dashboard.module.css";

const cls = (...names: string[]) => names.map(name => styles[name]).filter(Boolean).join(" ");
const message = (error: unknown) => error instanceof Error ? error.message : "Could not load the prospect. Please try again.";

export function ProspectEditor({ seed, engine, onClose, onSaved }: {
  seed: ProspectSeed; engine: DashboardController; onClose: () => void; onSaved?: () => void;
}) {
  const [draft, setDraft] = useState<Prospect>(() => emptyProspect(seed));
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const pending = useRef<{ fingerprint: string; id: string } | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const mounted = useRef(false);
  const request = engine.request;
  const reviewer = engine.data?.scopes?.some(scope => scope === "reviewer" || scope === "admin");
  const disabled = loading || !loaded || busy || !reviewer || !engine.connected || engine.signingOut;
  useEffect(() => {
    mounted.current = true;
    dialog.current?.showModal();
    heading.current?.focus();
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true); setLoaded(false); setError(null);
      try {
        const response = await request(`prospects/${seed.abn}`) as { prospect?: unknown };
        if (!response || !("prospect" in response) || response.prospect !== null && (!validProspect(response.prospect) || response.prospect.abn !== seed.abn)) throw new Error("The saved prospect could not be verified. Retry before editing.");
        if (!cancelled) { setDraft(response.prospect === null ? emptyProspect(seed) : response.prospect as Prospect); setLoaded(true); setDirty(false); }
      } catch (failure) { if (!cancelled) setError(message(failure)); }
      finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [seed, request, epoch]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  useEffect(() => {
    const beforeNavigate = (event: Event) => {
      if (busy || dirty && !window.confirm("Discard the unsaved prospect research?")) event.preventDefault();
    };
    window.addEventListener("leadgen:before-navigate", beforeNavigate);
    return () => window.removeEventListener("leadgen:before-navigate", beforeNavigate);
  }, [busy, dirty]);
  function edit<K extends keyof Prospect>(key: K, value: Prospect[K]) { setDraft(previous => ({ ...previous, [key]: value })); setDirty(true); setNote(null); }
  function close() { if (!busy && (!dirty || window.confirm("Discard the unsaved prospect research?"))) onClose(); }
  async function save() {
    if ((draft.website_url && draft.website_presence !== "present") || (draft.email && draft.email_presence !== "present") || (draft.social_url && draft.social_presence !== "present")) {
      setError("A saved website, email or social URL needs its presence set to Found. Clear the detail if it does not belong to this business."); return;
    }
    if (!!draft.registration_date !== !!draft.registration_evidence_ref.trim()) { setError("Enter the first registration date and its evidence together, or leave both blank until verified."); return; }
    setBusy(true); setError(null); setNote(null);
    const { revision } = draft;
    const payload = { abn: draft.abn, business_name: draft.business_name, source: draft.source, run_id: draft.run_id,
      snapshot_id: draft.snapshot_id, expected_revision: revision,
      website_presence: draft.website_presence, email_presence: draft.email_presence, social_presence: draft.social_presence,
      website_url: draft.website_url, email: draft.email, phone: draft.phone, social_url: draft.social_url,
      evidence_ref: draft.evidence_ref, research_note: draft.research_note, contact_stage: draft.contact_stage,
      follow_up_on: draft.follow_up_on, registration_date: draft.registration_date, registration_evidence_ref: draft.registration_evidence_ref };
    const fingerprint = JSON.stringify(payload);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, id: crypto.randomUUID() };
    try {
      const receipt = await request("prospects", { method: "POST", body: JSON.stringify({ ...payload, request_id: pending.current.id }) }) as { revision?: number; saved_at?: string };
      if (!receipt || receipt.revision !== revision + 1 || typeof receipt.saved_at !== "string") throw new Error("The save was not confirmed. Retry to check the same request.");
      const confirmed = await request(`prospects/${seed.abn}`) as { prospect?: unknown };
      if (!confirmed || !validProspect(confirmed.prospect) || confirmed.prospect.abn !== seed.abn || confirmed.prospect.revision !== receipt.revision) throw new Error("The engine accepted the save, but the saved research could not be read back. Reload saved research to check its current values.");
      if (!mounted.current) return;
      setDraft(confirmed.prospect);
      pending.current = null; setDirty(false); setNote("Research saved. Find this business in Saved prospects."); onSaved?.();
    } catch (failure) { if (mounted.current) setError(message(failure)); }
    finally { if (mounted.current) setBusy(false); }
  }
  const researchQuery = encodeURIComponent(`"${seed.business_name}" ${seed.abn}`);
  async function copyContact(value: string) {
    try { await navigator.clipboard.writeText(value); setNote("Contact detail copied. Use your approved contact process before reaching out."); }
    catch { setError("Copy was unavailable. Select and copy the contact detail from its field."); }
  }
  return <dialog ref={dialog} className={cls("prospect-dialog")} aria-labelledby="prospect-editor-title" onCancel={event => { event.preventDefault(); close(); }}><section className={cls("prospect-editor")} aria-busy={loading || busy}>
    <div className={cls("section-heading")}><div><span className={cls("prospect-eyebrow")}>Business research</span><h2 ref={heading} tabIndex={-1} id="prospect-editor-title">{seed.business_name}</h2><p>ABN {formatABN(seed.abn)} · Source {seed.source.toUpperCase()}</p></div><button type="button" className={cls("button", "secondary")} disabled={busy} onClick={close}>Close research</button></div>
    <div className={cls("prospect-research-links")}><a href={`https://abr.business.gov.au/ABN/View?id=${seed.abn}`} target="_blank" rel="noreferrer">Check ABN history ↗</a><a href={`https://www.google.com/search?q=${researchQuery}`} target="_blank" rel="noreferrer">Research business online ↗</a></div>
    <p className={cls("source-page-note")}>Check the business identity, then record what you can verify. An empty ABR field does not mean a website, email or social profile is absent.</p>
    {loading && <p role="status">Loading saved research…</p>}
    {error && <p role="alert" className={cls("field-error")}>{error} <button type="button" className={cls("button", "secondary", "small")} disabled={busy || loading} onClick={() => { if (!dirty || window.confirm("Reload and discard your unsaved changes?")) setEpoch(value => value + 1); }}>Reload saved research</button></p>}
    {note && <p role="status" className={cls("prospect-saved")}>{note}</p>}
    {!reviewer && <p>A reviewer account is needed to save research.</p>}
    <form onSubmit={event => { event.preventDefault(); void save(); }} className={cls("prospect-form")}>
      <fieldset disabled={disabled}><legend>Digital presence</legend><div className={cls("prospect-fields")}>
        {(["website", "email", "social"] as const).map(channel => <label key={channel}>{channel === "social" ? "Social media" : channel === "email" ? "Email presence" : "Website presence"}<select aria-label={channel === "social" ? "Social media" : channel === "email" ? "Email presence" : "Website presence"} value={draft[`${channel}_presence`]} onChange={event => edit(`${channel}_presence`, event.target.value as Presence)}>{Object.entries(presenceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>)}
        <label>Website URL<input type="url" maxLength={500} placeholder="https://…" value={draft.website_url} onChange={event => edit("website_url", event.target.value)} /></label>
        <label>Business email<input type="email" maxLength={254} value={draft.email} onChange={event => edit("email", event.target.value)} /></label>
        <label>Social profile URL<input type="url" maxLength={500} placeholder="https://…" value={draft.social_url} onChange={event => edit("social_url", event.target.value)} /></label>
        <label>Business phone<input type="tel" maxLength={40} value={draft.phone} onChange={event => edit("phone", event.target.value)} /></label>
        <label className={cls("prospect-wide")}>Research evidence / source reference<input required={draft.website_presence !== "unknown" || draft.email_presence !== "unknown" || draft.social_presence !== "unknown" || !!draft.phone || draft.contact_stage !== "not_contacted"} maxLength={1000} placeholder="Source URL, or reference to a conversation confirming these findings" value={draft.evidence_ref} onChange={event => edit("evidence_ref", event.target.value)} /></label>
      </div></fieldset>
      <fieldset disabled={disabled}><legend>Verify first registration</legend><p>Use the original ABN registration date, after checking its history. A recent reactivation does not qualify as a newly created ABN.</p><div className={cls("prospect-fields")}>
        <label>Verified first registration date<input type="date" max={australianToday()} value={draft.registration_date || ""} onChange={event => edit("registration_date", event.target.value || null)} /></label>
        <label className={cls("prospect-wide")}>Registration evidence<input required={!!draft.registration_date} maxLength={1000} placeholder="Reference confirming the first registration date" value={draft.registration_evidence_ref} onChange={event => edit("registration_evidence_ref", event.target.value)} /></label>
      </div></fieldset>
      <fieldset disabled={disabled}><legend>Contact & follow-up</legend><p>Record contact completed through your approved process. Saving research does not send a message or approve outreach.</p><div className={cls("prospect-fields")}>
        <label>Contact stage<select value={draft.contact_stage} onChange={event => edit("contact_stage", event.target.value as ContactStage)}>{Object.entries(stageLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Follow-up date<input type="date" required={draft.contact_stage === "follow_up"} value={draft.follow_up_on || ""} onChange={event => edit("follow_up_on", event.target.value || null)} /></label>
        <label className={cls("prospect-full")}>Research & conversation notes<textarea rows={4} maxLength={4000} placeholder="What have they confirmed? What help do they need? What is the next step?" value={draft.research_note} onChange={event => edit("research_note", event.target.value)} /></label>
      </div></fieldset>
      {(draft.phone || draft.email) && <div className={cls("form-actions")} aria-label="Use researched contact details"><button type="button" className={cls("button", "secondary", "small")} disabled={!draft.phone || disabled} onClick={() => void copyContact(draft.phone)}>Copy phone</button><button type="button" className={cls("button", "secondary", "small")} disabled={!draft.email || disabled} onClick={() => void copyContact(draft.email)}>Copy email</button></div>}
      <div className={cls("prospect-offer")}><strong>Conversation guide</strong><p>“We help newly established businesses find customers with zero cost to start. Do you already have a website, business email or social profile? Would a lead generation partnership be useful?”</p></div>
      <div className={cls("form-actions")}><button type="submit" className={cls("button", "primary")} disabled={disabled || !dirty}>{busy ? "Saving…" : "Save research"}</button><span>{dirty ? "Unsaved changes" : draft.revision ? `Last saved ${dateLabel(draft.saved_at)}` : "Not yet saved"}</span></div>
    </form>
  </section></dialog>;
}

export function ProspectsView({ engine }: { engine: DashboardController }) {
  const [data, setData] = useState<ProspectPage | null>(null);
  const [filters, setFilters] = useState<ProspectFilters>({});
  const [applied, setApplied] = useState<ProspectFilters>({});
  const [selected, setSelected] = useState<Prospect | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef({ id: 0 });
  const request = useRef(engine.request);
  useEffect(() => { request.current = engine.request; }, [engine.request]);
  const connected = engine.connected && !engine.signingOut && engine.data?.mode !== "fixture";
  async function load(next: ProspectFilters, offset = 0) {
    next = Object.fromEntries(Object.entries(next).filter(([, value]) => value?.trim()).map(([key, value]) => [key, value!.trim()]));
    const id = ++sequence.current.id;
    setBusy(true); setError(null);
    try {
      const result = await request.current("prospects/query", { method: "POST", body: JSON.stringify({ offset, filters: next }) });
      if (!validProspectPage(result, offset)) throw new Error("The saved prospect list could not be verified. Please refresh.");
      if (sequence.current.id === id) { setData(result); setApplied(next); }
    } catch (failure) { if (sequence.current.id === id) setError(message(failure)); }
    finally { if (sequence.current.id === id) setBusy(false); }
  }
  useEffect(() => {
    const state = sequence.current;
    const timer = connected ? setTimeout(() => { void load({}); }, 0) : undefined;
    return () => { clearTimeout(timer); state.id++; };
  }, [connected]);
  function preset(next: ProspectFilters) { setFilters(next); void load(next); }
  const recent = recentDates(7);
  const presets: [string, ProspectFilters][] = [
    ["All saved", {}], ["Verified new · 7 days", { registration_date_from: recent.from, registration_date_to: recent.to }],
    ["No website", { website_presence: "absent" }], ["No digital presence", { website_presence: "absent", email_presence: "absent", social_presence: "absent" }],
    ["Target match · 7 days", { registration_date_from: recent.from, registration_date_to: recent.to, website_presence: "absent", email_presence: "absent", social_presence: "absent" }],
    ["Follow-ups due", { contact_stage: "follow_up", follow_up_due: australianToday() }],
  ];
  return <section id="view-prospects" className={cls("view")} aria-labelledby="prospects-title">
    <div className={cls("page-heading")}><div><h1 id="prospects-title">Saved prospects.</h1><p>Turn verified research into a useful next conversation.</p></div><a href="#sources" className={cls("button", "primary")}>Find new businesses →</a></div>
    <div className={cls("prospect-offer")}><strong>Start with their first customers.</strong><p>Focus on ABNs first registered in the last 7 days with confirmed gaps in website, email and social presence. Offer a lead generation partnership with zero cost to start.</p></div>
    {!connected && <p role="status">Connect the live engine to load and save prospect research.</p>}
    <div className={cls("source-switch")} role="group" aria-label="Prospect quick filters">{presets.map(([label, value]) => <button key={label} type="button" className={cls("button", "secondary")} disabled={!connected || busy} aria-pressed={JSON.stringify(applied) === JSON.stringify(value)} onClick={() => preset(value)}>{label}</button>)}</div>
    <form className={cls("source-filter-form")} onSubmit={event => { event.preventDefault(); void load(filters); }}><fieldset disabled={!connected || busy}><legend className={cls("sr-only")}>Filter saved prospects</legend>
      <label className={cls("source-query")}>Business name or ABN<input type="search" maxLength={200} value={filters.query || ""} onChange={event => setFilters({ ...filters, query: event.target.value })} /></label>
      {(["website", "email", "social"] as const).map(channel => <label key={channel}>{channel === "website" ? "Website" : channel === "email" ? "Email" : "Social media"}<select aria-label={channel === "website" ? "Website" : channel === "email" ? "Email" : "Social media"} value={filters[`${channel}_presence`] || ""} onChange={event => setFilters({ ...filters, [`${channel}_presence`]: event.target.value })}><option value="">Any presence</option>{Object.entries(presenceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>)}
      <label>Contact stage<select value={filters.contact_stage || ""} onChange={event => setFilters({ ...filters, contact_stage: event.target.value })}><option value="">All stages</option>{Object.entries(stageLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <div className={cls("form-actions", "source-filter-actions")}><button className={cls("button", "primary")} type="submit">Apply prospect filters</button><button className={cls("button", "secondary")} type="button" onClick={() => preset({})}>Clear prospect filters</button></div>
    </fieldset></form>
    {(filters.registration_date_from || filters.follow_up_due) && <p className={cls("source-page-note")}>{filters.registration_date_from && `First registered: ${filters.registration_date_from} – ${filters.registration_date_to}. `}{filters.follow_up_due && `Follow-up due on or before ${filters.follow_up_due}. `}Dates use Brisbane time.</p>}
    {error && <p role="alert" className={cls("field-error")}>{error}{data && " The list still shows the previous results."}</p>}
    <div aria-busy={busy} className={cls("prospect-results")}>
      {busy && <p role="status">Loading saved prospects…</p>}
      {data && <><div className={cls("section-heading")}><h2>{data.total.toLocaleString("en-AU")} matching prospects</h2><button className={cls("button", "secondary", "small")} disabled={!connected || busy} onClick={() => void load(applied, data.offset)}>Refresh list</button></div>
        {!data.records.length ? <div className={cls("empty-state")}><h3>No saved prospects match.</h3><p>Open Source records, check a business and save its research. Unknown presence is never counted as absent.</p></div> : <div className={cls("prospect-list")}>{data.records.map(row => <button key={row.abn} type="button" className={cls("prospect-row")} disabled={!!selected} aria-pressed={selected?.abn === row.abn} onClick={() => setSelected(row)}><span><strong>{row.business_name}</strong><small>ABN {formatABN(row.abn)} · {row.registration_date ? `First registered ${row.registration_date}` : "First registration unverified"}</small></span><span className={cls("prospect-presence")}>{(["website", "email", "social"] as const).map(channel => <span key={channel} data-presence={row[`${channel}_presence`]}>{channel}: {presenceLabels[row[`${channel}_presence`]]}</span>)}</span><span>{stageLabels[row.contact_stage]}<small>{row.follow_up_on ? `Due ${row.follow_up_on}` : "Open research →"}</small></span></button>)}</div>}
        <div className={cls("source-pagination")}><p role="status">{data.total ? `${data.offset + 1}–${data.offset + data.records.length} of ${data.total}` : "0 saved prospects"}</p><div className={cls("form-actions")}><button className={cls("button", "secondary")} disabled={!connected || busy || !data.offset} onClick={() => void load(applied, data.offset - 50)}>Previous 50</button><button className={cls("button", "secondary")} disabled={!connected || busy || data.next_offset === null} onClick={() => void load(applied, data.next_offset!)}>Next 50</button></div></div>
      </>}
    </div>
    {selected && <ProspectEditor key={selected.abn} seed={selected} engine={engine} onClose={() => setSelected(null)} onSaved={() => void load(applied, data?.offset || 0)} />}
  </section>;
}
