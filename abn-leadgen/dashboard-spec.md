# Local lead dashboard

User-authorised extension, 9 September 2026. This adds an internal operator dashboard to the existing engine; the v4 engine specification and production gates still apply. The earlier exclusion of a dashboard is superseded only for this local fixture interface.

## Intended use

Open one local page to inspect the latest stored businesses and ABNs, understand why a business needs review, start a fixture run, download its private report, and save supported defaults for future runs. Source observations must never be described as registration dates or live leads. No contact or approval authority is granted by viewing a lead.

## Requirements

1. Serve the dashboard at loopback port 8767, including the previous `/report.html` entry point. Provide a repeatable Windows start/status/stop helper and a launcher.
2. Populate lead names, ABNs where recorded, source, score, tier, observation time, and restrictions from the engine. Missing facts remain unknown. Search and source/tier filters work together; a lead opens a detailed review panel.
3. Show recent runs and their real states. A run control invokes the existing fixture pipeline with saved defaults, prevents overlapping dashboard submissions and shows pending, completion, and failure states. Refresh loads current database state.
4. Link each available report/CSV to the correct run, enforce current artifact authority, and explain unavailable or stale artifacts. Never expose arbitrary storage paths.
5. Persist source preference and a validated monthly enrichment usage ceiling from A$0 to A$150. Settings apply to subsequent runs. No control claims to connect or enable unimplemented live providers.
6. Setup shows the actual fixture database, source and integration readiness, with clear steps for outstanding live inputs. Keep demo mode and disabled outreach apparent.
7. Match the repository DESIGN.md: real Maintain Media logo, local Albert Sans, deep teal surfaces and purple controls. Desktop has a list/detail workspace; narrow layouts stack without losing controls. Keyboard, focus, reduced motion, loading, empty, error and saved states are required.
8. Allow only local fixture access. Block hostile hosts, cross-site writes and missing CSRF tokens; never reveal credentials, raw contact endpoints or arbitrary files.

## Review rubric (written before implementation)

| Area | Points | Evidence |
|---|---:|---|
| Useful complete workflows | 30 | Browser run, filters/detail, settings save/reload, report downloads, setup |
| Data truth and access boundaries | 25 | Real DB projections, demo labels, validated settings, CSRF/host/artifact tests |
| Design and accessibility | 20 | Brand assets, desktop/mobile screenshots, keyboard and overflow checks |
| Reliable operation | 15 | Start/status/restart, duplicate jobs, failures and recovery |
| Maintainability and handover | 10 | Focused tests, lint/types, documented launch and limitations |

Critical failing controls or unsafe access prevent a pass regardless of total score. Report the evidence-supported score and remaining limitations; prior engine-wide acceptance receipts are not receipts for this extension.
