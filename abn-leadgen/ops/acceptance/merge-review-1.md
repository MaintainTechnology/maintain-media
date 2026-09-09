# Independent merge review — 8 September 2026

Scope: canonical R13/R25/R26 and precision transaction boundaries; reviewed `qualify/identity.py`, service canonical/family/source lookup/suppression, migration014 and existing merge tests. Findings recorded before root fixes.

1. **P1: canonical identity/licence lookup excludes preserved source aliases.** After A → B, `create_lead` correctly maps A's alias to B, but its `lead_source_link` remains attached to A and the unique alias key prevents inserting another link on B. `Service.identity` and `Service.licence` query only B's group ID, so a fresh review using the consolidated business's A licence fails with `IDENTIFIER_NOT_THIS_LEAD`/`LICENCE_NOT_THIS_LEAD`. Query source links across the canonical family without rewriting provenance or historical foreign keys. Audit the CRM ABN projection for the same exact-group assumption. Independent regression covers both merge directions.

2. **P2: blank and whitespace-equivalent evidence counts as corroboration.** The API accepts `list[str]`, including empty strings. `len(set(evidence)) >= 2` accepts `['', ' ']` and `['same', ' same ']`, allowing a reviewed merge without two real distinct references. Require every reference to be a nonempty string after trimming and compare normalised references. Independent tests preserve both negative controls.

Further review: the independent suite checks source-member erasure, aliases and future endpoint suppression in both directions; latest-ledger merge-edge replay into pre-merge database state without reopening outbound; pending CRM invalidation on both members; and rejection of inflight/uncertain remote work without graph changes. This is actual isolated PostgreSQL evidence, not a physical backup restore or live provider proof.

## Fix review and evidence

Root changed canonical-family identity/licence source lookup and normalised merge corroboration references. Both initially failing findings now pass. Reviewer additionally reproduced and fixed retention replay accepting conflicting pre-existing merge edges; conflicting/cyclic graphs are rejected before replay mutations and quarantine remains intact. Final combined independent merge/retention run at this stage: **40 passed in 105.51s**, including all ten merge review cases and thirty retention cases. The later native backup drill is separately recorded; no live release certification is inferred.
