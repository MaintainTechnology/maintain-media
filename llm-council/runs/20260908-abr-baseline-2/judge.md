# Judge Report

## Scores
- Plan 1: 8.3/10
- Plan 2: 8.0/10

## Comparative Analysis
Both plans satisfy the main task: they judge the supplied specification as documentation/build planning, use the weighted rubric, separate readiness from legal/production approval, and identify major blockers.

Plan 1 is stronger overall. It is more precise on snapshot identity, same-day republish collisions, ZIP generation matching, deterministic ordering, crawl SSRF controls, suppression propagation, retention conflict, channel gates, budget reservation, and artifact inventory. Its score of `8.1/10` for the actual specification is plausible, though slightly generous given the task brief says the referenced extractor path does not exist and historical `VERIFIED` claims must be treated as unverified.

Plan 2 is also solid and more conservative with `7.6/10`, which better reflects the evidence gap. It is less structured in separating specific blockers into executable correction tasks, and some acceptance criteria are broader than Plan 1’s.

Final independent specification score: **SPECIFICATION SCORE: 7.8/10**.

Weighted rubric for the supplied specification as written:
- Correctness/evidence: 6.8/10 × 25% = 1.70
- Requirements/acceptance: 8.6/10 × 20% = 1.72
- Architecture/data integrity: 8.2/10 × 20% = 1.64
- Privacy/security/operability: 7.6/10 × 20% = 1.52
- Scope/delivery/traceability: 8.1/10 × 15% = 1.22
- Total: **7.80/10**

The document is unusually detailed and close to build-planning ready, but not 9+ ready because critical evidence is not reproduced, a claimed repo path is known not to exist, snapshot/run identity is not fully collision-safe, crawl security is incomplete, suppression propagation is underdefined, and legal/procurement gates remain unresolved.

## Missing Steps
- Require an evidence appendix for every `VERIFIED`, benchmarked, measured, vendor-priced, legal, and volume claim.
- Add a canonical `snapshot_id`/`publication_id` model that survives same-day republishes and repeated inner XML dates.
- Define deterministic ZIP-half generation matching using resource metadata plus inner member dates or checksums.
- Add crash recovery and idempotency rules for every side-effecting stage.
- Specify stale lock recovery.
- Add crawler SSRF protections, redirect limits, DNS rebinding checks, scheme allowlists, response size limits, and content-type limits.
- Define suppression propagation to Google Sheets, GoHighLevel, carried-over leads, and already-exported worklists.
- Resolve the conflict between indefinite snapshot retention and R31a’s 24-month/thinned retention recommendation.
- Add a channel-by-channel export gate matrix for email, phone, contact form, social links, CRM-only fields, and Part 2 send-time duties.
- Add a spend ledger covering enrichment, DNC, CRM, hosting, object storage, exchange rates, retries, and staff time.
- Add an artifact inventory marking referenced files as `existing`, `missing`, `to-create`, `external`, or `removed`.

## Contradictions
- The spec says `deliverables/abr/extract_new_abns.py` exists, but the task brief says the claimed path does not exist in the current checkout.
- R6 says snapshots are immutable and retained indefinitely, while R31a recommends a finite retention rule: 24 months weekly, then monthly thinning.
- Snapshot filenames use `abr_<YYYYMMDD>.parquet`, but the spec also acknowledges off-cycle and same-day republishes that could reuse the same inner date.
- R1 accepts ZIP halves based mainly on `last_modified` recency and a 48-hour window, but matching publication generation also needs inner member/generation consistency.
- R26 says suppression is immediate, but R30 read-back happens at the start of the following run, leaving a possible weekly lag for Sheet/CRM remediation.
- The document labels many facts `VERIFIED`, but this review has no attached evidence and must treat those assertions as unverified.
- The status `build-ready` overstates readiness until evidence, legal gates, missing artifacts, run identity, retention, and operational recovery gaps are corrected.

## Improvements
- Adopt Plan 2’s more conservative scoring posture but Plan 1’s more precise correction structure.
- Replace historical `VERIFIED` labels with evidence-backed references or downgrade them to `ASSERTED`, `ESTIMATED`, or `REQUIRES RE-VERIFICATION`.
- Add a requirement-to-acceptance traceability matrix covering R1-R38 plus R15a, R18a, R24a, and R31a.
- Add collision-safe snapshot and manifest keys: `run_id`, `snapshot_id`, `publication_id`, `resource_id`, `resource_last_modified`, `etag`, `size`, `zip_sha256`, `inner_member_names`, `inner_member_dates`, and `member_crc`.
- Add safe build defaults: no sends, no calls, no production crawling, mocked external I/O, worklist-only output, and fail-closed export gates until legal/procurement approval.
- Treat legal approval, DNC setup, provider contracts, production credentials, and live first-run evidence as external gates, not specification readiness evidence.
- Add an Obsidian-friendly blocker table with exact section, failure example, smallest correction, owner, and gate type.

