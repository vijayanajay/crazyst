# E018 — breadth portfolio: rank-weighted top decile, monthly, 12-month holds — the first architecture whose arithmetic targets 10–20% CAGR

Pre-registered 2026-09-27, **before the run** (BRD §12): the arms, guards, bars and
decision rule below are frozen. The runner is implemented after this file exists and the
file is never edited afterwards; the verdict is written beside it as `verdict.md`.

## Motivation (from the committed record, cited)

- **The engine captures 9.4% of its own signal**: 5,605 arm-convention picks over the
  145-month slice, 529 completed picks (E014 `arms.baseline`). The 8-slot architecture
  discards 90%+ of the cross-section by construction; E011's own curve shows breadth is
  the recovery direction (4→8 slots recovered ₹403k of ₹510k of losses).
- **The basket arithmetic already supports the target band**: E006's all-picks book
  (≈ top-5%, ~38/month) earns **+3.05%/month net at 0.2%/side** (and rank>600 — most of a
  decile — earns MORE: +3.34%). At the engine's ~0.85 round trips/position-month cadence
  and E016's proven 12-month holds (87% of edge retained), the annualized arithmetic lands
  at 10–20% CAGR — the band no engine arm has ever reached.
- The index did +13.17% over this slice. A breadth book must beat that to matter.

## Window

The 145-month validation slice (2011-07-29 → 2023-07-31, boundary 2023-09-24), harness
convention (all decision-date eligible rows), test window untouched. This is a
**paper-book experiment**: it uses realized forward returns of the picks (E006/E018-style
leg arithmetic + adj_close month-end marks for price-path honesty), NOT the 8-slot engine —
the engine is the thing being replaced, so simulating inside it would beg the question.
Declared simplifications (caveats, same family as the break-even block): no intra-month
stops, no fill-gate refusals, no ADV impact cap; costs at the real-world ~0.21% per round
trip (LEDGER 2026-09-27 real-cost analysis) with a 0.5%/side sensitivity arm; delisting
legs priced at the symbol's last traded mark (sell-at-last-trade proxy, no dropped legs);
weights set at entry, never rebalanced mid-hold (E015's engine finding).

## Arms (frozen)

- **A TOP5_EQUAL** — top 5% of each month's cross-section (the smoke's own `_picks` set,
  ~38 names), equal weight, 12-month overlapping books (enter every month, exit at month
  +12), costs 0.21% per round trip. The baseline: the known basket.
- **B DECILE_RANK_W** — top decile of the cross-section (~77 names; every symbol with
  composite rank percentile ≤ 0.10), **rank-weighted** (weight ∝ 1/rank_position, normalized
  within the book), 12-month overlapping books, same cost model. The arm under test.
- **C DECILE_EQUAL** — same decile, equal weight (isolates the weighting effect).
- **D DECILE_RANK_W_MODELED_COST** — B at the shipped 0.5%/side model (the sensitivity
  arm: how much of the result survives the pessimistic cost model).

## Guards (frozen; all must pass for the run to count)

- **G0 (tradeability, added pre-run with the pilot's disclosure):** books are drawn from
  the LABELED decision rows only (the smoke's own convention). The pilot run found that the
  arm convention (all decision rows) puts 64.4% of picks in symbols with no adj_close
  coverage at all (unlabeled rows — delisted/renamed/out-of-window names the E012 floor
  already excludes from the labeled chain; 1,066 of 4,052 bhav symbols have zero Yahoo
  coverage, a pipeline finding recorded separately). A paper book cannot hold unpriceable
  names; the labeled convention is the tradeable one (verified: 4,522/4,522 labeled top-5%
  legs have both entry and exit marks). The 5,605 arm-convention pin stays as a G2
  cross-check of the selection code, not as a book.
- **G1** arm A's leg-level mean **gross** at 1-month holds reproduces the smoke's
  committed label-based `mean_gross` (+2.8113%/mo) within 0.15pp — the price-path vs
  mark-timing gap the break-even block measured is 6.3e-4 (the pre-registered draft
  originally cited E006's +3.05%, but E006 ran the pre-floor 6,622-pick book; the anchor
  is the current tape's own committed gross). Costs are then applied at the real-world
  round trip.
- **G2** tape pins: mean monthly IC == `smoke.SLICE_IC_PIN` to 1e-9 on the labeled
  convention; arm-convention picks == 5,605 (exactly — the selection code is shared).
- **G3** the price-path leg sets are survivorship-honest: zero dropped legs in every arm
  (every leg priced at entry and exit marks; delistings exit at last traded mark).
- **G4** B's book width: the decile is `round(10% of the month's scored cross-section)`
  by definition; the width window is a sanity check on that definition, not on a chosen
  number. *(Amended pre-run with disclosure: the frozen [70, 85]/≤90 guessed the
  cross-section's size distribution from the ~770–800 eligible count; the scored
  cross-section is wider (median ~610 scored names → median decile 61, max month 115). The
  check becomes median ∈ [55, 85] and every month ≤ 130 — still failing only if the
  decile construction itself breaks.)*

## Bars (frozen)

- **B1 (primary):** B's annualized net CAGR ≥ +10% over the slice.
- **B2:** B's maxDD ≤ the index-equivalent's worst drawdown over the same months + 10pp
  (the breadth book must not be a worse ride than buy-and-hold by more than that; the
  index's own maxDD over the slice is computed from the same sourced TRI curve and
  recorded in `results.json`).
- **Recorded, not gating:** B vs the index CAGR gap (the verdict prints it — the
  index-equivalent convention); turnover per year; the 2018-2020 sub-window (the
  small-cap stress period) separately; C vs B (weighting effect); D vs B (cost-model
  sensitivity).

## Decision rule

PASS iff B1 and B2 hold for B (the rank-weighted decile), all guards green. On PASS, the
follow-on is a portfolio-design decision (execution costs at real tick sizes, min
notional, the index-core/satellite blend) — not an engine change; nothing in the shipped
engine/config changes as part of this experiment. On FAIL: the breadth arithmetic does not
survive breadth (edge decay beats diversification), and the recorded conclusion is that
the signal cannot support 10–15% in ANY architecture measured — the program's final
recommendation becomes the 70/30 index-core + satellite blend or pure indexing.

Disclosures rule: any deviation between coded bars and these words is recorded in
`results.json` (`bars`, `bars_as_coded`) the E013/E014 way.
