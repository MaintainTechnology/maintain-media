# Implementation decision register

Specification authority: `specs/abr-lead-engine.md`, version 4.0, 8 September 2026.
The application directory is `abn-leadgen/`; the Python import is `abr_engine`.
This folder change does not approve a business rule or alter the canonical requirements.

| ID | Date / version | Decision / reason | Owner | Evidence and affected checks |
|---|---|---|---|---|
| D001 | 2026-09-08 / 1 | Offline fixtures are the default; live collection, enrichment, CRM and outreach remain disabled. | Jon Pepper / developer | Configuration and capability tests; G1–G7 pending. |
| D002 | 2026-09-08 / 1 | The legacy `deliverables/abr/extract_new_abns.py` corpus was absent during specification review. Synthetic rules are engineering fixtures, not 30 recovered rules. | Jon Pepper | Recover provenance and hash actual corpus or approve replacement; stratified 100-record review remains pending. |
| D003 | 2026-09-08 / 1 | Fixed originating signal and tier at selection define a cohort. Repeated events count a business once; a different explicitly declared cohort is reported separately. | Owner approval pending for live pilot | `tests/unit/test_outputs.py`; never retrospectively move outcomes to a current tier. |
| D004 | 2026-09-08 / 1 | Union every operator's overlapping calling/research/wash/review/admin intervals. Add different operators' time. | Developer; pilot owner review pending | Activity corrections append; sheet edit gaps are not worked time. |
| D005 | 2026-09-08 / 1 | Private static HTML/Markdown/CSV uses Maintain Media dark teal and purple. Only current authorised candidate projections contain contact values. | Developer | Escaping, CSV formula, expiry and positive-path fixtures. No dashboard or sender. |
| D006 | 2026-09-08 / 1 | Unknown capacity bounds block admission. Existing allocations are informational; remaining allocations plus 25 GiB headroom determine admission. | Developer | Formula fixtures. Full 20.5M-row benchmark and AU host selection pending. |
| D007 | 2026-09-08 / 1 | Sheets edits sign actual installable-trigger editor context, path/body/idempotency key; immediate suppression precedes outcome revision checks. | Developer | Mock contract; live editor identity and scope mapping requires G5 sandbox certification. |
| D008 | 2026-09-08 / 1 | Automatic procurement cash authority is A$0. Enrichment usage cap is a separate A$150 calendar-month ceiling. | Jon Pepper | Purchases require an external dated owner record; no purchasing function. |
| D009 | 2026-09-09 / 1 | Supersedes D002's missing-file observation: the local legacy extractor now exists; exactly 30 literal ordered regexes were recovered by AST without executing the old program. | Developer | `ops/acceptance/live-sources/rules-review-decision.json` binds source/rule hashes and behavioural differences. No production activation. |
| D010 | 2026-09-09 / 1 | User approved retaining all 30 trade categories, QLD plus NSW postcodes 2450–2490, QBCC Categories 1–2 and at most 60 businesses per week. | User in current Codex task | `ops/acceptance/live-sources/targeting-approval-2026-09-09.json`; targeting direction only. The real 100-record precision review, collection/vendor/hosting and release decisions remain pending. |

No current external licence, tariff, processor location or signup condition was verified by the output implementation. Refer to the dated specification source-check record as historical context and perform the release recheck. No historical count or timing is a new result.

Changes require an appended version, actor, date, reason, evidence, affected tests and owner approval where they change production policy. Do not overwrite prior approvals or infer approval from this implementation register.
