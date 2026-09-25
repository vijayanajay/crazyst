# Checkpoint pack — Phase 3 (feature library + univariate sweep) and Phase 4 (selection model)

**Date:** 2026-09-25 · **Profile for all reported numbers:** `full` (2011-07 → 2026-09-24
cutoff, except where a `quick` window is named) · **Git:** `ba590cb` · Everything here is
pre-registered per BRD §12 — hypothesis committed before each run, verdict written after,
evidence in `experiments/*/results.json` and the ledger blocks in `LEDGER.md`.

**The one-paragraph answer:** the Phase 3 sweep killed the folklore and kept two families —
**12M−1M momentum** and, reversing the quick-profile rejection, **delivery%** at full
history. Phase 4 turned them into a two-feature, parameter-free composite that cleared the
pre-registered gate (p = 0.0140) against a winner's-cursed comparator, then **beat the
learned ranker** that tried to replace it (p = 0.0159 the other way). Cost sensitivity says
the small-cap tail the strategy depends on is cost-resilient at equal fills — making the
fill model, not the cost constant, the thing Phase 5 must get right. The walk-forward on the
untouched test window (Phase 6) remains the only result that counts.

---

## 1. Experiment verdicts (ledger order)

| exp | question | verdict | the number that matters |
|---|---|---|---|
| E002 (quick) | univariate IC sweep, 11 up-months | partial | mom_12m_1m +0.065 BH-surviving; delivery rejected — later shown to be a bull-window artifact |
| E001 | winners vs rest anatomy | partial | momentum anatomy confirmed (AUC 0.544); delivery anatomy rejected; strongest separator = volatility state, **lore direction wrong**, uniform across buckets |
| E002b (full) | confirmation sweep, 15y, month-fixed-effects removed | **confirmed, one reversal** | **delivery family real** (delivery_pct +0.049, p = 1.2e-11); mom_12m_1m +0.052 counter-cyclical (+0.099 down / +0.023 n.s. up); atr_ratio regime-flips (+0.045 up / **−0.183 down**, 94%) |
| E000 | is top-1500 really large/mid-cap? | rejected on the letter, noise-bound in substance | top-1500 **contains** Nifty 200 (min 97.7%); pooled hit-rate Δ 0.86pp (~2σ) — no index data ever needed |
| P4.1 | 3-feature composite vs best single | inconclusive | 0.0625 vs 0.0529, p = 0.0585 — near-miss recorded as a near-miss; atr overlay rejected (p = 0.0033) |
| P4.1b | drop the weakest vote (mom_6m) | **confirmed** | 2-feature composite 0.0681 vs 0.0529, **p = 0.0140** — the gate clears |
| P4.2 | learned ranker vs composite_2f | rejected | ranker 0.0402 vs 0.0681, p = 0.0159 — a clear loss |
| E006 | do costs kill the >600 tail? | rejected | >600 edge survives 1.0%/side at 52% of base — the warning doesn't bind at equal fills |

**What died at this checkpoint** (the plan promised priors would): the delivery-is-noise
prior (E002b reversed it), low-volatility/"squeeze" lore (direction wrong, twice, and
regime-flipping), five candle/accumulation features (BH-rejected on direction at 15 years),
the atr-regime overlay via a trailing-market proxy (P4.1), the learned ranker (P4.2), and
the ₹5cr-floor "subsumed" premise (measured false; BRD §4 amended).

## 2. The chosen model — `composite_2f`

**Definition (pinned by `experiments/004b_composite_2feat/hypothesis.md`, task 4.3):** for
each decision month, the mean of the cross-sectional **percentile ranks** of
`mom_12m_1m` and `delivery_pct`. Equal weights, no fitted parameters, NaN rows stay NaN
(≥ 1 non-NaN feature required). No tuning happened anywhere in Phase 4 — every comparison
was pre-registered before its run.

