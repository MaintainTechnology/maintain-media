# Production preparation and host acceptance

This directory contains the separate manifest, systemd-bundle and host-acceptance
preparer. Its `render` and `check` commands do not install their output, create
approval records, migrate a database or enable adapters. The existing fixture
units in `../systemd/` are unchanged. Prepared bundles and historical acceptance
receipts must not be mistaken for the current installed service.

**Current result, checked 11 September 2026 (Manila): release 008 is running with
real QBCC records and a completed, manually reviewed phone-only website collection.**
The separate delegated-owner pilot decisions authorise the limited QBCC and
website research scopes until **24 September 2026, 23:18:20 UTC**. They are not a
general production approval or a qualified adviser's certification.

The QBCC import accepted **11,034 discovery records** with UNKNOWN bulk licence
status and **no automatic qualification**. One business subsequently passed a
genuine current-licence and website-identity review. Its live website job was verified
complete at 00:50:49 UTC on 11 September: **four pages, six requests, two landline contacts
and zero extracted email contacts**. Both private evidence readbacks matched the
reviewed contact page. The business still needs contact-permission review:
`export_eligible=false`, selected worklist count 0 and outreach disabled.

The live page is [ABN Lead Gen](https://www.maintainmedia.com.au/abn-lead-gen/dashboard).
Vercel release `dpl_Ex1sbMr6Ti2KxpqZybQhzisU5Enj` is READY with 74 uploaded files,
65 Sydney function outputs and global Clerk middleware. Its build/types and 12
public/signed-out HTTP checks passed. The public
[business research notice](https://www.maintainmedia.com.au/business-research-notice)
returned 200. This does not certify a fresh signed-in staff browser journey or
Australian-only processing.

To use it:

1. Open the dashboard and sign in with your approved Maintain Media account. Review actions require the separately assigned reviewer role.
2. In **Latest leads**, select the reviewed business. Open **Review phone evidence**, then **Open private captured evidence** to inspect what was saved. A completed collection does not mean permission to call; do not rerun it to clear that restriction.
3. For another business, scroll to **QBCC source review** and choose **Load source records**. Open the linked licence checker, check the exact business and current status, then save the evidence and check time. Only a matching eligible business becomes a lead.
4. Select that lead and open **Review the business website identity**. Record its domain, checked decision and two independent evidence references, then choose **Save identity review**.
5. Open **Collect phone details from the reviewed website**. Enter the checked HTTPS homepage ending in `/`, record the site's terms evidence and review time, tick the explicit permission box, then choose **Collect reviewed phone details**. Follow its saved job status and inspect the evidence. Do not tick the box without checking the terms.

Evidence: [accepted QBCC import](../acceptance/live-sources/qbcc-live-release007-result-20260911.json),
[website activation](../acceptance/aws/website-phone-pilot-activation-20260911.json),
[first live website result](../acceptance/live-sources/website-phone-first-live-result-20260911.json),
[private evidence readback](../acceptance/live-sources/website-phone-private-evidence-readback-20260911.json),
and [website deployment](../../../website/acceptance/vercel/website-phone-deployment-20260911.json).
The [first live QBCC brief](first-live-qbcc.md) gives the wider operating context.

Google/GHL hand-off, automatic email harvesting, ABR expansion and outreach remain
disabled. The measured pilot, independent key recovery, accepted business-data
backup/restore and other full-production checks remain incomplete.

The [post-collection host receipt](../acceptance/aws/website-phone-release008-host-20260911.json)
verifies a retention run from **00:54:15 to 00:54:18 UTC**, exit 0,
`primary_retention_complete`, with no holds. The API, source/control recovery,
review-staging cleanup and retention schedule are active. Weekly QBCC admission
and all three backup timers remain disabled. The host records two encrypted
contacts, two private captures, no remaining queued website payloads, no archives
and no action intents. This confirms the current retention run, not future expiry
performance, external deletion, backup acceptance or a completed recovery drill.

## Earlier installation checkpoint — release 005

The following installation details and test counts preserve the earlier checkpoint.
Its zero-data and closed-capability observations are superseded by release 008
above. The original
[`live-service-release-005-20260911.json`](../acceptance/aws/live-service-release-005-20260911.json)
remains historical evidence, not the latest activation state.

QBCC pipeline, dashboard, CRM drain and suppression wiring now exist. The guarded
legacy `serve` command is still fixture-only; the installed nonfixture service
uses the dedicated `live-serve` command. Direct uvicorn invocation is unnecessary
and must not bypass its configuration and authentication setup. ABR expansion
mapping, the measured QBCC pilot and its later expansion decision remain separate
unverified work.

Google's protected private worklist and matching server/script connection keys
are installed and read back. Its script stays disabled, with no active reader
registry or live pull. GHL's dedicated credential and all 13 empty mapped fields
are installed; folder assignment and removal of temporary field-write permission
are verified. Only metadata read scopes remain. See
[`LIVE-INSTALLATION.md`](../../integrations/LIVE-INSTALLATION.md) for the actual
receipts and remaining staff, collision, workflow and suppression tests.

The real backup CLI and S3 transport are installed. At **2026-09-10 18:05:38 UTC**
(11 September, 02:05 Manila), the actual Sydney storage probe encrypted a random
test value, uploaded it, downloaded and decrypted it successfully, then deleted
the exact test object and verified absence. It accessed no database or business
data. The private bucket, scoped publisher, host files and permissions are
installed; the bucket has public access blocked, no version history and a 34-day
lifecycle rule. See
[`backup-storage-installation-20260911.json`](../acceptance/aws/backup-storage-installation-20260911.json).
This is verified storage preparation, **not an accepted production backup**.

Release 005 also applied migration 026 with runtime queue privileges limited to
`SELECT/UPDATE` and no gate-write permission. Seven backup units are installed;
all three backup timers (daily, ledger and expiry) remain **disabled**. The manual
missing-authority check correctly held with exit 3; its local failure alarm exited
0 and the expected test failure state was reset. This verifies refusal and local
alarm recording, not external alert delivery or detection of a stopped timer.
The ledger baseline is generation 1, acknowledged generation 0.
The final release receipt records 495 passing unit tests with two deprecation
warnings. Native Linux checks also verified rejection of concurrent publishers,
recovery after a publisher process was killed and an independent capture lock;
those lock checks accessed neither the database nor the provider.

The private backup key is protected by current-user Windows DPAPI in Codex's
virtualized Windows profile; the canonical custody path was confirmed by the
operator. It is not on the Sydney source host. Independent custody recovery and
recovery of engine wrapping/encryption and retained lookup keys remain unproved.
Wider source/privacy/vendor records, approved backup authority, a real quarantined
restore, measured recovery loss/interval, stopped-timer monitoring, external
alerts, current-control recovery, matching accuracy, capacity and the measured
QBCC pilot remain full-production requirements. The scoped decisions above do not
pass those wider requirements. Prepared configuration is not approval.

## Prepare a reviewable bundle

From `abn-leadgen/`, using the locked Python 3.12 environment:

```powershell
uv run --frozen python ops/production/prepare.py render --plan ops/production/deployment-plan.example.json --output ops/acceptance/production-preparation
uv run --frozen python ops/production/prepare.py check --plan ops/acceptance/production-preparation/deployment-plan.json --manifest ops/acceptance/production-preparation/deployment-manifest.json --receipt ops/acceptance/production-preparation/host-check.json
```

Choose a new output directory for each preparation; existing bundles/receipts are never overwritten.
`render` returning 0 means the files were prepared, **not** that deployment is ready. `check` returns
6 for blockers and 2 for invalid input. On this Windows development machine it cannot pass the Linux,
provisioned-host, current evidence, private paths and core release gates. No remote host is contacted.

Copy the example to an operator-owned non-secret plan and replace its example deployment UUID.
Supply the actual provisioned hostname, provider/region and contractual AU residency reference.
Evidence fields contain only `record_id` (UUID), `sha256`, `checked_at` and `expires_at` (aware ISO
times). References do not self-approve anything: current machine-readable database gates are checked
separately by `abr-engine release-check --config ... --mode pilot|production`.

Required evidence covers the host egress firewall, backup contract, quarantine restore drill,
Linux scheduler drill and measured capacity. Keep all source/policy/vendor credentials, database
URLs and wrapping material out of this plan and bundle. The compiler rejects unrecognised fields.
Private configuration lives outside both the code and backup/artifact directories.

Capacity uses the existing `abr_engine.ops.capacity.CapacityPlan` names and formula: all remaining
download, staged Parquet, prior/new snapshot, spill, database/WAL and temporary backup allocations
plus 25 GiB free. Every bound must be measured; unknown is not zero. `existing_allocations` is
informational and is not charged twice. AU-host output-bearing performance/RSS measurements remain
required; a source-code hash or local fixture benchmark does not prove sufficient host capacity.

The bundle includes exact code-file digests and `uv.lock` digest. It refuses a changed plan or code
tree at startup; recompile the bundle after a legitimate release change and repeat acceptance.
Dotenv files, private key containers and credential/key-store data filenames within inventory
directories cause preparation to fail before their contents are read. Keep these files in the
declared private configuration locations; source modules, documentation and static assets remain
eligible for hashing. Sensitive parent directories, file/directory symlinks and Windows reparse
points are rejected before traversal or content reads; release inventory traversal never follows
directory links.

## Provisioned-host installation sequence

This is the preparer's generic gated-bundle sequence for a confirmed AU host,
not a report that all steps are outstanding or a replacement for the installed
`abr-engine-*` service procedure. Use the dated receipts above to establish what
is already installed before applying a new bundle. Do not run it against an
inferred host or replace an active service from these examples.

1. Provision the dedicated non-root `abr-engine` identity, Python 3.12, PostgreSQL 16, systemd,
   locked dependencies and a root-owned `/opt/abn-leadgen` release. Provision private writable
   `/var/lib/abr-engine` storage. The native PostgreSQL reference path is
   `/usr/lib/postgresql/16/bin/pg_dump`; adjust the verified platform contract through review if the
   chosen distribution uses another path. No package is downloaded by this preparer.
2. Supply the real private YAML config, encrypted key store and externally managed wrapping key.
   The existing key loader accepts `ABR_KEYSTORE_WRAPPING_KEY`; `EnvironmentFile` may be provisioned
   by the chosen secret manager. This tool neither creates nor reads that file's contents. Restrict
   private configuration to 0600 or 0640 with the dedicated group and verify the service can read
   its config/key envelope. Secret material must not appear in command arguments or logs.
3. Establish AU database/object/evidence/backup commitments, restricted TLS/identity entry points
   and host-level egress controls. `RestrictAddressFamilies` is not a private-IP firewall. Deny
   cloud metadata/private network destinations for the crawler while allowing only the explicitly
   needed private database/control flows. Never expose the loopback engine port publicly.
4. Run the approved schema migration with exact `db migrate --config ... --mode pilot` arguments
   only against the confirmed new/private target database. Establish the machine-readable gates
   from real owner evidence and complete the outstanding account/activation contracts.
   A YAML mode/capability switch alone never satisfies this step.
5. Copy the reviewed bundle plan and manifest to their declared private paths. Re-run the preparer
   as the actual service identity. It checks the current host, systemd/Python/PostgreSQL, code/plan
   hashes, file permission metadata, measured disk admission, current backup receipt and finally
   the read-only core `release-check`. It does not print config/key contents or core diagnostics.
6. Validate unit syntax using `systemd-analyze verify` before installation. The rendered units
   have no installation side effects. Install only after acceptance; run a controlled foreground
   CLI cycle and same-run recovery before enabling the timers. Preserve the exact command,
   revision, environment and private receipts. Review static report access and current suppression.
7. Confirm there are no cron/other scheduler duplicates and disable the old fixture timers on
   this host. The production source timers conflict with their fixture counterparts and share the
   nonblocking `/run/abr-engine/pipeline.lock`. An overlap exits 4; it is a skipped admission, not
   a source success. Exercise simultaneous starts/crash recovery and inspect durable stage locks.

The pilot bundle includes weekly Monday QBCC discovery, UTC, with persistent catch-up. It omits
ABR units entirely. **Start the QBCC pilot first.** A separately compiled production plan adds
six-hour ABR discovery and must pass the four measured QBCC weeks and current G6 expansion decision.
This preparer's API template still targets the guarded legacy `serve` entry point;
it is not the installed live API unit. The installed service uses `live-serve` on
loopback behind the authenticated HTTPS deployment. Do not install the legacy
template over it or use the old 8767 fixture page as evidence of a live connection.
Worker/control timer activity does not by itself authorize source discovery.

The monitor calls `alarms check` once per minute. Its `check --scope monitor` verifies only the
declared host, runtime and immutable/private paths; expired policy, backup or capacity evidence
cannot prevent observation of those failures. It does not call the core release gate, and its
successful status is `host_integrity_ready`. Source/API/general retention services keep their full
release preflight; the dedicated intake cleanup below uses the same host/integrity check.
There is deliberately no mock `alarms drain`
disguised as production delivery. Real operations-channel delivery is a separately configured
adapter/gate. An empty database raises `RUN_NOT_FOUND` and fails the monitor service; it is not a
successful health result. Initial source execution must establish a run before run-based monitoring
works, and host-level unit-failure delivery is still needed for database/credential failures.
The daily retention service includes `--execute`, so it is a destructive operation after release
gates pass: preview the same command without `--execute`, approve retention/holds and complete the
restore drill first. No retention command is executed during bundle preparation.

Both pilot and production bundles include a separate `abr-live-qbcc-review-cleanup` service and
daily timer at 03:05 UTC, with persistent catch-up. It invokes
`sources cleanup-qbcc-review --config /etc/abr-engine/config.yaml --execute`, using the plan's
actual private config path. This command handles only the managed seven-day QBCC review staging
and interrupted-intake cleanup; it enforces owned artifact paths, holds and managed configuration
itself. The host/integrity preflight lets cleanup run when collection approvals have expired.
It does not admit candidates, advance accepted source state or enable the general retention unit.
Rendering these particular files does not install or execute them. The separately
installed `abr-engine-qbcc-review-cleanup.timer` is recorded in release 005; do not
add a duplicate cleanup schedule from this generic bundle.

## Backup creation, verification and restore

The implemented `ops/aws/backup_cli.py` provides `create`, `ledger`, `expire` and
`restore`. It creates an actual PostgreSQL dump and verified artifact archive,
encrypts before upload, uses the private Sydney S3 transport and verifies object
read-back. The independent ledger operation captures suppression/erasure state;
restore keeps a fresh isolated cluster quarantined. Release 005 includes the
transactional ledger queue and disabled backup scheduling units. See
[`backup-operations.md`](../aws/backup-operations.md) for the full command,
authority, custody and recovery contracts. The older `backup drill` remains
fixture-only and is not the production create command.

Actual bucket/identity installation and the encrypted random-value
upload/read-back/decrypt/deletion check now have dated evidence. They do not prove
database or artifact recovery. Approved authority and independent custody
recovery, scheduled execution, acknowledged newer restriction ledgers, measured
recovery loss/interval, stopped-timer detection and a quarantined restore still
need evidence. Retain
wrapping/encryption material and all required lookup-key versions in separate
managed custody; do not put the backup private key on the source host. Expiry
must be checked against the 35-day limit, including interruptions and retries.

The approved backup operation writes a restricted JSON receipt to `backup_receipt_path`. The
`BackupReceipt` schema in `prepare.py` is the executable contract. It requires the deployment and
backup UUIDs; `status:complete`; `country:AU`; `encryption:encrypted_separate_key_custody`;
`completed_at`, `expires_at`, `ledger_watermark`; provider evidence; and exactly one encrypted
component each for `database`, `artifacts` and `suppression_erasure_ledger`. Each component has an
opaque object UUID, SHA-256 and positive encrypted byte count. No endpoint, key, signed URL or
database connection string is accepted. The receipt's captured ledger watermark must be within
five minutes before completion; this is a backup-capture check, not proof that a later restore has
the newest ledger. Keep the independent ledger current between daily backups.

```bash
/opt/abn-leadgen/.venv/bin/python /opt/abn-leadgen/ops/production/prepare.py verify-backup --plan /etc/abr-engine/deployment-plan.json --receipt /var/lib/abr-engine/receipts/latest-backup.json
```

This preparer's hourly backup-check timer validates receipt structure, deployment binding, component coverage,
24-hour freshness and 35-day maximum retention. **It does not create a backup, fetch a remote
object, verify encryption or prove a restore.** Its `receipt_valid` status is intentionally narrower
than deployment readiness. Missing/stale receipts fail the unit; configured redacted operations
delivery must independently report that failure once its adapter is approved. The actual backup
job must use the same systemd scheduler, not a second cron schedule.
The separately installed backup timers remain disabled; their presence and the
manual negative check are not proof of unattended execution or outside alerts.

Restore into a fresh isolated AU quarantine with user evidence access and outward actions closed.
Verify backup digests/provider receipts, restore database and artifacts, import the latest independent
suppression/erasure ledger (including changes after the backup), reconcile every required lookup
version and run overdue retention. Test pre/post-backup suppressions, an erased profile and an
allowed candidate before reopening. Never restore over the active authority or relax a missing
ledger/key gate. Record a new restricted restore receipt and refresh G3/G7 only through its named
owners. This package cannot certify those absent observations.

## Verification scope

Run `uv run --frozen pytest tests/unit/test_production_preparation.py -q` for the closed-plan,
gated-unit, backup receipt, host mismatch, revision drift and release-check fail-closed regressions.
These preparer tests do not provision a server, read a real credential file,
contact providers or install systemd. Actual host/runtime and integration setup
receipts now exist, as linked above. They do not certify this generic generated
bundle, backup schedule/ledger durability, encrypted remote backup/restore,
complete egress/capacity acceptance or the measured live pilot. Keep the historical
fixture and preparation receipts unchanged and record each later observation
against its exact deployed release.
