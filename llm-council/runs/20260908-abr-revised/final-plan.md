# Plan

## Overview
Independently assess the supplied ABR Lead Engine v4.0 specification as a documentation/build-planning artifact and improve it toward build readiness. SPECIFICATION SCORE: 8.5/10 using the weighted rubric above; this does not certify legal compliance, production readiness, source freshness, benchmark performance, or vendor procurement.

## Scope
- In: Score the supplied specification and embedded Spec Kit artifacts.
- In: Identify blockers with exact section/requirement, failure example, and smallest correction.
- In: Resolve documentation contradictions, checklist drift, missing references, and traceability gaps.
- In: Preserve safe build defaults: synthetic/offline mode, fail-closed gates, no outreach, no fabricated rules.
- Out: App implementation, repository execution, network verification, benchmark claims, legal advice, vendor signup, production approval, or live outreach.
- Out: Treating historical verified assertions as current evidence unless reproduced in the supplied material.

## Phases
### Phase 1: Independent Readiness Score
**Goal**: Record a defensible score for the actual supplied v4.0 documents only.

#### Task 1.1: Apply weighted rubric
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `plan.md`, `data-model.md`, `contracts/interfaces.md`, `tasks.md`, `quickstart.md`, `research.md`
- Description: Score the supplied specification set using the required five-dimension rubric.
- Estimated Tokens: 900
- Dependencies: None
- Steps:
  - Score correctness/evidence, requirements/acceptance, architecture/data integrity, privacy/security/operability, and scope/delivery/traceability.
  - State the weighted arithmetic and final specification score.
  - Separate specification readiness from production certification and legal approval.
- Acceptance Criteria:
  - Weighted score is arithmetically consistent.
  - Score is independent from Plan 1, Plan 2, and any historical Council score.
  - No hypothetical improvement increases the score.

#### Task 1.2: Explain score rationale
- Location: `specs/001-abr-lead-engine/analysis.md`, Obsidian mirror if maintained
- Description: Add a concise owner-readable explanation of why the spec is strong but not 9+.
- Estimated Tokens: 800
- Dependencies: Task 1.1
- Steps:
  - Credit strong controls: content identity, coherent snapshots, suppression authority, crawl bounds, tri-state consent, manual DNCR pilot, retention, budget reservations, and unchecked implementation tasks.
  - Penalize defects: checklist drift, missing legacy rules, risky gate wording, unresolved local references, and incomplete traceability matrix.
- Acceptance Criteria:
  - Non-engineers can understand what is ready and what remains blocked.
  - The note does not imply live approval or legal clearance.

### Phase 2: Resolve Documentation Defects
**Goal**: Remove contradictions that reduce specification readiness.

#### Task 2.1: Fix checklist drift
- Location: `specs/001-abr-lead-engine/checklists/security-and-readiness.md`
- Description: Reassess CHK006, CHK007, CHK008, CHK010, CHK018, and CHK019 against the supplied canonical spec, data model, contracts, quickstart, and tasks.
- Estimated Tokens: 1400
- Dependencies: Task 1.1
- Steps:
  - For each unchecked item, either check it with exact evidence or leave it unchecked with a concrete missing contract.
  - Label checklist results as writing/readiness checks only, not implementation proof.
- Acceptance Criteria:
  - CHK006 cites exact contact/channel provenance constraints or names the missing constraint.
  - CHK007 cites tri-state inferred/express basis and latest-sequence override.
  - CHK008 cites restricted export labels and action-time intent consumption.
  - CHK010 cites durable suppression, alias propagation, restore replay, and retention carve-outs.
  - CHK018 cites pilot time/cost denominators and owner expansion decision.
  - CHK019 cites an FR/R-to-task-to-acceptance mapping or lists exact gaps.

