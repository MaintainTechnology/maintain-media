# Bounded independent fixture review — 9 September 2026

Scope: read-only cross-module review after independent enrichment, control, retention, merge and adaptive-diff build/review loops. Root owns final package-wide verification and task status. This report does not certify production source mappings, legal review, provider accounts, deployment, or pilot outcomes.

## Remaining high-priority finding sent to root

**P1: raw evidence API bypasses recovery quarantine.** `control/api.py` GET `/v1/evidence/{provenance_id}` checks reviewer/compliance role and evidence expiry, then decrypts raw capture without taking the control authority or checking `restore_quarantine`, `key_compromised` or in-memory compromised-key state. The runbook and R26 require user evidence access to remain closed during isolated recovery; a role alone does not release quarantine. Obtain common authority and fail closed before decryption when any incident/recovery flag is active. Root was notified with the exact route and fix boundary. Current action gates and the repaired enrichment worker do check these flags.

## Other bounded review observations

- Reviewed cancellation resolution still uses exact group equality and exact-group ABN alias matching after canonical-family merges. This can reject otherwise corroborated reactivation for an inherited source alias. It is a controlled availability failure; do not weaken cancellation-only evidence requirements to fix it. Resolve the original family member's cancellation with positive evidence bound to that alias, and preserve unrelated opt-outs.
- Recovery intentionally leaves outbound quarantine enabled after suppression/erasure ledger reconciliation. The ledger does not contain all post-backup paid operations/budget reservations; therefore independent financial/operation reconciliation is still needed before enrichment reopening. No local drill receipt claims that release.
- Verification maps FR001–043 to test files and explicitly calls its result engineering-only. File references demonstrate coverage intent, not satisfaction of each full requirement. The harness should also include canonical/feature spec hashes and spec mirror validation for T057, and preserve a failed result receipt when a check process times out or cannot launch. These findings were sent to root, which owns `ops/verify.py`.
- T041 production rule recovery/review, T051 measured multiweek pilot, and T058 external approval/sandbox/operational gates cannot be marked complete from fixture tests. Final package checks, benchmark outputs and Windows native restore evidence have narrower, explicit scopes.

## Local evidence held by this reviewer

- Independent control regressions: 40 passing tests in the last completed combined backup/control run (42 total tests, 113.60s).
- Native encrypted PostgreSQL16 backup/restore plus retention: 35 passing tests in 111.54s before the later ops019 retention extension. The extension's targeted tests passed separately (three tests including operation retention), and the final combined rerun is recorded in the retention review once complete.
- Independent merge and retention stage: 40 passed in 105.51s, closing both merge findings and immutable replay-edge conflict handling.
- Adaptive diff: seven independent tests passed in 8.35s after the output-cleanup fix, including skew, boundary keys, simultaneous events and an injected storage failure followed by retry.
- Durable worker fixes preserve an opaque immutable attempt group ID (migration020), block missing expired stage evidence without new purchase, and apply restore/key-incident quarantine before reserve/dispatch/application. The final independent worker/retention run is recorded separately once complete.

No unobserved pass, real external send, remote erasure receipt, production custody guarantee or benchmark capacity certification is inferred from these records.

## Final rereview update

Root added `Service.personal_data_access` under common authority and calls it before evidence decryption and worklist reads. It checks both database incident/recovery flags and in-memory compromised-key state. This closes the high-priority source finding; root owns the newly added positive/negative API integration test execution. Root also changed cancellation-resolution alias/group matching to the canonical family; no claim of independent execution of those API regressions is made here.

The independent worker/retention final run completed: **39 passed in 153.25s**, with scoped Ruff/mypy clean. All recorded worker findings are closed for the checked fixture state. Backup native runtime now supports an explicitly configured absolute `ABR_FIXTURE_PG_BIN` for real Linux PostgreSQL16 CI, retaining the repository Windows runtime default and exact version check. Full package verification and external production gates remain root-owned.

### Final requested focused audit

Duplicate hints and evidence/worklist quarantine API tests passed (four tests in 15.08s). An additional actual API regression reproduced cancellation resolution making the old merged source active. The route now reactivates only the canonical group and leaves the other family records disqualified. Migration021 permits only one-way identifying merge-evidence erasure after 90 days, keeps the minimal reviewed graph/metadata immutable, and honours explicit merge/group holds. Selected profile archives include still-available merge evidence within their existing finite archive term.

Focused duplicate/quarantine/cancellation/merge-retention suite: **seven passed in 22.50s**, with Ruff/mypy clean. Additional selected-archive regression and existing archive-clock regression: **two passed in 6.86s**. No full suite was run by this reviewer for this final bounded change; root owns final frozen-tree verification.
