"""P4.2 — learned ranker vs composite_2f on the same validation-slice gate (run only after
hypothesis.md was written).

Monthly walk-forward HistGradientBoostingRegressor refits (fixed hyperparameters, no tuning,
purged training window), all 22 E002 features, NaN-native. Primary: paired monthly t of the
ranker's IC vs composite_2f's (P4.1b's shipped control, recomputed in-process via its module).
Plan 4.3's freeze check is part of the run: model_meta.json (hyperparameters, feature list,
fold manifest) is written to artifact/, the first and last scored folds are refit twice and
asserted identical to < 1e-12, and the last fold's top-5% picks are re-derived from a fresh
refit and asserted equal to the saved ones.

Usage:
    python -m experiments.0042_learned_ranker.run --profile full

Writes results.json + artifact/model_meta.json and prints the table. Verdict logic lives in
verdict.md; this script only measures. Exit 0 iff the run completed.
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
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor

from src.config import load
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")   # shared slice + helpers
P41B = importlib.import_module("experiments.004b_composite_2feat.run")  # composite_2f scoring
FEATURES = P41.FEATURES
ALPHA = 0.05
WARMUP_MONTHS = 24          # first fold needs >= 24 training months (pre-registered)
HYPERPARAMS = {             # fixed a priori, never swept (pre-registered)
    "max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 15,
    "min_samples_leaf": 100, "l2_regularization": 1.0,
    "early_stopping": False,
}
SYM = 2 + len(FEATURES)     # symbol column index in our own fetch (last column)


def _fetch(con):
    """P4.1's fetch plus symbol (last column) — needed for pick reproduction (plan 4.3)."""
    rows = con.execute(
        "SELECT mdate, next_month_ret, " + ", ".join(FEATURES) + ", symbol "
        "FROM feature_matrix WHERE next_month_ret IS NOT NULL ORDER BY mdate").fetchall()
    cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    return rows, cutoff


def _month_table(rs):
    """(X, y) for one month: features as float columns (None -> NaN), y = forward return."""
    fi = {name: 2 + i for i, name in enumerate(FEATURES)}
    X = [[r[fi[name]] if r[fi[name]] is not None else float("nan") for name in FEATURES]
         for r in rs]
    y = [r[1] for r in rs]
    return X, y


