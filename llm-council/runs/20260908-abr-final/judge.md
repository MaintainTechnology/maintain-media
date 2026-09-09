# Judge Report

## Scores
- Plan 1: 8.7/10
- Plan 2: 8.4/10

## Comparative Analysis
Plan 1 is stronger overall: it gives a more conservative and defensible SPECIFICATION SCORE of 8.3/10, better separates documentation readiness from production/legal readiness, and lists concrete blockers with section references, failure examples, and smallest corrections. It is concise enough and less likely to over-credit future intentions.

Plan 2 has broader coverage and a useful phase structure, but it prematurely fixes the specification score at 8.6/10 and sometimes treats requested final-report content as task acceptance criteria. It is more verbose without adding much extra judgment, and it underplays some residual contract ambiguity by giving higher architecture/privacy scores.

Both plans correctly avoid implementation, tools, legal certification, production claims, and historical verified assertions. Both identify the missing legacy classifier file, snapshot identity, ABR generation coherence, crawl/SSRF, suppression, consent, budget, retention, capacity, and traceability as key issues. The improved final plan should use Plan 1’s stricter scoring and blocker framing, plus Plan 2’s clear rubric math and explicit checklist/evidence-contract improvements.

## Missing Steps
- State a final independent specification score separately from the plan-quality scores.
- Provide the weighted rubric dimension scores for the supplied specification, not just a total.
- Explicitly classify each major issue as either a documentation defect, unresolved design dependency, or gated future evidence.
- Call out that checked Spec Kit checklists are writing-quality evidence only, not implementation evidence.
- Include nonexistent referenced files and proposed paths as traceability defects without demanding implementation.
- Include concrete safe build defaults: fixture/offline mode, live integrations disabled, no sending/dialling, manual DNCR pilot, QLD/northern NSW, A$150/month enrichment cap, 60 rows/week.
- Avoid setting acceptance criteria that force a predetermined report score unless the scoring rationale supports it.

## Contradictions
- Plan 2 says the final report must state `SPECIFICATION SCORE: 8.6/10`, which conflicts with the judge’s duty to score independently.
- Plan 2’s 8.6 score is slightly generous given unresolved metadata precision, missing classifier corpus, proposed-only implementation paths, and source/vault traceability gaps.
- Plan 1 says “hard specification blockers” but includes some live activation blockers; these should be separated from build-planning documentation defects.
- Both plans mention path-existence review, but the task forbids tools; the final report must rely only on supplied statements that the extractor path does not exist and no ABR production app was found.
- Neither plan should imply that unresolved legal/vendor/capacity evidence alone prevents a high documentation score; those are gated future evidence unless they leave the design contract ambiguous.

## Improvements
- Use an independent specification score of 8.3/10: strong enough for scoped build planning, not strong enough for 9+ because of unresolved classifier provenance, exact source-generation contract gaps, proposed-only artifacts, and remaining evidence/traceability weaknesses.
- Include weighted rubric math: correctness/evidence 8.4, requirements/acceptance 8.8, architecture/data integrity 8.3, privacy/security/operability 8.4, scope/delivery/traceability 7.6, total 8.34 rounded to 8.3.
- Keep blockers precise: section/requirement, failure example, smallest correction.
- Make the final plan an assessment-writing plan, not an implementation plan.
- Add a final “no questions” stance because unresolved items are dependencies/gates, not clarification requests.

## Final Plan

# Plan

## Overview
Independently assess the supplied ABR Lead Engine v4.0 specification package for documentation and build-planning readiness, not production certification or legal approval. SPECIFICATION SCORE: 8.3/10, using the required weighted rubric: correctness/evidence 8.4 x25%=2.10; requirements/acceptance 8.8 x20%=1.76; architecture/data integrity 8.3 x20%=1.66; privacy/security/operability 8.4 x20%=1.68; scope/delivery/traceability 7.6 x15%=1.14; weighted total 8.34, rounded to 8.3/10.

