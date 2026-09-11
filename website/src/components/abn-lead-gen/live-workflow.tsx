"use client";

import { useEffect, useRef, useState } from "react";
import type { Lead } from "@/lib/abn-lead-gen/types";
import { dateLabel, humanize, validJob, jobActive, type Job } from "@/lib/abn-lead-gen/types";
import { errorMessage, type DashboardController } from "./use-dashboard";
import { crmHandoffGuidance, websiteCollectionGuidance } from "./readiness";
import styles from "./dashboard.module.css";

const cls = (...names: string[]) => names.map(name => styles[name]).filter(Boolean).join(" ");
const outcomes = ["not_started", "no_usable_contact", "attempted_no_answer", "contacted_not_interested", "contacted_nurture", "meeting_booked", "meeting_held", "disqualified", "do_not_contact_requested"];
function localTime() { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
const errorText = (error: unknown) => error instanceof Error ? error.message : "Not saved. Check the connection and try again.";
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

export function LeadActions({ lead, engine }: { lead: Lead; engine: DashboardController }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [stopUnconfirmed, setStopUnconfirmed] = useState(false);
  const [evidence, setEvidence] = useState<{ contact: string; text: string; source: string } | null>(null);
  const [localWebsiteJob, setWebsiteJob] = useState<Job | null>(null);
  const websiteJob = jobActive(lead.website_job) && (!localWebsiteJob || lead.website_job?.job_id !== localWebsiteJob.job_id && !jobActive(localWebsiteJob))
    ? lead.website_job! : localWebsiteJob || lead.website_job || null;
  const websiteCollection = websiteCollectionGuidance(engine.data);
  const [outcomeVersion, setOutcomeVersion] = useState(lead.row_version);
  const [identityVersion, setIdentityVersion] = useState(lead.revision);
  const [formEpoch, setFormEpoch] = useState(0);
  const websiteRequest = useRef<{ fingerprint: string; id: string } | null>(null);
  const stop = useRef<{ lead_id: string; reason: string; source: string; requested_at: string } | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const reviewer = engine.data?.scopes?.includes("reviewer");
  const disabled = busy || !engine.connected || engine.signingOut;
  useEffect(() => {
    if (!websiteJob?.job_id || !jobActive(websiteJob) || !engine.connected) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await engine.request(`website-jobs/${websiteJob.job_id}`);
        if (!validJob(result)) throw new Error("The website collection status is incomplete. Refresh to check its saved state.");
        if (cancelled) return;
        setWebsiteJob(result);
        if (!jobActive(result)) { setReceipt(`Website collection ${humanize(result.state)}. Review the saved contact evidence and restrictions.`); await engine.refresh(); }
      } catch (failure) { if (!cancelled) setError(errorText(failure)); }
    }, 3000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [websiteJob, engine]);

  async function save(endpoint: string, body: unknown, method = "POST", stopping = false) {
    setBusy(true); setError(null); setReceipt(null);
    if (stopping) setStopUnconfirmed(true);
    try {
      const result = await engine.request(endpoint, { method, body: JSON.stringify(body) });
      if (!record(result) || stopping && !(typeof result.committed_at === "string" || result.suppression_committed === true)) {
        throw new Error("The engine did not confirm the change. Refresh to check its saved state before retrying.");
      }
      if (!mounted.current) return;
      if (stopping) { setStopUnconfirmed(false); stop.current = null; }
      if (endpoint.startsWith("worklist-rows/") && typeof result.version === "number") setOutcomeVersion(result.version);
      if (endpoint === "identity-assessments") setIdentityVersion(value => (value ?? 0) + 1);
      setReceipt(stopping ? "Do not contact saved. The engine has committed the restriction."
        : endpoint === "crm-approvals" ? `CRM decision saved. ${crmHandoffGuidance({ state: String(result.state), can_approve: false, can_reject: false, reason_codes: [], outbox_id: null, updated_at: null }).detail}`
          : "Saved to the engine.");
      await engine.refresh();
    } catch (failure) { if (mounted.current) setError(errorText(failure)); }
    finally { if (mounted.current) setBusy(false); }
  }
  function suppress() {
    stop.current ??= { lead_id: lead.lead_id, reason: "unsubscribe", source: "staff_dashboard", requested_at: new Date().toISOString() };
    void save("suppressions", stop.current, "POST", true);
  }

  return <section className={cls("live-actions")} aria-label="Business actions">
    <h4>Record the next step</h4>
    <p>Every saved change records your own staff identity. Sending messages and making calls are outside this tool.</p>
    <button className={cls("button", "danger-action")} type="button" disabled={disabled} onClick={suppress}>{busy && stopUnconfirmed ? "Saving do not contact…" : stopUnconfirmed ? "Retry do not contact now" : "Do not contact this business"}</button>
    {stopUnconfirmed && <p className={cls("field-error")} role="alert">Do not contact. The restriction has not yet been confirmed saved. Retry this action now; other business actions are paused.</p>}
    {error && <p className={cls("field-error")} role="alert">{error}</p>}
    {receipt && <p role="status">{receipt}</p>}
    {(lead.row_version !== outcomeVersion || lead.revision !== identityVersion) && <div role="status"><p>This business has changed since these forms opened. Your current edits have been kept. Reload the forms to use the latest saved decisions.</p><button className={cls("button", "secondary", "small")} disabled={disabled || stopUnconfirmed} type="button" onClick={() => { setOutcomeVersion(lead.row_version); setIdentityVersion(lead.revision); setFormEpoch(value => value + 1); }}>Reload saved form values</button></div>}
    {reviewer && <details className={cls("review-form")}><summary>Review the business website identity</summary>
      <p>{lead.website_identity ? `Latest decision: ${lead.website_identity.assessment} for ${lead.website_identity.registrable_domain}. Expires ${dateLabel(lead.website_identity.expires_at)}.` : "No website identity has been approved."} Approval needs matching business name plus a matching full address or independently corroborated phone number.</p>
      <form key={`identity:${formEpoch}`} onSubmit={event => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        void save("identity-assessments", { lead_id: lead.lead_id, expected_revision: identityVersion,
          registrable_domain: String(form.get("domain")).trim().toLowerCase(), assessment: form.get("assessment"),
          method: "reviewed_attributes", reason: form.get("reason"), evidence_refs: {
            name_match: form.get("name_match") === "on", address_match: form.get("address_match") === "on",
            phone_match: form.get("phone_match") === "on", references: [form.get("reference1"), form.get("reference2")],
          } });
      }}><fieldset disabled={disabled || stopUnconfirmed}><legend>Website identity evidence</legend>
        <label>Business domain<input name="domain" required maxLength={253} placeholder="business.com.au" defaultValue={lead.website_identity?.registrable_domain || ""} /></label>
        <label>Decision<select name="assessment" required defaultValue=""><option value="" disabled>Choose a checked decision</option><option value="approved">Approved — identity evidence matches</option><option value="rejected">Rejected — different business</option><option value="ambiguous">Unclear — hold for review</option></select></label>
        <label className={cls("checkbox-label")}><input name="name_match" type="checkbox" />The business name matches.</label>
        <label className={cls("checkbox-label")}><input name="address_match" type="checkbox" />The full address matches.</label>
        <label className={cls("checkbox-label")}><input name="phone_match" type="checkbox" />A phone number matches independent evidence.</label>
        <label>First evidence reference<input name="reference1" required maxLength={500} /></label>
        <label>Second independent evidence reference<input name="reference2" required maxLength={500} /></label>
        <label>Reason<textarea name="reason" required minLength={1} maxLength={2000} rows={2} /></label>
        <button type="submit" className={cls("button", "secondary")}>Save identity review</button>
      </fieldset></form>
    </details>}
    {reviewer && lead.website_identity?.assessment === "approved" && <details className={cls("review-form")}><summary>Collect phone details from the reviewed website</summary>
      <p>{websiteCollection.summary}</p>
      <p>The engine checks robots rules and reads up to six public HTML pages. The licence check and site-terms review must be less than 30 days old; the website identity decision must still be current. Use the HTTPS homepage with a trailing slash and no query or fragment.</p>
      <p><a href="/business-research-notice" target="_blank" rel="noreferrer">Read the business research notice</a>. The engine checks each request again before collection.</p>
      {websiteJob && <p role="status">Website job: {humanize(websiteJob.state)}{websiteJob.error_code ? ` · ${errorMessage(websiteJob.error_code, `${humanize(websiteJob.error_code)}. Check the saved review details before trying again.`)}` : ""}</p>}
      <form onSubmit={async event => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        const reviewedAt = new Date(String(form.get("terms_reviewed_at")));
        if (!Number.isFinite(reviewedAt.getTime())) { setError("Enter a valid date and time for your site-terms review."); return; }
        const body = { lead_id: lead.lead_id, identity_id: lead.website_identity!.identity_id,
          website_url: form.get("website_url"), terms_permit: form.get("terms_permit") === "on",
          terms_evidence_ref: form.get("terms_evidence_ref"), terms_reviewed_at: reviewedAt.toISOString() };
        const fingerprint = JSON.stringify(body);
        if (websiteRequest.current?.fingerprint !== fingerprint) websiteRequest.current = { fingerprint, id: crypto.randomUUID() };
        setBusy(true); setError(null); setReceipt(null);
        try {
          const result = await engine.request("website-collections", { method: "POST", body: JSON.stringify({ ...body, request_id: websiteRequest.current.id }) });
          if (!validJob(result)) throw new Error("Collection was not confirmed. Refresh to check its saved state before retrying.");
          if (!mounted.current) return;
          setWebsiteJob(result); websiteRequest.current = null;
          setReceipt("Website collection request saved. This panel will show its progress.");
        } catch (failure) { if (mounted.current) setError(errorText(failure)); }
        finally { if (mounted.current) setBusy(false); }
      }}><fieldset disabled={disabled || stopUnconfirmed || !websiteCollection.enabled || jobActive(websiteJob) || jobActive(lead.website_job)}><legend>Checked phone-only website collection</legend>
        <label>Website homepage<input name="website_url" type="url" required maxLength={300} defaultValue={`https://${lead.website_identity.registrable_domain}/`} /></label>
        <label className={cls("checkbox-label")}><input name="terms_permit" type="checkbox" required />I reviewed this site’s terms and recorded evidence permitting this phone-only collection.</label>
        <label>Terms review evidence<input name="terms_evidence_ref" required minLength={1} maxLength={500} /></label>
        <label>When did you review the terms? (your local time)<input name="terms_reviewed_at" type="datetime-local" required /></label>
        <button type="submit" className={cls("button", "secondary")}>Collect reviewed phone details</button>
      </fieldset></form>
    </details>}
    {reviewer && lead.contacts?.map(contact => <details key={contact.contact_id} className={cls("review-form")}><summary>{contact.channel === "email" ? "Review email permission" : "Review phone evidence"} · {contact.contact_id.slice(0, 8)}</summary>
      <p>{contact.channel === "email" ? "Public contact details do not automatically give permission. Review the captured evidence under your approved policy." : "These phone details are for internal research. Collection does not establish permission to call or confirm a Do Not Call Register check."}</p>
      <button className={cls("button", "secondary", "small")} type="button" disabled={disabled} onClick={async () => {
        setBusy(true); setError(null);
        try {
          const result = await engine.request(`evidence/${contact.provenance_id}`);
          if (!record(result) || typeof result.capture_text !== "string" || typeof result.source_url !== "string") throw new Error("Evidence could not be loaded.");
          if (mounted.current) setEvidence({ contact: contact.contact_id, text: result.capture_text, source: result.source_url });
        } catch (failure) { if (mounted.current) setError(errorText(failure)); }
        finally { if (mounted.current) setBusy(false); }
      }}>Open private captured evidence</button>
      {evidence?.contact === contact.contact_id && <div><p>Captured source: {evidence.source}</p><pre className={cls("evidence-text")}>{evidence.text}</pre><button type="button" className={cls("button", "small", "secondary")} onClick={() => setEvidence(null)}>Close evidence</button></div>}
      {contact.channel === "email" && <PermissionForm contact={contact} disabled={disabled || stopUnconfirmed} save={save} />}
    </details>)}
    {lead.row_id && lead.row_version ? <form key={`${lead.row_id}:${formEpoch}`} onSubmit={event => {
      event.preventDefault(); const form = new FormData(event.currentTarget); const status = String(form.get("status"));
      void save(`worklist-rows/${lead.row_id}`, { expected_version: outcomeVersion, status,
        attempts: Number(form.get("attempts")), invitation_state: form.get("invitation_state"),
        invitation_evidence_ref: String(form.get("invitation_evidence_ref") || "") || null,
        notes: form.get("notes"), occurred_at: new Date(String(form.get("occurred_at"))).toISOString() }, "PATCH", status === "do_not_contact_requested");
    }}>
      <fieldset disabled={disabled || stopUnconfirmed}>
        <legend>Worklist outcome</legend>
        <label>What happened?<select name="status" defaultValue={lead.outcome || "not_started"}>{outcomes.map(status => <option key={status} value={status}>{humanize(status)}</option>)}</select></label>
        <label>Number of attempts<input name="attempts" type="number" min="0" max="100000" step="1" required defaultValue={lead.outcome_details?.attempts ?? 0} /></label>
        <label>When did it happen? (your local time)<input name="occurred_at" type="datetime-local" required defaultValue={localTime()} /></label>
        <label>Invitation evidence<select name="invitation_state" defaultValue={lead.outcome_details?.invitation_state || "unknown"}><option value="unknown">Unknown</option><option value="uninvited">Uninvited</option><option value="invited">Invited — evidence required</option></select></label>
        <label>Invitation evidence reference<input name="invitation_evidence_ref" maxLength={500} defaultValue={lead.outcome_details?.invitation_evidence_ref || ""} placeholder="Required if invited" /></label>
        <label>Notes<textarea name="notes" maxLength={2000} rows={3} defaultValue={lead.outcome_details?.notes || ""} /></label>
        <button className={cls("button", "primary")} type="submit">Save outcome</button>
      </fieldset>
    </form> : <p>A worklist outcome becomes available after this business passes the contact checks and is selected. You can record a do-not-contact request now.</p>}
    <CrmReview key={`crm:${lead.row_id || "unselected"}:${formEpoch}`} lead={lead} reviewer={!!reviewer} disabled={disabled || stopUnconfirmed} expectedVersion={outcomeVersion} save={save} />
  </section>;
}

