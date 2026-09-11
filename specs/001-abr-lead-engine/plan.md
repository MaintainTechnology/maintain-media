# Implementation Plan: ABR Lead Engine

**Feature**: `001-abr-lead-engine` | **Specification version**: 4.0 | **Date**: 2026-09-08 | **Spec**: [spec.md](spec.md)
**Scoped policy amendments:** QBCC-PILOT-2026-09-11, WEBSITE-PHONE-PILOT-2026-09-11, GHL-DND-PILOT-2026-09-11 and ABR-EARLY-VALIDATION-2026-09-11, each v1.0.0; qualification/rule hashes unchanged.

## Summary

Build an internal Python pipeline that produces a controlled QBCC pilot worklist. The new delegated-owner ABR early-validation decision permits private complete-baseline/comparison and real matching-review work alongside the unfinished four-week commercial pilot; it does not pass commercial or classifier acceptance. PostgreSQL owns mutable decisions, cursors, queues and suppression. Immutable Parquet snapshots support comparison. A small authenticated API supports immediate opt-outs, worklist updates and live action checks. It does not send or dial; the separately requested website dashboard is implemented without extending contact authority.

This document defines the v4.0 implementation plan. The user subsequently authorised the application in `abn-leadgen/`; the Python package remains `abr_engine`. The original conceptual module paths below map to that application root, with cohesive controls consolidated in `control/service.py` and `control/api.py`; the [execution map](implementation-status.md) links actual files and checks. External integrations begin as mocks. The 30 literal rules in `deliverables/abr/extract_new_abns.py` were recovered on 9 September 2026, superseding the earlier missing-file finding. The user approved their targeting direction, while the real 100-record precision review remains pending. The recovered review artifact stays inactive; fixture runtime defaults are unchanged.

## Technical Context

| Area | Chosen baseline |
|---|---|
| Runtime | Python 3.12.12; exact dependencies in `abn-leadgen/uv.lock`; use `uv sync --frozen`. This is the tested local lock, not a claim that packages are latest. |
| Pipeline | Typer CLI, Pydantic settings, HTTPX with bounded timeouts/retries, secure streaming XML parser rejecting DTDs/external entities. |
| Analytics | DuckDB, PyArrow, Zstandard Parquet. Start at 50,000-row batches; explicit 512 MiB DuckDB memory limit and spill directory; tune against measurement. |
| State | PostgreSQL 16, psycopg 3, ordered SQL migrations and deferred/composite foreign keys. Real PostgreSQL for constraint tests. |
| Crawl | BeautifulSoup, Protego, pinned public suffix list, phonenumbers AU metadata. No headless browser in v1; scripted-only publication is unavailable evidence. Requests enforce20s deadline,2MiB/page,6HTML pages,3redirects,20total requests and public-IP validation at connection/redirect. |
| Control API | FastAPI/Uvicorn behind TLS; authenticated service/operator scopes; justified by immediate suppression and action checks. |
| Outputs | Escaped Jinja2 HTML/Markdown using existing branding; Sheets adapter and Apps Script bridge; CRM adapter with durable outbox. |
| Operations | Linux systemd services/timers, PostgreSQL advisory locks, encrypted AU object storage/backups. Windows development uses isolated task-local PostgreSQL16.15; containerized PostgreSQL16 is an alternative. AU deployment and Linux timer drill remain pending. |
| Tests | pytest, HTTPX mock transport, frozen clock, PostgreSQL16 service, Ruff, type checker; fixture CI blocks external network. |
| Scale | Approximately 20M business rows is a benchmark workload, not an approved capacity promise; 60 worklist rows/week. |

No historical price or benchmark is accepted as current deployment evidence. Research decisions are in [research.md](research.md); legal policy conclusions require the specified review gate.

## Constitution Check

| Principle | Design control |
|---|---|
| Truthful claims | Historical assertions separated from executed tests; absent rules explicitly tracked; FR-040/043 traceability. |
| Lawful, minimized acquisition | Mock-first development; source/counsel gates; own-domain identity proof; finite retention. |
| Server authority and human control | Live database checks, synchronous suppression acknowledgement, manual CRM approval. |
| Deterministic recovery | Content manifests and UUID snapshots, per-source atomic promotion, rule hashes, total ordering, durable outbox. |
| Evidence-backed acceptance | Real PostgreSQL tests, race/fault fixtures, clean-machine run, measured scale benchmark and pilot outcomes. |
| Proportional scope | Single Python codebase, small control API, no frontend or sending platform. |

