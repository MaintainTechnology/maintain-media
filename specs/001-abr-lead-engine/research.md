# Research and Decisions — ABR Lead Engine v4.0
Reviewed2026-09-08. Decisions support synthetic implementation; production approvals are separate.

## Decision: begin with a contractor pilot
Rationale: a limited list tests customer fit without first building the national diff pipeline.
Alternative: ABR-first, which adds compute and source complexity before commercial evidence.
Foundation controls still precede any live pilot. The old1–2-day complete-delivery estimate is withdrawn.
Sources: canonical R38 and the preserved v3.5 commercial hypothesis.

## Decision: retain Python, analytical snapshots and a relational control authority
Python3.12 is a selected baseline, not a claim of latest release. Use uv to lock compatible supported
dependency versions at implementation. DuckDB/Arrow suit file analytics; PostgreSQL16 owns mutable
permission, suppression, identity, queue, money and delivery state.
Alternative: a full workflow platform or duplicating20M current businesses in the relational store.
Neither is required. Small FastAPI control service is justified by immediate opt-outs/live checks;
it is not a general customer dashboard. Scheduled work uses systemd timers, not two schedulers.
Verify actual migration constraints on PostgreSQL16:
[official CREATE TABLE](https://www.postgresql.org/docs/16/sql-createtable.html).
DuckDB buffer limits do not cap all RSS:
[official memory guidance](https://duckdb.org/docs/current/guides/performance/oom).
No SQL or performance test is claimed in this documentation pass.

## Decision: manual DNCR wash import for pilot
Rationale: official SOAP and SFTP documents require type D or above. Published table reviewed shows
B A$126 and D A$5,058; signup terms still need checking. At pilot size, manual upload plus validated
receipt import avoids assuming a cheap direct automated interface.
Alternatives: separately priced provider API, or explicit type D procurement.
Sources and access limitations: [independent source checks](../abr-review-source-checks.md).
Manual work counts toward the two-hour pilot hypothesis. Receipt adapter defaults disabled until
a real format fixture and account are configured; synthetic adapter is sufficient for build tests.

## Decision: source identifiers, not publication dates, identify snapshots
A content manifest and UUID preserve same-date corrections. Coherence checks cannot be waived.
One source cursor advances transactionally with events; delivery resumes separately.
Alternative: date-only keys and48-hour part pairing; rejected because corrections collide and
mixed generations can create false changes. See R2–R8 and data-model.md.

## Decision: human-confirmed identity and permission
SERP rank, business-name similarity, public email and email verification each answer different
questions. Require identity evidence and reviewed express/inferred permission before candidate
handoff. Exact reviewer/policy/version and evidence are auditable.
Alternative: auto-pass on own domain/sole-trader status; rejected as insufficient proof.
See source checks SRC-01/02/09 and R16/R21/R27.

## Decision: fresh action checks and durable opt-outs
Weekly Sheets ingestion cannot satisfy immediate suppression. The small authenticated control
service commits blocks synchronously, while Sheets/CRM projections catch up.
External systems must integrate the live boundary before controlled outreach is enabled.
Alternative: static “OK to send” labels; rejected because expiry/withdrawal makes them stale.
No promise is made about senders that bypass the service or already-dispatched messages.

## Decision: bounded storage and collection
Full snapshots90d, raw ZIP30d, unworked profiles180d, normal evidence90d, purpose-selected
evidence7y, backups35d; erased profiles30d after suppression/disqualification.
These are explicit maximum design defaults subject to approval before live collection.
Alternatives: indefinite raw register storage, or assuming a hash-only index can reproduce all
old field changes. Neither is accepted. R29 defines expiry, rebaseline and restore behaviour.

## Decision: protect billable operations before calling providers
Use atomic micro-AUD reservations, FX/tax/buffer tariff configuration and conservative unknown-
charge handling. Report prepaid commitments separately. A post-request total is not a spend cap.
Zero-cap and concurrency fixtures are required.

## Decision: no forced framework/package upgrades in this review
No app lockfile exists for this feature. Lock dependency versions in the implementation task,
scan them and record compatibility evidence; do not invent versions or pretend tests were run.
The existing website/brand project is separate and untouched.

## Evidence inventory
| Artifact | State in this checkout | Action |
|---|---|---|
| specs/abr-lead-engine.md | Existing, revised4.0 | Canonical authority |
| specs/abr-lead-engine.v3.5.backup.md | Preserved exact prior source | Historical archive |
| MaintainMedia/Specs/ABR Lead Engine.md | Existing vault mirror | Regenerate from canonical |
| deliverables/abr/extract_new_abns.py | Missing at review | Recover or approve replacement; do not fabricate |
| Intended30 trade rules | Missing verified source | Blocks production classifier only |
| ABR application/migrations/tests | To create | Listed unchecked in tasks |
| Full-source data/performance evidence | Not reproduced | Dated source smoke/benchmark tasks |
| Legal/vendor approvals and credentials | External/pending | G1–G7; adapters remain disabled |
| Prior SQL and9.1-second claims | Historical assertion | Not carried as passed evidence |
| LLM Council original review | Completed single-model retry | Original scored7.8/10 |
| Original mixed-provider Council attempt | Failed | No valid score; preserve errors |

## Clarification coverage
Scope, actors, data ownership, unknown states, costs, retention, retry, identity and release gates
have explicit defaults. User optional intake has no recorded reply. Budget/launch/vendor choices
are not silently invented as approvals. Open operational evidence does not block mocked design.

