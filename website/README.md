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

The admin workspace is at **`/abn-lead-gen/dashboard`**, with a dedicated sign-in at `/abn-lead-gen/sign-in`. It is a React component dashboard within this website. The existing Python engine remains responsible for lead data, saved run preferences, pipeline jobs and protected report generation.

## Open ABN Lead Gen on this computer

Double-click **`Start-LeadGen.cmd`** in this directory. It starts or reuses the isolated Python engine/database and opens the Next.js website at **http://127.0.0.1:3001/abn-lead-gen/dashboard**. Port 3001 keeps this workspace separate from the other website using port 3000. The starter uses the local Next.js development server; publishing the site is a separate operation.

Sign in with the initial account recorded in **`.local/admin-access.txt`** on this computer. This ignored private file holds only the most recently created/reset account's credentials. The application stores salted scrypt password hashes and a random session signing key in `.local/admin-auth.json`; neither file belongs in source control or public assets.

From PowerShell, in the website directory:

```powershell
.\Start-LeadGen.ps1 -NoBrowser
.\Start-LeadGen.ps1 -Action status
.\Start-LeadGen.ps1 -Action stop
```

Stopping the website leaves the Python engine and isolated database running. Their existing stop helpers are `uv run --frozen python ops/local_dashboard.py stop` and `uv run --frozen python ops/local_postgres.py stop`, run from `../abn-leadgen/`. The website launcher preserves unrelated port listeners and processes. Its logs and process record are under `.local/website-3001*`.

The workspace supports lead search/filter/detail, run history, all three fixture source options, saved source and A$0–150 usage preferences, effective budget information, report/CSV downloads and setup readiness. It uses synthetic practice businesses and keeps outreach disabled. All admin users share this engine's review workspace and run defaults.

## Admin accounts

For a fresh local installation, run `npm ci`, provision the existing Python/database prerequisites in `../abn-leadgen/README.md`, and create the first account before launching:

```powershell
npm run admin:account -- create --username admin --name "Maintain Media Admin"
```

Create an individual account for each additional administrator, and use the CLI to list, disable or reset accounts:

```powershell
npm run admin:account -- create --username reviewer --name "Lead Reviewer"
npm run admin:account -- list
npm run admin:account -- disable --username reviewer
npm run admin:account -- reset --username reviewer
npm run admin:account -- enable --username reviewer
```

Passwords are generated randomly and written to the private access file. A reset invalidates existing sessions for that account; disabling an account immediately blocks future requests. Reset does not re-enable a disabled account. Sessions last at most eight hours, are HttpOnly/SameSite cookies and are Secure over HTTPS. Sign-out clears the browser session; a copied stateless token remains subject to expiry, account status and password-reset revocation. Login throttling is local to the Node process.

For a managed Node deployment, supply **both** `ABN_ADMIN_ACCOUNTS_JSON` (the registry's `accounts` array) and `ABN_ADMIN_SESSION_SECRET` (a strong random secret of at least 32 characters) in private server configuration. Set `ABN_ADMIN_ORIGIN` to the exact HTTPS website origin. These settings are server-only and must never use a `NEXT_PUBLIC_` prefix. The local account CLI refuses to override an environment-managed registry. Multi-instance hosting needs a shared login limiter and managed account/session operations.

The current server bridge reaches only a co-located loopback engine, default `ABN_ENGINE_ORIGIN=http://127.0.0.1:8767`. It does not forward browser credentials or expose the engine's CSRF token. It checks the current admin session on every endpoint and masks report contacts through the existing engine authority checks. **Deploying Next.js to a remote host does not give it access to this Windows computer's engine.** Live sources and externally hosted engine authentication remain separate release work; do not publish the loopback engine port.

## Dashboard verification

The migration requirements and rubric are in [specs/abn-lead-gen-dashboard.md](specs/abn-lead-gen-dashboard.md). The final browser and review evidence is recorded in [acceptance/abn-lead-gen/review.md](acceptance/abn-lead-gen/review.md).

```powershell
npm run test:auth
npm run test:bridge
npm run lint
npm run build
npm run test:leadgen
```

Browser acceptance uses the repository's installed Playwright, reads the ignored local admin access file without printing credentials, executes actual fixture runs and restores the original saved preferences. It separately intercepts failures to verify recovery and checks unauthorized access, sign-in/out, report links, desktop/mobile layouts and keyboard behavior. Run it with the website and engine ready; these fixtures do not certify live provider integrations.

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
