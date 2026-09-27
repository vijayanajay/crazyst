# E015 — exposure sizing: does volatility-scaled (equal-risk) slot sizing at unchanged average exposure capture the drawdown relief the regime filter only stumbled into?

Pre-registered 2026-09-27, **before the run** (BRD §12): arms, σ/window/pool definitions,
guards, bars and the reading rule below are frozen. The run happens after this file exists
and the file is never edited afterwards; the verdict goes beside it as `verdict.md`.

## Why (the committed evidence being interrogated)

E013 measured the shelved index filter (Nifty 200 TRI vs its own 200-session DMA) on the
realized 35-month window: it cleared all three pre-registered bars (CAGR −4.29%/−4.18% vs
−6.14%; drawdown severity 19.6% vs 23.0%; Sharpe −0.24/−0.23 vs −0.43) and was NOT adopted.
E014 then tested the premise on the validation slice and REJECTED it as timing: the gate's
35 risk-off intervals were *better* for the baseline than the 109 it left alone (+0.754% vs
−0.026%/month), and the arm's whole-slice equity advantage (Rs 1,108,821 vs 942,030; maxDD
−46.5% vs −65.6%) traces to **exposure / variance drag**, not signal — the baseline's
arithmetic mean was +0.164%/month against a 6.29% monthly sd, so its geometric path
(−0.041%/month) loses to a lower-variance path whatever the signal says.

If that reading is right, a *signal-free sizing rule* should buy back part of the relief:
no index, no breadth, no timing — only each name's own volatility. This experiment measures
how much of the relief is reachable that way, and splits the channel into redistribution
(unchanged average exposure) versus outright de-risking.

## Window, tape, convention (frozen)