def _fold_train_idx(ordered, label_end, mi):
    """Training month indices for fold mi: label end >= 1 month before M starts (purge)."""
    m = ordered[mi][0]
    return [k for k in range(mi)
            if label_end[ordered[k][0]] is not None and label_end[ordered[k][0]] < m]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    seed = cfg["backtest"]["random_seed"]
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff = _fetch(con)
    finally:
        con.close()
    assert rows, "no labeled rows — build feature_matrix first"
    months = sorted({str(r[0]) for r in rows})
    assert len(months) > 120 and months[0] < "2012", \
        f"expected the full-history matrix (got {len(months)} months from {months[0]})"
    val, test, boundary = P41.split_slice(rows, cutoff)
    assert val, "the validation slice must be non-empty"

    by_month = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    ordered = sorted(by_month.items())
    all_months = sorted({str(r[0]) for r in rows})
    label_end = {m: (all_months[i + 1] if i + 1 < len(all_months) else None)
                 for i, m in enumerate(all_months)}
    X_all, y_all = {}, {}
    for m, rs in ordered:
        X_all[m], y_all[m] = _month_table(rs)

    def fit_fold(mi):
        """One walk-forward fit: train on purged history, predict month mi's cross-section."""
        idx = _fold_train_idx(ordered, label_end, mi)
        Xtr = [row for k in idx for row in X_all[ordered[k][0]]]
        ytr = [v for k in idx for v in y_all[ordered[k][0]]]
        model = HistGradientBoostingRegressor(random_state=seed, **HYPERPARAMS)
        model.fit(Xtr, ytr)
        return model.predict(X_all[ordered[mi][0]]), len(idx), len(Xtr)

    # ---- walk-forward: refit every month, score the month's cross-section ----
    ranker_ics, composite_ics, folds = [], [], []
    ranker_scores = {}
    warmup = 0
    for mi, (m, rs) in enumerate(ordered):
        rets = y_all[m]
        if len(_fold_train_idx(ordered, label_end, mi)) < WARMUP_MONTHS:
            warmup += 1
            ranker_ics.append((m, None, len(rs)))          # disclosed warm-up month
            ranker_scores[m] = []
        else:
            pred, n_train, n_rows = fit_fold(mi)
            pairs = [(p, r) for p, r in zip(pred, rets) if r is not None
                     and not (isinstance(p, float) and math.isnan(p))]
            ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
            ranker_ics.append((m, ic, len(pairs)))
            ranker_scores[m] = list(pred)
            folds.append({"month": m, "train_months": n_train, "train_rows": n_rows, "ic": ic})
        s2 = P41B.score_month_2f(rs)
        pairs = [(s, r) for s, r in zip(s2, rets) if s is not None]
        cic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
        composite_ics.append((m, cic, len(pairs)))

    def mean_ic(seq):
        vals = [ic for _, ic, _ in seq if ic is not None]
        return (sum(vals) / len(vals) if vals else None), len(vals)

    ranker_mean, ranker_months = mean_ic(ranker_ics)
    comp_mean, comp_months = mean_ic(composite_ics)
    primary = P41._paired_t(ranker_ics, composite_ics)
    prec = {
        "ranker": {"precision": P41._top5_precision(by_month, ranker_scores)[0]},
        "composite_2f": {"precision": P41._top5_precision(
            by_month, {m: P41B.score_month_2f(rs) for m, rs in ordered})[0]},
    }

    # ---- freeze protocol (plan 4.3): artifact, determinism, pick reproduction ----
    art = os.path.join(os.path.dirname(__file__), "artifact")
    os.makedirs(art, exist_ok=True)
    meta = {
        "model": "sklearn.HistGradientBoostingRegressor",
        "sklearn_version": sklearn.__version__,
        "hyperparameters": HYPERPARAMS, "random_seed": seed,
        "features": list(FEATURES),
        "walk_forward": "monthly refit, 1-month purge by label end (BRD 10.2)",
        "warmup_rule": f">= {WARMUP_MONTHS} training months",
        "folds": folds,
    }
    meta_path = os.path.join(art, "model_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    scored = [i for i, (_, ic, _) in enumerate(ranker_ics) if ic is not None]
    first_i, last_i = scored[0], scored[-1]
    det = {}
    for tag, idx in (("first", first_i), ("last", last_i)):
        p1 = fit_fold(idx)[0]
        p2 = fit_fold(idx)[0]
        diff = max(abs(float(a) - float(b)) for a, b in zip(p1, p2))
        assert diff < 1e-12, f"{tag}-fold refit is not deterministic (max|diff| {diff:.2e})"
        det[tag] = {"month": ordered[idx][0], "max_abs_diff": diff}
    m_last, rs_last = ordered[last_i]
    pred_saved = fit_fold(last_i)[0]
    k = max(1, round(len(pred_saved) * 0.05))
    picks_saved = {rs_last[i][SYM] for i in
                   sorted(range(len(pred_saved)), key=lambda i: -pred_saved[i])[:k]}
    pred_fresh = fit_fold(last_i)[0]
    picks_fresh = {rs_last[i][SYM] for i in
                   sorted(range(len(pred_fresh)), key=lambda i: -pred_fresh[i])[:k]}
    assert picks_saved == picks_fresh, \
        "last fold's top-5% picks do not reproduce from a fresh refit"
    with open(meta_path) as f:
        assert len(json.load(f)["folds"]) == len(folds), "artifact fold count drifted"

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "P4.2_learned_ranker", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "validation_boundary": str(boundary),
        "validation_months": len(ordered), "validation_rows": len(val),
        "excluded_test_months": len({str(r[0]) for r in test}),
        "ranker_warmup_months": warmup,
        "hyperparameters": HYPERPARAMS, "random_seed": seed,
        "sklearn_version": sklearn.__version__,
        "mean_monthly_ic": {"ranker": {"ic": ranker_mean, "months": ranker_months},
                            "composite_2f": {"ic": comp_mean, "months": comp_months}},
        "paired_comparisons": {"ranker_vs_composite_2f": primary},
        "top5_precision_slice": prec,
        "determinism_checks": det,
        "artifact": "artifact/model_meta.json",
        "runtime_seconds": round(time.monotonic() - t0, 3),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"P4.2 ranker: {len(folds)} walk-forward fits over {len(ordered)} validation months "
          f"({warmup} warm-up months scored for the baseline only), boundary {boundary} — "
          f"wrote {path} + artifact/model_meta.json", flush=True)
    print(f"\n{'arm':<26}{'meanIC':>9}{'months':>8}{'top5prec':>10}")
    for arm, mean, nmon in (("ranker", ranker_mean, ranker_months),
                            ("composite_2f", comp_mean, comp_months)):
        pr = prec[arm]["precision"]
        print(f"{arm:<26}{mean:>9.4f}{nmon:>8,}{pr * 100 if pr is not None else float('nan'):>9.1f}%")
    if primary:
        print(f"\nranker vs composite_2f: mean monthly diff {primary['mean_diff']:+.4f} over "
              f"{primary['n_months']} months, t = {primary['t']:+.2f}, p = {primary['p']:.4f}")
    print(f"determinism: first fold max|diff| {det['first']['max_abs_diff']:.2e}, "
          f"last fold {det['last']['max_abs_diff']:.2e}; last fold's top-5% picks reproduce "
          f"exactly from a fresh refit", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
