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
- **Universe re-cuts (amended 2026-09-26):** proposals to move the as-of cutoff (e.g. top 1000, per the Phase 3–6 review `fixissues_phase36.md`) are **BRD-owner decisions, not config edits**. Every committed experiment result (E000–E006, P4.1–P4.2) is measured on top-1500; the confirmed ICs concentrate in the 601–1500 bucket (E002b), which a cut to 1000 removes entirely. Adopting a cut requires the config change plus the §4 invariant in `src/config.py`, `size_buckets` relabeling, a full experiment re-run, and a new ledger row — i.e. a pre-registered experiment trading measured edge for a liquidity thesis. Until such a decision, **top 1500 stands**. (E007, 2026-09-26: the cut was pre-registered, run, and **rejected** — top-1000's mean monthly IC 0.0695 vs 0.0681 is paired-t noise (t = −0.57, p = 0.57); its +1.0pp precision costs 57,226 symbol-months (−26%) of the evidence base; and it does not even buy tradability — the below-₹5cr share only falls 62.8% → 50.1%, half the top-1000 still trading under ₹5cr/day. Closed with evidence; any re-open starts from the 2026-09-26 E007 ledger row, not the thesis.)
- **Eligible stock:** in the as-of universe; EQ series; not in T2T/BE; not under GSM/ASM (as of D, where historical data exists); listed ≥ 6 months; price ≥ ₹20. All thresholds configurable. (Amended 2026-09-25: the original "₹5-crore-turnover floor is subsumed by the top-1500 rank" premise is measurably false — the rank-1500 boundary turns over ₹1.0–1.9cr/day and 30.8% of in-universe symbol-months sit below ₹5cr, including the 601–1500 bucket where the full-history IC sweep (E002b) measures its strongest confirmed signals. The floor therefore stays a config guard (`universe.min_median_turnover_cr`) shipped **off** (0.0); enforcing it needs a fresh decision by the BRD owner. Measurement is re-printed by the eligibility check on every run. Evidence: LEDGER "Phase 2 (M1) complete" and `experiments/002b_ic_sweep_full/`.) (Amended 2026-09-26, E009: that fresh decision happened — the floor is now **enforced at 0.75**, deliberately not BRD's literal ₹5cr. The E006 fill gate refuses a buy when notional > 5% of trailing-20-session median turnover: at the shipped ₹250k/slot, 38.8% of pick-months — 50.5% of gross pick return mass — were unenterable, and the refused picks were the model's best (+4.05% vs +2.52%). The 0.75cr floor (the gate's ₹0.5cr boundary × the measured med20/med3 shrinkage — chosen by arithmetic, not fitted) cuts refusal to 1.5%, improves the reachability-corrected pick mean (+2.52% → +2.61%), and leaves the IC unchanged (0.0675 vs 0.0681, paired t = −0.12). Measurement still re-printed by the eligibility check every run. Evidence: `experiments/009_fill_gate_reach/`, the 2026-09-26 E009 ledger block, and the Decision 2 update in `docs/brd_decisions_universe.md`.) (Further amended 2026-09-26, E012: the floor is **derived, not fitted** — it must move with the gate boundary, which scales with per-slot notional (med20 ≥ 20 × S). E011's 8-slot adoption halved S to ₹125k (boundary 0.25cr), and E012 re-derived the floor through the same construction (boundary × the same 1.5× headroom): **0.375**. Guards: E009's R1 rows bit-identical, restore IC = P4.1b frozen, the 0.75 arm = E009's R2 verbatim; the 0.375 arm keeps refusal at 1.14%, corrected pick mean +2.692% vs +2.632% at 0.75, IC 0.0717. Re-derive the floor on any future notional change; it is not a tuning knob. Evidence: `experiments/012_floor_at_8slots/`, the 2026-09-26 E012 ledger block.)
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

## 7. Selection: 4 stocks per month (Amended 2026-09-26, E011: 8 stocks)

1. On the **last trading day of the month**, after close, compute scores for all eligible stocks.
2. Rank and take the top 4 that are not already held, with a max of 4 positions total. (Amended 2026-09-26, E011: the max is now **8 positions** — see rule 3's amendment.)
3. Positions are equal weight: 25% each. (Amended 2026-09-26, E011: equal weight across free slots with **8 slots** — `portfolio.n_slots: 8`. The Phase 6.1 walk-forward harness isolated the realized −51% as **concentration, not selection**: 8 slots recovered Rs 402,923 of the Rs 510,297 loss (489,703 → 892,626; maxDD −65.2% → −23.9%; Sharpe −0.38 → −0.29) with the completed-pick hit rate unchanged (33% → 32%), clearing all four pre-registered bars; 12 slots cleared them too but lost to 8 on final equity, and the churn-control arm ruled the churn rise a slot artifact. Evidence: `experiments/011_slot_count/`, the 2026-09-26 E011 ledger block. Note the review's original proposal bundled slot expansion with volatility-inverse sizing — E011 adopts the count change ALONE; sizing stays equal-weight.)
4. Execution is **next trading day open**. The backtest never fills a trade at the close used to decide it.
5. If a chosen stock cannot be bought at T+1 open (circuit-locked, no traded volume), skip it and take the next-ranked stock. If none, hold cash.
6. The scoring model is whatever the current experiment defines — the portfolio rules in §8 are fixed so experiments stay comparable.

## 8. Portfolio rules: hold, sell, replace

All thresholds live in one config file with the defaults below. Experiments may tune them; defaults are what the walk-forward reports on.

All rank cutoffs are **percentiles of the eligible universe**, never absolute counts (with ~1500 stocks, absolute ranks are meaningless). The defaults below were calibrated for the original ~300-stock universe; before any walk-forward they must be re-tuned on pre-test-window data only.

(Amended 2026-09-26, per the Phase 3–6 review: this re-tuning gate is also why the review's structural risk proposals — ATR-based volatility stops replacing the flat 8% stop (§8.2), and expanding 4 slots to 8–10 with volatility-inverse sizing (§7) — are **not adopted as defaults**: each changes every drawdown, churn and turnover number the walk-forward reports, and bundled together they are unattributable. They are sequenced as individually pre-registered arms on the Phase 6 harness; the four-stock equal-weight design stands until one wins its gate. One exit rule DID change as a decided recommendation (Decision 3): the default `exit_gate` is now `escalate` — a stop the fill gate can veto indefinitely is not a stop (`docs/brd_decisions_universe.md`).) (Further amended 2026-09-26, E011: the slot half of that sentence has now run its pre-registered arm and WON its gate — count only, 4 → 8, sizing still equal-weight; the volatility-inverse-sizing half remains unadopted and untested.) (Further amended 2026-09-27, E015: the sizing half has now been tested and **rejected** on the validation slice — volatility-scaled (equal-risk) slot sizing is a bet against the composite's own alpha concentration. At unchanged average exposure (mean-1 equal-risk, the exposure contract held to −0.49pp of mean invested share) it made both axes worse: −1.9pp of drawdown severity and −1.6pp CAGR. The de-risk-only cap — the same σ information, clipped downward, average exposure 1.5pp lower — captured 17.8% of the regime filter's relief (3.4pp of E014's 19.07pp) with CAGR 0.2pp better: the relief scales with exposure *actually removed*, not with how the same exposure is distributed. `portfolio.n_slots: 8` stands; sizing stays equal-weight. Evidence: `experiments/015_exposure_sizing/`, the 2026-09-27 E015 ledger block.)

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

(Amended 2026-09-26, E008b: a breadth-tightened trail on this layer — the E008a gauge sampled daily/weekly, wired to Trigger B only — was pre-registered and **rejected**: max drawdown identical to baseline in both pre-named stress windows; the single gate fire landed in the rebound, after the crash. The config keys remain (`portfolio.midmonth.trigger_b_breadth_*`) but ship **OFF and inert**; do not re-propose without new evidence. See the 2026-09-26 E008b ledger block.)

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
7. Report results at three cost levels — 0.2%, 0.5%, and 1.0% per side — as pre-registered sensitivity (E006). Rank-600+ names will not fill at 0.2%; the cheap-cost result alone is not evidence. (Amended 2026-09-26: the shipped default is E006's Phase 6 finding — 0.5% per side (`backtest.cost_per_side_pct`), all three levels still reported; the original 0.2% default was measured optimistic. Re-measured on the post-E009 floor universe (E010, 2026-09-26): the 0.5% default is **confirmed with a mechanism** — E006's flat 0.5% was almost exactly the mean modelled impact of the untradable tail (0.565%/side), which the fill gate refuses; the tradable book's picks carry 0.139%/side, so the honest stack is flat costs plus impact ≈ 0.5%. The 1.0% stress level binds the >600 tail harder post-floor (its edge halves there) — deep-cost reporting matters more, not less.)

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
| Benchmark CAGR | Nifty 500 total return, same window (broad benchmark matching the 1500-stock universe; Nifty 200 reported alongside as the large-cap reference). (Sourced, 2026-09-27: Nifty 500 TRI as the benchmark and Nifty 200 TRI as this large-cap reference, both via niftyindices.com's historical-data API (src/download/nifty_tri.py, raw cache data/raw/nifty_tri/<index>/, table index_tri, 2011 -> cutoff); the harness prefers the 500 and falls back to the EW adj-close proxy only when the table is absent. The proxy remains the documented fallback construction.) |
| Sharpe (monthly) | mean monthly excess return ÷ std |
| Max drawdown | peak-to-trough on equity curve |
| Churn | replacements ÷ month |
| Average holding period | days per position |
| Per-regime table | months split by benchmark up/down/sideways. (Amended 2026-09-26: breadth-regime splits are also available — the validated `market_breadth` (month-end) and `market_breadth_daily` (per-session) derived tables; E008a/E008b rejected both as gates but kept them for exactly this reporting. Amended 2026-09-27: computed under both sourced indices — the Nifty 500 benchmark and the Nifty 200 large-cap reference (`regime_table`, `regime_table_nifty200`) — and over the 35 test months the two label every month identically at the pre-registered ±2%/month band (same table), so the per-regime conclusions do not depend on which index defines the regime; off the band the buckets move, and at 2.5%/1.5% the two indices even disagree on Jan-2025 (−3.47% vs −2.46%) / Dec-2024 (−1.37% vs −1.61%) — the band is pre-registered for this reason.) |

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
| Edge is mostly the small-cap liquidity/cost premium | Mandatory size-bucket attribution (§11); E006 cost sensitivity at 0.5%/1.0% per side; no strategy ships on blended numbers. (Amended 2026-09-26, E009: the concentration is measured, not hypothetical — at the shipped slot size 38.8% of pick-months (50.5% of gross return mass) were unenterable and the refused picks were the best ones; the ₹0.75cr floor now excludes the untradable tail upstream, and the honest corrected pick mean is +2.52%, not the paper +3.11%) |
| Small sample: 144 picks | Always report confidence intervals; prefer month-level and pick-level metrics together; never claim significance without the binomial test |
| Winners are catalyst-driven | Accept: system detects pre-conditioning, not the catalyst. Target is beating the 5% baseline, not perfection |
| Regime dependence | Per-regime reporting is mandatory; no strategy ships on blended numbers alone |
| Proposed regime filter (Nifty 200 vs 200-DMA, India VIX) | Index/VIX series are not in the free-data plan (§5). The question is now closed at all three decision layers with evidence: P4.1 rejected the trailing-market regime overlay (diluted the composite, p = 0.0033); E008a rejected the own-data monthly breadth gate (ρ = +0.144 < the 0.15 bar — the low-breadth months are the BEST pick months: troughs mark rebounds); E008b rejected the same gauge intra-month on the Trigger-B layer (drawdown identical to baseline in both stress windows; the only fire landed in the rebound). The validated breadth gauges survive as per-regime reporting inputs (§11). Re-open needs a genuinely new data source or cadence, pre-registered. Amended 2026-09-27: blocker (a) is dead for the index leg — daily NIFTY 200 TRI 2011→cutoff now lives in the repo (`index_tri`, `src/download/nifty_tri.py`) — and E013 measured the filter itself on the realized 35-month window: risk-off in 9/35 months; both the go-to-cash and the block-new-buys arms clear the pre-registered CAGR/drawdown/Sharpe bars (CAGR −4.29%/−4.18% vs shipped −6.14%; drawdown severity 19.6% vs 23.0%; Sharpe −0.24/−0.23 vs −0.43), and the gain survives forcing its hair-trigger month (2024-12-31, 10 bp below its DMA) risk-on (+1.5 pp CAGR, −2.5 pp drawdown). NOT adopted: the test window is burned for this rule family (§10.3), the attribution is a small-sample timing result (the gate's 8 intervals were *better* than average in the baseline; a −7.2 pp re-entry interval offsets the avoided Jan/Feb-2025 losses), and VIX still has no data path. LEDGER E013 has the numbers; adoption needs a fresh pre-registered out-of-sample. E014 then ran that premise test on the 145-month validation slice (test window untouched) and REJECTED it: the gate's 35 risk-off intervals were BETTER for the baseline than the 109 it left alone (+0.754% vs −0.026%/month engine return, one-sided p(gate helps) = 0.65) and only 3/5 counted episodes favored the gate; the arm's whole-slice equity advantage (Rs 1,108,821 vs 942,030, maxDD −46.5% vs −65.6%) traces to exposure/variance-drag on a tape whose own drag dominates (arithmetic +0.164%/month, sd 6.29%, geometric −0.041%/month), not to timing. The index leg is closed; no config change; see LEDGER E014. |
| Sector-concentration caps assume point-in-time sector membership | No historical sector/industry source exists in the plan (§5); today's classifications applied as-of are survivorship-biased for a 15-year backtest. Add a point-in-time feed first, or pre-register a rolling-correlation-cluster cap as the data-free proxy |
| Overfitting via config tuning | All tuning on pre-test-window data only; §10.3 protocol; ledger discipline |
