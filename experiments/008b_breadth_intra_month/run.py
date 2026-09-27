"""E008b — intra-month breadth protection on the Trigger-B layer (pre-registered in
hypothesis.md; run AFTER that file was written, per BRD 12).

Construction (fixed before the run):
  market_breadth_daily(date, breadth_200, n_top200) — one row per bhav EQ session:
    - as-of membership: the top-200 set of the LATEST universe_rank snapshot with
      mdate <= D (in_universe) — never a static list, never a future month's rank;
    - the DMA is 200 TRADING PRINTS of ADJUSTED closes over a dense session calendar
      (E008a's machinery, different sampling dates); <200 prints = not counted; the
      denominator shrinks on NULL adj prints rather than voting "below";
    - top-200 tier only (E008a: the 201-1000 tier agreed at rho 0.939 — redundant);
    - tier share via avg(...) on the member join only (E008a's dilution lesson).
  The weekly series is the daily table sampled on each week's last session. Gate timing:
  trigger_b decides at D's close and fills T+1, so the gate reads breadth as of D's close
  (weekly: the last completed week-end session <= D).

Sanity layer (mandatory — E008a's first run was wrong until caught):
  1. member-level recompute at 2017-06-30, 2018-10-25, 2020-03-23: pull the as-of member
     set and each member's trailing 200 adj prints, recompute in Python, assert
     agreement to 1e-6 (share and member count);
  2. intra-month trough: the daily minimum inside 2020-03 must sit at or below the
     month-end print (15.5%) — if the trough is not visible intra-month, daily sampling
     is dead and the run says so;
  3. stress visibility: 2018-09/10 and 2020-03 daily breadth well below the 2017 bull.

Interim evaluator (the 6.1 walk-forward harness does not exist yet; hypothesis.md's
decision): the smoke's proven engine pass extended to per-session Trigger-B checks and
daily equity marks, over FIXED pre-named windows on the validation slice:
  W0 calm control 2017-06..08  — the gate must never fire; curves identical to baseline
  W1 midcap stress 2018-09..11 — slow drawdown, the hard case for a trail gate
  W2 crash+rebound 2020-02..04 — Feb = false-fire probe, Mar = the crash, Apr = the
                                 rebound (an exited slot re-enters at the month-end only)
Arms: off (baseline) + threshold {30,40,50} x cadence {daily,weekly} = 7. Tighten 4.0 pp
is fixed by the pre-registration; the threshold is a family, not a tuned point.

python -m experiments.008b_breadth_intra_month.run --profile full
"""
import argparse
import datetime
import importlib
import json
import math
import os
import statistics
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.backtest import smoke_e2e as smoke          # _fetch (matrix read), _market pattern
from src.backtest.engine import Engine, Market, Order
from src.backtest.portfolio import Facts, Portfolio
from src.model import composite as model

P41 = importlib.import_module("experiments.004_composite_v0.run")   # frozen slice split
E007 = importlib.import_module("experiments.007_universe_cutoff.run")  # its chain builder

THRESHOLDS = (30.0, 40.0, 50.0)
TIGHTEN_PP = 4.0                      # pre-registered; NOT swept
WINDOWS = {                           # decision months, all inside the validation slice
    "W0_calm_2017": ("2017-06", "2017-07", "2017-08"),
    "W1_midcap_stress_2018": ("2018-09", "2018-10", "2018-11"),
    "W2_crash_rebound_2020": ("2020-02", "2020-03", "2020-04"),
}
SANITY_DATES = ("2017-06-30", "2018-10-25", "2020-03-23")

