---
title: "ABR Lead Engine - Final Judge"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "llm-council/runs/20260908-abr-adjudication/judge.md"
source_sha256: e4b99f17d7ea6db72733b9c6a9026a648ec90f6837235cca13dac12c14553fb2
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# Scores

**Independent specification score: 9.3/10 (unrounded weighted total 9.275).** Reviewed 8 September 2026, specification v4.0 and constitution v1.0.0. This is a **native fallback judge** following the earlier CLI Council reports' 8.6 scores and a capacity failure in the CLI judge. It is not a claim that all models independently awarded 9.3 or reviewed this corrected revision.

| Dimension | Weight | Score / 10 | Weighted contribution |
|---|---:|---:|---:|
| Correctness and evidence | 25% | 9.4 | 2.350 |
| Requirements and acceptance | 20% | 9.3 | 1.860 |
| Architecture and data integrity | 20% | 9.2 | 1.840 |
| Privacy, security and operability | 20% | 9.3 | 1.860 |
| Scope, delivery and traceability | 15% | 9.1 | 1.365 |
| **Total** | **100%** | **9.275 → 9.3** | **9.275** |

The package is sufficiently defined for scoped synthetic implementation planning. **No remaining substantive documentation blocker was identified in the final reviewed text.** Production gates remain pending. The score concerns written requirements and design, not implemented behaviour, legal clearance, vendor readiness or benchmark results.

Review basis: canonical specification, constitution, source checks, feature spec/plan/data model/research/tasks/quickstart/analysis, interfaces, precision contract and both checklists. The two anonymous reports were treated as suggestions, not authority. `council-review.md` was not read. After the final correction, `python tools/validate_abr_docs.py` exited 0: 43 requirements, 59 unchecked build tasks, 43/43 mapped requirements. This verifies document structure and links; it does not prove the proposed acceptance tests pass.

Final source SHA-256 references:

- Canonical: `08e5585d15f07f8f7301dda9d73e7c153722fed74e9f3eb2cc3a90ff86bc7b5a`.
- Data model: `b099e0460f04ae57cb4f15a03479caa6cefee986a832105154ed4a90c31c44f6`.
- Precision contract: `973b16b3c12f6b774be673d77cabe47020c1320a6ae068b6cc93ff44b12504c1`.

# Comparative Analysis

Both earlier reports correctly value source integrity, human permission assessment, synchronous suppression, finite retention, bounded spending and staged delivery. Their source/evidence cautions remain relevant to release. Several proposed corrections are already present in the current package and should not be charged again as unresolved design defects:

- `contracts/precision.md`, Publication inventory, requires approved exact source mapping, rejects null-equality as generation proof, and holds `GENERATION_UNPROVABLE` without an operator bypass. Missing publisher evidence is an explicit live-source dependency with safe acceptance behaviour.
- The Rule recovery section specifies `CLASSIFIER_DISABLED`, provenance, replacement approval and fixture evidence. An absent legacy extractor is neither fabricated nor represented as an existing application deliverable.
- `contracts/interfaces.md`, action-intent/consume and CRM sections, already define latest-pointer reads, both suppression/consumption orderings, external in-flight limits and uncertain-create reconciliation.
- Precision sections explicitly define DNS pinning, prepaid usage accounting, A$0 automatic procurement authority, staging cleanup and bounded capacity admission. Recommending these as wholly missing is obsolete.
- Canonical R1/R38/R42 and the tasks' implementation boundary explicitly separate the synthetic foundation, live QBCC pilot and later ABR expansion. Proposed `abr_engine/` files are valid future deliverables.

Credit is withheld from perfect scores because the package remains demanding to maintain across several normative documents. Acceptance obligations are concrete but distributed, some API storage/channel terminology needs editorial consolidation, and exact implementation schemas and operational proofs remain future deliverables. Those are bounded specification-maintenance and precision limitations, not deductions merely for closed production gates.

# Missing Steps

**Documentation blockers: none identified after the verified corrections.** The following remain release evidence, not missing design decisions:

- G1: qualified source, collection, notices, harvesting, retention and channel-policy approval.
- G2: approved live source mapping/schema fixtures and recovered or explicitly replaced trade rules.
- G3/G7: implemented security controls, AU hosting commitments, capacity results, restore/key drills, acceptance evidence and exact release revision.
- G4/G5: real wash format/account, certified action integration, current vendor terms/countries and tested CRM mappings/reconciliation/suppression.
- G6: measured pilot outcomes and the owner's ABR expansion decision.

The defined safe state is synthetic fixtures and disabled corresponding production capabilities. None of these gates can be marked passed by this review.

# Contradictions

The final read verifies that email relevance is a stored reviewer assessment; phone follows script/wash/calling policy without an invented email basis. Persistent restriction/deletion/CRM identity is an opaque group UUID, with erased active identifiers and retained minimal HMAC aliases. Content hashing now uses the exact uncompressed-member projection, excluding retrieval and compression metadata.

This judge also found a genuine additional defect during review: historical A→B→A content recurrence could collide with globally unique snapshot content and be discarded as a no-op. The final text resolves it in canonical R3/R8, data-model `source_content`/`source_snapshot`, precision Publication inventory, plan Seal, T038 and quickstart. Artifact deduplication is separate from occurrence UUIDs; no-op is current-cursor-only; fresh evidenced recurrence produces B→A events once; retry preserves occurrence identity. The named `abr_a_b_a_then_retry` fixture includes stale-cache rejection.

The final text also resolves token-only suppression key retirement: canonical R26 and the precision/model contracts prohibit HMAC-of-HMAC migration and premature destruction of a dependent old key. Restricted lookup-only keys preserve erased-identity matching; compromise freezes affected actions. The erasure-then-rotation fixture explicitly covers this.

No unresolved substantive contradiction was found. Minor wording such as plan “snapshot identity hashes” can be aligned to “content identity,” and its general dual-write rotation description can point directly to the precise active-write/prior-lookup rule.

# Improvements

These are non-blocking editorial/build-handoff improvements:

1. Add a short contract reading index and link each exact scenario to its eventual test identifier when T057 is implemented. Preserve the existing requirement/task authority rather than duplicating it.
2. Use “content artifact identity” versus “publication occurrence UUID” consistently in examples. Make the phone API-to-mobile/landline storage mapping explicit in generated schemas.
3. During implementation review, demonstrate sorted multi-group merge/endpoint locking as well as the existing single-group race fixtures; retain common lock authority across all writers.

# Final Plan

Accept this revision as the documentation baseline for the already-defined fixture build. Preserve prior Council scores and failed-run evidence separately. Keep all 59 implementation tasks unchecked until their actual evidence exists. Implement foundation, synthetic pilot, suppression and minimal outcome recording in the documented dependency order; retain live ABR gating and all source/vendor/policy approvals. Run independent build review and relevant tests against the implemented revision. This review itself implements no application and opens no production gate.
