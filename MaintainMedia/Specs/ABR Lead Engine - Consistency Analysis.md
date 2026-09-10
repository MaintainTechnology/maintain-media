---
title: "ABR Lead Engine - Consistency Analysis"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/001-abr-lead-engine/analysis.md"
source_sha256: 23d0564919b0ee207ef13bd17db3acc5284046e168f066c3fd155c5bf59c4072
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# Specification Consistency Analysis — ABR Lead Engine v4.0
Reviewed 2026-09-08. This is a documentation analysis, not a test of application behaviour.

## Findings and resolutions
| ID | Severity | Original issue | Final resolution |
|---|---|---|---|
| A1 | High | Unsubstantiated legal/revenue/pricing certainty | Official source checks; R23/R27/R40; unsupported claims withdrawn |
| A2 | High | Date-only snapshots and incoherent publication pairing | R2-R8 content identity, coherent inventory and atomic promotion |
| A3 | High | Weekly opt-out update and stale exported permission | R24-R25 live authority and synchronous durable suppression |
| A4 | High | Indefinite versus finite retention | R29 single finite schedule, erasure/restore controls |
| A5 | Medium | Non-transitive cross-source rank ties | R14 one score/time/UUID total order |
| RV-01 | Medium | Spreadsheet edits mistaken for total work | R38; operator_activity ledger; T050 includes calls/research/wash/admin |
| RV-02 | Medium | Older permission pass could survive later negative | R21 assessment sequence/current pointer; model and interface aligned |
| RV-03 | Medium | Undefined identity freshness | R16 current exact business/domain identity90d and QBCC review30d |
| RV-04 | Medium | Cancellation resolution contradicted permanent opt-out | R25 reason-specific resolution; opt-out/complaint remain blocked |
| RV-05 | Medium | Wrong business/domain evidence could grant permission | R20 composite identity/lead/domain provenance relationship |
| RV-06 | Medium | Tasks absent at first review | 59 unique unchecked tasks; all43 FRs mapped below |

Independent reviewer re-read marked all20 custom writing criteria satisfied; details in
[[ABR Lead Engine - Reviewer Notes|reviewer-notes.md]]. No unresolved substantive design finding from that pass.
The Council independently scores a frozen supplied document package; see [[ABR Lead Engine - Council Review|council-review.md]].

