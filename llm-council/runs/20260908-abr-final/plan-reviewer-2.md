# Plan

## Overview
Independently assess the supplied ABR Lead Engine v4.0 specification package for build-planning readiness, not production readiness. SPECIFICATION SCORE: 8.6/10 using weighted rubric: correctness/evidence 8.5/10 x25%=2.125; requirements/acceptance 9.0/10 x20%=1.8; architecture/data integrity 8.8/10 x20%=1.76; privacy/security/operability 8.7/10 x20%=1.74; scope/delivery/traceability 7.8/10 x15%=1.17; total 8.595 rounded to 8.6/10.

## Scope
- In: Score the actual supplied specification, check cross-document readiness, identify blockers, propose precise documentation improvements, separate spec quality from legal approval and production certification.
- In: Review canonical spec, source checks, Spec Kit feature spec, plan, data model, interfaces, quickstart, checklists, tasks, research, and workflow status embedded in the brief.
- Out: Application implementation, repository edits, command execution, network verification, legal advice, production certification, vendor procurement, delegated agent review.

## Phases
### Phase 1: Specification Readiness Judgment
**Goal**: Produce a defensible independent readiness score against the required weighted rubric.

#### Task 1.1: Score The Supplied Specification
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `specs/001-abr-lead-engine/plan.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: Score only the supplied v4.0 materials and attached source checks; do not credit future fixes, claimed prior verification, or nonexistent application files.
- Estimated Tokens: 1800
- Dependencies: None
- Steps:
  - Apply the five weighted dimensions exactly as supplied.
  - Treat all historical VERIFIED assertions as unverified unless reproduced in the attached source checks.
  - Rate documentation/build-planning readiness separately from release gates, legal approval, vendor setup, and production evidence.
- Acceptance Criteria:
  - Output states `SPECIFICATION SCORE: 8.6/10`.
  - Each weighted dimension has a numeric 0-10 score and contribution.
  - Score is below 9 because unresolved source files, external evidence, and some design-contract gaps remain.

#### Task 1.2: Explain Score Basis
- Location: Entire supplied document package
- Description: Summarize why the specification is strong but not yet 9+.
- Estimated Tokens: 1200
- Dependencies: Task 1.1
- Steps:
  - Credit explicit defaults: QLD/northern NSW pilot, A$150 enrichment cap, 60 rows/week, Part1 does not send.
  - Credit improved treatment of ABR/QBCC/GST/DNCR claims as signals rather than proof.
  - Penalize missing legacy rule corpus, referenced nonexistent extractor, unexecuted evidence, source-check dependency, and plan/task traceability weaknesses.
- Acceptance Criteria:
  - Findings distinguish documentation defects from gated future implementation/procurement evidence.
  - No benchmark, legal, vendor, or application completion is implied.

### Phase 2: Blocker Identification
**Goal**: Name readiness blockers with exact section/requirement, concrete failure example, and smallest correction.

#### Task 2.1: Identify Blocking Documentation Defects
- Location: `specs/abr-lead-engine.md` R2-R9, R16-R19, R21-R30, R36-R43; `research.md`; `tasks.md`
- Description: List blockers that affect buildability or acceptance design, not missing production execution alone.
- Estimated Tokens: 2200
- Dependencies: Phase 1
- Steps:
  - Check snapshot identity, same-day republishes, matching ZIP generations, concurrency, crash recovery, deterministic rules, crawl safety, suppression freshness, retention, consent, budget, capacity, and nonexistent files.
  - For each blocker, include exact section, failure example, smallest correction.
- Acceptance Criteria:
  - At least eight concrete blockers are listed.
  - Missing `deliverables/abr/extract_new_abns.py` is treated as a production classifier blocker, not a blocker to synthetic engineering.
  - Gated legal/vendor/capacity evidence is not incorrectly scored as implementation failure.

#### Task 2.2: Separate Gated Dependencies From Spec Defects
- Location: `Release gates and dependencies`, `research.md`, `quickstart.md`, `workflow-status.md`
- Description: Avoid over-penalizing the spec for correctly gated future work.
- Estimated Tokens: 1000
- Dependencies: Task 2.1
- Steps:
  - Classify legal approval, source terms, vendor terms, live DNCR account, CRM sandbox, capacity benchmark, and pilot outcomes as pending release evidence.
  - Classify inconsistent or incomplete contracts as specification defects.
- Acceptance Criteria:
  - Report explicitly says production gates are pending and do not equal spec unreadiness.
  - Report still lowers score where missing dependencies leave build contracts incomplete.

### Phase 3: Precision Improvements
**Goal**: Provide exact amendments that would raise the specification above 9 without pretending they already exist.

#### Task 3.1: Amend Traceability And Evidence Contracts
- Location: `specs/001-abr-lead-engine/tasks.md`, `specs/001-abr-lead-engine/checklists/requirements.md`, `specs/001-abr-lead-engine/checklists/security-and-readiness.md`
- Description: Make checklist claims verifiable against actual artifacts and avoid checked boxes that read stronger than the evidence.
- Estimated Tokens: 1300
- Dependencies: Phase 2
- Steps:
  - Add a requirement-to-task-to-acceptance matrix with one row per FR-001-FR-043.
  - Mark checklist state as “writing satisfies criterion” and add evidence file references.
  - Add a rule that no implementation acceptance box can be checked without command, revision, environment, and artifact path.
- Acceptance Criteria:
  - A reviewer can trace every requirement to at least one task and one scenario.
  - Checklist wording cannot be mistaken for passed software tests.

#### Task 3.2: Tighten Source Generation And Snapshot Contracts
- Location: R2-R8, `data-model.md`, `interfaces.md`, `quickstart.md`
- Description: Remove remaining ambiguity around source-generation evidence and same-day republication.
- Estimated Tokens: 1200
- Dependencies: Phase 2
- Steps:
  - Define the exact ABR “required part inventory” fields to compare, including inner transfer metadata, resource ID, member digest, and declared generation value.
  - Add fixture names for mixed-generation, same-date correction, identical-content republish, and repartitioned same-business publication.
  - State the exact rule for semantic no-op versus content-new snapshot.
- Acceptance Criteria:
  - Same date plus changed digest creates a new snapshot UUID.
  - Repartitioned content cannot create false business events.
  - Mixed-generation ZIPs cannot advance the source cursor.

#### Task 3.3: Resolve Rule Corpus Dependency
- Location: R9, `research.md`, `tasks.md` T004/T040/T041
- Description: Make the missing legacy classifier source actionable.
- Estimated Tokens: 900
- Dependencies: Phase 2
- Steps:
  - Add a `rules_recovery_decision` record shape: source path, hash, owner approval, review date, diff from v3.5 claims, and replacement approval path.
  - Define minimum synthetic rule fixture coverage independent of recovered legacy rules.
  - Define production behavior when rules remain missing: classify as disabled, not partially guessed.
- Acceptance Criteria:
  - `deliverables/abr/extract_new_abns.py` absence is a named dependency with a deterministic fallback.
  - Production classification cannot enable without approved rule evidence.

#### Task 3.4: Strengthen Consent, Suppression And Action-Time Contracts
- Location: R21-R25, `interfaces.md`, `data-model.md`
- Description: Make freshness, propagation, and action authority fully testable.
- Estimated Tokens: 1300
- Dependencies: Phase 2
- Steps:
  - Add explicit monotonic current-pointer transaction rules for identity, basis, wash, suppression, and action intent reads.
  - Define stale sheet/CRM behavior when a live suppression succeeds but downstream projection fails.
  - Add fixture examples where old pass, newer unknown, and newer withdrawn all block.
- Acceptance Criteria:
  - Static worklist export cannot be interpreted as reusable contact permission.
  - Suppression commit wins over all future controlled actions.
  - External already-dispatched race is documented without false atomicity claims.

#### Task 3.5: Clarify Capacity, Cost And Retention Defaults
- Location: R19, R29, R36, `Cost model`, `quickstart.md`
- Description: Reduce implementation ambiguity in money, storage, and capacity planning.
- Estimated Tokens: 1000
- Dependencies: Phase 2
- Steps:
  - Add minimum vendor budget-table columns and fixture examples for FX expiry, tax, retry billing, monthly rollover, and uncertain charges.
  - Define storage preflight formula for raw, current, previous, staged, spill, WAL, backup, and 25 GiB headroom.
  - Add explicit behavior when ABR publication stalls beyond the 90-day snapshot retention limit.
- Acceptance Criteria:
  - No paid call can start without a reservation.
  - Retention does not erase suppression authority.
  - Capacity target remains a release benchmark, not asserted evidence.

### Phase 4: Final Judge Report
**Goal**: Produce the Obsidian-ready final assessment.

#### Task 4.1: Write Final Markdown Assessment
- Location: New Obsidian documentation note or review section, e.g. `MaintainMedia/Specs/ABR Lead Engine Readiness Review.md`
- Description: Prepare a concise judge-style report from the assessment.
- Estimated Tokens: 1800
- Dependencies: Phases 1-3
- Steps:
  - Start with score and weighted rubric.
  - Include blockers, precise improvements, readiness conclusion, gated dependencies, and safe build defaults.
  - Keep under 2500 words.
- Acceptance Criteria:
  - Final score is independent from any planner report scores.
  - Report clearly says “ready for scoped build planning, not production certification.”
  - No legal approval, benchmark proof, or app implementation is claimed.

## Testing Strategy
- Validate the assessment against the required rubric: correctness/evidence 25%, requirements/acceptance 20%, architecture/data integrity 20%, privacy/security/operability 20%, scope/delivery/traceability 15%.
- Check every blocker has section/requirement, failure example, and smallest correction.
- Confirm the report challenges: inconsistent snapshot IDs/date keys, same-day republishes, matching ZIP generations, concurrency/crash recovery, deterministic rules, crawl identity/SSRF, suppression freshness, retention conflicts, consent/channel rules, budget accounting, capacity/cost, and nonexistent referenced files.
- Confirm the report does not demand implemented tests to rate the specification, but lowers the score for unresolved design contracts and missing tasks.
- Confirm production gates are separated from specification readiness.

## Risks
- The supplied package is unusually comprehensive, so the main scoring risk is over-crediting well-written future intentions as if they were verified evidence. Mitigation: score only documentation readiness and explicitly exclude production certification.
- The checklists contain checked boxes that could be misread as passed implementation tests. Mitigation: require the final report to restate that checked means writing criterion satisfied only.
- The missing legacy classifier file could be over-penalized. Mitigation: treat it as a production classification blocker and a traceability weakness, while allowing synthetic build planning to proceed.
- Legal and regulatory language may still be outdated by release. Mitigation: preserve G1 as a hard gate and avoid claiming current-law certainty beyond attached source checks.
- Self-critique: The plan cannot inspect the actual repository because the task forbids tools, so it may miss repo-only drift such as missing mirrors, stale Obsidian copies, or undocumented files outside the embedded source.
- Self-critique: The 8.6 score depends on the embedded documents being complete. If the actual canonical `specs/abr-lead-engine.md` differs from the pasted source, this assessment could be materially wrong.

## Rollback Plan
- If the assessment is later found to rely on stale or mismatched source text, discard the score and rerun against the actual checkout files.
- If legal/vendor/capacity evidence is later attached, keep this review as a v4.0 documentation-readiness baseline and create a new dated review rather than editing the score retroactively.
- If the missing rules file is recovered, add a fresh classifier-readiness review and adjust only the affected correctness/traceability dimensions.
- If implementation starts before blockers are resolved, force fixture-only mode and keep production classifier, crawler, paid enrichment, CRM, and outreach gates disabled.

## Edge Cases
- Same-day ABR correction with different digest but same date key.
- Identical-content republish with fresh metadata but no semantic changes.
- ABR ZIP parts from different generations or shifted member boundaries.
- Crash after object upload but before cursor promotion.
- Crash after cursor promotion but before worklist/CRM delivery completes.
- Concurrent source runs or billable enrichment reservations.
- Missing legacy rules file with synthetic classifier present.
- SERP result for a similarly named but different business.
- Redirect or DNS rebinding to private, local, link-local, metadata, or IPv6-equivalent addresses.
- Old consent pass superseded by newer unknown, fail, or withdrawn assessment.
- Old DNCR clear superseded by newer listed/error result.
- Opt-out committed while a sheet/CRM projection is stale.
- Retention deleting useful profile data while suppression tokens must persist.
- Month boundary during uncertain provider billing.
- Pilot with zero booked meetings but too-small sample size or incomplete activity accounting.

## Open Questions
- None for this planning task; unresolved items are documented as dependencies or gates rather than questions.