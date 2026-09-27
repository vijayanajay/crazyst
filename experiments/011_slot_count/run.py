"""E011 - slot-count attribution (pre-registered in hypothesis.md; run AFTER that file was
written, per BRD 12). Four arms through the UNMODIFIED walk-forward harness - the only
change is portfolio.n_slots (B8 also widens the two monthly-review percentiles):

  A4   n_slots=4 (the pre-E011 shipped default)
                                - the CONTROL: must reproduce the Phase 6.1 baseline
                                bit-for-bit on every reported number (the zero-drift
                                guard against runs/walkforward/harness_results.json
                                as committed at git a8cc624).
  A8   n_slots=8              - equal-weight per FREE slot, so per-slot notional halves;
                                the E006 fill gate sees smaller orders.
  A12  n_slots=12
  B8   n_slots=8 + monthly_review sell_below 0.25->0.15 / replace_above 0.15->0.10
                               (churn control: A8's churn read as slot artifact vs
                               ranking-pressure artifact). Secondary, never load-bearing.

Every arm runs the harness twice (verify_determinism) - each pass's serialized evaluation
must equal its own replay BEFORE the arm's numbers are accepted (BRD 9.5 at arm level).
Per-arm results + the pre-registered decision rule's evaluation go to results.json;
verdict logic lives in verdict.md.

python -m experiments.011_slot_count.run --profile full
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

from src.config import load
from src.walkforward import harness as wf

BASELINE = os.path.join("runs", "walkforward", "harness_results.json")
GUARD_KEYS = ("final_equity", "completed_picks", "pick_hit_rate", "month_hit_rate",
              "churn_per_month", "avg_holding_days", "max_drawdown", "total_return")
SLOT_BARS = {"equity_edge": 200_000.0, "dd_slack": 0.02, "hit_slack_pp": 0.03}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                          ).stdout.strip()


def _core(ev: dict) -> dict:
    return {k: ev[k] for k in GUARD_KEYS}


def _decide(arms: dict) -> dict:
    """The pre-registered rule from hypothesis.md, evaluated mechanically."""
    a4 = arms["A4"]["engine"]
    passing = []
    for name in ("A8", "A12"):
        ev = arms[name]["engine"]
        ok = {"equity": ev["final_equity"] >= a4["final_equity"] + SLOT_BARS["equity_edge"],
              "sharpe": ev["sharpe_monthly"] > a4["sharpe_monthly"],
              "maxdd": ev["max_drawdown"] >= a4["max_drawdown"] - SLOT_BARS["dd_slack"],
              "hit": ev["pick_hit_rate"] >= a4["pick_hit_rate"] - SLOT_BARS["hit_slack_pp"]}
        if all(ok.values()):
            passing.append((name, ev))
    adopt, note = "KEEP 4", "no arm cleared all four pre-registered bars"
    if passing:
        passing.sort(key=lambda p: p[1]["final_equity"])
        adopt, best = passing[-1][0], passing[-1][1]
        note = (f"{adopt} clears all four bars; between passing arms the higher final "
                f"equity wins ({', '.join(n for n, _ in passing)})")
    return {"adopt": adopt, "note": note, "bars": SLOT_BARS,
            "passing_arms": [n for n, _ in passing]}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    cfg = load(args.profile)
    # pre-ADOPT the shipped default was 4; post-ADOPT (this experiment's own verdict) it is
    # 8 - either way the arms pass their slot counts EXPLICITLY, so the run stays
    # re-runnable and bit-reproducible after the config change (the E009 pattern)
    if cfg["portfolio"]["n_slots"] not in (4, 8):
        raise SystemExit(f"shipped n_slots is {cfg['portfolio']['n_slots']}, expected 4 or 8")

    with open(BASELINE) as f:
        base = json.load(f)

    arms, paper = {}, None
    for name, overrides in (("A4", {"n_slots": 4}), ("A8", {"n_slots": 8}),
                            ("A12", {"n_slots": 12}),
                            ("B8", {"n_slots": 8,
                                    "monthly_review_sell_below_top_pct": 0.15,
                                    "monthly_review_replace_above_top_pct": 0.10})):
        t0 = time.monotonic()
        res = wf.run(args.profile, verify_determinism=True, portfolio_overrides=overrides)
        arms[name] = {"portfolio_overrides": overrides, "engine": res["engine"],
                      "folds": res["folds"], "regime_table": res["regime_table"],
                      "config": res["config"], "runtime_seconds": res["runtime_seconds"]}
        if paper is None:
            paper = res["paper_picks"]
        else:
            assert res["paper_picks"] == paper, f"{name}: paper picks moved between arms"
        arms[name]["seconds"] = round(time.monotonic() - t0, 1)
        print(f"[{name}] equity {res['engine']['final_equity']:,.0f} "
              f"({res['engine']['total_return']:+.2%}) sharpe "
              f"{res['engine']['sharpe_monthly']:.2f} maxDD "
              f"{res['engine']['max_drawdown']:.1%} picks {res['engine']['completed_picks']} "
              f"hit {res['engine']['pick_hit_rate']:.0%} churn "
              f"{res['engine']['churn_per_month']:.2f} ({arms[name]['seconds']}s)")

    # ---- zero-drift guard: A4 vs the committed Phase 6.1 baseline ------------------------
    drift = {k: (base["engine"][k], arms["A4"]["engine"][k]) for k in GUARD_KEYS
             if base["engine"][k] != arms["A4"]["engine"][k]}
    assert not drift, f"A4 does not reproduce the shipped baseline: {drift}"
    assert base["paper_picks"] == paper, "paper picks drifted from the baseline run"

    decision = _decide(arms)
    out = {"experiment": "E011 slot-count attribution (harness arms)",
           "git_hash": _git(), "profile": args.profile, "cutoff": base["cutoff"],
           "boundary": base["boundary"], "n_folds": base["n_folds"],
           "baseline_file": BASELINE, "baseline_git_hash": base["git_hash"],
           "pre_registration": "experiments/011_slot_count/hypothesis.md",
           "decision_rule": _decide.__doc__ or "hypothesis.md bars",
           "arms": arms, "paper_picks": paper,
           "decision": decision,
           "a4_guard": {"keys": GUARD_KEYS, "result": "bit-identical to the shipped baseline"}}
    path = os.path.join("experiments", "011_slot_count", "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"wrote {path}")
    print(f"decision: {decision['adopt']} - {decision['note']}")
    print("PASS: E011 arms complete (A4 guard bit-identical; each arm deterministic)",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
