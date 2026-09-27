"""Phase 6.1 — the walk-forward harness (BRD §10). The final judge E008b/E009/E010 defer to,
and the only place realized slippage — the one cost component P4.1b/E006/E010 never measured —
gets a number.

Protocol (BRD §10, decided before the first run and recorded in every results.json):

1. **Window** (§10.1): the test window is recomputed on every run from the DB cutoff via
   P41.split_slice's 36-month boundary — the exact months every validation-slice experiment
   excluded, so harness folds and the frozen slice can never disagree about where the wall is.
2. **Refit semantics** (the §10.2 "fit the model (features selected, thresholds, weights)"
   clause, decided): the shipped model is composite_2f — two cross-sectional percentile
   ranks averaged. It has NO fitted parameters: nothing is selected, no weights, no
   thresholds (the cross-sectional rank uses only the decision month's own features, all
   known at D). The honest reading is that every month's fit is the same frozen decision
   function, and the harness asserts exactly that instead of inventing a refittable
   variant: per fold, the function is the shipped two-feature composite and the refit
   month re-scores BIT-IDENTICALLY around the fold's own scoring (P4.2's freeze protocol,
   harness level — a stateful or refitted function trips it). A symbol's score legitimately
   differs between two months; the FUNCTION must not. (A learned-ranker refit is P4.2's
   machinery, already rejected on the validation slice; it does not get re-invented here
   un-asked.)
3. **Trade M with the frozen decision** (§10.2): the smoke's engine pass — real bars, real
   Market with trailing-20 ADV, Facts, Portfolio §8 rules, T+1 open fills — runs over ALL
   fold months consecutively (the ledger's prediction: "promoted, not rewritten"). One
   pass, in the shipped `exit_gate` mode; stuck/force stay engine-available, not walked.
4. **No peeking** (§10.3, the actionplan's "assert in code"): per fold month — the fold
   sits strictly after the refit month; every scored matrix symbol is inside the
   decision-date `eligible` snapshot (a stale matrix would silently score names that were
   not eligible at D); and decision-date scores equal refit-date scores (assert 2). The
   window itself is the split's boundary, never tuned (§10.3).
5. **Realized slippage** (the unmeasured cost component): per fill, the T+1 open the engine
   filled at vs the decision-close mark the paper experiments measured returns against.
   `slip_vs_mark_pct = side x (base_open / mark - 1) x 100`: positive = worse than paper
   (buys fill above the mark, sells below). Impact is already inside the fill price and
   reported separately. The mean is also taken over the fills belonging to COMPLETED round
   trips (the realized book), with all fills reported alongside.
6. **Warm ADV** (the E008b lesson, ledger 2026-09-26): each month's Market carries a
   20-session pad BEFORE the decision window so the first bar's trailing-20 ADV median is
   real history, not that bar itself — the fill gate and impact model are honest exactly
   at the month boundary where the T+1 fills land. Facts stay scoped to the decision
   window (the pad never leaks into DMA/trail facts).
7. **Benchmark** (§11): the SOURCED Nifty 500 TRI (niftyindices.com, index_tri via
   src/download/nifty_tri.py) on month-end marks, rebased to the strategy window — the
   2026-09-26 constraint's "when one exists" is now met — with the Nifty 200 TRI
   reported alongside as the large-cap reference (benchmark_nifty200). When the table
   is absent or does not cover the window, the harness falls back to the interim
   equal-weight total-return proxy of the eligible universe itself (adj close is
   dividend-adjusted, as-of decision-month membership, no daily rebalance); whichever
   ran is recorded in benchmark_source, and every benchmark number carries that
   construction's identity.
8. **Metrics** (§11): pick/month hit rate, CAGR, benchmark CAGR, Sharpe (monthly), max
   drawdown, churn, average holding period, binomial p vs the 5% baseline with a 95% CI,
   per-fold table, and the per-regime table (benchmark up/down/sideways at a 2% monthly
   band), reported under BOTH sourced indices — the Nifty 500 benchmark and the Nifty 200
   large-cap reference — so benchmark-dependence of the regime story is visible
   (regime_table, regime_table_nifty200). All from `src.backtest.metrics` — nothing duplicated.

python -m src.walkforward.harness                # synthetic self-check, no database needed
python -m src.walkforward.harness --profile full [--verify-determinism]
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import time

import duckdb

from src.backtest import smoke_e2e as smoke          # the promoted engine pass + fetch + picks
from src.backtest.metrics import (TradeEvent, avg_holding_days, benchmark_compare, cagr,
                                  churn_per_month, completed_picks, max_drawdown,
                                  month_hit_rate, monthly_returns, pick_hit_rate,
                                  sharpe_monthly)
from src.config import load
from src.model import composite as model
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")   # frozen slice split

SAT = 2 + len(model.PANEL_FEATURES) + 1      # symbol column in the matrix row tuples
REGIME_BAND = 0.02          # benchmark monthly move outside +-2% = up/down month (§11 table)
WARM_SESSIONS = 20          # the fill gate's own trailing window (E008b lesson)
Z95 = 1.959963984540054     # two-sided 95% normal quantile (no scipy, ledger policy)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _binomial_test(n: int, k: int, p0: float) -> dict:
    """Exact binomial upper-tail and probability-ordered two-sided tests."""
    if n <= 0 or not 0 <= k <= n or not 0 < p0 < 1:
        raise ValueError(f"invalid binomial inputs n={n}, k={k}, p0={p0}")
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p0) + (n - i) * math.log1p(-p0)
            for i in range(n + 1)]
    pmfs = [math.exp(v) for v in logs]
    return {"one_sided_greater": sum(pmfs[k:]),
            "two_sided_probability_ordered": sum(p for p in pmfs
                                                   if p <= pmfs[k] * (1 + 1e-12))}


def _fetch(con):
    """Full eligible decision rows (including unknown forward labels), the eligible
    snapshots, and session calendar. Select first, then label; otherwise excluding rows
    without next-month outcomes shrinks the cross-section before ranking and leaks future
    label availability into who could be picked at the decision date."""
    cols = ", ".join(model.PANEL_FEATURES)
    rows = con.execute(
        "SELECT mdate, next_month_ret, " + cols +
        ", liquidity_rank, symbol, size_bucket FROM feature_matrix ORDER BY mdate").fetchall()
    cutoff = con.execute("SELECT max(mdate) FROM feature_matrix").fetchone()[0]
    eliq: dict[str, set[str]] = {}
    for m, s in con.execute(
            "SELECT mdate, symbol FROM eligible WHERE eligible").fetchall():
        eliq.setdefault(str(m), set()).add(s)
    sessions = [str(r[0]) for r in con.execute(
        "SELECT DISTINCT date FROM bhav ORDER BY date").fetchall()]
    return rows, cutoff, eliq, sessions


def _month_end_closes(con, dates: list[str]) -> dict[str, dict[str, float]]:
    """Raw EQ closes at decision month-ends (the slippage mark, not the benchmark)."""
    out: dict[str, dict[str, float]] = {}
    for sym, d, c in con.execute(
            "SELECT symbol, date, close FROM bhav WHERE series = 'EQ' "
            "AND date IN (SELECT unnest(CAST($ds AS DATE[])))", {"ds": dates}).fetchall():
        out.setdefault(sym, {})[str(d)] = c
    return out


def _month_end_adj_closes(con, dates: list[str]) -> dict[str, dict[str, float]]:
    """Dividend-adjusted month-end marks for the §11 total-return proxy."""
    out: dict[str, dict[str, float]] = {}
    for sym, d, px in con.execute(
            "SELECT symbol, mdate, adj_close FROM adj_me "
            "WHERE mdate IN (SELECT unnest(CAST($ds AS DATE[]))) "
            "AND adj_close IS NOT NULL AND isfinite(adj_close) AND adj_close > 0",
            {"ds": dates}).fetchall():
        out.setdefault(sym, {})[str(d)] = px
    return out


def _regime_of(bench_ret: float, band: float = REGIME_BAND) -> str:
    """§11 per-regime split: benchmark month up / down / sideways at the band."""
    return "up" if bench_ret > band else ("down" if bench_ret < -band else "flat")


def _regime_table(folds: list[str], fold_rows: list[dict], bench_eq: list[dict]) -> dict:
    """§11 per-regime reduction of the fold metrics under ONE benchmark curve.

    The regime at decision month M is that benchmark's return over the month interval
    ending at M. The curve starts at the refit month (protocol point 1's boundary), so its
    later marks and the fold months are the same axis, zipped 1:1 — asserted, because a
    missing or shifted mark would silently relabel months instead of failing loudly.
    """
    rets = monthly_returns(bench_eq)
    months = sorted({r["date"][:7] for r in bench_eq})[1:]
    assert len(rets) == len(months) == len(folds) and months == [m[:7] for m in folds], \
        (len(rets), len(months), len(folds), months[:3], [m[:7] for m in folds][:3])
    table: dict[str, list] = {}
    for fr, bench_ret in zip(fold_rows, rets):
        table.setdefault(_regime_of(bench_ret), []).append(fr)
    return {k: {"months": len(v), "mean_net": _mean([f["mean_net"] for f in v]),
                "mean_ic": _mean([f["ic"] for f in v if f["ic"] is not None])}
            for k, v in sorted(table.items())}


def _benchmark_sourced_tri(cfg: dict, d1: str, d2: str,
                           index_name: str = "NIFTY 500") -> list[dict] | None:
    """A sourced Nifty TRI on month-end marks (protocol point 7, the sourced arm).

    NIFTY 500 is the §11 benchmark; NIFTY 200 the large-cap reference reported
    alongside (BRD §11's table). Returns None (the proxy fallback decides) when
    index_tri has no usable rows for that index — a fresh DB without the table, or a
    fetch that has never run. Rebased to d1 at equity 1.0; month-end marks must cover
    the strategy window (no gaps are tolerated at month-end: the index trades every
    session the strategy does).
    """
    try:
        con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
        try:
            rows = con.execute("SELECT max(date), arg_max(tri, date) FROM index_tri "
                               "WHERE index_name = ? GROUP BY date_trunc('month', date)",
                               [index_name]).fetchall()
        finally:
            con.close()
    except duckdb.Error:            # table absent: the fetch has never run
        return None
    curve = [{"date": str(d), "equity": tri} for d, tri in sorted(rows) if tri]
    if not curve or curve[0]["date"] > d1 or curve[-1]["date"] < d2:
        return None
    by_date = {r["date"]: r["equity"] for r in curve}
    base = by_date[d1]
    return [{"date": d, "equity": by_date[d] / base}
            for d in sorted(by_date) if d1 <= d <= d2]


def _benchmark_liquid(close_idx: dict[str, dict[str, float]], eliq: dict[str, set[str]],
                      d1: str, d2: str) -> list[dict]:
    """Monthly-rebalanced, equal-weight total-return proxy with as-of membership.

    For each interval D->D+1, membership is the eligible snapshot at D; each holding's
    adjusted-close return is measured over that interval, and a missing mark is a cash
    return of 0%. No future-member union is carried back to earlier months. This remains
    an interim broad-market proxy, not a sourced Nifty TRI or BRD's liquidity-weighted ideal.
    """
    dates = sorted({d for marks in close_idx.values() for d in marks if d1 <= d <= d2})
    if not dates or dates[0] != d1 or dates[-1] != d2:
        raise ValueError(f"benchmark marks do not span {d1} -> {d2}: {dates[:1]} {dates[-1:]}")
    curve = [{"date": d1, "equity": 1.0}]
    equity = 1.0
    for prev, current in zip(dates, dates[1:]):
        members = sorted(eliq.get(prev, set()))
        if not members:
            raise ValueError(f"no eligible members at benchmark rebalance date {prev}")
        returns = []
        for symbol in members:
            marks = close_idx.get(symbol, {})
            p0, p1 = marks.get(prev), marks.get(current)
            returns.append(p1 / p0 if p0 and p1 else 1.0)
        equity *= sum(returns) / len(returns)
        curve.append({"date": current, "equity": equity})
    assert all(r["equity"] > 0 for r in curve)
    return curve


def _benchmark_for_window(curve: list[dict], start: str, end: str) -> list[dict]:
    """Rebase a proxy curve to the strategy's exact first/last monthly marks."""
    by_date = {r["date"]: r["equity"] for r in curve}
    if start not in by_date or end not in by_date:
        raise ValueError(f"benchmark missing strategy window marks {start} -> {end}")
    base = by_date[start]
    return [{"date": d, "equity": by_date[d] / base}
            for d in sorted(by_date) if start <= d <= end]


def _slippage(fill_log: list[dict], close_idx: dict[str, dict[str, float]]) -> list[dict]:
    """Realized slippage per fill (protocol point 5): T+1 open (pre-impact base) vs the
    decision-close mark. Positive = the fill was worse than the paper mark."""
    out = []
    for f in fill_log:
        mark = close_idx.get(f["symbol"], {}).get(f["signal_date"])
        if not mark:
            continue
        side = 1.0 if f["qty"] > 0 else -1.0
        out.append({"symbol": f["symbol"], "signal_date": f["signal_date"],
                    "fill_date": f["fill_date"], "buy": f["qty"] > 0,
                    "base_open": f["base_price"], "exec_price": f["price"], "mark": mark,
                    "slip_vs_mark_pct": side * (f["base_price"] / mark - 1.0) * 100.0,
                    "impact_pct": f["impact_pct"] * 100.0})
    return out


def _frozen_decision_ok(refit_rows, fold_rows):
    """The §10.2 freeze check (protocol point 2), harness level. composite_2f is
    parameter-free, so there is nothing to fit per fold - what CAN drift is the decision
    function itself. Assert the function is the shipped two-feature composite and that it
    is stateless: the refit month re-scores BIT-IDENTICALLY before and after the fold
    month's own scoring (P4.2's freeze protocol). A symbol's score legitimately differs
    between two months (its inputs moved); the FUNCTION must not."""
    assert model.FEATURES == ("mom_12m_1m", "delivery_pct"), \
        f"the decision function changed under the harness: {model.FEATURES}"
    before = model.score_month_2f(refit_rows)
    model.score_month_2f(fold_rows)          # the fold's own scoring happens in between
    after = model.score_month_2f(refit_rows)
    assert before == after, "the decision function drifted between refit and fold scoring"


def _no_peek_ok(m, prev_m, all_months, by_month_all, eliq):
    """The §10.3 no-peek gate for one fold month (protocol point 4). Raises on any leak:
    fold before/inside its own history, a stale matrix scoring non-eligible names, or a
    drifted decision function."""
    past = [x for x in all_months if x < m]
    assert prev_m in past and m not in past, f"{m}: fold is not strictly after {prev_m}"
    snap = eliq.get(m) or set()
    assert snap, f"{m}: no decision-date eligible snapshot"
    scored = {r[SAT] for r in by_month_all[m]}
    assert scored <= snap, \
        f"{m}: {len(scored - snap)} matrix symbols are NOT in the decision-date eligible set " \
        f"(stale matrix / peeking): {sorted(scored - snap)[:5]}"
    _frozen_decision_ok(by_month_all[prev_m], by_month_all[m])


def _evaluate_pass(res: dict, folds: list[str], bench_eq: list[dict],
                   close_idx: dict) -> dict:
    """§11 metrics for one engine pass, from realized rows only (protocol point 8). The
    smoke's pass returns events/fill_log as plain dicts (JSON-shaped); rebuild the
    TradeEvents here so the FIFO pairing consumes its own realized rows."""
    events = [e if isinstance(e, TradeEvent) else
              TradeEvent(e["date"], e["symbol"], e["buy"], e["qty"], e["price"], e["cost"],
                         e["mid_month"], e["signal_month"]) for e in res["events"]]
    picks = completed_picks(events)
    hr, n_picks = pick_hit_rate(picks)
    mhr, _ = month_hit_rate(picks, len(folds))
    ch, twitchy = churn_per_month(events, len(folds))
    eq = res["curve"]
    cmp_ = benchmark_compare(eq, bench_eq)
    hold_days, n_open = avg_holding_days(picks)

    slip = _slippage(res["fill_log"], close_idx)
    by_key = {(s["fill_date"], s["symbol"]): s for s in slip}
    realized = []
    for p in picks:
        for k in ((p["buy_date"], p["symbol"]), (p["sell_date"], p["symbol"])):
            row = by_key.get(k)
            if row:
                realized.append(row["slip_vs_mark_pct"])

    return {"months": folds, "exit_gate": res["exit_gate"],
            "fills": res["fills"], "non_fills": res["non_fills"],
            "non_fill_reasons": res["non_fill_reasons"],
            "resized_buys": res["resized_buys"], "sell_nonfills": res["sell_nonfills"],
            "forced_exits": res["forced_exits"],
            "completed_picks": n_picks, "pick_hit_rate": hr, "month_hit_rate": mhr,
            "cagr": cmp_["strategy_cagr"], "sharpe_monthly": cmp_["strategy_sharpe"],
            "max_drawdown": max_drawdown(eq), "benchmark_cagr": cmp_["benchmark_cagr"],
            "benchmark_sharpe": cmp_["benchmark_sharpe"],
            "churn_per_month": ch, "twitchy": twitchy,
            "avg_holding_days": hold_days, "picks_still_open": n_open,
            "final_equity": eq[-1]["equity"],
            "total_return": eq[-1]["equity"] / eq[0]["cash"] - 1.0,
            "slippage": {"fills_measured": len(slip),
                         "mean_buy_slip_vs_mark_pct": _mean(
                             [s["slip_vs_mark_pct"] for s in slip if s["buy"]]),
                         "mean_sell_slip_vs_mark_pct": _mean(
                             [s["slip_vs_mark_pct"] for s in slip if not s["buy"]]),
                         "realized_sides": len(realized),
                         "mean_realized_slip_vs_mark_pct": _mean(realized)},
            "equity_curve": eq, "fill_log": res["fill_log"], "slippage_rows": slip,
            "decisions": res["decisions"]}


def run(profile: str = "full", verify_determinism: bool = False,
        portfolio_overrides: dict | None = None) -> dict:
    t0 = time.monotonic()
    cfg = load(profile)
    n_wf = cfg[profile]["walkforward_months"]
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff, eliq, sessions = _fetch(con)
    finally:
        con.close()
    assert rows, "no labeled rows - build the full-profile matrix first (E007._build_chain)"

    # ---- window (protocol point 1): the split's test slice, recomputed from the cutoff ---
    labeled_rows = [r for r in rows if r[1] is not None]
    val_rows, test_rows, boundary = P41.split_slice(labeled_rows, cutoff)  # labels define the report window
    folds = sorted({str(r[0]) for r in test_rows})
    assert val_rows and folds, "empty split"
    assert len(folds) <= n_wf, f"test window {len(folds)} exceeds walkforward_months {n_wf}"
    if profile == "full":
        assert len(folds) >= 30, \
            f"only {len(folds)} fold months at the full profile - the derived chain is " \
            f"probably at the quick profile; rebuild it (E007._build_chain) first"
    all_months = sorted({str(r[0]) for r in rows})
    by_month_all: dict[str, list] = {}
    for r in rows:
        by_month_all.setdefault(str(r[0]), []).append(r)
    prev_m = all_months[all_months.index(folds[0]) - 1]      # the refit month (purge gap = 1)

    # ---- no-peek asserts (protocol point 4) + picks with frozen decision-date scores -----
    picks_by_month: dict[str, list] = {}
    ic_by_month: dict[str, float | None] = {}
    for m in folds:
        _no_peek_ok(m, prev_m, all_months, by_month_all, eliq)
        # Score and select from all as-of eligible names; only after selection do labels
        # with a known forward return enter the precision/IC calculation.
        decision_rows = [r for r in by_month_all[m] if r[1] is not None]
        pk = smoke._picks(by_month_all[m])
        assert pk and {p["symbol"] for p in pk} <= eliq[m], f"{m}: picks outside the snapshot"
        picks_by_month[m] = pk
        scores = model.score_month_2f(decision_rows)
        pairs = [(s, r[1]) for s, r in zip(scores, decision_rows)
                 if s is not None and r[1] is not None]
        ic_by_month[m] = (spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
                          if len(pairs) >= 3 else None)

    # ---- config parity: the engine pass must measure the SHIPPED config ------------------
    # n_slots follows the shipped config (the pass syncs it; E011), pre-registered
    # portfolio_overrides are the recorded exception
    tc = smoke._cfg_test()
    tc["portfolio"]["n_slots"] = cfg["portfolio"]["n_slots"]
    if portfolio_overrides:
        tc["portfolio"].update(portfolio_overrides)
    assert tc["backtest"]["cost_per_side_pct"] == cfg["backtest"]["cost_per_side_pct"], tc
    assert tc["backtest"]["fill"] == cfg["backtest"]["fill"], tc
    gate = cfg["backtest"]["exit_gate"]

    # ---- benchmark + closes for marks ----------------------------------------------------
    month_ends = [prev_m] + folds
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        close_idx = _month_end_closes(con, month_ends)       # raw close for entry slippage
        adj_close_idx = _month_end_adj_closes(con, month_ends)  # adjusted total-return proxy
        cal = ("(SELECT mdate, lead(mdate) OVER (ORDER BY mdate) AS next_mdate "
               "FROM (SELECT DISTINCT mdate FROM universe_rank))")
        label_rows = con.execute(
            f"SELECT f.mdate, f.symbol, f.is_winner, w.is_top_decile, w.is_top20 "
            f"FROM feature_matrix f JOIN {cal} d ON d.mdate = f.mdate "
            "LEFT JOIN winners w ON w.symbol = f.symbol AND w.mdate = d.next_mdate "
            "WHERE f.mdate IN (SELECT unnest(CAST($ms AS DATE[])))", {"ms": folds}).fetchall()
    finally:
        con.close()
    label_by_key = {(str(m), s): {"top5": w5, "top_decile": dec, "top20": t20}
                    for m, s, w5, dec, t20 in label_rows}
    assert label_by_key, "no forward winner labels in the test window"
    regime_bench_eq = None
    bench200_eq = None
    tri = _benchmark_sourced_tri(cfg, prev_m, month_ends[-1])
    if tri is not None:
        regime_bench_eq = tri
        bench_source = "Nifty 500 TRI (sourced, niftyindices.com; month-end marks)"
        # the §11 large-cap reference, same construction, reported alongside only
        bench200_eq = _benchmark_sourced_tri(cfg, prev_m, month_ends[-1], "NIFTY 200")
    else:
        regime_bench_eq = _benchmark_liquid(adj_close_idx, eliq, prev_m, month_ends[-1])
        bench_source = "EW adj-close proxy (as-of eligible membership; fallback — run " \
                       "python -m src.download.nifty_tri to source the real TRI)"
    assert len(regime_bench_eq) == len(folds) + 1, (len(regime_bench_eq), len(folds))
    bench200 = None
    if bench200_eq is not None:
        # same window as the 500's bench_eq (rebased at folds[0], NOT the refit-anchored
        # regime curve — its first interval would leak the refit month into CAGR/Sharpe)
        bench200_win = _benchmark_for_window(bench200_eq, folds[0], folds[-1])
        assert [r["date"] for r in bench200_win] == folds
        bench200 = {"cagr": cagr(bench200_win), "sharpe": sharpe_monthly(bench200_win)}
    bench_eq = _benchmark_for_window(regime_bench_eq, folds[0], folds[-1])
    assert [r["date"] for r in bench_eq] == folds

    # ---- the walk (protocol point 3): one pass, shipped exit-gate mode -------------------
    val_bucket_rows = [r for m in folds for r in by_month_all[m]]
    kwargs = dict(market_warm=WARM_SESSIONS, engine_months_limit=len(folds),
                  portfolio_overrides=portfolio_overrides)
    res = smoke._engine_pass(cfg, gate.get("mode", "escalate"), gate.get("escalate_after", 2),
                             sessions, by_month_all, folds, picks_by_month,
                             val_bucket_rows, **kwargs)
    ev = _evaluate_pass(res, folds, bench_eq, close_idx)
    if verify_determinism:
        res2 = smoke._engine_pass(cfg, gate.get("mode", "escalate"),
                                  gate.get("escalate_after", 2), sessions, by_month_all,
                                  folds, picks_by_month, val_bucket_rows, **kwargs)
        assert json.dumps(ev, default=str, sort_keys=True) == \
            json.dumps(_evaluate_pass(res2, folds, bench_eq, close_idx),
                       default=str, sort_keys=True), "replay diverged (§9.5)"

    # ---- per-fold table + regimes (§10.4 / §11) ------------------------------------------
    cost_pct = cfg["backtest"]["cost_per_side_pct"] / 100.0
    fold_rows = []
    for m, mr in zip(folds, res["month_rows"]):
        rets = [p["ret"] for p in picks_by_month[m] if p["ret"] is not None]
        fold_rows.append({"month": m, "eligible": mr["eligible"], "picks": len(picks_by_month[m]),
                          "labeled_picks": len(rets), "ic": ic_by_month[m],
                          "mean_pick_ret": sum(rets) / len(rets) if rets else None,
                          "mean_net": sum(rets) / len(rets) - 2 * cost_pct if rets else None,
                          "held": mr["held"], "cash": mr["cash"]})
    # Regime at decision month M is the benchmark's return over the immediately preceding
    # month interval. The table is computed under BOTH sourced indices (BRD §11): the Nifty
    # 500 benchmark and the Nifty 200 large-cap reference, so a benchmark-dependent regime
    # conclusion would be visible instead of assumed away.
    regime_table = _regime_table(folds, fold_rows, regime_bench_eq)
    regime_table_200 = (None if bench200_eq is None
                        else _regime_table(folds, fold_rows, bench200_eq))

    # ---- §11 statistical check: binomial vs the 5% baseline + Wilson 95% CI --------------
    all_selected = [(m, p) for m in folds for p in picks_by_month[m]]
    labeled_picks = [(m, p) for m, p in all_selected
                     if label_by_key.get((m, p["symbol"]), {}).get("top5") is not None]
    all_pk = [p for _, p in all_selected if p["ret"] is not None]
    n_all = len(labeled_picks)
    hits = sum(bool(label_by_key[(m, p["symbol"])]["top5"]) for m, p in labeled_picks)
    p_hit = hits / n_all
    p0 = cfg["stats"]["baseline_hit_rate"]
    p_tests = _binomial_test(n_all, hits, p0)
    p_value = p_tests["one_sided_greater"]
    den = 1 + Z95 ** 2 / n_all
    center = (p_hit + Z95 ** 2 / (2 * n_all)) / den
    half = Z95 * math.sqrt(p_hit * (1 - p_hit) / n_all + Z95 ** 2 / (4 * n_all ** 2)) / den
    positive_return_n = len(all_pk)
    positive_return_hits = sum(1 for p in all_pk if p["ret"] > 0)
    positive_return_rate = positive_return_hits / positive_return_n if positive_return_n else None
    secondary_labels = {}
    for label_name, baseline in (("top_decile", cfg["stats"]["secondary_winner_labels"]["top_decile_pct"]),
                                 ("top20", None)):
        labeled = [(m, p) for m, p in all_selected
                   if label_by_key.get((m, p["symbol"]), {}).get(label_name) is not None]
        n_label = len(labeled)
        n_hits = sum(bool(label_by_key[(m, p["symbol"])][label_name]) for m, p in labeled)
        rate = n_hits / n_label if n_label else None
        item = {"n": n_label, "selected": len(all_selected), "hits": n_hits,
                "hit_rate": rate, "wilson95": None}
        if n_label:
            d = 1 + Z95 ** 2 / n_label
            c = (rate + Z95 ** 2 / (2 * n_label)) / d
            half_label = Z95 * math.sqrt(rate * (1 - rate) / n_label
                                         + Z95 ** 2 / (4 * n_label ** 2)) / d
            item["wilson95"] = [c - half_label, c + half_label]
        if baseline is not None and n_label:
            item["baseline_p"] = baseline
            item["binomial_test"] = _binomial_test(n_label, n_hits, baseline)
        else:
            item["note"] = "fixed top-20 label; null probability varies with the monthly " \
                            "scored universe, so no constant-p binomial test is claimed"
        secondary_labels[label_name] = item

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "harness": "walk-forward BRD 10 (Phase 6.1)", "git_hash": git, "profile": profile,
        "cutoff": str(cutoff), "boundary": str(boundary), "refit_month": prev_m,
        "test_months": folds, "n_folds": len(folds),
        "protocol": {
            "window": "P41.split_slice test slice, recomputed from the DB cutoff every run",
            "refit_semantics": "composite_2f is parameter-free: the monthly fit is the frozen "
                               "decision function; per fold the harness asserts the function "
                               "is the shipped two-feature composite and re-scores the refit "
                               "month bit-identically around the fold's own scoring",
            "no_peeking": "per fold: fold strictly after refit month; scored symbols inside "
                          "the decision-date eligible snapshot; frozen decision function",
            "slippage": "T+1 open (pre-impact) vs decision-close mark, per side, positive = "
                        "worse than paper; means over completed-round-trip fills too",
            "warm_adv": "each month's Market carries a 20-session pad before the decision "
                        "window (E008b lesson); facts stay scoped to the window",
            "benchmark": "Nifty 500 TRI (sourced: niftyindices.com total-return index, "
                         "month-end marks) when index_tri holds data, else the interim "
                         "monthly-rebalanced equal-weight adjusted-close proxy with "
                         "as-of eligible membership; missing marks earn 0%. The active "
                         "source is recorded in benchmark_source, and the Nifty 200 TRI "
                         "(BRD §11's large-cap reference) is reported alongside in "
                         "benchmark_nifty200 when sourced. "
                         "Benchmark CAGR/Sharpe are rebased to the strategy's test-month marks",
            "benchmark_source": bench_source,
            "engine_pass_mode": gate,
            "costs": "engine costs at backtest.cost_per_side_pct + capped impact on real ADV",
        },
        "config": {"walkforward_months": n_wf, "purge_months": cfg["backtest"]["purge_months"],
                   "cost_per_side_pct": cfg["backtest"]["cost_per_side_pct"],
                   "floor_cr": cfg["universe"]["min_median_turnover_cr"],
                   "start_capital": tc["portfolio"]["start_capital"],
                   "n_slots": tc["portfolio"]["n_slots"],
                   "portfolio_overrides": dict(portfolio_overrides or {})},
        "folds": fold_rows, "regime_table": regime_table,
        "regime_table_nifty200": regime_table_200,
        "selection": {"selected": len(all_selected), "labeled": n_all,
                      "unlabeled": len(all_selected) - n_all,
                      "note": "Top 5% selected from all decision-date eligible scores first; "
                              "only picks with a known next-month return enter hit rate and "
                              "mean-return statistics."},
        "paper_picks": {"n": n_all, "selected": len(all_selected), "unlabeled": len(all_selected) - n_all,
                        "hits": hits, "hit_rate": p_hit, "binomial_p": p_value,
                        "binomial_p_two_sided": p_tests["two_sided_probability_ordered"],
                        "ci95_wilson": [center - half, center + half],
                        "baseline_p": p0, "secondary_labels": secondary_labels,
                        "positive_return_n": positive_return_n,
                        "positive_return_hits": positive_return_hits,
                        "positive_return_rate": positive_return_rate,
                        "mean_gross": sum(p["ret"] for p in all_pk) / positive_return_n,
                        "mean_net_after_flat_cost": sum(p["ret"] for p in all_pk) / positive_return_n
                                                    - 2 * cost_pct,
                        "note": "top5 is the BRD winner-label hit rate among selected picks "
                                "with known forward labels; exact binomial test is against p=5%. "
                                "positive_return_rate is reported separately and is not the "
                                "winner-label hit rate."},
        "engine": ev,
        "benchmark_curve": bench_eq,
        "benchmark_regime_curve": regime_bench_eq,
        "benchmark_source": bench_source,
        "benchmark_nifty200": (None if bench200 is None else
                               {"regime_curve": bench200_eq,
                                "cagr": bench200["cagr"],
                                "sharpe": bench200["sharpe"],
                                "note": "BRD §11's large-cap reference, reported "
                                        "alongside the Nifty 500 TRI benchmark; same "
                                        "construction, same window, not compared to the "
                                        "strategy's own curve"}),
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    out_dir = os.path.join(cfg["paths"]["runs"], "walkforward")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "harness_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    # ---- report --------------------------------------------------------------------------
    pp = out["paper_picks"]
    print(f"walk-forward {profile}: {len(folds)} fold months {folds[0]} -> {folds[-1]} "
          f"(boundary {boundary}, refit month {prev_m}, cutoff {cutoff})")
    print(f"  paper picks: {pp['hits']}/{pp['n']} true top-5% winners "
          f"({pp['hit_rate']:.1%} vs p={p0:.0%}, exact p={pp['binomial_p']:.3g}, "
          f"CI95 [{pp['ci95_wilson'][0]:.3f}, {pp['ci95_wilson'][1]:.3f}]); "
          f"{pp['selected']} selected, {pp['unlabeled']} unlabeled; positive-return "
          f"rate {pp['positive_return_rate']:.1%}")
    print(f"  labeled top-5% mean gross {pp['mean_gross']:.2%}, net of flat cost "
          f"{pp['mean_net_after_flat_cost']:.2%}")
    print(f"  engine [{gate.get('mode', 'escalate')}]: fills {ev['fills']} "
          f"(non-fills {ev['non_fills']} {ev['non_fill_reasons']}), completed picks "
          f"{ev['completed_picks']} (hit {ev['pick_hit_rate']:.0%}), month hit "
          f"{ev['month_hit_rate']:.0%}, churn {ev['churn_per_month']:.2f}/mo, "
          f"avg hold {ev['avg_holding_days']:.0f}d, maxDD {ev['max_drawdown']:.1%}")
    def _pct(x):
        return f"{x:.2%}" if x is not None else "n/a"
    print(f"  equity {ev['final_equity']:,.0f} ({ev['total_return']:+.2%}), CAGR "
          f"{_pct(ev['cagr'])} vs benchmark {_pct(ev['benchmark_cagr'])} [{bench_source.split(' (')[0]}], Sharpe "
          f"{ev['sharpe_monthly']:.2f} vs {ev['benchmark_sharpe']:.2f}"
          + (f"; Nifty 200 TRI ref CAGR {_pct(bench200['cagr'])}, "
             f"Sharpe {bench200['sharpe']:.2f}" if bench200 else ""))
    if ev["cagr"] is not None and ev["benchmark_cagr"] is not None:
        gap = ev["benchmark_cagr"] - ev["cagr"]
        print(f"  index-equivalent: the same capital in {bench_source.split(' (')[0]} earns "
              f"{_pct(ev['benchmark_cagr'])} over this window — the engine underperforms "
              f"buy-and-hold by {gap:.2%}/yr (the do-nothing alternative every engine "
              f"result must be read against)")
    s = ev["slippage"]
    print(f"  realized slippage: {s['fills_measured']} fills measured "
          f"(buy {s['mean_buy_slip_vs_mark_pct']:+.3f}%, sell "
          f"{s['mean_sell_slip_vs_mark_pct']:+.3f}% vs decision mark); realized book "
          f"({s['realized_sides']} sides) {s['mean_realized_slip_vs_mark_pct']:+.3f}%/side")
    for k, v in regime_table.items():
        mic = f"{v['mean_ic']:.4f}" if v["mean_ic"] is not None else "n/a"
        print(f"  regime {k:<5} months {v['months']:>2}  mean net {v['mean_net']:.2%}  "
              f"mean IC {mic}")
    if regime_table_200 is not None:
        b2 = "  ".join(f"{k} {v['months']}mo net {v['mean_net']:+.2%}"
                        for k, v in regime_table_200.items())
        print(f"  regime(Nifty 200 TRI) {b2} -> "
              + ("same table as the 500" if regime_table_200 == regime_table
                 else "DIFFERS from the 500"))
    print(f"wrote {path} ({out['runtime_seconds']}s)")
    print("PASS: walk-forward harness (window recomputed, no-peek asserts held, frozen "
          "decision re-scores bit-identical, selection from full eligible cross-section, "
          "engine + portfolio walked every fold month, slippage measured, "
          f"benchmark {bench_source.split(' (')[0]})", flush=True)
    return out


# ---- synthetic self-check (no database) ------------------------------------------------------

def _synthetic_check() -> None:
    # slippage: buy filled 2% ABOVE the decision mark (unfavorable), sell at the mark
    close_idx = {"AAA": {"2026-01-30": 100.0, "2026-02-27": 110.0}}
    fill_log = [
        {"symbol": "AAA", "signal_date": "2026-01-30", "fill_date": "2026-02-02",
         "qty": 400, "base_price": 102.0, "price": 102.5, "impact_pct": 0.005},
        {"symbol": "AAA", "signal_date": "2026-02-27", "fill_date": "2026-03-02",
         "qty": -400, "base_price": 110.0, "price": 109.5, "impact_pct": 0.005},
    ]
    slip = _slippage(fill_log, close_idx)
    assert abs(slip[0]["slip_vs_mark_pct"] - 2.0) < 1e-12, slip    # buy 102 vs mark 100
    assert abs(slip[1]["slip_vs_mark_pct"] - 0.0) < 1e-12, slip    # sell 110 vs mark 110
    assert abs(slip[0]["impact_pct"] - 0.5) < 1e-12, slip

    # regime classification at the 2% band
    assert [_regime_of(r) for r in (0.03, -0.03, 0.005)] == ["up", "down", "flat"]

    # per-regime reduction (§11): identical fold metrics land in different buckets under a
    # curve whose monthly move crosses the band, and a curve not aligned with the folds
    # raises instead of relabeling months
    folds3 = ["2026-02-27", "2026-03-31", "2026-04-30"]
    fr3 = [{"mean_net": 0.02, "ic": 0.10}, {"mean_net": -0.01, "ic": 0.20},
           {"mean_net": 0.05, "ic": 0.30}]
    cur_a = [{"date": "2026-01-30", "equity": 1.0}, {"date": "2026-02-27", "equity": 1.03},
             {"date": "2026-03-31", "equity": 1.0403},
             {"date": "2026-04-30", "equity": 1.009091}]     # +3% / +1% / -3%
    cur_b = [{"date": "2026-01-30", "equity": 1.0}, {"date": "2026-02-27", "equity": 1.01},
             {"date": "2026-03-31", "equity": 1.0201},
             {"date": "2026-04-30", "equity": 0.989497}]     # +1% / +1% / -3%
    ta = _regime_table(folds3, fr3, cur_a)
    tb = _regime_table(folds3, fr3, cur_b)
    assert [ta[k]["months"] for k in ("down", "flat", "up")] == [1, 1, 1], ta
    assert "up" not in tb and tb["flat"]["months"] == 2 and tb["down"]["months"] == 1, tb
    assert abs(ta["up"]["mean_net"] - 0.02) < 1e-12, ta
    assert abs(tb["flat"]["mean_net"] - 0.005) < 1e-12, tb
    assert abs(tb["flat"]["mean_ic"] - 0.15) < 1e-12 and tb["down"]["mean_ic"] == 0.30, tb
    try:
        _regime_table(folds3, fr3, [c for c in cur_a if c["date"] != "2026-03-31"])
        raise SystemExit("a curve missing a fold month must raise")
    except AssertionError:
        pass

    # benchmark: 2 symbols; Y is not yet eligible in Jan (sits at 1.0), X falls in Mar
    close_idx2 = {"X": {"2026-01-30": 100.0, "2026-02-27": 110.0, "2026-03-31": 99.0},
                  "Y": {"2026-01-30": 50.0, "2026-02-27": 50.0, "2026-03-31": 55.0}}
    eliq2 = {"2026-01-30": {"X"}, "2026-02-27": {"X", "Y"},
             "2026-03-31": {"X", "Y"}}
    bench = _benchmark_liquid(close_idx2, eliq2, "2026-01-30", "2026-03-31")
    # Jan->Feb holds Jan's X only: +10%; Feb->Mar holds X+Y: (−10% + 10%)/2 = 0%.
    assert [round(r["equity"], 6) for r in bench] == [1.0, 1.1, 1.1], bench
    matched = _benchmark_for_window(bench, "2026-02-27", "2026-03-31")
    assert [r["date"] for r in matched] == ["2026-02-27", "2026-03-31"]
    assert [round(r["equity"], 6) for r in matched] == [1.0, 1.0]

    # sourced-TRI arm (protocol point 7): a synthetic index_tri table is preferred over
    # the proxy — rebased at d1, month-end marks only, coverage gaps fall back, and an
    # absent table falls back to None.
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp()
    cfg2 = {"paths": {"duckdb": os.path.join(tmp, "t.duckdb")}}
    from src.download.nifty_tri import SCHEMA as TRI_SCHEMA
    con = duckdb.connect(cfg2["paths"]["duckdb"])
    try:
        con.execute(TRI_SCHEMA)
        # gappy + non-rebased source values; month-ends picked by max(date) per month
        con.executemany("INSERT INTO index_tri VALUES (?, ?, ?, ?)", [
            ("NIFTY 500", "2026-01-30", 5000.0, None), ("NIFTY 500", "2026-01-31", 5050.0, None),
            ("NIFTY 500", "2026-02-27", 5151.0, None), ("NIFTY 500", "2026-03-31", 5100.0, None),
            ("NIFTY 500", "2026-04-02", 5200.0, None),   # mid-month row: must not become a month-end mark
            ("NIFTY 500", "2026-04-30", 5252.0, None),
        ])
    finally:
        con.close()
    tri = _benchmark_sourced_tri(cfg2, "2026-01-31", "2026-04-30", "NIFTY 500")
    assert tri and [round(r["equity"], 6) for r in tri] == \
        [1.0, round(5151.0 / 5050.0, 6), round(5100.0 / 5050.0, 6), round(5252.0 / 5050.0, 6)], tri
    assert _benchmark_sourced_tri(cfg2, "2025-12-31", "2026-04-30", "NIFTY 500") is None  # left gap
    assert _benchmark_sourced_tri(cfg2, "2026-01-31", "2026-05-31", "NIFTY 500") is None  # right gap
    assert _benchmark_sourced_tri(cfg2, "2026-01-31", "2026-04-30", "NIFTY 200") is None  # other index
    os.remove(cfg2["paths"]["duckdb"])
    assert _benchmark_sourced_tri(cfg2, "2026-01-31", "2026-04-30") is None   # absent table
    shutil.rmtree(tmp)

    # no-peek gate: clean case passes; a stale-matrix symbol, a score drift and an empty
    # snapshot each raise
    fi = {name: 2 + i for i, name in enumerate(model.PANEL_FEATURES)}

    def row(m, sym, mom=None, deliv=None, ret=0.01):
        r = [m, ret] + [None] * len(model.PANEL_FEATURES) + [1, sym, "top200"]
        r[fi["mom_12m_1m"]] = mom
        r[fi["delivery_pct"]] = deliv
        return tuple(r)

    months = ["2026-01", "2026-02", "2026-03"]
    by_month_all = {
        "2026-02": [row("2026-02", "AAA", 0.10, 50.0), row("2026-02", "BBB", 0.05, 40.0)],
        "2026-03": [row("2026-03", "AAA", 0.10, 50.0), row("2026-03", "BBB", 0.05, 40.0)],
    }
    eliq3 = {"2026-03": {"AAA", "BBB"}}
    _no_peek_ok("2026-03", "2026-02", months, by_month_all, eliq3)
    stale = dict(by_month_all)
    stale["2026-03"] = stale["2026-03"] + [row("2026-03", "ZZZ", 0.50, 50.0)]
    try:
        _no_peek_ok("2026-03", "2026-02", months, stale, eliq3)
        raise SystemExit("stale matrix must raise")
    except AssertionError:
        pass
    # a STATEFUL decision function must trip the freeze check: the refit month re-scores
    # differently after the fold's own scoring (a fitted model that updated itself would
    # look exactly like this)
    orig = model.score_month_2f
    calls = {"n": 0}

    def stateful(rs):
        calls["n"] += 1
        out = orig(rs)
        return [None if s is None else s + (1e-9 if calls["n"] >= 2 else 0.0) for s in out]

    model.score_month_2f = stateful
    try:
        _no_peek_ok("2026-03", "2026-02", months, by_month_all, eliq3)
        raise SystemExit("a stateful decision function must raise")
    except AssertionError:
        pass
    finally:
        model.score_month_2f = orig
    try:
        _no_peek_ok("2026-03", "2026-02", months, by_month_all, {})
        raise SystemExit("empty snapshot must raise")
    except AssertionError:
        pass

    # _evaluate_pass: one hand-computed round trip through every section-11 metric
    events = [TradeEvent("2026-02-02", "AAA", True, 400, 102.5, 0.0),
              TradeEvent("2026-03-02", "AAA", False, -400, 109.5, 0.0)]
    curve = [{"date": "2026-01-30", "cash": 50_000.0, "market_value": 0.0, "equity": 50_000.0},
             {"date": "2026-02-27", "cash": 9_000.0, "market_value": 400 * 110.0,
              "equity": 53_000.0},
             {"date": "2026-03-31", "cash": 52_800.0, "market_value": 0.0, "equity": 52_800.0}]
    res = {"events": events, "curve": curve, "fills": 2, "non_fills": 0,
           "non_fill_reasons": [], "resized_buys": [], "sell_nonfills": [],
           "forced_exits": [], "exit_gate": {"mode": "escalate", "escalate_after": 2},
           "fill_log": fill_log, "month_rows": [], "decisions": []}
    ev = _evaluate_pass(res, ["2026-02", "2026-03"],
                        [{"date": "2026-01-30", "equity": 1.0},
                         {"date": "2026-02-27", "equity": 1.02},
                         {"date": "2026-03-31", "equity": 1.01}], close_idx)
    assert ev["completed_picks"] == 1 and ev["pick_hit_rate"] == 1.0, ev
    assert abs(ev["final_equity"] - 52_800.0) < 1e-9
    assert abs(ev["total_return"] - (52_800.0 / 50_000.0 - 1.0)) < 1e-12
    assert ev["month_hit_rate"] == 0.5, ev                   # one winning month of two
    assert abs(ev["max_drawdown"] - (52_800.0 / 53_000.0 - 1.0)) < 1e-12, ev["max_drawdown"]
    assert ev["cagr"] is not None and ev["sharpe_monthly"] is not None
    assert ev["benchmark_cagr"] is not None
    assert ev["churn_per_month"] == 0.0 and not ev["twitchy"]
    assert abs(ev["avg_holding_days"] - 28.0) < 1e-12, ev["avg_holding_days"]
    assert ev["picks_still_open"] == 0
    s = ev["slippage"]
    assert s["fills_measured"] == 2 and s["realized_sides"] == 2
    assert abs(s["mean_realized_slip_vs_mark_pct"] - 1.0) < 1e-12, s   # (+2% buy, 0% sell)/2

    print("PASS: walkforward harness (slippage sign math, regime bands, benchmark "
          "construction, no-peek gate raises on stale matrix / score drift / empty "
          "snapshot, section-11 metrics on a hand-computed round trip)", flush=True)
    sys.exit(0)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="selfcheck")   # bare invocation = the self-check
    ap.add_argument("--verify-determinism", action="store_true")
    args = ap.parse_args(argv)
    if args.profile == "selfcheck":
        _synthetic_check()
    run(args.profile, verify_determinism=args.verify_determinism)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