## Final Plan

# Plan

## Overview
Independently assess the supplied ABR Lead Engine Part 1 specification as a documentation/build-planning artifact, not as production approval or legal advice. **SPECIFICATION SCORE: 7.8/10**, using the required weighted rubric against the supplied document only.

## Scope
- In: Score the actual supplied specification as written.
- In: Identify blockers with exact section/requirement, concrete failure example, and smallest correction.
- In: Propose precise Obsidian-ready documentation improvements.
- In: Separate specification readiness from production certification, legal approval, procurement, and live evidence.
- Out: App implementation.
- Out: File edits, code execution, repository inspection, web checks, delegated agents, or questions.
- Out: Legal advice, production approval, benchmark confirmation, or current-law certainty.

## Phases

### Phase 1: Readiness Judgement
**Goal**: Produce a defensible independent score and explain why the supplied specification is not yet 9+ ready.

#### Task 1.1: Score the Specification
- Location: `Obsidian/ABR Lead Engine/Specification Readiness.md`
- Description: Score the embedded specification only, treating historical `VERIFIED` claims as unverified unless reproduced in the supplied material.
- Estimated Tokens: 1200
- Dependencies: None
- Steps:
  - State `SPECIFICATION SCORE: 7.8/10`.
  - Include weighted rubric:
    - correctness/evidence 6.8/10 ×25% = 1.70
    - requirements/acceptance 8.6/10 ×20% = 1.72
    - architecture/data integrity 8.2/10 ×20% = 1.64
    - privacy/security/operability 7.6/10 ×20% = 1.52
    - scope/delivery/traceability 8.1/10 ×15% = 1.22
    - total 7.80/10
  - State that the score is specification readiness only.
  - State that legal approval and production certification remain separate external gates.
- Acceptance Criteria:
  - Numeric weighted score is present.
  - The score applies to the actual supplied document, not proposed improvements.
  - The judgement does not imply permission to send, call, crawl production sites, or process production personal information.

#### Task 1.2: Create Blocker Register
- Location: `Obsidian/ABR Lead Engine/Readiness Blockers.md`
- Description: List blockers with exact section/requirement, failure example, smallest correction, and gate type.
- Estimated Tokens: 2200
- Dependencies: Task 1.1
- Steps:
  - Flag nonexistent referenced path: `deliverables/abr/extract_new_abns.py`.
  - Flag unreproduced `VERIFIED`, benchmark, pricing, legal, source, and volume claims.
  - Flag snapshot identity ambiguity across `last_modified`, inner member dates, same-day republishes, and `snapshot_to`.
  - Flag ZIP generation matching gaps for Part 1 and Part 2.
  - Flag concurrency, stale lock, crash recovery, partial writes, CRM retry, and Sheet export idempotency gaps.
  - Flag deterministic rule gaps in same-type name ordering, locality tie-breaks, phrase lists, blocklists, public holidays, timezone source, and service-term vocabulary.
  - Flag crawl identity and SSRF gaps.
  - Flag suppression propagation gaps.
  - Flag retention conflict between R6 and R31a.
  - Flag consent/channel ownership ambiguities between Part 1 export and Part 2 sending.
  - Flag budget accounting gaps beyond enrichment.
- Acceptance Criteria:
  - Every blocker names section/requirement, failure example, and smallest correction.
  - Each blocker is classified as `specification`, `legal`, `procurement`, `production`, or `evidence`.
  - No invented benchmark, legal certainty, or external fact is introduced.

### Phase 2: Evidence and Traceability
**Goal**: Make the specification auditable without relying on embedded confidence labels.

#### Task 2.1: Define Evidence Appendix
- Location: `Obsidian/ABR Lead Engine/Evidence Appendix.md`
- Description: Specify the evidence pack required for all factual claims.
- Estimated Tokens: 1200
- Dependencies: Task 1.2
- Steps:
  - Require source, access date, command/API call, response excerpt, checksum, and reviewer for each claim.
  - Require raw CKAN responses, HTTP headers, ZIP listings, sample hashes, benchmark scripts, PostgreSQL DDL logs, and pricing captures.
  - Downgrade unsupported claims to `ASSERTED`, `ESTIMATED`, or `REQUIRES RE-VERIFICATION`.
