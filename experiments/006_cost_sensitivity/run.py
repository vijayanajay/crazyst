"""E006 — cost sensitivity: composite_2f's top-5% picks scored net of 0.2/0.5/1.0% per side
on the validation slice (run only after hypothesis.md was written).

Each decision month: composite_2f scores (P4.1b's construction, imported so experiments
cannot drift), top k = max(1, round(n * 0.05)) picks, gross forward return next_month_ret,
net = gross - 2*cost. Reported per cost level and per as-of rank group (<= 600 vs > 600,
the BRD 9.7 boundary): mean pick return per month, monthly hit rate (net > 0), plus the
size-bucket split for the report.

Usage:
    python -m experiments.006_cost_sensitivity.run --profile full

Writes results.json (config snapshot, git hash, cutoff — BRD 13) and prints the table.
Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the run completed.
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

P41 = importlib.import_module("experiments.004_composite_v0.run")   # shared slice + helpers
P41B = importlib.import_module("experiments.004b_composite_2feat.run")  # composite_2f scoring
COSTS = (0.002, 0.005, 0.010)          # per side, pre-registered (BRD 9.7 / plan 4.4)
RANK_BOUNDARY = 600                    # the BRD 9.7 line


SYM = 2 + len(P41B.FEATURES) + 1   # symbol column in our own fetch (features + liquidity_rank)


def _fetch(con):
    rows = con.execute(
        "SELECT mdate, next_month_ret, " + ", ".join(P41B.FEATURES) +
        ", liquidity_rank, symbol, size_bucket FROM feature_matrix "
        "WHERE next_month_ret IS NOT NULL ORDER BY mdate").fetchall()
    cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    return rows, cutoff


def _picks(rs):
    """Top-5% of composite_2f scores for one month -> (row indices into rs)."""
    scores = P41B.score_month_2f(rs)
    scored = [(s, i) for i, s in enumerate(scores) if s is not None]
    if len(scored) < 20:
        return []
    k = max(1, round(len(scored) * 0.05))
    return [i for _, i in sorted(scored, key=lambda p: -p[0])[:k]]


def _group_stats(pick_rows, cost):
    """Mean net return per pick-month and monthly hit rate for one group at one cost."""
    nets = [p["gross"] - 2 * cost for p in pick_rows]
    if not nets:
        return None
    months = {p["mdate"] for p in pick_rows}
    hit = sum(1 for n in nets if n > 0) / len(nets)
    return {"picks": len(nets), "months": len(months),
            "mean_net": sum(nets) / len(nets), "hit_rate": hit}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff = _fetch(con)
    finally:
        con.close()
    assert rows, "no labeled rows — build feature_matrix first"
    months = sorted({str(r[0]) for r in rows})
    assert len(months) > 120 and months[0] < "2012", \
        f"expected the full-history matrix (got {len(months)} months from {months[0]})"
    val, test, boundary = P41.split_slice(rows, cutoff)
    assert val, "the validation slice must be non-empty"

    by_month = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    picks = []
    for m, rs in sorted(by_month.items()):
        for i in _picks(rs):
            r = rs[i]
            rank = r[2 + len(P41B.FEATURES)]
            picks.append({"mdate": str(r[0]), "symbol": r[SYM],
                          "gross": r[1], "rank": rank, "bucket": r[-1]})

    # per (cost, rank group) and (cost, bucket)
    results = {"by_rank_group": {}, "by_bucket": {}}
    for cost in COSTS:
        for label, pred in (("rank<=600", lambda p: p["rank"] <= RANK_BOUNDARY),
                            ("rank>600", lambda p: p["rank"] > RANK_BOUNDARY),
                            ("all", lambda p: True)):
            grp = [p for p in picks if pred(p)]
            results["by_rank_group"].setdefault(label, {})[str(cost)] = _group_stats(grp, cost)
        for b in sorted({p["bucket"] for p in picks}):
            grp = [p for p in picks if p["bucket"] == b]
            results["by_bucket"].setdefault(b, {})[str(cost)] = _group_stats(grp, cost)

    # the pre-registered half-edge scan: smallest cost where the >600 group's mean net
    # falls below half its 0.2% value
    g = results["by_rank_group"]["rank>600"]
    base = g["0.002"]["mean_net"] if g.get("0.002") else None
    half_at = None
    if base is not None and base > 0:
        for cost in COSTS:
            st = g.get(str(cost))
            if st and st["mean_net"] < 0.5 * base:
                half_at = cost
                break

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "E006_cost_sensitivity", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "validation_boundary": str(boundary),
        "validation_months": len(by_month), "validation_rows": len(val),
        "excluded_test_months": len({str(r[0]) for r in test}),
        "costs_per_side": list(COSTS), "rank_boundary": RANK_BOUNDARY,
        "pick_rule": "composite_2f top-5% per month; net = gross - 2*cost",
        "picks_total": len(picks),
        "universe_note": "as-of top-1500, floor OFF; BRD-owner decisions pending flag",
        "random_seed": cfg["backtest"]["random_seed"],
        "results": results,
        "rank600_edge_halves_at": half_at,
        "runtime_seconds": round(time.monotonic() - t0, 3),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"E006: {len(picks):,} pick-months (composite_2f top-5%, {len(by_month)} months, "
          f"boundary {boundary}) — wrote {path}", flush=True)
    print(f"\n{'group':<14}{'cost/side':>10}{'picks':>8}{'mean net':>10}{'hit':>7}")
    for label in ("all", "rank<=600", "rank>600"):
        for cost in COSTS:
            st = results["by_rank_group"][label].get(str(cost))
            if st:
                print(f"{label:<14}{cost:>10.1%}{st['picks']:>8,}"
                      f"{st['mean_net'] * 100:>9.2f}%{st['hit_rate'] * 100:>6.1f}%")
    print("\nper size bucket (mean net % at 0.2 / 0.5 / 1.0):")
    for b, levels in results["by_bucket"].items():
        cells = [levels.get(str(c)) for c in COSTS]
        print(f"  {b:<10}" + "  ".join(
            f"{c['mean_net'] * 100:>6.2f}%" if c else "     —" for c in cells))
    if half_at:
        print(f"\nthe >600 edge halves at {half_at:.1%} per side", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
