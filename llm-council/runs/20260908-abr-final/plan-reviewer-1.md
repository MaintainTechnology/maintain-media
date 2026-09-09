# Plan

## Overview
Assess the supplied ABR Lead Engine v4.0 documentation package for specification readiness, not production readiness or legal approval. SPECIFICATION SCORE: 8.3/10 using weighted rubric: correctness/evidence 8.5/10 at 25%, requirements/acceptance 8.8/10 at 20%, architecture/data integrity 8.4/10 at 20%, privacy/security/operability 8.2/10 at 20%, scope/delivery/traceability 7.6/10 at 15%. The score reflects the actual supplied documents: strong controls and traceability, but readiness is held below 9 by unresolved external evidence, missing referenced artifacts, and several contracts that remain specified at intent level rather than fully build-contract precise.

## Scope
- In: Independently judge the supplied specification, feature package, contracts, data model, plan, quickstart, checklists, source checks and tasks.
- In: Identify documentation defects, unresolved design contracts, blockers, edge cases, risks, tests and precise improvements.
- In: Separate specification quality from future implementation, production certification, commercial pilot evidence and legal approval.
- Out: App implementation, code edits, repository execution, live source verification, network checks, legal advice, vendor procurement, delegated review and production release certification.
- Out: Treating historical VERIFIED assertions as current evidence unless reproduced in the supplied documents.

## Phases

### Phase 1: Score And Readiness Judgment
**Goal**: Produce a defensible specification-readiness score against the required weighted rubric.

#### Task 1.1: Score the supplied specification package
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `specs/001-abr-lead-engine/plan.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/tasks.md`, `specs/001-abr-lead-engine/checklists/requirements.md`, `specs/001-abr-lead-engine/checklists/security-and-readiness.md`
- Description: Rate only the attached specification package and distinguish build-readiness from release-readiness.
- Estimated Tokens: 1400
- Dependencies: None
- Steps:
  - Apply the required rubric with weights exactly as provided.
  - Penalize missing artifacts, unresolved external approvals, inconsistent or underspecified build contracts and unverified historical evidence.
  - Keep legal, vendor, benchmark and production-gate evidence separate from document quality.
- Acceptance Criteria:
  - Weighted dimension scores total to the stated score.
  - Score is not inflated by future tasks or checklists that are not implementation evidence.
  - Final score is independent from any prior Council, planner or checklist score.

#### Task 1.2: Publish the score basis
- Location: Same documentation package
- Description: Explain why the supplied document earns 8.3/10 and what prevents 9+.
- Estimated Tokens: 900
- Dependencies: Task 1.1
- Steps:
  - Identify strengths: explicit Part 1 boundary, strong suppression model, finite retention, source-coherence rules, traceability, action-time authority and honest production gates.
  - Identify score reducers: missing `deliverables/abr/extract_new_abns.py`, nonexistent `abr_engine/` implementation paths, unverified source counts/prices/benchmarks, pending legal/vendor approvals and reliance on future task evidence.
- Acceptance Criteria:
  - The score is tied to concrete supplied sections.
  - No production or legal certification is implied.

### Phase 2: Blocker Review
**Goal**: List blockers with exact section, concrete failure example and smallest correction.

#### Task 2.1: Document hard specification blockers
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/research.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Identify issues that block production-grade build planning or live activation.
- Estimated Tokens: 1500
- Dependencies: Phase 1
- Steps:
  - Review missing source corpus, snapshot identity, DNCR/manual wash contract, suppression freshness, crawl security, budget accounting, retention and referenced paths.
  - Classify each item as documentation defect, unresolved design dependency or gated future evidence.
- Acceptance Criteria:
  - Each blocker includes section/requirement, concrete failure example and smallest correction.

