# E009 — Hypothesis: the fill gate makes the model's best ideas uninvestable, and an ADV-aware eligibility floor fixes it (pre-registered)

Written **before** the run, per BRD §12. Motivation: E008b's W1 window degenerated into a
cash book — the E006 fill model refused 26/50 selection orders as `non_fill_adv` because a
₹250k slot cannot enter a stock that trades under ~₹0.5cr/day (the gate refuses an order
when `notional > 5% × trailing-20-session median turnover`). The model's four top-scored
September-2018 names were untradable at realistic sizing. The question is not whether the
gate is wrong (it correctly models that you cannot fill) but **how much of the strategy's
measured return is a paper return on names that could not have been bought, and whether
excluding them upstream (eligibility, ₹-crore floors on the 3-month median turnover
`med3`) recovers the honest, tradable edge.**

## The gate's arithmetic (fixed before the run)

The engine refuses a buy when `qty × open > max_position_adv_frac × adv20`, with
`max_position_adv_frac = 0.05`. At the slot size S = capital / n_slots, a stock is
enterable iff `adv20 ≥ S / 0.05 = 20 × S`: **₹0.5cr/day at ₹250k/slot** (the shipped
₹10L × 4 config), ₹1cr at ₹500k, ₹2cr at ₹1M. A *typical day* at the floor is ~twice the
20-day median at the 75th percentile of the turnover distribution, so the realized
refusal boundary sits near `med20 ≈ 0.6 × 20 × S` — predicted from the same tables this
experiment builds (no tuning: one distributional ratio, computed in-run and reported).

## Constructions (fixed before the run)

- **`liq_daily20(symbol, mdate, med20, n_days)`**, one row per symbol per decision month:
  the median of the trailing **20-session** daily turnover in rupees (sessions strictly
  before D: the fill window is the month after D, and the decision bar itself must not
  contribute to the gate's own window), rebuilt by this run script. `med3` (the rank
  input) already exists in `liq_me`.
- **`adv_2020_02`** — a frozen hand-check sample: every eligible row of the 2020-02
  decision month with `symbol, med20, n_days`, committed alongside results.json; the
  table is re-verified against it **row-for-row every run** (t-1 window equality,
  medians, member counts).
- Sanity: a synthetic fixture (known 4-session turnover → hand-computed median) plus the
  frozen-sample re-verification. A per-decision-date **member-level recompute** of every
  `liq_daily20` row against a from-scratch bhav scan (the rank module's own
  `_source_equivalence` pattern, sampled dates) — wrong window bounds, wrong series
  filter, or a wrong join die here.

## R1 — how much of the pick return is unreachable at realistic sizing?

On the validation slice (boundary 2023-09-24; test window untouched), for composite_2f's
top-5% picks (tie-break by symbol), and **at equal per-pick notional S** (a fill model
whose slots are S, not the engine's actual cross-sectional cash split):

1. **Headline at S = ₹250,000** (the shipped ₹10L × 4): % of pick-months refused
   (`med20 < 20 × S`), mean gross pick return of refused vs fillable picks, and the
   **reachability-corrected mean** = mean over fillable picks only. Pick return = the
   panel's `next_month_ret` (month-end to month-end, adjusted, costless — the E006
   convention); the engine's realized costs are *higher* on thin names, so costless
   overstates what the gate protects.
2. **Refusal share is not a tail event:** % of pick-months and % of *pick return mass*
   (return × weight in the pick mean) refused, plus refusal rate of the **top-decile
   score** picks specifically.
3. **Sensitivity at S ∈ {125k, 250k, 500k, 1M}** (pre-registered; the shipped S±:
   smaller slots refuse less, larger refuse more) — the same four numbers per S.
4. **The 2018-09 W1 window, named:** the four refused top-scored names (LIQUIDETF,
   INFRABEES, SPLIL, GKWLIMITED) — their `med20` at the decision date and their forward
   month returns, so the ledger block can name what the gate refused.

## R2 — does ADV-aware eligibility fix it?

- **The arm: `universe.min_median_turnover_cr: 0.75`** — declared BEFORE the run and
  justified by the gate's own arithmetic, not tuned: at the shipped ₹250k/slot the
  enterable boundary is `med20 ≥ 0.5cr`; the 3-month median must clear the same bar with
  the measured med20/med3 shrinkage (predicted ≈ 0.57–0.67, so 0.75 ≈ the boundary ×
  shrinkage, a safety margin, not a fitted value). One arm, one value, pre-registered —
  any other value would be a threshold sweep this experiment refuses to run.
- The floor is enforced through the real pipeline: config mutated, `E007._build_chain`
  rebuilt (rank → eligibility → winners → panel → matrix at the full profile), same slice
  split, same scoring, same top-5% rule.
- **Zero-drift restore + return-path guard:** after the arm, config restored to 0.0, the
  chain rebuilt again, and the mean monthly IC re-asserted **bit-identical** to P4.1b's
  frozen 0.0681243229 (to 1e-9) — E007's restore discipline, now guarding the return
  path too.
- **Measured on the same metrics as R1:** pick mean return, refusal share at S = 250k,
  IC, eligible symbol-months.

## Decision rule (written before the run)

- **R1 headline:** the corrected mean and its delta from the paper mean are reported
  regardless of outcome; the honest baseline claim follows the corrected number.
- **R2 ADOPT** the floor iff **all** of: (a) the corrected pick mean at 250k improves
  (floor arm ≥ baseline corrected mean); (b) IC does not fall materially
  (paired t ≥ −2 on the floor arm's monthly ICs vs baseline); (c) the floor's refusal
  share at 250k drops materially (≤ 1/3 of baseline's, so the fix buys tradability, not
  just a cleaner stat). Any single miss → **REJECT** (record only; the config floor stays
  0.0). Adoption means a config change plus a ledger-marked BRD §4 decision note —
  never a silent edit.
- Mixed/ambiguous → REJECT with the numbers, per the burden-of-proof discipline of
  E007. This file may not be edited after the run (BRD §12).

## Pre-run correction note (no runs had started)

The draft wired R1's headline through `smoke._engine_pass` (the smoke's 12-month engine
pass), which would have made the headline a plumbing-scale artifact with ~70 pick-months.
Corrected before any run: the headline is measured on **all ~6,622 pick-months at a fixed
equal per-pick notional S**, with `E007._build_chain` reusing the frozen helpers; the
smoke engine pass is dropped entirely (the gate's arithmetic is exact at a fixed S, and
the 2018-09 case is reported by name in R1.4).
