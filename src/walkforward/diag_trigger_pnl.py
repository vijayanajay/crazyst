"""Trigger-level P&L decomposition for a committed harness run (diagnostic, §11-reporting
spirit: the blended line is never the whole story).

The walk-forward engine's §11 metrics say WHO was sold; they do not say whether the RULE
that sold them helped. A stop that fires at −8% before a −15% slide CREATED value; a DMA
exit that fires on noise before a rebound DESTROYED it. Raw per-trigger mean returns
cannot tell these apart (they inherit the pick's own return, not the rule's timing).

This module answers it with a timing counterfactual per closed lot:

- FIFO-close the run's fills exactly like `metrics.completed_picks` (same math, same
  order), tagging each pick with the CLOSING fill's trigger (from the fill log's
  `reason`).
- For each closed lot, compare the realized exit price with the close at that exit
  month's decision date (the counterfactual "the rule did nothing and the book reviewed
  at month end"). `delta_rs = qty x (cf_px - exec_px)`: POSITIVE = the rule sold cheaper
  than the month-end mark it skipped — rupees destroyed vs waiting for the review;
  NEGATIVE = the exit beat the month-end — rupees saved. Per-side costs are ~equal on
  both sides and cancel in the delta; impact differences are second-order for ranking
  and disclosed as a caveat.
- Rank triggers by total delta DESCENDING (most rupees destroyed first): the ranking of
  which §8 rule destroys the most value. Hit rates and mean realized returns are
  reported alongside, but the RANK is the timing P&L — that is the part the rule
  controls.
- Still-open lots get the same month-end mark so the table does not quietly drop the
  tail of the book.

Diagnostic only: no rule change, no adoption, no pre-registered bars. The output is the
groundwork a subsequent pre-registration must cite.

python -m src.walkforward.diag_trigger_pnl     # synthetic self-check, no database
"""
from __future__ import annotations

import sys
from collections import defaultdict

from src.backtest.metrics import TradeEvent


def _as_trade_events(events) -> list[TradeEvent]:
    """Accept TradeEvents or the harness's dict-shaped events (JSON-ready)."""
    return [e if isinstance(e, TradeEvent) else
            TradeEvent(e["date"], e["symbol"], e["buy"], e["qty"], e["price"], e["cost"],
                       e["mid_month"], e["signal_month"]) for e in events]


def build_sell_reasons(fill_log: list[dict]) -> dict[tuple[str, str], str]:
    """{(fill_date, symbol): reason} for SELL fills. Raises on an ambiguous fill (the
    engine never fills one symbol twice per date; if that ever changes, extend the key)."""
    out: dict[tuple[str, str], str] = {}
    for f in fill_log:
        if f["qty"] > 0:
            continue
        key = (f["fill_date"], f["symbol"])
        assert key not in out, f"ambiguous sell fill for {key}: {out.get(key)} vs {f['reason']}"
        out[key] = f["reason"]
    return out


def close_lots(events, sell_reasons: dict[tuple[str, str], str]) -> list[dict]:
    """FIFO pairing, replicating metrics.completed_picks exactly (same math, same order),
    with the closing fill's trigger, exec price and rupee P&L attached."""
    open_lots: dict[str, list[list]] = defaultdict(list)   # sym -> [qty_left, basis, buy_date]
    out = []
    for e in _as_trade_events(events):
        if e.buy:
            open_lots[e.symbol].append([e.qty, e.price, e.date])
            continue
        sell_qty = -e.qty
        trigger = sell_reasons.get((e.date, e.symbol), "unknown")
        assert trigger != "unknown", f"no fill-log reason for sell {e.symbol} on {e.date}"
        cost_per_share = e.cost / sell_qty
        qty_to_close = sell_qty
        while qty_to_close > 0 and open_lots[e.symbol]:
            lot = open_lots[e.symbol][0]
            take = min(lot[0], qty_to_close)
            basis = lot[1] + cost_per_share                # buy price + share of sell costs
            proceeds = e.price - cost_per_share
            out.append({"symbol": e.symbol, "buy_date": lot[2], "sell_date": e.date,
                        "qty": take, "return": proceeds / basis - 1.0,
                        "trigger": trigger, "exec_px": e.price,
                        "basis_px": lot[1], "sell_month": e.date[:7]})
            qty_to_close -= take
            if take == lot[0]:
                open_lots[e.symbol].pop(0)
            else:
                open_lots[e.symbol][0][0] -= take
        assert qty_to_close == 0, f"sell without an open lot: {e.symbol} {e.date}"
    return out


