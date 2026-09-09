# Plan

## Overview
Assess the supplied ABR Lead Engine v4.0 documentation package as a specification, not as implemented software or legal certification. SPECIFICATION SCORE: 8.6/10 using weighted rubric: correctness/evidence 8.5/10 at 25%, requirements/acceptance 9.0/10 at 20%, architecture/data integrity 8.8/10 at 20%, privacy/security/operability 8.7/10 at 20%, scope/delivery/traceability 8.0/10 at 15%, weighted total 8.6/10.

## Scope
- In: Score the actual supplied specification package, including canonical spec, source checks, analysis, checklists, contracts, data model, plan, quickstart, research, tasks and workflow status.
- In: Identify blockers and precise improvements needed to raise specification readiness.
- In: Separate documentation readiness from production certification, implementation evidence, legal approval and vendor procurement.
- In: Credit controls already present, including synthetic/offline defaults, release gates, finite retention, current permission checks, suppression, SSRF controls and budget reservations.
- Out: Application implementation, code edits, command execution, repository validation, live source checks, network browsing, delegated review, legal advice, production approval or benchmark certification.

## Phases
### Phase 1: Freeze Review Basis
**Goal**: Define exactly what is being judged and prevent historical or planned evidence from being mistaken for current proof.

#### Task 1.1: Record review corpus and authority hierarchy
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `specs/001-abr-lead-engine/analysis.md`, `specs/001-abr-lead-engine/workflow-status.md`
- Description: Treat the canonical ABR Lead Engine v4.0 document and supplied feature package as the frozen review source. Confirm that planned application paths are future deliverables, not missing implemented files.
- Estimated Tokens: 900
- Dependencies: None
- Steps:
  - Record that version 4.0 revised 8 September 2026 is the reviewed document.
  - Record that all gates G1-G7 are pending and production capabilities remain off.
  - Record that `abr_engine/` and `deliverables/abr/extract_new_abns.py` are not current implementation evidence.
- Acceptance Criteria:
  - Review states the score applies only to supplied documentation.
  - Historical VERIFIED assertions are treated as unverified unless evidence is reproduced in the supplied package.
  - Production certification and legal approval remain explicitly separate.

#### Task 1.2: Apply weighted rubric
- Location: Review report section `Overview`
- Description: Score each required dimension from 0-10 and calculate weighted total.
- Estimated Tokens: 700
- Dependencies: Task 1.1
- Steps:
  - Score correctness/evidence, requirements/acceptance, architecture/data integrity, privacy/security/operability and scope/delivery/traceability.
  - Use only the supplied evidence, not hypothetical future fixes.
  - Round final weighted total to one decimal place.
- Acceptance Criteria:
  - Final specification score is independent from any prior Council/planner scores.
  - Rubric weights match: 25%, 20%, 20%, 20%, 15%.
  - Target 9+ is not awarded unless the current supplied document earns it.

### Phase 2: Score Findings
**Goal**: Identify readiness strengths and blockers with exact section, failure example and smallest correction.

#### Task 2.1: Assess correctness and evidence
- Location: `specs/abr-lead-engine.md`, `specs/abr-review-source-checks.md`, `specs/001-abr-lead-engine/research.md`
- Description: Verify whether factual claims are sourced, scoped and caveated.
- Estimated Tokens: 1100
- Dependencies: Phase 1
- Steps:
  - Credit corrections for GST, QBCC, DNCR cost, telemarketing windows, APP7, source cadence and consent heuristics.
  - Flag unresolved factual dependencies: current vendor pricing, signup terms, legal clearance, processor countries, legacy rule corpus, live source mapping and capacity evidence.
  - Ensure prior counts, timings and SQL claims remain historical or unverified.
- Acceptance Criteria:
  - Correctness/evidence score: 8.5/10.
  - Blockers distinguish missing evidence from defective specification text.
  - No invented benchmark, law or source certainty is introduced.

#### Task 2.2: Assess requirements and acceptance
- Location: `specs/001-abr-lead-engine/spec.md`, `specs/001-abr-lead-engine/tasks.md`, `specs/001-abr-lead-engine/quickstart.md`
- Description: Judge whether functional requirements are stable, testable and mapped to acceptance evidence.
- Estimated Tokens: 1000
- Dependencies: Phase 1
- Steps:
  - Credit FR-001-FR-043 coverage, user stories, edge cases, measurable outcomes and positive/negative fixture requirements.
  - Verify that acceptance criteria do not require live outreach or credentials.
  - Flag that many requirements delegate decisive precision to contracts, increasing review burden and drift risk.
