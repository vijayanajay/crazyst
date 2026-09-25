"""Task 1.2 — UDiFF bhavcopy downloader: daily zips, 2024-07-08 -> yesterday (config-bounded).

URL (verified live, GET + browser headers; bare HEAD gets 403):
    https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip
Span verified live: 2024-07-07 (Sunday) 404s, 2024-07-08 exists — exactly where cm-bhav 404s out.
- weekends skipped up front; market holidays fall out as 404s (recorded, never retried).
  ponytail: 404 is assumed to mean "non-trading day"; a server-side outage that 404s a
  real trading day would be silently accepted. The Phase 1.7 gap report is the safety net.
- same cache/retry/atomic-write/sleep discipline as 1.1, shared via src/download/_http.py
- after retries are exhausted the run aborts — missing data must be loud.

`python -m src.download.bhavcopy_udiff` runs the self-check: URL shape, era bounds, one live
recent month (Aug 2026: 21 weekdays, one holiday), and the cache-skip proof.
"""
import calendar
import os
import sys
from datetime import date, timedelta

import duckdb
import requests

from src.config import load
from src.download import _http
from src.download.bhavcopy_old import OLD_FORMAT_LAST_DAY
from src.normalize import panels

BASE = "https://archives.nseindia.com/content/cm"
FIRST_DAY = date(2024, 7, 8)  # verified live: cm05JUL2024bhav exists, cm08JUL2024bhav 404s


def url_for(d: date) -> str:
    return f"{BASE}/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"


def out_path_for(d: date, cfg: dict) -> str:
    out_dir = os.path.join(cfg["paths"]["raw_bhavcopy_udiff"], f"{d.year}", f"{d.month:02d}")
    return os.path.join(out_dir, f"BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip")


def _check_bounds(d: date, cfg: dict) -> None:
    """UDiFF-era bounds. The upper bound is the cutoff-gated as-of date (`--date` wins) — the
    fetch plan, not stored state: the downloaders must never refuse a day the plan asked for,
    and must never walk past it either (the refresh passes `--date asof` explicitly).
    """
    if d < FIRST_DAY:
        raise ValueError(f"{d} before UDiFF start {FIRST_DAY} (earlier dates are task 1.1, old format)")
    if d > _http.asof_date(cfg.get("fetch_asof"), cfg):
        raise ValueError(f"{d} after the as-of bound {cfg.get('fetch_asof') or 'today/yesterday by cutoff'} — "
                         f"pass --date / fetch_asof to reach further, never guess")


def fetch_day(session: requests.Session, d: date, cfg: dict) -> str:
    """Download one day's zip. Returns 'cached' | 'downloaded' | 'holiday'. Raises on persistent errors."""
    _check_bounds(d, cfg)
    return _http.fetch(session, url_for(d), out_path_for(d, cfg), cfg)


def download_month(session: requests.Session, year: int, month: int, cfg: dict, from_d: date | None = None) -> dict:
    summary = {"year": year, "month": month, "downloaded": 0, "cached": 0, "holidays": []}
    end_of_month = date(year, month, calendar.monthrange(year, month)[1])
    _, ndays = calendar.monthrange(year, month)
    for day in range(1, ndays + 1):
        d = date(year, month, day)
        if d.weekday() >= 5 or (from_d and d < from_d) or d > min(end_of_month, _http.asof_date(cfg.get("fetch_asof"), cfg)):
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
    u = url_for(date(2024, 7, 8))
    assert u == f"{BASE}/BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip", f"got {u}"

    # 2. era bounds: refuses both directions. The upper bound is the as-of fetch-plan bound:
    # an explicit fetch_asof pins it offline, and a day past it must be refused.
    cfg = load("quick")
    cfg["fetch_asof"] = "2026-09-22"
    try:
        _check_bounds(date(2024, 7, 5), cfg)
        raise AssertionError("2024-07-05 should be refused (old-format era)")
    except ValueError:
        pass
    try:
        _check_bounds(date.fromisoformat(cfg["fetch_asof"]) + timedelta(days=1), cfg)
        raise AssertionError("dates past the as-of bound should be refused")
    except ValueError:
        pass

    # 3. live check: one recent month + cache-skip proof. Aug 2026: 21 weekdays, all trading days —
    # live-verified (Ganesh Chaturthi falls in Sept 2026; the Aug-27 holiday was 2025's).
    # ponytail: holiday fixture from NSE's published list — the file-count assert is the real check.
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        cfg["fetch_asof"] = panels.data_cutoff(con)   # the live bound: the stored bhav cutoff
    finally:
        con.close()
    with requests.Session() as s:
        print("downloading 2026-08 (live)...")
        first = download_month(s, 2026, 8, cfg)
        got = first["downloaded"] + first["cached"]
        assert got == 21, f"expected 21 trading-day files for 2026-08, got {got}; 404s: {first['holidays']}"
        assert first["holidays"] == [], f"unexpected holiday set for 2026-08: {first['holidays']}"
        print("downloading 2026-08 again (cache-skip proof)...")
        second = download_month(s, 2026, 8, cfg)
        assert second["downloaded"] == 0 and second["cached"] == 21, \
            f"cache-skip violated: downloaded={second['downloaded']}, cached={second['cached']}"
        print("PASS: UDiFF URL/bounds checks + live 2026-08 (21 files, cache-skip verified)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