export function CrmReview({ lead, reviewer, disabled, expectedVersion, save }: {
  lead: Lead; reviewer: boolean; disabled: boolean; expectedVersion?: number | null;
  save: (endpoint: string, body: unknown) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const guidance = crmHandoffGuidance(lead.crm_handoff);
  const editable = reviewer && !!lead.row_id && Number.isSafeInteger(expectedVersion) && Number(expectedVersion) > 0;
  return <section className={cls("review-form")} aria-label="GoHighLevel hand-off">
    <h4>GoHighLevel hand-off</h4>
    <p role="status"><strong>{guidance.label}</strong></p><p>{guidance.detail}</p>
    <p>Enabling the connection does not approve every business. A reviewer must approve each eligible, selected tier A business. The worker then handles the saved request; this tool does not send messages or make calls.</p>
    {lead.crm_handoff?.reason_codes.map(code => <p key={code}>{errorMessage(code, `Additional engine check: ${humanize(code)}. Ask the administrator to review it.`)}</p>)}
    {lead.crm_handoff?.outbox_id && <p>Saved request: {lead.crm_handoff.outbox_id.slice(0, 8)} · Last updated: {dateLabel(lead.crm_handoff.updated_at)}</p>}
    {!reviewer && <p>An explicitly assigned reviewer role is required to inspect and approve this business’s hand-off.</p>}
    {error && <p className={cls("field-error")} role="alert">{error}</p>}
    {editable && <form onSubmit={event => {
      event.preventDefault(); const form = new FormData(event.currentTarget); const decision = form.get("decision");
      if (disabled || !(decision === "approve" ? guidance.canApprove : decision === "reject" && guidance.canReject)) {
        setError("This decision is not available under the current engine checks. Refresh and review the latest status before trying again."); return;
      }
      setError(null);
      void save("crm-approvals", { row_id: lead.row_id, expected_version: expectedVersion, decision, reason: form.get("reason") });
    }}><fieldset disabled={disabled || !(guidance.canApprove || guidance.canReject)}><legend>Record this business’s CRM decision</legend>
      <label>Decision<select name="decision" required defaultValue=""><option value="" disabled>Choose a checked decision</option><option value="approve" disabled={!guidance.canApprove}>Approve this business for hand-off</option><option value="reject" disabled={!guidance.canReject}>Reject this hand-off</option></select></label>
      <label>Reason<textarea name="reason" minLength={1} maxLength={2000} required rows={2} /></label>
      <button className={cls("button", "secondary")} type="submit">Save CRM decision</button>
    </fieldset></form>}
  </section>;
}


export function PermissionForm({ contact, disabled, save }: {
  contact: NonNullable<Lead["contacts"]>[number]; disabled: boolean;
  save: (endpoint: string, body: unknown) => Promise<void>;
}) {
  // Keep the revision that accompanied the form values. Background refreshes
  // must not make an older draft overwrite a newer reviewer's decision.
  const [revision, setRevision] = useState(contact.revision);
  const [formEpoch, setFormEpoch] = useState(0);
  return <>
    {contact.revision !== revision && <div role="status"><p>This contact has a newer saved decision. Your draft is still open; reload before recording another assessment.</p><button className={cls("button", "secondary", "small")} disabled={disabled} type="button" onClick={() => { setRevision(contact.revision); setFormEpoch(value => value + 1); }}>Reload permission form</button></div>}
      <form key={formEpoch} onSubmit={event => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        void save("basis-assessments", { contact_id: contact.contact_id, channel: "email", expected_revision: revision,
          basis_type: "inferred", assessment_state: form.get("assessment_state"),
          limbs: Object.fromEntries(["role", "publication", "agreement", "no_prohibition"].map(name => [name, form.get(name)])),
          evidence_provenance_id: contact.provenance_id, reason: form.get("reason") });
      }}><fieldset disabled={disabled}><legend>Record-level permission assessment</legend>
        {[["role", "A relevant individual or role is identified"], ["publication", "The address is conspicuously published"], ["agreement", "Evidence supports publication with agreement"], ["no_prohibition", "There is no statement prohibiting unsolicited contact"]].map(([name, label]) => <label key={name}>{label}<select name={name} required defaultValue="unknown"><option value="unknown">Unknown</option><option value="pass">Pass — evidence supports this</option><option value="fail">Fail</option></select></label>)}
        <label>Overall decision<select name="assessment_state" required defaultValue="unknown"><option value="unknown">Unknown — blocked</option><option value="pass">Pass — every required limb passes</option><option value="fail">Fail — blocked</option><option value="withdrawn">Withdrawn — blocked</option></select></label>
        <label>Reason<textarea name="reason" required minLength={1} maxLength={2000} rows={2} /></label>
        <button type="submit" className={cls("button", "secondary")}>Save permission assessment</button>
      </fieldset></form>
  </>;
}

