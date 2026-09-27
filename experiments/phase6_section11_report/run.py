"""Phase 6 — the consolidated BRD §11 report, at the shipped config.

Runs once over the CURRENT walk-forward harness results (runs/walkforward/harness_results.json)
and writes the §11 report pack under runs/walkforward/, every artifact prefixed
phase6_section11_:

  phase6_section11_report.json   consolidated report (window/config/protocol, stats + CI,
                                 engine metrics, regimes, baseline comparison, buckets, IC)
  phase6_section11_equity.csv    strategy vs benchmark monthly equity
  phase6_section11_equity.png    strategy vs benchmark chart
  phase6_section11_monthly.csv   35 rows: picks, hits, returns, IC, benchmark, regime,
                                 engine return, end equity, sell triggers by name
  phase6_section11_ic.csv        22 features x (mean monthly IC, pooled IC, n)
  phase6_section11_buckets.csv   size-bucket attribution (as-of buckets, engine-verified)

Two things this script does beyond reading the JSON:

1. Engine-pass rerun (~3 min, deterministic) to capture `buckets` — the harness results do
   not persist the engine's own bucket attribution, and reconstructing one from the
   persisted fill_log alone overcounts (131 FIFO lots vs the engine's 125): the log is an
   event-ordering artifact, not the engine's book. The rerun's res["buckets"] is produced
   inside the engine pass (assert_consistent held there), so it is authoritative. The
   rerun also re-derives fills/non-fills/picks/decisions and every derived number is
   asserted equal to harness_results.json — the cross-check doubles as this script's
   runnable check.
2. Per-feature IC over the TEST WINDOW only (BRD §11's "per-feature IC table" is a
   run-level metric): monthly Spearman IC per labeled decision month + the pooled IC over
   all test-window labeled rows, disclosed that pooled != mean monthly (E002/E002b's
   pattern). ICs and n only — no new multiple-testing claims.

python -m experiments.phase6_section11_report.run
"""
from __future__ import annotations

import csv
import importlib
import json
import math
import os
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.model import composite as model

P41 = importlib.import_module("experiments.004_composite_v0.run")   # frozen slice split
HARNESS = importlib.import_module("src.walkforward.harness")
SMOKE = importlib.import_module("src.backtest.smoke_e2e")
from src.backtest.attribution import assert_consistent
from src.stats import spearman_ic

RESULTS = os.path.join("runs", "walkforward", "harness_results.json")
OUT_DIR = os.path.join("runs", "walkforward")
BASELINE_A8 = {   # experiments/011_slot_count/results.json, arm A8 (OLD methodology)
    "label": "E011 arm A8 (4 months before the selection/benchmark corrections; "
             "floor 0.75, 8 slots)",
    "final_equity": 892626.0949598341,
    "total_return": -0.10737390504016586,
    "cagr": -0.03932933422550311,
    "sharpe_monthly": -0.28905295748630266,
    "max_drawdown": -0.23917323976536975,
    "benchmark_cagr": 0.0848129150949104,
    "benchmark_sharpe": 0.4958280901773682,
    "completed_picks": 125, "pick_hit_rate": 0.32,
    "month_hit_rate": 0.6285714285714286,
    "churn_per_month": 3.4571428571428573,
    "avg_holding_days": 53.4747282393081,
    "fills": 258, "non_fills": 0,
    "slippage": {"fills_measured": 258,
                 "mean_buy_slip_vs_mark_pct": -0.09901801431565384,
                 "mean_sell_slip_vs_mark_pct": -0.3057865481271637,
                 "realized_sides": 250,
                 "mean_realized_slip_vs_mark_pct": -0.1301366950283452},
    "paper": {"picks": 2196, "positive_return_rate": 0.5656,
              "mean_gross": 0.023237, "mean_net_after_flat_cost": 0.013237},
}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _month_ret(curve):
    """Consecutive equity ratios -> month returns (curve[0] carries no return)."""
    out = []
    for prev, cur in zip(curve, curve[1:]):
        out.append(cur["equity"] / prev["equity"] - 1.0)
    return out