## Scope
- In: Score the actual supplied v4.0 specification, source checks, Spec Kit package, plan, data model, interfaces, quickstart, checklists, research, tasks, and workflow status.
- In: Identify documentation defects, unresolved design dependencies, gated future evidence, contradictions, and precise improvements.
- In: Separate specification readiness from implementation completion, production certification, commercial pilot evidence, vendor procurement, and legal approval.
- Out: Repository inspection, code execution, file edits, network checks, delegated agents, legal advice, app implementation, live outreach, or production release approval.
- Out: Treating historical VERIFIED assertions as current evidence unless reproduced in the supplied source checks.

## Phases

### Phase 1: Score The Supplied Specification
**Goal**: Produce a defensible independent readiness score against the required weighted rubric.

#### Task 1.1: Apply Weighted Rubric
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `plan.md`, `data-model.md`, `contracts/interfaces.md`, `quickstart.md`, `research.md`, `tasks.md`, `checklists/*.md`, `workflow-status.md`
- Description: Score only the supplied document package and attached source checks.
- Estimated Tokens: 1200
- Dependencies: None
- Steps:
  - Apply the five required weighted dimensions.
  - Credit explicit defaults and controls: Part 1 does not send, QLD/northern NSW pilot, 60 rows/week, A$150/month enrichment cap, manual DNCR pilot, offline fixture mode.
  - Penalize missing referenced artifacts, unverified historical claims, proposed-only implementation paths, and unresolved build-contract precision.
- Acceptance Criteria:
  - Report states `SPECIFICATION SCORE: 8.3/10`.
  - Each dimension has a 0-10 score and weighted contribution.
  - The score is independent from Plan 1, Plan 2, checklist, or Council scores.

#### Task 1.2: Explain Readiness Boundary
- Location: `Release gates and dependencies`, `workflow-status.md`, `quickstart.md`
- Description: Explain why the package is ready for scoped build planning but not production certification.
- Estimated Tokens: 700
- Dependencies: Task 1.1
- Steps:
  - Separate documentation quality from G1-G7 release gates.
  - State that legal, vendor, capacity, source smoke, pilot, and sandbox evidence remain pending.
  - Avoid implying that pending gates alone are specification defects.
- Acceptance Criteria:
  - Reader cannot interpret the score as permission to collect personal data or contact businesses.
  - Production gates remain visibly closed.

### Phase 2: Identify Blockers
**Goal**: Name blockers with exact section/requirement, concrete failure example, and smallest correction.

#### Task 2.1: Classify Blocking Issues
- Location: R2-R9, R16-R19, R21-R30, R36-R43, `research.md`, `tasks.md`
- Description: Separate documentation defects from unresolved dependencies and future release evidence.
- Estimated Tokens: 1600
- Dependencies: Phase 1
- Steps:
  - Review snapshot identity, same-day republishes, ZIP generation matching, crash recovery, rule determinism, crawl identity/SSRF, suppression freshness, consent/channel rules, retention, budget, capacity, and nonexistent paths.
  - For each issue, classify as documentation defect, unresolved design dependency, or gated future evidence.
- Acceptance Criteria:
  - Each blocker includes section/requirement, failure example, and smallest correction.
  - Missing `deliverables/abr/extract_new_abns.py` is treated as a classifier provenance blocker, not a reason to block synthetic engineering.
  - Proposed `abr_engine/` paths are labelled proposed deliverables, not existing implementation evidence.

#### Task 2.2: Prioritize Corrections
- Location: Same package
- Description: Produce a concise correction list.
- Estimated Tokens: 1200
- Dependencies: Task 2.1
- Steps:
  - Require exact ABR part inventory and absence handling for generation coherence.
  - Require a rule recovery decision record or explicit approved replacement path.
  - Require resolver/connect semantics for SSRF and DNS rebinding protection.
  - Require retained suppression-token/alias fields after deletion.
  - Require per-message relevance schema and current-pointer precedence examples.
  - Require cost/procurement separation from the A$150 enrichment usage cap.
  - Require capacity-sizing worksheet and source-stall retention behavior.
  - Require requirement-to-task-to-acceptance traceability with evidence rules.
