# E000 — universe overlap: as-of top-1500 vs Nifty 200 (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12):** hypothesis written before `run.py` executes; predictions may not be
edited after. Only `results.json`, `verdict.md`, and the LEDGER verdict are written after.

**Question (BRD §4 / plan 3.8):** does the as-of top-1500 liquidity universe approximate the
BRD's large/mid-cap intent? Output: per-year overlap with Nifty 200 constituents, and the
hit-rate delta if winners were computed on the Nifty-200-only universe. This decides whether
index-membership data is ever needed on the critical path (plan non-goal: it is not, unless
E000 fails).

**Data source (decision recorded pre-run):** CURRENT Nifty 200 constituents, one static CSV
hand-downloaded from `https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv`
into `data/index/ind_nifty200list.csv` (the surveillance-snapshot trust boundary: a
human-fetched file, validated row by row by the loader). **Historical membership is not used:
no clean source exists without index-report scraping, which the plan forbids.** The snapshot
is applied as-of to every year — a deliberate, disclosed survivorship bias:

- names that LEFT the index (shrank, were delisted, reclassified) are absent from the
  denominator in ALL years, including years they were members — the overlap therefore
  UNDERSTATES what an as-of membership list would show, biasing the verdict against the
  as-of universe (the conservative direction);
- names that JOINED recently are counted in years before they joined, biasing overlap the
  other way (they are, by construction, liquid today); per-year counts of not-yet-listed and
  not-trading snapshot names are reported so the reader can see the drift.

**Metric:**

- For each YEAR (December decision month): `overlap% = |snapshot ∩ in_universe ∧ trading|
  / |snapshot ∧ trading|`, where "trading" = the symbol has a bhav row in that month and
  "in universe" = `universe_rank.in_universe` at that month's decision date (the as-of top
  1500). Names in neither the rank nor bhav that month are excluded from the denominator and
  counted in the report.
- Pooled verdict numbers: minimum and mean yearly overlap.
- **Hit-rate delta:** per year, winner rate (top 5% by adjusted forward return, the Phase 2
  `winners` flags) among `eligible ∩ snapshot` symbol-months vs among all `eligible`
  symbol-months. BRD's bar: the two universes differ by < 2 percentage points.

**Pre-registered prediction (the ledger E000 row):** overlap ≥ 80% of Nifty 200 constituents
per year; hit rates on the two universes differ by < 2pp.

**Decision rule (written pre-run):** E000 is **confirmed** iff every reported year's overlap
is ≥ 80% AND the mean |hit-rate delta| is < 2pp — index membership is then never needed. If
overlap fails but hit rates agree, the verdict is **partial**: the as-of universe is
broader-than-large/mid but the strategy's edge does not depend on the distinction (record
whether the winner sets are dominated by the overlap). If hit rates differ by ≥ 2pp, the
verdict is **rejected**: universe choice matters, and the BRD owner must decide whether the
strategy is a top-1500 strategy or a large/mid-cap strategy before Phase 6 reports numbers.

**Scope:** profile `full` (the as-of rank exists at full history — 183 decision months,
2011-07 onward). One snapshot, 15 years applied as-of, survivorship bias as above.
