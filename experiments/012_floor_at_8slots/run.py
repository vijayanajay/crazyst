"""E012 - the E009 floor at the 8-slot notional (pre-registered in hypothesis.md; run AFTER
that file was written, per BRD 12). E009's machinery, imported module-to-module so nothing
drifts; the only new code is the arm loop and the decision-rule evaluation.

Arms: baseline floor 0.0 (zero-drift guard vs E009's committed R1_by_slot at all four slot
sizes + the restore IC guard vs P4.1b's frozen IC), then 0.375 / 0.5 / 0.75 through the
REAL pipeline (chain rebuilt per arm). The 0.75 arm's S250k row must equal E009's committed
R2. Decision rule: the LOOSEST moving candidate (0.375, 0.5) clearing all four bars wins;
ties and failures keep the shipped 0.75 (hypothesis.md has the bars verbatim).

python -m experiments.012_floor_at_8slots.run --profile full
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load

import importlib
E009 = importlib.import_module("experiments.009_fill_gate_reach.run")   # machinery + guards
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
P41 = importlib.import_module("experiments.004_composite_v0.run")
from src.backtest import smoke_e2e as smoke
from src.model import composite as model

FLOORS = (0.375, 0.5, 0.75)          # 0.75 last: the shipped reference doubles as a guard
SLOTS_8 = 125_000.0                  # the 8-slot per-slot notional (E011 ADOPT)
SLOT_BARS = (125_000.0, 250_000.0, 500_000.0, 1_000_000.0)   # E009's R1 grid, for the guard
TOL_CORRECTED = 0.0005               # bar 1: 5bp/month (hypothesis.md)
IC_T_BAR = -2.0                      # bar 2: E009 verbatim
REFUSAL_FRAC = 3.0                   # bar 3: E009 verbatim (refusal <= baseline / 3)
BOUNDARY_8 = 20.0 * SLOTS_8 / 1e7    # bar 4: 0.25cr


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                          ).stdout.strip()


def _arm(con, cfg, floor_cr: float, med20: dict, sym_at: int) -> dict:
    """One floor arm through the real pipeline: chain rebuilt, picks, reachability at the
    8-slot notional (plus S250k for the 0.75 guard), ICs, paired t vs the baseline arm."""
    cfg["universe"]["min_median_turnover_cr"] = floor_cr
    E007._build_chain(con, cfg)
    rows, cutoff = smoke._fetch(con)
    val, _, _ = P41.split_slice(rows, cutoff)
    by_month: dict[str, list] = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    picks = E009._pick_set(rows, sym_at)                     # ALL labeled months, E009 semantics
    reach = E009._reachability(picks, med20, SLOTS_8)
    reach_250k = (E009._reachability(picks, med20, 250_000.0)
                  if floor_cr == 0.75 else None)
    ic = E009._mean_monthly_ic(by_month, sym_at)
    ics = E009._ic_triples(by_month, sym_at)
    elig = con.execute("SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]
    excl = con.execute(
        "SELECT count(*) FROM eligible WHERE eligible = FALSE "
        "AND reasons LIKE '%turnover<%'").fetchone()[0]
    # per-arm modelled impact at the 8-slot notional over the arm's picks (E010's formula)
    imp_rows = []
    for m, lst in picks.items():
        for _, sym, _ in lst:
            m20 = med20.get((sym, m))
            if m20 is not None:
                imp_rows.append(min(0.01, 0.10 * SLOTS_8 / m20))
    return {"floor_cr": floor_cr, "eligibles": elig, "excluded_turnover": excl,
            "reach_S125k": reach,
            "reach_S250k_guard": reach_250k, "ic_val_slice": ic, "ic_triples": ics,
            "mean_modelled_impact_S125k": sum(imp_rows) / len(imp_rows) if imp_rows else None,
            "cutoff": str(cutoff)}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    shipped_floor = cfg["universe"]["min_median_turnover_cr"]
    # pre-ADOPT the shipped floor was 0.75 (this experiment's own verdict moved it to 0.375);
    # the arms pass their floors EXPLICITLY, so the run stays re-runnable and
    # bit-reproducible after the config change (the E009/E011 pattern)
    assert shipped_floor in (0.75, 0.375), \
        f"this experiment's guards are written against the 0.75/0.375 floors, got {shipped_floor}"
    with open(os.path.join(os.path.dirname(__file__), "..", "009_fill_gate_reach",
                           "results.json"), encoding="utf-8") as f:
        e009 = json.load(f)
    p41b = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                       "004b_composite_2feat", "results.json"),
                          encoding="utf-8"))
    frozen_ic = p41b["mean_monthly_ic"]["composite_2f"]["ic"]

    con = duckdb.connect(cfg["paths"].get("duckdb"))
    try:
        # ---- baseline arm (floor 0.0): the zero-drift guard against E009's R1 -----------
        cfg["universe"]["min_median_turnover_cr"] = 0.0
        E007._build_chain(con, cfg)
        E009._build_liq20(con, cfg)                       # chain-independent; built once
        frozen = E009._frozen_sample_check(con, os.path.join(
            os.path.dirname(__file__), "..", "009_fill_gate_reach"))
        member = E009._member_recompute_check(con, cfg)
        rows, cutoff = smoke._fetch(con)
        sym_at = 2 + len(model.PANEL_FEATURES) + 1
        picks = E009._pick_set(rows, sym_at)
        med20 = {(s, str(m)): m20 for s, m, m20 in con.execute(
            "SELECT symbol, mdate, med20 FROM liq_daily20").fetchall()}
        r1 = {f"S{int(s // 1000)}k": E009._reachability(picks, med20, s) for s in SLOT_BARS}
        drift = {k: (e009["R1_by_slot"][k], v) for k, v in r1.items()
                 if e009["R1_by_slot"][k] != v}
        assert not drift, f"baseline does not reproduce E009's R1_by_slot: {list(drift)}"
        elig_baseline = con.execute("SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]
        assert elig_baseline == e009["R2"]["eligibles_baseline"], (elig_baseline,)
        val_rows, _, _ = P41.split_slice(rows, cutoff)
        base_by_month: dict[str, list] = {}
        for r in val_rows:
            base_by_month.setdefault(str(r[0]), []).append(r)
        base_ics = E009._ic_triples(base_by_month, sym_at)
        base_ic = E009._mean_monthly_ic(base_by_month, sym_at)

        # ---- the moving candidates + the shipped reference ------------------------------
        arms = {}
        for floor_cr in FLOORS:
            arms[str(floor_cr)] = _arm(con, cfg, floor_cr, med20, sym_at)
            a = arms[str(floor_cr)]
            print(f"[floor {floor_cr}] eligible {a['eligibles']:,} (excl {a['excluded_turnover']:,}) "
                  f"S125k refused {a['reach_S125k']['refused_pct']:.2%} "
                  f"corrected {a['reach_S125k']['corrected_mean']:+.3%} "
                  f"IC {a['ic_val_slice']:.6f}")
    finally:
        cfg["universe"]["min_median_turnover_cr"] = shipped_floor   # never leak an arm floor

    # ---- guards on the 0.75 arm (computed after restore; the data was already read) ----
    a75 = arms["0.75"]
    r2_keys = set(a75["reach_S250k_guard"])
    assert a75["reach_S250k_guard"] == {k: v for k, v in e009["R2"].items() if k in r2_keys}, \
        "the 0.75 arm's S250k row does not reproduce E009's committed R2"
    assert abs(a75["ic_val_slice"] - e009["R2"]["ic_floor"]) < 1e-9, \
        (a75["ic_val_slice"], e009["R2"]["ic_floor"])

    # ---- decision rule (hypothesis.md, evaluated mechanically) --------------------------
    def passes(a: dict) -> dict:
        r, r75 = a["reach_S125k"], a75["reach_S125k"]
        t = P41._paired_t(a["ic_triples"], base_ics)
        return {"corrected_mean_holds":
                r["corrected_mean"] >= r75["corrected_mean"] - TOL_CORRECTED,
                "ic_holds": t is not None and t["t"] >= IC_T_BAR,
                "gate_fixed": r["refused_pct"] <= r1["S125k"]["refused_pct"] / REFUSAL_FRAC,
                "boundary_covered": a["floor_cr"] >= BOUNDARY_8,
                "paired_t": t}

    evals = {k: passes(a) for k, a in arms.items() if k != "0.75"}
    # loosest = SMALLEST floor (a higher minimum excludes more names): candidates ordered
    # loosest-first, the first that clears all bars wins
    adopting = [k for k in ("0.375", "0.5") if k in evals and all(
        v for kk, v in evals[k].items() if kk != "paired_t")]
    adopt = adopting[0] if adopting else None
    decision = {"adopt_floor_cr": float(adopt) if adopt else 0.75,
                "loosest_passing": adopt, "bars": {"tol_corrected": TOL_CORRECTED,
                                                   "ic_t_bar": IC_T_BAR,
                                                   "refusal_frac": REFUSAL_FRAC,
                                                   "boundary_cr": BOUNDARY_8},
                "evaluations": evals}
    out = {"experiment": "E012_floor_at_8slots", "git_hash": _git(), "profile": args.profile,
           "cutoff": str(cutoff), "slot_8_rupees": SLOTS_8, "boundary_8_cr": BOUNDARY_8,
           "baseline_guard": {"e009_R1_bit_equal": True, "eligibles": elig_baseline,
                              "ic_val_slice": base_ic, "frozen_ic": frozen_ic,
                              "frozen_sample": frozen, "member_recompute": member},
           "arms": arms, "decision": decision,
           "runtime_seconds": round(time.monotonic() - t0, 1)}
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"\nbaseline (floor 0.0): R1 rows bit-equal to E009's committed table; "
          f"IC {base_ic:.6f} (frozen {frozen_ic:.6f}); {frozen['status']}; member recompute "
          f"{member['rows_checked']:,} rows")
    for k in ("0.75", "0.5", "0.375"):
        a, e = arms[k], evals.get(k)
        line = (f"[{k}] corrected(S125k) {a['reach_S125k']['corrected_mean']:+.3%} vs 0.75's "
                f"{a75['reach_S125k']['corrected_mean']:+.3%}; refusal "
                f"{a['reach_S125k']['refused_pct']:.2%} vs baseline-at-S125k "
                f"{r1['S125k']['refused_pct']:.2%}; impact "
                f"{a['mean_modelled_impact_S125k']:.4%}")
        if e:
            line += f" -> {'PASSES' if all(v for kk, v in e.items() if kk != 'paired_t') else 'fails'}"
        print(line)
    print(f"DECISION: {'ADOPT ' + str(decision['adopt_floor_cr']) if adopt else 'KEEP 0.75'}")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
