# Maintain Media — service line strategy

Current direction for the **Presence + Pipeline** offer. Read in this order.

| # | Document | What it is |
|---|----------|------------|
| 1 | [Marketing council — The Price Is the Bug](https://claude.ai/code/artifact/a8259d20-fb89-4c56-a39b-80554059908c) | Why the sub-$1k retainer can't scale, and the two-tier offer that replaces it |
| 2 | [Presence + Pipeline — the pitch](https://claude.ai/code/artifact/b94a78b3-52e5-4132-9e94-24852eb15b45) | Client-facing sales pitch, with objection handling for whoever runs the call |
| 3 | [Rollout plan](https://claude.ai/code/artifact/fa032ae5-ec5a-4058-8c68-a74238339de6) | 14-week implementation — owners, gates, Jon's time budget, risks |
| 4 | [Five Ways In](https://claude.ai/code/artifact/e7712aa9-2cdc-423b-ba21-bf4c8a5a836c) | Client acquisition — five warm pools ranked cheapest-first, with scripts |
| 5 | [How We Run An Account](https://claude.ai/code/artifact/ae8e0402-f1d3-4543-bd3a-e9a0361e7e66) | Service definition and delivery playbook — the daily operating document |

## The offer

- **Presence + Pipeline — AU$6,000/month.** Media VA and appointments VA on the same
  account. Content published weekly, then every engagement signal worked the same day,
  qualified, and booked into the client's calendar.
- **Presence — AU$3,500/month.** Content only. The downsell, never the lead.
- **Setup — AU$3,000 one-off**, both tiers.

Target: **3–4 clients = AU$10–15k/month**, no new hires. Jullian's capacity at these
prices is 2–3× the target; the binding constraint is the appointments VA (3–5 accounts),
not the media VA.

## Standing decisions

- **No lead-volume guarantee** until there is a full quarter of measured booking data.
  Guarantee the work and a 90-day out instead.
- **No per-appointment pricing** yet, for the same reason. It's the obvious v2.
- **No software build** in the first 14 weeks. Three clients doesn't justify it, and it
  would automate a process that isn't documented.
- **Disqualify on the call:** corporate employees, deal sizes under ~$10k, anyone who
  demands a lead guarantee.

## Withdrawn

`invisible-expert-ad-series.md` — a AU$1,500 paid LinkedIn campaign written before the
strategy work. Assumed an ad account, retargeting audiences and lead capture that don't
exist. The 12 pieces of copy are retained and reusable as organic posts on Jon's profile.

## Client campaigns

| Document | What it is |
|----------|------------|
| [Team playbook](https://claude.ai/code/artifact/52d32f41-44b0-4e21-bd3a-b910157067c8) | **The operating manual.** Message house, roles, runbook, gates, stop rules, phone scripts, kickoff message. Send this to the team. |
| [Campaign build](hvac-split-system-launch.md) | The reference doc — keywords, ad copy, funnel model, landing-page spec, unit economics, test plan. |

**Client:** licensed electrician, residential split-system install, Brisbane northside.
**Status:** draft — blocked on the offer decision (attach / multi-head, playbook §09) and
the compliance checklist (ARCtick, standard-install definition).

Run with the `hvac-growth-marketing` skill (`.claude/skills/hvac-growth-marketing`), which
holds the standing rules: optimise to CAC per *completed* install, never raw leads;
check unit economics before recommending spend; ACCC single-price and ARCtick compliance
gates.
