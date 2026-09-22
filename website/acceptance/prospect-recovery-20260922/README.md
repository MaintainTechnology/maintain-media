# Latest leads and Saved prospects production recovery

The website at revision 11d7d43 expected newer engine endpoints than the installed source explorer release. Signed production requests reproduced source query HTTP 422 (`INVALID_INPUT`, unsupported sort/date contract) and prospect query HTTP 404 (`Not Found`, missing route).

## Applied repair

Installed the matching six-file engine delta after checking all 167 previous manifest members and all 26 applied migration digests. Applied additive migration 027 with the existing production installer transaction and runtime grants, then started the API with the source sorting, date filters, prospect endpoints and research retention hooks. The API and retention timer returned to their previous active state. The new manifest identifies 169 files; receipts are alongside this document. Rollback preserves the additive research table and retention handling.

Deployed website error handling that distinguishes an unsupported engine feature from an empty list. Search validation no longer blames missing form evidence. Genuine missing-record errors stay intact; requests are never retried with relaxed filters. The isolated website upload includes only the 79 public source/configuration/assets selected by the existing release preparer.

## Verified results

- Actual HTTPS: 56,859 candidates for 30 days, 24 for 7 days, newest first; the next 50-row page also loaded. Saved prospect and website-presence queries returned HTTP 200 with zero saved records. Restricted operator access still returned HTTP 403.
- Signed-in live browser: Latest leads and the 7-day filter rendered real records; Saved prospects displayed its genuine empty state. The updated website was reloaded after promotion and a real business research dialog opened.
- Production runtime save, encrypted readback and batch query succeeded within an explicitly rolled-back transaction. Saved count stayed at zero; no test research or contact authority was retained.
- 88 focused backend units, 34 bridge tests, 28 dashboard tests and 31 real PostgreSQL integration checks passed. Integration covers research API, source ordering, expiry, erasure, holds, key rotation and production-style runtime grants. Local and hosted production builds passed.

The first broad local test command also selected database tests without the fixture cluster, encountered setup errors and was stopped. Those tests were then executed successfully through the isolated PostgreSQL helper; the final report has no failures or skips.

See `verification.json` for aggregate counts and release identities and `postgres-integration.xml` for the database test results. No new collection or outreach was started. The existing publication was imported on 14 September; its status dates can represent future activation or reactivation and are not proof of first registration.
