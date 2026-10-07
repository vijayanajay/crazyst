# Design freeze — `breadth_book` (deployable breadth book vs its own equal-weight universe)

Copy of docs/prospective/TEMPLATE.md, frozen 2026-10-01 — **before any fold this design
will score exists** (the first scorable virgin fold is the first labeled month whose
decision month is after 2026-10, i.e. it closes with December 2026's data). Registered
in runs/prospective/designs.json with the SHA-256 of this file.

## 0. Why this is not a re-run of a closed family (protocol §5)

The breadth family's closure (E018 PASS / E019 deployable REJECTED / E020-C blend
NON-CONFIRMED) judged the book against the **cap-weighted Nifty 500 TRI on burnt
windows**. That question is closed and stays closed — nothing here re-runs it. E026
(same day, pre-registered) measured the denominator that was never computed: the
strategy's **own equal-weight universe** earned +16.84%/yr in-sample vs the index's
+13.17%, and the book's edge over THAT benchmark is +7.40 pp/yr (matched estimator) —
real in-sample, unproven forward. This design freezes the **new judgment standard**
(book vs own-universe EW, net of real costs, monthly folds) and asks it on virgin folds
only. It is a new claim about a new denominator, not a re-litigation of breadth-vs-TRI.

## 1. Family and claim — frozen

- Family: breadth-book-vs-own-universe (deployable decile book, forward-only).
- The claim, one sentence, directional: the deployable breadth book (top decile of
  composite_2f, equal weight, real costs) earns a **positive mean monthly active
  return over its own equal-weight universe benchmark**, net of costs, on virgin folds.
- Mechanism: composite_2f (mom_12m_1m + delivery_pct cross-sectional percentile mean)
  concentrates the cross-section's best forward months (in-sample IC 0.0720, E018
  decile book +29.64%/yr vs its universe's +22.25% matched-estimator / +16.84%
  rebalanced, E026). Whether that spread persists out-of-sample, fold by fold, is the
  open question E020-C's burnt window could not answer cleanly against the right
  benchmark.

## 2. Exact construction — frozen

- Feature inputs: the shipped composite_2f on the decision month's labeled matrix rows
  (as-of eligible, PIT by construction; the scorer reads nothing else).
- Scoring rule: `score_month` = `src.model.composite.score_month_2f` verbatim (the
  deployed selector, parameter-free).
- Book (per fold): top **decile** = `round(0.10 × n_scored)` rows ranked by
  `(-score, symbol)` — E018's `_decile_book` definition and tie-break; weights equal
  `1/k`. Fold return = mean label of the book's members (the label IS the fold month's
  realized forward return) **minus one real-cost round trip** `COST_RT_REAL = 0.0021`
  (LEDGER 2026-09-27). This is the 1-month-hold book; the 12-month cohort structure of
  E018 cannot be expressed in monthly folds and is not claimed here.
- Benchmark (per fold): equal-weight mean label over the whole **scored** cross-section
  (== folds.csv's `mean_label` column), **gross** — benchmarks are gross, like the
  index. Repeated explicitly in `fold_metrics` as `bench_ew_gross` for a self-describing
  record.
- NaN contract: rows with a `None` composite score are excluded from BOTH the book and
  the benchmark denominators (they are untradeable by the program's own convention,
  E018 G0). G3b additionally requires the decile to be a book (`n_book ≥ 20`).
- The registered scorer (module:function — importable by src.prospective.score):
  `src.prospective.designs.breadth_book:score_month`, plus the `fold_metrics` hook.
- **Runner amendment, disclosed before any fold exists:** `src/prospective/score.py`
  gained a generic optional `fold_metrics(rows) -> dict` hook (2026-10-01, pre-
  registration): designs that declare it get their items appended as extra folds.csv
  columns; designs without it (x2f_interaction) are byte-identical in behavior and
  schema. No fold has been scored by this design; nothing is re-scored.

## 3. Guards — frozen

- **G1 (identity/PIT):** `ic − ref_ic == 0.000000` every fold — the reference IS the
  same shipped composite, so any nonzero difference means the registered scorer
  drifted from the deployed signal (hard fail, checked by the verdict helper).
- **G2 (anchor, context only — not gating):** in-sample, 145 months: E018 arm C
  (decile-equal, 12-mo cohorts, real costs) +31.04% CAGR vs E026's EW-universe
  matched-estimator +22.25% (+8.8 pp/yr under DIFFERENT conventions — cohort arithmetic
  vs fold months; recorded for orientation, never compared as a bar).
- **G3 (coverage):** `MIN_SCORED = 100` scored rows per fold (else `valid = 0`) and
  `n_book ≥ 20` legs (the fold_metrics assert).

## 4. Bar and decision rule — frozen

- Bar: mean monthly `book_return_net − bench_ew_gross` ≥ **+0.005** (0.5 pp/month,
  ≈ +6.2%/yr compounded) over **n = 12** valid virgin folds. Units: monthly return
  fraction. (The protocol's own effect-size note puts the program's book excess at
  ~1 pp/mo gross; half of that, net of costs, against the correct denominator.)
- Minimum folds before the verdict may be written: **12** valid folds (expected ~13
  months of tape after freeze — first fold closes with December 2026's data).
- Early stop (fail direction only): after **≥ 6** valid folds, mean diff ≤ **−0.005**
  → call FAIL early. A pass always needs the full n.
- Verdict goes to `runs/prospective/breadth_book/verdict.md` + a LEDGER row, computed
  by `python -m src.prospective.designs.breadth_book` (which also enforces G1).
  A PASS licenses the next pre-registration; it does not ship anything.

## 5. Disclosure log (append-only)

| date | change | reason |
|---|---|---|
| 2026-10-01 | design frozen + registered; score.py `fold_metrics` hook added pre-registration | book-level designs need their construction in the append-only record; no fold existed, nothing re-scored (LEDGER block 2026-10-01) |
