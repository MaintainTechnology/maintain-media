# Erasure and pilot metrics review — 9 September 2026

This receipt covers the bounded R29/R34/R38 correction for fixed pilot measurements disappearing when marketing profiles are erased. Builder and focused-test operator: `/root/safe_enrichment`. Independent final source reviewer: `/root/source_pipeline`. The tests used actual local PostgreSQL 16 at the fixture connection, with a separate migrated schema per test and rollback/cleanup. External sockets were blocked by the fixture harness. This is local engineering evidence; it is not a production release, external deletion, remote backup expiry, or observed pilot result.

## Initial reproduction

Before migration024 and the retained-fact projection, an actual PostgreSQL regression created a synthetic contact, selected worklist row, and dated contacted/meeting outcomes with two cumulative attempts. It queried `operational_summary` over one closed window, suppressed the profile, called the real `erase_profile`, and queried the identical window again. Before erasure the cohort contained one contacted group, one booked group and two attempts. After erasure the cohort list was empty. The comparison failed: the summary depended on `worklist_row`/`outcome_event` joined to the erased `lead_entity`.

This was a failing execution of the initial `tests/integration/test_erasure_metrics.py` regression, not an inferred source-only defect. That test was subsequently extended; this receipt does not invent an initial elapsed time or claim a preserved raw log for that first execution. The final regression checks unchanged cohort totals after erasure and verifies that the original lead and outcome records are deleted.

## Final implementation and review corrections

- Migration024 adds immutable minimal cohort, outcome and activity facts. It retains opaque group/worklist/event identifiers, fixed selected tier/signal, dated attempt increments and meeting states, and pseudonymous operator keys. Names, endpoints, outcome notes and source receipts are not copied into these metric facts.
- Profile erasure writes the minimal facts in the same database transaction before deleting the active profile. Summary reads live and retained facts with identifier-based deduplication and resolves group merges through current canonical group authority.
- Preselection observations cannot seed the attempt counter: an excluded observation with 99 attempts followed by a valid observation with two still yields two before and after erasure.
- Canonical group membership chooses the first selected tier/signal. Activity cost attribution uses those chosen memberships, so an A/B merge contributes its time once to tier A even when an unrelated B group keeps the B bucket present.
- Full activity correction history is validated before allocation. Effective correction leaves are then allocated to their final cohort/group, including a correction moved to another cohort. Archived originals cannot return through the live projection after retained facts expire.
- Expired correction chains are purged from their leaves, including original marked rows that never needed a retained fact. The all-expired-at-first-erasure regression proves deletion in the first retention execution and zero restored historical work time.
- A cost statement can reference a retained cohort after the last live row is erased. Unknown cost categories remain unknown. Historical summaries exclude propagation records created after the declared window end from propagation-age calculation, avoiding a negative age validation failure discovered during the focused tests.

## Retention and hold bounds

Outcome and activity metric deadlines use 24 calendar months from the actual event/activity timestamp. A retained cohort denominator lasts through the latest relevant selected/outcome/activity timestamp plus 24 calendar months. Correction ancestors remain only while a retained or live correction depends on them; expired chains are removed once those dependencies expire. Explicit scoped metric/cohort holds preserve the minimal facts, including an old held outcome, without blocking erasure of the identifying marketing profile. Existing explicitly scoped group/provenance/contact/evidence holds retain their separate meanings. Releasing a metric hold makes overdue facts eligible on the next retention execution.

Deletion remains subject to the existing fixture-only destructive authority. These tests prove execution of the local finite schedules, not that a production scheduler ran or that a remote provider/backup expired. The retained facts are pseudonymous and purpose-limited; they are not claimed to be irreversibly anonymous. No real owner rates, cash expenditures, prospect outcomes or pilot observations were invented.

## Final focused commands and results

Executed from `abn-leadgen` in Windows PowerShell using the local virtual environment:

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_erasure_metrics.py tests/integration/test_cost_evidence.py tests/integration/test_operational_summary.py -q
```

Result: **13 passed in 35.06s** (eight erasure metric cases, four cost cases, one operational summary case). This final run followed an intermediate run of 11 passed/one failed that exposed the historical propagation-age issue; the implementation was corrected before the final run.

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_retention.py -q
```

