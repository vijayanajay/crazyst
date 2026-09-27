# Data dictionary & pin map

2026-09-27. What every table/artifact is, and where each pinned number lives. Companion to
`docs/program_report.md`. Database: `data/duckdb/quant.duckdb` (full profile cutoff
2026-09-24; test window 2023-08-31 → 2026-06-30, spent by E020-C).

## 1. DuckDB tables

| table | what | notes |
|---|---|---|
| `bhav` | NSE EOD quotes (old + UDiFF formats unified), series EQ | cols: symbol, series, date, OHLC, prev_close, last, volume, turnover, trades, **isin** (no company names — tickers only) |
| `delivery` | NSE delivery (MTO + sec_bhavdata_full) | deliv_qty, deliv_per; 7 corrupt-source days healed (M2) |
| `adj_close` | yfinance adjusted closes per EQ symbol, `source` column marks repairs | 1,066 of 4,052 symbols have zero coverage (delisted; E018's G0 universe finding); 7 Yahoo-less sessions derived from bhav (repair block) |
| `adj_me` | month-end adjusted closes (panel input) | derived from adj_close |
| `deliv_me`, `liq_daily20`, `liq_me` | month-end delivery / 20-day liquidity panels | universe ranking inputs |
| `universe_rank` | rolling liquidity rank per symbol-month | as-of top-1500 universe (E000/E007) |
| `eligible` | the as-of eligible snapshot (symbol, mdate, eligible) | the only membership any scorer may read at decision date D |
| `winners` | next-month top-5% labels (BRD definition) | label side of the training matrix |
| `feature_panel` | 22 features per eligible symbol-month (src/features/panel.py) | momentum ×4, volume ×5, delivery ×4, volatility/candle ×9; SQL-CTAS, windows end at D, NULL not zero |
| `feature_matrix` | the scored matrix: **(mdate, next_month_ret, …22 PANEL_FEATURES…, liquidity_rank, symbol, size_bucket)** | the row-tuple layout EVERY scorer consumes (`model.score_month_2f`, E018's builders, prospective designs); labeled rows = 161,942; 180 labeled decision months 2011-07-29 → 2026-06-30 |
| `month_grid` | decision calendar | derived |
| `index_tri` | sourced Nifty 500 + Nifty 200 TRI, month-end capable (src/download/nifty_tri.py) | index_name ∈ {'NIFTY 500','NIFTY 200'}; 2011-01 → current |
| `index_events` | NSE inclusion/exclusion events (src/download/index_events.py) | index_name ('Nifty 500' sheet = 2,495 events 1998-08-01 → 2020-09-14), date, company, symbol (1,216 matched via EQUITY_L), action include/exclude; **stale after 2020-09** — do not extend without a new source |
| `market_breadth`, `market_breadth_daily` | own-data breadth gauges (E008a/b) | §11 reporting only; no gate (closed) |

## 2. Raw caches (data/raw/)

`bhavcopy_old/`, `bhavcopy_udiff/`, `delivery/` (per-session files, negative-cache in
`404_cache.txt`); `yf_adj/` (Yahoo frames per symbol); `nifty_tri/nifty500|nifty200/`
(per-year JSON chunks); `index_events/` (IndexInclExcl.xls + EQUITY_L.csv, fetched once).
All fetches: browser-like UA, .part atomic writes, loud failures (src/download/_http.py).

## 3. runs/ artifacts (the committed record)

| artifact | what | pins it holds |
|---|---|---|
| `runs/smoke_e2e/smoke_results.json` | smoke e2e pass over the slice | `light_pass.mean_gross` (E018/E022 G1 anchor), `slice_ic` → the IC pin, pick counts |
| `src/backtest/smoke_e2e.py` | `SLICE_IC_PIN = 0.07202922854484578`, `SLICE_IC_PIN_PRE_REPAIR = 0.07171797803434904` | the tape-repair re-baseline pair (repaired / pre-repair) |
| `runs/walkforward/harness_results.json` | the 35-month walk-forward (test window, §10) | `engine.benchmark_cagr = 0.12457495616414915`, `engine.cagr = −0.061435…`, `test_months` (35), `boundary = 2023-09-24`, benchmark_curve |
| `runs/walkforward/phase6_section11_report.json` | §11 metrics + regime tables | interim reference numbers (E011/E012 lineage) |
| `runs/prospective/` | prospective protocol record (designs.json, `<name>/folds.csv`) | created on first registration; append-only |

## 4. Pin map — every committed constant guards consume

| pin | value | defined | consumed by |
|---|---|---|---|
| Slice IC (repaired tape) | `0.07202922854484578` | `smoke_e2e.SLICE_IC_PIN` | E018 G2, E023 G1, smoke re-pins |
| Slice IC (pre-repair tape) | `0.07171797803434904` | `smoke_e2e.SLICE_IC_PIN_PRE_REPAIR` | the repair supersession record |
| Labeled top-5% picks | `4,579` | smoke_results.json | E018 G2 |
| Arm-convention picks | `5,605` | smoke `_picks` over all decision rows | E018 G2 |
| Eligible symbol-months (labeled) | `161,942` | feature_matrix | universe guards |
| Index equivalent, validation slice | CAGR `0.13174664181300377` / maxDD `−0.2887358301241153` | E019 results.json `index_equivalent` | E020 G2, E022 G2, E024 G2 |
| E020 satellite (E019 arm A sim) | CAGR `0.2576823502440744` / maxDD `−0.470202965689257` | E020 results.json `guards.G1_recomputed` | E020-C G1 |
| Index equivalent, test window | `0.12457495616414915` | harness_results.json `engine.benchmark_cagr` | E020-C G2 |
| E022 by-band excess (validation) | down `−0.0016655162567964852`, flat `0.0067124853060405235`, up `0.023954579561303944` | E022 results.json `book.post_hoc_slice_split.validation_by_band` | E024 G1 |
| E022 overall excess | `+0.01127861371645468`/mo (t 2.859) | E022 results.json `book.overall` | the closure forensics |
| Top-5% 1-month gross anchor | `0.02811289893242504` (pin), tolerance 0.15pp | smoke_results.json `light_pass.mean_gross` | E018 G1, E022 G1 |
| Smoke slice IC field | stored on the repaired tape as `SLICE_IC_PIN`; the json's `light_pass.slice_ic` is the live recompute | smoke_e2e.py / smoke_results.json | smoke re-pins |

Reproduce any guard: run the experiment (`--profile full`); every G-guard asserts against
these pins at 1e-9 (1e-6 where marked). A pin that stops reproducing is a data/code drift
alarm, not a number to update.
