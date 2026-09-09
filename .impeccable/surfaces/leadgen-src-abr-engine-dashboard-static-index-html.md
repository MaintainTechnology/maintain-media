---
version: 1
slug: "leadgen-src-abr-engine-dashboard-static-index-html"
primary_target: "abn-leadgen/src/abr_engine/dashboard/static/index.html"
related_targets: ["abn-leadgen/src/abr_engine/dashboard/static/dashboard.css","abn-leadgen/src/abr_engine/dashboard/static/dashboard.js"]
---

Scope: the local ABN Lead Engine dashboard at `/`, with `/report.html` as an existing entry point and views for latest leads, run history, and setup/settings. Visitor mode: Operate.

Audience and job: an internal operator using synthetic businesses on this computer. Inspect the latest stored leads and their restrictions, run the fixture pipeline, open the correct run's report or CSV, and save supported defaults for a subsequent run.

Composition: a working lead review desk. Compact navigation and a task heading lead into a summary strip, combined name/ABN search and source/tier filters, then a business list beside its detail panel. Selection reveals source facts, qualification, reasons and the next review step in place. Run history and setup/settings are separate views.

Data truth: summary values come from the engine; the list count describes matching stored rows. Preserve missing-name, missing-ABN, unscored and unknown-date states. Keep sample/demo labels and outreach-disabled notices visible. Source observations and qualification dates do not establish registration dates, revenue, buying intent or permission to contact. Report availability belongs to its run and current artifact authority; unavailable or stale reports need explicit feedback.

Supported controls: refresh stored state; start a demo run with pending/completion/failure feedback; save source preference and a validated A$0-150 monthly enrichment usage limit. Defaults apply to subsequent dashboard runs; the effective monthly limit can remain lower. Setup describes actual readiness and outstanding live prerequisites. There are no live-provider connection or outreach activation controls.

Visual authority: inherit the repository DESIGN.md, canonical Maintain Media mountain wordmark, local Albert Sans, deep teal surfaces and purple emphasis. Keep the compact information hierarchy and restrained state feedback. On phones, navigation fits three columns, filters remain available, list/detail and setup stack, and recent runs become cards with report actions. Preserve visible keyboard focus, empty/loading/error/saved states and the reduced-motion fallback.

Boundary: this is a loopback fixture workspace, not production authentication or live collection. The dashboard specification is `abn-leadgen/dashboard-spec.md`; production release gates remain separate. This brief records implemented surface behavior, not certification of those gates.
