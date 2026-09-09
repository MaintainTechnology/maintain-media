# Plan

## Overview
SPECIFICATION SCORE: 8.6/10. Weighted rubric: correctness/evidence 8.5/10 ×25% = 2.13; requirements/acceptance 9.0/10 ×20% = 1.80; architecture/data integrity 9.0/10 ×20% = 1.80; privacy/security/operability 8.5/10 ×20% = 1.70; scope/delivery/traceability 8.1/10 ×15% = 1.22; total = 8.65, rounded to 8.6/10. The supplied ABR Lead Engine v4.0 specification is substantially build-ready as documentation, but it should not be rated 9+ until cross-document checklist contradictions, missing referenced evidence files, release-gate semantics, and several acceptance/task traceability gaps are corrected.

## Scope
- In: independently judge the supplied specification artifacts as written.
- In: identify documentation defects, readiness blockers, precise corrections, and safe build-planning defaults.
- In: separate specification readiness from production certification, legal approval, benchmark proof, procurement, credentials, and live outreach readiness.
- In: produce Obsidian-friendly documentation improvement work against `specs/001-abr-lead-engine/` and canonical spec references.
- Out: app implementation, migrations, tests, live source access, legal advice, vendor procurement, benchmark claims, CRM/SERP/DNCR account setup, and outreach.

## Phases
### Phase 1: Record Independent Readiness Judgement
**Goal**: Create a concise, evidence-backed specification assessment that scores only the supplied documents, not hypothetical fixes.

#### Task 1.1: Add readiness score and weighted rubric
- Location: `specs/001-abr-lead-engine/analysis.md`, `specs/001-abr-lead-engine/workflow-status.md`
- Description: Record the independent score, dimension scores, and reason the score is below 9.
- Estimated Tokens: 1200
- Dependencies: none
- Steps:
  - State final specification score as `8.6/10`.
  - Include the weighted rubric exactly: correctness/evidence 25%, requirements/acceptance 20%, architecture/data integrity 20%, privacy/security/operability 20%, scope/delivery/traceability 15%.
  - Explicitly state this is not production certification or legal approval.
- Acceptance Criteria:
  - Score is visibly independent from any historical Council/planner score.
  - No historical “VERIFIED” assertions are treated as verified unless reproduced in attached evidence.
  - The report states that source smoke tests, legal approvals, vendor terms, and capacity proof remain separate release gates.

#### Task 1.2: Explain rating rationale in user-readable terms
- Location: `MaintainMedia/Specs/ABR Lead Engine.md`, `specs/001-abr-lead-engine/analysis.md`
- Description: Add an Obsidian-friendly summary explaining why the spec is strong but not yet 9+.
- Estimated Tokens: 900
- Dependencies: Task 1.1
- Steps:
  - Summarise strengths: deterministic source identity, fail-closed gates, suppression authority, bounded crawl, retention, budget controls, and task mapping.
  - Summarise deductions: checklist drift, missing referenced files, release-gate wording ambiguity, unresolved rules corpus, and acceptance/task traceability gaps.
- Acceptance Criteria:
  - A non-engineer can understand what is ready for build planning and what is not.
  - No legal certainty or production readiness is implied.

### Phase 2: Fix Documentation Contradictions and Missing References
**Goal**: Remove readiness blockers caused by inconsistent document state rather than implementation absence.

#### Task 2.1: Resolve checklist contradictions
- Location: `specs/001-abr-lead-engine/checklists/security-and-readiness.md`
- Description: The checklist leaves CHK006, CHK007, CHK008, CHK010, CHK018, and CHK019 unchecked even though supplied `data-model.md`, `interfaces.md`, `plan.md`, `quickstart.md`, and `tasks.md` appear to address several of them.
- Estimated Tokens: 1600
- Dependencies: Task 1.1
- Steps:
  - Reassess each unchecked checklist item against the supplied artifacts.
  - For each item, either check it with specific evidence or keep it unchecked with an exact missing contract.
  - Do not mark software implemented; label checks as writing/readiness checks only.
