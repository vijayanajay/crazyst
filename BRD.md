# BRD — NSE Monthly Top-Gainer Picker (Top-1500 Liquidity Universe)

| | |
|---|---|
| Version | 1.1 (universe: top 1500 by as-of liquidity) |
| Date | 2026-09-22 |
| Status | Draft |

## 1. Problem statement

Every month a handful of NSE large/mid cap stocks give the highest returns. We want to know if anything in price, volume, delivery, and structured event data (no sentiment analysis) can spot them **before** the month starts. We will run many small experiments, document each one, and keep only what survives honest testing.

## 2. Goal

- Build a repeatable system that, at each month-end, picks **4 stocks** for the next month.
- Measure how often those picks land in the month's top gainers, and how much money the 4-stock portfolio makes.
- Decide to **hold or sell** monthly, or mid-month when a better stock appears, or when a held stock is going down (or both).
- Find out honestly what works and what does not. A failed experiment that is well documented is a valid outcome.

### Success measures

With ~1500 eligible stocks and winners defined as the **top 5%** (≈75 stocks/month), 4 random picks per month produce a baseline hit rate of about 5%. That is the floor, not the goal. (Original design: top 20 of ~300 ≈ 6.7%. The ladder below is unchanged — winners scale as a percentage of the universe, never a fixed count.)

| Level | Pick-level hit rate* | Meaning |
|---|---|---|
| Reject | < 10% | Nothing learned, strategy useless |
| Minimum | 12–15% | Signal exists, roughly 1 hit in 2 months per slot |
| Target | 20–25% | ~1 of 4 picks lands in the winner set (top 5%) each month |
| Stretch | > 25% | Strong signal, likely regime-dependent |

\* hits ÷ total picks over the whole test window. Also report month-level hit rate: % of months with at least 1 hit. Top-20 hits (the original, harder label) and top-decile hits are reported alongside as secondary metrics.

Secondary measure: portfolio return vs a broad-market total-return benchmark (Nifty 500; Nifty 200 as large-cap reference). A high hit rate with negative returns is still a failure.

## 3. Scope

**In scope**

- NSE cash-market stocks (EQ series); universe = **top 1500 by as-of liquidity** (trailing 3-month median turnover, ranked as of each decision date). Small/mid caps enter by construction; the ₹20 price floor keeps penny stocks out.
- Free data only: NSE bhavcopy, delivery data, surveillance lists, bulk/block deals, SAST disclosures, corporate actions, index membership history, F&O OI (optional).
- Backtest + walk-forward engine, experiment ledger, reports.

**Out of scope**

- Sentiment analysis, news NLP, social media signals.
- F&O trading strategies (F&O data only as an input feature).
- Live trading. Output of this phase is a tested rule set, not a trading bot.
- Penny stocks (price < ₹20) and stocks below the as-of liquidity cutoff (rank > 1500). Small caps inside the universe are in scope and must be reported separately (size-bucket attribution, §11).

## 4. Definitions

- **Universe (as of date D):** the **top 1500 stocks by median daily turnover over the trailing 3 months, ranked as of D** from NSE bhav data, plus the filters below, all evaluated as of D. Never today's list applied to the past (survivorship bias). No external index membership is required; the Nifty 200 list is used only as an overlap reference in experiment E000.
- **Eligible stock:** in the as-of universe; EQ series; not in T2T/BE; not under GSM/ASM (as of D, where historical data exists); listed ≥ 6 months; price ≥ ₹20. All thresholds configurable. (Amended 2026-09-25: the original "₹5-crore-turnover floor is subsumed by the top-1500 rank" premise is measurably false — the rank-1500 boundary turns over ₹1.0–1.9cr/day and 30.8% of in-universe symbol-months sit below ₹5cr, including the 601–1500 bucket where the full-history IC sweep (E002b) measures its strongest confirmed signals. The floor therefore stays a config guard (`universe.min_median_turnover_cr`) shipped **off** (0.0); enforcing it needs a fresh decision by the BRD owner. Measurement is re-printed by the eligibility check on every run. Evidence: LEDGER "Phase 2 (M1) complete" and `experiments/002b_ic_sweep_full/`.)
- **Winner:** stock in the **top 5% by monthly return** among eligible stocks for a calendar month (≈75 of ~1500; the count scales with the eligible count, never a fixed number). Secondary labels: top decile, and top 20 (the original, harder target).
- **Monthly return:** adjusted close of last trading day of month M vs last trading day of month M-1.
- **Hit:** a pick that becomes a winner.
- **Test window:** last 36 months ending **yesterday**, recomputed every time the backtest runs.

