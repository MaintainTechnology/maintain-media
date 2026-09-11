# QBCC pilot: first real import completed

**11 September 2026 — collection enabled; real QBCC source accepted for review.**

**Release 007 is live and Business source collection is approved in the signed
dashboard response.** Collection and finite deletion are enabled. The API,
worker/control, review-cleanup and retention services/timers are active; weekly
source collection and all three backup timers stay disabled.

The [completed import receipt](../acceptance/live-sources/qbcc-live-release007-result-20260911.json)
records job `b53a0928-454c-4014-a443-e2a43696cb99` completed at
**2026-09-11T00:03:19.451115Z** (08:03 Manila), about 57 seconds after it was
queued. The source was accepted, producing 11,034 source events and zero qualified
candidates. The [private source-review check](../acceptance/live-sources/qbcc-live-release007-reviews-20260911.json)
confirms **11,034 QBCC source records available for review**; its first 100 returned
records all had publisher status UNKNOWN and needed review. These are source
records, not 11,034 verified businesses or contact-ready leads.

The [host verification](../acceptance/aws/qbcc-live-release007-host-20260911.json)
records 196,116 raw licence-class rows, 108,019 usable parsed licence records,
517 quarantined records and one committed snapshot. The 11,034 review events are
the Category 1–2 subset. No genuine licence reviews, qualified leads or contacts
have been created yet.

The download is fresh, but the publication is dated **18 May 2026**. It is not a
new-licence feed. The [signed dashboard check](../acceptance/live-sources/qbcc-live-release007-dashboard-20260911.json)
confirms the accepted QBCC source and approved collection; the qualified lead
count remains zero until genuine current licence/identity reviews qualify records.
A fresh browser Clerk login is still unverified; use the existing admin account.

**Current decision: the user has authorised the limited QBCC pilot and delegated
the decision. We do not need to wait for Jon or obtain another approval for that
recorded scope.** The [delegated-owner record](../acceptance/live-sources/qbcc-pilot-delegated-owner-20260911.json)
permits manual QBCC collection and private internal review until **24 September
2026, 23:18:20 UTC**. It explicitly records that no adviser assessment was obtained.
The existing AWS/Vercel/Clerk/admin architecture is accepted for this pilot with
unverified support/global-processing countries documented. Google, GHL, website
contact collection, ABR, outreach and external exports remain off.

The [technical companion](qbcc-pilot-technical-decision-20260911.md) admits the
controlled first-file validation under scoped G2/G3/G7 decisions and separately
authorises finite deletion through **10 September 2027, 23:18:20 UTC**. This keeps
deletion available after collection permission expires. Full recovery and
independent custody are deferred pilot limitations, not passed production checks.
The [installed authority receipt](../acceptance/aws/qbcc-pilot-activation-20260911.json)
records collection and retention activation. The subsequent
[release 007 continuation](qbcc-pilot-release-007-decision-20260911.md) has five new
revision-2 technical evidence rows: collection G2/G3/G7 and retention G3/G7.
Both G1 records and the retention policy are unchanged. Actual CSV acceptance is
recorded above. The retention service then completed successfully with exit 0 at
**2026-09-11T00:05:33Z**, as recorded in the host verification. No newly imported
records were expected to be due for deletion. This verifies an actual retention
execution, not future expiry or full disaster recovery.

The older Jon/adviser questions below remain a wider-use review pack. They do not
override this specific, time-limited decision.

## How to use the activated pilot

