"""Full historical backfill for both bhavcopy eras.

Runs two loops in one process (a single polite 2s-cadence session against NSE):
- old format: 2011-01 .. 2024-07 (stops at the Jul-5 boundary)
- UDiFF:      2024-07 (from the 8th) .. config end_date month

Skip-if-cached makes this idempotent — rerunning continues where it stopped.
After each month the progress line is flushed for `tail -f` friendliness.
No self-check of its own; each downloader module's check covers its era.
"""
import sys
import time
from datetime import date

import requests

from src.config import load
from src.download import _http
from src.download.bhavcopy_old import OLD_FORMAT_LAST_DAY, download_month as old_month
from src.download.bhavcopy_udiff import FIRST_DAY as UDIFF_FIRST, download_month as udiff_month


def months_between(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def main() -> int:
    cfg = load("quick")
    totals = {"downloaded": 0, "cached": 0, "holidays": 0}
    with requests.Session() as s:
        print(f"backfill start: old 2011-01..{OLD_FORMAT_LAST_DAY:%Y-%m}, "
              f"UDiFF {UDIFF_FIRST:%Y-%m}..{cfg['end_date'][:7]}", flush=True)
        for y, m in months_between(date(2011, 1, 1), OLD_FORMAT_LAST_DAY):
            up_to = OLD_FORMAT_LAST_DAY if (y, m) == (OLD_FORMAT_LAST_DAY.year, OLD_FORMAT_LAST_DAY.month) else None
            r = old_month(s, y, m, cfg, up_to=up_to)
            _add(totals, r)
            print(f"== old {y}-{m:02d}: +{r['downloaded']} new, {r['cached']} cached, "
                  f"{len(r['holidays'])} holidays | totals {totals}", flush=True)
        for y, m in months_between(UDIFF_FIRST, date.fromisoformat(cfg["end_date"])):
            from_d = UDIFF_FIRST if (y, m) == (UDIFF_FIRST.year, UDIFF_FIRST.month) else None
            r = udiff_month(s, y, m, cfg, from_d=from_d)
            _add(totals, r)
            print(f"== udiff {y}-{m:02d}: +{r['downloaded']} new, {r['cached']} cached, "
                  f"{len(r['holidays'])} holidays | totals {totals}", flush=True)
    print(f"DONE: {totals}", flush=True)
    return 0


def _add(totals: dict, r: dict) -> None:
    totals["downloaded"] += r["downloaded"]
    totals["cached"] += r["cached"]
    totals["holidays"] += len(r["holidays"])


if __name__ == "__main__":
    sys.exit(main())
