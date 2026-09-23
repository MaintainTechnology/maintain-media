# New-business prospect research

Maintain Media's mission is to help newly registered businesses get their first customers through a zero-cost-to-start lead generation partnership. The dashboard supports discovery, verified research and a next conversation. Source records remain immutable; prospect research is stored separately in the authenticated engine.

## Operator workflow

**Latest leads is now the main discovery entry point.** It opens on the last 30 Brisbane calendar days, with a last-7-days option. It queries active ABR source records directly, globally ordered by status date descending. Discovery is independent of qualification score and does not require missing email/social presence. **Leads list** opens on **All businesses**, showing collected ABR and QBCC source records without a minimum score, tier or date requirement. The original qualified-business list remains under **Qualification reviews**; its score is a qualification ranking, not a pass rate.

The all-business list queries the entire accepted publication by business name, ABN or QBCC licence. Each source has its own 50-record page, total and pagination pinned to the resolved run. Sources remain separate because their records are not a deduplicated business count or a single globally sorted list. Source candidates can open the same evidence-backed research editor and appear in Saved prospects after saving; a valid ABN and accepted snapshot are required. Missing scores remain unscored, and a missing ABN never inherits another business's qualification. Existing qualification and contact gates are unchanged.

The **No website** focus includes saved businesses at any age with `website_presence: absent`, even when email and social profiles are present. **Website unchecked** searches saved research with unknown website status; it is explicitly labelled as saved-only, while unsaved recent businesses remain available in the two date views. Batch research lookup annotates the current source page with verified website status and contact outcomes without loading a contact history for every publisher row. Missing saved research and a failed research lookup have distinct labels. Source/prospect read roles remain admin/reviewer/compliance.

Pagination stays on the accepted source run and preserves global ordering. Publication dates, stale-window warnings and explicit 30-day/all-source recovery remain visible; no date window is silently moved to an older publication. Recent status dates still require original-registration verification. The navigation count no longer misrepresents qualified businesses as the complete discovery universe.

1. Open **Source records → ABR → Last 7 days**. The engine searches the whole selected publication for active ABNs whose status commenced today or in the previous six Brisbane calendar days. Last 14 days, Last 30 days and custom inclusive date bounds are also available. Existing state, postcode, name, entity and GST filters remain available. Filtered CSV uses the same server predicate.
2. Use **Prospect view** for business name, ABN, location and status date. **All stored fields** preserves the original detailed table. Publication/import timestamps and the coverage caveat remain visible.
3. Open **Research business**. Check official ABN history and research the business online. Record website, email and social as Unknown, Found or Confirmed absent; retain supporting evidence and any business contact details. Missing publisher fields never imply absence.
4. Verify the *first* registration date and record evidence. An ABN status date can represent reactivation, so recent status dates alone never enter the verified-new filter.
5. Save research and open **Saved prospects**. Quick filters include Verified new (7 days), No website, No digital presence, Target match (7 days), and Follow-ups due. Target match requires all three presence fields confirmed absent plus the verified first registration window. These filters cover all saved research, not only the displayed page.
6. Copy researched phone/email details for the approved contact process. The form supplies a conversation guide for the zero-cost-to-start offer, contact outcome, notes and follow-up date. It sends no message and grants no contact permission. Existing lead qualification and CRM authority continue separately.

## Evidence and data boundaries

- The ABR extract is weekly and contains ABN status/date, names, entity, location and GST attributes; it does not contain the website/email/social evidence needed for this offer. References: [ABN Lookup bulk extract](https://abr.business.gov.au/Tools/BulkExtract), [ABN registration event search includes registration and reactivation](https://abr.business.gov.au/abrxmlsearch/).
- Original registration is explicitly staff-verified research with an evidence reference. Discovery never claims to prove first registration automatically. Historical publications are never silently reinterpreted as today's coverage.
- New records must bind an exact ABN in an accepted snapshot. Source identity and resolved run provenance are preserved on update. Authorised reviewers/admins save; compliance can read. Contact details are encrypted. Suppression and quarantine checks apply on reads/writes, finite inactivity retention is 180 days, and deletion/holds use the existing retention workflow.
- Saves use revision checks and retry identities, followed by readback. The modal protects unsaved work; failures preserve drafts. Empty filters are omitted. Queries have explicit work limits and pagination.
- Research is a prospect workflow; actual lead delivery, partnership billing and downstream customer-conversion reporting are separate business operations, not fabricated dashboard metrics.

## Implementation contract

- Source filters: `status_date_from`, `status_date_to`, canonical ISO dates, inclusive, ABR only. Use `status: ACT` for recent active discovery.
- Source query `sort`: `source_order` (default) or ABR-only `status_date_desc`, echoed in responses. Newest ordering spans all files/pages with stable ties and null dates last; CSV/default browsing order is unchanged. Sorting caches bounded aggregate counts, never source records.
- All-business list: `POST source-records/query` with `source`, `run_id`, `offset`, optional `filters.query` and `sort: source_order`. Default filters are empty. Do not use the bounded canonical qualification dashboard as the source of discovery records. Each source's failed query is isolated, and stale responses cannot overwrite a newer search or resurrect a hidden view.
- `POST /api/prospects/query`: `{offset, filters}` → `{records, total, offset, limit: 50, next_offset}`.
- Optional top-level `abns` on a prospect query limits lookup to 1–50 unique 11-digit ABNs using indexed retained-key aliases. Only current unsuppressed saved records are returned; absence does not imply a website gap.
- `GET /api/prospects/{abn}`: `{prospect: null | record}`.
- `POST /v1/prospects`: evidence-bearing draft with `request_id`, source snapshot/run and `expected_revision` → bounded save receipt. Browser requests use the existing authenticated website bridge (`prospects/query`, `prospects/{abn}`, `prospects`).
- Database migration: `abn-leadgen/migrations/027_prospect_research.sql`. Run the existing production database provision/migration installer first so runtime table grants are reapplied, then deploy the engine and website. Applying the SQL as database owner alone does not grant the runtime role access. No production migration, collection activation, outreach or deployment is performed by this change.

## Public website

The homepage hero, mission section, partnership process and closing CTA emphasise first customers, early-stage businesses and zero cost to start. Contact options accept personal email for owners without business email. No guaranteed lead volume or immediate delivery claim is invented. The existing enquiry backend is unchanged.

## Verification

- Python typed-date/source query/export units; prospect validation and real isolated PostgreSQL persistence, source binding, auth, revision, suppression, expiry and retention tests.
- Website strict response/date model tests, signed bridge tests, existing dashboard rendering tests, TypeScript and scoped ESLint.
- `node website/tests/source-records-browser/check.mjs`: actual dashboard React with synthetic engine responses, fully isolated from production. Covers original source workflows plus prospect discovery, evidence saves/readback, updating existing records, failed-save recovery, unknown exclusion, quick filters, modal protection and mobile layouts.
- Public homepage/contact browser smoke at desktop/mobile, with form writes blocked. Screenshots and results are under `website/acceptance/landing-mission-20260922/` and `website/acceptance/prospect-workflow-20260922/`.
- Leads-list regression evidence is in `website/acceptance/leads-list-20260923/`: unscored source browsing alongside one qualified record, Tier B/C reviews, per-source pagination, full-publication name/ABN search, research saving, missing-ABN handling, partial errors, request races and responsive layouts.
