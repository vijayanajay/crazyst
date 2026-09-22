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

\* the 6.35s figure was measured while the MTO/adj backfills were running; rank still reads daily
bhav directly (the panel rewire is pending), so treat this row as contention, not speedup.

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
