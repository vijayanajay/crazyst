"""E007 — rolling top-1000 vs top-1500 as-of universe (pre-registered in hypothesis.md).

The BRD-owner question from fixissues_phase36.md: does cutting ranks 1001-1500 (the
"illiquidity graveyard") buy tradability without costing signal? Both arms rebuild the
REAL derived chain through its real builders with only `universe.top_n` overridden in
memory — rank -> eligibility -> winners -> feature_panel -> feature_matrix — then measure:

  1. universe shape: eligible symbol-months, the rank-1000/1500 boundary turnover, the
     share of eligible symbol-months below Rs 5cr/day (the review's claim, tested);
  2. composite_2f mean monthly IC + top-5% precision on P4.1's validation slice
     (boundary 2023-09-24; the test window is excluded and untouched, BRD 10);
  3. a 12-month engine pass at the shipped defaults (exit_gate escalate, 0.5%/side)
     through smoke_e2e's own machinery — the exact code path, both arms.

Arm A (1500) runs first and AGAIN after arm B: the second A run's mean IC must equal the
first bit-for-bit (zero-drift gate — proves the override leaked nothing and the restore is
clean). Arm order and the paired decision rule are fixed in hypothesis.md; this script
only measures.

Usage:
    python -m experiments.007_universe_cutoff.run --profile full
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
from src.model import composite as model
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")   # frozen slice split
from src.backtest import smoke_e2e as smoke                          # engine-pass machinery


def _build_chain(con, cfg: dict) -> dict:
    """The derived chain, rebuilt through its real entry points for THIS cfg's top_n."""
    from src.universe import eligibility, rank, winners
    from src.features import matrix, panel
    t0 = time.monotonic()
    st = {"rank": rank.build(con, cfg), "eligible": eligibility.build(con, cfg),
          "winners": winners.build(con, cfg), "panel": panel.build(con, cfg),
          "matrix": matrix.build(con, cfg)}
    st["seconds"] = time.monotonic() - t0
    return st


def _shape(con) -> dict:
    months, rows, labeled = con.execute(
        "SELECT count(DISTINCT mdate), count(*), "
        "count(*) FILTER (WHERE next_month_ret IS NOT NULL) FROM feature_matrix").fetchone()
    med1000, med1500 = con.execute(
        "SELECT median(med3_cr) FILTER (WHERE rank <= 1000), "
        "median(med3_cr) FILTER (WHERE rank <= 1500) FROM universe_rank").fetchone()
    n_elig, illiq, in1000, over1000 = con.execute(
        "SELECT count(*), avg(CASE WHEN med3 < 5.0 * 1.0e7 THEN 1.0 ELSE 0.0 END), "
        "count(*) FILTER (WHERE rank <= 1000), count(*) FILTER (WHERE rank > 1000) "
        "FROM eligible WHERE eligible").fetchone()
    return {"decision_months": months, "matrix_rows": rows, "labeled_rows": labeled,
            "eligible_symbol_months": n_elig,
            "eligible_in_1000": in1000, "eligible_1001_1500": over1000,
            "median_turnover_cr_rank1000": med1000, "median_turnover_cr_rank1500": med1500,
            "share_eligible_below_5cr": illiq}


def _light_metrics(con) -> dict:
    """Slice metrics for the current matrix: mean monthly IC, precision, pick stats."""
    rows, cutoff = smoke._fetch(con)
    assert rows, "no labeled rows — the chain rebuild produced an empty matrix"
    val, test, boundary = P41.split_slice(rows, cutoff)
    by_month: dict[str, list] = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    months = sorted(by_month)
    sym_at = 2 + len(model.PANEL_FEATURES) + 1
    ics, picks = [], []
    for m in months:
        rs = by_month[m]
        scores = model.score_month_2f(rs)
        pairs = [(s, r[1]) for s, r in zip(scores, rs) if s is not None and r[1] is not None]
        ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
        if ic is not None:
            ics.append((m, ic, len(pairs)))
        scored = [(s, rs[i][sym_at], rs[i][1]) for i, s in enumerate(scores) if s is not None]
        if len(scored) < 20:
            continue
        k = max(1, round(len(scored) * 0.05))
        top = sorted(scored, key=lambda p: (-p[0], p[1]))[:k]   # ties broken by symbol
        picks += [(ret, s) for _, s, ret in top]
    mean_ic, n_ic = P41._mean_ic(ics)
    labeled = [p for p in picks if p[0] is not None]
    hit_rate = (sum(1 for r, _ in labeled if r > 0) / len(labeled)) if labeled else None
    return {"months": months, "by_month": by_month, "val": val, "boundary": str(boundary),
            "mean_monthly_ic": mean_ic, "ic_months": n_ic, "monthly_ics": ics,
            "picks": len(picks), "pick_hit_rate": hit_rate,
            "mean_pick_ret": (sum(r for r, _ in labeled) / len(labeled)) if labeled else None,
            "cutoff": str(cutoff)}