## 5. Data requirements

| # | Data | Source (free) | Fields | From | Used for | Known risk |
|---|---|---|---|---|---|---|
| D1 | Daily bhavcopy | NSE archives (old format → Jul 2024, UDiFF format after) | OHLC, volume, series, trades | 2011 | candles, momentum, volume | Two formats; one normalizer |
| D2 | Delivery data | NSE `sec_bhavdata_full` / MTO | DELIV_QTY, DELIV_PER, turnover | 2011 | accumulation signals | Missing days; format drift |
| D3 | Corporate actions | yfinance adjusted `.NS` + NSE actions list | splits, bonus, dividends | 2011 | correct returns, clean candles | Cross-check both sources on a sample |
| D4 | Index membership (optional) | Nifty 200/500 historical changes; F&O underlying list history | constituent lists | 2011 | overlap reference for E000 only — not on the critical path | Press-release scraping; never block the pipeline on it |
| D5 | Surveillance | NSE GSM/ASM lists | stage, date | current only | tradability filter | No historical archive — see Risks |
| D6 | Bulk / block deals | NSE archives | buyer, seller, qty, price | 2011 | smart-money feature | Late 2023 format change |
| D7 | SAST / insider | NSE SAST archives, exchange disclosures | acquirer, % change | 2011 | event feature | Messy names; needs matching |
| D8 | Shareholding | BSE/NSE quarterly | promoter %, pledge %, FII % | 2011 | slow features | Quarterly, not monthly |
| D9 | F&O bhavcopy + OI | NSE derivatives archives | OI change, basis | 2011 | optional overlay | Large volume of files |

**Rules**

- All raw files cached locally as downloaded. Never re-download to re-process.
- Two config profiles: `quick` (last 12 months) and `full` (15 years). Self-checks, validation, and experiments default to `quick`; `full` is the deliberate act. Every reported number states which profile produced it.
- One normalizer per source → one DuckDB database. Every experiment queries it; no experiment reads raw files.
- A validation report must run on every data refresh: date coverage, per-stock gap count, cross-source price mismatch count, canary checks (see §13).
- Daily refresh job appends yesterday's files. The database is append-only.

## 6. Signal / feature requirements

All features must be computable from data dated **on or before** the decision date. Features are grouped; experiments test them one group at a time first, then combined.

| Group | Examples |
|---|---|
| Momentum | 1M, 3M, 6M, 12M-1M returns; return / volatility (Sharpe momentum); 52-week-high distance |
| Volume structure | volume z-score, up-volume / down-volume ratio, volume on up days vs down days, breakout volume confirmation |
| Delivery (India-specific) | delivery% level and 20-day z-score, delivery spike while price flat, delivery trend |
| Volatility state | NR7, squeeze days, range compression, ATR ratio |
| Candlestick (as features, not triggers) | close-in-range position, upper/lower wick ratio, consecutive higher lows, big-body day position in trend |
| Events (structured, no NLP) | bulk/block deal net buying, SAST insider buying, pledge change, promoter stake change |
| F&O (optional) | OI build-up with price, basis change |

Every feature gets a definition, a formula, and a unit test with one known-input/known-output case before it enters any experiment.

## 7. Selection: 4 stocks per month

1. On the **last trading day of the month**, after close, compute scores for all eligible stocks.
2. Rank and take the top 4 that are not already held, with a max of 4 positions total.
3. Positions are equal weight: 25% each.
4. Execution is **next trading day open**. The backtest never fills a trade at the close used to decide it.
5. If a chosen stock cannot be bought at T+1 open (circuit-locked, no traded volume), skip it and take the next-ranked stock. If none, hold cash.
6. The scoring model is whatever the current experiment defines — the portfolio rules in §8 are fixed so experiments stay comparable.

## 8. Portfolio rules: hold, sell, replace

