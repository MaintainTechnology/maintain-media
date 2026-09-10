# ABN Lead Gen in the Maintain Media website

User-authorised extension, 9 September 2026. Replace the separate HTML operator interface with a genuine Next.js React dashboard at `/abn-lead-gen/dashboard`. Reuse the existing Python pipeline and fixture database. The user approved a dedicated admin sign-in because the marketing website has no identity system.

**Later authorised change:** `clerk-authentication.md` supersedes this document's local-password, local-account-provisioning and no-public-signup clauses. Clerk now owns account authentication; the lead workspace remains restricted to explicitly approved administrators. Original acceptance receipts describe the earlier local-auth build.

**10 September hosting extension:** `vercel-engine-connection.md` authorises the
existing Maintain Technology Vercel deployment and explicit HTTPS service transport.
It supersedes the same-host-only and no-public-website boundaries below. Fixture
labels, admin authority and separate live release gates remain required.

## Requirements

1. Render the dashboard as React components inside the existing Next.js website, with native website fonts, logo, colours, responsive layouts and keyboard controls. Keep marketing pages working; omit marketing navigation, footer and smooth-scroll effects from the admin workspace. Provide a return-to-website link.
2. Provide dedicated sign-in and sign-out for explicitly configured individual admin accounts. No public signup, default passwords or implicit localhost login. Check current enabled admin authority on the page and every data/action/report route. Use expiring HttpOnly sessions, hashed passwords, login throttling, same-origin writes and session-bound CSRF protection. Missing configuration must fail closed. Local setup must create a usable initial account without committing credentials.
3. Preserve actual engine leads, ABN/name search, all source/tier filters, selected business detail, restrictions, counts and unknown values. Preserve fixture labels and disabled outreach; no synthetic observation is called a live registration date.
4. Preserve run history and active/terminal state, all three source options, overlap prevention and idempotent retries, background polling and manual refresh. Runs execute the existing pipeline with persisted source and budget preferences.
5. Preserve settings save/discard and reload persistence, A$0–150 validation, effective current-month cap, unsaved-change protection, and safe handling of slow responses, offline/initial-loading states, malformed responses, rejected mutations and expired sessions.
6. Serve protected HTML/CSV/Markdown report links through the website, including each HTML/Markdown report's own CSV link. Retain current artifact integrity/authority and contact masking. Handle absent/stale reports and blocked popups clearly; no arbitrary file or URL proxying.
7. Keep all engine access server-side through a fixed allowlisted loopback bridge. Browser requests use website routes and authenticated sessions; engine credentials and upstream CSRF tokens never reach the browser. Timeouts and backend errors yield actionable non-sensitive responses. Private responses are not cacheable or indexable.
8. Make the website locally runnable against the existing isolated engine, document provisioning/start/stop and additional admin setup, and open the finished route. Verify successful/failed login, access denial, actual engine workflows, report downloads, recovery and responsive behavior; pass lint, type checking, production build and independent review.

## Boundaries

The existing engine remains fixture-only and loopback-only. Next.js and Python must run on the same trusted host for this bridge. A remote/serverless website cannot reach the developer's Windows loopback address. Public hosting, live source ingestion, external integration activation and outreach remain separate production work. No new external account or paid service is required for local use.

## Review rubric

| Area | Points |
|---|---:|
| Complete workflow parity | 30 |
| Admin authorization and data boundaries | 25 |
| Failure recovery and operational clarity | 20 |
| Native design, responsive layout and accessibility | 15 |
| Tests, build and handover | 10 |

Any material authorization or broken-workflow finding prevents a pass. Record actual evidence and remaining limits; prior HTML dashboard receipts are regression references, not proof of this migration.
