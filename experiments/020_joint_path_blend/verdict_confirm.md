# E020-C — verdict: NON-CONFIRMED

Run 2026-09-27, profile `full`, 35 test months 2023-08-31 → 2026-06-30 — the exact months
every validation-slice experiment excluded. `results_confirm.json` is the record;
`confirm_hypothesis.md` was written (and its one disclosed deviation fixed) before the run.
The test window was not touched until this run.

| arm            | CAGR    | maxDD   | Sharpe | worst-mo | sat-CAGR | sat-maxDD | B1    | B2   |
|----------------|---------|---------|--------|----------|----------|-----------|-------|------|
| warm_up        | +12.59% | −18.46% | 0.83   | −11.39%  | +13.82%  | −24.50%   | FAIL  | PASS |
| fresh_start    | +12.60% | −18.48% | 0.83   | −11.39%  | +13.95%  | −24.61%   | FAIL  | PASS |
| index (ref)    | +12.46% | −17.74% | —      | —        | —        | —         |       |      |

Guards: G1 the satellite re-run over the 145-month slice reproduces E020's committed
satellite (0.257682 / −0.4702) to 1e-9; G2 the index leg — built with the harness's own
`_benchmark_sourced_tri`/`_benchmark_for_window` and CAGR'd by `metrics.cagr` — equals the
committed test-window benchmark (0.12457495616414915) to 1e-9; G3 no look-ahead by
construction. All green.

## Reading

The 90/10 blend is a failure out of sample, and it fails the least interesting way: not
risk (B2 passed with room — the test window's max drawdown was −17.74%, far milder than
the validation slice's −28.87%) but reward. The satellite earned +13.82% in its test-window
year against the index's +12.46%, so at w=0.10 the blend is +12.59% vs +12.46% — a +0.13pp
edge against a +2.0pp bar. On this window the breadth signal simply carried no edge worth
a tenth of the book.

The sensitivity arm agrees: fresh-start (+12.60%) and warm-up (+12.59%) differ by 0.01pp,
well inside noise — the disclosed warm-up choice did not drive the result. The verdict
would be identical either way, so it is a confirmation of the outcome, not an artifact of
the one free parameter.

## Why the gap vs the validation slice

Two honest contributors, in likely order of size:

1. **Regime.** The test window (Aug 2023 – Jun 2026) is a mild-drawdown, index-friendly
   stretch (−17.74% maxDD) — nothing like 2018–2020, where the satellite's crash-regime
   alpha drove most of the validation-slice edge. The E020 blend's entire CAGR margin over
   the index came from the satellite's tail behavior; on a window with no crash to exploit,
   the margin collapses.
2. **Sample size.** 35 months vs 145. The validation slice's +2.2pp blend edge carried wide
   error bars too; one quiet window undoes it.

Note the harness's own engine (the E011 lineage, top-5% selection) did −6.14% CAGR over
these same months — the breadth book's decile construction remains the only variant that
has ever beaten the index on a window, and even it does not here.

## Decision

Per E020's decision rule and this pre-registration's frozen rule: **NON-CONFIRMED**. The
deploy recommendation reverts to **pure indexing** (Nifty 500 TRI), as E020's FAIL clause
recorded for the no-deployable-configuration case. The 90/10 design is not deployable on
this evidence: one PASS on 145 validation months, one FAIL on 35 test months. The breadth
family stays filed as a research result with no deployable configuration; per the
pre-registration, a non-confirmation is final for this design.
