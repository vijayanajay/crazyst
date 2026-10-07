"""E027 - the floor-1.5cr rung at 8xRs500k economics (pre-registered hypothesis.md; run
AFTER that file was written, per BRD 12). E009/E012's machinery, imported
module-to-module so nothing drifts; the only new code is the arm set, the current-tape
anchors (E026-certified this session), and the decision-rule evaluation.

Arms (each a real E007._build_chain rebuild, floors passed EXPLICITLY): B 0.375 (the
shipped floor, on-tape reference), C 0.75 (E009 R2 continuity), A 1.5 (the candidate
rung for the Rs40L account: boundary 1.0cr, floor rule 1.5x), O 3.0 (diagnostic
overshoot). Anchors replace E012's bit-equality guards with cause (the tape moved:
cutoff 2026-09-24 -> 2026-10-01, labels revised - E026's disclosed re-baseline): arm B
must reproduce THIS session's certified pins (picks 4,579 / 5,605 and
smoke.SLICE_IC_PIN on the exact 145-fold subset). Restore step returns the chain to
the shipped 0.375 state and re-asserts the pin.

python -m experiments.027_floor_1_5cr_rung.run --profile full
python -m experiments.027_floor_1_5cr_rung.run --self-check
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

from src.config import load

E009 = importlib.import_module("experiments.009_fill_gate_reach.run")   # machinery + guards
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
P41 = importlib.import_module("experiments.004_composite_v0.run")
E018 = importlib.import_module("experiments.018_breadth_portfolio.run")
HARNESS = importlib.import_module("src.walkforward.harness")
from src.backtest import smoke_e2e as smoke
from src.model import composite as model

ARMS = (("B", 0.375), ("C", 0.75), ("A", 1.5), ("O", 3.0))   # freeze order B, C, A, O
S = 500_000.0                                                # the Rs40L slot
SLOT_BARS = (125_000.0, 250_000.0, 500_000.0, 1_000_000.0)   # E009's R1 grid
TOL_CORRECTED = 0.0005                                       # T1: 5bp/month (E012 verbatim)
IC_T_BAR = -2.0                                              # T2 (E009/E012 verbatim)
REFUSAL_FRAC = 3.0                                           # T3 (E009 verbatim)
SUB145_LAST = "2023-07-31"                                   # E018/E026's pinned slice end


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                          ).stdout.strip()


# ---- the pre-registered decision rule, as pure functions so the self-check can pin it ----
def _bars(aS: dict, bS: dict, t) -> dict:
    """hypothesis.md's T1-T4 verbatim: A (floor 1.5cr) must hold the shipped B (0.375cr)."""
    return {"T1_corrected_holds": aS["corrected_mean"] >= bS["corrected_mean"] - TOL_CORRECTED,
            "T2_ic_holds": t is not None and t["t"] >= IC_T_BAR,
            "T3_gate_fixed": aS["refused_pct"] <= bS["refused_pct"] / REFUSAL_FRAC,
            "T4_recorded_refusal_le_5pct": aS["refused_pct"] <= 0.05,
            "paired_t": t}


def _adopt(bars: dict, a_elig: int, b_elig: int, anchors_ok: bool):
    """ADOPT = T1 and T2 and T3 (the bars) plus the G1 coverage floor and the anchors."""
    g1 = a_elig >= 0.60 * b_elig
    return (bool(bars["T1_corrected_holds"] and bars["T2_ic_holds"]
                 and bars["T3_gate_fixed"] and g1 and anchors_ok), bool(g1))


