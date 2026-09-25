# P4.2 — learned ranker vs composite_2f (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12 + plan 4.2/4.3):** hypothesis written before `run.py` executes;
predictions may not be edited after. Only `results.json`, the frozen artifacts, `verdict.md`,
and the LEDGER verdict are written after.

**Question:** can a gradient-boosted ranker, refit walk-forward monthly, beat the shipped
`composite_2f` (P4.1b: mean percentile rank of `mom_12m_1m` + `delivery_pct`, 0.0681 slice
IC) at the same gate — and does the freeze protocol (4.3) reproduce its picks exactly?

**Model (fixed now, no tuning during the run):** `sklearn.ensemble.HistGradientBoostingRegressor`
with `loss="squared_error"` on the monthly cross-section — the ranking comes from the
cross-sectional order of predictions, which is what Spearman IC measures; a pairwise
objective is not available in sklearn and adding lightgbm for one is the dependency the plan
says to justify against (ledger note in requirements.txt: rejected). **All features** (the
22 in E002's frozen list) enter every fit; NaN rows stay NaN (HistGBR is NaN-native, matching
the panel's missing-data semantics — never 0). Fixed hyperparameters, chosen a priori and
never swept: `max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100,
l2_regularization=1.0, early_stopping=False, random_state=cfg.backtest.random_seed`.
`early_stopping=False` and the fixed seed make a refit bit-deterministic (4.3's requirement).

**Walk-forward protocol (BRD §10.2 on pre-test-window data only):** for each labeled
validation month M (in date order), fit on all labeled months whose label end is ≥ 1 month
before M starts (the 1-month purge), predict M's cross-section, move on. Refit every month,
~145 fits on ~130k rows total. The test window (boundary 2023-09-24) is excluded and not
scored, as in P4.1/P4.1b. **The first fold needs training history:** the ranker starts
predicting once ≥ 24 training months exist; months before that are scored for the baseline
arms only (IC comparability handled by the paired test's month intersection). The warm-up
months are disclosed in results.json (`ranker_warmup_months`).

**Arms:** `ranker` (the walk-forward model), `composite_2f` (P4.1b's shipped control,
recomputed in-process), and the paired primary test: **ranker vs composite_2f, one-sample t
on month-paired IC differences, α = 0.05** — the same gate as P4.1/P4.1b. Secondary:
top-5% slice precision per arm, reported not gatekeeping. No BH: one primary comparison,
declared.

**Decision rule (written pre-run):** the ranker is **confirmed** iff it beats composite_2f
with p < 0.05 on the paired monthly IC test AND its raw mean IC is higher. If it loses
(either sign, p < 0.05) the verdict is **rejected** and composite_2f ships; if |p| ≥ 0.05
the verdict is **inconclusive** and composite_2f ships (simpler wins ties — the same rule
P4.1/P4.1b used). **In every non-confirmed outcome the composite keeps shipping**; the ranker
is only adopted on a clear win, per plan 4.2 ("if it loses, ledger says so and composite
ships").

**Freeze protocol (plan 4.3, checked in this run):** the run writes `artifact/` containing
`model_meta.json` (hyperparameters, feature list, fold dates, sklearn version, seed) and the
per-fold training manifests. **Reproducibility check:** refit the LAST fold twice and the
FIRST fold twice; assert identical predictions to < 1e-12 both times (deterministic refit);
then re-score the last fold's picks (top-5% by predicted score) from the saved manifest and
assert the pick set matches the live computation exactly.

**Honest caveats, pre-declared:** (1) the ranker sees all 22 features, several of which
E002/E002b rejected on direction — giving the model more rope than the composite is the
point of the experiment, but it also raises overfitting risk that the walk-forward only
partially controls; (2) squared-error on raw returns lets a few extreme forward months
dominate the loss; (3) ~145 refits × 200 trees is minutes of compute, deliberately spent —
no subsampling shortcuts; (4) the gate is the validation slice only — the Phase 6 walk-forward
on the test window remains the only result that counts.
