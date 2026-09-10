# One private Sydney backup bucket — review package

This package prepares the storage policy and private identity installation for the already owned Lightsail server. **It has not created a bucket, IAM user/key, host credential, backup, approval record or timer.** The earlier server approval excluded backup add-ons. The owner must approve this separate **US$5/month proposal** before storage provisioning.

The exact machine-readable plan is [backup-infrastructure-plan-20260911.json](../acceptance/aws/backup-infrastructure-plan-20260911.json). Its SHA-256 is `ee5f4349d2a0506d49664dfe47174cba43311be68086216f525fec65bb94f9c8`.

| Item | Proposed setting |
| --- | --- |
| AWS account | `052530979168` |
| Region | `ap-southeast-2` — Sydney |
| Existing deployment | `983c39eb-aaf2-4fb5-81af-d39d29de9568` |
| One bucket | `maintain-media-abn-backup-052530979168-983c39eb` |
| Only data prefix | `abn-backup/983c39eb-aaf2-4fb5-81af-d39d29de9568/` |
| Publisher IAM user | `/maintain-media/backup/abn-backup-publisher-983c39eb` |
| Stored encrypted bytes | At most `100000000000` total (decimal 100 GB) |
| Single encrypted object | At most 4 GiB; no multipart uploads |
| Privacy | All four public-access blocks; bucket-owner-enforced ownership; TLS; AES256 server encryption plus client encryption |
| History / expiry | Versioning never enabled; 34-day lifecycle on the exact prefix; explicit expiry checked every 12 hours |
| Extra services | No extra server, paid private CA, replication, archive tier or public endpoint |
| Proposed cadence | Daily full backup; independent ledger every four minutes and after restriction commits |

The CLI applies the lower of the recorded authority limit and **100,000,000,000 bytes**, even when an older authority permits 100 GiB. A publication lease and current prefix inventory precede every upload. This is an application storage limit, not an AWS billing stop; account owners can still incur charges through other actions.

## Cost basis and operating limits

