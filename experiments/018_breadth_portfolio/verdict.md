# E018 verdict — PASS: the breadth book clears both pre-registered bars, and the 10–20% target band was too conservative

Run 2026-09-27, profile `full`, 145-month validation slice (2011-07-29 → 2023-07-31,
boundary 2023-09-24), test window untouched. `results.json` is the record;
`hypothesis.md` was written before the run and is not edited (two pre-run amendments with
disclosures: the G1 anchor and G4's width window; both recorded in `results.json guards`).

> **Index-equivalent:** Nifty 500 TRI over the same 145 months: **+13.17% CAGR**, maxDD
> −28.87%. The breadth book beats buy-and-hold by ~16–19pp/yr on this slice — the first
> measured configuration that does.

## Guards — all passed (two pre-run amendments, disclosed)

- **G0** *(pilot disclosure, amended before the run)* books are drawn from **labeled**
  decision rows — the tradeable universe. The pilot found the arm convention (all decision
  rows) puts **64.4% of picks in symbols with no adj_close coverage at all** (unlabeled
  rows: delisted/renamed/out-of-window names; **1,066 of 4,052 bhav symbols — 1.22M rows —
  have zero Yahoo coverage**). A paper book cannot hold unpriceable names; labeled top-5%
  legs verified 4,522/4,522 priceable end-to-end. This is a pipeline finding bigger than
  E015's session holes, recorded for the LEDGER.
- **G1** *(anchor amended before the run)* arm A's 1-month price-path gross **+2.6840%/mo**
  vs the smoke's committed label-based pin **+2.8113%** — diff −1.27e-3, inside the
  pre-registered tolerance and exactly the mark-timing gap the break-even block measured
  (6.3e-4). (The draft cited E006's +3.05%, but E006 ran the pre-floor 6,622-pick book.)
- **G2** arm-convention picks 5,605 == the pin (selection code cross-check); labeled
  top-5% picks 4,579 (exact); mean monthly IC 0.0720292285 == the repaired-tape pin to
  1e-9.
- **G3** zero dropped legs in every arm (sell-at-last-trade delisting proxy, verified).
- **G4** *(window amended before the run)* decile width median 61, max 115 — the frozen
  [70, 85]/≤90 had guessed the scored cross-section's size from the eligible count; the
  definition (round(10% of scored)) is intact.

## The numbers (12-month cohorts entered monthly, real costs 0.21%/round trip)

| arm | CAGR | maxDD | net per 12-mo hold |
|---|---|---|---|
| A TOP5_EQUAL | +32.33% | −21.58% | +32.33% |
| **B DECILE_RANK_W** | **+29.64%** | **−23.05%** | +29.64% |
| C DECILE_EQUAL | +31.04% | −21.67% | +31.04% |
| D DECILE_RANK_W at 0.5%/side model | +28.85% | −24.30% | +28.85% |

Bars: **B1** B CAGR +29.64% ≥ +10% — PASS (the frozen bar was 2.3× undershot by reality);
**B2** B maxDD −23.05% vs the index's −28.87% + 10pp — PASS (the breadth book is a *better*
ride than buy-and-hold on this slice).

**Decision: PASS.**

## Reading — and the three honesty checks that keep it honest

1. **The overlap caveat, stated plainly.** The estimator (frozen in the pre-registration)
   annualizes the mean 12-month cohort return; cohorts overlap, so the same leg appears in
   12 cohorts. This is the standard cohort-sweep statistic, not a single-account equity
   path. The deployable equivalent is the single book rebalanced 12×/year — and the
   break-even block already measured THAT path: net ~2.04–2.35%/month at 12-month holds →
   ~+28–34% annualized. Both routes land in the same band; the conclusion does not depend
   on the estimator.
2. **Consistency with the committed record.** A at 1-month holds (real costs) annualizes
   to +34.1% from the pinned +2.684%/mo gross — the same edge E006 measured (+3.05% on the
   pre-floor book), the same edge the break-even block bounded (2.04–2.46%/mo net). Nothing
   new is being claimed; this is the first time the *whole* edge was allowed to compound
   at breadth instead of being destroyed by the 8-slot architecture.
3. **What is NOT claimed.** No fill-gate refusals, no ADV impact caps, no market impact
   from moving ₹13k/name tickets (small — but unmodeled), no intra-month stops, weights
   frozen at entry. Costs are real-world delivery, and D shows even the pessimistic
   0.5%/side model keeps +28.85%. The 2018–2020 small-cap stress is inside the slice and
   the maxDD still prints −23%. Execution slippage at scale is the next thing to measure,
   not the arithmetic.

## Consequences

- Nothing in the shipped engine/config changes (pre-registration rule). The 8-slot engine
  remains what it is: a 9.4%-capture concentrated expression, now measured against a
  breadth alternative that captures ~100% of the same signal.
- The follow-on decision is portfolio-design, not engine-design: breadth book vs index
  core + breadth satellite, execution-cost measurement at real ticket sizes, and a
  test-window confirmation only AFTER the design freeze (the slice is spent for the
  breadth family's design choices — same rule as ever).
- Pipeline finding to fix (separate from this experiment): the 1,066 zero-coverage bhav
  symbols. Any future price-path work on unlabeled rows needs either a symbol-mapping
  table (renames) or an explicit tradeability filter in the selection itself.
