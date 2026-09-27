# E011 verdict — ADOPT n_slots = 8 (the pre-registered rule fired)

Run AFTER hypothesis.md (2026-09-26, full profile, cutoff 2026-09-24, 35 fold months
2023-08-31 → 2026-06-30, refit month 2023-07-31). Every arm determinism-verified (each
pass run twice, serialized evaluations identical); **A4 guard bit-identical to the shipped
Phase 6.1 baseline** on every guarded number (final equity 489,703.08767582977,
completed picks 63, hit rates, churn 1.6571…, hold 44.9229…, maxDD −0.6516…, total return
−0.51029…); paper-pick stats identical across all four arms by assert. The same harness,
unmodified, moved one lever.

## Arms

| arm | n_slots | equity | return | CAGR | Sharpe | maxDD | picks | hit | month hit | churn/mo | hold d | buy slip | sell slip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A4 (control) | 4 | 489,703 | −51.03% | −22.29% | −0.38 | −65.2% | 63 | 33% | 40% | 1.66 | 45 | +0.441% | −0.420% |
| **A8** | 8 | **892,626** | **−10.74%** | −3.93% | **−0.29** | **−23.9%** | 125 | 32% | 63% | 3.46 | 53 | **−0.099%** | −0.306% |
| A12 | 12 | 731,870 | −26.81% | −10.44% | −0.36 | −42.1% | 182 | 34% | 71% | 5.03 | 62 | +0.103% | −0.204% |
| B8 (churn ctrl) | 8 + wider %iles | 882,467 | −11.75% | −4.32% | −0.33 | −23.8% | 125 | 32% | 60% | 3.43 | 53 | −0.034% | −0.307% |

Paper top-5% picks (arm-invariant): 2,196 picks, 56.6% hit, mean gross +2.32%, net +1.32%.

## The decision rule, evaluated mechanically

Bars (fixed in hypothesis.md): ADOPT a wider count iff for A8 or A12 —
1. equity ≥ A4 + Rs 200,000, 2. Sharpe > A4, 3. maxDD ≥ A4 − 2pp, 4. pick hit ≥ A4 − 3pp;
   between passing arms the higher final equity wins; ties resolve to shipped 4.

- **A8:** equity 892,626 ≥ 689,703 ✓ · Sharpe −0.29 > −0.38 ✓ · maxDD −23.9% ≥ −67.2% ✓ ·
  hit 32% ≥ 30% ✓ → **passes all four**
- **A12:** equity 731,870 ≥ 689,703 ✓ · Sharpe −0.36 > −0.38 ✓ · maxDD −42.1% ≥ −67.2% ✓ ·
  hit 34% ≥ 30% ✓ → **passes all four**
- Both pass; A8 has the higher final equity (892,626 > 731,870) → **ADOPT n_slots = 8**.

## The answer to the experiment's question

**Concentration, not selection.** Widening 4 → 8 slots recovers Rs 402,923 of the Rs
510,297 loss (+38.6pp of return) with maxDD falling from −65.2% to −23.9%, while the
completed-pick hit rate barely moves (33% → 32%, +1pp at 12 slots). The idiosyncratic
variance of a 4-name book — not the model's picks — was the dominant loss mechanism.
Selection failure is bounded by what remains: A8 still loses 10.7% against a +8.5%
benchmark, and the completed-pick hit (32%) still sits far below the paper 56.6%.

## Secondary findings (disclosed, not load-bearing)

- **The buy-side slippage sign flipped at 8 slots: +0.441% → −0.099% vs the decision
  mark.** Mechanism: per-slot notional halves (Rs 250k → ~Rs 125k), so buys fill at
  roughly half the relative size against the same ADV (smaller modelled impact) — and the
  wider book enters ~8 names/month instead of 4, spreading entries across months where the
  overnight gap is less systematically adverse. A8's *realized book* mean slippage is
  −0.130%/side — favorable. Part of A8's Rs +402,923 is therefore an execution-quality
  gain, not just diversification; the two effects are entangled by design here (slot
  count sets per-slot notional). A per-slot-notional-held-constant arm would decompose
  them and is the obvious follow-up pre-registration.
- **Churn rises with slots** (1.66 → 3.46 → 5.03/mo) — mechanically: more slots, more
  monthly review surface. B8 (wider percentiles) barely moved it (3.43) while giving up
  Rs 10,159 of equity: the churn rise is a slot artifact, not ranking pressure, and
  widening the review bands is NOT the knob. B8's role was to rule it out; ruled out.
- **A12 is worse than A8 on every equity metric** despite more breadth (182 picks, hit
  34%). Whatever marginal diversification the 9th–12th slots add is eaten by the higher
  churn (5.03/mo) and by picking deeper into the top-5% list at 12 names/month. 8, not
  "more is better".
- Non-fills: 1 circuit lock at A4, ZERO at A8/A12/B8 — the fill gate never bound at
  smaller per-slot notionals (consistent with E009's floor + E010's impact decomposition).

## Consequence

`portfolio.n_slots: 4 → 8` in config.yaml, citing this verdict. Per BRD §10.3, the
shipped Phase 6.1 run (git a8cc624 baseline) stands archived as the final-judge run at
the shipped config; the harness re-run from scratch (A8's own pass IS that re-run) is the
new reference. The remaining −10.7% vs +8.5% benchmark is now attributable to: residual
concentration at 8, entry timing (the adverse open), and exit-rule quality — in that
order of prior evidence. The next pre-registration should hold per-slot notional constant
to split the execution gain from the diversification gain.
