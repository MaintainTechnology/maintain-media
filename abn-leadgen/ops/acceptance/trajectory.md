# Evidence-based score trajectory

The rubric was written before implementation in [rubric.md](rubric.md). These are self-assessments of the implemented engineering package, not a legal, commercial or production certification. No target score is used as a reason to waive a finding.

## Iteration 1 — first runnable integrated fixture build: 68/100

Evidence: fixture run `134f0558-9cb6-4b47-a673-49ae94973c00` completed against PostgreSQL16.15 on Python3.12.12. It selected one allowed synthetic business, reported two blocked/deferred queue entries and made zero live API calls. Source/enrichment/output unit and contract suite:144 passed. Separate source recovery:14 passed; core control:8 passed; CRM recovery:14 passed. Those separately run suites are not represented as one final combined pass.

| Dimension | Earned / available | Weakness that costs points |
|---|---:|---|
| Specification behaviour and traceability | 17/25 | Some integration/retention/operation commands and requirement-to-test handoff still incomplete; live-dependent work remains pending |
| Data integrity and recovery | 16/20 | Source core is tested, but pipeline-level retry/artifact ownership and report-crash recovery need repair |
| Security and permission authority | 18/25 | Independent reviews found real missing consent/capture/timezone/CRM controls; most fixes written, combined regression evidence and retention review still pending |
| Runnable delivery and operations | 11/20 | First fixture command runs; API process, actual handover, full capacity and operational recovery evidence incomplete |
| Maintainability and independent verification | 6/10 | Subsystems have independent reviews; full-package type check reports integration errors; no final full review yet |
| **Total** | **68/100** | **Not a clean full-spec review** |

Highest-impact rewrite order: finish pipeline/retention recovery; close security regressions and API assignment controls; connect runnable commands; resolve package type/lint errors; run combined acceptance and independent handover. Preserve the passing deterministic source parser/diff, common transactional authority, bounded crawl and escaped reports.

## Iteration 2 — integrated operations and recovery: 86/100

The intermediate combined command `uv run pytest -q --junitxml=ops/acceptance/iteration-2-tests.xml` completed with **325 passed,3 failed in725.73s**. All three failures were crash-recovery tests counting every alarm as one; the new monitor legitimately records an additional typed alarm. The corrected assertion checks the required `SOURCE_INTEGRITY_HELD` receipt and passed the three focused crash cases. Source changed during this intermediate run; it is not a frozen final acceptance receipt.

| Dimension | Earned / available | Remaining weakness at this review |
|---|---:|---|
| Specification behaviour and traceability |22/25| Task evidence and current vault/build status incomplete; live dependencies still open |
| Data integrity and recovery |18/20| Full-scale diff succeeds, but final review found unconnected publication fill comparison |
| Security and permission authority |22/25| Review found report/read quarantine leak, merged-source reactivation and indefinite merge-evidence retention |
| Runnable delivery and operations |17/20| Actual fixture/report/API/native restore/independent handover work;60s stretch and target-host certification remain unmet |
| Maintainability and independent verification |7/10| Package Ruff/mypy clean and extensive focused tests; combined run not yet clean or frozen |
| **Total** |**86/100**| **Full-spec review remains incomplete** |

Rewrite priorities: enforce publication-weighted quality before promotion; require quarantine authority before personal projections; activate only canonical merged lead; apply finite immutable merge-evidence retention; add reviewer-visible duplicate hints; reconcile task evidence and mirrors. Preserve exact source event semantics, no-repayment receipts, provenance gates and the working positive report. Each correctness fix received a positive/negative PostgreSQL regression before final verification.

## Iteration 3 — task audit fixes and measured tuning: 91/100

All newly identified buildable high findings have scoped fixes and executed tests. The task audit additionally found embedded scoring instead of versioned YAML, no persisted full-cost input path, missing explicit FK/month/wash tests and no downstream suppression consumer. These are now implemented: exact-v4 qualification configuration, evidenced closed-window costs with unknowns preserved,11 PostgreSQL acceptance-matrix cases, and a bounded verified mock propagation worker. Its seven tests passed; an actual CLI drill verified the endpoint removal in4.637 seconds with no notifications.

The diff tuning sequence retained exact1,435,000 output events:200k partitions118.47s,400k73.34s,800k111.99s. The best400k source was restored and its SHA256 matches the73.34s receipt. These single-run Windows observations do not establish an AU host guarantee. The60s stretch remains missed. A new independent virtual environment installed successfully from the unchanged frozen lock and ran configuration validation.

Score: behaviour23/25, data integrity19/20, security24/25, operations17/20, maintainability8/10 = **91/100**. Remaining deductions: actual source/provider contracts and rule corpus; authentic full-scale source evidence; production access/key/egress certification; target-host/timer/end-to-end capacity and stretch time; final combined unchanged-tree verification and hosted CI. Full-spec review remains incomplete.

