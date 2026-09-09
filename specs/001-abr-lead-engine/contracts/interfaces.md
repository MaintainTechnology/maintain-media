# Interfaces v1 — specification v4.0

These contracts are proposed implementation requirements. Examples use synthetic identifiers. No external sender is implemented in Part 1. CLI/API schemas must be generated and contract-tested during implementation; breaking changes increment the contract major version.

## CLI and fixture safety

Entrypoint: `uv run abr-engine <command>`. Common flags: `--config PATH`, `--mode fixture|pilot|production` (default fixture), `--json`, `--run-id UUID` for resume. Configuration schema rejects unknown keys. Fixture mode refuses non-test databases and any configured live credential; it uses mock HTTP transports and fake business/contact data. Production requires explicit mode plus unexpired machine-readable capability gates.

| Command | Inputs and behavior |
|---|---|
| `validate-config` | Validate runtime, source allowlists, policy/rules versions and configured gates; redact secrets. Exit nonzero for invalid config. |
| `db migrate` | Apply ordered SQL under database migration lock; verify checksum; stop on edited/applied migration. |
| `run --source qbcc|abr|all` | Execute source stages and outputs. `all` reports sources independently; one failed source never advances the other cursor. No paid/external operation in fixture mode. |
| `resume --run-id UUID --stage NAME` | Resume idempotent committed work; verify snapshot/config/rule hashes. No implicit rebaseline or source mixing. |
| `baseline --source abr --reason TEXT` | Establish zero-event initial state or explicit history-gap baseline, authorized operator only; requires validated snapshot. |
| `wash import --file PATH --receipt PATH --batch-id UUID` | Parse provider-format normalized phone/result/timestamp rows; verify expected batch membership; one atomic import or quarantined report. |
| `worklist build --week YYYY-MM-DD` | Monday in Australia/Brisbane; latest gates, reserve/dedupe rules, immutable row IDs; repeated input revision reuses worklist rather than duplicating. |
| `crm drain --limit N` | Claim approved outbox entries; recheck latest gate; obey configured verified provider quotas; unknown response reconciles first. |
| `retention run --as-of ISO8601` | Operator-authorized production command; default preview of planned deletions; execution requires explicit `--execute` and release-configured retention policy. |
| `benchmark --rows 20500000 --output PATH` | Synthetic data, measured parser RSS/diff/load/WAL/disk; no live source access. Target hardware and exact lockfile recorded. |

Exit codes: 0 successful/no new publication; 2 invalid input/config; 3 source held/integrity failure; 4 another worker holds required lock; 5 integration unavailable/partial failure; 6 capability gate closed; 7 capacity preflight failed. Budget/quota deferral may exit 0 if all required stages completed safely, but manifest must say `complete_with_deferrals` and count every deferred candidate. stdout JSON uses `{schema_version,run_id,status,manifest_path,counts,alarms}`; stderr carries redacted diagnostic logs.

## Control API envelope and authorization

HTTPS JSON under `/v1`; max body 64 KiB. Authenticated actors use short-lived tokens issued by configured identity authority, checked for issuer/audience/expiry and `operator`, `reviewer`, `owner`, `compliance`, `sender` or `admin` scope. Apps Script service credential is stored in protected script properties and never in cells; it submits signed actor context for the actual editor. Unauthenticated requests cannot reveal contact existence. Protect cookies with CSRF controls if browser-session auth is used; service tokens are header-only. TLS and credentials are release prerequisites.

Mutation headers: `Authorization: Bearer ...`, `Idempotency-Key: UUID`, `X-Request-ID: UUID`. Same actor/key/body returns original receipt; changed body with same key returns 409. Error body: `{code,message,request_id,retryable,details}` with no raw endpoint. 401 unauthenticated, 403 wrong scope, 404 unknown object within authorized scope, 409 revision/idempotency conflict, 422 invalid fields, 429 bounded rate limit (`Retry-After`), 503 unavailable authority. Missing suppression or policy service always denies action.