All thresholds live in one config file with the defaults below. Experiments may tune them; defaults are what the walk-forward reports on.

All rank cutoffs are **percentiles of the eligible universe**, never absolute counts (with ~1500 stocks, absolute ranks are meaningless). The defaults below were calibrated for the original ~300-stock universe; before any walk-forward they must be re-tuned on pre-test-window data only.

### 8.1 Monthly review (last trading day, close)

- **Sell** a held stock if any of: it drops out of the eligible universe; its model rank falls below the top 25% of the universe; it stays below its 50-day average for 5 consecutive closes; or a replacement rule below says so.
- **Replace** a sold stock with the best-ranked available stock if that stock's rank is in the top 15% of the universe. Otherwise hold cash in that slot.

### 8.2 Mid-month checks (every Friday close, plus daily surveillance check)

**Trigger A — better stock found.** A new candidate's model score exceeds a held stock's score by more than 20% (relative). Sell the held stock at next open, buy the candidate at next open. Cap: **max 2 mid-month replacements per month** across the portfolio.

**Trigger B — stock going down.** Sell at next open if any of:
- Close falls 8% below entry price, **or** 12% below the month's high (trailing), whichever is hit first;
- Two consecutive closes below the 50-day average (early version of the monthly rule);
- Delivery% z-score < −2 for 3 consecutive days while price falls;
- Stock enters GSM/ASM stage 2 or higher (surveillance event = forced exit, no exceptions).

**Trigger C — both.** If A and B fire on the same stock, sell it and hold cash in that slot until the next monthly selection. Do not auto-buy the mid-month candidate from a Trigger A on the same day.

### 8.3 General

- No averaging down. No position added to.
- Every sell/replacement is logged with: date, trigger, score of sold and bought stock, prices used.
- Replacement count per month is a reported metric (churn). If average churn > 1.5 replacements/month, the rules are too twitchy — flag it in the report.

## 9. Backtest requirements

One engine. Every experiment uses it. The engine must:

