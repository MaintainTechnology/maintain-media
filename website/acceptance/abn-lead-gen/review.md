# Next.js ABN Lead Gen acceptance — 9 September 2026

Scope: [website migration specification](../../specs/abn-lead-gen-dashboard.md). This is a new authenticated React dashboard at `/abn-lead-gen/dashboard`, backed by the existing fixture engine. Prior HTML acceptance is historical context, not proof of this migration.

Disposition: **PASS — R1–R8 satisfied for the local fixture dashboard.** The final independent review found no remaining material authorization or workflow defect.

## Coverage

| Requirement | Implementation and verification |
|---|---|
| R1: Native website components and design | React views and state hook in `src/components/abn-lead-gen/`; scoped CSS, existing local fonts/logo, native admin navigation. `SiteShell` preserves public pages and omits marketing chrome/Lenis from the workspace. |
| R2: Dedicated individual admin access | Server page checks, every API family checks, scrypt password hashes, expiring signed HttpOnly sessions, current enabled admin registry, login throttling, exact Origin and session CSRF checks. Ignored local provisioning CLI supports multiple accounts, reset, disable and enable. |
| R3: Actual lead data and review | Existing database projection, truthful missing ABNs, combined search/source/tier filters, selected detail, reasons and fixture/outreach labels. |
| R4: Real run workflow | Server bridge invokes existing run admission; request IDs, source matching, confirmed receipt checks, shared overlap protection and active/terminal polling. |
| R5: Configuration and recovery | Persisted defaults, effective cap, validated A$0–150 values, dirty-state protection, coalesced polling, mutation generation checks, explicit error/retry states and expired-session clearing. |
| R6: Protected downloads | Allowlisted report routes retain engine integrity/authority/contact masking; website HTML/Markdown links point to authenticated CSV routes; browser download and popup fallback are supported. |
| R7: Server-only engine access | Fixed validated loopback origin, exact endpoint/method allowlist, bounded JSON, upstream timeouts, no forwarded browser credentials, no exposed upstream CSRF, private/no-store/noindex responses and restrictive report CSP. |
| R8: Local operation and verification | Website launcher and account CLI documented in README. Engine is co-located; fixture-only readiness remains explicit. Final test/build/browser receipts recorded below. |

## Review findings resolved

1. Uppercase UUID report requests did not rewrite the engine's lowercase CSV link. Canonicalise the UUID before link replacement; regression covers HTML and Markdown.
2. A rejected sign-out marked settings drafts clean. Retain drafts and their dirty state until sign-out succeeds; failed sign-out remains visible across polling.
3. A malformed or mismatched successful run response could clear the retry request ID. Validate receipt IDs, source and state and match the exact submitted identity before confirming admission.
4. An ambiguous POST retained its request ID even after a dashboard snapshot confirmed that job. Clear it only when a matching validated active/latest receipt confirms admission, allowing the next intentional run to get a new ID.
5. Next.js normalises its internal request URL to `localhost`, while the browser may use `127.0.0.1`. Legitimate sign-in was incorrectly rejected. Local origin validation now uses a strictly parsed loopback Host plus a loopback internal URL; forwarded headers cannot establish authority. Hosted HTTPS requires a canonical configured origin.
6. The public header's pre-existing effect synchronously reset menu state on navigation and failed the current React lint rule. Keying the header by pathname resets its menu on route changes without the effect; the public site retains the same behavior.
7. The public site's stat counter rendered different initial text under reduced motion, causing hydration recovery during a navigation check. Its initial server/client text now matches, and its effect applies the motion preference.
8. A malformed successful sign-out response could falsely confirm logout. Sign-out now requires parsed `{ok:true}` before clearing data/drafts. HTTP 503, malformed JSON and unexpected HTML preserve edits and show a persistent recovery message.

## Verification

