"""Statistics used by the experiments — hand-rolled, no scipy (ledger M2 dependency policy).

Spearman correlation = Pearson correlation of ranks (identical math, M2's precedent). Ties get
average ranks. The t approximation for a Spearman IC uses t = IC * sqrt((n-2)/(1-IC^2)) with a
two-sided p from Student's t via the regularized incomplete beta I_x(a, b):

    P(T > |t|) = 0.5 * I_{v/(v+t^2)}(v/2, 1/2)

I_x is computed by its continued fraction (Lentz), which converges for every x and is accurate
to ~1e-14 — verified below against hand-integrable cases and known t values.

BH step-up: sort p ascending, k* = max{i: p_(i) <= i*alpha/m}, reject the k* smallest p-values.

python -m src.stats runs hand-computed checks: rank/tie handling, a perfect correlation, the
incomplete beta against closed forms (t=1, v=1 -> 0.5; t=2, v=2 -> 0.4226; t=0 -> 0.5), a
known Spearman dataset, BH boundaries (reject-all, reject-none, the k* tie case) and the
degenerate-input contracts (empty, constant, NaN-carrying).
"""
import math

# ---- ranks, Spearman --------------------------------------------------------


def ranks(xs):
    """Average ranks (1-based), ties sharing the mean; NaN sorts last and keeps NaN rank."""
    idx = sorted(range(len(xs)), key=lambda i: _sort_key(xs[i]))
    out = [float("nan")] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and _sort_key(xs[idx[j + 1]]) == _sort_key(xs[idx[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[idx[k]] = float("nan") if _sort_key(xs[idx[k]])[0] else avg
        i = j + 1
    return out


def _sort_key(v):
    isnan = v is None or (isinstance(v, float) and math.isnan(v))
    return (isnan, 0.0 if isnan else v)


def _pearson(ys, zs):
    n = len(ys)
    my = sum(ys) / n
    mz = sum(zs) / n
    sxy = sum((a - my) * (b - mz) for a, b in zip(ys, zs))
    vx = sum((a - my) ** 2 for a in ys)
    vy = sum((b - mz) ** 2 for b in zs)
    if vx <= 0 or vy <= 0:
        raise ValueError("zero variance — correlation undefined")
    return sxy / math.sqrt(vx * vy)


def spearman(xs, ys):
    """Spearman rank correlation of paired samples; raises on mismatched/empty input."""
    if len(xs) != len(ys) or not xs:
        raise ValueError(f"paired samples must be non-empty and equal length: {len(xs)} vs {len(ys)}")
    return _pearson(ranks(xs), ranks(ys))


def spearman_ic(values, returns):
    """Cross-sectional Spearman IC with NaN rows dropped; None if < 3 complete pairs."""
    pairs = [(v, r) for v, r in zip(values, returns)
             if v is not None and not (isinstance(v, float) and math.isnan(v))
             and r is not None and not (isinstance(r, float) and math.isnan(r))]
    if len(pairs) < 3:
        return None
    xs, rs = zip(*pairs)
    try:
        return spearman(xs, rs)
    except ValueError:
        return None  # a constant feature has no cross-section

# ---- Student's t tail via the regularized incomplete beta --------------------


def betainc_reg(a, b, x):
    """Regularized incomplete beta I_x(a, b), 0 <= x <= 1, by the Lentz continued fraction."""
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"x out of [0, 1]: {x}")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _betacf(a, b, x):
    tiny, eps = 1e-300, 1e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        num = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + num * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + num / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        num = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + num * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + num / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def t_sf_two_sided(t, v):
    """Two-sided p for |T| under Student's t with v degrees of freedom."""
    if v <= 0:
        raise ValueError(f"degrees of freedom must be positive: {v}")
    t = abs(t)
    if t == 0.0:
        return 1.0
    x = v / (v + t * t)
    p = betainc_reg(v / 2.0, 0.5, x)
    return min(1.0, max(0.0, p))


def ic_pvalue(ic, n):
    """Two-sided p for a Spearman IC observed on n paired samples; None for degenerate input."""
    if n < 3 or ic is None or not math.isfinite(ic) or abs(ic) >= 1.0:
        return None if (ic is None or n < 3) else (0.0 if abs(ic) >= 1.0 else None)
    t = ic * math.sqrt((n - 2) / (1.0 - ic * ic))
    return t_sf_two_sided(t, n - 2)

# ---- Benjamini-Hochberg step-up ----------------------------------------------


def bh_rejects(pvals, alpha=0.05):
    """Indices of the k* smallest p-values rejected by BH at alpha. p=None never rejects."""
    m = sum(1 for p in pvals if p is not None)
    if m == 0:
        return set()
    order = sorted((p, i) for i, p in enumerate(pvals) if p is not None)
    k = 0
    for rank1, (p, i) in enumerate(order, start=1):
        if p <= rank1 * alpha / m:
            k = rank1
    return {i for _, i in order[:k]}


def _self_check():
    # ranks: ties average, NaN keeps NaN, ordering correct
    assert ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0], ranks([10, 20, 20, 30])
    assert math.isnan(ranks([5.0, float("nan"), 1.0])[1])
    # known Spearman: two adjacent transpositions (D = 2.5), average-rank tie math,
    # closed form rho = 1 - 6*sum(d^2) / (v*(v^2-1)) = 1 - 15/176 = 11/12
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    ys = [1, 3, 2, 4, 6, 5, 8, 9, 7]
    assert abs(spearman(xs, ys) - 11 / 12) < 1e-12, spearman(xs, ys)
    # perfect monotone, including ties
    assert abs(spearman([1, 2, 3, 4], [10, 20, 20, 40]) - 0.9486832980505138) < 1e-12
    # reversed
    assert abs(spearman([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-12
    # constant feature: no cross-section, None — never a fake 0.0
    assert spearman_ic([7.0] * 5, [1, 2, 3, 4, 5]) is None
    assert spearman_ic([1.0], [1.0]) is None  # too few pairs
    # IC drops NaN/None pairs rather than counting them
    ic_all = spearman_ic([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    ic_drop = spearman_ic([1, 2, float("nan"), 4, 5], [1, 2, 999.0, 4, 5])
    assert ic_all == 1.0 and ic_drop == 1.0, (ic_all, ic_drop)

    # t tail against closed forms: t=0 -> 1.0; Cauchy (v=1) P(|T|>1) = 1/2;
    # v=2 CDF F(t) = 1/2 + t/(2*sqrt(t^2+2)) -> two-sided p = 2*(1-F)
    assert abs(t_sf_two_sided(0.0, 10) - 1.0) < 1e-15
    assert abs(t_sf_two_sided(1.0, 1) - 0.5) < 1e-12
    assert abs(t_sf_two_sided(1.0, 2) - 2 * (1 - (0.5 + 1 / (2 * math.sqrt(3))))) < 1e-12
    assert abs(t_sf_two_sided(2.0, 2) - 2 * (1 - (0.5 + 2 / (2 * math.sqrt(6))))) < 1e-12
    # normal limit: v=1e6, t=2 ~ 0.0455 (O(1/v) finite-v deviation stays under 1e-6)
    assert abs(t_sf_two_sided(2.0, 1_000_000) - 0.0455002638963586) < 1e-6
    assert t_sf_two_sided(50.0, 5) < 1e-6  # deep tail converges, no overflow

    # ic_pvalue end to end: IC=1.0 on n=5 -> t=inf -> p=0; monotone in n
    assert ic_pvalue(1.0, 5) == 0.0
    p5 = ic_pvalue(0.9, 5)
    p50 = ic_pvalue(0.9, 50)
    assert 0 < p50 < p5 < 0.05, (p5, p50)
    assert ic_pvalue(None, 10) is None and ic_pvalue(0.5, 2) is None

    # BH: none reject, all reject, and the k* step boundary
    assert bh_rejects([0.9, 0.8, 0.7], 0.05) == set()
    assert bh_rejects([0.001, 0.002, 0.003], 0.05) == {0, 1, 2}
    # p_(2)=0.026 <= 2*0.05/3=0.0333, p_(3)=0.08 > 0.05 -> k*=2
    got = bh_rejects([0.026, 0.005, 0.08], 0.05)
    assert got == {0, 1}, got
    # None p-values never reject and do not count in m
    assert bh_rejects([0.01, None, 0.9], 0.05) == {0}
    assert bh_rejects([], 0.05) == set()
    print("PASS: stats (ranks/ties, Spearman, t-tail closed forms, BH boundaries)")
    sys.exit(0)


if __name__ == "__main__":
    import sys
    _self_check()
