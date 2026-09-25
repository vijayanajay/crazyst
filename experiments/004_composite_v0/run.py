"""P4.1 — composite v0 vs best single feature on the pre-test-window validation slice
(run only after hypothesis.md was written).

Arms (all parameter-free; hypothesis.md fixes them):
  composite              mean of cross-sectional percentile ranks of mom_12m_1m, mom_6m,
                         delivery_pct (NaN rows stay NaN, need >= 1 non-NaN feature)
  composite_atr_overlay  composite + sign(mkt_trail_1m) * pct(atr_ratio), where
                         mkt_trail_1m = cross-sectional mean of mom_1m at the decision date
  best_single            the single feature with the highest mean monthly IC ON THE SLICE
                         (selected in-sample on purpose — winner's curse makes it the
                         conservative comparator)

Primary metric: mean monthly Spearman IC on the validation slice, arms compared paired by
month (one-sample t on monthly IC differences). The test window (last 36 months, BRD 10.1)
is excluded and not touched.

Usage:
    python -m experiments.004_composite_v0.run --profile full

Writes results.json (config snapshot, git hash, cutoff — BRD 13) and prints the table.
Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the run completed.
"""
import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import date, timedelta

import duckdb

from src.config import load
from src.stats import spearman_ic, t_sf_two_sided

E002 = importlib.import_module("experiments.002_ic_sweep.run")   # frozen: the 22 features
FEATURES = E002.FEATURES
COMPOSITE_FEATURES = ("mom_12m_1m", "mom_6m", "delivery_pct")    # E002b survivors
ATR_FEATURE = "atr_ratio"
REGIME_PROXY = "mom_1m"                                          # trailing market 1M return
ALPHA = 0.05
TEST_WINDOW_MONTHS = 36                                          # BRD 10.1


def _fetch(con):
    rows = con.execute(
        "SELECT mdate, next_month_ret, " + ", ".join(FEATURES) +
        " FROM feature_matrix WHERE next_month_ret IS NOT NULL ORDER BY mdate").fetchall()
    cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    return rows, cutoff


