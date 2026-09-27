# E020 — the joint path: index core + breadth satellite blended, drawdowns on one equity curve

Pre-registered 2026-09-27, **before the run** (BRD §12): the arms, guards, bars and
decision rule below are frozen. The runner is implemented after this file exists and the
file is never edited afterwards; the verdict is written beside it as `verdict.md`.

## Motivation

E019 (LEDGER 2026-09-27) measured the deployable breadth book: +25.77% CAGR but a −47.02%
maxDD — an 18pp-worse ride than the index. Its FAIL clause named the recommendation (index
core + breadth satellite) and its required measurement: drawdowns are NOT additive, so the
blended maxDD must come from a joint monthly path, not from averaging two numbers. This
experiment computes that path.

## Window

The 145-month validation slice (2011-07-29 → 2023-07-31), same months as E018/E019. Test
window untouched.

## Arms (frozen — the satellite size sweep)

The joint account: fraction w in the index core (Nifty 500 TRI, month-end marks), 1−w in
the E019 deployable breadth book (arm A: real costs 0.105%/side, 12-month holds, 3% cap,
no stops). The blend REBANGLES monthly: each month the total equity is re-split w/(1−w)
between core and satellite (a constant-mix rebalance; the only way a fixed w is
maintainable, and the way a real account would be managed).

- **A 90/10** (w = 0.10 satellite)
- **B 80/20**
- **C 70/30**
- **R REFERENCE: pure index** (w = 0)

## Guards (frozen; all must pass for the run to count)

- **G1** the satellite leg's monthly series equals E019's committed arm A equity curve to
  1e-9 (same sim, re-used — no re-tuning).
- **G2** the index leg equals the sourced Nifty 500 TRI month-end series used by every
  prior index-equivalent line (+13.17% CAGR / −28.87% maxDD over this slice).
- **G3** no look-ahead: the blended path at month t uses only marks dated ≤ t (verified by
  recomputing the blend from the two committed curves — a pure post-hoc combination).

## Bars (frozen)

- **B1 (primary):** at least one satellite size w ∈ {0.10, 0.20, 0.30} delivers blended
  CAGR ≥ pure-index CAGR + 2.0pp (a real, deployable improvement over doing nothing).
- **B2:** that same arm's blended maxDD ≤ the index's −28.87% + 3.0pp (≤ −31.87%): the
  blend must not be a meaningfully worse ride than buy-and-hold. (Tighter than E019's
  10pp — the whole point of blending is risk control; 3pp is the tolerance.)
- **Recorded, not gating:** blended Sharpe per arm; the worst month; the 2018–2020
  sub-window drawdown; the w that maximizes CAGR subject to B2.

## Decision rule

PASS iff B1 and B2 hold for the same w, all guards green. On PASS: the blend (w as
passed) becomes the recorded recommendation for a design freeze — the test-window
confirmation is then the only remaining step before anything ships, and it must use this
exact w. On FAIL (no w gives +2.0pp within the drawdown tolerance): the recorded
recommendation is pure indexing; the breadth signal is filed as a research result with no
deployable configuration, and further breadth-family work on this slice is prohibited.

Disclosures rule: any deviation between coded bars and these words is recorded in
`results.json` (`bars`, `bars_as_coded`) the E013/E014 way.
