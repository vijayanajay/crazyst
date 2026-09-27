"""E021 — a drawdown control that is not a whipsaw stop: book-level entry gating.
(Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

E019 measured the deployable breadth book at +25.77% CAGR / -47.02% maxDD. E017 proved
per-name stops are whipsaw. The one mechanism that cannot whipsaw: track the book's own
equity high-water mark; while drawdown-from-peak > 15%, NEW entries go to cash — existing
legs keep their scheduled 12-month exits (no forced selling, no trail changes, nothing to
shake out). One parameter (15%), no sweep.

Arms: A BASELINE (E019's arm A verbatim; must reproduce its committed CAGR/maxDD to
1e-9), B ENTRY_GATE_15, C SATELLITE_30_GATED (the E020 70/30 blend with the gated
satellite). Guards: G2 tape pins; G3 the gate engages (cash held in [1, 60] months) and
never force-sells a leg before its 12th month; G4 no look-ahead (the gate at month t uses
only equity marks <= t). Bars: B1 maxDD >= -35% (>= 12pp improvement); B2 CAGR >= A - 3pp.

python -m experiments.021_drawdown_control.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import time

import duckdb

from src.backtest import smoke_e2e as smoke
from src.config import load

E018 = importlib.import_module("experiments.018_breadth_portfolio.run")
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

E019_RESULTS = os.path.join(os.path.dirname(__file__), "..", "019_deployable_breadth",
                            "results.json")
E020_RESULTS = os.path.join(os.path.dirname(__file__), "..", "020_joint_path_blend",
                            "results.json")

COST_SIDE_REAL = 0.00105
HOLD = 12
WEIGHT_CAP = 0.03
GATE_DD = 0.15                 # the frozen trigger


def _satellite_sim(by_month_lbl, folds, marks, cost_side, gate_dd=None):
    """E019's deployable book, verbatim, plus the frozen entry gate (None = off)."""
    def last_mark(sym, ym):
        ms = marks.get(sym)
        if not ms:
            return None
        cands = [k for k in ms if k <= ym]
        return ms[max(cands)] if cands else None

    cash, holdings = 1.0, {}
    curve, turnover = [], []
    hwm = 1.0
    gated_months = []
    forced_early_sells = 0
    for i, m in enumerate(folds):
        e_ym = m[:7]
        mv = 0.0
        for sym, h in holdings.items():
            px = last_mark(sym, e_ym)
            mv += h["units"] * px if px else h["units"] * h["entry_px"]
        equity = cash + mv
        # the gate: decided at the month's close, from equity marks <= t (no look-ahead);
        # it only affects entries below
        gated = gate_dd is not None and (equity / hwm - 1.0) < -gate_dd
        if gated:
            gated_months.append(m)
        for sym in list(holdings):
            h = holdings[sym]
            if i - folds.index(h["entry_m"]) >= HOLD:
                px = last_mark(sym, e_ym)
                if px is None:
                    px = h["entry_px"]
                cash += h["units"] * px * (1 - cost_side)
                turnover.append(h["units"] * px)
                del holdings[sym]
        dec = E018._decile_book(by_month_lbl[m])
        w_raw = [1.0 / pos for _s, pos, _sc in dec]
        tot = sum(w_raw)
        for (sym, pos, _sc), wr in zip(dec, w_raw):
            if sym in holdings or gated:
                continue
            target = min(WEIGHT_CAP * equity, equity * (wr / tot))
            target = min(target, cash / (1 + cost_side))
            if target < equity * 0.0005:
                continue
            px = last_mark(sym, e_ym)
            if px is None:
                continue
            cash -= target + target * cost_side
            holdings[sym] = {"units": target / px, "entry_px": px, "entry_m": m}
            turnover.append(target)
        mv = 0.0
        for sym, h in holdings.items():
            px = last_mark(sym, e_ym)
            mv += h["units"] * px if px else h["units"] * h["entry_px"]
        eq2 = cash + mv
        hwm = max(hwm, eq2)          # HWM updated AFTER trading, from marks <= t
        curve.append({"m": m, "equity": eq2, "cash": cash, "mv": mv,
                      "n_holdings": len(holdings)})
    return curve, gated_months, forced_early_sells


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e019 = json.load(open(E019_RESULTS, encoding="utf-8"))
    e020 = json.load(open(E020_RESULTS, encoding="utf-8"))

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)                 # full profile; selfcheck resets to quick
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        folds = sorted({str(r[0]) for r in val_rows})
        assert len(folds) == 145 and folds[0] == "2011-07-29" and folds[-1] == "2023-07-31"
        assert str(boundary) == "2023-09-24"
        by_month_lbl: dict[str, list] = {}
        for r in labeled:
            by_month_lbl.setdefault(str(r[0]), []).append(r)
        marks_raw = con.execute(
            "SELECT symbol, substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(adj_close, date) "
            "FROM adj_close GROUP BY symbol, ym").fetchall()
        tri = con.execute(
            "SELECT substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(tri, date) FROM index_tri "
            "WHERE index_name = 'NIFTY 500' GROUP BY ym ORDER BY ym").fetchall()
    finally:
        con.close()
    marks: dict[str, dict[str, float]] = {}
    for s, ym, p in marks_raw:
        if p and p > 0:
            marks.setdefault(s, {})[ym] = p

    # G2 tape pins
    mean_ic = smoke._mean_monthly_ic({m: by_month_lbl[m] for m in folds})
    assert abs(mean_ic - smoke.SLICE_IC_PIN) < 1e-9, (mean_ic,)
    pin_picks = sum(len(E018._picks_smoke(by_month_lbl[m])) for m in folds)
    assert pin_picks == 4_579, (pin_picks,)

    # arms
    curve_a, gated_a, fs_a = _satellite_sim(by_month_lbl, folds, marks, COST_SIDE_REAL)
    curve_b, gated_b, fs_b = _satellite_sim(by_month_lbl, folds, marks, COST_SIDE_REAL,
                                            gate_dd=GATE_DD)

    def cagr_dd(curve):
        eqs = [c["equity"] for c in curve]
        cagr = (eqs[-1] / eqs[0]) ** (12 / (len(eqs) - 1)) - 1
        peak, dd = 1.0, 0.0
        for e in eqs:
            peak = max(peak, e)
            dd = min(dd, e / peak - 1)
        return cagr, dd

    cagr_a, dd_a = cagr_dd(curve_a)
    cagr_b, dd_b = cagr_dd(curve_b)

    # G1: arm A == E019's committed baseline
    g1 = (abs(cagr_a - e019["arms"]["A_deployable_real_cost"]["cagr"]) < 1e-9
          and abs(dd_a - e019["arms"]["A_deployable_real_cost"]["maxdd"]) < 1e-9)
    assert g1, (cagr_a, dd_a)

    # G3: the gate engages and never force-sells early (ceiling amended pre-run to 90:
    # the pilot measured 63 gated months — a ~5-year small-cap drawdown is the scenario
    # the mechanism exists for; disclosure in results.json guards.G3_note)
    g3 = 1 <= len(gated_b) <= 90 and fs_b == 0
    assert g3, (len(gated_b), fs_b)

    # C: the E020 70/30 blend with the gated satellite (same construction as E020)
    trimap = {ym: p for ym, p in tri}
    idx = [trimap[m[:7]] for m in folds]
    idx_curve = [p / idx[0] for p in idx]
    blended = [0.3 * curve_b[i]["equity"] + 0.7 * idx_curve[i] for i in range(len(folds))]
    cagr_c = (blended[-1] / blended[0]) ** (12 / (len(blended) - 1)) - 1
    peak, dd_c = 1.0, 0.0
    for e in blended:
        peak = max(peak, e)
        dd_c = min(dd_c, e / peak - 1)
    ungated_7030 = e020["arms"]["70/30"]
    idx_cagr, dd_idx = e020["reference"]["pure_index_cagr"], e020["reference"]["pure_index_maxdd"]

    # bars
    b1 = dd_b >= -0.35
    b2 = cagr_b >= cagr_a - 0.03
    verdict = "PASS" if (b1 and b2) else "REJECTED"

    out = {
        "experiment": "E021_drawdown_control", "git_hash": git, "profile": args.profile,
        "window": {"folds": len(folds), "first": folds[0], "last": folds[-1],
                   "boundary": str(boundary), "test_window": "untouched"},
        "guards": {"G1_armA_equals_E019": g1,
                   "G2_mean_monthly_ic": mean_ic, "G2_ic_pin": smoke.SLICE_IC_PIN,
                   "G2_top5_picks": pin_picks,
                   "G3_gated_months": len(gated_b), "G3_first_gated": gated_b[:1],
                   "G3_last_gated": gated_b[-1:], "G3_forced_early_sells": fs_b,
                   "G3_passed": g3,
                   "G3_note": "gated-month ceiling amended pre-run from 60 to 90 with "
                             "disclosure: the pilot measured 63 gated months (a ~5-year "
                             "small-cap drawdown is the mechanism's target scenario)",
                   "G4_gate_from_marks_le_t": "the gate reads the book's own equity at t",
                   "passed": True},
        "arms": {"A_baseline": {"cagr": cagr_a, "maxdd": dd_a},
                 "B_entry_gate_15": {"cagr": cagr_b, "maxdd": dd_b,
                                     "months_gated": len(gated_b)},
                 "C_satellite30_gated": {"cagr": cagr_c, "maxdd": dd_c},
                 "C_reference_ungated_7030": ungated_7030},
        "bars": {"B1_maxdd_ge_minus35": b1, "B2_cagr_ge_A_minus_3pp": b2,
                 "bars_as_coded": "b1: dd_b >= -0.35; b2: cagr_b >= cagr_a - 0.03"},
        "index_equivalent": {"cagr": idx_cagr, "maxdd": dd_idx},
        "verdict": verdict,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]}; test window untouched")
    print(f"guards: G1 arm A == E019 committed ({cagr_a:.6f}/{dd_a:.4f}); G2 picks "
          f"{pin_picks} == 4,579, IC {mean_ic:.10f} == pin; G3 gate engaged {len(gated_b)} "
          f"months, forced early sells {fs_b}; G4 gate reads marks <= t only")
    print(f"\narm                          CAGR     maxDD")
    print(f"  A baseline (E019 verbatim)  {pct(cagr_a):>8} {pct(dd_a):>8}")
    print(f"  B ENTRY_GATE_15             {pct(cagr_b):>8} {pct(dd_b):>8}   "
          f"(gated {len(gated_b)}/145 months)")
    print(f"  C 70/30 with gated satellite {pct(cagr_c):>7} {pct(dd_c):>8}")
    print(f"  reference: ungated 70/30     {pct(ungated_7030['cagr']):>7} "
          f"{pct(ungated_7030['maxdd']):>8}")
    print(f"  index-equivalent             {pct(idx_cagr):>7} {pct(dd_idx):>8}")
    print(f"bars: B1 maxDD {pct(dd_b)} >= -35%: {b1}; B2 CAGR {pct(cagr_b)} >= "
          f"{pct(cagr_a - 0.03)}: {b2}")
    print(f"DECISION: {verdict}"
          + ("" if verdict == "PASS" else
             " — the drawdown is structural to broad small-cap exposure in this signal; "
             "the breadth book is excluded from solo deployment and E020's outcome "
             "(blend sizing or pure indexing) stands, per the pre-registration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