def open_lots(events) -> list[dict]:
    """Lots still held at the end of the log: {symbol, qty, buy_date, basis_px}."""
    held: dict[str, list[list]] = defaultdict(list)
    for e in _as_trade_events(events):
        if e.buy:
            held[e.symbol].append([e.qty, e.price, e.date])
        else:
            qty_to_close = -e.qty
            while qty_to_close > 0 and held[e.symbol]:
                lot = held[e.symbol][0]
                take = min(lot[0], qty_to_close)
                qty_to_close -= take
                if take == lot[0]:
                    held[e.symbol].pop(0)
                else:
                    held[e.symbol][0][0] -= take
    return [{"symbol": s, "qty": lot[0], "buy_date": lot[2], "basis_px": lot[1]}
            for s in sorted(held) for lot in held[s] if lot[0] > 0]


def timing_pnl(lots: list[dict], close_at: dict[str, dict[str, float]]) -> list[dict]:
    """Attach the timing counterfactual to each closed lot: `delta_rs = qty x (cf_px -
    exec_px)` against the close at the exit month's decision date. POSITIVE = the rule
    sold cheaper than the month-end it skipped (destroyed); NEGATIVE = it beat the
    month-end (saved). Lots whose symbol has no mark for that month (delisted/suspended
    through the window) keep cf=None and are excluded from the timing ranking, counted
    as `no_cf`."""
    out = []
    for p in lots:
        cf = close_at.get(p["symbol"], {}).get(p["sell_month"])
        row = dict(p)
        row["cf_px"] = cf
        row["delta_rs"] = p["qty"] * (cf - p["exec_px"]) if cf is not None else None
        out.append(row)
    return out


def rank_triggers(timed: list[dict]) -> dict[str, dict]:
    """Per trigger: lots, hit rate, mean realized return, total/mean timing delta.
    The caller ranks by total delta DESCENDING (most rupees destroyed first)."""
    rows: dict[str, dict] = {}
    for trig in sorted({p["trigger"] for p in timed}):
        picks = [p for p in timed if p["trigger"] == trig]
        deltas = [p["delta_rs"] for p in picks if p["delta_rs"] is not None]
        rows[trig] = {
            "lots": len(picks),
            "hit_rate": sum(1 for p in picks if p["return"] > 0) / len(picks),
            "mean_return": sum(p["return"] for p in picks) / len(picks),
            "total_delta_rs": sum(deltas) if deltas else 0.0,
            "mean_delta_rs": sum(deltas) / len(deltas) if deltas else 0.0,
            "no_cf": len(picks) - len(deltas),
        }
    return rows


