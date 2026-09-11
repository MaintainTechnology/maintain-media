---
title: ABR Lead Engine - GHL Phone Handoff 2026-09-11
project: Maintain Media
date: 2026-09-11
status: GHL account enabled; zero real business hand-offs
tags: [abr-lead-engine, maintain-media, ghl]
---

# What is working now

The lead engine can connect to the correct **Maintain Media GoHighLevel account**.
Its account connection was enabled on release 009b after real account tests.
GHL is a separate place where staff can keep an approved business record.
The current release is **010**. Its narrow source-cleanup repair was verified on
the running server; the GHL connection and individual approval rules are unchanged.

The engine already has one genuinely reviewed business and two landline
numbers from its reviewed website. **It has not sent that business to GHL.**
No business is selected for the worklist, and no real transfer is queued.

Think of this as a checked delivery door. The door is ready, but every business
still needs its own checked permission slip before its record can go through.
Approving the door does not approve everything in the building.

## What was tested

Two clearly labelled test contacts were created in the real account and removed
afterward. No real business contact details were used for those tests. The checks
proved that the engine could read its fields, find the right record, refuse a
duplicate without changing the first record, clear its saved details, preserve
an unrelated tag and keep **Do Not Disturb** on.

One test showed that GHL can take time to show a newly created record in search.
The engine now keeps that uncertain result and checks again; it does not blindly
create another contact. All six checked workflows stayed Draft with zero enrolments.
The runtime checks the reviewed workflow inventory before every change. This
does not stop an account administrator changing settings between requests.

Do Not Disturb is a protective account setting. It is **not consent to call**.
The lead engine does not send emails, make calls or enrol campaigns.

## Why the real business is still waiting

The connection is only one piece. The real phone still needs a current, genuine
Do Not Call Register check and its verification/locality review. The importer
that accepts the real provider's DNCR result format still needs to be built and
tested. The existing practice-file importer cannot stand in for that result.

After those checks, the business must meet the qualification rules, be selected
as an eligible tier A worklist row and receive an explicit reviewer decision for
that exact current row. This is unfinished implementation and evidence work;
signing into the account again will not complete it.

## What to open

1. Open [the dashboard](https://www.maintainmedia.com.au/abn-lead-gen/dashboard) and sign in with the approved Maintain Media account.
2. Refresh the page. Setup should show **GoHighLevel hand-off** approved while its dated authority remains current.
3. Select the reviewed business and read its **GoHighLevel hand-off** section. With no selected worklist row, it should show **Not selected for hand-off**.
4. Keep reviewing the captured phone evidence. An assigned reviewer can approve a hand-off only after the remaining real checks and selection are complete.

Later, **Queued for hand-off** means a request has been saved. **Hand-off verified**
means the engine checked that the approved projection reached GHL. Neither status
means a call was made or a message was sent.

## Limits and evidence

The limited phone-only acquisition decision expires **24 September 2026 at
23:18:20 UTC**. Separate removal authority lasts until **10 September 2027 at
23:18:20 UTC**; it does not allow new acquisitions after September 2026. The
decision records US storage and US/India service/support plus unknown provider
backup expiry. It is an owner-delegated decision, not a legal certification.

Google Sheet publishing, broader ABR and weekly collection remain off. Real
business backup/restore, independent recovery-key custody, outside alerts,
capacity and measured pilot acceptance are still outstanding. Current full-tool
progress is **87/100**, with trajectory **57 → 72 → 77 → 82 → 85 → 87**.

- [Actual GHL account tests](../../abn-leadgen/ops/acceptance/live-integration-20260910/ghl-live-account-contract-20260911.json)
- [Account activation](../../abn-leadgen/ops/acceptance/aws/ghl-dnd-pilot-activation-receipt-20260911.json)
- [Host and capability readback](../../abn-leadgen/ops/acceptance/aws/ghl-release009b-host-20260911.json)
- [Signed dashboard check](../../abn-leadgen/ops/acceptance/live-sources/ghl-release009b-dashboard-20260911.json)
- [Current release 010 host and cleanup verification](../../abn-leadgen/ops/acceptance/aws/cleanup010-host-20260911.json)
- [Current reviewer/access checks](../../abn-leadgen/ops/acceptance/live-sources/ghl-release010-reviewer-controls-20260911.json)
- [[ABR Lead Engine - Implementation Status]]
- [[ABR Lead Engine - Build Hub]]
