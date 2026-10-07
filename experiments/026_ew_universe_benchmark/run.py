"""E026 — the equal-weight universe benchmark (REPORTING; pre-registered hypothesis.md).

The program benchmarks against cap-weighted Nifty 500 TRI but trades the as-of
top-1500-by-liquidity universe. This experiment computes the missing denominator: the
monthly-rebalanced equal-weight return of the as-of eligible universe itself (adj_me
panel), side by side with E018's breadth book (arm B, reproduced and pinned) and the
sourced Nifty 500 TRI, over the 145-month validation slice and the 35-month test
window. No bars, no adoption — the deliverable is the table and the honest reading of
the B−EW gap.

Amendment disclosed pre-run (measured 2026-10-01 before this runner existed): the
cutoff-derived split moved with the tape (boundary 2023-09-24 → 2023-10-01; val
145 → 146 folds; test window shifted to 2023-09-29 → 2026-07-31). All pins are
reproduced on the exact 145-fold subset E018 pinned (val folds ≤ 2023-07-31).

python -m experiments.026_ew_universe_benchmark.run --profile full     # the run
python -m experiments.026_ew_universe_benchmark.run --self-check       # hand-computed fixture
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

from src.backtest import smoke_e2e as smoke
from src.config import load
from src.model import composite as model

HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
E018 = importlib.import_module("experiments.018_breadth_portfolio.run")

E018_SAT = 2 + len(model.PANEL_FEATURES) + 1   # symbol column in the matrix row tuples
COST_RT_REAL = 0.0021        # E018's real-cost round trip (leg B only)
HOLD = 12
COVER_FLAG = 0.80            # G5: months below this marked share are flagged

# committed pins (results.json of E018; smoke_e2e.SLICE_IC_PIN)
PIN_IDX_CAGR_145 = 0.13174664181300377
PIN_B_CAGR_145 = 0.296444033001356
PIN_TEST_BENCH = 0.12457495616414915     # E020-C's committed harness benchmark (OLD window)


# ---- pure helpers (self-checked below) --------------------------------------------------------

def ew_month(marks: dict, members: set, m: str, m1: str) -> tuple[float | None, int, int]:
    """EW monthly return of `members` over m -> m+1 from month-end marks; mean over
    members with BOTH marks (the E018 last_mark convention). Returns (ret, n_members,
    n_marked)."""
    rets = []
    for s in members:
        ms = marks.get(s)
        p0 = ms.get(m) if ms else None
        p1 = ms.get(m1) if ms else None
        if p0 and p1:
            rets.append(p1 / p0 - 1.0)
    return (sum(rets) / len(rets) if rets else None), len(members), len(rets)


def equity_from_rets(rets: list[float]) -> list[float]:
    """Equity at each fold date: eq[0]=1, then compounding. len == len(rets)+1."""
    eq, v = [1.0], 1.0
    for r in rets:
        v *= 1.0 + r
        eq.append(v)
    return eq


def series_cagr(eq: list[float]) -> float:
    """E018's index formula: (last/first) ** (12/(n_marks-1)) - 1."""
    return (eq[-1] / eq[0]) ** (12.0 / (len(eq) - 1)) - 1.0


def series_maxdd(eq: list[float]) -> float:
    peak, dd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1.0)
    return dd


def cohort_rets_from_equity(eq: list[float]) -> list[float]:
    """Overlapping HOLD-month cohorts on a compounded series: eq[i+HOLD]/eq[i]-1."""
    return [eq[i + HOLD] / eq[i] - 1.0 for i in range(len(eq) - HOLD)]


def cagr_from_cohorts(rets: list[float]) -> float:
    """E018's cohort estimator: mean cohort total -> per-month -> annualized."""
    per_mo = sum(1.0 + r for r in rets) / len(rets)
    return per_mo ** (12.0 / HOLD) - 1.0


def maxdd_from_cohorts(rets: list[float]) -> float:
    """E018's drawdown proxy: compound each cohort's monthly step in entry order."""
    eq, peak, dd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= 1.0 + (1.0 + r) ** (1.0 / HOLD) - 1.0
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1.0)
    return dd


