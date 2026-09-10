# AWS installation handover — 10 September 2026

The approved server is running in AWS Sydney. Its base bundle is US$44/month:
8GB memory, 2 CPUs and 160GB disk. AWS reported the account remained on the active
Free plan with US$100 credit after creation and access cleanup. Usage reporting
can lag; the balance is an observation, not a promise of unlimited free hosting.
No account upgrade, additional server, snapshot or paid backup was created.

## What is installed

- Ubuntu 24.04, Python 3.12.3 and PostgreSQL 16.15.
- Private engine code under `/opt/abn-leadgen`, with 62 locked dependency packages.
- A locked `abr-engine` service identity. The application code is root-owned;
  private runtime configuration and state directories are still empty.
- SSH restricted to the current operator IPv4. PostgreSQL is accessible only
  within the server. No public application ports are open.

The engine is installed as source plus dependencies and is **stopped**. It has no
production database/configuration, API service, timer or live business records.
The CLI is available through `python -m abr_engine.cli` with the source path;
the standalone `abr-engine` console entry point was not built. This avoids the
currently unpinned build backend while preserving the engine's resource paths.

## Evidence

- Host foundation: 11/11 actual checks and a new SSH/sudo login passed.
- Source integrity: all 109 installed package files match the trusted manifest.
- Actual Linux engine checks: 91 passed; two upstream deprecation warnings.
- Native DuckDB/Arrow/XML runtime and all 62 dependency compatibility checks passed.
- Local deployment/host/package checks: 124 tests and 9 subtests passed; Ruff and
  Linux-target mypy passed.
- Live release check correctly reports blocked. The attempted pilot serve command
  refused missing configuration and started no server.
- Temporary deployment IAM credentials were revoked and the owned IAM users removed.

The prewritten **host-foundation** rubric improved **79 → 94 → 94 → 100/100**.
The fixes addressed cleanup/recovery and actual Ubuntu listener/firewall formats;
the last six points came from real Linux and new-SSH evidence. This rates H1–H7
only. The entire live lead-generation system has not passed production acceptance.

See [server receipt](server-deployment.json), [Linux tests](linux-engine-tests.txt),
[blocked release check](linux-live-readiness.json) and [review](preparation-review.md).
Use the corrected [installation procedure](../../aws/release-install.md) for future
work; its directory-change instructions were corrected after the immutable source
package was prepared. The installed application code and lock are unchanged.

## How staff will open it

The website address remains
[Maintain Media ABN dashboard](https://www.maintainmedia.com.au/abn-lead-gen/dashboard).
Staff must sign in through Clerk and have an admin role. The user previously
confirmed `jeph@quotemax.com.au` can open it. This deployment did not alter Clerk
or the website; this run rechecked only the signed-out redirect to sign-in.

The server's numeric IP is for administration, not a new staff dashboard address.
It is currently `3.104.119.142` and is not reserved as a static address. SSH uses
the dedicated key outside the checkout and a pinned host key in
`%LOCALAPPDATA%/MaintainMedia/aws/known_hosts`. Do not automatically accept a changed
host key. If the operator's public IP changes, the AWS and host firewall rules
need coordinated maintenance; do not simply open SSH to the whole internet.

## What remains before real leads appear

1. Complete production engine/API and reviewer-identity wiring to the Next.js
   dashboard, including current review, vendor write-back and suppression handling.
2. Record the spec's current source/privacy/vendor approvals and verify the real
   QBCC intake. The targeting defaults are approved; the 100-business matching
   accuracy review is still required.
3. Install and verify the private Google Sheet and Maintain Media GHL location.
4. Complete production secrets/configuration, TLS, crawler network restrictions,
   scheduling, Australian backups, restore evidence and measured host capacity.
5. Run the measured QBCC pilot; whole-register ABR expansion still requires the
   four-week results and owner decision.

Messages, emails and calls remain outside this build. The spec's required approvals
and evidence cannot be supplied by changing a status flag or by a high review score.
