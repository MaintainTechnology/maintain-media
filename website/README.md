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
