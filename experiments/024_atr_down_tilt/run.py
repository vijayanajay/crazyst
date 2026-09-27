"""E024 — does a parameter-free low-ATR tilt inside the decile book fill the zero-excess
down-month bucket without breaking the up-month edge?
(Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

Shortlist item #2 of docs/feature_family_audit.md. E022's exact machinery, verbatim
(E018's rank-weighted decile book, mark-based 1-month cohorts, zero dropped legs, sourced
Nifty 500 TRI index leg over the identical interval, gross of costs). Arm A is the
committed baseline (weight ∝ 1/rank_pos). Arm B tilts: weight ∝ 1/rank_pos × (1 −
pct_atr), pct_atr = the leg's cross-sectional percentile of atr_ratio within its month's
labeled cross-section (the shipped _pct math; NaN → neutral 1.0; a leg at pct 1.0 drops
out, ≥ 5 legs asserted). No knob, no sweep.

Guards: G1 arm A's by-band mean excess == E022's committed validation_by_band to 1e-6;
G2 index leg == E019's committed index_equivalent to 1e-9; G3 zero dropped legs, ≥ 5 legs
per tilted book. Bars: B1 arm-B down-month excess >= +0.5pp; B2 arm-B up-month excess >=
arm-A up-month − 1.0pp; B3 paired mean excess diff (B − A) > 0 over 145 months. PASS =
candidate only; the deployable-sim pre-registration is the next step, nothing ships here.

python -m experiments.024_atr_down_tilt.run --profile full
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

E018 = importlib.import_module("experiments.018_breadth_portfolio.run")
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
model = importlib.import_module("src.model.composite")

E019_RESULTS = os.path.join(os.path.dirname(__file__), "..", "019_deployable_breadth",
                            "results.json")
E022_RESULTS = os.path.join(os.path.dirname(__file__), "..", "022_regime_decomposition",
                            "results.json")

REGIME_BAND = HARNESS.REGIME_BAND
B1_DOWN_MIN = 0.005
B2_UP_TOL = 0.010


def _decile_book_w(rs):
    dec = E018._decile_book(rs)
    w = [1.0 / pos for _s, pos, _sc in dec]
    tot = sum(w)
    return [(s, wi / tot) for (s, _p, _sc), wi in zip(dec, w)]


def _pct_atr(rs):
    """Cross-sectional percentile of atr_ratio over the month's labeled rows (the shipped
    _pct math: average ranks / (n-1), NaN/None -> None)."""
    fi = {name: 2 + i for i, name in enumerate(model.PANEL_FEATURES)}
    vals = [r[fi["atr_ratio"]] for r in rs]
    return model._pct(vals)


def _tilted_book(rs):
    dec = _decile_book_w(rs)
    pct = {r[-2]: p for r, p in zip(rs, _pct_atr(rs))}
    raw = []
    for s, w in dec:
        p = pct.get(s)
        f = 1.0 if p is None else (1.0 - p)
        if f > 0:
            raw.append((s, w * f))
    assert raw, "tilted book wiped out"
    tot = sum(w for _s, w in raw)
    return [(s, w / tot) for s, w in raw], len(dec) - len(raw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e022 = json.load(open(E022_RESULTS, encoding="utf-8"))
    e019 = json.load(open(E019_RESULTS, encoding="utf-8"))
    anchor = e022["book"]["post_hoc_slice_split"]["validation_by_band"]
    idx_cagr_pin = e019["index_equivalent"]["cagr"]
    idx_dd_pin = e019["index_equivalent"]["maxdd"]

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        val_folds = sorted({str(r[0]) for r in val_rows})
        test_folds = sorted({str(r[0]) for r in test_rows})
        assert len(val_folds) == 145 and val_folds[0] == "2011-07-29" \
            and val_folds[-1] == "2023-07-31"
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
    trimap = {ym: p for ym, p in tri}
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

    def _next_ym(ym):
        y, m = int(ym[:4]), int(ym[5:7])
        return f"{y + (m == 12):04d}-{(m % 12) + 1:02d}"

    def idx_fwd(ym):
        cur, nxt = trimap.get(ym), trimap.get(_next_ym(ym))
        return None if cur is None or nxt is None else nxt / cur - 1.0

    def idx_ret_prev(ym):
        y, mth = int(ym[:4]), int(ym[5:7])
        prev = f"{y - (mth == 1):04d}-{(mth - 2) % 12 + 1:02d}"
        cur, prv = trimap.get(ym), trimap.get(prev)
        return None if cur is None or prv is None else cur / prv - 1.0

    def cut_of(m):
        r = idx_ret_prev(m[:7])
        return None if r is None else ("up" if r > REGIME_BAND else
                                       ("down" if r < -REGIME_BAND else "flat"))

    # ---- G2: index anchor -----------------------------------------------------------------
    v_ym = [m[:7] for m in val_folds]
    idx_curve = [trimap[ym] / trimap[v_ym[0]] for ym in v_ym]
    c_m = idx_curve[-1] ** (12 / (len(idx_curve) - 1)) - 1
    pk, dd_m = 1.0, 0.0
    for e in idx_curve:
        pk = max(pk, e)
        dd_m = min(dd_m, e / pk - 1)
    g2 = abs(c_m - idx_cagr_pin) < 1e-9 and abs(dd_m - idx_dd_pin) < 1e-9
    assert g2, (c_m, idx_cagr_pin, dd_m, idx_dd_pin)

    # ---- both arms' monthly (book, index) pairs --------------------------------------------
    # E022's post-hoc validation_by_band covers 145 intervals: every val month's interval,
    # INCLUDING 2023-07-31 -> 2023-08-31 (exit mark = the first TEST month). Reproduced here
    # bit-for-bit so G1 anchors against the committed construction exactly; both arms get
    # identical intervals, so the between-arm bars are unaffected by the boundary interval.
    # Disclosed in results.json; E022's gating cuts were pooled by design and unaffected.
    chain = val_folds + [test_folds[0]]

    def series(book_of):
        out = {}
        dropped_total = 0
        for i, m in enumerate(val_folds):
            rs = by_month_lbl[m]
            ym, x_ym = m[:7], chain[i + 1][:7]
            book, dropped = book_of(rs)
            dropped_total += dropped
            legs = []
            for sym, w in book:
                pe, px = last_mark(sym, ym), last_mark(sym, x_ym)
                assert pe is not None and px is not None, (m, sym)
                legs.append((w, px / pe - 1))
            ifx = idx_fwd(ym)
            assert ifx is not None, (m, "no index forward")
            out[m] = (sum(w * r for w, r in legs), ifx)
        return out, dropped_total

    pairs_a, dropped_a = series(lambda rs: (_decile_book_w(rs), 0))
    pairs_b, dropped_b = series(_tilted_book)
    # G3 per the frozen words: zero MARK-unpriceable legs (asserted inside series()); tilt
    # dropouts (pct_atr = 1.0 -> factor 0) are the hypothesis's own construction, counted
    # and reported; every tilted book must keep >= 5 legs.
    min_legs_b = min(len(_tilted_book(by_month_lbl[m])[0]) for m in val_folds)
    g3 = dropped_a == 0 and min_legs_b >= 5   # dropped_b = tilt dropouts, by construction
    assert g3, (dropped_a, dropped_b, min_legs_b)

    # ---- G1: arm A by band == E022's committed validation_by_band ---------------------------
    def band_means(pairs):
        buckets: dict[str, list] = {}
        for m, (b, i) in pairs.items():
            c = cut_of(m)
            if c:
                buckets.setdefault(c, []).append(b - i)
        return {k: sum(v) / len(v) for k, v in buckets.items()}

    got = band_means(pairs_a)
    g1 = all(k in got and abs(got[k] - anchor[k]["mean_excess"]) < 1e-6
             for k in ("down", "flat", "up"))
    assert g1, (got, {k: v["mean_excess"] for k, v in anchor.items()})

    # ---- bars ------------------------------------------------------------------------------
    def bucket_excess(pairs, band):
        return [b - i for m, (b, i) in pairs.items() if cut_of(m) == band]

    down_b = bucket_excess(pairs_b, "down")
    up_a = bucket_excess(pairs_a, "up")
    up_b = bucket_excess(pairs_b, "up")
    b1 = sum(down_b) / len(down_b) >= B1_DOWN_MIN
    b2 = sum(up_b) / len(up_b) >= sum(up_a) / len(up_a) - B2_UP_TOL
    common = sorted(set(pairs_a) & set(pairs_b))
    diffs = [pairs_b[m][0] - pairs_b[m][1] - (pairs_a[m][0] - pairs_a[m][1]) for m in common]
    n = len(diffs)
    mean_d = sum(diffs) / n
    sd = (sum((d - mean_d) ** 2 for d in diffs) / (n - 1)) ** 0.5
    t_d = mean_d / (sd / n ** 0.5) if sd > 0 else 0.0
    b3 = mean_d > 0

    def _tbl(pairs, band):
        xs = bucket_excess(pairs, band)
        return {"n": len(xs), "mean_excess": sum(xs) / len(xs)}

    out = {
        "experiment": "E024_atr_down_tilt", "git_hash": git, "profile": args.profile,
        "window": {"validation_months": len(val_folds), "first": val_folds[0],
                   "last": val_folds[-1], "test_window": "burnt; not touched"},
        "guards": {"G1_armA_equals_E022": g1, "G1_armA_by_band": got,
                   "G2_index_anchor": g2, "G3_zero_mark_dropped": g3,
                   "G3_min_tilted_book_legs": min_legs_b,
                   "G3_note": "tilt dropouts (pct_atr=1.0, factor 0) are the frozen "
                              "construction, counted separately: "
                              f"{dropped_b} legs over 145 cohorts",
                   "passed": g1 and g2 and g3},
        "disclosures": {
            "boundary_interval": "E022's committed post-hoc validation_by_band includes the "
                                 "2023-07-31 -> 2023-08-31 interval (exit mark = the first "
                                 "test month); reproduced here for an exact G1 anchor. Both "
                                 "arms use identical intervals, so B1/B2/B3 comparisons are "
                                 "unaffected. E022's gating cuts were pooled over all 179 "
                                 "intervals by design (disclosed there) and are unaffected.",
            "tilt_dropouts": f"{dropped_b} legs across 145 cohorts had pct_atr = 1.0 "
                             "(factor 0) and left the tilted book, per the frozen "
                             "construction; every tilted book kept >= 5 legs."},
        "arms": {k: {"overall_excess": sum(b - i for b, i in v.values()) / len(v),
                     "down": _tbl(v, "down"), "flat": _tbl(v, "flat"), "up": _tbl(v, "up")}
                 for k, v in (("A_baseline", pairs_a), ("B_atr_tilt", pairs_b))},
        "bars": {"B1_down_ge_0.5pp": {"value": _tbl(pairs_b, "down")["mean_excess"],
                                      "bar": B1_DOWN_MIN, "passed": b1},
                 "B2_up_within_1pp": {"A_up": _tbl(pairs_a, "up")["mean_excess"],
                                      "B_up": _tbl(pairs_b, "up")["mean_excess"],
                                      "tolerance": B2_UP_TOL, "passed": b2},
                 "B3_paired_diff_positive": {"mean_diff": mean_d, "t": t_d, "n": n,
                                             "passed": b3}},
        "verdict": "PASS" if (b1 and b2 and b3) else "REJECTED",
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"E024: {len(val_folds)} validation months; guards G1 (arm A == E022 by band) "
          f"G2 G3 ({dropped_a + dropped_b} dropped legs) all green")
    for k, a in out["arms"].items():
        print(f"  {k:<12} down {pct(a['down']['mean_excess'])} (n={a['down']['n']})  "
              f"flat {pct(a['flat']['mean_excess'])} (n={a['flat']['n']})  "
              f"up {pct(a['up']['mean_excess'])} (n={a['up']['n']})  "
              f"overall {pct(a['overall_excess'])}")
    print(f"  paired B-A: {mean_d:+.5f}/mo, t {t_d:+.2f} over {n} months")
    print(f"  bars: B1 down >= +0.5pp [{b1}]  B2 up within 1pp of A [{b2}]  "
          f"B3 paired diff > 0 [{b3}]")
    print(f"DECISION: {out['verdict']}"
          + (" — the tilt becomes a candidate; the E019-style deployable-sim "
             "pre-registration is the next step, nothing ships here" if (b1 and b2 and b3)
             else " — the conditional-volatility direction is closed; the audit's remaining "
                  "direction is new data (index-inclusion flows)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
