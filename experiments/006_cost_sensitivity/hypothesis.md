# E006 — cost sensitivity of composite_2f's picks (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12 + plan 4.4):** hypothesis written before `run.py` executes; predictions
may not be edited after. Only `results.json`, `verdict.md`, and the LEDGER verdict are
written after.

**Question (plan 4.4, pre-registered there):** re-score composite_2f's picks at
**0.2% / 0.5% / 1.0% per side** on the validation slice. BRD §9.7's warning is the prior:
*"Rank-600+ names will not fill at 0.2%* — cheap-cost results alone are not evidence." The
ledger row's prediction: net edge at 0.2% does not survive 1.0% for picks ranked below ~600.

**Scoring model (fixed now, deliberately simple — this is a sensitivity scan, not a
backtest):** each decision month, take composite_2f's top-5% picks (the same top slice the
precision metric has used all along, k = max(1, round(n × 0.05))); each pick's gross forward
return is `next_month_ret`; the net return is `gross − 2 × cost` (round-trip, entry + exit
sides). Three cost levels: the config default 0.2%, and the pre-registered 0.5% / 1.0%
(`backtest.cost_sensitivity_pct`). Reported per level: mean pick return per month, monthly
hit rate (net > 0), and the spread vs the 0.2% level. No portfolio engine, no slot
competition, no triggers — Phase 5 owns those; this isolates the cost question.

**Rank-conditional split (the actual hypothesis):** picks are split by as-of liquidity rank
at the decision date (`liquidity_rank`: ≤ 600 vs > 600 — the BRD §9.7 boundary, also the
plan's size-bucket line) and by `size_bucket` for the report. The pre-registered claim is
about the >600 tail.

**Decision rule (written pre-run):** E006 is **confirmed** iff, in the >600 rank group, the
mean net pick return at 0.2% is positive AND turns negative (or falls below +0.5% gross-edge
parity: mean net < 25% of its 0.2% value) at 1.0%. If the >600 edge survives 1.0% intact
(≥ 50% of its 0.2% value), the verdict is **rejected** — the BRD's warning does not bind for
this strategy. Anything in between ⇒ **partial**. The headline cost level for Phase 6's
report is set by where the edge halves: the smallest cost at which the >600 group's mean net
return drops below half its 0.2% value.

**Honest caveats, pre-declared:** (1) pick-level means over a fixed top-5% slice ignore
portfolio capacity and slot competition — a 4-slot portfolio's realized costs differ; (2)
fills are assumed at the month-end decision close; T+1 open fills (BRD §9.1) are the
engine's job and will differ; (3) the validation slice only — Phase 6 re-asks this on the
test window inside the real engine; (4) 145 months, ~1,300 eligible names, top-5% ⇒ ~7,200
pick-months total, ~1,400 in the >600 group... enough for a mean, not for tail claims.
