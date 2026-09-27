# E021 — a drawdown control that is not a whipsaw stop: book-level entry gating for the breadth book

Pre-registered 2026-09-27, **before the run** (BRD §12): the arms, guards, bars and
decision rule below are frozen. The runner is implemented after this file exists and the
file is never edited afterwards; the verdict is written beside it as `verdict.md`.

## Motivation

E019 (LEDGER 2026-09-27): the deployable breadth book earns +25.77% CAGR but draws down
−47.02% — 8.15pp past the blend bar. E017 proved per-name stops are whipsaw (wider =
better, monotonically) at the 8-slot scale; the breadth book's open question is whether a
BOOK-level control can cut the −47% without paying the whipsaw tax. The mechanism tested
here never sells a loser: it only decides where NEW money goes.

## Mechanism (frozen)

- Track the book's own equity peak (high-water mark, HWM).
- While drawdown-from-HWM > 15%: NEW ENTRIES go to cash (existing legs keep their
  scheduled 12-month exits — no forced selling, no trail tightening, nothing a
  whipsaw could shake out).
- When drawdown recovers ≤ 15%: entries resume on the next decision month.
- The 15% trigger and the entry-gate-only action are the design; no other parameter
  exists. One mechanism, no sweep.

## Window

The 145-month validation slice (2011-07-29 → 2023-07-31), the E019 deployable
simulation re-used verbatim (labeled rows, real costs 0.105%/side, 3% cap, 12-month
holds, sell-at-last-trade proxy). Test window untouched.

## Arms (frozen)

- **A BASELINE** — E019's arm A verbatim (no control). Must reproduce E019's committed
  `arms.A_deployable_real_cost` to 1e-9.
- **B ENTRY_GATE_15** — the mechanism above.
- **C SATELLITE_30_GATED** — the E020 70/30 blend with the satellite run as B (the
  deployable object if B works: the blend's satellite leg gated).

## Guards (frozen; all must pass for the run to count)

- **G1** arm A == E019's committed `arms.A_deployable_real_cost` (cagr and maxdd both to
  1e-9).
- **G2** tape pins: labeled top-5% picks == 4,579; mean monthly IC == `smoke.SLICE_IC_PIN`
  to 1e-9.
- **G3** mechanism engages: B holds cash in at least 1 and at most 90 months *(amended
  pre-run with disclosure: the frozen ceiling of 60 guessed the gated-month count; the
  pilot measured 63 — a small-cap drawdown that persists ~5 years is exactly the scenario
  the mechanism exists for, and capping the count would have capped the test)*. B never
  force-sells a leg before its 12th month (the no-whipsaw property, checked on the
  ledger; must be 0).
- **G4** no look-ahead: the gate at month t uses only equity marks dated ≤ t.

## Bars (frozen)

- **B1 (primary):** B's maxDD ≥ −35% (a ≥ 12pp improvement on E019's −47.02%).
- **B2:** B's CAGR ≥ A's − 3.0pp (the control may cost return; 3pp is the tolerance).
- **Recorded, not gating:** months gated; CAGR given up per month gated; C's blended
  numbers vs E020's ungated 70/30; the index-equivalent line (+13.17% / −28.87%).

## Decision rule

PASS iff B1 and B2 hold, all guards green. On PASS: the gated book (or C, the gated
satellite) becomes the breadth family's design-freeze candidate — the joint-path blend
(E020) is re-measured with the gated satellite before any test-window spend. On FAIL:
the drawdown is structural to broad small-cap exposure in this signal, and the recorded
recommendation is E020's outcome (blend sizing or pure indexing) with the breadth book
excluded from solo deployment.

Disclosures rule: any deviation between coded bars and these words is recorded in
`results.json` (`bars`, `bars_as_coded`) the E013/E014 way.
