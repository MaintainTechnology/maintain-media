# Website phone pilot release 008 admission — 11 September 2026

Decision actor: Codex acting under the requesting administrator's express
delegation. This separately admits the bounded website-phone purpose described
in `website-phone-pilot-delegated-owner-20260911.json`, SHA256
`6364819693150146ded61e3cd00cd4e3900745158131a02a5109570b54004e07`.
It does not claim Jon Pepper's approval, a qualified adviser assessment, a
website operator's permission, permission to call, or full production readiness.

## Exact source and evidence

Admit release 008, manifest SHA256
`51a364b416b8b333c5651631e9db27d1e35e69e68f3ff1aae6ec8c9d501e58fb`,
archive SHA256
`695085655081999f8c2c0a13e59fd8531de8be2f30119671a46c676c5cc8e8e7`.
The package contains 153 allowlisted public files. Dependencies and 26 database
migrations are unchanged. Preserve installed release 007 for source rollback.
Its QBCC mapping, source evidence, accepted publication and reviews remain intact.
Before any rollback to 007, stop website work and disable website_collection:
007 does not enforce this new phone-only purpose. A source-only rollback with
website collection still enabled is not admitted by this decision.

Four runtime modules change from 007:

- `compliance/policy.py`: `6870cc0306dde8ddcc824c756568ab832a2edabff0d15962b0b5726b7b671413`.
- `compliance/retention.py`: `6238186552b367b15f09d0521eeef6ac447d2e7b7fe141c4e13c5ccac63472b2`.
- `live/enrichment.py`: `103cc5c0391f31734f88285f00b0911e14735a51d574f3fdce817c050165982f`.
- `live/dashboard.py`: `ade287d75b04b821c00f7794fb2a1d6f12f6df0627824c15b0ebd45440ee47b1`.

Checked evidence before admission:

- 75 distinct backend cases passed, covering current purpose/hash/channel
  admission, authority withdrawal, actual PostgreSQL boundaries, request expiry,
  profile erasure, scoped holds, archive exclusion and phone extraction. The
  overlapping final XML suites contain 44, 17 and 20 successful executions;
  these are not added together as a unique test count. Ruff and mypy passed.
  Their respective SHA256 values are
  `c06f5767980824b2fd3d3d18164ad666a3cdf8a8b863446e2ad93ef540028aeb`,
  `0c1929019594420b39ea0e2b7f902825f6a589ea6fdc9860c102ef370733867a`,
  `e8e37cff0b21a6ad516be4f86afee04c849f13011951b790b730f489ee43ec3d`.
- 107 staged-source tests passed on the actual Sydney Linux host with a network
  namespace denying external access. Two existing deprecation warnings remain.
  JUnit SHA256 `8ad2e27e2e171023391f0526b7c8137db516d255e7640e5e70a3f98649cc3f84`.
- Independent backend and frontend reviews found no remaining blocking finding
  in this bounded change. Frontend validation passed 33 focused tests, 20 bridge
  checks and scoped ESLint. Cloud build and TypeScript checks passed.
- Vercel deployment `dpl_Ex1sbMr6Ti2KxpqZybQhzisU5Enj` is READY on the existing
  Maintain Media aliases, from 74 files with source digest
  `88970d86a256e3dd16822cc5ebe316be090aa61dcce1a8829314c25c38beb82e`.
  All 65 ordinary functions are in Sydney; Clerk middleware remains global.
  Twelve public/signed-out HTTP checks passed. These do not certify a new staff
  browser session.
- The public research notice returned HTTP 200 at 2026-09-11T00:33:01Z. Six
  content checks passed before finalising the owner decision:
  <https://www.maintainmedia.com.au/business-research-notice>.

## G3: bounded private contact evidence

Use the existing private encrypted Sydney engine, restricted runtime role and
authenticated staff connection. The live preflight has one real reviewed lead,
one source snapshot and cursor, zero contacts, 12 historical gates and one policy.
The runtime cannot write policy or release gates. Existing private configuration
and keys remain in place and are not copied into the public release or read out.

The separately recorded pilot disposition accepts the existing recovery and
vendor-country limitations for this additional phone-evidence scope. Independent
key recovery, full database backup/restore and external alert delivery remain
unproved. Neither the storage probe nor local tests establish production recovery.

Collect only valid Australian MOBILE or FIXED_LINE numbers from visible static
text and telephone links. Do not extract/index email addresses or relabel 1300,
1800, premium, VoIP or ambiguous numbers as landlines. Keep source captures
encrypted; incidental page content is not a separate email-address lead list.

Every request needs an actual current active-licence review, independently
supported matching website identity and an attributable current site-terms
decision. Runtime robots, same-domain, IP pinning, suppression, request and page
limits remain authoritative. A failed or uncertain individual site stays held.
No calling, messaging, contact forms, campaign enrolment or vendor transfer is
authorised. No successful website capture is claimed by this admission document.

## G7 and continuing deletion

Append new website_collection G1/G3/G7 revision 1. G1 binds the exact owner bytes;
G3/G7 bind this technical decision. Append collection G7 revision 3 for this
source release, preserving the existing QBCC G1/G2/G3 scope and expiry.

Append retention G1 revision 2 bound to the expanded owner decision, and
retention G3/G7 revision 3 bound to this technical decision. Append policy
`website-phone-delegated-pilot-retention-20260911-v1`; preserve the old policy.
The new policy must expressly bind website collection to the owner hash, allow
only mobile/landline, and independently authorise finite website-data deletion.

`retention.retain_selected_evidence` must be false: no seven-year evidence archive
is authorised even if a worklist row exists. Ordinary capture/excerpt expiry is
90 days; profile expiry is 180 days from the last qualifying event, or 30-day
minimisation after restrictions where applicable. Queued encrypted requests
expire after 24 hours and are removed on profile erasure; attributable scoped
holds remain supported. Routine crawling does not reset the profile clock.

Enable only website_collection in addition to existing collection and retention.
Manual collection expires on 24 September 2026 at 23:18:20 UTC; finite deletion
continues until 10 September 2027 at 23:18:20 UTC. No automatic renewal, weekly
source collection, website batch schedule, ABR expansion, staff vendor transfer,
outreach or backup activation is included. Record actual activation, collection
attempt and subsequent retention execution separately.
