# E013 — the shelved index regime filter (Nifty 200 vs 200-session DMA) on the harness window

Written BEFORE any run (BRD §12). The BRD §15 risk row has kept "market regime filter
(Nifty 200 vs 200-DMA + VIX)" at **CONSTRAINT — NOT IMPLEMENTED** behind three blockers.
Blocker (a) — no index series in the repo — is now dead: `index_tri` holds daily NIFTY 200
TRI prints from 2011-01-03 through the cutoff (sourced in `src/download/nifty_tri.py`,
cache `data/raw/nifty_tri/nifty200/`). Blocker (b) recorded that P4.1's *trailing-market
atr overlay* (a score-level overlay) diluted the composite — that is NOT this filter.
Blocker (c) is about point-in-time index *membership*, which this filter does not use: the
signal is the index level vs its own DMA, no constituent list. The VIX leg still has no
data path; the review's own replacement (E008a/E008b breadth gates) was rejected on
premise and on the intra-month layer. The index leg itself has never been measured.

**Question:** does the originally-proposed regime filter — Nifty 200 below its 200-session
DMA = risk-off — improve the REALIZED walk-forward result (the 35-fold harness pass, the
result of record: Rs 835,695, CAGR −6.14%, Sharpe −0.43, maxDD −22.99%)?

## Signal (fixed before the run)

At each decision month-end M (the harness's fold dates):

- `dma200(M)` = mean of the last **200 daily NIFTY 200 TRI prints ending at M** (the
  index's own sessions; ≥ 200 prints required — satisfied since 2011).
- `risk_on(M)` iff `tri(M) > dma200(M)`; otherwise risk-off.
- Both quantities use prints ≤ M only: the state is known at M's close, decisions are
  taken at M's close, fills happen at T+1 by the engine's existing protocol. No
  look-ahead. The TRI carries dividends; the DMA is computed on the same series (the
  price-index variant would sit a few tenths of a percent apart; disclosed, not swept).

Measured state over the window (this is the mechanical construction, not a result): the
signal is risk-off in **9 of 35 folds** — 2024-12-31 … 2025-04-30 (the Jan–Feb 2025
correction; note 2024-12-31 is a hair-trigger: ratio 0.9990) and 2026-03-30 … 2026-06-30
(the recent drawdown). Vacuity guard below.

## Arms (fixed before the run)

All three arms are the harness's own engine pass (`smoke_e2e._engine_pass`) over the
harness's window, tape, picks and warm-ADV pad, at the shipped config. The gate is the
only difference; it is implemented as an inert-by-default keyword hook
(`regime_off` / `regime_liquidate`) so the shipped run cannot drift.

- **BASELINE (guard arm):** gate inert. MUST reproduce the persisted
  `runs/walkforward/harness_results.json` engine block **bit-for-bit** (every field of the
  harness's own `_evaluate_pass` output, via a JSON dump comparison). No comparison is
  valid without this; it is also the runnable check of this experiment.
- **CASH (primary — the shelved proposal's wording, "go to cash"):** in each risk-off
  fold: (i) every held position receives a sell decision at that month-end close
  (trigger `regime`; fills follow the normal T+1 path), and (ii) no buy orders are
  submitted that month (neither review replacements nor the all-cash initial selection).
  On the next risk-on month normal behavior resumes (re-entry is the ordinary initial
  selection/review path).
- **NO_BUYS (secondary, diagnostic only):** in each risk-off fold, new buys are blocked;
  holdings ride their own Trigger-B/review exits. Isolates the entry-block from the
  liquidation so the verdict can say which lever moved what.

No thresholds are swept: the 200-session DMA is the proposal's own construction, the
comparison is on-close strict (`>`), the cadence is monthly (the decision cadence; the
intra-month layer was E008b's rejected territory), no VIX leg (no data), no buffer, no
hysteresis. A FAIL kills this filter rather than inviting a tuning hunt (the E008b rule).

## Decision rule (fixed before the run)

- **Vacuousness guard:** if risk-off folds < 3, the verdict is INADEQUATE, not a decision
  (measured: 9, so the test runs).
- **Primary arm CASH, conjunctive — all three bars must hold vs BASELINE:**
  1. `cagr_cash > cagr_baseline` (strictly),
  2. `maxdd_cash < maxdd_baseline` (strictly smaller drawdown),
  3. `sharpe_cash > sharpe_baseline` (strictly).
  No partial credit, no look at the secondary arm for the verdict. If any bar fails, the
  filter is **REJECTED on this window**.
- **Secondary arm NO_BUYS:** all three bars computed and reported for diagnosis; carries
  no verdict.
- **Test-window burn (declared up front):** this test runs on the walk-forward window —
  the repo's last unspent slice. That is exactly what was asked ("the realized engine
  result"), and it is why the outcome must be read as **opt-in-regret evidence, not a
  validation**: a PASS would mean the filter improved THIS realized run, but the window
  is then burned for this rule family, and any adoption still requires a fresh
  pre-registered out-of-sample test (future months as they arrive, per §10.3's "the
  window itself is never tuned") plus the standard ledger/BRD bookkeeping. A FAIL is
  terminal for the filter as specified.

## Scope

No config, model, portfolio, engine or harness change. The only production-file edit is
the inert-by-default `regime_off`/`regime_liquidate` hook in `smoke_e2e._engine_pass`
(the same pattern as its existing `market_warm` / `portfolio_overrides` test hooks);
the harness's shipped call passes neither, so the shipped result cannot move. If the
verdict ever became ADOPT, the wiring (config key, harness pass-through, ledger row,
BRD amendment) is a separate pre-registered change, not this experiment.

**Consequences.** REJECT → the BRD §15 risk row gains "the index leg was measured on the
realized window on 2026-09-27 and rejected" with the numbers; the regime question stays
closed at all four layers. PASS → recorded as opt-in-regret evidence with the burned-
window caveat; no config change in this experiment.
