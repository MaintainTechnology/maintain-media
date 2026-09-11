---
title: "ABR Lead Engine - Activation Follow-up 2026-09-11"
project: Maintain Media
date: 2026-09-11
status: "Release 010 verified; GHL connection enabled, real individual hand-offs pending"
tags: [abr-lead-engine, maintain-media, deployment]
---

# Current activation follow-up — 11 September 2026

**Release 010 is running and verified. GHL account activation was completed in
009b and remains enabled.** Real QBCC and reviewed
website-phone collection continue. One genuinely reviewed business has two
private landlines, but **zero businesses are selected or exported**. The live
DNCR receipt adapter and genuine phone/qualification checks still need completion
before an individual hand-off can be approved. Account sign-in alone cannot
complete those steps.

The 010 repair fixes a protective cleanup hold that had incorrectly included
completed accepted intake in abandoned staging. Actual cleanup and retention
completed successfully at 02:18:58 and 02:18:59 UTC. All three accepted source
artifacts still match their ledger hashes/sizes. The configuration and both
policies were preserved; there are 25 dated gate rows. API and four core timers
are active, while weekly source collection and all three backup timers stay off.
See the [actual host receipt](../../abn-leadgen/ops/acceptance/aws/cleanup010-host-20260911.json)
and [current dashboard check](../../abn-leadgen/ops/acceptance/live-sources/ghl-release010-dashboard-20260911.json).

See [[ABR Lead Engine - GHL Phone Handoff 2026-09-11]] for the plain-English
connection result and next steps, and [[ABR Lead Engine - Website Phone Pilot 2026-09-11]]
for the existing real website evidence. The current implementation assessment is
**87/100**, trajectory **57 → 72 → 77 → 82 → 85 → 87** under the original rubric.
This is a progress score, not full production acceptance. Earlier checkpoints
below are historical.

## Earlier QBCC activation checkpoint — release 007

**Release 007 is live. Manual QBCC collection and finite deletion are enabled;
the first real source import completed.** This supersedes the closed-activation state
in the earlier release 006 section below.

The user explicitly authorised the QBCC pilot and delegated the decision, so
there is no need to wait for Jon within the recorded scope and expiry. The
[owner decision](../../abn-leadgen/ops/acceptance/live-sources/qbcc-pilot-delegated-owner-20260911.json)
permits manual public QBCC intake and authenticated internal review until
**24 September 2026, 23:18:20 UTC**. No adviser report is claimed. The existing
AWS Sydney/Vercel/Clerk/admin architecture is accepted with unverified support
and global-processing countries documented; this is not an Australian-only
processing claim.

The [initial activation receipt](../../abn-leadgen/ops/acceptance/aws/qbcc-pilot-activation-20260911.json)
records enabled collection and retention. The
[release 007 continuation](../../abn-leadgen/ops/production/qbcc-pilot-release-007-decision-20260911.md)
is installed with five new revision-2 evidence rows: collection G2/G3/G7 and
retention G3/G7. Both G1 records and the retention policy are unchanged.
The signed dashboard response reports Business source collection approved.
The API, worker/control, review-cleanup and retention are active. Weekly source
collection and all three backup timers remain disabled.

The [actual completed-import receipt](../../abn-leadgen/ops/acceptance/live-sources/qbcc-live-release007-result-20260911.json)
records job `b53a0928-454c-4014-a443-e2a43696cb99` completed at
**2026-09-11T00:03:19.451115Z** (08:03 Manila), about 56.993 seconds after queuing.
Snapshot `f10d2ded-a3d1-56b8-8770-883998f33815` is accepted at cursor version 1,
with content digest `92f95da5b9542027275d10558c38639894e7ff338734382699f022ce822922b5`.
It produced 11,034 source events and zero qualified candidates.

The [post-import host verification](../../abn-leadgen/ops/acceptance/aws/qbcc-live-release007-host-20260911.json)
records 196,116 raw licence-class rows, 108,019 usable parsed licence records and
517 quarantined records. One source snapshot is committed; its Category 1–2
review subset contains 11,034 events. There are zero genuine licence reviews,
qualified leads and contacts.

The [signed source-review check](../../abn-leadgen/ops/acceptance/live-sources/qbcc-live-release007-reviews-20260911.json)
confirms 11,034 source records available for review, with the first 100 all showing
publisher status UNKNOWN and review status `needs_review`. These are not 11,034
verified businesses or contact-ready leads. The download is fresh; the publisher's
date remains **18 May 2026 at 05:14:43.785988**, so this is aged discovery material,
not newly issued licences. The
[signed dashboard check](../../abn-leadgen/ops/acceptance/live-sources/qbcc-live-release007-dashboard-20260911.json)
reports the accepted source, approved collection and zero qualified leads.
A fresh staff browser Clerk login is still unverified; the existing admin account
is `jeph@quotemax.com.au`.

The [technical companion](../../abn-leadgen/ops/production/qbcc-pilot-technical-decision-20260911.md)
separately authorises finite deletion until **10 September 2027, 23:18:20 UTC**,
so collection expiry does not stop due deletion. The actual post-import retention
service completed successfully with exit 0 at **2026-09-11T00:05:33Z**. No newly
imported records were expected to be due for deletion; this does not prove future
expiry. Full recovery and independent custody remain
deferred pilot limitations. Google, GHL, website contact collection, ABR, outreach
and external exports remain off; production backup acceptance remains open.

Open the dashboard and inspect **Run history** for the completed request. An
assigned reviewer can now load **QBCC source review** and record a genuine current
licence/identity check. See the updated
[operating brief](../../abn-leadgen/ops/production/first-live-qbcc.md) and
[wider-use decision pack](../../abn-leadgen/ops/production/approval-pack.md).
The [full-scope progress score](../../abn-leadgen/ops/production/live-completion.md)
is now **82/100**, with trajectory **57 → 72 → 77 → 82**. The actual source import
and limited admission evidence add four source-workflow points; the real retention
execution adds one operations point. This is a progress assessment, not a full
specification pass, final plateau or acceptance of the remaining wider work.
The earlier 77 score below is historical.

## Earlier release 006 observation — superseded activation state

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
