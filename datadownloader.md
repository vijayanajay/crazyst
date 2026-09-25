# Data Downloader Reference

What this repo downloads, from where, in what shape, and what happens to it between the raw
file and the feature matrix. Every claim cites the module that implements it. Current-state
numbers are from the live database as of 2026-09-25 (cutoff 2026-09-24).

```
NSE archives ──► raw cache (data/raw/…) ──► DuckDB source tables ──► panels ──► universe ──► features
Yahoo Finance ──► (adj_close table only)        bhav, delivery        month_grid   rank       feature_panel
                                                adj_close             adj_me       eligible   feature_matrix
                                                                      liq_me       winners    (labels: forward month)
                                                                      deliv_me
```

Orchestration: `src/download/scheduler.py` (cron entry point) → `src/download/refresh.py`
(daily job) → shared HTTP discipline in `src/download/_http.py` → per-source downloaders in
`src/download/` → normalizers in `src/normalize/` → derived builders in `src/universe/`,
`src/features/`.

---

## 1. Sources

### 1.1 Old-format bhavcopy — 2011-01-03 → 2024-07-05 (`src/download/bhavcopy_old.py`)

- **URL**: `https://archives.nseindia.com/content/historical/EQUITIES/{YYYY}/{MMM}/cm{DD}{MMM}{YYYY}bhav.csv.zip`
  (e.g. `…/2011/JAN/cm03JAN2011bhav.csv.zip`) — one zip per trading day.
- **Shape**: zip → CSV, columns `SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE,
  TOTTRDQTY, TOTTRDVAL, TIMESTAMP, TOTALTRADES, ISIN` (+ a trailing empty column, dropped).
  `TOTALTRADES` and `ISIN` are absent in early years → NULL in the table.
- **Cache**: `data/raw/bhavcopy_old/{year}/{mm}/cm{DD}{MMM}{YYYY}bhav.csv.zip` (~3,800 files).
- Era boundary verified live: `cm05JUL2024bhav` exists, `cm08JUL2024bhav` 404s.

### 1.2 UDiFF bhavcopy — 2024-07-08 → today (`src/download/bhavcopy_udiff.py`)

- **URL**: `https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip`
  — the current daily format.
- **Shape**: zip → CSV, UDiFF column names (`TradDt, TckrSymb, SctySrs, OpnPric, HghPric,
  LwPric, ClsPric, PrvsClsgPric, LastPric, TtlTradgVol, TtlTrfVal, TtlNbOfTxsExctd, ISIN`).
- **Cache**: `data/raw/bhavcopy_udiff/{year}/{mm}/…`.
- The 2024-07 boundary month straddles both formats: `refresh.era_calls()` dispatches `["old",
  "udiff"]` for it, and no single date ever needs both (asserted in the scheduler self-check).

### 1.3 Delivery — legacy MTO — 2011-01-03 → today (`src/download/delivery.py`)

- **URL**: `https://archives.nseindia.com/archives/equities/mto/MTO_{DDMMYYYY}.DAT`
  (note the doubled `archives` path segment — live-verified). Plain text, still published daily.
- **Shape**: 3 header lines, then positional rows
  `record_type, sr_no, name, qty_traded, deliv_qty, deliv_per`. Only record type **20**
  (equities) is kept; 9xx rows are indices. Series filter applies (EQ only downstream).
- **Cache**: `data/raw/delivery/mto/{year}/{mm}/MTO_{DDMMYYYY}.DAT`.

### 1.4 Delivery — sec_bhavdata_full — 2019-10-01 → today (`src/download/delivery.py`)

- **URL**: `https://archives.nseindia.com/products/content/sec_bhavdata_full_{DDMMYYYY}.csv`
  (padded CSV — `skipinitialspace` matters). Verified 404 for every probed day before Oct 2019.
