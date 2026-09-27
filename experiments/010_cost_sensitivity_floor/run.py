"""E010 — E006's cost sensitivity re-measured on the post-E009 floor universe (pre-registered
in hypothesis.md; run AFTER that file was written, per BRD 12).

Protocol: E006's, imported module-to-module so nothing drifts — composite_2f top-5% picks
(k = max(1, round(n x 0.05)), tie-break by symbol), net = gross - 2 x cost, levels
{0.2%, 0.5%, 1.0%} per side, validation slice only, reported per level and per the BRD 9.7
rank split (<=600 vs >600) and size bucket. The ONLY change is the universe: the chain is
rebuilt at the shipped config (E009's adopted floor 0.75).

Arms:
  pre-floor (config floor 0.0, rebuilt) — must reproduce E006's committed results.json
    pick count EXACTLY and means within the tie-swap tolerance before any comparison;
  floor (shipped config 0.75, rebuilt) — the portfolio the engine can actually build.

Impact decomposition: per pick-month, the engine's own impact estimate at the shipped slot
size — min(impact_cap_pct, impact_coef x S / med20) per side (S = Rs250k), med20 from
E009's liq_daily20 machinery and sanity layer. Hypothesis: the floor arm's picks carry
materially lower modelled impact — the mechanism behind a lower honest per-side cost.

python -m experiments.010_cost_sensitivity_floor.run --profile full
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load

E006 = importlib.import_module("experiments.006_cost_sensitivity.run")   # its protocol
E007 = importlib.import_module("experiments.007_universe_cutoff.run")    # its chain builder
E009 = importlib.import_module("experiments.009_fill_gate_reach.run")    # liq_daily20 + sanity
P41 = importlib.import_module("experiments.004_composite_v0.run")        # slice split

SLOT_S = 250_000.0            # the shipped slot size (Rs10L x 4)
COSTS = E006.COSTS            # (0.002, 0.005, 0.010) — the pre-registered levels


def _measure(con) -> dict:
    """E006's exact measurement on the CURRENT chain state."""
    rows, cutoff = E006._fetch(con)
    assert rows, "no labeled rows — the chain rebuild produced an empty matrix"
    val, test, boundary = P41.split_slice(rows, cutoff)
    by_month: dict[str, list] = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    sym = E006.SYM
    picks = []
    for m, rs in sorted(by_month.items()):
        for i in E006._picks(rs):
            r = rs[i]
            picks.append({"mdate": str(r[0]), "symbol": r[sym],
                          "gross": r[1], "rank": r[2 + len(E006.P41B.FEATURES)],
                          "bucket": r[-1]})
    results = {"by_rank_group": {}, "by_bucket": {}}
    for cost in COSTS:
        for label, pred in (("rank<=600", lambda p: p["rank"] <= E006.RANK_BOUNDARY),
                            ("rank>600", lambda p: p["rank"] > E006.RANK_BOUNDARY),
                            ("all", lambda p: True)):
            grp = [p for p in picks if pred(p)]
            results["by_rank_group"].setdefault(label, {})[str(cost)] = \
                E006._group_stats(grp, cost)
        for b in sorted({p["bucket"] for p in picks}):
            grp = [p for p in picks if p["bucket"] == b]
            results["by_bucket"].setdefault(b, {})[str(cost)] = E006._group_stats(grp, cost)
    return {"picks": picks, "results": results, "cutoff": str(cutoff),
            "boundary": str(boundary), "months": len(by_month)}


def _half_edge(group: dict) -> float | None:
    """E006's headline rule: smallest level where the group's mean net drops below half
    its 0.2% value (None = the edge survives every level)."""
    base = group.get("0.002")
    if not base or base["mean_net"] <= 0:
        return None
    for cost in COSTS:
        st = group.get(str(cost))
        if st and st["mean_net"] < 0.5 * base["mean_net"]:
            return cost
    return None


