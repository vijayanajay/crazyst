"""E020-C — test-window confirmation of E020's frozen 90/10 blend (BRD §12: the final
pre-deployment step named by E020's decision rule).

Frozen construction = E020's committed run.py, unchanged: constant-mix monthly re-split of
total equity w/(1−w) between the index core (sourced Nifty 500 TRI month-end marks) and
the E019 deployable satellite (arm A: real costs 0.105%/side, 12-month holds, 3% cap, no
stops, sell-at-last-trade delisting proxy, labeled rows only, E018._decile_book). w = 0.10
— the E020 winner, never re-picked. The only degree of freedom E020's words do not settle
is the sim's warm-up start; it is pre-registered in confirm_hypothesis.md: the satellite
sim runs from the slice month exactly 12 before the test window (2022-08-31), the
confirmation window is the 35 test months (2023-08-31 → 2026-06-30), and a fresh-start
sensitivity arm (sim starts 2023-08-31 with cash 1.0) is recorded but not gating.

Guards: G1 the satellite re-run over the 145-month slice reproduces E020's committed
satellite CAGR/maxDD to 1e-9 (no code/data drift); G2 the index leg — built with the
harness's own _benchmark_sourced_tri/_benchmark_for_window and CAGR'd via
src.backtest.metrics.cagr — equals the harness's committed test-window benchmark_cagr to
1e-9 (the confirmation is read against the same benchmark every harness result is read
against); G3 no look-ahead by construction.

Bars (E020's, restated on the test window): B1 blended CAGR >= index + 2.0pp;
B2 blended maxDD >= index maxDD − 3.0pp (negative fractions). CONFIRMED iff B1+B2 for the
warm-up arm with all guards green; otherwise NON-CONFIRMED (deploy recommendation reverts
to pure indexing per E020's FAIL clause).

python -m experiments.020_joint_path_blend.confirm --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import time

import duckdb

from src.config import load
from src.backtest.metrics import cagr as m_cagr, max_drawdown as m_maxdd

E020 = importlib.import_module("experiments.020_joint_path_blend.run")
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

E020_RESULTS = os.path.join(os.path.dirname(__file__), "results.json")
HR_RESULTS = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "walkforward",
                          "harness_results.json")

W = 0.10                      # E020's frozen winner
WARMUP_MONTHS = 12            # one HOLD period
COST_SIDE_REAL = 0.00105
CAGR_BAR = 0.02               # B1
DD_TOL = 0.03                 # B2


def _stats_monthly(series: list[float]) -> tuple[float, float, float, float]:
    """CAGR (months), maxDD, Sharpe (monthly), worst month — E020's blend arithmetic."""
    cagr = (series[-1] / series[0]) ** (12 / (len(series) - 1)) - 1
    peak, dd = 1.0, 0.0
    for e in series:
        peak = max(peak, e)
        dd = min(dd, e / peak - 1)
    rets = [series[i] / series[i - 1] - 1 for i in range(1, len(series))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sharpe = mean / (var ** 0.5) * (12 ** 0.5)
    return cagr, dd, sharpe, min(rets)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e020 = json.load(open(E020_RESULTS, encoding="utf-8"))
    hr = json.load(open(HR_RESULTS, encoding="utf-8"))
    a_cagr = e020["guards"]["G1_recomputed"]["cagr"]          # E020's committed satellite
    a_dd = e020["guards"]["G1_recomputed"]["maxdd"]
    hb_cagr = hr["engine"]["benchmark_cagr"]                   # 35-mo committed benchmark

    # ---- data: the E020 path exactly (chain rebuild, _fetch, splits, marks) ---------------
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)                 # full profile; selfcheck resets to quick
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        slice_folds = sorted({str(r[0]) for r in val_rows})
        test_folds = sorted({str(r[0]) for r in test_rows})
        assert len(slice_folds) == 145 and slice_folds[0] == "2011-07-29" \
            and slice_folds[-1] == "2023-07-31"
        assert len(test_folds) == 35 and test_folds[0] == "2023-08-31" \
            and test_folds[-1] == "2026-06-30"
        assert str(boundary) == "2023-09-24"
        all_months = sorted({str(r[0]) for r in rows})
        prev_m = all_months[all_months.index(test_folds[0]) - 1]  # harness's refit month
        assert prev_m == "2023-07-31"
        by_month_lbl: dict[str, list] = {}
        for r in labeled:
            by_month_lbl.setdefault(str(r[0]), []).append(r)
        marks_raw = con.execute(
            "SELECT symbol, substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(adj_close, date) "
            "FROM adj_close GROUP BY symbol, ym").fetchall()
    finally:
        con.close()
    marks: dict[str, dict[str, float]] = {}
    for s, ym, p in marks_raw:
        if p and p > 0:
            marks.setdefault(s, {})[ym] = p

    # ---- G2: index leg via the harness's own committed benchmark construction -------------
    tri = HARNESS._benchmark_sourced_tri(cfg, prev_m, test_folds[-1])
    assert tri is not None, "sourced NIFTY 500 TRI missing - run src.download.nifty_tri"
    bench_eq = HARNESS._benchmark_for_window(tri, test_folds[0], test_folds[-1])
    assert [r["date"] for r in bench_eq] == test_folds, "benchmark marks off the fold axis"
    idx_curve = [r["equity"] for r in bench_eq]
    idx_cagr = m_cagr(bench_eq)
    idx_dd = m_maxdd(bench_eq)
    g2 = abs(idx_cagr - hb_cagr) < 1e-9
    assert g2, (idx_cagr, hb_cagr)

    # ---- G1: satellite re-run over the 145-month slice == E020's committed sim ------------
    sat_slice = E020._satellite_sim(by_month_lbl, slice_folds, marks, COST_SIDE_REAL)
    eqs = [c["equity"] for c in sat_slice]
    c_s = (eqs[-1] / eqs[0]) ** (12 / (len(eqs) - 1)) - 1
    peak, dd_s = 1.0, 0.0
    for e in eqs:
        peak = max(peak, e)
        dd_s = min(dd_s, e / peak - 1)
    g1 = abs(c_s - a_cagr) < 1e-9 and abs(dd_s - a_dd) < 1e-9
    assert g1, (c_s, dd_s, a_cagr, a_dd)

    # ---- satellite over the test window: warm-up arm (pre-registered) ---------------------
    start_i = len(slice_folds) - WARMUP_MONTHS                 # 2022-08-31
    assert slice_folds[start_i][:7] == "2022-08"
    warm_folds = slice_folds[start_i:] + test_folds
    sat_warm_full = E020._satellite_sim(by_month_lbl, warm_folds, marks, COST_SIDE_REAL)
    base = sat_warm_full[WARMUP_MONTHS]["equity"]              # equity AT 2023-08-31
    assert sat_warm_full[WARMUP_MONTHS]["m"] == test_folds[0]
    sat_warm = [{"m": c["m"], "equity": c["equity"] / base}
                for c in sat_warm_full[WARMUP_MONTHS:]]        # rebased at the test window
    sat_fresh = E020._satellite_sim(by_month_lbl, test_folds, marks, COST_SIDE_REAL)

    # ---- the blend: E020's constant-mix re-split, month by month --------------------------
    arms: dict[str, dict] = {}
    for name, sat in (("warm_up", sat_warm), ("fresh_start", sat_fresh)):
        assert len(sat) == 35
        blended = [W * sat[i]["equity"] + (1 - W) * idx_curve[i] for i in range(35)]
        cagr, dd, sharpe, worst = _stats_monthly(blended)
        sat_c, sat_dd, _sh, _w = _stats_monthly([c["equity"] for c in sat])
        arms[name] = {"w_satellite": W, "cagr": cagr, "maxdd": dd, "sharpe": sharpe,
                      "worst_month": worst, "satellite_cagr": sat_c, "satellite_maxdd": sat_dd,
                      "B1_cagr_ge_index_plus_2pp": cagr >= idx_cagr + CAGR_BAR,
                      "B2_maxdd_le_index_plus_3pp": dd >= idx_dd - DD_TOL}
    a = arms["warm_up"]
    confirmed = a["B1_cagr_ge_index_plus_2pp"] and a["B2_maxdd_le_index_plus_3pp"]
    verdict = "CONFIRMED" if confirmed else "NON-CONFIRMED"

    out = {
        "experiment": "E020_confirm_test_window", "git_hash": git, "profile": args.profile,
        "window": {"test_months": 35, "first": test_folds[0], "last": test_folds[-1],
                   "warmup_start": warm_folds[0], "construction": "E020 exact, w=0.10, "
                   "no re-tuning; warm-up start pre-registered in confirm_hypothesis.md"},
        "guards": {"G1_satellite_repro_E020": g1, "G1_recomputed": {"cagr": c_s, "maxdd": dd_s},
                   "G2_index_leg_equals_harness_benchmark": g2, "G2_index_cagr": idx_cagr,
                   "G2_index_maxdd": idx_dd,
                   "G3_no_lookahead": "construction: sim at month t consumes only marks "
                                      "dated <= t; selections from month-t rows only",
                   "passed": g1 and g2},
        "arms": arms,
        "reference": {"test_window_index_cagr": idx_cagr, "test_window_index_maxdd": idx_dd,
                      "harness_engine_cagr": hr["engine"]["cagr"],
                      "harness_benchmark_cagr_committed": hb_cagr},
        "bars": {"CAGR_bar_pp": CAGR_BAR * 100, "DD_tol_pp": DD_TOL * 100,
                 "bars_as_coded": "b1: cagr >= idx_cagr + 0.02; b2: maxdd >= idx_dd - 0.03 "
                                  "(negative fractions); gating arm = warm_up"},
        "verdict": verdict,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results_confirm.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                  # noqa: E731
    print(f"test window: 35 months {test_folds[0]} -> {test_folds[-1]} (E020 construction, "
          f"w=0.10, no re-tuning; warm-up from {warm_folds[0]})")
    print(f"guards: G1 satellite == E020 committed ({c_s:.6f}/{dd_s:.4f}); G2 index leg == "
          f"harness benchmark ({idx_cagr:.6f} vs {hb_cagr:.6f}); G3 by construction")
    print(f"\nreference: index {pct(idx_cagr)} CAGR / {pct(idx_dd)} maxDD "
          f"(harness engine CAGR {pct(hr['engine']['cagr'])} over the same months)")
    print("arm          CAGR     maxDD    Sharpe   worst-mo   sat-CAGR   sat-maxDD   B1     B2")
    for k, x in arms.items():
        print(f"  {k:<10} {pct(x['cagr']):>8} {pct(x['maxdd']):>8} {x['sharpe']:>7.2f} "
              f"{pct(x['worst_month']):>9}  {pct(x['satellite_cagr']):>9} "
              f"{pct(x['satellite_maxdd']):>10}   {str(x['B1_cagr_ge_index_plus_2pp']):<5} "
              f"{x['B2_maxdd_le_index_plus_3pp']}")
    print(f"bars: B1 CAGR >= index {pct(idx_cagr)} + 2.0pp; B2 maxDD >= {pct(idx_dd - DD_TOL)}")
    print(f"DECISION: {verdict}"
          + (" — the frozen 90/10 blend holds out of sample; the E020 design is deployable"
             if confirmed else
             " — the blend did not clear E020's bars out of sample; per E020's FAIL clause "
             "the deploy recommendation reverts to pure indexing"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
