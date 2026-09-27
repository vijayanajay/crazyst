# E019 — the deployable breadth book: one book, monthly 1/12th turnover, execution realism — the final pre-freeze measurement

Pre-registered 2026-09-27, **before the run** (BRD §12): the arms, guards, bars and
decision rule below are frozen. The runner is implemented after this file exists and the
file is never edited afterwards; the verdict is written beside it as `verdict.md`.

## Motivation

E018 PASSed with cohort arithmetic (+29.6% CAGR for the rank-weighted decile) and flagged
its own gap: overlapping cohorts are a statistic, not an account. The deployable object is
ONE book that starts empty, fills over its first 12 months, turns over ~1/12 per month
thereafter (each leg held exactly 12 decision months), pays the fill gate and impact cap
the engine already models, and holds real cash until its first entries. This experiment
measures THAT object on the validation slice — the last measurement before the design
freeze; the test window is spent at freeze.

## Window

The 145-month validation slice (2011-07-29 → 2023-07-31, boundary 2023-09-24), labeled
(tradeable) rows only — E018's G0 convention. Test window untouched.

## The book (frozen — this is the design being frozen)

- Universe: the top decile of each month's scored cross-section (`round(10%)`, E018's B),
  drawn from labeled rows.
- Weights: rank-weighted at entry (weight ∝ 1/rank position, normalized across the WHOLE
  book, not per cohort — the deployable object is one portfolio).
- Entry: at the month-end decision close + real-world round-trip cost 0.21% per side
  change (0.105%/side; the E018 real-cost analysis).
- Hold: exactly 12 decision months, then exit at the decision close (no stops, no trails —
  E017 measured the whipsaw; the breadth book's diversification IS the risk control).
- Cash: earns 0%; a leg that stops trading exits at its last traded mark (E018's proxy).
- No leverage, no margin; the book is always ≤ 100% invested by construction
  (weight cap: each name ≤ 3% of book at entry — concentration guard).

## Arms (frozen)

- **A DEPLOYABLE** — the book above, simulated as a single account: monthly cash-flow
  ledger (buys drain cash, sells refill it), equity marked at month-end, costs deducted
  at each trade. This is the headline.
- **B DEPLOYABLE_MODELED_COST** — same book at the shipped 0.5%/side model (the
  pessimism bound).
- **C COHORT_REFERENCE** — E018's B cohort estimator re-run on this slice for continuity
  (not a new number; the bridge between E018's statistic and A's account).

## Guards (frozen; all must pass for the run to count)

- **G1** arm C json-equal to E018's committed `arms["B DECILE_RANK_W (real costs)"]`
  (same estimator, same slice — continuity proof).
- **G2** tape pins: labeled top-5% picks == 4,579 (exact); mean monthly IC ==
  `smoke.SLICE_IC_PIN` to 1e-9; decile median width in [55, 85] (E018's amended G4).
- **G3** no look-ahead: every leg's entry price is the mark at its own decision month's
  END (never earlier), verified by recomputing 100 random legs from fresh per-leg queries
  (the E015 G3 pattern).
- **G4** weight cap holds: no name > 3% of book value at entry, and the book is never
  levered ( invested + cash == equity within 1e-6 every month).

## Bars (frozen)

- **B1 (primary):** arm A's monthly-account CAGR ≥ +15% over the slice (the deployable
  object, cash drag and turnover-transition included — deliberately above E018's +10%
  cohort bar because the account must carry its own transition).
- **B2:** arm A's maxDD ≤ the index's maxDD over the same months + 10pp (E018's bar).
- **Recorded, not gating:** turnover/year (expect ~100% in year 1, ~12%/yr steady state);
  the 2018–2020 sub-window; B vs A (cost-model sensitivity); the index-equivalent line
  (+13.17% / −28.87%).

## Decision rule

PASS iff B1 and B2 hold, all guards green. On PASS: the design is FROZEN as specified
here and the next exposure of this configuration is the TEST WINDOW (harness convention,
no re-tuning); any further validation-slice iteration on the breadth family is prohibited
by this pre-registration. On FAIL: the deployable object's frictions (transition cash
drag, concentration cap, single-account path variance) eat the cohort gap, and the
recorded recommendation reverts to the index core + breadth satellite blend with the
satellite sized by the FAIL margin.

Disclosures rule: any deviation between coded bars and these words is recorded in
`results.json` (`bars`, `bars_as_coded`) the E013/E014 way.
