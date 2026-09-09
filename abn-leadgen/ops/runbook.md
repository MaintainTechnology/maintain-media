# Operator and developer recovery runbook

This runbook supports specification v4.0. Production gates are pending and live integrations remain disabled. The [fixture handover](acceptance/handover-drill.md) records executed commands and report recovery. Other procedures require their own evidence before release.

For every incident record the run UUID, stage, alarm code/dedupe key, last committed cursor, redacted reason and owner. Never copy contact values, secrets, page contents or live tokens into logs. The alarm outbox must persist uniqueness on `(run_id, alarm_code, subject_key)` and retry a delivery without inventing a new incident. No notification channel is enabled by these instructions.

<a id="source-stale"></a><a id="source-mismatch"></a><a id="source-mismatch-escalation"></a>
## Late or mixed source

Owner: operator, escalating to developer/source-policy owner. ABR age above 10 days warns; conflicting generations above 48 hours warn and at seven days escalate. Show QBCC's actual publication age even if its unchanged backlog is useful. Compare immutable discovery metadata, inner transfer metadata, part inventory and checksums. Re-read discovery after download. Retry only against a new evidenced coherent publication or quarantine the failed run; no operator override may waive completeness/coherence. The accepted cursor stays unchanged on failure. More than 90 days without a retained accepted analytical baseline requires controlled expiry/rebaseline under retention policy, not an invented comparison.

<a id="integrity-failure"></a><a id="schema-failure"></a><a id="count-failure"></a><a id="duplicate-failure"></a><a id="field-fill-breach"></a><a id="unexpected-disappearance"></a><a id="member-count-changed"></a>
## Parse or integrity failure

Owner: developer. Preserve the failed run manifest and limited restricted diagnostic sample; quarantine unknown schema/enums, declared-count mismatch, duplicate ABNs, unsafe XML/ZIP and required-field change above two percentage points. Unexpected disappearance blocks affected marketing identities; do not label it cancellation. Member-count change alone is informational but still needs a verified complete inventory. Investigate parser/source contract before retry. A parser/hash/schema change needs an explicit migration or zero-event rebaseline; never manufacture business-change events by changing interpretation.

For a task-local fixture created before migration011, a retained baseline can have valid bytes and digest but no recorded `local_path`. The quality check holds it as `PREVIOUS_ARTIFACT_UNAVAILABLE`. Verify the retained file against its immutable checksum/size first, preserve the held receipt, then establish a new fixture baseline using `uv run abr-engine baseline abr "Verified legacy fixture bytes; pre011 location metadata requires a fresh baseline" --mode fixture`. This creates a new run, retains the exact reason and emits zero ABR events. A subsequent `run --source all --mode fixture` should complete. Never waive a digest mismatch or infer a historical business transition from this recovery; real-source recovery still requires its approved contract.

## Source replay and partial promotion

Owner: developer. Use final `resume --help`, then resume the recorded run/stage with matching snapshot/config/rule contracts. Inspect the committed source cursor and promotion receipt before replay. Pre-commit crash means retry staged work; post-commit crash means resume durable output delivery. A committed replay adds no events. Historical A-to-B-to-A content requires fresh publication evidence and compares B-to-A. Replaying retained bytes alone is not a new occurrence. Verify suppression and other-source cursors before and after recovery. Never reset shared database history to make the run pass.

<a id="classification-drift"></a><a id="volume-deviation"></a><a id="volume-zero-threshold-missing"></a><a id="hit-rate-deterioration"></a>
## Statistical drift

Owner: developer with owner review of policy. Classification movement above three percentage points is actionable only for comparable runs. Volume deviation above 50% uses the median of the last four comparable non-baseline publications. A zero median needs an explicitly configured absolute threshold; missing threshold is informational and cannot be guessed. Baseline/no-op runs do not trigger these comparisons. Hit-rate deterioration requires a measured approved baseline, threshold, minimum sample and tier/window denominators. Report missing baseline evidence. Recheck source/rule/evidence changes before attributing deterioration to business demand.

<a id="budget-stop"></a><a id="quota-stop"></a>
## Budget or provider quota stop

Owner: operator, with developer for reconciliation and Jon Pepper for cash decisions. Stop billable work before the next request when no reservation fits. Keep resumable stage receipts and successful cache entries; do not repay completed requests. Unknown billing keeps its original-month reservation until provider reconciliation. Monthly usage authority is at most A$150 inclusive of tax, FX buffer, retries and prepaid consumption. Cash procurement authority is A$0; do not top up or purchase subscriptions automatically. Reconcile tariff/FX/receipt evidence before retry, honour verified quotas and record every deferred group.

<a id="invalid-receipt"></a>
## Manual DNCR wash

Owner: authorised operator/reviewer. Generate a reviewed batch; manually wash through the approved account. Import only the exact batch with normalized phone results, provider/account, count, UTC wash time and matching receipt/batch digests using the final `wash import --help` workflow when available. Reject future/mismatched/malformed/conflicting receipts atomically and quarantine the report. Latest observation controls: a later listed/error record blocks even if an older wash was clear. Clear expires strictly at 30 days. Current licence review, identity and calling policy remain separate. Direct SOAP/SFTP is disabled; account costs/eligibility require a fresh owner review.

