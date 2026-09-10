# ABR Lead Engine — backup setup observation

Recorded 11 September 2026 (Manila), from the actual storage and release-005
receipts. This is a dated setup addendum. It does not change the build-task count,
scores, source/vendor decisions or historical acceptance records.

## Completed on the real service

The private AWS S3 bucket is installed in Sydney (`ap-southeast-2`), with public
access blocked, owner-enforced access, no version history and a 34-day lifecycle
rule. The dedicated publisher and restricted host files are installed. The
approved budget is US$5/month, with a 100 GB application storage cap; this is not
an automatic AWS billing limit.

At **2026-09-10 18:05:38 UTC** (**11 September 02:05:38 Manila**), a random test
value completed encrypted upload, download, successful decryption, deletion and
verified absence. The test accessed no business data or database. Its receipt
explicitly says `production_backup_accepted=false`.

Release 005 includes migration 026. The normal runtime can read and update the
single pending-ledger row, but cannot insert/delete it or write approval gates.
Seven backup units are installed. Daily-backup, ledger and expiry timers remain
disabled. A manual check with no authority document returned held/exit 3; its
local alarm returned exit 0. The expected test failure was then reset.

The API and existing worker/control/review-cleanup timers are active. The signed
API check returned HTTP 200, with zero leads and zero release approval records.
The ledger starts at generation 1, acknowledged generation 0. No real business
backup or source collection was enabled.

The final release receipt also records 495 passing unit tests and two
deprecation warnings. Native Linux checks verified publisher contention,
recovery after process termination and an independent capture lock, using no
database or provider operations. These checks are engineering evidence; they
do not replace the live restore and recovery requirements below.

## Still required before release

The private backup key is encrypted with current-user Windows DPAPI inside
Codex's virtualized Windows profile. The operator confirmed the canonical path;
the private key is not on the Sydney source host. That proves its present
storage, not independent recovery after this profile or device is lost.

Required evidence still includes:

- A named independent custodian and a successful recovery of the backup private
  key, engine encryption/wrapping material and retained lookup-key versions.
- Current source, privacy, vendor, retention and backup authority records.
- A real quarantined database/artifact restore using current approval authority
  and the newest independently acknowledged stop/deletion ledger.
- Measured recovery timing and possible data loss, including a primary-host
  failure between a committed stop request and its independent acknowledgement.
- Unattended schedule/expiry checks, detection of stopped timers and external
  alert delivery. A local alarm alone does not prove any of these.
- A fresh staff Clerk browser flow, 100-business accuracy review, capacity
  acceptance and the measured QBCC pilot. ABR expansion stays separate.

## Exact evidence

The current full live-tool progress score is **77/100**, with trajectory
**57 → 72 → 77**; the final review did not improve it further. This is separate
from historical document and fixture scores and is not production acceptance.
The rubric, deductions and review cycles are in the
[live completion review](../../abn-leadgen/ops/production/live-completion.md).

- `abn-leadgen/ops/acceptance/aws/backup-storage-installation-20260911.json`
- `abn-leadgen/ops/acceptance/aws/live-service-release-005-20260911.json`
- `abn-leadgen/ops/production/README.md`
- `abn-leadgen/ops/production/approval-pack.md`

Related: [[ABR Lead Engine - Staff Workflow Installation]],
[[ABR Lead Engine - Implementation Status]].
