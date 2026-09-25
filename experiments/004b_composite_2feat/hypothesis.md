# P4.1b — two-feature composite: mom_12m_1m + delivery_pct (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12):** hypothesis written before `run.py` executes; predictions may not be
edited after. Only `results.json`, `verdict.md`, and the LEDGER verdict are written after.
This is a child of P4.1 and may only tighten, never reinterpret, that experiment's rules.

**Motivation (from P4.1's verdict, written pre-run):** the three-feature composite beat the
best single feature on the point estimate (0.0625 vs 0.0529 mean monthly IC) but missed the
pre-registered α (p = 0.0585), and the slice's top-5 single-feature table ranked `mom_6m`
(0.0276) far behind its two siblings (mom_12m_1m 0.0529, delivery_pct 0.0445). The weakest
third vote is the natural suspect for the dilution. P4.1b asks the minimal follow-up: does
**dropping mom_6m** let the two-feature composite clear the bar the three-feature one missed?

**Arms (same construction as P4.1, parameter-free):**

1. `composite_2f` — mean of cross-sectional percentile ranks of `mom_12m_1m` and
   `delivery_pct` (NaN rows stay NaN; ≥ 1 non-NaN feature required, rows with 0 excluded
   from every arm's IC that month equally).
2. `composite_3f` — P4.1's exact three-feature composite, recomputed here as the within-experiment
   control (same code path, so the comparison cannot drift across runs).
3. `best_single` — identical to P4.1's comparator: highest mean monthly IC on the validation
   slice among all 22 features, selected on the slice (winner's curse included). P4.1 chose
   `mom_12m_1m`; if this run's slice selection agrees, the comparator is the same object.

**Slices:** identical to P4.1 — labeled decision months whose label end predates the test
window boundary (cutoff minus exactly 36 months; BRD §10.1). The test window is counted,
excluded, and never scored. The feature_matrix must hold the full-history labels (P4.1's
rebuild; asserted before scoring).

**Metrics and tests (pre-registered, no BH — two primary comparisons, stated openly):**

- PRIMARY 1: `composite_2f` vs `best_single`, paired monthly t on IC differences, α = 0.05
  (the same gate P4.1's composite missed).
- PRIMARY 2: `composite_2f` vs `composite_3f`, paired monthly t, α = 0.05 (is the third vote
  actually hurting?).
- Secondary: pooled top-5% precision on the slice per arm, reported not gatekeeping.

**Decision rule (written pre-run):**

- `composite_2f` is **confirmed** iff PRIMARY 1 clears (positive diff, p < 0.05) — it then
  becomes the Phase 4 score candidate and supersedes P4.1's shipped `mom_12m_1m` as v0.
- If PRIMARY 1 misses but PRIMARY 2 clears (2f > 3f, p < 0.05), the verdict is **partial**:
  the three-feature form is superseded by the two-feature form, but the M3 bar is still
  unmet and `mom_12m_1m` keeps shipping; the two-feature composite becomes the form 4.2's
  ranker must beat.
- If neither clears, the verdict is **inconclusive** and everything stands as P4.1 left it
  (single feature ships; three-feature composite remains the reference point).

**Honest caveats, pre-declared:** (1) this is a post-hoc refinement selected after seeing
P4.1 — the pre-registration is the only protection, and the two comparisons share the slice
with P4.1's (no fresh data). (2) Two uses of the same slice inflate the family error across
P4.1 + P4.1b; the α is not adjusted, by pre-registration, because BRD M3's gate is per-model
and the ledger records both runs side by side. (3) mom_12m_1m and delivery_pct correlate
weakly-positive (different families); no orthogonalization is applied in v0.
