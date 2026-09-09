---
title: ABR Lead Engine - Explained Simply
type: explainer
project: Maintain Media
explains: "[[ABR Lead Engine]]"
spec-version: "3.5"
written: 2026-09-08
tags:
  - explainer
  - abr-lead-engine
  - lead-generation
  - plain-english
  - maintain-media
---
> [!summary] The whole thing in one breath
> We are building a robot. Every week it reads the government's giant list of every business in Australia. It spots which businesses changed since last week. It picks out the ones most likely to want our help. It finds a lawful way to reach them. Then it hands a short, safe to-do list to a helper, who makes the calls and sends the emails. The full spec is here: [[ABR Lead Engine]].

## 1. The giant list of businesses

Imagine the government keeps one enormous book. Every business in Australia has a page in it. Every page has a special number on it, called an ABN. Think of the ABN as a name tag. There are about twenty million name tags in the book.

Every week the government puts a fresh copy of the whole book on a website. Anyone can take it for free. It comes as two big zipped boxes. Inside the boxes are twenty smaller books. Nobody is allowed to write the number twenty into the code, because the government is about to change how many small books there are.

The book tells you:

- the business's number, and whether it is open or closed
- what shape it is: one person, a company, a trust, and so on
- its name, or several names
- whether it pays a tax called GST, and since when
- which state it is in, and its postcode

The book does not tell you:

- a phone number
- an email address
- a street address
- a website
- what the business actually does

So the book is a great list of who exists, and a terrible list of how to reach anyone. That gap is why the rest of the machine exists.

The book comes out on Wednesday mornings Australian time. The exact moment shifts when the clocks change for daylight saving, so the robot must never be set to a fixed clock time. Instead it checks the website every six hours and asks "is there a newer copy?" It only starts work when both boxes are new and were posted within two days of each other. If the two boxes stay mismatched for a week, it rings an alarm and waits for a human.

## 2. Playing spot-the-difference

The robot takes a photo of the whole book every week and keeps every photo. Then it puts this week's photo next to last week's photo and plays spot-the-difference. This is called a diff.

Things it can spot:

- **New business.** A name tag that was not there last week and is open now.
- **Business closed.** Open last week, closed this week.
- **Business came back.** Closed last week, open this week. This is never counted as "new".
- **GST flip.** Did not pay GST last week, pays it now. That means the business just grew past seventy-five thousand dollars a year. A brand-new business that already pays GST counts as "new", not as a flip.
- **GST switched off.** Paid GST last week, not now.
- **Name changed.** The robot tidies the names first, so a change from lower-case to upper-case does not count.
- **Name tag vanished.** Gone completely. This should never happen. If it does, ring an alarm. It is never a lead.

Why photos, instead of trusting the dates written in the book? Because the "closed since" date is often wrong. Businesses tell the government "actually, I closed ages ago", and the book writes down that old date. About one closed date in three is more than a month in the past, and some are decades old. So you cannot ask the book "who closed this week?" You have to compare photos. The spec says the code must carry a comment explaining this.

Start dates are safer. A wrong start date only makes a business look older, and older is the safe direction for the tests below.

Two more tricks:

- Compare by name tag number, never by page number. The small books get re-cut every week, so page five this week is not page five last week.
- On the very first week there is nothing to compare against. The robot takes its first photo, writes "baseline done", and stops. No alarms fire that week.

The robot also checks its own work. Each small book says how many pages it holds. If the robot counts a different number, it throws the whole photo away and rings an alarm. It also checks that the usual boxes are filled in, like state and name. If those drop by more than a couple of percent, something about the file format changed, and the run fails on purpose.

## 3. Sorting the businesses

For every business, the robot writes down three labels.

1. **What shape is it?** One person, a company, a trust, a partnership, a super fund, government, or other.
2. **What does it do?** The robot reads the business's names and looks for clue words. "Plumbing" means plumber, and so on. There are thirty clue rules, and they are kept exactly as they are today. If no clue matches, the label is "Unclassified".
3. **When was it born?** The date it became active, kept as a month bucket.

There is a catch about names. A business can have several kinds of names, and they are not equally trustworthy.

| Name kind | What it is | How much we trust it |
|---|---|---|
| BN | A business name registered with ASIC | High. This is the only fresh, current name. |
| Main or legal name | The name the ABR holds | Medium |
| TRD | An old trading name | Medium at best. The government stopped updating these in 2012, so they can be fourteen years stale. |
| OTN | Other names | Never read. These are often a person's nickname. |

