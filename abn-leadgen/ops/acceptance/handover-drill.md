# Independent fixture command and report-recovery drill

Executed by the output/ops reviewer against the source owner's completed pipeline, 8 September 2026 23:13–23:18 UTC (9 September in the operator timezone). PostgreSQL16.15 on loopback port55432, Python3.12.12, Windows11, frozen `uv.lock`. Revision `40b9a016d67ddbe075b6114e630b672e722d5eef` with shared uncommitted implementation; exact relevant file hashes are in `handover-source-hashes.json`. This is an existing-instance drill, not a fresh-machine installation or overall production acceptance.

## Commands and results

All commands ran from `abn-leadgen/` using the installed uv executable at `C:/Users/dalig/AppData/Local/hermes/bin/uv.exe`. No live credentials, network providers or notification transport were enabled.

| Command | Observed result |
|---|---|
| `uv sync --frozen` | 64 packages checked, exit0 |
| `uv run python ops/local_postgres.py start` / `status` | Existing task-local PostgreSQL16.15 running, exit0; retained for other agents |
| `uv run abr-engine validate-config` | Valid fixture configuration, live integrations disabled |
| `uv run abr-engine db migrate` | Applied available migrations; final pre-run call applied020, earlier migrations already recorded |
| `uv run abr-engine run --source all --mode fixture --run-id 879088e2-d578-47e0-a413-cf2228cdf4f8` | Complete; both sources no-op against existing accepted fixture content; one selected, one blocked/deferred, zero live calls |
| `uv run abr-engine resume 879088e2-d578-47e0-a413-cf2228cdf4f8 --stage all --mode fixture` | Same immutable receipt and report paths retained |
| Same resume after temporarily renaming that run's HTML | Complete; fresh immutable report generation and receipt, same source snapshots/cursors with source replay flags; original HTML restored afterward |
| `uv run abr-engine alarms check --run-id 879088e2-d578-47e0-a413-cf2228cdf4f8 --mode fixture` | Available DB/run facts observed, unknown inputs explicit; stale prior active job produced heartbeat alarm |
| `uv run abr-engine alarms drain --mode fixture` | One durable mock receipt; zero notifications; repeated drain claimed zero |
| `uv run abr-engine worklist build 2026-09-07 --mode fixture` | Existing weekly selection replayed, one row |
| `uv run abr-engine retention run --mode fixture` | Preview only; no deletion. Old unclassified artifacts stayed held rather than guessed |

The current CSV contained one explicitly authorised synthetic contact view. Six SHA256 checks verified all three original and all three repaired report artifacts. The old HTML was preserved and restored; no report content or source history was deleted. The run ID was new, but existing source cursors meant source ingestion was correctly a no-op. Fresh-baseline/crash source coverage remains in the source owner's isolated database tests.

Initial immutable receipt: `var/runs/879088e2-d578-47e0-a413-cf2228cdf4f8/77a99b4a-3599-4b41-9a71-fc754c5279ed.json`.

Repair receipt: `var/runs/879088e2-d578-47e0-a413-cf2228cdf4f8/91b28006-bc76-45f7-8050-a82e115ea3ef.json`.

Supporting redacted outputs: `handover-run.json`, `handover-resume.json`, `handover-repair.json`, `handover-verification.json`, `handover-alarms-check.json`, `handover-alarms-drain.json`, `handover-alarms-redrain.json`, `handover-retention-preview.json`. Private report paths are recorded in those receipts. No fixture token was stored as handover evidence.

## Monitor builder checks and remaining boundaries

`uv run pytest tests/integration/test_ops_monitor.py tests/integration/test_summary_review.py -q`: **12 passed in60.54s**. The monitor suite reran after its member-count assertion: **8 passed in29.04s**, with Ruff and mypy clean. The tests exercise closed observations, threshold/deduplication behaviour, current budget month, expired policy, propagation, actual resource/heartbeat/backup state, distinct publication references, competing mock workers, retry due times, lease recovery, five-attempt exhaustion and control-failure inventory. The source owner integrated `monitor_run` before durable result commit; the retention owner added90-day observation/mock-receipt purge with scoped holds. The control owner wired the API error handler to the closed failure recorder; API hook regression evidence is separate.

The monitor reports unknown source publication time, mismatch clocks, classification/fill comparison baselines, approved hit-rate thresholds, resource admission bounds and external scheduler/restore inventory when absent. It does not infer a live observation from a fixture. Native backup/restore, browser360px review, opt-out denial/row conflicts and uncertain CRM provider recovery have separate evidence; they were not executed as user actions in this bounded handover. Systemd installation, AU hosting, current source/vendor policy, real sandbox contracts and commercial pilot remain pending.

Final semantics correction after handover: client event-to-commit elapsed time is now a separate observation and cannot trigger a server commit-latency alarm. Measured server latency remains unknown without actual measurement. The real PostgreSQL backdated-opt-out regression passed with the complete monitor suite: **9 passed in25.79s**; Ruff/mypy passed. Exact final monitor/test hashes are in `monitor-final-check.json`; the earlier handover hashes preserve the code at execution time.