def yearly_table(folds: list[str], ew_rets: list[float], tri_marks: list[float],
                 b12_pairs: list[tuple[str, float]],
                 b1mo_pairs: list[tuple[str, float]]) -> list[dict]:
    """Per-calendar-year leg returns over one fold window (the 2026-10-01 amendment,
    verdict.md AMENDMENT section; the program review's yearly-table form).

    Conventions, per leg: ew/tri compound the n-1 consecutive fold-pair returns of the
    year (identical month alignment by construction); B-12mo compounds the (1+r)^(1/12)
    cohort steps of cohorts ENTERED in the year (E018's own drawdown-proxy convention,
    extended per year); B-1mo (the matched-estimator book: decile, 1-month holds, real
    costs) compounds its monthly returns. gap = (1+B) - (1+EW) in growth-factor space.
    Partial years (2011 from July, 2023 to July) are marked partial = False/True by
    month count, not hidden."""
    n = len(folds)
    assert len(ew_rets) == n - 1 and len(tri_marks) == n, (len(ew_rets), n)
    tri_rets = [tri_marks[i + 1] / tri_marks[i] - 1.0 for i in range(n - 1)]
    b12_by_year: dict[str, list[float]] = {}
    for m, r in b12_pairs:
        b12_by_year.setdefault(m[:4], []).append((1.0 + r) ** (1.0 / HOLD) - 1.0)
    b1mo_by_year: dict[str, list[float]] = {}
    for m, r in b1mo_pairs:
        b1mo_by_year.setdefault(m[:4], []).append(r)

    def prod(xs):
        out = 1.0
        for x in xs:
            out *= 1.0 + x
        return out

    rows = []
    for y in sorted({m[:4] for m in folds}):
        idx = [i for i, m in enumerate(folds[:-1]) if m[:4] == y]
        ew_yr = prod([ew_rets[i] for i in idx]) - 1.0
        tri_yr = prod([tri_rets[i] for i in idx]) - 1.0
        b12_yr = prod(b12_by_year.get(y, [])) - 1.0
        b1_yr = prod(b1mo_by_year.get(y, [])) - 1.0
        rows.append({"year": y, "months": len(idx) + 1,
                     "partial": len(idx) + 1 < 12,
                     "ew_eligible": ew_yr, "nifty500_tri": tri_yr,
                     "b_12mo": b12_yr, "b_1mo_matched": b1_yr,
                     "gap_12mo": (1.0 + b12_yr) - (1.0 + ew_yr),
                     "gap_matched": (1.0 + b1_yr) - (1.0 + ew_yr)})
    return rows


def self_check() -> int:
    """Hand-computed fixture: EW mean with a missing mark, equity/series math, the
    cohort estimator, and the drawdown proxy — all to exact values."""
    marks = {"A": {"2026-01-31": 100.0, "2026-02-29": 110.0},
             "B": {"2026-01-31": 50.0, "2026-02-29": 45.0},
             "C": {"2026-01-31": 10.0}}                      # C has no Feb mark
    ret, n, marked = ew_month(marks, {"A", "B", "C"}, "2026-01-31", "2026-02-29")
    # A +10%, B -10%, C unmarked -> mean 0.0 over 2 of 3 members
    assert abs(ret - 0.0) < 1e-12 and (n, marked) == (3, 2), (ret, n, marked)
    eq = equity_from_rets([0.1, -0.1, 0.3])
    assert [round(v, 10) for v in eq] == [1.0, 1.1, 0.99, 1.287], eq
    assert abs(series_cagr(eq) - (1.287 ** 4 - 1)) < 1e-12        # 12/(4-1)=4 annualization
    assert abs(series_maxdd(eq) - (0.99 / 1.1 - 1.0)) < 1e-12     # peak 1.1 -> 0.99
    cr = cohort_rets_from_equity(eq)                              # HOLD=12 -> needs 13 marks
    eq13 = equity_from_rets([0.01] * 12 + [-0.02] * 2)            # 15 marks -> 3 cohorts
    cr13 = cohort_rets_from_equity(eq13)
    assert len(cr13) == 3 and abs(cr13[0] - (1.01 ** 12 - 1)) < 1e-12, cr13
    assert abs(cr13[2] - (eq13[14] / eq13[2] - 1)) < 1e-12, cr13
    # cohort estimator on two known cohorts: mean(1+r) -> per-month -> annualized
    two = [0.25, 1.0]                                             # mean 1.125^(1/12)^12
    exact = (sum(1.0 + r for r in two) / 2) ** (12.0 / HOLD) - 1.0
    assert abs(cagr_from_cohorts(two) - exact) < 1e-15
    dd = maxdd_from_cohorts([-0.5, 0.0])
    step = (1.0 - 0.5) ** (1.0 / HOLD) - 1.0
    assert abs(dd - step) < 1e-12, dd                             # one down cohort -> dd = step
    print("PASS: 026 self-check (EW month with uncovered member, equity/series math, "
          "cohort estimator, drawdown proxy)", flush=True)
    return 0


