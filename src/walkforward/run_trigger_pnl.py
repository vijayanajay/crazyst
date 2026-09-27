"""Diagnostic — decompose a committed walk-forward run's P&L by closing trigger and rank
the §8 rules by rupee damage. Diagnostic, not an experiment: it changes no rule, adopts
nothing, and pre-registers no bar (BRD 12 pre-registration applies to rule changes, not
autopsies of a committed run). The module under it (src.walkforward.diag_trigger_pnl) is
self-checked; this runner wires it to the committed artifacts:

  - the run's fill log + decisions  -> runs/walkforward/harness_results.json (default;
    the shipped-default reference run)
  - month-end closes for the marks  -> bhav (series EQ) at the run's decision dates

Per closing trigger: lots closed, hit rate, mean realized return, total/mean timing delta
(realized exit vs the close at the exit month's decision date; POSITIVE delta = the rule
sold cheaper than the month-end it skipped = rupees destroyed). Ranked most-damaging
first. Still-open lots are marked at the final decision date and reported separately
(their exit rule has not spoken yet). The ten worst timing deltas by name close the loop.

Caveats carried into results.json verbatim: the counterfactual is the month-end review
cadence (not "sell never"); per-side flat costs cancel in the delta but impact differences
do not (second-order at these notionals); delisted/suspended names have no month-end mark
and are excluded from the timing ranking (counted per trigger); still-open lots are outside
the ranking by construction.

python -m src.walkforward.run_trigger_pnl [--run runs/walkforward/harness_results.json]
"""
from __future__ import annotations

import argparse
import duckdb
import json
import os
import sys

from src.config import load
from src.walkforward import diag_trigger_pnl as T


