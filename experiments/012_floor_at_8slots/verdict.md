# E012 verdict — ADOPT floor 0.375 (the loosest candidate cleared every bar)

Run AFTER hypothesis.md (2026-09-26, full profile, cutoff 2026-09-24). E009's machinery
imported module-to-module; the baseline chain (floor 0.0) reproduced **E009's committed
R1_by_slot rows bit-for-bit at all four slot sizes**, the member recompute re-verified
(9,186 rows over 6 dates), the frozen 2020-02 sample re-verified row-for-row (1,136 rows),
the restore IC equaled P4.1b's frozen 0.0681243229, and the 0.75 arm reproduced **E009's
committed R2 row exactly** (S250k reachability) plus its IC to <1e-9. Guards first,
comparisons after.

## The measurement (validation-slice corrected pick means at the 8-slot notional, S = Rs 125k)

| arm | floor | eligible rows | refused @S125k | corrected mean | IC (145m) | modelled impact |
|---|---|---|---|---|---|---|
| baseline | 0.0 | 218,648 | 29.36% | +2.669% | 0.068124 | — |
| **ADOPTED** | **0.375** | 161,942 | **1.14%** | **+2.692%** | **0.071718** | 0.092%/side |
| passed | 0.5 | 154,813 | 0.46% | +2.730% | 0.070110 | 0.074%/side |
| reference | 0.75 | 144,059 | 0.21% | +2.632% | 0.067450 | 0.056%/side |

Every moving arm cleared the four pre-registered bars: corrected mean within 5bp of 0.75's
(both BEAT it), paired t vs baseline ≥ −2, refusal ≤ ⅓ of the un-floored 29.36%, floor ≥
the gate's 0.25cr boundary. The loosest passing candidate wins → **0.375** — which is also
the arithmetic answer: the gate's boundary at the 8-slot notional (0.25cr) × E009's own
1.5× headroom. The floor was never a tuned number; E012 re-derived it from the same
construction at the new notional.

**Answer to "should the floor move with slot size": yes — it MUST, because the gate's
boundary does.** The floor is derived from (gate boundary, headroom), not fitted to
backtest outcomes; per-slot notional halves at 8 slots, so the floor halves with it. The
wider book can now hold the 0.375–0.75cr band profitably: +6 to +10bp/month corrected mean
over the 0.75 floor, at modelled impact of 0.09%/side (vs the E010 stack's 0.5%/side — an
order of magnitude below the flat cost).

## Disclosure: a decision-rule bug, caught before any adoption

The first run's runner picked **0.5** — my code ordered the candidates loosest-last
("0.5" before "0.375"), inverting hypothesis.md's "ADOPT the LOOSEST floor clearing all
bars" (loosest = SMALLEST floor: a higher minimum excludes more names). The bug was
caught re-reading the run against the pre-registration before anything was adopted; the
comparison lines were ordered, not the candidates. Fixed in `run.py` (one tuple order +
comment), the run re-executed (234.6s, deterministic: all guards re-passed identically),
and the corrected decision is 0.375. Every measured number in the two results.json files
is identical; only the decision field differs (0.5 → 0.375). No number ever moved to fit
a conclusion.

## Consequences executed

1. `config.yaml`: `universe.min_median_turnover_cr: 0.75 → 0.375` with the E012 citation
   and the derivation note (re-derive on any notional change; not a tuning knob).
2. Chain rebuilt at the shipped 0.375: 161,942 eligible rows / 183 matrix months.
3. **Smoke re-pinned to E012's 0.375 arm**: eligible 161,942 asserted from results.json,
   IC bit-identical (0.07171797803434904), light-pass picks **4,579** (the E009-era 3,902
   pin retired to E012 with the same reasoning E006's anchor was retired to E009: the
   chain it described is no longer the shipped one). Smoke PASS.
4. **Harness reference re-run (§10.3)** at floor 0.375 + 8 slots, determinism-verified:
   final equity **892,626.0949598341 — bit-identical to E011's A8 arm**. Fill log
   symbol+date sets identical; the single fill-level difference is HARDWYN's 2023-09-29
   exit trigger label (monthly_review → trigger_b_dma): the wider eligible universe
   moved the rank percentile under the rank-band rule, so the DMA rule collected the
   sell. Same fill, same quantity, same rupees — churn +1 (3.457 → 3.486/mo) is the
   same sell counted under a different trigger. Paper picks: 2,212 (was 2,196 at the
   0.75 floor), hit 56.6%, +2.34% gross. Benchmark CAGR 8.25% (the universe changed, so
   the self-benchmark moved with it).
5. E012's own runner made re-runnable post-ADOPT (shipped-floor assert accepts 0.75 or
   0.375; arms pass floors explicitly — the E009/E011 pattern).

## What did NOT change

`backtest.fill.max_position_adv_frac` (0.05), cost 0.50%/side, exit_gate escalate,
n_slots 8, the model. BRD §4's floor sentence is amended by the E012 block in LEDGER.md
(the dated convention this repo uses for BRD amendments).