- Acceptance Criteria:
  - Historical `VERIFIED` claims are not accepted without attached evidence.
  - Client-facing claims are separated from internal planning assumptions.

#### Task 2.2: Build Requirement Traceability Matrix
- Location: `Obsidian/ABR Lead Engine/Acceptance Matrix.md`
- Description: Map every requirement to its proof path.
- Estimated Tokens: 1400
- Dependencies: Task 1.2
- Steps:
  - Assign stable IDs, resolving duplicate numbering around R15 and R15a.
  - Map each requirement to fixture, real-data test, manifest field, alarm, manual approval, legal review, procurement, or commercial validation.
  - Add artifact inventory for extractor, rules YAML, vocabularies, postcode lookup, CRM mapping, runbook, script tests, and README.
- Acceptance Criteria:
  - No requirement lacks an acceptance path.
  - Missing files are marked as planned or removed, not treated as existing inputs.

### Phase 3: Specification Corrections
**Goal**: Resolve build-readiness gaps before implementation planning starts.

#### Task 3.1: Normalize Snapshot and Run Identity
- Location: `Obsidian/ABR Lead Engine/Run Identity.md`
- Description: Define canonical identifiers for publications, resources, snapshots, and runs.
- Estimated Tokens: 1300
- Dependencies: Task 2.2
- Steps:
  - Define `run_id`, `snapshot_id`, `publication_id`, `resource_id`, `last_modified`, `etag`, `size`, `zip_sha256`, `inner_member_dates`, and `member_crc`.
  - Replace `abr_<YYYYMMDD>.parquet` with collision-safe naming such as `abr_<snapshot_date>_<snapshot_id>.parquet`.
  - Require ZIP halves to match by deterministic generation rules, not only a 48-hour window.
- Acceptance Criteria:
  - Same-day republishes cannot overwrite snapshots or collide in event keys.
  - Manifest can reconstruct exactly which source resources produced each snapshot.

#### Task 3.2: Add Operability and Recovery Rules
- Location: `Obsidian/ABR Lead Engine/Ops Runbook Requirements.md`
- Description: Specify crash-safe execution and retry semantics.
- Estimated Tokens: 1500
- Dependencies: Task 3.1
- Steps:
  - Require atomic writes: temp path, fsync, validate, rename.
  - Require object-storage verification before local cleanup.
  - Define stage checkpoints and idempotency keys for download, parse, snapshot, diff, enrichment, Sheet export, CRM push, and outcome read-back.
  - Define stale lock recovery using PID, hostname, start time, and logged operator override.
- Acceptance Criteria:
  - Every stage can be retried without duplicate events, duplicate CRM contacts, or lost worklist state.
  - Crash recovery has deterministic next actions.

#### Task 3.3: Add Crawl Security Controls
- Location: `Obsidian/ABR Lead Engine/Crawl Safety.md`
- Description: Extend robots compliance into a complete safe-crawl requirement.
- Estimated Tokens: 1300
- Dependencies: Task 3.2
- Steps:
  - Add scheme allowlist, HTTPS preference, redirect cap, DNS re-resolution, private/link-local/loopback/metadata IP denial, content-type allowlist, byte limits, and timeouts.
  - Require configured User-Agent with Maintain Media identity and contact URL.
  - Add fixtures for private IPs, metadata endpoints, bad schemes, redirects, oversized responses, and wildcard robots rules.
- Acceptance Criteria:
  - Crawler cannot fetch internal networks or metadata endpoints.
  - Logs prove identity, robots compliance, and rate limiting.

#### Task 3.4: Resolve Compliance, Retention, and Channel Gates
- Location: `Obsidian/ABR Lead Engine/Compliance Gate Matrix.md`
- Description: Consolidate privacy, Spam Act, DNC, ACL, retention, and Part 1/Part 2 boundaries.
- Estimated Tokens: 1800
- Dependencies: Task 3.3
- Steps:
  - Replace conflicting retention language with one binding schedule, or mark retention blocked pending legal sign-off.
  - Add channel matrix for email, mobile, landline, contact form, social URL, and CRM-only fields.
  - Define suppression propagation SLA for Sheets, GoHighLevel, carried-over worklists, and emergency opt-outs.
  - Mark legal review of clause 4, APP 5, APP 7, APP 8, s 22, DNC, calling windows, and ACL as external gates.
