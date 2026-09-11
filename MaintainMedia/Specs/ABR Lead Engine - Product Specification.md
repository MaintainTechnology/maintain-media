---
title: "ABR Lead Engine - Product Specification"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/001-abr-lead-engine/spec.md"
source_sha256: e0709f310c326258571a49ea58ea1aaaef42f9f7cd0dd41402f5b140e9118e28
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# Feature Specification: ABR Lead Engine

**Feature directory:** specs/001-abr-lead-engine
**Created:** 2026-09-08 Â· **Version:** 4.0
**Scoped policy amendments:** QBCC-PILOT-2026-09-11, WEBSITE-PHONE-PILOT-2026-09-11, GHL-DND-PILOT-2026-09-11 and ABR-EARLY-VALIDATION-2026-09-11, each v1.0.0; product/rule baseline unchanged.
**Status:** live implementation authorised in `abn-leadgen/`; full production acceptance outstanding.
**Input:** Review, improve and record the specification using LLM Council and Spec Kit, then build, run and review it as subsequently requested by the user.
**Authority:** [[ABR Lead Engine|Canonical specification]]. FR-nnn corresponds exactly to Rn;
the canonical requirement contains the complete policy, boundary and acceptance detail.
The feature directory is independent of the existing Git branch; this work did not switch branches.
Current execution evidence and remaining dependencies are in [[ABR Lead Engine - Implementation Status|implementation status]].

## User Scenarios & Testing

### User Story 1 â€” A small, useful contractor pilot (US1, Priority P1)
As a reviewer, I want a list of potential customer businesses with trustworthy identity evidence,
so I can spend my time investigating useful matches instead of a huge unfiltered register.
**Why this priority:** Tests the offer before building the nationwide change feed.
**Independent test:** Import a synthetic contractor publication and produce a reviewed list.
**Acceptance scenarios:**
1. Given mixed licences, missing ABNs and duplicated classes, when the list is prepared, then each
   valid business appears at most once and excluded/unknown records have a recorded reason.
2. Given200 eligible groups, when selection runs, then no more than60 appear, up to10 oldest
   eligible groups receive reserved places, and140 remain queued with eight-week expiry.
3. Given a licence category, when its signal is shown, then wording describes permitted capacity,
   never actual revenue or a promise that the business wants marketing.

### User Story 2 â€” Respect a request to stop (US2, Priority P1)
As a business owner or reviewer, I want an opt-out to stop further controlled contact immediately.
**Why this priority:** A useful list is unsafe if it ignores a person's request.
**Independent test:** Export a synthetic candidate, record an opt-out, then attempt another action.
**Acceptance scenarios:**
1. Given a previously exported contact, when opt-out is acknowledged, then every later controlled
   action is blocked even if its old sheet/CRM row has not yet refreshed.
2. Given a shared endpoint or merged identity, when one endpoint is suppressed, then all relevant
   records are blocked; a restore must not erase that block.
3. Given the control service is unavailable, when an action is attempted, then it remains blocked.
4. Given a valid allowed fixture with fresh evidence, when candidate export runs, then it succeeds
   with an explicit send-time-check label; an always-empty system fails acceptance.

### User Story 3 â€” Understand what changed in the business register (US3, Priority P2)
As the owner, I want reliable newly observed changes so I can test useful business signals.
**Why this priority:** The initial commercial pilot measures value. The separately authorised early ABR validation phase may establish source integrity and matching evidence while that pilot remains unfinished.
**Independent test:** Compare two complete synthetic publications with known changes.
**Acceptance scenarios:**
1. Given a baseline, when the first import completes, then zero ABR lead events are created.
2. Given a new publication containing cancellation/reactivation/GST changes, when comparison runs,
   then each expected event appears once, including multiple different events for one ABN.
3. Given a same-date correction or shifted file boundaries, when import runs, then history is
   distinguishable and no false new businesses arise from file membership.
4. Given a mixed or partial publication, when import fails, then the accepted baseline remains intact.

