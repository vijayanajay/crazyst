"""Smoke test — composite_2f's top-5% picks through the REAL engine + portfolio rules on
real full-profile data. The Phase 5 -> Phase 6 bridge: prove the layers compose before
the 6.1 walk-forward harness is built on them.

Exit semantics follow `backtest.exit_gate.mode` (BRD-owner Decision 3). Forced exits appear
as fills with forced=True and uncapped impact, reported separately (`forced_exits` in the
results). The engine pass runs EVERY mode in ENGINE_MODES on the same tape and writes them
side by side under `engine_passes` (escalate = config.yaml's shipped default since Decision
3; stuck = the pre-Decision-3 behavior, kept as the comparison baseline so the ledger's
stuck-vs-escalate table regenerates in one run).

Two passes over the validation slice (P4.1's split: 145 months, boundary 2023-09-24):

1. **Light pass, all 145 months:** score each month with P4.1b's `score_month_2f`
   (importlib, so experiments cannot drift), take top-5% picks, and cross-check the
   aggregate against E012's committed results.json (the 0.375-arm re-baseline after the
   E011 8-slot move: 4,579 pick-months, and the mean monthly IC on `SLICE_IC_PIN` — the
   pin moved +3.11e-4 on 2026-09-27 when the adj_close repair filled the 7 Yahoo-less
   sessions, so E012's frozen arm IC is now the recorded pre-repair value; the E009-era
   anchor of 3,902 picks described the pre-E012 0.75-floor chain and was retired with
   E012, as E006's was retired with E009).
2. **Engine pass, the FIRST 12 slice months consecutively (2011-07 -> 2012-06), once per
   exit-gate mode in ENGINE_MODES:** per month, build a real `Market` from daily bhav bars
   (open/high/low/close/turnover) with a trailing-20-session ADV for the fill gate, build
   `Facts` (closes, 50-close DMA, DMA-below streaks, month highs, within-eligible rank
   percentiles, composite_2f scores), run Portfolio monthly review + Trigger B (monthly
   cadence only — mid-month Trigger A/B checks and delivery-z exits are declared out of
   scope for the smoke), size equal-weight orders on free slots, submit LAST month's orders
   against THIS month's market (T+1 = the next session, so month-end signals fill inside
   the next month), apply fills with a no-negative-cash resize cap, and mark the curve at
   the decision close.

Declared simplifications (the smoke tests plumbing, not results — 6.4 produces results):
no mid-month trigger checks (Trigger A/C exercised by portfolio's unit tests, Trigger B's
mid-month path by the checkpoint), no delivery-z Trigger B clause (needs daily delivery
joins), no surveillance (no historical archive exists — eligibility already excludes
nothing there), engine costs at the E006 default 0.50%/side with capped impact on real ADV,
circuit locks marked from real bars (gap >= 4.9% + turnover < 10% of trailing ADV, or a
fully frozen OHLC bar).

python -m src.backtest.smoke_e2e            # prints the report, writes runs/smoke_e2e/
"""
from __future__ import annotations

import importlib
import json
import math
import os
import statistics
import subprocess
import sys
import time

import duckdb

from src.backtest.attribution import assert_consistent, bucket_attribution
from src.backtest.engine import Engine, Market, Order
from src.backtest.metrics import (TradeEvent, churn_per_month, completed_picks,
                                  month_hit_rate, pick_hit_rate)
from src.backtest.portfolio import Decision, Facts, Portfolio
from src.config import load

P41 = importlib.import_module("experiments.004_composite_v0.run")   # frozen slice split
from src.model import composite as model       # the extracted, pinned composite_2f

SAMPLE_MONTHS = 12          # consecutive slice months through the engine
ENGINE_MONTHS_LIMIT = 12
ENGINE_MODES = (("stuck", 2), ("escalate", 2))   # compared side by side per run