type SourceRow = { snapshot_id: string; licence_number: string; licensee_name: string; row_digest: string;
  original_address?: string; financial_category?: string | number; publisher_status: string;
  review_status?: string; reviewed_at?: string; reason_codes?: string[] };
type ReviewData = { total: number; rows: SourceRow[]; publisher_modified_at?: string; source_observed_at?: string };
function validReviewData(value: unknown): value is ReviewData {
  return record(value) && Number.isSafeInteger(value.total) && Number(value.total) >= 0 && Array.isArray(value.rows)
    && value.rows.length <= 100 && value.rows.every(row => record(row)
      && ["snapshot_id", "licence_number", "licensee_name", "row_digest", "publisher_status"].every(key => typeof row[key] === "string")
      && /^[a-f0-9]{64}$/.test(String(row.row_digest)));
}

export function SourceReviews({ engine }: { engine: DashboardController }) {
  const [data, setData] = useState<ReviewData | null>(null);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);
  const pending = useRef<{ fingerprint: string; id: string } | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  if (!engine.data?.scopes?.includes("reviewer")) return <section className={cls("settings-section")}><h2>Source review</h2><p>Checking a current QBCC licence needs an explicitly assigned reviewer role. Your admin account can still view stored businesses and record outcomes.</p></section>;
  const row = data?.rows.find(item => item.licence_number === selected) ?? data?.rows[0];
  async function load(page: number) {
    setBusy(true); setError(null);
    try {
      const response = await engine.request(`qbcc-reviews/${page}`);
      if (!validReviewData(response)) throw new Error("The source review response is incomplete. No change was made.");
      if (mounted.current) { setData(response); setOffset(page); setSelected(""); }
    } catch (failure) { if (mounted.current) setError(errorText(failure)); }
    finally { if (mounted.current) setBusy(false); }
  }
  return <section className={cls("settings-section", "source-review-section")} aria-labelledby="source-review-title">
    <div className={cls("section-heading")}><div><h2 id="source-review-title">QBCC source review</h2><p>A bulk record is a discovery clue. Check the current licence before qualifying a business.</p></div><button type="button" className={cls("button", "secondary")} disabled={busy || !engine.connected} onClick={() => void load(offset)}>{busy ? "Loading…" : data ? "Refresh source records" : "Load source records"}</button></div>
    {error && <p role="alert" className={cls("field-error")}>{error}</p>}{receipt && <p role="status">{receipt}</p>}
    {data && <><p>{data.total} stored source records. Publisher date: {dateLabel(data.publisher_modified_at)}. Imported: {dateLabel(data.source_observed_at)}.</p>
      {!data.rows.length ? <p>No accepted source records are available. Check Setup for required source approvals and run status.</p> : <div className={cls("source-review-grid")}>
        <div><label htmlFor="source-business">Business to review</label><select id="source-business" value={row?.licence_number || ""} onChange={event => setSelected(event.target.value)} disabled={busy}>{data.rows.map(item => <option key={item.licence_number} value={item.licence_number}>{item.licensee_name} · {item.licence_number}</option>)}</select>
          <p>Showing {offset + 1}–{offset + data.rows.length} of {data.total}</p><div className={cls("form-actions")}><button type="button" className={cls("button", "secondary", "small")} disabled={busy || !offset} onClick={() => void load(Math.max(0, offset - 100))}>Previous 100</button><button type="button" className={cls("button", "secondary", "small")} disabled={busy || offset + 100 >= data.total} onClick={() => void load(offset + 100)}>Next 100</button></div>
        </div>
        {row && <form key={`${row.licence_number}:${row.row_digest}`} onSubmit={async event => {
          event.preventDefault(); const form = new FormData(event.currentTarget);
          const body = { snapshot_id: row.snapshot_id, licence_number: row.licence_number, row_digest: row.row_digest,
            status: form.get("status"), identity_match: form.get("identity_match") === "on",
            evidence_ref: form.get("evidence_ref"), reviewed_at: new Date(String(form.get("reviewed_at"))).toISOString() };
          const fingerprint = JSON.stringify(body);
          if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, id: crypto.randomUUID() };
          setBusy(true); setError(null); setReceipt(null);
          try {
            const result = await engine.request("qbcc-reviews", { method: "POST", body: JSON.stringify({ ...body, request_id: pending.current.id }) });
            if (!record(result) || typeof result.review_id !== "string" || typeof result.state !== "string") throw new Error("The review was not confirmed. Refresh the source records before retrying.");
            if (!mounted.current) return;
            pending.current = null; setReceipt(`Review saved: ${humanize(result.state)}. Contact permission remains a separate check.`);
            await engine.refresh(); await load(offset);
          } catch (failure) { if (mounted.current) setError(errorText(failure)); }
          finally { if (mounted.current) setBusy(false); }
        }}><fieldset disabled={busy || !engine.connected}><legend>{row.licensee_name}</legend>
          <p>Licence {row.licence_number} · Category {row.financial_category ?? "Unknown"}<br />{row.original_address || "Address not recorded"}</p>
          <p>Current status from bulk file: {row.publisher_status}. Last reviewer decision: {humanize(row.review_status)}.</p>
          <a href="https://my.qbcc.qld.gov.au/s/qbcc-licensee-register" target="_blank" rel="noreferrer">Open the QBCC licence checker</a>
          <label>What does the current register show?<select name="status" required defaultValue=""><option value="" disabled>Choose the checked status</option>{["active", "suspended", "cancelled", "inactive", "unknown"].map(status => <option key={status} value={status}>{humanize(status)}</option>)}</select></label>
          <label className={cls("checkbox-label")}><input name="identity_match" type="checkbox" />I checked that this licence identifies this exact business.</label>
          <label>Evidence reference<input name="evidence_ref" required minLength={1} maxLength={500} placeholder="Private saved receipt or checked register record" /></label>
          <label>When did you check it? (your local time)<input name="reviewed_at" type="datetime-local" required /></label>
          <button type="submit" className={cls("button", "primary")}>Save licence review</button>
        </fieldset></form>}
      </div>}</>}
  </section>;
}
