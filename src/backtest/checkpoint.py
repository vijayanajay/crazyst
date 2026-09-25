"""Phase 5 checkpoint — the plan's line: "run engine on synthetic data with a trivial
'buy momentum' model. Show equity curve + trade log."

This module is the wiring the checkpoint asks to see, end to end:

  decision date -> toy momentum scores -> Facts -> Portfolio decisions (§8 rules)
  -> sized Orders -> Engine T+1 open fills -> cash/position walk -> equity curve
  -> §11 metrics + 5.6 bucket attribution -> checkpoint pack (JSON + printed tables)

The toy market: 6 names, 3 decision months + a final April mark, every bar with
open == close so fill prices are exactly the marks. Zero costs (cost math is engine-tested;
E006's cost levels are a Phase 6 report parameter) and no ADV history (the engine's gate is
off, impact 0) keep every equity value hand-computable to the rupee. n_slots = 2.

The story the tape tells, each rule firing once (all asserted):
- Jan: ME (+10%) and MO (+5%) lead the momentum board -> initial top-2 selection,
  fills Feb 02 at the open (T+1 across the month boundary).
- Feb: ME fades to the 5th of 6 ranks -> monthly review sells it; MB (+7.9%) is the only
  candidate inside the 15% replace percentile -> the replacement buy (221 sh @ 218) fills
  Mar 02.
- Mar: MO gaps down through its 8% stop (close 96 vs the 96.6 limit) -> Trigger B stop
  sells it Mar 05 (mid-month churn); no candidate is inside the replace percentile at the
  Mar review -> that slot holds CASH (§8.1 fallback).
- Final: equity 94,527 from 100,000 (the toy tape is hostile: both completed picks are
  losers — ME -1,818 and MO -4,760 realized, MB +1,105 still open). The checkpoint's point
  is determinism and exact paper math, not profit.

Trigger A/C never fire on this tape (monthly momentum spread stays under the 20% relative
excess) — they are unit-tested in src.backtest.portfolio. Portfolio sell state moves at
decision time (its docstring's contract); cash and positions move at the T+1 fill.

python -m src.backtest.checkpoint runs it twice (determinism), asserts every number above,
prints the equity curve, trade log and bucket table, and writes
src/backtest/checkpoint_results.json.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

from src.backtest.attribution import assert_consistent, bucket_attribution
from src.backtest.engine import Engine, Market, Order
from src.backtest.metrics import (TradeEvent, churn_per_month, completed_picks, cagr,
                                  month_hit_rate, monthly_returns, pick_hit_rate,
                                  sharpe_monthly)
from src.backtest.portfolio import Facts, Portfolio

START_CAPITAL = 100_000.0
N_SLOTS = 2

SESSIONS = [
    "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12",
    "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06", "2026-02-09",
    "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06", "2026-03-09",
    "2026-04-01",
]
MONTH_ENDS = ["2026-01-12", "2026-02-09", "2026-03-09"]

# close == open on every bar; the momentum score of a month is last close / first - 1
CLOSES: dict[str, list[tuple[str, float]]] = {
    "MO": [("2026-01-05", 100.0), ("2026-01-06", 101.0), ("2026-01-07", 102.0),
           ("2026-01-08", 103.0), ("2026-01-09", 104.0), ("2026-01-12", 105.0),
           ("2026-02-02", 105.0), ("2026-02-03", 106.0), ("2026-02-04", 107.0),
           ("2026-02-05", 108.0), ("2026-02-06", 109.0), ("2026-02-09", 110.0),
           ("2026-03-02", 110.0), ("2026-03-03", 100.0), ("2026-03-04", 96.0),
           ("2026-03-05", 95.0), ("2026-03-06", 95.0), ("2026-03-09", 95.0),
           ("2026-04-01", 95.0)],
    "ME": [("2026-01-05", 50.0), ("2026-01-06", 51.0), ("2026-01-07", 52.0),
           ("2026-01-08", 53.0), ("2026-01-09", 54.0), ("2026-01-12", 55.0),
           ("2026-02-02", 55.0), ("2026-02-03", 55.0), ("2026-02-04", 54.0),
           ("2026-02-05", 54.0), ("2026-02-06", 53.0), ("2026-02-09", 53.0),
           ("2026-03-02", 53.0), ("2026-03-03", 52.0), ("2026-03-04", 52.0),
           ("2026-03-05", 51.0), ("2026-03-06", 51.0), ("2026-03-09", 51.0),
           ("2026-04-01", 51.0)],
    "MB": [("2026-01-05", 200.0), ("2026-01-06", 200.0), ("2026-01-07", 201.0),
           ("2026-01-08", 201.0), ("2026-01-09", 202.0), ("2026-01-12", 202.0),
           ("2026-02-02", 202.0), ("2026-02-03", 205.0), ("2026-02-04", 208.0),
           ("2026-02-05", 211.0),           ("2026-02-06", 214.0), ("2026-02-09", 218.0),   # close 218 = Mar 02 open: the
                                                            # replacement sizes exactly
           ("2026-03-02", 218.0), ("2026-03-03", 219.0), ("2026-03-04", 220.0),
           ("2026-03-05", 221.0), ("2026-03-06", 222.0), ("2026-03-09", 223.0),
           ("2026-04-01", 223.0)],
    "FAD": [("2026-01-05", 80.0), ("2026-01-06", 79.0), ("2026-01-07", 78.0),
            ("2026-01-08", 77.0), ("2026-01-09", 76.0), ("2026-01-12", 75.0),
            ("2026-02-02", 75.0), ("2026-02-03", 74.0), ("2026-02-04", 73.0),
            ("2026-02-05", 72.0), ("2026-02-06", 71.0), ("2026-02-09", 70.0),
            ("2026-03-02", 70.0), ("2026-03-03", 69.0), ("2026-03-04", 69.0),
            ("2026-03-05", 68.0), ("2026-03-06", 68.0), ("2026-03-09", 68.0),
            ("2026-04-01", 68.0)],
    "FLAT1": [(d, 30.0) for d in SESSIONS],
    "FLAT2": [(d, 40.0) for d in SESSIONS],
}
SYMBOLS = tuple(CLOSES)

# as-of buckets the strategy saw at each buy's decision month (real runs: take these from
# feature_matrix.size_bucket rows)
BUCKETS = {("2026-01", "ME"): "201-600", ("2026-01", "MO"): "top200",
           ("2026-02", "MB"): "601-1500"}


def _cfg_backtest() -> dict:
    # config.yaml values except costs: zero here so the curve is exact on paper (declared)
    return {"backtest": {"cost_per_side_pct": 0.0, "purge_months": 1, "random_seed": 42,
                         "fill": {"max_position_adv_frac": 0.05, "impact_coef": 0.10,
                                  "impact_cap_pct": 1.0}}}


def _cfg_portfolio() -> dict:
    return {"portfolio": {
        "n_slots": N_SLOTS, "cash_earns": 0.0,
        "monthly_review_sell_below_top_pct": 0.25,
        "monthly_review_replace_above_top_pct": 0.15,
        "monthly_review": {"ma_below_consecutive_closes": 5},
        "midmonth": {"trigger_a_score_excess": 0.20, "trigger_a_cap": 2,
                     "trigger_b_stop_pct": 0.08, "trigger_b_trail_pct": 0.12,
                     "trigger_b_ma_close_below": 2, "trigger_b_deliv_z": -2.0,
                     "trigger_b_deliv_days": 3, "gsm_asm_stage_exit": 2},
        "churn_report_threshold": 1.5,
    }}


# ---- the toy model -------------------------------------------------------------------------------


def _close(sym: str, d: str) -> float:
    """Last close on or before d (the tape has no gaps, so 'last' is the current bar)."""
    return [px for dd, px in CLOSES[sym] if dd <= d][-1]


def month_scores(month: str) -> dict[str, float]:
    """Trivial buy-momentum model: score = first-to-last close return of the month."""
    out = {}
    for sym in SYMBOLS:
        px = [p for d, p in CLOSES[sym] if d[:7] == month]
        out[sym] = px[-1] / px[0] - 1.0
    return out


def rank_pct(scores: dict[str, float]) -> dict[str, float]:
    """Percentile from the top: 0 = best, (rank-1)/n with ties broken by symbol."""
    order = sorted(scores, key=lambda s: (-scores[s], s))
    return {s: i / len(order) for i, s in enumerate(order)}


def _facts(d: str) -> Facts:
    m0 = min(dd for dd in SESSIONS if dd[:7] == d[:7])
    return Facts(
        date=d,
        closes={s: [px for dd, px in CLOSES[s] if dd <= d] for s in SYMBOLS},
        dma_below_streak={s: 0 for s in SYMBOLS},          # no DMA exit on this tape
        month_high={s: max(px for dd, px in CLOSES[s] if m0 <= dd <= d) for s in SYMBOLS},
        scores=month_scores(d[:7]),
        rank_pct=rank_pct(month_scores(d[:7])),
        eligible=set(SYMBOLS),
        surveillance_stage={},
    )


# ---- the run -------------------------------------------------------------------------------------


def run_checkpoint() -> dict:
    mkt = Market(
        bars={s: [{"date": d, "open": px, "high": px, "low": px, "close": px,
                   "turnover": 1_000_000_000.0} for d, px in CLOSES[s]] for s in SYMBOLS},
        adv_median={},                       # no ADV -> engine's gate/impact off, exact marks
    )
    eng = Engine(mkt, _cfg_backtest())
    pf = Portfolio(_cfg_portfolio())
    cash, positions = START_CAPITAL, {}
    curve, trades, decisions_log, pending = [], [], [], []
    n_filled = 0

    def submit(orders: list[Order]) -> None:
        nonlocal n_filled
        if orders:
            eng.submit(orders)
            pending.extend(eng.fills[n_filled:])
            n_filled = len(eng.fills)

    for d in SESSIONS:
        # 1. T+1 fills landing today: sells first so proceeds fund same-day buys
        todays = sorted((f for f in pending if f.fill_date == d),
                        key=lambda f: f.qty > 0)     # sells (False) before buys (True)
        for f in todays:
            pending.remove(f)
            if f.qty > 0:
                assert positions.get(f.symbol, 0) == 0, f"averaging down on {f.symbol}"
                cash -= f.qty * f.price
                positions[f.symbol] = f.qty
                pf.apply_fill(f.symbol, f.qty, f.price)
            else:
                cash += -f.qty * f.price
                positions[f.symbol] = 0
                pf.apply_fill(f.symbol, f.qty, f.price)      # idempotent if already freed
            trades.append(TradeEvent(f.fill_date, f.symbol, f.qty > 0, f.qty, f.price,
                                     Engine.fill_cost(f), f.reason.startswith("trigger_"),
                                     f.signal_date[:7]))
            assert cash >= -1e-9, f"cash went negative on {d}: {cash}"

        # 2. decisions: Trigger B on any close (positions held); monthly branch above
        orders: list[Order] = []
        if d in MONTH_ENDS:
            pf.new_month()
            f = _facts(d)
            if not pf.held():                          # initial selection: top-N momentum
                picks = sorted(SYMBOLS, key=lambda s: -month_scores(d[:7])[s])[:N_SLOTS]
                for s in picks:
                    qty = math.floor((START_CAPITAL / N_SLOTS) / _close(s, d))
                    orders.append(Order(d, s, qty, "select_momentum"))
                    decisions_log.append({"date": d, "action": "buy", "symbol": s,
                                          "trigger": "select_momentum",
                                          "score_bought": month_scores(d[:7])[s],
                                          "score_sold": None, "qty": qty, "note": ""})
                submit(orders)
            else:
                sells = [x for x in pf.trigger_b(f) if x.action == "sell"]
                sells += [x for x in pf.monthly_review(f) if x.action == "sell"]
                seen: set[str] = set()
                for x in sells:
                    if x.symbol in seen:
                        continue                       # Trigger B and the review may both fire
                    seen.add(x.symbol)
                    qty = positions.get(x.symbol, 0)
                    decisions_log.append(_log_decision(d, x, qty))
                    if qty:
                        pf.apply_fill(x.symbol, -qty, _close(x.symbol, d))  # state moves now
                        orders.append(Order(d, x.symbol, -qty, x.trigger))
                buys = [x for x in pf.monthly_review(f)  # re-review: freed slots replaceable
                        if x.action == "buy"]
                for x in buys:
                    decisions_log.append(_log_decision(d, x, 0))
                # size buys by cash + expected sell proceeds (fill price = est: open == close)
                est = cash + sum(-o.qty * _close(o.symbol, d) for o in orders if o.qty < 0)
                for x in sorted(buys, key=lambda x: x.symbol):
                    px = _close(x.symbol, d)
                    qty = math.floor(est / px)
                    if qty > 0:
                        orders.append(Order(d, x.symbol, qty, x.trigger))
                        decisions_log[-1]["qty"] = qty
                        est -= qty * px
                submit(orders)
        elif any(v for v in positions.values()):
            for x in pf.trigger_b(_facts(d)):
                qty = positions.get(x.symbol, 0)
                decisions_log.append(_log_decision(d, x, qty))
                pf.apply_fill(x.symbol, -qty, _close(x.symbol, d))
                orders.append(Order(d, x.symbol, -qty, x.trigger))
            submit(orders)

        # 3. mark to market at the close
        mv = sum(q * _close(s, d) for s, q in positions.items() if q)
        curve.append({"date": d, "cash": cash, "market_value": mv, "equity": cash + mv})

    picks = completed_picks(trades)
    months_n = len({r["date"][:7] for r in curve})
    attr = bucket_attribution(trades, BUCKETS, months=months_n)
    return {
        "curve": curve,
        "trades": [{"signal_date": f.signal_date, "fill_date": f.fill_date,
                    "symbol": f.symbol, "qty": f.qty, "price": f.price,
                    "base_price": f.base_price, "cost_pct": f.cost_pct,
                    "impact_pct": f.impact_pct, "reason": f.reason} for f in eng.fills],
        "decisions": decisions_log,
        "picks": picks,
        "metrics": {
            "pick_hit_rate": pick_hit_rate(picks),
            "month_hit_rate": month_hit_rate(picks, months_n),
            "monthly_returns": monthly_returns(curve),
            "cagr": cagr(curve),
            "sharpe_monthly": sharpe_monthly(curve),
            "churn_per_month": churn_per_month(trades, months_n),
            "final_equity": curve[-1]["equity"],
            "total_return": curve[-1]["equity"] / START_CAPITAL - 1.0,
        },
        "buckets": attr,
    }


def _log_decision(d: str, x, qty: int) -> dict:
    return {"date": d, "action": x.action, "symbol": x.symbol, "trigger": x.trigger,
            "score_sold": x.score_sold, "score_bought": x.score_bought,
            "qty": qty if x.action == "sell" else None, "note": x.note}


# ---- the checkpoint assertions -------------------------------------------------------------------


def _self_check() -> None:
    r1, r2 = run_checkpoint(), run_checkpoint()
    assert (r1["curve"] == r2["curve"] and r1["trades"] == r2["trades"]
            and r1["decisions"] == r2["decisions"]), "checkpoint replay diverged (determinism)"

    # the trade log: exactly 5 fills, each hand-derived (engine sorts by date, symbol, qty)
    expected = [
        ("2026-01-12", "2026-02-02", "ME", 909, 55.0, "select_momentum"),
        ("2026-01-12", "2026-02-02", "MO", 476, 105.0, "select_momentum"),
        ("2026-02-09", "2026-03-02", "MB", 221, 218.0, "replace"),
        ("2026-02-09", "2026-03-02", "ME", -909, 53.0, "monthly_review"),
        ("2026-03-04", "2026-03-05", "MO", -476, 95.0, "trigger_b_stop"),
    ]  # engine order key = (signal_date, symbol, qty): "MB" < "ME" on Mar 02
    got = [(t["signal_date"], t["fill_date"], t["symbol"], t["qty"], t["price"], t["reason"])
           for t in r1["trades"]]
    assert got == expected, got
    assert all(t["cost_pct"] == 0.0 and t["impact_pct"] == 0.0 for t in r1["trades"])

    # equity curve, hand-computed to the rupee (zero costs, open == close). Paper walk:
    #   Jan 12: select ME 909 @55 (49,995) + MO 476 @105 (49,980) -> cash 25.0 after Feb 02
    #   Feb 09: review sells ME (rank 4/6 > 0.25); ME 909 @53 -> cash 48,202; MB 221 @218
    #           (48,178) -> cash 24.0 after Mar 02. March: MO 96 <= 96.6 stop -> Trigger B
    #   Mar 05: MO 476 @95 -> cash 45,244. Mar review: no candidate in the top 15% -> cash
    #   P&L at Apr 01: ME -1,818 realized, MO -4,760 realized, MB +1,105 open, equity 94,527
    want = {"2026-01-05": 100_000.0, "2026-01-06": 100_000.0, "2026-01-07": 100_000.0,
            "2026-01-08": 100_000.0, "2026-01-09": 100_000.0, "2026-01-12": 100_000.0,
            "2026-02-02": 100_000.0, "2026-02-03": 100_476.0, "2026-02-04": 100_043.0,
            "2026-02-05": 100_519.0, "2026-02-06": 100_086.0, "2026-02-09": 100_562.0,
            "2026-03-02": 100_562.0, "2026-03-03": 96_023.0, "2026-03-04": 94_340.0,
            "2026-03-05": 94_085.0, "2026-03-06": 94_306.0, "2026-03-09": 94_527.0,
            "2026-04-01": 94_527.0}
    for row in r1["curve"]:
        assert abs(row["equity"] - want[row["date"]]) < 1e-9, (row, want[row["date"]])
    assert abs(r1["curve"][-1]["cash"] - 45_244.0) < 1e-9, r1["curve"][-1]

    # metrics: both completed picks are losers; MB stays open
    m = r1["metrics"]
    assert m["pick_hit_rate"] == (0.0, 2), m["pick_hit_rate"]
    rets = m["monthly_returns"]
    assert len(rets) == 3, rets
    assert abs(rets[0] - (100_562.0 / 100_000.0 - 1)) < 1e-12, rets
    assert abs(rets[1] - (94_527.0 / 100_562.0 - 1)) < 1e-12, rets
    assert rets[2] == 0.0, rets
    assert m["cagr"] is not None and m["cagr"] < 0, m["cagr"]
    assert m["sharpe_monthly"] is not None
    assert m["churn_per_month"] == (0.25, False), m["churn_per_month"]  # 1 churn sell / 4 months
    assert abs(m["total_return"] + 0.05473) < 1e-9, m["total_return"]

    # 5.6 bucket table on the checkpoint's own picks, review gates enforced
    b = r1["buckets"]
    assert_consistent(b)
    assert b["top200"]["picks"] == 1 and abs(b["top200"]["mean_return"] + 10.0 / 105.0) < 1e-12
    assert abs(b["top200"]["churn_per_month"] - 0.25) < 1e-12, b["top200"]
    assert b["201-600"]["picks"] == 1 and abs(b["201-600"]["mean_return"] + 2.0 / 55.0) < 1e-12
    assert b["201-600"]["churn_per_month"] == 0.0, b["201-600"]
    assert b["blended"]["picks"] == 2 and b["blended"]["hit_rate"] == 0.0

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {"checkpoint": "phase5_engine_rules_momentum", "git_hash": git,
           "config": {"backtest": _cfg_backtest()["backtest"],
                      "portfolio": _cfg_portfolio()["portfolio"]},
           "start_capital": START_CAPITAL, **r1}
    path = os.path.join(os.path.dirname(__file__), "checkpoint_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"{'date':<12}{'cash':>12}{'market_value':>14}{'equity':>12}")
    for row in r1["curve"]:
        print(f"{row['date']:<12}{row['cash']:>12.0f}{row['market_value']:>14.0f}"
              f"{row['equity']:>12.0f}")
    print(f"\ntrade log ({len(r1['trades'])} fills, costs 0, impact 0):")
    for t in r1["trades"]:
        print(f"  signal {t['signal_date']}  fill {t['fill_date']}  {t['symbol']:<5}"
              f"{t['qty']:>5} @ {t['price']:<7.2f} {t['reason']}")
    print("\nbucket attribution (task 5.6 table on the checkpoint's own picks):")
    for k, v in b.items():
        print(f"  {k:<10} picks {v['picks']}  hit {v['hit_rate']:.0%}  "
              f"mean {v['mean_return'] * 100:>6.2f}%  churn/mo {v['churn_per_month']:.2f}")
    print(f"\nfinal equity {r1['curve'][-1]['equity']:,.0f} from {START_CAPITAL:,.0f} "
          f"({m['total_return']:+.2%}); wrote {path}")
    print("PASS: checkpoint (engine + portfolio rules + toy momentum end to end; "
          "curve and trade log match paper exactly; deterministic replay)", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
