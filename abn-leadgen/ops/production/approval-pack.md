# ABN Lead Gen — draft source, privacy and vendor decision pack

**DRAFT — NOT APPROVED — known setup updated 11 September 2026 (Manila).**

Prepared for Jon Pepper (`jon@maintain.com.au`) and a qualified Australian privacy/legal
adviser. Nothing has been sent to them. This document does not approve collection,
contact, overseas disclosure or production release. It turns the open decisions in
specification R27, R29, R30, G1 and G5 into questions the reviewers can answer.

## What you are deciding

Maintain Media wants a small private list of contractor businesses that staff can
review. The computer helps organise the list and remember decisions and opt-outs.
It does not send emails, messages or make calls. A business being on a public
register does not, by itself, give permission to market to that business.

Jon provides the business decisions. The adviser records which legal rules apply
and whether the proposed collection, notices, retention and disclosures are suitable.
The developer supplies the technical evidence and enables only the approved scope.
“Qualified adviser” means someone able to assess the Australian legal/privacy issues;
an AI review or passing software test is not that assessment.

The first stage is the **QBCC contractor pilot**. The already approved targeting is
30 trade categories, QLD plus NSW postcodes 2450–2490, QBCC Categories 1–2, and at
most 60 businesses each week. These are targeting choices. They are not source or
privacy approvals. Broader ABR discovery stays off until the four-week QBCC pilot,
the owner decision and the separate matching-accuracy review are complete.

## Known setup and things still unknown

