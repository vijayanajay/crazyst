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
