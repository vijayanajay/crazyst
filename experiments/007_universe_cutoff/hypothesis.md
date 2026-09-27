# E007 — Hypothesis: rolling top-1000 vs top-1500 as-of universe (pre-registered)

Written **before** the run, per BRD §12. The question comes from `fixissues_phase36.md`
(the Phase 3–6 review): should the as-of universe be cut from the BRD's top 1500 to a
rolling top 1000, removing ranks 1001–1500 as an "illiquidity graveyard"? This experiment
gives the BRD owner measured numbers instead of a thesis.

## Arms

- **A (control): `top_n: 1500`** — BRD §4 as written, the universe every committed result
  (E000–E006, P4.1–P4.2) is measured on. Must reproduce P4.1b's frozen IC before anything
  else is believed (zero-drift gate).
- **B (treatment): `top_n: 1000`** — the same config with only `universe.top_n` overridden
  in memory for the derived rebuild: rank → eligibility → winners → feature_panel →
  feature_matrix. Every downstream rule (price floor, listing age, GSM/ASM, rank
  percentiles) is unchanged, so the arms differ ONLY in the cutoff. The on-disk chain is
  rebuilt back to 1500 after both arms; a post-restore IC re-check gates the restore.

Both arms run on the full profile, through the real chain builders (`src.universe.rank`,
`src.universe.eligibility`, `src.universe.winners`, `src.features.panel`,
`src.features.matrix`), then scored with the shipped model (`src.model.composite`,
composite_2f) — the same stack the committed evidence used.

## Metrics

1. **Universe shape per arm:** decision months, eligible symbol-months, labeled rows;
   median rank-1000 and rank-1500 as-of turnover; share of eligible symbol-months below
   ₹5cr/day (the review's "illiquidity graveyard" claim, tested not assumed).
2. **Model quality on the validation slice** (P4.1's split: boundary 2023-09-24, test
   window excluded and untouched, per BRD §10): mean monthly Spearman IC of composite_2f
   (one IC per month over the full cross-section, E002b's method), paired by month across
   arms, plus top-5% precision. Pick sets are tie-broken by symbol (the Phase 6 contract).
3. **Engine-pass exit behavior:** 12 consecutive slice months through the real
   Market/Facts/Portfolio/Engine stack at the shipped defaults (exit_gate escalate,
   0.5%/side), counting fills, non-fills, forced exits, and completed picks per arm — the
   review's claim is that a 1000 cut reduces ADV-gate stress.
4. **Statistical bar:** the IC difference is paired by month (one-sample t). With ~145
   paired months, |t| ≈ 2 is the noise line; the decision rule below uses it explicitly.

## Pre-registered decision rule (written before the run)

- **Reject the cut (keep 1500)** if B's mean monthly IC is not higher than A's at the
  paired-test noise line (t ≥ 2), OR B's top-5% precision is lower. Rationale: the cut
  removes exactly the bucket (601–1500) where E002b measured the strongest confirmed ICs,
  so the burden of proof is on the cut, and "IC unchanged but fewer names" is a loss of
  evidence, not a win.
- **Recommend the cut** only if B's IC is higher at t ≥ 2 AND its engine pass shows
  materially less ADV-gate stress (fewer non-fills/forced exits) — i.e. the cut buys
  tradability without costing cross-sectional signal.
- Anything between: **inconclusive, keep 1500** (BRD-normative default; a change needs a
  positive case, not a tie).

The verdict names the numbers; this file may not be edited after the run (BRD §12).
