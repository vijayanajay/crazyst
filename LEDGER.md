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
