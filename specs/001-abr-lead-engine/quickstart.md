# Build validation quickstart — specification v4.0

The authorised application is in `abn-leadgen/`. The [README](../../abn-leadgen/README.md) is the executed command reference and [implementation status](implementation-status.md) separates local evidence from pending release requirements. Do not substitute live ABR records, websites, API credentials or CRM locations for synthetic fixtures.

## Prerequisites

Python3.12.12; uv; container runtime or isolated PostgreSQL16 test service; loopback network access. Work in `abn-leadgen/`. `config/fixture.yaml`, `ops/compose.test.yaml`, synthetic fixtures and `uv.lock` are present. Each integration test owns an isolated schema. Fixture mode rejects external network transport and live credentials. It runs without paid accounts or the production trade-rule corpus.

Commands (Windows, provisioned local PostgreSQL16 archive; Docker alternative in README):

```powershell
Set-Location C:\Users\dalig\Desktop\MaintainTech\MaintainOrg\maintain-media\abn-leadgen
uv sync --frozen
uv run python ops/local_postgres.py start
uv run abr-engine validate-config --config config/fixture.yaml --mode fixture --json
uv run abr-engine db migrate --config config/fixture.yaml --mode fixture --json
uv run python ops/verify.py
uv run abr-engine run --source all --config config/fixture.yaml --mode fixture --json
```

The last command runs the fixture demonstration once dependencies/database are ready. Outputs are a synthetic worklist of at most60 distinct business groups, private HTML/Markdown report and immutable manifest with source UUIDs/digests and zero live API calls. CRM has a separate approval and mock-drain command. `ops/verify.py` writes immutable command logs, JUnit results and a source-tree hash; the shared parent Git commit does not identify untracked application files.

## Required scenarios

| Scenario | Fixture / action | Expected outcome |
|---|---|---|
| QBCC first run | UTF16LE fixture with class duplicates, no-ABN licence, two licences sharing ABN and malformed address | Classes collapse deterministically; missing ABN retained; shared ABN yields one business group; unknown geography held; no fixed historical count assertion. |
| Coherent publications | ABR baseline, changed next publication, same-date corrected publication, mixed parts | Baseline zero events; changes exactly once; corrected publication has new UUID; mixed parts hold without cursor move. |
| Content identity projection | Recompress unchanged XML under the same mapped member labels, change only retrieval/download metadata, then change actual member bytes | Recompression/retrieval metadata do not change snapshot identity; member-byte correction does. Manifest still records distinct download integrity evidence. |
| Secure parser | Namespaced/escaped/empty-GST XML; DTD/oversized ZIP/duplicate ABN/count mismatch | Valid formats yield correct fields; unsafe/invalid inputs quarantine and preserve baseline. |
| Historical content recurrence | A1 baseline, B2 changed, newly evidenced A3 repeating A1 content, A3 retry | A3 has fresh occurrence UUID and B-to-A events once; verified content artifact may be reused; retry adds none; subsequent identical-to-current poll no-op; cached A1 without fresh coherence evidence holds. |
| Erasure then key rotation | Suppress, erase plaintext profile/aliases, rotate key, ingest original identifier | Retained lookup-only old key still matches and blocks; premature retirement and HMAC-of-old-HMAC migration rejected; compromised lookup key freezes affected action paths. |
| Crash recovery | Inject failure after upload, before DB commit, after commit, and mid-output | Retry reuses artifacts/events; cursor only advances atomically; output resumes from durable state. |
| Fair queue | 200 eligible groups and tie scores, then next weeks | Exactly60 max, up to10 oldest first, remaining140 carried; eight-week aged work deferred; one total order independent of input order. |
| Allowed and blocked email | Reviewed inferred basis or express consent plus deliverable current evidence; then unknown/expired/wrong-contact provenance | Allowed candidate appears; blocked contact masked; database rejects wrong-contact/channel links, preventing empty-output false confidence. |
| Phone receipt | Valid national/+61 forms; old clear then newer listed/error; future/mismatched receipt | Normalize once; latest observation controls; stale/future/bad receipt cannot allow action. |
| Immediate opt-out | Export candidate, then API suppression, then consume old intent | Receipt only after commit; old intent denied; alias/future endpoint blocked; simulated propagation outage does not reopen local permission. |
| Dispatch race | Consume-first and suppression-first orderings under concurrent test transactions | Suppression-first denies; consumed external in-flight action logged distinctly with cancellation attempt; no fictitious recall guarantee. |
| Channel-specific relevance | Sender submits forged relevance flag; reviewer supplies current exact email assessment; phone has fresh wash/script policy but no email basis | Forged flag rejected; current email assessment may pass only with all other checks; eligible phone can pass without invented email consent/relevance rows. |
| SSRF and identity | Similar business search hit, private IPv4/IPv6, DNS-rebinding redirect, wildcard robots block | No contact crawl without identity proof; all unsafe destinations blocked; page/request ceilings include retries/redirects. |
| Spend | Zero cap, concurrent near-cap requests, uncertain timeout, month boundary | Never over-reserve; uncertain billing retained; reservation month unchanged; remaining candidates resumable. |
| Sheets | Reorder rows, duplicate edit event, stale version, opt-out with stale version | Correct immutable row targeted; retry idempotent; ordinary stale edit409; opt-out commits even if outcome version conflicts. |
| CRM | Approval absent, shared remote endpoint, timeout after create,429, partial batch | No unapproved push; ambiguity held; reconcile before retry/create; successful intents not replayed. |
| Retention restore | Backup predating suppression/deletion, expired snapshots and rotated token keys | Restore quarantined; replay latest tombstones and reconcile keys before egress; snapshot age forces declared rebaseline. |
| Erased identity matching | Delete active encrypted ABN/licence aliases and profile, then reimport matching source identifier | No plaintext source key remains in restriction ledger/logs; HMAC alias resolves retained opaque group UUID and blocks new enrichment without recreating deleted profile. |

## Capacity and live evidence are separate

Run the `benchmark` command only on a designated test machine with preflight space; inspect `--help` and the README for output options. Record disk, WAL, spill, RSS, output-bearing diff time, full elapsed time and hardware. A60-second diff is a stretch target, <=6h full run and <=2GiB per ingest/diff worker are targets; the result determines capacity, not the host advertisement. Local20.5M synthetic diff evidence is recorded in implementation status; it does not certify an AU production host or the complete source download/parser cycle.

After G1–G5 applicable approvals, perform separately labelled source smoke and vendor sandbox tests. Never run real outreach as a test of this guide. Four measured QBCC pilot weeks and owner decision G6 precede live ABR expansion. G7 requires the full applicable acceptance evidence, security/restore/handover drills and exact release revision. Unresolved rule recovery keeps production classification off even if synthetic tests pass.

## Human handover check

A second developer follows only the implemented README and this guide, demonstrates a fixture run plus interrupted-run recovery, and records results. An operator demonstrates a blocked record, current licence/wash review, identity/consent review, acknowledged opt-out and conflict repair. Measure complete worked time (calls, research and administration) in addition to Sheets edit-gap instrumentation. The owner reviews denominators and booked/held meetings separately at four and eight weeks.