def split_slice(rows, cutoff):
    """Validation slice = labeled months whose LABEL END (next decision date) predates the
    test window's start (cutoff minus exactly 36 months). Label end of month M is the next
    decision date after M; a month whose label end is unknown (the last month) belongs to
    neither slice."""
    months = sorted({str(r[0]) for r in rows})
    nxt = {m: (date.fromisoformat(months[i + 1]) if i + 1 < len(months) else None)
           for i, m in enumerate(months)}
    c = date.fromisoformat(str(cutoff))
    m_index = c.year * 12 + (c.month - 1) - TEST_WINDOW_MONTHS
    boundary = date(m_index // 12, m_index % 12 + 1, 1) + timedelta(
        days=min((date(m_index // 12, m_index % 12 + 2, 1) - date(m_index // 12, m_index % 12 + 1, 1)).days,
                 c.day) - 1)
    val, test = [], []
    for r in rows:
        end = nxt[str(r[0])]
        if end is None:
            continue
        (test if end > boundary else val).append(r)
    return val, test, boundary


def _pct(vals):
    """Cross-sectional percentile ranks (average ranks / n), NaN preserved."""
    n = len(vals)
    from src.stats import ranks
    r = ranks(list(vals))
    return [None if v is None or (isinstance(v, float) and math.isnan(v)) else (r[i] - 1) / (n - 1)
            if n > 1 else None for i, v in enumerate(vals)]


def score_month(rs):
    """Scores for the three arms on one month's rows. Returns (composite, overlay) lists;
    rows with no non-NaN composite feature get None in both."""
    fi = {name: 2 + i for i, name in enumerate(FEATURES)}   # column index in the row tuple
    pcts = {name: _pct([r[fi[name]] for r in rs]) for name in set(COMPOSITE_FEATURES) | {ATR_FEATURE}}
    mkt = None
    mvals = [r[fi[REGIME_PROXY]] for r in rs if r[fi[REGIME_PROXY]] is not None
             and not (isinstance(r[fi[REGIME_PROXY]], float) and math.isnan(r[fi[REGIME_PROXY]]))]
    if mvals:
        mkt = sum(mvals) / len(mvals)
    comp, over = [], []
    for i, r in enumerate(rs):
        got = [pcts[f][i] for f in COMPOSITE_FEATURES if pcts[f][i] is not None]
        c = sum(got) / len(got) if got else None
        comp.append(c)
        o = None
        if c is not None and pcts[ATR_FEATURE][i] is not None and mkt is not None:
            o = c + (1.0 if mkt >= 0 else -1.0) * pcts[ATR_FEATURE][i]
        over.append(o)
    return comp, over


def _monthly_ics(rows):
    """{arm: [(month, ic)]} for composite / overlay / each single feature."""
    by_month = {}
    for r in rows:
        by_month.setdefault(str(r[0]), []).append(r)
    fi = {name: 2 + i for i, name in enumerate(FEATURES)}
    out = {"composite": [], "composite_atr_overlay": []}
    for name in FEATURES:
        out[name] = []
    for m, rs in sorted(by_month.items()):
        comp, over = score_month(rs)
        rets = [r[1] for r in rs]
        for arm, scores in (("composite", comp), ("composite_atr_overlay", over)):
            pairs = [(s, ret) for s, ret in zip(scores, rets) if s is not None]
            ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
            out[arm].append((m, ic, len(pairs)))
        for name in FEATURES:
            pairs = [(r[fi[name]], r[1]) for r in rs if r[fi[name]] is not None
                     and not (isinstance(r[fi[name]], float) and math.isnan(r[fi[name]]))]
            ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
            out[name].append((m, ic, len(pairs)))
    return out


def _mean_ic(ics):
    vals = [ic for _, ic, _ in ics if ic is not None]
    return (sum(vals) / len(vals)) if vals else None, len(vals)


def _paired_t(a, b):
    """One-sample t on the month-paired IC differences (a - b), both aligned by month."""
    da = {m: ic for m, ic, _ in a if ic is not None}
    db = {m: ic for m, ic, _ in b if ic is not None}
    common = sorted(set(da) & set(db))
    diffs = [da[m] - db[m] for m in common]
    n = len(diffs)
    if n < 6:
        return None
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else 0.0
    t = mean / (sd / math.sqrt(n)) if sd > 0 else (0.0 if mean == 0 else math.copysign(1e9, mean))
    return {"n_months": n, "mean_diff": mean, "t": t, "p": t_sf_two_sided(t, n - 1)}


def _top5_precision(ics_by_month_rows, scores):
    """Mean over months of the top-5% hit rate for one arm's scores."""
    hits, ns = [], 0
    for m, rs in sorted(ics_by_month_rows.items()):
        scored = [(s, r[1]) for s, r in zip(scores[m], rs) if s is not None]
        if len(scored) < 20:
            continue
        k = max(1, round(len(scored) * 0.05))
        top = sorted(scored, key=lambda p: -p[0])[:k]
        hits.append(sum(1 for _, ret in top if ret > 0) / k)
        ns += 1
    return (sum(hits) / ns if ns else None), ns


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff = _fetch(con)
    finally:
        con.close()
    assert rows, "no labeled rows — build feature_matrix first"
    val, test, boundary = split_slice(rows, cutoff)
    assert val, "the validation slice must be non-empty"
    # every IC below is computed from `val` only — `test` is counted and excluded, never scored

    ics = _monthly_ics(val)
    means = {arm: _mean_ic(v) for arm, v in ics.items()}
    # comparator: highest mean monthly IC on the slice, selected FROM the slice
    singles = {name: means[name][0] for name in FEATURES if means[name][0] is not None}
    best_single = max(singles, key=singles.get)
    comparisons = {
        "composite_vs_best_single": _paired_t(ics["composite"], ics[best_single]),
        "overlay_vs_composite": _paired_t(ics["composite_atr_overlay"], ics["composite"]),
    }
    # secondary: pooled top-5% precision per arm on the slice
    by_month = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    prec = {}
    for arm, key in (("composite", "composite"), ("composite_atr_overlay", "composite_atr_overlay")):
        scores = {}
        for m, rs in by_month.items():
            comp, over = score_month(rs)
            scores[m] = comp if key == "composite" else over
        p, nm = _top5_precision(by_month, scores)
        prec[arm] = {"precision": p, "months": nm}
    bs_scores = {}
    fi = {name: 2 + i for i, name in enumerate(FEATURES)}
    for m, rs in by_month.items():
        bs_scores[m] = [r[fi[best_single]] for r in rs]
    p, nm = _top5_precision(by_month, bs_scores)
    prec["best_single"] = {"feature": best_single, "precision": p, "months": nm}

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "P4.1_composite_v0", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "validation_boundary": str(boundary),
        "validation_months": len({str(r[0]) for r in val}),
        "validation_rows": len(val),
        "excluded_test_months": len({str(r[0]) for r in test}),
        "composite_features": list(COMPOSITE_FEATURES),
        "universe_note": "as-of top-1500, floor OFF; BRD-owner decisions pending flag (docs/brd_decisions_universe.md)",
        "random_seed": cfg["backtest"]["random_seed"],
        "mean_monthly_ic": {k: {"ic": v[0], "months": v[1]} for k, v in means.items()},
        "best_single": best_single,
        "single_feature_slice_ics": singles,
        "paired_comparisons": comparisons,
        "top5_precision_slice": prec,
        "runtime_seconds": round(time.monotonic() - t0, 3),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"P4.1 composite v0: validation slice {out['validation_months']} months / "
          f"{out['validation_rows']:,} rows (boundary {boundary}), test window "
          f"({out['excluded_test_months']} labeled months) not scored — wrote {path}", flush=True)
    print(f"\n{'arm':<26}{'meanIC':>9}{'months':>8}{'top5prec':>10}")
    for arm in ("composite", "composite_atr_overlay", best_single):
        m = means[arm]
        pr = prec["best_single"].get("precision") if arm == best_single else prec.get(arm, {}).get("precision")
        print(f"{arm:<26}{m[0]:>9.4f}{m[1]:>8,}{pr * 100 if pr is not None else float('nan'):>9.1f}%")
    print(f"\nbest single (chosen ON the slice, winner's curse included): {best_single}")
    for name, c in comparisons.items():
        if c:
            print(f"{name}: mean monthly diff {c['mean_diff']:+.4f} over {c['n_months']} months, "
                  f"t = {c['t']:+.2f}, p = {c['p']:.4f}")
        else:
            print(f"{name}: not computable (< 6 shared months)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
