---
title: "ABR Lead Engine - Activation Follow-up 2026-09-11"
project: Maintain Media
date: 2026-09-11
status: "Release 006 installed; business-data activation remains closed"
tags: [abr-lead-engine, maintain-media, deployment]
---

# Current activation follow-up — 11 September 2026

**Release 006 is installed and verified. The system is not yet collecting real
business data.** This note updates the current deployment position without changing
the earlier implementation history or approval status.

The [actual engine receipt](../../abn-leadgen/ops/acceptance/aws/live-service-release-006-20260911.json)
was checked at 2026-09-10T18:56:01Z (11 September, 02:56 Manila). It records
153 installed source files, 26 database migrations and an authenticated HTTP 200
with zero leads. No configuration, approval or enabled capability changed. The API
and worker/control/review-cleanup timers are active; all three backup timers,
weekly QBCC collection and general retention remain disabled.

Website contact collection now has its own default-off permission,
`website_collection`. It requires its own G1/G3/G7 decisions in addition to the
existing collection gates. The actual engine reports it separately blocked.
Approving QBCC intake alone cannot start website contact collection.

The [website deployment](../../website/acceptance/vercel/source-006-readiness-deployment-20260911.json)
is READY on `www.maintainmedia.com.au` and `maintainmedia.com.au`. All 59
non-middleware functions are in Sydney; Clerk middleware is separately global.
The current Clerk form does not prove a completed new staff login, which remains
unverified.

## What passed and what remains

Recorded checks passed: 496 unit tests, 83 distinct focused backend checks,
57 independent backend checks, 107 installed Linux offline checks, 72 frontend
checks and 12 production public/signed-out HTTP checks. Local and cloud website
builds/type checks also passed.

Google's protected Sheet and matching connection keys are installed, but live
sync remains disabled. GHL's 13 fields are installed with metadata-read access
only. The observed draft workflows do not certify complete automation isolation.
The encrypted Sydney storage probe passed earlier; accepted production backups,
independent key custody/recovery and an actual provider restore remain open.

The next business input is the attributable owner/adviser decision on the actual
legal entity, QBCC purpose and fields, notices, retention, and permitted vendors
and countries. No adviser response has been supplied. Existing accounts and
credentials do not need to be supplied again. The developer handles source checks,
staff integration tests, recovery, monitoring and scoped activation. See the
[first-live-QBCC brief](../../abn-leadgen/ops/production/first-live-qbcc.md) and
[draft decision pack](../../abn-leadgen/ops/production/approval-pack.md).

The first authorised QBCC worklist starts the four-week measured pilot. The
100-name classifier review belongs to later ABR expansion; it does not delay the
first QBCC-only worklist. QBCC source/schema and current-licence checks still apply.
ABR also needs its unfinished live-feed integration and full-feed host-capacity
measurements before expansion.

The [full-scope score remains 77/100](../../abn-leadgen/ops/production/live-completion.md),
with trajectory **57 → 72 → 77**. The new release closes a purpose-separation defect;
it does not pass the entire specification or enable outreach. Historical receipts,
release gates and the 63-of-71 task position are unchanged.
