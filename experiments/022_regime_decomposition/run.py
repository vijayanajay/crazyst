"""E022 — regime decomposition: where does the breadth satellite's excess return come from?
(Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

A diagnostic, not a design: no deployment claim, nothing ships. It decomposes the E018
decile book's excess return over the index (both measured over the identical label
interval) by two frozen, backward-looking index-state cuts — the harness's regime band
(REGIME_BAND=0.02 up/down/flat) and an index-drawdown bucket (shallow > -5%,
moderate (-15%,-5%], deep <= -15%) — over ALL 180 labeled months (2011-07-29 → 2026-06-30;
the test window is burnt as of E020-C, pooling disclosed in the hypothesis).

Guards: G1 the top-5% 1-month gross mean over the 145 validation months reproduces the
smoke's committed light_pass.mean_gross within 0.15pp; G2 the TRI ym marks over the
validation months reproduce E019's committed index_equivalent (CAGR/maxDD) to 1e-9; G3
coverage (180 months, >= 10 legs and an index forward everywhere, <= 2 months without a
regime band).

python -m experiments.022_regime_decomposition.run --profile full
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

E018 = importlib.import_module("experiments.018_breadth_portfolio.run")
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

E019_RESULTS = os.path.join(os.path.dirname(__file__), "..", "019_deployable_breadth",
                            "results.json")
SMOKE_RESULTS = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "smoke_e2e",
                             "smoke_results.json")

REGIME_BAND = HARNESS.REGIME_BAND           # 0.02, the harness's own band
DD_DEEP = -0.15
DD_MODERATE = -0.05
EXCESS_EDGE_PP = 3.0                        # decision rule: deep - shallow mean excess
HIT_RATE_MIN = 0.70
N_DEEP_MIN = 12


def _decile_book_w(rs):
    """E018's top decile, rank-weighted (weight ∝ 1/rank_pos), via the committed builder."""
    dec = E018._decile_book(rs)
    w = [1.0 / pos for _s, pos, _sc in dec]
    tot = sum(w)
    return [(s, wi / tot) for (s, _p, _sc), wi in zip(dec, w)]


def _top5_eq(rs):
    top5 = E018._picks_smoke(rs)
    return [(s, 1.0 / len(top5)) for s, _p, _sc in top5] if top5 else []


def _t_stat(xs):
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return mean / math.sqrt(var / n) if var > 0 else None


