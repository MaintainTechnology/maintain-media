# Maintain Media — Website

The Maintain Media marketing site, rebuilt from `maintain-media-initial/` as a
Next.js application on the repository's design system.

## Stack

- **Next.js 16** (App Router, Server Components, typed routes, Turbopack)
- **TypeScript** + **Tailwind CSS v4** (design tokens in `src/app/globals.css`, sourced from the repo root `DESIGN.md`)
- **Motion** (`motion/react`) — entrance orchestration, scroll reveals, counters
- **GSAP + ScrollTrigger** — the sticky-stack process section on the home page
- **Lenis** — smooth scrolling, wired into GSAP's ticker
- **Phosphor Icons** — this is the brand's icon family: the colored icon set in
  `../media/complete-toolkit/01 Visual Identity/icons-colored/` consists of
  Phosphor glyphs (Target, ChartLine, UsersThree, Globe, …), so
  `@phosphor-icons/react` renders the same set programmatically (duotone, purple)

## Brand assets

- Fonts are self-hosted from the brand toolkit: Albert Sans (variable) for
  UI/body, Vela Sans for display headlines (`src/fonts/`, loaded via
  `next/font/local` in `src/app/fonts.ts`).
- Logos, the wireframe mountain landscape and the mark live in `public/brand/`
  (copied from `../media/`; the mountain art is re-encoded as WebP for weight).
- Colors, radii, spacing and motion rules follow `../DESIGN.md`. Do not invent
  new tokens; extend `@theme` in `globals.css` if the system grows.

## Pages

