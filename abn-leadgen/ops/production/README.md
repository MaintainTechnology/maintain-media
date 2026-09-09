# Production preparation and host acceptance

This directory prepares a reproducible, uninstalled systemd bundle. It does not create a server,
approve evidence, migrate a database, read private credential files, send alerts or enable a live
adapter. The existing fixture units in `../systemd/` are unchanged.

**Current result: live deployment is blocked.** No AU host, storage contract or real backup provider
has been supplied. The current CLI also reports live pipeline/dashboard, ABR generation mapping,
CRM drain and suppression propagation implementation blockers. `serve --mode pilot|production`
still refuses nonfixture execution. These templates deliberately use the guarded CLI; running
uvicorn directly to bypass that refusal is not a deployment solution.

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

This sequence is for the developer on the explicitly selected AU host after its access is supplied.
It is documentation, not an installation receipt. Do not run it against an inferred host.

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
   from real owner evidence and complete the outstanding live implementation/contract work.
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
The API remains private on 8766 and uses `serve`; it cannot start until its nonfixture implementation
and TLS/identity deployment contract exist. The website's current fixture bridge on 8767 does not
become a live dashboard through these templates.

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
The generated files remain uninstalled; no cleanup is executed while preparing a bundle.

## Backup creation, verification and restore

No production backup-create command exists in the engine today. `backup drill` is intentionally
fixture-only; these units never call it in a live mode. The chosen AU backup provider must create
encrypted database and immutable artifact backups, maintain an independent current suppression/
erasure ledger and enforce deletion by 35 days. Keep encryption/wrapping/retired lookup keys in
separate managed custody. Evidence and restoration need the actual provider and account; inventing
a backup receipt would not make the system recoverable.

An external approved backup job writes a restricted JSON receipt to `backup_receipt_path`. The
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

The hourly backup-check timer validates receipt structure, deployment binding, component coverage,
24-hour freshness and 35-day maximum retention. **It does not create a backup, fetch a remote
object, verify encryption or prove a restore.** Its `receipt_valid` status is intentionally narrower
than deployment readiness. Missing/stale receipts fail the unit; configured redacted operations
delivery must independently report that failure once its adapter is approved. The actual backup
job must use the same systemd scheduler, not a second cron schedule.

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
No test provisions a server, reads a real credential file, contacts providers or installs systemd.
Actual Linux `systemd-analyze verify`, service-account access, timer timing, encrypted remote
backup/restore, egress and live pilot remain separate pending acceptance evidence.
