import type { DashboardData } from "@/lib/abn-lead-gen/types";

type SetupItem = DashboardData["setup"][number];
type Step = { owner: string; action: string };
type Guidance = { summary: string; steps: Step[] };

const capabilityGuidance: Record<string, Guidance> = {
  collection: {
    summary: "Collecting business records is switched off.",
    steps: [
      { owner: "Jon Pepper and the privacy adviser", action: "Confirm the written decision to use QBCC data, including source terms, privacy and how long records may be kept." },
      { owner: "Developer", action: "Verify the QBCC source format, security, backup recovery and release checks. Then enable only the approved QBCC pilot scope." },
    ],
  },
  crm: {
    summary: "Sending approved leads to GoHighLevel is switched off.",
    steps: [
      { owner: "Jon Pepper and the developer", action: "Confirm the approved GoHighLevel account, staff access, terms and countries where data is processed." },
      { owner: "Developer", action: "Test field mapping, duplicate handling and do-not-contact updates in the approved account before enabling hand-off." },
    ],
  },
  website_collection: {
    summary: "Collecting contact details from business websites is switched off.",
    steps: [
      { owner: "Jon Pepper and the privacy adviser", action: "Record the separate decision for website contact collection, including permitted fields, source terms, notices and retention. QBCC approval does not approve this feature." },
      { owner: "Reviewer and developer", action: "Verify business identity, current licence and each site's terms, then test the approved collection controls before enabling this feature." },
    ],
  },
  abr: {
    summary: "Broader ABR discovery is switched off. This is a later stage after the QBCC pilot.",
    steps: [
      { owner: "Jon Pepper", action: "Review four measured weeks of the QBCC pilot and record whether to expand to ABR." },
      { owner: "Jon Pepper and the developer", action: "Complete the separate 100-record matching review and ABR source checks." },
      { owner: "Developer", action: "Complete and test the live ABR feed. Then record the broader release approval with Jon before enabling it." },
    ],
  },
};

const gateGuidance: Record<string, Step> = {
  GATE_G1_CLOSED: { owner: "Jon Pepper and the privacy adviser", action: "Record or renew the source and privacy decision. The engine cannot confirm a current approval for this feature." },
  GATE_G2_CLOSED: { owner: "Jon Pepper and the developer", action: "Record or renew the relevant rules and source-format checks. The engine cannot confirm current evidence for this feature." },
  GATE_G3_CLOSED: { owner: "Developer and Jon Pepper", action: "Complete and record the hosting, access, backup recovery and capacity checks. The engine cannot confirm current security approval." },
  GATE_G4_CLOSED: { owner: "Jon Pepper, the reviewer and the developer", action: "Record the required contact checks and current action approval. This tool does not send messages or make calls." },
  GATE_G5_CLOSED: { owner: "Jon Pepper and the developer", action: "Record the vendor's terms and processing countries, then verify field mapping, retries, duplicates and do-not-contact updates. The engine cannot confirm current hand-off approval." },
  GATE_G6_CLOSED: { owner: "Jon Pepper", action: "Review four measured QBCC pilot weeks and record the ABR expansion decision. The engine cannot confirm current expansion approval." },
  GATE_G7_CLOSED: { owner: "Jon Pepper and the developer", action: "Record the final release decision for the installed version after the required checks and recovery exercise pass. The engine cannot confirm current release approval." },
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
  const steps = reportedChecks.map(code => gateGuidance[code] || {
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