def _measure(cfg: dict, label: str) -> dict:
    """One arm: rebuild the chain for cfg, then measure shape + slice metrics + engine pass."""
    t0 = time.monotonic()
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        chain = _build_chain(con, cfg)
    finally:
        con.close()
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        shape = _shape(con)
        light = _light_metrics(con)
        sessions = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT date FROM bhav ORDER BY date").fetchall()]
    finally:
        con.close()
    # engine pass at the shipped defaults, through smoke's own machinery (both arms
    # identical code): escalate N=2, 0.5%/side, 12 consecutive slice months
    picks_by_month = {m: smoke._picks(light["by_month"][m]) for m in light["months"]}
    engine = smoke._engine_pass(cfg, "escalate", 2, sessions, light["by_month"],
                                light["months"], picks_by_month, light["val"])
    print(f"[{label}] chain {chain['seconds']:.0f}s | eligible {shape['eligible_symbol_months']:,} "
          f"| IC {light['mean_monthly_ic']:.6f} ({light['ic_months']} mo) "
          f"| precision {light['pick_hit_rate']:.1%} | picks {light['picks']:,} "
          f"| engine {engine['total_return']:+.2%}, {engine['non_fills']} non-fills, "
          f"{len(engine['forced_exits'])} forced", flush=True)
    return {"chain_seconds": chain["seconds"], "shape": shape,
            "mean_monthly_ic": light["mean_monthly_ic"], "ic_months": light["ic_months"],
            "monthly_ics": light["monthly_ics"],
            "pick_count": light["picks"], "pick_hit_rate": light["pick_hit_rate"],
            "mean_pick_ret": light["mean_pick_ret"], "boundary": light["boundary"],
            "cutoff": light["cutoff"],
            "engine_pass": {k: engine[k] for k in
                            ("fills", "non_fills", "non_fill_reasons", "forced_exits",
                             "completed_picks", "pick_hit_rate", "churn_per_month",
                             "final_equity", "total_return", "exit_gate")}}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()

    print("E007 arm A: top-1500 (BRD control) — rebuilding the derived chain", flush=True)
    a = _measure(load(args.profile), "A top-1500")

    print("E007 arm B: top-1000 (the review's cut) — rebuilding the derived chain", flush=True)
    cfg_b = load(args.profile)
    cfg_b["universe"]["top_n"] = 1000          # the ONLY knob; in-memory, per arm
    b = _measure(cfg_b, "B top-1000")

    print("E007 restore: rebuilding the chain at 1500 (the database must be left "
          "BRD-normative)", flush=True)
    a2 = _measure(load(args.profile), "restore/1500")
    assert a2["mean_monthly_ic"] == a["mean_monthly_ic"], \
        (f"zero-drift gate FAILED: arm-A IC {a['mean_monthly_ic']!r} != post-restore "
         f"{a2['mean_monthly_ic']!r} — the top_n override leaked or the restore diverged")
    assert a2["pick_count"] == a["pick_count"] and a2["shape"] == a["shape"], \
        "post-restore universe shape or pick count drifted from arm A"

    # paired monthly t on the IC difference (A - B), month-aligned, frozen P4.1 code
    cmp_ab = P41._paired_t(a["monthly_ics"], b["monthly_ics"])

    out = {
        "experiment": "E007_universe_cutoff", "profile": args.profile, "git_hash": git,
        "hypothesis": os.path.join(os.path.dirname(__file__), "hypothesis.md"),
        "data_cutoff": a["cutoff"], "validation_boundary": a["boundary"],
        "arms": {
            "top_1500": {k: v for k, v in a.items() if k != "monthly_ics"},
            "top_1000": {k: v for k, v in b.items() if k != "monthly_ics"},
            "restore_check": {"mean_monthly_ic": a2["mean_monthly_ic"],
                              "pick_count": a2["pick_count"], "shape": a2["shape"]},
        },
        "paired_ic_comparison": cmp_ab,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"\nE007: paired IC comparison over {cmp_ab['n_months']} shared months: "
          f"A-B diff {cmp_ab['mean_diff']:+.5f}, t = {cmp_ab['t']:+.2f}, "
          f"p = {cmp_ab['p']:.4f}")
    sa, sb = a["shape"], b["shape"]
    print(f"  shape: eligible {sa['eligible_symbol_months']:,} -> {sb['eligible_symbol_months']:,} "
          f"(-{sa['eligible_symbol_months'] - sb['eligible_symbol_months']:,}); "
          f"below-5cr share {sa['share_eligible_below_5cr']:.1%} -> "
          f"{sb['share_eligible_below_5cr']:.1%}")
    ea, eb = a["engine_pass"], b["engine_pass"]
    print(f"  engine pass (escalate, 0.5%): non-fills {ea['non_fills']} -> {eb['non_fills']}, "
          f"forced {len(ea['forced_exits'])} -> {len(eb['forced_exits'])}, "
          f"return {ea['total_return']:+.2%} -> {eb['total_return']:+.2%}")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
