# Real-world delivery cost analysis — how close does the engine get to the index at honest costs?

2026-09-27, analysis (not a pre-registered experiment: it varies no code path, it re-reads
committed artifacts — E006/E010's measured sweeps and E017's fills — and does arithmetic
on them; the LEDGER block records it as such).

## The measured cost response (E006, validation slice, picks-only, per side)

| cost/side | 0.2% (modeled floor) | 0.5% (shipped model) | 1.0% | 2.0% |
|---|---|---|---|---|
| all picks net/mo | **+3.05%** | +2.45% | +1.45% | −1.55%* |

\* E006's 2% column sits in the `rank>600` group; the all-picks 2% point is the E010
reproduction's floor decision (`floor_all_gross` 2.76% gross → the 1% net edge halves
between 0.5% and 1.0%/side — `rank600_edge_halves_at` 0.01).

Linear response, exactly 1:1 with the per-side cost (each +0.1%/side costs ~0.2%/round
trip → −0.2%/mo of net edge at 1 round trip/month): **edge/side = 3.45% − 2 × cost/side**
per month of holding.

## Real-world delivery costs (India, 2026, small-account delivery)

Brokerage (discount broker, delivery): 0%. Statutory + charges: STT 0.1% buy + 0.1% sell,
exchange charges ~0.00297%, SEBI ~0.0001%, stamp 0.015% buy, GST ~0.0046% (18% on
exchange+transaction), DP charge ~₹13–15/sell (negligible at 8-slot ₹125k notional:
~0.011%). **Total ≈ 0.21–0.24% per round trip ≈ 0.105–0.12% per side.** The shipped model
(0.5%/side, E010) is ~4–5× the real number; E006's 0.2%/side "floor" is ~1.7–1.9× real.

## What the engine earns at real costs (picks-level, per the measured response)

- At 0.105%/side: 3.45% − 0.21% ≈ **+3.24%/mo** net edge on the 1-month-hold book.
- The engine's actual cadence (E017): ~983 fills / 145 months ≈ 0.85 round trips per
  position-month at 8 slots — so cost drag ≈ 0.21% × 0.85 ≈ **0.18%/mo** at real costs,
  vs ~0.85%/mo modeled.

## Through the engine (the honest step: E017's D2/D5 arms, re-costed)

E017's engine pass models 0.5%/side. Its fills are unchanged across the sweep (983 → 963),
so the sweep's arms differ only in exit quality. Re-costing D2's path at real costs:
modeled cost ≈ 963 fills ≈ 0.85 rt/position-month × 8 slots × 0.5%/side × 2 sides ≈
0.85%/mo of the book; at real ≈ 0.21% per rt ≈ 0.18%/mo. **Delta ≈ +0.67%/mo ≈ +8.4%/yr**
on an invested ~65–70% book.

- D2 at modeled costs: +0.84% CAGR (invested-share-weighted; the engine holds ~35% cash on
  this slice, so the portfolio-level edge is ~0.84% at ~65% deployment ≈ +1.29%/yr on
  invested capital).
- D2 at real costs: ≈ +0.84% + ~5.5–8pp (deployment-adjusted) ≈ **+6–9% CAGR** — within
  striking distance of, though still below, the index's +13.17%.
- A baseline at real costs: −0.50% + ~5.5–8pp ≈ +5–7.5% CAGR.

## Conclusion (recorded, not shipped)

1. The shipped cost model (0.5%/side) is the single largest *modeled* drag; at real-world
   delivery costs the whipsaw-fixed engine (D2) plausibly lands +6–9% CAGR — the first
   configuration that is even in the index's neighborhood, though still below it.
2. This is arithmetic on measured responses, NOT a measured engine run: the honest next
   step is one config change (`backtest.cost_per_side_pct` 0.5 → 0.12) and ONE engine pass
   on the validation slice — but that changes the cost model every prior experiment pinned
   against, so it needs its own pre-registration (E018) and a fresh pin for the smoke's
   engine anchors.
3. Until then: no config change, nothing promoted. The index-equivalent line stands:
   buy-and-hold pays +13.17% with zero fills, zero model risk, zero taxes beyond STT.
