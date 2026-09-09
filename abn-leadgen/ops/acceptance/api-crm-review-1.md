# API and CRM review 1

Reviewed 8 September 2026 while the parent implementation was still in progress. Scope: `src/abr_engine/control/api.py`, `auth.py`, `models.py`, relevant `service.py` paths, `export/crm.py` and their Sheets contract. This is a defect review, not a production-readiness score. Live capabilities remain disabled. Parent-owned code was not changed by this review.

## Findings requiring parent fixes

### P1 — An uncertain update can be marked succeeded without applying the approved payload (R33)

`export/crm.py:117–127` skips `provider.update` whenever the outbox state is `uncertain`, but every `TimeoutError` from discovery, create or update is stored in that same state. Reproduction: a remote group already exists with payload `old`; `update` raises before changing it; the next drain finds the group, skips update and commits `succeeded`. The remote projection is still `old`. A discovery timeout can also be misclassified as uncertain-create and remain stuck when no match exists.

Executed an isolated Python provider/connection-double reproduction, calling the real `drain_one` twice with only projection/authority fixtures. Output:

```text
Update attempt: {'outbox_id': 'job', 'state': 'uncertain'}
Reconcile attempt: {'outbox_id': 'job', 'state': 'succeeded'}
Remote value after claimed success: old
```

Fix: persist the uncertain operation kind and desired payload/revision before external work. Reconcile creates by identity **and approved projection**, and confirm/reapply updates idempotently before marking success. Keep discovery failures as discovery retries. Add provider-boundary tests for timeout-before-update, timeout-after-update, timeout-before-create, timeout-after-create and lookup timeout. A matching group alone does not prove its fields match the approved intent.

### P1 — Email consumption accepts an operator-only token for the same actor (R24/R26)

`control/api.py:162–164` accepts either `operator` or `sender` for consumption. Creation checks `sender` for email, but `Service.consume` receives only the actor ID and checks no scope. A pending email intent created by a sender-scoped identity can subsequently be consumed using an operator-only token with the same subject. This matters when an actor's assigned privileges are reduced or separate tokens intentionally narrow the action scope.

Fix: derive the stored intent channel inside the authoritative transaction and require current `sender` scope for email consumption; only phone consumption should permit an authorised operator. Apply the same channel-specific scope on action result reporting. Add a same-subject sender-create/operator-consume test that returns 403, plus allowed sender email and operator phone cases. This finding is based on the current route/service call chain; no live dispatch was attempted.

### P1 — Unauthenticated traffic can exhaust the only suppression rate budget (R25/R26)

`control/api.py:57–65` accounts every request in a single global 600/minute queue before any route authentication. Six hundred unauthenticated or invalid-path requests cause the next authenticated `/v1/suppressions` request to return 429 with a 60-second delay. The same shared bucket covers unsubscribe and all control mutations. An unrelated anonymous requester can therefore deny the immediate opt-out path.

Fix: separate bounded unauthenticated admission limits from authenticated control quotas, allocate protected suppression capacity and avoid letting ordinary reads or unknown paths consume all opt-out capacity. Keep in-memory accounting bounded, and retain a deployment reverse-proxy limit separately. Test saturating anonymous/ordinary traffic while an authorised suppression still commits or produces a deliberate actionable availability alarm. This is a concrete deterministic middleware path; no external traffic was generated.

### P1 — Provider latency holds the global suppression lock (R24/R25/R33)

`export/crm.py:85` acquires `service.authority(conn)` before discovery/update/create. That obtains the transaction-scoped global `control-authority` advisory lock (`control/service.py:46`), and the synchronous provider calls at `crm.py:107–120` execute before the transaction returns. Any slow or hung provider call blocks every suppression mutation and candidate/action check that needs that lock. The protocol currently supplies no timeout/deadline contract. A vendor wait can directly exceed the five-second suppression commit target.

Fix: persist an owned outbox claim and approved projection, release long-lived global authority locks before provider I/O, and implement bounded provider deadlines plus pre-dispatch authority recheck/cancellation/uncertainty reconciliation. Document the external in-flight race rather than promise atomic external recall. At minimum a blocking-provider fault test must prove a separate PostgreSQL suppression transaction can still commit promptly. Fixture mode limits current operational exposure; it does not make this lock coupling suitable for live certification.

### P2 — A naïve bridge timestamp causes HTTP 500 (R26/R32)

`control/api.py:83–85` parses an ISO timestamp then subtracts it from an aware UTC value, catching only `ValueError`. A syntactically valid timestamp without a timezone raises `TypeError`. An authenticated bridge request with `X-Bridge-Timestamp: 2026-09-08T12:00:00` reproduced HTTP 500 through `TestClient(..., raise_server_exceptions=False)` before any database call.

Fix: require a timezone-aware timestamp and catch malformed type/encoding errors as `BRIDGE_SIGNATURE_OR_EDITOR` 401. Test naïve, invalid, stale, future and correctly signed timestamps. Invalid bridge input should not produce an uncaught application exception.

### P2 — Dispatch results can claim an attempt before its authorisation (R24/R34)

`control/api.py:205–215` checks matching actor/dispatch, consumed state and a maximum future time, but accepts any earlier `occurred_at`. A result dated before the decision's `checked_at`, before intent creation, or outside the five-second decision interval can be saved as `sent`. The audit can then contradict the actual action-time contract while appearing valid.

Fix: validate actual dispatch start time against the consumed decision's interval and retain report-received time separately; reject or explicitly quarantine stale/out-of-order timing evidence. If provider completion may occur later, model dispatch-start and completion separately. Test pre-authorisation dispatch, dispatch outside the allowed interval, allowed dispatch with a delayed result receipt, and suppression/in-flight ordering. Do not rewrite historical times to make a receipt fit.

## Resolved integration mismatch owned by this slice

The Sheets opt-out branch originally sent `notes: null`, whereas `control.models.Outcome.notes` accepts a string. Suppression POST could commit, then the outcome PATCH always failed 422. Updated `integrations/sheets_bridge.gs` to send `notes: ''`. The Node harness now invokes the real edit handler with malformed ordinary fields and confirms suppression is posted first and the subsequent PATCH uses the closed typed opt-out payload. The current contract intentionally does not postpone suppression because unrelated invitation/attempt/note fields are invalid.

## Separate typing integration result

Executed `.venv/Scripts/python.exe -m mypy src/abr_engine` during this review. At that snapshot it checked 34 files and failed with 10 errors:

- `enrich/crawl.py:250,255,266,275,279`: optional host/IP values passed to required string APIs.
- `enrich/crawl.py:326,328,332`: BeautifulSoup attribute union includes `Sequence[str]` where URL logic requires a string.
- `control/service.py:76`: `reasons` needs an explicit list annotation.
- `control/api.py:30`: rate queue needs an explicit type annotation.

These are package-integration diagnostics, separate from the behavioural findings above. The source owner may already be modifying these files; rerun the final package check after fixes rather than treating this snapshot as final evidence.

## Scoped checks and limitations

Owned output tests rerun after the bridge fix: `python -m pytest tests/unit/test_outputs.py -q` → **37 passed in 1.19s**. The earlier owned-file Ruff and four-module mypy checks passed; final aggregate checks remain the parent owner's responsibility. Review reproductions used synthetic in-process mocks, no live providers, sends or external account state. Actual PostgreSQL race/failure tests are required to confirm the proposed transaction fixes. No missing future API route or unconfigured live adapter was counted as a behavioural finding merely because implementation is ongoing.
