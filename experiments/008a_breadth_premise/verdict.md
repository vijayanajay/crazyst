# E008a — Verdict: PREMISE FAILS (no monthly breadth gate; table kept for §11 reporting)

Run 2026-09-26, profile `full`, cutoff 2026-09-24, boundary 2023-09-24 (test window
untouched), git `a8cc624` (working tree). `market_breadth` built exactly per hypothesis:
as-of membership from `universe_rank` (top-200 and 201–1000 tiers), 200-trading-print
adjusted-close DMA per symbol, undefined-history symbols not counted, NULL-shrinking
denominator. 179 breadth months from 2011-10-31; 141 joined with the validation slice.

**Gauge integrity (must pass before the premise means anything):**
- Blue chips above DMA in the 2017 bull, below in the 2020 crash (member-level checks).
- Known stress months read correctly: 2018-09 **30.7%**, 2018-10 **28.8%**, 2020-03
  **15.5%** — the 2018 midcap stress and COVID crash are both visible in the top-200 tier.
- A first run reported nonsense (141/141 months "below 30"); the member-level sanity check
  caught an aggregate bug (the tier FILTER was on the count, not the average — each tier's
  share was diluted by the other tier's rows: 115/154 = 74.7% reported as 15.2%). Fixed and
  re-verified against the member-level recomputation. The sanity layer did its job.

## The premise, measured

| threshold | months below | pick ret below vs above | universe ret below vs above | hit below vs above | flips/yr |
|---|---|---|---|---|---|
| < 30 | 6 | **+10.70% vs +3.28%** | +11.09% vs +1.56% | 82.0% vs 53.8% | 1.0 |
| < 40 | 21 | +3.88% vs +3.55% | **+4.20% vs +1.58%** | 60.5% vs 54.1% | 1.9 |
| < 50 | 44 | **+2.34% vs +4.17%** | +1.74% vs +2.07% | 56.0% vs 54.6% | 2.3 |

ρ(breadth, next-month pick ret) = **+0.144** (below the 0.15 pre-registered bar);
ρ(breadth, universe ret) = +0.077. Tier agreement ρ = 0.939 (19/141 disagreements at 30) —
the mid tier is nearly redundant with the top-200 tier at monthly cadence.

## Reading

1. **No consistent low-breadth penalty at adjacent thresholds** — the pre-registered
   requirement — so the premise FAILS on its own rule. The deep-trough months (<30) are
   the *best* months in the sample for both the universe and the picks: breadth troughs
   mark bottoms, and the next month rebounds (2011-12, 2016-02→03, 2020-03→04, 2022-06,
   2025-02). A gate that goes to cash on those states sits out the best re-entry months.
2. **Why the famous crashes don't show up as losses here:** the gate's information state
   is evaluated at the decision date and paid at next month's return. By the time breadth
   reads 15% (2020-03-31), the crash is over; the label month is the rebound. A monthly
   gate is structurally mistimed for crash avoidance — it buys insurance after the fire.
3. The only supportive window is 40–50 (−1.8pp pick penalty), with a near-zero universe
   penalty — and it inverts at 40 and reverses at 30. That is a regime-flavored
   correlation, not a gate.
4. Whipsaw was never the problem (1.0–2.3 flips/yr) — the signal is just not there at
   this cadence.

## Decision

- **Do NOT wire the breadth gate** into portfolio rules or the walk-forward (pre-registered
  rule: no adjacent-threshold consistency, ρ < 0.15).
- `market_breadth` **stays as a table** for §11 per-regime reporting (the gauge itself is
  validated); it is rebuilt by this experiment and not part of the daily chain.
- If the regime idea lives on, it lives **intra-month** (weekly/daily breadth on the
  Trigger-B layer, where crash protection is actually timed) — that is a separate
  pre-registration, not an extension of this one.
