# Latest leads discovery redesign

Implemented locally on 22 September 2026. No deployment, new source collection, outreach or qualification-rule change.

## Result

The main Latest leads view now starts from recent source businesses rather than `lead_entity` qualification results. Default is 30 calendar days in Brisbane, with a 7-day focus. Global newest-first ordering uses ABN status dates across the whole publication. Those dates remain registration/reactivation signals, not verified original creation dates.

Independent No website and Website unchecked views browse saved research without requiring absent email/social profiles or a qualification score. Rows expose reasons, website evidence, saved-contact availability and contact outcome. Research opens directly from the list and saves back into its current view. The original reviewed workflow remains available and its filters/drafts survive main navigation. Native research dialogs protect unsaved edits and close safely when navigation is accepted.

## Verification

- Browser harness: 29 checks passed across source and prospect workflows plus discovery defaults, one reviewed score-100 business alongside multiple unqualified source candidates, global-order pagination, independent website gap eligibility, stale publication messaging, lookup failure, research save/readback/list refresh, late-response isolation and operator-only read restrictions. Desktop/tablet/mobile layouts down to 320px were inspected. See `browser-results.json` for fixture scope.
- Website model/rendering suites: 36 tests passed (10 new discovery helper tests plus 26 existing dashboard rendering checks).
- Backend source sorting units: 73 passed. Prospect validation units: 39 passed.
- Real disposable PostgreSQL integration: 15 passed (6 source-record and 9 prospect cases, including batch lookup, suppression, expiry and retained-key lookup).
- Scoped Ruff, ESLint, TypeScript and optimized Next.js build checked. The browser harness uses actual dashboard React with synthetic engine responses and does not certify live source-query speed or hosted authentication.

## Deployment

Deploy updated engine source-query/prospect endpoints before the website. The prior prospect workflow still requires migration 027 through the production installer so runtime grants are applied; this discovery extension adds no further migration. Verify signed-in newest-first discovery and saved-research lookup after deployment. Existing collection/qualification/contact controls remain in effect.

## Screenshots

- [Desktop discovery](latest-leads-desktop.png)
- [Mobile discovery](latest-leads-390.png)
- [Default 30-day view](latest-leads-default-30-days.png)
