# P4.1 — Composite score v0 vs the best single feature (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12 + plan 4.1):** hypothesis written before `run.py` executes; predictions may
not be edited after. Only `results.json`, `verdict.md`, and the LEDGER verdict are written
after. **Universe: as-of top-1500, turnover floor OFF** (`min_median_turnover_cr: 0.0`) — the
BRD-owner decisions of 2026-09-25 (`docs/brd_decisions_universe.md`) are implemented here as
"top-1500 / floor-off, flagged BRD-owner-review-pending"; the feature_matrix is already built
on exactly this universe.

**Question (plan 4.1 / BRD M3):** does a rank-average composite of the features that survived
E002b beat the best single feature on the pre-test-window validation slice, out-of-sample?

**Slices (fixed by BRD §10.1, not chosen):** the test window is the last 36 months ending at
the data cutoff. A labeled decision month belongs to the TEST window iff its label end (next
decision date) falls after `cutoff − 36 months`; **the validation slice is every labeled
decision month before that** (~2011-07 → 2023-08 at full profile). Every number in this
experiment comes from the validation slice; the test window is not touched (it belongs to the
Phase 6 walk-forward).

**Arms (all parameter-free — v0 has no fitted weights, by design):**

1. **`composite`** — per decision month, each feature's cross-sectional **percentile rank**
   (average ranks, NaN rows stay NaN), then the mean of the available percentiles of
   `mom_12m_1m`, `mom_6m`, `delivery_pct` (E002b's confirmed survivors, equal weights fixed
   a priori). A row needs ≥ 1 non-NaN feature to be scored; rows with 0 are excluded from
   that month's IC for every arm equally. Feature family note: mom_12m_1m and mom_6m
   correlate — they enter as two votes deliberately (both pre-registered horizons), and this
   is stated here so nobody later calls it hidden double-counting.
2. **`composite_atr_overlay`** — `composite + sign(mkt_trail_1m) × pct(atr_ratio)`, where
   `mkt_trail_1m` is the cross-sectional mean of `mom_1m` at the decision date (the
   equal-weight market's trailing 1-month return, known at D — no lookahead) and the sign is
   +1 when it is ≥ 0, else −1 (E002b: atr_ratio IC +0.045 in up-regimes, −0.183 in
   down-regimes; the overlay flips its vote with the regime). The forward-regime definitions
   of E002b are NOT usable at D; the trailing market return is the pre-registered proxy, and
   the slice test below is the test of that proxy. Weight 1.0 = one extra equal vote.
3. **`best_single` (comparator)** — the single feature with the highest mean monthly IC on
   the validation slice, selected FROM the validation slice among all 22 features. The
   selection is deliberately in-sample for the comparator (winner's curse inflates it), so
   beating it is the conservative form of M3's bar.

**Metrics:** primary — mean monthly Spearman IC (score vs forward return) on the validation
slice, arms compared **paired by month** (one-sample t on monthly IC differences, two-sided,
α = 0.05, `src.stats.t_sf_two_sided`; two arm-vs-comparator comparisons are run, both
reported, no BH — the pre-registration states this openly). Secondary — pooled top-5%
precision on the slice (mean of monthly top-5% hit rates), reported not gatekeeping.

**Decision rule (written pre-run):** the composite is **confirmed** for Phase 4 iff its mean
monthly IC difference vs `best_single` is positive with p < 0.05 on the paired t; otherwise
the ledger says so and Phase 4.2 (learned ranker) proceeds per plan 4.2. The overlay arm is
**confirmed as an addition** iff it beats the BASE composite on the same test (paired t,
p < 0.05); otherwise it is recorded as not-additive and does not ship in v0. If the composite
ties the comparator (|p| ≥ 0.05 either way), the verdict is `inconclusive` and the simpler
single feature ships (fewest moving parts wins ties).

**Honest caveats, pre-declared:** (1) the slice is pre-test-window but not untouched by
history — E002b's verdicts informed WHICH features enter; that is the plan's designed flow
(Phase 4 builds on Phase 3's evidence) and is why the bar is "beats the winner's-cursed
comparator", not "has positive IC". (2) 15 years contain one crash cluster; the overlay's
sign flip is exercised rarely. (3) Costs, portfolio rules and triggers are Phase 5/6 concerns
and are absent here — this is a cross-sectional ranking test, not a backtest.
