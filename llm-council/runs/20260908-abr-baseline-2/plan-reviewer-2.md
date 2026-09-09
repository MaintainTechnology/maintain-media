# Plan

## Overview
Independently assess the supplied ABR Lead Engine Part 1 specification as documentation/build planning, not implementation. SPECIFICATION SCORE: 7.6/10, based on weighted rubric: correctness/evidence 7.0/10 ×25% = 1.75; requirements/acceptance 8.5/10 ×20% = 1.70; architecture/data integrity 8.0/10 ×20% = 1.60; privacy/security/operability 7.5/10 ×20% = 1.50; scope/delivery/traceability 7.0/10 ×15% = 1.05; total = 7.60/10.

## Scope
- In: Assess the actual supplied specification only.
- In: Identify blockers, inconsistencies, missing evidence, unresolved dependencies, and build-readiness gaps.
- In: Propose precise documentation improvements suitable for Obsidian.
- In: Separate specification readiness from production certification and legal approval.
- Out: App implementation, code edits, repo changes, external verification, legal advice, production approval, delegated review.

## Phases
### Phase 1: Specification Readiness Judgement
**Goal**: Produce a rigorous readiness judgement for the supplied ABR Lead Engine specification with a defensible weighted score.

#### Task 1.1: Score the supplied specification
- Location: `specs/abr-lead-engine-part-1.md`, `docs/abr-lead-engine-readiness.md`, `Obsidian/ABR Lead Engine/Specification Readiness.md`
- Description: Score the embedded specification against the required weighted rubric, using only claims and evidence present in the supplied text.
- Estimated Tokens: 1800
- Dependencies: None
- Steps:
  - Treat all historical `VERIFIED` claims as unverified unless attached evidence is reproduced in the supplied material.
  - Score each rubric dimension independently from 0-10.
  - Calculate the weighted total explicitly.
  - State that the score is for specification readiness only, not production certification or legal approval.
- Acceptance Criteria:
  - Final score is stated as `SPECIFICATION SCORE: 7.6/10`.
  - Each rubric dimension includes numeric score, weight, rationale, and weighted contribution.
  - The judgement does not award 9+ because evidence reproduction, legal approval, repository path existence, and operational dependencies remain incomplete.

#### Task 1.2: Identify readiness blockers
- Location: `specs/abr-lead-engine-part-1.md`, `docs/abr-lead-engine-readiness.md`
- Description: List blockers with exact section or requirement, a concrete failure example, and the smallest correction.
- Estimated Tokens: 2200
- Dependencies: Task 1.1
- Steps:
  - Flag nonexistent referenced file path: `deliverables/abr/extract_new_abns.py`.
  - Flag inconsistent source evidence treatment where the document claims external verification but does not attach reproducible evidence.
  - Flag snapshot identity ambiguity around CKAN `last_modified`, inner member filename dates, same-day republishes, and snapshot file keys.
  - Flag concurrency and crash recovery gaps around lockfile, partial writes, deferred FK inserts, CRM partial pushes, and object-store replication.
  - Flag deterministic rule gaps around service-term vocabulary, postcode-to-locality tie-breaking, industry rules, blocked domains, phrase lists, and time-zone/public-holiday source.
  - Flag crawl identity, SSRF, robots handling, redirect limits, private IP filtering, and fetch safety as insufficiently specified.
  - Flag suppression freshness and propagation gaps across Google Sheets, GoHighLevel, worklist carry-over, and already-exported records.
  - Flag retention conflict between indefinite snapshots and R31a 24-month thinning recommendation.
  - Flag consent/channel rules needing legal approval and Part 2 contract clarity.
  - Flag budget accounting gaps separating enrichment cap, DNC access, infrastructure, object storage, CRM, Sheets, and staff time.
- Acceptance Criteria:
  - Every blocker has section/requirement, failure example, and smallest correction.
  - Blockers distinguish build-readiness blockers from legal/procurement/production blockers.
  - No invented benchmark, law, or current-source certainty is added.

### Phase 2: Improvement Plan
**Goal**: Convert the judgement into precise documentation changes that make the specification more buildable and reviewable.

