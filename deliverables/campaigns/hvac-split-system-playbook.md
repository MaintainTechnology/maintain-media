# Split-System Launch — Team Playbook

**Client:** licensed electrician, residential split-system installation, Brisbane
**Runs:** 6 weeks from kickoff · **Reference doc:** [hvac-split-system-launch.md](hvac-split-system-launch.md)
**Skill:** `.claude/skills/hvac-growth-marketing`

> This is the operating manual. The campaign doc holds the reasoning; this holds the
> instructions. If the two ever disagree, this one is wrong — flag it, don't improvise.

---

## 1. The one-pager — read this if you read nothing else

**What we're doing:** running Google Search ads in one dense pocket of Brisbane's
northside for an electrician who installs split systems at a fixed online price.

**What we're actually selling:** not air conditioning. **We're removing the three-day
quote.** Every competitor makes you book a technician visit, wait, and then get a number.
We give the number in two minutes from two photos.

**The one number that matters:** cost per *completed, paid, installed job*. Not leads.
Not clicks. Not enquiries. If someone reports "we got 40 leads this week" without saying
how many became installs, that's not a report.

**The number we're chasing:** ≤$400 per completed install, at ≥$900 gross profit per
job. Anything above that and we stop and fix the offer, not the ads.

**Budget:** $4,000 over 4 weeks. Google Search only. No Meta until week 5.

**Why now:** Brisbane aircon demand ramps in October and peaks November–January, and ad
costs rise with it. We're buying our lessons cheaply in September so we can scale hard
into summer with a funnel we know works.

---

## 2. What we say — the message house

Everyone who writes an ad, answers a phone, replies to a comment or sends an SMS uses
this. No freelancing. Consistency is the whole point.

### The one sentence

> **Aircon quotes shouldn't take three days.**

### The four claims — every piece of copy makes at least one

| # | Claim | The words |
|---|-------|-----------|
| 1 | **Fixed price** | 3.5 kW split system — $1,999 supplied and installed. |
| 2 | **No home visit** | Answer six questions, upload two photos, see your price. |
| 3 | **Fast** | Installed this week. |
| 4 | **One licensed trade** | The same licensed electrician does the install *and* the wiring. No second trade, no surprise switchboard cost. |

Claim 4 is the moat. Most aircon installers sub out the electrical work — that's where
the surprise costs come from. Nobody else running this offer can say it. **Use it more
than you think you should.**

### Say this / never say this

