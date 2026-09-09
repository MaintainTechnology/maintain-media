# Local dashboard acceptance — 9 September 2026

Disposition: **PASS for the local fixture dashboard**. Visual finish disposition: **ship**. Scope and pre-implementation rubric: [dashboard-spec.md](../../dashboard-spec.md).

This is a new acceptance record for the dashboard extension. Earlier engine-wide acceptance receipts remain historical; the current extension does not inherit their tree hashes or close any production release gate.

## Delivered workflows

- `http://127.0.0.1:8767/` and the existing `/report.html` bookmark open the dashboard.
- Lead names, recorded ABNs, scores, tiers, qualification times, regions and review reasons come from the fixture database. Missing ABNs are explicitly unknown. Search and source/tier filters operate together on the latest 200 stored businesses.
- Recent run history shows the latest 20 pipeline runs, report/CSV links, and durable latest-job completion/failure/interruption state. New runs use saved source and budget preferences and execute the existing pipeline.
- Source preference and A$0–150 ceiling persist locally. The UI displays the effective current-month ceiling; raising a saved preference does not bypass an existing lower ledger cap.
- Report reads enforce current authority, artifact state, location and integrity. The report's own CSV link works through the protected route.
- Setup explains actual local readiness and outstanding live source/rules/provider/hosting inputs. The interface is fixture-only, loopback-only and keeps outreach disabled.
- `Start-Dashboard.cmd` supports Windows double-click; `Start-Dashboard.ps1` and `ops/local_dashboard.py` support repeatable start/status/stop. Unowned port listeners are preserved.

## Evidence

The final relevant regression run passed **28 tests**, zero failures, zero skips, in **151.07 seconds**. Scope: new dashboard integration, launcher ownership, existing report review, quarantine and pipeline regression tests. Two dependency deprecation warnings were emitted; dependency versions were preserved.

```
uv run --frozen pytest tests/integration/test_dashboard.py tests/unit/test_dashboard_launcher.py tests/integration/test_final_report_review.py tests/integration/test_read_quarantine.py tests/integration/test_pipeline.py -q --junitxml=ops/acceptance/dashboard-regressions.xml
uv run --frozen ruff check .
uv run --frozen mypy src/abr_engine ops/local_dashboard.py
```

Ruff passed. Mypy passed **57 source files**. [JUnit evidence](dashboard-regressions.xml).

[Browser receipt](dashboard-browser/result.json) records the final actual fixture run `b86c2171-2064-439a-8fcd-8a96fefaa07f` and ten workflow checks. The check saves and reloads preferences, runs the actual engine using those preferences, downloads the CSV, opens its report and downloads the report's CSV, checks rejection recovery, and restores the original defaults. All three views fit **1440, 820, 390 and 360px** without page overflow. Reduced motion and keyboard focus preservation passed; no JavaScript errors were recorded. Error injection is explicitly a browser interception; it is not a live provider failure claim.

Screenshots: [desktop leads](dashboard-browser/desktop-leads.png), [desktop setup](dashboard-browser/desktop-setup.png), [phone leads](dashboard-browser/mobile-leads.png), [phone runs](dashboard-browser/small-mobile-runs.png).

The Impeccable detector ran once and returned no findings. An independent visual review then requested mobile report actions without sideways scrolling and earlier visibility of the first business. Both were fixed and the same reviewer marked both resolved, with no material regressions and final disposition **ship**.

Launcher verification included two real start/repeat/status/stop drills on port 8768, launch from another directory, detached-process survival, and preservation of the original static preview. The verified original preview was then replaced on 8767. Final status is ready with default settings restored to both sources and A$150. PostgreSQL and the dashboard are running locally.

## Review trajectory and weakest parts

| Pass | Score | Result |
|---|---:|---|
| Initial independent code review | 82/100 | Terminal jobs disappeared; effective cap was unclear; admission errors cleared; polling lost focus. |
| Independent review after fixes | 97/100 | All material code findings resolved; retry source/ID consistency and focus independently probed. |
| Final self-review after phone fixes and full browser rerun | 97/100 | Visual disposition ship; 28 relevant tests and final lint/types pass. No further material improvement identified within this scope. |

| Rubric | Score | Remaining limitation |
|---|---:|---|
| Useful complete workflows | 29/30 | Latest-200 business and latest-20 run windows; no full-history pagination. |
| Data truth and access boundaries | 25/25 | Local fixture boundary and existing report authority preserved. |
| Design and accessibility | 19/20 | Chromium plus keyboard/responsive/reduced-motion evidence; no screen-reader or Safari/Firefox certification. |
| Reliable operation | 14/15 | Verified on this provisioned Windows computer; fresh-machine installation still needs uv/Python and the documented PostgreSQL archive. |
| Maintainability and handover | 10/10 | Scope, launcher, tests, receipts and inherited design are documented. |

The best version scores **97/100 for this local dashboard**. Live ABN collection, account integrations, production authentication/hosting and the commercial pilot remain the separate pre-existing release work. No live registrations, sends, calls or purchases are claimed.
