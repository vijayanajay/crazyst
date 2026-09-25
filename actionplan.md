# Action Plan — NSE Monthly Top-Gainer Picker

Companion to `BRD.md`. Written for one developer. Follow the order unless a task says "parallel-safe". Every task ends with a runnable check — a task without a passing check is not done.

Universe note: we track ~1500 stocks via an as-of liquidity rank (top 1500 by trailing 3-month median turnover, computed from bhav data per decision date). Winners = top 5% of eligible stocks (BRD §4). No index-membership scraping on the critical path.

## Status (updated 2026-09-23)

Phases 0–2 are complete; every Phase 1/2 done-when is implemented and verified (audit + live
re-runs), and the selfcheck suite is green at **15/15 checks**. Evidence lives in `LEDGER.md`:
milestones **M2**, **M2.2**, **M2.3** and **"Phase 2 (M1) complete"**, which also record the
checkpoint artifacts (validation-report sign-off; the three winner lists vs re-computation).

Post-audit repairs (2026-09-23), all proven on live data: task 1.6's cross-check was dead code —
fixed (row unpacking, 0/0→NaN handling, date-index alignment, still-trading sampling,
recent-window comparison) and registered in the suite; the scheduler's `end_date` write was made
atomic then and has since been **removed at the root** — config no longer carries `end_date` and
the cutoff is the newest bhav date (LEDGER, 2026-09-25 refactor block); the daily-refresh gate
(agreement 1.0 on 105 pairs) and a full
backfill slice (638 rows, 99.8% vs NSE) were re-run through their real entry points.

Open items carried forward (none blocks a Phase 1/2 done-when):

- **₹5cr turnover floor** — BRD §4's "subsumed" premise is measurably false (enforcing it
  excludes ~31% of the universe); rule implemented, shipped OFF. Needs the BRD owner.
- Quality debt recorded in the ledger's "Open items for the next pass": `eligible()`'s
  connection/table dependency vs this plan's pure-function wording, the hand-synchronised
  `_CHECKS`/point-form rule pair, quarantine for malformed surveillance rows.
- **Phase 3 in progress**: tasks 3.1–3.5 implemented and verified; **E002 (3.7) has run** —
  verdict `partial` in the ledger (momentum 12M−1M confirmed, delivery z-score rejected,
  low-volatility state dominates). Open: 3.6 (E001 anatomy), 3.8 (E000 overlap),
  `experiments/001_anatomy/` still empty.

## Working rules (read first)

1. One config file (`config.yaml`) holds every threshold, path, cost, and date. No magic numbers in code.
2. Every experiment follows BRD §12: folder, pre-registered `hypothesis.md`, results, verdict. No exceptions, including "quick checks".
3. Every non-trivial module ships with one small self-check script (assert-based, no test framework). `python -m module_name` runs it.
4. Raw downloads are cached and never re-fetched if present. Deleting the cache is a deliberate act, done manually.
5. Any run must be reproducible: log config snapshot + git hash + data cutoff with results.
6. If a task takes more than 2 days, split it. Stop and report at each checkpoint below.

## Quick/full profiles

Two config profiles: `quick` = last 12 months, `full` = 15 years. Self-checks, validation, and experiments default to `quick` so iteration is seconds-fast; `full` is the deliberate act and is what produces reported numbers. Every reported result states its profile. The feature matrix is precomputed once per profile; experiments then run as SQL queries against it.

## Repo layout (build it in Phase 0, don't redesign later)

```
config.yaml
data/                  # raw cache + duckdb file (gitignored)
src/
  download/            # one module per source
  normalize/           # raw -> duckdb
  universe/            # membership, eligibility
  features/            # one file per feature group
  model/               # scoring / ranking
  backtest/            # engine + portfolio rules
  walkforward/         # harness + reports
  validate/            # canaries, data quality report
experiments/
  001_anatomy/         # hypothesis.md, run.py, results.json, verdict.md
  ...
LEDGER.md
```

---

## Phase 0 — Setup (0.5 day) — ✅ DONE

| # | Task | Done when |
|---|---|---|
| 0.1 | Repo skeleton per layout above; `requirements.txt` (python, duckdb, pandas or polars, requests, pyyaml, matplotlib); `.gitignore` with `data/` | `pip install -r requirements.txt` works; repo layout matches |
| 0.2 | `config.yaml` with: date range, universe definition (top-1500 as-of liquidity rank), eligibility thresholds, costs (with `quick`/`full` profiles), portfolio rule parameters as percentiles (BRD §4/§8), paths | File exists, every value referenced by later code comes from it |
| 0.3 | `LEDGER.md` created with table header | File exists |

