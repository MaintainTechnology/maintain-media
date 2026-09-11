import type { CrmHandoff, DashboardData, Job } from "@/lib/abn-lead-gen/types";

type SetupItem = DashboardData["setup"][number];
type Step = { owner: string; action: string };
type Guidance = { summary: string; steps: Step[] };

const capabilityGuidance: Record<string, Guidance> = {
  collection: {
    summary: "Collecting business records is switched off.",
    steps: [
      { owner: "Business owner or authorised delegate", action: "Confirm the owner's QBCC-only pilot scope, including permitted fields, source terms, privacy and retention limits. Website collection and vendor hand-off have separate controls." },
      { owner: "Developer", action: "Verify the QBCC source format and the security, recovery and release checks required for that limited pilot. Then enable only the owner-authorised QBCC scope." },
    ],
  },
  crm: {
    summary: "Sending approved leads to GoHighLevel is switched off.",
    steps: [
      { owner: "Business owner or authorised delegate and developer", action: "Confirm the approved GoHighLevel account, staff access, terms and countries where data is processed." },
      { owner: "Developer", action: "Test field mapping, duplicate handling and do-not-contact updates in the approved account before enabling hand-off." },
      { owner: "Reviewer", action: "Approve each eligible, selected tier A business separately. Enabling the connection does not approve every business or allow outreach." },
    ],
  },
  website_collection: {
    summary: "Collecting contact details from business websites is switched off.",
    steps: [
      { owner: "Business owner or authorised delegate", action: "Confirm the separate, limited website research decision, permitted phone fields, notice and retention limits. QBCC approval alone does not approve website collection or email harvesting." },
      { owner: "Reviewer and developer", action: "Verify the business identity, current licence and each site's terms. Enable only the recorded scope; each website still needs its own checked submission." },
    ],
  },
  abr: {
    summary: "ABR source validation and discovery are switched off.",
    steps: [
      { owner: "Business owner or authorised delegate", action: "Check the separate early ABR validation decision, public notice and its permitted fields and retention limits. The recorded scope can permit source validation before the later measured pilot finishes." },
      { owner: "Developer", action: "Verify the live ABR feed, source format, complete publication, capacity and recovery checks before enabling the recorded scope. The first accepted list is a baseline with zero new-business events or leads." },
      { owner: "Reviewer and developer", action: "Complete the separate 100-record matching review before activating classification. Collecting the source does not establish matched leads or approve contact collection or vendor hand-off." },
    ],
  },
};

const gateGuidance: Record<string, Step> = {
  GATE_G1_CLOSED: { owner: "Business owner and privacy adviser", action: "Record or renew the source and privacy decision. The engine cannot confirm a current approval for this feature." },
  GATE_G2_CLOSED: { owner: "Business owner and developer", action: "Record or renew the relevant rules and source-format checks. The engine cannot confirm current evidence for this feature." },
  GATE_G3_CLOSED: { owner: "Developer and business owner", action: "Complete and record the hosting, access, backup recovery and capacity checks. The engine cannot confirm current security approval." },
  GATE_G4_CLOSED: { owner: "Business owner, reviewer and developer", action: "Record the required contact checks and current action approval. This tool does not send messages or make calls." },
  GATE_G5_CLOSED: { owner: "Business owner and developer", action: "Record the vendor's terms and processing countries, then verify field mapping, retries, duplicates and do-not-contact updates. The engine cannot confirm current hand-off approval." },
  GATE_G6_CLOSED: { owner: "Business owner or authorised delegate", action: "Check or renew the scoped ABR expansion decision and its limits. The engine cannot confirm current approval; source validation and matching activation have separate requirements." },
  GATE_G7_CLOSED: { owner: "Business owner and developer", action: "Record the final release decision for the installed version after the required checks and recovery exercise pass. The engine cannot confirm current release approval." },
};

