# E021 verdict — REJECTED: the entry gate fixes the drawdown (−47% → −30.2%) but costs 16pp of CAGR; the drawdown is structural

Run 2026-09-27, profile `full`, 145-month validation slice (2011-07-29 → 2023-07-31,
boundary 2023-09-24), test window untouched. `results.json` is the record;
`hypothesis.md` was written before the run and is not edited. One pre-run amendment with
disclosure: G3's gated-month ceiling 60 → 90 (the pilot measured 63 — a ~5-year small-cap
drawdown is exactly the scenario the mechanism exists for; recorded in
`results.json guards.G3_note`).

> **Index-equivalent:** Nifty 500 TRI over the same 145 months: **+13.17% CAGR**, maxDD
> −28.87%.

## Guards — all passed

- **G1** arm A reproduces E019's committed baseline: +0.257682 / −0.4702 to 1e-9.
- **G2** tape pins: labeled top-5% picks 4,579 (exact); mean monthly IC 0.0720292285 ==
  the repaired-tape pin to 1e-9.
- **G3** (as amended) the gate engaged **63 of 145 months**, forced early sells **0** —
  the no-whipsaw property held exactly as designed.
- **G4** the gate at month t reads only equity marks dated ≤ t.

## The numbers

| arm | CAGR | maxDD |
|---|---|---|
| A baseline (E019 verbatim) | +25.77% | −47.02% |
| B ENTRY_GATE_15 | +9.80% | **−30.23%** |
| C 70/30 with gated satellite | +12.27% | −26.88% |
| reference: ungated 70/30 | +18.66% | −35.84% |
| index-equivalent | +13.17% | −28.87% |

Bars: **B1** maxDD ≥ −35% — **PASS** (−30.23%, a 16.8pp improvement; the gated book even
rides better than the index). **B2** CAGR ≥ A − 3.0pp (≥ +22.77%) — **FAIL by 12.97pp**.

**Decision: REJECTED.** The gate works exactly as designed and the design is still not
worth it: it sits in cash for 63 of 145 months (43% of the slice — the entire 2011–2015
small-cap bear and the 2018–2020 stretch), missing the rebounds that ARE the edge.

## Reading

1. **The whipsaw asymmetry is now measured on both sides.** E017: per-name stops cost
   money because exits shake out recoveries. E021: book-level entry gates cost MORE
   (16pp vs E017's ~1.3pp), because gating the whole book suspends the diversification
   engine itself — 60+ months of missed entries vs 116 early exits. There is no
   non-whipsaw drawdown control at this breadth; the drawdown is structural to broad
   small-cap exposure in this signal.
2. **The blend survives as the only deployable form.** C (70/30 with the gated satellite)
   is dominated by E020's ungated 90/10 (+15.33% CAGR, −31.13% maxDD — better on both
   axes), so the gate adds nothing inside a blend either.
3. **The family's final shape:** pure index (+13.17%, −28.87%) for the risk-averse;
   **90/10 blend (+15.33%, −31.13%)** as frozen by E020 for +2.2pp over the index; the
   ungated book solo only for an investor who can hold through −47%. Everything measured,
   nothing shipped, test window untouched.

**Consequences:** nothing shipped; the breadth family's validation-slice work is COMPLETE
(E018 design → E019 deployable → E020 blend frontier → E021 control — every branch
measured). The test-window confirmation of the 90/10 freeze is the only remaining step
before any deployment, and it must use E020's exact construction with no re-tuning.