The robot reads the BN names first, then the main name, then the old trading names. The first clue that matches wins, and it writes down the exact words that matched, so a bad guess can be traced back later.

The sad truth: most new businesses are one person whose only name is their own name, like "JANE SMITH". No clue words at all. About three in four new businesses end up Unclassified. That is not a bug. That is the ceiling of the data.

The robot also watches how many it could not classify each week. If that number jumps by more than three points from one week to the next, it rings an alarm.

## 4. Picking the good ones

Here is the surprise in the spec. The original idea was "find brand-new businesses and sell to them". But a brand-new ABN is a weak sign. Getting one is free and takes ten minutes. About two thirds of ABNs are not really trading. Lots belong to rideshare drivers. A day-one business has no money. And every accountant and online company-maker is already talking to them at that moment.

The spec builds the original idea anyway. But it also builds two much better signs, at almost no extra cost, and puts them first.

**Tier A, the best leads:**

- A business that is one to five years old and just flipped GST on. It just crossed seventy-five thousand dollars a year. It has customers, cash, probably a website, and probably a public business email. That last part is what makes lawful contact possible at all. Nobody else is competing for this moment.
- A Queensland licensed builder in QBCC Category 1 or 2. More on this below.

**Tier B, the original brief, filtered:** a new ABN that is a company or trust, already pays GST, and whose industry the robot could guess.

**Tier C:** every other new ABN. Counted and reported. Never worked.

**Closed businesses** go straight onto the "never contact" list.

The tier rules live in a small settings file, not in code, so they can be changed without a developer.

**Points.** Each lead gets a score so the helper works the best ones first.

| Thing | Points |
|---|---|
| Tier A | 60 |
| Tier B | 30 |
| Industry guess is high confidence | +15 |
| Industry guess is medium confidence | +5 |
| In the target area | +10 |
| It is a company | +5 |
| We found a verified email | +20 |
| We found a phone | +15 |
| We found only a website | +5 |

Take only the best one of the contact rows. Cap the total at one hundred. Ties go to the older business first.

Points are counted twice. Once before we look for contact details, to decide who to look up first. Once after, to decide the final order on the helper's list. Builders from the QBCC list use their own points because they do not have an ABR record yet: their financial category counts instead of industry, and a company licence gets a small bonus.

**Where.** Only Queensland and northern New South Wales, postcodes 2450 to 2490, for the first eight weeks. That is where Maintain Media sells, and it cuts the lookup bill by about eighty percent. It is one line in the settings file.

**Money guard.** At most one hundred and fifty Australian dollars a month on lookups. When the cap is hit, stop looking up, finish the run, ring an alarm, and queue the rest for next week. There is no way to run up a surprise bill.

## 5. The builder list, and why it comes first

Queensland publishes a list of licensed building contractors. It is called the QBCC register. It is a different list with different superpowers.

- It has full street addresses. The government book only has state and postcode.
- It has a "financial category" that says how much money the regulator believes the business handles.
- Category 1 and 2 means about eight hundred thousand to twelve million dollars a year. There are 11,080 of these. This is the one number in the whole spec that was actually counted rather than guessed.

But it has quirks:

- The file is written in an unusual text encoding called UTF-16LE. Read it the normal way and you get garbage.
- One licence can appear up to thirty-two times, once per licence class. Squash them to one row per licence.
- Almost half the rows have no ABN, so they cannot be matched to the government book. Keep them anyway, keyed on the licence number.
- One ABN can hold several licences. Each licence becomes its own lead, and the helper's list removes doubles so nobody gets the same business twice in a week.
- The file has not changed since May, about sixteen weeks. So it is not a weekly signal. The robot checks it weekly and only re-reads it when it actually changes.
- The address is one long string. The rule: the last four-digit chunk is the postcode, the word just before it is the state, and everything before that is the street. If a row has no state and postcode at the end, keep it, count it, report it, but leave it out of the area filter.
- The list includes some interstate builders, so filter on the address, not on the fact that it came from Queensland.

**Phase 0.** Build this list first. It takes one or two days of developer time. It needs no photos, no spot-the-difference, no weekly timer. Give the helper four weeks of to-do lists from it, with the top two hundred looked up for contact details.

