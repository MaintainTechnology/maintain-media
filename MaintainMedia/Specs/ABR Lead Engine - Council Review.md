---
title: "ABR Lead Engine - Council Review"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/001-abr-lead-engine/council-review.md"
source_sha256: ba9d64edc9cc958b197c2dc1e11a856603c7179fa6cf1d5faf4409c52c104dc4
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# LLM Council Review — ABR Lead Engine

Reviewed 8 September 2026. Specification quality only; no production/legal certification.

## Original v3.5

Independent judge: **7.8/10**. Two independent Codex reviews scored the source 7.6 and 8.1.
Weighted judge dimensions: correctness/evidence6.8(25%), requirements8.6(20%), architecture8.2(20%),
privacy/security/operations7.6(20%), scope/traceability8.1(15%).

[Original judge](llm-council/runs/20260908-abr-baseline-2/judge.md)
and [merged review plan](llm-council/runs/20260908-abr-baseline-2/final-plan.md).

## Method and limitations

The first mixed-provider run failed: Claude session limit; installed Codex CLI incompatible with
its configured model. Those error files are not review evidence or a score.
The successful fallback uses two independent gpt-5.5 Codex CLI sessions plus a separate gpt-5.5
judge through the installed LLM Council orchestrator. The runner supplies source documents,
anonymises review outputs and randomises presentation before judging.
This is a single-model multi-reviewer Council, not cross-provider agreement.
Provider errors and successful Markdown outputs are preserved under llm-council/runs.
No account reset, paid subscription or global model configuration was changed.

## Revised v4.0

**Final independent specification rating: 9.3/10** (weighted total 9.275).
The native fallback judge identified no remaining substantive documentation blocker in the
corrected revision. This supports beginning the scoped synthetic build. It does not certify
implemented behaviour, legal clearance, vendor readiness, performance or production release.

| Dimension | Weight | Final score / 10 |
|---|---:|---:|
| Correctness and evidence | 25% | 9.4 |
| Requirements and acceptance | 20% | 9.3 |
| Architecture and data integrity | 20% | 9.2 |
| Privacy, security and operability | 20% | 9.3 |
| Scope, delivery and traceability | 15% | 9.1 |

[[ABR Lead Engine - Final Judge|Final judge and reviewed source hashes]]
and [[ABR Lead Engine - Final Review Plan|final merged review plan]]
preserve the reasoning, limitations and build handoff.

## Review history and final fallback

| Review snapshot | Recorded result | Interpretation |
|---|---|---|
| abr-baseline | Provider failures | No valid score |
| abr-baseline-2 | Judge 7.8 | Original v3.5 |
| abr-revised | Judge 8.5 | Intermediate revision; checklist update was incomplete in that snapshot |
| abr-final | Judge 8.3 | Later intermediate revision; further contract precision needed |
| abr-precision | Two reviewers each 8.6; judge capacity failure | Reviewer scores only; no valid merged judge score |
| abr-adjudication | Native independent judge 9.3 | Corrected final v4.0, with source hashes in judge.md |

After the CLI capacity failure, a fresh native Codex judge reviewed the actual corrected files
and two anonymised, randomly ordered prior reports. It was not asked to award a target score
and did not read this score summary. Its verdict is a fallback adjudication, not unanimous
agreement by all earlier reviewers or cross-provider consensus. Earlier results remain intact.

Corrections include official-source accuracy, explicit release gates, channel-specific checks,
retained suppression identity, exact content hashing, publication recurrence versus retry, and
safe key retirement after erasure. The judge verified the last two corrections before scoring.
Minor terminology and implementation-schema refinements are retained in its handoff.

The independent requirements review closed RV-01–06 and recorded 20/20 writing-quality checks.
Document validation confirms 43 requirements and 59 unchecked build tasks, with 43/43 mapped.
All G1–G7 production evidence gates remain pending. No application test or deployment is claimed.
