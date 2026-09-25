"""E002 — univariate IC sweep over feature_matrix (run only after hypothesis.md was written).

For every feature: per decision month, Spearman IC between the feature at the decision date and
the forward month return; pooled IC over all labeled rows; the t-approximation p-value on the
pooled IC; top-5% precision on the direction the hypothesis pre-registers (positive-direction
features take their top 5% by value, negative-direction by value ascending — precision is
P(forward return > 0 | top 5%)), and Benjamini–Hochberg across all features at α = 0.05.

Usage:
    python -m experiments.002_ic_sweep.run            # profile quick
    python -m experiments.002_ic_sweep.run --profile full

Writes results.json (config snapshot, git hash, data cutoff, seed — BRD §13) and prints the
table. Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the sweep ran.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.stats import bh_rejects, ic_pvalue, spearman_ic

ALPHA = 0.05
PRECISION_PCT = 0.05
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


def _fetch(con):
    months, rows = con.execute(
        "SELECT count(DISTINCT mdate), count(*) FROM feature_matrix "
        "WHERE next_month_ret IS NOT NULL").fetchone()
    data = {}
    for m in FEATURES:
        data[m] = con.execute(
            "SELECT mdate, " + m + ", next_month_ret FROM feature_matrix "
            "WHERE next_month_ret IS NOT NULL AND " + m + " IS NOT NULL ORDER BY mdate"
        ).fetchall()
    return months, rows, data


def _sweep(data):
    out = {}
    for m in FEATURES:
        rows = data[m]
        vals, rets = [r[1] for r in rows], [r[2] for r in rows]
        by_month = {}
        for d, v, r in rows:
            by_month.setdefault(d, ([], []))[0].append(v)
            by_month[d][1].append(r)
        monthly = [(str(d), spearman_ic(vs, rs), len(vs)) for d, (vs, rs) in sorted(by_month.items())]
        pooled = spearman_ic(vals, rets)
        n = len(rows)
        p = ic_pvalue(pooled, n)
        # top-5% precision: higher-is-better features rank descending, lower-is-better ascending,
        # directionless features ascending (pure "top slice" reading)
        sgn = DIRECTIONS[m] if DIRECTIONS[m] != 0 else 1
        order = sorted(range(n), key=lambda i: -sgn * vals[i])
        k = max(1, int(round(n * PRECISION_PCT)))
        top_ret = [rets[i] for i in order[:k]]
        hit = sum(1 for r in top_ret if r > 0)
        out[m] = {
            "direction": DIRECTIONS[m], "pooled_ic": pooled, "n": n, "p": p,
            "months_with_ic": sum(1 for _, ic, _ in monthly if ic is not None),
            "monthly_ic_mean": (sum(ic for _, ic, _ in monthly if ic is not None) /
                                max(1, sum(1 for _, ic, _ in monthly if ic is not None))),
            "precision": hit / k if hit else 0.0,
            "precision_k": k, "precision_hits": hit,
        }
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
        months, total_rows, data = _fetch(con)
        cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    finally:
        con.close()
    assert months > 0 and total_rows > 0, "no labeled rows — build feature_matrix first"

    results = _sweep(data)
    flags = _bh_flags(results)

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    surv = sum(1 for m in FEATURES if flags[m] and results[m]["pooled_ic"] is not None
               and results[m]["p"] == 0.0)
    survivors = [{"feature": m, "direction": DIRECTIONS[m],
                  "pooled_ic": results[m]["pooled_ic"], "p": results[m]["p"]}
                 for m in FEATURES if flags[m]]
    out = {
        "experiment": "E002", "profile": args.profile,
        "git_hash": git, "config_snapshot": cfg,
        "data_cutoff": str(cutoff), "random_seed": cfg["backtest"]["random_seed"],
        "alpha": ALPHA, "precision_pct": PRECISION_PCT,
        "decision_months": months, "labeled_rows": total_rows,
        "runtime_seconds": round(time.monotonic() - t0, 3),
        "features": results, "bh_survivors": survivors,
        "survivor_count": len(survivors),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"E002 sweep: {len(FEATURES)} features x {months} decision months, "
          f"{total_rows:,} labeled rows, cutoff {cutoff} — wrote {path}", flush=True)
    print(f"{'feature':<28}{'dir':>4}{'pooledIC':>10}{'p':>12}{'BH':>4}{'prec':>8}{'n':>9}")
    for m in FEATURES:
        r = results[m]
        ic = f"{r['pooled_ic']:+.4f}" if r["pooled_ic"] is not None else "  —"
        p = f"{r['p']:.2e}" if r["p"] is not None else "—"
        print(f"{m:<28}{DIRECTIONS[m]:>4}{ic:>10}{p:>12}{'*' if flags[m] else '':>4}"
              f"{r['precision']:>8.1%}{r['n']:>9,}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