1. Fill buys at T+1 open, sells at T+1 open after the signal. Never same-bar.
2. Apply costs: default 0.2% per side (brokerage + STT + slippage + impact), configurable.
3. Use adjusted prices for returns; note that adjusted volume differs from raw (document, don't silently mix).
4. Handle: suspensions (exit at first trade day price; if none within 5 days, mark at last close and flag), delistings (same rule), circuit limits (skip the fill), missing delivery data (feature degrades to NaN, never to 0).
5. Be deterministic: same inputs + same config → same outputs, to the rupee.
6. Record per-month: picks, entry prices, every sell with its trigger, exits, portfolio return, benchmark return, hit/miss per pick.
7. Report results at three cost levels — 0.2% (default), 0.5%, and 1.0% per side — as pre-registered sensitivity (E006). Rank-600+ names will not fill at 0.2%; the cheap-cost result alone is not evidence.

## 10. Walk-forward test requirements

This is the only result that counts. Single in-sample backtests are not evidence.

1. **Test window:** the last **36 months ending yesterday**, recomputed on every run. Example: run on 2026-09-22 → test window 2023-09-21 to 2026-09-21.
2. **Walk-forward loop, per test month M:**
   - Fit the model (features selected, thresholds, weights) using only data before M starts, with a 1-month purge gap between train end and M.
   - Trade M with the frozen model.
   - Move to M+1 and repeat. Refit happens every month.
3. **No peeking:** test-window data is never used for feature choice, hyperparameters, or rule thresholds. If a rule is changed after seeing test results, the old run is archived untouched, the change is logged in the ledger, and the full walk-forward is re-run from scratch.
4. **Report per-fold and aggregate** (see §11). A rule that wins only in bull months is reported as such.

## 11. Metrics and reports

**Per run (aggregate over test window)**

| Metric | Definition |
|---|---|
| Pick-level hit rate | hits ÷ picks |
| Month-level hit rate | months with ≥1 hit ÷ months |
| Portfolio CAGR | geometric, net of costs |
| Benchmark CAGR | Nifty 500 total return, same window (broad benchmark matching the 1500-stock universe; Nifty 200 reported alongside as the large-cap reference) |
| Sharpe (monthly) | mean monthly excess return ÷ std |
| Max drawdown | peak-to-trough on equity curve |
| Churn | replacements ÷ month |
| Average holding period | days per position |
| Per-regime table | months split by benchmark up/down/sideways |

**Statistical check.** Hit rate is tested against the random baseline p = 0.05 (winners = top 5% of eligible stocks, per month), with a binomial test. A result without p-value is not reported. With 36 months × 4 picks = 144 picks, report the confidence interval — a 20% hit rate on 144 picks has a wide one.

**Reports produced automatically**

- Equity curve vs benchmark (PNG + CSV).
- Monthly table: picks, returns, hits, triggers fired.
- Per-feature IC table (Spearman rank correlation of feature vs next-month return, per month and pooled).
- Size-bucket attribution (mandatory): picks bucketed by as-of liquidity rank — top 200, 201–600, 601–1500. Hit rate, return, and churn per bucket. A strategy whose edge lives only in the small bucket is reported as such, not blended away.
- Ledger entry (see §12).

**Canary checks (data validation, run with every refresh).** Known anomalies must reproduce or the pipeline is wrong: 6–12M momentum should have positive IC in this market; delivery% must correlate with its own lag for liquid stocks; total monthly eligible count must be stable within ±20% except at known universe-change dates. A failed canary blocks experiments from running.

## 12. Experiment process

- Folder per experiment: `experiments/NNN_name/` containing `hypothesis.md` (written **before** running: what is tested, expected direction, metric), `run.py`, `results.json`, and a short `verdict.md`.
- One `LEDGER.md` lists every experiment, its pre-registered prediction, and its verdict (confirmed / rejected / inconclusive). Predictions may not be edited after the run.
- 20 univariate tests will produce ~1 false positive by chance. The ledger and the walk-forward re-test are the defense.

## 13. Non-functional requirements

- Python + DuckDB + pandas/polars; no paid APIs; no new dependency without a written reason in the ledger.
- All thresholds, costs, and rules in one config file (YAML), versioned.
- Every run stores: config snapshot, code commit hash, data cutoff date, random seed.
- Data refresh is idempotent and re-runnable.
- Any machine with the repo + cached data can reproduce any reported number.

## 14. Milestones and acceptance criteria

| # | Milestone | Acceptance |
|---|---|---|
| M0 | Data pipeline | 15 years loaded; validation report passes all canaries; both bhavcopy formats normalized |
| M1 | Universe + labels | As-of top-1500 liquidity universe built from bhav data; monthly winner list (top 5%) for 15 years; spot-check 10 random months by recomputing from raw bhav files |
| M2 | Signal sweep | Every feature group tested univariate with IC tables; ledger entries for all |
| M3 | Selection model | Composite or learned ranker beats best single feature out-of-sample (pre-walk-forward validation slice) |
| M4 | Portfolio rules | Backtest engine passes the deterministic-replay test and the no-lookahead audit (trade log vs raw data) |
| M5 | Walk-forward | 36-month walk-forward per §10, full report, p-value, per-regime table |
| M6 | Paper phase | Rules run on live data for 1 month, decisions logged before results known |

## 15. Risks and constraints

| Risk | Mitigation |
|---|---|
| NSE blocks scraping | Cache everything; rate-limit; UDiFF/edge CDNs; fallback mirrors documented in repo |
| No historical GSM/ASM archive | Filter applies going forward; in backtest, flag suspicious movers (blow-off top + extreme volume) instead of hard-excluding; report sensitivity with/without |
| As-of liquidity universe approximates large/mid-cap membership | E000 overlap check vs Nifty 200; size-bucket attribution makes any small-cap dependence visible |
| Edge is mostly the small-cap liquidity/cost premium | Mandatory size-bucket attribution (§11); E006 cost sensitivity at 0.5%/1.0% per side; no strategy ships on blended numbers |
| Small sample: 144 picks | Always report confidence intervals; prefer month-level and pick-level metrics together; never claim significance without the binomial test |
| Winners are catalyst-driven | Accept: system detects pre-conditioning, not the catalyst. Target is beating the 5% baseline, not perfection |
| Regime dependence | Per-regime reporting is mandatory; no strategy ships on blended numbers alone |
| Overfitting via config tuning | All tuning on pre-test-window data only; §10.3 protocol; ledger discipline |
