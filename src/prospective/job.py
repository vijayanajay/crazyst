"""The scheduled job — data refresh, then prospective scoring, one log file.

    python -m src.prospective.job          # what Task Scheduler / cron calls

Chain (docs/prospective_protocol.md "Operations"):
  1. `src.download.scheduler --once` — one refresh attempt (self-gating on the IST
     publish cutoff; exit 2 = not caught up yet (holiday / late archive), which is
     normal and healed by the next day's run).
  2. `src.prospective.score --all` — score every registered design on the newest virgin
     fold. Self-gating: a no-op unless a new fold exists, so running it daily is safe
     and the EFFECTIVE cadence is monthly (folds close monthly).

Everything appends timestamped lines to data/prospective.log; the exit code is 0 when
both stages ran (2 from the refresh alone is not a failure), 1 when the scorer itself
failed — that is the only line a monitoring alert needs to watch.

Wiring (Windows Task Scheduler, current user, no elevation):
    schtasks /create /tn QuantProspective /sc weekly /d MON,TUE,WED,THU,FRI /st 20:00 ^
        /tr "D:\Code\crazyst\prospective_job.cmd"
(cron equivalent: `45 19 * * 1-5 cd /path/to/repo && .venv/bin/python -m src.prospective.job`)
"""
from __future__ import annotations

import subprocess
import sys
import time

from src.config import load


def _log(msg: str) -> None:
    cfg = load("full")
    path = cfg["paths"].get("prospective_log", "data/prospective.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    print(msg, flush=True)


def main() -> int:
    _log("job: start")
    r = subprocess.run([sys.executable, "-m", "src.download.scheduler", "--once"],
                       capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
    _log(f"job: refresh exit {r.returncode} {tail[0][:120]}")
    if r.returncode == 1:
        _log("job: refresh FAILED (lock or error) — scoring proceeds on existing data")
    s = subprocess.run([sys.executable, "-m", "src.prospective.score", "--all"],
                       capture_output=True, text=True)
    for line in (s.stdout or "").strip().splitlines():
        _log(f"job: score | {line[:160]}")
    if s.returncode != 0:
        _log(f"job: SCORING FAILED (exit {s.returncode}) — inspect and re-run by hand")
        return 1
    _log("job: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
