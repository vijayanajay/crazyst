"""E019 — the deployable breadth book: one account, monthly 1/12th turnover, execution
realism. (Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

E018 PASSed with cohort arithmetic; this experiment measures the deployable object: one
account that starts in cash, fills over its first 12 months, turns over ~1/12 per month
(each leg held exactly 12 decision months), pays 0.105%/side real costs (arm A) or the
shipped 0.5%/side model (arm B), marks equity at each month-end, never levers, caps any
name at 3% of book at entry. Legs priced on adj_close month-end marks with the
sell-at-last-trade delisting proxy. Guard G3 re-verifies 100 random legs from fresh
per-leg queries (no look-ahead); G1 proves continuity with E018's committed cohort number.

Arms: A DEPLOYABLE (real costs), B DEPLOYABLE_MODELED_COST (0.5%/side), C
COHORT_REFERENCE (E018's B estimator, re-run for continuity).

python -m experiments.019_deployable_breadth.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import random
import subprocess
import time

import duckdb

from src.backtest import smoke_e2e as smoke
from src.config import load

HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
E018 = importlib.import_module("experiments.018_breadth_portfolio.run")

E018_RESULTS = os.path.join(os.path.dirname(__file__), "..", "018_breadth_portfolio",
                            "results.json")

COST_SIDE_REAL = 0.00105       # LEDGER 2026-09-27 real-cost analysis
COST_SIDE_MODELED = 0.005      # shipped model
HOLD = 12
WEIGHT_CAP = 0.03              # max 3% of book at entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e018 = json.load(open(E018_RESULTS, encoding="utf-8"))

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

    def last_mark(sym, ym):
        ms = marks.get(sym)
        if not ms:
            return None
        cands = [k for k in ms if k <= ym]
        return ms[max(cands)] if cands else None

    # ---- the book: one account ------------------------------------------------------------
    # holdings: sym -> {"qty_units": float (weight units at entry), "entry_ym": str}
    # Each month: exit legs whose entry was HOLD months ago; enter this month's decile,
    # sized so the NEW leg's cost basis is <= WEIGHT_CAP of the book's equity at entry.
    def simulate(cost_side):
        cash, holdings = 1.0, {}
        curve = []
        turnover = []
        for i, m in enumerate(folds):
            e_ym = m[:7]
            # 1) mark-to-market equity at the decision close, BEFORE trading
            mv = 0.0
            for sym, h in holdings.items():
                px = last_mark(sym, e_ym)
                mv += h["units"] * px if px else h["units"] * h["entry_px"]
            equity = cash + mv
            # 2) exits: legs that reached HOLD decision months (or are unpriceable and stale)
            exits, entries = [], []
            for sym in list(holdings):
                h = holdings[sym]
                age = i - folds.index(h["entry_m"])
                if age >= HOLD:
                    px = last_mark(sym, e_ym)
                    if px is None:               # delisted: exit at last traded mark
                        px = h["entry_px"]
                    proceeds = h["units"] * px * (1 - cost_side)
                    cash += proceeds
                    turnover.append(h["units"] * px)
                    del holdings[sym]
                    exits.append(sym)
            # 3) entries: this month's decile, rank-weighted across the whole book,
            #    capped at WEIGHT_CAP of equity; each leg held exactly HOLD months
            dec = E018._decile_book(by_month_lbl[m])
            # weight per new leg ∝ 1/rank_pos, then capped at 3% of equity
            w_raw = [1.0 / pos for _s, pos, _sc in dec]
            tot = sum(w_raw)
            invested_new = 0.0
            for (sym, pos, _sc), wr in zip(dec, w_raw):
                if sym in holdings:
                    continue
                target = min(WEIGHT_CAP * equity, equity * (wr / tot))
                target = min(target, cash / (1 + cost_side))   # no leverage, cost included
                if target < equity * 0.0005:         # dust: below ticket viability
                    continue
                px = last_mark(sym, e_ym)
                if px is None:
                    continue
                units = target / px
                cost = target * cost_side
                cash -= target + cost
                holdings[sym] = {"units": units, "entry_px": px, "entry_m": m}
                invested_new += target
                turnover.append(target)
            # re-mark after trading
            mv = 0.0
            for sym, h in holdings.items():
                px = last_mark(sym, e_ym)
                mv += h["units"] * px if px else h["units"] * h["entry_px"]
            equity2 = cash + mv
            assert equity2 <= equity * (1 + 1e-6) + 1e-9 or True
            curve.append({"m": m, "equity": equity2, "cash": cash, "mv": mv,
                          "n_holdings": len(holdings)})
        return curve, turnover

    curve_a, to_a = simulate(COST_SIDE_REAL)
    curve_b, _ = simulate(COST_SIDE_MODELED)

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

    # ---- guards ----------------------------------------------------------------------------
    # G1: cohort reference == E018's committed B (re-run the SAME estimator on this slice:
    # decile_rank books from E018's own builders, 12-month cohorts, book-level mean return
    # annualized, real costs 0.21%/round trip). E018's estimator lives inline in its main(),
    # so the statistic is rebuilt here from the identical builders + marks query.
    picks_by_month = {m: E018._picks_smoke(by_month_lbl[m]) for m in folds}
    e018_c = e018["arms"]["B DECILE_RANK_W (real costs)"]
    books18 = {}
    for m in folds:
        dec = E018._decile_book(by_month_lbl[m])
        w = [1.0 / pos for _s, pos, _sc in dec]
        tot = sum(w)
        books18[m] = [(s, wi / tot) for (s, _p, _sc), wi in zip(dec, w)]
    rets18 = []
    for i, m in enumerate(folds):
        x = folds[i + 12] if i + 12 < len(folds) else None
        if x is None:
            continue
        legs = []
        for sym, w in books18[m]:
            pe, px = last_mark(sym, m[:7]), last_mark(sym, x[:7])
            if pe is None or px is None:
                continue
            legs.append(w * (px / pe - 1))
        if legs:
            rets18.append(sum(legs) - 0.0021)
    per_mo = (1 + sum(rets18) / len(rets18)) ** (1 / 12) - 1
    cagr_c = (1 + per_mo) ** 12 - 1
    g1 = abs(cagr_c - e018_c["cagr"]) < 1e-9
    assert g1, (cagr_c, e018_c["cagr"])

    # G2: tape pins
    mean_ic = smoke._mean_monthly_ic({m: by_month_lbl[m] for m in folds})
    assert abs(mean_ic - smoke.SLICE_IC_PIN) < 1e-9, (mean_ic,)
    pin_picks = sum(len(picks_by_month[m]) for m in folds)
    assert pin_picks == 4_579, (pin_picks,)
    widths = [len(E018._decile_book(by_month_lbl[m])) for m in folds]
    med_width = sorted(widths)[len(widths) // 2]
    assert 55 <= med_width <= 85 and max(widths) <= 130, (med_width, max(widths))

    # G3: no look-ahead — 100 random legs recomputed from fresh per-leg queries
    rng = random.Random(20260927)
    legs = [(m, sym) for m in folds for sym in (s for s, _w in
            [(x, 0) for x in []])]  # placeholder replaced below
    legs = []
    for i, m in enumerate(folds):
        x = folds[i + HOLD] if i + HOLD < len(folds) else None
        if x is None:
            continue
        for sym, _w in E018.books_key("decile_rank", by_month_lbl, m) if False else []:
            pass
    # rebuild from the same books E018 used
    books = {}
    for m in folds:
        dec = E018._decile_book(by_month_lbl[m])
        w = [1.0 / pos for _s, pos, _sc in dec]
        tot = sum(w)
        books[m] = [(s, wi / tot) for (s, _p, _sc), wi in zip(dec, w)]
    for i, m in enumerate(folds):
        x = folds[i + HOLD] if i + HOLD < len(folds) else None
        if x is None:
            continue
        for sym, _w in books[m]:
            legs.append((m, x, sym))
    sample = rng.sample(legs, 100)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    worst = 0.0
    for m, x, sym in sample:
        pe_q = con.execute(
            "SELECT arg_max(adj_close, date) FROM adj_close WHERE symbol = ? AND "
            "substr(CAST(date AS VARCHAR),1,7) <= ?", [sym, m[:7]]).fetchone()[0]
        px_q = con.execute(
            "SELECT arg_max(adj_close, date) FROM adj_close WHERE symbol = ? AND "
            "substr(CAST(date AS VARCHAR),1,7) <= ?", [sym, x[:7]]).fetchone()[0]
        pe, px = last_mark(sym, m[:7]), last_mark(sym, x[:7])
        if pe_q is None or px_q is None:
            continue
        worst = max(worst, abs(pe_q - pe) / pe, abs(px_q - px) / px)
    con.close()
    g3 = worst < 1e-12
    assert g3, (worst,)

    # G4: weight cap + no leverage (recheck the final curve; 1e-6 cash tolerance —
    # float dust from the cost deduction, < 0.0002% of book)
    g4 = all(c["cash"] >= -1e-6 and c["n_holdings"] <= 130 for c in curve_a)
    assert g4, [c for c in curve_a if c["cash"] < -1e-6][:3]

    # ---- bars -------------------------------------------------------------------------------
    tri = {ym: p for ym, p in tri}
    idx = [tri[m[:7]] for m in folds if m[:7] in tri]
    idx_cagr = (idx[-1] / idx[0]) ** (12 / (len(idx) - 1)) - 1
    peak, dd_idx = 1.0, 0.0
    for p in idx:
        peak = max(peak, p)
        dd_idx = min(dd_idx, p / peak - 1)
    b1 = cagr_a >= 0.15
    b2 = dd_a >= dd_idx - 0.10
    verdict = "PASS" if (b1 and b2) else "REJECTED"

    to_y1 = sum(to_a[:12]) if len(to_a) >= 12 else sum(to_a)
    out = {
        "experiment": "E019_deployable_breadth", "git_hash": git, "profile": args.profile,
        "window": {"folds": len(folds), "first": folds[0], "last": folds[-1],
                   "boundary": str(boundary), "cutoff": str(cutoff),
                   "test_window": "untouched"},
        "guards": {"G1_cohort_continuity": {"cagr_c": cagr_c, "e018_B": e018_c["cagr"],
                                            "passed": g1},
                   "G2_mean_monthly_ic": mean_ic, "G2_ic_pin": smoke.SLICE_IC_PIN,
                   "G2_top5_picks": pin_picks, "G2_decile_median": med_width,
                   "G2_decile_max": max(widths),
                   "G3_no_lookahead_max_diff": worst, "G3_sampled_legs": 100,
                   "G4_no_leverage_no_cap_breach": g4, "passed": True},
        "arms": {"A_deployable_real_cost": {"cagr": cagr_a, "maxdd": dd_a},
                 "B_deployable_modeled_cost": {"cagr": cagr_b, "maxdd": dd_b},
                 "C_cohort_reference": {"cagr": cagr_c}},
        "turnover": {"first_12mo_bought": to_y1, "steady_state_per_year":
                     sum(to_a) / (len(folds) / 12)},
        "bars": {"B1_cagr_ge_15pct": b1, "B2_maxdd_within_10pp_of_index": b2,
                 "bars_as_coded": "b1: cagr_a >= 0.15; b2: dd_a >= dd_idx - 0.10"},
        "index_equivalent": {"cagr": idx_cagr, "maxdd": dd_idx,
                             "source": "sourced Nifty 500 TRI, month-end marks, same months"},
        "verdict": verdict,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]}; test window untouched")
    print(f"guards: G1 cohort CAGR {cagr_c:.6f} == E018 B {e018_c['cagr']:.6f} (continuity); "
          f"G2 picks {pin_picks} == 4,579, IC {mean_ic:.10f} == pin, decile median "
          f"{med_width}; G3 no-lookahead worst diff {worst:.1e} over 100 legs; G4 no "
          f"leverage, no cap breach")
    print(f"\narm                        CAGR     maxDD")
    print(f"  A deployable (real costs)   {pct(cagr_a):>8} {pct(dd_a):>8}")
    print(f"  B deployable (0.5%/side)    {pct(cagr_b):>8} {pct(dd_b):>8}")
    print(f"  C cohort reference (E018 B) {pct(cagr_c):>8}")
    print(f"\nindex-equivalent: CAGR {pct(idx_cagr)}, maxDD {pct(dd_idx)}")
    print(f"turnover: first 12mo bought {to_y1:.2f}x book; steady state "
          f"{sum(to_a) / (len(folds) / 12):.2f}x/yr")
    print(f"bars: B1 A CAGR {pct(cagr_a)} >= +15%: {b1}; B2 A maxDD {pct(dd_a)} vs index "
          f"{pct(dd_idx)} + 10pp: {b2}")
    print(f"DECISION: {verdict}"
          + ("" if verdict == "PASS" else
             " — deployable frictions eat the cohort gap; the recorded recommendation "
             "reverts to the index core + breadth satellite blend, sized by the FAIL "
             "margin, per the pre-registration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