`/` home, `/services` (anchors: #brand, #performance, #content, #web),
`/about`, `/contact` (server-action form), plus a branded 404, `sitemap.xml`,
`robots.txt`, favicon (`src/app/icon.svg`) and a generated Open Graph image.

The admin workspace is at **`/abn-lead-gen/dashboard`**, with Clerk sign-in at **`/sign-in`** and account creation at **`/sign-up`**. The previous `/abn-lead-gen/sign-in` address redirects to Clerk sign-in. This is a React component dashboard within the website. The existing Python engine remains responsible for lead data, saved run preferences, pipeline jobs and protected reports.

## Open ABN Lead Gen on this computer

Double-click **`Start-LeadGen.cmd`** in this directory. It starts or reuses the isolated Python engine/database and opens the Next.js website at **http://127.0.0.1:3001/abn-lead-gen/dashboard**. Port 3001 keeps this workspace separate from the other website using port 3000. The starter uses the local Next.js development server; publishing the site is a separate operation.

Use your **MaintainMedia Clerk account**. Choose **Sign up** in the website navigation to create your first test account. After verification, the profile control lets you manage your account. New accounts need an explicit admin role before opening business leads or operating the engine. The old local `admin` password and cookie no longer authenticate; private legacy files are left on disk but are not used by the application.

From PowerShell, in the website directory:

```powershell
.\Start-LeadGen.ps1 -NoBrowser
.\Start-LeadGen.ps1 -Action status
.\Start-LeadGen.ps1 -Action stop
```

Stopping the website leaves the Python engine and isolated database running. Their existing stop helpers are `uv run --frozen python ops/local_dashboard.py stop` and `uv run --frozen python ops/local_postgres.py stop`, run from `../abn-leadgen/`. The website launcher preserves unrelated port listeners and processes. Its logs and process record are under `.local/website-3001*`.

The workspace supports lead search/filter/detail, run history, all three fixture source options, saved source and A$0–150 usage preferences, effective budget information, report/CSV downloads and setup readiness. It uses synthetic practice businesses and keeps outreach disabled. All admin users share this engine's review workspace and run defaults.

## Clerk accounts and administrator access

This project links to **MaintainMedia**, application `app_3J5CahJ3ZoQlWkUPqenwuPfc9KH`. Clerk owns signup, verification, credentials, account recovery and sessions. Website access to leads is a separate server-side authorization decision.

For a fresh local installation, run `npm ci`, provision the Python/database prerequisites in `../abn-leadgen/README.md`, then authenticate the Clerk CLI and pull this application's development configuration:

```powershell
clerk auth login
clerk env pull --app app_3J5CahJ3ZoQlWkUPqenwuPfc9KH --instance dev --file .env.local
clerk doctor
.\Start-LeadGen.ps1 -NoBrowser
```

The CLI writes the standard `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and server-only `CLERK_SECRET_KEY` without requiring keys in terminal arguments. `.env.local` is ignored by Git. Local setup uses the development instance; production credentials should be configured separately in the deployment's private environment. Only the publishable key belongs in client configuration. Auth paths and post-auth dashboard redirects are configured in the provider and pages.

To approve an administrator, the person managing the **MaintainMedia** Clerk application should open its **development instance → Users**, select the correct signed-up account, and merge `"role": "admin"` into its **Public metadata**. Preserve other metadata fields. Do not use unsafe metadata. For example:

```json
{ "role": "admin" }
```

Return to the access page and choose **Check workspace access**. Each dashboard page and API request checks the current Clerk session and backend user, so no custom session-token claims configuration is needed. Removing the role, banning/locking the user, or revoking the session blocks subsequent protected requests. Optional application metadata `enabled: false` or `disabled: true` also denies access. These flags are application conventions; the role must still be exactly `admin`.

There is no automatic first-user promotion, email-domain shortcut, local-password fallback, or signup-based administrator grant. A signed-in ordinary user sees an access page with account controls. The dashboard's sign-out control confirms unsaved settings before ending the Clerk session. Old `/api/abn-lead-gen/auth/login` and `/logout` endpoints are retired.

After creating your first account, Clerk's [Dashboard](https://dashboard.clerk.com/) manages users and application settings. Its [Components guide](https://clerk.com/docs/reference/components/overview) covers account controls, and [Organizations](https://clerk.com/docs/guides/organizations/overview) can support team membership if the product needs it later.

For a managed Node deployment, set `ABN_ADMIN_ORIGIN` to the exact HTTPS website origin and configure the production instance's Clerk keys through the hosting environment. Current admin authority is checked through Clerk's backend on protected requests, so provider availability and API limits apply. Public website navigation remains public. The prior `ABN_ADMIN_ACCOUNTS_JSON` and `ABN_ADMIN_SESSION_SECRET` configuration no longer grants access.

The current server bridge reaches only a co-located loopback engine, default `ABN_ENGINE_ORIGIN=http://127.0.0.1:8767`. It does not forward browser credentials or expose the engine's CSRF token. It checks the current admin session on every endpoint and masks report contacts through the existing engine authority checks. **Deploying Next.js to a remote host does not give it access to this Windows computer's engine.** Live sources and externally hosted engine authentication remain separate release work; do not publish the loopback engine port.

## Dashboard verification

The original dashboard requirements and historical receipts remain in [specs/abn-lead-gen-dashboard.md](specs/abn-lead-gen-dashboard.md) and [acceptance/abn-lead-gen/review.md](acceptance/abn-lead-gen/review.md). Clerk supersedes the local-password requirement: see [specs/clerk-authentication.md](specs/clerk-authentication.md) and [acceptance/clerk/review.md](acceptance/clerk/review.md) for current migration evidence and remaining live-verification steps.

```powershell
npm run test:auth
npm run test:bridge
npm run lint
npm run build
npm run test:leadgen
```

The auth tests exercise the real authorization service boundary with a fake Clerk backend; there is no test-auth mode in the running application. Bridge tests cover allowlisted engine routes, report integrity and private errors. `test:leadgen` verifies current public auth routes and unauthenticated protection over HTTP without reading credentials or changing engine data. Completing a real signup/signin and verifying an explicitly approved admin through the browser are separate live checks; unit mocks do not certify those flows. Historical local-password browser receipts remain historical evidence only.

## Develop

```bash
npm install
npm run dev
```

```bash
npm run build && npm start
```

## Before going live

- Set the real production domain in `src/lib/site.ts` (`siteUrl`).
- Wire the contact form to an email provider or CRM in
  `src/app/contact/actions.ts` (enquiries currently log server-side).
- Add real social profile URLs to the footer if wanted (omitted rather than
  shipping dead links).
