# Plan

## Overview
SPECIFICATION SCORE: 8.1/10. Weighted rubric: correctness/evidence 8.0/10 × 25% = 2.00; requirements/acceptance 8.5/10 × 20% = 1.70; architecture/data integrity 8.0/10 × 20% = 1.60; privacy/security/operability 8.0/10 × 20% = 1.60; scope/delivery/traceability 8.0/10 × 15% = 1.20; total = 8.10/10. The specification is unusually detailed and close to build-ready as a planning document, but it is not 9+ ready because it embeds many unreproduced “VERIFIED” claims, references non-existent or unconfirmed repo artifacts, and leaves several determinism, legal, retention, concurrency, and operational recovery points insufficiently pinned down.

## Scope
- In: Independently judge the supplied ABR Lead Engine specification as written.
- In: Identify blockers and precise corrections before implementation planning proceeds.
- In: Separate specification readiness from production certification, legal approval, and live evidence.
- In: Produce an Obsidian-friendly documentation/build-planning plan.
- Out: App implementation.
- Out: File edits, code execution, network verification, delegated review, or live repo inspection.
- Out: Production certification, legal advice, benchmark confirmation, or current-law certainty.

## Phases
### Phase 1: Specification Readiness Judgment
**Goal**: Score the supplied document only, record the weighted basis, and identify readiness blockers that must be corrected before build.

#### Task 1.1: Record Independent Score
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Create a readiness assessment that scores the supplied specification as-is, not a hypothetical corrected version.
- Estimated Tokens: 1200
- Dependencies: None
- Steps:
  - State `SPECIFICATION SCORE: 8.1/10`.
  - Include the weighted rubric and per-dimension scores.
  - Explain that historical `VERIFIED` assertions are treated as unverified unless the evidence is attached and reproducible in this review.
  - State that legal approval and production certification are separate gates.
- Acceptance Criteria:
  - Score is independent, numeric, and weighted.
  - No score relies on external verification unavailable in the supplied material.
  - The assessment does not imply legal sign-off.

#### Task 1.2: Separate Readiness From Certification
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Add a short section distinguishing specification quality from release authority.
- Estimated Tokens: 700
- Dependencies: Task 1.1
- Steps:
  - Mark specification as “strong but conditionally build-ready.”
  - Mark production certification as blocked pending real source verification, legal review, live credentials, DNC access, and first-run evidence.
  - Mark legal approval as unresolved and outside the score.
- Acceptance Criteria:
  - The document cannot be read as permission to send, call, crawl, or process production personal information.
  - The build can start only with safe defaults and mocked external I/O.

### Phase 2: Blocker Register
**Goal**: Convert weaknesses into exact, fixable specification changes.

#### Task 2.1: Add Evidence and Source Blockers
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: List evidence blockers where the spec makes assertions without attached reproducible proof.
- Estimated Tokens: 1800
- Dependencies: Task 1.1
- Steps:
  - Blocker: `Changes in 3.5`, `Context / background`, `Constraints`; failure example: a developer treats vendor pricing, ABR cadence, DuckDB benchmark, ABS figures, QBCC freshness, or legal citations as current fact, but no evidence bundle is attached.
  - Smallest correction: attach dated evidence artifacts or downgrade each claim to “assumption pending verification.”
  - Blocker: `Context / background / What already exists in this repo`; failure example: spec claims `deliverables/abr/extract_new_abns.py` exists, while task brief says the claimed path does not exist in the current checkout.
  - Smallest correction: replace repo-current claims with “expected/imported prior artifact” or add a repo inventory appendix listing actual available files.
- Acceptance Criteria:
  - Every “VERIFIED” claim is either backed by attached evidence or marked unverified for this review.
  - Nonexistent referenced files are explicitly called out.

#### Task 2.2: Add Snapshot Identity and Republish Blockers
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Tighten snapshot identity, same-day republish handling, and date-key rules.
- Estimated Tokens: 1600
- Dependencies: Task 2.1
- Steps:
  - Blocker: R1/R6/R36 use `last_modified`, inner member filename date, and `snapshot_to` without a single canonical snapshot identity.
  - Failure example: two off-cycle republishes with the same inner `YYYYMMDD` overwrite `snapshots/abr_<YYYYMMDD>.parquet` or collide in `abr_events` primary keys.
  - Smallest correction: define `snapshot_id = hash(resource ids + last_modified values + sizes + inner member names + member CRCs)` and use it in manifests and event uniqueness; keep `snapshot_date` as descriptive metadata only.
  - Require object storage keys that cannot overwrite same-day republishes.
