# LEDGER — every experiment, its pre-registered prediction, and its verdict (BRD §12)

Predictions are written **before** the experiment runs and may not be edited after (BRD §12).
Verdicts: `confirmed` / `rejected` / `inconclusive`. One row per experiment; a run without a
ledger row is not done. Profile (`quick`/`full`), git hash, and data cutoff are logged in each
experiment's `results.json`.

| # | Experiment | Pre-registered prediction | Verdict | Date |
|---|---|---|---|---|
| E000 | Universe overlap: as-of top-1500 liquidity vs Nifty 200 | Overlap ≥ 80% of Nifty 200 constituents per year; hit rates computed on the two universes differ by < 2pp | pending | — |
| E001 | Anatomy of winners: winners differ from rest on momentum/delivery features | Winners' 6–12M momentum and 20-day delivery% z-score distributions sit above the eligible rest (median shift > 0) | pending | — |
| E002 | Univariate IC sweep (all features) | 6–12M momentum and delivery% z-score have positive pooled Spearman IC, surviving BH at α = 0.05 | pending | — |
| E006 | Cost sensitivity: 0.2 / 0.5 / 1.0 % per side | Net edge at 0.2% does not survive 1.0% for picks ranked below ~600 (BRD §9.7) | pending | — |
| E003 | Bulk/block deal net buying overlay (Phase 7) | Net institutional buying in the prior month adds IC on top of E002 survivors | pending | — |
| E004 | SAST/insider buying overlay (Phase 7) | Insider % acquisitions in the prior quarter add IC on top of E002 survivors | pending | — |
| E005 | F&O OI overlay, optional (Phase 7) | OI build-up with price adds IC on top of E002 survivors | pending | — |

---

## Milestone M2 — Phase 1 data pipeline complete (2026-09-22, commit `a2318ce`)

Not an experiment — the data-layer sign-off gate from actionplan.md Phase 1. Recorded here
because the plan's checkpoint is "show the validation report, get sign-off."

**Data state** (`full` profile, DuckDB `data/duckdb/quant.duckdb`, cutoff 2026-09-21):

| Source | Rows | Dates | Span |
|---|---|---|---|
| bhav (old + UDiFF formats) | 7,896,137 | 3,878 | 2011-01-03 → 2026-09-21 |
| delivery (MTO + sec_bhavdata_full) | 6,262,863 | 3,879 | same, incl. 7 healed days |
| adj_close (yfinance `.NS`) | 4,048 / 4,048 EQ symbols | — | 0 permanently unavailable after retries |

> **Superseded by M2.2 (below).** The 4,048/4,048 count was `count(DISTINCT symbol)`, which
> counted symbols whose frames were entirely NULL as priced. Real coverage: 2,982 priced
> symbols, 1,066 of them (26%) delisted tickers Yahoo no longer serves. Left as written,
> with this note, rather than quietly edited.

**Validation report:** yearly bhav coverage 93.1–95.4% (weekday-count denominator); 0 outage
holes — 222 weekday gaps == 222 recorded NSE holidays; delivery↔bhav join mismatch 0.00%;
result **PASS**.

**Canaries (BRD §11):** momentum Spearman IC **+0.065** pooled (285 months, > 0 ✓);
delivery% autocorrelation **0.89** (293,787 symbol pairs, > 0.5 ✓); eligible-count stability
all 189 months within ±20% of median (1,214 → 1,463) ✓. Selfcheck suite 8/8.

**Decision: the 7 corrupt MTO days (2017–2019).** Files arrive from NSE's archive with the
header's first byte truncated (`rade Date <…>`); re-downloading reproduces the corruption, so
it is source-side, not ours. Two normalizer rules were adopted as policy: (1) a wrong-dated
row is still refused outright; (2) when the header is truncated, the trade date is recovered
from the intact `10,MTO,DDMMYYYY` counts line — spot-checked against the filename for all 7
days. Corollary policy: one corrupt file never blocks a batch; refused files are collected
and raised at the end, loudly. The 7 healed days are in the delivery table and join bhav
with 0.00% mismatch.

