# P4.1b — verdict (written after the run; the hypothesis was not edited)

**Verdict: CONFIRMED — the two-feature composite (`mom_12m_1m` + `delivery_pct`) clears the
M3 bar and ships as Phase 4's v0, superseding P4.1's single-feature ship.**

- **PRIMARY 1 (`composite_2f` vs `best_single`):** mean monthly IC **0.0681 vs 0.0529**
  (comparator = `mom_12m_1m`, slice-selected, winner's curse included) — paired diff
  **+0.0153** over 145 months, t = +2.49, **p = 0.0140 < 0.05**. The gate P4.1's
  three-feature form missed at 0.0585 is cleared by dropping the weakest third vote.
- **PRIMARY 2 (`composite_2f` vs `composite_3f`):** +0.0057 (0.0681 vs 0.0625),
  t = +1.30, **p = 0.196** — dropping `mom_6m` helped on the point estimate, exactly as the
  P4.1 verdict suspected, but the help is not individually significant. The honest reading:
  the third vote was dead weight, not poison; the two-feature form wins because it is simpler
  and no worse, and its win over the SINGLE feature is what clears the pre-registered bar.
- **Precision note, recorded against the ship decision:** top-5% slice precision ranks
  3f (55.4%) above 2f (54.8%) above single (53.0%) — the tail metric mildly prefers the
  three-feature form while mean IC prefers the two-feature form. Mean monthly IC was
  pre-registered as the primary; the flip is disclosed, not hidden. A tail-focused variant
  (optimize top-5% precision directly) is a different experiment and was not run.
- **Consequence for the plan:** 4.1's shipped score is now **`composite_2f`** — the mean of
  cross-sectional percentile ranks of `mom_12m_1m` and `delivery_pct`, equal weights,
  parameter-free (P4.1's construction, one fewer input). 4.2's ranker must beat the same
  gate against this form, and the reference number to justify model complexity is now
  **0.0681** on the validation slice. Task 4.3's freeze protocol applies to the two-feature
  definition from here.
- **Honest caveats:** (1) post-hoc refinement after P4.1 — the pre-registration is the only
  protection, and both comparisons share P4.1's slice (no fresh data; family error across
  P4.1 + P4.1b is unadjusted by pre-registration, as declared). (2) The walk-forward (Phase 6)
  re-tests the two-feature form out-of-sample on the test window; nothing here predicts it
  holds. (3) The comparator's 0.0529 remains winner's-curse-optimistic, which makes clearing
  it the *easier* bar — the margin (+0.0153) should be read against that.
