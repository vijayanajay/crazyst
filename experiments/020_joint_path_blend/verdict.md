# E020 verdict — PASS at 90/10: the blend adds +2.2pp of CAGR over the index for +2.3pp of drawdown

Run 2026-09-27, profile `full`, 145-month validation slice (2011-07-29 → 2023-07-31,
boundary 2023-09-24), test window untouched. `results.json` is the record;
`hypothesis.md` was written before the run and is not edited. The blend is a pure
post-hoc combination of two committed monthly curves (G3 by construction).

> **Index-equivalent (the reference itself):** Nifty 500 TRI over the same 145 months:
> **+13.17% CAGR**, maxDD −28.87%.

## Guards — all passed

- **G1** the satellite leg (rebuilt from E019's own sim loop) reproduces E019's committed
  arm A: CAGR 0.257682 and maxDD −0.4702, both to 1e-9.
- **G2** the index leg equals the committed index-equivalent: +13.17% / −28.87%.
- **G3** no look-ahead — the blend re-splits two curves computed from marks dated ≤ t only.

## The frontier (the point of the whole exercise, on one curve)

| blend | CAGR | maxDD | Sharpe | worst month | DD 2018–20 | B1 | B2 |
|---|---|---|---|---|---|---|---|
| **90/10** | **+15.33%** | **−31.13%** | 0.89 | −25.22% | −31.13% | ✓ | ✓ |
| 80/20 | +17.12% | −33.13% | 0.94 | −26.22% | −33.13% | ✓ | ✗ |
| 70/30 | +18.66% | −35.84% | 0.98 | −27.09% | −35.43% | ✓ | ✗ |
| pure index | +13.17% | −28.87% | — | — | — | — | — |

Bars: **B1** blended CAGR ≥ index + 2.0pp — all three sizes pass. **B2** blended maxDD ≤
index + 3.0pp (≤ −31.87%) — **only 90/10 passes** (80/20 misses by 1.3pp, 70/30 by 4.0pp).

**Decision: PASS. Winner: 90/10 — this w is the design freeze.**

## Reading

1. **The pre-registered bar was the right tightness.** At the 70/30 blend everyone
   instinctively reaches for, the joint-path drawdown (−35.84%) breaks the 3pp tolerance —
   the satellite's small-cap air pockets bleed into the blend exactly as E019's account
   measurement predicted. The constant-mix rebalance also means the satellite's worst
   stretch is *bought into* (more satellite weight after it falls), which is return-additive
   but drawdown-negative.
2. **The frontier is real and monotone:** +2.2pp CAGR per +2.3pp maxDD moving 0→10%
   satellite; +1.8pp/+2.0pp for 10→20; +1.5pp/+2.7pp for 20→30. The first 10% is the only
   size whose trade is inside the pre-registered risk tolerance.
3. **90/10 is the design freeze per the pre-registration:** blended +15.33% CAGR (index
   +2.16pp), maxDD −31.13% (index +2.26pp), Sharpe 0.89. The test-window confirmation —
   the ONLY remaining step — must use exactly this w, on the untouched 35 test months,
   with no re-tuning.
4. **Not claimed:** impact at larger ticket sizes (a 10% satellite of ₹10L is ~₹1L over
   ~77 names — ₹1.3k/name, trivially executable at this scale but the design freeze is
   scale-specific); tax treatment of the monthly re-splits; the 2018–2020 small-cap
   stress is INSIDE these numbers (−31% sub-window drawdown) — it is the worst stretch and
   it is survived.

**Consequences:** nothing shipped (a design freeze is a decision record, not a config
change). The breadth family's remaining open item is E021 (the entry-gate control): if it
passes, the gated satellite re-enters this blend measurement before the freeze is
finalized; if it fails, 90/10 stands as frozen above.