export function readinessGuidance(item: SetupItem, mode: DashboardData["mode"]) {
  const ready = ["ready", "complete", "connected", "available", "approved"].includes(item.status);
  const statusLabels: Record<string, string> = {
    ready: "Ready", complete: "Complete", connected: "Connected", available: "Available",
    approved: "Approvals recorded", blocked: "Blocked", pending: "Pending", unknown: "Not verified",
  };
  const base = { ready, statusLabel: Object.hasOwn(statusLabels, item.status) ? statusLabels[item.status] : "Not verified", summary: item.detail, steps: [] as Step[], note: "", technicalDetail: "" };
  // Fixture descriptions and positive/unknown states remain the engine's own result.
  // A disabled flag alone is not evidence that a particular approval is missing.
  if (mode === "fixture" || item.status !== "blocked") return base;
  const match = /^Required evidence:\s*(.+)$/.exec(item.detail);
  const codes = match ? [...new Set(match[1].split(",").map(code => code.trim()))] : [];
  if (!codes.length || codes.some(code => !/^[A-Z][A-Z0-9_]*$/.test(code))) {
    return { ...base, steps: [{ owner: "Developer", action: "Check the engine details for this item and confirm the next step with the responsible approver." }] };
  }
  const disabled = codes.includes("CAPABILITY_DISABLED");
  const capability = typeof item.id === "string" && Object.hasOwn(capabilityGuidance, item.id) ? capabilityGuidance[item.id] : undefined;
  const reportedChecks = codes.filter(code => code !== "CAPABILITY_DISABLED");
  const steps = reportedChecks.map(code => code === "GATE_G1_CLOSED" && ["collection", "website_collection", "crm", "abr"].includes(item.id || "") ? {
    owner: "Business owner or authorised delegate and developer", action: item.id === "website_collection"
      ? "Check or renew the separate recorded phone-only website research decision and its limits. The engine cannot confirm current approval for this feature."
      : item.id === "crm" ? "Check or renew the separate decision permitting this limited GoHighLevel disclosure and its source/privacy limits. The engine cannot confirm current approval for this feature."
      : item.id === "abr" ? "Check or renew the separate early ABR validation decision, public notice and its field and retention limits. The engine cannot confirm current approval for this feature."
      : "Check or renew the recorded QBCC-only source decision and its limits. The engine cannot confirm current approval for this feature.",
  } : code === "GATE_G5_CLOSED" && item.id === "crm" ? {
    owner: "Business owner or authorised delegate and developer", action: "Check or renew the separate GoHighLevel vendor decision, actual account setup and data-processing evidence. The engine cannot confirm the current hand-off approval.",
  } : gateGuidance[code] || {
    owner: "Developer", action: "Review the additional engine check in the details below. Its meaning has not been verified here; keep this feature blocked.",
  });
  if (!reportedChecks.length) steps.push(...(capability?.steps || [{
    owner: "Developer and the business owner", action: "Identify this feature's required approvals and setup tests before enabling it.",
  }]));
  return {
    ...base,
    summary: disabled ? capability?.summary || "This feature is switched off." : reportedChecks.every(code => Object.hasOwn(gateGuidance, code)) ? "This feature is waiting for current approval evidence." : "This feature is waiting for required checks.",
    steps,
    note: disabled && !reportedChecks.length ? "Approval details have not been checked in this response. Confirm the steps below before activation." : "",
    technicalDetail: item.detail,
  };
}