Then the test: if nobody books a meeting in four weeks, the problem is the offer or the phone script, not the data. Stop and fix the offer. Do not build the twenty-million-record machine to fix a sales pitch problem.

## 6. Finding a way to reach them

This is called enrichment. It only runs for tiers A and B, and only if we have not looked at that business in the last ninety days. Three steps, in order.

1. **Find the website.** Ask a search API up to three carefully shaped questions. First, the name plus the suburb plus the state. The suburb comes from a free government postcode table. Second, the ASIC business name plus an industry word plus the state. Third, the name plus the postcode. Take the first real result that is not a directory, marketplace or social site. Yellow Pages, Hipages, Facebook, LinkedIn and friends are all skipped. Google Maps and Google Places may never be used, because their terms forbid saving business details.
2. **Read their website.** The home page plus up to four pages that look like contact, about, team or quote pages. Be polite: obey robots.txt, one request a second, and say who you are in the browser name with a contact link. If a site blocks us, back off, try once more, then give up. Never use tricks to get past a block.
3. **Check the email works** with a verification service. Only "deliverable" counts. "Catch-all" and "unknown" are stored for the record but never sent to.

Stop rules: no own website, stop after step one. Phone found but no email, stop after step two. Email found, always do step three. Hard limits per business: three searches, six page fetches, one verification. Blow a limit and the business is marked "exhausted" and left alone for ninety days.

What gets saved: the website, a contact form link, emails, phones, social links, and a short set of "positioning notes". The notes are not written by an AI. They are copied bits: the page title, the description, the first heading, and the three most common service words from a fixed word list. Copying is auditable. Making things up is not.

**The golden rule of enrichment:** every contact detail must come with a receipt. Where did we get it, which page, a saved snapshot of that page, the text around it, when, by what method, and whether we obeyed robots.txt. The database is built so that a contact detail without a receipt cannot exist.

## 7. The rules

This is the biggest and most serious part of the spec. Using the government book is allowed under its licence. The hard part is the laws about marketing. Four laws matter: the Spam Act, the Privacy Act, the Do Not Call Register Act, and the Australian Consumer Law.

**Rule 1. Never buy a list, and never pay anyone to add contact details.** Doing that would strip away the small-business protection in the Privacy Act. Never sell the list either, for the same reason.

**Rule 2. "It was on their website" is not a free pass.** Each email address has to pass five checks. They are stored as five yes-or-no boxes.

- **a. It points to a person or a role.** A named person at the business's own domain passes. A generic inbox like info@ passes only for a one-person business, or an individual licence holder, or when the page shows that inbox next to a named person in a stated role.
- **b. It is visible as plain text** on a page anyone can reach without logging in.
- **c. It is on the business's own website.** Directories and review sites fail this forever.
- **d. There is no "no unsolicited marketing" notice** on that page or on the site's terms page. If the site has no terms page at all, that still passes, as long as the crawl finished properly.
- **e. The message we send is relevant to that role.** This one is checked every single time we send, not once per record. The sending system in Part 2 owns this box.

**Rule 3. Fail closed.** If a box is not proven yes, the email is not exported. The gate lives in the export code, not in the helper's judgment. But the spec also insists the gate can actually open: there is a test where a fully clean record must come out the other side, marked "email sendable, pending relevance". Without that test, a gate that blocks everything would look perfect.

**Rule 4. Every phone number gets washed** against the Do Not Call Register within the last thirty days, with a receipt from the washing provider. No exceptions for business numbers. This cohort runs on personal mobiles anyway.

**Rule 5. The yes-boxes expire after ninety days.** A business can add a "do not contact us" notice at any time, so the robot re-checks against a fresh page capture before exporting again.

**Rule 6. The "never contact" list is global and permanent.** Unsubscribe from Maintain Media and you are also off MaintainAI and QuoteMax. The list is keyed on a scrambled version of the email or phone, so it survives even if the original record is deleted. A cancelled ABN goes on it too. Nothing on the list is ever looked up again.

**Rule 7. Opt-out everywhere.** Every message on every channel, including the helper's phone script, must offer a simple way to say no. If someone asks "where did you get my details?", we must be able to answer. The receipts from section 6 make that possible.

