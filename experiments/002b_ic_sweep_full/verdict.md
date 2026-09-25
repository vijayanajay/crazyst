# E002b — verdict (written after the run; the hypothesis was not edited)

**Verdict: CONFIRMED with one major reversal.** Per the pre-registered decision rule: at
least one momentum feature is confirmed (two are), and the sweep overall carries the Phase 4
candidate set. The reversal: **the quick-profile delivery rejection does not survive full
history — delivery is real at 15 years.**

- **CONFIRMED: `mom_12m_1m`** — mean monthly IC **+0.052** (t = 5.05, p = 1.1e-6,
  BH-surviving), 64% of 181 months positive. Plus `mom_6m` +0.024 (p = 0.019, BH-surviving).
  The momentum prior holds at full history, and it is **counter-cyclical**: IC in down-months
  +0.099 (75% of 69 months, p = 6e-8) vs up-months +0.023 (n.s., p = 0.069). Momentum is a
  crash-following signal here, not a bull-market one.
- **CONFIRMED (reversal of E002's quick rejection): the delivery family.** `delivery_pct`
  mean monthly IC **+0.049** (t = 7.2, p = 1.2e-11, BH-surviving, 72% of months),
  `delivery_pct_trend` +0.023 (p = 5.9e-9), `delivery_pct_zscore` +0.017 (p = 1.6e-5). E002's
  −0.010 on 11 up-months was a regime artifact, not a falsification. Delivery is even more
  regime-tilted than momentum: down-months +0.087 (87%, p = 1.6e-14) vs up-months +0.026
  (p = 0.004). E002's ledger row said "the delivery prior is falsified on quick data"; the
  full-profile row now says the opposite, and this is exactly why the plan demands the
  regime split before believing a sweep.
- **REJECTED (direction): `atr_ratio` at −1** — but the rejection is informative: mean
  monthly IC **+0.043 in up-months** (p = 6e-4; more volatile names keep winning in bull
  windows, matching E001's anatomy) and **−0.183 in down-months** (94% of 67 months, p = 7e-19;
  volatility is punished after crashes). The pre-registered sign holds in exactly the regime
  the quick window never sampled. `range_compression_20d` mirrors it (+0.008 up / −0.049
  overall, BH-rejected). Low-volatility is a crash-month factor, not an all-weather one.
- **REJECTED (direction): `up_down_volume_ratio`, `breakout_volume_confirmed`,
  `close_in_range`, `consec_higher_lows`, `big_body_day_in_trend`** — all BH-surviving with
  the wrong sign at full history; the candle/accumulation lore does not survive 15 years.
- `mom_1m` reversal (dir −1) is not confirmed at full history: mean monthly IC −0.018
  (p = 0.050 boundary, not BH-surviving), and it is regime-split (−0.047 up / +0.029 down).
  The strong quick-profile reversal does not survive; treat monthly reversal as regime-conditional.

**Decision rule applied:** momentum confirmed at full history ✓; the volatility-state clause
("stable sign across months, ≥ 70%") is NOT met overall (63%) — instead the data shows the
sign is stable *within* each regime and flips between them, which the pre-registration did
not anticipate and the verdict records rather than bends.

**Bucket attribution (descriptive):** the confirmed features price the whole universe —
`mom_12m_1m` +0.038/+0.049/+0.052 and `delivery_pct` +0.047/+0.059/+0.054 across top200 /
201–600 / 601–1500 — with the strongest ICs in the mid/small buckets. This is the opposite of
E001's quick-window anatomy (momentum vanishing in 601–1500); 15 years of data overrules 11
up-months.

**Consequence for the plan (Phase 4 composite candidates):** `mom_12m_1m` (+), `mom_6m` (+),
`delivery_pct` (+), with `atr_ratio` as a regime-conditional overlay (− in down-regimes) and
`close_in_range` (−) as the only candle feature with a stable wrong-direction IC worth a
pre-registered test. Delivery is back in — E002's quick verdict stands as written but is now
known to be a bull-window artifact, and this experiment is the citation.

**Honest caveats:** (1) 181 months is one market's history — India 2011–2026 has one 2020-style
crash cluster; down-regime n = 69 is thin even if internally consistent. (2) The regime split
is post-hoc descriptive (bucketed on the realized forward month), pre-registered as such; it
is evidence for Phase 4 design, not a tested strategy. (3) Feature overlap: mom_6m and
mom_12m_1m correlate; delivery_pct and its z-score/trend are the same family — the composite
must not count them as independent votes. (4) BH covers 22 features but the family is the
same one E002 tested; the two experiments share data through feature_matrix by construction.
