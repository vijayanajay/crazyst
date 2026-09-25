# quantdata

One command (and one DuckDB file) that downloads, normalizes, and serves 15 years of NSE
equity data — daily prices, delivery statistics, and Yahoo-adjusted closes — rebuilt into
month-end panels, a liquidity-ranked universe, and a labeled feature matrix for modeling.

```
NSE bhavcopy (2 formats) ─┐
NSE delivery (2 formats) ─┼─► raw cache ─► DuckDB ─► panels ─► universe ─► features ─► your project
Yahoo Finance (.NS)      ─┘   data/raw/    quant.duckdb
```

Everything is driven by `config.yaml` (profile `quick` = last 12 months, `full` = 15 years;
every threshold lives there). The **data cutoff is the newest bhav date in the database** —
no config date to keep in sync, and the daily refresh never mutates a versioned file.

## Quick start

From source (repo root is "home" — config and `data/` live there):

```
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python quantdata.py status          # see what you have
.venv/Scripts/python quantdata.py backfill        # 2011→today, resumable — rerun continues where it stopped
.venv/Scripts/python quantdata.py refresh         # daily catch-up + self-check gate
```

Portable executable (`python build_exe.py` → `dist/quantdata/`, 166 MB, PyInstaller):

```
quantdata.exe status                              # first run unpacks config.yaml next to the exe
quantdata.exe backfill                            # …or copy an existing data/ folder alongside it
```

The exe keeps `config.yaml` and `data/` in **its own folder** wherever it is copied, so one
binary + data folder moves between machines and projects intact. `build_exe.py` smoke-tests
the binary before declaring success.

## Commands

| Command | What it does |
|---|---|
| `status` | rows/date-spans for every table, the cutoff, raw-cache size |
| `check` | 30-second sanity: cutoff, duplicate-key count, adj coverage vs the canary floor |
| `query symbol RELIANCE` | one symbol's full daily history (add `-o out.csv` for CSV) |
| `query symbols EQ` | every symbol ever seen in a series, with first/last dates |
| `query dates 2026-08` | the month's EQ trading calendar |
| `query matrix -o m.csv` | the labeled feature matrix for modeling |
| `query sql "SELECT …"` | read-only escape hatch (SELECT/WITH only, validated) |
| `refresh [--date D] [--no-verify]` | fetch + normalize + rebuild + self-check gate; `--date` for catch-up runs |
| `scheduler [--once]` | cron entry point: waits for the 19:00 IST publish cutoff, retries, exit codes 0/1/2 (caught up / failed / behind) |
| `backfill` | full history build (bhavcopy both eras + MTO + normalize), resumable |
| `backfill-adj` / `trim-adj` | Yahoo adjusted closes for all EQ symbols / apply the history floor and drop placeholder rows |
| `selfcheck [--force] [--verbose]` | the 17-check suite, stamped — cached when nothing moved |
| `validate` / `canary` | the gap/join/coverage report; the momentum + delivery canaries |

Cron (the scheduler prints this recipe too): weekdays just after the cutoff —
`10 19 * * 1-5 cd /path && quantdata scheduler`. Logs: `data/refresh.log`,
`data/scheduler.log` (one line per event — a killed run still leaves its record).

## The database: `data/duckdb/quant.duckdb`

Four layers + one metadata table. Source tables are loaded from the raw cache (idempotent:
"one file = one date"; every pass ends with a key-dedupe + CHECKPOINT). Derived tables are
**rebuildable at any time** from the sources — never edit them by hand.

### Layer 1 — source tables (raw data, normalized)

**`bhav`** — the price backbone, ~7.9M rows, 2011-01-03 → cutoff. One row per
`(symbol, series, date)`; all series are kept (EQ = the trading universe, BE = trade-to-trade,
…), filtering happens downstream.

| column | meaning |
|---|---|
| symbol, series, date | key |
| open, high, low, close, prev_close, last | raw NSE prices (never adjusted) |
| volume | shares traded (TOTTRDQTY) |
| turnover | ₹ traded value (TOTTRDVAL) |
| trades | number of trades (NULL in early years) |
| isin | ISIN (NULL in early years) |

**`delivery`** — deliverable quantity, ~6.3M rows, 2011 → cutoff. EQ rows from MTO
(2011→) and sec_bhavdata_full (2019-10→); where both cover a date MTO won the dedupe.

| column | meaning |
|---|---|
| symbol, date | key |
| deliv_qty | shares delivered (settled, not intraday-swapped) |
| deliv_per | delivery as % of traded quantity |

**`adj_close`** — Yahoo Finance adjusted close, `SYMBOL → SYMBOL.NS`, from 2009-01-01
(buffer before the 2011 window + the longest 12M-1M lookback). This is the only table whose
history is adjusted for splits/bonuses/dividends — it exists for *correct returns*; raw NSE
prices stay untouched. ~1.3k delisted/renamed tickers have no Yahoo data (by design, not a
hole); a whole-series re-fetch replaces a symbol whenever its adjustment basis moves.