- Acceptance Criteria:
  - CHK006 is resolved by citing exact composite provenance constraints in `data-model.md` and API evidence validation in `interfaces.md`, or names the remaining missing field.
  - CHK007 is resolved by citing tri-state inferred/express basis rules in R21, `data-model.md`, and `interfaces.md`.
  - CHK008 is resolved by citing export labels and action-time intent consumption in R22/R24 and `interfaces.md`.
  - CHK010 is resolved by citing R25/R29, suppression projection, deletion/restore flow, and key rotation.
  - CHK018 is resolved by citing R38, operator activity ledger, and `tasks.md` T050-T051, or remains unchecked only for a concrete missing denominator/task.
  - CHK019 is resolved by verifying every FR maps to at least one task and acceptance scenario, or listing exact FRs lacking task evidence.

#### Task 2.2: Repair nonexistent and mismatched referenced paths
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/research.md`, `specs/001-abr-lead-engine/workflow-status.md`
- Description: The source material references files that may not exist in the current checkout or are likely path-invalid from the feature directory.
- Estimated Tokens: 1000
- Dependencies: Task 1.1
- Steps:
  - Mark `deliverables/abr/extract_new_abns.py` as an unresolved external dependency and production-classifier blocker, not a failed spec dependency.
  - Verify links such as `001-abr-lead-engine/spec.md`, `../abr-review-source-checks.md`, and `../../.agents/skills/speckit-converge/SKILL.md` resolve from their containing files.
  - Replace fragile relative links with correct repository-relative paths where needed.
- Acceptance Criteria:
  - Every referenced local artifact either resolves or is explicitly labelled absent/unavailable.
  - Missing legacy rules are not fabricated.
  - The build can proceed in synthetic mode with production classification disabled.

#### Task 2.3: Normalize release-gate wording
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `specs/001-abr-lead-engine/workflow-status.md`
- Description: “All gates are currently OPEN/PENDING” is semantically risky because “open” can mean enabled. Use fail-closed wording.
- Estimated Tokens: 700
- Dependencies: Task 1.1
- Steps:
  - Replace or qualify `OPEN/PENDING` with `pending/unapproved; live capability disabled`.
  - Keep distinction between documentation-quality rating and deployment approval.
- Acceptance Criteria:
  - No reader can interpret a gate as authorising production collection, sending, calling, or vendor access.
  - Fixture/synthetic work remains explicitly allowed.

### Phase 3: Tighten Design Contracts
**Goal**: Improve remaining underspecified or fragile contracts without demanding implementation evidence.

#### Task 3.1: Strengthen ABR snapshot and generation contract
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/quickstart.md`
- Description: Current source identity is strong, but acceptance should more explicitly challenge inconsistent snapshot IDs/date keys, same-day republishes, and matching ZIP generations.
- Estimated Tokens: 1300
- Dependencies: Task 2.1
- Steps:
  - Add explicit examples for same date plus different digest, same digest plus republished metadata, and mixed inner transfer metadata.
  - State that date keys are never primary keys in storage, tasks, manifests, or worklist explanations.
  - Clarify that matching ZIP generations require a recorded member inventory and coherent inner metadata, not merely timestamp proximity or resource count.
- Acceptance Criteria:
  - Same-day correction coexists with predecessor.
  - Identical-content republish is a no-op.
  - Mixed-generation ZIP set cannot advance cursor.
  - A concrete fixture scenario covers each behavior.

#### Task 3.2: Clarify concurrency, leases, and crash recovery boundaries
- Location: `specs/001-abr-lead-engine/plan.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: The supplied plan is good, but long-running ingest locks, provider uncertainty, and outbox recovery need one shared state diagram or table.
- Estimated Tokens: 1400
- Dependencies: Task 2.1
- Steps:
  - Add a transaction-boundary table for source promotion, enrichment billing, CRM create uncertainty, suppression/action consumption, and restore.
  - For each boundary, define before-commit crash, after-commit crash, replay key, and forbidden duplicate effect.
- Acceptance Criteria:
  - No task depends on row number, date-only key, or caller-supplied stale approval.
  - Crash after DB commit resumes delivery from durable outbox.
  - Crash before commit cannot expose partial promotion.
  - Provider timeout never blindly retries a possible create or releases uncertain spend.

#### Task 3.3: Tighten crawl identity and SSRF defaults
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`, `specs/001-abr-lead-engine/quickstart.md`
- Description: Crawl safety is strong; add safe defaults for crawl identity, DNS cache lifetime, user-agent identity, and incomplete terms findings.
- Estimated Tokens: 900
- Dependencies: Task 2.1
- Steps:
  - Define a transparent crawler user-agent/contact string as a configuration requirement before live crawl.
  - Specify DNS resolution is revalidated at connect and redirect, with no trust in stale cached private/public transitions.
  - Clarify incomplete crawl means permission evidence is unknown, not permissive.
