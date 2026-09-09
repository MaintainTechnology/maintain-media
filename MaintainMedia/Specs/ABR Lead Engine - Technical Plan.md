---
title: "ABR Lead Engine - Technical Plan"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/001-abr-lead-engine/plan.md"
source_sha256: 316e0cb994de916077511ef42f0114d9fafe339056c19bbc47416111a05a3425
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# Implementation Plan: ABR Lead Engine

**Feature**: `001-abr-lead-engine` | **Specification version**: 4.0 | **Date**: 2026-09-08 | **Spec**: [[ABR Lead Engine - Product Specification|spec.md]]

## Summary

Build an internal Python pipeline that first produces a controlled QBCC pilot worklist. Introduce whole-register ABR comparison after the four-week commercial gate passes. PostgreSQL owns mutable decisions, cursors, queues and suppression. Immutable Parquet snapshots support comparison. A small authenticated API supports immediate opt-outs, worklist updates and live action checks. It does not send, dial or provide a new frontend application.

This document defines the v4.0 implementation plan. The user subsequently authorised the application in `abn-leadgen/`; the Python package remains `abr_engine`. The original conceptual module paths below map to that application root, with cohesive controls consolidated in `control/service.py` and `control/api.py`; the [[ABR Lead Engine - Implementation Status|execution map]] links actual files and checks. External integrations begin as mocks. `deliverables/abr/extract_new_abns.py` and its claimed 30-rule corpus were absent at review. Recover and validate that corpus, or obtain approval for a separately reviewed replacement, before production classification. Development uses visibly synthetic rules.

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

No historical price or benchmark is accepted as current deployment evidence. Research decisions are in [[ABR Lead Engine - Research and Decisions|research.md]]; legal policy conclusions require the specified review gate.

## Constitution Check

| Principle | Design control |
|---|---|
| Truthful claims | Historical assertions separated from executed tests; absent rules explicitly tracked; FR-040/043 traceability. |
| Lawful, minimized acquisition | Mock-first development; source/counsel gates; own-domain identity proof; finite retention. |
| Server authority and human control | Live database checks, synchronous suppression acknowledgement, manual CRM approval. |
| Deterministic recovery | Content manifests and UUID snapshots, per-source atomic promotion, rule hashes, total ordering, durable outbox. |
| Evidence-backed acceptance | Real PostgreSQL tests, race/fault fixtures, clean-machine run, measured scale benchmark and pilot outcomes. |
| Proportional scope | Single Python codebase, small control API, no frontend or sending platform. |

Pre-design and post-design disposition: no intended exception. Document review does not pass legal, commercial or deployment gates. Check the finalized constitution again during implementation review.

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

Full-scale preflight accounts for current/prior/staged Parquet, promoted-lead database indexes/WAL, spill, downloads, backup/restore space plus 25 GiB headroom. An 8 GB/80 GB VPS is a candidate only. Start DuckDB at two threads with bounded spill and process-level limits; its 512 MiB buffer limit does not cap total RSS. Measure ingest/diff RSS <=2 GiB, 60-second representative 20.5M-row diff including output as stretch target, and <=6-hour full processing. A failed target requires profiling/capacity changes or an approved requirement amendment. Retention/deletion and backup limits are in [[ABR Lead Engine - Data Model|data-model.md]].

Implementation tuning,9September2026: the initial two-thread baseline was compared with one- and three-thread diff variants. The selected diff now uses three threads with400k-row partitions and the same512MB/8GB buffer/spill limits. Exact event values matched the reference. The three-thread observations were58.4 and104.0 seconds, versus116.5 seconds for the paired two-thread confirmation. These variable local results support the implementation choice without certifying consistent60-second performance, full XML processing or the target AU host. See [performance evidence](C:/Users/dalig/Desktop/MaintainTech/MaintainOrg/maintain-media/abn-leadgen/ops/acceptance/performance-thread-review.md); R36 targets and release obligations remain unchanged.

## Delivery sequence and gates

Foundation (schema, audit, suppression, source/collection assessments, retention, budget and mocks) precedes QBCC contact acquisition. Start the four-week pilot clock when usable authorized worklists and trained operator are available. No booked meeting triggers offer review and holds the live ABR phase. Synthetic ABR work can proceed while that commercial gate is closed. ABR acceptance needs a baseline and next coherent publication; do not require naturally occurring event types in a real release. Fixtures prove rare transitions.

Provider selection, credentials, VA country, source permission, counsel decision, recovered rules and proven hosting capacity are operational inputs. Their absence blocks corresponding live capabilities, not synthetic development. A documented manual DNCR receipt import is the initial option; do not assume inexpensive automated access. No one- or two-day compliant pilot promise is made.

## Contract precision
Read [[ABR Lead Engine - Build Contract Precision|contracts/precision.md]] with the interface/data-model contracts. It fixes source header mapping and grouping limits, staging ownership, DNS pinning, relevance evidence, retained aliases, cash authority and capacity admission without expanding product scope.