| Item | Current evidence or open question |
| --- | --- |
| Business using the tool | Maintain Media. Jon must confirm the exact legal entity name, ABN and business/privacy contact details. |
| Owner/reviewer | Jon Pepper is the nominated approver; `jeph@quotemax.com.au` is the website admin and Sheet owner. Confirm any other named staff and their locations. |
| Website | `www.maintainmedia.com.au`; Vercel under Maintain Technology. Record the account terms, all relevant processing/support countries and permitted telemetry. |
| Engine | The approved AWS Lightsail instance is in Sydney, `ap-southeast-2`. Release 005 is installed with migration 026 and limited runtime queue privileges. Its signed API check returned HTTP 200 with zero leads; the core worker/control/review-cleanup timers are active. A fresh staff Clerk browser flow is still unverified. An Australian server does not prove all vendors or support access stay in Australia. |
| Private worklist | [ABN Worklist](https://docs.google.com/spreadsheets/d/1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58/edit#gid=2107750955). The protected empty tab, standalone script and edit/repair triggers are installed. Workbook and script are **Restricted**, with Jeph alone listed. The real HTTPS endpoint and matching new server/Google keys are installed; the owner read back eight saved properties and verified both key matches without recording values. `ENABLED=false`, the reader registry remains a disabled draft without roles/approvals, and the API registry setting remains unset. No business rows or live pull are enabled. Actual staff write-back, suppression latency and vendor decisions remain unverified. See the dated Google preparation receipt. |
| Google operator | `jeph@quotemax.com.au`. Use this owner browser account; the existing connector belongs to another organisation and must not be used for this data. |
| Google processing countries | **Unknown for this account and Apps Script workflow.** Obtain its edition, signed/applicable terms, processing/support locations and subprocessor details. Restricted sharing does not establish Australian residency. |
| GHL account | Maintain Media, location `xHZFHMOE476t5CxY9vCG`. The new credential is securely installed; 13 empty field definitions and their folder assignment are verified. The saved integration has only location/field metadata read scopes; temporary field-write permission was removed and metadata reads passed again. No contact permissions, contact changes or workflow changes were made. Isolation/collision/suppression tests, current installation approval and actual processing/support countries remain unverified. |
| Backups | The user separately approved up to US$5/month for the now-installed private Sydney bucket `maintain-media-abn-backup-052530979168-983c39eb`, with a decimal 100 GB application cap; the budget is not an AWS billing hard stop. At 2026-09-10T18:05:38Z, an actual encrypted random-value upload/download/decrypt/delete-absence check passed without database or business data. The bucket is private, unversioned, with a 34-day lifecycle rule and a scoped publisher. Seven backup units are installed, but all three backup timers remain disabled. A missing-authority check held and recorded a local alarm; external alerts and stopped-timer detection remain unverified. No production backup is accepted. See the dated storage-installation and release-005 receipts. |
| Backup key custody and recovery | The private key is encrypted with Windows DPAPI in Codex's virtualized Windows profile; the operator confirmed the canonical custody path. It is absent from the Sydney source host. This does not prove that an independent custodian can recover it after loss of that profile. Named custody, independent recovery, retained engine-key versions, current-control recovery, approved backup/retention authority, a real quarantined restore and measured recovery loss/interval remain required. This draft creates none of those approvals. |
| Other vendors and overseas staff | Not approved by default. Record each actual recipient, purpose, country and account terms before enabling it. |

AWS's [data privacy FAQ](https://aws.amazon.com/compliance/data-privacy-faq/) explains
its region and data-handling model. Google documents region controls for supported
editions, with US/Europe/no-preference choices; do not assume those controls provide
an Australian location for this Sheet or cover Apps Script. See [Google's region
guidance](https://support.google.com/a/answer/14310028?hl=en-GB).

## G1 — source and collection decision

**Proposed purpose:** find a small number of trade businesses whose published
registration/licence details make them worth a human review for Maintain Media's
services. Record why each retained field is needed. Do not collect sensitive personal
information, private social profiles or unnecessary home-address details.

| Decision for Jon and the adviser | Current status | Evidence to attach |
| --- | --- | --- |
| Which legal entity operates this system, and does the Privacy Act apply to it? | NOT DECIDED | Entity details and the adviser's reasoned applicability assessment. Do not assume a small-business exemption. |
| May the identified QBCC publication be used for this exact purpose and workflow? | NOT DECIDED | Dated source/licence/terms capture and a purpose-specific assessment, including attribution requirements. |
| Which fields are reasonably needed? | NOT DECIDED | Approve a field list and exclusion list. Distinguish corporate information from information about identifiable people/sole traders. |
| May a reviewed business website be used to collect a contact endpoint? | NOT DECIDED | Source-specific permissions and the adviser's assessment of lawful/fair collection and address-harvesting restrictions. Keep automatic website contact collection disabled until resolved. |
| What notice is required, and when will people receive or find it? | NOT DECIDED | Approved collection notice, privacy policy, timing, access/correction/complaint process and responsible contact. |
| What channel rules apply if staff later conduct outreach outside this build? | NOT DECIDED | Separate email/phone assessment, including consent, source disclosure, opt-out, DNCR and APP7 interaction. This pack does not enable outreach. |
| Are the proposed retention times below necessary and suitable? | NOT DECIDED | Purpose for each period, adviser comments, owner decision, date and review/expiry date. |

The [official QBCC resource page](https://www.data.qld.gov.au/dataset/qbcc-licensed-contractors-register/resource/25608781-b28c-44f8-8545-0ab18d84082f)
currently identifies the licence as Creative Commons Attribution 4.0. It lists
18 May 2026 as the data update date. That is a source-age observation, not a current
licence check. The dataset's reuse licence does not settle privacy or marketing
permission. Show the actual source age and require the separate current licence
review described by the specification.

ABR is a later source. [ABN Lookup](https://abr.business.gov.au/Tools/BulkExtract)
describes a weekly XML extract of names, identifiers, state/postcode and registration
information. It does not list email or phone fields. Do not describe ABR as the
source of contact details obtained somewhere else. Recheck its exact publication
licence/terms when that phase is proposed.

The OAIC says that publicly available personal information still has collection
requirements; gathering only what is needed matters. The adviser should apply
[APP3 collection guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-3-app-3-collection-of-solicited-personal-information)
and [APP5 notice guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-5-app-5-notification-of-the-collection-of-personal-information).
Do not assume a notice only at first contact is sufficient for every collection.
The [OAIC direct-marketing guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/direct-marketing)
and [ACMA spam guidance](https://www.acma.gov.au/avoid-sending-spam) should inform
the separate channel assessment. ACMA addresses consent, sender identification,
unsubscribe facilities and address-harvesting software. These links are review
material, not a finding that the proposed use is lawful.

## R29 — proposed retention schedule for review

These are the specification's **proposed maximum periods**, not claims that the law
requires every record to be kept this long. The adviser and owner may require less.

| Information | Proposed maximum / trigger | Reason to assess |
| --- | --- | --- |
| Full downloaded source files | 30 days | Recover a failed import without building an indefinite archive. |
| Full analytical QBCC/ABR snapshots | 90 days | Compare accepted publications. If the source stalls beyond this, expire it and establish a new baseline. |
| Minimal event metrics | 24 months | Measure the service while keeping only necessary information. |
| Identifiable businesses never worked | 180 days after the last qualifying event | A routine crawl must not restart the clock. |
| Ordinary page captures not selected as evidence | 90 days | Check the collection, then remove unnecessary copies. |
| Selected contact, permission and action evidence | Proposed seven years after the last relevant assessment/attempt | The owner/adviser must document the need; seven years is not an automatic legal requirement. |
| Unnecessary fields after suppression/disqualification | Delete within 30 days | Keep only necessary restricted evidence and the information needed to respect the stop request. |
| Encrypted backups | 35 days | Finite recovery copies; test that expiry works. |
| Suppression tokens and aliases | Retain while necessary to honour the restriction; separately review any lawful end | Do not routinely erase a stop request or lose it during restore/key rotation. These are protected/pseudonymous data, not assumed anonymous. |

Any legal hold needs its reason, exact scope, owner and next review date. A restore
must stay closed to users until the latest stop/deletion ledger has been replayed,
overdue deletion has run, and keys and restrictions are checked. The [OAIC APP11
guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-11-app-11-security-of-personal-information)
is relevant to security and disposal decisions.

## G5 — vendor decision and evidence

A vendor is another company handling some of the information. A subprocessor is
another company that vendor uses. For **each** enabled vendor, record these items:

- The exact product/account and the information it receives.
- Why it needs that information, including support access and logs.
- The actual processing, storage, backup and support countries.
- The applicable signed/account terms and data-processing agreement, with dates.
- The relevant subprocessor list and how changes will be monitored.
- The overseas-disclosure assessment, safeguards, deletion process and complaint contact.
- The approving person, evidence file/link, evidence hash, date, expiry and limitations.

For Google, attach the account's applicable [data-processing terms](https://cloud.google.com/terms/data-processing-addendum/)
and [subprocessor list](https://workspace.google.com/terms/subprocessors/), and confirm
how they apply to both Sheets and Apps Script. For GHL, review the [data-processing
agreement](https://www.gohighlevel.com/data-processing-agreement) and [subprocessors](https://www.gohighlevel.com/sub-processors).
The public documents alone do not prove the exact service/account settings or all
actual access countries. **Unknown remains unknown and the affected adapter stays
off.** The adviser should record the relevant [APP8 overseas-disclosure assessment](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-8-app-8-cross-border-disclosure-of-personal-information).

The developer must also attach real account tests before enabling GHL: field and
location identity, exact business-group search, timeout-after-create reconciliation,
unrelated-tag preservation, DND and field clearing, and opt-out propagation. Review
Contact Created/Changed/Tag/DND automations so a contact/tag write cannot start an
unapproved workflow. Code that avoids the send endpoint is not proof that the
account has no triggered automations.

The owner has now observed six Draft workflows with zero total/active enrolments
in the visible first page of GHL's Marketing Workflows folder. This was a read-only
list check; pagination completeness, trigger/action definitions and other account
automations were not established. It does not satisfy the isolation test above
or permit contact writes. The dated workflow-list observation records its limits.

For Sheets, attach Restricted sharing and protections, standalone script ownership,
actual editor identification, sorted rows, stale versions, duplicate/replayed edits,
automatic real worklist pull, every named reader's assigned scope, preservation of
unsaved edits, outage redaction/recovery, and durable opt-out tests. Measure the
one-minute restriction timer's real delay: its configuration is not proof of the
specification's 60-second available-system propagation target. If the target is not
met, a verified immediate removal path is required before live disclosure.
The developer's local synthetic tests
are useful engineering evidence; they are not these live installation receipts.

The service keeps Google and GHL approvals separate. Google's technical scope is
`sheets`; GHL's scope is `crm`. Each requires its own current G1/G3/G5/G7 records.
Google's G5 record must identify the exact approved workbook/tab/reader registry
file and its hash. GHL's G5 record identifies the exact account installation file
and its hash. Approving one company does not approve the other company.

## Record the decision without guessing

Complete one record for G1 and a separate record for each vendor/G5 scope. Leave
the status **NOT DECIDED** until the responsible people have actually reviewed it.

| Field | Value to complete |
| --- | --- |
| Decision | NOT DECIDED — later choose approved, approved with limits, or rejected. |
| Exact scope | QBCC pilot collection / Google worklist / GHL hand-off / other named scope. |
| Legal entity and purpose | To be completed by Jon. |
| Owner name and decision date | To be completed by Jon. |
| Qualified adviser name, role and assessment date | To be completed by the adviser for G1/privacy questions. |
| Evidence attached | Exact source/terms/notice/retention/vendor/account-test files or stable links. |
| Conditions and exclusions | What is allowed, what must stay off, and what must be fixed first. |
| Approval expiry / next review | A real future date chosen by the responsible reviewer. |
| Signature or attributable written decision | Not yet supplied. |

The developer then hashes the final evidence, records the named decision through
the restricted deployment process, and checks the exact release revision. G1/G5
do not replace G3 hosting/backups, G7 technical release or the measured pilot. No
approval records or enable flags are created by saving this draft.