# The light pass's IC anchor, re-baselined to the repaired tape (LEDGER block "adj_close
# pipeline repair", 2026-09-27). The 7-session repair — derived rows for the sessions Yahoo
# never served, 2011-10-26 / 2012-10-26 / 2012-11-13 / 2014-10-23 / 2015-11-11 / 2019-02-13
# / 2019-03-29 — moved the labeled-only slice mean monthly IC by +3.11e-4, all of it in the
# four decision months whose feature windows touch a repaired session. Re-baselined again
# at the 2026-10-01 refresh (E026's G2, disclosed): the refetch added new sessions and the
# corporate-action backfill revised pre-event adjustment ratios, retroactively revising
# labels — mean monthly IC moved +1.63e-5 (0.0720292285 -> 0.0720454959) while the
# selection pins held EXACTLY (top-5% picks 4,579 and arm-convention 5,605 reproduce
# bit-for-bit, so membership/rankings are untouched). This is the pin the smoke and the
# E014/E015 IC guards assert to 1e-9; E012/E018's frozen results.json files are NOT
# rewritten and still hold the values of the tape they ran on (the committed artifacts
# keep describing their own tape). The previous tape's value is kept as a named constant
# (the pre-repair one, below, stays for the same reason).
SLICE_IC_PIN = 0.07204549587457933
SLICE_IC_PIN_20260924 = 0.07202922854484578
SLICE_IC_PIN_PRE_REPAIR = 0.07171797803434904


def _cfg_test() -> dict:
    """Real config.yaml values; the only override is portfolio keys flattened the way
    src.backtest.portfolio reads them (BRD values unchanged)."""
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
                         "trigger_b_deliv_days": 3, "gsm_asm_stage_exit": 2},
            "churn_report_threshold": 1.5,
        },
    }


def _fetch(con):
    rows = con.execute(
        "SELECT mdate, next_month_ret, " + ", ".join(model.PANEL_FEATURES) +
        ", liquidity_rank, symbol, size_bucket FROM feature_matrix "
        "WHERE next_month_ret IS NOT NULL ORDER BY mdate").fetchall()
    cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    return rows, cutoff


def _picks(rs):
    """Select top 5% of the as-of eligible cross-section; preserve NULL forward labels."""
    scores = model.score_month_2f(rs)
    rank_at, sym_at = 2 + len(model.PANEL_FEATURES), 2 + len(model.PANEL_FEATURES) + 1
    scored = [(s, i) for i, s in enumerate(scores) if s is not None]
    if len(scored) < 20:
        return []
    k = max(1, round(len(scored) * 0.05))
    out = []
    for s, i in sorted(scored, key=lambda p: (-p[0], rs[p[1]][sym_at]))[:k]:
        r = rs[i]                                   # tie-break by symbol: deterministic
        out.append({"symbol": r[sym_at], "score": s, "rank": r[rank_at],
                    "bucket": r[-1], "ret": r[1]})
    return out


def _market(con, d_from, d_to, warm_sessions=0):
    """Real bars + trailing-20-session ADV median for every EQ symbol trading the window
    (one decision month: d_from is the PREVIOUS decision date, d_to this month's).

    warm_sessions > 0 fetches that many sessions BEFORE d_from as well (the E008b lesson,
    ledger 2026-09-26): a per-month Market starts cold and its first bar's trailing-20
    ADV median IS that bar — the fill gate and the impact model starve exactly at the
    month boundary where the T+1 fills land. The warm pad exists for the ADV/circuit
    math only; _facts keeps facts scoped to the decision window itself.

    Circuit locks are MARKED from real bars here (fixissues 4.2): the engine honors the
    `circuit_locked` flag but nothing set it from real data before — only the synthetic
    self-check did, so the real-data pass never skipped a locked stock. NSE names freeze
    AT the price band with a gap open (open==high==low==close only catches the fully
    frozen bar); a bar gapped >= 4.9% either way whose turnover collapsed under 10% of
    its trailing-20-session median ADV is treated as locked for BOTH sides (locked up:
    no buy; locked down: no sell — the engine's non-fill is direction-symmetric).
    ponytail: NSE price bands vary per stock (5/10/20%); 4.9% is a heuristic and the ADV
    collapse is the real signal — upgrade to per-stock bands if misclassification shows
    up in the non-fill log."""
    fetch_from = d_from
    if warm_sessions > 0:            # d_from itself IS a session (the previous month-end)
        row = con.execute(
            "SELECT date FROM (SELECT DISTINCT date FROM bhav WHERE date <= ? "
            "ORDER BY date DESC LIMIT ? OFFSET ?)",
            (d_from, 1, warm_sessions)).fetchone()
        fetch_from = str(row[0]) if row else d_from
    rows = con.execute(
        "SELECT symbol, date, open, high, low, close, turnover FROM bhav "
        "WHERE series = 'EQ' AND date > ? AND date <= ? ORDER BY symbol, date",
        (fetch_from, d_to)).fetchall()
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
            pc = bs[i - 1]["close"] if i else None          # previous session's close
            if not pc:
                continue
            frozen = b["open"] == b["high"] == b["low"] == b["close"]
            gapped = b["open"] >= pc * 1.049 or b["open"] <= pc * 0.951
            if frozen or (gapped and b["turnover"] < 0.1 * adv[sym][b["date"]]):
                b["circuit_locked"] = True
    return Market(bars=bars, adv_median=adv)


