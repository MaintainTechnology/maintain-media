# Plan

## Overview
Assess the supplied ABR Lead Engine v4.0 documentation package as a specification, not as implemented software. SPECIFICATION SCORE: 8.6/10 using weighted rubric: correctness/evidence 8.5/10 at 25%, requirements/acceptance 9.0/10 at 20%, architecture/data integrity 9.0/10 at 20%, privacy/security/operability 8.5/10 at 20%, scope/delivery/traceability 8.0/10 at 15%, weighted total 8.6/10.

## Scope
- In: Independently judge the actual supplied specification package.
- In: Identify blockers, documentation defects, unresolved dependencies, risks, tests, and rollback steps.
- In: Propose precise documentation/build-planning improvements for Obsidian/spec artifacts.
- Out: Application implementation under `abr_engine/`.
- Out: Legal approval, production certification, live source testing, vendor procurement, or outreach.
- Out: Treating historical VERIFIED assertions as current evidence unless reproduced in the supplied material.

## Phases
### Phase 1: Specification Readiness Judgment
**Goal**: Produce an evidence-grounded score and readiness finding for the supplied documents.

#### Task 1.1: Score the Actual Specification
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `specs/001-abr-lead-engine/analysis.md`
- Description: Judge only the attached v4.0 package and separate document quality from production readiness.
- Estimated Tokens: 1600
- Dependencies: None
- Steps:
  - Apply the weighted rubric exactly.
  - Credit explicit corrections already present, including proxy-signal limits, same-day snapshot identity, live action checks, suppression, finite retention, and pending gates.
  - Penalise unresolved design contracts, missing source evidence, and documents that refer to future paths as deliverables rather than evidence.
- Acceptance Criteria:
  - Final score states each rubric dimension and weighted total.
  - Score does not assume hypothetical fixes.
  - Final readiness conclusion distinguishes specification readiness from production/legal approval.

#### Task 1.2: Record Blockers With Minimal Corrections
- Location: `specs/001-abr-lead-engine/research.md`, `specs/001-abr-lead-engine/contracts/precision.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Identify blockers that affect build readiness or release gates.
- Estimated Tokens: 1800
- Dependencies: Task 1.1
- Steps:
  - List exact section or requirement.
  - Provide one concrete failure example per blocker.
  - State the smallest correction needed.
- Acceptance Criteria:
  - Each blocker has section/requirement, failure example, and smallest correction.
  - Documentation defects are separated from explicitly gated future implementation/procurement evidence.

### Phase 2: Precision Improvements
**Goal**: Convert remaining ambiguity into deterministic build contracts without implementing the app.

#### Task 2.1: Tighten ABR Publication Coherence Contract
- Location: `specs/001-abr-lead-engine/contracts/precision.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Clarify inconsistent snapshot IDs/date keys, same-day republishes, and matching ZIP generations.
- Estimated Tokens: 1200
- Dependencies: Task 1.2
- Steps:
  - Add a compact matrix for `same effective date + changed content`, `same content + changed compression`, `changed partitioning + same semantic rows`, `missing generation evidence`, and `mixed generation`.
  - Tie each row to expected promotion result and event result.
  - Ensure T035-T039 require fixture names and expected manifests.
- Acceptance Criteria:
  - No date-only identity remains.
  - Same-day content correction and identical republish behavior are unambiguous.
  - Missing generation evidence holds rather than promotes.

