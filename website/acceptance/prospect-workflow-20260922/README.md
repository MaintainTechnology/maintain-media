# Prospect workflow verification — 22 September 2026

Implemented in the existing checkout; no production migration or deployment.

## Checks completed

- Optimized Next.js production build with webpack: passed, including TypeScript and static page generation.
- Full `tsc --noEmit --incremental false`: passed.
- Scoped ESLint on dashboard/source/prospect components, models, bridge, hook: passed with no warnings.
- Actual React browser harness: 22 workflows passed with no browser errors. Desktop and mobile widths down to 320px, no horizontal overflow, navigation labels fit. `browser-results.json` records the exact synthetic scope.
- Website model/bridge suites: 24 passed; existing dashboard rendering suite: 26 passed.
- Source query/record/export/cancellation units: 64 passed. Covers inclusive date boundaries, invalid dates, source restriction, streamed export parity and Parquet pruning.
- Prospect backend: 34 focused tests passed (27 validation and 7 real disposable PostgreSQL integration cases); the wider 48-test integration/regression run passed. Additional immutable-provenance test passed after review.
- Backend Ruff: passed on changed modules/tests. Independent review findings were fixed and rechecked.
- Additional deployment-boundary checks: 28 signature/inventory tests and 2 real PostgreSQL key-rotation/runtime-grant tests passed. Existing production ingress accepts the routes; no gateway changes were needed. Use the production migration installer to apply migration 027 and runtime grants before enabling the new backend.

## Review artifacts

- [Discovery view](prospect-discovery-1440.png)
- [Research form](prospect-research-1440.png)
- [Mobile research](prospect-research-390.png)
- [Mobile saved prospects](saved-prospects-320.png)
- [Feature behavior and deployment order](../../specs/prospect-research.md)

Browser screenshots use synthetic businesses and an isolated engine double. They do not prove a signed-in hosted workflow or a production source query. PostgreSQL verification used disposable local schemas, not production data. Live activation needs migration 027 plus engine/website deployment and then a signed-in acceptance check.

The public homepage/contact changes have separate evidence in `../landing-mission-20260922/`: the final production-preview desktop/mobile checks pass, with no page errors or horizontal overflow and working CTA navigation. The existing public enquiry action only logs enquiries; email/CRM delivery remains unwired. Direct contact links remain available. No outreach messages were sent.
