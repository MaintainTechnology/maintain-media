# AWS deployment preparation review

10 September 2026. The single Sydney server and use of the existing AWS credit
are approved. The account must remain on its Free plan. See
`deployment-approval.json`; do not request the same spending approval again.

## Current result

**The approved AWS server is running in Sydney and its host foundation passes.**
The earlier browser authentication interruption was resolved. The approved 8GB
Ubuntu 24.04 Lightsail instance was created through scoped temporary IAM access.
Its AWS firewall permits only the operator's IPv4 on TCP22. All deployment IAM
users and bootstrap keys were removed; a revocation probe confirmed denied access.
No paid upgrade, extra server, snapshot or backup add-on was attempted.

The current-user AWS CLI installation and restricted local SSH key are ready.
The public key fingerprint is recorded in `../../aws/deployment-session.md`.
The private key remains outside the repository and was verified through the SSH
tool without printing its contents. A Windows argument-quoting issue was repaired
before use; the key now supports unattended SSH under its restricted directory ACL.

## Build and review loop

The controller review found uncertain IAM creation cleanup, uncertain instance
creation recovery and firewall/exit-status verification gaps. These were fixed
before any cloud mutation. It now reconciles the uniquely tagged IAM user and
the same fixed instance name, narrows creation permissions, verifies the firewall
readback, revokes permissions on completion and reports incomplete cleanup as a
failure. Twelve offline regressions cover those paths. The independent reviewer
reported no remaining local blocking findings.

The host-foundation review found interrupted PostgreSQL installation recovery
and incomplete key-only SSH enforcement. The builder fixed both and added
regressions. An owned partial installation can admit the distribution's temporary
IPv6 loopback listener; the final verifier still requires IPv4-only loopback.
SSH explicitly requires public-key authentication and checks administrator/root
contexts. The independent reviewer rechecked both fixes and reported no remaining
local blocking findings.

Final combined validation:

- `uv run --frozen pytest ops/aws/test_deploy_session.py ops/aws/test_host_bootstrap.py -q`:
  **84 tests and 9 subtests passed** after actual Ubuntu compatibility fixes.
- `uv run --frozen ruff check ops/aws`: **passed**.
- Builder Linux-targeted mypy on the three host modules: **passed**.

These local tests mock AWS and privileged OS effects. Separate actual evidence
now exists: `host-foundation.json` records 11/11 successful checks at 14:36:03 UTC,
and `server-deployment.json` records a new SSH/sudo login at 14:36:18 UTC. Runtime
output required two narrow compatibility fixes: numeric IPv4 addresses with a
Linux `%lo` interface suffix, and UFW's disabled-routing display. Unsafe addresses,
forwarding switches and IPv4/IPv6 policies still fail their regression checks.

## Executed steps and remaining evidence

1. **Done:** renew the owner-authorized browser login without reading cached credentials.
2. **Done:** verify the same account and Free-plan credit, obtain restricted temporary
   deployment access, delete the bootstrap key and prove the temporary session
   still performs its allowed read.
3. **Done:** create only the approved instance, reconcile its exact ARN/tags/hardware and
   verify the operator-only AWS firewall. Report a Free-plan refusal instead of
   upgrading the account or launching a replacement.
4. **Done:** establish SSH trust, run the reviewed foundation scripts, record
   the real verifier output and confirm a second successful SSH/sudo connection.
   AWS's optional host-key array was empty; a recorded first-use fingerprint was
   accepted after AWS ARN/IP verification, then pinned for every later connection.
5. **Done for dormant installation:** install and verify the locked engine source
   and dependency wheels separately. All 109 source files match the package manifest;
   62 installed packages passed compatibility checks and 91 selected engine tests
   passed on Linux under the service user with network namespace isolation.
   Existing live startup,
   source/vendor, staff-integration, backup, capacity and pilot requirements remain.
6. **Done:** complete temporary-identity cleanup and verify denied access. AWS
   reported Free/Active and US$100 credit after cleanup; usage reporting can lag.

The independent H1–H7 host review passes at **100/100**, following the prewritten
rubric and **79 → 94 → 94 → 100** trajectory. The last six points came from actual
Linux and new-SSH evidence. This narrowly rates the fresh host foundation; neither
it nor the earlier website score is a full live-engine acceptance result.

## Dormant engine installation review

R1–R5 in `../../aws/release-install.md` are satisfied for the dormant source
installation. The package helper passed 40 tests. Independent review identified
and closed hard-link private-input admission and archive size/count consistency
findings before packaging. The deployed SHA256-authenticated archive contains 109
public source/policy/template/test files. It excludes existing environment files,
private runtime configuration, keys and source business records. The generated
`config/fixture.yaml` is only `mode: fixture`; no fixture database or dashboard runs.

The engine's build backend is not pinned in the dependency lock. The install
therefore uses frozen wheel-only dependency synchronization without building the
project, and invokes `python -m abr_engine.cli` from its preserved source layout.
No console entry point or running production service is claimed. Actual Linux
checks exercised native DuckDB/Arrow/XML dependencies and CLI help, with 91 tests
passing. Two upstream TestClient deprecation warnings remain; no dependency upgrade
was mixed into this release. `uv pip check` passed for all 62 installed packages.

The installer instructions were corrected after packaging so the working directory
changes under root or the service identity, preserving private directory permissions.
The immutable release keeps the initial reference document; use the corrected workspace
procedure for subsequent installations. Application source and lock hashes are unchanged.

The actual release check returns blocked (exit6), and an attempted pilot serve
command refuses missing production configuration (exit1); no listener was started.
Post-install read-only checks confirmed empty private config/state, no application
database or engine units, PostgreSQL loopback isolation and the operator-only firewall.
The public dashboard still redirects signed-out requests to the existing sign-in page.

Final combined deployment/host/package suite: **124 tests and 9 subtests passed**;
Ruff on all `ops/aws` code and Linux-target mypy on the four host/release modules
passed. The separate actual Linux engine run remains **91 passed, 2 upstream
deprecation warnings**. These check counts have different scopes and are not a
rerun or certification of the complete end-to-end production system.

The remaining weaknesses belong to full live delivery: production API/identity and
pipeline wiring, approved source/vendor evidence, Sheet/GHL installation, backups,
scheduler and measured pilot. The AWS foundation removes the missing-host obstacle;
it does not satisfy those unfinished acceptance requirements.
