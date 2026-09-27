"""Prospective dashboard — where every registered design stands against its frozen bar.

    python -m src.prospective.dashboard

Per registered design (from runs/prospective/designs.json): fold count (valid/total),
the running paired IC difference vs its reference, a one-sample t on those differences,
and the distance to the early-stop and verdict thresholds codified in the design module
(BAR_DIFF / N_FOLDS / EARLY_STOP_N / EARLY_STOP_T, read from the module when present).
Read-only over folds.csv; writes nothing.
"""
from __future__ import annotations

import csv
import importlib
import json
import math
import os
import statistics

DESIGNS_PKG = "src.prospective.designs"


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _t1(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mean = statistics.mean(xs)
    sd = statistics.stdev(xs)
    if sd == 0:
        return None if mean == 0 else math.copysign(1e9, mean)   # P4.1's _paired_t convention
    return mean / (sd / math.sqrt(len(xs)))


def _row(designs: dict, name: str) -> str:
    d = designs[name]
    path = os.path.join(_root(), "runs", "prospective", name, "folds.csv")
    if not os.path.exists(path):
        return f"  {name:<20} no folds yet (registered {d.get('registered_at', '?')[:10]})"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    valid = [r for r in rows if r.get("valid", "1") == "1"]
    lines = [f"  {name:<20} folds {len(valid)}/{len(rows)} valid "
             f"(registered {d.get('registered_at', '?')[:10]})"]

    # paired differences vs the reference column, when the design ships one
    diffs = [float(r["ic"]) - float(r["ref_ic"]) for r in valid
             if r.get("ref_ic") not in (None, "", "None")]
    ref = importlib.import_module(f"{DESIGNS_PKG}.{name}")
    bar = getattr(ref, "BAR_DIFF", None)
    n_bar = getattr(ref, "N_FOLDS", None)
    es_n = getattr(ref, "EARLY_STOP_N", None)
    es_t = getattr(ref, "EARLY_STOP_T", None)

    if diffs:
        mean = statistics.mean(diffs)
        t = _t1(diffs)
        lines.append(f"    paired diff {mean:+.4f} over {len(diffs)} folds, "
                     f"t {'undefined (zero variance)' if t is None else f'{t:+.2f}'}")
        if bar is not None:
            need = bar - mean
            lines.append(f"    bar: diff >= +{bar:.4f} over n={n_bar} "
                         f"-> {'MET' if mean >= bar else f'{need:+.4f} to go'}"
                         f"{f', {n_bar - len(valid)} folds to verdict' if n_bar else ''}")
        if es_n is not None:
            if t is not None and len(valid) >= es_n and t < es_t:
                lines.append(f"    EARLY-STOP zone: n {len(valid)} >= {es_n} and "
                             f"t {t:+.2f} < {es_t} (fail direction) — call it")
            else:
                lines.append(f"    early stop: needs n >= {es_n} and t < {es_t} "
                             f"(now {'t undefined' if t is None else f't {t:+.2f}'})")
    else:
        lines.append("    no reference column — bar distances unavailable")
    g2 = d.get("reference_insample_ic")
    if g2:
        lines.append(f"    in-sample context (not gating): diff {g2['paired_diff']:+.4f}, "
                     f"t {g2['t']:+.2f}")
    return "\n".join(lines)


def main() -> int:
    dj = os.path.join(_root(), "runs", "prospective", "designs.json")
    if not os.path.exists(dj):
        print("no designs registered")
        return 0
    designs = json.load(open(dj, encoding="utf-8"))
    print(f"prospective dashboard — {len(designs)} design(s), "
          f"record: runs/prospective/<name>/folds.csv")
    for name in sorted(designs):
        print(_row(designs, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
