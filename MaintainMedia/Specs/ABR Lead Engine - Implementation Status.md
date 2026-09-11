---
title: "ABR Lead Engine - Implementation Status"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/001-abr-lead-engine/implementation-status.md"
source_sha256: 7ae4ff1791c76febf0773dbbf7b7d6c110ebae5591e273b293702478dc282314
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# ABR Lead Engine implementation status

## Live pilot update — 11 September 2026

**Release 010 is running with real QBCC data, verified phone-only website
collection and the guarded GoHighLevel account enabled. This is a limited
internal-research pilot; no real business has been handed off to GHL.**
The separate delegated-owner decisions admit the QBCC, reviewed website and
individually approved phone-only CRM scopes until **24 September 2026,
23:18:20 UTC**. They do not represent Jon's signature, adviser approval,
individual lead approval or permission to contact.

The [actual activation](abn-leadgen/ops/acceptance/aws/ghl-dnd-pilot-activation-receipt-20260911.json)
added only four CRM gates in 009b; the later source-only 010 repair added two G7
revisions. The [current host readback](abn-leadgen/ops/acceptance/aws/cleanup010-host-20260911.json)
confirms 25 gates, two unchanged policies, 26 migrations and **one business,
two phone contacts, zero selected worklist rows, zero CRM outbox entries and
zero remote CRM identities**. The [current signed dashboard](abn-leadgen/ops/acceptance/live-sources/ghl-release010-dashboard-20260911.json)
reports approved GHL setup with HTTP 200/no-store; unsigned access returns 401.
The actual Sydney service credential also [verified the intended account](abn-leadgen/ops/acceptance/aws/ghl-sydney-account-verification-20260911.json)
at 01:52:26 UTC without performing a mutation.

Release 010 fixes a cleanup selection defect found after account activation:
completed accepted source intake had been treated as abandoned review staging,
causing a protective `INTAKE_NOT_UNREFERENCED` hold. Nothing was deleted.
The [reviewed fix](abn-leadgen/ops/acceptance/live-sources/qbcc-cleanup-lifecycle-fix-20260911.json)
passed 28 focused checks; unknown/inconsistent acceptance still holds, and
ordinary finite retention is unchanged. The [actual 010 cleanup](abn-leadgen/ops/acceptance/aws/cleanup010-actual-operation-20260911.json)
completed successfully at 02:18:58 UTC without decrypting records or deleting
accepted files. Retention completed successfully at 02:18:59 UTC. The host
verified all three accepted source artifacts against their ledger hashes/sizes.
Its API is active, and the latest worker/control/cleanup/retention runs all
succeeded. This does not certify future expiry or a business-data restore.
The [current role check](abn-leadgen/ops/acceptance/live-sources/ghl-release010-reviewer-controls-20260911.json)
confirms reviewer/admin access, hides CRM controls from an admin without reviewer
scope and denies a non-admin operator. Approval stays disabled for the unselected
business. The probe submitted no approval and exported no business.

The [actual GHL contract test](abn-leadgen/ops/acceptance/live-integration-20260910/ghl-live-account-contract-20260911.json)
used two labelled synthetic contacts and removed both. Mapping, group search,
duplicate protection, DND, clearing and unrelated-tag preservation passed.
Delayed provider indexing was observed and reconciled without another create;
release 009b also safely fetches a known update ID when search is empty. Every
mutation checks current local authority and the reviewed all-Draft workflow
inventory. Six workflows remained Draft with zero enrolments after the test.
This does not certify a real production outbox transfer or future administrator changes.

**The next real-hand-off blocker is engineering as well as evidence.** The live
DNCR receipt-format adapter is unfinished: `compliance.wash.import_receipt()`
rejects nonfixture receipts with `VENDOR_RECEIPT_MAPPING_PENDING`. After that
adapter is built and tested, a phone still needs genuine current clearance,
verification/locality and the business's qualification, selected tier A worklist
row and version-bound reviewer approval. GHL activation supplies none of these.
Do Not Disturb stays enabled and gives no permission to call or send messages.

The [limited vendor decision](abn-leadgen/ops/acceptance/live-integration-20260910/ghl-dnd-pilot-delegated-owner-20260911.json)
records US storage and US/India service/support, with unknown provider-backup
expiry and other stated vendor unknowns. It is not an Australian-only processing
or legal compliance claim. Separate removal authority remains finite through
10 September 2027, 23:18:20 UTC; it does not extend CRM acquisition.

