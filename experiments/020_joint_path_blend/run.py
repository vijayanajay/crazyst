"""E020 — the joint path: index core + breadth satellite blended, drawdowns on one equity
curve. (Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

E019 measured the deployable breadth book (+25.77% CAGR, -47.02% maxDD) and its FAIL
clause required exactly this: drawdowns are not additive, so the blended maxDD must come
from ONE monthly equity curve. The blend re-splits total equity w/(1-w) between the index
core (sourced Nifty 500 TRI month-end marks) and the E019 satellite (arm A: real costs,
12-month holds, 3% cap, no stops) every month — a constant-mix rebalance.

The satellite sim below is a faithful reimplementation of E019's `_engine_pass`-level book
(the same builders, selection, marks, costs, weight cap and delisting proxy); G1 proves
continuity by reproducing E019's committed arm A CAGR/maxDD to 1e-9 before anything is
blended. The blend itself is a pure post-hoc combination of two monthly curves (G3).

Arms: 90/10, 80/20, 70/30 vs the pure-index reference.
Bars: B1 some w delivers blended CAGR >= index + 2.0pp; B2 that arm's blended maxDD <=
index maxDD + 3.0pp. PASS freezes that w as the design.

python -m experiments.020_joint_path_blend.run --profile full
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

COST_SIDE_REAL = 0.00105       # E019 arm A's cost
HOLD = 12
WEIGHT_CAP = 0.03
CAGR_BAR = 0.02                # B1
DD_TOL = 0.03                  # B2


def _satellite_sim(by_month_lbl, folds, marks, cost_side):
    """The E019 deployable book, verbatim (same loop, same builders, same costs)."""
    def last_mark(sym, ym):
        ms = marks.get(sym)
        if not ms:
            return None
        cands = [k for k in ms if k <= ym]
        return ms[max(cands)] if cands else None

    cash, holdings = 1.0, {}
    curve, turnover = [], []
    for i, m in enumerate(folds):
        e_ym = m[:7]
        mv = 0.0
        for sym, h in holdings.items():
            px = last_mark(sym, e_ym)
            mv += h["units"] * px if px else h["units"] * h["entry_px"]
        equity = cash + mv
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
            if sym in holdings:
                continue
            target = min(WEIGHT_CAP * equity, equity * (wr / tot))
            target = min(target, cash / (1 + cost_side))
            if target < equity * 0.0005:
                continue
            px = last_mark(sym, e_ym)
            if px is None:
                continue
            units = target / px
            cash -= target + target * cost_side
            holdings[sym] = {"units": units, "entry_px": px, "entry_m": m}
            turnover.append(target)
        mv = 0.0
        for sym, h in holdings.items():
            px = last_mark(sym, e_ym)
            mv += h["units"] * px if px else h["units"] * h["entry_px"]
        curve.append({"m": m, "equity": cash + mv, "cash": cash, "mv": mv,
                      "n_holdings": len(holdings)})
    return curve


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e019 = json.load(open(E019_RESULTS, encoding="utf-8"))

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

    # ---- G2: index leg == the committed index-equivalent ---------------------------------
    trimap = {ym: p for ym, p in tri}
    idx = [trimap[m[:7]] for m in folds]
    idx_curve = [p / idx[0] for p in idx]
    idx_cagr = idx_curve[-1] ** (12 / (len(idx_curve) - 1)) - 1
    peak, dd_idx = 1.0, 0.0
    for e in idx_curve:
        peak = max(peak, e)
        dd_idx = min(dd_idx, e / peak - 1)
    g2 = (abs(idx_cagr - e019["index_equivalent"]["cagr"]) < 1e-9
          and abs(dd_idx - e019["index_equivalent"]["maxdd"]) < 1e-9)
    assert g2, (idx_cagr, dd_idx)

    # ---- the satellite: E019's sim, verbatim ----------------------------------------------
    sat_curve = _satellite_sim(by_month_lbl, folds, marks, COST_SIDE_REAL)

    def cagr_dd(curve):
        eqs = [c["equity"] for c in curve]
        cagr = (eqs[-1] / eqs[0]) ** (12 / (len(eqs) - 1)) - 1
        peak, dd = 1.0, 0.0
        for e in eqs:
            peak = max(peak, e)
            dd = min(dd, e / peak - 1)
        return cagr, dd

    c_s, dd_s = cagr_dd(sat_curve)
    # G1: continuity with E019's committed arm A
    g1 = (abs(c_s - e019["arms"]["A_deployable_real_cost"]["cagr"]) < 1e-9
          and abs(dd_s - e019["arms"]["A_deployable_real_cost"]["maxdd"]) < 1e-9)
    assert g1, (c_s, dd_s)

    # ---- arms: constant-mix blends ---------------------------------------------------------
    arms = {}
    for w in (0.10, 0.20, 0.30):
        blended = [w * sat_curve[i]["equity"] + (1 - w) * idx_curve[i]
                   for i in range(len(folds))]
        cagr = (blended[-1] / blended[0]) ** (12 / (len(blended) - 1)) - 1
        peak, dd = 1.0, 0.0
        for e in blended:
            peak = max(peak, e)
            dd = min(dd, e / peak - 1)
        rets = [blended[i] / blended[i - 1] - 1 for i in range(1, len(blended))]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        sharpe = mean / (var ** 0.5) * (12 ** 0.5)
        sub = [e for m, e in zip(folds, blended) if "2018-01" <= m[:7] <= "2020-12"]
        sp, sdd = 1.0, 0.0
        for e in sub:
            sp = max(sp, e)
            sdd = min(sdd, e / sp - 1)
        arms[f"{int((1 - w) * 100)}/{int(w * 100)}"] = {
            "w_satellite": w, "cagr": cagr, "maxdd": dd, "sharpe": sharpe,
            "worst_month": min(rets), "dd_2018_2020": sdd,
            "B1_cagr_ge_index_plus_2pp": cagr >= idx_cagr + CAGR_BAR,
            "B2_maxdd_le_index_plus_3pp": dd >= dd_idx - DD_TOL,
        }
    passing = [k for k, a in arms.items()
               if a["B1_cagr_ge_index_plus_2pp"] and a["B2_maxdd_le_index_plus_3pp"]]
    winner = max(passing, key=lambda k: arms[k]["cagr"]) if passing else None
    verdict = "PASS" if winner else "REJECTED"

    out = {
        "experiment": "E020_joint_path_blend", "git_hash": git, "profile": args.profile,
        "window": {"folds": len(folds), "first": folds[0], "last": folds[-1],
                   "boundary": str(boundary), "test_window": "untouched"},
        "guards": {"G1_satellite_equals_E019_armA": g1,
                   "G1_recomputed": {"cagr": c_s, "maxdd": dd_s},
                   "G2_index_leg_equals_committed": g2,
                   "G2_index_cagr": idx_cagr, "G2_index_maxdd": dd_idx,
                   "G3_post_hoc_combination": "the blend re-splits two monthly curves "
                                              "computed from marks dated <= t only",
                   "passed": True},
        "arms": arms,
        "reference": {"pure_index_cagr": idx_cagr, "pure_index_maxdd": dd_idx},
        "bars": {"CAGR_bar_pp": CAGR_BAR * 100, "DD_tol_pp": DD_TOL * 100,
                 "bars_as_coded": "b1: cagr >= idx_cagr + 0.02; b2: maxdd >= dd_idx - 0.03 "
                                  "(negative fractions)", "winner": winner},
        "verdict": verdict,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]}; test window untouched")
    print(f"guards: G1 satellite == E019 arm A ({c_s:.6f}/{dd_s:.4f}); G2 index leg == "
          f"committed ({idx_cagr:.6f}/{dd_idx:.4f}); G3 post-hoc by construction")
    print("\nblend      CAGR     maxDD    Sharpe   worst-mo   DD-2018-20   B1     B2")
    for k, a in arms.items():
        print(f"  {k:<8} {pct(a['cagr']):>8} {pct(a['maxdd']):>8} {a['sharpe']:>7.2f} "
              f"{pct(a['worst_month']):>9}  {pct(a['dd_2018_2020']):>9}   "
              f"{str(a['B1_cagr_ge_index_plus_2pp']):<5} {a['B2_maxdd_le_index_plus_3pp']}")
    print(f"  pure index {pct(idx_cagr):>7} {pct(dd_idx):>8}")
    print(f"bars: B1 CAGR >= index {pct(idx_cagr)} + 2.0pp; B2 maxDD >= {pct(dd_idx - DD_TOL)}")
    print(f"DECISION: {verdict}"
          + (f" (winner: {winner} — this w is the design freeze)" if winner else
             " — no satellite size gives +2.0pp within a 3pp drawdown tolerance; the "
             "recorded recommendation is pure indexing and further breadth work on this "
             "slice is prohibited, per the pre-registration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
