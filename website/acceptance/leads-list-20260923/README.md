# Leads list repair — 23 September 2026

The production qualification list contained one canonical qualified business (QBCC, Tier A, 100/100). Neither the dashboard query nor its default All tiers filter excluded lower scores. ABR collection runs in observation mode and does not populate that qualification table; the accepted source publications contained 20,510,902 ABR records and 108,019 QBCC records at investigation time. Those are source-record counts, not distinct reachable prospects.

The Leads list now defaults to All businesses and queries accepted publications directly. It lists 50 records per source without qualification or date requirements, supports full-publication name/ABN/licence search and independent run-pinned pagination, and opens the existing research editor for records with a valid ABN. Qualification reviews preserve the prior score filters and actions. Recent ABN views and saved website-gap views remain available above the list.

## Validation

- 38 dashboard/model tests passed.
- 39 actual React browser checks passed with synthetic engine responses and zero browser errors; see `results.json`.
- Browser coverage includes unscored records alongside one Tier A record, lower Tier B/C qualification scores, full-publication search, per-source pagination, saving research into Saved prospects, invalid/missing ABNs, partial failures, stale responses, role restrictions and 1440/820/390/320 px layouts.
- TypeScript passed; scoped production-component ESLint passed with no warnings.
- Local webpack production build and hosted Turbopack production build passed.
- Independent final code review found no remaining material functional or security issues.
- Screenshots are synthetic test data, not production businesses. Production verification is recorded separately below.

## Release

- Website-only release; no engine deployment, migration, source ingestion, qualification or contact-permission changes.
- Upload: 80 allowlisted application/build/public files; environment files excluded.
- Source digest: `b593d6dbc67ae8f382954f7ec2dbafec36a78bac23b3ac078cb6f6dba9d18814`.
- Previous production deployment: `dpl_AvfYhgDFMyYqErgawg5vbCFWih3U` (`website-50fbs7u40-maintain-technology.vercel.app`).
- Production deployment: `dpl_BfWTTTSPibShrSBJ8k8MyP1jq17L` (`website-ex596767j-maintain-technology.vercel.app`), ready and aliased to `www.maintainmedia.com.au`.
- Authenticated live verification confirmed Leads list → All businesses loads 50 ABR and 50 QBCC records. Unscored records display Source candidate / No score required, while JANBAY retains its existing Tier A score within the wider list.
- Live ABR pagination advanced to records 51–100 while QBCC remained on its first page. A formatted ABN search returned JANBAY from both full publications. Qualification reviews still showed the one canonical Tier A record and all tier options.
- Saved prospects loaded its valid empty state (0 matching prospects); no production research was fabricated or saved during verification.