The [accepted QBCC import](abn-leadgen/ops/acceptance/live-sources/qbcc-live-release007-result-20260911.json)
contains **11,034 discovery records**. Bulk licence status remains UNKNOWN and
the import created no automatic candidates. **One business** subsequently passed
a genuine current-licence and website-identity review. Its
[first live website job](abn-leadgen/ops/acceptance/live-sources/website-phone-first-live-result-20260911.json)
was verified complete at 00:50:49 UTC on 11 September: **four pages, six requests, two landline
contacts and zero extracted email contacts**. Both
[private evidence readbacks](abn-leadgen/ops/acceptance/live-sources/website-phone-private-evidence-readback-20260911.json)
matched the reviewed contact page. It still needs contact-permission review;
`export_eligible=false`, selected worklist count 0 and outreach disabled.

The [website activation receipt](abn-leadgen/ops/acceptance/aws/website-phone-pilot-activation-20260911.json)
records only mobile/landline collection, separately controlled retention and the
scoped expiry. Ordinary page evidence can incidentally contain email text; no
email contacts were extracted. Google Sheet publishing, automatic email harvesting,
broader ABR and outreach remain disabled. GHL is separately enabled at account
level, with zero real transfers. Collection does not establish call
permission or a current Do Not Call Register check.

The [current website deployment](website/acceptance/vercel/ghl-handoff-deployment-20260911.json)
is `dpl_4uugYiVhLyYZgKVeVMta1Wxcb7HZ`: READY, 74 uploaded files, 65 Sydney function
outputs and global Clerk middleware. Forty focused UI checks, lint, types, cloud
build and public/signed-out HTTP checks passed. The [updated public notice](website/acceptance/vercel/ghl-handoff-notice-readback-20260911.json)
was read back. These receipts do not certify a fresh signed-in staff browser
journey or Australian-only processing. Backend evidence records
[106 distinct local cases](abn-leadgen/ops/acceptance/live-sources/ghl-backend-review-20260911.json),
[107 core plus 74 GHL checks on isolated Sydney Linux](abn-leadgen/ops/acceptance/aws/backend009b-offline-tests-20260911.json),
and 32 activation-helper checks with independent review.

### How to use the current page

1. Open [the dashboard](https://www.maintainmedia.com.au/abn-lead-gen/dashboard) and sign in with your approved account. Licence, website and evidence reviews need the separately assigned reviewer role.
2. In **Latest leads**, select the reviewed business. Open **Review phone evidence** → **Open private captured evidence**. The completed collection still needs permission review; repeating the collection does not clear that restriction.
3. To review another business, scroll to **QBCC source review** → **Load source records**. Use the linked current licence checker and save the exact business/status evidence and check time. Only a matching eligible business becomes a lead.
4. Select the lead → **Review the business website identity**. Save its checked domain, decision and two independent evidence references.
5. Open **Collect phone details from the reviewed website**. Supply the checked HTTPS homepage ending in `/`, the site-terms evidence and review time. Tick the permission box only after checking the terms, then choose **Collect reviewed phone details**. Follow the saved job status and inspect its evidence.
6. Open **GoHighLevel hand-off** for the business. With no selected row, it should show **Not selected for hand-off**. Do not treat Setup's approved connection as individual approval. Once the missing live DNCR adapter and genuine contact/qualification checks are completed, only an eligible selected tier A row can receive **Approve this business for hand-off**. A queued result is not a completed transfer; the worker must return **Hand-off verified** after provider readback.

**T071 remains open.** The live DNCR adapter, eligible selected worklist, real GHL
outbox/suppression timing, disabled Google workflow and measured pilot remain
unfinished. Independent custody recovery, accepted business-data backup/quarantined
restore, capacity, recovery targets and external monitoring remain incomplete.
The 100-business classifier review and unfinished live ABR feed concern later ABR
expansion; they are not prerequisites for this first QBCC-only intake. The
[full-tool review](abn-leadgen/ops/production/live-completion.md) records
**87/100**, trajectory **57 → 72 → 77 → 82 → 85 → 87**. The latest two-point gain is
below the existing three-point meaningful-improvement threshold; no full-spec
pass or 9.0–10 application rating is claimed, nor that further work cannot
materially improve the score.

The earlier [post-collection host receipt](abn-leadgen/ops/acceptance/aws/website-phone-release008-host-20260911.json)
verified release 008 and a retention run from **00:54:15 to 00:54:18 UTC**: exit 0,
`primary_retention_complete`, no holds. Two encrypted contacts and two private
captures remain; queued website payloads, archives and action intents are all 0.
The current 010 host readback confirms the API, source/control recovery,
review-staging cleanup and retention schedule are active. Weekly QBCC admission
and all three backup timers remain disabled.
This is evidence of the current run, not future expiry performance, external
deletion, backup acceptance or a completed recovery drill.

## Historical implementation snapshot — 9 September 2026

The sections below preserve their original dated evidence and claims. Earlier
zero-data, fixture-only and closed-activation statements are superseded by the
verified pilot update above; historical scores are unchanged.

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
