# E010 — Verdict: KEEP 0.5%/side (the default survives re-measurement — now for a measured reason, not a hand-waved one)

Run 2026-09-26, profile `full`, boundary 2023-09-24 (test window untouched), git `e8bf4f2`
(working tree). Protocol per hypothesis.md: E006's measurement imported module-to-module,
the only change the universe. The backward guard passed first: the pre-floor arm
reproduced E006's committed results exactly — 6,622 picks, all means/hit-rates within the
tie-swap tolerance, and E006's recorded edge-halving value (`None`) reproduced by the same
rule. Comparisons are therefore apples-to-apples.

## The tables

| group | arm | 0.2% | 0.5% | 1.0% |
|---|---|---|---|---|
| all | pre-floor (6,622 picks) | 3.04% | 2.44% | 1.44% |
| **all** | **floor (3,902 picks)** | **2.36% (53% hit)** | **1.76% (51%)** | **0.76% (47%)** |
| rank ≤ 600 | floor | 2.29% | 1.69% | 0.69% |
| rank > 600 | floor | 2.49% | 1.89% | 0.89% |

## The mechanism (the decomposition is the headline)

Modelled per-side impact of the picks at the shipped ₹250k slot
(`min(1%, 0.10 × S/med20)`):

| | pre-floor | floor |
|---|---|---|
| mean modelled impact | **0.565%/side** | **0.139%/side** |
| median pick med20 | (illiquid tail present) | **₹2.63cr** |
| by band | — | <1cr: 0.376% (n=703) · 1–5cr: 0.130% (n=1,924) · 5–20cr: 0.030% · ≥20cr: 0.006% |

E006's flat 0.5%/side default was, almost exactly, the **mean modelled impact of a paper
portfolio the engine refuses to build** (0.565% — the untradable tail dominating the
average). On the tradable book, the honest cost stack is flat real costs
(STT + fees + spread, ~0.2–0.35%) **plus** 0.14% modelled impact ≈ **0.5%**. The default
survives — no longer as a hand-waved "conservatism midpoint" (E006's own wording) but as
the measured sum of its parts.

## The rule, applied

- (a) floor "all" net at 0.2% ≥ 2.0%: **2.36% — PASS**
- (b) >600 edge-halving point relaxes (or survives all levels): **FAIL** — it *tightens*:
  pre-floor the >600 edge survived 1.0% (52.1% of base, padded by the untradable gems);
  on the floor universe it halves at 1.0% (0.89% = 35.7% of 2.49%). The tradable small-cap
  tail carries a real but thinner edge, and the deep-cost warning binds it where before it
  was masked.
- (c) impact mechanism (floor ≤ 80% of pre-floor): **0.139 vs 0.565 — PASS** (4× reduction)
- (d) gross retained ≥ 2.3%: **2.76% — PASS**

Three of four pass, and the one failure is conservative: the universe where costs bite
hardest is now actually *in* the portfolio instead of being silently refused by the fill
gate. Per the pre-registered rule — **KEEP 0.5%**.

## Decision

- **No config change**: `backtest.cost_per_side_pct: 0.50` stands; all three levels
  (0.2/0.5/1.0) remain reported per BRD §9.7, with 0.2% explicitly the optimistic bound
  (floor arm nets 2.36% there) and 1.0% the stress bound (>600 edge halves).
- E009's corrected honest baseline (+2.61% at the 0.5% convention) remains the pick-level
  headline; the floor arm's net at 0.5% is **1.76%** with a 51% hit rate — the tradable
  edge after E006's default cost.
- E010's own frozen sample (616 rows, the floor universe's 2020-02 eligible set) now pins
  future re-runs; E009's pre-floor sample (1,136 rows) is untouched.
- Re-open conditions, pre-declared: a real fill-model upgrade (per-name spread data, or
  the 6.1 harness's realized slippage), or a microstructure regime change. A number this
  load-bearing should move on evidence, not on re-tuning.

## Honest caveats

(1) E006's protocol limitations are inherited: flat haircut on month-end closes, no slot
competition, validation slice only. (2) The 0.139%/side impact is the engine's *linear
model* at a fixed slot size — it validates the mechanism's direction and magnitude order,
not per-name realized slippage; Phase 6's fill model remains the binding uncertainty.
(3) The >600 floor group has ~2,000 pick-months — enough for the mean, not for tail claims.
(4) The two frozen samples (E009 pre-floor, E010 floor) pin different universes by design;
re-verification is arm-consistent in each script.
