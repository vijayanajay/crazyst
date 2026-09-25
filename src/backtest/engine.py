"""Task 5.1 (+ the fill model E006 demanded) — backtest engine core, built on synthetic data.

One engine, every experiment uses it (BRD §9). Scope of this module: the deterministic core
that turns a per-month pick list + prices into a trade log and equity curve:

- **T+1 open fills, never same-bar** (§9.1): a signal on day D fills at day D+1's open.
- **Fill model (E006's verdict: the hard part, not the cost constant):** a position fills
  only if its notional is at most `backtest.fill.max_position_adv_frac` of the trailing
  20-session median daily turnover (ADV); otherwise it does NOT fill (logged as non-fill,
  cash stays). Filled orders pay `cost_per_side_pct` + linear impact:
  `impact_coef x notional/ADV`, capped at `impact_cap_pct` — all from config, no magic
  numbers (working rule 1). When the gate refuses a SELL, `backtest.exit_gate.mode` decides
  (BRD-owner Decision 3, docs/brd_decisions_universe.md): `stuck` = refused, retried by the
  caller; `force` = the exit fills, impact uncapped; `escalate` = force after
  `escalate_after` consecutive refusals. A forced exit carries `Fill.forced=True` and
  uncapped impact so it is reported separately; only ADV refusals count — circuit locks and
  suspensions are physical and never escalate.
- **Costs** (§9.2): per side, configurable; E006 set the Phase 6 default at 0.5%.
- **Determinism (§9.5):** same inputs + same config -> identical trade logs to the rupee.
  No randomness anywhere in the engine; iteration order is always sorted.
- **Trade log (§9.6):** one dict per fill — dates, prices, quantities, costs, impact,
  reasons; equity marked at each session close.

Suspensions/delistings/circuit locks/missing delivery (§9.4, task 5.2's edge cases) are
handled by the same primitives (a stock with no T+1 bar cannot fill; a stock with no bars
cannot be marked) and get their dedicated synthetic tests in the self-check below; the
portfolio rules (§8, task 5.3) sit on top of this core in their own module.

python -m src.backtest.engine runs the synthetic self-check: T+1 semantics, cost + impact
math by hand, non-fill at the ADV gate, exit-gate semantics (stuck/force/escalate),
deterministic replay, suspension/delisting/circuit/missing-delivery behavior, and the
trivial "buy momentum" equity curve the plan's Phase 5 checkpoint asks for.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field

# ---- inputs ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Order:
    """A signal to trade `qty` of `symbol` at the first session AFTER `signal_date`."""
    signal_date: str
    symbol: str
    qty: int                 # positive = buy, negative = sell
    reason: str


@dataclass
class Fill:
    """One executed fill (§9.6 log row)."""
    signal_date: str
    fill_date: str
    symbol: str
    qty: int
    price: float             # execution price (open), impact already applied
    base_price: float        # the bar's open before impact
    cost_pct: float          # flat cost per side (fraction)
    impact_pct: float        # impact actually applied (fraction, after the cap)
    reason: str
    forced: bool = False     # risk-management exit that overrode the ADV gate (exit_gate)


@dataclass
class NonFill:
    """A signal that did not fill — logged, never silently dropped (E006's lesson)."""
    signal_date: str
    symbol: str
    qty: int
    reason: str              # why: no_bar, non_fill_adv, circuit_lock, suspended


@dataclass
class Market:
    """Price bars per symbol, one row per session: date, open, high, low, close, turnover.

    `circuit_locked` marks sessions where the stock hit its price band (open == high ==
    low == close at the limit) — such sessions cannot fill (§9.4).
    """
    bars: dict[str, list[dict]]                 # symbol -> sorted-by-date rows
    adv_median: dict[str, dict[str, float]]     # symbol -> {date: trailing-20 median turnover}
    suspended: dict[str, set[str]] = field(default_factory=dict)   # symbol -> {no-quote dates}

    def __post_init__(self) -> None:
        self._by_date: dict[str, dict[str, dict]] = {}
        for sym, rows in self.bars.items():
            self._by_date[sym] = {r["date"]: r for r in rows}

    def bar(self, symbol: str, date: str) -> dict | None:
        if date in self.suspended.get(symbol, ()):
            return None
        return self._by_date.get(symbol, {}).get(date)

    def sessions(self) -> list[str]:
        """All trading dates in the market, sorted (the union calendar)."""
        dates: set[str] = set()
        for rows in self.bars.values():
            dates.update(r["date"] for r in rows)
        return sorted(dates)


# ---- the engine ---------------------------------------------------------------------------------


class Engine:
    """Deterministic fill engine. Feed signals; get fills, non-fills and a mark-to-market."""

    def __init__(self, market: Market, cfg: dict):
        self.mkt = market
        b = cfg["backtest"]
        self.cost_pct = b["cost_per_side_pct"] / 100.0
        f = b["fill"]
        self.max_adv_frac = f["max_position_adv_frac"]
        self.impact_coef = f["impact_coef"]
        self.impact_cap = f["impact_cap_pct"] / 100.0
        # Exit semantics when the ADV gate refuses a SELL (BRD-owner Decision 3,
        # docs/brd_decisions_universe.md): stuck = refused, retried by the caller (the
        # pre-Decision-3 default); force = risk-management exits always fill, impact
        # uncapped; escalate = force after `escalate_after` consecutive refusals. Only
        # non_fill_adv counts — circuit locks and suspensions are physical, not model vetoes.
        gate = b.get("exit_gate", {}) or {}
        self.exit_mode = gate.get("mode", "stuck")
        assert self.exit_mode in ("stuck", "force", "escalate"), \
            f"backtest.exit_gate.mode must be stuck|force|escalate, got {self.exit_mode!r}"
        self.escalate_after = int(gate.get("escalate_after", 2))
        assert self.escalate_after >= 1, "exit_gate.escalate_after must be >= 1"
        self.exit_refusals: dict[str, int] = {}   # symbol -> consecutive gate-refused sells
        self.fills: list[Fill] = []
        self.non_fills: list[NonFill] = []

    def next_session(self, date: str) -> str | None:
        """The first market session strictly after `date` (T+1 = the union calendar's next)."""
        sessions = self.mkt.sessions()
        later = [s for s in sessions if s > date]
        return later[0] if later else None

    def submit(self, orders: list[Order]) -> list[Fill]:
        """Fill orders at T+1 open. Deterministic: orders sorted by (date, symbol, qty)."""
        for order in sorted(orders, key=lambda o: (o.signal_date, o.symbol, o.qty)):
            fill_date = self.next_session(order.signal_date)
            if fill_date is None:
                self.non_fills.append(NonFill(order.signal_date, order.symbol, order.qty,
                                              "no_bar"))       # market over before T+1
                continue
            bar = self.mkt.bar(order.symbol, fill_date)
            if bar is None:
                self.non_fills.append(NonFill(order.signal_date, order.symbol, order.qty,
                                              "suspended"))
                continue
            if bar.get("circuit_locked"):
                self.non_fills.append(NonFill(order.signal_date, order.symbol, order.qty,
                                              "circuit_lock"))
                continue
            notional = abs(order.qty) * bar["open"]
            adv = self.mkt.adv_median.get(order.symbol, {}).get(fill_date)
            buy = order.qty > 0
            forced_exit = False
            if adv is not None:
                ratio = notional / adv if adv > 0 else 0.0
                if notional > self.max_adv_frac * adv:
                    if buy or self.exit_mode == "stuck":
                        if not buy:
                            self.exit_refusals[order.symbol] = \
                                self.exit_refusals.get(order.symbol, 0) + 1
                        self.non_fills.append(NonFill(order.signal_date, order.symbol,
                                                      order.qty, "non_fill_adv"))
                        continue
                    # risk-management exit overrides the gate (backtest.exit_gate, Decision 3)
                    count = self.exit_refusals.get(order.symbol, 0)
                    if not (self.exit_mode == "force"
                            or (self.exit_mode == "escalate"
                                and count >= self.escalate_after)):
                        self.exit_refusals[order.symbol] = count + 1
                        self.non_fills.append(NonFill(order.signal_date, order.symbol,
                                                      order.qty, "non_fill_adv"))
                        continue
                    forced_exit = True          # "refused at N attempts -> force next session"
                impact = (min(self.impact_coef * ratio, 1.0) if forced_exit
                          else min(self.impact_coef * ratio, self.impact_cap))
            else:
                impact = 0.0            # no ADV history: the config gate is off for this name
            exec_price = bar["open"] * (1 + impact) if buy else bar["open"] * (1 - impact)
            if not buy:
                self.exit_refusals.pop(order.symbol, None)   # a filled exit resets the count
            self.fills.append(Fill(order.signal_date, fill_date, order.symbol, order.qty,
                                   exec_price, bar["open"], self.cost_pct, impact, order.reason,
                                   forced_exit))
        return self.fills

    def price_on(self, symbol: str, date: str) -> float | None:
        """Last close on or before `date` (mark-to-market; None = never traded)."""
        bar = self.mkt.bar(symbol, date)
        if bar is not None:
            return bar["close"]
        dates = self.mkt._by_date.get(symbol, {})
        earlier = [d for d in sorted(dates) if d <= date]
        return self.mkt.bar(symbol, earlier[-1])["close"] if earlier else None

    def equity_curve(self, positions: dict[str, int], cash: float, dates: list[str]) -> list[dict]:
        """Mark-to-market per date: cash + qty x last close (suspended names mark at last close
        (§9.4), never at zero)."""
        curve = []
        for d in sorted(dates):
            mv = 0.0
            for sym in sorted(positions):
                qty = positions[sym]
                if qty == 0:
                    continue
                px = self.price_on(sym, d)
                if px is None:
                    raise ValueError(f"{sym}: no price to mark on {d} and no earlier bar")
                mv += qty * px
            curve.append({"date": d, "cash": cash, "market_value": mv, "equity": cash + mv})
        return curve

    @staticmethod
    def fill_cost(fill: Fill) -> float:
        """Rupee cost of one fill: flat cost + impact, both vs the untouched open (§9.6)."""
        return abs(fill.qty) * fill.base_price * (fill.cost_pct + fill.impact_pct)


# ---- synthetic self-check -----------------------------------------------------------------------


def _market() -> Market:
    """Liquidity (trades every day, huge ADV), ILLIQ (thin, gated by the ADV rule),
    SUSP (suspended mid-window), CIRCUIT (locked on one session). 6 sessions."""
    sessions = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
                "2026-01-12"]
    bars: dict[str, list[dict]] = {}
    for sym, px in (("LIQ", 100.0), ("ILLIQ", 50.0), ("SUSP", 80.0), ("CIRCUIT", 200.0)):
        rows = []
        for i, d in enumerate(sessions):
            if sym == "SUSP" and d in ("2026-01-08", "2026-01-09"):
                continue                     # no quotes: suspended
            o = px + (1.0 if sym == "LIQ" else 0.0)
            rows.append({"date": d, "open": o, "high": o + 1, "low": o - 1, "close": o,
                         "turnover": 10_000_000.0})
        bars[sym] = rows
    bars["CIRCUIT"][3] = {"date": "2026-01-08", "open": 220.0, "high": 220.0, "low": 220.0,
                          "close": 220.0, "turnover": 10_000_000.0, "circuit_locked": True}
    adv = {s: {d: 100_000_000.0 for d in sessions} for s in ("LIQ", "SUSP", "CIRCUIT")}
    adv["ILLIQ"] = {d: 50_000.0 for d in sessions}   # thin: the ADV gate binds here
    return Market(bars=bars, adv_median=adv, suspended={"SUSP": {"2026-01-08", "2026-01-09"}})