| column | meaning |
|---|---|
| symbol, date | key |
| adj_close | adjusted price (NULL/NaN placeholder rows are filtered by every consumer) |

### Layer 2 — month-end panels (daily → monthly, built ONCE)

**`month_grid`** (189 rows) — the decision calendar: `m` (month), `mdate` (that month's last
EQ trading day). Every later stage anchors on `mdate`.

**`adj_me`** — month-end adjusted prices, one row per symbol-month **only if a valid print
exists that month**. `adate` ≤ `mdate` always (a suspended/delisted symbol can never be
priced from a stale row — the lookahead invariant, checked). Columns: `symbol, m, mdate,
adate, adj_close`.

**`liq_me`** — liquidity input: `med3` = **pooled** median daily turnover (₹) over the
trailing 3 months ending AT `mdate` (a median of monthly medians is not a median), plus
`n_days`. Full history regardless of profile, so a decision month's lookback is never
truncated. Columns: `symbol, m, mdate, med3, n_days`.

**`deliv_me`** — monthly delivery aggregates: `deliv_per_mean, deliv_qty_sum, n_days` per
symbol-month.

### Layer 3 — universe and labels

**`universe_rank`** — per decision month: `med3`, `med3_cr` (₹ crore), `rank`
(1 = most liquid), `in_universe` (top 1500 by `universe.top_n`).

**`eligible`** — the eligibility verdict per `(mdate, symbol)`: `close`, `listed_before`,
`med3`, `rank`, `in_universe`, `eligible`, and `reasons` (why not: price floor ₹20, listed
< 6 months, series, …). GSM/ASM surveillance exclusion is wired but inert until a snapshot
is supplied (`paths.surveillance_csv`).

**`winners`** — the label table, per `(mdate, symbol)`: `ret` = the **forward** month-end
return (keyed at the decision date the return *ends* at), and three winner definitions —
`is_winner` (top 5%), `is_top_decile`, `is_top20` (secondary, harder).

### Layer 4 — features

**`feature_panel`** — 22 features per eligible symbol-month, one DuckDB CTAS, no Python
loops: momentum (`mom_1m/3m/6m/12m_1m` from `adj_me`), volume structure
(`volume_zscore`, `up/down_volume_20d`, `up_down_volume_ratio`, `breakout_volume_confirmed`),
delivery (`delivery_pct`, `_zscore`, `_trend`, `delivery_spike_while_flat`),
volatility/candles (`atr_ratio`, `nr7`, `squeeze_days_20d`, `range_compression_20d`,
`close_in_range`, `upper/lower_wick_ratio`, `consec_higher_lows`, `big_body_day_in_trend`).
Windows end at the decision date; missing lookbacks are **NULL, never zero, never
forward-filled**; future-data isolation is synthetically proven.

**`feature_matrix`** — `feature_panel` + the join to labels and buckets:
`next_month_ret`, `is_winner`, `liquidity_rank`, `size_bucket` (top200 / 201-600 / 601-1500).
This is the modeling surface; `quantdata query matrix -o matrix.csv` exports it.

### Metadata

**`build_stamp`** — caching machinery (`key, fingerprint, outputs, seconds, built_at`):
each builder records a fingerprint of its inputs (code, config values, source-table
row-count/max-date, raw-cache stats) and skips work only when nothing moved. `selfcheck
--force` and `python quantdata.py … --force`-style reruns ignore it.

## Reading the data from another project

The DB is a single file — open it read-only from anything that speaks DuckDB:

```python
import duckdb
con = duckdb.connect(r"...\quantdata\data\duckdb\quant.duckdb", read_only=True)
print(con.execute("SELECT max(date) FROM bhav").fetchone())
df = con.execute("SELECT * FROM feature_matrix WHERE mdate >= '2026-01-01'").df()
```

Or skip SQL entirely: `quantdata query symbol TCS -o tcs.csv`,
`quantdata query matrix -o matrix.csv`, `quantdata query sql "…"`.

Two properties to rely on: the **cutoff** is `max(bhav.date)` (`quantdata status` prints it;
treat anything after it in `adj_close` as pre-publish noise), and **derived tables are
disposable** — if in doubt, `quantdata refresh` rebuilds them and gates on the self-check.

## Layout and docs

```
config.yaml        every threshold, path, profile window (single source of truth)
data/raw/          raw cache (bhavcopy zips, MTO/sec files, 404 negative cache) — deletable, re-downloadable
data/duckdb/       quant.duckdb — everything above
build_exe.py       builds dist/quantdata/ (portable exe)
datadownloader.md  every source URL, raw format, and the raw→feature processing detail
LEDGER.md          dated build log with evidence for every reported number
```