| Say | Never say |
|-----|-----------|
| "$1,999 for a standard installation" | "$1,999, all inclusive" / "no hidden costs" |
| "You'll see any extra costs on screen before you pay anything" | "There are no extras" |
| "Licensed electrician, install and wiring" | "Fully licensed and certified" *(vague = unsupportable)* |
| "Most Brisbane jobs completed within 7 days" | "Next-day installation" *(we can't guarantee it)* |
| "Upload two photos and get your price" | "Book your free quote" *(that's the old model)* |
| "Standard install — here's exactly what that means" *(link)* | Silence on what standard means |
| "We're not the cheapest — we're the fastest to a real number" | "Cheapest in Brisbane" |

### Words that are banned outright

**Legal risk:** guaranteed · unlimited · no exclusions · fully inclusive · beat any
price · certified *(unless naming the specific certification)*

**Slop:** passionate about comfort · your comfort is our priority · quality workmanship ·
industry-leading · we pride ourselves on · at [company], we believe

**Jargon the customer doesn't care about:** inverter technology · COP rating · our
process · our system · reverse-cycle *(fine in a spec line, never in a headline)*

### The tone

Talk like a tradesman who respects your time, not a marketing department. Short
sentences. Australian spelling. No exclamation marks. If a line sounds like a brochure,
delete it.

---

## 3. Who owns what

| Owner | Owns | Time/week |
|-------|------|-----------|
| **Marketing VA** | Google Ads account, ad copy, negatives, search-term review, weekly scorecard, creative production for Phase 2 | ~6 hrs |
| **Developer** | Landing pages, six-question qualification flow, photo upload, price engine, deposit + date picker, full tracking including offline import | Build weeks −2 to 0, then ~2 hrs |
| **Lead-gen VA** | Every lead that sees a price and doesn't pay. SMS within 2 hrs, call within 24 hrs. Books the job. | ~5 hrs |
| **Client (electrician)** | Compliance docs, standard-install definition, add-on prices, the installs, job photos, asking for reviews | ~2 hrs + delivery |
| **Jon** | Offer economics sign-off, week-2 gate, week-4 gate. Nothing else. | **~4 hrs total, all 6 weeks** |

**If you are stuck for more than 30 minutes, escalate. Don't burn a day being polite.**

---

## 4. Before a single dollar is spent — blocking checklist

Nothing goes live until every box is ticked. A price-led campaign with half-built
tracking optimises toward the wrong thing and you can't tell until you've wasted the
budget.

### Compliance — client, with Jon signing off

- [ ] **ARCtick licence** held, or a named licensed refrigerant handler engaged
      *(an electrical licence does NOT cover refrigerant work — if this is missing, old-unit removal comes out of the offer)*
- [ ] **QLD electrical licence** number, available to display
- [ ] Public liability insurance current
- [ ] Warranty wording matches the actual manufacturer + workmanship terms
- [ ] Any review count or install count we publish is real and evidenced

### The offer — client + Jon

- [ ] **"Standard installation" written in plain English and published as a linked page**
- [ ] Add-on price list finalised and published — pipe run, height access, core drilling,
      new circuit, switchboard upgrade, old-unit removal, condensate pump, extra heads
- [ ] Decision made: are we attaching add-ons and multi-head at price presentation?
      **This is the campaign's make-or-break. See §9.**

### Build — developer

- [ ] Four landing pages live, one per ad group
- [ ] Six-question flow + two-photo upload + on-screen itemised price
- [ ] Deposit payment + install date picker
- [ ] Events firing: `qualification_started`, `photos_uploaded`, `price_presented`,
      `deposit_started`, `deposit_paid`
- [ ] **`deposit_paid` set as the Google Ads primary conversion**
- [ ] **Offline conversion import wired** for `install_completed` with the real invoice
      total — this is what closes the loop on add-on revenue
- [ ] Call tracking on the header phone number
- [ ] "How did you hear about us?" mandatory at deposit

### Account — marketing VA

- [ ] Four ad groups, phrase + exact match only
- [ ] Negatives loaded *(full list in the campaign doc §CHANNEL)*
- [ ] Geography set to the northside cluster only — **not all of Brisbane**
- [ ] Maximise Conversions bidding, optimising to `deposit_paid`
- [ ] Daily budget caps set per ad group

---

## 5. The six-week runbook

### Weeks −2 to 0 — build

Developer builds. Client supplies compliance docs, standard-install definition and add-on
prices. Marketing VA builds the account but does **not** enable it. Jon signs off the
offer economics.

**Gate:** every box in §4 ticked. No exceptions, no "we'll fix tracking next week".

### Week 1 — go live, watch, don't touch

Ads on Monday. **Change nothing for seven days.** The single most common way to wreck a
new account is optimising on three days of noise.

Marketing VA, daily 20 minutes: check spend is pacing, check ads are actually serving,
check conversions are firing. That's it.

Lead-gen VA: work every lead from day one. SMS within 2 hours of a price being seen,
call within 24.

### Week 2 — first real read, and the CPC gate

Marketing VA: first full search-term report. Add negatives. Nothing else.

**GATE — Jon, 30 minutes, end of week 2:**

| Actual CPC | Action |
|---|---|
| Under $14 | Continue as planned |
| $14–$18 | Tighten geography and keywords, continue |
| **$18+** | **Pause.** The plan needs reworking before we spend the back half. |

### Weeks 3–4 — optimise the funnel, not the bids

Now there's enough data to see *where* people drop. Fix the stage that's actually broken:

| Symptom | The problem is | Fix |
|---|---|---|
| Clicks fine, few start the form | Landing page / message match | Make the hero match the ad wording exactly |
| Start the form, don't upload photos | Flow friction | Fewer taps, clearer instruction, show an example photo |
| Upload photos, don't reach a price | Technical | Developer — this is a bug, escalate same day |
| See the price, don't pay a deposit | Price or trust | Lead-gen VA follow-up, and review the trust block |

Client: photograph every completed job. Ask every customer for a review on the day.
These are Phase 2's creative and we can't fake them.

### Week 4 — the gate that decides everything

**GATE — Jon, 1 hour.** All four must clear:

1. ≥8 completed installations from $4,000 *(CAC ≤$500)*
2. **Blended gross profit ≥$900 per install**
3. Cost per price-presented ≤$110
4. Callback / rework ≤10%

**All four clear** → Phase 2. Raise Search spend, add Meta prospecting and retargeting.

**#2 fails** → **stop.** The offer is the problem. More spend against thin margin just
builds a bigger fragile business. Fix the attach rate first.

**#1 or #3 fails but #2 clears** → the funnel is the problem, not the economics.
Diagnose the specific stage from the table above and re-measure.

### Weeks 5–6 — Phase 2

Meta prospecting and retargeting go live using real installer photography and real
reviews. Run CTA Test 1 *(campaign doc §NEXT TEST)*. Nothing else changes at the same
time.

---

## 6. The daily loop

### Marketing VA — 20 minutes, every weekday

1. Spend pacing to plan?
2. Any ad group with zero impressions? *(usually a disapproval — fix same day)*
3. Conversions firing?
4. Anything obviously wrong in yesterday's search terms?

**Do not change bids, budgets or copy outside the weekly review.** Log what you noticed;
act on Monday.

### Lead-gen VA — the highest-value job on this campaign

About 70% of people who see a price won't pay a deposit on the spot. Recovering even a
tenth of them takes CAC from ~$389 to ~$292 — a 25% improvement from follow-up alone.
That's worth more than any bid change we could make.

| When | Action |
|---|---|
| **Within 2 hours** of `price_presented` with no deposit | SMS |
| **Within 24 hours** | Phone call |
| Day 3 | Second call, different time of day |
| Day 7 | Final SMS, then stop |

**SMS template:**

> Hi [name], [installer] here — you got a price of $[X] for the [room] earlier today.
> Happy to answer anything before you book. Any questions?

**Call opener:**

> Hi [name], it's [X] from [company]. You had a look at a price for the [room] — I'm not
> chasing you, just checking whether anything didn't make sense. What were you thinking?

Then shut up and listen. The objection they give you is data — log it. Three people
giving the same objection is a landing-page fix worth more than the three jobs.

---

## 7. Monday scorecard — 15 minutes, whole team

Marketing VA fills this in before the call. Same fifteen lines every week, no
narrative-only updates.

```
Ad spend                  Revenue
Leads                     ASP
Qualified leads           Gross profit
Deposits                  Gross margin
Completed installs        Contribution after marketing
CAC                       Google conversion rate
Landing-page conversion   Reviews collected
Referral installs
```

Then three sentences — **no more than three**:

1. **What happened?**
2. **Why?**
3. **What changes this week?**

If the honest answer to #3 is "nothing", say nothing and change nothing. A week with no
changes is a legitimate outcome. Fiddling to look busy is how accounts get wrecked.

---

## 8. Stop rules — anyone can call these, no permission needed

| Trigger | Action |
|---|---|
| An ad makes a claim not on the compliance checklist | **Pause that ad immediately.** Tell Jon. |
| A customer says the price changed after they committed | **Pause all spend.** This is the offer's credibility and it's not recoverable. |
| Conversions stop firing for more than 24 hrs | **Pause spend.** We're flying blind. Developer, same day. |
| Install capacity is booked out beyond 2 weeks | **Cut budget 50%.** Selling jobs we can't deliver on time destroys the "installed this week" claim. |
| CPC over $18 in week 2 | Pause and re-plan. |
| Callback / rework over 10% | Pause scaling. Delivery problem, not a marketing problem. |

**Pausing spend is always the safe move. Nobody will ever be in trouble for pausing.**

---

## 9. The one decision that decides whether this works

Jon needs to make this call before build starts.

The $1,999 single head produces about $567 gross profit. Against a realistic $389 CAC
that leaves $178 per job — technically profitable, practically fragile. One callback or
one site that turns out non-standard wipes out a job's entire contribution.

**The fix is not cheaper ads. It's more profit per job.** Two changes:

1. **Attach priced add-ons at the moment the price appears on screen** — especially the
   dedicated circuit and switchboard work, which is exactly what an electrician owns and
   what other installers have to sub out.
2. **Ask about other rooms in the qualification form.** Someone air-conditioning a
   bedroom in September is doing the living room by December. Question 6 exists for this.

At a blended ~$2,900 job and ~$1,050 gross profit, the same $389 CAC yields $661
contribution and 2.7× marketing efficiency. That's a business that can scale into summer.

**Everything in this playbook assumes that decision is yes.**

---

## 10. Common questions — for whoever is on the phone

**"Is $1,999 really the total?"**
> For a standard install, yes. If your photos show something non-standard — a longer pipe
> run, double brick, a switchboard that needs work — you'll see that priced on screen
> before you pay anything. No surprises after we're on site.

**"Why won't you come out and quote?"**
> Because it takes three days and you end up paying for it in the price. Two photos tells
> us what a site visit tells us, and you get the number now.

**"Can you beat [competitor]'s price?"**
> We don't discount. What you should compare is what's included — we're electricians, so
> the wiring and any switchboard work is in our price. Most installers sub that out and
> it lands as an extra later.

**"Do I need a new circuit?"**
> Your photos will tell us. If you do, you'll see exactly what it costs before you commit.

**"Can you do it this week?"**
> Let me check the calendar. *(Check. Never promise a date the crew can't hit — "installed
> this week" is the whole campaign and one broken promise costs more than one job.)*

**"What brand is it?"**
> *(Name it. State the actual warranty terms. Never inflate them.)*

---

## 11. Kickoff message — send this to the team

> **Split-system launch — starting [date]**
>
> We're running paid search for [client], a licensed electrician doing split-system
> installs on Brisbane's northside. Six weeks, $4,000, Google only to start.
>
> **What we're selling:** not air conditioning — we're removing the three-day quote.
> Everyone else makes you book a technician and wait. We give a fixed price in two
> minutes from two photos, installed this week, by one licensed trade who does the wiring
> too. That last bit is our edge — nobody else offering this price can say it.
>
> **The only number that counts** is cost per completed, paid, installed job. Not leads,
> not clicks. Target is ≤$400. If anyone reports lead volume without installs, I'll ask
> the same question every time.
>
> **Your bit:**
> · [Developer] — landing pages, the six-question flow, and full tracking including
>   offline import. Nothing goes live until tracking is complete.
> · [Marketing VA] — the ads account and the Monday scorecard. Week 1 you change nothing;
>   we let it run.
> · [Lead-gen VA] — every person who sees a price and doesn't book. SMS in 2 hours, call
>   in 24. This is the highest-value job on the campaign — good follow-up is worth about
>   25% off our cost per job, more than any ad tweak.
> · [Client] — compliance docs, the standard-install definition, add-on prices, and a
>   photo of every finished job plus a review ask on the day.
>
> **The playbook is the source of truth** — message house, scripts, stop rules, all of it:
> [link]. Read §2 before you write anything customer-facing. If you're stuck more than
> 30 minutes, escalate; don't lose a day.
>
> Gates are end of week 2 (ad costs) and end of week 4 (do we scale). Anyone can pause
> spend at any time for any reason on the stop-rule list — nobody gets in trouble for
> pausing.