export function sourceJobGuidance(job: Job) {
  const active = ["queued", "running", "pending"].includes(job.state);
  if (job.source !== "abr") return { title: active ? "The engine is working on your run." : job.state === "complete" ? "Your run is complete." : "Your run needs attention.", detail: "" };
  if (active) return { title: "The engine is checking the ABR publication.", detail: "A complete, validated publication is needed before the accepted list changes. The first accepted list establishes a baseline; it does not create new-business events or leads." };
  if (job.state !== "complete") return { title: "This ABR run needs attention.", detail: "This run has not confirmed a new accepted result. Previously accepted data is not replaced by an incomplete publication." };
  const result = job.result;
  if (result?.noop === true && result.events === 0 && result.candidates === 0) return { title: "ABR publication is unchanged.", detail: "The engine confirmed an unchanged source. No new leads were created by this check." };
  if (result?.baseline === true && result.events === 0 && result.candidates === 0) return { title: "ABR baseline accepted.", detail: "The starting reference list is stored. This baseline created zero new-business events and zero leads. Matching still needs its separate accuracy review." };
  if (typeof result?.events === "number" && typeof result.candidates === "number") return { title: "ABR publication comparison complete.", detail: `${result.events.toLocaleString("en-AU")} registration changes observed; ${result.candidates.toLocaleString("en-AU")} lead candidates created. A registration change is not proof of a newly formed business.${result.classification === "disabled" ? " Matching is disabled pending its separate accuracy review." : ""}` };
  return { title: "ABR run complete; result details not verified.", detail: "Refresh for the committed source receipt. A completed run alone does not confirm new businesses or leads." };
}

export function crmHandoffGuidance(handoff?: CrmHandoff | null) {
  const states: Record<string, { label: string; detail: string }> = {
    not_selected: { label: "Not selected for hand-off", detail: "This business does not have a selected worklist row. Complete its qualification and contact checks before a reviewer can approve a GoHighLevel hand-off." },
    awaiting_review: { label: "Awaiting your decision", detail: "A reviewer must check this selected business and explicitly approve or reject its hand-off. The engine checks current eligibility again when you save." },
    rejected: { label: "Hand-off rejected", detail: "The saved decision rejects this hand-off. This status does not say that any earlier completed transfer has been removed." },
    pending: { label: "Queued for hand-off", detail: "The approval is saved. The worker will check current eligibility before transferring this business; transfer is not yet confirmed." },
    inflight: { label: "Hand-off in progress", detail: "The worker is checking or transferring this business. Wait for its verified result; do not create a duplicate contact manually." },
    retry: { label: "Waiting to retry", detail: "The worker will retry using the saved request after its waiting period. A successful hand-off has not been confirmed." },
    uncertain: { label: "Checking the remote result", detail: "The previous request has an uncertain result. The worker must reconcile it before another create attempt; do not create a duplicate contact manually." },
    succeeded: { label: "Hand-off verified", detail: "The engine verified this saved transfer in GoHighLevel. This does not mean that a message was sent or that a call is permitted." },
    blocked: { label: "Hand-off blocked", detail: "The worker cannot proceed under the current checks. Review the reported restrictions; do not bypass them or assume a previous transfer was removed." },
    dead_letter: { label: "Administrator review required", detail: "Automatic attempts have stopped. Ask the administrator to reconcile the saved request before trying again." },
  };
  const known = !!handoff && Object.hasOwn(states, handoff.state);
  return { ...(known ? states[handoff.state] : { label: "Hand-off not verified", detail: "No recognised current hand-off status is available. Refresh the workspace before making a CRM decision." }),
    canApprove: known && handoff.can_approve,
    canReject: known && handoff.can_reject,
  };
}

export function websiteCollectionGuidance(data: DashboardData | null) {
  const policy = data?.website_collection_policy;
  const enabled = data?.mode !== "fixture" && !!policy && policy.reason_codes.length === 0
    && policy.allowed_channels.length === 2 && policy.allowed_channels.includes("mobile") && policy.allowed_channels.includes("landline")
    && typeof policy.expires_at === "string" && Date.parse(policy.expires_at) > Date.now();
  return {
    enabled,
    summary: enabled
      ? "This request can collect public Australian phone numbers from the reviewed business website for internal research. Email extraction is disabled. A phone number does not establish permission to call."
      : data?.mode === "fixture" ? "Synthetic records do not authorise a live website request."
        : "Phone-only website collection is not currently confirmed for this workspace. Refresh and check Website contact collection in Setup before submitting.",
  };
}