#### Task 2.2: Repair references and absent dependencies
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/research.md`, `workflow-status.md`
- Description: Make every referenced local artifact either resolvable or explicitly labelled absent.
- Estimated Tokens: 900
- Dependencies: Task 1.1
- Steps:
  - Mark `deliverables/abr/extract_new_abns.py` and the intended 30-rule corpus as absent production-classifier dependencies.
  - Check relative links for canonical spec, source checks, Spec Kit files, and skill references.
  - Replace fragile links or add repository-relative alternatives.
- Acceptance Criteria:
  - No missing file is presented as available evidence.
  - Synthetic build planning remains allowed.
  - Production classification remains disabled until recovered or approved replacement rules exist.

#### Task 2.3: Normalize gate wording
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `workflow-status.md`
- Description: Remove ambiguity from release-gate status language.
- Estimated Tokens: 500
- Dependencies: Task 1.1
- Steps:
  - Replace `OPEN/PENDING` with `pending/unapproved; live capability disabled`.
  - Reiterate that document quality does not approve collection, contact, procurement, or deployment.
- Acceptance Criteria:
  - No gate wording can be read as authorising production mode.
  - Fixture/synthetic development remains explicitly permitted.

### Phase 3: Tighten Design Contracts
**Goal**: Make the specification harder to misimplement without requiring implementation evidence.

#### Task 3.1: Strengthen source identity examples
- Location: `specs/abr-lead-engine.md`, `data-model.md`, `quickstart.md`
- Description: Add explicit acceptance examples for snapshot identity and ABR generation coherence.
- Estimated Tokens: 900
- Dependencies: Task 2.1
- Steps:
  - Add examples for same date with different digest, same digest with new metadata, and mixed inner transfer metadata.
  - State that dates are descriptive metadata, never primary keys.
- Acceptance Criteria:
  - Same-day correction coexists with predecessor.
  - Identical-content republish is a no-op.
  - Mixed-generation ZIP set holds and cannot advance the cursor.

#### Task 3.2: Add recovery boundary table
- Location: `plan.md`, `contracts/interfaces.md`, `tasks.md`
- Description: Summarize transaction boundaries for promotion, billing, CRM, suppression/action consumption, and restore.
- Estimated Tokens: 1100
- Dependencies: Task 2.1
- Steps:
  - For each boundary, define before-commit crash, after-commit crash, replay key, and forbidden duplicate effect.
  - Include provider timeout handling and uncertain billing/create reconciliation.
- Acceptance Criteria:
  - Crash before commit exposes no partial promotion.
  - Crash after commit resumes from durable outbox/state.
  - Provider uncertainty cannot cause duplicate CRM creates or unaccounted spend.

#### Task 3.3: Clarify consent, channel, crawl, and suppression defaults
- Location: `specs/abr-lead-engine.md`, `data-model.md`, `contracts/interfaces.md`, `quickstart.md`
- Description: Add concrete fail-closed examples for privacy, crawl safety, and suppression freshness.
- Estimated Tokens: 1000
- Dependencies: Task 2.1
- Steps:
  - Add examples: public email without reviewed basis blocks; deliverable email without relevance blocks; clear DNCR wash is not call permission; phone wash does not imply email permission.
  - Define crawler user-agent/contact configuration before live crawl and confirm incomplete terms crawl means unknown.
  - State external Sheets/CRM projections are never authority and restore must replay suppression/erasure before egress.
- Acceptance Criteria:
  - Email and phone gates remain distinct.
  - Latest fail/unknown/withdrawn overrides older pass.
  - Suppression cannot be erased by retention, backup restore, projection lag, or alias merge.

### Phase 4: Traceability and Handoff
**Goal**: Make the specification auditable and easy to build from.

#### Task 4.1: Add requirements-to-acceptance matrix
- Location: `specs/001-abr-lead-engine/tasks.md`, `analysis.md`
- Description: Add a compact matrix linking FR-001 through FR-043 to canonical Rn, tasks, acceptance scenario, and release gate.
- Estimated Tokens: 1600
- Dependencies: Task 2.1
- Steps:
  - Map every FR/R to at least one task and one acceptance or evidence reference.
  - Mark document checks separately from implementation test evidence.
- Acceptance Criteria:
  - FR-001 through FR-043 each has a visible task and acceptance reference.
  - No task checkbox is marked complete without command/revision/environment/artifact evidence.
  - Production-only dependencies are gates, not failed spec checks.

#### Task 4.2: Publish concise judge note
- Location: `MaintainMedia/Specs/ABR Lead Engine.md`, `specs/001-abr-lead-engine/analysis.md`
- Description: Create an Obsidian-ready summary of score, blockers, and exact next documentation corrections.
- Estimated Tokens: 900
- Dependencies: Tasks 2.1-4.1
- Steps:
  - Include score and weighted rubric.
  - List blockers in the required format: section/requirement, failure example, smallest correction.
  - State safe build defaults and unresolved dependencies.
- Acceptance Criteria:
  - Owner can see what remains unresolved.
  - Developer can start scoped implementation planning without confusing gates for approval.
  - 9+ is reserved for corrected checklist/reference/traceability state, not implementation proof.

## Testing Strategy
- Manually verify weighted-score arithmetic.
- Trace every required challenge topic to a requirement, contract, task, or explicit unresolved blocker.
- Confirm blockers include exact section/requirement, failure example, and smallest correction.
- Validate all local references or label them absent.
- Check FR-001 through FR-043 against task IDs and acceptance scenarios.
- Confirm document-quality checks, implementation evidence, release gates, production certification, procurement, and legal approval remain separate.

## Risks
- Checklist drift may hide real missing contracts; mitigation: resolve each unchecked item with exact evidence or keep it open with a precise defect.
- Missing legacy extractor/rule corpus may be misread as blocking all work; mitigation: state it blocks production classification only, while synthetic build planning remains valid.
- Gate wording may imply live capability; mitigation: use fail-closed `pending/unapproved; live capability disabled` language.
- Source prices, laws, licences, vendor terms, and processor countries may change; mitigation: require release-time reconfirmation and avoid current-law certainty.
- Strong requirements may look like completed software; mitigation: keep all tasks unchecked until executed evidence exists.
- Capacity targets may be mistaken for benchmarks; mitigation: label A4vCPU/8GiB and 20.5M-row diff as candidate/target until measured.

## Rollback Plan
- Revert only edited review/checklist/analysis/link text if a correction is wrong.
- Preserve v4.0 and v3.5 backup as comparison/archive sources.
- If a checklist item is over-marked, restore unchecked state and add the exact missing evidence.
- If any wording implies implementation, legal approval, or production capability, replace it with a gate/dependency statement.
- Do not delete historical claims; relabel them historical/unverified unless reproduced evidence is attached.

## Edge Cases
- Same-date ABR content with different digest creates a distinct snapshot.
- Identical content with new metadata is a no-op with manifest evidence.
- Mixed ZIP generations hold, alarm, and do not promote.
- Baseline import emits zero ABR lead events.
- Missing QBCC ABN remains discovery evidence but cannot force ABN identity.
- Later DNCR listed/error overrides older clear.
- Public email without reviewed basis blocks.
- Deliverable email without current relevance blocks.
- Unknown identity, geography, permission, source coherence, policy gate, source terms, or action service status blocks.
- Suppression survives alias merge, future endpoint discovery, CRM lag, retention, and backup restore.
- Budget rollover keeps uncertain request charged to reservation month.
- External send already underway after consumed action intent is audited, not falsely recalled.
- Retention expiry may require rebaseline and documented history gap.

## Open Questions
- None. Unresolved items are documented blockers or release-gated dependencies, not questions for this planning pass.