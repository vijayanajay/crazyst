# Phase 6.1 checkpoint — the walk-forward harness (2026-09-26)

What was built, the decisions made before the first run, and the first run's numbers.
The ledger block of the same date is the condensed record; this file is the design doc.

## What exists now

`src/walkforward/harness.py` — the BRD §10 evaluator: rolling re-score over the test
window, every fold month traded through the real engine + portfolio, §11 metrics,
realized slippage. Registered in the suite as `walkforward.harness` (25 checks, all PASS).
Its synthetic self-check needs no database: slippage sign math, regime bands, benchmark
construction, the no-peek gate (raises on stale matrix / empty snapshot / a stateful
scorer), and every §11 metric against one hand-computed round trip.

The smoke's engine loop was **promoted, not rewritten** — exactly the 5.1 review note's
prediction. `smoke_e2e._engine_pass` gained:

- `market_warm=N` — N sessions fetched BEFORE the decision window (default 0 = bit-identical
  to the old behavior). This is the E008b ledger lesson: a per-month `Market` starts cold
  and its first bar's trailing-20 ADV median IS that bar, so the fill gate and impact model
  starved exactly at the month boundary where the T+1 fills land. The harness walks with
  `market_warm=20` (the fill gate's own trailing window).
- `engine_months_limit=` — the harness walks all 35 test months; the smoke keeps its 12.
- `_facts(d_from=)` — facts stay scoped to the decision window; the ADV pad never leaks
  into DMA/trail facts.
- dict-shaped `events` / `fill_log` return keys (JSON-ready) — additive; the smoke's own
  pins and report are untouched and were re-verified after the promotion (3,902 picks,
  IC bit-identical to E009's floor arm).

`src/backtest/metrics.py` gained the two §11 lines it lacked: `max_drawdown` (worst
peak-to-trough over EVERY curve row — month-end marks alone hid the toy's intramonth dip)
and `avg_holding_days` (share-weighted days per completed FIFO lot, still-open disclosed).

## Decisions made before the first run (recorded in results.json `protocol`)

1. **Window** — P41.split_slice's test slice (boundary 2023-09-24 at cutoff 2026-09-24),
   recomputed from the DB cutoff every run. The same split every validation-slice
   experiment used, so harness folds and the frozen slice cannot disagree about the wall.
2. **Refit semantics.** §10.2 says "fit the model (features selected, thresholds,
   weights)" — but the shipped model is composite_2f: two cross-sectional percentile
   ranks averaged. It has NO fitted parameters; the cross-sectional rank uses only the
   decision month's own features, all known at D. Inventing a refittable variant for the
   harness would have changed the shipped strategy to satisfy a sentence written for
   fitted models. Decided: the monthly "fit" is the frozen decision function, and the
   harness asserts it per fold — the function is the shipped two-feature composite, and
   the refit month (2023-07-31) re-scores BIT-IDENTICALLY around the fold's own scoring
   (P4.2's freeze protocol, harness level). A stateful or refitted function trips the
   assert; a fitted model, if one ever ships, breaks this first, which is the point.
   Note the freeze check is about the FUNCTION, not per-symbol scores: a symbol's score
   legitimately differs between two months (its inputs moved); the function must not.
3. **No-peek gate** (the actionplan's "assert in code"): per fold month — the fold sits
   strictly after the refit month; every scored matrix symbol is inside the decision-date
   `eligible` snapshot (a stale matrix would silently score names not eligible at D);
   frozen-decision check above.
4. **Trade M with the frozen decision** — the promoted pass over all 35 fold months
   consecutively, one pass, shipped `exit_gate` (escalate), shipped costs (0.50%/side +
   capped impact on real ADV). stuck/force stay engine-available, not walked; per-mode
   side-by-side walks would double runtime for a question nobody asked yet.
5. **Realized slippage** — per fill, T+1 open (pre-impact base) vs the decision-close
   mark, side-signed: positive = worse than paper. Reported over all fills AND over the
   realized book (fills belonging to completed round trips). Impact is inside the fill
   price already and reported alongside.
6. **Benchmark** — §11's 2026-09-26 constraint construction: equal-weight total-return
   index of the eligible universe from dividend-adjusted closes, monthly marks, as-of
   decision-month membership (a member without a mark yet sits at 1.0 = a cash slot).
   Replaced by a sourced Nifty 500 TRI when one exists.
7. **Determinism** — the full-profile run was executed twice (`--verify-determinism`);
   the serialized evaluations are asserted identical (§9.5).

## First run (full profile, cutoff 2026-09-24, 35 folds 2023-08-31 → 2026-06-30)

- Paper top-5% picks: 2,196, **56.6% hit** vs the 5% baseline (binomial p ≈ 0, CI95
  [0.545, 0.586]); mean gross +2.32%/pick, net-of-flat-cost +1.32%. The selection edge
  is real on the test window.
- Engine (§8 portfolio, 4 slots): 130 fills (1 non-fill, a circuit lock), 63 completed
  picks, pick hit 33%, month hit 40%, churn 1.66/mo, avg hold 45d.
- **Equity 489,703 from 1,000,000 (−51.0%), CAGR −22.3% vs benchmark +8.5%, Sharpe −0.38
  vs +0.50, max drawdown −65.2%.**
- Regime table (mean net per paper pick): down +3.17% (8 months), flat −1.06% (13),
  up +2.51% (14). Mean monthly IC: 0.0758 / 0.1267 / 0.0387.
- **Realized slippage: +0.441%/side on buys, −0.420%/side on sells** vs the decision
  mark (130 fills); realized book +0.176%/side.

## Reading — the harness works; the numbers are negative

The paper selection edge does NOT survive the §8 portfolio layer over the test window:
the same picks that average +1.32% net on paper produce a −51% realized equity at 4
slots. Candidate mechanisms (candidate, not concluded — this is the report the next
pre-registration must move):

- **Concentration:** 4 slots vs ~63 paper picks per fold month. The paper stat is a
  breadth statistic; the portfolio holds 4 names and eats idiosyncratic variance.
- **The adverse T+1 open:** +0.44%/side on buys, −0.42% on sells — E010's modelled ~0.14%
  impact was real but small; the overnight gap from decision close to next open is the
  larger, previously unmeasured component (momentum picks gap up into the entry).
- **Churn:** 1.66 replacements/month pulls flat costs through the book at 0.50%/side.

Per §10.3: any rule change motivated by this report archives this run, logs the change
in the ledger, and re-runs the full walk-forward from scratch. The per-fold and regime
tables in `runs/walkforward/harness_results.json` are where a proposed fix must show its
delta before it becomes a pre-registered experiment.

## Runbook

```
.venv/Scripts/python.exe -m src.walkforward.harness              # synthetic self-check
.venv/Scripts/python.exe -m src.selfcheck                        # 25 checks
# full-profile work needs the chain at FULL (the suite resets it to quick):
E007._build_chain(con, load("full"))                             # ~50s
.venv/Scripts/python.exe -m src.backtest.smoke_e2e               # pins: 3,902 picks
.venv/Scripts/python.exe -m src.walkforward.harness --profile full --verify-determinism
```
