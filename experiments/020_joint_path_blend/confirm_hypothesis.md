# E020-C — test-window confirmation of the frozen 90/10 blend

Pre-registered 2026-09-27, **before the run** (BRD §12). This is the final pre-deployment
step named by E020's decision rule: run E020's **exact construction** on the 35 untouched
test months (2023-08-31 → 2026-06-30) with **no re-tuning** — the arms, bars, guards and
decision rule below are frozen before any test-window number is computed.

## Construction (frozen — identical to E020's committed run.py)

Constant-mix monthly re-split of total equity w/(1−w) between the index core (sourced
Nifty 500 TRI month-end marks, table `index_tri`, index_name 'NIFTY 500') and the E019
deployable satellite (arm A: real costs 0.105%/side, 12-month holds, 3% weight cap, no
stops, sell-at-last-trade delisting proxy, labeled rows only, decile book from E018's
`_decile_book`). w = 0.10 — the E020 winner, never re-picked.

## Window

The 35 test months from `P41.split_slice(labeled, cutoff)` test_rows — the exact months
every validation-slice experiment excluded, also the harness's walk-forward folds.

## One disclosed deviation: the sim's warm-up start

E020's construction starts the satellite sim at folds[0] with cash 1.0; inside a 145-month
window that start is the slice itself. The test window is only 35 months, so the analog
choice is not mechanical. Frozen choice: **the sim starts at the first slice month whose
book state is fully formed by the test window** — the sim runs from the slice month exactly 12
before the test window (2022-08-31 → 2023-07-31: one full HOLD period, so at the first
test month the book holds cohorts aged 1..12 with the oldest exiting that month — the
same age structure as any month inside the validation-slice run) and the confirmation
window is 2023-08-31 → 2026-06-30. Sim months before the test window are used only to
form holdings (cash + book); **no test-window number is computed from them.** The
satellite leg is rebased to 1.0 at the test window's first month (preserving monthly
growth ratios), which is what makes the blend a true w/(1−w) constant-mix re-split at
2023-08-31 — the deployed account's re-split of existing equity. The alternative (fresh start at 2023-08-31 with cash 1.0) is
recorded as arm `fresh_start` — a sensitivity arm, not the pre-registered result: a fresh
book is fully invested only after 12 months of ramp, so its early months carry idle cash
that the deployed account would not have (the deployed account carries holdings into the
test window, and so does the warm-up construction).

Disclosure: this warm-up choice is the one degree of freedom E020's "exact construction"
does not settle; it is disclosed here **before the run**, per the same rule that required
E021's G3 amendment to be pre-disclosed. No other deviation exists. If the two arms
disagree qualitatively (PASS vs FAIL), the verdict is NON-CONFIRMED regardless of which
one passes — a result that depends on the unsettled choice is not a confirmation.

## Guards (frozen; all must pass for the run to count)

- **G1 (satellite continuity):** the satellite sim re-run over the 145-month validation
  slice reproduces E020's committed G1 values (CAGR 0.257681…, maxDD −0.470199…) to 1e-9
  (same code, same data — proves no drift between E020 and this runner).
- **G2 (index leg):** the index leg over the test window, dated 2023-08-31 → 2026-06-30
  and CAGR'd by days/365.25 via `src.backtest.metrics.cagr`, equals the harness's
  committed test-window benchmark_cagr (0.12457495616414915) to 1e-9 — proving the
  confirmation's benchmark equals the one every harness result is read against.
- **G3 (no look-ahead):** by construction — the sim at month t consumes only marks dated
  ≤ t; selections at month t come from `_decile_book` on month-t rows only. No separate
  computation; recorded as construction identity, the E020 G3 way.

## Bars (frozen — E020's bars restated on the test window)

- **B1:** blended CAGR ≥ test-window index CAGR + 2.0pp.
- **B2:** blended maxDD ≤ test-window index maxDD + 3.0pp (more negative is worse; the
  bar is `blended_dd >= index_dd − 0.03` in negative-fraction units, E020's B2 as coded).
- **Reported, not gating:** blended Sharpe, worst month, satellite-only curve, and the
  fresh-start sensitivity arm.

## Decision rule (frozen)

CONFIRMED iff B1 and B2 hold for the 90/10 blend (warm-up construction), all guards
green. Otherwise NON-CONFIRMED, and the deploy recommendation reverts to pure indexing
per E020's FAIL clause. Either way the result goes to `results_confirm.json` (the record),
`verdict_confirm.md`, and the LEDGER. Nothing about the blend's construction may be
changed after this file is written; a non-confirmation is final for this design.
