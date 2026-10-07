"""Design scorer for `breadth_book` (docs/prospective/breadth_book/design.md).

The deployable breadth book judged against its own universe, forward-only. Per virgin
fold: the book is the top DECILE (E018's round(10%) definition) of the shipped
composite's scored cross-section, equal weight; its fold return is the mean label of
its members net of one real-cost round trip (0.21%, LEDGER 2026-09-27). The benchmark
is the equal-weight mean label of the whole scored cross-section, GROSS (a benchmark,
like the index). The judged quantity is book_return_net − bench_ew_gross, recorded per
fold through the score.py fold_metrics hook.

score_month returns the shipped composite_2f and score_month_reference returns the
same — so folds.csv's ic − ref_ic is an identity check: it must be 0.000000 every
fold; anything else means the registered scorer drifted from the shipped signal.
"""
from __future__ import annotations

import csv
import math
import os
import statistics
import sys

from src.model import composite as model

COST_RT_REAL = 0.0021          # LEDGER 2026-09-27 real-cost round trip
DECILE = 0.10                  # E018's book-width definition

MIN_SCORED = 100               # G3: a fold below this is valid = FALSE
MIN_BOOK = 20                  # G3b: the decile must be a book, not a list

# the frozen bar (design.md §4), codified for the dashboard/verdict: the JUDGED
# quantity is book-level (fold_metrics columns), not the IC difference — the IC
# columns carry the identity check instead (ic == ref_ic every fold).
BAR_MONTHLY = 0.005            # mean monthly (book_net − bench) required, in returns
N_FOLDS = 12                   # valid virgin folds before the verdict may be written
EARLY_STOP_N = 6               # early stop (fail direction only) after this many
EARLY_STOP_DIFF = -0.005       # ...when the mean diff is this negative


def _book_stats(scores: list[float | None], rs) -> dict:
    """The fold's book-level record, pure in (scores, rows) so the self-check can drive
    it by hand. book = top decile by (-score, symbol) — E018's tie-break; benchmark =
    EW mean label over scored rows (== folds.csv's mean_label column)."""
    sym_at = 2 + len(model.PANEL_FEATURES) + 1
    scored = [(s, i) for i, s in enumerate(scores) if s is not None]
    k = max(1, round(len(scored) * DECILE))
    top = sorted(scored, key=lambda p: (-p[0], rs[p[1]][sym_at]))[:k]
    book_labels = [rs[i][1] for _s, i in top]
    bench_labels = [rs[i][1] for _s, i in scored if rs[i][1] is not None]
    gross = sum(book_labels) / len(book_labels)
    return {"book_return_gross": gross,
            "book_return_net": gross - COST_RT_REAL,
            "bench_ew_gross": sum(bench_labels) / len(bench_labels),
            "n_book": k, "n_scored": len(scored)}


def fold_metrics(rs) -> dict:
    """The hook score.py consumes: the fold's book construction, appended as extra
    folds.csv columns. G3b fires here (the book must be a book, not a list)."""
    stats = _book_stats(model.score_month_2f(rs), rs)
    assert stats["n_scored"] >= 2 * MIN_BOOK and stats["n_book"] >= MIN_BOOK, stats
    return stats


def score_month(rs) -> list[float | None]:
    """The shipped composite_2f — the deployed book's selector, unchanged."""
    return model.score_month_2f(rs)


def score_month_reference(rs) -> list[float | None]:
    """The same shipped composite: ic − ref_ic is the per-fold identity check (G1)."""
    return model.score_month_2f(rs)


def verdict() -> int:
    """Read folds.csv, apply the frozen bar, print where the design stands. Refuses to
    write a verdict before N_FOLDS valid folds (fail-direction early stop excepted)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "runs", "prospective", "breadth_book", "folds.csv")
    if not os.path.exists(path):
        print("breadth_book: no folds yet (registered; first virgin fold is the first "
              "labeled month after the 2026-10 freeze)")
        return 0
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    valid = [r for r in rows if r.get("valid", "1") == "1"]
    diffs = [float(r["book_return_net"]) - float(r["bench_ew_gross"]) for r in valid]
    ident = [float(r["ic"]) - float(r["ref_ic"]) for r in valid]
    assert all(abs(d) < 1e-9 for d in ident), \
        "G1 identity broken: the registered scorer drifted from the shipped composite"
    mean = statistics.mean(diffs) if diffs else float("nan")
    t = None
    if len(diffs) >= 2 and statistics.stdev(diffs) > 0:
        t = mean / (statistics.stdev(diffs) / math.sqrt(len(diffs)))
    print(f"breadth_book: {len(valid)}/{len(rows)} valid folds; mean monthly "
          f"(book_net − bench) {mean:+.4f} (bar +{BAR_MONTHLY:.4f} over n={N_FOLDS})"
          + (f", t {t:+.2f}" if t is not None else ""))
    if len(valid) >= EARLY_STOP_N and mean <= EARLY_STOP_DIFF:
        print("VERDICT: FAIL (early stop, fail direction — the book underperforms its "
              "own universe net of costs)")
    elif len(valid) >= N_FOLDS:
        print(f"VERDICT: {'PASS' if mean >= BAR_MONTHLY else 'FAIL'} at n={len(valid)} "
              "(write to runs/prospective/breadth_book/verdict.md + a LEDGER row)")
    else:
        print(f"not decidable: {N_FOLDS - len(valid)} valid folds to go "
              f"(early stop from n={EARLY_STOP_N} in the fail direction only)")
    return 0


def self_check() -> int:
    """Hand-computed folds: the decile arithmetic, net-of-cost, benchmark mean, and the
    E018 tie-break (a tie split across the cut must take the alphabetically-first
    symbol) are the code under test."""
    sym_at = 2 + len(model.PANEL_FEATURES) + 1

    def row(sym, label):
        r = [None] * (sym_at + 1)
        r[1], r[sym_at] = label, sym
        return tuple(r)

    # main fold: 40 scored rows, decile = 4; the book's labels are known exactly
    syms = [f"TOP{i}" for i in range(4)] + [f"FILL{i:02d}" for i in range(36)]
    top_labels = [0.10, 0.02, -0.03, 0.05]
    scores = [0.9] * 4 + [0.1] * 36
    rs = [row(s, top_labels[i] if i < 4 else 0.01) for i, s in enumerate(syms)]
    st = _book_stats(scores, rs)
    assert st["n_scored"] == 40 and st["n_book"] == 4, st
    assert abs(st["book_return_gross"] - 0.035) < 1e-12, st          # (0.10+0.02-0.03+0.05)/4
    assert abs(st["book_return_net"] - (0.035 - COST_RT_REAL)) < 1e-12, st
    assert abs(st["bench_ew_gross"] - 0.0125) < 1e-12, st            # (0.14 + 36*0.01)/40
    # tie-break: a tie split across the cut — slot 4 goes to ATIE, not ZTIE
    tie_scores = [0.95, 0.94, 0.93, 0.9, 0.9] + [0.0] * 35
    tie_rs = [row("AAA", 0.30), row("BBB", 0.20), row("CCC", -0.10),
              row("ATIE", 0.10), row("ZTIE", 0.90)] + \
             [row(f"F{i:02d}", 0.0) for i in range(35)]
    tie = _book_stats(tie_scores, tie_rs)
    assert tie["n_book"] == 4, tie
    assert abs(tie["book_return_gross"] - 0.125) < 1e-12, tie        # ZTIE's 0.90 excluded
    print("PASS: breadth_book self-check (decile arithmetic, net-of-cost, benchmark "
          "mean, E018 tie-break)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(self_check() if "--self-check" in sys.argv else verdict())