- Acceptance Criteria:
  - Requirements/acceptance score: 9.0/10.
  - Planned tests are not misrepresented as passing tests.
  - All correction recommendations are specification-level.

#### Task 2.3: Assess architecture and data integrity
- Location: `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/contracts/precision.md`, `specs/001-abr-lead-engine/plan.md`
- Description: Judge whether source identity, state transitions, data constraints, queueing and recovery are sufficiently buildable.
- Estimated Tokens: 1300
- Dependencies: Phase 1
- Steps:
  - Credit UUID/content snapshot identity, same-day corrections, atomic promotion, CAS cursor, immutable manifests, staging cleanup and replay boundaries.
  - Credit deterministic ranking, rule gate, composite provenance constraints, current pointer semantics and latest wash semantics.
  - Flag source mapping as still dependent on approved live-source schema evidence and exact fixture files.
- Acceptance Criteria:
  - Architecture/data integrity score: 8.8/10.
  - Blockers include concrete failure examples for incoherent ABR generation, missing source mapping and absent legacy rules.
  - Crash recovery and concurrency are rated as specified, not implemented.

#### Task 2.4: Assess privacy, security and operability
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/quickstart.md`
- Description: Judge readiness of consent, suppression, crawl safety, retention, access control, residency, operations and budget controls.
- Estimated Tokens: 1300
- Dependencies: Phase 1
- Steps:
  - Credit synchronous opt-out, action-time authority, no reusable send token, suppression survival through restore, SSRF/DNS pinning, finite retention and encrypted/HMAC endpoint handling.
  - Credit budget micro-AUD reservations and procurement authority separation.
  - Flag legal/policy review, processor countries, notice strategy and vendor adapters as explicitly gated, not solved.
- Acceptance Criteria:
  - Privacy/security/operability score: 8.7/10.
  - Review does not claim compliance approval.
  - Risks include crawl identity, consent, channel rules, suppression propagation and retention conflicts.

#### Task 2.5: Assess scope, delivery and traceability
- Location: `specs/001-abr-lead-engine/analysis.md`, `specs/001-abr-lead-engine/tasks.md`, `specs/001-abr-lead-engine/workflow-status.md`
- Description: Judge whether build sequence, traceability and documentation delivery are coherent enough for next implementation planning.
- Estimated Tokens: 900
- Dependencies: Phase 1
- Steps:
  - Credit 59 unchecked tasks mapped to all 43 FRs and explicit future implementation boundary.
  - Credit workflow status distinguishing specify/plan/checklist/analyze from implement/converge.
  - Flag nonexistent referenced application paths and external dependencies as easy to misread unless summarized prominently for Obsidian readers.
- Acceptance Criteria:
  - Scope/delivery/traceability score: 8.0/10.
  - Review recommends an Obsidian-facing readiness summary and dependency register.
  - No demand is made for implementation tests to rate the specification.

### Phase 3: Blockers and Corrections
**Goal**: Convert weaknesses into precise documentation improvements.

#### Task 3.1: Add a source-mapping readiness appendix
- Location: `specs/001-abr-lead-engine/contracts/precision.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Strengthen the contract for ABR ZIP/resource grouping, generation evidence and same-day republishes.
- Estimated Tokens: 1000
- Dependencies: Phase 2
- Steps:
  - Add a table of required live-source mapping artifacts: XSD copy, README copy, fixture manifests, accepted generation equality rules and failure modes.
  - Explicitly define how same-day corrected content with incomplete generation evidence is held.
  - Link each named fixture to the task that creates it.
- Acceptance Criteria:
  - Blocker: R3/R6 source coherence. Failure example: two ZIP resources share a date but have different inner `ExtractTime`; current build could not prove they belong together. Smallest correction: require approved `source_mapping.json` fixture evidence before live ABR promotion.
  - Blocker: R2/R3 snapshot identity. Failure example: same calendar date publishes corrected content and overwrites a date-keyed artifact. Smallest correction: preserve UUID plus canonical inventory digest as the only accepted identity in all examples.

#### Task 3.2: Add a missing-dependency register
- Location: `specs/001-abr-lead-engine/research.md`, `specs/001-abr-lead-engine/analysis.md`
- Description: Make unresolved dependencies visible in one table for readers.
- Estimated Tokens: 900
- Dependencies: Phase 2
- Steps:
  - List owner, needed evidence, blocked capability and safe default for each missing dependency.
  - Include legacy rules, live source mapping, DNCR account/receipt format, CRM sandbox mapping, processor countries, legal policy, capacity benchmark and vendor pricing.
  - Mark `deliverables/abr/extract_new_abns.py` as absent evidence, not a broken active app path.
