"""Self-check runner (plan "Self-check runner" section).

Runs every module's `python -m` self-check in a subprocess, prints `PASS/FAIL + elapsed`
per check, and exits non-zero at the first failure. Subprocesses keep checks isolated
(each one calls sys.exit and may hold DuckDB handles). Stdout is captured by default so
the summary stays clean; on failure the tail is printed so the assert's `got X, expected
Y` message is visible without rerunning. `--verbose` streams full output live.

Usage:
    python -m src.selfcheck            # run all, fail fast
    python -m src.selfcheck --verbose  # stream each check's output
    python -m src.selfcheck --list     # show the registry
"""
import subprocess
import sys
import time

# registry: (name, module with a __main__ self-check). Network checks are cache-backed:
# once months are cached they run in seconds and hit NSE only for missing files.
CHECKS = [
    ("config", "src.config"),
    ("bhavcopy_old", "src.download.bhavcopy_old"),
    ("bhavcopy_udiff", "src.download.bhavcopy_udiff"),
    ("delivery", "src.download.delivery"),
    ("normalize.bhav", "src.normalize.bhav"),
    ("normalize.delivery", "src.normalize.delivery"),
    ("validate.report", "src.validate.report"),
    ("validate.canary", "src.validate.canary"),
    ("universe.rank", "src.universe.rank"),
    ("universe.eligibility", "src.universe.eligibility"),
    ("universe.winners", "src.universe.winners"),
]


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for name, module in CHECKS:
            print(f"{name:<18} {module}")
        return 0
    verbose = "--verbose" in argv or "-v" in argv
    assert CHECKS, "no checks registered"

    for name, module in CHECKS:
        t0 = time.monotonic()
        if verbose:
            print(f"== {name} ({module}) ==", flush=True)
            r = subprocess.run([sys.executable, "-m", module])
            tail = []
        else:
            r = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True)
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
    print(f"ALL PASS ({len(CHECKS)} checks)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