_BREADTH_DAILY_SQL = """
CREATE OR REPLACE TABLE market_breadth_daily AS
WITH cal AS (
    SELECT row_number() OVER (ORDER BY date) AS session_no, date
    FROM (SELECT DISTINCT date FROM bhav WHERE series = 'EQ')
),
adj AS (
    SELECT a.symbol, c.session_no, a.adj_close
    FROM adj_close a JOIN cal c ON c.date = a.date
    WHERE a.adj_close IS NOT NULL AND isfinite(a.adj_close) AND a.adj_close > 0
),
adj_windowed AS (
    -- trailing 200 PRINTS per symbol (the sessions it actually traded): the full window
    -- (n200 = 200) is required, so a late-listed or suspended-heavy symbol is simply not
    -- counted until it has 200 prints of its own
    SELECT symbol, session_no, adj_close,
           count(*) OVER w AS n200,
           avg(adj_close) OVER w AS dma200
    FROM adj
    WINDOW w AS (PARTITION BY symbol ORDER BY session_no
                 ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)
),
dma AS (
    SELECT symbol, session_no, dma200 FROM adj_windowed WHERE n200 = 200
),
at_close AS (
    SELECT a.symbol, c.date, a.adj_close, d.dma200,
           a.adj_close > d.dma200 AS above
    FROM adj a
    JOIN cal c ON c.session_no = a.session_no
    JOIN dma d ON d.symbol = a.symbol AND d.session_no = a.session_no
),
session_asof AS (
    -- latest rank snapshot at or before each session: membership changes monthly, so the
    -- as-of join is sessions x snapshot dates (small) — joining at_close x universe_rank
    -- on mdate <= date would materialise ~1e9 rows
    SELECT c.date, max(u.mdate) AS asof
    FROM cal c
    JOIN (SELECT DISTINCT mdate FROM universe_rank) u ON u.mdate <= c.date
    GROUP BY c.date
),
members AS (
    SELECT s.date, u.symbol
    FROM session_asof s
    JOIN universe_rank u ON u.mdate = s.asof AND u.in_universe AND u.rank <= 200
)
SELECT m.date,
       -- the share runs over the MEMBER join only: averaging over at_close directly would
       -- dilute it by every non-member row (E008a's FILTER lesson, join-shaped)
       100.0 * avg(CASE WHEN a.above THEN 1.0 ELSE 0.0 END) AS breadth_200,
       count(*) AS n_top200
FROM members m
JOIN at_close a ON a.symbol = m.symbol AND a.date = m.date
GROUP BY m.date
ORDER BY m.date
"""


def _arm_cfg(threshold: float | None, cadence: str | None) -> dict:
    """The engine-pass test config; the gate keys are the only difference between arms."""
    tighten = TIGHTEN_PP if threshold is not None else None
    return {
        "backtest": {"cost_per_side_pct": 0.50, "purge_months": 1, "random_seed": 42,
                     "fill": {"max_position_adv_frac": 0.05, "impact_coef": 0.10,
                              "impact_cap_pct": 1.0},
                     "exit_gate": {"mode": "escalate", "escalate_after": 2}},
        "portfolio": {
            "start_capital": 1_000_000.0, "n_slots": 4, "cash_earns": 0.0,
            "monthly_review_sell_below_top_pct": 0.25,
            "monthly_review_replace_above_top_pct": 0.15,
            "monthly_review": {"ma_below_consecutive_closes": 5},
            "midmonth": {"trigger_a_score_excess": 0.20, "trigger_a_cap": 2,
                         "trigger_b_stop_pct": 0.08, "trigger_b_trail_pct": 0.12,
                         "trigger_b_ma_close_below": 2, "trigger_b_deliv_z": -2.0,
                         "trigger_b_deliv_days": 3, "gsm_asm_stage_exit": 2,
                         "trigger_b_breadth_threshold": threshold or 40.0,
                         "trigger_b_breadth_trail_tighten": tighten},
            "churn_report_threshold": 1.5,
        },
    }


def _market(con, d_from: str, d_to: str) -> Market:
    """smoke_e2e's real-bars Market: trailing-20-session ADV + circuit-lock marking."""
    rows = con.execute(
        "SELECT symbol, date, open, high, low, close, turnover FROM bhav "
        "WHERE series = 'EQ' AND date > ? AND date <= ? ORDER BY symbol, date",
        (d_from, d_to)).fetchall()
    bars: dict[str, list[dict]] = {}
    for sym, d, o, h, l, c, t in rows:
        bars.setdefault(sym, []).append(
            {"date": str(d), "open": o, "high": h, "low": l, "close": c, "turnover": t})
    adv = {}
    for sym, bs in bars.items():
        turns, per_date = [], {}
        for b in bs:
            turns.append(b["turnover"])
            per_date[b["date"]] = statistics.median(turns[-20:])
        adv[sym] = per_date
    for sym, bs in bars.items():
        for i, b in enumerate(bs):
            pc = bs[i - 1]["close"] if i else None
            if not pc:
                continue
            frozen = b["open"] == b["high"] == b["low"] == b["close"]
            gapped = b["open"] >= pc * 1.049 or b["open"] <= pc * 0.951
            if frozen or (gapped and b["turnover"] < 0.1 * adv[sym][b["date"]]):
                b["circuit_locked"] = True
    return Market(bars=bars, adv_median=adv)


