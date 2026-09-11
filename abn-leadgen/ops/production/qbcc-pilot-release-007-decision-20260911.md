# QBCC pilot release 007 admission — 11 September 2026

Decision actor: Codex acting under the requesting administrator's explicit
delegation recorded in `qbcc-pilot-delegated-owner-20260911.json`. This is a
technical continuation of `qbcc-pilot-technical-decision-20260911.md`; that
immutable release 006 decision and its limitations remain historical evidence.

## G2: the publisher's current download route

The first live attempt on release 006 was held with
`QBCC_SOURCE_HTTP_REJECTED`, request `dddf5663-c44b-4b3e-99ae-b370fb817a20`.
No publication was accepted. Investigation verified the original official
resource URL returns HTTP 302 to its own current attachment path, and that
target returns HTTP 200, application/csv, Content-Length 76,300,852 bytes.

Admit exactly one 302 redirect from the existing pinned resource URL to:
`https://www.data.qld.gov.au/ckan-opendata-attachments-prod/resources/25608781-b28c-44f8-8545-0ab18d84082f/builder-contractor-qbcc-licensee-register.csv`
with only an `ETag` query containing 32 hexadecimal characters. Reject other
hosts, resources, query fields, statuses, extra hops and malformed responses.
Recheck authority before each HTTP request and retry. Keep original-source
provenance, final response URL, redirect count, unmodified raw bytes and SHA256.

The 11-column mapping, encoding, source inventory, size, quality and drift
checks are unchanged. Current licence status remains UNKNOWN pending actual
current-source review. No classifications or contact approvals are fabricated.

## G3 and G7: bounded technical release

Admit release 007 final manifest SHA256
`5ec6694f2ba4c555083398b4c5a9a1bffbf3a0b17c4e97667ec2c9759b8c0fbd`;
archive SHA256
`3e8eafb14ced552ded7b0aa8027eca60c38b735cb1f3b389a001804a85a0941c`.
The only packaged change from release 006 is `src/abr_engine/live/runtime.py`,
SHA256 `b0e2d350f8fc8572614f49a8e7010a24ab2ab31388f1a1d5a741ead90abfa9cd`.
Dependencies, database migrations, parser, configuration and retention rules
are unchanged. Preserve release 006 for rollback.

Evidence checked before admission:

- 73 local tests passed, including isolated PostgreSQL acceptance and authority
  withdrawal between redirect requests. Ruff and mypy passed. JUnit SHA256
  `1b0d40f23ff3f6efd6ec001fafd4bd5c6ee15a7dedc7eae1cb40bab191aa41bc`.
- Independent review: 34 focused checks passed on the final runtime hash;
  both findings from the earlier candidate were fixed.
- 107 staged Linux tests passed with networking disabled, using unchanged
  frozen dependencies. JUnit SHA256
  `8c89048ae3db7b834a8e138600ace78603fac2bb0333c2d28c0eee556221b202`.

These checks admit a real import attempt; they do not claim the complete CSV
has already been imported. Its actual result must be recorded separately.

Collection G1 owner decision, targeting and expiry remain unchanged:
24 September 2026 at 23:18:20 UTC. Retention G1, policy `abr-v4-defaults` and
expiry remain unchanged: 10 September 2027 at 23:18:20 UTC. Continue finite
deletion after collection expires. Record new revision 2 evidence only for
collection G2/G3/G7 and retention G3/G7.

This remains a manual, private QBCC pilot. Keep weekly collection, website
collection, broader ABR, Google Sheets transfer, CRM, outreach and backup
capabilities disabled. Production backup acceptance, independent key recovery,
external alerting and full production release are not claimed. No Jon Pepper
or privacy adviser assessment is represented by this delegated decision.