<a id="suppression-unconfirmed"></a><a id="suppression-commit-delayed"></a><a id="suppression-propagation-delayed"></a>
## Opt-out failure or delay

Owner: operator immediately, compliance/developer on failure. Use authenticated `POST /v1/suppressions` with lead ID or endpoint, reason, source, request time and stable idempotency key. Acknowledge saved only after durable receipt; a timeout is unconfirmed and prohibits further contact. Reuse the same key/body to recover the receipt. Never wait for the five-minute Sheet repair or weekly import. Commit target is within five seconds; external sheet/CRM propagation target is within 60 seconds when available. A blocked or stale outcome edit cannot prevent suppression. Inspect alias/group/endpoint restriction projection and cancellation outbox; new endpoints inherit entity blocks. A remote outage must not reopen local action authority. Escalate an already-dispatched race with actual timing and cancellation evidence, without claiming recall.

<a id="writeback-conflict"></a>
## Worklist edit conflict

Owner: operator. Read the returned safe current row version/status and refresh before applying an ordinary edit. Bind immutable row UUID, never spreadsheet row number; duplicate identities require repair. The same idempotency key with changed payload is a conflict, not a retry. The permitted outcome vocabulary and invitation evidence rules are in `templates/worklist_schema.json`. Actual activity dates are required. A booked meeting does not imply invited. For `do_not_contact_requested`, confirm suppression first even if the ordinary outcome remains conflicted. Failed Sheets edits remain prominently unsaved; after five bounded retries repair manually. No cell content belongs in edit telemetry.

<a id="crm-reconciliation-pending"></a>
## Partial or uncertain CRM export

Owner: developer with reviewer identity resolution. Read durable outbox state, approval payload/revision, location/group mapping, attempts and remote receipts. Recheck current eligibility and suppression immediately before retry. An uncertain create reconciles by configured identity fields. Exactly one consistent match may establish a mapping, then the desired projection must be verified/reapplied before success. Zero matches after an uncertain create remain held; never blindly repeat that create. Contradictory/multiple/shared-endpoint matches require review. Preserve successful items in partial batches and unrelated tags. After five failed attempts, dead-letter and alarm. Suppression cancels pending exports and prioritises block/removal updates. `uv run abr-engine crm drain --mode fixture` operates only the database mock; no campaigns or messages.

<a id="disk-capacity"></a><a id="memory-limit"></a><a id="spill-exhausted"></a>
## Resource admission or exhaustion

Owner: developer. Stop before new work if free bytes are below the capacity worksheet: remaining downloads + staged Parquet + prior/new snapshot remaining allocations + bounded spill + projected DB + WAL growth + temporary backup + 25 GiB. Unknown bounds block admission. Do not double-count bytes already reflected in filesystem free space. The initial DuckDB baseline used two threads; the selected diff uses three threads and400k-row partitions after the measured comparison in `acceptance/performance-thread-review.md`. Its512MB buffer is not an RSS limit. Worker RSS above two GiB alarms; bound spill and fail on exhaustion rather than grow indefinitely. The58.4/104.0-second synthetic observations do not prove consistent60-second compliance or AU-host capacity. Profile representative wide-name/event-output samples and resize/revise the approved plan if targets fail. Preserve the measured exact environment and output-bearing operation. No historical timing or tiny sample proves full-register capacity.

<a id="policy-expired"></a>
## Expired policy, missing evidence or unavailable authority

Owner: the recorded policy/release owner. Block the affected capability immediately. Obtain a current scoped assessment with source/actor/digest/version/expiry, or keep work in fixture/manual review. Operators and developers cannot self-approve legal or marketing-review policy. Unknown identity, permission, source coherence, current licence/wash, recipient timezone or authority service means blocked. Candidate rendering never substitutes for action-time authority.

<a id="backup-failed"></a><a id="restore-failed"></a>
## Backup and restore quarantine

Owner: developer with compliance. A failed backup or restore remains alarmed; do not report success from an attempted job. Restore into an isolated quarantine with outbound actions and user evidence access closed. Replay the latest suppression/erasure ledger, including minimal HMAC aliases and pending deletion receipts; reconcile encryption/lookup keys; run overdue retention; verify restrictions and formerly erased identities before reopening any capability. Capture an allowed fixture plus blocked pre-backup/post-backup opt-outs and rotation cases against actual database boundaries. Existing backups expire within 35 days; record primary deletion separately from complete backup expiry. G3/G7 remain closed without this drill.

## Retention and erasure

Owner: compliance/developer. Preview final `retention --help` plans before authorised execution. Maximum policies: raw ZIPs 30 days; analytical snapshots 90 days; unworked profiles 180 days after last qualifying event; ordinary captures 90 days; unnecessary suppressed/disqualified profile fields 30 days; backups 35 days. Selected evidence's seven-year period is a proposed purpose-based policy requiring approval, not a universal legal claim. Scoped legal holds need owner/reason/review date. Erase plaintext ABN/licence aliases and marketing endpoints while retaining required minimal keyed restriction aliases. Suppression is never routinely deleted or restored away. Mark deletion complete only after all applicable database/object/Sheets/CRM/backup expiry receipts exist.