- [Final authentication and bridge JUnit receipt](unit-tests.xml): **24 individual test cases passed**, zero failures, errors or skips. This includes origin-normalisation/reverse-proxy regressions, token expiry/tampering/role revocation, multiple-account CLI operations and report/body/URL boundaries. Node's aggregate test count additionally counts the parent authentication group.
- Final **production build passed after all review fixes**, including TypeScript and all 12 static-generation entries. Dashboard, sign-in and API routes are dynamic; public marketing routes build successfully. Compilation took 14.4 seconds and TypeScript took 2.9 minutes on the shared Windows host.
- Actual website stop/status/start drill passed on port 3001. It stopped only the verified owned website; the same engine process and its database remained available.
- Local account configuration and the generated access file are ignored by Git; passwords were not printed in tool output or committed.
- [Full browser receipt](2026-09-09T07-08-25-900Z/result.json): **24 checks passed**, including **12 isolated failure-recovery probes**, eight anonymous API denial checks, successful/rejected admin sign-in, all normal controls and all three actual source runs. Each double-click run test sent one admission request and completed. All three report formats and nested CSV links worked; no raw contact endpoints or upstream token were exposed.
- [Final sign-out regression](2026-09-09T07-12-39-529Z/result.json): the failed sign-out probe additionally covers HTTP 503, malformed HTTP 200 JSON and HTTP 200 HTML after the final fix; normal sign-out still denies re-entry. No engine runs were started by this focused check. Original preferences were verified/restored. Both browser receipts record zero uncaught errors.
- [Public-site navigation receipt](site-shell.json): mobile menu closes after navigation; Services/About/Contact retain their public header/footer and fit 390px; sign-in uses the separate admin chrome. Zero uncaught browser errors.
- Screenshots in the full browser receipt directory cover leads, runs and setup at **1440, 820, 390 and 360px**. Root visually reviewed the desktop lead workspace and phone run cards. The user-facing in-app browser is open on the new sign-in route.
- Final global ESLint passed. The independent reviewer accepted all R1–R8 after the final test and build results. [Verification summary](verification.json).

The saved source/budget preferences are restored to the existing values, **both sources and A$100**. The latest actual fixture run is complete. The private initial account is ready and its access file remains Git-ignored.

## Self-assessment

Scores are retrospective assessments of the review stages using the rubric written before this migration was built; a material defect fails the gate regardless of score.

| Review stage | Score | Result |
|---|---:|---|
| First integrated build | 82/100 | Sign-in Origin mismatch and asynchronous confirmation/draft issues required fixes. |
| Normal workflows and initial resilience checks | 95/100 | Real runs, settings and reports passed; malformed sign-out confirmation remained. |
| After final sign-out fix and targeted regression | 97/100 | All identified control failures resolved. |
| Final independent review, lint and production build | 97/100 | No further material findings; score unchanged. |

| Rubric | Score | Remaining deduction |
|---|---:|---|
| Complete workflow parity | 30/30 | None within the requested fixture workflows. |
| Admin authorization and data boundaries | 24/25 | Throttling and session operations are designed for one Node process; multi-instance operations need shared infrastructure. |
| Failure recovery and operational clarity | 19/20 | Provisioned-machine launcher/recovery is verified; a fresh-machine installation has not been certified. |
| Native design, responsive layout and accessibility | 14/15 | Chromium, keyboard and reduced-motion checks passed; no screen-reader or Safari/Firefox certification. |
| Tests, build and handover | 10/10 | Executed checks, provisioning, launcher and evidence are recorded. |

## Operational boundaries

The current runnable configuration is this Windows computer with Next.js and Python on the same host. Remote/serverless hosting does not reach its loopback engine. Live ABN discovery, vendor connections and outreach remain separate release gates. This interface does not close those gates.

Browser evidence covers Chromium, keyboard navigation, reduced motion and four responsive widths; it is not Safari/Firefox or screen-reader certification. Login throttling is per Node process. Sign-out deletes the browser cookie; copied stateless tokens are invalidated by expiry, password reset, account removal/disable or role changes, rather than a shared individual-session revocation store. These constraints are documented in the README.