- Acceptance Criteria:
  - SSRF fixtures include private IPv4, IPv6, metadata IP, DNS rebinding, redirect-to-private, bad scheme, credentialed URL, and blocked robots.
  - Crawler cannot use proxy evasion or undeclared headless browsing.
  - Identity evidence is required before endpoint extraction is trusted.

#### Task 3.4: Reconcile suppression freshness, propagation, and retention
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`
- Description: Suppression rules are mostly robust, but retention and restore language should explicitly prevent stale backups or downstream systems from re-enabling contact.
- Estimated Tokens: 1000
- Dependencies: Task 2.1
- Steps:
  - Add a suppression-ledger replay invariant to restore and deletion sections.
  - State that external projection failure alarms do not weaken local action denial.
  - Reconcile evidence retention with minimisation: retain only what is needed for suppression, complaint, legal hold, or selected consent/action evidence.
- Acceptance Criteria:
  - Suppression cannot be deleted through routine retention.
  - Restore cannot reopen outbound actions until latest suppression and erasure ledger is replayed.
  - Sheets/CRM are labelled projections, not authority.

### Phase 4: Improve Acceptance, Traceability, and Delivery Readiness
**Goal**: Make the specification easier to build from and easier to audit later.

#### Task 4.1: Add a requirements-to-acceptance matrix
- Location: `specs/001-abr-lead-engine/tasks.md`, `specs/001-abr-lead-engine/analysis.md`
- Description: R43/FR-043 says every requirement maps to tasks and acceptance evidence, but the supplied materials do not include a compact matrix.
- Estimated Tokens: 1800
- Dependencies: Task 2.1
- Steps:
  - Create a table with columns: FR, canonical R, task IDs, acceptance scenario, release gate if applicable.
  - Mark document checks separately from implementation checks.
- Acceptance Criteria:
  - FR-001 through FR-043 each has at least one task and one acceptance/evidence reference.
  - Production-only dependencies are labelled as gates rather than failing synthetic build readiness.
  - No task checkbox is checked without executed evidence.

#### Task 4.2: Clarify consent and channel rules as policy gates
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/data-model.md`, `specs/001-abr-lead-engine/contracts/interfaces.md`
- Description: The spec handles consent carefully, but should make the exact safe default obvious: unknown blocks, and no channel inherits consent from another channel.
- Estimated Tokens: 900
- Dependencies: Task 2.1
- Steps:
  - Add explicit examples: public email with no reviewed basis blocks; deliverable email without relevance blocks; clear DNCR wash does not approve calling; phone wash does not imply email permission.
  - Keep legal approval separate from requirements quality.
- Acceptance Criteria:
  - Email and phone branches remain distinct.
  - Express consent and inferred publication evidence are not mixed.
  - Current highest-sequence fail/unknown/withdrawn beats old pass.

#### Task 4.3: Expand budget, capacity, and cost acceptance evidence
- Location: `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/quickstart.md`, `specs/001-abr-lead-engine/tasks.md`
- Description: The budget model is strong, but cost and capacity evidence need clear acceptance records and owner decisions.
- Estimated Tokens: 900
- Dependencies: Task 2.1
- Steps:
  - Add required budget evidence artifacts: tariff version, FX date, tax/buffer, prepaid/subscription commitment, reservation-month ownership, uncertain-charge reconciliation.
  - Add capacity evidence artifact requirements: hardware, disk preflight, RSS, WAL, spill, output-bearing diff time, full elapsed time.
- Acceptance Criteria:
  - A$150 enrichment cap is not confused with total monthly operating cost.
  - No current VPS/storage/vendor quote is implied.
  - Historical 9.1s or 20.5M claims remain unverified until reproduced.

