# Dashboard operability review — 9 September 2026

Scope: the local fixture dashboard in [dashboard-spec.md](../../dashboard-spec.md), including its buttons, navigation, settings, reports, service launcher and recovery. This record supersedes the earlier dashboard control review for the changed behavior; it does not certify live ABN ingestion or close production release gates.

Disposition: **PASS for the local fixture dashboard**. The final independent review passed all eight requirements with no remaining material failure found.

## Build/review findings and fixes

- Delayed dashboard responses could overwrite newly saved preferences. Refresh requests now coalesce, and snapshots from before a mutation are discarded before a fresh read.
- A malformed successful response could replace usable state and leave a Run control stuck. Response shapes are checked before rendering or accepting save/run confirmations. Loading and offline controls now remain disabled until usable data is available.
- Keyboard skip navigation changed the selected view. It now focuses the current main content and preserves the view.
- A blocked report popup downloaded a file whose relative CSV link would fail. The fallback opens the protected report in the current tab, preserving its CSV link, Back navigation and unsaved-change protection.
- Completion polling could overwrite a worker's finished receipt with an interrupted state. Receipt state is now read again under the process lock. Run admission also rechecks idempotency after acquiring that lock.
- An unreadable job receipt could make the whole dashboard fail. Valid records remain usable; a persistent, escaped notice identifies the issue without disclosing receipt contents or deleting evidence.
- Reopening the launcher after database loss did not recover an existing unhealthy dashboard. It now bootstraps the isolated database and rechecks the owned service while preserving foreign processes.
- Dashboard reports exposed a gate-approved synthetic contact despite the dashboard's stricter redaction requirement. HTML, CSV and Markdown now use contact-masked projections after the original artifact-integrity and current-authority checks. Canonical private engine files remain byte-for-byte unchanged.

## Requirement evidence

| Requirement | Evidence |
|---|---|
| R1: Repeatable local launch and legacy URL | Launcher ownership regression tests, real database recovery drill, browser entry through `/report.html` |
| R2: Actual stored leads, search, filters and detail | Every stored business opened; name and formatted ABN searches; all 12 source/tier combinations |
| R3: Runs, status, serialization and refresh | Actual completed all/ABR/QBCC runs; saved source and cap assertions; lock and duplicate-request regressions; both Refresh buttons |
| R4: Correct protected report downloads | Actual HTML/CSV/Markdown requests; report popup and its CSV download; stale/integrity/deletion/quarantine tests; blocked-popup recovery |
| R5: Persistent validated preferences | Save/reload and discard; invalid budget rejection; delayed-response ordering; failed save and unsaved-edit recovery |
| R6: Truthful setup | Fixture database health, synthetic-source labels and pending live prerequisites; real outage produces HTTP 503 and launcher restores readiness |
| R7: Brand, responsive layout and accessible states | Existing canonical logo/font retained; all views at 1440/820/390/360px; keyboard focus and skip link; reduced motion; loading, empty, error and saved states |
| R8: Local access and redaction | Host/origin/CSRF tests; artifact path/authority boundaries; allowed-contact redaction in three formats with original files unchanged |

## Executed checks

- [Actual workflow receipt](operability-2026-09-09T03-09-02-817Z/result.json): all three source choices completed through the browser, including a phone run. Names, ABNs, all filter combinations, exports, settings and navigation passed. Zero uncaught browser errors. The control inventory contains repeated representations of shared controls; it is not a count of unique tests.
- [Failure-handling receipt](dashboard-resilience/result.json): **12/12 browser regression scenarios passed**, with zero actual API mutations and zero browser errors. These intercepted failures are distinct from the actual source runs and database recovery.
- [Database recovery receipt](dashboard-recovery.json): stopped the isolated database, observed HTTP 503, reopened the launcher and recovered the same owned dashboard process. Settings and stored businesses were preserved.
- [Initial broader regression receipt](dashboard-operability-regressions.xml): **37 passed**, zero failures, zero skips, in **243.03 seconds**. Includes dashboard, launcher, report review, quarantine and pipeline tests. This preceded the final contact-masking change.
- [Final post-change browser receipt](dashboard-operability-final-browser/result.json): **10/10 workflow groups passed** after the masked-report change. A new QBCC run completed with saved preferences; its report and nested CSV download worked. All three views fit 1440/820/390/360px; keyboard focus, reduced motion and rejection recovery passed. Zero browser errors.
- Final Ruff check passed. Mypy passed **58 source files**. The dashboard's JavaScript and the new browser-check scripts passed Node syntax checks.
- [Final post-change Python receipt](dashboard-operability-final.xml): **28 passed**, zero failures, zero skips, in **126.94 seconds**. Covers dashboard, launcher, report review and quarantine after the final report change. Two dependency deprecation warnings remain; they are not application runtime failures and dependency versions were preserved.
- Independent final live review of run `38523d8f-0123-45e0-b399-1a0ba56bccb7` confirmed contact masking in all three formats, preserved names/sources/identifiers/tiers/scores, unchanged original artifact bytes, and working HTML/Markdown CSV links. The actual Chromium download contained masked contacts and produced no browser errors. This closed the earlier R8 failure.

The final owned dashboard process is ready on `http://127.0.0.1:8767/`. Saved defaults were restored to both sources and A$150; the latest fixture run is complete. The isolated database remains running.

## Reproduction

Run from `abn-leadgen/`, with the isolated fixture database and dashboard ready:

```powershell
uv run --frozen pytest tests/integration/test_dashboard.py tests/unit/test_dashboard_launcher.py tests/integration/test_final_report_review.py tests/integration/test_read_quarantine.py -q --junitxml=ops/acceptance/dashboard-operability-final.xml
uv run --frozen ruff check .
uv run --frozen mypy src/abr_engine ops/local_dashboard.py ops/dashboard_recovery_drill.py
node ops/dashboard_operability_check.cjs
node ops/dashboard_resilience_check.cjs
$env:ABR_DASHBOARD_TEST_OUTPUT = Join-Path (Get-Location) 'ops/acceptance/dashboard-operability-final-browser'
node ops/dashboard_browser_check.cjs
```

The actual browser checks execute fixture runs and restore saved source/budget preferences. The tests use isolated database schemas. The database recovery drill deliberately interrupts the shared local fixture database and should run separately when no other work depends on it.

## Practical limits

The verified scope is this provisioned Windows computer and Chromium at desktop, tablet and phone widths. Screen-reader, Safari/Firefox and fresh-machine installation certification remain separate. Lead and run windows remain the latest 200 businesses and 20 pipeline runs. Live sources, external provider setup, production authentication/hosting and outreach are still outside this local fixture dashboard; the setup page keeps these limitations visible.