- Acceptance Criteria:
  - Corrections are smallest viable documentation amendments.
  - No correction demands implemented tests merely to rate the specification.

### Phase 3: Improve Assessment Output
**Goal**: Produce an Obsidian-ready review that is precise, understandable, and under 2500 words.

#### Task 3.1: Write Final Readiness Report
- Location: Proposed note such as `MaintainMedia/Specs/ABR Lead Engine Readiness Review.md`
- Description: Draft the assessment content without editing files.
- Estimated Tokens: 1600
- Dependencies: Phase 2
- Steps:
  - Start with score and weighted rubric.
  - Summarize strengths, blockers, smallest corrections, gated dependencies, and safe build defaults.
  - Explicitly state that checklist marks are writing checks only.
- Acceptance Criteria:
  - Report distinguishes specification readiness from production certification and legal approval.
  - Historical source claims remain unverified unless attached evidence reproduces them.
  - Final report is concise and action-oriented.

## Testing Strategy
- Verify weighted score math totals 8.34 and rounds to 8.3/10.
- Confirm every required challenge topic is addressed: snapshot IDs/date keys, same-day republishes, ZIP generations, concurrency/crash recovery, deterministic rules, crawl identity/SSRF, suppression freshness, retention conflicts, consent/channel rules, budget accounting, capacity/cost, and nonexistent referenced files.
- Confirm blockers include section/requirement, concrete failure example, and smallest correction.
- Confirm gated future evidence is not misclassified as failed implementation.
- Confirm no tools, edits, code execution, network checks, questions, or delegated agents are requested.

## Risks
- Risk: Over-crediting comprehensive prose as implemented evidence. Mitigation: score documentation readiness only and keep all implementation evidence pending.
- Risk: Over-penalizing legal/vendor/capacity gates. Mitigation: lower score only where they leave contracts ambiguous; otherwise classify them as release dependencies.
- Risk: Missing repo-only drift due to no-tool constraint. Mitigation: rely only on supplied statements about nonexistent paths and proposed deliverables.
- Risk: Score inflation from checked checklists. Mitigation: state that checked means writing criterion satisfied, not software passed.

## Rollback Plan
- If later review uses actual repository files and finds drift, discard this score and rerun against the current files.
- If recovered legal/vendor/source/capacity evidence is attached later, create a new dated review rather than retroactively editing this v4.0 score.
- If the legacy rule file is recovered, reassess only classifier provenance, deterministic fixtures, and traceability dimensions.
- If implementation begins before corrections are made, keep fixture mode, paid enrichment, CRM, crawler live access, classifier production mode, and outreach disabled.

## Edge Cases
- Same-day ABR correction with changed content digest.
- Identical-content republish with fresh metadata.
- ZIP parts from mixed generations or repartitioned members.
- Baseline zero events versus failed ingestion.
- Crash before promotion, after promotion, or during delivery.
- Concurrent source runs and concurrent near-cap spend reservations.
- Missing legacy rules with synthetic classifier present.
- Similar-name website, wrong business identity, or incomplete corroboration.
- SSRF through redirects, IPv4/IPv6 private ranges, metadata IPs, or DNS rebinding.
- Old consent pass superseded by newer fail, unknown, or withdrawn assessment.
- Old DNCR clear superseded by newer listed/error result.
- Opt-out while sheet/CRM projections are stale.
- Retention deleting profiles while suppression authority must persist.
- Month boundary with uncertain billing.
- CRM timeout after possible remote create.
- Restore from backup predating suppression, deletion, or key rotation.
- Pilot with zero booked meetings and insufficient denominator evidence.

## Open Questions
- None for this review; unresolved items are documented dependencies, gates, or required corrections rather than questions.