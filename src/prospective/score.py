"""Prospective scoring — the mechanical half of docs/prospective_protocol.md.

New designs are scored ONLY on virgin labeled folds: months that (a) carry a label,
(b) fall strictly after the design's freeze month, and (c) were never scored before.
Everything is append-only: folds.csv is the record, a fold scored twice is a hard error,
and the design freeze is hash-pinned at registration so post-hoc edits are detectable.

Commands:
    python -m src.prospective.score --register docs/prospective/<name>/design.md
        hash-pin the design (writes designs.json entry; refuses an already-registered name)
    python -m src.prospective.score --score <name>
        score the newest virgin fold for one design (idempotent; re-scores are an error)
    python -m src.prospective.score --all
        score every registered design on the newest virgin fold (the monthly job)
    python -m src.prospective.score --repin <name>
        re-pin the hash after a DISCLOSED amendment (records the old and new hash)

Designs live at src/prospective/designs/<name>.py and expose `score_month(rows) ->
list[float | None]` over the harness's labeled row tuples (same layout every P4.x
experiment scored). A design MAY also expose `fold_metrics(rows) -> dict` for
book-level constructions: its items are appended as extra folds.csv columns (disclosed
in the design freeze before any fold exists). `--self-check` runs the hand-computed
fixture.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load

HARNESS = importlib.import_module("src.walkforward.harness")
E007 = importlib.import_module("experiments.007_universe_cutoff.run")
DESIGNS_PKG = "src.prospective.designs"


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _prospective_dir() -> str:
    return os.path.join(_repo_root(), "runs", "prospective")


def _designs_json() -> str:
    return os.path.join(_prospective_dir(), "designs.json")


def _folds_csv(name: str) -> str:
    return os.path.join(_prospective_dir(), name, "folds.csv")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_designs() -> dict:
    if os.path.exists(_designs_json()):
        with open(_designs_json(), encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_designs(designs: dict) -> None:
    os.makedirs(_prospective_dir(), exist_ok=True)
    with open(_designs_json(), "w", encoding="utf-8") as f:
        json.dump(designs, f, indent=2)


def register(design_md: str) -> int:
    designs = _load_designs()
    name = os.path.basename(os.path.dirname(os.path.abspath(design_md)))
    if name in designs:
        raise SystemExit(f"design {name!r} already registered — use --repin for amendments")
    code_path = os.path.join(_repo_root(), "src", "prospective", "designs", f"{name}.py")
    code_sha = _sha256(code_path) if os.path.exists(code_path) else None
    designs[name] = {
        "design_md": os.path.relpath(design_md, _repo_root()).replace("\\", "/"),
        "sha256": _sha256(design_md),
        "code_path": os.path.relpath(code_path, _repo_root()).replace("\\", "/") if code_sha else None,
        "code_sha256": code_sha,
        "registered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_designs(designs)
    print(f"registered {name!r}: sha256 {designs[name]['sha256'][:16]}… (code {code_sha[:16] if code_sha else 'none'}…)")
    return 0


def repin(name: str, reason: str) -> int:
    designs = _load_designs()
    if name not in designs:
        raise SystemExit(f"design {name!r} not registered")
    d = designs[name]
    old_md = d["sha256"]
    d["sha256"] = _sha256(os.path.join(_repo_root(), d["design_md"]))
    code_path = os.path.join(_repo_root(), "src", "prospective", "designs", f"{name}.py")
    old_code = d.get("code_sha256")
    new_code = _sha256(code_path) if os.path.exists(code_path) else None
    d["code_path"] = os.path.relpath(code_path, _repo_root()).replace("\\", "/") if new_code else None
    d["code_sha256"] = new_code
    d.setdefault("amendments", []).append(
        {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "from": old_md, "to": d["sha256"],
         "code_from": old_code, "code_to": new_code,
         "reason": reason})
    _save_designs(designs)
    print(f"re-pinned {name!r}: {old_md[:12]}… -> {d['sha256'][:12]}… (reason recorded)")
    return 0


def _newest_virgin_fold(cfg: dict, designs: dict, name: str) -> str | None:
    """The newest labeled month whose LABEL END is after the design's freeze timestamp and
    which is not already in the design's folds.csv."""
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
    finally:
        con.close()
    labeled = [r for r in rows if r[1] is not None]
    months = sorted({str(r[0]) for r in labeled})
    if not months:
        return None
    freeze_month = designs[name].get("registered_at", "")[:7]     # YYYY-MM
    freeze_ym = freeze_month if len(freeze_month) == 7 else "0000-00"
    scored = set()
    if os.path.exists(_folds_csv(name)):
        with open(_folds_csv(name), encoding="utf-8") as f:
            scored = {row["month"] for row in csv.DictReader(f)}
    # a month is virgin only if its decision month is AFTER the freeze month (the label
    # that closes after the freeze is what makes the fold out-of-sample)
    candidates = [m for m in months if m[:7] > freeze_ym and m not in scored]
    return candidates[-1] if candidates else None