**Honest caveats:** (1) the momentum canary was initially computed with an inverted ratio and
reported −0.065; the inversion was caught and fixed — the +0.065 figure is the corrected one.
(2) The IC pool includes micro-caps with gappy history; the Phase 3 experiment recomputes IC
on the as-of top-1500 universe (the canary's eligibility SQL is the template). (3) scipy was
not added: Spearman is computed as Pearson-on-ranks (identical math) — BRD §13 dependency
justification avoided by construction.

---

## Milestone M2.2 — pipeline performance and input stamps (2026-09-22, uncommitted; working tree on `7d5d431`)

Not an experiment — an infrastructure pass. Recorded because it changed **what the data tables
contain**, not only how fast they load. Commit hash to be filled in once committed.

### Measured savings

| What | Before | After |
|---|---|---|
| self-check suite, real work | 156.0s | 30.0s |
| self-check suite, nothing changed | 156.0s | **1.9s** (cached) |
| `universe.winners` check | 134.3s | 2.7s |
| `adj_close` table | 30.3M rows | **6.79M** |
| DuckDB file / free blocks | 551 MB / 419 blocks | 437 MB / **0** |
| `adj_close` → pandas | 2.4 GB, 2.9s | 0.55 GB, 0.85s |
| winners recompute input | 30.3M rows, 4.9s | 688,824 rows, 0.12s |
| winners build SQL | 6.97s | 0.22s |
| full-history rank build | 6.35s* | 4.02s |
| month-end panels (new) | — | 2.9s, 1.45M rows |

\* the 6.35s figure was measured while the MTO/adj backfills were running, and rank has since
moved onto the `liq_me` panel (follow-up note at the end of this block) — treat this row as
contention, not speedup.

**R1 — scoped recompute.** The winners spot-check loaded all 30.3M `adj_close` rows into pandas
(2.4 GB) and re-sliced the frame 20 times — 128.7s of the 134.3s check. It now fetches only the
sampled months' window (688,824 rows, 0.12s) in one pass. Verified equivalent, not assumed:
**10/10 months identical, worst return difference 0.00e+00, winner sets identical.**

**R2 — table diet.** See the NULL/coverage decision below for the row reduction, plus the
`--trim` repair, the bounded fetch, and the file rewrite that reclaimed the deleted blocks.

**R3 — month-end panels** (`month_grid`, `adj_me`, `turnover_me`, `deliv_me`): daily→monthly
once, so repeated work is joins against 1–2M-row panels. `winners` now joins `adj_me` instead of
two ASOF joins over 30M daily rows. `turnover_me`/`deliv_me` are built but **not yet read by
anything** — Phase 3 staging at 0.3s each; delete them if the feature library does not want them.

### Decision: 10.9M NULL `adj_close` rows, and why coverage was reporting a false 100%

Of 30.3M stored rows, **10,929,155 (36%) had `adj_close IS NULL`**, and **1,066 of 4,048 EQ
symbols (26%) were entirely NULL** — delisted or renamed tickers Yahoo no longer serves (probe:
"possibly delisted"; multi-ticker batches also pad gap and pre-listing days with NaN). The old
backfill cached those all-NaN frames and counted the symbols as *fetched*, and the canary's
coverage metric was `count(DISTINCT symbol)` — so it reported **100% coverage over symbols it
could not price**. Policy adopted:

1. the fetcher skips an all-NaN frame, so a delisted ticker is reported *unavailable* rather
   than cached as permanently empty;
2. `--trim` deletes pre-`adj_history_start` **and** NULL rows from an existing table (idempotent:
   a second run removes 0); the fetch floor is `adj_history_start: 2009-01-01`, not `period="max"`,
   so the 1991–2008 tail (42% of the table, unreachable by any profile) cannot come back;
3. coverage is measured on **still-trading** symbols: 2,738/2,738 = **100%**, with the all-time
   2,982/4,048 = 73.7% reported alongside as the survivorship hole BRD §4 warns about.

Consequence for the panel invariant: 17,066/17,225 eligible symbol-months (99.1%) are priced, and
the 159 holes trace to exactly **36 unpriceable symbols** (24 entirely NULL, 12 sparse). The
gap assertion therefore tests *"a valid in-month print existed and the panel lost it"* rather
than *"zero holes"* — it must fail on a panel bug, not on Yahoo's absent tickers.

### Winners relabelling caused by R3

The rewiring tightened two rules: no symbol can be priced from a stale cross-month row, and the
current **partial month (2026-09-21) is never labeled** (it would silently change tomorrow).
Against the pre-change snapshot: **1,276 rows removed = exactly the September pool** (64 winners /
128 top-decile / 20 top-20), **0 label flips and 0 return changes across all 11 shared months**,
and 3 pool rows *added* (INFRABEES, NIF100BEES, NIFTYIETF) that the old NULL-matching ASOF join
had dropped. Database file shrank 551→437 MB: the reclamation needed a rewrite (parquet
EXPORT/IMPORT *grew* it 498→506 MB; native `ATTACH` + `CREATE TABLE AS` gave 421 MB with 0 free
blocks), done with a verified backup that was removed after the suite passed.

**Canary note:** momentum IC is now **+0.0639 over 200 month-ends** (was +0.065 over 285) —
deleting NULL rows means `lag(252)` counts trading days that actually have prices, so a few
pseudo month-ends disappear. Same sign, still passes.

### Input stamps (`src/stamp.py`, check #2 in the runner)

A stamp is a `build_stamp` row: fingerprint + output row counts + built-at. The fingerprint hashes
five spec kinds — `code` (sha256 over `src/**/*.py`, `config.yaml`, `requirements.txt`),
`cfg:a.b`, `table:t.col` as `(rows, max)`, `dir:path` as `(files, bytes, newest mtime)`, `file:p` —
and an unknown spec **raises** rather than being ignored. It is current only if the fingerprint
matches **and** every recorded output table still holds its recorded row count (a dropped or
truncated table forces a rerun). It is **cleared before** the run and **recorded only after all
13 checks pass**, so a failure can never look like a pass.

`(rows, max)` instead of a content hash is deliberate: every check rebuilds the tables it
validates, and a rebuild writing identical rows must not invalidate its own stamp — asserted in
the self-check and confirmed live (an `ensure()` rebuild of all four panels left the suite stamp
current).

| Evidence | Result |
|---|---|
| repeat run, nothing touched | **1.9s**, `ALL PASS (13 checks, cached …)` |
| `--force` | 46.3s, reruns every check (bypass proven) |
| comment-only edit to `src/validate/report.py` | full 27.2s rerun — the code hash is content-based, so even a comment invalidates |
| one cached MTO file mtime-touched (bytes unchanged) | full 29.3s rerun, then 1.9s cached |
| `panels.ensure()` no-op / rebuild / no-op | 0.01s / 1.78s / 0.01s (vs 2.9s unconditional) |
| `python -m src.stamp` | full rule set asserted: absent/dir/file hashing, identical-rebuild stability, new row + config change invalidate, unknown spec raises, dropped/truncated output not current, record/clear round-trip |

`data/raw/404_cache.txt` is deliberately **not** in the fingerprint: it is a negative cache of
URLs NSE 404'd, appending to it changes no table, and including it would let one network 404
defeat the cache forever.

**Honest caveats:** (1) a cached pass means "this exact fingerprint passed" — `--force` exists
for when that is not good enough. (2) The file-size gain is modest (437 MB); the real win is the
78% row reduction, which shrinks every scan rather than the bytes on disk. (3) Phase 1's
momentum verdict and the M2 sign-off above were computed before the NULL trim; the table state
has changed since, so the M2 canary numbers should be read as "same sign, re-measured" rather
than bit-identical.

### Follow-up (same session): rank reads the panel

The unused `turnover_me` (monthly medians) was replaced by **`liq_me`** — the BRD §4 trailing-
window median, **pooled** (a median of monthly medians is not a median) and full-history — and
`universe_rank` now ranks that instead of rescanning daily bhav. The window expression lives in
one place from here on.

Equivalence, measured rather than asserted:

- **`full` profile: bit-identical.** 330,831 rows both ways, 0 added, 0 removed, 0 differing
  med3/rank/in_universe values against the old daily-bhav query. (Expected: no bhav data precedes
  2011, so the window was never truncated there.)
- **Rank's own self-check** now recomputes med3 straight from bhav for sampled decision dates
  (7,765 symbol-months, incl. first and last month) and asserts exact equality with the panel,
  plus every `universe_rank` row against its `liq_me` row — 0 mismatches.
- **`quick` changes exactly three months** (2025-09-30, 2025-10-31, 2025-11-28). Cause: the old
  query filtered *daily* rows by profile start before building the window, so the first
  lookback−1 decision months were ranked on truncated evidence — the wart its own docstring
  admitted. Fixing it adds 84 symbol-months, flips 121 eligible flags/reasons, and moves winners
  by 56 rows added / 39 removed / **1 gained winner, 0 lost**.
- Cost: panel rebuild +0.94s (`liq_me` is 2.21s of the 3.84s), and rank's build drops from 4.02s
  to **1.11s** for the full history (330,831 rows) because it no longer touches daily bhav.

---

## Milestone M2.3 — daily refresh and scheduler (2026-09-23, uncommitted; working tree on `7d5d431`)

Not an experiment — the operational gate that turns Phase 1's tables from "built once" into
"current every evening". Two new modules: `src/download/refresh.py` (the pipeline, callable by
hand) and `src/download/scheduler.py` (the single entry point the clock calls). Data cutoff moved
**2026-09-21 → 2026-09-22**; bhav is now **7,899,813 rows**, delivery 6,262,863, and adj_close
prices **2,658 of 2,662 traded symbols on the newest NSE day**.

### The daily path

`python -m src.download.refresh` (`--date` for catch-up): as-of → fetch → normalize → `end_date`
→ adj_close → derived rebuild → stamped self-check.

- **as-of** is today once past `download.publish_cutoff_ist` (19:00 IST), else yesterday. Not a
  nicety: `_http` remembers a 404 for 30 days, so one run before NSE publishes would hide a real
  trading day for a month.
- **adj_close gets a daily path** (`refresh_recent`). `backfill()` skips symbols that already
  exist, so it could never see a new day. It fetches one short window for symbols whose bhav
  history runs past their last stored adjusted date, and **self-heals corporate actions**: a
  split rewrites Yahoo's whole adjusted history, which an append cannot fix, so when the adj/raw
  factor moves between the two days the symbol's entire series is re-fetched and replaced.
- **`end_date` is set from the data, not the clock** — the clock decides what to fetch, the newest
  bhav date present decides what is written. The edit preserves the line's comment (a yaml
  round-trip would have deleted every comment in config.yaml).

