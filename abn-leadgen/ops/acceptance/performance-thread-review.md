# Bounded thread performance review

Recorded 2026-09-09 after the parent reported the frozen 408-test suite passed. No main source, configuration or test files were changed by these experiments. Candidate modules and both harnesses were copied into task-local `.runtime`; immutable review snapshots and receipts are retained in `performance-thread-comparison-5883627e117c4be191d13f3ea1da3c67/` beside this note. Archived code snapshots use inert `.py.txt` filenames; their bytes and SHA-256 values are unchanged from the executed candidates/harnesses. Its `sha256.json` identifies every copied receipt and code snapshot.

## Result and interpretation

Three threads showed a lower elapsed time than two threads in the requested sequential confirmation (103.9512s versus 116.4851s, about 10.76%). The first three-thread run reached 58.4163s, but its confirmation did not meet the 60-second stretch target. The historical retained two-thread result was 73.3443s; the new two-thread run was substantially slower. These few sequential runs have uncontrolled filesystem cache and operating-system scheduling, so they do not establish a stable speedup or repeatable stretch-target compliance. The parent has approved adoption subject to affected/full re-verification of the changed main code.

| Phase | Threads | Timed full diff (s) | Diff worker peak RSS (MiB) | Process-tree peak incl. validation (MiB) | Peak spill incl. validation (MiB) | Validation (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| comparison | 1 | 93.4161 | 778.27 | 1046.62 | 1496.09 | 131.5667 |
| comparison | 3 | 58.4163 | 802.00 | 1016.72 | 1530.16 | 158.0330 |
| confirmation | 2 | 116.4851 | 773.68 | 773.85 | 333.91 | 2.3831 |
| confirmation | 3 | 103.9512 | 773.95 | 776.44 | 284.91 | 0.1412 |

## Correctness and resource boundary

Every run materialized all 1,435,000 events: exactly 205,000 each of abn_new, abn_cancelled, abn_reactivated, gst_registered, gst_cancelled, name_changed and abn_disappeared. The first one-thread and three-thread outputs passed bidirectional EXCEPT ALL against the retained reference across ABN, event type, effective date, complete before/after JSON and quarantine flag; both differences were zero. Occurrence-dependent UUIDs and observation timestamps were excluded from that semantic comparison.

Confirmation reused the completed semantic proof only after matching the exact candidate, input and reference hashes, and independently materialized/count-checked every output. All four newly generated files additionally have identical SHA-256 `c4f0a8247e4028e38007b5500b54db5d6bb23c88b9ce5d056404fc66d0573c67`. This is stronger than count-only agreement. Full event files remain at the absolute `.runtime` paths in the receipts; this review bundle does not duplicate those files.

Candidates retain 400,000-row maximum partitions per side, DuckDB 512MB buffers, an 8GiB spill limit, duplicate validation and complete output/readback semantics. The only candidate source change is the thread count. A parent monitor sampled the launcher and recursively discovered worker descendants every 10ms, retaining process handles across launcher exits. No RSS/timeout guard fired. It would kill descendants before the launcher beyond 2GiB summed RSS. This is sampled protection, not a kernel-enforced allocation ceiling; short peaks may be missed. Spill was sampled every 100ms. Expensive semantic validation is outside the timed diff. No database/WAL, full pipeline, Linux AU host or production certification is claimed.

## Reproducibility and retained evidence

Environment: Windows-11-10.0.26200-SP0; Python 3.12.12; DuckDB 1.5.5; 8 physical / 16 logical CPUs. The full synthetic retained sizing dataset represents 20.5M keys; both input hashes and actual byte sizes are recorded in each comparison manifest. Disk admission required 25GiB headroom plus 8GiB spill and 1GiB output before work.

Commands, run sequentially with no concurrent full test suite:

```powershell
.venv/Scripts/python.exe .runtime/performance-thread-comparison/compare.py --go
.venv/Scripts/python.exe .runtime/performance-thread-comparison/confirm.py --go
```

The initial launch failed before any candidate execution because Windows psutil required a string path for disk_usage. The task-local harness was corrected and the failure retained as launch-failure-1.json. The first active harness remained unchanged while its process ran; confirmation used a separate file.

| Module | Actual SHA-256 |
| --- | --- |
| 1-thread candidate (`events_threads_1.py.txt`) | `5f72ea756a9d8a0fdef1bc7bcda96b53acabd10f6c8df25968f5467b4206a47c` |
| 2-thread candidate (`events_threads_2.py.txt`) | `8df5488572e812c750b36780e29374cfdffba17d7587f3202fd116b37d0c105a` |
| 3-thread candidate (`events_threads_3.py.txt`) | `31116f8187d6588b07a174aeb2f2de506e932b59057d33205b1f0d6cd33d8e51` |
| compare.py.txt | `faaaf2f1a3604a63ae311c4c78f3d8af9715181ac68a2f6ec30f5b5583c6d3a3` |
| confirm.py.txt | `33e40b1fdb9dda9f0e3a4533e01f3a990ad8dd69be3dd9f04351701ca1eea840` |

The two-thread candidate is byte-identical to the reviewed frozen main module before adoption (`8df5488572e812c750b36780e29374cfdffba17d7587f3202fd116b37d0c105a`). Candidate hashes are not presented as main-code hashes. The initial single-run 60-second crossing is not labelled an optimisation plateau or a production guarantee.

After these results, the parent decided to adopt the exact three-thread candidate and perform affected tests followed by full frozen-tree verification and runtime checks. That decision does not establish repeatable stretch compliance or increase the retained engineering assessment. This review records the experiment; it does not pre-claim the parent's subsequent verification outcome.