Product-role mapping: owner may approve policy/gates; developer administers infrastructure/migrations and holds no automatic marketing-review authority; trained reviewer may assess identity/basis and approve tierA CRM rows; operator may read assigned rows, record outcomes, request suppression and run permitted call checks. `compliance` scope is explicitly assigned for evidence/deletion administration; `sender` is a separately certified service role. All humans need assigned scopes; an operator cannot grant themselves reviewer/owner scope. Evidence reads are audited. Reviewer decision endpoints use `reviewer` scope even where routine worklist endpoints use `operator`.

### POST /suppressions — immediate opt-out

Scope `operator` or `compliance`. Body: `{lead_id?, endpoint?, channel?, reason, source, requested_at, operator_note?}`. Require lead ID or endpoint. reason: unsubscribe/complaint/no_unsolicited_notice/cancellation/manual. Endpoint-only accepts a normalized raw value in TLS request, encrypts if needed and never logs it. For lead ID resolve canonical business plus aliases, suppress entity and all known endpoint tokens; future endpoints remain blocked by entity projection. For endpoint-only suppress globally across every linked entity. Cancellation targets business identity even with no contact rows.

Acquire canonical entity then sorted endpoint locks; commit suppression projection, audit, cancellation of pending intents/CRM jobs and deletion scheduling together. Respond **201 only after durable commit**: `{suppression_id,committed_at,scope,affected_leads,receipt_id}`. Retry returns 200 same receipt. Cannot commit ->503, never fake success. Cross-product central authority must acknowledge before UI says saved. Verbal opt-out uses this path immediately; routine outcome sync cannot postpone it.

Unauthenticated unsubscribe links use a separate `POST /unsubscribe/{opaque_token}` with random signed/hashed token bound only to suppression scope, no login/fee, no data read privileges. Expired link tokens still accept a narrowly scoped suppression after verifying server-held token mapping; never re-enable contacts because link lifetime ended. GET displays a minimal confirm page and does not mutate on email-security scanners. This utility page is not a lead-management frontend.

### PATCH /worklist-rows/{row_id}

Scope `operator`. Body: `{expected_version,status,attempts,invitation_state,invitation_evidence_ref?,notes?,occurred_at}`; invitation_state is invited/uninvited/unknown, with evidence required for invited; nonnegative attempts, notes <=2000 chars, maximum five-minute future timestamp skew. Allowed status values: `not_started`, `no_usable_contact`, `attempted_no_answer`, `contacted_not_interested`, `contacted_nurture`, `meeting_booked`, `meeting_held`, `disqualified`, `do_not_contact_requested`. Tier/signal/entity/score cannot be edited. Server derives meetings from dated events and retains independent outcome event history; booking never implies invitation.

For ordinary status, compare row version and update projection/audit atomically, returning `{row_id,version,status,saved_at}`. Stale edit returns409 plus safe current status/version, requiring operator refresh. `do_not_contact_requested` invokes suppression first and records request even if the outcome revision is stale; return `{suppression_committed:true,outcome_conflict:true,current_version}` when necessary. Suppression is never lost to an optimistic-lock conflict.

### POST /crm-approvals

Scope `reviewer`; body `{row_id,expected_version,decision: approve|reject,reason}`. Approved row must be selected tier A, have current eligibility, resolved identity and complete CRM mapping; otherwise409/422. Approval binds lead/contact/policy revision and payload digest. Atomic outbox creation returns `{approval_id,outbox_id,state}`. Later changes invalidate approval; no automatically inherited approval for a new endpoint/template/week. Raw tier A status never bypasses approval.

### Reviewer assessments

`POST /identity-assessments` requires reviewer scope and `{lead_id,registrable_domain,expected_revision,assessment:approved|rejected|ambiguous,method,evidence_refs,reason}`. Validate exact source identifier or documented two-attribute evidence, append a monotonic assessment_seq under lead/domain lock and atomically update current pointer. Return201 `{identity_id,assessment_seq,expires_at}`; approved default expiry90days, later negative/ambiguous evidence blocks immediately. `POST /licence-reviews` accepts `{lead_id,licence_number,status,identity_match,evidence_ref,reviewed_at}` and records current positive evidence valid no longer than30days.

