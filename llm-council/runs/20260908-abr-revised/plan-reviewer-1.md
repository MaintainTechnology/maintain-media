# Plan

## Overview
Independently assess ABR Lead Engine specification v4.0 as a documentation/build-planning artifact, not as production certification or legal approval. SPECIFICATION SCORE: 8.4/10 using weighted rubric: correctness/evidence 8.5/10 x25% = 2.13; requirements/acceptance 8.7/10 x20% = 1.74; architecture/data integrity 8.8/10 x20% = 1.76; privacy/security/operability 8.3/10 x20% = 1.66; scope/delivery/traceability 7.5/10 x15% = 1.13; weighted total = 8.42.

## Scope
- In: Assess supplied canonical specification and embedded Spec Kit artifacts.
- In: Identify blockers, documentation defects, unresolved dependencies, safe build defaults, and precise improvements.
- In: Separate specification readiness from production certification, legal approval, vendor procurement, and implementation evidence.
- In: Produce an implementation-planning review suitable for Obsidian documentation and owner/developer handoff.
- Out: App implementation, repository edits, code execution, delegated agents, network verification, benchmark claims, or legal conclusions.
- Out: Treating historical VERIFIED assertions, benchmark timings, counts, prices, or SQL execution as verified unless reproduced in the supplied evidence.

## Phases
### Phase 1: Score The Supplied Specification
**Goal**: Produce a defensible readiness score for the actual supplied v4.0 documents.

#### Task 1.1: Apply Weighted Rubric
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `plan.md`, `data-model.md`, `contracts/interfaces.md`, `tasks.md`, `quickstart.md`, `research.md`
- Description: Score only the supplied document set against the required five-dimension rubric.
- Estimated Tokens: 1200
- Dependencies: None
- Steps:
  - Rate correctness/evidence, requirements/acceptance, architecture/data integrity, privacy/security/operability, and scope/delivery/traceability from 0-10.
  - Compute weighted total and state it explicitly in the Overview.
  - Keep production readiness and legal approval separate from specification quality.
- Acceptance Criteria:
  - Weighted rubric is visible and arithmetically consistent.
  - Final score is independent from any prior planner or council report scores.
  - Score does not reward hypothetical future improvements.

#### Task 1.2: Justify Score
- Location: Same document set
- Description: Explain why v4.0 earns a high but not 9+ score.
- Estimated Tokens: 1000
- Dependencies: Task 1.1
- Steps:
  - Credit explicit improvements: corrected proxy claims, no production claim, durable suppression, snapshot UUID/content identity, bounded crawl, tri-state consent, DNCR manual pilot, finite retention, and unchecked implementation tasks.
  - Penalize remaining defects: incomplete checked readiness checklist, referenced nonexistent files, unresolved rule corpus, external evidence gaps, and possible cross-document drift.
- Acceptance Criteria:
  - Strengths and penalties are tied to exact sections or requirements.
  - No invented benchmark, source, vendor, or legal certainty is introduced.

### Phase 2: Identify Blockers And Defects
**Goal**: Convert review findings into actionable corrections with exact requirement references.

