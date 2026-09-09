# Build and review — ABR Lead Engine v4.0

**Offline engineering checks: PASS. Full-spec acceptance: FAIL / incomplete.** The runnable synthetic implementation passed the checks below. Seven original implementation/release obligations remain partial or externally dependent; these are not waived by the 92/100 engineering score.

## Verified version and operation

- Frozen source/document tree SHA256: `3c2ba7ed46ead9fdf8dc3476f9b6f85159791f2238f6c02a6b1ada573e7f16ae`. Exact file hashes and commands: [verification receipt](verify-eb8385d049dc4342ba0531603b17d623/result.json).
- `408 passed`, 0 failures, 0 errors, 0 skipped. Actual isolated PostgreSQL 16, external-network-denying fixtures, boundary faults and real composite constraints. Frozen installation, Ruff, mypy and document/vault checks passed with unchanged source throughout.
- A separate fresh virtual environment installed the same lock and ran configuration validation. Hosted GitHub Actions has not been executed in this task.
- Current run `b0fbe8ea-3422-404a-84d1-39e0a55ff9df` completed with 1 selected business, 1 blocked/deferred and 0 live calls. [Running API and browser evidence](runtime-review-final.md) records the actual permitted report, mobile-width review and 0.298584s HTTP opt-out commit acknowledgement.
- [Native PostgreSQL backup/restore](native-backup-drill.json), [independent README recovery](handover-drill.md), [mock downstream stop](propagation-drill-444cf383-b386-46a9-bc93-a4df3e369a22.json) and [capacity comparisons](performance-thread-review.md) have separate receipts and explicit limits.

After this successful unchanged-tree check, only acceptance/task/status documentation and generated vault mirrors were reconciled. `final-content-closure.json` records the final tree hash and verifies that every runtime, configuration, test and workflow file still equals the tested revision.

## Requirement-by-requirement evidence and limits

Each row links the canonical item to executed engineering scenarios. Scope qualifications are part of the verdict: fixture evidence never substitutes for live approval, actual source/vendor contracts, AU deployment or a measured commercial pilot. The full file map is [requirements.json](../../tests/requirements.json).

