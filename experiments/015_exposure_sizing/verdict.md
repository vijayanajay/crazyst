# E015 verdict — FAIL: at unchanged average exposure, volatility-scaled sizing does not capture the relief

Run 2026-09-27, profile `full`, working tree on `cd204c4`, 145-month validation slice
(2011-07-29 → 2023-07-31, boundary 2023-09-24), test window untouched. `results.json` is
the record; `hypothesis.md` was written before the run and is not edited.

## Guards — all passed, nothing disclosed as broken

- **G1a** the sizing hook is inert: a 12-month pass with the hook present and no scales
  reproduces the committed `runs/smoke_e2e/smoke_results.json` escalate arm bit-for-bit
  (curve prefix, fill log, decisions, month rows).
- **G1b** arm A's metrics equal E014's committed `arms.baseline` exactly, on the same tape
  (cutoff 2026-09-24 asserted).
- **G2** tape pins: arm-convention picks 5,605 (== the pin), mean monthly IC
  0.07171797803434904 (== E012's 0.375-arm IC), eligible rows 161,942. *(Historical note,
  2026-09-27: the adj_close pipeline repair moved the repaired-tape IC to 0.0720292285 —
  LEDGER's adj_close-repair row — and the G2 pin was re-baselined to it the same day;
  this verdict's text records the pre-repair run as it happened. A repaired-tape rerun the
  same day moved arms B/C's magnitudes — B final equity 772,093 → 756,608, maxDD −67.51% →
  −68.11%; C 965,412 → 966,926 — and strengthened the FAIL; arm A was bit-identical. Full
  record in the LEDGER's E015 supersession row; G2's other pins — picks, eligible — were
  unaffected by the repair.)*
- **G3** σ is point-in-time: every 40th (month, symbol) pair of B's map (364 pairs)
  recomputed from a fresh per-pair query — max abs diff **1.4e-17**.
- **G4** the exposure contract held: B's mean invested share 67.4% vs A's 67.9% —
  **−0.49 pp**, inside the frozen ±2.00 pp (−0.49 ≥ −2.00). B is a mean-1 sizing rule in
  fact, not just by construction (scale diagnostics: per-month pool mean scale exactly 1.0
  for all 144 σ-bearing months; median/clip range 0.484–1.906; median normalizer k = 1.036).
- **G5** B's pooled normalization identity holds; C's every scale ≤ 1.0.

## The numbers

| arm | equity | total | CAGR | Sharpe | maxDD | fills | picks | hit | churn/mo | invested | mean buy scale |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A BASELINE | 942,030 | −5.80% | −0.50% | 0.090 | −65.58% | 983 | 529 | 44% | 3.32 | 67.9% | 1.000 |
| B EQUAL_RISK_MEAN1 | 772,093 | −22.79% | −2.13% | 0.009 | −67.51% | 949 | 582 | 45% | 3.20 | 67.4% | 1.040 |
| C DERISK_CAP (diagnostic) | 965,412 | −3.46% | −0.29% | 0.094 | −62.19% | 989 | 531 | 44% | 3.34 | 66.4% | 0.941 |

Capture versus E014's committed relief R = 19.07 pp (baseline −65.58% → block −46.51%):

- **B: gain −1.93 pp (−10.1% of R; the bar was ≥ 6.36 pp)** and CAGR −1.63 pp worse → **B1 fails**.
- **B2 passes trivially**: B's episode drawdown severity is better in 3 of 6 pre-named
  episodes — 2018_ilfs 5.60 → 4.72, 2020_covid 28.73 → 28.25, 2022_rates 15.98 → 15.07 —
  and worse in the other three (2011_euro 9.80 → 10.11, 2013_taper 2.06 → 3.28,
  2015_16_china 12.08 → 14.68).
- **C: gain +3.40 pp (17.8% of R)** at CAGR +0.21 pp better — direction consistent with
  E014's mechanism, magnitude far below the bar; C carries no bar by pre-registration.

Variance decomposition (monthly, 144 intervals): A mean +0.164% / sd 6.31% → geometric
−0.041%; B +0.015% / 6.17% → **−0.179%**; C +0.165% / **6.09%** → −0.024%.

## What happened

**B did not buy variance relief — it bought a bet against the alpha.** The tilt moves weight
out of the volatile names and into the calm ones; the engine's realized book keeps its
return in the volatile names, so B's arithmetic mean fell 0.149 pp/month while the sd fell
only 0.14 pp: a trade with no payoff, and the whole-slice maxDD got *worse* (−67.5% vs
−65.6%) even though B beat A in all three crisis episodes. Side effects reported: B's
resized buys 12 vs A's 3 (upscaled buys hitting the cash constraint, disclosed in
hypothesis.md), completed picks 582 vs 529, mean holding 91.9 vs 65.0 days — a different
path, not a cleaner one. Mean scale actually applied to B's buys 1.040 (vs the pool's 1.0),
and B's invested share still landed 0.5 pp *below* A's.

**C is the channel that works, and it works by removing exposure.** Clipping only downward
(C) leaves the arithmetic edge intact (+0.165%) and cuts the sd to 6.09%, so the geometric
path improves from −0.041% to −0.024%/month — exactly E014's variance-drag mechanism — and
17.8% of the relief comes with it. But C removed only 1.5 pp of mean invested share and
bought ~18% of R. The relief scales with exposure actually removed; a mean-1 rule cannot
remove any, and a below-1 rule is just a smaller book (not a signal-free rescue of timing).

## What it answers

**No.** At unchanged average exposure the relief is not reachable by slot sizing: equal-risk
rebudgeting actively costs (−1.9 pp drawdown, −1.6 pp CAGR) because it is a bet against the
composite's own concentration, and the only sizing variant that helped is a de-risk cap
that recovered ~1/5 of the relief while lowering average exposure. The E013/E014 conclusion
survives its strongest challenger: the relief required *less exposure in bad stretches* —
the exposure/timing device itself — not a smarter distribution of the same exposure.

## Disclosures / observations

- **`adj_close` one-session gap (2019-03-29):** the feed has zero rows that session (bhav
  has it), so no σ view exists at that fold — scale 1.0, i.e. the fold behaves as baseline
  in both arms (1 of 145). The momentum feature and month-end marks read `adj_close`, so the
  pipeline should know about this hole (month-end marks fall back to 2019-03-28 for that
  month). Recorded for the refresh/backfill task, not a finding of this experiment.
- 13.2% of pool symbol-months carry no σ (short history / no adj closes) and hold scale 1.0;
  they keep the pool mean at 1.0, which is why the normalization stays honest.
- The 0.375 floor is derived at the equal-weight notional (E012); under B/C the effective
  notional moves 0.5×–2×, so the gate binds differently. No refusal-rate comparison to the
  shipped 1.14% is made, and **any** future sizing arm must re-derive the floor per arm
  (E012's rule) on fresh data before adoption.
- No config change, no rule adopted, nothing promoted. The sizing family is closed on the
  validation slice at this reading; a re-open needs a different mechanism (e.g. an explicit
  exposure target with its own pre-registration), not a re-run of this one.
- The inert `size_scale` hook stays in `smoke_e2e._engine_pass` (default `None` =
  bit-identical; every E015 run re-proves it via the smoke prefix guard).
