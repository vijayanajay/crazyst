# E009 — Verdict: ADOPT (the paper edge was half unreachable; a ₹0.75cr floor restores tradability at no signal cost)

Run 2026-09-26, profile `full`, boundary 2023-09-24 (test window untouched), git
`e8bf4f2` (working tree). Built per hypothesis.md: `liq_daily20` (301,659 symbol-months),
frozen 2020-02 sample re-verified row-for-row (1,136 rows), member-level recompute clean
over 6 sampled dates (9,186 rows) after the comparator itself was fixed twice
(window-anchor semantics, then the full-window requirement — both documented in the
script).

## R1 — how much of the pick return was a paper return?

At the shipped ₹250k/pick (the engine refuses a buy when notional > 5% × trailing-20
median turnover, i.e. `med20 < 0.50cr` at this slot):

| metric | value |
|---|---|
| pick-months | 8,802 (8,703 with a defined med20) |
| **refused** | **3,413 (38.8%)** |
| **gross return mass refused** | **50.5%** |
| mean pick return, all / fillable / refused | +3.11% / **+2.52%** / **+4.05%** |
| top-decile-score picks refused | 46.6% |

**The refused picks are the model's BEST picks.** Illiquidity is concentrated exactly
where the composite concentrates: the smallest, most-illiquid tail is where a
3-month-liquidity momentum + delivery-spike score finds its extremes. The paper mean
(+3.11%) is not achievable at the shipped sizing — the reachability-corrected mean is
**+2.52%** (−0.59pp), and the correction compounds with E006's cost finding: what the
fill gate protects is precisely the expensive-to-exit tail.

Sensitivity (refused share / return mass refused): ₹125k → 29.4% / 39.4%; ₹500k → 49.6% /
57.0%; ₹1M → 61.2% / 68.0%. The shipped ₹10L × 4 configuration sits at the unfavorable
end: even halving the slot refuses ~a third of picks. Only 99 pick-months (1.1%) lack a
20-print history at D (fresh listings, excluded consistently).

## R2 — does ADV-aware eligibility fix it?

The floor arm (`universe.min_median_turnover_cr: 0.75`, chosen by the gate's arithmetic
and the measured med20/med3 shrinkage, not tuned) through the real chain:

| metric | baseline | floor 0.75 |
|---|---|---|
| eligible symbol-months | 218,648 | 144,059 (−34%) |
| refusal at ₹250k | 38.8% | **1.5%** |
| corrected pick mean | +2.52% | **+2.61%** |
| mean monthly IC | 0.068124 | 0.067450 (paired t = **−0.12**) |

All three pre-registered criteria met: (a) corrected mean improves (+2.61% ≥ +2.52%);
(b) IC does not fall materially (t = −0.12, nowhere near the −2 bar — the signal is
cross-sectionally *stronger* per name on the tradable subset); (c) refusal drops to 1.5%,
far under the ≤⅓ bar — **the floor buys tradability, not just a cleaner statistic.**
Zero-drift restore: config and chain rebuilt, IC 0.0681243229 → bit-identical
(delta 1.4e-17), R1 measurement reproduced exactly.

## The W1 postscript (E008b's evaluator caveat, corrected)

At decision time 2018-09-28, LIQUIDETF (med20 ₹0.90cr) and SPLIL (₹0.62cr) were actually
**enterable** — only INFRABEES and GKWLIMITED were under the 0.50cr line. E008b's W1
refusal count was inflated by its evaluator: the smoke's month-window Market starves the
trailing-20 ADV at a window's first bars. E008b's arm-vs-arm conclusion (identical
curves) is untouched — both arms shared the tape — but its caveat understated how much
the fill model's behavior depends on the market window's shape. Recorded in the ledger.

## Decision

- **ADOPT `universe.min_median_turnover_cr: 0.75`** as the shipped default: the config
  changes 0.0 → 0.75 with this experiment cited, and the BRD §4 note records the closed
  question (the old "as a config guard, subsumed by the top-1500 rank" comment is
  measured-false twice over: rank 1500 still turns over under ₹5cr/day, and the *model's
  own picks* are where illiquidity concentrates).
- The engine's fill gate stays exactly as it is — it remains the last-resort reality
  check; the fix is upstream, at eligibility, where it also improves the fill model's
  impact estimates (entries now land in names whose ADV supports them).
- What does NOT follow from this row: any claim that the corrected +2.52% (or the floor's
  +2.61%) is the strategy's return. It is the pick-level, costless, equal-notional
  headline; engine-level results remain the 6.1 harness's job.
- A future re-open needs: a named liquidity regime change (tick-size, lot-size, or
  exchange microstructure), not a tuning hunt.