### User Story 4 â€” Review, hand off and learn (US4, Priority P2)
As a reviewer, I want clear restrictions and safe outcome recording, so we learn what works.
**Why this priority:** Prevents speculative revenue claims and makes the commercial decision measurable.
**Independent test:** Approve a synthetic tier A row, simulate a CRM timeout and edit a reordered list.
**Acceptance scenarios:**
1. Given an uncertain remote create, when retry runs, then it reconciles before creating again.
2. Given a stale row version, when a reviewer edits it, then a visible conflict prevents silent overwrite.
3. Given a booked meeting, when outcomes aggregate, then its business is counted once with the
   predeclared cohort and dated evidence; an invitation is not inferred from the meeting.

### User Story 5 â€” Operate within limits and recover (US5, Priority P2)
As an operator, I want predictable spend, clear alarms and safe recovery without specialist guesswork.
**Why this priority:** A weekly feed must remain affordable and repeatable.
**Independent test:** Inject crashes, concurrent charges, expired policies and a restored backup.
**Acceptance scenarios:**
1. Given insufficient budget, when paid work is requested, then no unreserved charge begins and
   resumable work remains queued.
2. Given a crash around source promotion, when rerun starts, then accepted state and events remain
   consistent and delivery resumes without duplication.
3. Given a backup restored in isolation, when access is reopened, then current opt-outs and erasures
   have been reapplied and overdue personal data removed.

### Edge Cases
Unknown industry/geography/identity/permission; missing ABN; multiple licences per business;
same names for different businesses; shared emails/phones; same-day corrections; changed source
parts; backdated/future dates; zero-change republication; incomplete terms crawl; blocked/redirected
websites; international/invalid numbers; later listed wash after old clear wash; expired permission;
opt-out during delivery; month rollover with pending billing; reordered rows; uncertain remote
creates; stale data beyond retention; lost lock; interrupted restore.

## Requirements

