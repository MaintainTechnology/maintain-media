# Production backup and quarantine restore

This implementation creates real PostgreSQL 16 custom-format dumps, archives verified owned source files, and publishes the current suppression/erasure ledger independently. It encrypts each object before it leaves the host, uploads to a private Sydney S3 bucket, downloads it again, and checks its size and SHA-256. A completed receipt is produced only after those operations succeed. The receipt itself is encrypted and copied to S3 for recovery if the primary host is lost.

**Current evidence includes an actual storage installation and a separate local
PostgreSQL restore test.** The private Sydney bucket and scoped publisher are
installed. At 2026-09-10T18:05:38Z, an encrypted random-value upload, read-back,
decryption, deletion and absence check passed on that provider without accessing
the database or business data. See [the storage receipt](../acceptance/aws/backup-storage-installation-20260911.json).
Release 005 includes migration 026 and seven backup units; all three backup timers
remain disabled. [The release receipt](../acceptance/aws/live-service-release-005-20260911.json)
also records the missing-authority refusal and local failure alarm.

The native PostgreSQL test uses synthetic records and a local object-store
stand-in. It proves actual dump/restore, file recovery, newer opt-out/deletion
replay, overdue raw-file removal and retained quarantine in that test. It does
not prove an installed-provider database restore, independent recovery of the
Windows DPAPI key custody, production scheduling, a zero-loss restriction
replica, stopped-timer monitoring or external alerts. Neither receipt creates
source/privacy/vendor or backup authority. `production_backup_accepted` remains
false; the successful provider probe is not a production database backup.

## Files and operations

- `backup_crypto.py`: random AES-256-GCM content key per object, wrapped to an RSA-OAEP-SHA256 public recipient key of at least 3072 bits. Four MiB frames authenticate their position and header; a mandatory final frame detects truncation. The source host stores only the public backup key.
- `backup_store.py`: official AWS CLI adapter pinned to `ap-southeast-2`, an explicit AWS account, private bucket and opaque UUID keys under `abn-backup/<deployment-id>/`. It checks Sydney location, all public-access blocks, a non-public policy, no version history, and an enabled expiry rule for that exact prefix. It uses conditional creation and verifies each upload through a real readback. The deployed CLI and recorded live policy limit the prefix to **100 GB (100,000,000,000 bytes)**, with objects up to **4 GiB**; multipart upload is unsupported. The reusable store helper's wider 100-GiB ceiling does not increase that deployed limit.
- `backup_runtime.py`: exported repeatable-read database snapshot shared with `pg_dump`; only verified/referenced non-backup artifact manifests are included. Paths must resolve inside the artifact root without links or traversal. Actual bytes copied into the archive must match recorded hashes. A changed/missing file fails the backup. Current retention/backup authority is rechecked before provider uploads and the returned receipt. Separate OS-held capture and publication locks prevent concurrent full dumps and provider-cap races. Process death releases these locks automatically; their persistent lock files must never be deleted while workers may run. A legacy `publication.lock` from an older release still requires operator reconciliation. Full backups wait at most 120 seconds for an individual upload lock; independent ledgers can publish during local dump/capture and between bulk uploads.
- `backup_restore.py`: only a newly initialized, password-protected loopback PostgreSQL cluster and new private artifact directory can be targets. It authenticates encrypted objects, extracts only exact regular files declared in the manifest, checks hashes, remaps operational artifact locations, and replays the newest independent ledger. It runs overdue retention, checks quarantine, and stops the cluster. It offers no command to activate the restored service.
- `backup_cli.py`: `create`, `ledger`, `expire`, and `restore` entry points. It writes `latest-backup.json`, `latest-ledger.json`, `latest-expiry.json`, or `latest-restore.json` into an existing private receipt directory. Errors are redacted. It loads the explicit YAML runtime configuration through the normal application loader; it never loads dotenv files.

## Before enabling business-data backups

The owner must provide a current backup/residency contract, a separately recorded key-custody arrangement, the retained engine-key recovery procedure, and the current approved retention/restore policy. `BackupAuthority` is a closed JSON document containing `deployment_id`, `record_id`, `sha256`, `checked_at`, `expires_at`, `recipient_sha256`, `key_custody_record_id`, and `maximum_bytes`. These are references to actual records; generating UUIDs is not approval.

Live admission now **resolves those references against the existing current registry before any provider call**. A separate `capabilities.backup` flag and latest G1/G3/G7 `release_gate` rows with scope `backup` are required, in addition to current retention authority. G1 must reference the exact `record_id` and `sha256`; G7 must reference the distinct `key_custody_record_id` and the custody checksum recorded in policy. G3 must match the current policy's `evidence_ref` and `settings.retention.evidence_sha256`. Gate actors must be named, the latest revisions must be current, and the authority must expire no later than those gates and the policy. A newer withdrawn/future gate closes access even when an older approval exists.