# ---- the run -----------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        marks_raw = con.execute(
            "SELECT symbol, substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(adj_close, date) "
            "FROM adj_close GROUP BY symbol, ym").fetchall()
        tri_raw = con.execute(
            "SELECT substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(tri, date) FROM index_tri "
            "WHERE index_name = 'NIFTY 500' GROUP BY ym ORDER BY ym").fetchall()
    finally:
        con.close()

    # G1: the measured amendment (frozen in hypothesis.md)
    val_folds = sorted({str(r[0]) for r in val_rows})
    test_folds = sorted({str(r[0]) for r in test_rows})
    sub145 = [m for m in val_folds if m <= "2023-07-31"]
    assert str(boundary) == "2023-10-01", boundary
    assert len(val_folds) == 146 and val_folds[0] == "2011-07-29" and val_folds[-1] == "2023-08-31"
    assert len(test_folds) == 35 and test_folds[0] == "2023-09-29" and test_folds[-1] == "2026-07-31"
    assert len(sub145) == 145 and sub145[0] == "2011-07-29" and sub145[-1] == "2023-07-31"

    by_month_lbl: dict[str, list] = {}
    for r in labeled:
        by_month_lbl.setdefault(str(r[0]), []).append(r)
    by_month_all: dict[str, list] = {}
    for r in rows:
        by_month_all.setdefault(str(r[0]), []).append(r)

    # G2: tape pins on the exact 145-fold subset E018 pinned
    mean_ic = smoke._mean_monthly_ic({m: by_month_lbl[m] for m in sub145})
    assert abs(mean_ic - smoke.SLICE_IC_PIN) < 1e-9, (mean_ic, smoke.SLICE_IC_PIN)
    picks5 = sum(len(E018._picks_smoke(by_month_lbl[m])) for m in sub145)
    assert picks5 == 4_579, (picks5,)
    picks_arm = sum(len(smoke._picks(by_month_all[m])) for m in sub145)
    assert picks_arm == 5_605, (picks_arm,)

    # E018's marks (adj_close arg_max per ym) for the book leg
    marks_ym: dict[str, dict[str, float]] = {}
    for s, ym, p in marks_raw:
        if p and p > 0:
            marks_ym.setdefault(s, {})[ym] = p

    def last_mark(sym, ym):
        ms = marks_ym.get(sym)
        cands = [k for k in ms if k <= ym] if ms else []
        return ms[max(cands)] if cands else None

    tri = {ym: p for ym, p in tri_raw}

    # ---- the two windows -----------------------------------------------------------------------
    def run_window(folds: list[str], label: str) -> dict:
        """All four legs on one fold window; returns the results.json block."""
        # legs 1-2: EW series from the adj_me panel (as-of membership at each fold)
        fold_dates = folds
        con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
        try:
            adj_me = HARNESS._month_end_adj_closes(con, fold_dates)
        finally:
            con.close()

        def ew_leg(members_of):
            rets, cover, flagged = [], {}, []
            for i, m in enumerate(fold_dates[:-1]):
                r, n, k = ew_month(adj_me, members_of(m), m, fold_dates[i + 1])
                assert r is not None, (label, m, n, k)   # a 1500-name EW month cannot be empty
                rets.append(r)
                cover[m] = {"members": n, "marked": k, "share": k / n if n else 0.0}
                if n and k / n < COVER_FLAG:
                    flagged.append(m)
            eq = equity_from_rets(rets)
            cohorts = cohort_rets_from_equity(eq)
            return {"series_cagr": series_cagr(eq), "series_maxdd": series_maxdd(eq),
                    "cohort_cagr": cagr_from_cohorts(cohorts), "n_cohorts": len(cohorts),
                    "mean_monthly": sum(rets) / len(rets),
                    "monthly": rets,
                    "cover_min_share": min(c["share"] for c in cover.values()),
                    "months_below_80pct_cover": flagged, "cover": cover}

        leg_elig = ew_leg(lambda m: eliq.get(m, set()))
        leg_lbl = ew_leg(lambda m: {r[E018_SAT] for r in by_month_lbl.get(m, [])})

        # leg 3: E018 arm B reproduced (decile, rank-weighted, 12-mo cohorts, real costs)
        books = {}
        for m in fold_dates:
            dec = E018._decile_book(by_month_lbl[m])
            w = [1.0 / pos for _s, pos, _sc in dec]
            tot = sum(w)
            books[m] = [(s, wi / tot) for (s, _p, _sc), wi in zip(dec, w)]
        b_rets, dropped = [], 0
        for i, m in enumerate(fold_dates):
            x = fold_dates[i + HOLD] if i + HOLD < len(fold_dates) else None
            if x is None:
                continue
            legs = []
            for sym, w in books[m]:
                pe, px = last_mark(sym, m[:7]), last_mark(sym, x[:7])
                if pe is None or px is None:
                    dropped += 1
                    continue
                legs.append((w, px / pe - 1.0))
            if legs:
                b_rets.append(sum(w * r for w, r in legs) - COST_RT_REAL)
        leg_b = {"cagr": cagr_from_cohorts(b_rets), "maxdd": maxdd_from_cohorts(b_rets),
                 "cohorts": len(b_rets)}

        # the matched-estimator book (AMENDMENT leg): same decile books at 1-month holds,
        # real costs — B's selection on the EW benchmark's own accounting
        b1_rets, dropped1 = [], 0
        for i, m in enumerate(fold_dates[:-1]):
            x = fold_dates[i + 1]
            legs = []
            for sym, w in books[m]:
                pe, px = last_mark(sym, m[:7]), last_mark(sym, x[:7])
                if pe is None or px is None:
                    dropped1 += 1
                    continue
                legs.append((w, px / pe - 1.0))
            if legs:
                b1_rets.append(sum(w * r for w, r in legs) - COST_RT_REAL)
        leg_b1 = {"cagr": series_cagr(equity_from_rets(b1_rets)),
                  "mean_monthly": sum(b1_rets) / len(b1_rets)}
        b12_pairs = [(fold_dates[i], r) for i, r in enumerate(b_rets)]
        b1mo_pairs = [(fold_dates[i], r) for i, r in enumerate(b1_rets)]

        # leg 4: sourced Nifty 500 TRI on the same fold months
        idx = [tri[m[:7]] for m in fold_dates if m[:7] in tri]
        assert len(idx) == len(fold_dates), (label, len(idx), len(fold_dates))
        leg_idx = {"cagr": series_cagr(idx), "maxdd": series_maxdd(idx), "marks": len(idx)}

        yearly = yearly_table(fold_dates, leg_elig["monthly"], idx, b12_pairs, b1mo_pairs)

        return {"folds": len(fold_dates), "first": fold_dates[0], "last": fold_dates[-1],
                "ew_eligible": leg_elig, "ew_labeled": leg_lbl, "breadth_b": leg_b,
                "breadth_b_1mo_matched": leg_b1,
                "nifty500_tri": leg_idx,
                "gaps": {"B_minus_EWelig_cohort": leg_b["cagr"] - leg_elig["cohort_cagr"],
                         "B_minus_EWelig_matched": leg_b1["cagr"] - leg_elig["series_cagr"],
                         "B_minus_TRI": leg_b["cagr"] - leg_idx["cagr"],
                         "EWelig_minus_TRI_series": leg_elig["series_cagr"] - leg_idx["cagr"]},
                "dropped_legs": dropped, "dropped_legs_1mo": dropped1,
                "yearly": yearly}

    w145 = run_window(sub145, "val145")
    wtest = run_window(test_folds, "test35")

    # G3/G4/G3b: reproduction pins
    assert abs(w145["nifty500_tri"]["cagr"] - PIN_IDX_CAGR_145) < 1e-6, \
        (w145["nifty500_tri"]["cagr"], PIN_IDX_CAGR_145)
    assert w145["dropped_legs"] == 0, w145["dropped_legs"]
    b_gap = abs(w145["breadth_b"]["cagr"] - PIN_B_CAGR_145)
    assert b_gap < 0.01, (w145["breadth_b"]["cagr"], PIN_B_CAGR_145)
    bench_gap = wtest["nifty500_tri"]["cagr"] - PIN_TEST_BENCH   # disclosed, not asserted

    out = {
        "experiment": "E026_ew_universe_benchmark", "git_hash": git, "profile": args.profile,
        "kind": "REPORTING (no bars, no adoption)",
        "cutoff": str(cutoff), "boundary": str(boundary),
        "amendment": ("split drift measured pre-run: boundary 2023-09-24 -> 2023-10-01; val "
                      "145 -> 146 folds (gained 2023-08-31); test window shifted to "
                      "2023-09-29 -> 2026-07-31; pins reproduced on the exact 145-fold "
                      "subset E018 pinned (see hypothesis.md)"),
        "guards": {"G1_split": "146/35/145 as measured", "G2_ic": mean_ic,
                   "G2_picks_top5": picks5, "G2_picks_arm": picks_arm,
                   "G3_index_cagr_145": w145["nifty500_tri"]["cagr"],
                   "G3_pin": PIN_IDX_CAGR_145, "G3_passed": True,
                   "G4_b_cagr_145": w145["breadth_b"]["cagr"], "G4_pin": PIN_B_CAGR_145,
                   "G4_diff": b_gap, "G4_passed": True, "G4_dropped_legs": w145["dropped_legs"],
                   "G5_flagged_months_145": w145["ew_eligible"]["months_below_80pct_cover"],
                   "G5_min_share_145": w145["ew_eligible"]["cover_min_share"],
                   "G5_flagged_months_test": wtest["ew_eligible"]["months_below_80pct_cover"],
                   "G5_min_share_test": wtest["ew_eligible"]["cover_min_share"],
                   "passed": True},
        "val_145": w145, "test_35": wtest,
        "harness_pin_disclosure": {
            "pin": PIN_TEST_BENCH, "old_window": "2023-08-31 -> 2026-06-30 (E020-C)",
            "tri_cagr_new_window": wtest["nifty500_tri"]["cagr"], "diff": bench_gap,
            "note": "expected to differ: the cutoff-derived test window itself moved"},
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                    # noqa: E731
    for win in (w145, wtest):
        print(f"\n== {win['folds']} folds: {win['first']} -> {win['last']} ==")
        print(f"  {'leg':<28} {'CAGR':>9} {'maxDD':>8}  note")
        e, l, b, x = win["ew_eligible"], win["ew_labeled"], win["breadth_b"], win["nifty500_tri"]
        print(f"  {'EW-ELIGIBLE (rebal)':<28} {pct(e['series_cagr']):>9} "
              f"{pct(e['series_maxdd']):>8}  cohort-est {pct(e['cohort_cagr'])}, "
              f"min cover {e['cover_min_share']:.1%}")
        print(f"  {'EW-LABELED (rebal)':<28} {pct(l['series_cagr']):>9} "
              f"{pct(l['series_maxdd']):>8}  cohort-est {pct(l['cohort_cagr'])}")
        print(f"  {'B DECILE_RANK_W (real c)':<28} {pct(b['cagr']):>9} {pct(b['maxdd']):>8}  "
              f"{b['cohorts']} cohorts")
        print(f"  {'NIFTY 500 TRI':<28} {pct(x['cagr']):>9} {pct(x['maxdd']):>8}")
        g = win["gaps"]
        print(f"  gaps: B-EWelig {pct(g['B_minus_EWelig_cohort'])} (cohort est) / "
              f"{pct(g['B_minus_EWelig_matched'])} (matched 1-mo); B-TRI "
              f"{pct(g['B_minus_TRI'])}; EWelig-TRI "
              f"{pct(g['EWelig_minus_TRI_series'])}")
        print(f"  yearly (year, EW, TRI, B12mo, B1mo, gap12, gap1mo): "
              + "; ".join(f"{r['year']} {pct(r['ew_eligible'])}/{pct(r['nifty500_tri'])}"
                          f"/{pct(r['b_12mo'])}/{pct(r['b_1mo_matched'])} "
                          f"{pct(r['gap_12mo'])}/{pct(r['gap_matched'])}"
                          + (" *" if r["partial"] else "")
                          for r in win["yearly"]))
    print(f"\nguards: IC {mean_ic:.10f} == pin; picks {picks5}/4,579, {picks_arm}/5,605; "
          f"index pin diff {abs(w145['nifty500_tri']['cagr'] - PIN_IDX_CAGR_145):.2e}; "
          f"B pin diff {b_gap:.2e}; dropped legs {w145['dropped_legs']}")
    print(f"harness bench pin (E020-C, OLD window) vs new-window TRI: "
          f"{PIN_TEST_BENCH:.6f} vs {wtest['nifty500_tri']['cagr']:.6f} "
          f"(diff {bench_gap:+.6f}, disclosed)")
    print(f"wrote results.json ({out['runtime_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_check() if "--self-check" in __import__("sys").argv else main())