#### Task 2.1: Create evidence appendix requirements
- Location: `docs/abr/evidence/`, `specs/abr-lead-engine-part-1.md`
- Description: Define an evidence pack structure for every claim currently labelled `VERIFIED`, benchmarked, measured, or vendor-priced.
- Estimated Tokens: 1200
- Dependencies: Task 1.2
- Steps:
  - Add an evidence index with source, date accessed, command/API call, response excerpt, checksum where relevant, and reviewer.
  - Require raw CKAN responses, HTTP headers, ZIP member listings, sample hashes, benchmark scripts, PostgreSQL DDL execution logs, and pricing screenshots or API responses.
  - Relabel unsupported claims as `ASSERTED`, `ESTIMATED`, or `REQUIRES RE-VERIFICATION`.
- Acceptance Criteria:
  - Historical verified claims are no longer accepted without attached evidence.
  - Build can proceed using safe defaults where evidence is missing.
  - Client-facing claims are separated from internal planning claims.

#### Task 2.2: Normalize snapshot identity and run keys
- Location: `specs/abr-lead-engine-part-1.md`, `docs/abr/run-manifest-schema.md`
- Description: Specify canonical identifiers for ABR publications, ZIP halves, XML member dates, same-day republishes, and generated snapshots.
- Estimated Tokens: 1300
- Dependencies: Task 1.2
- Steps:
  - Define `publication_id`, `resource_id`, `resource_last_modified`, `resource_etag`, `zip_sha256`, `inner_member_dates`, `snapshot_date`, and `run_id`.
  - Require collision-safe snapshot naming for same-day republishes, such as `abr_<snapshot_date>_<publication_id>.parquet`.
  - Require matching ZIP generation rules that compare both resource metadata and inner member dates.
  - Define manual override fields for mismatched halves.
- Acceptance Criteria:
  - Same-day republishes cannot overwrite prior snapshots.
  - Mixed-generation Part 1/Part 2 processing is impossible without logged override.
  - Manifest can reconstruct exactly which external resources produced each snapshot.

#### Task 2.3: Add safety and operability defaults
- Location: `specs/abr-lead-engine-part-1.md`, `docs/abr/ops-runbook.md`
- Description: Strengthen operational safety, crawl safety, budget controls, and recovery procedures.
- Estimated Tokens: 1700
- Dependencies: Task 1.2
- Steps:
  - Add atomic file-write pattern: write to temp path, fsync, validate, then rename.
  - Add object-storage replication verification before local cleanup.
  - Add stage-level idempotency keys and checkpointing.
  - Add SSRF protections: block private, loopback, link-local, metadata, and non-http schemes; cap redirects; re-resolve DNS after redirect.
  - Add user-agent and contact identity requirements for crawls.
  - Add public-holiday and timezone data source requirements.
  - Add budget ledger covering enrichment, DNC, CRM, storage, host, and manual labour separately.
- Acceptance Criteria:
  - Crash during download, parse, Parquet write, DB transaction, CRM push, or Sheets export has a deterministic recovery path.
  - Crawl cannot fetch internal networks or metadata endpoints.
  - Budget cap semantics are unambiguous and auditable.

#### Task 2.4: Repair traceability and acceptance mapping
- Location: `specs/abr-lead-engine-part-1.md`, `docs/abr/acceptance-matrix.md`
- Description: Create a requirement-to-test traceability matrix.
- Estimated Tokens: 1400
- Dependencies: Task 1.2
- Steps:
  - Assign stable IDs to every requirement, including duplicate numbering around R15 and R15a.
  - Map every requirement to fixtures, evidence, manifest field, operational alarm, or manual approval.
  - Mark each acceptance item as `fixture`, `real-data`, `legal-review`, `procurement`, `production-monitoring`, or `commercial-validation`.
  - Identify nonexistent referenced files and either remove them or replace them with real repo paths.
- Acceptance Criteria:
  - No requirement lacks an acceptance path.
  - No acceptance item depends on unavailable files without a remediation step.
  - Legal approval and production certification are clearly marked as external gates.

## Testing Strategy
- Perform a document-only rubric review using the five weighted dimensions.
- Validate internal consistency of requirement IDs, snapshot naming, storage retention, gating logic, and delivery flow.
- Check every `VERIFIED`, `measured`, `benchmarked`, and vendor-cost claim for attached reproducible evidence in the supplied material.
- Build a blocker table with exact section, failure example, and smallest correction.
- Build an acceptance matrix covering ingest, diff, classify, qualify, enrich, compliance, delivery, operations, and commercial validation.
- Confirm the final output remains documentation planning only and does not imply legal advice, production certification, or implementation approval.