The current approved policy must contain a closed `settings.backup` object with exactly these fields: `approved` (true), `deployment_id`, `record_id`, `evidence_sha256`, `key_custody_record_id`, `key_custody_sha256`, `recipient_sha256`, `account_id`, `bucket`, `country` (`AU`), `region` (`ap-southeast-2`) and `maximum_bytes` (at most 100,000,000,000). Its IDs, hashes, recipient, exact store account/bucket/region and cap must match the supplied authority/provider. This code does not write any of those approvals. The fixture-only tests use isolated synthetic records and a provider stand-in; they do not authorize a production upload.

Live restore resolves current evidence from the separately supplied **current control database**, before provider inventory/download and before its final receipt. It never grants authority from the historical database being restored. If the current control registry is unavailable after primary-host loss, restore holds until the custodian supplies a separately recovered, verified current control authority. The independent approval-registry recovery procedure and retained key custody therefore remain required installation evidence.

The historical restored database also keeps its original policy/gate rows and must pass its own retention/replay checks. An expired or withdrawn historical policy can therefore leave the recovered cluster **held and quarantined**, even when the independent current registry permits reading the backup. No code silently rewrites those old rows as current approval. The operator must reconcile the quarantined control records against verified current owner records through a separately reviewed procedure, then repeat replay/retention. That procedure and its real live drill remain an acceptance item; the fixture restore is narrower engineering evidence.

Retain the backup private key outside the source server and outside the S3 data bucket. The restore custodian also needs the separately protected engine encryption/wrapping material and **all retained lookup-key versions**. The data dump does not supply those keys. Lost or mismatched keys block restoration. The source needs only the public recipient key and its checked fingerprint.

Provision an unversioned Sydney bucket with all public access blocked, a non-public policy, TLS-only access, one scoped deployment prefix, and a **34-day lifecycle rule**. A previously versioned bucket is rejected because deleting its current object would leave hidden older copies. Grant the one approved publisher only the required configuration read, list, get, conditional put and delete permissions for that bucket/prefix. Do not grant bucket creation, policy changes or access to other application prefixes. The adapter verifies expected bucket owner on every call. Use a separately installed scoped workload identity: the current Lightsail host does not provide an attachable EC2 instance profile. See [Lightsail backup identity](backup-auth-lightsail.md). Do not reuse the interactive bootstrap login as an unattended identity or paste credentials into the project.

Use a private staging directory outside the source artifact root and a private receipt directory. On Linux the staging root must be mode 0700; files are created mode 0600. On Windows a separate restrictive ACL is still the custodian's deployment requirement. Bound available disk for encrypted readbacks and quarantine restore files. A fresh restore cluster holds sensitive data even while stopped: it must be purged under the approved drill retention procedure or retained only for explicit recovery. This tool does not delete an operator's restored cluster automatically.

## Commands after records and storage are installed

Run the module using the application's pinned Python environment. The following names are **installation placeholders**, not completed setup or actual records:

```sh
python /opt/abn-leadgen/ops/aws/backup_cli.py create \
  --config /etc/abr-engine/config.yaml \
  --authority /etc/abr-engine/backup-authority.json \
  --public-key /etc/abr-engine/backup-recipient.pem \
  --aws-cli /usr/local/bin/aws --account-id APPROVED_ACCOUNT_ID \
  --bucket APPROVED_SYDNEY_BUCKET --pg-bin /usr/lib/postgresql/16/bin \
  --staging /var/lib/abr-backup-staging --receipts /var/lib/abr-engine/receipts
```

Use the same arguments with `ledger` for independent ledger publishing and `expire` for explicit expiry/deletion/readback verification. The encrypted receipt can be recovered from an unexpired S3 object whose metadata kind is `receipt`, downloaded with the adapter's digest check, and decrypted by the separate backup custodian. `restore` additionally requires `--receipt`, `--private-key`, and `--minimum-ledger-watermark`; use `--private-key-encrypted` to enter its password interactively. Never store that private key on the source host to make the command easier.

`backup_schedule_install.py` defaults to review only. Its explicit `--install-disabled` operation installs seven exact systemd units and two private work directories on the existing host, verifies their configuration and leaves every timer disabled. It does not write approval/configuration records. After separately approved activation, daily `create` is due at 02:00 UTC; `expire` at 03:00 and 15:00 UTC. The ledger has a four-minute calendar schedule plus a 15-second **local** poll. A durable database claim permits at most one worker provider attempt per 240 seconds, so polling does not mean copying every 15 seconds. One in-flight provider upload cannot be preempted; timer latency, contention and failed gates can exceed the target. Actual acknowledgement delay must be measured, never inferred from this schedule.

Migration 026 adds constant-space `backup_ledger_state`. Deferred triggers record a generation change once per committed transaction involving the four restriction-ledger tables; rollback records nothing. These triggers perform no network I/O. The publisher captures that generation and every ledger table in one read-only repeatable snapshot, labels it with the conservative transaction-start time, closes the transaction, and uploads encrypted bytes. Only verified upload/readback plus a final current-authority check allow acknowledging that captured generation. Later commits remain pending. The migration starts with a pending baseline and needs the normal host migration/role-grant helper: runtime can SELECT/UPDATE the singleton but cannot insert, delete or truncate it. No source capabilities must be enabled to record the bounded intent.

