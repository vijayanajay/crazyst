# E006 — verdict (written after the run; the hypothesis was not edited)

**Verdict: REJECTED — the BRD §9.7 cost warning does not bind for composite_2f's picks on
this evidence. The edge at 1.0% per side survives at 52% of its 0.2% value in the very group
the warning names.**

- **The pre-registered rule, applied:** the >600 rank group's mean net pick return is
  **3.34%** at 0.2% and **1.74%** at 1.0% per side — **52.1% of base**, above the ≥ 50%
  survival line, and positive throughout. Per the rule, the warning "does not bind for this
  strategy" ⇒ **rejected**. (The strict negative-or-parity confirmation never came close:
  1.74% is nowhere near negative or below the 25% parity line.)
- **The full table (6,622 pick-months, 145 months, top-5% of composite_2f):**

  | group | 0.2% | 0.5% | 1.0% |
  |---|---|---|---|
  | all picks | 3.05% (52.8% hit) | 2.45% (50.6%) | 1.45% (46.3%) |
  | rank ≤ 600 | 2.25% (54.5%) | 1.65% (52.5%) | 0.65% (48.4%) |
  | **rank > 600** | **3.34% (52.2%)** | **2.74% (49.9%)** | **1.74% (45.6%)** |

  The small-cap tail is not the cost victim the BRD feared — it carries the strongest gross
  edge (3.34% vs 2.25%) and stays the best group at every cost level. Bucket view agrees:
  601–1500 nets 1.74% at 1.0% vs top200's 1.00%.
- **What "rejected" means here — the caveat that still bites:** this scan models cost as a
  uniform `gross − 2×cost` haircut on month-end closes. It does NOT model **impact and
  non-fill** — the real mechanism behind BRD §9.7's "rank-600+ names will not fill" is that
  illiquid names slip or don't fill at all, which shows up as *worse effective prices*, not a
  clean per-side fee. The honest conclusion: **at equal fills, the small-cap edge survives
  1% costs; whether fills ARE equal is exactly what Phase 5's engine (T+1 open, circuit
  locks, liquidity-aware slippage) must test on synthetic data before Phase 6 believes it.**
  The cost parameter is not the binding constraint; the fill model is the open question.
- **Consequence for the plan:** E006's ledger purpose — "sets the report's default cost
  assumption" — resolves to **0.5% per side** for the Phase 6 report: the 0.2% default is
  optimistic for a strategy whose picks average the 601–1500 buckets, 1.0% is survivable but
  halves the hit rate (45.6%), and 0.5% sits at the conservatism midpoint with the edge still
  82% of base. All three levels stay in the report per BRD §9.7. Phase 5's engine must make
  the fill model its hardest problem, not the cost constant.
- **Honest caveats:** (1) pick-level means on a fixed top-5% slice ignore slot competition
  and capacity — 4 slots select 4 of the ~46 monthly picks, and a real portfolio's picks may
  skew differently; (2) month-end-close fills vs the engine's T+1 open will differ (gap risk
  between signal and fill is unmodeled here); (3) the validation slice only — Phase 6
  re-asks this on the test window inside the real engine; (4) no confidence intervals on the
  group means — the ~4,800 >600 pick-months make the means stable, but the *fill-model*
  uncertainty dominates them anyway.
