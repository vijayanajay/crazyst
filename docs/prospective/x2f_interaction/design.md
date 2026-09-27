# Design freeze — `x2f_interaction` (conjunctive aggregation of the shipped pair)

Frozen 2026-09-27, before any fold it will score exists (docs/prospective_protocol.md).
Registered from `docs/prospective/TEMPLATE.md`. Chosen as the first prospective design
because it is the audit's strongest surviving unmeasured item (docs/feature_family_audit.md
#4): the shipped composite_2f averages two percentile ranks — a *compensatory* aggregation
where strength in momentum offsets weakness in delivery — and the conjunctive alternative
(the rank **product**, requiring strength in both) has never been measured on this
universe. It is a new family (aggregation structure), not a re-run of any closed one.

## 1. Family and claim — frozen

- Family: aggregation structure of the shipped pair (`mom_12m_1m`, `delivery_pct`).
- The claim, directional: **the conjunctive product scores beats the shipped mean's
  monthly Spearman IC on virgin folds** (a positive mean monthly IC difference is not
  required for the screen bar below, but the claim's direction is "product ≥ mean").
- Mechanism: the shipped mean lets a top-decile-momentum name with bottom-decile delivery
  score ~0.5 and enter the book; the product pushes such names out. If the composite's
  edge concentrates in names strong on BOTH legs (the E002b evidence that each leg is
  independently confirmed at 15y suggests the conjunction is informative), the product's
  top-5% should be cleaner than the mean's — the reversal of the dilution that sank
  P4.1's and E023's 3f variants (adding a *feature* diluted; changing the *aggregation*
  does not).

## 2. Exact construction — frozen

- Feature inputs: `feature_matrix` columns `mom_12m_1m` and `delivery_pct` only (indices
  via `PANEL_FEATURES`, the shipped map). No other column, no labels at scoring time.
- Scoring rule (src/prospective/designs/x2f_interaction.py `score_month`):
  `score = pct(mom_12m_1m) × pct(delivery_pct)`, where `pct` is the shipped
  `model._pct` (average ranks / (n−1), NaN → None), **rows with any None component score
  None** (the conjunction's own NaN contract — stricter than the mean's; recorded as a
  deliberate coverage trade: the product is only defined when both legs exist).
- Selection/portfolio rule: none in this screen — the design is scored as a signal
  (per-fold Spearman IC, top-5% mean label), the E025 bar style.
- NaN contract: as above; coverage per fold is recorded in folds.csv (`n_scored` vs the
  month's labeled rows via the `mean_score` column's companion count).
- Registered scorer: `src.prospective.designs.x2f_interaction:score_month`

## 3. Guards — frozen

- G1 (PIT/identity): per fold, `n_scored` ≤ labeled rows and every scored pair carries a
  real label (the runner's own construction); the scorer reads only the two frozen
  columns — a column-index drift fails loudly (KeyError/None-collapse to n_scored = 0).
- G2: in-sample reference (not gating): on the 145-month validation slice the product's
  mean monthly IC is recorded once, at registration time, as `reference_insampling_ic` in
  designs.json — for context only; the verdict reads virgin folds alone.
- G3 (coverage bar): a fold is valid iff n_scored ≥ 100 (both legs present for ≥ 100
  labeled names — the pair's joint coverage was ~84% in the matrix; folds below the bar
  are recorded with `valid = FALSE` and do not count toward n).

## 4. Bar and decision rule — frozen

- Screen bar: mean monthly IC difference (product − shipped mean, paired by fold) ≥
  **+0.005** over **n = 18** valid folds (≈ 18 months ≈ 1.5 years; sized to detect a
  ~0.01 IC delta at the composite's monthly IC sd with 80% power — the smallest delta
  that ever mattered in this program's composite tests was 0.0096–0.0153).
- One-sided reading; paired by fold (both scorers run on the same fold inside the same
  job — the shipped 2f is the reference scorer, computed identically and stored in the
  same folds.csv row).
- Early stop: if after ≥ 12 valid folds the paired mean difference is negative with
  t < −1.5, the design may be called a fail early (fail direction only).
- Verdict: `runs/prospective/x2f_interaction/verdict.md` + a LEDGER row. PASS licenses a
  book-level pre-registration (E018 machinery, real costs); it ships nothing.

## 5. Disclosure log (append-only)

| date | change | reason |
|---|---|---|
