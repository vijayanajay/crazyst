"""Task 1.1 — old-format bhavcopy downloader: monthly archive zips, 2011-01-03 -> 2024-07-05.

URL (verified live, GET + browser headers; bare HEAD gets 403):
    {BASE}/{YYYY}/{MMM-UPPER}/cm{DD}{MMM-UPPER}{YYYY}bhav.csv.zip
- weekends skipped up front; market holidays fall out as 404s (recorded, never retried).
  ponytail: 404 is assumed to mean "non-trading day"; a server-side outage that 404s a
  real trading day would be silently accepted. The Phase 1.7 gap report (per-symbol gap
  counts) is the safety net that would surface such a hole.
- cache/retry/atomic-write/sleep discipline lives in src/download/_http.py
- after retries are exhausted the run aborts — missing data must be loud.

`python -m src.download.bhavcopy_old` runs the self-check: URL shape, holiday math, and one
live month (Jan 2024, 21 trading days) including the cache-skip proof.
"""
import calendar
import os
import sys
from datetime import date

import requests

from src.config import load
from src.download import _http

BASE = "https://archives.nseindia.com/content/historical/EQUITIES"
OLD_FORMAT_LAST_DAY = date(2024, 7, 5)   # verified: cm05JUL2024 exists, cm08JUL2024 404s (UDiFF takes over, task 1.2)
FIRST_DAY = date(2011, 1, 3)


def url_for(d: date) -> str:
    mmm = calendar.month_abbr[d.month].upper()
    return f"{BASE}/{d.year}/{mmm}/cm{d.day:02d}{mmm}{d.year}bhav.csv.zip"


def expected_trading_days(year: int, month: int, holidays: set[int]) -> int:
    """Weekdays in the month minus the holiday set (downloader never hardcodes this for real runs)."""
    _, ndays = calendar.monthrange(year, month)
    return sum(
        1 for day in range(1, ndays + 1)
        if date(year, month, day).weekday() < 5 and day not in holidays
    )


def _check_bounds(d: date) -> None:
    if not (FIRST_DAY <= d <= OLD_FORMAT_LAST_DAY):
        raise ValueError(
            f"{d} outside old-format span {FIRST_DAY}..{OLD_FORMAT_LAST_DAY} "
            f"(later dates are task 1.2, UDiFF format)"
        )


def fetch_day(session: requests.Session, d: date, cfg: dict) -> str:
    """Download one day's zip. Returns 'cached' | 'downloaded' | 'holiday'. Raises on persistent errors."""
    _check_bounds(d)
    mmm = calendar.month_abbr[d.month].upper()
    out_dir = os.path.join(cfg["paths"]["raw_bhavcopy_old"], f"{d.year}", f"{d.month:02d}")
    out_path = os.path.join(out_dir, f"cm{d.day:02d}{mmm}{d.year}bhav.csv.zip")
    return _http.fetch(session, url_for(d), out_path, cfg)


def download_month(session: requests.Session, year: int, month: int, cfg: dict, up_to: date | None = None) -> dict:
    # Self-bound to the as-of date like the UDiFF loop, so no caller can walk into a day fetch_day
    # refuses by iterating the current month without an explicit up_to.
    up_to = min([d for d in (up_to, _http.asof_date(cfg.get("fetch_asof"), cfg)) if d])
    summary = {"year": year, "month": month, "downloaded": 0, "cached": 0, "holidays": []}
    _, ndays = calendar.monthrange(year, month)
    for day in range(1, ndays + 1):
        d = date(year, month, day)
        if d.weekday() >= 5 or (up_to and d > up_to):
            continue
        status = fetch_day(session, d, cfg)
        if status == "holiday":
            summary["holidays"].append(d.isoformat())
        else:
            summary[status] += 1
        print(f"  {d}  {status}", flush=True)
    return summary


def _self_check() -> None:
    # 1. URL shape against the live-verified pattern
    u = url_for(date(2011, 1, 3))
    assert u == f"{BASE}/2011/JAN/cm03JAN2011bhav.csv.zip", f"got {u}"

    # 2. holiday math: Jan 2024 has 23 weekdays; NSE holidays were Jan 22 (Ram Mandir) and Jan 26 (Republic Day).
    # Live-verified: NSE was OPEN on Jan 1 (New Year's Day is not an NSE holiday).
    assert expected_trading_days(2024, 1, set()) == 23, "weekday count drifted"
    jan24_holidays = {22, 26}  # ponytail: check fixture from NSE's published 2024 list, not a downloader input
    assert expected_trading_days(2024, 1, jan24_holidays) == 21, "holiday subtraction wrong"

    # 3. boundary guard: old-format era only
    try:
        _check_bounds(date(2024, 7, 8))
        raise AssertionError("2024-07-08 should be refused (UDiFF era)")
    except ValueError:
        pass

    # 4. live check: one month, then rerun for the cache-skip proof
    cfg = load("quick")
    with requests.Session() as s:
        print("downloading 2024-01 (live)...")
        first = download_month(s, 2024, 1, cfg)
        got = first["downloaded"] + first["cached"]
        assert got == 21, f"expected 21 trading-day files for 2024-01 (23 weekdays - 2 holidays), got {got}; 404s: {first['holidays']}"
        assert set(first["holidays"]) == {c.isoformat() for c in (date(2024, 1, 22), date(2024, 1, 26))}, \
            f"404'd days do not match the known Jan-2024 holidays: {first['holidays']}"
        print(f"downloading 2024-01 again (cache-skip proof)...")
        second = download_month(s, 2024, 1, cfg)
        assert second["downloaded"] == 0 and second["cached"] == 21, \
            f"cache-skip violated: downloaded={second['downloaded']}, cached={second['cached']}"
        print("PASS: downloader URL/holiday/boundary checks + live 2024-01 (21 files, cache-skip verified)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
