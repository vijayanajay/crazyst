"""E025 — do NSE index-inclusion events predict monthly returns on this universe?
(Pre-registered in hypothesis.md, run AFTER that file was written, per BRD 12.)

An IC screen, not a design experiment: at each labeled decision month m, a symbol's flag
is 1 iff the sourced IndexInclExcl workbook records a Nifty 500 inclusion (or exclusion)
dated within the 12 months BEFORE m — backward-looking, no look-ahead. Measured: per-month
Spearman IC of the 0/1 flag vs next_month_ret, the mean label gap (flagged − unflagged),
one-sample t across months, event-bearing months. Data: src.download.index_events
(IndexInclExcl.xls + EQUITY_L.csv name->symbol bridge; 48.7% of Nifty 500 events matched;
the file is stale after 2020-09 — recorded as a coverage guard, not hidden).

Practical bar (frozen): includer gap >= +1.0pp/mo (or excluder gap <= -1.0pp/mo) over
>= 30 event-bearing months. PASS licenses a portfolio pre-registration; it promotes
nothing. If the source were unfetchable the verdict would be NOT MEASURED (it fetched).

python -m experiments.025_inclusion_events.run --profile full
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import time
from datetime import date, timedelta

import duckdb

from src.config import load
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")
HARNESS = importlib.import_module("src.walkforward.harness")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")

WINDOW_MONTHS = 12
GAP_BAR_PP = 1.0
EVENT_MONTHS_MIN = 30


def _t_stat(xs):
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return mean / math.sqrt(var / n) if var > 0 else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        E007._build_chain(con, cfg)
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
        labeled = [r for r in rows if r[1] is not None]
        val_rows, test_rows, boundary = P41.split_slice(labeled, cutoff)
        val_folds = sorted({str(r[0]) for r in val_rows})
        assert len(val_folds) == 145 and val_folds[0] == "2011-07-29" \
            and val_folds[-1] == "2023-07-31"
        assert str(boundary) == "2023-09-24"
        by_month: dict[str, dict[str, float]] = {}
        for r in val_rows:
            by_month.setdefault(str(r[0]), {})[r[-2]] = r[1]
        # events with a matched symbol, Nifty 500 sheet only
        ev = con.execute(
            "SELECT symbol, date, action FROM index_events "
            "WHERE index_name = 'Nifty 500' AND symbol IS NOT NULL").fetchall()
        n_total, n_matched = con.execute(
            "SELECT count(*), count(symbol) FROM index_events WHERE index_name = 'Nifty 500'"
        ).fetchone()
        last_ev = con.execute("SELECT max(date) FROM index_events "
                              "WHERE index_name = 'Nifty 500'").fetchone()[0]
    finally:
        con.close()

    # G1: source coverage (frozen bar: >= 1,000 matched events on the Nifty 500 sheet)
    g1 = n_matched >= 1_000
    assert g1, (n_total, n_matched)
    # G2: slice pins
    g2 = len(val_folds) == 145 and str(boundary) == "2023-09-24"
    assert g2

    # per-symbol event date lists, per action
    by_action: dict[str, dict[str, list]] = {"include": {}, "exclude": {}}
    for sym, d, act in ev:
        by_action.setdefault(act, {}).setdefault(sym, []).append(d)

    def flag_in_window(sym: str, m: str, action: str) -> bool:
        """1 iff an event of `action` for sym is dated within WINDOW_MONTHS before m
        (strictly after m minus the window; <= m). Events dated > m are never read."""
        lo = date.fromisoformat(m) - timedelta(days=30.44 * WINDOW_MONTHS + 2)
        mm = date.fromisoformat(m)
        return any(lo < d <= mm for d in by_action.get(action, {}).get(sym, ()))

    results = {}
    for action in ("include", "exclude"):
        ics, gaps, event_months, flagged_total, cross_rows = [], [], 0, 0, 0
        for m in val_folds:
            labels = by_month[m]
            flags = {s: 1 if flag_in_window(s, m, action) else 0 for s in labels}
            k = sum(flags.values())
            cross_rows += len(labels)
            flagged_total += k
            if k == 0:
                continue                       # no event-bearing names this month
            event_months += 1
            pairs = [(flags[s], labels[s]) for s in labels]
            ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
            ics.append(ic)
            f_vals = [labels[s] for s in labels if flags[s]]
            u_vals = [labels[s] for s in labels if not flags[s]]
            if f_vals and u_vals:
                gaps.append(sum(f_vals) / len(f_vals) - sum(u_vals) / len(u_vals))
        mean_ic = sum(ics) / len(ics) if ics else None
        mean_gap = sum(gaps) / len(gaps) if gaps else None
        results[action] = {
            "event_bearing_months": event_months, "flagged_name_months": flagged_total,
            "mean_monthly_ic": mean_ic, "ic_t_across_months": _t_stat(ics),
            "mean_label_gap": mean_gap, "gap_t_across_months": _t_stat(gaps),
            "months_in_sample": len(val_folds),
        }

    inc = results["include"]
    exc = results["exclude"]
    pass_inc = (inc["event_bearing_months"] >= EVENT_MONTHS_MIN and inc["mean_label_gap"]
                is not None and inc["mean_label_gap"] >= GAP_BAR_PP / 100)
    pass_exc = (exc["event_bearing_months"] >= EVENT_MONTHS_MIN and exc["mean_label_gap"]
                is not None and exc["mean_label_gap"] <= -GAP_BAR_PP / 100)
    screen_pass = pass_inc or pass_exc

    out = {
        "experiment": "E025_inclusion_events", "git_hash": git, "profile": args.profile,
        "window": {"validation_months": len(val_folds), "first": val_folds[0],
                   "last": val_folds[-1], "event_window_months": WINDOW_MONTHS,
                   "test_window": "burnt; not touched"},
        "guards": {"G1_source_coverage": g1, "G1_events_total": n_total,
                   "G1_events_matched": n_matched, "G1_last_event": str(last_ev),
                   "G2_slice_pins": g2,
                   "G3_no_lookahead": "flags read only events dated <= m; asserted by "
                                      "construction in flag_in_window",
                   "passed": g1 and g2},
        "disclosures": {
            "stale_source": f"the workbook's last event is {last_ev}; months after that "
                            "have empty flag sets and cannot contribute (visible in "
                            "event_bearing_months)",
            "match_rate": f"{n_matched}/{n_total} Nifty 500 events matched to NSE symbols "
                          "via the EQUITY_L master; unmatched are renames/delistings/"
                          "master gaps (counted, excluded)"},
        "sweep": results,
        "bars": {"gap_bar_pp": GAP_BAR_PP, "event_months_min": EVENT_MONTHS_MIN,
                 "pass_include": pass_inc, "pass_exclude": pass_exc},
        "verdict": "PASS" if screen_pass else "REJECTED",
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    for action, r in results.items():
        print(f"{action:<8} event-months {r['event_bearing_months']:>3}  "
              f"IC {r['mean_monthly_ic']:+.4f} (t {r['ic_t_across_months']:+.2f})  "
              f"gap {r['mean_label_gap']:+.4f}/mo (t {r['gap_t_across_months']:+.2f})  "
              f"flagged {r['flagged_name_months']}")
    print(f"coverage: {n_matched}/{n_total} matched, last event {last_ev}")
    print(f"bars: gap >= +{GAP_BAR_PP}pp/mo (incl) or <= -{GAP_BAR_PP}pp/mo (excl) over "
          f">= {EVENT_MONTHS_MIN} event-months")
    print(f"DECISION: {out['verdict']}"
          + (" — the effect justifies a portfolio pre-registration (promotes nothing "
             "itself)" if screen_pass else
             " — no deployable-sized inclusion effect at the monthly horizon on this "
             "universe; the data direction is measured and closed"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