## Testing Strategy
- Run a documentation consistency review only; do not require app tests to pass a specification-quality rating.
- Validate every local link referenced from `specs/abr-lead-engine.md`, `specs/001-abr-lead-engine/spec.md`, `plan.md`, `research.md`, `quickstart.md`, `data-model.md`, and `contracts/interfaces.md`.
- Check FR-001 through FR-043 against task IDs T001-T059 and acceptance scenarios.
- Re-score after documentation fixes using the same weighted rubric; target 9+ only if checklist contradictions, missing links, release-gate wording, and traceability matrix are resolved.
- Confirm all checked checklist items describe writing quality only, not executed software evidence.
- Confirm all live/procurement/legal/vendor/capacity items remain gated and fail-closed.

## Risks
- The checklist currently contradicts the richer supplied artifacts: unchecked CHK006/007/008/010 may unfairly lower readiness unless either corrected or justified with exact missing fields.
- The canonical document references `001-abr-lead-engine/spec.md` and other local files; if those paths do not resolve from the actual file location, Obsidian and reviewer navigation will degrade.
- “OPEN/PENDING” gate wording can be misread as enabled; the smallest correction is to say `pending/unapproved; live capability disabled`.
- The missing `deliverables/abr/extract_new_abns.py` and intended 30-rule corpus block production classification, but not synthetic build planning; the documents must preserve that distinction.
- Same-day ABR republishes and date-key collisions are addressed conceptually, but a concrete matrix of fixture examples would make the contract harder to misimplement.
- Consent/channel requirements are legally cautious but still depend on future qualified policy review; no spec score should imply legal approval.
- Capacity/cost claims remain planning targets; using them in sales or release language before benchmark/procurement evidence would be a factual defect.
- Self-critique: This plan relies only on embedded source material as required, so it cannot verify whether repository paths actually exist or whether Obsidian mirrors are current.
- Self-critique: The 8.6 score may still be slightly generous because the security checklist has unresolved unchecked items; if those reflect real missing contracts rather than stale checklist state, the architecture/privacy sub-scores should drop closer to 8.0.
- Self-critique: The plan focuses on documentation readiness, so it may underweight implementation effort hidden inside “strong” requirements such as suppression serialization, DNS rebinding protection, and composite FK provenance.
- Self-critique: The supplied spec is large and internally careful, but size itself creates risk: future implementers may miss authoritative precedence unless the traceability matrix and gate summaries are made more navigable.

## Rollback Plan
- Keep `specs/abr-lead-engine.v3.5.backup.md` as historical archive only.
- Before documentation edits, copy current v4.0 artifacts into a dated review snapshot or rely on git history if available.
- If a proposed checklist correction is disputed, revert only that checklist line and add an explicit unresolved blocker with section, failure example, and smallest correction.
- If link normalization breaks Obsidian navigation, restore the previous link and add a repository-relative alternate link beside it.
- Do not delete historical claims; relabel them as historical/unverified unless reproduced evidence is attached.
- Do not check any implementation task checkbox without command, revision, environment, and artifact evidence.

## Edge Cases
- Same date, different ABR content digest: distinct publication with separate snapshot UUID.
- Same digest, new metadata: no-op republish with manifest evidence.
- Mixed ZIP members from different generations: hold, alarm after 48 hours, escalate after seven days.
- ABN disappears from source: quality anomaly, not cancellation.
- Missing legacy rules: synthetic classifier allowed; production classification disabled.
- Similar business name found online: identity unknown unless exact ABN/licence or reviewed two-attribute corroboration exists.
- Public email with no reviewed basis: blocked.
- Deliverable email with stale permission: blocked.
- Old DNCR clear followed by newer listed/error: blocked.
- Opt-out during export or stale sheet edit: suppression commits first and stale projection cannot authorise contact.
- Budget month rollover with uncertain request: charge remains in reservation month.
- Restore from backup predating suppression: quarantine, replay suppression/erasure ledger, run overdue deletion, then reopen.
- Retention conflict between evidence minimisation and seven-year selected evidence: retain only scoped selected evidence with documented purpose.
- Nonexistent referenced source-check or extractor file: mark unresolved dependency; do not invent evidence.

## Open Questions
- None for this planning pass; unresolved items are documented blockers or release-gated dependencies, not questions requiring user input.