#### Task 2.2: Prioritized blocker list
- Location: Same package
- Description: Produce a build-actionable list of corrections.
- Estimated Tokens: 1800
- Dependencies: Task 2.1
- Steps:
  - Blocker: R9 / research evidence inventory. Failure example: implementation cannot reproduce “30 legacy trade rules” because `deliverables/abr/extract_new_abns.py` is absent. Smallest correction: add a rules recovery task with exact acceptance artifact, or mark production ABR classification disabled until a replacement corpus is formally approved.
  - Blocker: R3 / R6 / data-model source snapshot. Failure example: same-day ABR republication with changed content could be accepted, but the required “inner transfer metadata/date” fields are not enumerated. Smallest correction: define the exact ABR metadata fields used to establish generation coherence and the fallback when a field is absent.
  - Blocker: R7 / plan lock model. Failure example: process crash after source object upload but before database commit may leave staging; garbage collection is stated, but ownership proof and manifest reconciliation are not fully specified. Smallest correction: add a staging-object manifest table and cleanup eligibility rule keyed by run ID, source and snapshot digest.
  - Blocker: R16 / R17 crawl identity and SSRF. Failure example: DNS changes between resolution and TCP connect could bypass public-IP checks unless the implementation pins resolved IP and validates the connected peer. Smallest correction: specify resolver/connect strategy, IP pinning and test fixture expectations.
  - Blocker: R21 / R24 consent/action rules. Failure example: “message relevance belongs to each actual attempt” is required, but template/content policy fields are only partly enumerated. Smallest correction: add a relevance-evidence schema with actor, campaign, template digest, reason, expiry and rejection states.
  - Blocker: R25 / R29 suppression retention. Failure example: profile deletion after suppression could remove alias data needed to block future contacts. Smallest correction: explicitly list the minimal alias and token fields retained after deletion and who can access them.
  - Blocker: R19 / cost model. Failure example: vendor prepaid minimums are reported separately, but a prepaid purchase could exceed A$150 even if marginal enrichment reservations do not. Smallest correction: separate “monthly enrichment usage cap” from “cash procurement approval cap” with owner approval thresholds.
  - Blocker: R36 / capacity. Failure example: A4vCPU/8GiB host is a candidate, but no tested input-size storage formula or minimum disk size is binding. Smallest correction: add a capacity-sizing worksheet requirement with raw, staged, Parquet, WAL, backup and spill multipliers.
  - Blocker: R43 / tasks traceability. Failure example: tasks cite future paths under `abr_engine/`, but the checkout does not contain that package. Smallest correction: state that all `abr_engine/` paths are proposed and add a first task to create the package root before any path-based verification.
- Acceptance Criteria:
  - All required challenged topics are covered.
  - Each correction is the smallest plausible specification change, not an implementation demand.

### Phase 3: Precision Improvements
**Goal**: Raise the specification toward 9+ readiness without pretending unresolved gates are complete.

#### Task 3.1: Tighten ambiguous contracts
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/data-model.md`
- Description: Convert remaining prose-only rules into explicit schemas, invariants and fixture obligations.
- Estimated Tokens: 1600
- Dependencies: Phase 2
- Steps:
  - Add exact ABR part-coherence field names, accepted absence states and same-day correction examples.
  - Add crawl DNS/IP pinning semantics and SSRF fixture matrix for IPv4, IPv6, redirects and rebinding.
  - Add suppression post-deletion retained-field table.
  - Add consent relevance schema for per-message action checks.
- Acceptance Criteria:
  - A developer can implement without guessing field identity, current-pointer precedence, retained tokens or crawl boundary behavior.
  - Unknown states remain blocked by default.

#### Task 3.2: Repair traceability weaknesses
- Location: `specs/001-abr-lead-engine/tasks.md`, `specs/001-abr-lead-engine/workflow-status.md`, `specs/001-abr-lead-engine/research.md`
- Description: Ensure every referenced artifact is either present, proposed, archived or explicitly missing.
- Estimated Tokens: 1000
- Dependencies: Task 3.1
- Steps:
  - Add a “nonexistent in current checkout” status for `abr_engine/` and `deliverables/abr/extract_new_abns.py`.
  - Require source hash/version sync between canonical spec, Spec Kit package and Obsidian mirror.
  - Add a task to verify referenced markdown links and fail if a claimed canonical dependency is absent.
- Acceptance Criteria:
  - No path can be mistaken for an existing deliverable.
  - Missing files are named dependencies, not silent assumptions.

### Phase 4: Release Boundary
**Goal**: Keep the planning package honest about what readiness does and does not mean.

#### Task 4.1: Separate specification readiness from production release
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/quickstart.md`, `specs/001-abr-lead-engine/checklists/*.md`
- Description: Preserve the current distinction between document checks, implementation tests, live pilot gates and legal approval.
- Estimated Tokens: 900
- Dependencies: Phase 3
- Steps:
  - Keep all G1-G7 gates pending until external evidence is attached.
  - Ensure checked checklist items are labelled writing checks only.
  - Add a visible rule that benchmark, vendor, legal and production claims require dated reproduced evidence.