**Why it won:** both inputs are E002b-confirmed at 15 years with the pre-registered sign
(+0.052 and +0.049 mean monthly IC, 64%/72% of months positive), from *different* feature
families (momentum / delivery), both strongest in down-regimes — the model is a
crash-following ranker by construction. It cleared the M3 bar vs the winner's-cursed best
single feature (+0.0153, p = 0.0140) and then defended its seat against the 22-feature
gradient-boosted ranker (+0.0221 the other way, p = 0.0159). Simplicity was not the tiebreak
here; it was the winning property.

**Validation-slice scoreboard** (145 decision months, 132,530 labeled rows, boundary
2023-09-24; the 35 test-window months were counted and never scored):

| arm | mean monthly IC | top-5% precision |
|---|---|---|
| **composite_2f** | **0.0681** | 54.8% |
| composite_3f (P4.1 control) | 0.0625 | 55.4% |
| best single (mom_12m_1m, slice-selected) | 0.0529 | 53.0% |
| HistGBR ranker (walk-forward) | 0.0402 | 54.5% |

## 3. Freeze evidence (task 4.3's done-when, demonstrated)

- The composite's "fit" is parameter-free, so its freeze artifact is the pinned definition
  plus the feature list — in version control since before the run.
- The ranker run (which needed a real freeze) proved the protocol end to end:
  `experiments/0042_learned_ranker/artifact/model_meta.json` pins hyperparameters, the
  22-feature list, sklearn version, seed and the 120-fold manifest; first and last scored
  folds refit **bit-identically** (max |diff| = 0.00e+00); the last fold's top-5% pick set
  reproduces exactly from a fresh refit; the artifact's fold count round-trips.
  **Re-running an old run with its saved artifacts reproduces its picks — demonstrated.**

## 4. Cost table (E006; 6,622 composite_2f pick-months)

Mean net return per pick, net = gross − 2 × cost, validation slice:

| group | 0.2%/side | 0.5%/side | 1.0%/side |
|---|---|---|---|
| all picks | 3.05% (52.8% hit) | 2.45% (50.6%) | 1.45% (46.3%) |
| rank ≤ 600 | 2.25% (54.5%) | 1.65% (52.5%) | 0.65% (48.4%) |
| **rank > 600** | **3.34% (52.2%)** | **2.74% (49.9%)** | **1.74% (45.6%)** |

- **BRD §9.7's warning does not bind at equal fills** — the rank>600 tail is the strongest
  group at every cost level (52% of its 0.2% edge survives 1.0%).
- **The caveat that matters:** the scan models a uniform haircut; impact, slippage and
  non-fill — the real mechanism §9.7 worries about — are unmodeled. **The fill model is the
  open question, not the cost constant.**
- **Report default set: 0.5% per side** (edge at 82% of base; 0.2% optimistic for a
  601–1500-heavy pick set, 1.0% survivable but halves the hit rate). All three levels stay
  in every Phase 6 report.

## 5. Open items carried into Phase 5/6

1. **Fill model** (Phase 5's hardest problem, per E006): T+1 open fills, circuit locks,
   liquidity-aware slippage/non-fill — the mechanism that could still make the small-cap
   edge fictional.
2. **Two BRD-owner decisions** (`docs/brd_decisions_universe.md`): universe choice
   (recommendation: keep top-1500; pooled Δ 0.86pp) and the ₹5cr floor (recommendation:
   keep off, amend §4 — done on the text side). Default path runs top-1500 / floor-off,
   flagged BRD-owner-review-pending.
3. **Regime overlay, done right:** E002b showed atr_ratio flips by regime; P4.1's
   trailing-market proxy failed to capture it. A real regime classifier (index drawdown
   state) is pre-registrable as its own experiment.
4. **Tuned ranker:** P4.2's hyperparameters were fixed a priori; a tuned variant is a
   future pre-registration, not a loophole.
5. **The walk-forward (Phase 6)** on the untouched 35 test-window months — with the 0.5%
   default, binomial CI vs the 5% baseline, and per-regime + size-bucket attribution —
   remains the only result that counts (BRD §10).

*Every number above is reproducible from its experiment's `results.json` (config snapshot,
git hash, data cutoff) and the ledger blocks in `LEDGER.md`.*
