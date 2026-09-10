# Prepared ABN dashboard deployment

The production website source passed a local Next.js production build using Node
24.21.0, the same major version as the existing Vercel project. All 50 auth and
bridge tests, seven dashboard rendering tests, and scoped application ESLint
checks passed. No source change followed that build. The new local upload helper
also passed four integrity and exclusion tests.

The Node runtime was downloaded from the official versioned Windows distribution
and its SHA256 was checked against the official release checksum list. This was a
separate local executable; the user's global Node installation was not changed.

The frozen upload contains 72 app source, public asset, and build configuration
files. It excludes environment files, dependencies, build output, the lead engine,
the Obsidian vault, scripts, tests, and acceptance evidence.

- Inventory SHA256: `96bc200bfa70911591fdc7f7a00cf7450c610712d71692c9c5db1918d1a96dff`
- Existing Vercel project: `prj_0jiFRBJLqKpgwyClzI4bl1qn1a12` (`website`)
- Existing team: `team_gYhhisBKAi13MDy31JjETCJK` (`maintain-technology`)
- Project root directory: `website`
- Website function region configuration: `syd1`
- Frozen directory: `C:\Users\dalig\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\MaintainMedia\vercel-releases\3007cc13-f551-46e7-92e4-e3a01de718cb`

The local `.vercel/project.json` in that directory binds the upload to the exact
existing project. Its manifest and files were independently re-verified against
the inventory digest above. `scripts/prepare-production-upload.mjs --verify`
supports repeating this check without contacting any provider.

The deployment operator should set only these non-secret production variables
after verifying the private engine's authenticated API:

```text
ABN_ENGINE_TRANSPORT=remote
ABN_ENGINE_ORIGIN=https://abn-engine.maintainmedia.com.au
ABN_ENGINE_MODE=pilot
```

The dedicated `ABN_ENGINE_ASSERTION_KEY` has a separate secure installation
process. Do not copy it into the upload or browser code. Do not read an environment
file to prepare a release.

Run the installed Vercel CLI from the frozen directory, retaining the exact project
binding and root directory. The deployment command is `deploy --prod --project
prj_0jiFRBJLqKpgwyClzI4bl1qn1a12 --scope maintain-technology --regions syd1 --yes
--cwd <frozen-directory>`. Confirm the current rollback
deployment before publishing. Do not create or relink a different Vercel project.

This record confirms local readiness and a reviewed upload, not a Vercel release.
After deployment, verify the cloud build, custom-domain alias, signed-out private
route rejection, and a real Clerk staff browser session. Live source collection,
vendor installation, retention/backup approvals, and measured pilot results remain
separate evidence; an empty connected dashboard must not imply those are complete.

The first release, `dpl_7uWBC43DakjtS6GA6f945eHRSVXi`, reached READY and passed all
12 public/signed-out HTTP checks. Independent inspection found its dashboard and
API functions deployed to `iad1`, despite the declared `syd1` configuration. This
release did not pass the Australian runtime-region check. The CLI's explicit
`--regions syd1` option is now included in the prepared deployment arguments; a
corrective release must be inspected for actual `lambda.deployedTo`, not merely
the configuration or build location. No business records or source approvals
existed at this checkpoint.

The corrective release `dpl_387fws7PqGeZ5fHhPstMwZWbK5w4` reached READY and is aliased
to `www.maintainmedia.com.au`. All 59 non-middleware function outputs are verified
in `syd1`, including the dashboard, API, sign-in and sign-up. The separate Clerk
`_middleware` component is deployed globally; do not describe the entire request
or authentication path as Australian-only. The new release also passed all 12
public/signed-out GET/HEAD checks. A real signed-in staff browser journey and the
remaining processing-country approvals are still separate. Receipts are in
`acceptance/vercel/deployment-20260911-function-regions.json` and
`acceptance/vercel/dpl_387fws7PqGeZ5fHhPstMwZWbK5w4-http.json`.