### Functional Requirements
- **FR-001**: The system MUST keep Part1 scope, named roles and production gates explicit; synthetic development works while live integrations remain disabled.
- **FR-002**: The system MUST retain dated source evidence and content identity for every publication.
- **FR-003**: The system MUST accept only complete, coherent business-register publications; detect same-date corrections and no-op republishes.
- **FR-004**: The system MUST recover bounded source downloads without accepting partial or changed content.
- **FR-005**: The system MUST validate every source record, field and declared count within the stated memory bound.
- **FR-006**: The system MUST keep accepted snapshots immutable and distinguish corrections published on the same date.
- **FR-007**: The system MUST promote source state atomically and replay interrupted work without duplicate events or deliveries.
- **FR-008**: The system MUST report newly observed registrations and status/name changes with effective dates separate from observation dates.
- **FR-009**: The system MUST classify deterministically using approved rules; unknown industry and unavailable rule sources remain explicit. The dated early ABR validation amendment permits unapproved shadow predictions for private genuine accuracy review only. Operational qualification requires at least100 real stratified classified-record reviews, independent evidence, per-rule false-positive checks and an exact source/mapping/rules/reviewer-bound result; a declared count or prediction is not proof.
- **FR-010**: The system MUST assign A/B/C qualification tiers without treating registrations or licences as proof of revenue.
- **FR-011**: The system MUST restrict the pilot to QLD and NSW postcodes2450â€“2490; hold unknown geography and invalid age evidence.
- **FR-012**: The system MUST collapse contractor records by licence, retain missing-ABN records and distinguish stale discovery from current licence evidence.
- **FR-013**: The system MUST maintain durable business identity, deduplicate weekly work and carry suppression across aliases.
- **FR-014**: The system MUST rank and retain work fairly with a60-business weekly cap and eight-week active-queue expiry.
- **FR-015**: The system MUST avoid rebilling recent completed discovery, preserve resumable budget interruptions and respect suppression.
- **FR-016**: The system MUST confirm a website belongs to the intended business before using its contact evidence.
- **FR-017**: The system MUST limit website collection and reject unsafe destinations, prohibited pages and incomplete permission evidence.
- **FR-018**: The system MUST normalise endpoints consistently, record verification status and never equate deliverability with permission.
- **FR-019**: The system MUST prevent paid enrichment exceeding A$150 per calendar month, including concurrent requests and uncertain charges.
- **FR-020**: The system MUST tie every contact and assessment to evidence for that exact record and channel.
- **FR-021**: The system MUST record evidence-backed permission decisions with unknown/fail states, separate express/inferred bases and expiry.
- **FR-022**: The system MUST export only reviewed candidates with clear restrictions; a worklist label cannot authorise contact.
- **FR-023**: The system MUST require the latest valid manual wash result and block outdated, listed, erroneous or mismatched phone evidence.
- **FR-024**: The system MUST require a fresh check at the actual contact attempt; block stale, replayed or mismatched approvals.
- **FR-025**: The system MUST acknowledge opt-outs only after durable blocking, propagate them promptly and preserve them through restoration.
- **FR-026**: The system MUST authenticate each actor, restrict personal-data access and audit sensitive actions and policy changes.
- **FR-027**: The system MUST require recorded collection, notice and channel policy with accurate source disclosure before live personal-data use. The canonical QBCC-PILOT-2026-09-11 and WEBSITE-PHONE-PILOT-2026-09-11 amendments, each v1.0.0, separately permit the user's delegated-owner decisions within their fixed scopes and expiry, explicitly record that no adviser assessment was obtained, and preserve separate source/security/release evidence. The website amendment permits manually reviewed Australian mobile/landline evidence only, prohibits automated email extraction/indexing, requires a verified public notice plus genuine per-site terms/domain/licence evidence, and needs its own website capability and hash-bound channel policy. Its retention policy enforces 24-hour pending requests, 90-day captures and no seven-year selected-evidence archive. The separate GHL-DND-PILOT-2026-09-11 v1.0.0 owner record supplies only its named phone-only CRM onward purpose/country authority, preserves individual R33 approval and phone checks, and requires its own actual account evidence and public notice readback. The separate ABR-EARLY-VALIDATION-2026-09-11 v1.0.0 approves manual public bulk source validation, complete baseline/comparison and genuine private rule review before the commercial pilot completes, with its own ABR notice, source/security/release evidence, validation-only enforcement and expiry; it does not approve ABR contact extraction or vendor disclosure. All other scopes retain ordinary R27/G1 review.
- **FR-028**: The system MUST show and recheck approved recipient-time calling windows; preserve invitation evidence for downstream contracting.
- **FR-029**: The system MUST apply finite purpose-based retention, erasure and restoration controls to each artifact class.
- **FR-030**: The system MUST record actual processing locations and approved overseas recipients, including support access.
- **FR-031**: The system MUST give reviewers a private, understandable, accessible worklist and source-age/context information.
- **FR-032**: The system MUST accept conflict-safe, identity-bound outcome updates and process opt-outs immediately.
- **FR-033**: The system MUST push only human-approved tier A records to CRM with duplicate-safe recovery and suppression propagation. The separately authorised GHL-DND-PILOT-2026-09-11 v1.0.0 limits the named account to one eligible phone, DND enabled and current all-Draft workflow inventory before every mutation. It requires independent row-version approval and existing phone checks, its own CRM G1/G3/G5/G7, exact configuration/installation evidence and continuing minimum-removal authority; no outreach, email transfer or implied extension of earlier source decisions.
- **FR-034**: The system MUST report reproducible counts, denominators, costs, failures, source ages and cohort outcomes.
- **FR-035**: The system MUST give operators timely actionable alarms, safe locks and documented recovery for every failure class.
- **FR-036**: The system MUST measure the stated capacity/resource budgets rather than promise performance from historical claims.
- **FR-037**: The system MUST require positive, negative, recovery and isolated integration evidence before technical release.
- **FR-038**: The system MUST run the measured four-week contractor pilot and assess cohort value over eight outreach weeks. The canonical ABR-EARLY-VALIDATION-2026-09-11 v1.0.0 prospectively permits private ABR source validation, baseline/comparison and real matching review before those four weeks, under the user's separate delegation. It does not certify pilot completion, commercial results, precision, capacity or operational qualification; G6 must record its limited sequencing meaning and expiry.
- **FR-039**: The system MUST enable another developer and operator to run and recover the system from the written handover.
- **FR-040**: The system MUST label facts, assumptions and historical evidence accurately and recheck changing external conditions.
- **FR-041**: The system MUST version changes and rebaselines without false business events; detect drift between documents.
- **FR-042**: The system MUST keep sending, payments, client delivery and unapproved data sources outside Part1.
- **FR-043**: The system MUST map each requirement to implementation work and acceptance evidence without confusing document checks with completion.
### Key Entities
- **Publication:** one evidenced, coherent source generation with its source age and acceptance status.
- **Business group and lead:** stable work identity and its ABN/licence aliases.
- **Observed event:** a source change with before/after values and separate observation/effective dates.
- **Candidate:** ranked work with qualification, queue state and expiry.
- **Contact and provenance:** endpoint plus evidence linking it to the correct business/channel.
- **Permission decision:** reviewed basis, scope, evidence, expiry and unknown/blocked outcomes.
- **Suppression:** durable business/endpoint restriction that overrides other eligibility.
- **Wash receipt:** evidence about a particular checked batch, its results and freshness.
- **Worklist and outcome:** versioned reviewer work and dated commercial observations.
- **Delivery intent:** one approved hand-off with reconciliation state.
- **Spend reservation:** funds held or settled for one billable operation.
- **Policy/release decision:** accountable owner, reason, version and evidence.