#### Task 2.2: Tighten Concurrency, Crash, and Budget Contracts
- Location: `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Make lock order, recovery, action linearisation, and budget accounting fully testable.
- Estimated Tokens: 1300
- Dependencies: Task 1.2
- Steps:
  - Add canonical lock ordering for source cursor, lead group, endpoint, budget month, and outbox operations.
  - Add crash-point table for before upload, after upload before DB commit, after DB commit before output, and during CRM uncertain create.
  - Add budget examples for retries, timeout with unknown charge, FX expiry, prepaid balance, and month rollover.
- Acceptance Criteria:
  - Tests can deterministically prove no duplicated events, no lost suppression, and no over-cap spend.
  - Recovery behavior is defined for every durable side-effect boundary.

#### Task 2.3: Tighten Crawl Identity and SSRF Controls
- Location: `specs/001-abr-lead-engine/contracts/precision.md`, `specs/001-abr-lead-engine/quickstart.md`
- Description: Ensure crawl identity and network safety cannot be weakened during implementation.
- Estimated Tokens: 1000
- Dependencies: Task 1.2
- Steps:
  - Add explicit fixture outcomes for mixed public/private DNS answers, DNS rebinding, redirect to metadata IP, TLS peer mismatch, robots wildcard block, and incomplete terms crawl.
  - State that unsafe destinations must be blocked before socket connection.
  - Keep JavaScript-only sites manual-review only.
- Acceptance Criteria:
  - SSRF tests fail if any blocked destination reaches the transport.
  - Identity cannot pass from SERP rank, similar names, or directory absence.

#### Task 2.4: Tighten Suppression Freshness and Propagation
- Location: `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/data-model.md`
- Description: Clarify latest suppression, wash, permission, and projection rules.
- Estimated Tokens: 1100
- Dependencies: Task 1.2
- Steps:
  - Add examples where old permission pass is superseded by new unknown, fail, withdrawal, expired basis, or later DNCR listed result.
  - Clarify that external propagation failure does not reopen local action authority.
  - Define projection-delay alarms and reconciliation receipts.
- Acceptance Criteria:
  - Latest blocking evidence always defeats older passing evidence.
  - Opt-outs survive merge, restore, key rotation, and future endpoint discovery.

### Phase 3: Obsidian Explanation and Traceability
**Goal**: Make the package understandable to a human reviewer without weakening the formal requirements.

#### Task 3.1: Add Plain-English Readiness Note
- Location: `MaintainMedia/Specs/ABR Lead Engine.md`, `specs/001-abr-lead-engine/analysis.md`
- Description: Add a short Obsidian-friendly explanation of what is ready, what is blocked, and what safe build defaults mean.
- Estimated Tokens: 900
- Dependencies: Phase 2
- Steps:
  - State that Part 1 prepares records and controls only; it does not send.
  - State that QLD+northern NSW, A$150/month, 60 rows/week, and manual DNCR wash are defaults.
  - State that `abr_engine/` paths are future deliverables and `deliverables/abr/extract_new_abns.py` is absent.
- Acceptance Criteria:
  - Non-technical readers can identify allowed build work versus blocked production work.
  - No claim of implementation, legal approval, or benchmark success is introduced.

#### Task 3.2: Add Release-Gate Dependency Index
- Location: `specs/001-abr-lead-engine/analysis.md`, `specs/001-abr-lead-engine/research.md`
- Description: Summarise unresolved dependencies without treating them as specification failures.
- Estimated Tokens: 900
- Dependencies: Task 3.1
- Steps:
  - Map missing rule corpus to G2.
  - Map legal/source policy and consent review to G1.
  - Map actual vendors, countries, accounts, and CRM sandbox evidence to G5.
  - Map capacity benchmark and restore drills to G3/G7.
- Acceptance Criteria:
  - Each dependency has owner, required evidence, and safe work while pending.
  - Production certification remains separate from specification quality.

## Testing Strategy
- Review the rubric math: weighted total = 8.5×0.25 + 9.0×0.20 + 9.0×0.20 + 8.5×0.20 + 8.0×0.15 = 8.625, rounded to 8.6/10.
- Validate requirement coverage: confirm R1-R43 map to FR-001-FR-043 and tasks T001-T059.
- Validate consistency claims against supplied documents only: `analysis.md`, checklists, contracts, data model, plan, quickstart, research, workflow status.
- Validate that planned application paths are described as future deliverables, not broken links.
- Validate that document-only coverage/link reports are treated as documentation evidence, not app-test evidence.
- Validate that no production gate is marked passed from specification scoring.

## Risks
- Blocker: R9 / `research.md` evidence inventory says `deliverables/abr/extract_new_abns.py` and intended 30 trade rules are missing. Failure example: production ABR classification silently uses synthetic rules and creates misleading Tier B leads. Smallest correction: keep `CLASSIFIER_DISABLED` for production until recovered rules are hashed or replacement rules are owner-approved with fixtures.
- Blocker: R3 / `contracts/precision.md` admits ABR source metadata may not prove generation grouping. Failure example: two ZIP parts from different same-date corrections are paired and false `abn_new` events are emitted. Smallest correction: require approved `source_mapping.json` plus fixture evidence; otherwise hold with `GENERATION_UNPROVABLE`.
- Blocker: R24/R25 action authority depends on future external sender integration. Failure example: a CRM user sends from an old exported row after opt-out because the sender never calls `/action-intents/{id}/consume`. Smallest correction: keep static contact actions disabled until the downstream workflow is certified against the live gate.
- Blocker: R27/G1 legal and collection policy approval is pending. Failure example: crawler stores public website contact evidence before approved notice, harvesting, retention, and channel policy decisions. Smallest correction: fixture-only collection until G1 evidence is recorded.
- Risk: Capacity remains a candidate design, not evidence. Mitigation: require T055 benchmark and admission worksheet before production ABR ingestion.
- Risk: Vendor pricing and country/subprocessor data are not current approvals. Mitigation: require dated procurement records and processor disclosures before enabling adapters.
- Risk: Retention schedule may conflict with later qualified legal advice. Mitigation: keep it as maximum design defaults pending approval and version any legal-hold or retention change.
- Self-critique: This plan scores a very large supplied package from embedded text only; without filesystem validation it may miss drift between embedded documents and actual checkout files.
- Self-critique: The 8.6 score relies on accepting internal coverage tables as documentation evidence; if task files or checklists contain stale or auto-generated mappings not manually verified, traceability should be scored lower.

## Rollback Plan
- For documentation changes: revert only the specific edited spec/Obsidian sections using version control or saved document history.
- For score changes: keep prior score as an archived review entry with date, reviewer, rubric, and source hash.
- For contract tightening: if a new clarification conflicts with canonical R1-R43, roll back the clarification and update the canonical requirement first.
- For release-gate notes: if an approval is later superseded, append a new decision record rather than rewriting historical approvals.
- For Obsidian mirror updates: regenerate from canonical spec and verify source hash before treating the mirror as current.

## Edge Cases
- Same date, changed content: new snapshot UUID, normal comparison, not overwritten by date key.
- Same content, new retrieval metadata: no-op content identity, but manifest may record observation.
- Changed ZIP partitioning with identical semantic records: no business events.
- Missing or null generation evidence: cannot satisfy coherence by null equality.
- ABN disappearance: quarantine quality anomaly, not automatic cancellation.
- Newer DNCR listed/error after older clear: latest result blocks.
- Old permission pass followed by fail/unknown/withdrawn: latest sequence blocks.
- Suppression during CRM export or action consume: local authority blocks if suppression commits first; consumed external in-flight action is logged without false recall.
- Budget timeout with unknown provider billing: reservation remains until reconciliation.
- Backup restored before opt-out: restore stays quarantined until latest suppression/erasure ledger is replayed.
- Unknown geography, timezone, identity, source coherence, consent, processor country, or vendor terms: block live action.
- Planned paths under `abr_engine/`: future deliverables, not evidence of existing implementation.
- Historical verified SQL, counts, timings, or prices: unverified unless reproduced in attached evidence.

## Open Questions
- None. Per instruction, no questions are asked; unresolved items are recorded as gated dependencies rather than clarification requests.