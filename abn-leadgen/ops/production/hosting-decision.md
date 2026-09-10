# Australian engine hosting proposal

10 September 2026. The user selected Maintain Technology for Vercel and has now
created an AWS account and approved the local AWS CLI browser connection. Vercel
website ownership is settled. The approved single Sydney server has been
provisioned using the AWS credit, with the Free plan unchanged. See
`../acceptance/aws/server-deployment.json` for the resource and access receipt.

## Approved server launch

On 10 September 2026, after the exact US$44/month Sydney 8GB proposal and Free-plan
constraint were presented, the user answered: "Yes, please go ahead and use the
AWS credit." This authorizes the one Ubuntu 24.04 instance using bundle
`large_3_2`, in `ap-southeast-2`, and the scoped deployment setup needed to install
it. Do not ask for this same credit/server approval again. It does not authorize
a paid-plan upgrade, extra servers or paid backup/storage add-ons.

The initial browser login subsequently failed token refresh with AWS
`CreateOAuth2Token` / `ValidationException` / `INVALID_REQUEST`. A fresh browser
login subsequently succeeded. The deployment used a disposable, scoped IAM
session. Its bootstrap key was removed before provisioning; after deployment,
access was revoked and the temporary IAM user was removed. A readback confirmed
there are no remaining users under the task's `/maintain-media/` IAM path.

The running instance is `maintain-media-abn-engine`, Ubuntu 24.04, Sydney
`ap-southeast-2a`, bundle `large_3_2`. Its current IPv4 is `3.104.119.142` (dynamic).
The AWS firewall was read back as TCP22 from the current operator IPv4 only,
with no IPv6 rules or application ports. First SSH trust used a recorded host
fingerprint after AWS ARN/IP verification; the optional AWS host-key array was
empty. All later SSH connections enforce the saved key. The actual host verifier
passed 11 checks and a new SSH/sudo login passed. The dormant engine source and
locked dependency wheels are installed, with 91 selected offline Linux tests passing.
The engine is stopped and the live dashboard remains unconnected; this does not close T071.

After server creation and identity cleanup, AWS still reported the Free plan as
active and US$100 credit remaining. Credit reporting may lag usage. No paid
upgrade, extra server, snapshot or backup add-on was requested.

## Verified AWS account connection

At 13:48 UTC on 10 September 2026, AWS CLI 2.36.42 was installed for the current
Windows user using the official MSI with a valid Amazon Web Services signature.
The user completed browser authentication for profile `maintain-media-deploy`.
No environment files, passwords, secret access keys or cached tokens were read
or printed. The CLI manages its temporary credentials outside this repository.

Read-only STS and AWS service calls verified:

- Account ending `9168`; the connected identity is the account root user.
  This connection was used for account bootstrap and cleanup; provisioning used
  the separate limited deployment session described above.
- Account plan `FREE`, status `ACTIVE`, with **US$100** remaining credit.
- Free-plan expiration reported by AWS: **10 March 2027, 13:43 UTC**. Credit
  exhaustion can end the Free plan sooner; this is not six months of free server
  capacity or a guarantee that any particular resource can be provisioned.
- Sydney (`ap-southeast-2`) availability zones are available. There are no
  existing Lightsail instances in that region.
- Active Linux bundle `large_3_2`: **US$44/month**, 8GB RAM, 2vCPU, 160GB disk,
  one public IPv4 address. Active OS blueprint `ubuntu_24_04` is available.

These catalogue reads do not prove account permission to create the bundle or
engine capacity. At the time of that preflight, no cloud resources or IAM
identities were created, no plan was upgraded, and no source data was collected.
The initial one-server launch is now approved above. Separate backup/storage
costs still need to be settled before those additional resources are created.

Sanitized evidence: `../acceptance/aws/account-preflight.json`.

## Approved server design

Use a company-owned AWS account with an Amazon Lightsail Linux instance in Sydney
(`ap-southeast-2`). A candidate pilot size is8GB RAM,2vCPU,160GB disk. AWS currently
lists this public-IPv4 bundle at **US$44/month**, before applicable tax and separate
backup/storage/overage costs. The resource receipt now proves creation of this
bundle; measured engine capacity remains unverified.

Official references checked10 September2026:

- [Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)
- [Lightsail regions](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html)

The owner has approved the initial AWS server and supplied authorised browser
access. Additional spending remains outside that approval. No password, payment card or
API secret belongs in this document or chat. Account verification, payment details
and acceptance of provider terms must be completed by the account owner.

## Engineering installation after account selection

Install locked Python3.12/PostgreSQL16, private state and TLS; configure the Vercel
connection; use the single scheduler and acceptance steps in `README.md`. Measure
the pilot's disk/RSS/time on the selected machine before declaring the size adequate.
Keep remote database and internal engine ports private. Use dedicated scoped
operator/service identities and retain the live `/v1` reviewer authority contract.

Choose and document AU encrypted object/backup storage with separate key custody,
finite retention and an independently retained suppression/erasure ledger. Prove a
quarantined restore and timer recovery. An instance snapshot alone does not satisfy
the existing backup contract. Whole-register ABR capacity remains separately gated.

This proposal does not approve source collection/privacy/vendor records, install
Sheets/GHL, complete the100-business review, or replace the four-week pilot. Those
obligations remain in T071 and the release-gate register.
