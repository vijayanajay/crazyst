# E016 verdict — REJECTED: the monthly review was already nearly inert; suppressing its remaining sells loses money

Run 2026-09-27, profile `full`, 145-month validation slice (2011-07-29 → 2023-07-31,
boundary 2023-09-24), test window untouched. `results.json` is the record;
`hypothesis.md` was written before the run and is not edited.

> **Index-equivalent:** over this experiment's identical 145-month slice, the same capital
> in Nifty 500 TRI compounds at **+13.17% CAGR** — every arm below loses to the index, from
> ~14pp/yr (A) to ~16pp/yr (C).

## Guards — all passed

- **G1** arm A is json-equal to E014's committed `arms.baseline` (bit-for-bit; G2's IC
  printed against the repaired-tape pin `smoke.SLICE_IC_PIN`, LEDGER 2026-09-27).
- **G2** tape pins: arm-convention picks 5,605 ≥ 4,579; eligible rows 161,942; mean monthly
  IC 0.0720292285 == pin to 1e-9.
- **G3** the mechanism engaged: monthly_review sell decisions over the slice — A **8**,
  B **3**, C **2** (B drops the rank-fade and DMA-streak sells; C additionally blocks
  early ones).
- **G4** the `min_hold` hook is inert by default: the smoke re-run after the hook edit
  reproduced its committed engine passes bit-for-bit (diff = git_hash + runtime only).

## The numbers

| arm | equity | total | CAGR | Sharpe | maxDD | fills | MR-sells/mo |
|---|---|---|---|---|---|---|---|
| A baseline (shipped) | 942,030 | −5.80% | −0.50% | 0.090 | −65.58% | 983 | 0.06 |
| B SELL_GATE | 817,629 | −18.24% | −1.66% | 0.029 | −65.62% | 981 | 0.02 |
| C MIN_HOLD_12 | 689,387 | −31.06% | −3.05% | −0.036 | −65.85% | 979 | 0.01 |

## Bars (pre-registered)

- **B1** an arm reaches CAGR ≥ A + 3.0pp: **FAIL for both** — B is −1.16pp *below* A, C is
  −2.55pp below. Neither saves costs (fills essentially unchanged, 983 → 981/979) nor
  avoids the losses the review's sells were avoiding.
- **B2** maxDD not worse by >5pp: both pass trivially (drawdowns are the same
  −65.6/−65.9% — the drawdowns were never caused by the monthly review).

**Decision: REJECTED.** The low-turnover family is closed on this slice.

## What this actually taught (the important part)

The premise came from the break-even arithmetic — a 2%+/month raw pick edge against a
−6% CAGR engine — and the arithmetic survives, but the churn it blames is **not the
monthly review's**: over 145 months the shipped review emitted **8 sell decisions**.
It was already holding through rank fade by construction (rank threshold 0.25 with a
top-15% replace pool means few names fall out each month), and the 8 sells it did make
were, in aggregate, alpha — removing them costs 1.2–2.5pp of CAGR, they save no fills
(the replacement buys still happen; only 2–6 fill events disappear).

The real turnover lives elsewhere: Trigger B stops/trails (stop 8% below entry, trail 12%
below the month's high) and the T+1 fill path. ~980 fills over 145 months ≈ 6.8/month ≈
0.85 round trips per position-month at 8 slots — that cadence × the E010 cost/impact model
is the drag the break-even arithmetic priced, and it is driven by risk-control exits, not
by review churn. A holding-horizon change that keeps the stops (this experiment) cannot
touch it; the cost lever (E010's measured 0.5%/side vs real-world delivery costs) or the
stop design itself are the levers that remain.

**Consequences:** no config change, nothing promoted; `min_hold` stays as an inert hook
(G4-proven). The monthly-review sell rules are exonerated. If the engine's cost drag is to
be attacked again, it must be via the stop/exit design (E017 candidate) or the cost model,
not the review.