#### Task 2.1: Blocker Table
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/checklists/security-and-readiness.md`
- Description: List readiness blockers with exact section/requirement, concrete failure example, and smallest correction.
- Estimated Tokens: 1800
- Dependencies: Phase 1
- Steps:
  - Mark `CHK006`, `CHK007`, `CHK008`, `CHK010`, `CHK018`, and `CHK019` as unresolved checklist evidence, even where the canonical spec appears stronger.
  - Identify `deliverables/abr/extract_new_abns.py` and intended 30 trade rules as absent dependencies blocking production classification under R9/G2/T041.
  - Flag source-check evidence that must be reverified at release: DNCR costs, ABR cadence, source licences, vendor terms, processor countries, and legal policy.
- Acceptance Criteria:
  - Each blocker has a smallest correction, not a vague recommendation.
  - Documentation defects are separated from gated future implementation/procurement evidence.

#### Task 2.2: Challenge Required Risk Areas
- Location: R2-R8, R14, R16-R30, R33-R38, R40-R43
- Description: Check all required challenge areas from the brief.
- Estimated Tokens: 1600
- Dependencies: Task 2.1
- Steps:
  - Confirm the spec addresses snapshot UUIDs/date keys, same-day republishes, ZIP generations, concurrency, crash recovery, deterministic rules, SSRF, suppression freshness, retention, consent, channel rules, budget accounting, and capacity claims.
  - Record remaining weaknesses where cross-artifact proof is incomplete or checklist evidence is unchecked.
- Acceptance Criteria:
  - Every challenge topic is explicitly covered.
  - Findings distinguish “specified well” from “specified but not yet evidenced” and “still unclear.”

### Phase 3: Propose Precise Improvements
**Goal**: Raise the specification toward 9+ readiness without pretending implementation has occurred.

#### Task 3.1: Fix Checklist Drift
- Location: `specs/001-abr-lead-engine/checklists/security-and-readiness.md`
- Description: Align checked items with the stronger canonical requirements or add exact follow-up requirements where still incomplete.
- Estimated Tokens: 1200
- Dependencies: Phase 2
- Steps:
  - For CHK006, cite R20/data-model/contact provenance composite constraints or add missing evidence text.
  - For CHK007, cite R21/contracts basis assessments or add explicit reviewer scenario references.
  - For CHK008, cite R22/R24/action-intents or add negative stale-token acceptance examples.
  - For CHK010, cite R25/R29/restore or add alias/future-endpoint restore scenario references.
  - For CHK018, cite R38/operator activity/cost tasks or add pilot denominator acceptance examples.
  - For CHK019, cite T001-T059 plus requirements manifest T057 or add an FR-to-task matrix.
- Acceptance Criteria:
  - Checklist no longer contradicts the canonical spec.
  - Checked status never implies software passed.

#### Task 3.2: Add Missing Evidence Register
- Location: `specs/001-abr-lead-engine/research.md`, `abr_engine/ops/release-gates.md` planned path
- Description: Create or expand a single unresolved-dependencies register.
- Estimated Tokens: 1000
- Dependencies: Task 3.1
- Steps:
  - Record missing legacy extractor/rules corpus, source fixtures, source licence reconfirmation, DNCR signup terms, provider pricing, AU residency commitments, VA/vendor countries, CRM field mapping, capacity benchmark, and legal policy approvals.
  - Assign each dependency to a gate and safe default.
- Acceptance Criteria:
  - Every unresolved external fact has owner, required evidence, gate, and fail-closed behavior.
  - Historical verified claims remain labelled historical/unverified.

#### Task 3.3: Tighten Acceptance Traceability
- Location: `specs/001-abr-lead-engine/tasks.md`, `quickstart.md`, `spec.md`
- Description: Make acceptance coverage mechanically auditable.
- Estimated Tokens: 1100
- Dependencies: Task 3.2
- Steps:
  - Add a compact FR-to-scenario-to-task matrix.
  - Ensure positive allowed fixtures exist alongside blocked fixtures for permission/export gates.
  - Add explicit scenario names for same-day corrected publication, mixed ZIP generation, latest DNCR listed overriding clear, budget month rollover, suppression restore, and action-time race.
- Acceptance Criteria:
  - Each FR001-FR043 maps to at least one task and acceptance scenario.
  - Requirements-quality checks are visibly separate from implementation test evidence.

### Phase 4: Deliver Review Output
**Goal**: Produce owner-readable documentation that explains score, blockers, and next steps.

#### Task 4.1: Obsidian-Ready Judge Note
- Location: `MaintainMedia/Specs/ABR Lead Engine.md` mirror, `specs/001-abr-lead-engine/analysis.md` if maintained
- Description: Draft a concise judge note summarizing independent score and improvements.
- Estimated Tokens: 1400
- Dependencies: Phase 3
- Steps:
  - State score and weighted rubric.
  - Summarize blockers and smallest corrections.
  - Clarify that a 9+ specification-quality score would still not certify production or legal readiness.
- Acceptance Criteria:
  - Non-technical reader can understand why the spec is close to buildable.
  - Developer can identify the next exact documentation corrections.

## Testing Strategy
- Validate arithmetic of the weighted rubric manually.
- Trace each required challenge topic to at least one requirement or artifact.
- Check that no finding relies on unprovided repo state, network lookup, or historical “verified” claims.
- Confirm blockers include exact section/requirement, concrete failure example, and smallest correction.
- Confirm final output distinguishes documentation defects, gated implementation evidence, procurement evidence, production certification, and legal approval.
- Confirm no implementation tests are demanded merely to rate the specification, while unresolved design contracts reduce the score.

## Risks
- The security checklist marks several items unchecked even though the canonical spec and contracts appear to cover them; mitigation: treat this as traceability/checklist drift until exact evidence text is added.
- The referenced `deliverables/abr/extract_new_abns.py` and intended 30-rule corpus do not exist in the supplied current checkout notes; mitigation: production classification must remain disabled until recovered or replaced with approved provenance and fixtures.
- Source/material dates and URLs are supplied, not live-verified in this review; mitigation: keep them as attached evidence only and require release-time reconfirmation under R40/G1-G5.
- Capacity claims remain target-level only; mitigation: preserve A4vCPU/8GiB as candidate hardware and require benchmark artifact before production release.
- Legal and consent rules are intentionally gated; mitigation: do not treat R21/R27 wording or this score as legal approval.
- Same-day publication corrections and coherent ZIP generations are specified strongly, but implementation tasks must still prove they cannot collide by date-only keys.
- Budget controls are well specified, but actual provider tariffs, prepaid minimums, FX, retry billing, and subscription treatment remain procurement dependencies.
- Self-critique: This plan cannot verify whether the repository actually contains all listed files because the task forbids tools; it relies on the embedded source and checkout notes.
- Self-critique: The 8.4 score may be slightly generous if the unchecked security/readiness checklist reflects real missing contract text rather than stale checklist state; a stricter interpretation could justify roughly 7.8-8.1.
- Self-critique: The plan emphasizes specification completeness and may underweight usability of the final Obsidian explanation unless a separate plain-English summary is explicitly added.

## Rollback Plan
- If documentation corrections overreach, revert only the edited review/checklist/analysis notes to the prior v4.0 text.
- Preserve canonical v4.0 and v3.5 backup as immutable comparison points.
- If a checklist item is incorrectly marked complete, restore it to unchecked and add a precise missing-evidence note.
- If a proposed requirement accidentally implies implementation or legal approval, replace it with a gate/dependency statement.
- If recovered rule corpus or source evidence later contradicts the plan, update the dependency register and lower the readiness score rather than silently carrying the old assessment forward.

## Edge Cases
- Same date with different ABR content digest must create a distinct snapshot, not overwrite.
- Identical-content republication is a no-op even if observed later.
- Mixed ZIP parts or matching date but inconsistent inner metadata must hold, alarm, and avoid promotion.
- Baseline import emits zero ABR events.
- Missing ABN in QBCC remains valid discovery evidence but cannot force ABN-based identity.
- Later DNCR listed/error receipt overrides older clear receipt.
- Unknown identity, geography, permission, source coherence, policy gate, or action-time service status blocks.
- Suppression must survive alias merge, CRM projection lag, backup restore, and future endpoint discovery.
- Budget reservation spanning month boundary remains charged to reservation month.
- External sender already underway after consumed action intent may not be recallable; audit timing instead of claiming atomic external cancellation.
- Retention may limit historical replay after snapshot expiry; document history gaps and rebaseline.
- Public source/license/vendor terms may change before release and must be rechecked.

## Open Questions
- None for this planning response; unresolved items are treated as gated dependencies rather than questions.