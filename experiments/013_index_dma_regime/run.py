"""E013 — the BRD's shelved index regime filter (Nifty 200 TRI vs its 200-session DMA)
measured on the REALIZED walk-forward result (pre-registered in hypothesis.md, run AFTER
that file was written, per BRD 12).

The signal's data path only became available on 2026-09-27 (sourced NIFTY 200 TRI, daily
since 2011, table `index_tri`); the BRD risk row had kept the filter at "no data path".
This experiment tests the INDEX leg (the VIX leg still has none) exactly as the proposal
words it: risk-off (index below its own 200-session DMA) -> go to cash.

Machinery: the harness's own window, tape, picks and engine pass, so the comparison IS the
realized result with one gate added. The BASELINE arm (gate inert) must reproduce the
persisted `runs/walkforward/harness_results.json` engine block BIT-FOR-BIT — that guard is
this experiment's runnable check. Arms (fixed in hypothesis.md, none swept):
  CASH     : risk-off month -> liquidate the book at that month-end (trigger `regime`,
             T+1 fills) and submit no buys; re-entry on the next risk-on month.
  NO_BUYS  : risk-off month -> block new buys; holdings ride their own exits.

Decision rule (conjunctive, primary arm CASH only): CAGR higher AND maxDD smaller AND
Sharpe higher than baseline, with a vacuity guard (>= 3 risk-off folds). The window is
the walk-forward test slice — a PASS is opt-in-regret evidence, not a validation (the
window is burned for this rule family; see hypothesis.md's declaration).

python -m experiments.013_index_dma_regime.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import time

import duckdb

from src.backtest import smoke_e2e as smoke
from src.config import load

HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

INDEX = "NIFTY 200"
DMA_SESSIONS = 200
MIN_RISK_OFF = 3                       # vacuity guard (hypothesis.md)
RESULTS = os.path.join("runs", "walkforward", "harness_results.json")

_DMA_SQL = """
WITH idx AS (
    SELECT date, tri FROM index_tri
    WHERE index_name = ? AND tri IS NOT NULL
    ORDER BY date
), w AS (
    SELECT date, tri,
           count(*) OVER (ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) AS n,
           avg(tri)  OVER (ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) AS dma200
    FROM idx
)
SELECT strftime(date, '%Y-%m-%d') AS d, tri, dma200, n FROM w WHERE n >= 200
"""


def _signal(con, folds: list[str]) -> dict[str, dict]:
    """Nifty 200 TRI vs its 200-session DMA at each decision month-end (prints <= M only)."""
    rows = con.execute(_DMA_SQL, [INDEX]).fetchall()
    sig = {d: {"tri": t, "dma200": dm, "n": int(n)} for d, t, dm, n in rows}
    missing = [m for m in folds if m not in sig]
    assert not missing, f"no warmed DMA at {missing}"
    out = {}
    for m in folds:
        s = sig[m]
        assert s["n"] == DMA_SESSIONS, (m, s)
        s["ratio"] = s["tri"] / s["dma200"]
        s["state"] = "on" if s["ratio"] > 1.0 else "off"
        out[m] = s
    return out


def _signal_sanity(con, sig: dict[str, dict]) -> dict:
    """Recompute each fold's DMA in Python from that date's own trailing 200 prints and
    assert agreement — the no-look-ahead check (only prints <= M may enter)."""
    worst = 0.0
    for m, s in sig.items():
        prints = [r[0] for r in con.execute(
            "SELECT tri FROM index_tri WHERE index_name = ? AND date <= ?::DATE "
            "AND tri IS NOT NULL ORDER BY date DESC LIMIT ?", [INDEX, m, DMA_SESSIONS]
        ).fetchall()]
        assert len(prints) == DMA_SESSIONS, (m, len(prints))
        py_dma = sum(prints) / DMA_SESSIONS
        worst = max(worst, abs(py_dma - s["dma200"]))
    assert worst < 1e-9, worst
    return {"months_checked": len(sig), "max_abs_dma_diff": worst}


def _arm_metrics(ev: dict, res: dict) -> dict:
    """The harness's own §11 metric dict, trimmed to what the verdict and the record need."""
    return {
        "final_equity": ev["final_equity"], "total_return": ev["total_return"],
        "cagr": ev["cagr"], "sharpe_monthly": ev["sharpe_monthly"],
        "max_drawdown": ev["max_drawdown"],
        "benchmark_cagr": ev["benchmark_cagr"], "benchmark_sharpe": ev["benchmark_sharpe"],
        "fills": ev["fills"], "non_fills": ev["non_fills"],
        "non_fill_reasons": ev["non_fill_reasons"],
        "resized_buys": len(ev["resized_buys"]),
        "forced_exits": len(ev["forced_exits"]),
        "completed_picks": ev["completed_picks"], "pick_hit_rate": ev["pick_hit_rate"],
        "month_hit_rate": ev["month_hit_rate"],
        "churn_per_month": ev["churn_per_month"], "twitchy": ev["twitchy"],
        "avg_holding_days": ev["avg_holding_days"], "picks_still_open": ev["picks_still_open"],
        "slippage": ev["slippage"],
        "regime_sells": sum(1 for d in res["decisions"] if d["trigger"] == "regime"),
        "regime_sells_detail": [{"month": d["month"], "symbol": d["symbol"], "qty": d["qty"]}
                                for d in res["decisions"] if d["trigger"] == "regime"],
        "regime_off_months": res["regime_off_months"],
        "decisions": len(res["decisions"]),
        "equity_curve": ev["equity_curve"],
    }


