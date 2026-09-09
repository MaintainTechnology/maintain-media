# Pipeline integration review 1

Reviewed 2026-09-08 against canonical specification v4.0 R2-R8/R34/R35.
Scope: `src/abr_engine/pipeline.py`, its source/promotion boundary and report lifecycle.
This is a source review before the following build step, not production acceptance.

## Findings

1. **P1 — No process or source-stage ownership surrounds parsing.** Two invocations can
   create/read the same run directories, snapshot IDs and state file concurrently. The
   short promotion lock cannot protect the earlier download/parse/diff stages. A partial
   directory also makes a retry fail `exist_ok=False` indefinitely. R3/R4/R7/R35.

2. **P1 — The final manifest destroys the durable promotion replay ledger.** Promotion
   stores `promotion_results` in `pipeline_run.manifest`; finalisation replaces the entire
   object with the report summary. A held multi-source run then retries a committed source
   without its prior result and encounters cursor conflicts. Source selection and fixture
   identity are also absent from the saved run request, so resume can silently choose a
   different input. R7/R8.

3. **P1 — Artifact ownership is registered after writes and excludes raw/state/report files.**
   Existing `register_artifacts` runs only after parse and diff. A crash leaves unowned
   personal-data artifacts, and retention cannot locate physical bytes from logical keys.
   The state JSON contains absolute paths but is neither verified nor authoritative. R2/R4/R6/R7.

4. **P1 — Report failure is not recoverable.** A partial bundle raises a manual repair error;
   a complete run returns without verifying its report files. A crash between writing the
   final manifest and updating PostgreSQL can leave different disk/database summaries.
   Report repair must use new staging and atomic publication, preserve source promotion,
   and recheck the current export gate before regenerating contact projections. R6/R7/R34/R35.

5. **P2 — Source failures are incompletely accounted for.** Filesystem/ZIP/parser failures can
   escape the narrow catch and leave a running row without a durable failure alarm.
   `alarms` is a JSON list only, never the deduplicated database alarm outbox. R34/R35.

6. **P2 — Provenance and measurement are incomplete.** ABR lacks top-level parsed/declaration/
   field-fill summaries; QBCC lacks explicit normalised-versus-quarantined counts. No source
   stage duration or monitored peak RSS is recorded. Ending RSS is correctly labelled but
   cannot substantiate the ingest/diff memory target. Missing publisher source time must
   remain null and must not be replaced by retrieval time. R2/R5/R34/R35.

7. **P2 — Fixture input selection is only validated by the CLI.** Direct execute calls with
   an unknown source take the QBCC branch. The orchestration function needs its own closed
   source/fixture validation and a bound saved request for resume. R2/R3/R7.

## Build direction

Add nonblocking OS/run and PostgreSQL source-stage ownership, persistent request/stage data,
pre-write artifact declarations with physical metadata, crash-safe attempts, verified report
publication/repair, immutable final receipts and durable deduplicated alarms. Exercise failures
at actual writer/transaction boundaries against isolated PostgreSQL16. Preserve synthetic-only
operation and leave live source, legal, hosting and full-scale capacity gates pending.

## Build and verification

All seven findings have scoped fixes. The pipeline now holds nonblocking process/run/source
ownership across staging and promotion, binds a saved request, preserves promotion receipts,
declares raw/normalised/transient/report/receipt artifacts before writes, persists validated
stages, and publishes each report generation by a directory rename. Missing reports regenerate
through the current gate; missing final receipts regenerate from the durable database result.
Fresh source observations retain counts and sampled resources without claiming full-scale proof.

Actual isolated PostgreSQL16 integration: `tests/integration/test_pipeline.py` passed all nine
cases after durable fixture enrichment and operational summary integration (81.77 seconds).
Earlier final summary/report-only integration also passed nine cases (46.49 seconds).
Tests cover three source crash boundaries, two report/final-commit crash boundaries, replay,
missing bundle/receipt repair, pre-write registration, and process ownership conflicts.
Full source promotion recovery passed 14 cases in the combined 22-test worker/source run
(118.06 seconds). Ruff and mypy passed for pipeline, promotion and worker.

The fixture provider has stable lookup/crawl/verify operation IDs and actual zero-cost receipts;
its explicitly named synthetic approval adapter supplies synthetic permission separately.
Production source mappings, live provider adapters and release gates remain pending. The local
sampled RSS is operational evidence only; the independent benchmark owns capacity acceptance.

Final integration follow-up: complete-run replay compares the current safe report projection,
excluding query timestamps, with the saved projection digest. Changed policy, suppression,
outcomes or evidence produce a new immutable bundle without replaying source promotions. A
policy-revocation regression confirms the new bundle masks contacts and preserves the old
private historical bundle. The operational monitor now persists redacted observations and
alarms in the final result transaction; notification I/O remains absent.