- Acceptance Criteria:
  - Blocker: R9 missing rules. Failure example: production classifier silently uses synthetic rule fixtures as if they were the claimed 30 legacy rules. Smallest correction: add machine-readable `CLASSIFIER_DISABLED` default until recovered or replacement-approved corpus exists.
  - Blocker: G5 vendor hand-off. Failure example: CRM field IDs differ in production and suppression updates hit the wrong custom field. Smallest correction: require sandbox-verified field mapping before enabling CRM drain.

#### Task 3.3: Add an action-time race and suppression propagation note
- Location: `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/quickstart.md`
- Description: Make concurrency, crash recovery and downstream propagation limits easier to test.
- Estimated Tokens: 900
- Dependencies: Phase 2
- Steps:
  - Add explicit examples for suppression-first, consume-first, crash-after-consume-before-provider-result and stale exported row.
  - Clarify local action gate denial is immediate after suppression commit even if Sheets/CRM propagation is delayed.
  - Keep external already-dispatched actions outside claimed atomicity.
- Acceptance Criteria:
  - Blocker: R24/R25 linearisation. Failure example: old CRM row sends after opt-out because it bypasses the control API. Smallest correction: require certification that each sender consumes live action intent immediately before dispatch.
  - Blocker: R7/R33 crash recovery. Failure example: timeout after CRM create leads to duplicate contact on retry. Smallest correction: preserve uncertain state and reconcile by configured identity before retry.

#### Task 3.4: Add consent/channel decision matrix
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`
- Description: Reduce ambiguity around email, phone, notices, relevance and channel-specific rules.
- Estimated Tokens: 1000
- Dependencies: Phase 2
- Steps:
  - Add a table for email candidate, phone candidate, contact form, SMS, social DM and CRM-only handoff.
  - For each channel, state required identity, permission basis, freshness, action-time check and default if unknown.
  - State that no current-law certainty is claimed without qualified review.
- Acceptance Criteria:
  - Blocker: R21/R27 consent freshness. Failure example: 91-day-old inferred consent assessment still appears passable because an export row was not refreshed. Smallest correction: highest-sequence current pointer plus expiry must be checked at export and consume.
  - Blocker: R28 channel rules. Failure example: phone call allowed from postcode-only timezone at a border locality. Smallest correction: unknown or ambiguous timezone blocks until reviewed.

#### Task 3.5: Add cost and capacity admission checklist
- Location: `specs/001-abr-lead-engine/contracts/precision.md`, `specs/001-abr-lead-engine/quickstart.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Make budget accounting and host sizing preconditions operationally unambiguous.
- Estimated Tokens: 800
- Dependencies: Phase 2
- Steps:
  - Add an admission checklist for free disk, spill, WAL, backup, staged artifacts and 25 GiB headroom.
  - Add examples for prepaid credit, subscription commitment and zero remaining budget.
  - Require current tariff/FX/tax evidence before any paid call.
- Acceptance Criteria:
  - Blocker: R19 budget accounting. Failure example: prepaid vendor credits make requests appear free and bypass the A$150 usage cap. Smallest correction: reserve micro-AUD value for prepaid calls and separately record procurement cash.
  - Blocker: R36 capacity. Failure example: DuckDB buffer limit is mistaken for total RSS and 8 GiB host OOMs during output materialisation. Smallest correction: capacity worksheet plus measured benchmark before production runs.

### Phase 4: Final Readiness Report
**Goal**: Produce a concise, understandable assessment for Obsidian and build planning.

#### Task 4.1: Write specification readiness summary
- Location: `specs/001-abr-lead-engine/council-review.md` or Obsidian mirror summary
- Description: Summarize score, major strengths, blockers, corrections and safe defaults.
- Estimated Tokens: 1200
- Dependencies: Phase 3
- Steps:
  - Lead with SPECIFICATION SCORE: 8.6/10 and weighted rubric.
  - State that the document is strong enough for scoped synthetic build planning but not production/legal release.
  - List blockers with section, example and smallest correction.
- Acceptance Criteria:
  - Summary is understandable to non-implementers.
  - No implementation or legal approval is implied.
  - Safe defaults are clear: fixture/offline mode, production gates closed, Part1 does not send, A$150 enrichment cap, 60 rows/week, QLD+northern NSW pilot.