- Acceptance Criteria:
  - A reader cannot interpret 8.3/10 as permission to collect personal data or contact businesses.
  - Future 9+ document score remains compatible with closed production gates.

## Testing Strategy
- Requirements review: Re-score all 43 FR/R mappings against the five weighted rubric dimensions after each documentation change.
- Consistency test: Verify `R1-R43`, `FR-001-FR-043`, task IDs and acceptance scenarios have one-to-one traceability.
- Path existence review: Mark `abr_engine/` and `deliverables/abr/extract_new_abns.py` as missing/proposed until present in checkout.
- Edge-case review: Confirm explicit examples for same-day republishes, mixed ABR ZIP generations, matching ZIP repartitions, crash recovery, suppression propagation, stale wash overriding old clear, budget concurrency and restore after deletion.
- Evidence review: Confirm every claim about prices, source counts, timings, licences, law and vendor behavior is either attached with dated source evidence or labelled unverified/pending.
- Negative acceptance review: Ensure every fail-closed gate has at least one allowed fixture so an always-empty system cannot pass.

## Risks
- The specification is broad and control-heavy; implementation could become slow or overbuilt before the QBCC pilot validates commercial value. Mitigation: keep MVP to US1 + US2 + minimal US4 on synthetic data, with ABR live expansion gated by G6.
- Some legal/privacy/channel requirements are necessarily policy-gated. Mitigation: preserve unknown as blocked, require qualified assessment before live collection, and avoid treating this plan as legal approval.
- Referenced implementation paths do not exist in the current checkout. Mitigation: make package creation and path verification an explicit first implementation task.
- Source behavior may differ from documented assumptions, especially ABR ZIP metadata, same-day republications and QBCC freshness. Mitigation: require smoke tests and source manifests before live ingestion.
- Budget controls may understate real cash exposure because subscriptions, prepaid credits, taxes and operator time sit outside the A$150 enrichment ceiling. Mitigation: split usage cap from procurement approval and report fully loaded cost.
- Self-critique: This assessment relies only on supplied source text, per the constraint, so it cannot verify whether the repository actually contains the claimed canonical files, Obsidian mirror or checklist artifacts.
- Self-critique: The 8.3/10 score may be generous because the documents are internally mature, but several “specified” controls still depend on future schema details and external evidence that may expose deeper contradictions during implementation.
- Self-critique: The plan identifies missing ABR metadata precision, but without inspecting real ABR files it cannot propose the exact definitive field names safely.

## Rollback Plan
- If documentation changes introduce ambiguity, revert the changed specification section to v4.0 and reapply only the smallest missing-contract correction.
- If a referenced path is found to be nonexistent, do not delete references; relabel it as proposed or missing and add a recovery task.
- If legal, source, vendor or benchmark evidence cannot be reproduced, roll back any “verified” wording to “pending”, “historical” or “unverified”.
- If implementation later contradicts a requirement, do not silently change tasks; create a versioned decision record and update canonical spec, feature spec, tasks and Obsidian mirror together.
- If the pilot scope expands beyond QBCC/manual wash/60 rows/week/A$150 enrichment cap, require owner-approved decision record before changing acceptance criteria.

## Edge Cases
- ABR publication has identical date but different content digest.
- ABR ZIP parts share close timestamps but belong to different generations.
- ABR member count changes or records move between ZIP parts without semantic business changes.
- First ABR baseline produces zero events and must not be treated as failed ingestion.
- Existing ABN gains GST and changes name in the same publication.
- ABN disappears from source without cancellation evidence.
- QBCC licence has no ABN, conflicting address, duplicated class rows or stale source age.
- Similar business name appears on a website but lacks exact ABN/licence or two-attribute reviewer proof.
- Crawl encounters private IP, IPv6 local range, DNS rebinding, credentials in URL, redirect chain or robots block.
- Old DNCR clear wash is followed by newer listed/error result.
- Permission pass expires, is withdrawn, or is superseded by unknown/fail.
- Opt-out occurs during action-intent creation or immediately after consumption.
- Suppression deletes profile fields but must retain enough token/alias data to block future contact.
- Billing times out with unknown provider charge near month boundary.
- Worklist rows are sorted, duplicated, edited stale or contain masked contact fields.
- CRM create times out after remote success and must reconcile before retry.
- Backup restore predates suppression, deletion or key rotation.
- Capacity benchmark fails on candidate host despite specification-level readiness.

## Open Questions
- None for this review; unresolved items are documented dependencies or production gates, not questions to the user.