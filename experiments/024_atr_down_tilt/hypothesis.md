# E024 — the down-month question: does a low-ATR tilt inside the decile book fill the zero-excess down-month bucket without breaking the up-month edge?

Pre-registered 2026-09-27, **before the run** (BRD §12). Shortlist item #2 of
`docs/feature_family_audit.md`. E022 measured the book's excess as +2.40%/mo in up-months
and −0.17% in down-months; E002b measured `atr_ratio`'s IC as −0.183 in down-months (94%
sign consistency) — low-volatility names hold up when the index falls. This experiment
tests whether tilting the book toward low-ATR names converts that into down-month excess
without paying for it in up-months.

## Window

The 145-month validation slice only. The test window is burnt and stays closed; a PASS
here earns a promotion pre-registration (E019-style sim), not a test-window run.

## Construction (frozen)

E022's exact machinery, verbatim: E018's decile book (rank-weighted, `1/rank_pos`),
mark-based 1-month cohorts (adj_close month-end marks, zero dropped legs), the sourced
Nifty 500 TRI as the index leg over the identical interval, gross of costs (the constant
~0.21% round trip cancels in every between-arm comparison; disclosed). Regime bands from
the harness convention (±2% on the index return ending at m).

- **Arm A (control):** the E018/E022 baseline book. Weight ∝ 1/rank_pos.
- **Arm B (treatment):** the atr-tilted book. Weight ∝ `1/rank_pos × (1 − pct_atr)`,
  normalized. `pct_atr` is the leg's cross-sectional percentile of `atr_ratio` within its
  month's full labeled cross-section (the shipped `_pct` math: average ranks, NaN → None).
  The tilt is parameter-free — no knob, no sweep. A leg whose `pct_atr` is None (missing
  atr) gets the neutral factor 1.0; a leg at pct_atr = 1.0 gets factor 0 and drops out of
  the book (asserted: ≥ 5 legs remain every month).

## Guards (frozen; all must pass for the run to count)

- **G1 (continuity with the committed diagnostic):** arm A's by-band mean excess over the
  validation slice equals E022's committed `post_hoc_slice_split.validation_by_band`
  (down/flat/up) to 1e-6 — same construction, same data, no drift.
- **G2 (index leg):** equals E019's committed `index_equivalent` over the slice to 1e-9
  (E022's G2, unchanged).
- **G3 (tradeability):** zero dropped legs in both arms across all 145 cohorts; every
  tilted book keeps ≥ 5 legs.

## Bars (frozen)

- **B1 (the fill):** arm B's mean excess in DOWN months ≥ +0.5pp/mo — materially filling
  the bucket E022 measured at −0.17% (t −0.12).
- **B2 (the retention):** arm B's mean excess in UP months ≥ arm A's up-month mean excess
  − 1.0pp (the +2.40% up-month edge may cost at most 1pp of its monthly mean).
- **B3 (no net harm):** paired-by-month mean excess difference (B − A) > 0 over all 145
  months (one-sample t on monthly differences, one-sided reading; the point estimate and
  t are both recorded).

## Decision rule (frozen)

PASS iff B1 ∧ B2 ∧ B3 with all guards green. On PASS: the tilt becomes a *candidate* — the
next pre-registration is the E019-style deployable sim with the tilt inside; nothing ships
from this experiment. On FAIL: the conditional-volatility direction is closed alongside
the composite family (E023), and the audit's remaining direction is new data
(index-inclusion flows), not new uses of the existing panel.
