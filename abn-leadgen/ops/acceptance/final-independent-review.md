# Final bounded independent review — 9 September 2026

Reviewed canonical specification v4.0 R1–R43, current control/report/source/worker/CRM interfaces,
retention and recovery boundaries, recorded review evidence and independent handover. This is a
cross-module engineering review; it does not claim new full-suite execution or external release.
The reviewer previously built source/pipeline/worker code, so independence is strongest for the
cross-module report/control boundary and weaker for those owned modules.

## Findings and disposition

1. **P1, R26/R29: report personal data bypassed recovery quarantine.** `report_context` originally
   acquired control authority but projected business names and outcome notes when restore/key
   quarantine was active. Endpoint masking did not protect these other personal fields. Root
   changed it to `service.personal_data_access` before querying. The focused independent test
   `tests/integration/test_final_report_review.py` passed all three database restore/key and
   in-memory compromise cases in 9.16 seconds, with a positive populated report before quarantine.

2. **P1, R5/R7/R35: required-field fill comparison was not connected to promotion.** The parser
   has an optional local baseline check, but neither source orchestration nor promotion supplied
   the accepted publication's weighted baseline. Per-member fractions alone cannot be compared
   safely across repartition. Root authorised a separate build step to persist row-weighted
   publication fill, verify it against actual Parquet and hold promotion on >2 percentage points
   against the accepted same-contract baseline. This finding remains open until that build's
   positive/negative PostgreSQL regression passes; final status is recorded below.

## Checked boundaries and limits

- R1–R12/R41: source mappings and classification are explicitly synthetic/disabled until approved;
  full-output diff, A–B–A occurrence identity, parser rebaseline and atomic source recovery have
  real fixture evidence. New fill comparison above is a buildable gap, not an external gate.
- R13–R20: canonical aliases/family suppression, queue fairness, durable budget/provider receipts,
  quarantine, finite payload retention and stale-evidence holds are present. Worker review tests
  cover erased merged-family cooldown and no repayment after uncertain response. Live query,
  crawl/verification adapters remain separately gated; pure safe-crawl tests are narrower evidence.
- R21–R33: current identity/basis/wash/action checks, exact provenance relationships, authenticated
  suppression, CRM approval/reconciliation and finite erasure have scoped independent tests.
  Native restore deliberately remains quarantined pending current financial/key reconciliation.
  This review found the report read bypass above despite correctly blocked contact endpoints.
- R34–R35: operational summary/monitor persist redacted actual observations and explicit unknowns.
  Missing measured field-fill comparison is being fixed; absent production publication, classifier,
  approved hit-rate and external scheduler baselines remain unknown. No notification was sent.
- R36–R43: capacity calculations and full-output benchmarks have separate receipts; no <=60-second
  result, AU-host custody, deployed scheduler, live source/vendor certification or measured pilot
  is inferred. The fixture pipeline samples RSS/disk, while host admission/resource enforcement
  belongs to the documented deployment/capacity gate. Root owns final package verification and
  requirement/task completion; file-to-requirement mappings alone are not proof of satisfaction.

## Existing report recovery

Complete-run replay verifies artifact digests and recomputes a current safe projection digest,
excluding transient query timestamps. Policy/restriction/outcome changes create a new immutable
report generation; source promotions are replayed from durable receipts. The policy-revocation
test verifies masked new CSV, unchanged source promotion count and retained private historical
bundle. Historical local files are restricted snapshots, not live authorisation; deployment access
and suppression propagation must enforce their approved custody. No static file can retract bytes
already read. The independent handover also exercised unchanged replay and missing-HTML repair.

No further critical/high issue was confirmed in this bounded pass beyond the two findings above.

## Authorised build follow-up and final verdict

Finding 2 is closed for the configured fixture mapping. `ingest/quality.py` computes the closed
required-field map weighted by real member row counts; archive manifests and pipeline validation
include the numeric map and source_rows. Promotion independently recomputes the aggregates from
verified Parquet, rejects false declared metadata, compares the accepted same-parser/schema
baseline before cursor/event changes, and checks required fields even when older manifests lack
quality metadata. Previous retained artifacts are checksum/length verified before recomputation.
An explicit parser rebaseline resets comparison but cannot waive mandatory field validity.

Focused execution: quality/source promotion selection **4 passed in 15.80s**, covering weighted
repartition, A–B–A, parser rebaseline, and an actual PostgreSQL33pp fill breach with zero cursor/event
effects followed by a valid successful retry. Source/quality unit tests plus selected pipeline
integration **46 passed, 7 deselected in 29.49s**. Ruff passed on changed files; mypy passed quality,
promotion and pipeline. No full package suite was run in this review.

Verdict: the two confirmed high findings are fixed and have scoped positive/negative evidence.
Ready for root's final frozen package verification; external release and measured pilot gates
remain pending. The independently owned monitor consumes the new weighted observations and
records its own final tests; this review does not attribute unrun monitor tests to this reviewer.