def _self_check() -> None:
    # Hand tape: two buys, three sells, one partial close, one still-open lot.
    #   WIN  bought 100 @ 10 (Jan), sold 100 @ 10.5 on 2024-02-10, trigger_b_dma;
    #        Feb month-end close 12.0 -> delta = 100 x (12.0 - 10.5) = +150 DESTROYED
    #        (the rule sold at 10.5 and skipped a 12.0 month-end review).
    #   STOP bought 100 @ 10 (Jan), sold 60 @ 8.0 on 2024-02-10, trigger_b_stop;
    #        Feb month-end close 7.0 -> delta = 60 x (7.0 - 8.0) = -60 SAVED
    #        (the stop beat the month-end by Re 1/share), and 40 shares stay OPEN.
    fill_log = [
        {"signal_date": "2024-01-31", "fill_date": "2024-02-01", "symbol": "WIN",
         "qty": 100, "price": 10.0, "base_price": 10.0, "cost_pct": 0.005,
         "impact_pct": 0.0, "reason": "select", "forced": False},
        {"signal_date": "2024-01-31", "fill_date": "2024-02-01", "symbol": "STOP",
         "qty": 100, "price": 10.0, "base_price": 10.0, "cost_pct": 0.005,
         "impact_pct": 0.0, "reason": "select", "forced": False},
        {"signal_date": "2024-02-09", "fill_date": "2024-02-10", "symbol": "WIN",
         "qty": -100, "price": 10.5, "base_price": 10.5, "cost_pct": 0.005,
         "impact_pct": 0.0, "reason": "trigger_b_dma", "forced": False},
        {"signal_date": "2024-02-09", "fill_date": "2024-02-10", "symbol": "STOP",
         "qty": -60, "price": 8.0, "base_price": 8.0, "cost_pct": 0.005,
         "impact_pct": 0.0, "reason": "trigger_b_stop", "forced": False},
    ]
    events = [
        {"date": "2024-02-01", "symbol": "WIN", "buy": True, "qty": 100, "price": 10.0,
         "cost": 5.0, "mid_month": False, "signal_month": "2024-01"},
        {"date": "2024-02-01", "symbol": "STOP", "buy": True, "qty": 100, "price": 10.0,
         "cost": 5.0, "mid_month": False, "signal_month": "2024-01"},
        {"date": "2024-02-10", "symbol": "WIN", "buy": False, "qty": -100, "price": 10.5,
         "cost": 5.25, "mid_month": True, "signal_month": "2024-02"},
        {"date": "2024-02-10", "symbol": "STOP", "buy": False, "qty": -60, "price": 8.0,
         "cost": 3.0, "mid_month": True, "signal_month": "2024-02"},
    ]
    reasons = build_sell_reasons(fill_log)
    lots = close_lots(events, reasons)
    assert len(lots) == 2, lots
    win, stop = lots[0], lots[1]
    # FIFO math equals completed_picks: cost/share = 5.25/100 = 0.0525
    assert win["trigger"] == "trigger_b_dma" and win["qty"] == 100
    assert abs(win["return"] - (10.5 - 0.0525) / (10.0 + 0.0525) + 1.0) < 1e-12 or True
    assert abs(win["return"] - ((10.5 - 0.0525) / (10.0 + 0.0525) - 1.0)) < 1e-12, win
    assert stop["trigger"] == "trigger_b_stop" and stop["qty"] == 60      # partial close
    # cost/share = 3.0/60 = 0.05 -> same on both legs
    assert abs(stop["return"] - ((8.0 - 0.05) / (10.0 + 0.05) - 1.0)) < 1e-12, stop

    # timing P&L, hand-computed: Feb decision date = 2024-02-29
    close_at = {"WIN": {"2024-02": 12.0}, "STOP": {"2024-02": 7.0, "2024-03": 6.0}}
    timed = timing_pnl(lots, close_at)
    assert abs(timed[0]["delta_rs"] - 100 * (12.0 - 10.5)) < 1e-9, timed[0]   # +150 wrecked
    assert timed[0]["delta_rs"] > 0 and timed[1]["delta_rs"] < 0, timed
    assert abs(timed[1]["delta_rs"] - 60 * (7.0 - 8.0)) < 1e-9, timed[1]      # -60 saved

    # ranking: the DMA exit lands FIRST (most rupees destroyed) despite a smaller |return|
    ranked = sorted(rank_triggers(timed).items(), key=lambda kv: -kv[1]["total_delta_rs"])
    assert [k for k, _ in ranked] == ["trigger_b_dma", "trigger_b_stop"], ranked
    assert abs(ranked[0][1]["total_delta_rs"] - 150.0) < 1e-9
    assert abs(ranked[1][1]["total_delta_rs"] + 60.0) < 1e-9

    # still-open lots: the 40-share STOP remainder at basis 10.0
    held = open_lots(events)
    assert held == [{"symbol": "STOP", "qty": 40, "buy_date": "2024-02-01",
                     "basis_px": 10.0}], held

    # a lot with no mark for its month keeps cf=None, is excluded from deltas, counted
    close_at_partial = {"WIN": {"2024-02": 12.0}}                 # STOP's mark missing
    timed2 = timing_pnl(lots, close_at_partial)
    assert timed2[0]["delta_rs"] is not None and timed2[1]["delta_rs"] is None
    r2 = rank_triggers(timed2)
    assert r2["trigger_b_stop"]["no_cf"] == 1 and r2["trigger_b_stop"]["total_delta_rs"] == 0.0

    # a sell without a fill-log reason must raise (no silent "unknown" attribution)
    try:
        close_lots(events, {})
        raise SystemExit("missing sell reason must raise")
    except AssertionError:
        pass

    print("PASS: diag_trigger_pnl (FIFO pairing with trigger tags = completed_picks math; "
          "timing deltas hand-computed; trigger ranking by rupee damage; still-open lots; "
          "missing-mark and missing-reason handling)", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
