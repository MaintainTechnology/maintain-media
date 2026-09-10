---
title: "ABR Lead Engine - Implementation Status"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/001-abr-lead-engine/implementation-status.md"
source_sha256: 18decbce231e1a73cd905c561b99f99315a593e562dfd2b9c5dab7eaf7ca76b5
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

> **Latest deployment, 11 September 2026:** release 006 is installed and verified;
> real business-data activation remains closed. See
> [[ABR Lead Engine - Activation Follow-up 2026-09-11|Current activation status and remaining decisions]].

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

Paths above are within `abn-leadgen/src/abr_engine/` unless a configuration, test, migration or ops artifact is named. The file-level test map is [requirements.json](abn-leadgen/tests/requirements.json). Tests exercise actual PostgreSQL16; external transports are mocked and fixture sockets reject non-loopback destinations.

## Evidence to open

- [Run and recovery instructions](abn-leadgen/README.md) and [operator runbook](abn-leadgen/ops/runbook.md).
- [Fixed scoring rubric](abn-leadgen/ops/acceptance/rubric.md) and [score trajectory](abn-leadgen/ops/acceptance/trajectory.md).
- [Independent handover](abn-leadgen/ops/acceptance/handover-drill.md), [browser review](abn-leadgen/ops/acceptance/browser-review.md) and [native restore receipt](abn-leadgen/ops/acceptance/native-backup-drill.json).
- [Initial two-thread resource receipt](abn-leadgen/ops/acceptance/diff-recheck-82f2b2206da3471dafed13746776852e.json):20.5M synthetic universe,20.295M rows per snapshot,1.435M output events in73.34s. The400k partition size was retained after200k/800k alternatives performed worse. Earlier OOM attempts remain recorded.
- [Current three-thread comparison](abn-leadgen/ops/acceptance/performance-thread-review.md): one thread took93.42s; three threads took58.42s with exact semantic equality across all1.435M events. Fresh two/three-thread confirmations took116.49/103.95s and produced identical output hashes. Three threads with400k partitions are selected; the diff's sampled RSS stayed below1GiB. Substantial local variance prevents a consistent60-second or target-host performance claim. AU-host and full XML pipeline certification remain pending.
- [Database/WAL sample](abn-leadgen/ops/acceptance/db-wal-sample-1000.json):1,000 real synthetic promoted records. WAL measurement is a concurrent cluster-wide upper bound, not exclusively attributable volume.

Immutable `abn-leadgen/ops/acceptance/verify-*/result.json` receipts contain exact commands, environment, exit codes, file hashes and whether the source stayed unchanged throughout checks. Intermediate suites are labelled separately. A shared parent Git commit cannot identify this untracked application tree.

## Full-spec review remains incomplete

No full-spec PASS or production-ready claim is made. [G1â€“G7](abn-leadgen/ops/release-gates.md) remain pending: qualified source/collection/channel/retention policy, actual legacy rules or approved replacement, authentic source discovery/schema smoke, AU infrastructure and Linux scheduler/access drill, actual wash/vendor contracts and sandbox mappings, separately certified action consumers, and measured four/eight-week pilot outcomes. Live modes remain blocked while these required inputs are absent. Hosted CI configuration exists; a local run does not prove GitHub Actions has executed.

Requirement-quality checklist completion is separate from implementation task completion, which is separate from release approval. Scores describe tested local engineering only. The task execution ledger links any completed checkbox to actual evidence; partial tasks and externally dependent tasks remain unchecked.

## Earlier verified fixture delivery

408 tests passed with zero failures/errors/skips. Frozen install, lint, types, document/vault validation and unchanged-source verification passed. The final local engineering score is 92/100; trajectory 68→86→91→92→92→92. 58/65 tasks are complete; seven remain partial or dependent on external evidence. See the [final build review](abn-leadgen/ops/acceptance/release-review.md) and [task ledger](specs/001-abr-lead-engine/task-evidence.json). Full-spec and production acceptance remain incomplete.

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
runtime/account dependencies are in the [live release review](abn-leadgen/ops/acceptance/live-release-review.md).
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

