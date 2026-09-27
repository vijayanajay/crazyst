# E010 — Hypothesis: E006's cost sensitivity re-measured on the post-E009 floor universe (pre-registered)

Written **before** the run, per BRD §12. Motivation: E009 proved the pre-floor universe's
paper picks were 38.8% unenterable at the shipped slot size — the tail the fill gate
refused is the tail where per-side costs are worst (spread + impact on thin turnover).
E006's 0.5%/side default was therefore calibrated on a portfolio the engine itself would
not have built. This experiment re-runs E006's protocol, unchanged, on the floor universe,
and decomposes where the cost actually comes from.

## Protocol (E006's, replicated exactly — importlib, so no drift)

- Same scoring: composite_2f top-5% per month (k = max(1, round(n × 0.05))), gross =
  `next_month_ret`, **net = gross − 2 × cost**; three levels
  **{0.2%, 0.5%, 1.0%} per side** (`backtest.cost_sensitivity_pct`); validation slice only
  (boundary 2023-09-24; test window untouched); reported per level **and** per the BRD
  §9.7 rank split (≤600 vs >600) and size bucket. Picks are selected with E006's own
  `_picks` INCLUDING its row-order tie convention — the backward guard must reproduce
  E006 bit-for-bit, so this experiment inherits E006's convention, not the symbol
  tie-break the smoke uses.
- **The only change is the universe**: the shipped config (`min_median_turnover_cr: 0.75`,
  E009's adopted floor) → the chain rebuilt at full profile. E006's committed results.json
  (universe_note: "floor OFF; BRD-owner decisions pending") is the comparison baseline.
- **The impact decomposition** (new, pre-registered): E006's flat per-side number is a
  proxy for what the engine models as flat cost + spread/impact headroom. Per pick-month,
  compute the engine's own impact estimate at the shipped slot size —
  `min(impact_cap_pct, impact_coef × S / med20)` per side (S = ₹250k; `med20` from E009's
  `liq_daily20` and its sanity layer, reused) — and report mean per-side impact by level
  of `med20`. Hypothesis: the floor arm's picks carry materially lower modelled impact,
  which is *why* the honest per-side cost fell.
- Sanity layer: E009's frozen-sample and member-recompute checks re-run against the
  `liq_daily20` this run rebuilds; the pre-floor E006 numbers are re-measured in-run
  (config 0.0, chain rebuilt) and must reproduce E006's committed results.json pick count
  **exactly** and means to the tie-swap tolerance before any comparison is made — the same
  zero-drift discipline E007/E009 used, now pointing backward at E006.

## Predictions (fixed before the run)

1. **Edge-halving (E006's own headline rule):** on the pre-floor universe the >600
   group's edge halves somewhere in {0.5%, 1.0%}. On the floor universe, the same
   half-edge point moves to a **higher** cost level — or the >600 edge survives 1.0%
   intact (≥ 50% of its 0.2% value), which would make E006's BRD warning non-binding
   for the tradable portfolio.
2. **The floor arm's net edge at 0.2% is strong in absolute terms:** mean net of the
   "all" group at 0.2% ≥ 2.0%, and its GROSS mean stays ≥ 2.3% (E009's corrected paper
   mean) — the retained picks carry the edge, not a cost artifact.
3. **Impact decomposition:** mean modelled per-side impact of the floor arm's picks is
   below the pre-floor arm's by a factor consistent with the med20 shift — reported as
   the mechanism, not a tuned parameter.

## Decision rule (written before the run)

- **Default moves to 0.2%/side** iff ALL of: (a) the floor arm's "all" mean net at 0.2%
  is ≥ 2.0% — the candidate default leaves a strong absolute edge; (b) the >600 group's
  edge-halving point on the floor universe is strictly higher than on the pre-floor
  universe, or the edge survives every level (E006's warning demonstrably relaxes);
  (c) the impact decomposition confirms the mechanism (floor-arm picks' modelled impact
  ≤ 80% of the pre-floor arm's); (d) the floor arm's "all" GROSS mean stays ≥ 2.3%
  (E009's corrected paper level — the gain is signal retained, not cost arithmetic).
- Otherwise: **keep 0.5%** and record the re-measurement — conservatism that costs a
  known, bounded amount is cheaper than re-baselining every frozen anchor twice in one
  week. The E009-corrected honest baseline stays the corrected number either way.
- Anything ambiguous → keep 0.5%, report, no config change. This file may not be edited
  after the run (BRD §12).

## Pre-run correction note (no runs had started)

Two defects in the first draft, fixed before any run: (1) the protocol said "tie-break by
symbol" — wrong, E006's `_picks` uses row-order ties and the backward guard requires
reproducing E006 exactly, so the E006 convention is inherited; (2) the original criterion
(a) ("the 'all' group's cost slope flattens by ≥ 0.6pp between 0.2% and 0.5%") was a
tautology — in this protocol `net = gross − 2 × cost`, so the level-to-level slope is
arithmetic and identical in every universe. Replaced with the absolute-net and gross-
retention criteria above, which actually test whether the honest default is lower.