The frozen validation slice — 145 months, 2011-07-29 → 2023-07-31, boundary 2023-09-24
(P4.1's split; the 35-month test window is untouched by this family). Tape and convention
are E014's arm convention: `HARNESS._fetch`'s all-eligible decision rows, warm=20 sessions,
exit_gate escalate, cost 0.50%/side, n_slots 8, floor 0.375 — the shipped defaults.

**σ (frozen):** trailing **60** sessions of daily log returns of `adj_close` (split/dividend
adjusted), sampled **at the fold's decision date, sessions ≤ M only** (no look-ahead). A
name needs **≥ 40** returns, else it carries **no view** and its scale is 1.0 (reported).
σ_med is the median σ over the month's pool.

**Pool (frozen):** the set the engine may buy from that month — eligible, with
`rank_pct ≤ monthly_review_replace_above_top_pct` (config 0.15). Held names are not
excluded (disclosed: the engine buys from the pool minus its book, whose mean scale is
therefore ≈1 rather than exactly 1; guard G4 measures the net exposure effect).

## Arms

- **A BASELINE** — shipped equal-weight slots; the sizing hook is absent (`size_scale=None`),
  so this arm must be bit-identical to E014's committed `arms.baseline`.
- **B EQUAL_RISK_MEAN1 (primary)** — per-symbol scale `ŝ_i = clip(σ_med/σ_i, 0.5, 2.0)`
  divided by the mean of the clipped values over the pool's σ-bearing members, so the
  pool's mean scale is **exactly 1.0**: risk-balanced entry notionals at unchanged average
  exposure. Buys are sized `per_slot × ŝ_i`.
- **C DERISK_CAP (diagnostic, no verdict)** — `clip(σ_med/σ_i, 0.5, 1.0)`, no
  normalization: every name at or below its equal-weight slot, the wild ones smaller.
  Average exposure *falls* by construction. Same information set as B (own-name vol only),
  no timing — the "the filter was a crude exposure knob" arm.

### Why there is no portfolio-vol-target arm "at unchanged average exposure"

The book is long-only and cash-constrained: a de-risked stretch cannot be offset by a
grossed-up one (no leverage, and the baseline already spends most of its cash in its good
months). "Unchanged average exposure with lower conditional exposure" is therefore not
causally implementable here. The only implementable devices are **redistribution at mean
1.0** (B) and a **global de-risk** (C) — and the split between them is exactly the
mechanism question this experiment answers.

## Guards (each must pass; failures are disclosed)

- **G1a hook inertness** — a 12-month engine pass with the sizing hook present and no
  scales must reproduce the committed `runs/smoke_e2e/smoke_results.json` escalate arm
  bit-for-bit (the smoke's own convention: labeled-only tape, warm=0).
- **G1b baseline reproduction** — arm A's metrics must equal E014's committed
  `arms.baseline` exactly (same convention, warm=20, same cutoff 2026-09-24): the hook
  changed no shipped number.
- **G2 tape pin** — arm-convention picks total == 5,605 and the mean monthly IC == E012's
  0.375-arm IC (0.07171797803434904) to 1e-9.
- **G3 no look-ahead** — for every 40th (month, symbol) pair in B's scale map, σ is
  recomputed from a fresh per-pair query (the last ≤60 adj closes on or before the fold
  date) and must match to 1e-12.
- **G4 exposure contract** — B's mean invested share (mean over the 145 folds of
  market_value/equity) within **±2.00 pp** of A's. If it fails, B is not "unchanged average
  exposure" and the verdict is **CONFOUNDED** regardless of the bars.
- **G5 normalization identity** — every month's pool mean scale is 1.0 to 1e-12 (B), and
  every C scale is ≤ 1.0.

## Bars (pre-registered)

Relief reference `R = |maxDD_A − maxDD_block|` from E014's committed arms on this same
slice (19.07 pp at the committed numbers).

- **B1 capture** — B's maxDD severity improves by **≥ R/3 (≥ 6.36 pp)** versus A, AND B's
  CAGR **≥ A's − 1.00 pp** (the relief must not be bought with return). maxDD is a negative
  fraction: "improves" = less negative.
- **B2 episodic consistency** — B's within-episode drawdown severity beats A's in **≥ 3 of
  the 6** pre-named episodes (2011_euro, 2013_taper, 2015_16_china, 2018_ilfs, 2020_covid,
  2022_rates; episode DD = max drawdown of the arm's own curve rebased at the episode's
  first fold).
- **Verdict** = **PASS** iff B1 ∧ B2 ∧ G4; **FAIL** if G4 holds and B1/B2 fail;
  **CONFOUNDED** if G4 fails (no verdict).

## Reported (not bars)

capture ratio per arm `(DD_A − DD_X)/R`; the C diagnostic; realized mean invested share per
arm; mean scale actually applied to bought names; resized-buy counts; non-fills; arithmetic
mean and sd of monthly returns per arm (the variance-drag decomposition E014 used).

## Disclosures (frozen)

- The 0.375 floor is **derived** from the fill gate's boundary at the equal-weight Rs125k
  notional (E012). Under B/C the effective notional moves (0.5×–2×), so the gate binds
  differently per arm: the floor is NOT re-derived here and no arm's refusal rate may be
  read as the shipped 1.14%. **Any PASS requires E012's floor re-derivation per arm before
  adoption**, on fresh data.
- Buys up-scaled above 1× can hit the cash constraint and be resized at fill; the resized
  counts are reported and G4 measures the net exposure effect.
- Weights drift after entry (the engine never rebalances), so B equalizes the **entry
  notional's** risk, not the held book's: call it volatility-scaled slot sizing, not risk
  parity.
- A PASS is licence to spend **fresh out-of-sample data** (a pre-registered test-window
  evaluation is legitimate — the test window is untouched by the sizing family) and nothing
  more. It is never adoption; no config changes come out of this experiment either way.
- Sign conventions are stated inline (maxDD negative; "better" = smaller severity) because
  E013 and E014 each recorded a sign slip in their own hypotheses.