- Acceptance Criteria:
  - Same-day or off-cycle republishes cannot overwrite snapshots.
  - Diff inputs are uniquely identifiable even when inner XML dates repeat.

#### Task 2.3: Add Matching ZIP Generation Rules
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Define how Part 1 and Part 2 are proven to belong to the same ABR generation.
- Estimated Tokens: 1000
- Dependencies: Task 2.2
- Steps:
  - Blocker: R1 says ZIP halves must be within 48 hours but does not require consistent inner date keys, schema/version markers, or count manifest compatibility.
  - Failure example: Part 1 and Part 2 are both newly modified but contain different generation dates, causing phantom joins and false exits.
  - Smallest correction: require both ZIPs to share an expected generation date or compatible metadata, and fail closed if inner member dates disagree.
- Acceptance Criteria:
  - ZIP pairing has deterministic acceptance and refusal rules.
  - Manual override records exact mismatched metadata.

#### Task 2.4: Add Concurrency and Crash Recovery Blockers
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Strengthen lock, transaction, idempotency, and resume semantics.
- Estimated Tokens: 1500
- Dependencies: Task 2.2
- Steps:
  - Blocker: R38 says a lockfile prevents concurrent runs but does not define stale lock recovery, stage idempotency, or partial artifact cleanup.
  - Failure example: process crashes after uploading a snapshot but before writing `run_manifest.json`; next run may reprocess, duplicate events, or skip an unmanifested snapshot.
  - Smallest correction: require run states `started`, `snapshot_written`, `events_written`, `exported`, `completed`, with atomic manifest writes and resumable stage commands keyed by `run_id` and `snapshot_id`.
  - Define stale lock rules using PID, hostname, start time, and operator override.
- Acceptance Criteria:
  - Every stage can be safely retried.
  - Partial CRM pushes and Sheet exports are idempotent.

### Phase 3: Determinism, Data Integrity, and Safety Corrections
**Goal**: Make ambiguous business rules deterministic enough for implementation and testing.

#### Task 3.1: Tighten Deterministic Rules
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Identify non-deterministic or underspecified rules and add exact corrections.
- Estimated Tokens: 1700
- Dependencies: Phase 2
- Steps:
  - Blocker: R12/R14 classify “all BN names” and “all TRD names” but do not define ordering within same type.
  - Failure example: two parsers preserve `OtherEntity` order differently and choose different `industry_matched_on`.
  - Smallest correction: sort same-type names by source order if guaranteed by XML, otherwise by normalized text; state which one is authoritative.
  - Blocker: R21 says use highest-population locality for postcode but does not name the population source, tie-break, or version.
  - Smallest correction: commit postcode-locality lookup with source version and deterministic tie-break.
- Acceptance Criteria:
  - Fixed fixtures produce byte-identical output across platforms and reruns.
  - Every tie-break has a documented field order.

#### Task 3.2: Tighten Crawl Identity and SSRF Controls
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Add crawler security controls beyond robots compliance.
- Estimated Tokens: 1400
- Dependencies: Task 3.1
- Steps:
  - Blocker: R21 defines crawl behavior but not SSRF, redirects, DNS rebinding, private IP blocks, file URL blocks, or maximum response sizes.
  - Failure example: accepted domain redirects to `http://169.254.169.254/latest/meta-data` or an internal IP and the crawler fetches it.
  - Smallest correction: require HTTPS preference, URL scheme allowlist, DNS resolution checks before and after redirects, private/link-local IP denial, redirect limit, content-type allowlist, and byte/time ceilings.
  - Require crawl User-Agent and contact URL to be configured and logged.
- Acceptance Criteria:
  - Fixture URLs for private IPs, metadata services, bad schemes, large files, and redirect chains are refused.
  - Crawl logs prove identity and rate limits.

#### Task 3.3: Tighten Suppression Freshness and Propagation
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Ensure opt-outs and suppression propagate across exports, enrichment, CRM, and worklists.
- Estimated Tokens: 1300
- Dependencies: Task 3.2
- Steps:
  - Blocker: R26/R30 say suppression is immediate and permanent but do not define propagation latency or CRM remediation.
  - Failure example: VA records `do_not_contact_requested` after export; lead remains callable in GoHighLevel until next weekly run.
  - Smallest correction: require immediate Sheet read-back or webhook-triggered suppression, CRM tag/update within one business day, and every export to re-check suppression at generation time.
