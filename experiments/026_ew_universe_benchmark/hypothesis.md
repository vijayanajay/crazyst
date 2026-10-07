# E026 — the equal-weight universe benchmark: the edge measured against the book the strategy actually trades (REPORTING)

Pre-registered 2026-10-01, **before the run** (BRD §12). This is a **reporting
experiment**: no arms are compared against a pass/fail bar, nothing ships, nothing is
adopted. The deliverable is one side-by-side table — EW eligible universe vs E018's
breadth book (arm B) vs sourced Nifty 500 TRI — over the validation slice and the test
window, plus the verdict text that reads the table honestly.

## Motivation (the gap this closes)

Every benchmark in the program's record is the **cap-weighted** Nifty 500 TRI. The
strategy trades the **as-of top-1500-by-liquidity eligible universe** — a mid/small-cap
book. A cap-weighted index mechanically underweights exactly the tail the strategy
lives in, so "the strategy beat the index" has always left the wrong comparison open:
what did the strategy earn vs an **equal-weight** portfolio of the names it was allowed
to buy, held monthly? That number was never computed. Small/mid-cap equal-weight books
earned a large liquidity premium over 2011–2023 on NSE; if the EW universe return
explains most of E018's +29.6%, the "breadth edge" is mostly beta to the strategy's own
universe, not selection.

## Window — measured amendment, disclosed pre-run

The frozen split is derived from the live DB cutoff (`P41.split_slice`: boundary =
cutoff − 36 months). At E018's committed cutoff (2026-09-24) the boundary was
2023-09-24 and the slices were 145/35. The tape has since advanced to 2026-10-01 and
the chain was rebuilt. **Measured before this file was written** (probe run, 2026-10-01,
full-profile chain rebuild):

- boundary moved 2023-09-24 → **2023-10-01** (cutoff − 36 months, as coded);
- validation slice: **146 folds**, 2011-07-29 → **2023-08-31** (gained 2023-08-31, whose
  label end 2023-09-29 now falls at/below the boundary);
- test slice: **35 folds, shifted** 2023-08-31→2026-06-30 became **2023-09-29 →
  2026-07-31** (the 2023-09-29 fold entered from val-side; 2026-07-31 entered as its
  label closed);
- 2026-08-31 is labeled but in neither slice (last labeled month has no next-month
  label end — `split_slice`'s own rule).

This drift is a property of the frozen split convention (cutoff-derived), not a
methodology change. The amendment: **all slices are computed at the live cutoff and
asserted to exactly the measured values above** (146/35, boundary 2023-10-01). The
E018-committed 145-fold slice (→2023-07-31) is additionally reconstructed **exactly** as
the subset of val folds ≤ 2023-07-31, so every tape pin is reproduced on the precise
months E018 pinned, without touching the derived test window.

## Legs (frozen — these are reports, not arms)

1. **EW-ELIGIBLE** — per decision month m: the as-of eligible snapshot from the
   `eligible` table (`eliq[m]`, the top-1500 universe the strategy may actually trade);
   book return = mean over members of (adj_me mark at m+1 / mark at m − 1). Marks from
   `adj_me` (dividend-adjusted month-end), E018's arg_max-per-ym recipe on adj_close.
   A member with no mark contributes nothing and is counted as uncovered (coverage
   reported); the mean is over members WITH marks — this is the same last_mark
   convention E018's books use (no dropped legs; the sell-at-last-trade proxy is
   unnecessary at monthly EW because adj_me carries the last traded adjusted price).
   Monthly-rebalanced, no costs (a benchmark, not a strategy).
2. **EW-LABELED** — same construction over the labeled-row universe (the smoke's
   convention) instead of the eligible snapshot: the comparability leg, isolating how
   much of leg 1 is the labeled-coverage filter.
3. **BREADTH-B (reproduced)** — E018's arm B verbatim (decile, rank-weighted,
   overlapping 12-month cohorts, real costs 0.21% per round trip), recomputed on the
   current tape. Pinned: mean IC == smoke.SLICE_IC_PIN (1e-9), top-5% picks == 4,579,
   arm-convention picks == 5,605, all on the 145-fold subset; B's CAGR within 1pp of
   the committed 0.29644 on the 145-fold subset (tape advanced one decision month,
   2026-08→2026-09; a bigger gap is investigated before any verdict text is written).
4. **NIFTY500-TRI** — sourced Nifty 500 TRI, month-end marks, arg_max per ym, the
   E018/harness recipe. Pinned: index CAGR on the 145-fold subset within 1e-6 of the
   committed 0.13174664181300377 (the sourced series is fixed history — a gap means the
   recipe drifted, not the tape).
5. **Harness benchmark pin (test window)** — on the shifted 35-fold test slice, the
   TRI leg's CAGR is reported next to E020-C's committed benchmark 0.12457495616414915
   (computed on the OLD 35-fold window); they will NOT match exactly because the window
   itself moved — the diff is recorded and disclosed, not asserted away.

## Conventions (frozen)

- CAGR: `(series[-1]/series[0]) ** (12/(n_marks-1)) - 1` (E018's formula, legs 1–4).
  Legs 1–2 are reported BOTH as monthly-rebalanced CAGR and as a **breadth-book-comparable
  figure** computed by the same cohort arithmetic E018 uses (overlapping 12-month
  cohorts on the EW monthly series, no costs), so the EW number and the book number are
  measured the same way — the comparison is like-for-like, not series-vs-cohorts.
- maxDD: running peak-to-trough on the monthly equity series (negative fraction).
- Costs: leg 3 only (it is a strategy leg); legs 1, 2, 4 are costless benchmarks.
- No stats tests: reporting experiment. The verdict text states the gaps and what they
  imply; it claims no significance.

## Guards (frozen; all must pass for the run to count)

- **G1** the split: boundary == 2023-10-01, val folds == 146 (first 2011-07-29, last
  2023-08-31), test folds == 35 (first 2023-09-29, last 2026-07-31), 145-subset folds
  == 145 (first 2011-07-29, last 2023-07-31). (The measured amendment above.)
- **G2** tape pins on the 145-subset: mean monthly IC == smoke.SLICE_IC_PIN (1e-9);
  labeled top-5% picks == 4,579; arm-convention picks == 5,605.
- **G3** leg-4 index pin: CAGR on the 145-subset within 1e-6 of 0.13174664181300377.
- **G4** leg-3 reproduction: arm-B CAGR on the 145-subset within 1pp of 0.29644.
- **G5** coverage honesty: legs 1–2 report per-month member counts, marked-member
  counts, and the marked share; if the marked share ever falls below 80% the month is
  flagged in results.json (no month is dropped — the flag is the disclosure).

## Decision rule

None (reporting). The verdict.md records: (a) the table, (b) the gap BREADTH-B −
EW-ELIGIBLE on each window, (c) the honest reading — if the gap is small relative to
the B−index gap, the program's edge claim against a CAP-WEIGHTED index was the wrong
denominator, and the prospective design (registered the same day) is judged against
EW-ELIGIBLE going forward, not against the TRI.
