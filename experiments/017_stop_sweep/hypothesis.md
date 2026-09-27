# E017 — stop/trail width sweep: is Trigger B the churn source, and do wider stops beat the cost drag?

Pre-registered 2026-09-27, **before the run** (BRD §12): the arms, guards, bars and reading
rule below are frozen. The runner is implemented after this file exists and the file is
never edited afterwards; the verdict is written beside it as `verdict.md`.

## Motivation

- E016 (LEDGER 2026-09-27) exonerated the monthly review: 8 sell decisions in 145 months,
  suppressing them LOSES 1.2–2.5pp of CAGR. The real turnover — ~980 fills over the slice,
  ~0.85 round trips per position-month at 8 slots — must live in Trigger B
  (`midmonth.trigger_b_stop_pct` 0.08, `trigger_b_trail_pct` 0.12, the 2-close 50-DMA
  clause) and the T+1 fill path.
- The break-even arithmetic (LEDGER 2026-09-27) says the pick edge survives long holds
  (~2.0–2.3%/mo net at any horizon from 1 to 12 months). If stops are the fills, widening
  them converts cost into holding time — but also converts the trail's loss-cutting into
  larger single-trade losses. This experiment measures that trade through the REAL engine
  (fills, gates, impact caps), on the validation slice.

## Window

The 145-month validation slice (2011-07-29 -> 2023-07-31, boundary 2023-09-24), harness
convention, warm=20, E014 machinery. Test window untouched.

## Arms (frozen — a 3x2 grid plus baseline; all config-only via `portfolio_overrides`)

- **A BASELINE** — shipped config (`stop 0.08 / trail 0.12`). Must reproduce E016's
  committed `arms.A` bit-for-bit (json-equal), which itself equals E014's baseline.
- **D1 WIDE** — `stop 0.16 / trail 0.24` (2x both).
- **D2 VERY_WIDE** — `stop 0.32 / trail 0.48` (4x both).
- **D3 STOP_ONLY_OFF** — `stop 0.999 / trail 0.12` (hard stop effectively off; trail and
  DMA/delivery clauses unchanged — isolates the stop's contribution).
- **D4 TRAIL_ONLY_OFF** — `stop 0.08 / trail 0.999` (trail effectively off; isolates the
  trail's contribution).
- **D5 BOTH_OFF** — `stop 0.999 / trail 0.999` (GSM forced exits and universe exits remain;
  the maximum-hold arm — the break-even arithmetic's h=12 regime, engine-honest).
- **T1 TIGHT** — `stop 0.04 / trail 0.06` (half; the falsification arm — if the churn/cost
  story is wrong and stops are alpha, T1 should WIN).

## Guards (frozen; all must pass for the run to count)

- **G1** arm A json-equal to E016's committed `arms.A`.
- **G2** tape pins: arm-convention picks >= 4,579; eligible == 161,942; mean monthly IC ==
  `smoke.SLICE_IC_PIN` to 1e-9.
- **G3** mechanism signal: the stop/trail widths must MOVE the trigger_b sell counts and
  in the pre-registered directions where they bind: T1 (tight) emits strictly MORE
  trigger_b sells than A, and D5 (both off) emits strictly FEWER than A. (Set before the
  run: the pilot run showed the shipped widths bind rarely — 486 trigger_b sells in 145
  months, mostly the DMA/delivery clauses which the sweep does not touch — so strict
  monotonicity along A -> D1 -> D2 was replaced by this directional signal. The written
  rule and the coded check are recorded in `results.json` as `bars_as_coded` discloses.)
- **G4** GSM/universe exits are NOT suppressed in any arm (every arm still emits
  `trigger_b_gsm` machinery; D5's only trigger_b sells are gsm/dma/deliv, never stop/trail).

## Bars (frozen)

- **B1 (primary):** at least one arm reaches slice CAGR >= A's CAGR + 2.0pp.
- **B2:** that arm's maxDD is not worse than A's by more than 5pp (negative-fraction
  convention: `maxDD_arm >= maxDD_A - 0.05`).
- **Recorded, not gating:** fills/month per arm (the cost mechanism); per-trigger sell
  counts; the **index-equivalent** line — slice Nifty 500 TRI CAGR (+13.17%) printed beside
  every arm.

## Decision rule

PASS iff B1 and B2 hold for the same arm, all guards green. On PASS, adoption is a separate
decision (config amendment; E012's floor re-derivation at the changed turnover if adopted).
On FAIL: the stop/trail widths are NOT the binding lever either, and the remaining cost
lever is the cost model itself (real-world delivery costs ~0.1–0.2%/side vs the modeled
0.5%/side) — to be measured against E010's sweep data without touching the test window.

Disclosures rule: any deviation between coded bars and these words is recorded in
`results.json` (`bars`, `bars_as_coded`) the E013/E014 way.