Result: **34 passed in 68.83s**. This is a separate focused regression execution, not a combined 47-test invocation or a full-package verification.

```powershell
.venv/Scripts/python.exe -m ruff check src/abr_engine/ops/pilot_facts.py src/abr_engine/ops/summary.py src/abr_engine/ops/costs.py src/abr_engine/compliance/retention.py tests/integration/test_erasure_metrics.py
.venv/Scripts/python.exe -m mypy src/abr_engine/ops/pilot_facts.py src/abr_engine/ops/summary.py src/abr_engine/ops/costs.py src/abr_engine/compliance/retention.py
```

Final results: Ruff **all checks passed**; mypy **no issues found in four source files**. The independent reviewer reread the final implementation and regressions without editing them or running a full suite, and reported no remaining high/critical finding within the reviewed scope. Full package verification and post-migration runtime evidence belong to the parent task's separate receipts.

## Frozen patch SHA256

Hashes were read after focused validation and independent source review, before writing this acceptance-only receipt. Paths are relative to `abn-leadgen`.

| File | SHA256 |
| --- | --- |
| `migrations/024_retained_pilot_metrics.sql` | `0191DE6E929401F8DBAD14BCE4192921EC6EA2AF2A16F4A6D3991B4166A3EE69` |
| `src/abr_engine/ops/pilot_facts.py` | `DBDCA9C373D140724AB259FF68866EC9A393E23466DFCA9FBA4D4107F95E2A0A` |
| `src/abr_engine/ops/summary.py` | `0BB500244F8053635D0A3D8DB48801E9E5662CB35095E0311D68C6B6264714DB` |
| `src/abr_engine/ops/costs.py` | `02623F21F18F74F95C716C3EF37E402BB8DD631173ABD3B9BFA8AB98C8812386` |
| `src/abr_engine/compliance/retention.py` | `2C8BFCDB09F2C1D9A53D4099E74AD32E2F9B24FE0C453EF711DB80B999981C33` |
| `tests/integration/test_erasure_metrics.py` | `5C95166D33B48180538EEB57BC8A5E7D3AB962A8BCD51D5105BE667555EF6323` |

## Local Linux availability inventory

The read-only requested command `wsl --list --quiet --verbose` returned exit 1 and usage text. A bounded follow-up `wsl --list --verbose` returned exit 0 and listed **Ubuntu — Stopped — version 2**.

The parent subsequently authorised starting that existing distribution solely for a bounded OS/init/tool inventory. `wsl -d Ubuntu --exec /bin/sh -c <inventory>` completed with exit 0 inside a 20-second subprocess timeout. It reported:

```text
Linux 6.6.114.1-microsoft-standard-WSL2 x86_64
Ubuntu 26.04 LTS (Resolute Raccoon)
PID 1: systemd
uv: unavailable on PATH
/usr/bin/python3: Python 3.14.4
node: unavailable on PATH
psql: unavailable on PATH
pg_dump: unavailable on PATH
pg_restore: unavailable on PATH
```

Explicit executable checks also found no `psql`, `pg_dump`, `pg_restore`, `initdb`, or `pg_ctl` at `/usr/lib/postgresql/16/bin/`. PATH absence is not a claim that no alternate user installation exists. No packages were installed, dependencies downloaded, services/timers changed, secrets/configuration dumped, tests executed in Linux, or remote CI started. An existing Linux environment can start, but the checked environment does not provide the PostgreSQL16/tooling readiness needed for a Linux verification claim.

### Cleanup status

The parent authorised restoring Ubuntu's initially stopped state only if a bounded process-name inspection showed startup daemons and this inspection alone. `wsl -d Ubuntu --exec /bin/ps -eo pid,ppid,comm` completed with exit 0. Alongside startup daemons and the inspection's `SessionLeader`/`Relay`/`ps` chain, it showed a separate `login` process (PID 375) parenting `bash` (PID 460), with user `systemd`/`sd-pam` processes. Names alone cannot establish that this shell is disposable startup activity. Ubuntu was therefore left running to preserve possible unrelated interactive work; `wsl --terminate` was not called. No command arguments or secrets were inspected, and no other distribution was touched.
