# E008b — Verdict: FAIL (the intra-month gate never fires where it is aimed)

Run 2026-09-26, profile `full`, boundary 2023-09-24 (test window untouched), git
`1dbec3e` (working tree). Built exactly per hypothesis.md: `market_breadth_daily` (3,675
sessions from 2011-10-20), as-of membership from the latest `universe_rank` snapshot at or
before each session, 200-trading-print adjusted-close DMA, NULL-shrinking denominator,
member join only (E008a's dilution lesson). 7 arms × 3 windows through the interim
evaluator (per-session Trigger-B, daily marks, the smoke's real engine layers).

## Gauge integrity (must pass before the premise means anything)

- **Member-level recompute to 1e-6** at 2017-06-30 (74.7%, 154 members), 2018-10-25
  (22.7%, 163), 2020-03-23 (4.1%, 169) — SQL table vs an independent Python recomputation
  of every member's trailing-200 adj-print DMA. E008a's aggregate bug would not have
  survived this layer.
- **Intra-month trough visible:** 2020-03 minimum **4.1% on 2020-03-23** vs month-end
  15.5% — the daily sample shows the crash trough the monthly decision date never sees
  (4.1% on the worst day vs 15.5% at month-end: the information is there intra-month).
- **Stress visibility:** 2018-09/10 average 33.2% vs the 2017 calm 78.9%.

## The gate, measured

| window | baseline ret | baseline maxDD | best gate arm | fires | in-window effect |
|---|---|---|---|---|---|
| W0 calm 2017-06..08 | −3.17% | 5.79% | identical (all 6) | 0 | curves bit-identical |
| W1 stress 2018-09..11 | −0.03% | 0.03% | identical (all 6) | 0 | nothing to protect |
| W2 crash 2020-02..04 | −2.14% | 20.41% | identical (all 6) | 1 (Apr 15, breadth 24%) | equity identical to the rupee |

The single gate fire in the entire experiment: HDFCBANK, 2020-04-15 — **in the rebound**,
16 days after the crash trough, and its T+1 fill lands outside the window. Baseline held
the name until its own April-30 review exit; the 4 pp tighten moved the decision 15 days
and changed nothing economically.

## Reading

1. **The trail already carries the protection; breadth adds no timing.** In W2 the
   baseline's stop/DMA/review clauses did the exiting (ARVINDFASN stopped Mar 9; the
   March review swapped the dead month-end picks for banks; two stops fired Apr 3). The
   breadth-tightened trail had nothing left to protect earlier — the same 20.41% max
   drawdown to the rupee.
2. **The mistiming E008a found at monthly cadence reproduces intra-month.** When breadth
   finally sits below 40, the crash is over; a gate that tightens exits on the state is
   again selling insurance after the fire — now demonstrated at daily granularity.
3. **W1 was an uncontrolled event, not a stress test:** the E006 fill model (correctly)
   refused 26/50 selection orders as `non_fill_adv` — the model's four highest-scored
   names (LIQUIDETF, INFRABEES, SPLIL, GKWLIMITED) were untradable at ₹250k/slot — so the
   portfolio sat in cash through the crash month. A trail gate has no drawdown to cut on
   a cash book. The stress-window conclusion therefore rests on W2 alone.
4. The engine machinery behaved correctly throughout: no `no_bar` non-fills, one
   `circuit_lock` (SPENCERS, Apr 3), ADV refusals only on genuinely thin names.

## Decision

- **FAIL on the pre-registered rule**: criterion (a) — strictly lower max drawdown in both
  W1 and W2 — is unmet (max drawdown identical in both; return criterion (b) trivially
  holds only because nothing changed). W0 confirms the default-OFF contract: curves
  bit-identical, zero false fires.
- **Do NOT wire the breadth gate**: `trigger_b_breadth_trail_tighten` stays `null` (OFF)
  in config.yaml; the plumbing stays (self-checked, default-inert), `market_breadth_daily`
  remains a §11 per-regime reporting table. The breadth-protection question is closed at
  monthly AND intra-month cadence with evidence, not lore.
- Interim-evaluator caveat (declared in the pre-registration): fixed windows from an
  all-cash start, no delivery-z clause, monthly re-selection only. The 6.1 walk-forward
  harness remains the final judge for anything that survives a pre-registration — none
  did.
