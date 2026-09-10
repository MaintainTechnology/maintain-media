# Approved private backup provisioning — operator execution

This is the engineering installation for the approved US$5/month storage budget.
It creates one private Sydney S3 bucket and one restricted publishing identity.
It does not approve business-data collection, source/privacy/vendor use, production
backups, retention, a restore drill or any scheduled backup service.

Run from the existing abn-leadgen checkout in the signed-in Windows operator
session. The default command only prints the review scope:

```powershell
.venv/Scripts/python.exe ops/aws/backup_provision.py
```

After root review, the explicit command provisions the fixed resources, installs
the publisher/public encryption recipient through pinned SSH, and performs a
synthetic encrypted nonce upload/readback/decrypt/delete probe:

```powershell
.venv/Scripts/python.exe ops/aws/backup_provision.py --apply --probe
```

The official AWS CLI is pinned to
C:/Users/dalig/AppData/Local/Programs/Amazon/AWSCLIV2/aws.exe and the existing
maintain-media-deploy owner profile. Owner requests are restricted to STS identity
verification and IAM. S3 configuration uses a separately tagged temporary
principal with an explicit policy expiry under 30 minutes; its bootstrap access
key is removed immediately after STS issuance. No mutating API is retried on an
uncertain response. Known-denied authorization reads may be polled for propagation.

The fixed bucket is maintain-media-abn-backup-052530979168-983c39eb in ap-southeast-2,
account 052530979168. The exact deployment prefix is
abn-backup/983c39eb-aaf2-4fb5-81af-d39d29de9568/.
Bucket/publisher tags include the plan's Project, Purpose and DeploymentId and a
new public ProvisioningId that binds them to the durable local installation journal.
The publisher has no console password, no managed policies or groups, and one
active access key with the reviewed prefix-only policy. No IAM role, extra
server, replication, versioning, public access or extra bucket is created.

The storage cap is decimal 100 GB. US$5 is the approved spending allowance, not
an AWS billing hard stop. Request, tax and restore-transfer charges still require
operator billing review. The bucket expiry backstop is 34 days; application
retention and backup approval gates remain separate and unchanged.

## Custody and recovery

The public provider journal and two separate current-user DPAPI escrows use the
logical path `C:/Users/dalig/AppData/Local/MaintainMedia/aws/backup-key-escrow-983c39eb/`.
For this actual installation, the operator verified the canonical location in
Codex's virtualized Windows profile as
`C:/Users/dalig/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/MaintainMedia/aws/backup-key-escrow-983c39eb`.
This is a custody-location observation, not proof that an independent custodian
can recover it after loss of the profile. No key contents are recorded here.
Only the scoped publisher credential and RSA public recipient reach the host.
The private RSA recipient stays in its separate Windows custody file. Existing
.env files and credential caches are never opened by this Python helper.
The official CLI consumes its configured owner profile using its normal login.

A completed retry reuses the same publisher key and private recipient. Keep the
owned journal and both DPAPI files after any failure. Do not remove them to
force a fresh setup.

- A confirmed, tagged bucket can resume partial configuration.
- An uncertain create with an untagged bucket remains held for explicit
  ownership reconciliation. The coordinator never blindly tags it or creates
  a replacement bucket.
- A known newly created key that fails custody is removed immediately if it
  was not escrowed. A lost response is reconciled from the owned user's key
  list and removed on retry. No replacement is generated automatically.
  After reviewing the held state, root may explicitly use
  --apply --probe --resume-lost-key to replace the removed uninstalled key.
- If the process dies with temporary STS material only in memory, retry first
  attaches and reads back an explicit deny, removes any bootstrap keys, and
  waits for the original policy expiry before deleting that temporary user.
- Normal completion proves a previously successful S3 bucket-location read
  becomes denied, then removes the temporary user. A Lightsail denial is not
  accepted as evidence for this S3 identity.
- An uncertain SSH outcome keeps the same DPAPI material for a replay of the
  remote installer's owned-inode journal.
- The synthetic probe journals an opaque object ID, encrypted size and hash
  before upload. Retry reconciles only that exact object; no database or
  business data is used. A synthetic probe cannot create a production backup
  acceptance record.

The host must already contain source release dependencies including
backup_install_identity.py, provision_runtime.py and provision_database.py.
This coordinator does not upload or activate source releases.

## Verification

The final coordinator suite passed 64 checks; the separate shared private-file
journal suite passed 34 checks. The coordinator cases cover fixed
account/region/bucket/prefix, no duplicate resources, foreign ownership,
unexpected publisher permissions, closed credential/output boundaries,
partial configuration, unknown IAM creation, DPAPI and SSH failure recovery,
and genuine denial/absence handling. See
../acceptance/aws/backup-coordinator-final-20260911.xml and the earlier combined
../acceptance/aws/backup-coordinator-tests-20260911.xml.
These tests perform no provider operations. Actual provider receipts are
recorded separately by the executing root operator.

The first real attempt created/tagged the owned bucket and held at encryption
readback. Two read-only inspections established that AWS adds
`BlockedEncryptionTypes: {EncryptionType: [SSE-C]}` alongside AES256 and
`BucketKeyEnabled: false`. The comparison now permits only that observed stricter
restriction. The approved write configuration is unchanged; `NONE`, an empty or
unknown encryption list, additional fields, KMS and an enabled bucket key remain
rejected. The installation receipt records the actual observed restriction.
This follows the official [encryption rule](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ServerSideEncryptionRule.html)
and [blocked encryption types](https://docs.aws.amazon.com/AmazonS3/latest/API/API_BlockedEncryptionTypes.html)
schemas. `--apply --inspect` uses a temporary S3-read-only identity to inspect the
exact owned bucket; it performs no bucket, publisher, object or host writes.

If bucket, publisher and host installation are already complete and only the
synthetic probe remains, use `--apply --probe-only`. This requires the same
completed journal and DPAPI custody, verifies publisher permissions and the
single key through read-only IAM/STS requests, and performs no temporary IAM,
bucket-configuration or host operations. It never creates or replaces a key.
Known provider denials appear as fixed safe codes. Only bucket-metadata reads
may retry a definite authorization-propagation denial; object mutations are
never retried by the CLI wrapper.

The packaged Windows app can virtualize the same custody directory beneath its
LocalCache folder. Probe staging accepts that one verified package path only
after both logical and canonical paths pass the existing link/reparse checks,
current-user-only ACL verification and same-file-identity comparison. It does not
accept arbitrary alternate directories or read secret file contents to do this.
