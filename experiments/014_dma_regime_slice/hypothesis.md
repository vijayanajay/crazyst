# E014 — the risk-off buy-block on the validation slice: does the signal travel across episodes?

Written BEFORE any run (BRD §12). E013 measured the shelved index regime filter on the
harness's 35-month realized window and found the actionable core is the **buy block**, not
the liquidation (the review's own exits had already emptied the book whenever the gate
fired; block-buys-only outran go-to-cash by Rs 2,925). E013's weakness is sample size: 8
gated intervals, one 2024-25 correction, one re-entry lottery — the gate's 8 intervals were
even *better* than average in the baseline (−0.19% vs −0.54%), so the +4.8 pp gain was as
much path as signal. This experiment asks the premise question the test window cannot
answer: **across the validation slice's diverse episodes (2011 euro crisis, 2013 taper,
2015-16 China/oil, 2018 IL&FS, 2020 COVID, 2022 rates), does blocking new entries in
risk-off months help the realized engine, consistently?**

This is a premise test on pre-test-window data only (BRD §10.3 / §12's discipline). It
cannot authorize adoption — E013 already burned the test window for this rule family — but
it can confirm or kill the signal's cross-episode claim before anyone spends fresh
out-of-sample data on it.

## Window (frozen)

P4.1's validation slice, recomputed from the DB cutoff by `P41.split_slice` (the last 36
months are excluded and untouched): **145 decision months, 2011-07-29 → 2023-07-31**
(boundary 2023-09-24). The chain is rebuilt through E007's real builder at the full profile
before measurement (the selfcheck suite can reset it to quick).

## Signal (fixed before the run — construction, not results)

Same construction as E013, recomputed here with the warm-up made explicit: daily NIFTY 200
TRI (`index_tri`) vs its own 200-session DMA at each decision month-end, prints ≤ M only;
risk-off iff `tri(M) <= dma200(M)`; decisions at M's close, fills at T+1 by the engine's
existing protocol. The index series starts 2011-01-03, so the DMA needs 200 prints to warm:
the first warmed fold is **2011-10-31** and the three folds before it (2011-07-29,
2011-08-30, 2011-09-30) are **risk-on by construction** — a filter with no history cannot
fire, and pretending otherwise would be look-ahead. Measured state: **35 risk-off folds**
out of 142 warmed, spread 2011:3, 2012:2, 2013:4, 2015:5, 2016:4, 2018:3, 2019:4, 2020:5,
2022:3, 2023:2.

## Arms (fixed before the run)

The harness's own engine pass (`smoke_e2e._engine_pass`, the `regime_off` hook) over the
145-month slice at the shipped config, one pass per arm, same tape:

- **BASELINE (guard arm):** gate inert. Its first 12 months MUST reproduce the persisted
  `runs/smoke_e2e/smoke_results.json` escalate arm's curve / fill_log / decisions /
  month_rows **bit-for-bit** (same tape, same config, the 12-month pass is the 145-month
  pass stopped early), AND the slice's total pick-months MUST equal E012's committed 4,579
  with the mean monthly IC equal to E012's 0.375-arm IC to 1e-9. No comparison is valid
  without these.
- **BUY_BLOCK (primary):** in each risk-off fold, new buys are blocked (review replacements
  and all-cash initial selection); holdings ride their own exits. E013's actionable core.
- **CASH (secondary, diagnostic only, no verdict):** BUY_BLOCK plus liquidation of every
  held position at risk-off month-ends (trigger `regime`). Tests E013's small-sample claim
  that the liquidation leg adds nothing, on a slice with a real crash (2020-03) in it.

No sweep. No config, engine, model, portfolio or harness change.

## Primary statistic and decision rule (fixed before the run)

For each fold i, the interval ending at fold i+1 (the engine's monthly mark-to-mark
return). An interval is **gated** iff fold i's state is risk-off (the decision at fold i
governs the book through fold i+1); un-warmed folds are risk-on. Define
`d_i = baseline_interval_return − arm_interval_return` over gated intervals (positive =
the baseline did worse than the arm, i.e. blocking entries helped).

- **B1 (whole slice):** mean(d) > 0 with a one-sided paired t-test p < 0.05
  (`src.stats.t_sf_two_sided` on the one-sample t of d, halved for the pre-registered
  direction), n ≥ 10 gated intervals.
- **B2 (episodes):** six pre-named episodes — 2011_euro (2011-07..12), 2013_taper
  (2013-05..09), 2015_16_china (2015-08..2016-03), 2018_ilfs (2018-09..12), 2020_covid
  (2020-02..05), 2022_rates (2022-01..06). Episodes with ≥ 3 gated intervals count
  (expected: 5 — 2018_ilfs has 2 and is reported, not counted); B2 requires at least
  ceil(2/3 × counted) episodes with mean(d) > 0 and at least 3 counted episodes (5
  counted → 4 of 5 must be positive: at most one episode may be against).

**Verdict mapping:** `INADEQUATE` if total gated intervals < 10; else `CONFIRMED` if B1
AND B2; `PARTIAL` if exactly one; `REJECTED` if neither.

**Reported, never load-bearing:** per-arm full-slice equity / total return / CAGR / Sharpe
/ maxDD / fills / picks / hit / churn; the per-episode table (months, gated intervals,
mean(d), sum(d)); the placebo — mean(d) over **ungated** intervals, where the gate did not
fire (expected ≈ 0; path carry-over after a gated episode is disclosed, not hidden); the
CASH diagnostic; the risk-off month list; the signal sanity recompute (every warmed fold's
DMA recomputed in Python from that date's own trailing 200 prints).

**Reading rule (declared up front):** CONFIRMED means the signal's premise travels across
episodes — a licence to spend fresh out-of-sample data on the rule, nothing more. It is
not adoption: adoption still needs a live/future pre-registered window (the test window is
burned), the config/harness wiring, and the standard ledger/BRD bookkeeping. REJECTED
closes the index leg for good; PARTIAL means the signal works in some regimes only and
needs an episode-conditioned theory before another test.

**Consequences.** Any verdict amends the BRD §15 risk row's E013 amendment with the slice
numbers + verdict, and gets a LEDGER block. No config change in any case.