1. Open the [ABN dashboard](https://www.maintainmedia.com.au/abn-lead-gen/dashboard)
   and sign in as the existing admin, `jeph@quotemax.com.au`.
2. In **Setup & settings**, choose **QBCC contractor register** as the data source.
   The recorded collection scope is installed; the weekly source timer stays
   disabled. Saving defaults does not enable any other blocked feature.
3. Open **Run history** to see the completed first import. For a later manual
   check, use **Check source updates** when no run is active. If a source is held
   or unavailable, leave it held; the developer diagnoses the cause.
4. An assigned reviewer can now use **QBCC source review → Load source records**
   and the linked current licence checker. Save only a genuine,
   evidenced licence/identity decision. An imported business can correctly remain
   UNKNOWN and absent from the qualified worklist.

The first usable authorised worklist starts the measured pilot. Importing a file
alone does not prove that the businesses are suitable or may be contacted.

The website and Australian engine are installed. The next step is to let the
engine prepare a real, private list of QBCC contractor businesses for staff to
review. Sending messages and making calls stay outside this build.

## You do not need to supply the accounts again

We already have the Maintain Media website, Maintain Technology Vercel account,
AWS Sydney service, Clerk admin access, Jeph's private Google Sheet and Maintain
Media GHL location. The connection credentials have been installed securely.
Do not put passwords or API keys in your reply.

The targeting decision is also recorded: 30 trades, QLD plus NSW postcodes
2450–2490, QBCC Categories 1–2, and up to 60 businesses each week.

The earlier [pre-activation recheck](../acceptance/live-integration-20260910/live-activation-recheck-20260911.json)
records a working authenticated engine, 26 database migrations, zero businesses
and zero release approvals. Google remains disabled; GHL has metadata access
only. A current Clerk sign-in form and an inspected draft GHL workflow do not
prove a completed staff login or safe contact automation. Its zero-approval count
is historical; the installed pilot authority and release 007 update above supersede it.

## Earlier wider-use questions retained for future review

For ordinary wider-use approval, Jon Pepper and a qualified Australian privacy/legal
adviser supply the business decision and assessment. The developer supplies
source/account evidence. These earlier questions do not delay the authorised
QBCC-only exception above.

The [draft decision pack](approval-pack.md) already contains the proposed purpose,
retention periods and review questions. Jon and the adviser need to settle:

1. **Who operates the tool?** The actual legal entity and ABN, the responsible
   privacy/complaint contact, and the notice or privacy-policy wording and link.
2. **What may we collect from QBCC, and why?** Confirm the exact publication's
   terms, purpose, necessary fields, notice timing and retention. The developer
   supplies the exact 11-field list, including business addresses, identifiers
   and licence details, and explains raw-file retention and current-licence review.
3. **Which companies may handle which information, in which countries?** Assess
   the actual account terms and processing/support countries for AWS, Vercel,
   Clerk and each enabled staff tool. Google and GHL can remain off pending their
   decisions. Signing in does not settle those decisions.
4. **Who can recover the backup keys if this computer/profile is lost?** Name a
   custodian; the developer handles the secure handover and recovery test.

These are the project's requirements in
[R27: reviewed collection and notice policy](../../../specs/abr-lead-engine.md#permission-suppression-and-safe-hand-off),
[R30: actual residency and vendor countries](../../../specs/abr-lead-engine.md#permission-suppression-and-safe-hand-off),
[G1: owner/adviser collection decision](../../../specs/abr-lead-engine.md#release-gates-and-dependencies)
and [G5: vendor decision and real integration tests](../../../specs/abr-lead-engine.md#release-gates-and-dependencies).
The instruction to make the tool live authorises implementation; it does not
create the missing adviser assessment or vendor evidence.

## The developer handles the technical work

A gate is a recorded check that must pass before a feature is switched on.
Enable each feature only for its approved source, account and purpose.

| Feature | Who supplies the decision | Developer's remaining checks before enabling |
| --- | --- | --- |
| QBCC intake (`collection`) | Recorded delegated-owner decision and installed technical authority; no new Jon approval required within scope/expiry | First import accepted; 11,034 source records are available for review. Preserve source age, genuine current licence review, UNKNOWN and separation from website collection. |
| Website contact collection (`website_collection`) | Its own source/purpose G1/G3/G7 decision; existing `collection` gates also required | Keep this separate capability off for QBCC-only review. Its controls are implemented; verify deployment, each site's current terms and business identity before any separately approved use. |
| Google worklist (`sheets`) | Its own G1/G3/G5/G7 decision and named readers | Verify genuine editor identity, sorted/stale/replayed edits, unsaved outcomes, outage masking and measured opt-out removal. Then bind the exact reader registry and enable the pull. |
| GHL hand-off (`crm`) | Its own G1/G3/G5/G7 decision | Finish automation inventory and isolation. Only then install needed contact scopes and run isolated duplicate, retry, field-clear, tag-preservation and suppression tests. Six visible drafts do not certify isolation. |
| Finite deletion (`retention`) | Installed separate authority through 10 September 2027, 23:18:20 UTC | Retention is active and the post-import service run passed with exit 0. Continue checking due-deletion receipts; collection expiry must not stop deletion. |
| Backups (`backup`) | Wider recovery/custody decision remains separate | Prove independent key recovery, quarantined restore with current restrictions, recovery interval, expiry, capacity, stopped-timer detection and external alerts. The encrypted storage probe passed; production backup acceptance is still open. |
| ABR discovery (`abr`) | Later owner expansion decision, including G6 | Keep off for the first QBCC worklist. Finish the live feed-to-accepted-leads connection and full-feed capacity measurements, as well as the later requirements below. |
| Email/phone action controls | Separate channel decision and G4 evidence | Keep off. This build does not send or dial. |

The separate website capability defaults to off. Its code, independent review and
[release 006 deployment checks](../acceptance/aws/live-service-release-006-20260911.json)
are complete; the actual authenticated engine reports it separately blocked.
Enabling QBCC intake alone does not authorise website contact collection.

The developer also tests a real staff Clerk login/dashboard and records acceptance
results for the installed revision. You do not need to troubleshoot servers or
write configuration.

## The four-week pilot comes after the first QBCC worklist

We do **not** need four weeks of results before starting the authorised QBCC
pilot. Once its foundations pass, staff can review the real worklist and record
outcomes for four measured weeks. Those results support the later ABR expansion
decision under [R38](../../../specs/abr-lead-engine.md#delivery-operation-and-success)
and [G6](../../../specs/abr-lead-engine.md#release-gates-and-dependencies).

The [R9 sample of 100 name classifications](../../../specs/abr-lead-engine.md#classification-qualification-and-work)
tests the name-based classifier before its later ABR launch or rule changes.
It is not a substitute for QBCC licence checks, nor a prerequisite for the first
QBCC-only worklist. QBCC source/schema accuracy still needs verification now.
ABR also needs unfinished live-feed integration and measured capacity for the full
publication on the actual host. The sample and pilot decisions alone do not finish
that engineering work.

## Wider-use decision form — not required again for this QBCC pilot

Leave anything unresolved as **not decided**. Attach the actual adviser
assessment; the developer will turn the completed decisions into reviewed records.

```text
Legal entity and ABN:
Privacy/complaint contact and notice/policy:
QBCC purpose, fields, notices and retention: approve draft / changes / not decided:
Adviser name, role, assessment document and date:
Decision on the developer's vendor/country evidence:
Jon's decision, limits, date and next review date:
Backup recovery custodian (name only):
```