- Acceptance Criteria:
  - Each channel has one deterministic export gate.
  - Suppression is immediate in system behavior, not delayed until the next weekly run.
  - Production contact remains blocked until legal/procurement gates pass.

#### Task 3.5: Add Budget and Capacity Ledger
- Location: `Obsidian/ABR Lead Engine/Cost and Capacity Model.md`
- Description: Make spend and capacity controls auditable.
- Estimated Tokens: 1000
- Dependencies: Task 3.4
- Steps:
  - Define billing month, exchange-rate source/date, provider unit costs, pre-call budget reservation, failed-call refund handling, and atomic spend ledger.
  - Track enrichment, DNC, CRM, Sheets, hosting, object storage, egress, and VA time separately.
  - Add pre-run disk/temp/WAL checks and first-snapshot measurement replacement of estimates.
- Acceptance Criteria:
  - Retries and concurrent runs cannot exceed the cap.
  - Cost model is updated from measured data before continuing past Phase 0.

## Testing Strategy
- Perform static review against the five weighted rubric dimensions.
- Verify every blocker has section/requirement, failure example, smallest correction, and gate type.
- Review contradictions in snapshot identity, ZIP pairing, retention, suppression timing, channel gates, and Part 1/Part 2 boundaries.
- Require evidence downgrade or attachment for all `VERIFIED`, measured, benchmarked, legal, vendor, pricing, and volume claims.
- Build a traceability matrix from every requirement to fixture, real-data proof, alarm, manifest field, legal review, procurement, production monitoring, or commercial validation.
- Confirm final output stays documentation-only and does not imply implementation, legal sign-off, or production certification.

## Risks
- Unreproduced evidence may invalidate major source, cost, legal, or benchmark claims; mitigation: require an evidence appendix and downgrade unsupported claims.
- Same-day republishes may overwrite snapshots or collide in event keys; mitigation: add immutable `snapshot_id` and non-overwriting object keys.
- Missing repo artifacts may make build-ready status false; mitigation: add artifact inventory and mark missing inputs explicitly.
- Crawl compliance may fail without SSRF controls; mitigation: add network safety requirements and fixtures.
- Suppression may not propagate fast enough after export; mitigation: define immediate propagation and CRM/Sheet reconciliation.
- Legal assumptions may be wrong or stale; mitigation: keep all contact channels fail-closed until Australian legal review.
- Budget cap may be exceeded if spend is recorded after calls; mitigation: use pre-call reservation and atomic spend ledger.

## Rollback Plan
- Restore the prior specification/readiness note from version control if the assessment overstates certainty.
- If a blocker is later disproven, mark it resolved with evidence path, date, and reviewer.
- If legal review rejects a channel assumption, disable that channel in rules/config and keep worklist-only reporting.
- If implementation has already started, pause production-facing work and backfill evidence, artifact inventory, run identity, retention, channel gates, and recovery rules before continuing.
- If repo files differ from the spec, update documentation references before building against stale paths.

## Edge Cases
- Same inner XML date but different ZIP content or `last_modified`.
- Part 1 and Part 2 modified within 48 hours but with incompatible inner member dates.
- ABR off-cycle republish with zero meaningful row changes.
- Crash after snapshot upload but before manifest completion.
- Crash after partial CRM push or Sheet export.
- Stale lock from killed process.
- Rules YAML changes between provisional and final scoring.
- QBCC lead has no ABN or no parseable postcode.
- Multiple QBCC licences share one ABN.
- One endpoint appears on multiple leads and receives one opt-out.
- Email basis expires while a lead is carried over.
- DNC wash expires between enrichment and worklist use.
- Site adds a no-unsolicited notice after enrichment.
- SERP result redirects to private IP, metadata IP, non-HTTP scheme, or oversized content.
- Spend cap reached mid-record.
- Snapshot archive conflicts with APP minimisation.
- Google Sheets contains personal information and must be treated as an overseas-recipient disclosure.
- Claimed extractor path does not exist in the current checkout.
- Tier B produces no meetings while Tier A does, triggering the pre-committed switch-off.

## Open Questions
- None for this planning pass. The unresolved items are blockers or external gates: evidence appendix, legal review, DNC access tier and lead time, artifact inventory, current repo file map, production credentials policy, and measured Phase 0/first-snapshot capacity data.