def _table(pairs):
    """pairs: (book_ret, index_ret) per month. The frozen reduction: mean book, mean index,
    mean excess, t-stat of excess, hit rate."""
    n = len(pairs)
    if not n:
        return {"n": 0}
    ex = [b - i for b, i in pairs]
    mean = sum(ex) / n
    return {"n": n, "mean_book": sum(b for b, _ in pairs) / n,
            "mean_index": sum(i for _, i in pairs) / n, "mean_excess": mean,
            "t_stat": _t_stat(ex), "hit_rate": sum(x > 0 for x in ex) / n}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e019 = json.load(open(E019_RESULTS, encoding="utf-8"))
    smoke_res = json.load(open(SMOKE_RESULTS, encoding="utf-8"))
    pin_gross = smoke_res["light_pass"]["mean_gross"]
    idx_cagr_pin = e019["index_equivalent"]["cagr"]
    idx_dd_pin = e019["index_equivalent"]["maxdd"]

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)                 # full profile; selfcheck resets to quick
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        val_folds = sorted({str(r[0]) for r in val_rows})
        test_folds = sorted({str(r[0]) for r in test_rows})
        assert len(val_folds) == 145 and val_folds[0] == "2011-07-29" \
            and val_folds[-1] == "2023-07-31"
        assert len(test_folds) == 35 and test_folds[0] == "2023-08-31" \
            and test_folds[-1] == "2026-06-30"
        assert str(boundary) == "2023-09-24"
        by_month_lbl: dict[str, list] = {}
        for r in labeled:
            by_month_lbl.setdefault(str(r[0]), []).append(r)
        tri = con.execute(
            "SELECT substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(tri, date) FROM index_tri "
            "WHERE index_name = 'NIFTY 500' GROUP BY ym ORDER BY ym").fetchall()
    finally:
        con.close()
    trimap = {ym: p for ym, p in tri}
    months = val_folds + test_folds                 # all 180 labeled months, in order

    # month-end adj_close marks per symbol (E018's exact marks query)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        marks_raw = con.execute(
            "SELECT symbol, substr(CAST(date AS VARCHAR),1,7) AS ym, arg_max(adj_close, date) "
            "FROM adj_close GROUP BY symbol, ym").fetchall()
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

    def idx_fwd(ym: str) -> float | None:
        """The index's return over the label interval starting at decision month m
        (month-end ym(m) -> the next decision month's mark)."""
        nxt = trimap.get(_next_ym(ym))
        cur = trimap.get(ym)
        return None if cur is None or nxt is None else nxt / cur - 1.0

    def _next_ym(ym: str) -> str:
        y, m = int(ym[:4]), int(ym[5:7])
        return f"{y + (m == 12):04d}-{(m % 12) + 1:02d}"

    def idx_ret_prev(ym: str) -> float | None:
        """The index's return over the month interval ENDING at m (regime-at-m)."""
        y, mth = int(ym[:4]), int(ym[5:7])
        prev = f"{y - (mth == 1):04d}-{(mth - 2) % 12 + 1:02d}"
        cur, prv = trimap.get(ym), trimap.get(prev)
        return None if cur is None or prv is None else cur / prv - 1.0

    # label lookup (unused since the mark-based switch; kept for the record's provenance)
    def lbl_of(rs, sym):
        for r in rs:
            if r[-2] == sym:
                return r[1]
        return None

    # ---- G2: index anchor over the 145 validation months (E020's exact arithmetic) --------
    v_ym = [m[:7] for m in val_folds]
    idx_curve = [trimap[ym] / trimap[v_ym[0]] for ym in v_ym]
    c_m = idx_curve[-1] ** (12 / (len(idx_curve) - 1)) - 1
    pk, dd_m = 1.0, 0.0
    for e in idx_curve:
        pk = max(pk, e)
        dd_m = min(dd_m, e / pk - 1)
    g2 = abs(c_m - idx_cagr_pin) < 1e-9 and abs(dd_m - idx_dd_pin) < 1e-9
    assert g2, (c_m, idx_cagr_pin, dd_m, idx_dd_pin)

    # ---- per-month books and excess returns (E018's mark-based cohort construction) -------
    pairs = {}                                      # m -> (book_ret, index_fwd)
    t5_pairs = {}
    for i, m in enumerate(months[:-1]):
        rs = by_month_lbl[m]
        dec = _decile_book_w(rs)
        assert len(dec) >= 10, (m, len(dec))
        ym, x_ym = m[:7], months[i + 1][:7]         # marks: decision month-end -> next
        ifx = idx_fwd(ym)
        assert ifx is not None, (m, "no index forward")
        legs = []
        for sym, w in dec:
            pe, px = last_mark(sym, ym), last_mark(sym, x_ym)
            assert pe is not None and px is not None, (m, sym)   # E018's zero-dropped guard
            legs.append((w, px / pe - 1))
        b = sum(w * r for w, r in legs)
        pairs[m] = (b, ifx)
        t5 = _top5_eq(rs)
        if t5:
            l5 = [(w, last_mark(s, x_ym) / last_mark(s, ym) - 1)
                  for s, w in t5 if last_mark(s, ym) is not None
                  and last_mark(s, x_ym) is not None]
            if len(l5) == len(t5):
                t5_pairs[m] = (sum(w * r for w, r in l5), ifx)
    excess = {m: b - i for m, (b, i) in pairs.items()}

    # ---- G1: top-5% 1-month GROSS anchor over the validation months -----------------------
    # E018's cohort_returns("top5", 1, 0.0) verbatim: val folds only, exit at the next val
    # fold, missing legs skipped (no zero-drop assert at the 1-month horizon), unweighted-mean
    # of cohort gross returns. The diagnostic's decile series (pairs) is NOT this series.
    def t5_series(fold_list):
        out = []
        for i, m in enumerate(fold_list):
            x = fold_list[i + 1] if i + 1 < len(fold_list) else None
            if x is None:
                continue
            t5 = _top5_eq(by_month_lbl[m])
            if not t5:
                continue
            legs = [(w, last_mark(s, x[:7]) / last_mark(s, m[:7]) - 1)
                    for s, w in t5
                    if last_mark(s, m[:7]) is not None and last_mark(s, x[:7]) is not None]
            if legs:
                out.append(sum(w * r for w, r in legs))
        return out

    a_1mo = t5_series(val_folds)
    a_mean = sum(a_1mo) / len(a_1mo)
    g1 = abs(a_mean - pin_gross) < 0.0015
    assert g1, (a_mean, pin_gross)

    # ---- G3: coverage ---------------------------------------------------------------------
    n_bands = sum(1 for m in months if idx_ret_prev(m[:7]) is None)
    g3 = len(months) == 180 and n_bands <= 2
    assert g3, (len(months), n_bands)

    # ---- cuts ------------------------------------------------------------------------------
    def cut_of(m):
        r = idx_ret_prev(m[:7])
        if r is None:
            return "no_band"
        return "up" if r > REGIME_BAND else ("down" if r < -REGIME_BAND else "flat")

    def dd_of(m):
        ym = m[:7]
        hist = [v for k, v in trimap.items() if k <= ym]
        peak = max(hist)
        dd = trimap[ym] / peak - 1.0
        return "shallow" if dd > DD_MODERATE else \
            ("moderate" if dd > DD_DEEP else "deep")

    def reduce_(cut, sel=None):
        buckets: dict[str, list] = {}
        for m in months:
            if m in pairs and (sel is None or m in sel):
                buckets.setdefault(cut(m), []).append(pairs[m])
        return {k: _table(v) for k, v in sorted(buckets.items())}

    by_band = reduce_(cut_of)
    by_dd = reduce_(dd_of)
    overall = _table(list(pairs.values()))

    # POST-HOC addition (disclosed, not part of the frozen reductions; the decision rule
    # does not read it): slice x band split — does the in-sample band pattern survive the
    # test window? This is the reconciliation with E020-C's +0.04pp/mo test-window excess.
    post_hoc = {
        "disclosure": "slice x band split added after the first run to reconcile with "
                      "E020-C; descriptive only, no gate reads it",
        "validation_by_band": reduce_(cut_of, set(val_folds)),
        "test_by_band": reduce_(cut_of, set(test_folds)),
    }

    # 2018–2020 episode's share of the full-sample mean excess
    ep = [excess[m] for m in months if m in excess and "2018-01" <= m[:7] <= "2020-12"]
    episode = {"n": len(ep), "mean_excess": sum(ep) / len(ep),
               "share_of_full_mean": (sum(ep) / len(ep)) / overall["mean_excess"]}
    # ---- decision rule --------------------------------------------------------------------
    deep, shallow = by_dd.get("deep", {"n": 0, "mean_excess": 0.0}), by_dd["shallow"]
    reopens = (deep["n"] >= N_DEEP_MIN
               and deep["mean_excess"] - shallow["mean_excess"] >= EXCESS_EDGE_PP / 100
               and deep.get("hit_rate", 0.0) >= HIT_RATE_MIN)

    out = {
        "experiment": "E022_regime_decomposition", "git_hash": git, "profile": args.profile,
        "window": {"months": len(months), "first": months[0], "last": months[-1],
                   "validation": len(val_folds), "test_pooled": len(test_folds),
                   "pooling_disclosure": "test window burnt as of E020-C; diagnostic only"},
        "guards": {"G1_top5_anchor": g1, "G1_mean_gross": a_mean, "G1_pin": pin_gross,
                   "G2_index_anchor": g2, "G2_index_cagr": c_m, "G2_index_maxdd": dd_m,
                   "G3_coverage": g3, "G3_no_band_months": n_bands, "passed": g1 and g2 and g3},
        "book": {"overall": overall, "by_regime_band": by_band, "by_index_dd": by_dd,
                 "episode_2018_2020": episode, "top5_overall": _table(list(t5_pairs.values())),
                 "post_hoc_slice_split": post_hoc},
        "decision_rule": {"deep_minus_shallow_pp": (deep["mean_excess"] - shallow["mean_excess"])
                          * 100 if deep["n"] else None, "n_deep": deep["n"],
                          "deep_hit_rate": deep.get("hit_rate"),
                          "thresholds": {"edge_pp": EXCESS_EDGE_PP, "hit_rate": HIT_RATE_MIN,
                                         "n_deep": N_DEEP_MIN}},
        "reopens_family": reopens,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"months: {len(months)} ({months[0]} -> {months[-1]}); guards G1 ({a_mean:.4f} vs "
          f"pin {pin_gross:.4f}) G2 G3 ({n_bands} no-band) all green")
    print(f"overall: excess {pct(overall['mean_excess'])}/mo, t {overall['t_stat']:.2f}, "
          f"hit {overall['hit_rate']:.0%}; 2018-20 episode share "
          f"{episode['share_of_full_mean']:.0%}")
    print("\nregime band   n    mean-excess   t      hit")
    for k, t in by_band.items():
        print(f"  {k:<10} {t['n']:>4}  {pct(t['mean_excess']):>10}  "
              f"{(t['t_stat'] or float('nan')):>5.2f}  {t['hit_rate']:>4.0%}")
    print("index dd      n    mean-excess   t      hit")
    for k, t in by_dd.items():
        print(f"  {k:<10} {t['n']:>4}  {pct(t['mean_excess']):>10}  "
              f"{(t['t_stat'] or float('nan')):>5.2f}  {t['hit_rate']:>4.0%}")
    print(f"\nDECISION: deep {pct(deep['mean_excess'])} (n={deep['n']}, hit "
          f"{deep.get('hit_rate', 0.0):.0%}) vs shallow {pct(shallow['mean_excess'])} -> "
          + ("family MAY re-open via a fresh pre-registration (index-conditional sizing)"
             if reopens else
             "edge is regime-uniform or absent — family stays closed; next step is new "
             "signal families, not more mechanics on this one"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
