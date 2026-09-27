# E023 — the delivery-dynamics composite: 3f (mom_12m_1m + delivery_pct + delivery_pct_trend) vs the shipped 2f

Pre-registered 2026-09-27, **before the run** (BRD §12). The arms, bars, guards and decision
rule below are frozen; the runner is implemented after this file exists; the verdict is
written beside it. Shortlist item #1 of `docs/feature_family_audit.md`.

## Motivation

The shipped composite_2f is the mean percentile rank of `mom_12m_1m` + `delivery_pct`.
E002b (full history, BH-corrected) confirmed a third feature the composite has never used:
`delivery_pct_trend` (+0.0229 mean monthly IC, p 5.9e-9) — the delivery *dynamics* vs the
shipped level. P4.1's original 3f (which added `mom_6m`, p 0.019) missed its pre-registered
bar (p 0.0585); the delivery-dynamics variant has never been tested in any combination.

## Window

The 145-month validation slice (2011-07-29 → 2023-07-31, boundary 2023-09-24) — P41's
split, unchanged. The test window is burnt (E020-C) and is not touched.

## Arms (frozen)

- **T (treatment):** composite_3f_dt — mean cross-sectional percentile rank of
  `mom_12m_1m`, `delivery_pct`, `delivery_pct_trend` (NaN rows stay NaN; a row with ≥ 1
  non-NaN feature still scores — the shipped composite's own NaN contract, via
  `model.score_month`).
- **C (control):** the shipped `model.score_month_2f` — bit-identical to the production
  path, scored on the same rows.

## Guards (frozen; all must pass for the run to count)

- **G1:** C's slice mean monthly IC equals the smoke's committed `SLICE_IC_PIN`
  (0.07202922854484578) to 1e-9 — the control is the production signal, not a lookalike.
- **G2:** 145 validation months, boundary 2023-09-24 (the slice pins).
- **G3:** ≥ 6 common months with non-None ICs for the paired comparison (P4.1's minimum).

## Bars (frozen)

- **B1 (primary, gating):** paired-by-month one-sample t on the monthly IC differences
  (T − C), P4.1's `_paired_t` construction re-used verbatim so the bar cannot drift:
  mean diff > 0 and two-sided p < 0.05. No BH correction (P4.1b's single-comparison
  precedent). ONE pre-registered combination — no sweep, no post-hoc variants.
- **Recorded, not gating:** each arm's mean monthly IC; top-5% precision per arm (P4.1's
  `_top5_precision`); the fraction of scored rows (NaN-contract cost of the third feature).

## Decision rule (frozen)

PASS iff B1 holds with all guards green. On PASS: the 3f becomes a *candidate* — a
promotion test (E018-style book at real costs, then the usual chain) is the next
pre-registration, and nothing ships from this experiment. On FAIL: the shipped 2f stands
and the composite family is closed (a third feature must beat the paired bar to exist;
one more miss retires the direction).