- **Shape**: richer than MTO — adds previous/last prices, turnover in ₹ lakhs, trade count and
  the ISIN — but the normalizer keeps the same 4 columns as MTO (schema is identical either way;
  where both cover a date, the dedupe keeps the first-loaded rows, which MTO is — recorded in
  `src/download/backfill_all.py`'s docstring after being caught in review).
- **Cache**: `data/raw/delivery/sec_bhavdata_full/{year}/{mm}/…`.
- Both delivery sources are fetched for every planned day (going forward sec_* becomes the sole
  source if MTO ever retires; today both still exist, so both load).

### 1.5 Yahoo Finance adjusted closes — 2009-01-01 → today (`src/normalize/adj_close.py`)

- **Source**: `yfinance`, batched `yf.download`, mapping NSE `SYMBOL` → `{SYMBOL}.NS`
  (M&M.NS, BAJAJ-AUTO.NS work as-is). History floor `adj_history_start: 2009-01-01`
  (config) — two years of buffer before the 2011 data window and the longest 12M-1M lookback;
  the unused 1991–2008 tail was trimmed (`--trim`).
- **Kept**: only `Adj Close` (raw Close is used transiently for the Yahoo-vs-NSE agreement
  check). This table exists for *correct returns* — splits/bonuses/dividends — never as a
  price source; NSE raw prices stay untouched.
- **Refusals**: a ticker whose frame is entirely NaN (delisted/renamed — ~1,3xx symbols) is
  reported as unavailable and never cached as "fetched"; placeholder rows (Close and Adj Close
  both NaN, Yahoo's same-day artifact) are filtered on value everywhere (`adj_me` requires
  `IS NOT NULL AND NOT isnan AND > 0`).
- **Cache**: the `adj_close` table itself (API data, no raw files) — symbols already present are
  skipped, so the backfill is resumable.

### 1.6 GSM/ASM surveillance snapshot — optional, human-supplied

`paths.surveillance_csv` (`data/surveillance/surveillance.csv`), schema
`symbol, effective_from, list, stage`. NSE does not publish historical surveillance stages
(BRD §5 D5), so nothing can be downloaded for the past; until a snapshot is supplied the
GSM/ASM eligibility guard excludes nothing (documented in `config.yaml`). See §5 for a fix.

---

## 2. Download discipline (shared, `src/download/_http.py`)

Every source goes through one `fetch()`:

| Rule | Implementation |
|---|---|
| Browser headers | NSE 403s bare clients (verified live); UA/Accept/Referer sent on every hit |
| Cache, never re-fetch | existing file short-circuits; a routine run is a few HTTP hits |
| Atomic writes | write to `.part`, then `os.replace` — a killed run leaves no truncated cache entry |
| Content validation | zip must start `PK\x03\x04` and be ≥10 KB; text must be ≥1 KB and not an HTML error page |
| Retry + backoff | `retry_attempts: 3`, linear backoff, 2s politeness sleep before *every* hit |
| Missing is loud | after retries: raise. 404 is special — see below |
| 404 = holiday (ponytail) | a 404 is *assumed* to mean non-trading day and recorded in a negative cache (`raw_404_cache`, 30-day TTL); the Phase 1.7 gap report is the safety net if NSE ever 404s a real trading day |
| As-of gating | `asof_date()`: today once past `download.publish_cutoff_ist` (19:00 IST), else yesterday; `--date` wins, future dates refused. Before the cutoff the day's files don't exist and would poison the negative cache for a month |

The as-of date is the **fetch-plan bound**, not stored state: `refresh.main()` sets
`work["fetch_asof"]` and every downloader's month loop refuses to walk past it (and never
refuses a day the plan reached for). The *data cutoff* is a different thing entirely — see §4.

---

## 3. Orchestration

### 3.1 Scheduler — `src/download/scheduler.py` (the cron entry point)

1. Waits for the publish cutoff (chunked sleeps).
2. Takes an exclusive lock (`data/.refresh.lock`, stale takeover after 90 min).
3. Per attempt: evicts the target date's URLs from the negative cache (a retry must actually
   re-probe NSE, not replay "holiday"), runs `refresh --date <asof>` as a subprocess, then
   reads `max(bhav.date)` and issues a verdict:

| Exit | Verdict |
|---|---|
| 0 | `ok: caught up` — stored ≥ as-of |
| 1 | `FAILED: the refresh did not complete` — refresh exit ≠ 0 |
| 2 | `BEHIND` — NSE holiday, or their archive is late (not an error) |

