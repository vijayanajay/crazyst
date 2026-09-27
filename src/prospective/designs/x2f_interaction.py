"""Design scorer for `x2f_interaction` (docs/prospective/x2f_interaction/design.md).

score = pct(mom_12m_1m) * pct(delivery_pct) — the conjunctive aggregation of the shipped
pair, using the shipped `model._pct` rank math. A row with any None component scores None
(the conjunction's contract, stricter than the mean's; disclosed in the freeze).
"""
from __future__ import annotations

from src.model import composite as model
from src.features.panel import _FEATURES as PANEL_FEATURES

FEATURES = ("mom_12m_1m", "delivery_pct")
fi = {name: 2 + PANEL_FEATURES.index(name) for name in FEATURES}
MIN_SCORED = 100                                   # G3: a fold below this is valid = FALSE


def score_month(rs) -> list[float | None]:
    pcts = [model._pct([r[fi[name]] for r in rs]) for name in FEATURES]
    out = []
    for i in range(len(rs)):
        a, b = pcts[0][i], pcts[1][i]
        out.append(a * b if a is not None and b is not None else None)
    return out


def score_month_reference(rs) -> list[float | None]:
    """The shipped composite_2f, the paired reference stored in the same folds.csv row."""
    return model.score_month_2f(rs)
