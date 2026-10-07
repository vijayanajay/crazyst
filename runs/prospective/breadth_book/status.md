# breadth_book — first-virgin-fold status

**Status: not scorable yet.** No verdict, no ledger row. This checkpoint records why, and
the integrity checks that *did* pass.

## What the protocol requires

- First scorable virgin fold = first labeled month whose decision month is **after the
  2026-10 freeze** (registered 2026-10-02 00:40:45). Per
  [design.md](docs/prospective/breadth_book/design.md), that close carries **December 2026**
  data — i.e. decision month **2026-11-30**, labeled by 2026-12-31's winners row, available
  ~early January 2027. Decision month 2026-10-31 is inside the freeze month and is excluded
  by the `m[:7] > registered_at[:7]` rule.
- Verdict requires **12 valid virgin folds** (fail-direction early stop only after 6).

## Tape state (verified 2026-10-06)

- DuckDB cutoff: **2026-10-05**; `feature_matrix` spans 2025-09-30 → 2026-10-05.
- Labeled months: **12**, 2025-09-30 → 2026-08-31 (2026-09-30 and later are unlabeled —
  their labels live at the next decision date, which has not closed).
- No labeled month after the 2026-10 freeze → the first virgin fold does not exist yet.

```
$ python -m src.prospective.score --score breadth_book
breadth_book: no virgin fold yet (freeze 2026-10-02 00:40:45; nothing new to score)
[exit 0]
```

## CORRECTION — there is no schema mismatch

An earlier version of this note claimed the live `feature_matrix` column order did not match
the layout `score_month_2f` / `fold_metrics` expect. **That was wrong**, and was an artifact
of an ad-hoc diagnostic that read the table with `SELECT *` instead of going through the
scorer's own fetch path.

- The table's physical order is `mdate, symbol, <22 features>, next_month_ret, is_winner,
  liquidity_rank, size_bucket` — exactly what `src/features/matrix.build()`'s `_MATRIX_SQL`
  emits (`SELECT p.*, w.ret AS next_month_ret, ... FROM feature_panel p`). Nothing else
  builds this table.
- `harness._fetch` does **not** `SELECT *`; it names its columns explicitly
  (`SELECT mdate, next_month_ret, <features>, liquidity_rank, symbol, size_bucket`), which
  produces the 27-tuple the frozen scorer expects: label at index 1, symbol at
  `SAT = 2 + 22 + 1 = 25`.
- `src/prospective/score.py` calls `HARNESS._fetch`, so **the real entry point already gets
  the right layout regardless of physical column order.**

Verified end-to-end against the live DB through that exact path:

| check | result |
|---|---|
| `_fetch` tuple length / symbol at SAT=25 | 27 / `NAM-INDIA` ✓ |
| G1 identity on fold 2026-08-31 | `ic == ref_ic == 0.087856`, diff `0.000000000` ✓ |
| `fold_metrics` (the judged hook) | `n_scored 1338`, `n_book 134`, book_net − bench **+0.005196** ✓ |
| `python -m src.prospective.score --score breadth_book` | exit 0, "no virgin fold yet" ✓ |

So the scorer, both guards, and the `fold_metrics` hook all run cleanly on live data. No
build-path fix is needed for prospective scoring.

## State note: the derived chain is at the `quick` profile

`config.yaml` has `profile: quick` (start 2025-09-01), so the derived tables only span that
window — hence 12 labeled months rather than the full history. This is **not** a defect for
this design (it only needs months after the freeze, which accumulate forward), but it does
mean a full-profile harness run would trip its own `assert len(folds) >= 30` guard ("the
derived chain is probably at the quick profile; rebuild it").

Who extends `feature_matrix` forward, since the daily refresh does not touch it directly:

1. `src.download.refresh` rebuilds `panels → rank → eligibility → winners` each night.
2. That refresh's verify step runs `python -m src.selfcheck`, whose registry contains
   `features.panel` and `features.matrix`; both self-checks call `build()` at the config
   profile, so **the nightly refresh is what rebuilds `feature_panel` and `feature_matrix`**
   with the new decision months.
3. The suite is stamped, so this happens whenever data moved (which is exactly when new
   months exist).

## Integrity checks that passed

- `python -m src.prospective.designs.breadth_book --self-check` — PASS (decile arithmetic,
  net-of-cost, benchmark mean, E018 tie-break).
- `python -m src.prospective.score --self-check` — PASS (hand IC, top-5 pick, append-only
  record, header check).
- `runs/prospective/designs.json` sha256 pins match disk for both `design_md` and
  `code_path` — nothing drifted from the registration.

## Next step to actually score the first virgin fold

Wait for the decision month **2026-11-30** to close with December 2026 data (~early Jan
2027), let the nightly refresh extend the chain, then:

```
python -m src.prospective.score --score breadth_book
```

That is the honest first fold. The 12-fold bar must be met before any verdict.md or LEDGER
row is written; a single fold writes one `folds.csv` row and nothing else.

## Files

- Design freeze: [docs/prospective/breadth_book/design.md](docs/prospective/breadth_book/design.md)
- Scorer: [src/prospective/designs/breadth_book.py](src/prospective/designs/breadth_book.py)
- Registration: [runs/prospective/designs.json](runs/prospective/designs.json)
- Scoring machinery: [src/prospective/score.py](src/prospective/score.py)
- Ledger block (E026, the benchmark this design is judged against): [LEDGER.md](LEDGER.md)