4. Still behind → retry, `refresh_retry_minutes` (20) apart, max 3 attempts, then surface the
   exit code. One line per event in `data/scheduler.log`; the refresh's detail in
   `data/refresh.log`. A killed run still leaves its record (that property failed live once —
   the `LOG_PATH` NameError on 2026-09-25 — and was fixed; see LEDGER).

### 3.2 Daily refresh — `src/download/refresh.py`

1. Compute the as-of date (cutoff-gated).
2. Plan every month from the oldest stored date to as-of (`months_to_check`) — a scheduler that
   was off for a week closes the whole gap in one run; cache-skip makes it cheap.
3. Fetch each month era-aware: bhavcopy (old and/or UDiFF) + MTO + sec_bhavdata_full.
4. Normalize bhav + delivery (idempotent; §4.1–4.2). Assert the normalize can't shrink bhav and
   can't hold a date past the fetch plan — the invariant that replaced the old config write.
5. `adj_close.refresh_recent()`: short recent window for symbols whose bhav history runs past
   their last stored adjusted date (30-day recency filter keeps the ~1,3xx dead tickers from
   rate-limiting Yahoo); full re-fetch + replace for any symbol whose adjustment basis moved
   (a split/bonus rewrites Yahoo's whole adjusted history). Known ceiling: a suspension
   spanning an ex-date is not detected this way (§5).
6. Rebuild derived tables (§4.3): panels → rank → eligible → winners.
7. Gate on `python -m src.selfcheck` (17 checks, ~5 min) — the run is stamped DONE only if the
   suite passes. Live end-to-end: ~11 min total, `git status` clean afterwards (the cutoff is
   read from the database, never written to a versioned file).

### 3.3 Historical backfill — `src/download/backfill_bhavcopy.py`, `backfill_all.py`

Same downloaders, full span (2011-01 → as-of), resumable by cache-skip; `backfill_all` chains
the delivery backfill (MTO covers the whole span) and a final normalize, with sanity guards on
rows-per-file and minimum table size.

---

## 4. Processing: raw → DuckDB → features

### 4.1 `bhav` — the price backbone (`src/normalize/bhav.py`)

    bhav(symbol, series, date, open, high, low, close, prev_close, last,
         volume, turnover, trades, isin)

- One column-mapping file per era (`columns_old.py`, `columns_udiff.py`); dates parsed with
  primary format + COVID-era fallback (`dd-Mon-yy`); unparseable dates abort that file.
- All series kept (EQ, BE, …) — eligibility filtering happens at query time.
- Idempotent + resumable: dates already in the table are skipped; "one file = one date" means a
  re-issued corrected file is *not* re-read — delete the DB rows for that date deliberately.
- Corrupt zips fail the pass at END (all good files still load, then raise).
- Every pass ends with `_self_heal()`: dedupe on `(symbol, series, date)` + `CHECKPOINT`.
- Self-check: hand-built zip per format → exact table values; live spot-checks that raw EQ
  symbol sets equal DB symbol sets across the format boundary; rerun loads 0 files.

### 4.2 `delivery` (`src/normalize/delivery.py`)

    delivery(symbol, date, deliv_qty, deliv_per)

- MTO parsed positionally; the file's own "Trade Date" header is validated against the filename
  (a mismatched file is refused; ~7 known truncated-header days fall back to the counts line).
- sec_bhavdata_full via its column map; content dates must equal the filename date.
- EQ only (features are computed on the eligible EQ universe); same idempotency/self-heal.
- Done-when check: bhav-EQ rows on delivery-dates lacking a delivery row < 1%.

### 4.3 `adj_close` (`src/normalize/adj_close.py`)

    adj_close(symbol, date, adj_close)

- Append-only for new days; whole-series replace when the adjustment basis moved
  (`ACTION_TOL = 1e-4` on the adj/raw factor). Rowid-deduped on `(symbol, date)` every insert.
- Daily trust check: Yahoo raw close vs NSE raw close agreement on the new rows
  (a mapping regression shows as disagreement, ~0% match, never as a wrong price).

### 4.4 Month-end panels (`src/normalize/panels.py`) — daily → monthly, ONCE

| Panel | Grain | Rule |
|---|---|---|
| `month_grid` | (m, mdate) | each month's last **EQ** trading day — the decision calendar |
| `adj_me` | symbol-month | last *valid* adjusted print at-or-before the decision date, inside that month; a suspended/delisted symbol can never be priced from a stale row (lookahead-checked: 0 rows with `adate > mdate`) |
| `liq_me` | symbol-month | **pooled** median daily turnover over the trailing `liquidity_lookback_months` (3) ending AT the decision date — a median of medians is not a median |
| `deliv_me` | symbol-month | mean delivery %, sum delivery qty, days |

Panels are full-history regardless of profile (the profile bounds reported windows, not
lookback). Stamped via `src/stamp.py`: rebuilt only when a source table, the panel SQL, or the
config spec moved; a no-op in the steady state.

### 4.5 Universe (`src/universe/`)

- `rank.py` → `universe_rank`: liquidity rank (as-of `liq_me.med3`) per decision month.
- `eligibility.py` → `eligible`: series ∈ {EQ} (from config, rendered once by
  `panels.series_sql`), price ≥ ₹20, listed ≥ 6 months, GSM/ASM stage ≤ 0 (inactive until a
  snapshot exists, §5). ~17.2k eligible rows in the quick window.
- `winners.py` → `winners`: the label — top 5% of eligible forward month-end returns
  (independently recomputed 10/10 months exact).

### 4.6 Features (`src/features/panel.py`, `matrix.py`)

- `feature_panel`: 22 features per eligible symbol-month — monthly momentum (1M/3M/6M/12M-1M
  from `adj_me`), volume structure (z-score, up/down ratio, confirmed breakout), delivery
  (level, z-score, trend, spike-while-flat), volatility/candles (ATR ratio, NR7, squeeze days,
  range compression, close-in-range, wicks, higher-lows streak, big body). One DuckDB CTAS —
  no Python loops. Windows end at the decision date; missing data is NULL, never zero, never
  forward-filled; future-data isolation is synthetically proven.
- `feature_matrix`: features + the FORWARD label (`next_month_ret`, `is_winner`) — keyed by the
  decision date the return *ends* at (lead over decision dates; a same-date join would ship
  past-month returns as labels) + `size_bucket` (top200 / 201–600 / 601–1500). 14,373 labeled
  rows at a 5.0% winner rate in the quick window.

---

## 5. Freely available data worth adding

Grounded in what the pipeline already lacks (each item names the gap it fills):

| Source | Free? | Span / grain | Fills what gap | Effort |
|---|---|---|---|---|
| **NSE index histories** — niftyindices.com (NIFTY 50/200/500 CSV, full history; constituent lists `ind_nifty*list.csv`) | Yes, no auth | daily, from 2007-ish | Market-level series: E002 showed mom_1m's pooled IC is a *between-month* effect — an index return column makes that measurable instead of inferred | Small: one table `market(date, idx_close)`, yfinance `^NSEI` as a cross-check |
| **India VIX** — nseindia.com daily report; also `^INDIAVIX` on yfinance | Yes | daily | Vol-regime feature; pairs with the volatility-cluster deconfound E003 | Trivial (same table as above) |
| **Corporate actions (bonus/split ex-dates)** — NSE corporates CSV | Yes | daily, historical archive | Independent validation of Yahoo's adjustment factors; would catch the documented ceiling (suspension spanning an ex-date) that factor-comparison misses | Medium: new fetch + cross-check against adj factors |
| **GSM/ASM surveillance daily reports** — nseindia.com surveillance page (CSV for recent days) | Yes, but **no history** | daily only | The repo models the schema (`surveillance_csv`) yet no automatic source exists; a daily snapshot job builds history going forward, and the eligibility guard finally activates | Medium: fetch + stage-parse; history must accumulate |
| **Bulk/block deals CSV** — nseindia.com archives | Yes | daily, years back | Whale-activity features (monthly aggregates over the EQ universe) | Medium |
| **FPI flows** — NSDL FPI monitor (daily net activity CSV/archive) | Yes | daily, long history | Market-timing context; complements, doesn't contaminate, the monthly cross-sectional design | Small |
| **Short-sell / SLB reports** — NSE daily | Yes | daily | Thin but free; another flow feature | Small |

**Already covered — don't re-download:** deliverable quantity (MTO + sec_bhavdata_full),
adjusted closes (yfinance), prices/turnover (bhavcopy).

**Deliberately not recommended:** screener.in / broker-site scraping (free-looking but ToS-gray,
unstable HTML — contradicts the repo's structured-source discipline), and paid APIs (ACE,
CMIE, Bloomberg) — out of scope by definition.

**Highest value-per-effort, in order:** (1) index + VIX history — an evening, one small table,
and it directly serves the E002 deconfounding work; (2) corporate-actions ex-dates — the one
source that checks an existing dependency (Yahoo adjustments) instead of adding a feature;
(3) GSM/ASM daily snapshots — start accumulating today because the past is unavailable; the
guard is otherwise dead config until one exists.

---

## 6. The portable executable (`quantdata.exe`)

One binary plus its data folder, usable across projects and machines — built by
`python build_exe.py` (PyInstaller onedir, build-time-only dependency): `dist/quantdata/`
contains `quantdata.exe` (15.9 MB), the packaged default `config.yaml`, the build-ID marker
the stamp fingerprint hashes when frozen, and the bundled runtime in `_internal/` (166 MB
in total).

- **Home anchoring** (`src/config.home_dir`): frozen, the exe's own folder is home —
  `config.yaml` is unpacked there on first run and every relative path resolves against it,
  so a shortcut from any other directory can't scatter a second `data/` tree. From source,
  the repo root (cwd) is home, unchanged.
- **Frozen fingerprints** (`src/stamp.code_fp`): an exe has no source files, so the code
  fingerprint hashes the `quantdata_build_id.txt` marker written at build time — copies of the
  same build share a fingerprint; a rebuild invalidates stamps, a copy doesn't.
- **In-process dispatch** (`quantdata.py --run-module` + runpy): the frozen exe has no
  interpreter to `-m` into, so child processes (the selfcheck runner's 17 module checks, the
  refresh's verify gate, the scheduler's refresh child) re-invoke the exe via
  `src.config.python_child_args`, and `runpy` runs the module's `__main__` in-process — exit
  codes propagate exactly as `python -m` did.

Commands:

    quantdata.exe status                       rows/spans/cutoff across all tables
    quantdata.exe check                        30-second sanity: cutoff, dupes, adj coverage
    quantdata.exe query symbol TCS -o tcs.csv  one symbol, full history (CSV)
    quantdata.exe query matrix -o matrix.csv   labeled feature rows for modeling
    quantdata.exe query sql "SELECT ..."       read-only (SELECT/WITH only)
    quantdata.exe refresh / scheduler          the daily pipeline and its cron entry point
    quantdata.exe selfcheck                    the full 17-check suite
    quantdata.exe backfill                     full 2011→today history build (resumable)

Cross-project use: copy `dist/quantdata/` anywhere; either let it backfill from scratch, or
copy an existing `data/` folder alongside it (status/check/query work read-only on it, and a
second project can hold just the exe + data while another holds the modeling code). Verified
live: a copied folder in %TEMP% serves identical status/check numbers and a full TCS history
export with zero repo files present.

## 7. Current state (live, 2026-09-25)

| Table | Rows | Span / note |
|---|---|---|
| `bhav` | 7,907,146 | 2011-01-03 → 2026-09-24 (the data cutoff) |
| `delivery` | 6,268,195 | 2011-01-03 → 2026-09-24; may run a day ahead of bhav when the feeds lag differently (classified informational, not a hole) |
| `adj_close` | 6,791,302 | 2009-01-02 → 2026-09-25 (Yahoo prices the current day before NSE publishes bhav); ~1.3k delisted symbols unpriced (mark-at-last-price) |
| `universe_rank` / `eligible` | 33,563 / 17,205 | quick window, 13 decision months |
| `winners` | 724 flags / 11 months | 5.0% winner rate among labeled rows |
| raw cache | ~4,000 files | `data/raw/` + negative 404 cache; DuckDB at `data/duckdb/quant.duckdb` |