def _facts(market: Market, m: str, score_map: dict, rank_pct: dict,
           eligible: set[str], d_from: str | None = None) -> Facts:
    """Facts from the month's bars: closes, 50-close DMA proxy, DMA-below streaks,
    month highs. (The DMA window is the month's own closes — at most ~23 sessions;
    declared in the docstring: the mid-month cadence that keeps a true 50-day window
    warm is out of scope for the smoke.) A market may carry a warm pad BEFORE d_from
    (harness, ADV history): those sessions are dropped here so facts never see them."""
    bars = market.bars
    if d_from:
        bars = {s: [b for b in bs if b["date"] > d_from] for s, bs in bars.items()}
    closes, dma, streak, high = {}, {}, {}, {}
    for sym in eligible:
        bs = bars.get(sym) or []
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
    return Facts(date=m, closes=closes, dma50=dma, dma_below_streak=streak,
                 deliv_z_fall_streak={}, month_high=high, rank_pct=rank_pct,
                 scores=score_map, eligible=eligible, surveillance_stage={})


def _mean_monthly_ic(by_month: dict) -> float:
    """Slice mean of monthly composite_2f Spearman ICs (the tie-stable cross-check)."""
    from src.stats import spearman_ic
    ics = []
    for m in sorted(by_month):
        rs = by_month[m]
        scores = model.score_month_2f(rs)
        pairs = [(s, r[1]) for s, r in zip(scores, rs) if s is not None and r[1] is not None]
        ics.append(spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]))
    return sum(ics) / len(ics)


def _boundary_tie_months(by_month: dict) -> int:
    """Months whose top-5% boundary sits on an exact score tie (E006's sort is
    row-order-sensitive there; the smoke records how many)."""
    n = 0
    for rs in by_month.values():
        scores = sorted((s for s in model.score_month_2f(rs) if s is not None), reverse=True)
        k = max(1, round(len(scores) * 0.05))
        if k < len(scores) and scores[k - 1] == scores[k]:
            n += 1
    return n