| Requirement | Implemented/tested scope and remaining obligation | Executed scenario files |
|---|---|---|
| R1 / FR-001 — Scope, actors and release gates | Synthetic default and live capabilities fail closed; production G1-G7 pending | `test_enrichment.py`, `test_control_review_regressions.py` |
| R2 / FR-002 — Source evidence | Source manifests and identity fixtures; real dated source smoke pending | `test_sources.py`, `test_pipeline.py`, `test_discovery.py` |
| R3 / FR-003 — Coherent ABR generation | Generation coherence, current-only noop and fresh recurrence; actual publication discovery approval pending | `test_sources.py`, `test_abr_recovery.py`, `test_discovery.py` |
| R4 / FR-004 — Bounded downloads | HTTPS/resume/length/archive rejection via injected transport | `test_sources.py`, `test_discovery.py` |
| R5 / FR-005 — Streaming parser | Streaming XML schema/count/canaries; full XML scale on target host pending | `test_sources.py`, `test_publication_quality.py`, `test_abr_recovery.py` |
| R6 / FR-006 — Immutable snapshots | Immutable artifact ownership, readback and promotion | `test_pipeline.py`, `test_abr_recovery.py` |
| R7 / FR-007 — Atomic promotion and recovery | Atomic CAS and crash replay | `test_pipeline.py`, `test_abr_recovery.py` |
| R8 / FR-008 — ABR events and time meaning | Seven exact observed event types including disappearances | `test_sources.py`, `test_abr_recovery.py`, `test_diff_review.py` |
| R9 / FR-009 — Deterministic classification and missing rules | Deterministic synthetic classifier; actual 30 rules and precision review pending | `test_sources.py` |
| R10 / FR-010 — Tiers | ABR/QBCC tiers without revenue inference | `test_sources.py`, `test_qualification_policy.py` |
| R11 / FR-011 — Geography and dates | Geography and completed calendar months | `test_sources.py`, `test_enrichment.py` |
| R12 / FR-012 — QBCC | QBCC collapse/ABN/address/age and current licence review | `test_sources.py`, `test_control_review_regressions.py` |
| R13 / FR-013 — Identity and deduplication | Canonical alias merge and restriction union | `test_merge.py`, `test_merge_review_regressions.py`, `test_duplicate_hints.py`, `test_merge_cancellation_resolution.py` |
| R14 / FR-014 — Durable queue and ranking | 200-to60, fairness, queue expiry and current gate | `test_sources.py`, `test_control.py`, `test_qualification_policy.py` |
| R15 / FR-015 — Refresh policy | Durable lease/reservation/apply recovery, policy/quarantine rechecks and90-day merged-family cooldown; actual providers separately gated | `test_enrichment.py`, `test_enrichment_worker.py`, `test_enrichment_worker_review.py` |
| R16 / FR-016 — Own-domain identity | Own-domain exact or reviewed corroboration, current identity | `test_enrichment.py`, `test_control_review_regressions.py` |
| R17 / FR-017 — Safe, bounded crawl | Bounded static crawl, pinned public DNS/TLS and robots | `test_crawl_safety.py` |
| R18 / FR-018 — Endpoints | Endpoint normalisation/selection/verification separation | `test_enrichment.py`, `test_control_review_regressions.py` |
| R19 / FR-019 — Spend authority | Atomic reservations, dated FX, cap and uncertain charges | `test_control.py`, `test_control_review_regressions.py`, `test_enrichment_worker.py`, `test_acceptance_matrix.py` |
| R20 / FR-020 — Provenance integrity | Actual PostgreSQL deferred/composite provenance | `test_control_review_regressions.py`, `test_acceptance_matrix.py` |
| R21 / FR-021 — Permission assessment | Latest sequence, actual express consent, inference limbs | `test_control_review_regressions.py`, `test_control.py`, `test_acceptance_matrix.py` |
| R22 / FR-022 — Export decision | Allowed/blocked current export and masking | `test_control.py`, `test_outputs.py`, `test_final_report_review.py` |
| R23 / FR-023 — Manual DNCR wash | Exact manual-wash receipt and latest observation | `test_control_review_regressions.py`, `test_acceptance_matrix.py` |
| R24 / FR-024 — Action-time authority | Single-use current action/actor binding and races; sender certification pending | `test_control.py`, `test_api_assignments.py` |
| R25 / FR-025 — Immediate suppression | Committed group/endpoint optout, future aliases and recovery | `test_control.py`, `test_merge_review_regressions.py`, `test_retention.py`, `test_propagation.py` |
| R26 / FR-026 — Security and audit | Scopes, key custody/rotation/dependency and audit | `test_control_review_regressions.py`, `test_api_assignments.py`, `test_read_quarantine.py`, `test_final_report_review.py` |
| R27 / FR-027 — Law and notices as reviewed policy | Policy capability fence; qualified legal review pending | `test_control_review_regressions.py` |
| R28 / FR-028 — Calling and downstream contracting | Confirmed timezone/calendar/wash and invitation state; Part2 excluded | `test_control_review_regressions.py`, `test_enrichment.py` |
| R29 / FR-029 — Finite retention and restoration | Finite retention, erased profile, restricted archive, native backup/replay | `test_retention.py`, `test_backup.py`, `test_merge_evidence_retention.py`, `test_cost_evidence.py`, `test_erasure_metrics.py` |
| R30 / FR-030 — Residency | Unknown live processor approvals denied; AU contract pending | `test_control_review_regressions.py` |
| R31 / FR-031 — Worklist usability | Private escaped report and executable Sheets CSV contract; browser evidence separate | `test_outputs.py`, `test_api_assignments.py` |
| R32 / FR-032 — Write-back | Version/idempotency/closed outcomes and edit bridge | `test_control.py`, `test_api_assignments.py`, `test_outputs.py` |
| R33 / FR-033 — CRM approval and outbox | Typed mappings, approval, provider uncertainty and suppression race; live vendor sandbox pending | `test_crm_recovery.py`, `test_propagation.py` |
| R34 / FR-034 — Reports and metrics | Immutable summaries, real DB metrics, explicit unknown denominators/costs | `test_outputs.py`, `test_operational_summary.py`, `test_pipeline.py`, `test_summary_review.py`, `test_cost_evidence.py`, `test_erasure_metrics.py` |
| R35 / FR-035 — Ops and alarms | Alarm inventory, durable locks and scheduler templates; Linux drill pending | `test_outputs.py`, `test_pipeline.py`, `test_ops_monitor.py` |
| R36 / FR-036 — Capacity and stack | 20.5M output-bearing resource evidence under ops/acceptance; target host certification pending | `test_outputs.py`, `test_sources.py` |
| R37 / FR-037 — Test/release evidence | Actual isolated PostgreSQL16 and injected boundary failures | `test_control_review_regressions.py`, `test_pipeline.py`, `test_acceptance_matrix.py` |
| R38 / FR-038 — Commercial pilot | Dated cohort metrics; four/eight-week live pilot pending | `test_outputs.py`, `test_operational_summary.py`, `test_cost_evidence.py`, `test_erasure_metrics.py` |
| R39 / FR-039 — Handover | CLI and recovery commands; independent handover evidence separate | `test_pipeline.py`, `test_backup.py` |
| R40 / FR-040 — Factual accuracy | Cautious signal wording and synthetic labels; release facts recheck pending | `test_outputs.py`, `test_sources.py` |
| R41 / FR-041 — Migration and authority | Parser rebaseline, ordered migrations, dual-key retention | `test_abr_recovery.py`, `test_retention.py`, `test_erasure_metrics.py`, `test_discovery.py` |
| R42 / FR-042 — Exclusions | No sending/dialling/procurement; fixture output only | `test_crawl_safety.py`, `test_pipeline.py` |
| R43 / FR-043 — Traceability | This requirement map and verify.py; scores distinct from full specification release | `test_pipeline.py` |

