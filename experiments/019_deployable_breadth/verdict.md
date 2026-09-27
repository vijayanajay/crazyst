# E019 verdict — REJECTED on B2: the deployable single book carries a −47% drawdown, far worse than the cohort statistic showed

Run 2026-09-27, profile `full`, 145-month validation slice (2011-07-29 → 2023-07-31,
boundary 2023-09-24), test window untouched. `results.json` is the record;
`hypothesis.md` was written before the run and is not edited. No code amendments after
the run; one implementation note: the G1 continuity check rebuilds E018's cohort
statistic from E018's own builders (its estimator lives inline in its `main()`).

> **Index-equivalent:** Nifty 500 TRI over the same 145 months: **+13.17% CAGR**, maxDD
> −28.87%.

## Guards — all passed

- **G1** the cohort reference rebuilt from E018's own builders reproduces E018's committed
  B CAGR **0.296444 == 0.296444** to 1e-9 (continuity proven).
- **G2** tape pins: labeled top-5% picks 4,579 (exact); mean monthly IC 0.0720292285 ==
  the repaired-tape pin to 1e-9; decile median width 61 (E018's amended window).
- **G3** no look-ahead: 100 random legs recomputed from fresh per-leg queries, worst
  price diff **0.0e+00**.
- **G4** no leverage (cash ≥ −1e-6, float dust only), no 3% weight-cap breach, holdings
  ≤ 130 in every month.

## The numbers

| arm | CAGR | maxDD |
|---|---|---|
| **A deployable (real costs 0.105%/side)** | **+25.77%** | **−47.02%** |
| B deployable (0.5%/side model) | +24.88% | −47.97% |
| C cohort reference (E018 B) | +29.64% | — |
| index-equivalent | +13.17% | −28.87% |

Bars: **B1** A CAGR +25.77% ≥ +15% — **PASS**. **B2** A maxDD −47.02% vs the index's
−28.87% + 10pp (bar: ≥ −38.87%) — **FAIL by 8.15pp**.

**Decision: REJECTED.** Per the pre-registration: the deployable object's frictions eat
the cohort gap, and the recorded recommendation is the **index core + breadth satellite
blend, sized by the FAIL margin**.

## What this actually taught (the decisive finding of the day)

The +29.6% cohort CAGR and the +25.8% single-account CAGR agree on return — the account
only gives up ~4pp to transition cash drag and cost. What the cohort statistic **could
not show** is the drawdown: a single rank-weighted decile book, held through 2011 and
2013's small-cap air pockets, draws down **−47%** — an 18pp-worse ride than the index.
The cohort overlay averaged 12 staggered entry vintages and hid the path.

This is exactly the failure mode the pre-registration was built to catch, and it changes
the recommendation quantitatively, not vaguely:

- The satellite blend is now the ONLY recorded way to hold this signal: blended 70/30
  with the index, the account-level numbers become ≈ **+16.9% CAGR** (0.7 × index +
  0.3 × satellite, approximate since drawdowns are not additive — the true blended maxDD
  must be computed on a joint path before any deployment; that joint-path measurement is
  the natural next pre-registration).
- The steady-state turnover came out **8.55×/yr, not ~1×**: legs exit after exactly 12
  months, but the 3% weight cap plus rank-weighting keeps re-sizing the surviving names
  far more than the "1/12 per month" design intuition. Turnover this high makes the cost
  model matter again (A vs B: only 0.9pp — costs stay small — but real-market impact at
  ₹13k tickets is unmodeled).
- The 12-month fixed hold (E016/E017's conclusion) applied at breadth produces the
  return; the missing piece is a DRAWDOWN control that is not a whipsaw stop. That is
  the one open design question before any freeze — and it must be solved on THIS slice
  with a fresh pre-registration, or accepted as-is inside a blend.

**Consequences:** nothing shipped; the breadth family's test-window confirmation is now
GATED on the joint-path blended measurement (index core + satellite). The design-freeze
clause of the pre-registration does NOT trigger (the FAIL reverts the recommendation
instead). All artifacts, guards and the turnover finding are in `results.json`.
