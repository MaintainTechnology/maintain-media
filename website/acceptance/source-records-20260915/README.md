# Source record browsing release — 15 September 2026

Published the missing ABR/QBCC source tables, visible source switches and
completed-run table links to https://www.maintainmedia.com.au/abn-lead-gen/dashboard.

Website deployment: `dpl_8xtKJfc1zVWPVYjzRrE5wDRyxT2m`.
Frozen 75-file inventory: `7422f4769b29ca490ac7ce1a062cee8794c904f03dbe9548224adfb86124733d`.
Hosted build and TypeScript passed. All 65 non-middleware functions are in Sydney;
existing authentication middleware remains global.

Engine release changed only `live/api.py`, the new `live/source_records.py` and
its source manifest. The API service was restarted; settings, approval gates,
collection schedules and existing records were preserved. All 165 manifest files
match. Original files are retained at `/opt/abn-source-browser-rollback-90d441bb`.
Website rollback: `dpl_AsyYHpbXLtuqoxaE6NTM6FgAqgvL`.

Verification passed:

- 11 backend tests, including real synthetic PostgreSQL baselines, source/run
  selection, authority, expiry, artifact integrity and bounded pagination.
- 60 website rendering, readiness and bridge tests; application lint passed.
- 14 browser interaction checks with synthetic data, at 375/768/1024/1440px.
- Eight authenticated HTTPS reads of the actual completed source publications:
  ABR `2f634182…` has 20,510,902 records; QBCC `692faa4e…` has 108,019 records.
- Signed-in production website: source buttons, both loaded tables, ABR second
  page and both exact-run history links worked. No source run or licence decision
  was submitted during this check.
- Signed-out source endpoints reject access with HTTP 401 and private no-store.

The screenshots contain synthetic data. Real-data evidence records only counts,
run identifiers and validation results. Browsing source records does not establish
qualification or contact permission. The ABR publication instant is not recorded;
the UI reports this honestly instead of assigning a timezone to its extract time.