### Live verification

| Test | Result |
|---|---|
| New day (2026-09-22) fetched and normalized | bhav **+3,676 rows**, 2,662 EQ symbols; `end_date` bumped 2026-09-21 → 2026-09-22; derived rebuilt; self-check **ALL PASS (13)** |
| Adjusted-close coverage of that day | **2,662/2,662 traded symbols priced** |
| Second run the same day | 8.4s, "panels already current", self-check **cached** |
| Delete 2 settled adj rows, re-run | restored exactly — "+2 symbols, +2 rows" |
| `scheduler --once` (real run) | **exit 0**, "ok: caught up to 2026-09-22", 42s |
| that run's own verify step | self-check **ALL PASS (13 checks) in 28.4s**, stamp recorded |
| `scheduler --self-check` | verdict codes (equal/ahead/behind/empty/failed), cutoff wait math, era-aware URL set, lock exclusivity + stale takeover, 404 eviction scoping + idempotence + missing file |
| suite afterwards | **13/13 in 32.8s**, no stale lock, both stamps current |

The daily log line reads: `2,658/2,662 traded symbols priced (4 missing)` — the missing four are
`20MICRONS, 21STCENMGM, 360ONE, 3BBLACKBIO`, whose 2026-09-22 rows my delete-and-restore test
removed and Yahoo is currently serving as a **placeholder row (Close and Adj Close both NaN)**.
The notna guard correctly refuses to store it and the day stays queued; the table, not the code,
is what is 4 rows short, and the recovery mechanism is the one proven above.