`POST /basis-assessments` requires reviewer scope and `{contact_id,channel,expected_revision,basis_type,assessment_state,limbs?,express_scope?,evidence_provenance_id,reason}`. Inferred path needs pass/fail/unknown on four limbs; express path needs source/scope/time evidence, neither may create assumed consent. Validate composite evidence identity. Append assessment_seq and update current contact/channel pointer in one locked transaction, default expiry90days. Later fail/unknown/withdrawn always supersedes an older pass. Return201 `{basis_id,assessment_seq,expires_at}`; wrong evidence422, stale revision409. No “use prior pass” request field exists.

`POST /cancellation-resolutions` requires reviewer scope and `{lead_id,cancellation_event_id,positive_reactivation_evidence_ref,reason}`. It may append resolution of that specific cancellation reason only. Return active remaining reasons; unsubscribe/complaint and endpoint opt-outs cannot be resolved through this route or ordinary reactivation.

`POST /relevance-assessments` requires reviewer scope and `{contact_id,channel:email,campaign_id,template_id,content_sha256,policy_version,state:pass|fail|unknown,role_evidence_id,reason,expected_contact_revision}`. Server derives reviewer identity/time, validates evidence belongs to that exact contact, and appends assessment_seq/current pointer while holding group then endpoint locks. Return201 `{assessment_id,assessment_seq,expires_at}`; invalid evidence422/stale revision409. Expiry is earliest of24h or current basis/identity/policy expiry. Later fail/unknown supersedes prior pass and invalidates pending intents. Phone requests reject this email-only assessment route with422; phone uses approved script/calling policy.

### POST /action-intents and POST /action-intents/{id}/consume

Scope `sender` or authorized operator call-check. Create body `{lead_id,contact_id,channel,campaign_id,template_id,content_sha256,relevance_assessment_id?,script_policy_version?,expected_contact_revision,recipient_timezone}`. Email requires a stored exact current reviewer relevance assessment ID; reject caller-provided relevance booleans/actor assertions or an obsolete assessment. Phone requires current script_policy_version and uses no email basis/relevance row. Server derives group UUID and authenticated actor, confirms approved content/required fields, applicable policy, suppression and expiry. Phone checks latest wash, verified timezone and call window/holiday calendar. Unknown policy/timezone ->deny. Return `{intent_id,state:pending|denied,expires_at,reason_codes}`; pending lasts at most60seconds and is **not permission to send**.

Both candidate export and consume read latest committed identity assessment for exact lead+domain (approved and less than90days old), plus positive QBCC licence/status identity review no older than30days for QBCC groups. Email additionally requires latest contact/channel basis (later fail/unknown/withdrawn blocks) and current deliverable verification less than90days old; consume also requires exact current reviewer relevance assessment. Candidate export does not require per-message relevance. Phone uses latest valid wash and current approved script/calling policy, never fabricated email basis/relevance. Request IDs cannot choose old passes. Evidence domain matches captured page and constrained identity row.

Consume body `{dispatch_id,content_sha256}` under same group-UUID/endpoint serialization as suppression, identity/basis/relevance updates and wash imports. Recheck every applicable latest pointer/revision/predicate at transaction time; lock and transition once to consumed. Return `{decision:allowed|denied,decision_id,checked_at,dispatch_id,reason_codes}`. Replay of same dispatch returns receipt; different dispatch for consumed intent ->409. No caching or reuse across campaigns/contacts. A sender must consume immediately at actual dispatch (within five seconds; later requires fresh intent), cancel queued work on suppression notification and acknowledge eventual dispatch result via `POST /action-results` `{decision_id,dispatch_id,state:sent|failed|cancelled|uncertain,provider_ref?,occurred_at}`.

Linearization is consumption versus suppression commit within this service. If suppression commits first, consume denies. If an external send is already underway after consumption, it may complete despite suppression; the audit records decision/suppression/dispatch timing and cancellation attempt. There is no false claim of atomicity with an external provider. Tests include both orderings. An integration unable to enforce these requirements cannot enable the email/call action capability. A manual operator must use the live check immediately before dialling; a printed sheet is insufficient.

### POST /deletions and GET /deletions/{id}

