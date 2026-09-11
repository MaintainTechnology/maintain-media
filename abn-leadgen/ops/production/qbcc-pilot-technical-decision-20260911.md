# QBCC pilot technical admission — 11 September 2026

Decision version: 1.0.0. Decision actor: Codex acting under the requesting
administrator's explicit delegation to enable business source collection.
This is the technical companion to
`../acceptance/live-sources/qbcc-pilot-delegated-owner-20260911.json`.
It admits a controlled first-file validation and private review, not a full
production release or an adviser assessment. The collection authority expires
on 24 September 2026 at 23:18:20 UTC; renewal requires a new recorded decision.

## G2: source and mapping

Approve only official Queensland Government resource
`25608781-b28c-44f8-8545-0ab18d84082f` in dataset
`980b6499-c0b4-491b-ba9c-1c7506368a50`, using the current fixed CSV URL.
The catalogue licence must remain CC-BY-4.0. Credit the Queensland Building and
Construction Commission, link to the source and licence, and identify the
normalisation/filtering without implying endorsement.

Mapping version: `qbcc-catalogue-11-column-v1`. The ordered fields are:
Licence Number; Licensee Name; ACN; ABN; Licensee Business Address;
Licence Type DESC; Licence Type CODE; Financial Category DESC;
Financial Category CODE; Licence Grade; Licence Class Type.

The parser requires UTF-16LE with BOM and the exact ordered header, verifies
category descriptions/codes, collapses licence-class rows, and preserves
unknown status and identity conflicts. The source file is independently hashed.
Before/after inventory must match; the intake rejects changed mappings, sizes,
hashes and invalid rows. A present source name or address is not contact consent.

The official zero-row schema request returned HTTP 200 with these 11 fields,
reporting 196,116 raw rows. The catalogue still dates the publication to
18 May 2026. Browser inspection confirms that publication date and directs
readers to the current QBCC licence search for up-to-date licence status.
The entire publication is parsed; 60/week is the later business-worklist cap.

The local HEAD request returned HTTP 202 and zero bytes. Availability of the
actual CSV GET, encoding, exact length, content quality and full-file memory use
remain to be measured by the admitted first run. This decision permits that
attempt; it does not certify its success. A rejected source must remain held.

Evidence bindings:

- `../acceptance/live-sources/qbcc-pilot-metadata-observation-20260911.json`:
  SHA256 `0fd2d129fb0132260040fa5a87e437fb09fab3225e00dd31eace1b43cbb3fd35`.
- `../acceptance/live-sources/qbcc-pilot-activation-focused-20260911.xml`:
  SHA256 `df7072677320d1803d0dfcb9bb5bda165cd8529f111622ff8dc68c78f2b43497`;
  **60 passed**, including PostgreSQL runtime admission, mocked transport,
  source mapping, drift, replay and recovery. This is not a live CSV test.
- Installed parser `src/abr_engine/ingest/qbcc.py`:
  SHA256 `726513ad155cf20bb654c4c79824876b53d13fc6c98ab345d5ff7c0bb6c9448e`.
- Installed intake `src/abr_engine/ingest/qbcc_review.py`:
  SHA256 `935d8e566cab011f575ce7033c4930e9001b888b0f333b9c3eeda7908037d1cb`.
- Installed runtime `src/abr_engine/live/runtime.py`:
  SHA256 `a37bfba2a32b392e845c262041db1b1cdb377d98e74bf1ade73790565c4320d4`.

## G3: limited pilot operating decision

The fresh Sydney host preflight is recorded in
`../acceptance/aws/qbcc-pilot-preflight-20260911.json` at
2026-09-10T23:19:18Z. The API, worker/control and review-cleanup timers are active;
26 migrations are installed; the empty database has zero leads, gates and
policies. The runtime is not a superuser and cannot insert policy or release
approvals. Private configuration/key permissions are 0600/0640; quarantine and
key-compromise flags are false; free disk space exceeds 150 GB.

Release 006 provides the tested separation from website contact collection.
Its deployment receipt also records authenticated HTTPS/no-store and installed
Linux checks. No production backup is accepted and independent key recovery,
external alerting and recovery loss/interval are still unverified. Under the
dated delegated pilot amendment these remain explicit limitations for a manual
public-source review pilot, rather than being reported as passed production
checks. Staff review changes may be lost if the server/key custody fails.

Keep the source weekly timer disabled. Keep website, ABR, Google Sheets, CRM,
email/phone action and backup capabilities disabled. Source access is through
the existing admin-authorised website and Australian engine. Do not assert all
Clerk/Vercel support or global processing is Australian.

## G7: controlled release decision and retention

Admit the existing release 006 only, manifest SHA256
`aeb806afdaad134494cfa3147ea72f58d5c99116db3c616c177bb154872cd5ea`.
Its receipt is `../acceptance/aws/live-service-release-006-20260911.json`.
The prior test evidence includes 496 unit, 83 distinct focused backend, 107
installed Linux offline and 72 frontend checks. Current source-specific checks
add the independently rerun 60-test result above. These do not imply that every
full specification gate has passed.

Enable `collection` for the dated manual QBCC-only pilot and separately enable
finite deletion. Authorise the existing `abr-v4-defaults` retention schedule
for this pilot's records: raw publication 30 days; accepted snapshot 90 days;
unreferenced held/failed staging 7 days; unworked profile 180 days, subject to
existing narrowly scoped retention holds. The full source snapshot expires even
when it is the most recent. Collection expiry does not revoke deletion authority.
Deletion authority runs until 10 September 2027 at 23:18:20 UTC. No restore or
backup authority is granted by this decision. Separate counters/receipts must
record the actual retention execution and first source run after installation.

The first acceptance must leave licence status UNKNOWN until a genuine current
licence/identity review. Do not manufacture reviews, candidates or contact
permissions to make the dashboard appear populated or successful.
