"""Task 1.3 — delivery data downloader: legacy MTO (2011 → today) + sec_bhavdata_full (2019-10 → today).

Boundaries verified live:
- MTO:              https://archives.nseindia.com/archives/equities/mto/MTO_{DDMMYYYY}.DAT
                    (note the doubled "archives" path segment) — exists 2011-01-03 through today,
                    still published daily. Plain .DAT: 3 header lines, then
                    `20,<sr>,<SYMBOL>,<SERIES>,<qty_traded>,<deliv_qty>,<deliv_per>` rows
                    (record type 20 = equities; series column exists, 9xx rows are indices).
- sec_bhavdata_full: https://archives.nseindia.com/products/content/sec_bhavdata_full_{DDMMYYYY}.csv
                    — verified 404 for every 2012–2019 trading day probed; starts 2019-10-01.
                    Richer (adds delivery turnover + ISIN); becomes the sole source going forward.

Both share the cache/retry/atomic-write/sleep discipline (src/download/_http.py, kind="text").
Weekend skip + 404-as-holiday, same as bhavcopy. ponytail: 404 is assumed to mean
"non-trading day"; the 1.7 gap report is the safety net for any server-side hole.

`python -m src.download.delivery` runs the self-check: URL shapes, era bounds, one live MTO
month (2011-01, which also proves MTO is the pre-2020 source), one live recent month
(sec_bhavdata_full), per-source gap reporting, and the cache-skip proof.
"""
import calendar
import os
import sys
from datetime import date

import duckdb
import requests

from src.config import load
from src.download import _http
from src.normalize import panels

MTO_BASE = "https://archives.nseindia.com/archives/equities/mto"
SEC_BASE = "https://archives.nseindia.com/products/content"
SEC_FULL_FIRST_DAY = date(2019, 10, 1)  # verified: 2019-07/2019-10 boundary probed — 404 before Oct 2019


def mto_url(d: date) -> str:
    return f"{MTO_BASE}/MTO_{d:%d%m%Y}.DAT"


def sec_url(d: date) -> str:
    return f"{SEC_BASE}/sec_bhavdata_full_{d:%d%m%Y}.csv"


def _out_path(d: date, cfg: dict, source: str, ext: str) -> str:
    sub = {"mto": "mto", "sec_full": "sec_bhavdata_full"}[source]
    out_dir = os.path.join(cfg["paths"]["raw_delivery"], sub, f"{d.year}", f"{d.month:02d}")
    name = f"MTO_{d:%d%m%Y}.DAT" if source == "mto" else f"sec_bhavdata_full_{d:%d%m%Y}.csv"
    return os.path.join(out_dir, name)


def fetch_day(session: requests.Session, d: date, cfg: dict, source: str) -> str:
    """Fetch one day from 'mto' or 'sec_full'. Returns 'cached'|'downloaded'|'holiday'. Raises on persistent errors."""
    # Same as-of guard as bhavcopy UDiFF: the fetch-plan bound, not stored state (see there).
    if d > _http.asof_date(cfg.get("fetch_asof"), cfg):
        raise ValueError(f"{d} after the as-of bound {cfg.get('fetch_asof') or 'today/yesterday by cutoff'} — "
                         f"pass --date / fetch_asof to reach further, never guess")
    if source == "mto":
        url, ext = mto_url(d), "DAT"
    elif source == "sec_full":
        if d < SEC_FULL_FIRST_DAY:
            raise ValueError(f"{d} before sec_bhavdata_full start {SEC_FULL_FIRST_DAY}")
        url, ext = sec_url(d), "csv"
    else:
        raise ValueError(f"unknown source {source!r}")
    return _http.fetch(session, url, _out_path(d, cfg, source, ext), cfg, kind="text")


def _month_days(year: int, month: int, up_to: date | None, from_d: date | None):
    _, ndays = calendar.monthrange(year, month)
    for day in range(1, ndays + 1):
        d = date(year, month, day)
        if d.weekday() >= 5 or (up_to and d > up_to) or (from_d and d < from_d):
            continue
        yield d


def download_month(session: requests.Session, year: int, month: int, cfg: dict,
                   source: str, up_to: date | None = None, from_d: date | None = None) -> dict:
    # Self-bound to the as-of date like both bhavcopy month loops, so a caller iterating the
    # CURRENT month cannot walk into days fetch_day refuses (caught live by the daily refresh,
    # which had to know to pass up_to=asof while every other fetcher bounds itself).
    up_to = min([d for d in (up_to, _http.asof_date(cfg.get("fetch_asof"), cfg)) if d])
    summary = {"year": year, "month": month, "source": source, "downloaded": 0, "cached": 0, "holidays": []}
    for d in _month_days(year, month, up_to, from_d):
        status = fetch_day(session, d, cfg, source)
        if status == "holiday":
            summary["holidays"].append(d.isoformat())
        else:
            summary[status] += 1
        print(f"  {d}  {status}", flush=True)
    return summary


