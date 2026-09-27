# E007 — Verdict: REJECTED (keep the top-1500 universe)

Run 2026-09-26, profile `full`, cutoff 2026-09-24, validation boundary 2023-09-24 (test
window excluded and untouched), git `a8cc624` (working tree). Both arms rebuilt the real
derived chain (rank → eligibility → winners → feature_panel → feature_matrix) through its
real builders with only `universe.top_n` overridden; scored with the shipped
`src.model.composite` (composite_2f); engine pass through `smoke_e2e`'s own machinery at
the shipped defaults (exit_gate escalate N=2, 0.5%/side).

**Integrity gates:** arm A ran first and again after arm B restored the chain — the
post-restore run reproduced arm A **bit-for-bit** (mean monthly IC 0.068124…, 6,622
picks, identical shape), so the override leaked nothing and the database is left
BRD-normative (top-1500). Arm A's IC equals P4.1b's frozen value exactly.

## The numbers

| metric | A: top-1500 | B: top-1000 | Δ |
|---|---|---|---|
| eligible symbol-months | 218,648 | 161,422 | **−57,226 (−26.2%)** |
| labeled rows | 178,171 | 132,050 | −46,121 |
| mean monthly IC (145 mo) | 0.068124 | 0.069540 | **+0.00142, t = −0.57, p = 0.57** (paired) |
| top-5% precision (6,622 → 5,047 picks) | 54.6% | 55.6% | +1.0pp |
| mean pick return | +3.44% | +2.81% | −0.63pp |
| below-₹5cr/day share of eligible symbol-months | 62.8% | 50.1% | −12.7pp |
| engine pass: non-fills / forced exits | 4 / 1 | 3 / 1 | −1 / 0 |
| engine pass: return / churn | +3.92% / 1.58/mo | +2.38% / 1.75/mo | worse on the tape |

The paired IC t of **−0.57 is nowhere near the pre-registered t ≥ 2 bar** — the nominal
+0.0014 IC edge for the cut is indistinguishable from month noise (p = 0.57).

## Reading

1. **The signal is unchanged, the evidence is not.** The cut buys no measurable IC or
   precision improvement while discarding 26% of the labeled universe — including the
   601–1500 bucket where E002b measured the strongest confirmed ICs. Per the
   pre-registered rule ("IC not higher at the noise line ⇒ reject"), that alone decides it.
2. **The "illiquidity graveyard" claim is directionally true but doesn't die by the
   cut.** The rank-1000 boundary turns over ₹4.12cr/day vs ₹1.36cr at rank-1500, yet the
   below-₹5cr share only falls 62.8% → 50.1%: **half the top-1000 universe still trades
   under ₹5cr/day.** Illiquidity is a property of the whole small/mid-cap tail, not a
   1001–1500 island.
3. **Tradability benefit is marginal.** One fewer non-fill and zero fewer forced exits on
   the 12-month escalate-mode engine pass; churn rose (1.58 → 1.75/mo) and the tape's
   return fell. Nothing here suggests the gate's stress concentrates in ranks 1001–1500
   (the smoke's own case study, SOLARINDS, ranked well inside 1000).
4. **E006 already showed the tail's edge survives costs** — the 601–1500 bucket was the
   most cost-resilient group at every level. Cutting it trades measured, cost-resilient
   edge for a thesis this run does not confirm.

## Decision

**Keep `universe.top_n: 1500` (BRD §4 as written).** The config invariant stays. A cut
remains available to the BRD owner if live capacity ever demands it, but it now carries
this experiment's negative evidence, not just the review's liquidity thesis.
