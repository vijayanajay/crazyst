# P4.1 — verdict (written after the run; the hypothesis was not edited)

**Verdict: INCONCLUSIVE at the pre-registered bar — the simpler single feature ships v0. The
composite is a near-miss worth recording, not a win to celebrate.**

- **Composite vs best single (`mom_12m_1m`, chosen on the slice with its winner's curse):**
  mean monthly IC **0.0625 vs 0.0529** — difference **+0.0096** over 145 paired months,
  t = +1.91, **p = 0.0585**. The rule said confirmed iff p < 0.05; it is not. Under the
  pre-registered tie handling (|p| ≥ 0.05 either way ⇒ inconclusive ⇒ simpler ships), **v0 is
  the single feature `mom_12m_1m`**, and the ledger records that the composite might be better
  — the evidence just does not clear the bar we set before looking.
- **Overlay arm: rejected as an addition.** `composite + sign(mkt_trail_1m) × pct(atr_ratio)`
  scores **0.0223 vs the base composite's 0.0625** (paired diff −0.0390 over 138 months,
  t = −2.99, **p = 0.0033**). E002b's regime flip is real in cross-section, but the
  pre-registered trailing-market proxy for the regime does not capture it — worse, in
  up-months the overlay *dilutes* the composite with an atr vote that E002b measured as
  regime-conditional. Per the rule it does not ship in v0. A proper regime classifier (e.g.
  index drawdown state, not the cross-sectional mean of mom_1m) remains an open idea, file-
able as its own experiment — nothing in this verdict tests that.
- **Secondary precision agrees with the ranking story:** top-5% hit rate on the slice —
  composite **55.4%**, overlay 53.2%, best single 53.0% (mom_12m_1m). The composite's edge
  concentrates in the tail it will actually pick from; the point estimate is not an artifact
  of the middle of the distribution.
- **What the slice comparison looked like before the arms:** top-5 single-feature mean ICs on
  the slice — mom_12m_1m 0.0529, delivery_pct 0.0445, mom_6m 0.0276, delivery_pct_trend
  0.0203, mom_3m 0.0135. The composite's three inputs are the top three, but the third
  (mom_6m) adds little beyond the first two — a natural, still-pre-registration-honest
  question for a future two-feature composite is whether it clears 0.05 where three did not.
  That is NOT run here; it would be a new pre-registration.
- **Consequence for the plan:** 4.1 ships `mom_12m_1m` as the v0 score. 4.2 (learned ranker)
  proceeds per the plan against the same comparator — its bar is unchanged, and the composite
  result sets the number to beat: **mean monthly IC 0.0625 on the validation slice** is the
  honest reference point the ranker must clear to justify its complexity, not the single
  feature's 0.0529 (the plan's "beats best single feature" stays the gate; 0.0625 is what the
  evidence says the combination is worth).
- **Honest caveats:** (1) p = 0.0585 is a near-miss — a different α or one more year of data
  could flip it; the discipline is that the α was written before the run, and the near-miss is
  recorded as a near-miss, not rounded down. (2) The comparator's winner's curse was included
  to make the composite's bar conservative; the flip side is that mom_12m_1m's 0.0529 is
  itself optimistic as a shipped-model expectation. (3) The walk-forward (Phase 6) re-tests
  everything out-of-sample; nothing here predicts it will hold.