- Acceptance Criteria:
  - Suppression created from any channel blocks all future exports immediately.
  - CRM and worklist state are reconciled and audited.

#### Task 3.4: Resolve Retention Conflict
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Reconcile R6 indefinite snapshot retention with R31a limited retention.
- Estimated Tokens: 1000
- Dependencies: Task 3.3
- Steps:
  - Blocker: R6 says snapshots are retained indefinitely; R31a recommends 24 months then thinning.
  - Failure example: implementer keeps full-register personal information forever because R6 appears authoritative.
  - Smallest correction: replace R6 “retained indefinitely” with the R31a schedule, or explicitly mark legal sign-off required before indefinite retention.
- Acceptance Criteria:
  - There is one authoritative retention rule.
  - Out-of-scope personal information has a minimization path.

### Phase 4: Compliance, Cost, and Delivery Gaps
**Goal**: Clarify unresolved dependencies and safe build defaults before any production-like run.

#### Task 4.1: Add Consent and Channel Rules Matrix
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Convert compliance prose into a channel-by-channel export matrix.
- Estimated Tokens: 1500
- Dependencies: Phase 3
- Steps:
  - Blocker: R24-R29 are rich but scattered; channel decisions can still be misimplemented.
  - Failure example: phone is exported because email passed clause 4, or email is blocked because `send_eligibility` does not yet exist in Part 1.
  - Smallest correction: add a table for email, mobile, landline, contact form, social URLs, and CRM-only fields showing required gates, expiry, evidence, export label, and Part 1 vs Part 2 owner.
- Acceptance Criteria:
  - Each channel has a single deterministic gate.
  - Part 1 does not accidentally send or require send-time data.

#### Task 4.2: Add Budget Accounting Rules
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Define how spend is tracked, reserved, and stopped.
- Estimated Tokens: 1000
- Dependencies: Task 4.1
- Steps:
  - Blocker: R20 sets A$150/month enrichment cap but does not define exchange rate source, billing month, preflight reservation, retry accounting, or partial-call cost attribution.
  - Failure example: concurrent or retried enrichment spends over cap before the manifest notices.
  - Smallest correction: define cap period, currency conversion source/date, per-provider unit costs, pre-call budget reservation, refund on failed no-charge calls, and atomic spend ledger.
- Acceptance Criteria:
  - Cap enforcement is testable without real providers.
  - Retries and partial failures cannot bypass the cap.

#### Task 4.3: Add Capacity and Cost Validation
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Replace fragile estimates with required measurement checkpoints.
- Estimated Tokens: 1200
- Dependencies: Task 4.2
- Steps:
  - Blocker: host disk, memory, storage growth, and enrichment volume depend on estimates and prior assertions.
  - Failure example: first full run exhausts 75 GB local disk because temporary files, DuckDB spill, ZIPs, Parquet, Postgres WAL, and page captures overlap.
  - Smallest correction: add pre-build capacity worksheet, pre-run disk budget, WAL/temp directory limits, object-storage lifecycle, and measured first-snapshot replacement of estimates.
- Acceptance Criteria:
  - The first production-like run has explicit free-space and temp-space checks.
  - Cost model is updated from measured output before continuing past Phase 0.

#### Task 4.4: Add Missing File and Traceability Corrections
- Location: `docs/specs/abr-lead-engine-readiness.md`
- Description: Ensure the spec references files that either exist or are planned deliverables.
- Estimated Tokens: 1000
- Dependencies: Task 4.3
- Steps:
  - Blocker: referenced paths and artifacts include `deliverables/abr/extract_new_abns.py`, rules YAML, service-term vocabulary, postcode lookup, CRM mapping, script tests, runbook, and READMEs, but not all are confirmed present.
  - Failure example: developer starts from a missing extractor and silently recreates incompatible behavior.
  - Smallest correction: add an artifact inventory with status values `existing`, `to-create`, `external`, or `removed`, and list exact target paths.
- Acceptance Criteria:
  - Every referenced artifact has an owner path and status.
  - Missing prior files are not treated as build inputs.

