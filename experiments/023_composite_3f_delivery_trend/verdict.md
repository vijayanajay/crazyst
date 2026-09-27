# E023 — verdict: REJECTED — the 3f delivery-dynamics composite is significantly worse than the shipped 2f

Run 2026-09-27, profile `full`, 145-month validation slice (test window untouched).
`results.json` is the record; `hypothesis.md` was written before the run.

| arm | mean monthly IC | top-5% precision |
|---|---|---|
| shipped 2f (mom_12m_1m + delivery_pct) | **+0.0720** | 55.7% |
| composite_3f_dt (+ delivery_pct_trend) | +0.0606 | 55.5% |

Paired by month (P4.1's `_paired_t`, re-used verbatim): mean diff **−0.0115**, t = **−2.69**,
p = **0.008** over all 145 months. B1 required diff > 0 at p < 0.05; the measured diff is
negative at p = 0.008 — not a near-miss, a significant degradation.

Guards: G1 the control's slice mean IC equals the smoke's committed `SLICE_IC_PIN`
(0.07202922854484578) to 1e-9; G2 slice pins (145 months, boundary 2023-09-24); G3 145
paired months. All green.

## Reading

`delivery_pct_trend` is the delivery level's own 20-session difference — it carries almost
no information the level lacks, and the equal-weight mean pays for the redundancy twice:
the shipped 2f weights momentum 50/50 with delivery; the 3f weights momentum 1/3 against a
correlated delivery pair at 2/3. E002b's standalone IC for the trend (+0.0229) was real,
but standalone IC does not survive correlation inside an equal-weight rank mean — the same
lesson as P4.1's 3f (mom_6m variant, p 0.0585), now measured a second way.

## One implementation note (disclosed in results.json, the E013/E014 way)

The first run reproduced the control bit-identically (diff +0.0000, p 1.0) — because
`model.score_month` iterates its own hardcoded two-feature global, silently dropping any
third feature passed through its `feature_at` lambda. The treatment scorer was rebuilt on
`model._pct` (the shipped rank math and NaN contract) with the three frozen features
explicit. The production path was never touched; the guard that caught it was G1's
next-door neighbor — the paired comparison itself going to zero.

## Decision

Per the frozen rule: **REJECTED**. The shipped 2f stands. The composite family is closed —
two 3f variants have now missed their pre-registered bars (P4.1: mom_6m; E023:
delivery_pct_trend), and a third feature must beat the paired bar to exist. The audit's
remaining directions (the atr down-month tilt, index-inclusion flows) do not route through
the composite and are unaffected.