Scope `compliance`; body `{lead_id,reason,requested_at,retain_suppression:true}`. Create suppression before scheduling deletion. Return202 `{job_id,state,primary_due_at,backup_expiry_at}`. GET exposes stage receipts (database, objects, Sheets, CRM, backups), scoped legal hold and errors. `complete` only when all applicable deletions/backup expiry verified; primary-only completion is distinct. No endpoint values in receipts.

### POST /operator-activities

Scope `operator`; body `{activity_id,worklist_id,lead_id?,category,started_at,ended_at,correction_of?}`. category calling/research/wash/review/admin; nonnegative bounded duration and actor from authentication. Idempotent201 receipt records actual work; overlapping intervals for one operator are unioned for total time. Corrections append, never rewrite history. The weekly two-hour measure aggregates every category, including off-sheet calls and manual washing.

## Spreadsheet contract

Protected columns: `row_id`, `worklist_id`, `lead_id`, `row_version`, `generated_at`, signal/tier/score, business identity, safe contact view, gate label, gate_checked_at, next action, opener. Editable columns map exactly to outcome API fields. Contacts with failed gate are masked; eligible contacts are visible only to authorized operators. Labels: “Email: needs send-time checks”, “Phone: check before calling”, “Do not contact”, “Needs review”; reasons distinguish missing wash, failed basis and other blocks. Never unconditional “OK to send”.

Apps Script uses immutable row UUID after sort/filter, never sheet row number as identity. Validate dropdowns for convenience and revalidate server-side for authority. Every edit displays Pending, Saved with receipt, or Not saved; retry transient failures with idempotency key. Opt-out failures prominently say “Do not contact; opt-out not yet saved” and require immediate control API retry/operator escalation. Poll/import ordinary edits at least every five minutes as recovery; no weekly suppression dependence. Record `{row_id,column,actor,timestamp}` as auxiliary edit telemetry only. Gaps below15minutes can estimate editing activity but cannot stand in for total worked time; operator activity ledger includes calls/research/wash/review/admin. No sensitive cell contents in activity sheet.

## CRM adapter contract

Input `CRMUpsertIntent`: location ID, opaque group UUID, approved payload digest/revision, chosen verified contact, custom-field map version, add-tags set and idempotency/outbox ID. Persist remote contact mapping per location/group UUID, never ABN/licence plaintext key. Before first create, query supported configured identity fields; exactly one consistent match establishes mapping, zero permits create, multiple/contradictory/shared-endpoint matches block for human review. Never assume vendor duplicate rules preserve business identity. After external deletion confirmation remove raw contact mapping and retain non-identifying job receipt only.

Custom fields map ABN, signal, score, tier, industry, entity class, state, website, positioning notes and basis summary to configured IDs/types validated in sandbox. Add/remove only engine-owned tags with dedicated endpoints; do not overwrite unrelated tags. Provider version/base URL/verified rate limits are configuration, backed by dated official documentation. On429 honor Retry-After and preserve queue; on5xx bounded retry; on timeout after create mark uncertain, reconcile by mapping/custom identity before retry. Partial batches retain success receipts and retry only unresolved intents. Dead-letter after five failed attempts with alarm and operator repair path. All tests mock remote I/O until explicit sandbox setup gate.

## Run manifest and report

Manifest v1 includes run/source IDs; observed metadata; prior/new UUID snapshots and digests; parser/schema/rules/config versions; row/member counts; canary values; baseline/history-gap status; event/tier counts; candidate queued/expired/carried/selected counts; enrichment attempted/completed/hit denominators by tier; requests/retries; reservation/actual/uncertain spend with currency/FX/month; CRM attempted/succeeded/retry/conflict counts; phase durations/RSS/disk/WAL; gate decisions; alarms with dedupe IDs; artifact digests. No credentials or raw contact details. Each alarm delivery is a durable outbox item with `{run_id,alarm_code,subject_key}` uniqueness; mocks verify payload and delivery retry without sending an email.

Reports link dated source evidence and include ABR/QBCC attribution. Operational rates report denominator and cohort window; booked/held meetings are distinct. GST registration and QBCC category are signals, never guarantees of revenue or buying intent.
