"""E023 — the delivery-dynamics composite: 3f (mom_12m_1m + delivery_pct +
delivery_pct_trend) vs the shipped 2f on the validation slice.
(Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

Shortlist item #1 of docs/feature_family_audit.md. P4.1's frozen machinery (split, paired-t,
mean IC, top-5% precision) is imported, not copied — the bar cannot drift. The only new
code is the treatment scorer: `model.score_month` over the three frozen features (the
shipped composite's own NaN contract). The control IS `model.score_month_2f`, the
production path.

Guards: G1 the control's slice mean monthly IC == smoke.SLICE_IC_PIN to 1e-9; G2 slice
pins (145 months, boundary 2023-09-24); G3 >= 6 common months for the paired t.

Bar B1 (gating): paired monthly t of T - C, mean diff > 0 and two-sided p < 0.05
(P4.1/P4.1b alpha; no BH — one pre-registered combination, no sweep). Recorded, not
gating: per-arm mean ICs, top-5% precision, scored-row fractions.

python -m experiments.023_composite_3f_delivery_trend.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import time

import duckdb

from src.config import load
from src.model import composite as model
from src.features.panel import _FEATURES as PANEL_FEATURES
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")
HARNESS = importlib.import_module("src.walkforward.harness")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
smoke = importlib.import_module("src.backtest.smoke_e2e")

FEATURES_3F = ("mom_12m_1m", "delivery_pct", "delivery_pct_trend")
ALPHA = 0.05

# matrix row layout: (mdate, next_month_ret, ...PANEL_FEATURES..., liquidity_rank, symbol,
# size_bucket) — the same map model.score_month_2f derives from PANEL_FEATURES
fi3 = {name: 2 + PANEL_FEATURES.index(name) for name in FEATURES_3F}


def _score_3f(rs):
    """The treatment: mean percentile rank of the three frozen features, built on the
    shipped `model._pct` (the composite's own rank math and NaN contract: rows with >= 1
    non-NaN feature score, None rows stay None). NOT model.score_month — that function
    iterates the module's own two-feature FEATURES global, so a third feature passed via
    the feature_at lambda is silently dropped (caught when the first run reproduced the
    control bit-identically)."""
    pcts = {name: model._pct([r[fi3[name]] for r in rs]) for name in FEATURES_3F}
    out = []
    for i in range(len(rs)):
        got = [pcts[f][i] for f in FEATURES_3F if pcts[f][i] is not None]
        out.append(sum(got) / len(got) if got else None)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    ic_pin = smoke.SLICE_IC_PIN

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        val_folds = sorted({str(r[0]) for r in val_rows})
        assert len(val_folds) == 145 and val_folds[0] == "2011-07-29" \
            and val_folds[-1] == "2023-07-31"
        assert str(boundary) == "2023-09-24"
        by_month: dict[str, list] = {}
        for r in val_rows:
            by_month.setdefault(str(r[0]), []).append(r)
    finally:
        con.close()

    # ---- monthly ICs for both arms on the validation slice -------------------------------
    def month_ic(scores, rs):
        pairs = [(s, r[1]) for s, r in zip(scores, rs) if s is not None and r[1] is not None]
        return (spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
                if len(pairs) >= 3 else None), len(pairs)

    ics_t, ics_c, n_scored_t, n_rows = [], [], 0, 0
    for m in val_folds:
        rs = by_month[m]
        n_rows += len(rs)
        it, nt = month_ic(_score_3f(rs), rs)
        ic_, nc = month_ic(model.score_month_2f(rs), rs)
        ics_t.append((m, it, nt))
        ics_c.append((m, ic_, nc))
        n_scored_t += nt
    mean_t, mt_n = P41._mean_ic(ics_t)
    mean_c, mc_n = P41._mean_ic(ics_c)

    # ---- guards --------------------------------------------------------------------------
    g1 = abs(mean_c - ic_pin) < 1e-9
    assert g1, (mean_c, ic_pin)
    g2 = len(val_folds) == 145 and str(boundary) == "2023-09-24"
    assert g2
    comp = P41._paired_t(ics_t, ics_c)
    g3 = comp is not None and comp["n_months"] >= 6
    assert g3, comp

    # ---- bar + recorded-not-gating --------------------------------------------------------
    b1 = comp["mean_diff"] > 0 and comp["p"] < ALPHA
    by_month_rows = {m: by_month[m] for m in val_folds}
    prec = {}
    for name, scorer in (("composite_3f_dt", _score_3f), ("shipped_2f", model.score_month_2f)):
        scores = {m: scorer(by_month_rows[m]) for m in val_folds}
        p5, nm = P41._top5_precision(by_month_rows, scores)
        prec[name] = {"precision": p5, "months": nm}
    frac_scored = n_scored_t / n_rows

    out = {
        "experiment": "E023_composite_3f_delivery_trend", "git_hash": git,
        "profile": args.profile,
        "window": {"validation_months": len(val_folds), "first": val_folds[0],
                   "last": val_folds[-1], "boundary": str(boundary),
                   "test_window": "burnt by E020-C; not touched"},
        "guards": {"G1_control_equals_ic_pin": g1, "G1_control_mean_ic": mean_c,
                   "G1_pin": ic_pin, "G2_slice_pins": g2,
                   "G3_paired_months": comp["n_months"], "passed": g1 and g2 and g3},
        "arms": {"composite_3f_dt": {"features": list(FEATURES_3F), "mean_monthly_ic": mean_t,
                                     "months": mt_n, "frac_rows_scored": frac_scored,
                                     "top5_precision": prec["composite_3f_dt"]},
                 "shipped_2f": {"mean_monthly_ic": mean_c, "months": mc_n,
                                "top5_precision": prec["shipped_2f"]}},
        "bars": {"B1_paired_t": {**comp, "alpha": ALPHA, "passed": b1},
                 "as_coded": "P41._paired_t(ics_3f, ics_2f); b1 = mean_diff > 0 and p < 0.05"},
        "verdict": "PASS" if b1 else "REJECTED",
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"E023: validation slice {len(val_folds)} months (test window untouched); guards "
          f"G1 control IC {mean_c:.10f} == pin, G2, G3 ({comp['n_months']} paired months)")
    print(f"  shipped_2f     mean IC {mean_c:+.4f}   top5 {prec['shipped_2f']['precision']:.1%}")
    print(f"  composite_3f   mean IC {mean_t:+.4f}   top5 {prec['composite_3f_dt']['precision']:.1%}"
          f"   ({frac_scored:.1%} of rows scored)")
    print(f"  paired: diff {comp['mean_diff']:+.4f}, t {comp['t']:+.2f}, p {comp['p']:.4f} "
          f"(alpha {ALPHA})")
    print(f"DECISION: {out['verdict']}"
          + (" — the 3f becomes a candidate; a promotion test (E018-style book at real "
             "costs) is the next pre-registration, nothing ships here" if b1 else
             " — the shipped 2f stands; the composite family is closed"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