### The scheduler: entry points and exit codes

| Invocation | Behaviour |
|---|---|
| `python -m src.download.scheduler` | waits for the cutoff, refreshes, retries while behind |
| `--once` | one attempt now, no waiting or retrying (the manual equivalent) |
| `--self-check` | the offline rules above; no network, no DB writes |
| exit **0** | caught up — or nothing was due |
| exit **1** | refused to run (another refresh in flight) or the refresh itself failed |
| exit **2** | ran fine but still behind: NSE holiday, or their archive is late |

Two pieces are load-bearing, not decoration:

- **Every attempt evicts the target date from the negative cache first**, otherwise a retry is
  theatre — `_http` would answer "holiday" from the 30-day cache without contacting NSE. Verified
  against the live 451-line cache: exactly the target date's 3 URLs dropped, other dates and
  unrelated lines untouched.
- **A single-instance lock** (takeover only after 90 min, i.e. a dead process, not a slow one),
  so a scheduled run and a manual run cannot both write DuckDB.

The refresh runs in a subprocess — its own DuckDB writers, its own env, exactly as run by hand —
and the wrapper judges it from `max(bhav.date)`, not from the exit code alone.

### Finding: retrying a late archive is expensive, and that is what the cutoff is for

The live scheduled-mode test hit the 600s tool timeout. It was **not** a bug: with
`refresh_retry_minutes: 1` (a test value) the run did 3 attempts × (full refresh 40–90s + real NSE
probes + 60s sleeps), which exceeds ten minutes. The honest lesson is the cost model — a retry
against a not-yet-published day spends real NSE timeout time (60s read timeout × retries per
source), which is exactly why the default cutoff is 19:00 and the retry gap 20 minutes. Bounded
retrying stays: a late archive recovers, a holiday never will.

