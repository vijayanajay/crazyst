"""E001 — anatomy of winners: feature distributions, winners vs rest (run only after
hypothesis.md was written).

For every feature on the labeled feature_matrix: winners (is_winner, top 5% forward return)
vs the eligible rest — median shift in feature units, tie-safe AUC = P(winner > rest) from
pooled average ranks (the scale-free separation measure), normal-approximation p on the
rank-sum statistic, Benjamini–Hochberg across all features at α = 0.05, and per-month sign
consistency (share of decision months whose own median shift carries the pre-registered
sign). Headline features are also split per regime (month's realized cross-sectional mean
return up/down) and per as-of size bucket — the size-bucket split is the pre-registered
small-cap-artifact check on E002's volatility finding.

Usage:
    python -m experiments.001_anatomy.run            # profile quick
    python -m experiments.001_anatomy.run --profile full

Writes results.json (config snapshot, git hash, data cutoff — BRD §13) and prints the table.
Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the run completed.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.stats import bh_rejects, ranks

ALPHA = 0.05
FEATURES = ("mom_1m", "mom_3m", "mom_6m", "mom_12m_1m",
            "volume_zscore", "up_volume_20d", "down_volume_20d", "up_down_volume_ratio",
            "breakout_volume_confirmed", "delivery_pct", "delivery_pct_zscore",
            "delivery_pct_trend", "delivery_spike_while_flat",
            "atr_ratio", "nr7", "squeeze_days_20d", "range_compression_20d",
            "close_in_range", "upper_wick_ratio", "lower_wick_ratio",
            "consec_higher_lows", "big_body_day_in_trend")
DIRECTIONS = {                       # pre-registered in hypothesis.md (+1/-1/0); may not change
    "mom_1m": -1, "mom_3m": -1, "mom_6m": +1, "mom_12m_1m": +1,
    "volume_zscore": 0, "up_volume_20d": 0, "down_volume_20d": 0,
    "up_down_volume_ratio": +1, "breakout_volume_confirmed": +1,
    "delivery_pct": +1, "delivery_pct_zscore": +1, "delivery_pct_trend": +1,
    "delivery_spike_while_flat": +1,
    "atr_ratio": -1, "nr7": 0, "squeeze_days_20d": +1, "range_compression_20d": -1,
    "close_in_range": +1, "upper_wick_ratio": -1, "lower_wick_ratio": +1,
    "consec_higher_lows": +1, "big_body_day_in_trend": +1,
}
PRIMARY = ("mom_12m_1m", "delivery_pct_zscore")     # the ledger E001 row's two features
REGIME_FEATURES = ("mom_12m_1m", "delivery_pct_zscore", "mom_6m",
                   "atr_ratio", "squeeze_days_20d", "volume_zscore")


def _fetch(con):
    cols = "mdate, symbol, is_winner, size_bucket, " + ", ".join(FEATURES)
    rows = con.execute(f"SELECT {cols} FROM feature_matrix WHERE is_winner IS NOT NULL"
                       ).fetchall()
    months = con.execute("SELECT count(DISTINCT mdate) FROM feature_matrix "
                         "WHERE is_winner IS NOT NULL").fetchone()[0]
    return rows, months


def _auc_p(win_vals, rest_vals):
    """Tie-safe AUC = P(winner > rest) via pooled average ranks, plus its normal p.

    rank-sum identity: sum of winner average-ranks R_w over n_w winners gives
    U = R_w - n_w(n_w+1)/2, AUC = U / (n_w * n_r). The normal approximation uses the
    tie-corrected variance of U.
    """
    n_w, n_r = len(win_vals), len(rest_vals)
    if n_w < 5 or n_r < 5:
        return None, None
    r = ranks(list(win_vals) + list(rest_vals))
    r_w = r[:n_w]
    ties = {}
    for v in list(win_vals) + list(rest_vals):
        key = None if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, 12)
        ties[key] = ties.get(key, 0) + 1
    n = n_w + n_r
    tie_term = sum(t ** 3 - t for t in ties.values()) / (n * (n - 1))
    var_u = n_w * n_r / 12.0 * ((n + 1) - tie_term)
    r_sum = sum(x for x in r_w if not (isinstance(x, float) and math.isnan(x)))
    u = r_sum - n_w * (n_w + 1) / 2.0
    auc = u / (n_w * n_r)
    z = (u - n_w * n_r / 2.0) / math.sqrt(var_u) if var_u > 0 else 0.0
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return auc, p


def _shift(win_vals, rest_vals):
    """Median shift in the feature's own units; None when either side is empty.

    ponytail: no MAD-scaled variant — these features carry point masses (exact 0 trends,
    boolean flags) whose MAD is 0-or-noise, so a scale-free shift divides by garbage. AUC is
    the scale-free separation measure here; if a units-free shift is ever needed, do it on
    within-month ranks, not raw values.
    """
    if not win_vals or not rest_vals:
        return None
    w, r = sorted(win_vals), sorted(rest_vals)
    med = lambda xs: xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
    return med(w) - med(r)


def _analyze(rows):
    """Per feature: winners-vs-rest stats pooled, per month (sign consistency), per regime
    (month's cross-sectional mean return up/down) and per size bucket."""
    by_month = {}
    for row in rows:
        d = str(row[0])
        by_month.setdefault(d, []).append(row)
    month_ret = {d: sum(r[3 + len(FEATURES)] for r in rs if r[3 + len(FEATURES)] is not None)
                 / max(1, sum(1 for r in rs if r[3 + len(FEATURES)] is not None))
                 for d, rs in by_month.items()}
    out = {}
    for fi, name in enumerate(FEATURES):
        col = 4 + fi
        win = [row[col] for row in rows if row[2] and row[col] is not None
               and not (isinstance(row[col], float) and math.isnan(row[col]))]
        rest = [row[col] for row in rows if row[2] is False and row[col] is not None
                and not (isinstance(row[col], float) and math.isnan(row[col]))]
        auc, p = _auc_p(win, rest)
        shift = _shift(win, rest)
        # per-month sign consistency on the median shift
        signs = []
        for d, rs in sorted(by_month.items()):
            wv = [r[col] for r in rs if r[2] and r[col] is not None]
            rv = [r[col] for r in rs if r[2] is False and r[col] is not None]
            s, = _shift(wv, rv),
            if s is not None:
                signs.append((s > 0) - (s < 0))
        sgn = DIRECTIONS[name]
        agree = (sum(1 for s in signs if s == sgn) / len(signs)) if (sgn and signs) else None
        # regime + size-bucket splits (headline features only; descriptive)
        regime, buckets = {}, {}
        if name in REGIME_FEATURES:
            up = [r for r in rows if month_ret[str(r[0])] > 0]
            dn = [r for r in rows if month_ret[str(r[0])] <= 0]
            for label, sub in (("up", up), ("down", dn)):
                wv = [r[col] for r in sub if r[2] and r[col] is not None]
                rv = [r[col] for r in sub if r[2] is False and r[col] is not None]
                a, _ = _auc_p(wv, rv)
                regime[label] = {"auc": a, "shift": _shift(wv, rv),
                                 "months": len({str(r[0]) for r in sub})}
        if name in REGIME_FEATURES:
            for b in sorted({str(r[3]) for r in rows}):
                sub = [r for r in rows if str(r[3]) == b]
                wv = [r[col] for r in sub if r[2] and r[col] is not None]
                rv = [r[col] for r in sub if r[2] is False and r[col] is not None]
                a, _ = _auc_p(wv, rv)
                buckets[b] = {"auc": a, "shift": _shift(wv, rv), "n": len(sub)}
        out[name] = {"direction": sgn, "n_winners": len(win), "n_rest": len(rest),
                     "median_shift": shift,
                     "auc": auc, "p": p,
                     "months_with_shift": len(signs),
                     "sign_consistency": agree,
                     "regime": regime or None, "size_buckets": buckets or None}
    return out


def _bh_flags(results):
    pvals = [results[m]["p"] for m in FEATURES]
    flags = bh_rejects(pvals, ALPHA)
    return {m: (i in flags) for i, m in enumerate(FEATURES)}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="quick")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, months = _fetch(con)
        cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    finally:
        con.close()
    assert rows and months > 0, "no labeled rows — build feature_matrix first"

    results = _analyze(rows)
    flags = _bh_flags(results)
    winners = sum(1 for r in rows if r[2])

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "E001", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "random_seed": cfg["backtest"]["random_seed"], "alpha": ALPHA,
        "decision_months": months, "labeled_rows": len(rows), "winners": winners,
        "runtime_seconds": round(time.monotonic() - t0, 3),
        "features": results,
        "bh_rejects": [m for m in FEATURES if flags[m]],
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"E001 anatomy: {len(FEATURES)} features x {months} decision months, "
          f"{len(rows):,} labeled rows ({winners:,} winners), cutoff {cutoff} — wrote {path}",
          flush=True)
    print(f"{'feature':<28}{'dir':>4}{'AUC':>8}{'p':>11}{'shift':>10}{'sign%':>7}{'BH':>4}{'n_w':>7}")
    for m in FEATURES:
        r = results[m]
        auc = f"{r['auc']:.3f}" if r["auc"] is not None else "—"
        p = f"{r['p']:.2e}" if r["p"] is not None else "—"
        sh = f"{r['median_shift']:+.4g}" if r["median_shift"] is not None else "—"
        sc = f"{r['sign_consistency']:.0%}" if r["sign_consistency"] is not None else "—"
        print(f"{m:<28}{r['direction']:>4}{auc:>8}{p:>11}{sh:>10}{sc:>7}"
              f"{'*' if flags[m] else '':>4}{r['n_winners']:>7,}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