def _wilson(k, n, z=1.959963984540054):
    den = 1 + z * z / n
    c = (k / n + z * z / (2 * n)) / den
    half = z * math.sqrt((k / n) * (1 - k / n) / n + z * z / (4 * n * n)) / den
    return [c - half, c + half]


def _trigger_counts(h):
    """Sell triggers fired per month, counted from engine.decisions (sell actions).
    Skipped contingency buys are tracked separately (buys_skipped_no_slot)."""
    counts = {m: {} for m in h["test_months"]}
    for d in h["engine"]["decisions"]:
        if d["action"] == "sell":
            counts[d["month"]][d["trigger"]] = counts[d["month"]].get(d["trigger"], 0) + 1
    return counts


def main() -> int:
    t0 = time.monotonic()
    h = json.load(open(RESULTS, encoding="utf-8"))
    cfg = load("full")
    folds = h["test_months"]
    assert folds == h["engine"]["months"] and len(folds) == 35, len(folds)

    # ---- the walk again: authoritative buckets + the runnable cross-check ----------------
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
    finally:
        con.close()
    assert str(cutoff) == h["cutoff"], (cutoff, h["cutoff"])
    labeled_rows = [r for r in rows if r[1] is not None]
    val_rows, test_rows, boundary = P41.split_slice(labeled_rows, cutoff)
    assert str(boundary) == h["boundary"] and sorted({str(r[0]) for r in test_rows}) == folds

    by_month = {}
    for r in rows:
        by_month.setdefault(str(r[0]), []).append(r)
    picks = {m: SMOKE._picks(by_month[m]) for m in folds}
    val = [r for m in folds for r in by_month[m]]
    gate = h["engine"]["exit_gate"]
    res = SMOKE._engine_pass(cfg, gate["mode"], gate["escalate_after"], sessions,
                             by_month, folds, picks, val,
                             market_warm=HARNESS.WARM_SESSIONS,
                             engine_months_limit=len(folds))
    assert_consistent(res["buckets"])

    # ---- cross-check the rerun against the persisted run (the runnable check) ------------
    r_ev = h["engine"]
    assert res["fills"] == r_ev["fills"], (res["fills"], r_ev["fills"])
    assert res["non_fills"] == r_ev["non_fills"]
    assert len(res["decisions"]) == len(r_ev["decisions"])
    assert len(res["fill_log"]) == len(r_ev["fill_log"])
    assert [c["equity"] for c in res["curve"]] == [c["equity"] for c in r_ev["equity_curve"]], \
        "rerun equity diverged from the persisted full run"
    assert res["completed_picks"] == r_ev["completed_picks"]
    assert res["churn_per_month"] == r_ev["churn_per_month"]
    for m, mr in zip(folds, res["month_rows"]):
        fr = h["folds"][folds.index(m)]
        assert mr["eligible"] == fr["eligible"] and mr["held"] == fr["held"]
    print(f"cross-check PASS: rerun reproduces the persisted run "
          f"(fills {res['fills']}, non-fills {res['non_fills']}, picks "
          f"{res['completed_picks']}, decisions {len(res['decisions'])}, equity curve "
          f"bit-identical over {len(res['curve'])} marks)")

    # ---- buckets (engine-authoritative) ---------------------------------------------------
    bucket_rows = []
    for name in sorted(k for k in res["buckets"]):
        b = res["buckets"][name]
        bucket_rows.append({"bucket": name, "picks": b["picks"],
                            "hit_rate": b["hit_rate"], "mean_return": b["mean_return"],
                            "churn_per_month": b["churn_per_month"]})
    blended = res["buckets"]["blended"]
    assert blended["picks"] == res["completed_picks"] == r_ev["completed_picks"]
    fill_reasons = {}
    for f in res["fill_log"]:
        fill_reasons[f["reason"]] = fill_reasons.get(f["reason"], 0) + 1
    skips = res["buys_skipped_no_slot"]

    # ---- per-feature IC over the test window (BRD §11 run-level table) -------------------
    feats = list(model.PANEL_FEATURES)
    labeled = [r for r in val if r[1] is not None]
    per_month = {}
    for r in labeled:
        per_month.setdefault(str(r[0]), []).append(r)
    month_names = sorted(per_month)
    ic_rows = []
    for i, name in enumerate(feats):
        col = 2 + i
        monthly = []
        pooled_pairs = []
        for m in month_names:
            rs = per_month[m]
            pairs = [(r[col], r[1]) for r in rs
                     if r[col] is not None and not (isinstance(r[col], float)
                                                    and math.isnan(r[col]))]
            pooled_pairs.extend(pairs)
            monthly.append(spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
                           if len(pairs) >= 3 else None)
        pooled = (spearman_ic([p[0] for p in pooled_pairs], [p[1] for p in pooled_pairs])
                  if pooled_pairs else None)
        vals = [v for v in monthly if v is not None]
        ic_rows.append({
            "feature": name, "n": len(pooled_pairs),
            "mean_monthly_ic": _mean(monthly),
            "months_with_ic": len(vals),
            "pooled_ic": pooled,
        })
    comp = {f: next(r for r in ic_rows if r["feature"] == f) for f in model.FEATURES}

    # ---- monthly table --------------------------------------------------------------------
    bench_by_date = {r["date"]: r["equity"] for r in h["benchmark_curve"]}
    # Regime at decision month M is the proxy's return over the interval ENDING at M
    # (the harness's own labeling: month labels of the regime curve, first dropped).
    reg_curve = h["benchmark_regime_curve"]
    reg_rets = _month_ret(reg_curve)
    reg_months = sorted({r["date"][:7] for r in reg_curve})[1:]
    assert len(reg_rets) == len(reg_months) == len(folds)
    regime_by_date = dict(zip(reg_months, (HARNESS._regime_of(r) for r in reg_rets)))
    trig = _trigger_counts(h)
    cost = h["config"]["cost_per_side_pct"] / 100.0
    eq_by_month = {c["date"][:7]: c["equity"] for c in r_ev["equity_curve"]}
    engine_rets = _month_ret(r_ev["equity_curve"])
    engine_ret_by_month = {c["date"][:7]: ret
                           for c, ret in zip(r_ev["equity_curve"][1:], engine_rets)}
    # Benchmark monthly returns from the REGIME curve (the same proxy, one mark earlier:
    # it starts at the refit month), so the FIRST fold month's return is defined too —
    # and the regime label is by construction _regime_of of exactly this return.
    reg_by_date = {r["date"]: r["equity"] for r in h["benchmark_regime_curve"]}
    reg_dates = sorted(reg_by_date)
    bench_ret_by_date = {cur_d: reg_by_date[cur_d] / reg_by_date[prev_d] - 1.0
                         for prev_d, cur_d in zip(reg_dates, reg_dates[1:])}
    monthly = []
    for m, fr in zip(folds, h["folds"]):
        pk = picks[m]
        lab = [p for p in pk if p["ret"] is not None]
        rets = [p["ret"] for p in lab]
        d = str(fr["month"])[:7]
        monthly.append({
            "month": str(fr["month"]),
            "eligible": fr["eligible"], "picks": len(pk),
            "labeled": len(lab), "unlabeled": len(pk) - len(lab),
            "mean_gross": _mean(rets),
            "mean_net": (sum(rets) / len(rets) - 2 * cost) if rets else None,
            "composite_ic": fr["ic"],
            "benchmark_ret": bench_ret_by_date.get(str(fr["month"])),
            "regime": regime_by_date[d],
            "engine_ret": engine_ret_by_month.get(d),   # None at month 1: no prior mark yet
            "end_equity": eq_by_month.get(d),
            "sells_trigger_b_dma": trig[m].get("trigger_b_dma", 0),
            "sells_trigger_b_stop": trig[m].get("trigger_b_stop", 0),
            "sells_trigger_b_trail": trig[m].get("trigger_b_trail", 0),
            "sells_monthly_review": trig[m].get("monthly_review", 0),
            "buys_skipped_no_slot": sum(1 for s in skips if s["month"] == m),
        })
    # top5/decile/top20 hits per month need the winner labels: join decision month ->
    # next decision mdate, the harness's own label SQL pattern
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        cal = ("(SELECT mdate, lead(mdate) OVER (ORDER BY mdate) AS next_mdate "
               "FROM (SELECT DISTINCT mdate FROM universe_rank))")
        label_rows = con.execute(
            f"SELECT f.mdate, f.symbol, f.is_winner, w.is_top_decile, w.is_top20 "
            f"FROM feature_matrix f JOIN {cal} d ON d.mdate = f.mdate "
            "LEFT JOIN winners w ON w.symbol = f.symbol AND w.mdate = d.next_mdate "
            "WHERE f.mdate IN (SELECT unnest(CAST($ms AS DATE[])))",
            {"ms": folds}).fetchall()
    finally:
        con.close()
    lab_by_key = {(str(m), s): (w5, dec, t20) for m, s, w5, dec, t20 in label_rows}
    for row in monthly:
        m, hits3 = row["month"], [0, 0, 0]
        nl = 0
        for p in picks[m]:
            w5, dec, t20 = lab_by_key.get((m, p["symbol"]), (None, None, None))
            if w5 is None:
                continue
            nl += 1
            hits3[0] += bool(w5)
            hits3[1] += bool(dec)
            hits3[2] += bool(t20)
        row["top5_hits"], row["decile_hits"], row["top20_hits"] = hits3
        assert HARNESS._regime_of(row["benchmark_ret"]) == row["regime"], \
            f"{m}: regime label disagrees with the benchmark return it classifies"
        assert nl == row["labeled"], \
            f"{m}: winner-label join covers {nl} picks but {row['labeled']} have forward returns"
        row["labeled"] = nl

    # ---- equity CSV/PNG --------------------------------------------------------------------
    eq_csv = os.path.join(OUT_DIR, "phase6_section11_equity.csv")
    strat_rets = _month_ret(r_ev["equity_curve"])
    bench_rets = _month_ret(h["benchmark_curve"])
    # the §11 large-cap reference, sliced to the strategy window and rebased like the 500
    b2 = h.get("benchmark_nifty200") or None
    curve2 = rets2 = None
    if b2:
        curve2 = [r for r in b2["regime_curve"] if folds[0] <= r["date"] <= folds[-1]]
        assert [r["date"] for r in curve2] == [c["date"] for c in h["benchmark_curve"]], \
            "Nifty 200 and Nifty 500 month-end calendars diverge"
        base2 = curve2[0]["equity"]
        curve2 = [r["equity"] / base2 for r in curve2]
        rets2 = [b / a - 1.0 for a, b in zip(curve2, curve2[1:])]
    with open(eq_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "strategy_equity", "benchmark_equity", "nifty200_equity",
                    "strategy_return", "benchmark_return", "nifty200_return"])
        for i, (c, b) in enumerate(zip(r_ev["equity_curve"], h["benchmark_curve"])):
            # row i carries the return over the interval ENDING at i (row 0: none yet)
            sr = "" if i == 0 else f"{strat_rets[i - 1]:.6f}"
            br = "" if i == 0 else f"{bench_rets[i - 1]:.6f}"
            v2 = "" if curve2 is None else f"{curve2[i]:.6f}"
            r2 = "" if rets2 is None or i == 0 else f"{rets2[i - 1]:.6f}"
            assert c["date"] == b["date"]
            w.writerow([c["date"], f"{c['equity']:.2f}", f"{b['equity']:.6f}", v2, sr, br, r2])
        assert len(r_ev["equity_curve"]) == len(h["benchmark_curve"]) == 35

    png = os.path.join(OUT_DIR, "phase6_section11_equity.png")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dates = [c["date"] for c in r_ev["equity_curve"]]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(dates, [c["equity"] for c in r_ev["equity_curve"]],
            label=f"Strategy (8 slots, net) end {r_ev['final_equity']:,.0f}", lw=1.8)
    ax.plot(dates, [b["equity"] * 1_000_000 for b in h["benchmark_curve"]],
            label=f"{h.get('benchmark_source', 'Benchmark').split(' (')[0]} end "
                  f"{h['benchmark_curve'][-1]['equity'] * 1_000_000:,.0f}", lw=1.8)
    if curve2:
        ax.plot(dates, [v * 1_000_000 for v in curve2],
                label=f"Nifty 200 TRI (large-cap ref) end {curve2[-1] * 1_000_000:,.0f}",
                lw=1.5, ls="--")
    ax.set_title("Phase 6 §11 — walk-forward equity vs benchmark "
                 "(35 fold months, 2023-08 → 2026-06)")
    ax.set_ylabel("Equity (Rs, start 1,000,000)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(png, dpi=150)
    plt.close(fig)

    # ---- IC + bucket CSVs ------------------------------------------------------------------
    ic_csv = os.path.join(OUT_DIR, "phase6_section11_ic.csv")
    with open(ic_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["feature", "n", "mean_monthly_ic", "months_with_ic", "pooled_ic"])
        for r in ic_rows:
            w.writerow([r["feature"], r["n"],
                        "" if r["mean_monthly_ic"] is None else f"{r['mean_monthly_ic']:.6f}",
                        r["months_with_ic"],
                        "" if r["pooled_ic"] is None else f"{r['pooled_ic']:.6f}"])

    bk_csv = os.path.join(OUT_DIR, "phase6_section11_buckets.csv")
    with open(bk_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bucket", "picks", "hit_rate", "mean_return", "churn_per_month"])
        for r in bucket_rows:
            w.writerow([r["bucket"], r["picks"], f"{r['hit_rate']:.6f}",
                        f"{r['mean_return']:.6f}", f"{r['churn_per_month']:.6f}"])

    mon_csv = os.path.join(OUT_DIR, "phase6_section11_monthly.csv")
    cols = ["month", "eligible", "picks", "labeled", "unlabeled", "top5_hits",
            "decile_hits", "top20_hits", "mean_gross", "mean_net", "composite_ic",
            "benchmark_ret", "regime", "engine_ret", "end_equity",
            "sells_trigger_b_dma", "sells_trigger_b_stop", "sells_trigger_b_trail",
            "sells_monthly_review", "buys_skipped_no_slot"]
    with open(mon_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in monthly:
            w.writerow([
                row["month"], row["eligible"], row["picks"], row["labeled"],
                row["unlabeled"], row["top5_hits"], row["decile_hits"], row["top20_hits"],
                "" if row["mean_gross"] is None else f"{row['mean_gross']:.6f}",
                "" if row["mean_net"] is None else f"{row['mean_net']:.6f}",
                "" if row["composite_ic"] is None else f"{row['composite_ic']:.6f}",
                "" if row["benchmark_ret"] is None else f"{row['benchmark_ret']:.6f}",
                row["regime"],
                "" if row["engine_ret"] is None else f"{row['engine_ret']:.6f}",
                "" if row["end_equity"] is None else f"{row['end_equity']:.2f}",
                row["sells_trigger_b_dma"], row["sells_trigger_b_stop"],
                row["sells_trigger_b_trail"], row["sells_monthly_review"],
                row["buys_skipped_no_slot"],
            ])

    # ---- consolidated JSON ------------------------------------------------------------------
    tdiag = json.load(open(os.path.join("runs", "walkforward", "trigger_pnl_results.json"),
                           encoding="utf-8"))
    pp = h["paper_picks"]
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    report = {
        "report": "Phase 6 consolidated BRD section-11 report",
        "generated_by": "experiments/phase6_section11_report/run.py",
        "git_hash": git,
        "source_results": {"path": RESULTS, "git_hash": h["git_hash"],
                           "runtime_seconds": h["runtime_seconds"]},
        "window": {"cutoff": h["cutoff"], "boundary": h["boundary"],
                   "refit_month": h["refit_month"], "test_months": folds,
                   "n_folds": len(folds),
                   "eligible_rows_full_chain": 161942,
                   "test_window_matrix_rows": sum(len(v) for v in
                                                  [[r for r in by_month[m]] for m in folds])},
        "config": {"profile": h["profile"], "n_slots": h["config"]["n_slots"],
                   "floor_cr": h["config"]["floor_cr"],
                   "cost_per_side_pct": h["config"]["cost_per_side_pct"],
                   "exit_gate": h["engine"]["exit_gate"],
                   "start_capital": h["config"]["start_capital"],
                   "walkforward_months": h["config"]["walkforward_months"]},
        "protocol": h["protocol"],
        "statistical_check": {
            "selected": pp["selected"], "labeled": pp["n"],
            "unlabeled": pp["unlabeled"],
            "top5_hits": pp["hits"], "top5_hit_rate": pp["hit_rate"],
            "baseline_p": pp["baseline_p"],
            "binomial_p_one_sided": pp["binomial_p"],
            "binomial_p_two_sided": pp["binomial_p_two_sided"],
            "wilson95": pp["ci95_wilson"],
            "secondary_labels": pp["secondary_labels"],
            "positive_return_rate": pp["positive_return_rate"],
            "mean_gross": pp["mean_gross"],
            "mean_net_after_flat_cost": pp["mean_net_after_flat_cost"],
        },
        "engine": {k: r_ev[k] for k in
                   ("fills", "non_fills", "non_fill_reasons", "completed_picks",
                    "pick_hit_rate", "month_hit_rate", "cagr", "sharpe_monthly",
                    "max_drawdown", "benchmark_cagr", "benchmark_sharpe", "churn_per_month",
                    "twitchy", "avg_holding_days", "picks_still_open", "final_equity",
                    "total_return", "slippage")},
        "benchmark_source": h.get("benchmark_source"),
        "benchmark_nifty200": (None if not h.get("benchmark_nifty200") else
                               {k: h["benchmark_nifty200"][k]
                                for k in ("cagr", "sharpe", "note")}),
        "regime_table": h["regime_table"],
        "regime_table_nifty200": h.get("regime_table_nifty200"),
        "buckets": {"rows": bucket_rows, "blended": blended,
                    "note": "Engine-pass bucket attribution (as-of decision-month buckets), "
                            "assert_consistent() held inside the pass. Reconstructing buckets "
                            "from the persisted fill_log alone overcounts (131 FIFO lots vs "
                            "125): the fill log is an event-ordering artifact of rebuild-"
                            "from-log, not the engine's book — do not use it.",
                    "fill_reason_counts": fill_reasons,
                    "buys_skipped_no_slot": skips},
        "per_feature_ic": {
            "statistic": "Spearman IC vs next-month return over the test window only; "
                         "monthly per labeled decision month + pooled over all test-window "
                         "labeled rows (pooled != mean monthly — disclosed, no new "
                         "multiple-testing claims)",
            "composite_features": {k: {"mean_monthly_ic": v["mean_monthly_ic"],
                                       "pooled_ic": v["pooled_ic"], "n": v["n"]}
                                   for k, v in comp.items()},
            "all_features": ic_rows},
        "baseline_comparison": {
            "baseline": BASELINE_A8,
            "current": {"final_equity": r_ev["final_equity"],
                        "total_return": r_ev["total_return"], "cagr": r_ev["cagr"],
                        "sharpe_monthly": r_ev["sharpe_monthly"],
                        "max_drawdown": r_ev["max_drawdown"],
                        "benchmark_cagr": r_ev["benchmark_cagr"],
                        "completed_picks": r_ev["completed_picks"],
                        "pick_hit_rate": r_ev["pick_hit_rate"],
                        "month_hit_rate": r_ev["month_hit_rate"],
                        "churn_per_month": r_ev["churn_per_month"],
                        "avg_holding_days": r_ev["avg_holding_days"],
                        "fills": r_ev["fills"], "non_fills": r_ev["non_fills"],
                        "slippage": r_ev["slippage"]},
            "deltas": {
                "equity_rs": r_ev["final_equity"] - BASELINE_A8["final_equity"],
                "total_return_pp": (r_ev["total_return"] - BASELINE_A8["total_return"]) * 100,
                "cagr_pp": (r_ev["cagr"] - BASELINE_A8["cagr"]) * 100,
                "sharpe": r_ev["sharpe_monthly"] - BASELINE_A8["sharpe_monthly"],
                "max_drawdown_pp": (r_ev["max_drawdown"]
                                    - BASELINE_A8["max_drawdown"]) * 100},
            "not_apples_to_apples": (
                "The E011 A8 baseline ran the OLD harness methodology: selection from the "
                "label-available subset only (pre-correction), a raw-close benchmark proxy "
                "(pre-correction), and the 0.75 floor. The current run is the corrected "
                "harness at the shipped 0.375 floor, and its benchmark is now the SOURCED "
                "Nifty 500 TRI (was the EW adj-close proxy in both the baseline and the "
                "first corrected report) — so even benchmark_cagr is not comparable to the "
                "baseline's +8.48%. Three things moved at once, so the "
                "delta is NOT causally attributable to the floor change: E012 documented "
                "that under the OLD methodology a 0.375-floor re-run matched A8 "
                "bit-identically (equity 892,626.095, 2,212 paper picks; only HARDWYN's "
                "trigger label changed monthly_review -> trigger_b_dma, churn 3.457 -> "
                "3.486). Read the delta as the combined corrected-methodology + shipped-"
                "config effect on one shared window, not as the floor's effect."),
            "e012_old_methodology_equivalence": {
                "floor_0375_vs_075_at_old_methodology": "bit-identical equity "
                                                        "892,626.095; 2,212 paper picks; "
                                                        "churn 3.457 -> 3.486 "
                                                        "(HARDWYN trigger label)"},
        },
        "trigger_timing_diagnostic": {
            "source": tdiag["source_run"],
            "conventions": tdiag["conventions"],
            "trigger_ranking": tdiag["trigger_ranking"],
            "total_timing_delta_rs": tdiag["total_timing_delta_rs"],
            "symbol_concentration": tdiag["symbol_concentration"],
            "note": "§11-reporting-spirit diagnostic on THIS run: how much P&L each sell "
                    "trigger's timing destroyed or saved vs holding to the month-end review "
                    "counterfactual. Positive delta = the rule sold cheaper than the "
                    "month-end it skipped (destroyed)."},
        "artifacts": {"equity_csv": "phase6_section11_equity.csv",
                      "equity_png": "phase6_section11_equity.png",
                      "monthly_csv": "phase6_section11_monthly.csv",
                      "ic_csv": "phase6_section11_ic.csv",
                      "buckets_csv": "phase6_section11_buckets.csv",
                      "monthly_rows": len(monthly), "ic_rows": len(ic_rows),
                      "bucket_rows": len(bucket_rows) - 1},
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(OUT_DIR, "phase6_section11_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"wrote {path}")
    print(f"  {eq_csv}\n  {png}\n  {mon_csv}\n  {ic_csv}\n  {bk_csv}")
    bsum = ", ".join(f"{r['bucket']}={r['picks']}" for r in bucket_rows)
    print(f"PASS: Phase 6 section-11 report pack ({report['runtime_seconds']}s; buckets "
          f"{bsum}; blended {blended['picks']}; headline numbers asserted equal to "
          f"harness_results.json)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