Next review keeps the successful implementation fixed and runs the complete package checks. Only documented correctness failures justify reopening the build. No score credit is awarded for pending live/pilot approvals.

### Additional correctness review after the first complete pass

Receipt `verify-9c2124df83d846b2b9d50681ca78eb17/result.json` records 383 passing tests, no failures/errors/skips, and an unchanged source tree. A subsequent actual PostgreSQL regression exposed a previously untested defect: erasing a suppressed profile removed its historical contacted/booked/held cohort counts. This reopened the build despite the passing suite. Independent review also identified invalid preselection attempt counters, activity expiry and merged-cohort/correction attribution cases that the repair must cover. The previous pass remains valid for its exact revision; it is not the final acceptance of the repaired version. Closing this high-impact finding counts as meaningful improvement under the fixed rubric even if the total score changes by fewer than two points.


## Iteration 4 — reporting repair and discovery composition: 92/100

The first repaired-tree whole gate passed 408 tests with zero failures/errors/skips, frozen installation, Ruff, mypy and document/vault validation. Receipt `verify-ccce0e8d9d5a4c46bb88dbb2583d4dbc/result.json` identifies unchanged tree `c132b389560cf5e6da4e33658c839e17ee56416aee18b592d38c39cb19d4d6df`. This included migration 024, minimal retained cohort/outcome/activity facts, correction/merge/expiry/scoped-hold fixes and composed publisher discovery/download/revalidation. Earlier 383-test verification remains historical evidence of the prior version; it did not cover the newly discovered erasure defect.

The assessment was recorded before the new thread experiments in `pre-thread-tuning-score.json`: behaviour 23/25, integrity 19/20, security 24/25, operations 17/20, maintainability 9/10 = **92/100**. Repairing the high-impact reporting defect was a meaningful improvement regardless of its numerical score delta and reset the clean-review streak. No credit was awarded in advance for timing experiments.

## Iteration 5 — one-thread rewrite: retained score 92/100

An isolated source copy changed only DuckDB's thread count from 2 to 1. It materialized all 1.435M events in 93.4161s, with 205,000 of every event type. Bidirectional EXCEPT ALL compared the complete semantic values with the reference and found zero differences. Its diff worker sampled peak was 816,074,752 bytes; validation was measured separately. The alternative did not improve the retained 73.3443s historical observation or reach the 60s stretch target, so the two-thread implementation was kept. `thread-1-score.json` records the decision: **92/100, change 0**.

## Iteration 6 — three-thread rewrite and confirmation: retained score 92/100

The second isolated rewrite used three threads, preserving 400k partitions and the 512MB buffer/8GiB spill settings. Its first full diff took 58.4163s and passed the complete semantic comparison. Fresh two/three-thread confirmation runs took 116.4851/103.9512s respectively; every new output file had the identical SHA256 and all 1.435M events. The paired three-thread result was 10.76% faster, but the 58.4–104.0s range demonstrates substantial local variation and inconsistent 60-second compliance. All resource guards stayed clear. Raw receipts, limits and exact code snapshots are in `performance-thread-review.md` and its linked bundle.

Three threads were selected for the observed paired benefit. The main diff source exactly matches the reviewed candidate SHA256 `31116f8187d6588b07a174aeb2f2de506e932b59057d33205b1f0d6cd33d8e51`. The selected source then passed renewed whole-package verification: **408 tests**, no failures/errors/skips, frozen install, Ruff, mypy and document/vault checks; `verify-eb8385d049dc4342ba0531603b17d623/result.json`, unchanged tree `3c2ba7ed46ead9fdf8dc3476f9b6f85159791f2238f6c02a6b1ada573e7f16ae`. The app/API/report were run again from this selected version.

The performance deduction remains because the target was not met consistently; the other evidence gaps are unchanged. Score: 23+19+24+17+9 = **92/100, change 0**. The last two substantive tuning attempts gained 0 and 0, below the fixed 2-point real-margin threshold, and the bounded reviews found no remaining high/critical local defect. This establishes the requested assessed local plateau across these attempts; it does not prove an absolute performance optimum or complete the production specification.

## Final evidence delivery and remaining weaknesses

The best verified local implementation is retained. Task/status documents and 21 Obsidian mirrors were reconciled after verification, with runtime/configuration/test/workflow bytes held equal to the tested tree. 58/65 locally scoped tasks are complete; seven remain partial or pending.

The missing 8 points remain: authentic source/vendor contracts and original or approved rules (2); authentic full-source-scale proof (1); production security/cross-system certification (1); consistent stretch performance, complete-pipeline/AU-host/Linux scheduler and measured pilot evidence (3); hosted CI execution (1). A bounded nearby-folder search did not find the original extractor/rule corpus. Existing Ubuntu can start but lacks the checked Python 3.12/uv/Node/PostgreSQL 16 toolchain; no Linux deployment or CI execution was claimed. Full-spec and production acceptance remain incomplete. Further target-host profiling remains legitimate future work, not a hidden success here.