## Success Criteria

### Measurable Outcomes
- **SC-001:** Each accepted fixture publication produces exactly its expected events once; incomplete
  or incoherent publications never change the accepted baseline.
- **SC-002:** Each worklist has at most60 distinct business groups, follows its ten-slot age reservation
  and accounts for every unselected eligible group.
- **SC-003:** Every permitted candidate is traceable to exact identity/contact evidence; all negative
  permission/suppression fixtures block and the positive candidate fixture passes.
- **SC-004:** Acknowledged opt-outs block later controlled actions immediately after commit; target
  acknowledgement<=5s and available remote projections update<=60s.
- **SC-005:** Reserved plus settled enrichment never exceeds A$150 in the configured month, including
  retries, concurrency and unknown billing outcomes.
- **SC-006:** Full processing finishes within6h without memory/disk exhaustion on the approved host;
  the60s large-diff target is measured separately and labelled stretch until demonstrated.
- **SC-007:** Another developer completes the fixture cycle and recovery unaided using the handover.
- **SC-008:** Over two consecutive pilot weeks, measure all reviewer/VA work using explicit time
  records; assess the two-hour target and adjust list size/staffing if it fails.
- **SC-009:** At weeks4/8 the owner can see distinct contacted groups, attempts, booked/held meetings,
  costs and sample sizes by cohort and make the predeclared expansion/pause decision.
SC-008/009 require a live pilot and remain pending; they cannot pass from document inspection.

## Assumptions
- The user has authorised implementation towards live operation; current execution and remaining production dependencies are recorded in implementation status.
- QLD/northern NSW pilot, human CRM approval, manual DNCR wash and A$150/month are explicit defaults.
- The intended legacy rule source must be recovered or explicitly replaced before production classification.
- Legal/policy, processor, account, capacity and release evidence are deployment dependencies,
  not reasons to fabricate evidence or prevent synthetic engineering.
- The system provides no automatic authority over external senders that have not integrated its live gate.

## Clarifications
### Session 2026-09-09
The user authorised work towards live operation and explicitly approved retaining all
30 recovered trade categories, QLD plus NSW postcodes 2450â€“2490, QBCC Categories 1â€“2
and a maximum of 60 businesses weekly. This is targeting-direction approval only.
The exact rule corpus is now recovered; real precision sampling, source/privacy and
vendor decisions, production hosting and the measured pilot remain outstanding.
The earlier missing-file/defaults statements below describe the original review.

### Session 2026-09-08
Optional scope/stack/budget/pilot intake was offered. No reply is recorded; the defaults above are
planning assumptions, not user-confirmed answers. Remaining approval-dependent choices are
enumerated as production gates in the canonical spec. No silent production enablement is allowed.
