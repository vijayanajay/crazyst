# E013 verdict — the index regime filter improves the realized window, and that is all it proves

> **Index-equivalent (added 2026-09-27):** over this experiment's identical 35-month window,
> the same capital in Nifty 500 TRI compounds at **+12.46% CAGR** (`results.json`
> `arms.*.benchmark_cagr`) — every arm in this verdict, including the PASSing CASH arm
> (−4.29% CAGR), loses to the index by ~17pp/yr.

Run: `python -m experiments.013_index_dma_regime.run --profile full` (109.4 s);
`results.json` committed. `hypothesis.md` was written before the run. **Nothing shipped**:
no config, model, portfolio, engine or harness change — the only production-file edit is
the inert-by-default `regime_off` / `regime_liquidate` hook on `smoke_e2e._engine_pass`
(the same pattern as its `market_warm` / `portfolio_overrides` test hooks), and the
harness calls it without arguments, so the persisted harness result cannot move.

## What ran

- **Signal:** daily NIFTY 200 TRI (`index_tri`, sourced 2026-09-27) vs its own 200-session
  DMA at each of the 35 decision month-ends; risk-off = `tri <= dma200`. Prints ≤ M only;
  each fold's DMA was recomputed in Python from that date's own trailing prints and agreed
  to 2.2e-11. Risk-off in **9 of 35 months**: 2024-12-31 … 2025-04-30 and 2026-03-30 …
  2026-06-30.
- **Arms:** the harness's own engine pass over its own window/tape/picks at the shipped
  config. BASELINE (gate inert) reproduced the persisted
  `runs/walkforward/harness_results.json` engine block **bit-for-bit** (the runnable
  check). CASH liquidated at risk-off month-ends (trigger `regime`) and blocked all new
  buys; NO_BUYS blocked new buys only.
- **Decision rule:** primary arm CASH must beat baseline on CAGR, drawdown and Sharpe
  (vacuity guard ≥ 3 risk-off folds — 9 measured).

## Numbers (35 folds, 2023-08-31 → 2026-06-30)

| arm | final equity | total | CAGR | Sharpe | maxDD | fills | picks | hit | churn/mo | regime sells |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline (shipped) | 835,694.98 | −16.43% | −6.14% | −0.427 | −22.99% | 260 | 125 | 28% | 3.54 | 0 |
| **CASH (primary)** | 883,269.82 | −11.67% | **−4.29%** | **−0.244** | **−19.55%** | 202 | 101 | 31% | 2.66 | 2 |
| NO_BUYS (secondary) | 886,195.37 | −11.38% | −4.18% | −0.235 | −19.55% | 200 | 99 | 30% | 2.66 | 0 |
| CASH* (post-hoc probe) | 873,169.67 | −12.68% | −4.68% | −0.273 | −20.47% | 222 | 111 | 29% | 2.83 | 6 |

CASH* = CASH with 2024-12-31 forced risk-ON (its ratio was 0.9990, 10 bp below the DMA):
not pre-registered, no verdict, disclosure only.

## Verdict

**PASS on the pre-registered rule**, with three disclosures that matter more than the pass.

1. **All three bars hold for both real arms.** CASH: CAGR −4.29% vs −6.14%; drawdown
   severity 19.55% vs 22.99%; Sharpe −0.244 vs −0.427. NO_BUYS passes the same bars and is
   Rs 2,925 *better* than CASH: in this window the "go to cash" liquidation leg added
   nothing — each time the gate fired, the review's own exits had already emptied the book
   (the gate's only extra sells were 2 names at 2026-03-30). The value is in **not
   entering**, i.e. the shelved proposal's actionable core is the buy block.
2. **Sign-convention correction, disclosed.** `hypothesis.md` writes the drawdown bar as
   `maxdd_cash < maxdd_baseline`; `metrics.max_drawdown` documents a **negative fraction**,
   so that literal inequality asks for a *deeper* drawdown — the opposite of the
   hypothesis's words ("strictly smaller drawdown"). The words govern (E012's runner-bug
   precedent); the runner now tests the magnitude and records the literal signed reading
   (`REJECTED`) beside it in `results.json`. Corrected after seeing the numbers; no bar or
   threshold moved, and the arms clear the magnitude bar by 3.4 pp.
3. **Post-hoc fragility probe.** The gate's earliest and biggest action hinges on a 10 bp
   margin (2024-12-31: ratio 0.9990). Forcing that month risk-ON still improves on the
   baseline (+1.46 pp CAGR, +0.154 Sharpe, 2.5 pp shallower drawdown) — the result is not
   one hair-trigger month, but it is also not a wide-margin effect.

**Why this is not a validated edge.** Interval attribution (baseline returns, correctly
aligned: the interval ending at fold i+1 is gated by fold i's state) shows the gated
intervals were **better than average in the baseline**: mean −0.19% over the 8 gated
intervals vs −0.54% over the 26 ungated ones. The +4.8 pp total-return gain decomposes into
≈ +2.7 pp from the 8 gated intervals themselves (mostly Jan-25 −1.09% and Feb-25 −4.58%
avoided at ~0% cash, partly offset by Mar/Apr-25 rebounds missed) and ≈ +2.1 pp from the
re-entry path afterwards — which includes a **−7.2 pp interval** (Aug-25, CASH −10.30% vs
baseline −3.08%) and a +6.5 pp pair (Jun/Jul-25). Eight gated intervals, one window, one
re-entry lottery. The paper per-pick means in the risk-off months are not even
negative (+0.76% mean net) — the gain is a realized-path effect, not a pick-quality effect.

**The window is burned.** This test used the walk-forward window, the repo's last unspent
slice, because that is where "the realized engine result" lives. Per hypothesis.md, a PASS
here is opt-in-regret evidence, not validation: any adoption requires a fresh
pre-registered out-of-sample (future months as they arrive) plus the standard config /
verdict / ledger bookkeeping. Nothing was adopted.

## Consequences

- BRD §15's risk row amended: blocker (a) is dead for the index leg (daily NIFTY 200 TRI
  now in-repo), blocker (b) was a different overlay and never addressed this filter, and
  the index leg is now *measured* — improving this window but not adopted, with the burned
  window and the attribution caveat recorded. VIX still has no data path.
- LEDGER E013 block added.
- Reusable by later experiments: `regime_off` / `regime_liquidate` on the engine pass (the
  signal is the caller's; the hook is inert by default).
