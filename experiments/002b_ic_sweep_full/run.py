"""E002b — full-profile confirmation IC sweep (run only after hypothesis.md was written).

Same feature set and pre-registered directions as E002 (imported from that frozen module so
the two cannot drift), different pooling statistic fixed by E002b's hypothesis: the headline
is the MEAN MONTHLY IC with a one-sample t-test across decision months (month fixed effects
removed by construction — a bull window cannot manufacture IC), BH-corrected across all 22
features. E002's raw pooled IC is reported alongside for continuity; no verdict leans on it.
Headline features also get per-regime (month's realized cross-sectional mean forward return)
and per-size-bucket mean monthly ICs.

Usage:
    python -m experiments.002b_ic_sweep_full.run --profile full

Writes results.json (config snapshot, git hash, data cutoff — BRD §13) and prints the table.
Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the sweep ran.
"""
import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.stats import bh_rejects, spearman_ic, t_sf_two_sided

ALPHA = 0.05
E002 = importlib.import_module("experiments.002_ic_sweep.run")   # frozen: features + directions
FEATURES, DIRECTIONS = E002.FEATURES, E002.DIRECTIONS
REGIME_FEATURES = ("mom_12m_1m", "delivery_pct", "delivery_pct_zscore", "atr_ratio",
                   "squeeze_days_20d", "volume_zscore", "mom_1m")


def _fetch(con):
    return con.execute(
        "SELECT mdate, symbol, is_winner, size_bucket, next_month_ret, "
        + ", ".join(FEATURES) +
        " FROM feature_matrix WHERE next_month_ret IS NOT NULL ORDER BY mdate").fetchall()


def _month_ic(pairs):
    vals, rets = [p[0] for p in pairs], [p[1] for p in pairs]
    return spearman_ic(vals, rets) if len(pairs) >= 3 else None


def _t_stat(ics):
    """(mean monthly IC, t across months, p, sign consistency, months) — None-IC months skipped."""
    vals = [ic for _, ic, _ in ics if ic is not None]
    if len(vals) < 6:
        return None
    n = len(vals)
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    t = mean / (sd / math.sqrt(n)) if sd > 0 else (0.0 if mean == 0 else math.copysign(1e9, mean))
    pos = sum(1 for v in vals if v > 0)
    return {"mean_monthly_ic": mean, "t": t, "p": t_sf_two_sided(t, n - 1), "months": n,
            "sign_consistency": max(pos, n - pos) / n}


def _analyze(rows):
    """Mean monthly IC per feature, plus regime and size-bucket splits for headline features."""
    month_mean = {}
    for r in rows:
        d = str(r[0])
        if r[4] is not None:
            s = month_mean.setdefault(d, [0.0, 0])
            s[0] += r[4]
            s[1] += 1
    regime = {d: ("up" if s / n > 0 else "down") for d, (s, n) in month_mean.items() if n}

    results = {}
    for fi, name in enumerate(FEATURES):
        col = 5 + fi
        # pooled raw IC (E002's statistic, continuity only)
        pooled_pairs = [(r[col], r[4]) for r in rows if r[col] is not None
                        and not (isinstance(r[col], float) and math.isnan(r[col]))
                        and r[4] is not None]
        pooled = _month_ic(pooled_pairs)
        per_month, reg_cells, bucket_cells = {}, {}, {}
        for r in rows:
            if r[col] is None or (isinstance(r[col], float) and math.isnan(r[col])) or r[4] is None:
                continue
            d = str(r[0])
            per_month.setdefault(d, []).append((r[col], r[4]))
            reg_cells.setdefault((regime[d], d), []).append((r[col], r[4]))
            bucket_cells.setdefault((d, str(r[3])), []).append((r[col], r[4]))
        monthly = [(d, _month_ic(pairs), len(pairs)) for d, pairs in sorted(per_month.items())]
        entry = {"direction": DIRECTIONS[name], "n": len(pooled_pairs), "pooled_ic_raw": pooled,
                 "mean_monthly": _t_stat(monthly)}
        if name in REGIME_FEATURES:
            # regime: one IC per month over that month's full cross-section (never per bucket —
            # bucket cells would inflate n with correlated within-month observations)
            regimes = sorted({rg for rg, _ in reg_cells})
            entry["regime"] = {k: _t_stat([(d, _month_ic(ps), len(ps))
                                           for (kk, d), ps in sorted(reg_cells.items())
                                           if kk == k])
                               for k in regimes}
            buckets = sorted({b for _, b in bucket_cells})
            entry["size_buckets"] = {b: _t_stat([(d, _month_ic(ps), len(ps))
                                                 for (d, bb), ps in sorted(bucket_cells.items())
                                                 if bb == b])
                                     for b in buckets}
        results[name] = entry
    return results


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows = _fetch(con)
        cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    finally:
        con.close()
    assert rows, "no labeled rows — build feature_matrix first (full profile)"

    results = _analyze(rows)
    pvals = [results[m]["mean_monthly"]["p"] if results[m]["mean_monthly"] else None
             for m in FEATURES]
    flags = {m: (i in bh_rejects(pvals, ALPHA)) for i, m in enumerate(FEATURES)}

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "E002b", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "random_seed": cfg["backtest"]["random_seed"], "alpha": ALPHA,
        "statistic": "mean monthly Spearman IC, one-sample t across months, BH-corrected",
        "decision_months": len({str(r[0]) for r in rows}), "labeled_rows": len(rows),
        "runtime_seconds": round(time.monotonic() - t0, 3),
        "features": results, "bh_rejects": [m for m in FEATURES if flags[m]],
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"E002b sweep ({args.profile}): {len(FEATURES)} features x {out['decision_months']} "
          f"decision months, {len(rows):,} labeled rows, cutoff {cutoff} — wrote {path}",
          flush=True)
    print(f"{'feature':<28}{'dir':>4}{'meanIC':>9}{'t':>9}{'p':>11}{'sign%':>7}"
          f"{'pooledIC':>10}{'BH':>4}{'n':>9}")
    for m in FEATURES:
        r = results[m]
        s = r["mean_monthly"]
        mic = f"{s['mean_monthly_ic']:+.4f}" if s else "—"
        t = f"{s['t']:+.2f}" if s else "—"
        p = f"{s['p']:.2e}" if s else "—"
        sc = f"{s['sign_consistency']:.0%}" if s else "—"
        pic = f"{r['pooled_ic_raw']:+.4f}" if r["pooled_ic_raw"] is not None else "—"
        print(f"{m:<28}{r['direction']:>4}{mic:>9}{t:>9}{p:>11}{sc:>7}{pic:>10}"
              f"{'*' if flags[m] else '':>4}{r['n']:>9,}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
