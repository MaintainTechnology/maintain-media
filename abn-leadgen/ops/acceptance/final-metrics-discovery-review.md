# Final independent metrics and discovery review

Reviewed 2026-09-09 by the source/pipeline agent, independently of the agents implementing these changes. Verdict: no remaining confirmed high or critical defect in this bounded review of R29/R34/R38 metric erasure and R2/R3/R4 offline discovery composition.

## Scope and boundaries

Read the relevant requirements in `specs/abr-lead-engine.md`, migration024, minimal pilot fact retention/projection, summary membership and cost attribution, profile-erasure hooks, discovery composition and focused regression tests. Read the existing download/ZIP/parser composition to check the discovery boundary. The costs change reviewed here is the retained-cohort existence lookup; broader cost review is recorded separately.

This reviewer made no source or test edits and ran no test suite, migration, live discovery, provider request or deployment. The only authored artifact in this review is this acceptance note. Test results below are explicitly reported by the implementing agents, not independent executions. The parent owns final combined verification.

## Findings closed by implementation and reread

- Profile erasure previously removed historical selected-cohort/outcome facts. Minimal retained facts now preserve original selection, dated outcome deltas and activity attribution without retaining outcome notes or endpoint fields.
- Invalid preselection cumulative attempts previously changed later valid attempt deltas during archival. Archive calculation now excludes those observations before advancing the valid counter, matching the summary projection.
- Expired archived activity could fall back to surviving live activity and reappear. The archive marker excludes fallback, while retention removes expired original activity rows.
- Merged groups could allocate the same activity to both raw selected tiers. Cost eligibility now uses the chosen first membership per canonical group and cohort.
- A correction moving between cohorts could lose its predecessor during per-cohort filtering. Complete-history correction leaves are resolved before cohort allocation; complete history remains subject to interval validation.
- Metric-specific holds briefly blocked full profile erasure. Those hold types are absent from `_profile_held`; only the scoped minimal facts remain held. Tests assert that identifying lead/outcome records are still erased.
- Old correction ancestors and orphan originals needed finite, dependency-aware cleanup. Retention preserves ancestors needed by recent corrections, removes complete expired chains iteratively, and prunes unarchived expired leaves before the retained-chain pass. The all-expired-at-first-erasure regression checks deletion in the first execution and zero historical worked seconds afterward.
- A closed-window summary could compute negative propagation age from later-created rows. The query now restricts observations to rows created by the declared window end.
- Discovery initially omitted metadata HTTP-validator absence. Its immutable evidence now explicitly records `metadata_response_validators` as `{status: unavailable, etag: null, last_modified: null}`. The positive test checks that exact state, and the reader contract documents that ZIP headers are not metadata response headers.

## Discovery conclusions and retained limits

The offline composition validates the exact publisher field mapping and complete inventory, bounds retries and cumulative downloaded bytes, binds available response validators and hashes, re-reads metadata before parsing, uses actual ZIP/XML validation, checks inner generation, and writes an exclusive publication manifest. Generated local filenames prevent publisher labels from controlling paths. Failure does not promote any source cursor.

Production mode rejects before I/O. The injected metadata reader must enforce its supplied network byte/time bounds; the returned object is bounded again by composition. A future authorised live adapter must capture actual metadata response headers and use a reviewed real publisher schema. These remain explicit external integration limits, not evidence of a live smoke test or production readiness.

## Reported focused verification

- Metrics implementer: 13 actual PostgreSQL focused tests passed in 35.06 seconds, comprising eight erasure cases, four cost tests and one operational-summary test; scoped Ruff and mypy clean.
- Discovery implementer, after validator-absence correction: 58 discovery/source tests passed in 4.52 seconds; scoped Ruff and mypy clean.

The reviewer inspected the final positive and negative regression source, including all-expired correction chains, merged tiers, cross-cohort corrections, preselection attempts, scoped holds, metadata drift, actual interrupted download resume, cumulative unknown-length caps and live-mode refusal.

## Inspected file SHA-256

Paths are relative to `abn-leadgen/`. These identify the reviewed working-tree bytes, not a claim that the shared checkout was committed or clean.

| File | SHA-256 |
| --- | --- |
| `src/abr_engine/ops/pilot_facts.py` | `dbdca9c373d140724ab259ff68866ec9a393e23466dfca9fba4d4107f95e2a0a` |
| `src/abr_engine/ops/summary.py` | `0bb500244f8053635d0a3d8db48801e9e5662cb35095e0311d68c6b6264714db` |
| `src/abr_engine/compliance/retention.py` | `2c8bfcdb09f2c1d9a53d4099e74ad32e2f9b24fe0c453ef711db80b999981c33` |
| `src/abr_engine/ops/costs.py` | `02623f21f18f74f95c716c3ef37e402bb8dd631173abd3b9bfa8ab98c8812386` |
| `migrations/024_retained_pilot_metrics.sql` | `0191de6e929401f8dbad14bce4192921ec6ea2af2a16f4a6d3991b4166a3ee69` |
| `tests/integration/test_erasure_metrics.py` | `5c95166d33b48180538eeb57bc8a5e7d3ab962a8bcd51d5105be667555ef6323` |
| `src/abr_engine/ingest/discovery.py` | `627312eebabb833f33f94804614430b75996160a0cba3ec5344f709da582ebf6` |
| `tests/unit/test_discovery.py` | `4a61d0e6701ec767386e5db4b0f379f4c9afcf41add3b2f586efb000034ca2bf` |