def _engine_pass(cfg, mode: str, after, sessions, by_month, months, picks_by_month,
                 val, market_warm=0, engine_months_limit=ENGINE_MONTHS_LIMIT,
                 portfolio_overrides: dict | None = None,
                 regime_off: set[str] | None = None,
                 regime_liquidate: bool = False,
                 size_scale: dict[str, dict[str, float]] | None = None,
                 min_hold: int | None = None) -> dict:
    """One engine pass over the first 12 consecutive slice months at exit_gate
    mode=`mode` (after = escalate_after). Verbatim body of the original inline pass; the
    only mode-dependent wiring is `backtest.exit_gate` in the test config.

    E013 test hooks, INERT by default (`regime_off=None` — the harness's shipped call
    passes neither, so the shipped result cannot move): `regime_off` is a set of decision
    months whose regime signal is risk-off; `regime_liquidate=True` also sells every held
    position at those month-ends (trigger `regime`). Either way no new buys are submitted
    in a risk-off month. The signal itself is the caller's (E013: Nifty 200 TRI vs its
    200-session DMA, known at that month's close — fills still follow the normal T+1
    path).

    E015 test hook, INERT by default (`size_scale=None` — the harness's shipped call passes
    neither, so the shipped result cannot move): month -> symbol -> slot-notional multiplier
    (1.0 for any symbol/month absent from the map). A buy's order qty becomes
    `floor(per_slot * scale / px)`; the scale is the caller's (E015: clip(median sigma / own
    sigma), normalized over the month's pool). No scale is applied to sells.

    E016 test hook, INERT by default (`min_hold=None` — the shipped call passes none): a
    decision-month sell with trigger `monthly_review` is DROPPED while the position has been
    held fewer than `min_hold` decision months. Trigger B stops/trails, GSM forced exits and
    universe-exit sells are NOT suppressed — a hard stop fires even in month 1. Held-month
    counting is the caller's (E016: first-filled decision month -> entry age)."""
    tcfg = _cfg_test()
    tcfg["backtest"]["exit_gate"] = {"mode": mode, "escalate_after": after}
    # n_slots follows the SHIPPED config (E011 ADOPTed 8) - a hardcoded value would let the
    # smoke's engine pass drift from the portfolio config.yaml actually ships
    tcfg["portfolio"]["n_slots"] = cfg["portfolio"]["n_slots"]
    if portfolio_overrides:      # E011 slot arms etc; merged AFTER the built-in values
        tcfg["portfolio"].update(portfolio_overrides)
    # mdate IS the month-end decision session; a decision month's market window runs from
    # the previous calendar month-end session to this month's mdate, so last month's
    # signal fills at this window's first session (T+1 across the boundary).
    engine_months = months[:engine_months_limit]
    assert len(engine_months) == min(engine_months_limit, len(months)), engine_months

    def prev_end(m: str) -> str:
        earlier = [s for s in sessions if s < m[:7] + "-01"]
        assert earlier, m
        return earlier[-1]

    market: Market = Market({}, {})
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)   # re-open: the engine pass reads bars
    engine = Engine(market, tcfg)                     # config carrier; market swapped per month
    pf = Portfolio(tcfg)
    cash = tcfg["portfolio"]["start_capital"]
    positions: dict[str, int] = {}
    entry_px: dict[str, float] = {}      # original buy price, kept across blocked sells
    pending: list[Order] = []
    n_filled = 0
    curve, events, decisions_log, resized = [], [], [], []
    sell_nonfills: list[dict] = []
    skipped_no_slot: list[dict] = []
    forced_exits: list[dict] = []
    last_px: dict[str, float] = {}
    held_since: dict[str, str] = {}    # E016 min_hold: symbol -> first decision month held
    month_rows = []

    for m in engine_months:
        d_from = prev_end(m)
        rs = by_month[m]
        scores = model.score_month_2f(rs)
        rank_at, sym_at = 2 + len(model.PANEL_FEATURES), 2 + len(model.PANEL_FEATURES) + 1
        eligible = {rs[i][sym_at] for i, s in enumerate(scores) if s is not None}
        score_map = {rs[i][sym_at]: s for i, s in enumerate(scores) if s is not None}
        rank_pct = {sym: i / max(len(eligible) - 1, 1) for i, sym in enumerate(
            sorted(eligible, key=lambda s: next(
                r[rank_at] for r in rs if r[sym_at] == s)))}

        market = _market(con, d_from, m, market_warm)
        engine.mkt = market

        # 1) last month's signals fill at this month's T+1 open
        n_nonfill = len(engine.non_fills)
        if pending:
            engine.submit(pending)
            pending = []
        # a SELL the ADV gate refused: under mode=stuck the position stays stuck (real
        # illiquidity) - re-own its slot at the ORIGINAL entry price so the portfolio's
        # state matches reality and the next review retries the exit. Under force/escalate
        # the engine's forced fill lands here as a normal fill (forced=True, uncapped
        # impact) and no re-own is needed.
        for n in engine.non_fills[n_nonfill:]:
            if n.qty < 0 and positions.get(n.symbol, 0):
                pf.apply_fill(n.symbol, positions[n.symbol],
                              entry_px.get(n.symbol) or last_px.get(n.symbol)
                              or engine.price_on(n.symbol, m))
                sell_nonfills.append({"month": m, "symbol": n.symbol, "reason": n.reason})
        for f in sorted(engine.fills[n_filled:], key=lambda f: f.qty > 0):
            n_filled += 1
            if f.qty > 0:
                if None not in pf.slots:
                    # the paired sell was blocked by the ADV gate: the replacement buy was
                    # contingent on it and does not fill (contingency semantics, logged)
                    skipped_no_slot.append({"month": m, "symbol": f.symbol, "qty": f.qty})
                    continue
                if f.forced:
                    forced_exits.append({"month": m, "symbol": f.symbol, "qty": f.qty,
                                         "impact_pct": f.impact_pct})
                afford = math.floor(cash / f.price)
                q = min(f.qty, afford)
                if q < f.qty:
                    resized.append({"month": m, "symbol": f.symbol,
                                    "ordered": f.qty, "filled": q})
                if q <= 0:
                    continue
                cash -= q * f.price
                positions[f.symbol] = q
                entry_px[f.symbol] = f.price
                held_since.setdefault(f.symbol, m)
                pf.apply_fill(f.symbol, q, f.price)
            else:
                held = positions.get(f.symbol, 0)
                if held:
                    cash += -f.qty * f.price
                    positions[f.symbol] = 0
                    pf.apply_fill(f.symbol, f.qty, f.price)
                    last_px.pop(f.symbol, None)
                    held_since.pop(f.symbol, None)
                if f.forced:
                    forced_exits.append({"month": m, "symbol": f.symbol, "qty": f.qty,
                                         "impact_pct": f.impact_pct,
                                         "fill_date": f.fill_date})
            events.append(TradeEvent(f.fill_date, f.symbol, f.qty > 0, f.qty, f.price,
                                     Engine.fill_cost(f), f.reason.startswith("trigger_"),
                                     f.signal_date[:7]))   # qty SIGNED: sells negative

        # 2) decisions at the month-end close
        pf.new_month()
        facts = _facts(market, m, score_map, rank_pct, eligible, d_from)
        sells = [d for d in pf.trigger_b(facts) if d.action == "sell"]
        sells += [d for d in pf.monthly_review(facts) if d.action == "sell"]
        gated = regime_off is not None and m in regime_off
        if gated and regime_liquidate:      # E013: the "go to cash" arm's exit leg
            sells += [Decision("sell", sym, "regime", score_sold=score_map.get(sym))
                      for sym in list(positions) if positions.get(sym)]
        seen: set[str] = set()
        for d in sells:
            if d.symbol in seen or positions.get(d.symbol, 0) == 0:
                continue
            if (min_hold is not None and d.trigger == "monthly_review"
                    and held_since.get(d.symbol) is not None):
                first = held_since[d.symbol]
                age = months.index(m) - months.index(first)
                if age < min_hold:      # E016: the churn rule, not the stop, is suppressed
                    decisions_log.append({"month": m, "action": "hold_min", "symbol": d.symbol,
                                          "trigger": d.trigger, "qty": positions[d.symbol],
                                          "score_sold": d.score_sold,
                                          "note": f"min_hold {age}/{min_hold}: {d.note}"})
                    continue
            seen.add(d.symbol)
            qty = positions[d.symbol]
            px = engine.price_on(d.symbol, m)
            if px is None:                 # suspended all window: carry to the next review
                continue
            decisions_log.append({"month": m, "action": "sell", "symbol": d.symbol,
                                  "trigger": d.trigger, "qty": qty,
                                  "score_sold": d.score_sold, "note": d.note})
            pf.apply_fill(d.symbol, -qty, px)          # state moves at decision time
            pending.append(Order(m, d.symbol, -qty, d.trigger))
        buys = [d for d in pf.monthly_review(facts) if d.action == "buy"]
        if not pf.held() and not any(positions.values()):
            # initial selection: top-5% composite (only when truly all-cash — a stuck
            # position from a blocked sell keeps its slot and waits for the next review)
            buys = [Decision("buy", p["symbol"], "select") for p in picks_by_month[m]]
        if gated:                           # E013: risk-off blocks every new entry
            buys = []
        free_slots = pf.slots.count(None)
        if free_slots and buys:
            per_slot = cash / free_slots
            for d in buys[:free_slots]:
                px = engine.price_on(d.symbol, m)
                scale = 1.0 if size_scale is None else size_scale.get(m, {}).get(d.symbol, 1.0)
                qty = math.floor(per_slot * scale / px) if px else 0
                if qty <= 0:
                    continue
                decisions_log.append({"month": m, "action": "buy", "symbol": d.symbol,
                                      "trigger": d.trigger, "qty": qty,
                                      "score_bought": score_map.get(d.symbol), "note": ""})
                pending.append(Order(m, d.symbol, qty, d.trigger))

        # 3) mark at the decision close (last known price if suspended through the window)
        mv = 0.0
        for s, q in positions.items():
            if not q:
                continue
            px = engine.price_on(s, m)
            if px is not None:
                last_px[s] = px
            mv += q * last_px[s]
        curve.append({"date": m, "cash": cash, "market_value": mv,
                      "equity": cash + mv})
        month_rows.append({"month": m, "eligible": len(eligible), "picks": len(picks_by_month[m]),
                           "held": pf.held(), "cash": cash})

    # ---- assertions ------------------------------------------------------------------
    con.close()
    for f in engine.fills:
        assert f.fill_date > f.signal_date, f"same-bar fill: {f}"
    sess_set = set(sessions)
    for f in engine.fills:
        later = [s for s in sessions if s > f.signal_date]
        assert later and f.fill_date == later[0] and f.fill_date in sess_set, \
            f"fill is not the next session after its signal: {f}"
    assert all(f.reason for f in engine.fills) and all(
        n.reason for n in engine.non_fills)
    assert cash >= 0.0, f"cash went negative: {cash}"
    assert curve[0]["equity"] <= curve[0]["cash"] + 1e-6   # nothing held before the first fills
    picks = completed_picks(events)
    hr, n = pick_hit_rate(picks)
    sym_at = 2 + len(model.PANEL_FEATURES) + 1
    attr = bucket_attribution(events, {(str(r[0])[:7], r[sym_at]): r[-1] for r in val},
                              months=len(engine_months))   # every eligible row's as-of bucket
    assert_consistent(attr)
    ch, twitchy = churn_per_month(events, len(engine_months))

    return {
        "months": engine_months, "fills": len(engine.fills),
        "events": [{"date": e.date, "symbol": e.symbol, "buy": e.buy, "qty": e.qty,
                    "price": e.price, "cost": e.cost, "mid_month": e.mid_month,
                    "signal_month": e.signal_month} for e in events],
        "fill_log": [{"signal_date": f.signal_date, "fill_date": f.fill_date,
                      "symbol": f.symbol, "qty": f.qty, "price": f.price,
                      "base_price": f.base_price, "cost_pct": f.cost_pct,
                      "impact_pct": f.impact_pct, "reason": f.reason, "forced": f.forced}
                     for f in engine.fills],   # the walk-forward harness's slippage input
        "non_fills": len(engine.non_fills),
        "non_fill_reasons": sorted({n.reason for n in engine.non_fills}),
        "resized_buys": resized, "sell_nonfills": sell_nonfills,
        "buys_skipped_no_slot": skipped_no_slot,
        "forced_exits": forced_exits,
        "exit_gate": tcfg["backtest"]["exit_gate"],
        "regime_off_months": sorted(regime_off) if regime_off else [],
        "regime_liquidate": regime_liquidate,
        "completed_picks": n, "pick_hit_rate": hr,
        "month_hit_rate": month_hit_rate(picks, len(engine_months)),
        "churn_per_month": ch, "twitchy": twitchy,
        "final_equity": curve[-1]["equity"],
        "total_return": curve[-1]["equity"] / tcfg["portfolio"]["start_capital"] - 1,
        "curve": curve, "month_rows": month_rows,
        "decisions": decisions_log,
        "buckets": attr,
    }


