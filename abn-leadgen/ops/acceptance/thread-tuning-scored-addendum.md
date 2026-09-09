

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