## Testing Strategy
- Static spec review: verify each blocker includes exact section/requirement, failure example, and smallest correction.
- Traceability review: map every requirement R1-R38, R15a, R18a, R24a, and R31a to an acceptance item or explicitly mark as operational/legal-only.
- Contradiction review: check snapshot retention, snapshot identity, ZIP pairing, same-day republishes, channel gates, and Part 1/Part 2 boundaries.
- Evidence review: downgrade or attach support for every `VERIFIED`, benchmark, legal, vendor, volume, and pricing claim.
- Determinism review: ensure all ordering, tie-breaks, date keys, currency conversion, locality matching, scoring, queue ageing, and retry behavior are fixed.
- Security review: confirm crawler SSRF controls, robots wildcard behavior, credential handling, access separation, suppression propagation, and audit logging are specified.
- Operability review: simulate crash points on paper for download, parse, snapshot write, diff insert, enrichment spend cap, Sheet export, CRM push, and outcome read-back.
- Readiness gate: do not score above 8.5 until attached evidence, artifact inventory, legal-review dependencies, and snapshot identity corrections are present.

## Risks
- Risk: The spec’s strongest claims are historical and embedded, not attached as reproducible evidence. Mitigation: require an evidence bundle or downgrade those claims before build.
- Risk: Same-day republishes can collide because `YYYYMMDD` is used as a storage and event date key. Mitigation: add immutable `snapshot_id` and non-overwriting object keys.
- Risk: The spec says both “snapshots retained indefinitely” and “24 months then monthly thinning.” Mitigation: make R31a the authoritative retention rule or block pending legal approval.
- Risk: Crawl compliance is incomplete without SSRF and redirect controls. Mitigation: add URL, DNS, IP, redirect, content-type, byte, and timeout restrictions.
- Risk: Suppression may be weekly rather than immediate if tied only to the next run. Mitigation: define immediate read-back/webhook and CRM remediation workflow.
- Risk: The DNC, Spam Act, Privacy Act, APP, ACL, and Google terms content may have changed or may be interpreted differently. Mitigation: treat all legal material as planning assumptions pending Australian legal review.
- Risk: Budget cap can be exceeded if spend is recorded after calls rather than reserved before calls. Mitigation: add atomic spend ledger and pre-call reservation.
- Risk: Nonexistent referenced repo files make “build-ready” overstated. Mitigation: add an artifact inventory and mark missing files as planned deliverables.
- Self-critique: This plan cannot verify the actual checkout because the task forbids tools, so the file-path recommendations are documentation targets rather than confirmed repo paths.
- Self-critique: The 8.1 score may still be generous because the specification relies heavily on unreproduced evidence; if even a few verified source, benchmark, or legal claims fail live verification, readiness should drop below 7.5.

## Rollback Plan
- If the readiness document overstates certainty, revise only the assessment document and lower claims from “verified” to “assumption pending evidence.”
- If a blocker is later proven invalid with attached evidence, remove that blocker and update the weighted score with a dated note.
- If implementation has already started from this spec, pause production-facing work, preserve generated artifacts, and backfill the artifact inventory, snapshot identity rule, retention rule, and channel matrix before continuing.
- If legal review rejects the crawl, email, phone, APP 3, APP 5, APP 7, APP 8, DNC, or ACL assumptions, disable the affected channel in rules/config and keep Phase 0 as a non-contact research/worklist exercise until corrected.
- If current repo files differ from the spec, update the spec references first rather than renaming or recreating code to match stale documentation.

## Edge Cases
- Same inner XML date but different `last_modified` values.
- Part 1 and Part 2 modified within 48 hours but containing inconsistent generation dates.
- ABR off-cycle republish with zero meaningful row changes.
- Re-run after crash between snapshot upload and manifest completion.
- Re-run after partial CRM push or partial Google Sheet update.
- Stale lock left by killed process.
- Rules YAML changed between provisional and final scoring.
- QBCC lead has no ABN and no parseable postcode.
- Multiple QBCC licences share one ABN.
- Same endpoint appears on multiple leads and receives one opt-out.
- Email basis expires while lead is carried over.
- DNC wash expires between worklist generation and VA action.
- Target site adds “no unsolicited marketing” after first enrichment.
- SERP result redirects to private IP, metadata IP, non-HTTP scheme, or oversized content.
- Spend cap reached mid-record.
- Snapshot archive retention conflicts with APP minimization.
- Google Sheet contains personal information and therefore makes Google an overseas recipient.
- Existing referenced extractor path does not exist in current checkout.
- Tier B produces no meetings while Tier A does, requiring pre-committed switch-off.

## Open Questions
- None for this planning pass; unresolved dependencies are blockers, not questions: attached evidence bundle, legal review, DNC access tier and lead time, artifact inventory, current repo file map, production credentials policy, and measured Phase 0/first-snapshot capacity data.