**Checkpoint: nothing to show. Proceed.**

## Phase 1 — Data pipeline (M0) (4–5 days) — ✅ DONE 2026-09-22 (LEDGER M2/M2.2/M2.3; task 1.6 cross-check repaired and re-proven 2026-09-23)

Work in this order. Each task depends on the previous.

| # | Task | Details | Done when |
|---|---|---|---|
| 1.1 | Downloader: old bhavcopy | Monthly archive zips, 2011 → Jul 2024. Retry ×3, sleep between hits, skip-if-cached | `data/raw/bhavcopy_old/` filled; count of trading-day files matches expected (cross-check one month's file list vs NSE holiday list) |
| 1.2 | Downloader: UDiFF bhavcopy | Daily zips, Jul 2024 → yesterday | Same check for a recent month |
| 1.3 | Downloader: delivery data (`sec_bhavdata_full`) | Same span; note it starts ~2011 but has known missing stretches | Files cached; gap report printed |
| 1.4 | Normalizer: both bhavcopy formats → one table | Map old + UDiFF columns to one schema: symbol, series, date, OHLC, volume, trades. One mapping file per format, one output schema | `SELECT count(*), count(DISTINCT date) FROM bhav` sane; spot-check 5 random dates across the format boundary give same symbol set (±new listings) |
| 1.5 | Normalizer: delivery → `delivery` table | symbol, date, deliv_qty, deliv_per | Join to bhav on symbol+date mismatches < 1% |
| 1.6 | Corporate actions / adjusted prices | yfinance `.NS` adjusted closes for all symbols; store `adj_close` table. Keep NSE raw prices untouched | Cross-check: for 20 random symbols, NSE close and yf close match on ≥95% of overlapping days (else symbol-mapping bug) |
| 1.7 | Validation report (`src/validate/report.py`) | Coverage per year, per-symbol gap counts, price-mismatch count, missing-delivery % | One command prints report; exits non-zero if coverage below config threshold |

**Self-check:** `src/validate/canary.py` — BRD §11 canaries (momentum IC positive, delivery% autocorrelates, eligible count stable). Must pass before Phase 3 runs.

**Checkpoint: show the validation report. Get sign-off before continuing.**

## Phase 2 — Universe + labels (M1) (2–3 days) — ✅ DONE 2026-09-23 (LEDGER "Phase 2 (M1) complete")

| # | Task | Details | Done when |
|---|---|---|---|
| 2.1 | As-of universe rank | Pure SQL over bhav data: trailing 3-month median turnover per symbol, ranked as of each decision date, top 1500. No external index data | Rank for 5 hand-picked dates printed; ranks stable month-over-month except at real liquidity shifts; runtime minutes, not hours |
| 2.2 | Eligibility function | BRD §4 rules as a pure function `eligible(symbol, date) -> bool` from config | Unit check: 6 hand-built cases (T2T stock, low turnover, recent listing, GSM-flagged, rank>1500, normal) all behave correctly |
| 2.3 | Monthly winners table | Top 5% per month by adjusted return (plus top-20 and top-decile secondary labels), per BRD §4 | Spot-check 10 random months by recomputing from raw bhav files (no public site lists market-wide gainers); 10/10 match |

**Checkpoint: show 3 winner lists side by side with re-computation from raw files.**

## Phase 3 — Feature library + univariate sweep (M2) (4–5 days)

| # | Task | Details | Done when |
|---|---|---|---|
| 3.1 | Feature framework | Panel-wide computation: one DuckDB `CREATE TABLE AS` with window functions ordered by date — past-only by construction, no per-symbol-month Python calls | ✅ Implemented in `src/features/panel.py`; one CTAS computes monthly momentum (1M/3M/6M/12M−1M) over the existing panels; synthetic hand-values, calendar gaps, NULL/empty inputs, future-isolation, and live quick-profile build pass; registered self-check (`src.features.panel`) passes |
| 3.2 | Momentum group | BRD §6 momentum features | Each has a hand-computed test case |
| 3.3 | Volume + delivery group | BRD §6 volume structure, delivery features | ✅ Implemented in `src/features/panel.py` (same CTAS as 3.1): volume z-score, 20-session up/down volume split + ratio, breakout-with-volume confirmation, delivery% level/z-score/20-session trend, delivery-spike-while-flat; windows ride the EQ session calendar so absent sessions NULL rather than shift lags; synthetic hand-values (up-volume 95/down 144, both z-scores), missing-session/-delivery, future-isolation and live build pass |
| 3.4 | Volatility + candle group | BRD §6; candles as features, not triggers | ✅ Implemented in `src/features/panel.py` (same CTAS): ATR ratio (14-session adjusted TR / close), NR7, squeeze days (TR below the configured fraction of its own prior-20 mean), 20-session range compression, close-in-range position, upper/lower wick ratios, consecutive-higher-lows streak, big-body-day-in-trend — all on adjusted OHLC (split-safe), all completeness-gated (TR windows need a prior close, so `source_days` warms up one extra session); synthetic hand-values (ATR 7/112 and 7/104 and 7/125, NR7 with a tie, squeeze 1, 13/14 close-in-range, 20-session higher-low streak), missing-session NULLing, future isolation and live build pass |
| 3.5 | Feature matrix build | One table: symbol, month, all features, next-month return, is_winner (top 5%), plus liquidity rank and size bucket (top 200 / 201–600 / 601–1500) | ✅ Implemented in `src/features/matrix.py`: `feature_matrix` = feature_panel LEFT-joined to as-of rank and to the FORWARD label — `winners` rows are keyed by the date their return ends at, so decision D's label is read at the NEXT decision date (lead over the decision calendar); unmeasured forward months stay NULL, never False. Row count = eligible symbol-months, no duplicate keys, all buckets populated, 5.0% winner rate live; synthetic checks prove the forward direction (the +30% month read from its prior decision row), per-month as-of buckets, last-month NULLs and schema completeness |
| 3.6 | **Experiment 001 — anatomy of winners** | Hypothesis: winners differ from rest on momentum/delivery features. Output: feature distribution table winners vs rest, per regime | `hypothesis.md` written and committed BEFORE `run.py` executes; results + verdict in ledger |
| 3.7 | **Experiment 002 — univariate IC sweep** | Spearman IC per feature per month + pooled; top-5% precision vs 5% baseline; Benjamini–Hochberg correction across the ~20 features | ✅ Ran per BRD §12: `experiments/002_ic_sweep/hypothesis.md` (pre-registered directions for all 22 features, written before the run) → `run.py` (per-month + pooled Spearman via `src.stats`, exact t-tail p, top-5% precision, BH) → `results.json` (config/git/cutoff snapshot) → verdict + ledger block. Result: **partial** — mom_12m_1m confirmed (+0.065, BH-surviving), delivery z-score and mom_6m rejected on direction, low-volatility state is the sweep's dominant signal |
| 3.8 | **Experiment 000 — universe overlap** | Hypothesis: the as-of top-1500 liquidity universe approximates the large/mid-cap intent. Output: per-year overlap with Nifty 200 constituents, hit-rate delta if winners were computed on the Nifty-200-only universe | Overlap table in ledger; E000 verdict decides whether index membership is ever needed |

**Checkpoint: present IC table + anatomy findings + E000 overlap. Expect some priors to die here — that is the deliverable.**

## Phase 4 — Selection model (M3) (3–4 days) — *parallel-safe from 3.5 with Phase 5*

| # | Task | Details | Done when |
|---|---|---|---|
| 4.1 | Composite score v0 | Rank-average of the 3–5 features that survived E002, weights fixed in config | Beats best single feature on pre-test-window validation slice (pre-registered in hypothesis.md) |
| 4.2 | Learned ranker | Gradient boosting with rank objective (scikit-learn / lightgbm — justify dependency in ledger) trained walk-forward style on pre-window data | Same bar as 4.1; if it loses, ledger says so and composite ships |
| 4.3 | Model freeze protocol | Model + weights + feature list saved with each run | Re-running an old run with its saved artifacts reproduces its picks exactly |
| 4.4 | **Experiment 006 — cost sensitivity** | Pre-registered: re-score picks at 0.2% / 0.5% / 1.0% per side on the validation slice. Rank-1200 names will not fill at 0.2% | Ledger row with all three cost levels; sets the report's default cost assumption |

**Checkpoint: compare v0 vs ranker on the validation slice. Pick one. Document why.**

## Phase 5 — Backtest engine + portfolio rules (M4) (4–5 days)

Build against **synthetic data first** so it never waits on the pipeline.

| # | Task | Details | Done when |
|---|---|---|---|
| 5.1 | Engine core | BRD §9 rules: T+1 open fills, costs, no same-bar fills, deterministic | Deterministic-replay check: two runs on same inputs → identical trade logs to the rupee |
| 5.2 | Edge cases | Suspension, delisting, circuit lock, missing delivery data | Each case has a synthetic-data test that asserts the documented behavior |
| 5.3 | Portfolio rules | BRD §8: monthly review, Trigger A/B/C, churn cap, cash slots | Rule unit tests: one test per trigger with a hand-built price path |
| 5.4 | No-lookahead audit script | Recompute every pick from data available at decision date; assert match | Audit passes on a 12-month synthetic run and later on real data |
| 5.5 | Trade log + metrics | BRD §11 metric set from the log | One function produces all metrics from a trade log; checked against hand-computed toy portfolio |
| 5.6 | Size-bucket attribution | Split picks by as-of liquidity rank: top 200 / 201–600 / 601–1500; hit rate, return, churn per bucket | Bucket table present in the report pack; blended-only reporting fails review |

**Checkpoint: run engine on synthetic data with a trivial "buy momentum" model. Show equity curve + trade log.**

## Phase 6 — Walk-forward harness + reports (M5) (3–4 days)

| # | Task | Details | Done when |
|---|---|---|---|
| 6.1 | Walk-forward loop | BRD §10: monthly refit, 1-month purge, test window = last 36 months ending yesterday, recomputed per run | Window boundaries printed; refit never sees test month (assert in code) |
| 6.2 | Run protocol | §10.3: config change after seeing results → archive old run dir, append ledger note, full re-run | Demonstrated once on purpose |
| 6.3 | Reports | Equity curve PNG+CSV, monthly pick table, IC table, per-regime table, size-bucket attribution (5.6), binomial test + CI vs 5% baseline | One command produces the full report pack from a run dir |
| 6.4 | **The run** | Full walk-forward of the chosen model on real data | Report pack generated; hit rate, p-value, CI, per-regime table all present; verdict written in ledger regardless of outcome |

**Checkpoint: this is the project's first real answer. Present the full report, including confidence interval, honestly.**

## Phase 7 — Experiments batch + paper phase (M6) (ongoing, ~2 days setup + 1 month calendar)

| # | Task | Details | Done when |
|---|---|---|---|
| 7.1 | Event overlays | E003 bulk/block deals, E004 SAST disclosures, E005 F&O OI (optional) as separate experiments per BRD §12 | Each has its own ledger row and walk-forward delta vs the base model |
| 7.2 | Rule tuning (bounded) | Rank thresholds (§8 percentiles) and mid-month trigger thresholds swept on pre-window data only; churn reported | Chosen percentile values logged with the sweep results; churn metric reported |
| 7.3 | Paper phase | Run rules live: score at month-end, log intended picks + triggers before results known, compare after | 1 month of decisions logged in advance; divergence between paper log and what backtest would have said = 0 |
| 7.4 | Final writeup | What works, what doesn't, ceiling estimate, next-phase proposal | Written in LEDGER.md verdict section |

## Dependency map

```
Phase 0 ──> Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4 ──┐
                │                       │                  ├──> Phase 6 ──> Phase 7
                └───────────────────────┴──> Phase 5 ──────┘
```

Phase 5 starts after 3.5 exists (needs feature matrix for refits) but is built on synthetic data and can run alongside Phase 4.

## Self-check runner

One small command (stdlib only) imports each module's `python -m` self-check, prints `PASS/FAIL` + elapsed per check, exits non-zero on first failure. Default profile `quick`. Every assert carries a message (`got X, expected Y`) so failures are self-explaining; `--verbose` prints per-month rows.

## Total estimate

~21–27 working days for one developer, excluding calendar time for the paper phase.

## Explicit non-goals during this plan

- No live broker integration. No dashboard. No sentiment/NLP. No strategy claims without a p-value. Do not "improve" the portfolio rules mid-walk-forward — file it as an experiment instead.
- No index-membership scraping during this plan; E000 decides if it is ever worth adding.
