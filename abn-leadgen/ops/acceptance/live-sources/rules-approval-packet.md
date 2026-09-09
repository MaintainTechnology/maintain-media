# Recovered trade rules: owner review packet

9 September 2026. Status: **targeting direction approved; production precision review pending**.

The user approved keeping all 30 categories, QLD plus NSW postcodes 2450–2490,
QBCC Categories 1–2 and the 60-business weekly limit in this task. The
[dated approval](targeting-approval-2026-09-09.json) records that exact scope.
It does not approve collection, vendor processing or production release. The
100-business accuracy review and production classifier activation remain pending.

The source `deliverables/abr/extract_new_abns.py` now exists in this checkout. Its
first literal `TRADE_RULES` assignment contains exactly 30 ordered industry labels
and regex strings. An AST reader extracted those literals without executing the
old program. This supersedes the earlier bounded search's missing-file finding;
it does not make the old parser or its single-snapshot lead claims authoritative.

The source SHA-256 is
`b521b03e8c678e1cbbb8ee7c6c60a3d2d606f3b5091e7d7c7ef52f99ecd585b5`.
The exact order, patterns and labels are in
[`config/rules.review.yaml`](../../../config/rules.review.yaml). The associated
[decision record](rules-review-decision.json) binds its SHA-256, source lines,
extraction method, rule IDs and pending approval. `fixture_only: true` keeps this
review input disabled for production; it is a safety flag, not a claim that these
patterns were invented as synthetic examples. No runtime default points to it.

## What the owner is deciding

Review the 30 original trade categories in the YAML and decide whether they fit
Maintain Media. The corpus ranges from plumbing, electrical and construction to
transport, cleaning, security, signage, pools, mining and general maintenance.
Keeping all 30 is now approved as the targeting direction by the user.
Any exclusion, regex change or reorder requires a new version and a recorded reason.

The existing v4 fit proposal remains: QLD or NSW postcodes 2450–2490; QBCC exact
financial Categories 1 and 2 as capacity proxies, with actual revenue unknown;
at most 60 distinct groups weekly and up to 10 oldest eligible groups reserved.
The QBCC pilot does not require these ABR trade rules. ABR expansion still needs
the measured pilot decision in G6.

## Behaviour that differs from the old program

The 30 rule strings and order are unchanged. v4 checks BN names, then MAIN, then
TRD, using sorted unique canonical names within each type. OTN is excluded.
For example, BN names `A Builder` and `Z Plumbing` select Building under v4's
name order; the old join-all-names implementation selected Plumbing because
that pattern came first. Unicode NFKC and whitespace canonicalisation also apply.
These intentional v4 changes have synthetic regression cases; they need review
alongside the recovered patterns. The old regex XML reader and active-date filter
are not imported into the new pipeline.

## Required precision review

1. Obtain a G1-authorised, coherent source snapshot and record its digest. Keep
   identifying samples and source evidence in approved private storage.
2. Copy the [100-slot worksheet](rules-precision-review.template.csv) into that
   private location. It reserves 4 classified examples for each of the first 10
   rules and 3 for each of the remaining 20. Include BN, MAIN and TRD, relevant
   geography and overlap cases across the sample. Use additional examples when
   a rule has too few or ambiguous observations; never fabricate a match.
3. An authorised reviewer independently records the expected actual trade from
   source evidence, observed rule, false-positive decision and evidence reference.
   Unknown industry is unresolved, not a passing result. Sampling intent alone
   does not count as a completed review; there are currently **zero** reviewed rows.
4. Report sample counts and false-positive rates per rule and overall. Above 10%
   false positives blocks the affected rule under R9. With only 3 or 4 samples,
   one failure exceeds that threshold; expand or revise and re-review rather than
   hide it in the overall average. Also test unclassified and misleading-name
   negatives separately; those do not replace the 100 classified samples.
5. Record the owner, date, decision, evidence digest, exact ordered rule IDs,
   applicable mapping version, regression suite digest and blocked rule IDs.
   Only then create an approved production rules artifact and enable the matching
   capability through the normal gates. Editing this packet alone grants nothing.

The private worksheet contains only references in repository copies. Do not commit
business names, ABNs, contact details or collected pages to this review folder.

## Coverage and remaining work

- R9 / FR-009: the exact 30-rule source has been recovered, hashed and preserved
  for review; name priority, first-match precedence and OTN exclusion are tested.
- R40 / FR-040: the earlier missing-input observation is superseded by current
  file evidence without repeating historical volume or revenue claims.
- R41 / FR-041: provenance and behavioural differences are explicit. No active
  rule version, live source cursor or event history was changed.
- Still pending: source/privacy policy decision, 100 real classified-record reviews,
  authentic approved ABR mapping, G1/G2/G6 and production integration evidence.
