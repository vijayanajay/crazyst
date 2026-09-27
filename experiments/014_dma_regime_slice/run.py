"""E014 — the risk-off buy-block on the 145-month validation slice: does the DMA signal
travel across episodes? (Pre-registered in hypothesis.md, run AFTER that file was written,
per BRD 12.)

E013 measured the shelved index filter on the 35-month realized window: the buy block is
the actionable core, but 8 gated intervals and one re-entry lottery cannot tell signal from
path. This experiment re-runs the buy block on the frozen validation slice (P4.1's split:
145 months, 2011-07-29 -> 2023-07-31, boundary 2023-09-24; test window untouched) and asks
whether the gated intervals are worse in the baseline, consistently, across the slice's
pre-named episodes (2011 euro, 2013 taper, 2015-16 China/oil, 2018 IL&FS, 2020 COVID,
2022 rates).

Arms: BASELINE (gate inert), BUY_BLOCK (no new buys in risk-off folds; E013's core), CASH
(BUY_BLOCK + liquidation at risk-off month-ends; diagnostic, no verdict). Guards: the
baseline's 12-month prefix (warm=0, the smoke's own convention) must reproduce the
persisted `runs/smoke_e2e/smoke_results.json` escalate arm bit-for-bit; the slice's
pick-months must equal E012's committed 4,579 with the mean monthly IC equal to E012's
0.375-arm IC to 1e-9; every warmed fold's DMA is recomputed in Python.

python -m experiments.014_dma_regime_slice.run --profile full
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

from src.backtest import smoke_e2e as smoke
from src.config import load
from src.stats import t_sf_two_sided

E013 = importlib.import_module("experiments.013_index_dma_regime.run")   # metric extractors
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

INDEX = "NIFTY 200"
DMA_SESSIONS = 200
MIN_GATED = 10                        # vacuity guard (hypothesis.md)
PICKS_PIN = 4579                      # E012's 0.375-arm re-baseline (smoke's own pin)
EPISODES = (("2011_euro", "2011-07", "2011-12"), ("2013_taper", "2013-05", "2013-09"),
            ("2015_16_china", "2015-08", "2016-03"), ("2018_ilfs", "2018-09", "2018-12"),
            ("2020_covid", "2020-02", "2020-05"), ("2022_rates", "2022-01", "2022-06"))
SMOKE_RESULTS = os.path.join("runs", "smoke_e2e", "smoke_results.json")
E012_RESULTS = os.path.join("experiments", "012_floor_at_8slots", "results.json")

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
SELECT strftime(date, '%Y-%m-%d') AS d, tri, dma200, n FROM w
"""


def _signal(con, folds: list[str], index_name: str = INDEX) -> tuple[dict[str, dict], str]:
    """A sourced TRI vs its own 200-session DMA at every slice month-end. Folds before the
    DMA has 200 prints are risk-ON by construction (a filter with no history cannot fire);
    the first warmed fold is returned so the report can state where reachability starts."""
    rows = con.execute(_DMA_SQL, [index_name]).fetchall()
    by_date = {d: (t, dm, int(n)) for d, t, dm, n in rows}
    out, first_warmed = {}, None
    for m in folds:
        assert m in by_date, f"no {index_name} print on fold {m}"
        tri, dma, n = by_date[m]
        warmed = n >= DMA_SESSIONS
        if warmed and first_warmed is None:
            first_warmed = m
        out[m] = {"tri": tri, "dma200": dma, "n": n, "warmed": warmed,
                  "ratio": tri / dma,
                  "state": ("off" if tri <= dma else "on") if warmed else "on"}
    assert first_warmed, "no warmed fold in the slice"
    return out, first_warmed


def _signal_sanity(con, sig: dict[str, dict]) -> dict:
    """Recompute each WARMED fold's DMA in Python from that date's own trailing 200 prints
    (no-look-ahead check); un-warmed folds are skipped by construction."""
    worst, checked = 0.0, 0
    for m, s in sig.items():
        if not s["warmed"]:
            assert s["n"] < DMA_SESSIONS, (m, s)
            continue
        prints = [r[0] for r in con.execute(
            "SELECT tri FROM index_tri WHERE index_name = ? AND date <= ?::DATE "
            "AND tri IS NOT NULL ORDER BY date DESC LIMIT ?", [INDEX, m, DMA_SESSIONS]
        ).fetchall()]
        assert len(prints) == DMA_SESSIONS, (m, len(prints))
        worst = max(worst, abs(sum(prints) / DMA_SESSIONS - s["dma200"]))
        checked += 1
    assert worst < 1e-9, worst
    return {"warmed_folds_checked": checked, "max_abs_dma_diff": worst}


