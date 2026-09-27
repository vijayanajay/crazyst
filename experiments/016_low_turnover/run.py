"""E016 — low-turnover engine: does suppressing the monthly review's churn recover the
edge the monthly architecture destroys? (Pre-registered in hypothesis.md, run AFTER that
file was written, per BRD 12.)

The break-even arithmetic (LEDGER 2026-09-27, breakeven.py): the top-5% pick edge decays
only ~0.31pp/month from 1-month to 12-month holds while round trips fall 12x — so churn x
costs, not signal decay, is the likeliest reason every engine configuration measured so far
loses to the index.

Arms (hypothesis.md is the contract): A BASELINE (shipped config; must equal E014's
committed arms.baseline bit-for-bit), B SELL_GATE (config-only: never sell on rank fade or
the 50-DMA streak; Trigger B stops/trails, GSM and universe exits remain), C MIN_HOLD_12
(new inert `_engine_pass` hook `min_hold`: monthly_review sells dropped before the
position's 12th held decision month; stops fire even in month 1).

Guards: G1 A == E014 baseline (json-equal); G2 tape pins (arm picks >= 4,579, eligible
== 161,942, IC == smoke.SLICE_IC_PIN to 1e-9); G3 mechanism (B and C emit strictly fewer
monthly_review sells than A); G4 hook inertness (the smoke re-run stays bit-identical,
checked separately after the hook edit). Bars: B1 an arm reaches slice CAGR >= A + 3.0pp;
B2 that arm's maxDD is not worse than A's by >5pp (negative-fraction convention). Every
arm is reported against the slice's index-equivalent CAGR (`benchmark_cagr`).

python -m experiments.016_low_turnover.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import time

import duckdb

from src.backtest import smoke_e2e as smoke
from src.config import load

E014 = importlib.import_module("experiments.014_dma_regime_slice.run")
E013 = importlib.import_module("experiments.013_index_dma_regime.run")   # _arm_metrics
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

E014_RESULTS = os.path.join(os.path.dirname(__file__), "..", "014_dma_regime_slice",
                            "results.json")

CAGR_BAR_PP = 3.0          # B1: CAGR_arm >= CAGR_A + 3.0pp
DD_TOL_PP = 5.0            # B2: maxDD_arm >= maxDD_A - 5pp (negative-fraction convention)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e014 = json.load(open(E014_RESULTS, encoding="utf-8"))
    dump = lambda x: json.dumps(x, default=str, sort_keys=True)          # noqa: E731
    assert smoke._cfg_test()["portfolio"]["monthly_review_replace_above_top_pct"] == 0.15

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
        assert str(boundary) == "2023-09-24" and len(test_months) == 35, (boundary,)
        assert str(cutoff) == e014["window"]["cutoff"], (str(cutoff),)
        by_month_all: dict[str, list] = {}
        for r in rows:
            by_month_all.setdefault(str(r[0]), []).append(r)
        picks_by_month = {m: smoke._picks(by_month_all[m]) for m in folds}
        val_bucket_rows = [r for m in folds for r in by_month_all[m]]
        sig500, _ = E014._signal(con, folds, "NIFTY 500")     # reporting-only benchmark
        close_idx = HARNESS._month_end_closes(con, folds)
    finally:
        con.close()
    base500 = sig500[folds[0]]["tri"]
    bench_eq = [{"date": m, "equity": sig500[m]["tri"] / base500} for m in folds]

    # ---- guards -----------------------------------------------------------------------
    # G2 tape pins on the smoke's labeled-only convention (IC needs labels)
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
    assert elig_pin == e014["guards"]["eligible_rows_pin"], (elig_pin,)
    ic_pin = smoke.SLICE_IC_PIN
    mean_ic = smoke._mean_monthly_ic(by_month_lbl)
    assert abs(mean_ic - ic_pin) < 1e-9, (mean_ic, ic_pin)
    all_picks = [p for m in folds for p in picks_by_month[m]]
    assert len(all_picks) >= 4_579, (len(all_picks),)

    # ---- arms (warm=20, the harness convention; E014's machinery) ----------------------
    gate = cfg["backtest"]["exit_gate"]
    kw = dict(market_warm=HARNESS.WARM_SESSIONS, engine_months_limit=len(folds))
    res_a = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                               by_month_all, folds, picks_by_month, val_bucket_rows, **kw)
    ov = {"monthly_review_sell_below_top_pct": 1.01,
          "monthly_review": {"ma_below_consecutive_closes": 999}}
    res_b = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                               by_month_all, folds, picks_by_month, val_bucket_rows,
                               portfolio_overrides=ov, **kw)
    res_c = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                               by_month_all, folds, picks_by_month, val_bucket_rows,
                               min_hold=12, **kw)
    ev = {k: HARNESS._evaluate_pass(r, folds, bench_eq, close_idx)
          for k, r in (("A", res_a), ("B", res_b), ("C", res_c))}

    # G1: arm A == E014's committed baseline (bit-for-bit)
    g1 = dump(E013._arm_metrics(ev["A"], res_a)) == dump(e014["arms"]["baseline"])
    assert g1, "arm A != E014's committed baseline"

    # G3 mechanism: the overrides/hooks must actually suppress monthly_review churn
    def mr_sells(res):
        return sum(1 for d in res["decisions"]
                   if d["action"] == "sell" and d["trigger"] == "monthly_review")
    n_mr = {k: mr_sells(r) for k, r in (("A", res_a), ("B", res_b), ("C", res_c))}
    g3 = n_mr["B"] < n_mr["A"] and n_mr["C"] < n_mr["A"]
    assert g3, (n_mr,)

    # ---- bars (pre-registered) ----------------------------------------------------------
    cagr_a = ev["A"]["cagr"]
    dd_a = ev["A"]["max_drawdown"]
    bars = {}
    for k in ("B", "C"):
        cagr_ok = ev[k]["cagr"] >= cagr_a + CAGR_BAR_PP / 100
        dd_ok = ev[k]["max_drawdown"] >= dd_a - DD_TOL_PP / 100   # negative fractions
        bars[k] = {"B1_cagr_ge_A_plus_3pp": cagr_ok,
                   "B2_maxdd_not_worse_by_5pp": dd_ok,
                   "passes_both": cagr_ok and dd_ok}
    winner = next((k for k in ("B", "C") if bars[k]["passes_both"]), None)
    verdict = "PASS" if winner else "REJECTED"

    rt = {k: (r["fills"]) / len(folds) for k, r in
          (("A", res_a), ("B", res_b), ("C", res_c))}      # fills per month, recorded

    out = {
        "experiment": "E016_low_turnover", "git_hash": git, "profile": args.profile,
        "window": {"folds": len(folds), "first": folds[0], "last": folds[-1],
                   "boundary": str(boundary), "cutoff": str(cutoff),
                   "test_window": "untouched"},
        "arms_defined": {
            "A": "shipped config (must equal E014's committed baseline)",
            "B": "SELL_GATE: sell_below_top_pct 1.01, ma_below_consecutive_closes 999 "
                 "(config-only; Trigger B / GSM / universe exits unchanged)",
            "C": "MIN_HOLD_12: monthly_review sells dropped before the 12th held decision "
                 "month (new inert hook; stops fire even in month 1)"},
        "guards": {"G1_armA_equals_E014_baseline": g1,
                   "G2_arm_picks": len(all_picks), "G2_picks_pin": 4_579,
                   "G2_eligible_rows": elig_pin,
                   "G2_mean_monthly_ic": mean_ic, "G2_ic_pin": ic_pin,
                   "G3_monthly_review_sells": n_mr, "G3_passed": g3,
                   "G4_smoke_bit_identical": "checked separately after the hook edit; the "
                                             "shipped call passes no min_hold",
                   "passed": True},
        "arms": {k: E013._arm_metrics(ev[k], r) for k, r in
                 (("A", res_a), ("B", res_b), ("C", res_c))},
        "fills_per_month": rt,
        "bars": {"CAGR_bar_pp": CAGR_BAR_PP, "DD_tol_pp": DD_TOL_PP,
                 "maxDD_convention": "negative fraction; worse-by-5pp means "
                                     "maxDD < maxDD_A - 0.05",
                 "per_arm": bars, "winner": winner},
        "index_equivalent": {"benchmark_cagr_A": ev["A"]["benchmark_cagr"],
                             "note": "Nifty 500 TRI sampled at each fold's own index print, "
                                     "rebased at folds[0]; the same engine pass reports it "
                                     "for every arm — printed in the verdict next to each "
                                     "arm so no result can read as success while losing to "
                                     "the index"},
        "verdict": verdict,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]} (boundary {boundary}); "
          f"test window untouched")
    print(f"guards: G1 arm A == E014 baseline (bit-for-bit); G2 picks {len(all_picks)} >= "
          f"4,579, eligible {elig_pin}, IC {mean_ic:.10f} == pin {ic_pin:.10f}; G3 "
          f"monthly_review sells A/B/C = {n_mr['A']}/{n_mr['B']}/{n_mr['C']}")
    print(f"\narm          equity        ret      CAGR     Sharpe    maxDD   fills  "
          f"MR-sells/mo   index CAGR")
    for k, name in (("A", "A baseline"), ("B", "B SELL_GATE"), ("C", "C MIN_HOLD_12")):
        m = out["arms"][k]
        print(f"  {name:<14} {m['final_equity']:>10,.0f}  {pct(m['total_return']):>8}  "
              f"{pct(m['cagr']):>8}  {m['sharpe_monthly']:>7.3f}  {m['max_drawdown']:>7.2%}  "
              f"{m['fills']:>5}  {n_mr[k] / len(folds):>8.2f}   "
              f"{pct(m['benchmark_cagr']):>8}")
    print(f"\nbars: B1 CAGR >= A{pct(cagr_a)} + {CAGR_BAR_PP}pp; B2 maxDD within "
          f"{DD_TOL_PP}pp of {dd_a:.2%}")
    for k in ("B", "C"):
        print(f"  {k}: CAGR {pct(out['arms'][k]['cagr'])} (B1 "
              f"{bars[k]['B1_cagr_ge_A_plus_3pp']}), maxDD "
              f"{out['arms'][k]['max_drawdown']:.2%} (B2 "
              f"{bars[k]['B2_maxdd_not_worse_by_5pp']})")
    print(f"index-equivalent over the same 145 months: CAGR "
          f"{pct(ev['A']['benchmark_cagr'])} — every arm is reported against it")
    print(f"DECISION: {verdict}"
          + (f" (winner: {winner})" if winner else
             " — neither arm clears B1+B2; the low-turnover family is closed on this slice"
             " per the pre-registration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