### Change: per-event logging (prompted by that timeout)

The wrapper originally buffered its output and wrote one block at the end of the run. A killed or
rebooted run therefore left **no record at all** — the failure mode most worth logging was the one
case that logged nothing. `log_line()` now appends one IST-timestamped line per event through
`say()`, so an interrupted run still shows how far it got:

```
2026-09-23 00:33:32 IST  --- scheduler start (once, pid 24916)
2026-09-23 00:34:14 IST  attempt 1/3: ok: caught up to 2026-09-22 (42s, refresh exit 0)
2026-09-23 00:34:14 IST  RESULT: ok: caught up to 2026-09-22 (exit 0)
```

The module docstring now carries the concrete cron and `schtasks` lines, plus the property that
makes one missed night harmless: the refresh walks every month from the newest stored date to
as-of, so a run after downtime closes the whole gap.

### Bugs found and fixed on the way

1. **Any run in the current month could crash**: `delivery.download_month` ignored `end_date`
   unless the caller passed `up_to`, while both bhavcopy loops bound themselves. The same latent
   shape existed in `bhavcopy_old.download_month`. Both now bound themselves, so no call site can
   walk into a day `fetch_day` refuses.
2. **Yahoo rate-limited us (HTTP 429)**: ~1,067 delisted tickers sat in the fetch set on *every*
   run, because after the NULL trim they have no stored rows, so their bhav max always looked
   newer than "no stored date". The daily set is now scoped to symbols that traded in the last 30
   days (114s → 47s); a symbol suspended longer is picked up by itself when it resumes.
3. **My own assertion was wrong**, twice: it demanded `panels.ensure()` rebuild every time, which
   breaks the harmless second run of the day (now reported, not required), and it asserted the
   2024-07 era boundary could be straddled by a single *date* when it is a straddled *month*.
4. `months_between` is a generator — the fetch plan was a generator, not the list the code assumed.

### Number reconciliation (looked contradictory in the logs)

`winners` holds **14,373 rows** = one per eligible symbol-month (~1,337/month, 11 months), of which
**724 are winner flags** (~67/month, top 5%), 1,441 top-decile, 220 top-20. The stamp reports table
rows, the refresh reports winner flags; both numbers are right.