**Rule 8. Messages must say who sent them** and how to unsubscribe. Legal name, ABN, address, a contact that works for at least thirty days, and an unsubscribe link honoured within five working days. First contact must also include a privacy notice: who we are, where we got the details, why, where the privacy policy is, how to complain, and which countries can see the data. Part 1 does not send anything, but it defines these fields and fails the export if any are missing.

**Rule 9. Calling hours** in the recipient's time zone. Weekdays nine to eight, Saturdays nine to five, never Sundays, never public holidays. If a sale might be closed on the call, weekdays nine to six instead. The default is six. Show your number, say who you are and why, and hang up if asked.

**Rule 10. Selling from an uninvited call** creates what the law calls an unsolicited consumer agreement. The buyer gets ten business days to change their mind, and we may not take payment or start work in that time. If the required disclosures were not given, that window stretches to three or six months. So the helper's opening script must contain the disclosures, the proposal template must contain the cooling-off notice, and the system records whether the contact was invited. That flag must be set at first touch, because it cannot be worked out later.

**Rule 11. The helper writes back what happened** for each lead, using a fixed set of words: not started, no usable contact, attempted no answer, contacted not interested, contacted nurture, meeting booked, meeting held, disqualified, and do not contact requested. That last one instantly puts the business and all of its contact details on the never-contact list. Without this write-back, the week-eight decision cannot be made.

**Rule 12. Keep the evidence for seven years.** Suppression hashes are kept forever. Profiles of people who opted out or were disqualified are destroyed on a schedule.

**Rule 13. The giant photo archive is a privacy question.** It holds millions of people's names. The spec's position: it is the spot-the-difference tool, not a marketing database. Lock it away separately, never query it for marketing, keep weekly photos for two years and then thin them to monthly. If the lawyer says even that is too much, keep only scrambled numbers for out-of-area records.

**Rule 14. Data lives in Australia.** Every overseas party that touches the data is listed with its country: the helper, GoHighLevel in the US, the search provider, the email verifier. Page captures must stay in Australia. Contracts must push the legal duties back to Maintain Media, because the law can hold Maintain Media responsible for what those parties do.

**Rule 15. A question only a lawyer can answer:** is our website reader "address-harvesting software" under the Spam Act? The defence holds only as long as the five-box gate holds.

## 8. What comes out each week

1. **A report.** Counts of everything, what is new, what closed, the unclassified rate, lookup hit rates by tier, spend against the cap, and every alarm. Styled with the Maintain Media design system.
2. **The helper's to-do list**, a Google Sheet with the top sixty leads. That is about two hours of work at two minutes each. Leftovers roll to next week and are re-ranked. To stop the queue clogging forever, two rules apply. The builder list alone is 185 weeks of leads. A lead not worked within eight weeks is set aside until something new happens to it. And ten of the sixty slots always go to the oldest waiting leads, so age eventually beats score. Each row says in plain words what to do: "Email: OK to send", "Do not email", "Call after DNC wash". Each row also carries an opener that matches the reason it is there, like "registered for GST last week after three years trading", plus the calling window for that time zone.
3. **A push into GoHighLevel** for tier A leads that pass the gate. One contact per call, because there is no bulk endpoint. Respect the rate limits. Add tags with the tag endpoint, never by overwriting the tags field. Tier B stays on the sheet for a human to review.
4. **A run manifest file** recording everything the run did: what triggered it, counts, events, tiers, spend, pushes, rules version, how long it took, and every alarm.
5. **Alarms** by email and a healthcheck ping when things look wrong. The full list: no new file in ten days, page counts do not match, small-book count changed, zero changes on a normal week, any change type wildly off its usual number, hit rate low two weeks running, spend cap hit, API quota gone, vanished name tags, mismatched boxes for more than a week, unclassified rate jumped, field-fill check off, and builder address parse failures above one percent.

## 9. How it is built

- Python, with a small columnar database called DuckDB and Parquet files for the photos and spot-the-difference. A proper PostgreSQL database for everything with a legal duty attached: contacts, receipts, consent boxes, the never-contact list and outcomes. Contact details are encrypted at rest.
- Plain cron and systemd. No fancy workflow tools. One person must be able to log in and run the exact command the timer runs.
- A small server in Australia for about twenty dollars a month, plus Australian object storage for the photo archive and page captures. The server's disk holds only the current work; the archive lives in object storage.
- Running cost depends mostly on where the computer lives, not on how many businesses we look up. On the cheapest Australian host it is roughly twenty to forty-five dollars a month. On any other Australian host it is roughly fifty to one hundred dollars a month. Looking up businesses is the small part, about six to thirty dollars. The safety cap on looking things up is one hundred and fifty dollars, so there is a lot of room.
- One repo, one README, one command. A lock file so two runs cannot overlap. A runbook for the five bad days: the file is late, the parse fails, the cap is hit, the CRM push half-finishes, and re-running one stage.
- Build time is fifteen to twenty-three developer days. Phase 0 is one or two of those.

