# P4.2 — verdict (written after the run; the hypothesis was not edited)

**Verdict: REJECTED — the learned ranker loses to `composite_2f`, which ships. The ledger
says so, exactly as plan 4.2 requires.**

- **Primary comparison:** ranker mean monthly IC **0.0402** (120 scored folds) vs
  `composite_2f` **0.0681** (145 months) — paired monthly diff **−0.0221** over the 120
  months both arms scored, t = −2.45, **p = 0.0159 < 0.05**. The ranker is significantly
  WORSE, not merely not-better: this is a clear loss, not a tie.
- **Why the loss is informative, not embarrassing:** the ranker saw all 22 features —
  including the five candle/accumulation features E002b BH-rejected on direction and the
  regime-flipping `atr_ratio` — with squared-error loss on raw returns, where a few extreme
  forward months dominate. The composite's strength was its blindness: two features, both
  confirmed at full history, no rope to grab noise with. Giving the model more rope made it
  grab more noise. That is the experiment's finding, and it validates the plan's gate design
  (composite first, ranker must *earn* adoption).
- **Freeze protocol (4.3): passed, part of the run.** `artifact/model_meta.json` records
  hyperparameters, feature list, sklearn version, seed and the 120-fold manifest; first and
  last scored folds refit **bit-identically** (max |diff| = 0.00e+00, the fixed seed +
  early-stopping-off doing their job); the last fold's top-5% pick set reproduces exactly
  from a fresh refit; the artifact's fold count round-trips. Re-running an old run with its
  saved artifacts reproduces its picks — the plan's done-when, demonstrated on real folds.
- **Consequence for the plan:** `composite_2f` (mean percentile rank of `mom_12m_1m` +
  `delivery_pct`) is the Phase 4 model, adopted on a confirmed win (P4.1b) and defended
  against the ranker (this experiment). 4.3's freeze protocol now applies to it — its
  "training" is parameter-free (no fit), so the freeze artifact is its feature list and
  construction, already pinned in `experiments/004b_composite_2feat/hypothesis.md`. Phase 6
  walks **composite_2f** forward.
- **Honest caveats:** (1) hyperparameters were fixed a priori, never tuned — a tuned ranker
  might close the gap, but the plan's gate was a fair fixed fight and tuning on this slice
  would burn the no-peeking budget; file "tuned ranker" as a future pre-registration if ever
  justified. (2) 25 warm-up months are scored for the baseline only; the paired test uses the
  120 shared months. (3) scikit-learn enters requirements.txt on this experiment's
  justification (rank-aware objective unavailable without lightgbm; NaN-native; deterministic
  under fixed seed) — the dependency earned its place even though the model lost, because the
  Phase 6 harness may yet need it for diagnostics.
