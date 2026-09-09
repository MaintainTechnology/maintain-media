# MaintainMedia Clerk migration review

9 September 2026. Reviewed against `specs/clerk-authentication.md`. The prior ABN dashboard's local-password receipts remain historical evidence.

## Current verdict

**Implementation and independent source review: PASS. Production build and TypeScript: PASS.** Live account creation, administrator approval, authenticated dashboard operation and Clerk sign-out require a user-completed account and are not claimed as verified.

## Coverage

| Requirement | Evidence |
| --- | --- |
| R1 CLI and correct application | CLI updated to 3.3.0 through npm; authenticated; explicit init linked MaintainMedia application `app_3J5CahJ3ZoQlWkUPqenwuPfc9KH` and installed `@clerk/nextjs` 7.9.1. Init stalled after scaffolding and was stopped. Explicit `clerk env pull --app … --instance dev --file .env.local` completed configuration. Doctor passed every applicable check and identified development keys. No environment-file contents were inspected or printed. |
| R2 Next.js integration | Provider inside body; awaited server `auth()`; exact `/__clerk/:path*` matcher follows API/TRPC matcher. Resource-level authorization remains in the dashboard and every API route. |
| R3 Account controls | Native branded catchall sign-in/up pages and public navigation controls; UserButton profile controls; old bookmark redirects. Real Clerk components loaded in the in-app browser, with configured Google, Microsoft, email, phone and password options. |
| R4 Administrator authority | Fresh backend session/user checks, active/unexpired matching session, exact server-managed Public metadata admin role, banned/locked/optional disabled flags. Ordinary signup and old local cookies grant no access. Policy/service tests and signed-out HTTP probes pass. |
| R5 Dashboard protection | Existing engine bridge, source/settings/run/report contracts and masking preserved. Session-derived CSRF and same-origin mutations remain mandatory. Every HTTP data/action/report denial retains strict private/no-store headers. No source ingestion or outreach was enabled. |
| R6 Recovery | Explicit 401/403 data clearing; Clerk sign-out shares dirty-draft confirmation and recovery; revoked JWTs receive session reset instead of redirect loops; provider lookup is bounded and errors sanitized. Tests cover session revocation, identity mismatch, authority removal, outages and stale auth-entry decisions. |
| R7 Verification | 37 individual unit test cases with zero failures in `unit-tests.xml`; 31/31 HTTP probes in `http-smoke.json`; full lint plus final focused UI lint passed. Browser observations are recorded in `browser.json`. Production build and TypeScript passed. A temporary local production-mode server also passed all five private-page/API header checks in `production-http.json`. |
| R8 Local handover | Starter now checks canonical Clerk sign-in and no longer requires local password provisioning. Starter reuse succeeded against website 3001 and original engine 8767. README describes first signup, manual admin approval, test/live configuration, restart and host-co-location limits. |

## Build/review fixes

1. Added the Clerk proxy matcher omitted by CLI scaffolding.
2. Replaced local passwords, session cookies and provisioning with Clerk authority. Retired credential endpoints return 410.
3. Fixed a Next.js loopback normalization bug that made Clerk's internal rewrite recursively proxy requests. The documented `skipProxyUrlNormalize` setting preserves the loopback URL and the original 127.0.0.1 bind. See [Next.js issue 94745](https://github.com/vercel/next.js/issues/94745).
4. Fixed the revoked-session redirect loop using fresh access checks and explicit browser-session recovery; added five focused regressions.
5. Fixed immediate workspace locking after an ambiguous sign-out and removed duplicated brand titles.
6. Updated compatible `sharp` and `js-yaml` dependencies flagged during installation. npm reported zero vulnerabilities afterward.

## Evidence limits

- This is a local development-instance installation, not a public production deployment.
- No real Clerk end-user account was created by the agent. User signup/verification, explicit admin approval, profile menu and authenticated engine/sign-out flows remain live acceptance steps. Mocks are only used at the test service boundary; the running app has no authentication bypass.
- The real Clerk signup and signin forms, email/phone switching, password visibility, empty-required-field validation and 360/390px fit were observed. Desktop sign-in styling was inspected. Social-login buttons were rendered; provider login and SMS/email verification were not submitted.
- The development HTTP receipt accepts Next development's `no-cache, must-revalidate` only on signed-out HTML/redirects. Every API/data/action/report probe still requires `private, no-store`. A separate production-mode local server verified private/no-store/noindex on both auth pages, dashboard/access redirects and the private API. This used development Clerk keys and does not certify a public production deployment.
- Current server-side admin checks require Clerk backend availability and are subject to its API limits. No production instance settings were changed. Next.js and Python still need to share a trusted host.

## Score against the pre-build rubric

Scores are retrospective stage assessments of this Clerk migration, separate from the earlier dashboard's 97/100 score. A material defect prevents a passing verdict irrespective of score.

| Stage | Score | Main deductions |
| --- | ---: | --- |
| Initial CLI scaffold | 62 | Existing password authority remained, account controls incomplete, matcher omitted, runtime rewrite loop. |
| Connected integration before review fixes | 88 | Revoked-session redirect loop, unverified live account workflow, stale browser harness and unfinished verification. |
| Reviewed integration | 94 | Live user/signup/admin/sign-out evidence remains unverified; broader browser and assistive-technology coverage is limited. |
| Final scope review | 94 | Further score improvement needs real account acceptance and broader runtime evidence. |

Final rubric allocation: Clerk setup/session correctness 24/25; authorization/CSRF/data isolation 30/30; dashboard preservation/recovery 17/20; native UI/accessibility 14/15; verification/handover 9/10. The weakest area is actual authenticated browser acceptance after changing the identity provider. Existing engine logic, restricted bridge and design system were retained while fixing the top implementation weaknesses.
