"""The shipped Phase 4 model — composite_2f, extracted from experiments (fixissues 3.1).

The v0 model (P4.1b's `composite_2f`: mean cross-sectional percentile rank of
mom_12m_1m + delivery_pct) had lived in `experiments/004b_composite_2feat/run.py` with
production imports reaching it through `importlib` — smoke_e2e and audit pinned a file in
the experiments tree as a load-bearing dependency. This module is the extraction: the
experiments stay frozen exactly as they ran (P4.1b's frozen `results.json` is the verdict's
evidence, BRD §12/§13 — editing them would orphan every committed artifact), and production
imports THIS.

Extraction contract, verified in the self-check below: for a month's rows, the scores from
this module and from the frozen P4.1b `score_month_2f` are **bit-identical** (==, not
approx) — same `_pct` math (average ranks / (n-1), NaN preserved), same NaN semantics (a
row with no non-NaN feature scores None). P4.2's freeze protocol already proved the score
is deterministic; this pins the same bar for the move.

`python -m src.model.composite` runs the check: a hand-built month asserts hand-computed
scores and the two-implementation equality (P41b via importlib, this module directly).
"""
from __future__ import annotations

import math
import sys

from src.features.panel import _FEATURES as PANEL_FEATURES

FEATURES = ("mom_12m_1m", "delivery_pct")   # the composite's inputs, in P4.1b's order


def _pct(vals):
    """Cross-sectional percentile ranks (average ranks / (n-1)); None/NaN rows stay None.

    Same construction as P4.1's `_pct` (the experiments' shared building block)."""
    from src.stats import ranks
    n = len(vals)
    r = ranks(list(vals))
    return [None if v is None or (isinstance(v, float) and math.isnan(v)) else (r[i] - 1) / (n - 1)
            if n > 1 else None for i, v in enumerate(vals)]


def score_month(rows, feature_at):
    """Composite_2f scores for one month's rows — bit-identical to P4.1b's score_month_2f.

    `rows` are this month's records in any order; `feature_at(name, row)` returns the
    feature value (None/NaN when missing). A row with no non-NaN composite feature scores
    None (P4.1's NaN contract); the mean is over the features present, so a row with only
    one of the two features still scores.
    """
    pcts = {name: _pct([feature_at(name, r) for r in rows]) for name in FEATURES}
    scores = []
    for i in range(len(rows)):
        got = [pcts[f][i] for f in FEATURES if pcts[f][i] is not None]
        scores.append(sum(got) / len(got) if got else None)
    return scores


def score_month_2f(rs):
    """The smoke/audit adapter: scores over the feature_matrix row tuples, where columns
    are (mdate, next_month_ret, ...22 features..., liquidity_rank, symbol, size_bucket) —
    the layout every P4.x experiment scored. The 22-feature order is the feature panel's
    column order (matrix.py writes `SELECT p.*` from feature_panel), so the mapping comes
    from `PANEL_FEATURES` — production-owned, not re-copied here. Returns None per row
    exactly like P41B."""
    fi = {name: 2 + i for i, name in enumerate(PANEL_FEATURES)}
    return score_month(rs, lambda name, r: r[fi[name]])


def _self_check() -> None:
    # hand month: 5 rows; delivery_pct has a None hole and a NaN hole
    rows = [
        (0, 0.30), (1, 0.10), (2, 0.20), (3, None), (4, 0.40),
    ]
    vals = {"mom_12m_1m": [0.10, 0.40, 0.20, 0.30, 0.50],
            "delivery_pct": [50.0, 60.0, None, 70.0, float("nan")]}
    scores = score_month(rows, lambda name, r: vals[name][r[0]])
    # pct = (avg rank - 1) / (n - 1) over the FULL month's rows (NaN keeps NaN, holes stay
    # None; no renormalization over the scored subset — P4.1's construction):
    #   mom_12m_1m [0.10,.20,.30,.40,.50] -> pct 0, .25, .5, .75, 1
    #   delivery_pct [50,60,·,70,·]       -> pct 0, .25, None, .5, None
    # row0 (0+0)/2=0.0  row1 (.75+.25)/2=.5  row2 (mom .25 only)=.25
    # row3 (.5+.5)/2=.5  row4 (mom 1 only)=1.0
    want = [0.0, 0.5, 0.25, 0.5, 1.0]
    for got, w, r in zip(scores, want, rows):
        assert got is not None and abs(got - w) < 1e-12, (r, got, w)

    # the extraction contract: bit-identical to the frozen P4.1b implementation
    # (feature_matrix layout: (mdate, ret, 22 features..., rank, symbol, bucket)); the
    # scatter's column map is derived from P41B's own FEATURES, not hand-copied
    m41b = importlib.import_module("experiments.004b_composite_2feat.run")
    assert PANEL_FEATURES == m41b.FEATURES, \
        "panel feature order drifted from the frozen experiment order — score_month_2f's " \
        "column map is stale"
    fi = {name: 2 + i for i, name in enumerate(m41b.FEATURES)
          if name in FEATURES}
    rs = [(f"2026-0{m}", None, *[None] * 22, 1, f"S{j:03d}", "top200")
          for m in range(1, 10) for j in range(12)]
    for j, r in enumerate(rs):                     # scatter real values, ties, NaN holes
        r = list(r)
        r[fi["mom_12m_1m"]] = [0.05, 0.10, 0.10, None, 0.30][j % 5]
        r[fi["delivery_pct"]] = [40.0, float("nan"), 60.0, 60.0, None][j % 5]
        rs[j] = tuple(r)
    mine, theirs = score_month_2f(rs), m41b.score_month_2f(rs)
    assert mine == theirs, "extracted composite_2f is not bit-identical to the frozen P41b"
    assert any(s is not None for s in mine), "the scatter scored nothing — fixture is broken"

    print("PASS: src.model.composite (hand-computed scores; bit-identical to the frozen "
          "P4.1b composite_2f)")
    sys.exit(0)


if __name__ == "__main__":
    import importlib
    _self_check()
