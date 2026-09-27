# E016 — low-turnover engine: does suppressing forced churn recover the edge the monthly architecture destroys?

Pre-registered 2026-09-27, **before the run** (BRD §12): the arms, guards, bars and reading
rule below are frozen. The runner is implemented after this file exists and the file is
never edited afterwards; the verdict is written beside it as `verdict.md`.

## Motivation

- The LEDGER block "Break-even arithmetic" (2026-09-27, `breakeven.py`): the top-5% pick
  edge barely decays with holding period — net ~2.35%/month at 1-month holds vs ~2.04%/month
  at 12-month holds (price-path estimator, delisting-honest) — while round trips fall 12x.
  Every engine configuration ever measured loses to the index; churn x costs is the
  difference between a +2%/month raw edge and a −6% CAGR engine.
- The monthly review (BRD §8.1) sells a holding on rank fade (below top-25%) or a 5-close
  50-DMA streak, then replaces it. That is the churn. Trigger B (stop/trail/GSM) and
  universe exits are risk controls, not churn — they stay.

## Window

The 145-month validation slice (2011-07-29 -> 2023-07-31, boundary 2023-09-24). The test
window is untouched. Arms run full-slice engine passes (harness convention, warm=20), the
E014 machinery.

## Arms (frozen)

- **A BASELINE** — the shipped config, no overrides. Must reproduce E014's committed
  `arms.baseline` bit-for-bit (json-equal).
- **B SELL_GATE** — config-only: `monthly_review_sell_below_top_pct` 0.25 -> 1.01 (never
  sell on rank fade) and `monthly_review.ma_below_consecutive_closes` 5 -> 999 (never sell
  on the DMA streak). Trigger B stops/trails, GSM forced exits and universe-exit sells
  remain. Replacement buys for freed slots remain. No new code.
- **C MIN_HOLD_12** — a new inert `_engine_pass` hook, `min_hold: int | None = None`
  (default inert): a decision-month sell with trigger `monthly_review` is dropped while the
  position has been held fewer than 12 decision months. Trigger B and universe exits are
  NOT suppressed — a hard stop fires even in month 1.

## Guards (frozen, all must pass for the run to count)

- **G1** arm A json-equal to E014's committed `arms.baseline`.
- **G2** tape pins: arm-convention picks >= 4,579; eligible rows == 161,942; mean monthly
  IC == `smoke.SLICE_IC_PIN` (repaired tape, LEDGER 2026-09-27) to 1e-9.
- **G3** mechanism check: B and C each emit strictly fewer `monthly_review` sell decisions
  than A over the slice.
- **G4** hook inertness: `python -m src.backtest.smoke_e2e` PASSes after the hook edit and
  its committed engine passes stay bit-identical (the shipped call passes no `min_hold`).

## Bars (frozen)

- **B1 (primary):** at least one of B/C delivers slice CAGR >= A's CAGR + 3.0pp
  (A's CAGR is -0.50%, so the bar is >= +2.50% CAGR). The 3.0pp floor is the cost-drag the
  break-even arithmetic says is recoverable; anything smaller is not worth an architecture
  change.
- **B2:** the winning arm's maxDD is not worse than A's by more than 5pp. Sign convention
  (E013/E014 lesson): `max_drawdown` is a NEGATIVE fraction, so "worse by >5pp" means
  `maxDD_arm < maxDD_A - 0.05`.
- **Recorded, not gating:** round trips/month per arm (the mechanism, must fall); the
  **index-equivalent line** — the slice's Nifty 500 TRI benchmark CAGR from the same engine
  pass (`benchmark_cagr`), printed in the verdict next to every arm. An arm beating its
  baseline while still losing to the index is a real but partial result; the verdict must
  say both numbers. (Whether the satellite should exist at all given the index alternative
  is the portfolio question, kept out of this experiment's gate.)

## Decision rule

PASS iff B1 and B2 both hold for at least one arm, with all guards green. On PASS,
adoption is a separate decision (config amendment + re-derivation of E012's floor at the
new turnover). On FAIL, the low-turnover family is closed on this slice: the monthly
review's sells are doing alpha work that churn costs do not explain, and the remaining
pivot is portfolio-level (index core + small satellite), not engine-level.

Disclosures rule: any deviation between the coded bar and these words gets recorded in
`results.json` (`bars`, `bars_as_coded`) the E013/E014 way, and both readings are judged.
