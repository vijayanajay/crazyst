"""P4.1b — two-feature composite (mom_12m_1m + delivery_pct) vs P4.1's three-feature
composite and the best single feature on the same validation slice (run only after
hypothesis.md was written).

Reuses P4.1's scoring and slice code by importlib so the two experiments cannot drift. Arms:
composite_2f (mean percentile rank of mom_12m_1m + delivery_pct), composite_3f (P4.1's
control, recomputed here), best_single (slice-selected among all 22 features). Primary
comparisons: 2f vs best_single and 2f vs 3f, paired monthly t, alpha = 0.05 — per the
pre-registration, no BH.

Usage:
    python -m experiments.004b_composite_2feat.run --profile full

Writes results.json (config snapshot, git hash, cutoff — BRD 13) and prints the table.
Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the run completed.
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")   # shared slice + scoring
FEATURES = P41.FEATURES
COMPOSITE_2F = ("mom_12m_1m", "delivery_pct")
COMPOSITE_3F = ("mom_12m_1m", "mom_6m", "delivery_pct")     # P4.1's control, frozen
ALPHA = 0.05


def score_month_2f(rs):
    """Two-feature composite scores for one month's rows (P4.1's _pct construction)."""
    fi = {name: 2 + i for i, name in enumerate(FEATURES)}
    pcts = {name: P41._pct([r[fi[name]] for r in rs]) for name in COMPOSITE_2F}
    scores = []
    for i, _ in enumerate(rs):
        got = [pcts[f][i] for f in COMPOSITE_2F if pcts[f][i] is not None]
        scores.append(sum(got) / len(got) if got else None)
    return scores


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff = P41._fetch(con)
    finally:
        con.close()
    assert rows, "no labeled rows — build feature_matrix first"
    # P4.1's rebuild left the full-history matrix in place; a quick-profile rebuild would
    # strand the slice, so assert the span the pre-registration promises before scoring.
    months = sorted({str(r[0]) for r in rows})
    assert len(months) > 120 and months[0] < "2012", \
        f"expected the full-history matrix (got {len(months)} months from {months[0]}) — " \
        "rebuild the full-profile chain first"
    val, test, boundary = P41.split_slice(rows, cutoff)
    assert val, "the validation slice must be non-empty"

    by_month = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    fi = {name: 2 + i for i, name in enumerate(FEATURES)}

    ics = {"composite_2f": [], "composite_3f": []}
    for name in FEATURES:
        ics[name] = []
    scores_2f, scores_3f = {}, {}
    for m, rs in sorted(by_month.items()):
        rets = [r[1] for r in rs]
        s2 = score_month_2f(rs)
        s3, _ = P41.score_month(rs)
        scores_2f[m], scores_3f[m] = s2, s3
        for arm, scores in (("composite_2f", s2), ("composite_3f", s3)):
            pairs = [(s, ret) for s, ret in zip(scores, rets) if s is not None]
            ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
            ics[arm].append((m, ic, len(pairs)))
        for name in FEATURES:
            pairs = [(r[fi[name]], r[1]) for r in rs if r[fi[name]] is not None
                     and not (isinstance(r[fi[name]], float) and math.isnan(r[fi[name]]))]
            ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
            ics[name].append((m, ic, len(pairs)))

    means = {arm: P41._mean_ic(v) for arm, v in ics.items()}
    singles = {name: means[name][0] for name in FEATURES if means[name][0] is not None}
    best_single = max(singles, key=singles.get)
    comparisons = {
        "composite_2f_vs_best_single": P41._paired_t(ics["composite_2f"], ics[best_single]),
        "composite_2f_vs_composite_3f": P41._paired_t(ics["composite_2f"], ics["composite_3f"]),
    }
    prec = {}
    for arm, scores in (("composite_2f", scores_2f), ("composite_3f", scores_3f),
                        ("best_single", {m: [r[fi[best_single]] for r in rs]
                                         for m, rs in by_month.items()})):
        p, nm = P41._top5_precision(by_month, scores)
        prec[arm] = {"precision": p, "months": nm}

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "P4.1b_composite_2feat", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "validation_boundary": str(boundary),
        "validation_months": len(by_month), "validation_rows": len(val),
        "excluded_test_months": len({str(r[0]) for r in test}),
        "composite_2f_features": list(COMPOSITE_2F),
        "composite_3f_features": list(COMPOSITE_3F),
        "universe_note": "as-of top-1500, floor OFF; BRD-owner decisions pending flag",
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
    print(f"P4.1b: validation slice {out['validation_months']} months / {len(val):,} rows "
          f"(boundary {boundary}), test window ({out['excluded_test_months']} labeled months) "
          f"not scored — wrote {path}", flush=True)
    print(f"\n{'arm':<26}{'meanIC':>9}{'months':>8}{'top5prec':>10}")
    for arm in ("composite_2f", "composite_3f", best_single):
        m = means[arm]
        pr = prec["best_single"]["precision"] if arm == best_single else prec[arm]["precision"]
        print(f"{arm:<26}{m[0]:>9.4f}{m[1]:>8,}{pr * 100 if pr is not None else float('nan'):>9.1f}%")
    print(f"\nbest single (chosen ON the slice): {best_single}")
    for name, c in comparisons.items():
        if c:
            print(f"{name}: mean monthly diff {c['mean_diff']:+.4f} over {c['n_months']} months, "
                  f"t = {c['t']:+.2f}, p = {c['p']:.4f}")
        else:
            print(f"{name}: not computable (< 6 shared months)")
    return 0


if __name__ == "__main__":
    import math
    sys.exit(main(sys.argv[1:]))
