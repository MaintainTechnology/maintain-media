# Build rubric — fixed before implementation

Baseline: ABR specification v4.0, 8 September 2026. Application root is `abn-leadgen/` by explicit user instruction; Python import remains `abr_engine`. Full specification review and local engineering score are reported separately. External policy/account approvals and measured four/eight-week pilot cannot be fabricated or replaced by this score.

| Dimension | Points | Evidence needed for full credit |
|---|---:|---|
| Specification behaviour and traceability | 25 | R1–R43 mapped to implemented paths and executed scenarios; missing obligations visible; all buildable scope implemented |
| Data integrity and recovery | 20 | Real PostgreSQL constraints, exact source events, publication recurrence/retry, atomic promotion, meaningful fault/concurrency tests |
| Security and permission authority | 25 | Authentication/scopes, exact provenance, latest evidence, suppression races/restore/erasure/keys, safe crawl, closed live gates |
| Runnable delivery and operations | 20 | Frozen installation, runnable demonstration/API, usable private report, durable output/budgets, recovery commands, measured resource evidence |
| Maintainability and independent verification | 10 | Lint/types/tests pass; understandable handover; independent review findings resolved; reproducible revision/results |

Score only evidence actually collected. Partial work earns proportional credit and is listed explicitly. A failing security or data-integrity invariant prevents a clean local review regardless of score. Full-spec PASS requires every requirement and acceptance obligation; live/pilot evidence remains a separate unresolved obligation when absent.

Review loop: build -> run checks -> independent review -> score and rank weaknesses -> fix highest-impact buildable weaknesses while preserving passing behaviour -> rerun affected checks -> review again. A real margin is at least two total points or resolution of any high/critical correctness finding. Stop quality-polish iterations only after no actionable high/critical finding remains and two assessed revisions improve by less than two points; never use a plateau to hide unfinished buildable work.

Scores and commands will be recorded in `trajectory.md` after execution. Initial state: no application, no implementation score awarded.
