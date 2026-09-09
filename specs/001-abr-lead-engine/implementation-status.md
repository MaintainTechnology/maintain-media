# ABR Lead Engine implementation status

Specification v4.0; execution update9September2026. The user's later request authorises the application at `abn-leadgen/`, with Python package `abr_engine`. It preserves R1â€“R43 and the Part1 exclusions. The original Council9.3/10 assessed documents; it is not the implementation score.

The local system runs on Python3.12.12 and isolated PostgreSQL16.15. It ingests synthetic ABR/QBCC publications, detects changes, qualifies and reviews businesses, enforces current contact restrictions, and writes a private worklist/report. It includes durable enrichment and CRM mock workers, an authenticated control API, budget reservations, operational alarms, retention and a native backup/restore drill. No live outreach or vendor calls were made.

## Actual implementation map

Conceptual `abr_engine/` paths in the original task descriptions mean the authorised `abn-leadgen/` application root. Cohesive modules consolidate some originally proposed files. This mapping records those implementation choices without changing required behaviour.

| Scope | Actual implementation | Executed evidence |
|---|---|---|
| R1â€“R8/R12 source integrity | `ingest/`, `diff/events.py`, `pipeline.py`, `ops/promotion.py`, migrations | Source unit fixtures, actual PostgreSQL recovery, pipeline crash/resume tests |
| R9â€“R14 classification/identity/queue | `classify/rules.py`, `qualify/`, `control/service.py`, `export/worklist.py` | Synthetic rules, tiers/geography, canonical merge, duplicate hints and fairness tests |
| R15â€“R20 enrichment/budget/provenance | `enrich/`, `control/service.py`, composite SQL constraints | Bounded crawl/DNS fixtures, durable worker, uncertain billing and contact-bound evidence tests |
| R21â€“R28 authority and action controls | `control/api.py`, `control/auth.py`, `control/service.py`, `compliance/wash.py` | Allowed/blocked contacts, latest decisions, scoped reads, opt-out/action races and recipient calling policy tests |
| R29/R41 retention and keys | `compliance/retention.py`, `compliance/keys.py`, `ops/backup.py` | Profile erasure, alias/key preservation and native pg_dump/pg_restore with latest ledger replay |
| R31â€“R34/R38 work delivery and metrics | `export/`, `integrations/`, `ops/summary.py` | Escaped responsive report, outcome/actor tests, mock CRM recovery, dated group/time/cost metrics |
| R35â€“R37/R39 operations and checks | `ops/monitor.py`, `ops/systemd/`, `ops/verify.py`, README/runbook | Alarm/recovery tests, independent README drill, local capacity sample, frozen verification receipts |
| R40/R42/R43 boundaries and traceability | Configuration gates, source evidence, tests/requirements.json, this package |43 acceptance mappings; no live release claim; document and vault hashes |

Paths above are within `abn-leadgen/src/abr_engine/` unless a configuration, test, migration or ops artifact is named. The file-level test map is [requirements.json](../../abn-leadgen/tests/requirements.json). Tests exercise actual PostgreSQL16; external transports are mocked and fixture sockets reject non-loopback destinations.

## Evidence to open

- [Run and recovery instructions](../../abn-leadgen/README.md) and [operator runbook](../../abn-leadgen/ops/runbook.md).
- [Fixed scoring rubric](../../abn-leadgen/ops/acceptance/rubric.md) and [score trajectory](../../abn-leadgen/ops/acceptance/trajectory.md).
- [Independent handover](../../abn-leadgen/ops/acceptance/handover-drill.md), [browser review](../../abn-leadgen/ops/acceptance/browser-review.md) and [native restore receipt](../../abn-leadgen/ops/acceptance/native-backup-drill.json).
- [Initial two-thread resource receipt](../../abn-leadgen/ops/acceptance/diff-recheck-82f2b2206da3471dafed13746776852e.json):20.5M synthetic universe,20.295M rows per snapshot,1.435M output events in73.34s. The400k partition size was retained after200k/800k alternatives performed worse. Earlier OOM attempts remain recorded.
- [Current three-thread comparison](../../abn-leadgen/ops/acceptance/performance-thread-review.md): one thread took93.42s; three threads took58.42s with exact semantic equality across all1.435M events. Fresh two/three-thread confirmations took116.49/103.95s and produced identical output hashes. Three threads with400k partitions are selected; the diff's sampled RSS stayed below1GiB. Substantial local variance prevents a consistent60-second or target-host performance claim. AU-host and full XML pipeline certification remain pending.
- [Database/WAL sample](../../abn-leadgen/ops/acceptance/db-wal-sample-1000.json):1,000 real synthetic promoted records. WAL measurement is a concurrent cluster-wide upper bound, not exclusively attributable volume.

Immutable `abn-leadgen/ops/acceptance/verify-*/result.json` receipts contain exact commands, environment, exit codes, file hashes and whether the source stayed unchanged throughout checks. Intermediate suites are labelled separately. A shared parent Git commit cannot identify this untracked application tree.

## Full-spec review remains incomplete

No full-spec PASS or production-ready claim is made. [G1â€“G7](../../abn-leadgen/ops/release-gates.md) remain pending: qualified source/collection/channel/retention policy, actual legacy rules or approved replacement, authentic source discovery/schema smoke, AU infrastructure and Linux scheduler/access drill, actual wash/vendor contracts and sandbox mappings, separately certified action consumers, and measured four/eight-week pilot outcomes. Live modes remain blocked while these required inputs are absent. Hosted CI configuration exists; a local run does not prove GitHub Actions has executed.

Requirement-quality checklist completion is separate from implementation task completion, which is separate from release approval. Scores describe tested local engineering only. The task execution ledger links any completed checkbox to actual evidence; partial tasks and externally dependent tasks remain unchecked.

## Earlier verified fixture delivery

408 tests passed with zero failures/errors/skips. Frozen install, lint, types, document/vault validation and unchanged-source verification passed. The final local engineering score is 92/100; trajectory 68→86→91→92→92→92. 58/65 tasks are complete; seven remain partial or dependent on external evidence. See the [final build review](../../abn-leadgen/ops/acceptance/release-review.md) and [task ledger](task-evidence.json). Full-spec and production acceptance remain incomplete.

## Live implementation update — 9 September 2026

The user's current request authorises work towards real sources, approved targeting,
installed staff integrations and production operation. The exact legacy 30-rule file
is now recovered; the user approved its targeting direction and the geography,
QBCC category and weekly limit defaults. Earlier missing-file statements are superseded.
The real 100-business precision review remains pending.

Current official catalogue metadata is reachable. The authentic QBCC schema, real GHL
transport, private standalone Sheets installer and production preparation tools are
implemented and locally verified; none of these observations alone establishes a live
worklist or installed production service. Current status, exact receipts and remaining
runtime/account dependencies are in the [live release review](../../abn-leadgen/ops/acceptance/live-release-review.md).
Phase 10 tasks distinguish this work from the earlier fixture evidence.

T071 now includes a separate approved-file QBCC intake path with encrypted review
records, immutable raw custody and narrow seven-day expiry/crash recovery. It
preserves UNKNOWN licence status, does not create candidates or advance the accepted
cursor, and has not ingested real business rows. The protected licence review,
promotion and live worklist integration remain pending.

The final combined live-preparation verification passed 641 tests with no
failures/errors/skips, plus Ruff and mypy for 60 application modules and the
production preparer. Application and Python test source hashes stayed unchanged.
These synthetic/local checks do not establish real-data acceptance, installed
accounts, a running AU production service or elapsed pilot outcomes.