## Deployment addendum — 11 September 2026

This dated addendum supersedes the earlier statements that no Australian service
or private Google worklist has been installed. The original 9 September snapshot,
its source hash and historical scores above are preserved. It does not declare a
completed live pilot or change any approval.

The Python service is now running on the Maintain Media AWS host in Sydney at
[the engine health page](https://abn-engine.maintainmedia.com.au/health). The
installation receipt verifies public DNS, a valid HTTPS certificate, the private
PostgreSQL database using local peer authentication, and the installed application
schema. The deployment operator confirmed all 26 migrations. Runtime keys are
stored outside the repository, with a separate encrypted Windows recovery copy.
The API and the separate source/control recovery timers are running. Release 005
contains 153 manifest-bound source files and migration 026's transactional
restriction-ledger queue. Runtime queue privileges are limited to SELECT/UPDATE;
approval-gate writes remain denied. The source
worker, control worker and seven-day review-staging cleanup timers are enabled.
The weekly QBCC admission and retention timers are installed but disabled.

The health request returned 200. A dashboard request without authentication
returned 401. A short, request-bound service assertion for the current approved
Clerk actor returned 200 with pilot mode, zero leads and zero selected businesses.
The response was marked no-store. This verifies the server connection; it does not
verify a human's signed-in production browser session. Source capabilities remain
closed, and no source rows or release approvals were created by provisioning.

The implemented Next.js page at `/abn-lead-gen/dashboard` now has a real database
API, durable run receipts, current licence/website review, conflict-aware outcomes,
explicit CRM approval and immediate do-not-contact controls. It preserves the real
Clerk actor and explicit reviewer scope. An empty live database is displayed as
empty. Closed source or vendor approvals are shown as blocked, with no fixture
substitution. Bounded website collection leaves contact permission and email
verification unknown until their separate evidence is supplied.

The website passed a production build on Node 24.21.0, 50 authentication/bridge
tests, seven dashboard tests and scoped application linting. The frozen upload
contains only 72 approved website files, bound to the existing Maintain Technology
Vercel project. The remote origin and pilot transport variables are installed.
The published production release is `dpl_387fws7PqGeZ5fHhPstMwZWbK5w4`, aliased to
[the Maintain Media dashboard](https://www.maintainmedia.com.au/abn-lead-gen/dashboard).
All 12 public and signed-out GET/HEAD checks passed. Private pages redirect to
sign-in; private API requests without authentication are rejected before reaching
the engine. A signed-in staff browser journey remains unverified.

The first release's runtime region check found the dashboard/API in `iad1` despite
the configuration naming Sydney. The deployment operator corrected this with the
CLI's explicit Sydney region option. Independent inspection of the new release
confirmed all 59 non-middleware function outputs in `syd1`, including the dashboard,
private API, sign-in and sign-up. The Clerk `_middleware` component is replicated
globally. Therefore the entire request/authentication path is not claimed to be
Australian-only; Vercel and Clerk processing-country approvals remain separate.

The private Google Sheet is installed under `jeph@quotemax.com.au`, with Restricted
sharing and no other named readers. It has a protected, empty **ABN Worklist** tab
with all 29 headers. The original tab was preserved. The separate Apps Script was
saved, authorised and read back against the local source. Its edit and repair
triggers exist. The real HTTPS endpoint and two new matching keys are now installed
in the server and the owner's Apps Script properties. The owner verified all eight
saved properties and both key matches without recording key values. Its `ENABLED`
property remains false; the draft reader registry has no approved roles/evidence,
and the API registry setting remains unset. No genuine editor write-back,
suppression latency or live business-data disclosure has been verified. This is a
private installation with synchronisation still disabled.

The GHL integration is installed for the Maintain Media location, with 13 empty
field definitions and their named folder verified in the actual account. Its new
credential is in separate encrypted custody and on the Sydney service. The saved
integration now has only location and field-metadata read permissions; the
temporary field-write permission was removed and metadata reads passed again.
No contact permissions, contact writes or workflow changes were made. Collision,
workflow isolation, opt-out propagation, installation approval and actual contact
synchronisation remain incomplete.

The user separately approved a US$5/month allowance for one private Sydney backup
bucket and a decimal 100 GB application storage cap. That spending decision does
not approve business-data backups or provide an AWS billing hard stop. The actual
private bucket, scoped publisher and restricted host files are installed. At
2026-09-10T18:05:38Z, an encrypted random-value upload/download/decrypt/delete-
absence check passed without accessing a database or business data. Seven backup
units are installed; all three backup timers remain disabled. Missing authority
correctly held a manual test and raised a local alarm. External alert delivery
and stopped-timer monitoring remain unverified. The Windows DPAPI private-key
copy is in Codex's virtualized profile; independent custody recovery, a real
quarantined database restore and current backup authority are still required.
No production backup is accepted by the storage-probe receipt.

The source acceptance/review, bounded website collection, durable source worker,
weekly admission, separately gated retention, and encrypted backup/restore code
have additional positive, negative and recovery tests. Earlier preparation and
release-003 checks included 106 local schedule/maintenance cases, 106 selected
native Linux cases, and separate Windows suites of 507 unit and 376 integration
checks. Release 005 records 495 passing final unit tests, two deprecation warnings,
79 combined scheduler checks, seven retained-key checks and native Linux lock
contention/process-death recovery checks. These counts describe separate suites and
must not be added as if every case were unique. These are engineering results; source collection approval,
real vendor processing and the measured pilot remain separate.

Evidence for this checkpoint:

- [Australian installation receipt](../../abn-leadgen/ops/acceptance/aws/live-service-install-20260911.json).
- [Current runtime release 005 receipt](../../abn-leadgen/ops/acceptance/aws/live-service-release-005-20260911.json).
- [Private Google installation receipt](../../abn-leadgen/ops/acceptance/live-integration-20260910/google-installation.json).
- [Google matching-key connection preparation](../../abn-leadgen/ops/acceptance/live-integration-20260910/google-connection-preparation-20260911.json).
- [GHL field and restricted-scope verification](../../abn-leadgen/ops/acceptance/live-integration-20260910/ghl-browser-installation-20260911.json).
- [Backup spending decision](../../abn-leadgen/ops/acceptance/aws/backup-spend-approval-20260911.json).
- [Actual private storage installation and encrypted probe](../../abn-leadgen/ops/acceptance/aws/backup-storage-installation-20260911.json).
- [Backup coordinator checks](../../abn-leadgen/ops/acceptance/aws/backup-coordinator-final-20260911.xml).
- [Schedule and maintenance checks](../../abn-leadgen/ops/acceptance/live-sources/live-schedule-tests-20260911.xml).
- [Live dashboard contract and limits](../../website/specs/live-abn-dashboard.md).
- [Frozen website upload and Node 24 checks](../../website/specs/production-upload-2026-09-11.md).
- [Published function-region inspection](../../website/acceptance/vercel/deployment-20260911-function-regions.json).
- [Published public/auth HTTP checks](../../website/acceptance/vercel/dpl_387fws7PqGeZ5fHhPstMwZWbK5w4-http.json).

T071 remains open. The remaining acceptance includes approved source/privacy and
processing-location records, the real 100-business classification review, enabled
and tested Google synchronisation, real GHL contact and suppression verification,
actual business-data backup and quarantined restore evidence, independent custody
recovery, measured recovery loss/interval, target-host capacity, stopped-timer
monitoring and external alerts, a real staff browser journey, and the measured pilot. Full ABR
expansion remains conditional. Sending messages and making calls remain outside
this build. Current source and vendor gates must be met before collecting or
disclosing business records.
