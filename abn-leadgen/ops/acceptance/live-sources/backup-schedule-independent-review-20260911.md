# Independent backup queue and scheduling review — 11 September 2026

Reviewer: live_dashboard subagent. Read-only source review and isolated local tests;
no source edits, provider operations, real business data or approval records were
performed by this review.

Final focused result: **20 passed in 56.16 seconds**.
[JUnit receipt](backup-schedule-independent-review-20260911.xml).

Reviewed scope:

- Migration 026 and the singleton backup_ledger_state queue.
- Deferred, coalesced generation changes on business groups, suppression aliases,
  restriction events and deletion jobs.
- REPEATABLE READ ledger capture with the captured generation and conservative
  transaction-start watermark.
- Remote readback and current-authority rechecks before acknowledging that exact
  generation, preserving any later committed restrictions.
- Conditional no-op lookup-key fingerprint validation inside the read-only snapshot.
- Separate capture/publication OS leases; crash release, bounded bulk waits,
  independent ledger admission during local database capture, and explicit legacy
  lock reconciliation.
- The priority worker, durable safe failure receipts, 240-second attempt cadence,
  and snapshot-age/pending-lag health.
- Per-deletion expiry re-admission and the dormant systemd installer, including
  no-replace file publication and final private directory metadata checks.
- Narrow service-role SELECT/UPDATE access to the existing queue singleton;
  migration/install authority remains outside the application role.

Review findings were resolved before the final pass: ordinary publication
contention no longer counts as a failure; database capture does not monopolize
the ledger publication lease; full captures have a separate concurrency lock;
bulk publication waits are bounded; unchanged key fingerprints do not write in
a read-only snapshot; the snapshot watermark cannot claim later changes; new
unit publication cannot overwrite a concurrently created file; and the Windows
process-death test terminates the actual Python process rather than only a venv
redirector.

The first review test run overlapped active implementation fixes and failed.
It was not acceptance evidence. The final receipt above replaces that run for
the reviewed current source.

Limits remaining outside this review:

- Actual host migration, dormant unit installation, timer execution, measured
  replication lag, failure response and production restore acceptance need
  their separate operator receipts.
- One in-flight object transfer is not preemptible. The polling cadence is not
  a guaranteed four-minute recovery-point objective.
- Primary-host loss before asynchronous replication may leave an unknown latest
  restriction watermark. Restore must remain closed when that required evidence
  cannot be established; this review does not certify zero data loss.
- External notifications and a dashboard health view are not provided by the
  local systemd failure alarm.
- Business-data source/privacy/vendor/retention/backup release evidence remains
  distinct from engineering tests or the separately approved storage budget.

