"""Self-check runner (plan "Self-check runner" section).

Runs every module's `python -m` self-check in a subprocess, prints `PASS/FAIL + elapsed`
per check, and exits non-zero at the first failure. Subprocesses keep checks isolated
(each one calls sys.exit and may hold DuckDB handles). Stdout is captured by default so
the summary stays clean; on failure the tail is printed so the assert's `got X, expected
Y` message is visible without rerunning. `--verbose` streams full output live.

Input stamps (src/stamp.py): a full pass records a fingerprint of the data, code and config it
validated. If nothing has moved since, the next run prints `ALL PASS (cached)` in under a
second instead of redoing every scan — seconds when nothing changed, full work when data moved.
The stamp is recorded only after every check passes, and is cleared before the run starts, so a
failure or a crash can never look like a pass.

Usage:
    python -m src.selfcheck            # all checks, cached when inputs are unchanged
    python -m src.selfcheck --force    # ignore the stamp and re-run every check
    python -m src.selfcheck --verbose  # stream each check's output
    python -m src.selfcheck --list     # show the registry
"""
import subprocess
import sys
import time

import duckdb

from src import stamp
from src.config import load, python_child_args

# registry: (name, module with a __main__ self-check). Network checks are cache-backed:
# once months are cached they run in seconds and hit NSE only for missing files.
CHECKS = [
    ("config", "src.config"),
    ("stats", "src.stats"),
    ("stamp", "src.stamp"),
    ("bhavcopy_old", "src.download.bhavcopy_old"),
    ("bhavcopy_udiff", "src.download.bhavcopy_udiff"),
    ("delivery", "src.download.delivery"),
    ("normalize.bhav", "src.normalize.bhav"),
    ("normalize.delivery", "src.normalize.delivery"),
    ("normalize.adj_close", "src.normalize.adj_close"),
    ("normalize.panels", "src.normalize.panels"),
    ("validate.report", "src.validate.report"),
    ("validate.canary", "src.validate.canary"),
    ("universe.rank", "src.universe.rank"),
    ("universe.eligibility", "src.universe.eligibility"),
    ("features.panel", "src.features.panel"),
    ("features.matrix", "src.features.matrix"),
    ("universe.winners", "src.universe.winners"),
    ("backtest.engine", "src.backtest.engine"),
    ("backtest.portfolio", "src.backtest.portfolio"),
    ("backtest.metrics", "src.backtest.metrics"),
]

SUITE_KEY = "selfcheck"


def suite_inputs(cfg: dict) -> list:
    """Everything the checks read: the sources, the raw cache, the code and the config.

    Every table here is also re-verified by row count when the stamp is checked, so a truncated
    or dropped table forces a rerun rather than a false "unchanged".
    """
    return [
        "code",
        "table:bhav.date",
        "table:delivery.date",
        "table:adj_close.date",
        "table:month_grid.m",
        "table:adj_me.mdate",
        "table:liq_me.mdate",
        "table:deliv_me.mdate",
        "table:feature_panel.mdate",
        "table:feature_matrix.mdate",
        "table:universe_rank.mdate",
        "table:eligible.mdate",
        "table:winners.mdate",
        f"dir:{cfg['paths']['raw_bhavcopy_old']}",
        f"dir:{cfg['paths']['raw_bhavcopy_udiff']}",
        f"dir:{cfg['paths']['raw_delivery']}",
        f"dir:{cfg['paths']['raw_yf_adj']}",
    ]


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for name, module in CHECKS:
            print(f"{name:<18} {module}")
        return 0
    verbose = "--verbose" in argv or "-v" in argv
    force = "--force" in argv
    assert CHECKS, "no checks registered"

    t_start = time.monotonic()
    cfg = load()
    specs = suite_inputs(cfg)
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        fp = stamp.fingerprint(cfg, con, specs)
        if not force and stamp.is_current(con, SUITE_KEY, fp):
            print(f"ALL PASS ({len(CHECKS)} checks, cached — no data/code/config change since "
                  f"{stamp.built_at(con, SUITE_KEY)}; --force to rerun)")
            return 0
        stamp.clear(con, SUITE_KEY)  # success is not known yet: never leave a fresh-looking stamp
    finally:
        con.close()

    for name, module in CHECKS:
        t0 = time.monotonic()
        if verbose:
            print(f"== {name} ({module}) ==", flush=True)
            r = subprocess.run(python_child_args(module))
            tail = []
        else:
            r = subprocess.run(python_child_args(module), capture_output=True, text=True)
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
        dt = time.monotonic() - t0
        if r.returncode == 0:
            print(f"PASS  {name:<18} {dt:6.1f}s", flush=True)
        else:
            print(f"FAIL  {name:<18} {dt:6.1f}s  (exit {r.returncode})", flush=True)
            for line in tail:
                print(f"      | {line}", flush=True)
            print(f"stopped at first failure: {name}", flush=True)
            return 1

    total = time.monotonic() - t_start
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        stamp.record(con, SUITE_KEY, stamp.fingerprint(cfg, con, specs),
                     outputs=stamp.spec_tables(con, specs), seconds=total)
    finally:
        con.close()
    print(f"ALL PASS ({len(CHECKS)} checks) in {total:.1f}s  "
          f"[stamped: next run is cached until data, code or config changes]", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