## Coverage
| Requirement | Has task | Task IDs | Detailed acceptance source |
|---|---|---|---|
| FR-001 | Yes | T002, T003, T008, T010, T013, T058 | Canonical R1 |
| FR-002 | Yes | T015, T036, T038 | Canonical R2 |
| FR-003 | Yes | T035, T036, T044 | Canonical R3 |
| FR-004 | Yes | T035, T036 | Canonical R4 |
| FR-005 | Yes | T035, T037, T044 | Canonical R5 |
| FR-006 | Yes | T037, T038, T044 | Canonical R6 |
| FR-007 | Yes | T043, T044, T053 | Canonical R7 |
| FR-008 | Yes | T035, T039, T044 | Canonical R8 |
| FR-009 | Yes | T004, T040, T041, T044 | Canonical R9 |
| FR-010 | Yes | T017, T042 | Canonical R10 |
| FR-011 | Yes | T017, T042 | Canonical R11 |
| FR-012 | Yes | T014, T015, T024, T026, T032 | Canonical R12 |
| FR-013 | Yes | T005, T014, T016, T048 | Canonical R13 |
| FR-014 | Yes | T006, T017, T026 | Canonical R14 |
| FR-015 | Yes | T022 | Canonical R15 |
| FR-016 | Yes | T018, T019, T025 | Canonical R16 |
| FR-017 | Yes | T018, T020 | Canonical R17 |
| FR-018 | Yes | T009, T021 | Canonical R18 |
| FR-019 | Yes | T006, T011, T012, T022 | Canonical R19 |
| FR-020 | Yes | T005, T007, T021, T026 | Canonical R20 |
| FR-021 | Yes | T005, T007, T010, T023, T026 | Canonical R21 |
| FR-022 | Yes | T025, T026 | Canonical R22 |
| FR-023 | Yes | T006, T024, T025, T026 | Canonical R23 |
| FR-024 | Yes | T006, T028, T031, T034 | Canonical R24 |
| FR-025 | Yes | T009, T016, T028, T029, T030, T034, T047 | Canonical R25 |
| FR-026 | Yes | T005, T008, T009, T029, T034, T056 | Canonical R26 |
| FR-027 | Yes | T010, T013, T023, T030, T058 | Canonical R27 |
| FR-028 | Yes | T013, T032, T046 | Canonical R28 |
| FR-029 | Yes | T013, T033, T034, T056 | Canonical R29 |
| FR-030 | Yes | T003, T010, T013, T058 | Canonical R30 |
| FR-031 | Yes | T027, T047 | Canonical R31 |
| FR-032 | Yes | T006, T028, T045, T046, T047 | Canonical R32 |
| FR-033 | Yes | T006, T045, T048, T049 | Canonical R33 |
| FR-034 | Yes | T027, T050, T052 | Canonical R34 |
| FR-035 | Yes | T043, T053, T054, T056 | Canonical R35 |
| FR-036 | Yes | T001, T039, T055, T058 | Canonical R36 |
| FR-037 | Yes | T002, T007, T012, T018, T026, T034, T044, T045, T054, T057, T058, T059 | Canonical R37 |
| FR-038 | Yes | T050, T051 | Canonical R38 |
| FR-039 | Yes | T001, T003, T052, T056 | Canonical R39 |
| FR-040 | Yes | T004, T013, T041, T042, T058 | Canonical R40 |
| FR-041 | Yes | T004, T005, T038, T043, T044, T057, T059 | Canonical R41 |
| FR-042 | Yes | T002, T020, T048 | Canonical R42 |
| FR-043 | Yes | T057, T059 | Canonical R43 |

## Acceptance coverage
- US1/SC002/003: T014-T027 define pilot identity, qualification, evidence and allowed/blocked export tests.
- US2/SC004: T028-T034 define immediate opt-outs, current action checks and restore races.
- US3/SC001: T035-T043 define coherent snapshots, events, deterministic rules and recovery tests.
- US4/SC008/009: T044-T051 define private worklist, CRM/outcomes and measured pilot decisions.
- US5/SC005: T011-T012 budget reservation and concurrency fixtures.
- US5/SC006/007: T052-T059 capacity, operational recovery and handover evidence.
Implementation outcomes and commercial pilot measures remain unchecked/pending.

## Constitution review
Five principles applied: evidence before claims; authoritative permission/suppression;
deterministic recovery; bounded operations; traceable acceptance. No unresolved conflict identified.
Feature requirements contain business outcomes; language/framework choices are in the technical plan.
Current gate states are PENDING and production capability switches OFF.

## Metrics and limits
43 requirements,59 unique unchecked tasks,43/43 mapped (100%). No unknown requirement IDs.
No application implementation, live law/source clearance or performance acceptance is asserted.
Rule recovery or explicit replacement, accounts, current pricing, approval evidence, capacity and
actual pilot outcomes remain genuine release dependencies. Synthetic build work can begin.

## Next action
Start the scoped fixture build with the unchecked tasks; keep production adapters disabled until
the relevant release gates have evidence. The post-implementation converge command has not run.

## Final independent adjudication

The corrected v4.0 received 9.3/10 (weighted 9.275) from the native fallback judge.
No remaining substantive documentation blocker was identified. The final contracts distinguish
email relevance from phone checks, opaque retained group identity from erased active aliases,
and content artifacts from publication occurrences. The A-to-B-to-A recurrence fixture prevents
historical deduplication from losing real changes; erased-token key retirement preserves opt-outs.
These are written obligations for future tests, not executed application evidence.
See [[ABR Lead Engine - Council Review|the Council review]] for prior scores, method and limitations.
