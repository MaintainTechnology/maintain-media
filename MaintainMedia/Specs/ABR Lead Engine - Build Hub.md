---
title: ABR Lead Engine - Build Hub
project: Maintain Media
version: "4.0"
revised: 2026-09-11
tags: [abr-lead-engine, maintain-media]
---

# ABR Lead Engine — Build Hub

Start with [[ABR Lead Engine - Explained Simply]]. It explains the whole idea using small
examples and everyday language. Then read [[ABR Lead Engine]] for the authoritative requirements.

The application in `abn-leadgen/` now serves the authenticated
[live dashboard](https://www.maintainmedia.com.au/abn-lead-gen/dashboard). Actual
QBCC intake, reviewed website-phone collection and the separately approved GHL
connection are enabled. There is one reviewed business with two landlines and
zero selected worklist rows or real GHL transfers. Local fixture tools still use
synthetic data and remain separate.

Open [[ABR Lead Engine - Implementation Status]] and
[[ABR Lead Engine - Activation Follow-up 2026-09-11]] for the verified release,
operating steps and remaining work. The live DNCR receipt adapter, genuine
individual phone/qualification approval, disabled Google workflow, backup/restore
acceptance and measured pilot are unfinished. Broader ABR also needs its live
feed implementation and classifier study. The full-tool progress score is
**87/100**; no full-production pass is claimed.

The original specification scored 7.8/10; the corrected v4.0 received a final independent
native fallback judgment of **9.3/10**. This rates the documents, not a completed application.

## Understand the product

- [[ABR Lead Engine|Canonical specification v4.0]]
- [[ABR Lead Engine - Explained Simply|Detailed simple explanation]]
- [[ABR Lead Engine - Product Specification|User stories and 43 requirements]]
- [[ABR Lead Engine - Research and Decisions|Design decisions and assumptions]]
- [[ABR Lead Engine - Source Checks|Official source checks and corrections]]

## Build it

- [[ABR Lead Engine - Constitution|Governing principles]]
- [[ABR Lead Engine - Technical Plan|Architecture and chosen stack]]
- [[ABR Lead Engine - Data Model|Data ownership and constraints]]
- [[ABR Lead Engine - Interface Contracts|Commands, control API and vendor contracts]]
- [[ABR Lead Engine - Build Contract Precision|Exact source fields, invariants and edge cases]]
- [[ABR Lead Engine - Build Tasks|Implementation tasks and six convergence follow-ups]]
- [[ABR Lead Engine - Developer Quickstart|Fixture validation and handover]]
- [[ABR Lead Engine - Implementation Status|Runnable build and acceptance evidence]]
- [[ABR Lead Engine - GHL Phone Handoff 2026-09-11|Current GHL connection and why individual hand-offs still wait]]
- [[ABR Lead Engine - Staff Workflow Installation|Private Google and GHL installation status]]

## Review evidence

- [[ABR Lead Engine - Council Review|Original and revised Council scores]]
- [[ABR Lead Engine - Final Judge|Final 9.3/10 judgment and limitations]]
- [[ABR Lead Engine - Final Review Plan|Independent build handoff]]
- [[ABR Lead Engine - Consistency Analysis|Requirement coverage and consistency review]]
- [[ABR Lead Engine - Reviewer Notes|Independent findings and resolutions]]
- [[ABR Lead Engine - Specification Checklist|Built-in specification quality check]]
- [[ABR Lead Engine - Security and Readiness Checklist|Security and readiness writing review]]
- [[ABR Lead Engine - Spec Kit Status|Applied stages and remaining release gates]]
- [[ABR Lead Engine - v3.5 Archive|Preserved original specification]]

## Keep this vault in sync

The repository file `specs/abr-lead-engine.md` is authoritative. Imported notes include their
source path and SHA-256 so changes can be checked. Local Markdown document links are adapted
to Obsidian links; the wording is preserved.

From the repository, run `python tools/sync_abr_vault.py`, then
`python tools/validate_abr_docs.py --vault`. These commands synchronise/check documents only.
Application build and deployment have their own tasks and evidence gates.