## Risks
- The specification is unusually detailed, but much of its confidence depends on historical verification claims that are not reproduced in the supplied material; mitigation: require an evidence appendix and downgrade unsupported claims.
- The claimed existing extractor path `deliverables/abr/extract_new_abns.py` does not exist in the current checkout per task brief; mitigation: remove dependency on it or document it as missing input before build.
- Snapshot identity is underspecified for same-day republishes; mitigation: add collision-safe publication IDs and immutable snapshot names.
- Retention policy conflicts remain: the data model says snapshots are retained indefinitely, while R31a recommends 24-month full retention then monthly thinning; mitigation: choose one binding retention schedule and record legal rationale.
- Crawl compliance may fail despite robots handling if SSRF, redirects, DNS rebinding, private IPs, contact identity, and blocked schemes are not specified; mitigation: add explicit network safety requirements.
- Suppression may not propagate fast enough to exported Sheets or CRM records; mitigation: define propagation SLA, write-back reconciliation, and emergency suppression procedure.
- Budget control currently centers on enrichment but excludes DNC subscription, CRM costs, infrastructure drift, storage growth, and VA time; mitigation: add a unified cost ledger and pre-run budget checks.
- Consent and channel rules are carefully discussed but still require legal approval; mitigation: mark them as legal-review gates rather than build-complete evidence.
- Self-critique: This plan cannot verify any repository contents, benchmarks, laws, source metadata, or pricing because the brief prohibits tools and external checks; the score is therefore a readiness judgement of the supplied document, not a factual audit.
- Self-critique: The score may still be generous because the supplied specification contains many sophisticated mitigations, but without reproduced evidence the true correctness/evidence score could be materially lower after live verification.

## Rollback Plan
- Revert documentation changes by restoring the previous Obsidian note or spec version from version control.
- If the score or rubric is challenged, preserve the original scoring table and add a revised dated judgement rather than overwriting the prior one.
- If later evidence contradicts a blocker, mark that blocker `resolved by evidence` with the evidence path, date, and reviewer.
- If legal review rejects a compliance assumption, rollback affected requirements to fail-closed defaults: no sending, no calling, no export of personal contact endpoints, and worklist-only reporting.
- If production certification is requested prematurely, rollback status from `build-ready` to `planning-ready with external gates`.

## Edge Cases
- Same-day ABR republish with identical inner member date but different ZIP content must create a distinct immutable snapshot.
- Part 1 and Part 2 have matching `last_modified` dates but different inner member dates; processing must hold unless manually overridden.
- QBCC file remains stale for months; this is not a pipeline failure unless freshness is incorrectly used as a weekly lead signal.
- Matching ZIP generations cannot rely only on weekday or clock time because daylight saving and off-cycle republishes are explicitly acknowledged.
- A lockfile exists but the process crashes after external side effects; stage-level idempotency and manifest checkpoints must decide retry behaviour.
- A suppression request arrives after a lead was exported to Google Sheets or GoHighLevel; the spec needs an immediate propagation and reconciliation path.
- A URL redirects from a public website to localhost, metadata IP, file URL, or private address; crawler must refuse it.
- A domain allows homepage but disallows contact pages through wildcard robots rules; crawler must respect wildcard rules.
- A carried-over lead has consent basis expire before export; it must be re-gated every export.
- A phone wash is clear at enrichment time but stale at worklist time; export must require a wash within 30 days.
- A record has no ABN but enters through QBCC; all dedupe, suppression, opt-out, and export logic must key on `lead_id` or licence number as specified.
- Two QBCC licences share one ABN; export must avoid handing the VA the same business twice in one week.
- Legal names identify sole traders and may be personal information even when the record is public.
- Public holiday and recipient timezone calculation can change call eligibility; source of truth must be specified.
- Google Sheets contains personal information and must be treated as an overseas-recipient disclosure, not a harmless export format.

## Open Questions
- None for this planning response; unresolved dependencies are treated as blockers or external gates rather than questions requiring user input.