def gap_report(cfg: dict) -> str:
    """Per-source cached-month coverage report: expected weekday files vs cached, flags short months.

    Done-when ("gap report printed") without re-hitting NSE: reads the cache only.
    Short months are expected (delivery data has known missing stretches — BRD D2) and are
    flagged, not failed; the 1.7 validation report decides severity.
    """
    lines = []
    root = cfg["paths"]["raw_delivery"]
    for source, label in (("mto", "MTO"), ("sec_full", "sec_bhavdata_full")):
        src_dir = os.path.join(root, {"mto": "mto", "sec_full": "sec_bhavdata_full"}[source])
        if not os.path.isdir(src_dir):
            continue
        lines.append(f"{label}:")
        total_missing = 0
        for year in sorted(int(y) for y in os.listdir(src_dir)):
            ydir = os.path.join(src_dir, str(year))
            for month in sorted(os.listdir(ydir)):
                mdir = os.path.join(ydir, month)
                n = len([f for f in os.listdir(mdir) if f.endswith((".DAT", ".csv"))])
                _, ndays = calendar.monthrange(year, int(month))
                weekdays = sum(1 for day in range(1, ndays + 1)
                               if date(year, int(month), day).weekday() < 5)
                missing = weekdays - n
                total_missing += missing
                flag = "  <-- SHORT" if missing > 2 else ""
                lines.append(f"  {year}-{month}: {n}/{weekdays} weekday files ({missing} missing){flag}")
        lines.append(f"  total missing (before holiday subtraction): {total_missing}")
    return "\n".join(lines)


def _self_check() -> None:
    # 1. URL shapes against the live-verified patterns
    d = date(2011, 1, 3)
    assert mto_url(d) == f"{MTO_BASE}/MTO_03012011.DAT", f"got {mto_url(d)}"
    assert sec_url(d) == f"{SEC_BASE}/sec_bhavdata_full_03012011.csv", f"got {sec_url(d)}"

    # 2. era guard: sec_bhavdata_full refuses its pre-start era
    cfg = load("quick")
    try:
        fetch_day(requests.Session(), date(2019, 7, 1), cfg, "sec_full")
        raise AssertionError("2019-07 should be refused for sec_full")
    except ValueError:
        pass

    # 3. era guard: bhavcopy must exist for a delivery file to be usable later — sanity only
    from src.download.bhavcopy_old import FIRST_DAY as BHAV_FIRST
    assert BHAV_FIRST == date(2011, 1, 3), "delivery and bhavcopy eras should align at 2011-01-03"

    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        cfg["fetch_asof"] = panels.data_cutoff(con)   # the live bound: the stored bhav cutoff
    finally:
        con.close()
    with requests.Session() as s:
        # 4. live MTO month (2011-01): 21 weekdays (Jan 1 was a Saturday), 1 holiday (Jan 26 Republic Day).
        #    Live probe showed MTO_03012011.DAT exists; final count asserted against actual trading days.
        print("downloading MTO 2011-01 (live)...")
        m1 = download_month(s, 2011, 1, cfg, "mto")
        got = m1["downloaded"] + m1["cached"]
        assert got == 20, f"expected 20 MTO files for 2011-01 (21 weekdays - Jan 26 holiday), got {got}; 404s: {m1['holidays']}"
        assert "2011-01-26" in m1["holidays"], f"Jan 26 (Republic Day) should 404 as holiday: {m1['holidays']}"

        # 5. live sec_bhavdata_full month (2026-08): 21 weekdays, all trading days (verified in 1.2)
        print("downloading sec_bhavdata_full 2026-08 (live)...")
        m2 = download_month(s, 2026, 8, cfg, "sec_full")
        got = m2["downloaded"] + m2["cached"]
        assert got == 21, f"expected 21 sec_full files for 2026-08, got {got}; 404s: {m2['holidays']}"

        # 6. cache-skip proof on both sources
        r1 = download_month(s, 2011, 1, cfg, "mto")
        r2 = download_month(s, 2026, 8, cfg, "sec_full")
        assert r1["downloaded"] == 0 and r1["cached"] == 20, f"mto cache-skip violated: {r1}"
        assert r2["downloaded"] == 0 and r2["cached"] == 21, f"sec_full cache-skip violated: {r2}"

        # 7. gap report: reads cache only, prints per-month coverage
        print("\n" + gap_report(cfg))

    print("PASS: delivery URL/bounds checks + live MTO 2011-01 (20) + sec_full 2026-08 (21) + gap report")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
