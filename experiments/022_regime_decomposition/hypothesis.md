# E022 — regime decomposition: where does the breadth satellite's excess return come from?

Pre-registered 2026-09-27, **before the run** (BRD §12). A DIAGNOSTIC, not a design
experiment: it makes no deployment claim and ships nothing. Its job is to explain the one
number the family's closure left unexplained — the satellite edge collapsing from +12.6pp/yr
on the validation slice to +1.36pp on the test window — and to state, in advance, the only
condition under which the closed breadth family may re-open.

## Background

E018's decile book beat the index by ~12.6pp/yr on the 145 validation months; E020's 90/10
blend passed on that slice; the E020-C test-window confirmation failed with a +0.13pp blend
edge (satellite edge +1.36pp over the same 35 months). E021 showed drawdown is structural;
E020 tracked `dd_2018_2020` because the suspected source of the edge is index-stress
behavior. That suspicion is exactly what this experiment measures, on all labeled history,
with no re-tuning and no design choice.

## Construction (frozen)

- **Months:** ALL 180 labeled months in the DB (145 validation + 35 test; 2011-07-29 →
  2026-06-30). The test window is now burnt as of E020-C; pooling it here is legitimate for
  a diagnostic and disclosed as such.
- **Satellite book (1-month):** the E018 lineage at the label horizon — each month, the
  top decile of the labeled cross-section by composite rank (`E018._decile_book`),
  rank-weighted (weight ∝ 1/rank_pos, normalized), return = weighted mean of the legs'
  `next_month_ret`. Gross of costs (a constant ~0.21%/mo round-trip across all months
  cancels in every between-bucket comparison; noted, not applied). Top-5% equal-weight
  (the engine's lineage) computed alongside, recorded not gating.
- **Index leg:** sourced Nifty 500 TRI month-end marks (`index_tri`, 'NIFTY 500'); the
  index's forward monthly return over each label interval: `tri[ym(m+1)]/tri[ym(m)] − 1`.
  **Excess(m) = book(m) − index_forward(m)** — both legs cover the identical interval.
- **State variables (backward-looking, no look-ahead):**
  - **Regime band** (harness convention, `REGIME_BAND = 0.02`): the index's return over
    the month interval ENDING at m: up (> +2%), down (< −2%), flat.
  - **Index drawdown bucket at m:** `tri_ym(m)/running_peak(tri_ym through m) − 1`:
    shallow (dd > −5%), moderate (−15% < dd ≤ −5%), deep (dd ≤ −15%).

## Guards (frozen; all must pass for the run to count)

- **G1 (book anchor):** the top-5% equal-weight 1-month gross mean over the 145 validation
  months reproduces the smoke's committed `light_pass.mean_gross` within 0.15pp (E018's G1
  construction and tolerance, unchanged) — ties selection + labels to committed numbers.
- **G2 (index anchor):** the TRI ym marks over the 145 validation months reproduce E019's
  committed `index_equivalent` (CAGR 0.13168275883319414 / its maxDD) to 1e-9 (E020's G2,
  unchanged).
- **G3 (coverage):** 180 months, every month has a decile book of ≥ 10 legs and an index
  forward return; at most 2 months lack a regime band (TRI history before the first label).

## Reductions (frozen)

Per bucket of each cut: n, mean book return, mean index return, mean excess, t-stat of the
excess (mean / SE of monthly excess), hit rate (share of months with excess > 0). Cuts:
regime band, index-drawdown bucket, and the full-history overall row. Also recorded, not
gating: the same table for top-5%; the 2018–2020 episode's contribution to the full-sample
mean excess.

## Decision rule (frozen)

The breadth family may re-open (as a NEW mechanism, e.g. index-conditional sizing, fresh
pre-registration required) **iff** the deep-stress bucket's mean excess exceeds the
shallow bucket's mean excess by ≥ 3.0pp/month, with ≥ 70% positive-excess months among
deep-stress months and n(deep) ≥ 12. Otherwise the edge is regime-uniform or absent: the
family stays closed, and the program's next step is new signal families (the feature audit),
not more mechanics on this signal. This rule is diagnostic and final; a PASS here licenses
a pre-registration, not a deployment.