Safe per-operation receipts are written atomically in `/var/lib/abr-engine/backup-receipts`, including failures. Queue health exposes pending age, last acknowledged generation/receipt, acknowledgement time and failure state to operators. More than five minutes without acknowledgement is reported as overdue; it is not treated as a successful backup. A failed unit invokes a local `daemon.err` journal alarm tagged `abr-backup`. External notifications and a dashboard backup-health panel are not installed by this change. An entirely stopped timer cannot emit its own failure alarm: independent monitoring of timer heartbeat, queue age, expiry and capacity remains operational acceptance work.

**A periodic copy cannot prove zero lost opt-outs.** At recovery, obtain the latest independent acknowledged ledger watermark from incident evidence, not from the old database dump. The provider's newest unexpired ledger must meet it; restoration rejects missing/older ledgers, rechecks for a concurrent newer one, and remains quarantined. If a primary failed after a restriction committed but before it was acknowledged in S3, resolve that gap from independent records before any owner release. The bounded commit signal, worker and local alarm now have engineering coverage; their installed end-to-end recovery/alert proof remains required. An old backup or a successful local test cannot waive that requirement.

The adapter explicitly deletes expired own-prefix objects and verifies they are absent. The 34-day lifecycle is a backstop because S3 lifecycle expiry is asynchronous. Monitor expiry results and provider inventory so copies do not exceed the spec's 35-day maximum; a scheduler outage is a failed operational gate, not evidence of compliance. DELETE operations are limited to parsed UUID objects under the configured deployment prefix.

## Approved infrastructure spending; separate production authority

The owner approved the US$5/month one-bucket backup spending budget on 2026-09-11; see [the spending receipt](../acceptance/aws/backup-spend-approval-20260911.json). This approves storage expenditure only. Current backup/retention, source/privacy and vendor/custody records remain separate requirements. The budget is not a hard billing stop.

AWS's published Sydney S3 Standard price checked on 2026-09-10 was **US$0.025 per GB-month**, **US$0.0055 per 1,000 PUT/COPY/POST/LIST**, and **US$0.0044 per 10,000 GET/other requests**. At 100 GB, 10,000 first-tier requests and 10,000 second-tier requests, that is about **US$2.56/month**, before tax or transfer. An initial **US$5/month backup budget** allows modest request overhead; monitor actual inventory and request volume. Credits may offset eligible charges but are not a guarantee of free operation.

The general store helper's maximum is 100 GiB, but the deployment CLI now enforces a lower **100,000,000,000-byte cap (100 GB)**. Frequent whole-prefix ledger discovery, readback, verification, and changing suppression activity increase requests; the 10,000-request example is illustrative, not the scheduled workload or an enforced request-cost limit. The [concrete one-bucket plan](backup-infrastructure-plan.md) accounts for a four-minute ledger cadence and twelve-hour expiry checks; a fifteen-second ledger timer would exceed this small request budget. No archive tiers or cross-region copies are used. Production operators must verify actual billable bytes, provider pricing and cost monitoring before activation.

Sources: [official S3 pricing](https://aws.amazon.com/s3/pricing/), [official Sydney price data](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-southeast-2/index.json), [S3 lifecycle expiry behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html), [lifecycle rule timing](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html).

## Required production acceptance

Run the actual encrypted upload/readback, newer-ledger publish, private Sydney restore/replay and verified expiry cycle using the installed provider. Test revoked authority, missing historical keys, wrong recipient, corrupted/truncated object, older ledger, stopped publisher, storage cap, and concurrent retention. Record redacted real receipts and operator approval. Independently verify that the API/actions remain quarantined throughout recovery. Only the existing separate owner release process may authorize use after current restrictions, retention, storage and all other production gates pass.

## Separate synthetic storage probe

`backup_probe.py` defaults to review-only. Its approved coordinator receives the **new** publisher identity and separate RSA recipient key from the owned DPAPI escrow in memory. `ProbeStore(provider_call)` fixes the account, Sydney endpoint, bucket and deployment prefix. The callback uses that new scoped official CLI identity; it must map only a genuine `head-object` 404/NotFound to absence.

`run_probe(store, private_recipient, staging_root, record_prepared=callback)` encrypts a fresh nonce with no business fields. The callback must durably save its public object UUID, ciphertext digest/size and recipient fingerprint, then return true **before the PUT**. The probe reads back and decrypts the ciphertext, compares the nonce, deletes the exact object and verifies absence. Interrupted or failed operations retain the journal for `cleanup_probe`; cleanup refuses a different digest/size and never deletes other objects. Staging is private, and only the encrypted nonce reaches S3. The RSA private key remains with the Windows custodian.

The returned schema is `abr-synthetic-backup-storage-probe-v1`, with `production_backup_accepted=false`. It accesses no business database, creates no approval records and enables no timers. It can prove the approved storage identity/encryption/round-trip/deletion behavior while production collection and retention gates remain closed. It cannot prove installed post-commit ledger publishing, a measured recovery interval, overdue expiry scheduling, current-control/historical-policy reconciliation or a live business-data restore.