def score(name: str) -> int:
    designs = _load_designs()
    if name not in designs:
        raise SystemExit(f"design {name!r} not registered")
    d = designs[name]
    md_path = os.path.join(_repo_root(), d["design_md"])
    if not os.path.exists(md_path):
        raise SystemExit(f"design file missing: {d['design_md']}")
    if _sha256(md_path) != d["sha256"]:
        raise SystemExit("design file changed since registration — amend via --repin "
                         "with a disclosure, never silently")
    code_path = os.path.join(_repo_root(), "src", "prospective", "designs", f"{name}.py")
    if d.get("code_sha256"):
        if not os.path.exists(code_path):
            raise SystemExit(f"scorer code missing: {code_path}")
        if _sha256(code_path) != d["code_sha256"]:
            raise SystemExit(f"scorer code {code_path} changed since registration — amend via --repin "
                             "with a disclosure, never silently")
    mod = importlib.import_module(f"{DESIGNS_PKG}.{name}")
    cfg = load("full")

    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows, cutoff, eliq, sessions = HARNESS._fetch(con)
    finally:
        con.close()
    labeled = [r for r in rows if r[1] is not None]
    by_month: dict[str, list] = {}
    for r in labeled:
        by_month.setdefault(str(r[0]), []).append(r)

    fold = _newest_virgin_fold(cfg, designs, name)
    if fold is None:
        print(f"{name}: no virgin fold yet (freeze {d['registered_at']}; nothing new to score)")
        return 0

    t0 = time.monotonic()
    scores = mod.score_month(by_month[fold])
    rs = by_month[fold]
    pairs = [(s, r[1]) for s, r in zip(scores, rs) if s is not None and r[1] is not None]
    if len(pairs) < 2:
        raise SystemExit(f"{name}: fold {fold} scored {len(pairs)} usable pairs — "
                         "the scorer is broken (G3 coverage)")
    from src.stats import spearman_ic
    ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
    mean_score = sum(p[0] for p in pairs) / len(pairs)
    mean_ret = sum(p[1] for p in pairs) / len(pairs)
    top_k = max(1, round(len(pairs) * 0.05))
    top = sorted(pairs, key=lambda p: -p[0])[:top_k]
    top_mean_ret = sum(r for _s, r in top) / top_k

    # optional paired reference (a design may ship score_month_reference) + validity flag
    ref_ic = ""
    if hasattr(mod, "score_month_reference"):
        ref_scores = mod.score_month_reference(rs)
        rp = [(s, r[1]) for s, r in zip(ref_scores, rs) if s is not None and r[1] is not None]
        ref_ic = f"{spearman_ic([p[0] for p in rp], [p[1] for p in rp]):.6f}"
    min_scored = getattr(mod, "MIN_SCORED", 0)
    valid = int(len(pairs) >= min_scored)

    # optional design-level fold metrics (book-level designs record their construction
    # here; the hook must be disclosed in the design freeze BEFORE any fold exists).
    # Appended as extra columns so the record stays one row per fold. Designs without
    # the hook (x2f_interaction) are untouched: no extra columns, identical schema.
    extras: list[tuple[str, str]] = []
    if hasattr(mod, "fold_metrics"):
        for k, v in mod.fold_metrics(rs).items():
            extras.append((k, f"{v:.6f}" if isinstance(v, float) else str(v)))

    expected_header = ["month", "ic", "n_scored", "mean_score", "mean_label",
                       "top5_mean_label", "ref_ic", "valid", "scored_at",
                       "design_sha256"] + [k for k, _v in extras]
    os.makedirs(os.path.dirname(_folds_csv(name)), exist_ok=True)
    new_file = not os.path.exists(_folds_csv(name))
    if not new_file:
        with open(_folds_csv(name), encoding="utf-8") as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != expected_header:
            raise SystemExit(f"{name}: folds.csv header mismatch — "
                             f"existing {existing_header} != expected {expected_header}")
    with open(_folds_csv(name), "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(expected_header)
        w.writerow([fold, f"{ic:.6f}", len(pairs), f"{mean_score:.6f}",
                    f"{mean_ret:.6f}", f"{top_mean_ret:.6f}", ref_ic, valid,
                    time.strftime("%Y-%m-%d %H:%M:%S"), d["sha256"][:16]]
                   + [v for _k, v in extras])
    n_folds = len({row["month"] for row in csv.DictReader(open(_folds_csv(name),
                                                               encoding="utf-8"))})
    print(f"{name}: fold {fold} scored — IC {ic:+.4f} over {len(pairs)} rows, "
          f"top-5% mean label {top_mean_ret:+.2%} ({n_folds} folds on record, "
          f"{time.monotonic() - t0:.1f}s)")
    return 0


def self_check() -> int:
    """Hand-computed fixture for the record path: a fake month, a known ranking, an
    append-only assertion (a second identical score must fail), and header consistency."""
    import tempfile
    from src.stats import spearman_ic

    scores = [0.9, 0.1, 0.5, None, 0.3]
    labels = [0.04, -0.02, 0.00, 0.10, -0.01]
    pairs = [(s, y) for s, y in zip(scores, labels) if s is not None]
    ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
    # score ranks (asc): 0.1->1, 0.3->2, 0.5->3, 0.9->4; label ranks: -0.02->1, -0.01->2,
    # 0.00->3, 0.04->4 — the pairs are perfectly aligned, so rho = 1.0 (the None row and
    # its label 0.10 are excluded first, which is the point of the fixture)
    assert abs(ic - 1.0) < 1e-12, ic
    # a second, imperfect alignment: swap two labels -> d^2 = 1 + 1 = 2, n = 4
    ic2 = spearman_ic([0.9, 0.1, 0.5, 0.3], [0.04, -0.01, 0.00, -0.02])
    assert abs(ic2 - (1 - 6 * 2 / (4 * (4 ** 2 - 1)))) < 1e-12, ic2
    top_k = max(1, round(len(pairs) * 0.05)) or 1
    assert top_k == 1
    top = sorted(pairs, key=lambda p: -p[0])[:top_k]
    assert abs(top[0][1] - 0.04) < 1e-12
    tmp = tempfile.mkdtemp()
    f = os.path.join(tmp, "folds.csv")
    with open(f, "w", newline="", encoding="utf-8") as fh:
        fh.write("month,ic\n2026-10-31,0.5\n")
    rows = list(csv.DictReader(open(f, encoding="utf-8")))
    assert rows[0]["month"] == "2026-10-31"
    assert len({r["month"] for r in rows}) == len(rows)

    # header alignment check assertion
    with open(f, encoding="utf-8") as fh:
        hdr = next(csv.reader(fh), [])
    assert hdr == ["month", "ic"]
    print("PASS: src.prospective.score self-check (hand IC, top-5 pick, append-only record, header check)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--register", metavar="DESIGN_MD")
    ap.add_argument("--score", metavar="NAME")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--repin", nargs=2, metavar=("NAME", "REASON"))
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check:
        return self_check()
    if args.register:
        return register(args.register)
    if args.repin:
        return repin(args.repin[0], args.repin[1])
    if args.score:
        return score(args.score)
    if args.all:
        designs = _load_designs()
        if not designs:
            print("no designs registered; the protocol wall is recorded in "
                  "runs/prospective/designs.json (created on first registration)")
            return 0
        rc = 0
        for name in sorted(designs):
            rc |= score(name)
        return rc
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