def _decision_close(con, symbols: set[str], dates: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for sym, d, c in con.execute(
            "SELECT symbol, date, close FROM bhav WHERE series = 'EQ' "
            "AND symbol IN (SELECT unnest(CAST($sy AS VARCHAR[]))) "
            "AND date IN (SELECT unnest(CAST($ds AS DATE[])))",
            {"sy": sorted(symbols), "ds": dates}).fetchall():
        out.setdefault(sym, {})[str(d)] = c
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join("runs", "walkforward",
                                                  "harness_results.json"))
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    with open(args.run) as f:
        run = json.load(f)
    assert run["config"]["n_slots"] == 8, \
        f"this autopsy targets the adopted 8-slot book; got n_slots={run['config']['n_slots']}"
    ev = run["engine"]
    fill_log, folds = ev["fill_log"], run["test_months"]

    cfg = load(args.profile)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        marks = _decision_close(con, {f["symbol"] for f in fill_log}, folds)
    finally:
        con.close()
    close_at = {s: {d[:7]: px for d, px in marks[s].items()} for s in marks}

    reasons = T.build_sell_reasons(fill_log)
    # the committed results.json carries the FILL LOG, not raw trade events - rebuild the
    # TradeEvents from it exactly (cost = the engine's fill_cost formula, so FIFO returns
    # and pairing are bit-faithful)
    events = sorted(
        ({"date": f["fill_date"], "symbol": f["symbol"], "buy": f["qty"] > 0,
          "qty": f["qty"], "price": f["price"],
          "cost": abs(f["qty"]) * f["base_price"] * (f["cost_pct"] + f["impact_pct"]),
          "mid_month": f["reason"].startswith("trigger_"),
          "signal_month": f["signal_date"][:7]} for f in fill_log),
        key=lambda e: (e["date"], e["symbol"], e["qty"]))
    sold = T.close_lots(events, reasons)
    open_pos = T.open_lots(events)
    timed = T.timing_pnl(sold, close_at)
    ranked = sorted(T.rank_triggers(timed).items(), key=lambda kv: -kv[1]["total_delta_rs"])

    # still-open lots at the final decision mark: unrealized vs basis, same convention
    last_m = folds[-1][:7]
    open_rows = []
    for lot in open_pos:
        px = close_at.get(lot["symbol"], {}).get(last_m)
        open_rows.append({**lot, "mark": px,
                          "unrealized_rs": (lot["qty"] * (px - lot["basis_px"])
                                            if px is not None else None)})

    total_destroyed = sum(v["total_delta_rs"] for _, v in ranked)
    worst = sorted([p for p in timed if p["delta_rs"] is not None],
                   key=lambda p: -p["delta_rs"])[:10]
    # per-symbol concentration: is a trigger's "destruction" broad or one name's whipsaw?
    sym_delta: dict[str, float] = {}
    for p in timed:
        if p["delta_rs"] is not None:
            sym_delta[p["symbol"]] = sym_delta.get(p["symbol"], 0.0) + p["delta_rs"]
    top_syms = sorted(sym_delta.items(), key=lambda kv: -kv[1])[:5]
    worst_sym = top_syms[0][0] if top_syms else None
    excl_worst = sorted(
        ((k, sum(p["delta_rs"] for p in timed if p["trigger"] == k
                 and p["symbol"] != worst_sym and p["delta_rs"] is not None))
          for k, _ in ranked), key=lambda kv: -kv[1]) if worst_sym else ranked

    out = {
        "diagnostic": "trigger-level P&L decomposition (timing counterfactual)",
        "source_run": args.run, "source_git_hash": run["git_hash"],
        "n_slots": run["config"]["n_slots"], "folds": folds,
        "conventions": {
            "delta_rs": "qty x (close_at_exit_month_decision_date - exec_px); POSITIVE = the "
                        "rule sold cheaper than the month-end it skipped (destroyed)",
            "counterfactual": "the month-end review cadence, not 'sell never'; costs cancel, "
                              "impact differences second-order",
            "excluded": "no month-end mark (delisted/suspended) -> no_cf, outside the ranking; "
                        "still-open lots reported separately",
        },
        "trigger_ranking": [{"trigger": k, **v} for k, v in ranked],
        "total_timing_delta_rs": total_destroyed,
        "symbol_concentration": {
            "top_syms_rs": top_syms,
            "trigger_ranking_excluding": worst_sym,
            "trigger_ranking_excluding_deltas": dict(excl_worst),
        },
        "completed_picks": len(sold), "picks_no_cf": sum(1 for p in timed if p["delta_rs"] is None),
        "still_open": open_rows,
        "worst_timing_lots": worst,
        "fill_reason_counts": {r: sum(1 for f in fill_log if f["reason"] == r)
                               for r in sorted({f["reason"] for f in fill_log})},
    }
    path = os.path.join("runs", "walkforward", "trigger_pnl_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"trigger P&L decomposition of {args.run} ({run['git_hash'][:12]}, 8 slots, "
          f"{len(folds)} folds, {len(sold)} closed lots, {len(open_pos)} lots open)")
    print(f"{'trigger':<20}{'lots':>5}{'hit':>7}{'mean ret':>10}{'total delta':>14}"
          f"{'mean/lot':>11}{'no_cf':>7}")
    for k, v in ranked:
        print(f"{k:<20}{v['lots']:>5}{v['hit_rate']:>7.0%}{v['mean_return']:>10.2%}"
              f"{v['total_delta_rs']:>14,.0f}{v['mean_delta_rs']:>11,.0f}{v['no_cf']:>7}")
    print(f"{'TOTAL':<20}{'':>5}{'':>7}{'':>10}{total_destroyed:>14,.0f}")
    if top_syms:
        print(f"\nby symbol (top 5 by destroyed rupees): "
              + ", ".join(f"{s} {d:+,.0f}" for s, d in top_syms))
        print(f"trigger ranking EXCLUDING {worst_sym}: "
              + ", ".join(f"{k} {v:+,.0f}" for k, v in excl_worst))
    print("\nstill open (marked at the final decision date):")
    for r in open_rows:
        px = f"{r['mark']:.2f}" if r["mark"] is not None else "no mark"
        ur = f"{r['unrealized_rs']:+,.0f}" if r["unrealized_rs"] is not None else "n/a"
        print(f"  {r['symbol']:<12} {r['qty']:>5} sh  basis {r['basis_px']:>9.2f}  "
              f"mark {px:>9}  unrealized {ur}")
    print("\nten worst timing deltas (the rule sold cheapest vs the skipped month-end):")
    for p in worst:
        print(f"  {p['sell_month']}  {p['symbol']:<12} {p['qty']:>5} sh  "
              f"exec {p['exec_px']:>9.2f} -> cf {p['cf_px']:>9.2f}  "
              f"delta {p['delta_rs']:>+10,.0f}  [{p['trigger']}]")
    print(f"\nwrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
