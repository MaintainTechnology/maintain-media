# First live QBCC worklist: the remaining decisions

**11 September 2026 — preparation brief, not an approval record.**

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

The [latest live recheck](../acceptance/live-integration-20260910/live-activation-recheck-20260911.json)
records a working authenticated engine, 26 database migrations, zero businesses
and zero release approvals. Google remains disabled; GHL has metadata access
only. A current Clerk sign-in form and an inspected draft GHL workflow do not
prove a completed staff login or safe contact automation.

## The first decision belongs to Jon and a qualified adviser

Jon Pepper approves the business use. A qualified Australian privacy/legal adviser
supplies the required assessment. The developer supplies source/account evidence
and installs the result.

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
| QBCC intake (`collection`) | Jon + adviser for G1; Jon/developer for G2, G3 and G7 | Bind G2 to the exact QBCC schema/mapping evidence; verify source age, current licence review, UNKNOWN results, actual accepted worklist and deployed separation from website collection. |
| Website contact collection (`website_collection`) | Its own source/purpose G1/G3/G7 decision; existing `collection` gates also required | Keep this separate capability off for QBCC-only review. Its controls are implemented; verify deployment, each site's current terms and business identity before any separately approved use. |
| Google worklist (`sheets`) | Its own G1/G3/G5/G7 decision and named readers | Verify genuine editor identity, sorted/stale/replayed edits, unsaved outcomes, outage masking and measured opt-out removal. Then bind the exact reader registry and enable the pull. |
| GHL hand-off (`crm`) | Its own G1/G3/G5/G7 decision | Finish automation inventory and isolation. Only then install needed contact scopes and run isolated duplicate, retry, field-clear, tag-preservation and suppression tests. Six visible drafts do not certify isolation. |
| Backups and deletion (`backup`, `retention`) | Jon/adviser retention decision; named custodian | Prove independent key recovery, quarantined restore with current restrictions, recovery interval, expiry, capacity, stopped-timer detection and external alerts. The encrypted storage probe passed; production backup acceptance is still open. |
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

## Short reply to complete with the decision pack

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