def _bars_to(market: Market, sym: str, dates: list[str]) -> list[dict]:
    """The symbol's bars on the given window sessions (its own trading days only)."""
    by_date = market._by_date.get(sym, {})
    if by_date:
        return [by_date[d] for d in dates if d in by_date]
    want = set(dates)
    return [b for b in market.bars.get(sym, []) if b["date"] in want]


def _facts(d: str, market: Market, window_sessions: list[str], score_map: dict,
           rank_pct: dict, eligible: set[str], breadth_pct: float | None) -> Facts:
    """Trigger-B Facts at session d: closes to d within the window, 50-close DMA of the
    window's sessions, DMA-below streaks, trailing month high (window-to-date). The smoke's
    month-window DMA proxy, extended to the session window; declared simplification — the
    gate under test lives in the trail clause, not the DMA clause."""
    closes, dma, streak, high = {}, {}, {}, {}
    for sym in eligible:
        bs = _bars_to(market, sym, window_sessions)
        cl = [b["close"] for b in bs]
        if not cl:
            continue
        closes[sym] = cl
        dma[sym] = sum(cl[-50:]) / len(cl[-50:])
        s = 0
        for c in reversed(cl):
            if c < dma[sym]:
                s += 1
            else:
                break
        streak[sym] = s
        high[sym] = max(b["high"] for b in bs)
    return Facts(date=d, closes=closes, dma50=dma, dma_below_streak=streak,
                 deliv_z_fall_streak={}, month_high=high, rank_pct=rank_pct,
                 scores=score_map, eligible=eligible, surveillance_stage={},
                 breadth_pct=breadth_pct)


def _week_ends(all_dates: list[str]) -> list[str]:
    """Each week's last session (Monday-week), sorted — the weekly cadence's sample dates."""
    last: dict[tuple, str] = {}
    for d in all_dates:
        key = datetime.date.fromisoformat(d).isocalendar()[:2]
        last[key] = d
    return sorted(last.values())