def _bars(ev_arm: dict, ev_base: dict) -> dict:
    """The pre-registered conjunctive bars, plus the literal signed drawdown comparison.

    metrics.max_drawdown documents "a negative fraction", so hypothesis.md's words
    "strictly smaller drawdown" mean a SHALLOWER magnitude: |mdd_arm| < |mdd_base|. The
    hypothesis's inequality as written (`maxdd_cash < maxdd_baseline`) is sign-inverted
    against that convention; the words govern (E012's pattern: hypothesis words over a
    runner slip, disclosed), and the literal signed reading is recorded separately so the
    record shows both. No threshold moved: the arms clear the magnitude bar by 3.4pp."""
    return {"cagr_higher": ev_arm["cagr"] > ev_base["cagr"],
            "maxdd_shallower": abs(ev_arm["max_drawdown"]) < abs(ev_base["max_drawdown"]),
            "sharpe_higher": ev_arm["sharpe_monthly"] > ev_base["sharpe_monthly"],
            "maxdd_literal_signed_lower": ev_arm["max_drawdown"] < ev_base["max_drawdown"]}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    h = json.load(open(RESULTS, encoding="utf-8"))
    assert h["n_folds"] == 35, f"persisted run is not the 35-fold window: {h['n_folds']}"

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        # the selfcheck suite resets the derived chain to quick; rebuild at the full profile
        # through E007's real builder (E008a/E008b/E012's pattern), then pin the window to
        # the persisted run's own cutoff/boundary/refit/folds before any measurement
        E007._build_chain(con, cfg)
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        assert str(cutoff) == h["cutoff"], (cutoff, h["cutoff"])
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        folds = sorted({str(r[0]) for r in test_rows})
        assert folds == h["test_months"] and str(boundary) == h["boundary"]
        all_months = sorted({str(r[0]) for r in rows})
        prev_m = all_months[all_months.index(folds[0]) - 1]
        assert prev_m == h["refit_month"], (prev_m, h["refit_month"])
        by_month_all: dict[str, list] = {}
        for r in rows:
            by_month_all.setdefault(str(r[0]), []).append(r)
        picks_by_month = {m: smoke._picks(by_month_all[m]) for m in folds}
        for fr in h["folds"]:
            assert len(picks_by_month[fr["month"]]) == fr["picks"], fr["month"]
        val_bucket_rows = [r for m in folds for r in by_month_all[m]]

        sig = _signal(con, folds)
        sanity = _signal_sanity(con, sig)
        risk_off = [m for m in folds if sig[m]["state"] == "off"]
        close_idx = HARNESS._month_end_closes(con, [prev_m] + folds)
    finally:
        con.close()
    # AFTER the read-write connection is closed: _benchmark_sourced_tri opens the DB
    # read-only itself and treats ANY duckdb.Error as "table absent", so calling it with
    # a RW connection open on the same file silently returns None (the harness always
    # calls it with no connection open)
    tri_curve = HARNESS._benchmark_sourced_tri(cfg, prev_m, folds[-1])
    assert tri_curve is not None, "Nifty 500 TRI is required for the harness metrics"
    bench_eq = HARNESS._benchmark_for_window(tri_curve, folds[0], folds[-1])

    gate = h["engine"]["exit_gate"]
    kw = dict(market_warm=HARNESS.WARM_SESSIONS, engine_months_limit=len(folds))
    res_base = smoke._engine_pass(cfg, gate["mode"], gate["escalate_after"], sessions,
                                  by_month_all, folds, picks_by_month, val_bucket_rows, **kw)
    res_cash = smoke._engine_pass(cfg, gate["mode"], gate["escalate_after"], sessions,
                                  by_month_all, folds, picks_by_month, val_bucket_rows,
                                  regime_off=set(risk_off), regime_liquidate=True, **kw)
    res_nb = smoke._engine_pass(cfg, gate["mode"], gate["escalate_after"], sessions,
                                by_month_all, folds, picks_by_month, val_bucket_rows,
                                regime_off=set(risk_off), **kw)
    ev_base = HARNESS._evaluate_pass(res_base, folds, bench_eq, close_idx)
    ev_cash = HARNESS._evaluate_pass(res_cash, folds, bench_eq, close_idx)
    ev_nb = HARNESS._evaluate_pass(res_nb, folds, bench_eq, close_idx)

    # Post-hoc fragility probe (NOT pre-registered, no verdict, disclosure only): the
    # 2024-12-31 signal is a hair-trigger (ratio 0.9990 = 10bp below its DMA) and dropping
    # new entries at that month-end is the gate's earliest action. This one extra pass
    # re-runs the primary arm with that month forced risk-ON, to expose how much of the
    # result hangs on that coin flip. It cannot change the decision.
    HAIR_TRIGGER = "2024-12-31"
    res_probe = smoke._engine_pass(cfg, gate["mode"], gate["escalate_after"], sessions,
                                   by_month_all, folds, picks_by_month, val_bucket_rows,
                                   regime_off=set(risk_off) - {HAIR_TRIGGER},
                                   regime_liquidate=True, **kw)
    ev_probe = HARNESS._evaluate_pass(res_probe, folds, bench_eq, close_idx)

    # ---- the guard: the gate-inert arm IS the persisted realized run ---------------------
    dump = lambda d: json.dumps(d, default=str, sort_keys=True)        # noqa: E731
    if dump(ev_base) != dump(h["engine"]):
        diffs = sorted(k for k in set(ev_base) | set(h["engine"])
                       if dump(ev_base.get(k)) != dump(h["engine"].get(k)))
        raise AssertionError(f"baseline does not reproduce the persisted harness engine "
                             f"block; differing fields: {diffs}")

    bars_cash = _bars(ev_cash, ev_base)
    bars_nb = _bars(ev_nb, ev_base)
    non_vacuous = len(risk_off) >= MIN_RISK_OFF
    bar_keys = ("cagr_higher", "maxdd_shallower", "sharpe_higher")
    verdict = ("INADEQUATE" if not non_vacuous else
               "PASS" if all(bars_cash[k] for k in bar_keys) else "REJECTED")
    literal_verdict = ("INADEQUATE" if not non_vacuous else
                       "PASS" if all(bars_cash[k] for k in bar_keys
                                     if k != "maxdd_shallower")
                       and bars_cash["maxdd_literal_signed_lower"] else "REJECTED")

    out = {
        "experiment": "E013_index_dma_regime", "git_hash": git, "profile": args.profile,
        "question": "does Nifty 200 TRI below its 200-session DMA (risk-off) improve the "
                    "realized walk-forward engine result when taken to cash / blocking buys?",
        "window": {"cutoff": str(cutoff), "boundary": str(boundary), "refit_month": prev_m,
                   "folds": folds, "n_folds": len(folds)},
        "signal": {"index": INDEX, "dma_sessions": DMA_SESSIONS, "cadence": "monthly "
                   "(decision month-end close; fills T+1 by the engine's protocol)",
                   "rule": "risk_off iff tri(M) <= dma200(M); TRI series, dividends "
                           "included; VIX leg absent (no data path)",
                   "months": {m: sig[m] for m in folds},
                   "risk_off_months": risk_off, "n_risk_off": len(risk_off),
                   "sanity": sanity},
        "baseline_guard": {"bit_identical_to_harness_engine": True,
                           "source": RESULTS, "rerun_final_equity": ev_base["final_equity"],
                           "harness_final_equity": h["engine"]["final_equity"]},
        "arms": {"baseline": _arm_metrics(ev_base, res_base),
                 "cash": _arm_metrics(ev_cash, res_cash),
                 "no_buys": _arm_metrics(ev_nb, res_nb),
                 "cash_probe_dec24_risk_on": _arm_metrics(ev_probe, res_probe)},
        "decision": {"rule": "primary arm CASH must hold ALL of: cagr higher, maxdd "
                             "shallower, sharpe higher vs baseline (hypothesis.md); vacuity "
                             "guard >= 3 risk-off folds",
                     "n_risk_off": len(risk_off), "non_vacuous": non_vacuous,
                     "bars_cash": bars_cash, "bars_no_buys_diagnostic": bars_nb,
                     "verdict": verdict, "verdict_literal_signed_reading": literal_verdict,
                     "pre_registration_disclosure":
                         "hypothesis.md's inequality 'maxdd_cash < maxdd_baseline' is "
                         "sign-inverted against metrics.max_drawdown's documented "
                         "negative-fraction convention; its words 'strictly smaller drawdown' "
                         "state the intent, and the substantive verdict follows the words. "
                         "The literal signed reading is recorded (it reads REJECTED). "
                         "Corrected after seeing the numbers, disclosed; no bar or threshold "
                         "changed, and the arms clear the magnitude bar by 3.4pp.",
                     "post_hoc_fragility_probe": {
                         "status": "post-hoc, not pre-registered, no verdict, disclosure only",
                         "what": f"primary CASH arm with {HAIR_TRIGGER} forced risk-ON "
                                 "(its ratio was 0.9990, 10bp below the DMA)",
                         "final_equity": ev_probe["final_equity"],
                         "cagr": ev_probe["cagr"], "sharpe_monthly": ev_probe["sharpe_monthly"],
                         "max_drawdown": ev_probe["max_drawdown"],
                         "bars_vs_baseline": _bars(ev_probe, ev_base)},
                     "test_window_burn": "this test runs on the walk-forward window: a PASS "
                                         "is opt-in-regret evidence, not a validation; any "
                                         "adoption needs a fresh pre-registered out-of-sample",
                     "secondary_arm": "no_verdict (diagnostic only)"},
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                              # noqa: E731
    print(f"window: {len(folds)} folds {folds[0]} -> {folds[-1]} (cutoff {cutoff})")
    print(f"signal: {INDEX} vs {DMA_SESSIONS}-session DMA -> risk-off in {len(risk_off)} "
          f"months (sanity: DMA reproduced in Python at all {sanity['months_checked']}, "
          f"max diff {sanity['max_abs_dma_diff']:.1e})")
    print(f"        risk-off: {', '.join(risk_off)}")
    print(f"guard : baseline arm reproduces harness_results.json engine block bit-for-bit "
          f"(equity {ev_base['final_equity']:,.2f})")
    print("\narm          equity        ret      CAGR     Sharpe    maxDD   fills picks "
          "hit   month-hit churn/mo  regime-sells")
    for name, m in (("baseline", out["arms"]["baseline"]), ("CASH", out["arms"]["cash"]),
                    ("NO_BUYS", out["arms"]["no_buys"]),
                    ("CASH*", out["arms"]["cash_probe_dec24_risk_on"])):
        print(f"  {name:<9} {m['final_equity']:>10,.0f}  {pct(m['total_return']):>8}  "
              f"{pct(m['cagr']):>8}  {m['sharpe_monthly']:>7.3f}  "
              f"{m['max_drawdown']:>7.2%}  {m['fills']:>5} {m['completed_picks']:>5} "
              f"{m['pick_hit_rate']:>4.0%}  {m['month_hit_rate']:>5.0%}   "
              f"{m['churn_per_month']:>6.2f}  {m['regime_sells']:>6}")
    print(f"\nprimary arm CASH bars vs baseline: {bars_cash}")
    print(f"secondary NO_BUYS bars (diagnostic): {bars_nb}")
    print(f"CASH* = post-hoc fragility probe (2024-12-31 forced risk-ON, not pre-registered)")
    print(f"DECISION: {verdict}   (literal signed-inequality reading of the same bars: "
          f"{literal_verdict}; disclosure in results.json)"
          + ("  (opt-in-regret: test-window burn declared in hypothesis.md)"
             if verdict == "PASS" else ""))
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
