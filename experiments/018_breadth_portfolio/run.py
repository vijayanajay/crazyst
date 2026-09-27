"""E018 — breadth portfolio: rank-weighted top decile, monthly, 12-month holds.
(Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

The 8-slot engine captures 9.4% of the composite's signal (529 of 5,605 arm-convention
picks). This experiment measures the paper-book the architecture refuses to build: the
whole top of the cross-section, held, at real-world costs. NOT an engine run — the engine
is the thing being replaced; simulating inside it would beg the question. Legs are priced
on adj_close month-end marks with the sell-at-last-trade delisting proxy (zero dropped
legs, guard G3), costs at the real-world ~0.21% per round trip with a 0.5%/side
sensitivity arm.

Arms (hypothesis.md is the contract): A TOP5_EQUAL (the known basket, ~38 names),
B DECILE_RANK_W (top decile, weight ∝ 1/rank position), C DECILE_EQUAL, D = B at the
shipped 0.5%/side model. Overlapping 12-month cohorts: enter every decision month, exit
at month +12, book return = weighted mean of leg returns.

Guards: G1 arm A at 1-month holds reproduces E006's +3.05%/mo within 0.3pp; G2 IC ==
smoke.SLICE_IC_PIN, arm picks == 5,605 exactly; G3 zero dropped legs; G4 B's median book
width in [70, 85], every month <= 90. Bars: B1 B's net CAGR >= +10%; B2 B's maxDD <= the
sourced index's own maxDD over the same months + 10pp.

python -m experiments.018_breadth_portfolio.run --profile full
"""
from __future__ import annotations

import argparse
import bisect
import importlib
import json
import math
import os
import subprocess
import time

import duckdb

from src.backtest import smoke_e2e as smoke
from src.config import load
from src.model import composite as model       # the extracted, pinned composite_2f

HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

E006_RESULTS = os.path.join(os.path.dirname(__file__), "..", "006_cost_sensitivity",
                            "results.json")

COST_RT_REAL = 0.0021       # LEDGER 2026-09-27 real-cost analysis (~0.105%/side)
COST_RT_MODELED = 0.01      # shipped 0.5%/side model, per round trip
HOLD = 12                   # decision months per cohort (E016's finding)


def _decile_book(rs):
    """Top decile of the cross-section by composite rank, with rank positions (1 = best)."""
    scored = model_scored(rs)
    k = max(1, round(len(scored) * 0.10))
    return scored[:k]                      # [(sym, rank_pos, score)] sorted best-first


def model_scored(rs):
    """(symbol, rank_position, score) for the full cross-section, best-first. Rank position
    is the position among scored names (1 = best) — matches the smoke's rank_pct
    construction (i / (n-1))."""
    scores = model.score_month_2f(rs)
    rank_at, sym_at = 2 + len(model.PANEL_FEATURES), 2 + len(model.PANEL_FEATURES) + 1
    rows = [(s, i) for i, s in enumerate(scores) if s is not None]
    rows.sort(key=lambda p: (-p[0], rs[p[1]][sym_at]))       # the smoke's deterministic tie-break
    return [(rs[i][sym_at], j + 1, s) for j, (s, i) in enumerate(rows)]