def run_window(con, window: str, months: tuple[str, ...], sessions: list[str],
               by_month: dict, arm: str, threshold: float | None,
               cadence: str | None, breadth: dict[str, float]) -> dict:
    """The engine pass over one window, one arm: per-session Trigger-B, daily marks.
    Chronological within each month — Trigger B first at every close (including the
    month-end), then the monthly review at the month-end close."""
    cfg = _arm_cfg(threshold, cadence)
    engine = Engine(Market({}, {}), cfg)
    pf = Portfolio(cfg)
    cash = cfg["portfolio"]["start_capital"]
    positions: dict[str, int] = {}
    last_px: dict[str, float] = {}
    pending: list[Order] = []
    curve, decisions_log, gate_fires, forced = [], [], [], []
    trail_exits = 0
    n_filled = 0
    week_end = _week_ends(sessions)

    def month_sessions(m: str) -> list[str]:
        return [s for s in sessions if s[:7] == m[:7]]   # m is the slice's mdate

    def d_end(m: str) -> str:
        in_m = month_sessions(m)
        assert in_m, m
        return in_m[-1]

    def prev_end(m: str) -> str:
        before = [s for s in sessions if s < month_sessions(m)[0]]
        assert before, m
        return before[-1]

    def breadth_at(d: str) -> float | None:
        if cadence is None:
            return None
        if cadence == "daily":
            return breadth.get(d)
        we = max((w for w in week_end if w <= d), default=None)
        return breadth.get(we) if we else None

    for m in months:
        rs = by_month[m]
        scores = model.score_month_2f(rs)
        sym_at = 2 + len(model.PANEL_FEATURES) + 1
        rank_at = sym_at - 1
        eligible = {rs[i][sym_at] for i, s in enumerate(scores) if s is not None}
        score_map = {rs[i][sym_at]: s for i, s in enumerate(scores) if s is not None}
        rank_pct = {sym: i / max(len(eligible) - 1, 1) for i, sym in enumerate(
            sorted(eligible, key=lambda s: next(r[rank_at] for r in rs if r[sym_at] == s)))}

        market = _market(con, prev_end(m), d_end(m))
        engine.mkt = market

        # 1) last month-end's orders fill at this month's T+1 open
        if pending:
            engine.submit(pending)
            pending = []
        for f in sorted(engine.fills[n_filled:], key=lambda f: f.qty > 0):
            n_filled += 1
            if f.forced:
                forced.append({"month": m, "symbol": f.symbol, "qty": f.qty})
            if f.qty > 0:
                if None not in pf.slots:
                    continue                     # blocked-sell contingency (smoke semantics)
                afford = math.floor(cash / f.price)
                q = min(f.qty, afford)
                if q <= 0:
                    continue
                cash -= q * f.price
                positions[f.symbol] = q
                pf.apply_fill(f.symbol, q, f.price)
            else:
                held = positions.get(f.symbol, 0)
                if held:
                    cash += -f.qty * f.price
                    positions[f.symbol] = 0
                    pf.apply_fill(f.symbol, f.qty, f.price)
                last_px.pop(f.symbol, None)

        # 2) the month's sessions, chronological
        ms = month_sessions(m)
        de = d_end(m)
        for d in ms:
            # Trigger B at any close — the layer under test
            if positions:
                bp = breadth_at(d)
                facts = _facts(d, market, [s for s in ms if s <= d], score_map,
                               rank_pct, eligible, bp)
                sold = {o.symbol for o in pending if o.qty < 0}
                for x in pf.trigger_b(facts):
                    if x.symbol in sold or positions.get(x.symbol, 0) == 0:
                        continue
                    px = engine.price_on(x.symbol, d)
                    if px is None:
                        continue
                    if x.trigger == "trigger_b_trail":
                        trail_exits += 1
                        if x.note:
                            gate_fires.append({"date": d, "symbol": x.symbol,
                                               "breadth": bp})
                    decisions_log.append({"date": d, "action": "sell", "symbol": x.symbol,
                                          "trigger": x.trigger, "note": x.note})
                    pf.apply_fill(x.symbol, -positions[x.symbol], px)
                    pending.append(Order(d, x.symbol, -positions[x.symbol], x.trigger))

            # monthly review at the month-end close
            if d == de:
                pf.new_month()
                bp_end = breadth_at(d)
                facts = _facts(d, market, ms, score_map, rank_pct, eligible, bp_end)
                sold = {o.symbol for o in pending if o.qty < 0}
                for x in (y for y in pf.monthly_review(facts) if y.action == "sell"):
                    if x.symbol in sold or positions.get(x.symbol, 0) == 0:
                        continue
                    px = engine.price_on(x.symbol, d)
                    if px is None:             # suspended all window: carry to next review
                        continue
                    decisions_log.append({"date": d, "action": "sell", "symbol": x.symbol,
                                          "trigger": x.trigger, "note": x.note})
                    pf.apply_fill(x.symbol, -positions[x.symbol], px)
                    pending.append(Order(d, x.symbol, -positions[x.symbol], x.trigger))
                sold = {o.symbol for o in pending if o.qty < 0}
                buys = [x.symbol for x in pf.monthly_review(facts) if x.action == "buy"]
                initial = not pf.held() and not any(positions.values())
                if initial:
                    # initial selection: the composite's top-5% (the smoke's convention)
                    k = max(1, round(len(score_map) * 0.05))
                    buys = [s for s, _ in
                            sorted(score_map.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]
                free_slots = pf.slots.count(None)
                if free_slots and buys:
                    per_slot = cash / free_slots
                    for sym in buys[:free_slots]:
                        if sym in sold:
                            continue
                        px = engine.price_on(sym, d)
                        qty = math.floor(per_slot / px) if px else 0
                        if qty <= 0:
                            continue
                        decisions_log.append({"date": d, "action": "buy", "symbol": sym,
                                              "trigger": "select" if initial else "replace",
                                              "note": ""})
                        pending.append(Order(d, sym, qty,
                                             "select" if initial else "replace"))

            # 3) mark at the close
            mv = 0.0
            for s, q in positions.items():
                if not q:
                    continue
                px = engine.price_on(s, d)
                if px is not None:
                    last_px[s] = px
                mv += q * last_px.get(s, 0.0)
            curve.append({"date": d, "cash": cash, "equity": cash + mv})

    assert all(r["equity"] > 0 for r in curve), "equity must stay positive on these tapes"
    return {"window": window, "arm": arm, "threshold": threshold, "cadence": cadence,
            "final_equity": curve[-1]["equity"],
            "total_return": curve[-1]["equity"] / 1_000_000.0 - 1.0,
            "max_drawdown": _max_drawdown(curve),
            "gate_fires": gate_fires, "n_gate_fires": len(gate_fires),
            "trail_exits": trail_exits, "n_forced": len(forced),
            "curve": curve, "decisions": decisions_log}


def _max_drawdown(curve: list[dict]) -> float:
    peak, worst = float("-inf"), 0.0
    for r in curve:
        peak = max(peak, r["equity"])
        worst = max(worst, 1.0 - r["equity"] / peak)
    return worst


def _sanity_member_recompute(con) -> list[dict]:
    """As-of member set + each member's trailing 200 adj prints at each sanity date,
    DMA and above-share recomputed in Python, compared to the SQL table."""
    out = []
    for d in SANITY_DATES:
        sql_share, sql_n = con.execute(
            "SELECT breadth_200, n_top200 FROM market_breadth_daily WHERE date = ?::DATE",
            [d]).fetchone()
        syms = [r[0] for r in con.execute(
            "SELECT symbol FROM universe_rank "
            "WHERE mdate = (SELECT max(mdate) FROM universe_rank WHERE mdate <= ?::DATE) "
            "AND in_universe AND rank <= 200 ORDER BY symbol", [d]).fetchall()]
        py_above, py_n = 0, 0
        for sym in syms:
            prints = con.execute(
                "SELECT a.adj_close FROM adj_close a JOIN "
                "(SELECT DISTINCT date FROM bhav WHERE series = 'EQ') c ON c.date = a.date "
                "WHERE a.symbol = ? AND a.date <= ?::DATE AND a.adj_close IS NOT NULL "
                "AND isfinite(a.adj_close) AND a.adj_close > 0 ORDER BY a.date DESC LIMIT 200",
                [sym, d]).fetchall()
            if len(prints) < 200:
                continue
            py_n += 1
            py_above += 1 if prints[0][0] > sum(p[0] for p in prints) / len(prints) else 0
        py_share = 100.0 * py_above / py_n if py_n else None
        assert py_n and py_share is not None and abs(py_share - sql_share) < 1e-6 \
            and py_n == sql_n, (d, py_share, sql_share, py_n, sql_n)
        out.append({"date": d, "breadth_200": sql_share, "n_top200": sql_n,
                    "python_share": py_share, "python_n": py_n})
    return out


def _resolve_months(prefixes: tuple[str, ...], by_month: dict) -> tuple[str, ...]:
    """'2017-06' -> the slice's full decision date ('2017-06-30'): by_month is keyed by
    mdate, not month prefix."""
    out = []
    for p in prefixes:
        hits = [m for m in by_month if m[:7] == p]
        assert len(hits) == 1, (p, hits)
        out.append(hits[0])
    return tuple(out)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()

    con = duckdb.connect(cfg["paths"].get("duckdb"))
    try:
        # the selfcheck suite resets the derived chain to quick; rebuild at the full profile
        E007._build_chain(con, cfg)

        rows, cutoff = smoke._fetch(con)
        val, test, boundary = P41.split_slice(rows, cutoff)
        by_month: dict[str, list] = {}
        for r in val:
            by_month.setdefault(str(r[0]), []).append(r)
        windows = {w: _resolve_months(ms, by_month) for w, ms in WINDOWS.items()}
        assert max(m for ms in windows.values() for m in ms) < str(boundary), \
            f"a window crosses the {boundary} boundary"

        sessions = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT date FROM bhav WHERE series='EQ' ORDER BY date").fetchall()]

        con.execute(_BREADTH_DAILY_SQL)
        n_days, first_day = con.execute(
            "SELECT count(*), min(date) FROM market_breadth_daily").fetchone()
        sanity = _sanity_member_recompute(con)

        mar = con.execute("SELECT date, breadth_200 FROM market_breadth_daily "
                          "WHERE date BETWEEN '2020-03-01' AND '2020-03-31' ORDER BY date"
                          ).fetchall()
        assert mar, "no daily breadth rows in 2020-03"
        mar_min_d, mar_min = min(((str(d), v) for d, v in mar), key=lambda p: p[1])
        mar_end = mar[-1][1]
        trough_ok = mar_min <= mar_end
        sep18 = con.execute("SELECT avg(breadth_200) FROM market_breadth_daily "
                            "WHERE date BETWEEN '2018-09-01' AND '2018-10-31'").fetchone()[0]
        calm17 = con.execute("SELECT avg(breadth_200) FROM market_breadth_daily "
                             "WHERE date BETWEEN '2017-06-01' AND '2017-08-31'").fetchone()[0]

        breadth = {str(d): v for d, v in con.execute(
            "SELECT date, breadth_200 FROM market_breadth_daily").fetchall()}

        results = {}
        for wname, months in windows.items():
            arms = {"off": run_window(con, wname, months, sessions, by_month,
                                      "off", None, None, breadth)}
            for x in THRESHOLDS:
                for cad in ("daily", "weekly"):
                    aname = f"{cad}_{x:.0f}"
                    arms[aname] = run_window(con, wname, months, sessions, by_month,
                                             aname, x, cad, breadth)
            results[wname] = arms
            base = arms["off"]
            print(f"\n{wname}: baseline ret {base['total_return']:+.2%} "
                  f"maxDD {base['max_drawdown']:.2%} trail exits {base['trail_exits']}")
            for aname, a in arms.items():
                if aname == "off":
                    continue
                print(f"  {aname:<10} ret {a['total_return']:+.2%} "
                      f"(vs base {a['total_return'] - base['total_return']:+.2%})  "
                      f"maxDD {a['max_drawdown']:.2%} "
                      f"(vs base {a['max_drawdown'] - base['max_drawdown']:+.2%})  "
                      f"fires {a['n_gate_fires']} trail exits {a['trail_exits']}")
    finally:
        con.close()

    # ---- pre-registered decision rule ------------------------------------------------
    w0 = results["W0_calm_2017"]
    pass_rows = {}
    for aname in results["W0_calm_2017"]:
        if aname == "off":
            continue
        per = {}
        for wname, arms in results.items():
            base, a = arms["off"], arms[aname]
            per[wname] = {"dd_lower": a["max_drawdown"] < base["max_drawdown"],
                          "ret_ge": a["total_return"] >= base["total_return"],
                          "fires": a["n_gate_fires"]}
        dd_ok = per["W1_midcap_stress_2018"]["dd_lower"] and \
            per["W2_crash_rebound_2020"]["dd_lower"]
        ret_ok = per["W1_midcap_stress_2018"]["ret_ge"] and \
            per["W2_crash_rebound_2020"]["ret_ge"]
        w0_identical = w0[aname]["curve"] == w0["off"]["curve"]
        tested = per["W1_midcap_stress_2018"]["fires"] > 0 or \
            per["W2_crash_rebound_2020"]["fires"] > 0
        pass_rows[aname] = {"dd_lower_both": dd_ok, "ret_ge_both": ret_ok,
                            "w0_curve_identical": w0_identical, "fired": tested,
                            "PASS": aname.startswith("daily") and dd_ok and ret_ok
                                    and w0_identical and tested}

    out = {
        "experiment": "E008b_breadth_intra_month", "profile": args.profile, "git_hash": git,
        "data_cutoff": str(cutoff), "validation_boundary": str(boundary),
        "breadth_days": n_days, "first_breadth_day": str(first_day),
        "tighten_pp": TIGHTEN_PP, "thresholds": list(THRESHOLDS),
        "sanity_member_recompute": sanity,
        "trough_2020_03": {"min_date": mar_min_d, "min_breadth": mar_min,
                           "month_end": mar_end, "trough_at_or_below_month_end": trough_ok},
        "stress_visibility": {"avg_2018_09_10": sep18, "avg_2017_06_08": calm17},
        "windows": {w: {a: {k: v for k, v in r.items() if k != "curve"}
                        for a, r in arms.items()} for w, arms in results.items()},
        "decision": pass_rows,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"\nbreadth_days {n_days} from {first_day}; member-level recompute OK at "
          + ", ".join(f"{s['date']} ({s['n_top200']} members, {s['breadth_200']:.1f}%)"
                      for s in sanity))
    print(f"2020-03 trough {mar_min:.1f}% on {mar_min_d} vs month-end {mar_end:.1f}% "
          f"({'OK' if trough_ok else 'TROUGH NOT VISIBLE INTRA-MONTH'})")
    print(f"stress visibility: 2018-09/10 avg {sep18:.1f}% vs 2017 calm {calm17:.1f}%")
    print("\ndecision (pre-registered rule; only daily arms are eligible for PASS):")
    for aname, v in pass_rows.items():
        print(f"  {aname:<10} dd {v['dd_lower_both']}  ret {v['ret_ge_both']}  "
              f"w0-identical {v['w0_curve_identical']}  fired {v['fired']}  -> "
              f"{'PASS' if v['PASS'] else 'fail'}")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
