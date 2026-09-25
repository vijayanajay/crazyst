# LEDGER — every experiment, its pre-registered prediction, and its verdict (BRD §12)

Predictions are written **before** the experiment runs and may not be edited after (BRD §12).
Verdicts: `confirmed` / `rejected` / `inconclusive`. One row per experiment; a run without a
ledger row is not done. Profile (`quick`/`full`), git hash, and data cutoff are logged in each
experiment's `results.json`.

| # | Experiment | Pre-registered prediction | Verdict | Date |
|---|---|---|---|---|
| E000 | Universe overlap: as-of top-1500 liquidity vs Nifty 200 | Overlap ≥ 80% of Nifty 200 constituents per year; hit rates computed on the two universes differ by < 2pp | **rejected on the letter of the rule** — overlap clause decisively confirmed (min 97.7% / mean 98.7% per year, 15 years); hit-rate trigger fired (mean yearly |Δ| 2.48pp ≥ 2pp) but the fired statistic is noise-bound (yearly binomial noise floor ±1.91pp; pooled |Δ| = 0.86pp, below the bar). No index-membership data needed; universe choice (0.86pp, ~2σ) handed to the BRD owner. See 2026-09-25 E000 block | 2026-09-25 |
| E002b | Full-profile confirmation IC sweep (mean monthly IC, month fixed effects removed) | Momentum features (mom_6m / mom_12m_1m) confirmed at 15 years; volatility-state finding reproduces with a stable sign | **confirmed, with one major reversal** — mom_12m_1m +0.052 (p = 1.1e-6) and mom_6m confirmed; **delivery family CONFIRMED at full history** (delivery_pct +0.049, p = 1.2e-11) — E002's quick rejection was a bull-window artifact; atr_ratio is regime-flipping (+0.045 up / −0.183 down, 94% down-month consistency), so its pre-registered sign holds only in the regime quick never sampled. See 2026-09-25 E002b block | 2026-09-25 |
| E001 | Anatomy of winners: winners differ from rest on momentum/delivery features | Winners' 6–12M momentum and 20-day delivery% z-score distributions sit above the eligible rest (median shift > 0) | **partial** — momentum anatomy confirmed (mom_12m_1m AUC 0.544, +0.050 median shift, 64% per-month consistency); delivery z-score anatomy REJECTED (AUC 0.478, wrong sign — matches E002); strongest separator is volatility state with the LORE-DIRECTION wrong (atr_ratio AUC 0.639 at every month, uniform across size buckets — not a small-cap artifact; momentum vanishes in the 601–1500 bucket, AUC 0.507). See 2026-09-25 block | 2026-09-25 |
| E002 | Univariate IC sweep (all features) | 6–12M momentum and delivery% z-score have positive pooled Spearman IC, surviving BH at α = 0.05 | **partial** — mom_12m_1m confirmed (+0.065, right sign, BH-surviving); delivery z-score REJECTED (−0.010, n.s.); mom_6m wrong sign; volatility-state features dominate (see 2026-09-24 block) | 2026-09-24 |
| P4.1 | Composite v0 (rank-avg of E002b survivors) beats the best single feature on the pre-test-window validation slice (paired monthly t, α = 0.05); atr overlay additive on the same test | **inconclusive** — composite 0.0625 vs best single (mom_12m_1m) 0.0529 mean monthly IC, diff +0.0096 over 145 months, p = 0.0585: point estimate wins, pre-registered bar missed ⇒ **mom_12m_1m ships as v0** (tie ⇒ simpler). Atr overlay REJECTED as an addition (−0.0390, p = 0.0033): the trailing-market regime proxy dilutes, not captures. Overlay's 0.0625-vs-0.0529 gap is the number the 4.2 ranker must justify. See 2026-09-25 P4.1 block | 2026-09-25 |
| P4.1b | Two-feature composite (mom_12m_1m + delivery_pct; P4.1's weakest-vote follow-up) clears the M3 bar vs the slice-selected best single | **confirmed** — 0.0681 vs 0.0529, diff +0.0153 over 145 months, p = 0.0140; 3f control recomputed (0.0625), 2f > 3f +0.0057 (p = 0.196, mom_6m was dead weight, not poison). **composite_2f ships as v0**, superseding P4.1's single-feature ship; precision flip (3f 55.4% > 2f 54.8%) disclosed. See 2026-09-25 P4.1b block | 2026-09-25 |
| P4.2 | Learned ranker (HistGBR, monthly walk-forward refits, all 22 features, fixed hyperparameters) beats composite_2f on the same validation-slice gate; freeze protocol reproduces picks | **rejected** — ranker 0.0402 vs composite_2f 0.0681, paired diff −0.0221 over 120 months, p = 0.0159: a clear loss (all-features rope + squared-error loss grabs noise the two-feature blindness avoids). **composite_2f ships as the Phase 4 model**; freeze protocol passed (bit-identical refits, max|diff| 0.00e+00; top-5% picks reproduce exactly; artifact round-trips). sklearn dependency justified in requirements.txt. See 2026-09-25 P4.2 block | 2026-09-25 |
| E006 | Cost sensitivity: 0.2 / 0.5 / 1.0 % per side | Net edge at 0.2% does not survive 1.0% for picks ranked below ~600 (BRD §9.7) | **rejected** — the >600 tail's edge SURVIVES: 3.34% → 1.74% mean net per pick (52% of base, above the 50% line), the strongest group at every cost level. The uniform-haircut model cannot see impact/non-fill — the fill model (Phase 5) is the open question, not the cost constant. Phase 6 default set to 0.5% per side (edge 82% of base), all three levels reported. See 2026-09-25 E006 block | 2026-09-25 |
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

---

## Phase 2 (M1) complete — universe + labels (2026-09-23, uncommitted; working tree on `8df273b`)

Not an experiment — the plan's Phase 2 checkpoint ("show 3 winner lists side by side with
re-computation"). Recorded because the audit found three BRD §4 rules that existed only in config
or docstrings, and because one of them falsifies a stated assumption in the BRD.

### The audit: plan Phase 2 against the working tree

| Task | Plan's done-when | Before this pass | Now |
|---|---|---|---|
| 2.1 as-of rank | 5 dates printed; stable MoM except real liquidity shifts; minutes not hours | **satisfied** (`rank.py` + the `liq_me` panel; 5 dates printed; Jaccard ≥ 0.85 asserted on all 12 transitions; 1.5–3.7s vs a 300s bar) | unchanged — not rebuilt |
| 2.2 eligibility | BRD §4 as a pure function from config; 6 hand-built cases (T2T, low turnover, recent listing, GSM-flagged, rank>1500, normal) | **partial**: 4 of §4's rules present; series rule hardcoded rather than from config; turnover floor dead config; GSM/ASM implemented nowhere. Of the 6 cases: normal, rank>1500 and recent listing covered; **low turnover and GSM-flagged had none**; T2T covered only at the rank layer (BE never ranks) and unanswerable in the point form | completed (below) |
| 2.3 winners | top 5% + top-20 + top-decile; 10 random months recomputed, 10/10 | **satisfied** with one documented deviation; checkpoint lists not printed | checkpoint artifact added (below) |

What 2.2 was missing, and what it cost: the series rule lived as a hardcoded `'EQ'` string in
`rank.py`, `panels.py` and `eligibility.py` while `universe.allowed_series` — the config key that
owns it — was never read (plan working rule 1). All ~180 series codes in `bhav` were checked to
settle it: **`"T2T"` appears in no row** (BE is the trade-to-trade series that actually exists), so
the `exclude_series: [BE, T2T]` key was dead config and is gone. `panels.series_sql()` is now the
single renderer for the decision calendar, the liquidity panel, eligibility and rank's oracle, and
`allowed_series` is a `cfg:` spec in the panel stamp — changing it rebuilds the panels.

### Decision: BRD §4's "subsumed" ₹5-crore floor is measurably false

BRD §4 states: *"The ₹5-crore-turnover floor is subsumed by the top-1500 rank and kept only as a
config guard."* Nothing read the key, so the claim had never been tested. Measured on the quick
profile (13 decision months):

| Quantity | Value |
|---|---|
| Rank-1500 median daily turnover (pooled 3-month), by month | **₹1.01cr – ₹1.94cr/day** |
| In-universe symbol-months below ₹5cr | **6,010 of 19,500 (30.8%)** |
| Effect of enforcing the floor | excludes ~31% of the as-of universe |

**Decision: implemented, shipped OFF.** The floor is now a real config-driven rule (`> 0` excludes
with reason `turnover<Ncr`), but `min_median_turnover_cr: 0.0` leaves live behaviour BRD-normative —
the premise is false, the *policy* that follows from it (rank governs liquidity) is still the BRD's,
and silently relabelling 30.8% of the universe on a contradicted sentence is not an audit's call.
`_live_check` re-reports the measurement on every run so the claim can never go unverified again.
Switching it on is one config line, and it needs the BRD owner.

Implementation bug caught here: `med3` is in **rupees** while the floor is in **₹ crore**, so the
first version compared 1e8 against 15.0 and never fired. There is now one shared conversion
(`panels.RUPEE_PER_CRORE`, also used by rank's `med3_cr`).

### GSM/ASM: a real rule with no historical source

BRD §4 requires "not under GSM/ASM (as of D, where historical data exists)"; the code had nothing.
Now: `surveillance(symbol, effective_from, list, stage)`, excluded when `max(stage)` over rows with
`effective_from <= D` exceeds `universe.gsm_asm_max_allowed_stage` (default **0** — any listing
excludes). §8.2's *hold* rule (`gsm_asm_stage_exit: 2`, forced exit) is a different decision and
stays in the engine. `load_surveillance()` imports `paths.surveillance_csv` when a snapshot exists;
the CSV is the trust boundary, so rows are validated and a malformed one raises rather than being
skipped. Live, the rule reports itself honestly:

```
surveillance: none — no historical GSM/ASM archive exists (BRD §4 'where historical data exists'),
so the rule excludes nothing in the backtest
```

Exercised end to end on real data with a temporary snapshot: a symbol in the universe for all 13
months took eligible **17,204 → 17,191** (−13 = exactly its 13 months), the point form returned
`(False, ['gsm_asm'])`, and dropping the snapshot + rebuilding restored the baseline hash. Known
limits, recorded rather than hidden: no `effective_to`, so "left the list" is unrepresentable; the
table survives removal of the CSV (deliberate — a snapshot is an import, not a lease), which the
live check makes visible every run; and one bad row aborts the whole `build()` (robustness gap,
named in the audit, not yet fixed).

### The six cases the plan names

| Case | Fixture | Expected reasons at the Sep decision |
|---|---|---|
| normal | A, B | `''` (eligible) |
| rank>1500 (+ penny) | Y (rank 6, ₹5) | `rank>5,price<20.0,turnover<15.0cr` |
| recent listing | D (first month Aug) | `listed<6m,gsm_asm` |
| low turnover | C (rank 5 — **inside** the universe) | `turnover<15.0cr` |
| GSM-flagged | G (GSM stage 2 from Jan 2024) | `gsm_asm` |
| T2T stock | X (`BE`), Q (`'T'`) | never enter the rank; point form → `series_not_allowed` |

The low-turnover case deliberately mirrors the live finding: a symbol **inside** the top-1500 and
still excluded by the floor. `D`'s ASM begins Sep 1, so its Aug row must *not* carry `gsm_asm` — the
as-of test — while `A`'s flag (Oct 1) is after the window and must not exclude at all. Flipping the
stage threshold 0 → 2 makes G eligible again, then back to 0 re-excludes it, so the threshold is
provably config. One feature of the rewrite: table and point form are now compared **literally,
reason for reason**, and that caught a latent divergence — a NULL close suppressed the `listed`
reason in the point form only. Three live rows exercise it (SCANSTL 2026-08-31, BTTL 2026-09-22,
KAVDEFENCE 2025-09-30); all three now agree.

### 2.3 winners — satisfied, with one documented deviation

The done-when is met: top 5% (724 flags / 11 months), top decile 1,441, top 20 220, and an
**independent from-scratch pandas recompute matches 10/10 sampled months exactly** (worst per-symbol
return difference < 1e-9, winner sets identical). The deviation the plan should know about: the
recompute reads `adj_close`, not raw bhav ratios. Raw month-end ratios are not a return oracle —
a mid-month 10:1 split reads as −89% (GOLDADD, Aug 2026) and NSE vs Yahoo place dividend adjustments
differently (Feb 2026: 149 of 1,279 names diverging >5pts, in both directions) — while BRD §4 rules
that returns come from adjusted closes. The raw→bhav half of the chain is Phase 1's (task 1.4's
done-when plus the canaries), so the chain is verified in two halves rather than by a zips-level
oracle.

### Checkpoint: three winner lists, table vs recomputation

Now printed by the check itself, because a claim without a visible artifact is not a checkpoint:

```
2026-08-31: pool 1,337 | winners 67 (recomputed 67)
  table     : MOREPENLAB +87.87%, RATNAVEER +68.72%, INDSWFTLAB +62.69%, KENNAMET +55.81%, SHILPAMED +55.30%
  recomputed: MOREPENLAB +87.87%, RATNAVEER +68.72%, INDSWFTLAB +62.69%, KENNAMET +55.81%, SHILPAMED +55.30%
2025-11-28: pool 1,282 | winners 65 (recomputed 65)
  table     : SILVER1 +66.07%, THANGAMAYL +49.98%, RICOAUTO +44.96%, CUPID +40.95%, LGBBROSLTD +38.34%
  recomputed: SILVER1 +66.07%, THANGAMAYL +49.98%, RICOAUTO +44.96%, CUPID +40.95%, LGBBROSLTD +38.34%
2025-10-31: pool 1,304 | winners 66 (recomputed 66)
  table     : GMBREW +74.60%, MCLEODRUSS +67.17%, SHAREINDIA +46.20%, INDOTHAI +43.18%, TATVA +40.56%
  recomputed: GMBREW +74.60%, MCLEODRUSS +67.17%, SHAREINDIA +46.20%, INDOTHAI +43.18%, TATVA +40.56%
independent recompute: 10/10 months match exactly (returns < 1e-9, winner sets identical)
```

### Zero drift: the audit changed no label

Snapshotted before the first edit, compared by hash after the last:

| Table | Baseline (before) | After | |
|---|---|---|---|
| `eligible` | 33,567 rows / 17,204 eligible / reasons_hash `309004543472110316846433` | identical | **IDENTICAL** |
| `winners` | 14,373 / 724 win / 1,441 decile / 220 top20 / labels_hash `132390852150023982609164` | identical | **IDENTICAL** |
| `universe_rank` | 33,567 rows / rank_hash `310020180659703283487795` | identical | **IDENTICAL** |

That is the property that mattered: the series rule was re-expressed (not changed in effect), the
floor stayed off, and the surveillance table is empty — so every number Phase 3 will join to is
bit-for-bit what it was. Suite after the change: `python -m src.selfcheck` → **ALL PASS (13 checks)
in 28.5s**.

### Open items for the next pass

1. **The ₹5cr floor decision** — the premise is falsified; enforcing it cuts ~31% of the universe.
   Needs the BRD owner, not an agent.
2. **`eligible()` is not the "pure function" the plan asks for**: it needs an open connection *and*
   the `month_history` table that only `build()` creates (on a fresh DB:
   `CatalogException: Table with name month_history does not exist!`).
3. **The rule set has two owners**: `_CHECKS` (SQL) and the point form's if-chain must be
   hand-synchronised — the divergence found above is the class, and fixing that class is the
   highest-value next pass.
4. **A malformed surveillance row aborts the whole build** (and with it the daily refresh chain)
   instead of being quarantined.
5. Minor, recorded for honesty: `eligible` keeps the partial September month while `winners`
   excludes it (benign — no return is provisional — but previously undocumented); 2.1's "5
   hand-picked dates" are deterministic picks (first, quartiles, last); and printing `₹` raises
   `UnicodeEncodeError` on this cp1252 console, so new output says `Rs`.

---

## Experiment E002 — univariate IC sweep (2026-09-24, profile `quick`)

- **Prediction (pre-registered in the ledger row above and in
  `experiments/002_ic_sweep/hypothesis.md`, written before the run):** 6–12M momentum and
  delivery% z-score have positive pooled Spearman IC, surviving BH at α = 0.05.
- **Run:** `experiments/002_ic_sweep/run.py --profile quick` — 22 features × 11 decision months,
  14,373 labeled rows (as-of top-1500 universe), cutoff 2026-09-22, git `d37580c`, 64s. All
  per-month and pooled ICs, p-values, top-5% precisions and the BH step-up are in
  `experiments/002_ic_sweep/results.json`; every number is reproducible from that config snapshot.
- **Verdict: PARTIALLY CONFIRMED.**
  - **CONFIRMED, right sign, BH-surviving: `mom_12m_1m` pooled IC +0.065 (p = 2.5e-14) — exactly
    the +0.065 the M2 momentum canary measured on its own universe, now on the as-of top-1500
    with the proper forward label.** `mom_1m` −0.095 (p = 2e-30): monthly reversal confirmed at
    the pre-registered negative sign, top-5%-by-value precision 72%.
  - **REJECTED, pre-registered positive direction: `delivery_pct_zscore` IC −0.010
    (p = 0.22, not even significant).** The E001/E002 delivery prior is falsified on quick data.
  - **`mom_6m` IC −0.024 (p = 0.004, wrong sign): rejected as a positive-direction prior** —
    on 12 months of quick data the 6M horizon still carries reversal, not momentum.
  - **Direction-agnostic findings (no pre-registered direction, reported not celebrated):**
    `squeeze_days_20d` −0.196 (p = 7e-123) and `atr_ratio` +0.126 (p = 2e-51) are the two
    strongest signals in the sweep — **low volatility predicts higher next-month returns** on
    this universe (volatility-compression "breakout lore" points the WRONG way here), and
    `volume_zscore` +0.106. Volatility-state features dominate the sweep; most candle features
    are weak-to-negative.
  - 18 of 22 features survive BH (n = 14k ⇒ tiny ICs are "significant"); the discipline that
    matters is the pre-registered sign + the per-month view: pooled ranks mix market-wide level
    shifts, and several features flip sign between pooled and monthly means (e.g. `mom_3m`
    pooled −0.019, monthly mean +0.028) — pooled-only verdicts would be fragile. The 0.10 IC
    "conventional" threshold leaves only `mom_12m_1m` (monthly mean +0.102) standing.
- **Honest caveats:** quick profile = 11 months, one regime; monthly IC counts are small
  (~1,300 rows/month) so per-month ICs are noisy; multiple-testing across 22 features is
  handled by BH but the direction-agnostic features get no such protection — their findings are
  hypotheses for E001/the full-profile re-run, not conclusions. The full-profile sweep is the
  same code with `--profile full` and is NOT pre-registered here.
- **Consequence for the plan:** Phase 4's composite (4.1) must rank-average features that
  survived E002 **with the measured signs** — low volatility is now a candidate factor, the
  delivery z-score is not.

---

## Refactor — `end_date` removed from config; the cutoff is the data (2026-09-25, uncommitted; working tree on `440e923`)

Not an experiment — an infrastructure pass in the M2.2/M2.3 line: it changed **where the pipeline's
data cutoff lives** and removed the one write the daily refresh made to a versioned file. No
experiment, label, or universe number moved; the zero-drift evidence is below.

### What moved where

| Was (M2.3 state) | Now |
|---|---|
| `config.yaml` carried `end_date: "2026-09-22"`, and the refresh **rewrote that line** every evening (`bump_end_date`, regex edit + atomic replace, adopted precisely because a yaml round-trip would have eaten the file's comments) | the key is **gone from config**, and `config.load()` now **refuses** a config that carries it — the class of state-in-config problems is deleted, not guarded |
| every stage trusted the config value as the cutoff | **`panels.data_cutoff(con)` is the single source of truth**: `max(bhav.date)`, read-only, with an empty/missing-bhav sentinel. bhav (the price backbone) decides — the delivery feed's one-day lead still must not move the cutoff (validate.report keeps classifying that as informational) |
| rank/winners formatted `end=cfg["end_date"]` into their SQL | `end=panels.data_cutoff(con)` — the database cannot disagree with the build inputs |
| validate.report's holes-vs-ahead split and adj_close's `_window_start` empty-table fallback read `cfg["end_date"]` | same reads against the database cutoff (`_window_start` still honors an `end_date` cfg key, explicitly marked backward-compat, so its self-check stays pure/offline) |
| refresh owned `asof_date()` (cutoff-gated today-or-yesterday, `--date` wins); the three downloader month loops self-bounded to `date.fromisoformat(cfg["end_date"])` | `asof_date()` moved to **`src/download/_http.py`** — the module every downloader already imports (a refresh-side home would make the backfill tools import refresh: a cycle); the downloaders bound their loops to the **as-of fetch-plan bound** (`cfg["fetch_asof"]`, set per-process by the refresh from its `--date`), and the backfill tools use it as their end bound |
| `git status` dirty after every refresh (`config.yaml` always modified) | the refresh writes **no repo file**; a run's outputs are the raw cache, the DuckDB tables and `data/refresh.log` |

The downloaders' upper bound changed meaning, deliberately: "config end_date" was *stored state*;
the as-of bound is *the fetch plan*. Same effective coverage on every real run (the refresh passes
`--date asof`; the live months sit under both bounds), but a downloader now refuses days the plan
did not ask for rather than days past a file line — and can never again be the thing that silently
clamps a catch-up run.

### Bug caught while re-auditing for this block

The first pass left `refresh.main()` still setting `work["end_date"] = asof` — a key the
downloaders had stopped reading. Harmless on the routine path (as-of defaults to the same
cutoff-gated yesterday), but a `--date 2026-09-15` catch-up would have fetch-planned the whole
current month instead of stopping at the 15th. Fixed: the plan key is `fetch_asof`, and the
as-of date flows from the one place that owns it (`--date` → `asof_date` → the downloaders'
`_http.asof_date` bound). Proven live: with `fetch_asof: 2026-09-21` the udiff month loop accepts
Sep-1 rows (its bounds check passed the probe before the probe's toy config ran out of fixture),
and the module self-check pins both refusal directions.

### New invariant replacing the old write

`bump_end_date` was the refresh's mechanism for keeping the cutoff monotonic. It is gone with the
key, so the guarantee moved into an assertion right after normalize:

```python
if not after["bhav"][1] or after["bhav"][1] < before["bhav"][1]:
    raise AssertionError(f"normalize shrank bhav: {before['bhav'][1]} -> {after['bhav'][1]}")
assert after["bhav"][1] <= asof, f"bhav holds {after['bhav'][1]}, past as-of {asof}"
```

A normalize run can no longer silently lose the newest bhav day (which would move every downstream
cutoff, rank and label backwards), and bhav cannot hold a date past the fetch plan. The refresh
log now states the property outright: *the cutoff downstream stages read is that bhav max date
(panels.data_cutoff)*.

### Zero drift, measured

The refactor rewired reads only, so the derived tables must be bit-identical. Every chain stage
was rebuilt through its real entry point and compared to the Phase 2/3 checkpoints above:

| Table / check | Baseline (this ledger) | After the refactor | |
|---|---|---|---|
| data cutoff | config `end_date: 2026-09-22` | `2026-09-22` from `max(bhav.date)` | **IDENTICAL** |
| `universe_rank` | 33,567 rows / 13 decision months | 33,567 / 13 | **IDENTICAL** |
| `eligible` | 17,204 eligible of 33,567 | 17,204 of 33,567 | **IDENTICAL** |
| `winners` | 724 winner flags / 11 months | 724 / 11 | **IDENTICAL** |
| independent recompute | 10/10 months exact (returns < 1e-9, sets identical) | 10/10, same months printed side by side | **IDENTICAL** |
| `feature_panel` / `feature_matrix` | 17,204 rows; labeled 14,373 at 5.0% winners | 17,204; 14,373 / 5.0% | **IDENTICAL** |

Suite after the change: `python -m src.selfcheck` → **ALL PASS (17 checks) in 57.8s**, and
`config.load()` reports `end_date in config: False` — with the new guard in place, a config that
tried to bring the key back refuses to load rather than silently half-working.

### Honest caveats

1. The three downloader self-checks now pin their offline upper bound to an explicit `fetch_asof`
   fixture and take the live bound from the database cutoff — the month-count asserts are
   unchanged (2024-01: 21 files, 2026-08: 21, MTO 20), but the *mechanism* of the bound changed;
   anyone diffing M2.3's check descriptions against these will see that, and it is intended.
2. The as-of bound is one knob with two spellings: `--date` (the refresh's CLI) and
   `cfg["fetch_asof"]` (what the downloaders read). The refresh is its only writer today; a
   future second caller should go through `_http.asof_date` rather than invent another.
3. `_window_start`'s backward-compat `end_date` branch exists so its self-check stays pure and
   offline; nothing in the repo sets that key anymore. If a third caller ever appears, delete the
   branch and test against the database cutoff instead.

Consequence for the plan: actionplan's M2.3 status clause "the scheduler's `end_date` write is
now atomic" describes a mechanism that no longer exists — the write is gone, and the 2026-09-23
audit finding it answered is closed at the root rather than defended in place.

---

## Experiment E001 — anatomy of winners (2026-09-25, profile `quick`)

- **Prediction (pre-registered in the ledger row above and in
  `experiments/001_anatomy/hypothesis.md`, written before the run):** winners' 12M−1M momentum
  and 20-day delivery% z-score distributions sit above the eligible rest (median shift > 0),
  judged by tie-safe AUC, BH across 22 features, and per-month sign consistency, with a
  pre-registered size-bucket split as the small-cap-artifact check on E002's volatility
  finding.
- **Run:** `experiments/001_anatomy/run.py --profile quick` — 22 features, 14,373 labeled rows
  (724 winners), 11 decision months, cutoff 2026-09-24, 1.8s. All shifts, AUCs, p-values,
  BH flags, regime and bucket splits are in `experiments/001_anatomy/results.json`.
- **Verdict: PARTIAL** (details in the ledger row and `verdict.md`). Momentum anatomy
  confirmed; delivery anatomy rejected (second independent falsification of the delivery
  prior); the volatility-state direction is the strongest and most consistent winner anatomy
  on this window — against the pre-registered lore direction — and it is uniform across size
  buckets, while momentum's separation concentrates in the top/mid buckets.
- **Honest caveats:** quick profile = 11 months, all of them up-regime, so the pre-registered
  regime split was vacuous (needs the full-profile re-run to mean anything); the pooled
  tail-vs-bulk disagreement on mom_1m/mom_3m (pooled positive, monthly bulk reversal) is
  flagged for E002b, not resolved here; E001 shares E002's window, so "confirmed" here means
  "confirmed on the same 11 up-months", not out-of-sample.

### Live verification (2026-09-25) — and one bug the live run caught

First real execution of the committed code: `python -m src.download.scheduler --once`, pre-cutoff
(10:52 IST), as-of 2026-09-24, a genuine 2-day gap to close (stored cutoff was 2026-09-22).

| Step | Result |
|---|---|
| 404 eviction for the target date | 1 entry dropped, re-probed NSE (the M2.3 mechanism, unchanged) |
| fetch + normalize (2 missed days, cache-skip after an interrupted first attempt) | bhav **7,899,813 → 7,907,146 rows**, cutoff **2026-09-22 → 2026-09-24**; delivery 6,262,863 → 6,268,195; adj_close +1 straggler row (the 4-missing self-heal queue from M2.3) |
| cutoff provenance | the log states it outright: *the cutoff downstream stages read is that bhav max date (panels.data_cutoff)* — no config write anywhere |
| derived rebuild | `universe_rank` 33,563 rows / 13 months, `eligible` 33,563, **winners 724 over 11 months (unchanged)** |
| verification gate | selfcheck **ALL PASS (17 checks) in 294.2s** inside the refresh; scheduler verdict **ok: caught up to 2026-09-24, exit 0** (336s) |
| repo hygiene | `git status` after the run: clean apart from the one-line fix below — the property this refactor exists for |
| Yahoo lag (documented, by design) | newest NSE day 2026-09-24: 804/2,664 traded symbols priced — placeholder NaN rows refused, queued for the next run |

**The bug:** the refactor's constants cleanup deleted `LOG_PATH` along with `CONFIG`, and the
refresh crashed with a `NameError` **after all data work had succeeded** — exit 1 on a run that
had caught up. The scheduler judged it exactly right (`FAILED: the refresh did not complete
(stored 2026-09-24, as-of 2026-09-24)`, traceback tail logged per-event, retry scheduled), which
is the verdict logic working as designed against the new cutoff path — and the per-event log
captured the whole failure, the exact killed-run record M2.3's logging change exists for. Fixed
by restoring the constant; the lesson is the same one M2.3 learned: self-checks green ≠ the job
entry point exercised. The live run is the check.

---

## Experiment E002b — full-profile confirmation IC sweep (2026-09-25, profile `full`)

- **Why a new experiment:** E002 ran on `quick` (11 decision months, one regime) and its own
  row pre-registered that the full sweep "is NOT pre-registered here". Running more data
  through the same code after seeing quick results would be post-hoc; `E002b`'s hypothesis
  (written before the run) fixes the method instead: **mean monthly Spearman IC with a
  one-sample t-test across months** — month fixed effects removed by construction, closing
  the pooled-ranks fragility E002's verdict itself flagged. E002 is frozen and unedited.
- **Run:** full-profile derived chain rebuilt through its real entry points (panels 5.7s,
  rank 6.2s, eligible 8.0s, winners 8.3s, feature_panel 59.0s, feature_matrix 0.9s → 218,648
  rows × 183 decision months), then `experiments/002b_ic_sweep_full/run.py --profile full` —
  22 features, **178,171 labeled rows / 181 measured months**, cutoff 2026-09-24. All mean
  monthly ICs, t/p values, BH flags, pooled-raw-IC continuity columns and the regime/bucket
  splits are in `experiments/002b_ic_sweep_full/results.json`.
- **Verdict: CONFIRMED, with one major reversal** (details in the ledger row and
  `verdict.md`):
  - `mom_12m_1m` +0.052 (p = 1.1e-6, BH ✓, 64% of months) and `mom_6m` +0.024 (BH ✓) — the
    momentum prior survives 15 years, and it is counter-cyclical: down-months +0.099
    (75% of 69) vs up-months +0.023 (n.s.).
  - **The delivery family is confirmed at full history** — `delivery_pct` +0.049
    (t = 7.2, p = 1.2e-11, 72% of months), trend +0.023, z-score +0.017 (all BH ✓). E002's
    quick-profile rejection was a bull-window artifact: delivery IC is +0.087 in down-months
    (87%) vs +0.026 in up-months. The two experiments deliberately disagree; E002b is the
    citation.
  - `atr_ratio` is a **regime-flipping** feature: +0.045 in up-months (matches E001's
    quick-window anatomy) and **−0.183 in down-months** (94% of 67, p = 7e-19). Low-vol is a
    crash factor, not an all-weather one. Five candle/accumulation features (up-down ratio,
    breakout, close_in_range, higher-lows, big-body) are BH-rejected on direction at full
    history.
- **Bucket attribution:** the confirmed features price the whole universe (mom_12m_1m
  0.038/0.049/0.052, delivery_pct 0.047/0.059/0.054 across top200/201–600/601–1500) — 15
  years overrules E001's quick-window impression that momentum dies in the small-cap tail.
- **Method note:** the first run of the splits counted month×bucket cells as months
  (336+207 = 543 "months", p-values anti-conservative); caught by the months-not-summing
  sanity check and fixed before any verdict was written — regime stats now use one IC per
  month over the full cross-section (112 + 69 = 181).
- **Consequence for the plan:** Phase 4's composite candidates are `mom_12m_1m` (+),
  `mom_6m` (+), `delivery_pct` (+), with `atr_ratio` as a regime-conditional overlay; the
  delivery features are correlated (one family = one vote). E002's verdict stands as
  written; its "delivery falsified" claim is superseded by this row, and the status line at
  the top of this plan is updated accordingly.

---

## Experiment E000 — universe overlap (2026-09-25, profile `full`)

- **Source decision (settled pre-run, recorded in `hypothesis.md`):** historical Nifty 200
  membership has no clean source (yfiua.github.io does not carry NIFTY200; index-report
  scraping is a plan non-goal), so E000 ran on the **current** constituents CSV
  (`data/index/ind_nifty200list.csv`, 200 validated symbols, hand-downloaded from
  `nsearchives.nseindia.com` — the same trust-boundary pattern as the surveillance snapshot)
  applied as-of to every year, with the survivorship bias disclosed and its direction argued
  (it understates overlap → conservative for the verdict that matters).
- **Run:** `experiments/000_universe_overlap/run.py --profile full` — 15 December decision
  years, per-year overlap from `universe_rank` and hit-rate delta from `eligible`/`winners`
  with the forward label. All counts in `results.json`.
- **Verdict: REJECTED on the letter of the pre-registered rule, noise-bound in substance**
  (details in the ledger row and `verdict.md`):
  - overlap: **min 97.7% / mean 98.7%** — the top-1500 as-of universe contains the Nifty 200
    in every year; index membership is never needed on the critical path.
  - hit-rate delta: mean yearly |Δ| 2.48pp fired the ≥ 2pp trigger; at ~130 labeled N200
    names/year the binomial noise floor is ±1.91pp, and the **pooled** |Δ| (not the
    pre-registered trigger, reported as the tiebreaker) is **0.86pp** (5.04% vs 4.17%, 741 vs
    94 winners) with noise sd 0.46pp — small, likely real, immaterial.
  - recommendation to the BRD owner: keep top-1500; N200-only would discard ~85% of labeled
    rows for ~0.9pp of hit rate within yearly noise.
- **Honest caveats:** early-year N200 rows are the least trustworthy (today's list applied
  as-of; 71/200 names did not exist by end-2011); 2011's 0/123 N200 hit rate is the noise
  floor, not a finding; the pooled 2σ significance was not family-corrected.
- **Method note:** the survivorship-drift column was initially computed from the trading
  subset (structurally zero — a mislabeled denominator). Caught on the live run and fixed
  before the verdict: `not_ever_traded_by_year_end` now reads the snapshot directly.

---

## Experiment P4.1 — composite score v0 (2026-09-25, profile `full`)

- **Universe decision implemented:** as-of top-1500, turnover floor OFF — the top-1500 /
  floor-off default from `docs/brd_decisions_universe.md`, flagged BRD-owner-review-pending
  in the pre-registration. (The full-profile feature matrix had been left at the quick
  profile by the selfcheck suite's rebuilds; the chain was rebuilt through its real entry
  points before the run — 218,648 rows × 183 months, 47.7s.)
- **Prediction (pre-registered in `experiments/004_composite_v0/hypothesis.md`, written
  before the run):** the rank-average composite of the E002b survivors
  (`mom_12m_1m`, `mom_6m`, `delivery_pct`; equal weights, parameter-free) beats the best
  single feature on the pre-test-window validation slice (paired monthly t, α = 0.05); the
  atr-regime overlay is additive on the same test. The comparator is selected ON the slice
  (winner's curse included) — the conservative form of BRD M3's bar. The test window (last
  36 months, BRD §10.1; boundary 2023-09-24) is excluded and not scored.
- **Run:** `experiments/004_composite_v0/run.py --profile full` — validation slice
  **145 decision months / 132,530 labeled rows** (2011-07 → 2023-08), 35 test-window months
  excluded. All arm ICs, paired tests and precisions in `results.json`.
- **Verdict: INCONCLUSIVE — mom_12m_1m ships as v0** (details in the ledger row and
  `verdict.md`):
  - composite **0.0625** vs best single (mom_12m_1m) **0.0529** mean monthly IC; paired diff
    +0.0096, t = 1.91, **p = 0.0585** — the point estimate wins, the pre-registered α does
    not clear, and the tie rule (⇒ simpler ships) applies as written.
  - atr overlay **rejected**: 0.0223 vs 0.0625 (diff −0.0390, p = 0.0033) — E002b's
    regime flip is real in cross-section but the pre-registered trailing-market proxy
    dilutes the composite instead of capturing it. A real regime classifier remains an open,
    separately-pre-registrable idea.
  - top-5% precision on the slice: composite 55.4% > overlay 53.2% > single 53.0% — the
    composite's edge concentrates in the picked tail.
- **Consequence for the plan:** 4.1 ships the single feature; 4.2 (learned ranker) proceeds
  against the unchanged gate ("beats best single feature out-of-sample"), with the honest
  reference number to justify complexity being the composite's 0.0625. The walk-forward
  (Phase 6) remains the only result that counts (BRD §10).
- **Honest caveats:** p = 0.0585 is a near-miss recorded as a near-miss; the comparator's
  0.0529 carries its own winner's curse; nothing here predicts the Phase 6 test window.

---

## Experiment P4.1b — two-feature composite (2026-09-25, profile `full`)

- **Why:** P4.1's verdict flagged `mom_6m` as the weakest third vote (slice IC 0.0276 vs its
  siblings' 0.0529/0.0445) and asked, pre-registered, whether dropping it lets the composite
  clear the M3 bar the three-feature form missed (p = 0.0585).
- **Prediction (pre-registered in `experiments/004b_composite_2feat/hypothesis.md`, before
  the run):** `composite_2f` (mean percentile rank of `mom_12m_1m` + `delivery_pct`) vs the
  slice-selected best single (paired monthly t, α = 0.05) — same gate, same slice, P4.1's
  three-feature form recomputed as the within-experiment control.
- **Run:** `experiments/004b_composite_2feat/run.py --profile full` — reuses P4.1's slice and
  scoring code by importlib (the two experiments cannot drift); asserts the full-history
  matrix before scoring (145 months / 132,530 rows, boundary 2023-09-24; 35 test-window
  months excluded, untouched).
- **Verdict: CONFIRMED — `composite_2f` ships as Phase 4's v0** (details in the ledger row
  and `verdict.md`):
  - vs best single (mom_12m_1m, winner's curse included): 0.0681 vs 0.0529, paired diff
    **+0.0153**, t = 2.49, **p = 0.0140** — the gate clears.
  - vs the 3f control: +0.0057 (p = 0.196) — `mom_6m` was dead weight, not poison; the form
    wins by being simpler and no worse.
  - precision flip disclosed: top-5% slice precision prefers 3f (55.4%) to 2f (54.8%); mean
    monthly IC was the pre-registered primary, and the flip is recorded, not hidden.
- **Consequence for the plan:** the shipped v0 score is the two-feature composite; 4.2's
  ranker must beat it at the same gate (reference number 0.0681); task 4.3's freeze protocol
  applies to the two-feature definition. Phase 6 re-tests it out-of-sample — the only result
  that counts (BRD §10).
- **Honest caveats:** post-hoc refinement after P4.1 (pre-registration is the only
  protection); shared slice with P4.1, family error unadjusted by pre-registration as
  declared; the comparator's 0.0529 is itself winner's-curse-optimistic.

---

## Experiment P4.2 — learned ranker (2026-09-25, profile `full`)

- **Prediction (pre-registered in `experiments/0042_learned_ranker/hypothesis.md`, before
  the run):** a HistGradientBoosting ranker, refit walk-forward monthly (fixed
  hyperparameters, never swept; all 22 E002 features; 1-month purge by label end; ≥ 24
  training months before the first fold), beats `composite_2f` on the paired monthly IC
  test at α = 0.05 — and the 4.3 freeze protocol reproduces its picks exactly.
- **Run:** `experiments/0042_learned_ranker/run.py --profile full` — **120 walk-forward
  fits** over the 145 validation months (25 warm-up months scored for the baseline only),
  ~130k training rows per late fold, boundary 2023-09-24, test window untouched.
- **Verdict: REJECTED — composite_2f ships** (details in the ledger row and `verdict.md`):
  - ranker **0.0402** vs composite_2f **0.0681** mean monthly IC; paired diff **−0.0221**
    over the 120 shared months, t = −2.45, **p = 0.0159** — significantly worse, a clear
    loss, not a tie. All-features rope + squared-error-on-raw-returns grabs noise the
    two-feature blindness avoids; the plan's gate design (composite first) did its job.
  - **Freeze protocol (4.3) passed inside the run:** `artifact/model_meta.json`
    (hyperparameters, feature list, sklearn version, seed, 120-fold manifest); first and
    last scored folds refit **bit-identically** (max |diff| 0.00e+00); the last fold's
    top-5% pick set reproduces exactly from a fresh refit; the artifact fold count
    round-trips. Re-running with saved artifacts reproduces picks — the plan's done-when.
- **Consequence for the plan:** Phase 4's model is `composite_2f`; Phase 6 walks it
  forward. sklearn enters `requirements.txt` with the justification the plan demands
  (no lightgbm; NaN-native matching the panel's missing-data semantics; deterministic under
  a fixed seed with early stopping off) — earned by the experiment even though the model
  lost, as the Phase 6 harness may need it for diagnostics.
- **Honest caveats:** hyperparameters were fixed a priori — a tuned ranker might close the
  gap, and that is a future pre-registration, not a loophole pulled now; the paired test
  uses the 120 shared months (warm-up excluded for the ranker arm); the gate is the
  validation slice only — BRD §10's walk-forward on the test window remains the only result
  that counts.

---

## Experiment E006 — cost sensitivity (2026-09-25, profile `full`)

- **Prediction (pre-registered in `experiments/006_cost_sensitivity/hypothesis.md`, before
  the run):** per plan 4.4 and the ledger row — the net edge at 0.2% per side does not
  survive 1.0% for picks ranked below ~600 (BRD §9.7). Rule: >600 edge halves by 1.0% ⇒
  partial; turns negative or below 25% parity ⇒ confirmed; survives ≥ 50% ⇒ rejected.
- **Run:** `experiments/006_cost_sensitivity.run --profile full` — composite_2f's top-5%
  picks (6,622 pick-months, 145 validation months, boundary 2023-09-24), net = gross −
  2 × cost at 0.2 / 0.5 / 1.0% per side, split by the §9.7 rank boundary (≤ 600 vs > 600)
  and by size bucket. Test window excluded as in P4.1/P4.1b/P4.2.
- **Verdict: REJECTED — the warning does not bind at equal fills** (details in the ledger
  row and `verdict.md`):
  - rank > 600: **3.34%** mean net per pick at 0.2% → **1.74%** at 1.0% = **52.1% of base**,
    above the ≥ 50% survival line, positive at every level, and the strongest group at every
    level (rank ≤ 600: 2.25% → 0.65%).
  - the small-cap tail is the cost-resilient group, not the victim — the gross edge there
    (3.34% vs 2.25%) is bigger than the added cost.
- **The caveat that still bites (recorded in the verdict):** the scan models cost as a
  uniform haircut on month-end closes; it cannot see impact, slippage, or non-fill — the
  actual mechanism behind §9.7's warning. Conclusion: at equal fills the small-cap edge
  survives 1% costs; **whether fills are equal is Phase 5's fill model's job to test** (T+1
  open, circuit locks, liquidity-aware slippage) before Phase 6 believes it.
- **Consequence for the plan:** the Phase 6 report's default cost assumption is set to
  **0.5% per side** (edge at 82% of base; 0.2% optimistic for a 601–1500-heavy pick set,
  1.0% survivable but halves the hit rate), with all three levels reported per §9.7.
- **Honest caveats:** pick-level means on a fixed top-5% slice ignore slot competition and
  capacity; month-end-close fills differ from the engine's T+1 open; validation slice only —
  Phase 6 re-asks this inside the real engine on the test window.

---

## Phase 5 checkpoint — engine + portfolio rules + toy momentum, end to end (2026-09-26, commit `d0125bf`)

Not an experiment — the plan's Phase 5 checkpoint line ("run engine on synthetic data with a
trivial buy momentum model. Show equity curve + trade log"). With 5.6 (bucket attribution)
landed the same day, all Phase 5 tasks (5.1–5.6) are done; this block records the integration
run the checkpoint asks to see: `src/backtest/checkpoint.py`, results in
`src/backtest/checkpoint_results.json` (config snapshot + git hash embedded).

### The tape (declared simplifications)

6 names × 19 sessions spanning 4 curve months (Jan–Apr 2026); every bar has **open == close**
so fill prices are exactly the marks; **zero costs and no ADV history** (the engine's gate and
impact are off) so every equity value is hand-computable to the rupee. Cost math is
engine-tested separately; E006's 0.5%/side default is a Phase 6 report parameter, not this
tape's job. n_slots = 2, start 100,000. The toy model scores each month as first-to-last
close return; the checkpoint's point is deterministic plumbing and exact paper math, not edge.

### The story — each §8 rule firing exactly once (all asserted)

1. **Jan 12, initial selection:** ME (+10%) and MO (+5%) lead the momentum board → top-2
   buys; T+1 fills land Feb 02 at the open (the month-boundary case).
2. **Feb 09, monthly review:** ME has faded to the 5th of 6 ranks (0.667 > the 0.25 sell
   percentile) → sell; MB (+7.9%, rank 0) is the only candidate inside the 15% replace
   percentile → replacement buy (221 sh @ 218), fills Mar 02.
3. **Mar 04, Trigger B stop:** MO closes 96.0 ≤ its 96.6 stop (entry 105 × 0.92; the 12%
   trail from the 110 month-high sits at 96.8 — the stop wins by trigger_b's priority order)
   → mid-month sell, fills Mar 05. The one churn event.
4. **Mar 09, review with a cash slot:** MO's freed slot finds no candidate inside the top
   15% (MB is held; every other name ranks 1/6 or worse) → the slot **holds cash** (§8.1
   fallback). ME is already out (its round trip completed Mar 02).

Trigger A and C never fire on this tape (the monthly momentum spread stays under the 20%
relative excess) — both are unit-tested in `src.backtest.portfolio`'s own check.

### Equity curve (19 rows, asserted exact)

```
date          cash   market_value    equity
2026-01-05  100000             0    100000   (…flat through 01-12: capital uninvested)
2026-02-02      25         99975    100000   T+1 fills: ME 909 @ 55, MO 476 @ 105
2026-02-03      25        100451    100476
2026-02-04      25        100018    100043
2026-02-05      25        100494    100519
2026-02-06      25        100061    100086
2026-02-09      25        100537    100562
2026-03-02      24        100538    100562   fills: ME -909 @ 53, MB 221 @ 218
2026-03-03      24         95999     96023   MO gaps down
2026-03-04      24         94316     94340   close 96 <= stop 96.6 -> Trigger B
2026-03-05   45244         48841     94085   MO -476 @ 95 fills
2026-03-06   45244         49062     94306
2026-03-09   45244         49283     94527
2026-04-01   45244         49283     94527
```

### Trade log (5 fills, asserted exact, engine order = (date, symbol, qty))

```
signal 2026-01-12  fill 2026-02-02  ME   909 @ 55.00  select_momentum
signal 2026-01-12  fill 2026-02-02  MO   476 @ 105.00 select_momentum
signal 2026-02-09  fill 2026-03-02  MB   221 @ 218.00 replace
signal 2026-02-09  fill 2026-03-02  ME  -909 @ 53.00  monthly_review
signal 2026-03-04  fill 2026-03-05  MO  -476 @ 95.00  trigger_b_stop
```

### Paper math (how every number above is derived)

- **Sizing:** 50,000/slot → ME 909 = floor(50,000/55) costing 49,995, MO 476 =
  floor(50,000/105) costing 49,980 → cash 25.0. (The first paper draft said 486 MO shares —
  486 × 105 = 51,030 overdraws the slot; the assert caught the arithmetic, floor is the rule.)
- **Replacement sizing:** the Feb 09 buy is sized on cash + expected sell proceeds
  (25 + 909 × 53 = 48,202 → 221 = floor(48,202/218)); it fills at exactly 218 because the
  tape pins MB's Feb 09 close to its Mar 02 open — on real data the est and the fill price
  diverge and the engine's cash guard (never negative) is what binds.
- **State moves twice, on purpose:** sell decisions free portfolio slots at decision time
  (portfolio.py's contract) while cash/positions move at the T+1 fill — the Mar 02 fills
  settle both the ME sale and the MB buy on one session.
- **P&L at Apr 01:** ME −1,818 realized (909 × (53−55)), MO −4,760 realized (476 × (95−105)),
  MB +1,105 open (221 × (223−218)); sum −5,473 = final equity 94,527 − 100,000, with cash
  45,244 + MB mark 49,283. The tape is hostile on purpose: both completed picks are losers,
  and the asserts still hold to the rupee.
- **Churn:** 1 mid-month sell / 4 curve months = 0.25/month (< the 1.5 §8.3 flag). (First
  draft divided by 12 sessions; the metric's window is curve months — caught by the assert.)

### Bucket attribution on the checkpoint's own picks (task 5.6, review gates enforced)

```
201-600   picks 1   hit  0%   mean  -3.64%   churn/mo 0.00    (ME: Jan decision)
top200    picks 1   hit  0%   mean  -9.52%   churn/mo 0.25    (MO: Jan decision)
blended   picks 2   hit  0%   mean  -6.58%   churn/mo 0.25
```

601–1500 is absent: MB is still open, and the table only counts completed round trips.
Buckets are **as-of the decision month** — this checkpoint drove the fix that makes that
true: `TradeEvent` now carries `signal_month`, because a month-end signal fills in the next
month and attribution keyed on the fill month would file Jan's picks under February.

### What the checkpoint caught

- the real `signal_month` provenance fix above (a genuine attribution bug, not a tape quirk);
- two paper errors of the author's own (486-vs-476 share sizing; churn window in sessions
  vs months) — the asserts did their job, which is the point of asserting hand-computed
  values rather than re-deriving them in code.

### Honest caveats

1. Zero costs / no ADV gate are declared simplifications (see The tape); a real run adds
   E006's 0.5%/side, impact, and non-fills — the fill model remains the open question.
2. The toy momentum model is not composite_2f; Phase 6 wires the real model to real data.
   Nothing here predicts the test window — BRD §10's walk-forward stays the only result
   that counts.
3. Trigger A/C and the delisting/suspension paths are unexercised on this tape (unit-tested
   in their own modules); a tape that fires them end to end remains possible future work.
4. Determinism is asserted by running the checkpoint twice and comparing curve, trade log
   and decisions bit-for-bit; the run is 0.1s and registered as selfcheck
   `backtest.checkpoint` — suite **ALL PASS (23 checks)** after this block.