def _impact_decomposition(con, picks: list[dict], floor_cfg) -> dict:
    """Modelled per-side impact of the picks at the shipped slot size, by med20 band."""
    from src.config import load as _l
    cfg = _l("full")
    cap = cfg["backtest"]["fill"]["impact_cap_pct"] / 100.0
    coef = cfg["backtest"]["fill"]["impact_coef"]
    med20 = {(s, str(m)): v for s, m, v in con.execute(
        "SELECT symbol, mdate, med20 FROM liq_daily20").fetchall()}
    rows = []
    for p in picks:
        m20 = med20.get((p["symbol"], p["mdate"]))
        if m20 is None:
            continue
        impact = min(cap, coef * SLOT_S / m20)
        rows.append({"impact": impact, "med20": m20, "rank": p["rank"]})
    assert rows, "no pick matched liq_daily20 — table/chain mismatch"
    bands = (("med20 < 1cr", lambda m: m < 1e7),
             ("1-5cr", lambda m: 1e7 <= m < 5e7),
             ("5-20cr", lambda m: 5e7 <= m < 2e8),
             (">= 20cr", lambda m: m >= 2e8))
    out = {"picks_with_med20": len(rows), "slot_rupees": SLOT_S,
           "impact_cap_pct": cap * 100, "impact_coef": coef, "by_band": {}}
    for label, pred in bands:
        sel = [r for r in rows if pred(r["med20"])]
        if not sel:
            continue
        out["by_band"][label] = {
            "n": len(sel),
            "mean_impact_pct": sum(r["impact"] for r in sel) / len(sel) * 100,
            "max_impact_pct": max(r["impact"] for r in sel) * 100,
        }
    mean_impact = sum(r["impact"] for r in rows) / len(rows)
    out["mean_impact_pct"] = mean_impact * 100
    out["impact_gt_half_cap_pct"] = sum(1 for r in rows if r["impact"] > cap / 2) / len(rows)
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out_dir = os.path.dirname(__file__)
    shipped_floor = cfg["universe"]["min_median_turnover_cr"]
    assert shipped_floor == 0.75, \
        f"E010 measures the E009 floor arm; shipped floor is {shipped_floor}"

    # sanity layer first: E009's fixture + member recompute, independent of the arms
    E009._synthetic_fixture()

    con = duckdb.connect(cfg["paths"].get("duckdb"))
    try:
        # ---- arm 1: the FLOOR universe (shipped config) --------------------------------
        E007._build_chain(con, cfg)
        n_liq = E009._build_liq20(con, cfg)
        frozen = E009._frozen_sample_check(con, out_dir)
        member = E009._member_recompute_check(con, cfg)
        floor = _measure(con)
        impact_floor = _impact_decomposition(con, floor["picks"], cfg)
        med20_floor = {(s, str(m)): v for s, m, v in con.execute(
            "SELECT symbol, mdate, med20 FROM liq_daily20").fetchall()}
        pick_med20_floor = [med20_floor[(p["symbol"], p["mdate"])] for p in floor["picks"]
                            if (p["symbol"], p["mdate"]) in med20_floor]
        med20_floor_median = sorted(pick_med20_floor)[len(pick_med20_floor) // 2] \
            if pick_med20_floor else None

        # ---- arm 2: the PRE-FLOOR universe (config 0.0, rebuilt) -----------------------
        cfg["universe"]["min_median_turnover_cr"] = 0.0
        E007._build_chain(con, cfg)
        pre = _measure(con)
        impact_pre = _impact_decomposition(con, pre["picks"], cfg)

        # zero-drift backward guard: reproduce E006's committed results exactly
        e006 = json.load(open(os.path.join(out_dir, "..", "006_cost_sensitivity",
                                           "results.json"), encoding="utf-8"))
        e006_all = e006["results"]["by_rank_group"]["all"]
        assert len(pre["picks"]) == e006["picks_total"], \
            (len(pre["picks"]), e006["picks_total"])
        for cost in COSTS:
            a, b = pre["results"]["by_rank_group"]["all"][str(cost)], e006_all[str(cost)]
            assert abs(a["mean_net"] - b["mean_net"]) < 5e-4, (cost, a["mean_net"], b["mean_net"])
            assert abs(a["hit_rate"] - b["hit_rate"]) < 5e-4, (cost, a["hit_rate"], b["hit_rate"])
        # restore the shipped floor and the chain it implies
        cfg["universe"]["min_median_turnover_cr"] = shipped_floor
        E007._build_chain(con, cfg)
    finally:
        cfg["universe"]["min_median_turnover_cr"] = shipped_floor
        con.close()

    # ---- decision rule (pre-registered; corrected in the hypothesis before the run) ----
    fa = floor["results"]["by_rank_group"]["all"]
    f6, p6 = (floor["results"]["by_rank_group"]["rank>600"],
              pre["results"]["by_rank_group"]["rank>600"])
    ok_a = fa["0.002"]["mean_net"] >= 0.020
    ok_b = (_half_edge(f6) is not None and _half_edge(p6) is not None
            and _half_edge(f6) > _half_edge(p6)) or \
           (_half_edge(f6) is None and _half_edge(p6) is not None)
    ok_c = impact_floor["mean_impact_pct"] <= impact_pre["mean_impact_pct"] * 0.8
    gross_floor_all = fa["0.002"]["mean_net"] + 2 * COSTS[0]   # net = gross - 2*cost
    ok_d = gross_floor_all >= 0.023
    adopt_02 = ok_a and ok_b and ok_c and ok_d

    out = {
        "experiment": "E010_cost_sensitivity_floor", "profile": args.profile,
        "git_hash": git, "data_cutoff": floor["cutoff"],
        "validation_boundary": floor["boundary"],
        "shipped_floor_cr": shipped_floor, "slot_rupees": SLOT_S,
        "sanity": {"liq_daily20_rows": n_liq, "frozen_sample": frozen, "member": member},
        "prefloor_vs_e006": {"reproduced": True,
                             "e006_picks": e006["picks_total"],
                             "remeasured_picks": len(pre["picks"])},
        "floor_arm": {"picks": len(floor["picks"]), "results": floor["results"],
                      "impact": impact_floor, "pick_med20_median_cr":
                          med20_floor_median / 1e7 if med20_floor_median else None},
        "prefloor_arm": {"picks": len(pre["picks"]), "results": pre["results"],
                         "impact": impact_pre},
        "half_edge": {"floor": _half_edge(f6), "prefloor": _half_edge(p6)},
        "decision": {"a_net_edge_2pct": ok_a, "b_warning_relaxes": ok_b,
                     "c_impact_mechanism": ok_c, "d_gross_retained": ok_d,
                     "floor_all_gross": gross_floor_all,
                     "MOVE_DEFAULT_TO_02": adopt_02},
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(out_dir, "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    def _tbl(label, res):
        print(f"\n{label} ({res['months']} slice months, {len(res['picks']):,} picks):")
        print(f"{'group':<12}" + "".join(f"{c:>10.1%}" for c in COSTS) + "   (mean net / hit)")
        for g in ("all", "rank<=600", "rank>600"):
            cells = []
            for cost in COSTS:
                st = res["results"]["by_rank_group"][g].get(str(cost))
                cells.append(f"{st['mean_net'] * 100:>6.2f}%/{st['hit_rate'] * 100:>4.0f}%")
            print(f"{g:<12}" + "".join(f"{c:>12}" for c in cells))
        for b in sorted(res["results"]["by_bucket"]):
            cells = []
            for cost in COSTS:
                st = res["results"]["by_bucket"][b].get(str(cost))
                cells.append(f"{st['mean_net'] * 100:>6.2f}%")
            print(f"  {b:<10}" + "".join(f"{c:>12}" for c in cells))

    print("sanity: liq_daily20 re-verified " + frozen["status"] +
          f"; member recompute {member['rows_checked']:,} rows")
    print(f"pre-floor arm reproduces E006 exactly: {len(pre['picks']):,} picks "
          f"(E006 {e006['picks_total']:,}), means within tie-swap tolerance")
    _tbl("PRE-FLOOR (E006 replicated)", pre)
    _tbl("FLOOR (E009 universe, shipped config)", floor)
    print(f"\nedge-halving point (rank>600): pre-floor {_half_edge(p6)} -> floor "
          f"{_half_edge(f6)}")
    imp_line = (f"modelled impact of picks at Rs{SLOT_S:,.0f}/slot: pre-floor "
                f"{impact_pre['mean_impact_pct']:.3f}%/side -> floor "
                f"{impact_floor['mean_impact_pct']:.3f}%/side "
                f"(cap {impact_floor['impact_cap_pct']:.0f}%, picks with med20 "
                f"{impact_floor['picks_with_med20']:,}")
    if med20_floor_median:
        imp_line += f"; floor-arm median pick med20 {med20_floor_median / 1e7:.2f}cr"
    print(imp_line + ")")
    for band, v in impact_floor["by_band"].items():
        print(f"  {band:<12} n {v['n']:>5,}  mean impact {v['mean_impact_pct']:.3f}%/side  "
              f"max {v['max_impact_pct']:.3f}%")
    print(f"\nDECISION: {'MOVE DEFAULT TO 0.2%' if adopt_02 else 'KEEP 0.5%'} "
          f"(a {ok_a}, b {ok_b}, c {ok_c}, d {ok_d})")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