def _self_check() -> int:
    B = {"corrected_mean": 0.0200, "refused_pct": 0.20}
    # T1 is "A >= B - 5bp": equality holds, one basis point below does not
    assert _bars({"corrected_mean": 0.0200 - TOL_CORRECTED, "refused_pct": 0.05},
                 B, {"t": 0.0})["T1_corrected_holds"]
    assert not _bars({"corrected_mean": 0.0200 - TOL_CORRECTED - 1e-9, "refused_pct": 0.05},
                     B, {"t": 0.0})["T1_corrected_holds"]
    # T2 is "paired t >= -2": equality holds, below does not; a missing t is not a pass
    assert _bars(B, B, {"t": IC_T_BAR})["T2_ic_holds"]
    assert not _bars(B, B, {"t": IC_T_BAR - 1e-6})["T2_ic_holds"]
    assert not _bars(B, B, None)["T2_ic_holds"]
    # T3 is "A refusal <= B/3": exactly a third holds, a hair over does not
    assert _bars({"corrected_mean": 0.02, "refused_pct": 0.20 / REFUSAL_FRAC},
                 B, {"t": 0.0})["T3_gate_fixed"]
    assert not _bars({"corrected_mean": 0.02, "refused_pct": 0.20 / REFUSAL_FRAC + 1e-9},
                     B, {"t": 0.0})["T3_gate_fixed"]
    # T4 is recorded, never gating: 6% refusal is recorded False and still ADOPTs
    GOOD = {"corrected_mean": 0.02, "refused_pct": 0.05}               # T1-T3 all hold
    b4 = _bars({"corrected_mean": 0.02, "refused_pct": 0.06}, B, {"t": 0.0})
    assert b4["T4_recorded_refusal_le_5pct"] is False
    assert _adopt(b4, 100, 100, True)[0]
    # T3 does gate, though: 8% refusal is over a third of B's 20% and vetoes ADOPT
    assert not _adopt(_bars({"corrected_mean": 0.02, "refused_pct": 0.08},
                            B, {"t": 0.0}), 100, 100, True)[0]
    # G1 is a 60% coverage floor, and a failed anchor vetoes the adoption outright
    bars_good = _bars(GOOD, B, {"t": 0.0})
    assert _adopt(bars_good, 60, 100, True)[0]
    assert not _adopt(bars_good, 59, 100, True)[0]
    assert not _adopt(bars_good, 100, 100, False)[0]
    assert not _adopt(_bars({"corrected_mean": 0.0194, "refused_pct": 0.05},
                            B, {"t": 0.0}), 100, 100, True)[0]      # T1 alone vetoes
    print("PASS: 027 self-check (T1/T2/T3 boundary inclusivity, T4 recorded-not-gating, "
          "G1 floor, anchor veto)", flush=True)
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check:
        return _self_check()
    t0 = time.monotonic()
    cfg = load(args.profile)
    shipped_floor = cfg["universe"]["min_median_turnover_cr"]
    assert shipped_floor == 0.375, \
        f"E027's restore guard is written against the shipped 0.375 floor, got {shipped_floor}"

    con = duckdb.connect(cfg["paths"]["duckdb"])
    sym_at = 2 + len(model.PANEL_FEATURES) + 1
    arms = {}
    raw_picks: dict[str, dict] = {}      # kept out of results.json; G2 recounts from it
    try:
        med20 = None
        for label, floor_cr in ARMS:
            cfg["universe"]["min_median_turnover_cr"] = floor_cr
            E007._build_chain(con, cfg)
            if med20 is None:                       # chain-independent; built once (E012)
                E009._build_liq20(con, cfg)
                med20 = {(s, str(m)): m20 for s, m, m20 in con.execute(
                    "SELECT symbol, mdate, med20 FROM liq_daily20").fetchall()}
            rows, cutoff = smoke._fetch(con)
            val, _, boundary = P41.split_slice(rows, cutoff)
            by_month: dict[str, list] = {}
            for r in val:
                by_month.setdefault(str(r[0]), []).append(r)
            picks = E009._pick_set(rows, sym_at)     # ALL labeled months, E009 semantics
            raw_picks[label] = picks
            reach = {f"S{int(s // 1000)}k": E009._reachability(picks, med20, s)
                     for s in SLOT_BARS}
            ic146 = smoke._mean_monthly_ic({m: by_month[m] for m in by_month})
            sub145 = sorted(m for m in by_month if m <= SUB145_LAST)
            ic145 = smoke._mean_monthly_ic({m: by_month[m] for m in sub145})
            imp = [min(0.01, 0.10 * S / med20[(sym, m)]) for m, lst in picks.items()
                   for _, sym, _ in lst if med20.get((sym, m)) is not None]
            arms[label] = {"floor_cr": floor_cr, "cutoff": str(cutoff),
                           "boundary": str(boundary), "n_val_folds": len(by_month),
                           "eligibles": con.execute(
                               "SELECT count(*) FROM eligible WHERE eligible").fetchone()[0],
                           "excluded_turnover": con.execute(
                               "SELECT count(*) FROM eligible WHERE eligible = FALSE "
                               "AND reasons LIKE '%turnover<%'").fetchone()[0],
                           "reach": reach, "ic_val_146": ic146, "ic_145": ic145,
                           "ic_triples": E009._ic_triples(by_month, sym_at),
                           "mean_modelled_impact_S500k":
                               sum(imp) / len(imp) if imp else None}
            print(f"[{label} floor {floor_cr}] eligibles {arms[label]['eligibles']:,} "
                  f"(excl {arms[label]['excluded_turnover']:,}) S500k refused "
                  f"{reach['S500k']['refused_pct']:.2%} corrected "
                  f"{reach['S500k']['corrected_mean']:+.3%} IC145 {ic145:.6f}")

        # ---- anchors (G0, arm B; the E026-certified pins of this session) --------------
        cfg["universe"]["min_median_turnover_cr"] = shipped_floor
        E007._build_chain(con, cfg)                  # restore FIRST: anchors need 0.375 rows
        rows, cutoff = smoke._fetch(con)
        val, _, _ = P41.split_slice(rows, cutoff)
        by_month = {}
        for r in val:
            by_month.setdefault(str(r[0]), []).append(r)
        # the ARM convention is select-then-label, so its cross-section carries the UNLABELED
        # decision rows too (E014's definition): smoke._fetch filters next_month_ret NOT NULL
        # and would collapse the arm pin onto the labeled-only count.
        by_month_all = {}
        for r in HARNESS._fetch(con)[0]:
            by_month_all.setdefault(str(r[0]), []).append(r)
        sub145 = sorted(m for m in by_month if m <= SUB145_LAST)
        picks5 = sum(len(E018._picks_smoke(by_month[m])) for m in sub145)
        picks_arm = sum(len(smoke._picks(by_month_all[m])) for m in sub145)
        ic145 = smoke._mean_monthly_ic({m: by_month[m] for m in sub145})
        anchors = {"picks_top5": picks5, "picks_top5_pin": 4579,
                   "picks_arm": picks_arm, "picks_arm_pin": 5605,
                   "ic_145": ic145, "ic_pin": smoke.SLICE_IC_PIN,
                   "n_sub145": len(sub145), "n_val_folds": len(by_month),
                   "passed": (picks5 == 4579 and picks_arm == 5605
                              and abs(ic145 - smoke.SLICE_IC_PIN) < 1e-9
                              and len(sub145) == 145)}
        assert anchors["passed"], anchors
        # arm B's own in-run numbers must match the restored state bit-for-bit
        assert arms["B"]["ic_145"] == ic145 and arms["B"]["ic_val_146"] == \
            smoke._mean_monthly_ic({m: by_month[m] for m in by_month}), \
            "arm B drifted from the restored chain"

        # ---- structural guard (G2 machinery identity) -----------------------------------
        struct = {}
        for label, _f in ARMS:
            rs = arms[label]["reach"]
            pk = raw_picks[label]
            # recounted here ON PURPOSE: an identity checked with _reachability's own
            # bookkeeping proves nothing, and the fillable count is not in its dict.
            fill = {f"S{int(s // 1000)}k": sum(
                        1 for m, lst in pk.items() for _, sym, ret in lst
                        if ret is not None and med20.get((sym, m)) is not None
                        and med20[(sym, m)] >= 20.0 * s) for s in SLOT_BARS}
            labelled = sum(1 for lst in pk.values() for t in lst if t[2] is not None)
            # G2 as amended 2026-10-03: `picks` is already net of the unenterable, so the
            # partition is refused + fillable == picks, and picks + missing == the labeled
            # pick rows. Both recounted here, never read back out of _reachability.
            ok = all(r["refused"] + fill[k] == r["picks"]
                     and r["picks"] + r["picks_missing_liq20"] == labelled
                     for k, r in rs.items())
            mono = all(rs[f"S{int(SLOT_BARS[i] // 1000)}k"]["refused_pct"]
                       <= rs[f"S{int(SLOT_BARS[i + 1] // 1000)}k"]["refused_pct"] + 1e-12
                       for i in range(len(SLOT_BARS) - 1))
            struct[label] = {"identity": ok, "refusal_monotone_in_S": mono,
                             "fillable": fill, "labeled_pick_rows": labelled}
        assert all(v["identity"] and v["refusal_monotone_in_S"] for v in struct.values()), struct
        excl = [arms[l]["excluded_turnover"] for l, _f in ARMS]
        assert excl == sorted(excl), f"excluded_turnover must rise with the floor: {excl}"

        # ---- continuity tripwire (G3, arm C vs E009's committed R2) ---------------------
        e009 = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                           "009_fill_gate_reach", "results.json"),
                              encoding="utf-8"))
        c250 = arms["C"]["reach"]["S250k"]
        g3 = {"c_refusal_S250k": c250["refused_pct"],
              "e009_R2_refusal": e009["R2"]["refused_pct"],
              "c_corrected_S250k": c250["corrected_mean"],
              "e009_R2_corrected": e009["R2"]["corrected_mean"],
              "passed": c250["refused_pct"] <= 0.05
                        and abs(c250["corrected_mean"] - e009["R2"]["corrected_mean"]) <= 0.03}
        assert g3["passed"], g3

        # ---- the decision rule (hypothesis.md, evaluated mechanically) ------------------
        aS, bS = arms["A"]["reach"]["S500k"], arms["B"]["reach"]["S500k"]
        t = P41._paired_t(arms["A"]["ic_triples"], arms["B"]["ic_triples"])
        bars = _bars(aS, bS, t)
        bars["bars_as_coded"] = "T1: A.S500k.corrected >= B.S500k.corrected - 0.0005; " \
                                "T2: paired_t(A-B) >= -2; T3: A.S500k.refused <= " \
                                "B.S500k.refused / 3; T4 recorded, not gating"
        adopt, g1 = _adopt(bars, arms["A"]["eligibles"], arms["B"]["eligibles"],
                           anchors["passed"])

        out = {"experiment": "E027_floor_1_5cr_rung", "git_hash": _git(),
               "profile": args.profile, "slot_rupees": S, "boundary_cr": 20.0 * S / 1e7,
               "cutoff": str(cutoff), "anchors": anchors, "structural": struct,
               "G1_coverage": {"A_eligibles": arms["A"]["eligibles"],
                               "B_eligibles": arms["B"]["eligibles"],
                               "ratio": arms["A"]["eligibles"] / arms["B"]["eligibles"],
                               "passed": g1},
               "G3_continuity": g3, "arms": arms, "bars": bars,
               "decision": {"adopt_floor_1_5cr": adopt,
                            "meaning": "ADOPT = an Rs40L account is supportable ONLY with "
                                       "floor 1.5cr on these numbers; the shipped config "
                                       "changes only on ADOPT and adoption ships nothing"},
               "runtime_seconds": round(time.monotonic() - t0, 1)}
        path = os.path.join(os.path.dirname(__file__), "results.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2, default=str)

        print(f"\nanchors: picks {picks5}/4,579, {picks_arm}/5,605, IC145 {ic145:.10f} "
              f"== pin; sub145 {len(sub145)} folds; structural guard OK; G3 continuity "
              f"C@S250k refusal {c250['refused_pct']:.2%} (E009 committed "
              f"{e009['R2']['refused_pct']:.2%}), corrected {c250['corrected_mean']:+.3%} "
              f"vs {e009['R2']['corrected_mean']:+.3%}")
        print(f"{'arm':<10} {'floor':>6} {'eligibles':>10} {'refused@S500k':>14} "
              f"{'corrected':>10} {'impact':>8}")
        for label, _f in ARMS:
            a = arms[label]
            r5 = a["reach"]["S500k"]
            imp = a["mean_modelled_impact_S500k"]
            imp_s = "n/a" if imp is None else f"{imp:.4%}"
            print(f"{label:<10} {a['floor_cr']:>6} {a['eligibles']:>10,} "
                  f"{r5['refused_pct']:>14.2%} {r5['corrected_mean']:>10.3%} {imp_s:>8}")
        t_s = "n/a" if t is None else f"{t['t']:+.2f}"
        print(f"bars: T1 {bars['T1_corrected_holds']} (A {aS['corrected_mean']:+.3%} vs "
              f"B {bS['corrected_mean']:+.3%}); T2 {bars['T2_ic_holds']} (t {t_s}); "
              f"T3 {bars['T3_gate_fixed']} (A {aS['refused_pct']:.2%} vs B "
              f"{bS['refused_pct']:.2%}/3); G1 ratio {out['G1_coverage']['ratio']:.2f}")
        decision_txt = ("ADOPT floor 1.5cr for the Rs40L rung" if adopt else
                        "the Rs40L rung stays unsupported: the capacity note Rs20L "
                        "ceiling stands")
        print(f"DECISION: {decision_txt}")
        print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
        return 0
    finally:
        cfg["universe"]["min_median_turnover_cr"] = shipped_floor   # never leak an arm floor
        con.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