## Definition of done, edge cases and exclusions

Local engineering obligations verified: coherent baseline/changes/republish/A-B-A/rebaseline, seven materialised event types, field-fill hold before promotion, exact alias/group deduplication, fair 60-business queue, permitted and blocked contact projections, latest permission/wash authority, immediate opt-outs and dispatch races, durable budgets/uncertain billing/month rollover, row-sort/idempotency, CRM uncertainty and downstream stop confirmation, finite erasure/key preservation/native restore quarantine, source/artifact crash recovery, valid cost/time evidence, minimal retained cohort/outcome/activity facts after erasure, scoped metric holds, corrected merged-cohort attribution, composed publisher discovery/download/revalidation and documented operating commands. Full specification acceptance still requires the seven tasks below and G1-G7.

Constraints respected in local execution: Python 3.12, PostgreSQL 16, bounded DuckDB/Arrow/Parquet, static crawl and small authenticated API. The selected three-thread/400k-partition diff materialized 1.435M events from the 20.5M synthetic universe in 58.42s and 103.95s. Exact semantic output equality passed; the paired two-thread repeat took 116.49s. Diff sampled RSS stayed below 1GiB and no guard fired. Cache/scheduling were uncontrolled; 60s stretch compliance is not consistent. Full source-to-report <=6h and production-host capacity remain unproven.

No out-of-scope sending, calling, payments, purchased lists, Maps/Places enrichment, social messaging or new dashboard was built. Live adapters remain blocked. There is no new confirmed actionable high/critical local finding after the bounded reviews and final regression run. Reviews were split among builders; their ownership and limits are disclosed in each review artifact, not presented as external certification.

## Remaining fixes/evidence for full-spec acceptance

- **T041:** Pending: recover the actual legacy 30-rule corpus or obtain an approved replacement and 100-record precision review.
- **T051:** Pending: four measured QBCC weeks, owner expansion decision and eight-week cohort outcomes.
- **T053:** Partial: Linux systemd installation, access, timer and overlap drill not executed; templates and local locks tested.
- **T055:** Partial: selected three-thread diff varied from 58.42s to 103.95s, so 60s stretch is not consistently met; full XML pipeline/AU host/retained WAL and backup bounds need target-host evidence.
- **T058:** Pending: applicable G1-G7 policy/source/vendor/AU infrastructure/pilot approvals.
- **T062:** Partial: PG 16 native CI setup and bounded verification code exist; hosted Linux execution has not been observed.
- **T065:** Pending: actual source/rule/provider/wash/host inputs and release authorisation; fixtures cannot satisfy these obligations.

## Score and weakest parts

The rubric preceded implementation. Final local engineering score: **92/100**. Behaviour 23/25, data integrity 19/20, security 24/25, operations 17/20, maintainability 9/10. The missing 8 points are: authentic source/provider integration and actual rule inputs (2); full authentic source-scale evidence (1); production key/access/egress and cross-system certification (1); stretch/complete-pipeline performance, AU/Linux operations and actual live handover/pilot evidence (3); hosted CI execution and external certification (1). These cannot be replaced by more synthetic assertions or a higher score.

[Score trajectory and rewrites](trajectory.md): 68→86→91→92→92→92. The post-pass metrics defect reopened the build and reset the clean-review streak. After its repair, two substantive thread-count rewrites each left the retained engineering score at 92: the one-thread alternative was rejected, and three threads were selected after complete output comparison and timing confirmation. The selected source then passed renewed whole-package verification. Both score gains were 0, below the fixed 2-point margin, with no confirmed high/critical finding remaining in these bounded local reviews. This is a local assessment plateau, not proof that further optimisation is impossible or that full-spec acceptance is complete.