def _paired(diffs: list[float]) -> dict:
    """One-sample t on the interval differences d = baseline - arm.

    SIGN CONVENTION (disclosed in the verdict): hypothesis.md's parenthetical says
    "positive = the baseline did worse", which is arithmetically wrong for negative
    returns — with d = base - arm, the baseline did worse when d < 0. Both one-sided p
    values are returned so the record can carry the INTENDED reading (gate helps =
    mean(d) < 0) and the parenthetical's literal reading (mean(d) > 0) side by side."""
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else 0.0
    t = mean / (sd / math.sqrt(n)) if sd > 0 else (0.0 if mean == 0 else math.copysign(1e9, mean))
    p2 = t_sf_two_sided(t, n - 1) if n > 1 else 1.0
    p_pos = p2 / 2 if mean >= 0 else 1 - p2 / 2
    return {"n": n, "mean": mean, "sd": sd, "t": t, "p_two_sided": p2,
            "p_one_sided_positive": p_pos, "p_one_sided_negative": 1 - p_pos}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e012 = json.load(open(E012_RESULTS, encoding="utf-8"))
    ic_pin = e012["arms"]["0.375"]["ic_val_slice"]
    smoke_ep = json.load(open(SMOKE_RESULTS, encoding="utf-8"))["engine_passes"]["escalate"]
    dump = lambda x: json.dumps(x, default=str, sort_keys=True)          # noqa: E731

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)                 # full profile; selfcheck resets to quick
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        folds = sorted({str(r[0]) for r in val_rows})
        assert len(folds) == 145 and folds[0] == "2011-07-29" and folds[-1] == "2023-07-31", \
            (len(folds), folds[:1], folds[-1:])
        test_months = sorted({str(r[0]) for r in test_rows})
        assert str(boundary) == "2023-09-24" and len(test_months) == 35 and \
            test_months[0] == "2023-08-31", (boundary, len(test_months), test_months[:1])
        # NOTE: unlike the harness window, the slice's first fold IS the matrix's first
        # month - there is no refit month before it, so the benchmark is rebased at folds[0]
        # itself (it feeds only _evaluate_pass's benchmark_cagr/sharpe, never the engine)
        by_month_all: dict[str, list] = {}
        for r in rows:
            by_month_all.setdefault(str(r[0]), []).append(r)
        picks_by_month = {m: smoke._picks(by_month_all[m]) for m in folds}
        val_bucket_rows = [r for m in folds for r in by_month_all[m]]

        sig, first_warmed = _signal(con, folds)
        sanity = _signal_sanity(con, sig)
        risk_off = [m for m in folds if sig[m]["state"] == "off"]
        # the BENCHMARK (Nifty 500 TRI, reporting only) is sampled at each fold's own index
        # print: the sourced 500's own month-end marks disagree with the equity calendar on
        # 2 slice folds (2015-02-28, 2016-10-30 - exchange special sessions the bhav
        # calendar does not carry), and the strategy's decision dates govern either way
        sig500, _ = _signal(con, folds, "NIFTY 500")
        close_idx = HARNESS._month_end_closes(con, folds)
    finally:
        con.close()
    base500 = sig500[folds[0]]["tri"]
    bench_eq = [{"date": m, "equity": sig500[m]["tri"] / base500} for m in folds]

    # ---- guards --------------------------------------------------------------------------
    # A) engine-pass / hook regression, on the smoke's OWN convention and inputs (its
    #    _fetch keeps labeled rows only): the 12-month pass must reproduce the committed
    #    runs/smoke_e2e escalate arm bit-for-bit.
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows_lbl, cutoff_lbl = smoke._fetch(con)
        val_lbl, _, _ = P41.split_slice(rows_lbl, cutoff_lbl)
        elig_pin = con.execute("SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]
    finally:
        con.close()
    by_month_lbl: dict[str, list] = {}
    for r in val_lbl:
        by_month_lbl.setdefault(str(r[0]), []).append(r)
    assert sorted(by_month_lbl) == folds, "labeled-only slice months differ from the folds"
    assert elig_pin == e012["arms"]["0.375"]["eligibles"], (elig_pin,)
    mean_ic = smoke._mean_monthly_ic(by_month_lbl)   # IC needs labels: convention-free
    assert abs(mean_ic - ic_pin) < 1e-9, (mean_ic, ic_pin)
    gate = cfg["backtest"]["exit_gate"]
    assert gate.get("mode", "escalate") == "escalate", gate   # the smoke guard arm's mode
    picks_lbl = {m: smoke._picks(by_month_lbl[m]) for m in folds}
    res_smoke = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                                   by_month_lbl, folds, picks_lbl, val_lbl,
                                   engine_months_limit=len(smoke_ep["months"]))
    n12 = len(smoke_ep["months"])
    assert dump(res_smoke["curve"][:n12]) == dump(smoke_ep["curve"]), "smoke curve prefix"
    assert dump(res_smoke["fill_log"]) == dump(smoke_ep["fill_log"]), "smoke fill_log"
    assert dump(res_smoke["decisions"]) == dump(smoke_ep["decisions"]), "smoke decisions"
    assert dump(res_smoke["month_rows"][:n12]) == dump(smoke_ep["month_rows"]), "smoke months"
    # B) tape pin for the ARM convention (the harness's: selection from ALL decision-date
    #    eligible rows, labels consulted only after selection). Adding unlabeled rows to
    #    the cross-section can only grow k, so the arm pick set is >= the labeled-only pin.
    all_picks = [p for m in folds for p in picks_by_month[m]]
    assert len(all_picks) >= PICKS_PIN, (len(all_picks), PICKS_PIN)

    # ---- arms (warm=20: the harness's own warm-ADV convention) ---------------------------
    kw = dict(market_warm=HARNESS.WARM_SESSIONS, engine_months_limit=len(folds))
    res_base = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                                  by_month_all, folds, picks_by_month, val_bucket_rows, **kw)
    res_bb = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                                by_month_all, folds, picks_by_month, val_bucket_rows,
                                regime_off=set(risk_off), **kw)
    res_cash = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                                  by_month_all, folds, picks_by_month, val_bucket_rows,
                                  regime_off=set(risk_off), regime_liquidate=True, **kw)
    ev_base = HARNESS._evaluate_pass(res_base, folds, bench_eq, close_idx)
    ev_bb = HARNESS._evaluate_pass(res_bb, folds, bench_eq, close_idx)
    ev_cash = HARNESS._evaluate_pass(res_cash, folds, bench_eq, close_idx)

    # ---- the paired premise statistic (pre-registered) -----------------------------------
    def _intervals(curve):
        return [curve[i + 1]["equity"] / curve[i]["equity"] - 1.0
                for i in range(len(curve) - 1)]

    rb, rbb, rc = (_intervals(ev_base["equity_curve"]),
                   _intervals(ev_bb["equity_curve"]),
                   _intervals(ev_cash["equity_curve"]))
    gated = [j for j in range(len(folds) - 1) if sig[folds[j]]["state"] == "off"]
    ungated = [j for j in range(len(folds) - 1) if j not in set(gated)]
    d_bb = [rb[j] - rbb[j] for j in gated]
    d_bb_placebo = [rb[j] - rbb[j] for j in ungated]
    d_cash = [rb[j] - rc[j] for j in gated]
    stats_bb, stats_cash = _paired(d_bb), _paired(d_cash)
    stats_placebo = _paired(d_bb_placebo)

    ep_rows = []
    for name, a, b in EPISODES:
        js = [j for j in gated if a <= folds[j][:7] <= b]
        d = [rb[j] - rbb[j] for j in js]
        ep_rows.append({"episode": name, "from": a, "to": b, "gated_intervals": len(js),
                        "mean_d": (sum(d) / len(d)) if d else None,
                        "sum_d": sum(d) if d else None,
                        "base_sum_ret": sum(rb[j] for j in js) if js else None,
                        "arm_sum_ret": sum(rbb[j] for j in js) if js else None})
    included = [e for e in ep_rows if e["gated_intervals"] >= 3]
    helps = sum(1 for e in included if e["mean_d"] < 0)      # d<0: baseline worse
    hinders = sum(1 for e in included if e["mean_d"] > 0)     # d>0: baseline better
    needed = math.ceil(2 * len(included) / 3) if included else 0
    # INTENDED direction (does the gate help? = is the baseline worse in gated intervals?)
    b1 = (len(gated) >= MIN_GATED and stats_bb["mean"] < 0
          and stats_bb["p_one_sided_negative"] < 0.05)
    b2 = len(included) >= 3 and helps >= needed
    # the hypothesis's parenthetical as literally written ("positive = baseline worse")
    b1_coded = (len(gated) >= MIN_GATED and stats_bb["mean"] > 0
                and stats_bb["p_one_sided_positive"] < 0.05)
    b2_coded = len(included) >= 3 and hinders >= needed
    verdict = ("INADEQUATE" if len(gated) < MIN_GATED else
               "CONFIRMED" if b1 and b2 else ("PARTIAL" if b1 or b2 else "REJECTED"))
    verdict_coded = ("INADEQUATE" if len(gated) < MIN_GATED else
                     "CONFIRMED" if b1_coded and b2_coded else
                     ("PARTIAL" if b1_coded or b2_coded else "REJECTED"))

    out = {
        "experiment": "E014_dma_regime_slice", "git_hash": git, "profile": args.profile,
        "question": "does blocking new entries in Nifty-200-below-200-DMA months help the "
                    "realized engine across the validation slice's episodes?",
        "window": {"cutoff": str(cutoff), "boundary": str(boundary),
                   "first_month": folds[0], "last_month": folds[-1],
                   "n_folds": len(folds), "test_window_untouched": True},
        "signal": {"index": INDEX, "dma_sessions": DMA_SESSIONS,
                   "rule": "risk_off iff tri(M) <= dma200(M); prints <= M only; folds "
                           "before the DMA warms (2011-07..09) are risk-on by construction",
                   "first_warmed_month": first_warmed,
                   "risk_off_months": risk_off, "n_risk_off": len(risk_off),
                   "months": {m: sig[m] for m in folds}, "sanity": sanity},
        "benchmark": {"construction": "Nifty 500 TRI sampled at each fold's own index print "
                                          "(2 slice folds' sourced month-end marks differ "
                                          "from the equity calendar: 2015-02-28 / "
                                          "2016-10-30 special sessions), rebased at folds[0]; "
                                          "reporting only",
                      "final_tri": sig500[folds[-1]]["tri"]},
        "guards": {"smoke_escalate_prefix_12mo_bit_equal": True,
                   "smoke_guard_convention": "labeled-only rows + warm=0 (the smoke's own "
                                            "inputs); the arms run the harness convention "
                                            "(all eligible rows, warm=20)",
                   "arms_warm": HARNESS.WARM_SESSIONS,
                   "picks_total": len(all_picks), "picks_pin_labeled_only": PICKS_PIN,
                   "eligible_rows_pin": elig_pin,
                   "mean_monthly_ic": mean_ic, "e012_arm_ic": ic_pin,
                   "picks_and_ic_guards": "passed"},
        "arms": {"baseline": E013._arm_metrics(ev_base, res_base),
                 "buy_block": E013._arm_metrics(ev_bb, res_bb),
                 "cash": E013._arm_metrics(ev_cash, res_cash)},
        "premise": {"n_gated_intervals": len(gated), "n_ungated_intervals": len(ungated),
                    "buy_block_gated": stats_bb, "buy_block_placebo_ungated": stats_placebo,
                    "cash_gated_diagnostic": stats_cash,
                    "episodes": ep_rows, "episodes_included": len(included),
                    "episodes_gate_favored": helps, "episodes_baseline_favored": hinders,
                    "episodes_needed": needed,
                    "gated_baseline_mean": sum(rb[j] for j in gated) / len(gated),
                    "ungated_baseline_mean": sum(
                        rb[j] for j in ungated) / len(ungated)},
        "decision": {"rule": "INTENDED: gate helps iff the baseline is worse in gated "
                             "intervals (mean d<0) with one-sided p<0.05 (n>=10), and at "
                             "least ceil(2/3*counted) episodes with mean d<0, >=3 counted "
                             "(hypothesis.md's question; its parenthetical sign claim was "
                             "arithmetically wrong - disclosure below)",
                     "bars": {"B1": b1, "B2": b2}, "verdict": verdict,
                     "bars_as_coded": {"B1": b1_coded, "B2": b2_coded},
                     "verdict_under_the_literal_parenthetical": verdict_coded,
                     "sign_disclosure": "hypothesis.md's parenthetical 'positive = the "
                                        "baseline did worse' is inverted for the d = base "
                                        "- arm definition (negative d means the baseline "
                                        "return was lower). Both readings were evaluated: "
                                        "the intended one and the literal one; they give "
                                        "the SAME verdict, so nothing hinges on the slip.",
                     "reading": "CONFIRMED = licence to spend fresh out-of-sample data, "
                                "never adoption (E013 burned the test window for this rule "
                                "family; hypothesis.md's reading rule)",
                     "cash_arm": "diagnostic only, no verdict"},
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]} (boundary {boundary}, "
          f"cutoff {cutoff}); test window untouched")
    print(f"guards: smoke escalate 12-month prefix bit-equal (labeled-only tape); eligible "
          f"rows {elig_pin} == E012 pin; IC {mean_ic:.10f} == E012 {ic_pin:.10f}; "
          f"arm-convention picks {len(all_picks)} >= labeled-only pin {PICKS_PIN}; DMA sanity "
          f"{sanity['max_abs_dma_diff']:.1e} over {sanity['warmed_folds_checked']} warmed folds")
    print(f"signal: risk-off in {len(risk_off)} of {len(folds)} folds "
          f"(first warmed {first_warmed}; 2011-07..09 risk-on by warm-up)")
    print("\narm          equity        ret      CAGR     Sharpe    maxDD   fills picks "
          "hit   churn/mo  regime-sells")
    for name, m in (("baseline", out["arms"]["baseline"]),
                    ("BUY_BLOCK", out["arms"]["buy_block"]), ("CASH", out["arms"]["cash"])):
        print(f"  {name:<9} {m['final_equity']:>10,.0f}  {pct(m['total_return']):>8}  "
              f"{pct(m['cagr']):>8}  {m['sharpe_monthly']:>7.3f}  "
              f"{m['max_drawdown']:>7.2%}  {m['fills']:>5} {m['completed_picks']:>5} "
              f"{m['pick_hit_rate']:>4.0%}  {m['churn_per_month']:>6.2f}  "
              f"{m['regime_sells']:>6}")
    print(f"\ngated intervals: {len(gated)} | d=base-arm mean {stats_bb['mean']:+.3%} "
          f"(one-sided p gate-helps {stats_bb['p_one_sided_negative']:.4f} / literal "
          f"{stats_bb['p_one_sided_positive']:.4f}); placebo ungated d "
          f"{stats_placebo['mean']:+.3%} (n={stats_placebo['n']})")
    print(f"baseline monthly engine return: gated mean "
          f"{out['premise']['gated_baseline_mean']:+.3%} vs ungated "
          f"{out['premise']['ungated_baseline_mean']:+.3%}")
    print("episode             gated   mean(d)     sum(d)   base_sum   arm_sum")
    for e in ep_rows:
        print(f"  {e['episode']:<16} {e['gated_intervals']:>5}  "
              f"{pct(e['mean_d']) if e['mean_d'] is not None else 'n/a':>8}  "
              f"{pct(e['sum_d']) if e['sum_d'] is not None else 'n/a':>8}  "
              f"{pct(e['base_sum_ret']) if e['base_sum_ret'] is not None else 'n/a':>8}  "
              f"{pct(e['arm_sum_ret']) if e['arm_sum_ret'] is not None else 'n/a':>8}"
              + ("" if e["gated_intervals"] >= 3 else "   (not counted: <3 gated)"))
    print(f"DECISION: {verdict}   (B1 {b1}, B2 {b2}: {helps}/{len(included)} counted "
          f"episodes gate-favored, needed {needed}; literal-parenthetical reading "
          f"{verdict_coded}); CASH gated d mean {stats_cash['mean']:+.3%} (diagnostic)")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