## 10. The honest money talk

The helper can work sixty leads a week, about two hundred and sixty a month. The spec walks the funnel through: two call attempts each, about a third answer, five to ten percent of those book a meeting, most meetings happen, and a fifth or so of those buy. That lands at roughly half a sale to one and a half sales a month.

The goal is fifty thousand dollars a month, which needs about twenty clients paying two and a half thousand each. This channel, at this staffing, is about ten times too small. The spec calls it a test bench, not the engine. Either staff it properly, or use it to feed good conversations into a bigger offer. The spec says to argue about this number before building, not after.

## 11. What is not being built

- Part 2: client onboarding, website builds, and the proposal.
- Sending anything. No email, SMS or dialling. Part 1 only produces the gate status and calling window.
- A data product to sell. Enrichment is a commodity, and reselling would break the Privacy Act rule.
- Buying data or paying anyone to append it.
- Google Places or Maps.
- Scraping SEEK or other job boards. Job ads are the best signal of all, but the terms forbid it, so it stays a manual play for the helper.
- More industry clue rules. Deferred to the next version, one category at a time with tests.
- History from before the first run. There is none.
- The daily ABN Lookup API. Maybe later, as a speed-up on top of the weekly photos, never instead of them.

## 12. How we know it is done

The tests are staged. Fixture tests in week one. First real spot-the-difference in week two. Business checks at weeks four and eight. Some highlights:

- The robot stays under two gigabytes of memory.
- Page counts match, or the run fails.
- A business going closed to open is a "came back", never a "new".
- The industry guesser is checked by two people on fifty samples and must be at least ninety percent right.
- A fully clean record actually exports.
- No Google Maps calls exist anywhere in the code.
- Ten random records can each be fully reconstructed from their receipts in under fifteen minutes.
- The helper finishes a list in under two hours of real work, measured by edit timestamps in the sheet.
- The lead pipeline's login cannot read the photo archive.

Before any code is written, someone spends one hour counting how many GST flips happened in the last week in an existing photo, by business age and state. That replaces the guessed tier A volume with a real number.

**The pre-committed decision.** If by week eight tier B has booked no meetings and tier A has, tier B is switched off in the settings file and the money moves to tier A. It is written down now so nobody has to argue about it later.

## 13. Still to decide

1. Does tier A go straight into GoHighLevel, or wait for a human to approve each one? One-line change either way.
2. How we get onto the Do Not Call list checking service, and how long the account takes to open. We now know the price is a set yearly government fee based on how many numbers we check, and at our size that is only a few hundred dollars a year. So this is no longer the thing that could stop the phone calls. The one part still unknown is whether letting the robot check numbers automatically costs more than doing it by hand.
3. A lawyer must sign off on section 7 before the first message is sent.

## 14. The filing cabinets

For the curious, the spec defines these drawers in the database.

| Drawer | What it holds |
|---|---|
| Snapshots | One photo of the book per week, as a Parquet file |
| abr_events | Every spot-the-difference finding, one row per business per event type per week, never edited |
| qbcc_events | The same for the builder list, keyed on licence number |
| businesses | The current state of every business, updated each week |
| lead_entity | One row per lead. Keyed on its own id, because builder leads may have no ABN |
| contact_record | Each email or phone, encrypted, with a scrambled hash |
| collection_provenance | The receipt for every contact detail |
| spam_act_basis | The four record-level yes-boxes, who assessed them, and when they expire |
| send_eligibility | The fifth box, asserted per send by Part 2 |
| do_not_market | Opt-outs at the business level |
| enrichment | What the lookups found and how many calls they used |
| qbcc_licence | The builder list, one row per licence per snapshot |
| worklist_candidate | Who is queued for the helper, with both scores |
| dnc_wash | Every Do Not Call check and its receipt |
| suppression | The global never-contact list |
| outcomes | What the helper reported back each week |