The official Sydney S3 Standard price inspected for this work is US$0.025 per GB-month, US$0.0055 per 1,000 PUT/COPY/POST/LIST requests, and US$0.0044 per 10,000 GET/other requests. At the cap, storage is about **US$2.50/month**. Four-minute ledger publication retains roughly 12,240 objects over 34 days, plus daily backup components and receipts. Each upload scans the prefix, so steady-state LIST pagination is material: roughly 13 pages per publication, not one request. At the proposed cadence, normal request costs add approximately US$1–1.50/month, leaving a small margin inside the **US$5 proposal**, before tax, exceptional restores or transfer. These are calculated estimates, not a bill guarantee. [Official S3 pricing](https://aws.amazon.com/s3/pricing/), [official Sydney price data](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-southeast-2/index.json).

Measure actual requests and bytes during the isolated drill and pilot. A 15-second ledger timer is outside this cost model: retaining and repeatedly listing that many objects would exceed the small budget and eventually the adapter's bounded inventory limit. Increased traffic, ledger size, additional restore downloads, repeated failures or request storms require a fresh cost assessment. No paid AWS budget product or billing alarm is claimed installed by this package.

## Exact provider setup sequence after spend approval

`backup_infrastructure.py` returns the exact bucket configuration and publisher IAM policy. `bootstrap_policy(expires_at)` returns an exact-bucket-only setup policy with a maximum 30-minute expiry. Its default CLI only writes the public review document. There is deliberately no unattended owner-account deployment command in this package: the remaining scoped provider bootstrap is performed by the approved deployment coordinator using the existing `deploy_session.py` pattern and redacted AWS CLI responses.

1. Use the existing owner CLI session only for `sts:GetCallerIdentity` and IAM bootstrap/publisher management. Verify account `052530979168`. Create one tagged temporary IAM user with a unique owned session name, attach `bootstrap_policy(now + 30 minutes)`, obtain temporary STS credentials, and immediately delete its bootstrap access key. Never print credentials or put them in shell arguments or the repository. S3 calls use this limited temporary identity and the Sydney endpoint.
2. Check the exact bucket name before creation. Do not adopt an untagged existing bucket or change the name automatically if it is unavailable. Record the create attempt in a redacted durable journal before the call. On uncertain completion, reconcile that same name and exact ownership tags; do not blindly create another resource.
3. Create that one bucket with the plan's `CreateBucketConfiguration` and explicit `ObjectOwnership`. Immediately apply its deployment tags. Apply public-access block, ownership controls, AES256 encryption, TLS-only bucket policy and exact-prefix 34-day lifecycle. Do not enable versioning. Read each setting back with the expected account owner and compare to the plan. The limited setup policy has no object read/write/delete, bucket delete or versioning-write permissions.
4. Using only the owner IAM bootstrap channel, create the exact publisher user with the exact path/tags from the plan, no console password, and only `publisher_policy()`. Verify user ARN/path/tags before creating one access key. A pre-existing unrelated identity or additional active key is a reconciliation hold. Unknown access-key creation cannot be retried blindly: its secret is returned only once.
5. Pass the newly created `AccessKeyId` and `SecretAccessKey` directly in memory to `backup_identity_client.prepare`, or to its `--prepare` stdin through a captured subprocess. It creates a new RSA recipient and two separate current-user DPAPI files before any host delivery. Keep the provider credential result in memory until escrow succeeds. If escrow or key creation is uncertain, reconcile/deactivate the same owned uninstalled key through IAM; never create replacement active keys automatically.
6. Deploy the reviewed Python files to the fixed owned host. Run `backup_identity_client.py --install` from the approved Windows custodian account. It resumes only its new escrow and uses the existing pinned SSH host key, dedicated SSH identity, no forwarding and private stdin. Only the scoped IAM credential and **public** RSA recipient cross SSH. The root installer publishes files under `/etc/abr-engine/backup`; it neither reads nor replaces existing runtime files.
7. Verify the publisher identity and the adapter's private Sydney bucket checks through the newly installed profile, then perform only the separately permitted engineering drill. Do not substitute the temporary owner/bootstrap identity for an unattended publisher. Install no live timer until current source/privacy, vendor, retention and custody records actually authorize it.
8. Revoke the temporary setup principal before deleting it: verify ownership, attach explicit deny-all, delete all owned access keys, and prove the temporary credentials now fail a previously allowed S3 configuration read. The existing Lightsail probe in `deploy_session.finish()` is **not** a valid S3 revocation test because this temporary principal never had Lightsail permission. Retain the deny/cleanup receipt if revocation cannot be verified.

S3 bucket names are globally unique, so account identity alone does not prove ownership of an existing name. Mutations following an uncertain create require the durable owned-resource journal and tags. No automatic resource deletion, replacement bucket, broad IAM grants or hidden retry is authorized by this plan.

## Prepared host and custody installers

`backup_install_identity.py` defaults to review-only. With explicit `--apply`, root reads at most 16 KiB of new material from stdin, checks the exact target and canonical RSA public key, verifies the owned database, and uses the existing inode-journal publication primitive in an isolated namespace. Existing unrelated files, wrong ownership/modes, symlinks, changed keys and mismatched recovery journals are refused. Completed retries verify public journal and file metadata without reading existing credential contents.

New host files are `credentials` (0640 root:abr-engine), `aws-config` (0640), `public-recipient.pem` (0640), `identity.env` (0600 root) and `infrastructure.json` (0640). The directory is 0750 root:abr-engine. Two separately named root-only parent control files, `.backup-directory-983c39eb.lock` and `.backup-directory-983c39eb.json`, reserve directory creation before `mkdir` and prove its inode before ownership/mode changes. Interrupted directory setup can recover only the reserved empty root-private inode; it never adopts an unrelated directory or modifies the existing runtime `installation.json`. The identity environment selects the `abn-backup` profile and disables metadata discovery. Future systemd backup units must load that identity environment and explicitly unset inherited `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_WEB_IDENTITY_TOKEN_FILE`, `AWS_ROLE_ARN` and endpoint/proxy overrides, so an unrelated credential cannot take precedence. The provider adapter also pins the S3 endpoint and expected bucket owner.

`backup_identity_client.py` uses a new directory outside the checkout: `C:/Users/dalig/AppData/Local/MaintainMedia/aws/backup-key-escrow-983c39eb`. It holds `private-recipient.dpapi` and `publisher-identity.dpapi`, with current-user-only ACLs and a backup-specific DPAPI entropy namespace. An OS lease serializes operations. Interrupted encrypted writes and uncertain SSH results resume the same keys. It accepts only new AKIA publisher credentials through `--prepare` stdin, never an existing `.env` or AWS credential store. The private RSA PEM is never sent to the source host or S3.

These files establish local custody mechanics; they do not invent the spec's owner/custodian approval. Before live backup release, record who can recover that protected Windows account/DPAPI material and test the independent custody recovery procedure. The existing engine encryption/wrapping and retained historical lookup keys remain separate required recovery inputs. The provider key should be rotated/revoked through a separately reviewed operation; the installer intentionally refuses silent replacement.

## Evidence and remaining installation boundary

The new test suite covers exact resource scope, private bucket settings, short bootstrap expiry, input injection, wrong account/region, private-key rejection, all 44 before/after publication interruptions, no existing secret reads, immutable file recovery, uncertain SSH replay and a **real Windows CurrentUser DPAPI round-trip with a synthetic key**. It does not call AWS, install files on the server or prove a live provider receipt. The earlier backup suite separately uses a real temporary PostgreSQL dump/restore and a local S3 stand-in.

Independent review plus green tests make this package ready for the owner's concrete storage-spend decision. After approval, the scoped S3/IAM bootstrap, host installation, real encrypted upload/readback, quarantine restore and measured billing evidence are still required. The actual G1/retention/restore and other production gates remain closed until their real records exist.

Relevant official references: [Lightsail CLI credentials](https://docs.aws.amazon.com/lightsail/latest/userguide/lightsail-how-to-set-up-and-configure-aws-cli.html), [Lightsail IAM support](https://docs.aws.amazon.com/lightsail/latest/userguide/security_iam_service-with-iam.html), [S3 conditional-write policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html), [conditional write header values](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html), [S3 lifecycle expiry behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html).
