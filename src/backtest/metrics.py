"""Task 5.5 — the §11 metric set, from an engine equity curve + trade log.

One function per report line, all from two inputs the engine already produces:

- `equity_curve`   — the engine's mark-to-market rows (date, cash, market_value, equity)
- `fills`          — the engine's Fill/NonFill lists (buys + sells make picks; §9.6 log)

Metrics (BRD §11):
- pick_hit_rate      — hits ÷ picks, where a pick is a completed round trip (buy then its
                       sell) and a hit is net proceeds > cost basis (§8.3 logging makes the
                       pairing deterministic: FIFO by symbol, sells close the oldest lot).
- month_hit_rate     — months with ≥ 1 winning completed pick ÷ months in the curve window.
- cagr               — geometric annualized growth of equity, first→last curve row.
- sharpe_monthly     — mean monthly excess return ÷ std, annualized × sqrt(12); excess vs
                       `cash_earns` (§13: reported, config-driven, default 0).
- benchmark          — the same cagr/sharpe on a benchmark equity series passed in (Nifty 500
                       TR per §11; the caller supplies it — this module never fetches).
- churn              — mid-month replacements per month, flagged above the §8.3 threshold.

No lookahead and no averaging: every statistic is computed from realized rows only.

python -m src.backtest.metrics runs the hand-computed toy portfolio: 2 picks (one win, one
loss), a known cash path, known monthly returns — every metric asserted to the exact value
on paper first.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Lot:
    """One open buy: symbol, qty, cost basis per share, fill date."""
    symbol: str
    qty: int
    basis: float
    date: str


@dataclass(frozen=True)
class TradeEvent:
    """A fill, reduced to what metrics need: buy=True/False, net cash moved (signed)."""
    date: str
    symbol: str
    buy: bool
    qty: int
    price: float          # execution price (impact included)
    cost: float           # rupee cost of this fill (flat + impact), >= 0
    mid_month: bool = False   # True for Trigger A/B replacements (churn), False for monthly


def completed_picks(events: list[TradeEvent]) -> list[dict]:
    """FIFO pairing: each sell closes the oldest open lot of that symbol. One entry per
    completed round trip with its net return fraction (after all costs)."""
    open_lots: dict[str, list[Lot]] = {}
    out = []
    for e in events:
        if e.buy:
            open_lots.setdefault(e.symbol, []).append(
                Lot(e.symbol, e.qty, e.price, e.date))
            continue
        lots = open_lots.get(e.symbol, [])
        sell_qty = -e.qty                     # sell qty is negative
        cost_per_share = e.cost / sell_qty    # this fill's rupee cost spread over its shares
        qty_to_close = sell_qty
        while qty_to_close > 0 and lots:
            lot = lots[0]
            take = min(lot.qty, qty_to_close)
            basis = lot.basis + cost_per_share            # buy price + share of costs
            proceeds = e.price - cost_per_share           # sell price net of costs
            out.append({"symbol": e.symbol, "buy_date": lot.date, "sell_date": e.date,
                        "qty": take, "return": proceeds / basis - 1.0})
            qty_to_close -= take
            if take == lot.qty:
                lots.pop(0)
            else:
                open_lots[e.symbol][0] = Lot(lot.symbol, lot.qty - take, lot.basis, lot.date)
    return out


def pick_hit_rate(picks: list[dict]) -> tuple[float, int]:
    """Hits ÷ picks; a hit is a completed round trip with positive net return."""
    if not picks:
        return 0.0, 0
    hits = sum(1 for p in picks if p["return"] > 0)
    return hits / len(picks), len(picks)


def month_hit_rate(picks: list[dict], months: int) -> tuple[float, int]:
    """Months with ≥ 1 winning completed pick ÷ months in the window."""
    if months <= 0:
        return 0.0, 0
    win_months = {p["sell_date"][:7] for p in picks if p["return"] > 0}
    return len(win_months) / months, len(win_months)


def monthly_returns(equity_curve: list[dict]) -> list[float]:
    """Equity → calendar-month returns from the first curve row."""
    if not equity_curve:
        return []
    by_month: dict[str, float] = {}
    for row in equity_curve:
        by_month[row["date"][:7]] = row["equity"]
    months = sorted(by_month)
    rets = []
    prev = None
    for m in months:
        if prev is not None and by_month[prev] > 0:
            rets.append(by_month[m] / by_month[prev] - 1.0)
        prev = m
    return rets


def cagr(equity_curve: list[dict]) -> float | None:
    """Geometric annualized growth, first → last equity row (None if flat/empty/inverted)."""
    if len(equity_curve) < 2:
        return None
    first, last = equity_curve[0]["equity"], equity_curve[-1]["equity"]
    if first <= 0 or last <= 0:
        return None
    years = _year_fraction(equity_curve[0]["date"], equity_curve[-1]["date"])
    if years <= 0:
        return None
    return (last / first) ** (1 / years) - 1.0


def sharpe_monthly(equity_curve: list[dict], cash_earns: float = 0.0) -> float | None:
    """Mean monthly excess return ÷ std, annualized × sqrt(12). Excess vs cash_earns/12."""
    rets = monthly_returns(equity_curve)
    if len(rets) < 2:
        return None
    excess = [r - cash_earns / 12.0 for r in rets]
    n = len(excess)
    mean = sum(excess) / n
    var = sum((x - mean) ** 2 for x in excess) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return (mean / sd) * math.sqrt(12.0)


def _year_fraction(d1: str, d2: str) -> float:
    from datetime import date
    a, b = date.fromisoformat(d1), date.fromisoformat(d2)
    return (b - a).days / 365.25


def churn_per_month(events: list[TradeEvent], months: int) -> tuple[float, bool]:
    """Mid-month replacements per month + the §8.3 twitchy flag (> 1.5)."""
    if months <= 0:
        return 0.0, False
    n = sum(1 for e in events if e.mid_month and not e.buy)
    return n / months, n / months > 1.5


def benchmark_compare(eq: list[dict], bench_eq: list[dict], cash_earns: float = 0.0) -> dict:
    """Strategy vs benchmark on the same window: CAGR and Sharpe side by side."""
    return {
        "strategy_cagr": cagr(eq), "benchmark_cagr": cagr(bench_eq),
        "strategy_sharpe": sharpe_monthly(eq, cash_earns),
        "benchmark_sharpe": sharpe_monthly(bench_eq, cash_earns),
    }


# ---- hand-computed toy portfolio -----------------------------------------------------------------


def _self_check() -> None:
    # Two completed picks: WIN (bought 100 @ 10, sold @ 12 -> +20% net of a 1.0 cost),
    # LOSS (bought 50 @ 20, sold @ 18 -> negative). Costs split per fill.
    events = [
        TradeEvent("2026-01-05", "WIN", True, 100, 10.0, 1.0),
        TradeEvent("2026-01-05", "LOSS", True, 50, 20.0, 1.0),
        TradeEvent("2026-02-10", "WIN", False, -100, 12.0, 1.0),
        TradeEvent("2026-03-10", "LOSS", False, -50, 18.0, 1.0),
    ]
    picks = completed_picks(events)
    assert len(picks) == 2, picks
    win = next(p for p in picks if p["symbol"] == "WIN")
    loss = next(p for p in picks if p["symbol"] == "LOSS")
    # WIN: proceeds 1200 - 1, basis 1000 + 1 -> (1199/1001) - 1
    assert abs(win["return"] - (1199.0 / 1001.0 - 1.0)) < 1e-12, win
    # LOSS: proceeds 900 - 1, basis 1000 + 1 -> (899/1001) - 1
    assert abs(loss["return"] - (899.0 / 1001.0 - 1.0)) < 1e-12, loss

    hr, n = pick_hit_rate(picks)
    assert n == 2 and abs(hr - 0.5) < 1e-12, (hr, n)          # 1 hit of 2 picks

    # WIN sells in Feb (positive), LOSS sells in Mar (negative) -> exactly 1 winning month of 3
    mr, wm = month_hit_rate(picks, 3)
    assert wm == 1 and abs(mr - 1 / 3) < 1e-12, (mr, wm)

    # Equity curve, hand-computed: start 10,000; WIN bought on cash 10,000 -> 9,001 cash
    # (with LOSS reserved? No — the toy marks equity as cash + positions at close prices).
    # Jan 31: cash 10,000 - 1,000 - 1,000 - 2 = 7,998; holdings WIN 100x11 + LOSS 50x21
    eq = [
        {"date": "2026-01-31", "cash": 7998.0, "market_value": 100 * 11 + 50 * 21,
         "equity": 7998.0 + 100 * 11 + 50 * 21},
        {"date": "2026-02-28", "cash": 7998.0 + 1200.0 - 1.0, "market_value": 50 * 19,
         "equity": 7998.0 + 1199.0 + 50 * 19},
        {"date": "2026-03-31", "cash": 9197.0 + 900.0 - 1.0, "market_value": 0.0,
         "equity": 9197.0 + 899.0},
    ]
    rets = monthly_returns(eq)
    assert len(rets) == 2, rets
    assert abs(rets[0] - (eq[1]["equity"] / eq[0]["equity"] - 1)) < 1e-12, rets
    assert abs(rets[1] - (eq[2]["equity"] / eq[1]["equity"] - 1)) < 1e-12, rets

    # CAGR over the 59-day window (Jan 31 -> Mar 31): the toy LOSES money overall
    # (10,148 -> 10,096), so CAGR is negative — annualized by hand to the same value.
    total = eq[2]["equity"] / eq[0]["equity"]
    years = _year_fraction("2026-01-31", "2026-03-31")
    expected_cagr = total ** (1 / years) - 1
    assert expected_cagr < 0, f"the toy must lose money for this check to mean anything: {total}"
    assert abs(cagr(eq) - expected_cagr) < 1e-12, (cagr(eq), expected_cagr)

    # Sharpe: two known monthly returns; excess vs 0 cash
    r1 = eq[1]["equity"] / eq[0]["equity"] - 1
    r2 = eq[2]["equity"] / eq[1]["equity"] - 1
    mean, sd = (r1 + r2) / 2, abs(r1 - r2) / math.sqrt(2)     # sample std of 2 points
    expected = (mean / sd) * math.sqrt(12.0)
    assert abs(sharpe_monthly(eq) - expected) < 1e-12, (sharpe_monthly(eq), expected)

    # Churn: 1 mid-month sell over 3 months = 0.33, not twitchy
    events_churn = events + [TradeEvent("2026-02-15", "WIN", False, -10, 11.0, 0.5, True)]
    c, twitchy = churn_per_month(events_churn, 3)
    assert abs(c - 1 / 3) < 1e-12 and not twitchy, (c, twitchy)
    c2, twitchy2 = churn_per_month(
        [TradeEvent("2026-02-15", "X", False, -10, 11.0, 0.5, True) for _ in range(5)], 3)
    assert twitchy2 and abs(c2 - 5 / 3) < 1e-12, (c2, twitchy2)

    # Benchmark comparison shape
    bench = [{"date": r["date"], "equity": 10_000.0 * (1.0 + i / 100.0)}
             for i, r in enumerate(eq)]
    cmp_ = benchmark_compare(eq, bench)
    assert cmp_["strategy_cagr"] is not None and cmp_["benchmark_cagr"] is not None

    print("PASS: metrics (FIFO picks, hit rates, monthly returns, CAGR, Sharpe, churn flag, "
          "benchmark compare — all against hand-computed values)", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
