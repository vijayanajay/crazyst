"""E015 — volatility-scaled slot sizing at unchanged average exposure (pre-registered in
hypothesis.md, run AFTER that file was written, per BRD 12).

E014's finding carried forward: the index/200-DMA gate's whole-slice equity advantage
traced to exposure / variance drag, not timing — the baseline's arithmetic +0.164%/month
against a 6.29% monthly sd loses to a lower-variance path whatever the signal says. If
exposure is the mechanism, a SIGNAL-FREE sizing rule should buy back part of the relief.

Arms: A BASELINE (sizing hook absent — must reproduce E014's committed baseline exactly),
B EQUAL_RISK_MEAN1 (clip(median sigma / own sigma, 0.5, 2.0) normalized so the month's
pool mean scale is exactly 1.0 -> unchanged average exposure, risk-balanced entry
notionals), C DERISK_CAP (diagnostic: clip(..., 0.5, 1.0), no normalization -> the wild
names smaller, average exposure falls by construction).

Guards: G1a the hook is inert (12-month smoke escalate prefix bit-equal); G1b arm A equals
E014's committed arms.baseline exactly; G2 tape pins (arm-convention picks 5,605, mean
monthly IC == the repaired-tape pin smoke.SLICE_IC_PIN, re-baselined 2026-09-27 with the
adj_close repair); G3 sigma is point-in-time (every 40th (month, symbol)
pair of B's map recomputed from a fresh per-pair query); G4 B's mean invested share within
+/-2.00pp of A's; G5 per-month pool mean scale == 1.0 (B) and every C scale <= 1.0.

python -m experiments.015_exposure_sizing.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import date, timedelta

import duckdb

from src.backtest import smoke_e2e as smoke
from src.config import load

E013 = importlib.import_module("experiments.013_index_dma_regime.run")     # metric extractors
E014 = importlib.import_module("experiments.014_dma_regime_slice.run")    # _signal (benchmark)
HARNESS = importlib.import_module("src.walkforward.harness")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

VOL_SESSIONS = 60                 # trailing returns for sigma (hypothesis.md, frozen)
VOL_MIN = 40                      # below this a name carries no view (scale 1.0)
CLIP_B = (0.5, 2.0)               # arm B's clip
CLIP_C = (0.5, 1.0)               # arm C's clip
POOL_PCT = 0.15                   # == portfolio monthly_review_replace_above_top_pct
PICKS_PIN = 5605                  # E014's arm-convention pick total (same tape)
DD_GAIN_FRAC = 1.0 / 3.0          # B1: capture >= R/3
CAGR_TOL = 0.01                   # B1: CAGR >= A - 1.00pp
EXPOSURE_TOL_PP = 2.0             # G4
EPISODES = E014.EPISODES          # the same six pre-named windows (frozen)
SMOKE_RESULTS = os.path.join("runs", "smoke_e2e", "smoke_results.json")
E012_RESULTS = os.path.join("experiments", "012_floor_at_8slots", "results.json")
E014_RESULTS = os.path.join("experiments", "014_dma_regime_slice", "results.json")

_SIGMA_SQL = """
WITH adj AS (
    SELECT symbol, date,
           ln(adj_close) - ln(lag(adj_close) OVER (PARTITION BY symbol ORDER BY date)) AS r
    FROM adj_close
    WHERE date >= $floor::DATE AND adj_close IS NOT NULL AND isfinite(adj_close) AND adj_close > 0
), w AS (
    SELECT symbol, date, r,
           count(r) OVER (PARTITION BY symbol ORDER BY date
                          ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n,
           stddev_samp(r) OVER (PARTITION BY symbol ORDER BY date
                                ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS sd
    FROM adj
)
SELECT strftime(date, '%Y-%m-%d') AS d, symbol, sd, n
FROM w WHERE date IN (SELECT unnest(CAST($ds AS DATE[])))
"""


def _sigma(con, folds: list[str]) -> dict[str, dict[str, tuple[float, int]]]:
    """Trailing 60-session vol of adj-close log returns at every fold date: window-function
    frame ending at the fold date, so only sessions <= M enter (no look-ahead). Returns
    {month: {symbol: (sd, n_returns)}}."""
    floor = str(date.fromisoformat(folds[0]) - timedelta(days=180))
    rows = con.execute(_SIGMA_SQL, {"ds": folds, "floor": floor}).fetchall()
    out: dict[str, dict[str, tuple[float, int]]] = {}
    for d, sym, sd, n in rows:
        out.setdefault(str(d), {})[sym] = (sd, int(n))
    return out


def _pools(by_month: dict, folds: list[str]) -> dict[str, set[str]]:
    """The month's replace-eligible pool, built EXACTLY as smoke._engine_pass builds
    eligible/rank_pct (same rows, same rank column, same tie-ordered sort)."""
    rank_at = 2 + len(smoke.model.PANEL_FEATURES)
    sym_at = 2 + len(smoke.model.PANEL_FEATURES) + 1
    pools: dict[str, set[str]] = {}
    for m in folds:
        rs = by_month[m]
        scores = smoke.model.score_month_2f(rs)
        eligible = {rs[i][sym_at] for i, s in enumerate(scores) if s is not None}
        rank_pct = {sym: i / max(len(eligible) - 1, 1) for i, sym in enumerate(sorted(
            eligible, key=lambda s: next(r[rank_at] for r in rs if r[sym_at] == s)))}
        pools[m] = {s for s in eligible if rank_pct.get(s) is not None and rank_pct[s] <= POOL_PCT}
    return pools


def _scales(pools: dict[str, set[str]], sig: dict, mode: str) -> tuple[dict, list]:
    """Per-month scale maps. mode 'mean1' (arm B): clip(sigma_med/sigma) normalized over the
    pool's sigma-bearing members so the POOL mean scale is exactly 1.0 (no-view names carry
    1.0, which leaves the mean at 1.0) — 'unchanged average exposure'. mode 'cap' (arm C):
    clip(sigma_med/sigma, 0.5, 1.0), no normalization. Returns (map, per-month diagnostics
    with the median and normalizer G3 needs to re-derive a scale from a fresh sigma)."""
    lo, hi = CLIP_B if mode == "mean1" else CLIP_C
    scale, diags = {}, []
    for m, pool in pools.items():
        sd_of = sig.get(m, {})
        view = {s: sd_of[s][0] for s in pool
                if s in sd_of and sd_of[s][1] >= VOL_MIN and sd_of[s][0] and sd_of[s][0] > 0}
        if not view:
            diags.append({"month": m, "pool": len(pool), "with_sigma": 0,
                          "no_sigma": len(pool), "sigma_med": None, "k": None,
                          "pool_mean_scale": 1.0, "min": None, "max": None})
            continue
        med = statistics.median(view.values())
        raw = {s: min(max(med / v, lo), hi) for s, v in view.items()}
        k = (sum(raw.values()) / len(raw)) if mode == "mean1" else 1.0
        norm = {s: v / k for s, v in raw.items()}
        scale[m] = norm
        diags.append({"month": m, "pool": len(pool), "with_sigma": len(view),
                      "no_sigma": len(pool) - len(view), "sigma_med": med, "k": k,
                      "pool_mean_scale": (sum(norm.values()) + len(pool) - len(view)) / len(pool),
                      "min": min(norm.values()), "max": max(norm.values())})
    return scale, diags


def _invested(curve: list[dict]) -> float:
    """Mean invested share over the fold months (market_value / equity)."""
    return sum(r["market_value"] / r["equity"] for r in curve) / len(curve)


def _episode_dd(curve: list[dict], folds: list[str], a: str, b: str) -> float:
    """Within-episode drawdown severity (positive pp) on the arm's own curve, rebased at
    the episode's first fold. maxDD convention: metrics.max_drawdown returns a negative
    fraction; severity = -mdd."""
    eq = [curve[j]["equity"] for j, m in enumerate(folds) if a <= m[:7] <= b]
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    return -mdd


def _moments(curve: list[dict]) -> dict:
    """Monthly arithmetic mean/sd and the geometric path (E014's variance-drag read)."""
    r = [curve[i + 1]["equity"] / curve[i]["equity"] - 1.0 for i in range(len(curve) - 1)]
    mean = sum(r) / len(r)
    sd = math.sqrt(sum((x - mean) ** 2 for x in r) / (len(r) - 1))
    geo = math.exp(sum(math.log1p(x) for x in r) / len(r)) - 1.0
    return {"n": len(r), "arith_mean": mean, "sd": sd, "geometric_mean": geo}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    e012 = json.load(open(E012_RESULTS, encoding="utf-8"))
    e014 = json.load(open(E014_RESULTS, encoding="utf-8"))
    # single source of truth for the IC pin: the smoke's re-baselined constant (LEDGER
    # 2026-09-27 "adj_close pipeline repair"). E012's frozen results.json still holds the
    # pre-repair 0.375-arm IC and must keep holding it — the smoke asserts that.
    ic_pin = smoke.SLICE_IC_PIN
    smoke_ep = json.load(open(SMOKE_RESULTS, encoding="utf-8"))["engine_passes"]["escalate"]
    dump = lambda x: json.dumps(x, default=str, sort_keys=True)          # noqa: E731
    assert smoke._cfg_test()["portfolio"]["monthly_review_replace_above_top_pct"] == POOL_PCT

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
        assert str(cutoff) == e014["window"]["cutoff"], (str(cutoff), e014["window"]["cutoff"])
        by_month_all: dict[str, list] = {}
        for r in rows:
            by_month_all.setdefault(str(r[0]), []).append(r)
        picks_by_month = {m: smoke._picks(by_month_all[m]) for m in folds}
        val_bucket_rows = [r for m in folds for r in by_month_all[m]]
        sig500, _ = E014._signal(con, folds, "NIFTY 500")     # reporting-only benchmark
        close_idx = HARNESS._month_end_closes(con, folds)
        sig = _sigma(con, folds)
        pools = _pools(by_month_all, folds)
    finally:
        con.close()
    base500 = sig500[folds[0]]["tri"]
    bench_eq = [{"date": m, "equity": sig500[m]["tri"] / base500} for m in folds]

    # ---- guards --------------------------------------------------------------------------
    # A) the sizing hook must be INERT: the 12-month smoke pass (its own convention:
    #    labeled-only tape, warm=0) reproduces the committed escalate arm bit-for-bit.
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
    mean_ic = smoke._mean_monthly_ic(by_month_lbl)
    assert abs(mean_ic - ic_pin) < 1e-9, (mean_ic, ic_pin)
    gate = cfg["backtest"]["exit_gate"]
    assert gate.get("mode", "escalate") == "escalate", gate
    picks_lbl = {m: smoke._picks(by_month_lbl[m]) for m in folds}
    res_smoke = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                                   by_month_lbl, folds, picks_lbl, val_lbl,
                                   engine_months_limit=len(smoke_ep["months"]))
    n12 = len(smoke_ep["months"])
    assert dump(res_smoke["curve"][:n12]) == dump(smoke_ep["curve"]), "smoke curve prefix"
    assert dump(res_smoke["fill_log"]) == dump(smoke_ep["fill_log"]), "smoke fill_log"
    assert dump(res_smoke["decisions"]) == dump(smoke_ep["decisions"]), "smoke decisions"
    assert dump(res_smoke["month_rows"][:n12]) == dump(smoke_ep["month_rows"]), "smoke months"
    # B) tape pins for the ARM convention (harness's: all eligible decision rows)
    all_picks = [p for m in folds for p in picks_by_month[m]]
    assert len(all_picks) >= PICKS_PIN, (len(all_picks), PICKS_PIN)

    # ---- arms ---------------------------------------------------------------------------
    scale_b, diag_b = _scales(pools, sig, "mean1")
    scale_c, diag_c = _scales(pools, sig, "cap")
    kw = dict(market_warm=HARNESS.WARM_SESSIONS, engine_months_limit=len(folds))
    res_a = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                               by_month_all, folds, picks_by_month, val_bucket_rows, **kw)
    res_b = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                               by_month_all, folds, picks_by_month, val_bucket_rows,
                               size_scale=scale_b, **kw)
    res_c = smoke._engine_pass(cfg, gate["mode"], gate.get("escalate_after", 2), sessions,
                               by_month_all, folds, picks_by_month, val_bucket_rows,
                               size_scale=scale_c, **kw)
    ev_a = HARNESS._evaluate_pass(res_a, folds, bench_eq, close_idx)
    ev_b = HARNESS._evaluate_pass(res_b, folds, bench_eq, close_idx)
    ev_c = HARNESS._evaluate_pass(res_c, folds, bench_eq, close_idx)
    m_a, m_b, m_c = (E013._arm_metrics(ev_a, res_a), E013._arm_metrics(ev_b, res_b),
                     E013._arm_metrics(ev_c, res_c))
    assert dump(m_a) == dump(e014["arms"]["baseline"]), "arm A != E014's committed baseline"

    # ---- G3: sigma is point-in-time (fresh per-pair query path) ---------------------------
    pairs = sorted((m, s) for m, mp in scale_b.items() for s in mp)
    sample = pairs[::40]
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        worst = 0.0
        for m, s in sample:
            cl = [r[0] for r in con.execute(
                "SELECT adj_close FROM adj_close WHERE symbol = ? AND date <= ?::DATE "
                "AND adj_close IS NOT NULL AND isfinite(adj_close) AND adj_close > 0 "
                "ORDER BY date DESC LIMIT ?", [s, m, VOL_SESSIONS + 1]).fetchall()]
            cl.reverse()
            rets = [math.log(cl[i + 1]) - math.log(cl[i]) for i in range(len(cl) - 1)]
            sd, n = sig[m][s]
            assert n == len(rets) and len(rets) >= VOL_MIN, (m, s, n, len(rets))
            worst = max(worst, abs(statistics.stdev(rets) - sd))
        assert worst < 1e-12, worst
    finally:
        con.close()
    # G5: the normalization contract, on the stored diagnostics
    for d in diag_b:
        if d["sigma_med"] is not None:
            assert abs(d["pool_mean_scale"] - 1.0) < 1e-12, d
    assert all(v <= 1.0 for mp in scale_c.values() for v in mp.values()), "C scale > 1"

    # ---- the pre-registered bars ----------------------------------------------------------
    relief = abs(e014["arms"]["baseline"]["max_drawdown"]
                 - e014["arms"]["buy_block"]["max_drawdown"])
    sev = lambda m: -m["max_drawdown"]                                  # noqa: E731
    gain_b, gain_c = sev(m_a) - sev(m_b), sev(m_a) - sev(m_c)
    b1 = gain_b >= relief * DD_GAIN_FRAC and m_b["cagr"] >= m_a["cagr"] - CAGR_TOL
    ep_rows = []
    for name, a, b in EPISODES:
        dd_a, dd_b = _episode_dd(ev_a["equity_curve"], folds, a, b), \
            _episode_dd(ev_b["equity_curve"], folds, a, b)
        ep_rows.append({"episode": name, "from": a, "to": b,
                        "baseline_dd": dd_a, "mean1_dd": dd_b, "better": dd_b < dd_a})
    n_better = sum(1 for e in ep_rows if e["better"])
    b2 = n_better >= 3
    inv_a, inv_b, inv_c = (_invested(ev_a["equity_curve"]), _invested(ev_b["equity_curve"]),
                           _invested(ev_c["equity_curve"]))
    g4 = abs((inv_b - inv_a) * 100) <= EXPOSURE_TOL_PP
    verdict = ("CONFOUNDED" if not g4 else "PASS" if (b1 and b2) else "FAIL")
    bought_scale = lambda res, sc: (sum(sc.get(d["month"], {}).get(d["symbol"], 1.0)          # noqa: E731
                                       for d in res["decisions"] if d["action"] == "buy")
                                    / max(1, sum(1 for d in res["decisions"]
                                                 if d["action"] == "buy")))

    out = {
        "experiment": "E015_exposure_sizing", "git_hash": git, "profile": args.profile,
        "question": "does volatility-scaled (equal-risk) slot sizing at unchanged average "
                    "exposure capture the drawdown relief the regime filter stumbled into?",
        "window": {"cutoff": str(cutoff), "boundary": str(boundary),
                   "first_month": folds[0], "last_month": folds[-1], "n_folds": len(folds),
                   "test_window_untouched": True},
        "sigma": {"definition": "trailing 60 sessions of daily log returns of adj_close, "
                                "window frame ending at the fold's decision date; >= 40 "
                                "returns required else no view (scale 1.0)",
                  "vol_sessions": VOL_SESSIONS, "vol_min": VOL_MIN,
                  "clip_mean1": list(CLIP_B), "clip_cap": list(CLIP_C),
                  "pool_pct": POOL_PCT,
                  "pool_definition": "eligible & rank_pct <= replace_above_top_pct (held not "
                                     "excluded; the engine buys from the pool minus its book)",
                  "sanity_sampled_pairs": len(sample), "sanity_max_abs_sigma_diff": worst},
        "benchmark": {"construction": "Nifty 500 TRI sampled at each fold's own index print, "
                                      "rebased at folds[0]; reporting only",
                      "final_tri": sig500[folds[-1]]["tri"]},
        "guards": {"G1a_smoke_escalate_prefix_12mo_bit_equal": True,
                   "G1a_convention": "labeled-only rows + warm=0 (the smoke's own inputs)",
                   "G1b_baseline_equals_e014": True,
                   "arms_warm": HARNESS.WARM_SESSIONS,
                   "G2_picks_total": len(all_picks), "G2_picks_pin": PICKS_PIN,
                   "G2_eligible_rows_pin": elig_pin,
                   "G2_mean_monthly_ic": mean_ic, "G2_ic_pin": ic_pin,
                   "G2_ic_pin_source": "smoke.SLICE_IC_PIN (repaired tape, LEDGER 2026-09-27); "
                                       "E012's frozen arm IC 0.07171797803434904 is the "
                                       "pre-repair value and stays frozen",
                   "G3_sampled_sigma_pairs": len(sample),
                   "G3_max_abs_sigma_diff": worst,
                   "G4_invested_share_A": inv_a, "G4_invested_share_B": inv_b,
                   "G4_invested_share_C": inv_c,
                   "G4_diff_pp": (inv_b - inv_a) * 100, "G4_tolerance_pp": EXPOSURE_TOL_PP,
                   "G4_passed": g4, "G5_pool_mean_scale_is_1": True, "G5_cap_le_1": True,
                   "passed": True},
        "arms": {"baseline": m_a, "equal_risk_mean1": m_b, "derisk_cap": m_c,
                 "baseline_moments": _moments(ev_a["equity_curve"]),
                 "equal_risk_mean1_moments": _moments(ev_b["equity_curve"]),
                 "derisk_cap_moments": _moments(ev_c["equity_curve"]),
                 "mean_scale_applied_to_buys": {"equal_risk_mean1": bought_scale(res_b, scale_b),
                                                "derisk_cap": bought_scale(res_c, scale_c)}},
        "scale_diagnostics": {"equal_risk_mean1": diag_b, "derisk_cap": diag_c},
        "capture": {"relief_reference_r": relief,
                    "reference": "|maxDD_baseline - maxDD_buy_block| from E014's committed arms "
                                 "on this same slice",
                    "gain_pp": {"equal_risk_mean1": gain_b, "derisk_cap": gain_c},
                    "ratio": {"equal_risk_mean1": gain_b / relief, "derisk_cap": gain_c / relief},
                    "bar_pp": relief * DD_GAIN_FRAC},
        "episodes": ep_rows, "episodes_better": n_better,
        "decision": {"rule": "PASS iff B1 (DD gain >= R/3 AND CAGR >= A - 1.00pp) and B2 "
                             "(better DD in >= 3 of 6 episodes) and G4; CONFOUNDED if G4 "
                             "fails; FAIL otherwise",
                     "bars": {"B1": b1, "B2": b2}, "verdict": verdict,
                     "reading": "PASS = licence to spend fresh out-of-sample data (the test "
                                "window is untouched by the sizing family), never adoption; "
                                "no config change either way"},
        "disclosures": [
            "the 0.375 floor is derived at the equal-weight Rs125k notional (E012); under "
            "B/C the effective notional moves (0.5x-2x) so the fill gate binds differently "
            "per arm - the floor is NOT re-derived here and no refusal rate is comparable "
            "to the shipped 1.14%",
            "up-scaled buys can hit the cash constraint and be resized at fill (resized_buys "
            "reported per arm); G4 measures the net exposure effect",
            "weights drift after entry (the engine never rebalances): B equalizes the ENTRY "
            "notional's risk, not the held book's - volatility-scaled slot sizing, not risk "
            "parity",
            "no portfolio-vol-target arm at unchanged average exposure exists: the book is "
            "long-only and cash-constrained, so a de-risked stretch cannot be offset by a "
            "grossed-up one (hypothesis.md, 'Why there is no ...')",
        ],
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}"                                          # noqa: E731
    print(f"slice: {len(folds)} months {folds[0]} -> {folds[-1]} (boundary {boundary}, "
          f"cutoff {cutoff}); test window untouched")
    print(f"guards: hook inert (smoke 12-month escalate prefix bit-equal); arm A == E014 "
          f"baseline; picks {len(all_picks)} >= pin {PICKS_PIN}; IC {mean_ic:.10f} == "
          f"repaired-tape pin {ic_pin:.10f}; "
          f"sigma PIT {worst:.1e} over {len(sample)} sampled pairs; G4 exposure diff "
          f"{(inv_b - inv_a) * 100:+.2f}pp (tol +/-{EXPOSURE_TOL_PP}); pool mean scale 1.0")
    print(f"sigma views: months with no sigma-bearing pool "
          f"{sum(1 for d in diag_b if d['sigma_med'] is None)}/145; median pool "
          f"{statistics.median([d['pool'] for d in diag_b]):.0f} names")
    print("\narm                equity        ret      CAGR   Sharpe    maxDD   fills  "
          "picks  hit  churn/mo  invested  mean-scale")
    for name, m, s, mom in (("baseline", m_a, None, out["arms"]["baseline_moments"]),
                            ("EQUAL_RISK_MEAN1", m_b, bought_scale(res_b, scale_b),
                             out["arms"]["equal_risk_mean1_moments"]),
                            ("DERISK_CAP", m_c, bought_scale(res_c, scale_c),
                             out["arms"]["derisk_cap_moments"])):
        inv = {"baseline": inv_a, "EQUAL_RISK_MEAN1": inv_b, "DERISK_CAP": inv_c}[name]
        print(f"  {name:<16} {m['final_equity']:>10,.0f}  {pct(m['total_return']):>8}  "
              f"{pct(m['cagr']):>8}  {m['sharpe_monthly']:>7.3f}  {m['max_drawdown']:>7.2%}  "
              f"{m['fills']:>5} {m['completed_picks']:>5}  {m['pick_hit_rate']:>4.0%}  "
              f"{m['churn_per_month']:>6.2f}  {inv:>7.1%}  "
              f"{(f'{s:.3f}' if s else '  1.000')}")
    print(f"  variance: arith mean/sd = A {out['arms']['baseline_moments']['arith_mean']:+.3%}/"
          f"{out['arms']['baseline_moments']['sd']:.2%}, B "
          f"{out['arms']['equal_risk_mean1_moments']['arith_mean']:+.3%}/"
          f"{out['arms']['equal_risk_mean1_moments']['sd']:.2%}, C "
          f"{out['arms']['derisk_cap_moments']['arith_mean']:+.3%}/"
          f"{out['arms']['derisk_cap_moments']['sd']:.2%}")
    print(f"capture: R {relief:.2%}; B gain {gain_b:+.2%} ({gain_b / relief:.0%} of R, bar "
          f"{relief * DD_GAIN_FRAC:.2%}); C gain {gain_c:+.2%} ({gain_c / relief:.0%})")
    print("episode            base_dd   B_dd    better")
    for e in ep_rows:
        print(f"  {e['episode']:<16} {e['baseline_dd']:>7.2%}  {e['mean1_dd']:>6.2%}  "
              f"{'yes' if e['better'] else 'no'}")
    print(f"DECISION: {verdict}   (B1 {b1}, B2 {b2}: {n_better}/6 episodes better; G4 "
          f"{'pass' if g4 else 'FAIL'}); non_fills A/B/C {m_a['non_fills']}/"
          f"{m_b['non_fills']}/{m_c['non_fills']}, resized A/B/C {m_a['resized_buys']}/"
          f"{m_b['resized_buys']}/{m_c['resized_buys']}")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
