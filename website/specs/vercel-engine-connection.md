# Maintain Technology Vercel and engine connection

User-authorised extension, 10 September 2026. Use the existing Maintain Technology
Vercel team and its `website` project. This supersedes the earlier dashboard
specification's same-host-only transport and no-public-website-deployment boundaries.
It does not supersede source, privacy, vendor or live-engine release gates.

## Requirements for this build

1. Retain the existing project, custom domains, Clerk application and explicit admin
   authority. Configure the canonical admin origin and Sydney website functions.
   Deploy only website application files; exclude credentials, local state, engine
   records and the Obsidian vault. Keep the existing production release recoverable.
2. Add an explicit server-only HTTPS engine transport with a strong credential,
   bounded requests and responses, route allowlisting and no redirect following.
   Browser cookies, bearer credentials and upstream CSRF tokens must not cross into
   the wrong trust boundary. Hosted deployments must not fall back to localhost.
3. Preserve the existing local fixture workflow and require a genuine authenticated
   gateway counterpart for remote fixture verification. This gateway is preparation
   only; it must not bypass guarded pilot/production startup or admit live data.
4. When the engine is not connected, show that state clearly and disable dependent
   actions. Keep retry, setup navigation and sign-out working. Only an actual fixture
   response may display fixture/demo data. Do not manufacture live businesses.
5. Verify authentication denial, rejected transport configurations, credential
   isolation, gateway authorization, build/lint and the deployed public/auth routes.
   Record current evidence and the remaining signed-in, host and live-data checks.

## Confirmed setup inputs

- Vercel team: Maintain Technology (`maintain-technology`), verified Pro plan.
- Existing project: `website`, root `website`, project ID
  `prj_0jiFRBJLqKpgwyClzI4bl1qn1a12`.
- Website: `https://www.maintainmedia.com.au`; domain registered through GoDaddy.
- Google account identified by user: `jeph@quotemax.com.au`; Sheet access unverified.
- Private worklist destination supplied by user:
  `https://docs.google.com/spreadsheets/d/1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58/edit`.
- GHL: Maintain Media, location `xHZFHMOE476t5CxY9vCG`; installation unverified.
- Business contact/approver supplied: Jon Pepper, `jon@maintain.com.au`.
- The user confirms there is no Australian server/cloud account yet.

These destination identifiers are not installation, sharing or approval receipts.

## Rubric recorded before implementation

| Area | Points |
| --- | ---: |
| Correct existing Vercel ownership, configuration and deployment | 25 |
| Clerk/admin authority and secure transport boundaries | 30 |
| Engine counterpart and accurate disconnected/fixture behaviour | 25 |
| Executed verification and repeatable handover | 20 |

A material access or secret-disclosure defect prevents a pass. Score only this
connection/deployment slice, separately from full live ABN readiness. Missing host,
vendor approvals and pilot evidence remain unresolved rather than receiving points.

## Tasks

- [x] V001 Verify and link the existing Maintain Technology project; record current
  release and configure canonical origin, Sydney functions and safe upload scope.
- [x] V002 Build the remote website transport and security regressions.
- [x] V003 Build the matching fixture gateway and denied/permitted contract tests.
- [x] V004 Clarify disconnected dashboard state and preserve dependent-action guards.
- [x] V005 Run local checks, independent review, deploy and verify production routes;
  record score trajectory, limitations and the next AU-host requirements.
- [ ] V006 Install and verify the approved AU host, live engine and full T071 workflow.

V006 remains an external/live obligation and cannot pass from this website release.

Executed evidence: [`../acceptance/vercel/review.md`](../acceptance/vercel/review.md),
deployment and source-verification receipts in the same directory. Completion of
V005 means its bounded checks and limitations are recorded, not that V006 passed.