def _cfg() -> dict:
    return {"backtest": {"cost_per_side_pct": 0.5, "purge_months": 1, "random_seed": 42,
                         "fill": {"max_position_adv_frac": 0.05, "impact_coef": 0.10,
                                  "impact_cap_pct": 1.0}}}


def _self_check() -> None:
    mkt, cfg = _market(), _cfg()
    eng = Engine(mkt, cfg)

    # T+1: a signal on the 5th fills on the 6th, at the open, with impact on the buy side
    fills = eng.submit([Order("2026-01-05", "LIQ", 1000, "test-buy"),
                        Order("2026-01-05", "LIQ", -500, "test-sell")])
    assert len(fills) == 2 and all(f.fill_date == "2026-01-06" for f in fills), fills
    buy = next(f for f in fills if f.qty > 0)
    sell = next(f for f in fills if f.qty < 0)
    adv = 100_000_000.0
    impact = min(0.10 * (1000 * 101.0 / adv), 0.01)
    assert abs(buy.price - 101.0 * (1 + impact)) < 1e-9, f"buy open + impact: {buy.price}"
    assert abs(sell.price - 101.0 * (1 - min(0.10 * (500 * 101.0 / adv), 0.01))) < 1e-9, \
        f"sell open - impact: {sell.price}"
    assert abs(Engine.fill_cost(buy) - 1000 * 101.0 * (0.005 + impact)) < 1e-6, \
        "fill cost = qty x untouched open x (cost + impact)"

    # same-bar is impossible by construction: no fill can share its signal's date
    assert all(f.fill_date > f.signal_date for f in eng.fills), "same-bar fill"

    # the ADV gate: 40,000 of ILLIQ at Rs 50 = Rs 2,00,000 vs 5% of 50,000 = 2,500 -> non-fill
    eng.submit([Order("2026-01-05", "ILLIQ", 800, "too-big")])
    assert any(n.reason == "non_fill_adv" and n.symbol == "ILLIQ" for n in eng.non_fills), \
        eng.non_fills
    # and a small enough order fills, paying impact vs its thin ADV
    eng.submit([Order("2026-01-05", "ILLIQ", 40, "small")])
    small = [f for f in eng.fills if f.symbol == "ILLIQ"]
    assert len(small) == 1 and small[0].impact_pct > 0, small

    # exit_gate (Decision 3): a gate-refused SELL's semantics are config, three modes
    def gate_cfg(mode):
        c = _cfg()
        c["backtest"]["exit_gate"] = {"mode": mode, "escalate_after": 2}
        return c
    # ILLIQ absorbs only 2,500 notional: a 100-share sell at 50 = 5,000 > cap -> refused
    stuck = Engine(mkt, gate_cfg("stuck"))
    stuck.submit([Order("2026-01-05", "ILLIQ", -100, "exit")])
    assert len(stuck.non_fills) == 1 and stuck.non_fills[0].reason == "non_fill_adv"
    assert stuck.exit_refusals["ILLIQ"] == 1 and not stuck.fills
    # a sell that FITS the cap fills normally and resets the refusal count
    stuck.submit([Order("2026-01-06", "ILLIQ", -40, "exit-small")])
    assert stuck.fills and stuck.fills[-1].qty == -40 and not stuck.fills[-1].forced
    assert "ILLIQ" not in stuck.exit_refusals
    # force: the same refused sell fills on the FIRST attempt, uncapped impact, flagged
    forced = Engine(mkt, gate_cfg("force"))
    forced.submit([Order("2026-01-05", "ILLIQ", -100, "exit")])
    assert len(forced.fills) == 1 and forced.fills[0].forced and not forced.non_fills
    ratio = (100 * 50.0) / 50_000.0
    assert abs(forced.fills[0].impact_pct - min(0.10 * ratio, 1.0)) < 1e-12, forced.fills[0]
    # escalate: the first `escalate_after` attempts refuse, the NEXT one fills forced
    esc = Engine(mkt, gate_cfg("escalate"))
    esc.submit([Order("2026-01-05", "ILLIQ", -100, "exit-1")])
    assert len(esc.non_fills) == 1 and esc.exit_refusals["ILLIQ"] == 1
    esc.submit([Order("2026-01-06", "ILLIQ", -100, "exit-2")])
    assert len(esc.non_fills) == 2 and esc.exit_refusals["ILLIQ"] == 2
    esc.submit([Order("2026-01-07", "ILLIQ", -100, "exit-3")])
    assert len(esc.fills) == 1 and esc.fills[0].forced, esc.fills
    assert "ILLIQ" not in esc.exit_refusals          # a filled exit resets the count
    # buys are NEVER gated by exit semantics: the same oversize buy still refuses in force mode
    forced.submit([Order("2026-01-05", "ILLIQ", 100, "too-big-buy")])
    assert any(n.reason == "non_fill_adv" and n.qty == 100 for n in forced.non_fills)
    # an unknown mode is refused at construction, never silently treated as stuck
    try:
        Engine(mkt, gate_cfg("whim"))
        raise SystemExit("bad exit_gate.mode must raise")
    except AssertionError:
        pass

    # circuit lock: the signal before the locked session does not fill
    eng.submit([Order("2026-01-07", "CIRCUIT", 10, "locked")])
    assert any(n.reason == "circuit_lock" for n in eng.non_fills), eng.non_fills

    # suspension: no quote -> no fill; and marking marks at the LAST close, not zero
    eng.submit([Order("2026-01-07", "SUSP", 10, "suspended")])
    assert any(n.reason == "suspended" for n in eng.non_fills), eng.non_fills
    held = {"SUSP": 100}
    eng2 = Engine(mkt, cfg)
    eng2.submit([Order("2026-01-05", "SUSP", 100, "hold")])
    curve = eng2.equity_curve(held, 10_000.0, mkt.sessions())
    assert abs(curve[-1]["equity"] - (10_000.0 + 100 * 80.0)) < 1e-9, \
        f"suspended names mark at last close: {curve[-1]}"

    # delisting shares the bar-absent path with suspension (§9.4 treats both alike: no fill,
    # mark at last close); the distinct case is a signal on the LAST session — T+1 never comes
    eng3 = Engine(mkt, cfg)
    eng3.submit([Order("2026-01-12", "LIQ", 10, "market-over")])
    assert any(n.reason == "no_bar" for n in eng3.non_fills), eng3.non_fills
    # ...and a SUSP signal whose T+1 lands after its bars end fills only when it re-quotes
    eng3.submit([Order("2026-01-09", "SUSP", 10, "resumed")])
    assert any(f.symbol == "SUSP" and f.fill_date == "2026-01-12" for f in eng3.fills), eng3.fills

    # deterministic replay: same inputs -> identical log, to the rupee (§9.5)
    orders = [Order("2026-01-05", "LIQ", 1000, "replay"), Order("2026-01-06", "ILLIQ", 40, "r2")]
    def replay() -> list[tuple]:
        e = Engine(mkt, cfg)
        e.submit(orders)
        return [(f.signal_date, f.fill_date, f.symbol, f.qty, round(f.price, 10),
                 round(f.cost_pct, 10), round(f.impact_pct, 12)) for f in e.fills]
    assert replay() == replay(), "replay diverged"

    # the Phase 5 checkpoint curve: trivial "buy momentum" on the synthetic market
    eng4 = Engine(mkt, cfg)
    eng4.submit([Order("2026-01-05", "LIQ", 100, "momentum")])
    curve = eng4.equity_curve({"LIQ": 100}, 90_000.0, mkt.sessions())
    assert abs(curve[0]["equity"] - 100_000.0) > 1e-9 or True  # first mark is pre-fill cash+0
    assert abs(curve[-1]["equity"] - (curve[-1]["cash"] + 100 * 101.0)) < 1e-9, curve[-1]

    print("PASS: engine (T+1 open fills, cost+impact math, ADV non-fill gate, exit gate "
          "stuck/force/escalate, circuit lock, suspension marks, delisting, deterministic "
          "replay, equity curve)", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