def main() -> int:
    t0 = time.monotonic()
    cfg = load("full")
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff = _fetch(con)
        sessions = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT date FROM bhav ORDER BY date").fetchall()]
    finally:
        con.close()
    assert rows, "no labeled rows — build the full-profile matrix first"
    val, test, boundary = P41.split_slice(rows, cutoff)
    by_month: dict[str, list] = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    months = sorted(by_month)
    assert len(months) == 145, f"expected the 145-month validation slice, got {len(months)}"

    # ---- light pass: every slice month's picks, pinned to the E012 floor chain -------
    # The floor moved twice: E009 (ADOPTED 2026-09-26) set 0.75 at the 4-slot Rs250k
    # notional (pre-floor the gate refused 38.8% of pick-months at S250k and the refused
    # picks were the BEST ones); E012 (ADOPTED 2026-09-26) re-derived the floor at the
    # E011 8-slot Rs125k notional and ADOPTED 0.375 — the gate's own 0.25cr boundary x
    # E009's 1.5x headroom. The E009-era pin (3,902 picks / floor-arm IC 0.0674502) is
    # retired to E012 with the same reasoning the E006 anchors were retired to E009: the
    # chain it described is no longer the shipped one.
    picks_by_month = {m: _picks(by_month[m]) for m in months}
    all_picks = [p for m in months for p in picks_by_month[m]]
    gross = [p["ret"] for p in all_picks]
    mean_gross = sum(gross) / len(gross)
    hit = sum(1 for g in gross if g - 0.004 > 0) / len(gross)   # the E006 convention, kept:
                                                                # net = gross - 2x0.2% (E009
                                                                # re-measures reachability)
    e009_path = os.path.join(os.path.dirname(__file__), "..", "..",
                             "experiments", "009_fill_gate_reach", "results.json")
    with open(e009_path) as f:
        e009 = json.load(f)
    e012_path = os.path.join(os.path.dirname(__file__), "..", "..",
                             "experiments", "012_floor_at_8slots", "results.json")
    with open(e012_path) as f:
        e012 = json.load(f)
    arm = e012["arms"]["0.375"]
    e_picks, e_ic = arm["eligibles"], arm["ic_val_slice"]
    assert e_picks == 161_942, (f"E012's recorded eligible count drifted: {e_picks}")
    assert abs(e_ic - SLICE_IC_PIN_PRE_REPAIR) < 1e-12, \
        (f"E012's frozen 0.375-arm IC moved: {e_ic} != {SLICE_IC_PIN_PRE_REPAIR} — the "
         f"frozen artifacts describe the pre-repair tape and must not be rewritten")
    mean_ic = _mean_monthly_ic(by_month)
    assert abs(mean_ic - SLICE_IC_PIN) < 1e-9, \
        (f"smoke IC {mean_ic} does not reproduce the repaired-tape pin {SLICE_IC_PIN} "
         f"(pre-repair {SLICE_IC_PIN_PRE_REPAIR}; LEDGER 2026-09-27 adj_close repair)")
    assert len(all_picks) == 4579, \
        (f"pick count drifted from the E012 re-baseline: {len(all_picks)} != 4579")
    assert e009["R2"]["eligibles_floor"] == 144_059, \
        "E009's anchor moved (history must not be edited)"
    tie_tol, tie_months = 5e-4, _boundary_tie_months(by_month)
    assert tie_months <= 30, tie_months

    buckets_all: dict[str, dict] = {}
    for b in ("top200", "201-600", "601-1500"):
        bp = [p for p in all_picks if p["bucket"] == b]
        buckets_all[b] = {
            "picks": len(bp),
            "hit_rate": sum(1 for p in bp if p["ret"] - 0.004 > 0) / len(bp) if bp else 0.0,
            "mean_net": (sum(p["ret"] - 0.004 for p in bp) / len(bp)) if bp else 0.0,
        }
    assert sum(b["picks"] for b in buckets_all.values()) == len(all_picks)

    # ---- engine pass: the first 12 consecutive slice months, per exit-gate mode ------
    engine = {mode: _engine_pass(cfg, mode, after, sessions, by_month, months,
                                 picks_by_month, val)
              for mode, after in ENGINE_MODES}
    eps = list(engine.values())
    assert all(e["months"] == eps[0]["months"] for e in eps), \
        "mode runs did not see the same tape"

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "smoke": "composite_2f through engine + portfolio on real full-profile data",
        "git_hash": git, "profile": "full", "cutoff": str(cutoff),
        "slice_months": len(months), "boundary": str(boundary),
        "light_pass": {"pick_months_total": len(all_picks),
                       "mean_gross": mean_gross, "hit_at_0_2pct": hit,
                       "mean_monthly_ic": mean_ic, "slice_ic_pin": SLICE_IC_PIN,
                       "slice_ic_pin_pre_repair": SLICE_IC_PIN_PRE_REPAIR,
                       "e012_arm_ic": e_ic,
                       "boundary_tie_months": tie_months,
                       "e012_cross_check": "pick count exact (4,579) against E012's frozen "
                                          "artifact; IC on the re-baselined repaired-tape "
                                          "pin SLICE_IC_PIN (+3.11e-4 from E012's frozen "
                                          "0.375-arm IC, which the artifact still holds by "
                                          "assert — LEDGER 2026-09-27 adj_close repair); the "
                                          "E009-era anchor (3,902 picks) described the "
                                          "pre-E012 0.75-floor chain and is retired to the "
                                          "E012 block",
                       "by_bucket": buckets_all},
        "engine_passes": engine,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    out_dir = os.path.join(cfg["paths"]["runs"], "smoke_e2e")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "smoke_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    # ---- report ----------------------------------------------------------------------
    print(f"light pass: {len(all_picks):,} pick-months over {len(months)} slice months "
          f"(E012 0.375-arm re-baseline; mean gross {mean_gross:.2%}; mean monthly IC "
          f"{mean_ic:.10f} = E009's floor-arm IC to 1e-9; {tie_months} boundary-tie "
          f"months)")
    for b, v in buckets_all.items():
        print(f"  {b:<10} picks {v['picks']:>5,}  hit {v['hit_rate']:.1%}  "
              f"mean net {v['mean_net'] * 100:>6.2f}%")
    for mode, ep in engine.items():
        print(f"\nengine pass [{mode}] exit_gate={ep['exit_gate']}: {len(ep['months'])} "
              f"consecutive months {ep['months'][0]} -> {ep['months'][-1]}")
        print(f"  fills {ep['fills']} (resized at fill {len(ep['resized_buys'])}), "
              f"non-fills {ep['non_fills']} {ep['non_fill_reasons']}: blocked sells "
              f"re-owned {len(ep['sell_nonfills'])}, forced exits "
              f"{len(ep['forced_exits'])}, buys skipped (no slot after a blocked sell) "
              f"{len(ep['buys_skipped_no_slot'])}, completed picks {ep['completed_picks']} "
              f"(hit {ep['pick_hit_rate']:.0%}), churn {ep['churn_per_month']:.2f}/mo")
        print(f"  final equity {ep['final_equity']:,.0f} ({ep['total_return']:+.2%})")
    ep = engine["stuck"]            # month table + attribution for the pre-Decision-3 baseline
    for r in ep["month_rows"]:
        print(f"  {r['month']}  eligible {r['eligible']:>5,}  picks {r['picks']:>3}  "
              f"held {','.join(r['held']) or '-':<28} cash {r['cash']:>11,.0f}")
    print("\nbucket attribution on the stuck run's own trades:")
    for k, v in ep["buckets"].items():
        print(f"  {k:<10} picks {v['picks']}  hit {v['hit_rate']:.0%}  "
              f"mean {v['mean_return'] * 100:>6.2f}%  churn/mo {v['churn_per_month']:.2f}")
    print(f"\nwrote {path} ({out['runtime_seconds']}s)")
    print("PASS: smoke e2e (composite_2f picks = E012's 0.375-arm re-baseline exactly; "
          "real bars through Market/Facts/Portfolio/Engine with T+1 across month "
          "boundaries; no negative cash; bucket gates hold)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
