# Vercel connection build review

Scope: `website/specs/vercel-engine-connection.md`, 10 September 2026.
This scores the website deployment and secure connection preparation only.
It is not a full-spec/live ABN release score.

## First completed-build score: 88/100

| Rubric area | Score | Remaining weakness |
| --- | ---: | --- |
| Correct Vercel ownership/configuration/deployment |25/25| Existing Maintain Technology project and Pro team verified; candidate built and promoted; Sydney functions observed. |
| Clerk/admin and secure transport |28/30| Unit denial/role/session checks pass; real signed-in staff workflow still awaits user completion. |
| Counterpart and disconnected/fixture behaviour |20/25| Actual local gateway boundary and rendered states pass; no provisioned AU TLS gateway exists. |
| Verification and repeatable handover |15/20| Checks pass, but the receipt still needs exact deployed-source matching and consolidated release/rollback evidence. |

The top fixable weakness is evidence/handover completeness. Capture the uploaded
source hashes from the actual Vercel deployment, compare them with the current
application files, and bind the test/smoke receipts to that exact deployment.
Keep the passing access and fixture boundaries. External signed-in and public
gateway observations cannot be replaced by another unit test or a higher score.

## Build/review fixes already made

- Added the missing production canonical admin origin. The public site used Clerk
  already, but authenticated mutations need this exact origin.
- Added explicit HTTPS service transport; Vercel cannot fall back to its own loopback.
- Independent review caught service 401 being treated as a Clerk expiry, and a
  mutation preflight that needed explicit fixture/outreach validation. Both were
  fixed and regression-tested before deployment.
- Disabled data-dependent UI handlers as well as visible controls on disconnect;
  preserved retry, navigation, loaded fixture labels and Clerk sign-out.
- Restricted deployment inputs; the final dry run excluded local/credential data
  and empty internal-state directories. Only 73 website files were uploaded.

## Executed checks

- 29 authentication tests passed.
- 15 website bridge tests passed after the security fixes.
- 4 actual-component rendering checks passed with explicit synthetic doubles.
- 40 Python gateway tests passed against the real inner HTTP boundary with synthetic
  business services; Ruff and mypy passed for the new gateway.
- Whole-website ESLint passed. Local Next production build/typecheck passed.
- Vercel Linux production build/typecheck passed; deployment Ready and promoted.
- 17 deployed HTTP checks passed after promotion: marketing/auth pages, protected
  page redirects, and denied data/report/settings/run requests.
- Independent cross-review found no further actionable transport/gateway defects.

Warnings: Node's direct TypeScript tests emit an existing module-type warning;
Python's test client emits two dependency deprecation warnings. An initial combined
Python invocation named a nonexistent test file and ran no tests; the corrected
40-test gateway invocation passed. These are not live-data test receipts.

## Remaining live obligations

No AU server exists yet; no public gateway/TLS integration was installed. Current
remote transport still implements the fixture dashboard contract. T071 additionally
needs accepted real-source promotion, current licence/identity review, live worklists,
actual-editor permissions, Sheets/GHL installation and suppression/CRM delivery.
Source/privacy/vendor approvals, classifier accuracy, backups/restore and the
measured pilot remain distinct release obligations. Production collection and
outreach were not activated by this website deployment.

## Final review: 92/100 for this deployment/connection slice

Score trajectory: **88 → 91 → 92 → 92**.

- 88: completed build and deployment, with evidence/handover gaps listed above.
- 91: verified all 73 actual deployed source hashes against local files, recorded
  the current and previous deployment IDs, and consolidated production HTTP and
  browser-form observations. All 73 hashes matched; no forbidden files were present.
- 92: the user completed sign-in and identified `jeph@quotemax.com.au` for admin
  access. The exact verified production Clerk account received `public_metadata.role`
  `admin` through the merge endpoint. Independent readback verified the stored role.
  The user then confirmed the dashboard opens. No session was impersonated.
- 92: final requirement review found no further fixable defect in this slice. The
  remaining deductions depend on host and external/manual observations below.

Final rubric: deployment 25/25; access/transport 29/30; counterpart/state 20/25;
verification/handover 18/20. Weakest remaining parts:

- **5 points:** the remote receiver has local contract evidence but no provisioned
  public AU TLS endpoint or real Vercel-to-engine integration observation.
- **2 points:** another operator has not repeated the complete new remote handover;
  current UI rendering checks are narrower than full browser/mobile workflow testing.
- **1 point:** real sign-out/session-switch behaviour was not observed this turn.
  The account's successful entry is user-confirmed; signed-out denial is automated.

No score increase can honestly replace those observations. Full live ABN acceptance
is still incomplete and was not rescored as 92/100.

## Release and recovery

Current: `dpl_79jQ4GMb5gyUvXEwFq28WMUAb7Fp`,
`https://website-f8pfn7ufd-maintain-technology.vercel.app`, promoted onto the existing
custom domains. Vercel's exact production target was read back after promotion.
Functions were observed in `syd1`; the build ran in `iad1`. The region statement is
about functions, not all processing locations or vendor residency approval.

Previous: `dpl_5tVHBUQ6WHRS8Zzn3BJrwG9osqAV`,
`https://website-8lak6boop-maintain-technology.vercel.app`.
If recovery is required, use Vercel's rollback to that exact previous deployment,
then repeat the production smoke. No rollback was executed.

Receipts:

- `deployment.json`: owner, project, canonical origin, current/prior release, region.
- `deployment-source-verification.json`: actual uploaded source hashes matched to
  local content, based on Git revision `da6850035fce191c6eba3a6e446168e00ee4b047`
  plus the task's uncommitted changes. A deployment is not a Git push.
- `upload-manifest.json`: earlier safe-upload dry run; the post-deployment source
  verification is authoritative for final content (README changed after the dry run).
- `production-http.json`: all 17 post-promotion public and signed-out checks passed.
- `admin-access.json`: exact user-selected account, verified email, role readback
  and separately labelled user confirmation.

Browser observations after release: production sign-in displayed Clerk email and
Continue controls; sign-up displayed email, password and Continue controls.
No signup was submitted by the agent. The user's own sign-in and dashboard-entry
confirmations are distinct from these agent-observed form checks.