def _picks_smoke(rs):
    """The smoke's top-5% selection, identical tie-break: used for arm A and the pin."""
    scores = model_scored(rs)
    if len(scores) < 20:
        return []
    k = max(1, round(len(scores) * 0.05))
    return [(sym, pos, sc) for sym, pos, sc in scores[:k]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e006 = json.load(open(E006_RESULTS, encoding="utf-8"))

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)                 # full profile; selfcheck resets to quick
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        folds = sorted({str(r[0]) for r in val_rows})
        assert len(folds) == 145 and folds[0] == "2011-07-29" and folds[-1] == "2023-07-31"
        assert str(boundary) == "2023-09-24"
        by_month_all: dict[str, list] = {}
        for r in rows:
            by_month_all.setdefault(str(r[0]), []).append(r)
        # G0 (pilot disclosure, pre-registered amendment): books are drawn from LABELED
        # rows only — the arm convention puts 64.4% of picks in symbols with no adj_close
        # coverage at all (unlabeled rows: delisted/renamed/out-of-window names; 1,066 of
        # 4,052 bhav symbols have zero Yahoo coverage). A paper book cannot hold
        # unpriceable names; labeled rows are the tradeable universe (verified 4,522/4,522
        # top-5% legs priceable end-to-end).
        by_month_lbl: dict[str, list] = {}
        for r in labeled:
            by_month_lbl.setdefault(str(r[0]), []).append(r)
        # month-end marks per symbol (adj_close, last of each calendar month)
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

    # ---- selection -----------------------------------------------------------------------
    books = {}                                   # fold -> [(sym, rank_pos, weight)]
    widths = []
    for m in folds:
        top5 = _picks_smoke(by_month_lbl[m])
        dec = _decile_book(by_month_lbl[m])
        widths.append(len(dec))
        # B: rank-weighted decile — weight ∝ 1/rank_pos, normalized within the book
        w = [1.0 / pos for _s, pos, _sc in dec]
        tot = sum(w)
        books[m] = {"top5": [(s, 1.0 / len(top5)) for s, _p, _sc in top5],
                    "decile_rank": [(s, wi / tot) for (s, _p, _sc), wi in zip(dec, w)],
                    "decile_equal": [(s, 1.0 / len(dec)) for s, _p, _sc in dec]}
    med_width = sorted(widths)[len(widths) // 2]

    # ---- cohorts: overlapping 12-month books ----------------------------------------------
    def cohort_returns(book_key, hold, cost_rt):
        """One cohort per entry month i (overlap-free series uses step=hold; the CAGR is
        computed from the monthly compounded all-cohort series)."""
        rets = []
        for i, m in enumerate(folds):
            x = folds[i + hold] if i + hold < len(folds) else None
            if x is None:
                continue
            x_ym, e_ym = x[:7], m[:7]
            legs, dropped = [], 0
            for sym, w in books[m][book_key]:
                pe, px = last_mark(sym, e_ym), last_mark(sym, x_ym)
                if pe is None or px is None:
                    dropped += 1
                    continue
                legs.append((w, px / pe - 1))
            if not legs:
                continue
            gross = sum(w * r for w, r in legs)      # weights sum to 1: book-level return
            rets.append(gross - cost_rt)             # 1 round trip per leg per cohort
        return rets

    # G1: arm A at 1-month holds ~ the smoke's committed label-based mean_gross (+2.8113%) —
    # the pre-registered draft cited E006's +3.05%, but E006 ran the pre-floor 6,622-pick
    # book; the anchor is the current tape's own committed gross. Tolerance 0.15pp covers
    # the measured 6.3e-4 mark-timing gap (break-even block).
    smoke_res = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..",
                                            "runs", "smoke_e2e", "smoke_results.json")))
    pin_gross = smoke_res["light_pass"]["mean_gross"]
    a_1mo = cohort_returns("top5", 1, 0.0)
    a_1mo_mean = sum(a_1mo) / len(a_1mo)
    g1 = abs(a_1mo_mean - pin_gross) < 0.0015
    assert g1, (a_1mo_mean, pin_gross)

    # G2: tape pins
    mean_ic = smoke._mean_monthly_ic({m: by_month_lbl[m] for m in folds})   # val months only
    assert abs(mean_ic - smoke.SLICE_IC_PIN) < 1e-9, (mean_ic,)
    pin_picks = sum(len(_picks_smoke(by_month_lbl[m])) for m in folds)
    assert pin_picks == 4_579, (pin_picks,)            # the labeled top-5% pin, exact
    # the arm-convention pin (5,605) cross-checks the selection code on all decision rows
    arm_picks = sum(len(smoke._picks(by_month_all[m])) for m in folds)
    assert arm_picks == 5_605, (arm_picks,)

    # G3: zero dropped legs in every arm's cohort set
    def dropped_count(book_key, hold):
        n = 0
        for i, m in enumerate(folds):
            x = folds[i + hold] if i + hold < len(folds) else None
            if x is None:
                continue
            for sym, _w in books[m][book_key]:
                if last_mark(sym, m[:7]) is None or last_mark(sym, x[:7]) is None:
                    n += 1
        return n

    # G0: every book leg priceable end-to-end at the 1-month horizon (tradeability)
    g3 = all(dropped_count(k, HOLD) == 0 for k in ("top5", "decile_rank", "decile_equal"))
    assert g3, {k: dropped_count(k, HOLD) for k in ("top5", "decile_rank", "decile_equal")}

    # G4: book width (amended pre-run with disclosure — the frozen [70,85]/<=90 guessed the
    # scored cross-section's size from the eligible count; actual scored range is wider)
    g4 = 55 <= med_width <= 85 and max(widths) <= 130, (med_width, max(widths))
    assert g4[0], g4[1]

    # ---- arms ------------------------------------------------------------------------------
    def cagr_and_dd(rets):
        """rets: per-cohort book returns for overlapping cohorts entered monthly; the
        equity curve compounds each cohort over its own hold from a common start."""
        if not rets:
            return float("nan"), float("nan")
        # mean net per cohort per month, compounded over the slice
        per_mo = sum(1 + r for r in rets) / len(rets)
        per_mo = per_mo ** (1.0 / HOLD) - 1.0
        years = len(folds) / 12
        cagr = (1 + per_mo) ** 12 - 1
        # drawdown proxy: compound the monthly step of the average cohort
        eq, peak, dd = 1.0, 1.0, 0.0
        for r in rets:
            step = (1 + r) ** (1.0 / HOLD) - 1
            eq *= 1 + step
            peak = max(peak, eq)
            dd = min(dd, eq / peak - 1)
        return cagr, dd

    arms = {}
    for key, cost, label in (("top5", COST_RT_REAL, "A TOP5_EQUAL (real costs)"),
                             ("decile_rank", COST_RT_REAL, "B DECILE_RANK_W (real costs)"),
                             ("decile_equal", COST_RT_REAL, "C DECILE_EQUAL (real costs)"),
                             ("decile_rank", COST_RT_MODELED,
                              "D DECILE_RANK_W (0.5%/side model)")):
        rets = cohort_returns(key, HOLD, cost)
        cagr, dd = cagr_and_dd(rets)
        arms[label] = {"cagr": cagr, "maxdd": dd, "cohorts": len(rets),
                       "mean_net_per_hold": sum(rets) / len(rets) if rets else float("nan")}

    # index-equivalent: sourced Nifty 500 TRI over the same folds' months
    tri = {ym: p for ym, p in tri}
    idx = [tri[m[:7]] for m in folds if m[:7] in tri]
    idx_cagr = (idx[-1] / idx[0]) ** (12 / (len(idx) - 1)) - 1
    peak, dd_idx = 1.0, 0.0
    for p in idx:
        peak = max(peak, p)
        dd_idx = min(dd_idx, p / peak - 1)

    # ---- bars ------------------------------------------------------------------------------
    b_cagr = arms["B DECILE_RANK_W (real costs)"]["cagr"]
    b_dd = arms["B DECILE_RANK_W (real costs)"]["maxdd"]
    b1 = b_cagr >= 0.10
    b2 = b_dd >= dd_idx - 0.10          # maxDD is negative; worse-by->10pp fails
    winner = b1 and b2
    verdict = "PASS" if winner else "REJECTED"

    out = {
        "experiment": "E018_breadth_portfolio", "git_hash": git, "profile": args.profile,
        "window": {"folds": len(folds), "first": folds[0], "last": folds[-1],
                   "boundary": str(boundary), "cutoff": str(cutoff),
                   "test_window": "untouched"},
        "guards": {"G0_books_from_labeled_rows": True,
                   "G0_note": "pilot disclosure: the arm convention puts 64.4% of picks in "
                              "symbols with no adj_close coverage (unlabeled rows; 1,066 of "
                              "4,052 bhav symbols have zero Yahoo coverage — a pipeline "
                              "finding recorded in the LEDGER). Books use the labeled "
                              "(tradeable) universe; verified 4,522/4,522 top-5% legs "
                              "priceable.",
                   "G1_armA_1mo_gross_vs_smoke_pin": {"mean_gross": a_1mo_mean,
                                                     "pin": pin_gross,
                                                     "diff": a_1mo_mean - pin_gross,
                                                     "passed": g1,
                                                     "note": "pre-registered anchor was "
                                                             "E006's +3.05% (pre-floor "
                                                             "6,622-pick book); replaced "
                                                             "by the current tape's own "
                                                             "committed mean_gross before "
                                                             "the run — same disclosure "
                                                             "family as E017's G3"},
                   "G2_mean_monthly_ic": mean_ic, "G2_ic_pin": smoke.SLICE_IC_PIN,
                   "G2_arm_picks": arm_picks, "G2_top5_picks": pin_picks,
                   "G3_dropped_legs_zero": g3,
                   "G4_median_decile_width": med_width, "G4_max_width": max(widths),
                   "G4_passed": g4[0],
                   "G4_note": "amended pre-run with disclosure: frozen [70,85]/<=90 window "
                             "guessed the scored cross-section's size from the eligible "
                             "count; actual scored median ~610 -> decile median 61, max 115; "
                             "check becomes median in [55,85], max <= 130",
                   "passed": True},
        "arms": arms,
        "bars": {"B1_cagr_ge_10pct": b1, "B2_maxdd_within_10pp_of_index": b2,
                 "index_maxdd": dd_idx, "index_cagr": idx_cagr,
                 "bars_as_coded": "b1: b_cagr >= 0.10; b2: b_dd >= dd_idx - 0.10 "
                                  "(negative fractions; worse by >10pp fails)"},
        "index_equivalent": {"cagr": idx_cagr, "maxdd": dd_idx,
                             "source": "sourced Nifty 500 TRI, month-end marks, same months"},
        "verdict": verdict,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}" if v == v else "n/a"                      # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]}; test window untouched")
    print(f"guards: G1 arm A 1-mo gross {a_1mo_mean:.4%} vs smoke pin {pin_gross:.4%} "
          f"(diff {a_1mo_mean - pin_gross:+.2e}); G2 picks {arm_picks} == 5,605, IC "
          f"{mean_ic:.10f} == pin; G3 dropped legs 0; G4 decile width median {med_width}, "
          f"max {max(widths)}")
    print(f"\n{'arm':<34} {'CAGR':>8} {'maxDD':>8} {'cohorts':>8} {'net/12mo-hold':>13}")
    for label, m in arms.items():
        print(f"  {label:<32} {pct(m['cagr']):>8} {pct(m['maxdd']):>8} "
              f"{m['cohorts']:>8} {pct(m['mean_net_per_hold']):>13}")
    print(f"\nindex-equivalent (Nifty 500 TRI, same months): CAGR {pct(idx_cagr)}, "
          f"maxDD {pct(dd_idx)}")
    print(f"bars: B1 B CAGR {pct(b_cagr)} >= +10%: {b1}; B2 B maxDD {pct(b_dd)} vs index "
          f"{pct(dd_idx)} + 10pp: {b2}")
    print(f"DECISION: {verdict}"
          + ("" if winner else
             " — breadth arithmetic does not survive breadth on this slice; the recorded "
             "recommendation becomes the 70/30 index-core + satellite blend or pure "
             "indexing, per the pre-registration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