## Testing Strategy
- Validate documentation consistency by checking R1-R43 map to FR-001-FR-043, tasks and acceptance scenarios.
- Validate requirement quality by ensuring every major risk has at least one positive and one negative fixture or review gate.
- Validate evidence discipline by confirming historical counts, timings, SQL claims and source-law assertions are labelled historical, pending or unverified.
- Validate security readiness by tracing a candidate from source evidence through identity, contact provenance, permission, export, action-time check, suppression and restore.
- Validate operability by tracing failure cases: mixed ABR generation, same-day correction, crash before/after promotion, budget exhaustion, stale wash, later negative consent, stale sheet edit, CRM uncertain create and restore from backup.
- Validate scope discipline by confirming no task enables outreach, payments, contact forms, social DMs, Google Places/Maps enrichment or production adapters by default.
- Validation result target: a specification can proceed to scoped fixture implementation when blockers are documented as gates and no unresolved contradiction would force rework in foundation architecture.

## Risks
- R3/R6 source generation risk: ABR publisher metadata may be insufficient to prove all parts belong to one coherent generation. Mitigation: live promotion must require approved source mapping and hold with `GENERATION_UNPROVABLE` when evidence is inadequate.
- R9 rule-corpus risk: the claimed 30 legacy trade rules and `deliverables/abr/extract_new_abns.py` are absent. Mitigation: production classification remains disabled until the corpus is recovered or a replacement is explicitly approved with fixtures.
- R21/R24 consent freshness risk: old positive evidence could be misread by implementers as reusable permission. Mitigation: require highest-sequence current pointer, expiry checks and exact campaign/template/content relevance at consume time.
- R17 crawl safety risk: SSRF controls are well specified but easy to weaken through default HTTP client behavior, redirects, proxies or DNS rebinding. Mitigation: add transport-level contract tests proving blocked destinations never reach sockets.
- R25 suppression propagation risk: local suppression is immediate, but Sheets/CRM/third-party tools can lag or bypass the authority. Mitigation: state cross-system coverage is unclaimed until each external system integrates and certifies the live gate.
- R29 retention conflict risk: current and previous full snapshots must fit a 90-day absolute limit, which may force rebaseline if source publication stalls. Mitigation: make history-gap behavior prominent in operator documentation and reports.
- R19 cost risk: enrichment cap excludes subscriptions and procurement cash unless readers understand the separate authority model. Mitigation: add a dated cost register and explicit A$0 automatic procurement cap.
- R36 capacity risk: 20.5M-row figures and 8 GiB host sizing remain hypotheses. Mitigation: require admission worksheet and output-bearing benchmark before production.
- Self-critique: This plan scores the package from embedded documents only and cannot detect omissions in the actual checkout, broken links, or drift between canonical and mirror files because the constraints forbid tools.
- Self-critique: The 8.6 score gives significant credit for very detailed contracts, but that detail also creates implementation ambiguity if developers do not read `precision.md`; the plan should probably require a single build-readiness index page before handoff.
- Self-critique: The plan treats legal/vendor gaps as gated dependencies rather than specification defects where the spec names the gate clearly; if the user expected procurement-ready planning, the scope/delivery score may be too generous.

## Rollback Plan
- If a readiness summary or review document is added, rollback by deleting only that new review artifact and leaving canonical v4.0 source documents unchanged.
- If wording changes are made to canonical documentation, rollback by reverting the specific documentation patch and preserving the v3.5 backup and v4.0 archive references.
- If a correction introduces contradiction, restore the previous text for the affected section and add a decision-register entry explaining why the correction was withdrawn.
- If a score is challenged, keep the blocker list intact and recalculate only the rubric table against the same frozen source corpus.
- No application state, database, credentials, source downloads or vendor accounts are affected because this is documentation planning only.

## Edge Cases
- Same-day ABR corrected content with the same visible publication date but different member content.
- ABR resource inventory changes during download.
- ABR parts with missing, null or conflicting generation evidence.
- Identical-content republish producing zero business events.
- Repartitioned files producing a new artifact identity but no semantic business events.
- Missing ABN in QBCC records and invalid ABN on an otherwise useful licence.
- Matching business names across unrelated entities.
- Shared endpoints across distinct businesses.
- Later negative or withdrawn permission assessment after an older pass.
- Later listed/error DNCR wash after an older clear wash.
- Opt-out during export, CRM retry or action-intent consumption.
- Restore from backup predating a suppression or deletion.
- Prepaid vendor balance with no marginal invoice but still consuming the A$150 usage cap.
- Calendar-month rollover in Australia/Brisbane with pending or uncertain charges.
- Unknown recipient timezone or postcode border ambiguity.
- Vendor processor country, terms or signup cost unknown at release.
- Legal hold conflicting with default retention expiry.
- Human operator manually contacting from a copied sheet outside the live control boundary.

## Open Questions
- None for this planning task; all unresolved items are treated as dependencies, gates or blockers rather than questions to the user.