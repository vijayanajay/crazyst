"""Break-even arithmetic: pick edge per month vs cost per month across holding horizons.

The decision basis for E016 (LEDGER block "Break-even arithmetic", 2026-09-27): does the
top-5% pick edge survive longer holding periods, or is it a 1-month phenomenon that the
engine's monthly churn was required to capture?

Three estimators over the 145-month validation slice (P4.1 split, labeled picks == E012's
4,579 pin):
  label  — chain feature_matrix next_month_ret; h>1 drops legs whose symbol loses its
           label mid-hold (optimistic: those are disproportionately delistings);
  dead   — worst case: every missing mid-hold label is a -100% leg (pessimistic bound);
  price  — the truth: actual adj_close month-end marks, entry at the entry month's own
           month-end mark, exit at the last traded mark on or before the exit month
           (sell-at-last-trade delisting proxy). No leg is dropped.

Costs follow the E006 convention: net = gross - 0.4% per round trip; h>1 pays entry+exit
only (2 round trips per hold... i.e. one buy + one sell), h=1 pays one round trip per month.

python -m experiments.016_low_turnover.breakeven
"""
from __future__ import annotations

import json
import math
import os

import duckdb

from src.config import load
from src.backtest import smoke_e2e as smoke
P41 = __import__("importlib").import_module("experiments.004_composite_v0.run")

COST_RT = 0.004          # E006 convention: 2 x 0.2% per round trip
HORIZONS = (1, 3, 6, 12)


def _load():
    cfg = load("full")
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff = smoke._fetch(con)
        lab = con.execute(
            "SELECT CAST(mdate AS VARCHAR), symbol, next_month_ret FROM feature_matrix "
            "WHERE next_month_ret IS NOT NULL").fetchall()
        marks_raw = con.execute(
            "SELECT symbol, substr(CAST(date AS VARCHAR),1,7) AS ym, "
            "arg_max(adj_close, date) FROM adj_close GROUP BY symbol, ym").fetchall()
    finally:
        con.close()
    val, _, _ = P41.split_slice(rows, cutoff)
    by_month: dict[str, list] = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    picks = {m: smoke._picks(by_month[m]) for m in sorted(by_month)}
    return picks, {(m, s): r for m, s, r in lab}, \
        {s: {ym: p for ym, p in ms if p and p > 0}
         for s, ms in _group(marks_raw).items()}


def _group(rows):
    g: dict[str, list] = {}
    for s, ym, p in rows:
        g.setdefault(s, []).append((ym, p))
    return g


def _label_stats(fwd, picks, months, h, dead=None):
    rets = []
    for i in range(0, len(months) - h + 1, h):
        ms = months[i:i + h]
        for sym in (p["symbol"] for p in picks[months[i]]):
            path = [fwd.get((mm, sym)) for mm in ms]
            if any(r is None for r in path):
                if dead is None:
                    continue
                rets.append((1 + dead) * math.prod(1 + r for r in path if r is not None) - 1)
                continue
            rets.append(math.prod(1 + r for r in path) - 1)
    return rets


def _price_stats(marks, picks, months, h):
    def last_mark(sym, ym):
        ms = marks.get(sym)
        if not ms:
            return None
        cands = [k for k in ms if k <= ym]
        return ms[max(cands)] if cands else None

    rets = []
    for i in range(0, len(months) - h + 1, h):
        e_ym = months[i][:7]
        x_ym = months[i + h][:7] if i + h < len(months) else None
        if x_ym is None:
            continue                       # last book has no exit month
        for sym in (p["symbol"] for p in picks[months[i]]):
            pe, px = last_mark(sym, e_ym), last_mark(sym, x_ym)
            if pe is None or px is None:
                continue                   # no tradable mark at all on one side
            rets.append(px / pe - 1)
    return rets


def main(argv=None) -> int:
    picks, fwd, marks = _load()
    months = sorted(picks)
    out = {}
    print(f"{'hold':>5} {'legs':>6} | {'label net/mo':>12} {'dead net/mo':>12} | "
          f"{'price legs':>10} {'price net/hold':>14} {'price net/mo':>12}")
    for h in HORIZONS:
        cost = (1 if h == 1 else 2) * COST_RT
        lab = _label_stats(fwd, picks, months, h)
        dead = _label_stats(fwd, picks, months, h, dead=-1.0)
        pri = _price_stats(marks, picks, months, h)
        conv = lambda rs: (1 + sum(rs) / len(rs) - cost) ** (1 / h) - 1 if rs else float("nan")  # noqa: E731
        out[h] = {"label_legs": len(lab), "label_net_per_month": conv(lab),
                  "dead_net_per_month": conv(dead), "price_legs": len(pri),
                  "price_mean_gross": sum(pri) / len(pri), "cost_per_leg": cost,
                  "price_net_per_hold": sum(pri) / len(pri) - cost,
                  "price_net_per_month": conv(pri)}
        print(f"{h:>4}m {len(lab):>6} | {conv(lab):>12.4%} {conv(dead):>12.4%} | "
              f"{len(pri):>10} {out[h]['price_net_per_hold']:>14.4%} {conv(pri):>12.4%}")

    # ---- checks: the h=1 label estimator must reproduce the committed pins exactly ----
    smoke_res = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..",
                                            "runs", "smoke_e2e", "smoke_results.json")))
    h1 = _label_stats(fwd, picks, months, 1)
    mg = sum(h1) / len(h1)
    assert len(h1) == 4_579, len(h1)
    assert abs(mg - smoke_res["light_pass"]["mean_gross"]) < 1e-12, (mg,)
    for h in HORIZONS:
        s = out[h]
        assert abs(s["price_net_per_hold"] -
                   (s["price_mean_gross"] - s["cost_per_leg"])) < 1e-12
        assert s["price_legs"] > 0
        # the price estimator is a superset: it prices legs whose label vanished mid-hold
        assert h == 1 or s["price_legs"] >= s["label_legs"], (h, s["price_legs"], s["label_legs"])
    # bounds ordering: label (skip-missing) >= price (truth) at every horizon
    assert all(out[h]["label_net_per_month"] >= out[h]["price_net_per_month"] - 1e-9
               for h in HORIZONS), {h: (out[h]["label_net_per_month"],
                                        out[h]["price_net_per_month"]) for h in HORIZONS}
    print("PASS: breakeven (h=1 == smoke light-pass pins; net identity; bounds ordered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