Original pre-design and post-design disposition: no intended exception. Document review does not pass legal, commercial or deployment gates.

**11 September 2026 impact review:** the user's express delegation authorises the
[canonical QBCC-only policy amendment](../abr-lead-engine.md#delegated-owner-qbcc-pilot-amendment--11-september-2026),
recorded in [the dated decision](../../abn-leadgen/ops/acceptance/live-sources/qbcc-pilot-delegated-owner-20260911.json).
This uses existing constitutional user authority without changing its principles.
It replaces the adviser prerequisite only for the 14-day manual QBCC intake/internal
review scope; no adviser report or general legal compliance is asserted. Existing
Sydney AWS/Vercel functions, Clerk and named private admin access are accepted with
unverified global/support/access countries explicitly recorded. Google/GHL, website
contact collection, ABR and outreach remain off.

The pilot G3 disposition accepts current encryption/access and bounded storage
evidence while deferring full DR and independent custody certification. It does
not satisfy production backup or wider recovery acceptance. The developer must
record real G2 mapping/source and applicable G7 evidence, verify finite deletion,
and keep source coherence, actual licence review, UNKNOWN and suppression checks.
Raw data expires within 30 days, accepted snapshots within 90, and unreferenced
intake staging within seven. Approval expiry stops new manual collection. No rule,
schema, migration, task checkbox, score or historical approval changes with this
amendment. Review includes capability separation, expiry, mismatched G2, actual
source parsing, private access and deletion; executed receipts remain separate.

**Subsequent 11 September 2026 impact review:** the user's new express delegation
supports a separate [website-phone pilot amendment](../abr-lead-engine.md#delegated-owner-website-phone-pilot-amendment--11-september-2026)
and [owner record](../../abn-leadgen/ops/acceptance/live-sources/website-phone-pilot-delegated-owner-20260911.json),
not an implied extension of QBCC approval. It allows manual own-domain collection
of valid Australian mobile/landline evidence for genuinely qualified QBCC records;
automated email extraction/indexing, outreach, external exports and other vendors
remain excluded. Existing source licence review, 90-day identity, actual per-site
terms less than 30 days old, robots, bounded static HTTP and suppression apply.
No adviser report or legal certification is invented. A source-specific public
notice must be published and read back before admission; no individual messages
are sent. Existing architecture/country uncertainty and limited recovery risk are
accepted separately for this additional contact-evidence scope.

Implement current hash-bound `website_collection` phone channels and expiry in the
approved policy; require own G1/G3/G7 and parent collection G1/G2/G3/G7 before queued
execution, around network I/O and before contact commit. Append a retention policy
version and scope evidence, keeping the old QBCC policy immutable. Apply 24-hour
encrypted pending-request expiry and profile-erasure cleanup; ordinary captures
expire after 90 days, profiles after 180 days without a crawl reset, unnecessary
suppressed/disqualified fields after 30 days. Explicit
`settings.retention.retain_selected_evidence=false` must prevent seven-year archives
and worklist-based page extensions, while retaining scoped holds and minimal
suppression aliases. Website authority co-terminates at 2026-09-24T23:18:20Z and
finite deletion authority stays at 2027-09-10T23:18:20Z.

Review phone-only positive/negative extraction, policy hash/channel/expiry binding,
authority withdrawal during I/O, pending-job expiry and concurrent erasure,
capture minimisation and absence of seven-year archival, private evidence access
and live notice readback. Record installed-release results separately. The
amendment does not change rules, targets, task checkboxes or historical scores,
and cannot invent a current licence/domain/terms review for a business.

### Impact review: GHL DND pilot authority

The [separate GHL amendment](../abr-lead-engine.md#delegated-owner-ghl-dnd-pilot-amendment--11-september-2026)
and [final owner record](../../abn-leadgen/ops/acceptance/live-integration-20260910/ghl-dnd-pilot-delegated-owner-20260911.json)
record the user's new delegated decision. Do not treat the existing website-phone
policy's source scope as permission for onward CRM disclosure; the new `crm/G1`
supplies that purpose, while the existing collection/retention policy is preserved.
The recorded US storage, US/India support, optional-routing and provider-backup
uncertainties apply to the named account only, with no adviser/contract-signature
claim and no outreach. Public notice and the actual synthetic account checks have
been verified; installed runtime and release-gate admission remain separate evidence.

Enforce `allowed_channels: [phone]`, DND and the reviewed complete all-Draft
workflow inventory hash before each mutation; recheck local authority after
inventory I/O. Preserve selected tier A, current individual row-version approval,
identity/suppression/verification/DNCR/locality checks and existing capacity limits.
No email, HTML capture, private excerpt or unrelated field is disclosed. Preserve
unrelated tags/customer records and duplicate settings. An empty search index must
not cause another create after uncertain creation or for a known remote identity.

Append only `crm` G1/G3/G5/G7 with exact owner, technical and installation hashes;
install the real 13-field config and seven check receipts. Preserve both existing
policies, source capability scope and prior authority rows. Acquisition G1/G7 ends
2026-09-24T23:18:20Z; minimum-removal installation/G3/G5 continues to
2027-09-10T23:18:20Z, still conditional on current account controls. Keep finite
retention, no export clock reset/no seven-year archive, and the explicit provider
backup limit. Record actual remote removal separately from future timed cleanup.
The activation helper previews by default, validates a stopped and unchanged
baseline, appends authority, verifies full readback and enables CRM alone. It
never starts services or approves a business, and failures preserve history and
stop services. Review failure/retry/identity/suppression boundaries and the exact
deployed release; leave historical task checkboxes and scores unchanged.

### Impact review: early ABR validation authority

The user's new explicit delegation is recorded in the [early ABR source-purpose
decision](../../abn-leadgen/ops/acceptance/live-sources/abr-early-validation-delegated-owner-20260911.json)
and [canonical amendment](../abr-lead-engine.md#delegated-owner-early-abr-validation-amendment--11-september-2026).
It prospectively changes R38/G6 business sequencing only for manual private source
validation, a complete baseline, later coherent diffs and genuine rule review.
Four measured QBCC weeks, commercial results, actual ABR source acceptance and the
100-record precision review are not claimed complete. Preserve the constitution,
product/rule baseline, original owner decisions and current QBCC/website/CRM scope.

Implement a live ABR source adapter using the actual current public XSD/readme,
complete resource/member inventory and inner transfer evidence. Do not enable the
synthetic `FixtureGeneration`, flat name paths or fixture-only rule artifact in
production. G2 must name the admitted source-validation phase separately from
operational classifier approval. Enforce a validation-only state that can commit a
complete zero-event baseline and private unqualified diffs while preventing ABR
lead/enrichment/worklist/vendor creation. Recheck current purpose/expiry and source
authority before network operations and final atomic commit; preserve replay,
no-op, historical recurrence and cross-source isolation. Do not use a filtered
sample as the full baseline or substitute a single effective-date filter for events.

Acquire and hash actual source/schema evidence and verify metadata again after
download. Reject incomplete, changed or mixed inventory, unsafe archives, unknown
schema/enums and invalid counts/duplicates. Measure remaining storage, existing
spill/process limits and required headroom before a whole-register run. Record
bounded capacity evidence honestly, retaining the uncompleted full-scale benchmark
and recovery acceptance. Existing raw30/snapshot90/staging7 retention must cover
new source artifacts and private review samples, without extending a retained
cursor or resetting profile clocks. Record any required append-only retention
continuation separately; preserve existing phone/no-seven-year restrictions.

Build a reproducible private stratified sample against the recovered30-rule hash:
at least100 independently reviewed classified businesses, spread across all rules,
BN/MAIN/TRD, geography and overlap; retain unresolved and negative outcomes. Bind
the computed per-rule/overall result and evidence references to source, mapping,
ordered rule IDs, reviewer/date and test digest. A synthetic truth label or edited
sample count cannot activate matching. More than10% false positives blocks the
affected rule; operational qualification requires a separately admitted current
review result. The source-validation phase can therefore proceed while this work
is pending without pretending the classifier passed.

Verify the ABR-specific public research notice before source-row collection. Retain
the dataset-specific CC BY3.0Australia attribution/change/no-endorsement notice,
personal-name acknowledgement and the existing Sydney/global-processing limits.
Scope current `abr` G1/G2/G3/G6/G7 to the actual phase and exact release, with G6
explicitly the early-sequencing decision rather than four-week completion. Manual
collection expires2026-09-24T23:18:20Z; separately admitted finite deletion remains
bounded through2027-09-10T23:18:20Z. No ABR-driven phone/email discovery, paid work,
Google/GHL transfer, automatic source timer or outreach follows from this amendment.
Do not change historical task checkboxes or scores because a decision is recorded.

## Project Structure

```text
specs/001-abr-lead-engine/
  spec.md plan.md research.md data-model.md quickstart.md tasks.md
  contracts/interfaces.md
  checklists/
abr_engine/
  pyproject.toml uv.lock .python-version README.md
  src/abr_engine/
    cli.py config.py db.py
    ingest/ diff/ classify/ qualify/ enrich/
    compliance/ control/ export/ ops/
  migrations/
  config/{rules,entity_types,service_terms,domain_blocklist,policy}.yaml
  assets/{public_suffix_list,postcode_localities}/
  templates/{report.html.j2,report.md.j2,worklist_schema.json}
  integrations/{sheets_bridge.gs,crm_fields.yaml}
  ops/{systemd,compose.test.yaml,runbook.md,release-gates.md}
  tests/{unit,contract,integration,fixtures,performance}/
```

Application paths are proposed deliverables, not claims that they exist. A dedicated `abr_engine/` folder preserves the media/vault workspace.

## Processing and transaction boundaries

1. **Observe:** ABR poll every six hours; QBCC weekly. Persist resource IDs, source timestamps, ETags, lengths and validators. Metadata is a discovery hint, not identity. Daily validator probes and weekly conditional download/digest reconciliation catch unchanged metadata republishes. Pair changed/unchanged ABR halves only when actual contents declare the same generation and pass all consistency checks. Hold conflicts; warn at 48 hours and escalate after seven days. No override bypasses content integrity.
2. **Stage:** run-specific download paths; resume only against matching server validators. Limit ZIP entries, paths, expansion and bytes; reject unsafe XML. Stream all members; assert declared counts, unique ABNs, schema and field-fill canaries. Conflicting QBCC attributes quarantine the candidate. Canonically sort names before hashing; member placement is not business data.
3. **Seal:** write `snapshots/{source}/{snapshot_uuid}/part-*.parquet`, canonical JSON manifest and SHA-256 digests. Snapshot identity hashes only stable mapped part/member labels and uncompressed member SHA-256 values using precision.md's exact projection; ZIP/download/retrieval metadata is evidence only. Verify object uploads before marking validated. Same-day changed content gets a new UUID; content equal to the current accepted cursor under the same parser/schema is a no-op. Historical A-to-B-to-A recurrence with fresh coherence evidence creates a new occurrence UUID and B-to-A events while content artifacts may be reused. Parser/schema changes require explicit migration/rebaseline, never historical rewriting.
4. **Prepare:** compare full-register Parquet with the committed cursor. Stage events and promoted lead-state changes by run/snapshot keys. Full-register classified state remains Parquet; PostgreSQL stores only promoted leads and controls. Readers keep using the committed snapshot until promotion. Status-effective dates are never represented as incorporation dates or revenue proof.
5. **Promote:** lock the source cursor; compare expected prior snapshot; atomically insert events, apply promoted lead changes/cancellation suppression/create candidates and advance that source cursor. A pre-commit crash exposes nothing; post-commit retry resumes from the promotion record. ABR and QBCC cursors succeed independently. Object-store failure cannot advance either cursor.
6. **Enrich:** claim persistent queue rows with `FOR UPDATE SKIP LOCKED`; recheck suppression, 90-day cooldown and budget before each external attempt. Domain identity proof precedes endpoint extraction. Retries consume ceilings and budget. Endpoint and initial provenance commit together under deferred constraints.
7. **Select:** expire unworked queue items at eight weeks; re-evaluate gates and final scores; group canonical business identities. Reserve up to ten slots for oldest eligible rows, then fill highest scores to 60. Exclude already-worked identities and duplicated endpoints in one worklist. Queue age/state survive weekly runs and failures.
8. **Deliver:** render review sheet/report. Explicit approval emits a version-bound CRM intent. Recheck approval and suppression at each outbox attempt. Routine outcome edits use optimistic concurrency; opt-outs use synchronous API writes immediately.

## Determinism

Classify BN names, main/legal display name, then TRD; exclude OTN. Within type use NFKC, uppercase, collapsed whitespace, deduplicate and sort normalized text then original text. First ordered rule on first matching name wins; capture literal text, rule ID and rule hash. BN confidence is a stronger name-source signal, not proof of current service. No recovered rules means no production ABR classification. The launch/rule-change precision gate uses at least 100 stratified records and holds affected rules above 10% false positives.

ABR score: A=60/B=30, high confidence=15/medium=5, target geography=10, company=5, highest contact contribution deliverable email=20/phone=15/website=5; cap 100. QBCC: A=60, Cat2=20/Cat1=15, Company=5, target geography=10, same contact contribution. Contact score is not permission. Across all sources use the single total order final_score descending, first_qualified_at ascending, lead_id ascending. Provisional enrichment order substitutes provisional_score; oldest reserve uses first_qualified_at then lead_id. Store UTC; use recipient IANA timezone for calls and Australia/Brisbane for monthly budgets/Monday worklist boundaries.

## Safety, storage and capacity

systemd uses a nonblocking `flock` on a fixed run path. PostgreSQL advisory locks key by source/stage and release when the owning connection closes. Work/CRM leases use random owner tokens, 120-second expiry and 30-second heartbeats; conditional renewal/completion requires matching owner and unexpired lease. Expired work is reclaimed only after provider uncertainty reconciliation, with side-effect idempotency keys preserved. Long-running parse holds its source advisory lock and refreshes run heartbeat; no remote mutable stage is completed merely because a lease expired.

The API serializes suppression and action consumption using common canonical entity/endpoint lock keys. Static worklist flags are never send permits. A downstream sender must revalidate at dispatch and support cancellation of queued work. Suppression committed before authorization consumption blocks it. External transmission already underway may not be recalled; record the race and cancellation attempt without claiming distributed atomicity. Unsupported downstream integrations leave actions disabled.

Lock identity is opaque group UUID plus endpoint token, never raw ABN/licence key. Email relevance is a stored reviewer assessment bound to exact contact/campaign/content, and caller flags cannot grant it. Phone has its own script/calling/wash branch without an email basis/relevance requirement. Identity, basis, relevance, wash and suppression changes share these locks and invalidate pending intents.

Encrypt endpoints and evidence with versioned envelope keys held outside the repository. Suppression matching uses HMAC-SHA256 over normalized value and canonical channel family; authorized Maintain products use the same central authority. Key rotation dual-reads/writes matching tokens until reconciled. Operators cannot mutate evidence, policy or audit tables directly.

Business-group UUIDs are all retained relational restriction/CRM/deletion keys. Source ABN/licence strings are encrypted active aliases, removed with profile erasure; separate minimal HMAC aliases retain only lookup token/type/key version and group link. Any `canonical_business_key` string is transient matching input, not a persisted key. Restriction matching survives deletion without preserving a plaintext marketing identity.

Full-scale preflight accounts for current/prior/staged Parquet, promoted-lead database indexes/WAL, spill, downloads, backup/restore space plus 25 GiB headroom. An 8 GB/80 GB VPS is a candidate only. Start DuckDB at two threads with bounded spill and process-level limits; its 512 MiB buffer limit does not cap total RSS. Measure ingest/diff RSS <=2 GiB, 60-second representative 20.5M-row diff including output as stretch target, and <=6-hour full processing. A failed target requires profiling/capacity changes or an approved requirement amendment. Retention/deletion and backup limits are in [data-model.md](data-model.md).

Implementation tuning,9September2026: the initial two-thread baseline was compared with one- and three-thread diff variants. The selected diff now uses three threads with400k-row partitions and the same512MB/8GB buffer/spill limits. Exact event values matched the reference. The three-thread observations were58.4 and104.0 seconds, versus116.5 seconds for the paired two-thread confirmation. These variable local results support the implementation choice without certifying consistent60-second performance, full XML processing or the target AU host. See [performance evidence](../../abn-leadgen/ops/acceptance/performance-thread-review.md); R36 targets and release obligations remain unchanged.

## Delivery sequence and gates

Foundation (schema, audit, suppression, source/collection assessments, retention, budget and mocks) precedes QBCC contact acquisition. Start the four-week pilot clock when usable authorized worklists and a trained operator are available. No booked meeting triggers offer review and the ordinary expansion hold. The dated early ABR amendment separately permits private source validation, baseline/comparison and matching review before that commercial decision; it does not pass the measured pilot or operational qualification. ABR acceptance needs a baseline and next coherent publication; do not require naturally occurring event types in a real release. Fixtures prove rare transitions.

Provider selection, credentials, VA country, source permission, counsel decision, recovered rules and proven hosting capacity are operational inputs. Their absence blocks corresponding live capabilities, not synthetic development. A documented manual DNCR receipt import is the initial option; do not assume inexpensive automated access. No one- or two-day compliant pilot promise is made.

## Contract precision
Read [contracts/precision.md](contracts/precision.md) with the interface/data-model contracts. It fixes source header mapping and grouping limits, staging ownership, DNS pinning, relevance evidence, retained aliases, cash authority and capacity admission without expanding product scope.
