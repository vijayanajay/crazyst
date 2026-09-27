# E008a — Hypothesis: does own-data market breadth predict losing pick-months? (pre-registered)

Written **before** the run, per BRD §12. The proposal (fixissues_phase36.md follow-up):
no external index/VIX feed is needed — market regime can be measured from the repo's own
bhav + as-of liquidity rank as **breadth**: the share of the as-of top-200 liquid stocks
whose adjusted close is above its own 200-session DMA. This experiment pre-tests the
premise before any portfolio rule is wired: **low breadth must predict negative forward
months for the shipped model's picks**, or the gate idea dies here cheaply.

## Construction (fixed before the run)

- `market_breadth(date DATE, breadth_200 DOUBLE, breadth_mid DOUBLE)` in DuckDB, one row
  per decision date (month-end session), full history, rebuilt by the run script.
- **As-of membership:** the top-200 set at date D comes from `universe_rank` as of D
  (rank ≤ 200) — never a static list (E000's survivorship lesson). The mid tier is
  201–1000 (the review's proposed cut boundary), same construction.
- **DMA:** 200 *trading sessions* (not calendar days), computed on **adjusted closes**
  (a raw-price DMA breaks at splits/bonuses) via a dense per-session calendar so
  suspensions cannot shift a window. A symbol with fewer than 200 sessions of history is
  **not counted** (neither above nor below); the denominator is the count of symbols with
  a defined DMA, so a NULL adj print shrinks the denominator rather than voting "below".
- **Early history:** the DMA exists only after ~200 sessions from 2011-01; months before
  the first defined breadth value are excluded from every statistic and the count is
  reported.

## Metrics (all on the validation slice, boundary 2023-09-24; test window untouched)

1. **Premise test:** for thresholds X ∈ {30, 40, 50} on the top-200 tier: mean forward
   month return of composite_2f's top-5% picks (tie-broken by symbol, the Phase 6
   contract), equal-weight universe forward return, and pick hit rate, split by
   breadth < X vs ≥ X. The premise **holds** iff low-breadth months show materially
   worse pick outcomes at **two or more adjacent thresholds** (the threshold is a
   family, not a tuned point).
2. **Predictiveness:** Spearman rank correlation of monthly breadth vs the month's pick
   mean return and the universe return (one value per month, ~150-180 months —
   cross-sectional IC does not apply to a time-series feature).
3. **Flip frequency:** count of month-to-month state flips per year at each threshold
   (the whipsaw cost of any gate built on it); a threshold that flips > ~4×/year is
   declared unusable as a monthly gate.
4. **Two-tier split:** breadth_200 vs breadth_mid (ranks 201–1000) on the same months —
   does the mid tier add information (e.g. the 2018 midcap stress), and do they
   disagree often enough to matter?
5. **Regime sanity:** breadth in the known stress months (2018-09 onward, 2020-03,
   2011-08/09) vs the calm months — the gauge must see the famous tape events or it is
   mis-built.

## Pre-registered decision rule (written before the run)

- **Premise HOLDS** → pre-register E008b (the portfolio gate arm) with the threshold
  family {30, 40, 50}, selected on the validation slice only.
- **Premise FAILS** (no consistent low-breadth penalty, |ρ| < 0.15, or flip frequency
  too high) → **do not wire the gate**; record that the breadth table exists as a
  per-regime reporting input only (§11), and the gate question is closed with evidence.
- Anything ambiguous → inconclusive, no gate, reporting-only use.

This file may not be edited after the run (BRD §12).
