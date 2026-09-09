# Maintain Media Clerk authentication

User-authorised change, 9 September 2026. This supersedes the local-password and no-public-signup clauses of `abn-lead-gen-dashboard.md`. Existing lead-engine functionality and admin-only access remain required.

## Requirements

1. Use the Clerk CLI to connect this existing Next.js/npm website to application `app_3J5CahJ3ZoQlWkUPqenwuPfc9KH`. Update/install the CLI, authenticate before initialisation, run init with the explicit application, and run doctor. Do not inspect or print existing environment files or credentials. Prefer development/test instance for local use; preserve production configuration.
2. Install `@clerk/nextjs`, put `ClerkProvider` inside the root body, and configure `src/proxy.ts` with Clerk middleware. Include `'/__clerk/:path*'` exactly once after `'/(api|trpc)(.*)'`. Await the server auth API and protect resources at their server boundaries.
3. Provide working Clerk sign-in and sign-up pages, visible signed-out navigation controls, and signed-in account/profile/sign-out controls. Retain native Maintain Media typography, colours and responsive navigation. Existing ABN sign-in links must still lead to the new flow. Keep auth pages out of indexing.
4. Replace the dashboard's local password/session authority with verified Clerk identity. Check current server-managed Clerk admin authority for every dashboard page and data/action/report request. New signup, user-editable metadata, old local cookies, and merely being signed in must never grant admin access. Show a useful access-pending state to signed-in non-admins. Do not silently promote accounts.
5. Preserve same-origin and session-bound CSRF checks for engine mutations, bounded errors and bodies, private response headers and server-only engine access. Preserve the existing source/filter/run/settings/report workflows and honest fixture labels. Remove obsolete password endpoints and local account provisioning guidance from the active flow.
6. Handle signed-out, expired/revoked session, removed admin authority and unavailable Clerk service without exposing lead data or secrets. Keep public marketing pages public. Keep unsaved-change protection and an operable sign-out path.
7. Verify lint, production build, focused authorization/bridge tests, signed-out browser routes and responsive auth controls. Verify real Clerk components load and record any external login/verification step that needs the user. Do not fabricate account creation or use authentication bypasses as live evidence.
8. Leave the app running locally, open the new sign-up/sign-in route and document account creation, admin grants, test/live configuration and restart instructions. Record independent review evidence and genuine remaining limitations.

## Boundaries

No public deployment, Clerk production-instance settings change, automated email or outreach, new lead ingestion, or automatic first-user admin promotion. The Python engine remains on the same host through the existing loopback bridge. Secrets are loaded by the supported CLI/framework, never copied into source or receipts.

## Rubric recorded before implementation

| Area | Points |
| --- | ---: |
| Clerk setup, routing and session correctness | 25 |
| Admin authorization, CSRF and data isolation | 30 |
| Existing dashboard workflow preservation and recovery | 20 |
| Native UI, mobile and accessible controls | 15 |
| Verification, review and operational handover | 10 |

A material authorization or broken-flow defect prevents a pass regardless of score. External verification that has not happened is recorded as unverified, not passed.