## Key rotation and compromise

Owner: developer with compliance. Keep encryption, HMAC lookup and signing secrets separate and outside source/DB backups. Dual-read/write approved lookup versions during migration; verify erased token-only restrictions still match. Do not HMAC an old HMAC as though it were the original endpoint. Retain lookup-only encrypted prior keys while any restriction depends on them; refuse premature retirement. Key compromise freezes affected actions and opens incident recovery. Rotate signed-service credentials, revoke obsolete scopes, verify private evidence access and record restricted receipts without secrets.

<a id="timer-heartbeat-missed"></a>
## Missed timer or overlapping run

Owner: operator/developer. Check systemd timer/service status, latest immutable manifest, process and database lock ownership and lease heartbeat. There is one scheduler and a shared nonblocking process lock; overlap returns code 4. Never delete locks while an owner is alive. A crash releases flock and database connection locks; expired remote-work leases still require uncertainty reconciliation before reclaim. Lease/token/heartbeat ownership belongs in durable stage state. Confirm no duplicate cron schedule exists. A failed or missing scheduled run must not silently advance its source cursor.

## Independent handover drill record

Bounded fixture command/recovery drill: **PASSED**, [record and limits](acceptance/handover-drill.md). It used an existing task-local database, a new run UUID, same-run replay and deliberately missing HTML recovery, with six report hashes verified. It did not perform an unaided fresh-machine install, live source collection or a real user opt-out. API suppression/row-conflict/CRM uncertainty and native restore have separate fixture tests/drills; do not merge them into one broader claim.

## Monitor and fixture delivery

Run `uv run abr-engine alarms check --run-id <uuid> --mode fixture`, then `uv run abr-engine alarms drain --mode fixture`. Without a run ID, the check selects the latest recorded run. Both passed the handover. Checking derives current policy/budget/suppression/CRM and active-run heartbeat state and records source/run numeric observations. A running job without a database heartbeat for more than 300 seconds alarms; this is distinct from the external scheduler inventory, which remains unknown without an evidenced timestamp and expected interval. Do not clear an old running row merely to suppress an alert; inspect its lock and recovery state.

Additional measured inputs use `--observations <private.json>` and the closed `Observation` schema. No raw endpoint/name/page fields are accepted. Missing classification/fill/hit-rate comparison inputs or approved baselines remain listed as unknown. Delivery claims at most 60 rows with 60-second leases, exponential retries and five attempts maximum. Mock receipts are idempotent and contain no original error payload. There is no configured notification transport. Uninstalled `abr-engine-monitor.timer` uses the same CLI every minute within systemd; do not add cron.

`suppression_request_to_commit_seconds` measures elapsed time from the client-supplied event date to the database timestamp and may include manual/upstream delay. It is never used as server commit latency. `suppression_commit_seconds` stays unknown unless an actual server receive-to-ack measurement is supplied; a backdated opt-out does not manufacture a slow local commit alarm.

For the native fixture backup drill, `uv run abr-engine backup drill --mode fixture` accepts `ABR_FIXTURE_PG_BIN` as an absolute PostgreSQL16 binary directory. Linux CI uses `/usr/lib/postgresql/16/bin`; Windows defaults to `.runtime/pgsql/bin`. It restores into an isolated local cluster; see its separate receipt. A failed drill must remain failed, and successful local restore does not approve AU hosting or external backup expiry.

## Downstream stop recovery

Use `uv run abr-engine propagation drain --mode fixture`. The CRM command also prioritises these jobs before/after ordinary delivery. Each job obtains a120-second lease, checks current family/incident authority and exact remote group mapping, then performs provider I/O outside the database locks. The fixture projection clears engine-owned marketing values and applies the configured `maintain-media:suppressed` tag while preserving unrelated tags/custom fields. Real vendor clearing of nonnullable fields requires the separate G5 contract.

After an uncertain update, retry first fetches the remote projection; an already-correct stop does not repeat the write. Unresolved actually dispatched CRM creates/updates keep propagation pending for reconciliation; a blocked approval that was never dispatched does not. Completion requires a confirmed remote stop or confirmed absence with no unresolved dispatched write. Failure retains the opt-out, records only a closed error code and retries with bounded backoff; five attempts dead-letter. Quarantine prevents personal projection access and cannot be bypassed by the worker. The fixture CLI drill measured4.637317 seconds enqueue-to-confirmation with no notification; this does not establish production latency.

## Recorded cash and operator time

`uv run abr-engine cost-import <private-evidence.json> --mode fixture` validates the closed `CostStatement` described in [cost-input-review.md](acceptance/cost-input-review.md). Use exact declared aware period bounds and genuine supplied receipt/approval/FX/rate evidence; do not supply guessed zero spending. The returned summary uses that exact window, keeps usage reservations separate from cash and requires every cash category, rate and reviewed time coverage before a fully loaded total. Cohort allocations remain separate. Raw receipt evidence has90-day retention with scoped holds; numeric metrics have24-calendar-month retention. This command does not authorise procurement or invent pilot observations.
