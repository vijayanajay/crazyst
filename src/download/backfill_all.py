"""Chained backfill + final normalize (run via nohup; survives no interactive session).

Order:
1. bhavcopy resume: old format (2011-01 -> 2024-07-05), then UDiFF (2024-07-08 -> end_date)
2. MTO delivery backfill (2011-01 -> end_date); sec_bhavdata_full is not backfilled — MTO
   covers the whole span. On overlapping dates both sources load and the dedupe keeps the
   first-loaded (MTO) rows — the delivery schema is identical either way, so the choice is
   immaterial (the docstring here used to claim sec_* preference, which the rowid dedupe
   does not implement — fixed after being caught in review).
3. final normalize of bhav + delivery (idempotent; absorbs everything cached)
4. stats printed and written to data/normalize_stats.txt

Skip-if-cached makes every stage resumable: rerun this script after any interruption.
"""
import os
import sys
from datetime import date

import requests

from src.config import load
from src.download._http import asof_date
from src.download.backfill_bhavcopy import months_between
from src.download.bhavcopy_old import OLD_FORMAT_LAST_DAY, download_month as old_month
from src.download.bhavcopy_udiff import FIRST_DAY as UDIFF_FIRST, download_month as udiff_month
from src.download.delivery import download_month as deliv_month
from src.normalize import bhav as norm_bhav
from src.normalize import delivery as norm_deliv

STATS_PATH = "data/normalize_stats.txt"
ROWS_PER_FILE_CAP = 4_000_000  # real files are ~2-3k rows; far above = wrong download


def _deliv_stats_guard(cfg: dict, stats: dict) -> None:
    n, nd = _delivery_counts(cfg)
    if nd and n / nd > ROWS_PER_FILE_CAP:
        raise AssertionError(f"delivery rows/date {n / nd:,.0f} exceeds cap {ROWS_PER_FILE_CAP:,} — wrong file in cache?")
    assert n >= 1_000_000, f"delivery table suspiciously small after full MTO backfill: {n:,} rows"


def _delivery_counts(cfg: dict):
    import duckdb
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        return con.execute("SELECT count(*), count(DISTINCT date) FROM delivery").fetchone()
    finally:
        con.close()


def main() -> int:
    cfg = load("quick")
    end = asof_date(None, cfg)   # the fetch-plan bound: the cutoff-gated as-of date
    totals = {"downloaded": 0, "cached": 0, "holidays": 0}
    with requests.Session() as s:
        # 1. bhavcopy, both eras (resumes where the previous run stopped)
        print(f"[1/3] bhavcopy resume: old 2011-01..{OLD_FORMAT_LAST_DAY:%Y-%m}, "
              f"UDiFF {UDIFF_FIRST:%Y-%m}..{end:%Y-%m}", flush=True)
        for y, m in months_between(date(2011, 1, 1), OLD_FORMAT_LAST_DAY):
            up_to = OLD_FORMAT_LAST_DAY if (y, m) == (OLD_FORMAT_LAST_DAY.year, OLD_FORMAT_LAST_DAY.month) else None
            r = old_month(s, y, m, cfg, up_to=up_to)
            totals["downloaded"] += r["downloaded"]; totals["holidays"] += len(r["holidays"])
            print(f"== old {y}-{m:02d}: +{r['downloaded']} | totals {totals}", flush=True)
        for y, m in months_between(UDIFF_FIRST, end):
            from_d = UDIFF_FIRST if (y, m) == (UDIFF_FIRST.year, UDIFF_FIRST.month) else None
            r = udiff_month(s, y, m, cfg, from_d=from_d)
            totals["downloaded"] += r["downloaded"]; totals["holidays"] += len(r["holidays"])
            print(f"== udiff {y}-{m:02d}: +{r['downloaded']} | totals {totals}", flush=True)

        # 2. MTO delivery, full span
        print("[2/3] MTO delivery backfill 2011-01..end", flush=True)
        for y, m in months_between(date(2011, 1, 1), end):
            r = deliv_month(s, y, m, cfg, "mto")
            totals["downloaded"] += r["downloaded"]; totals["holidays"] += len(r["holidays"])
            print(f"== mto {y}-{m:02d}: +{r['downloaded']} | totals {totals}", flush=True)

    # 3. final normalize + stats
    print("[3/3] final normalize", flush=True)
    st_b = norm_bhav.normalize(cfg)
    st_d = norm_deliv.normalize(cfg)
    n_d, nd_d = _delivery_counts(cfg)
    _deliv_stats_guard(cfg, st_d)

    import duckdb
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        bh = con.execute("SELECT count(*), count(DISTINCT date), min(date), max(date) FROM bhav").fetchone()
        dl = con.execute("SELECT count(*), count(DISTINCT date), min(date), max(date) FROM delivery").fetchone()
    finally:
        con.close()
    lines = [
        f"bhav:     {bh[0]:,} rows | {bh[1]:,} dates | {bh[2]} .. {bh[3]}",
        f"delivery: {dl[0]:,} rows | {dl[1]:,} dates | {dl[2]} .. {dl[3]}",
        f"(normalize this run: bhav +{st_b['files']} files/{st_b['rows']:,} rows, "
        f"delivery +{st_d['files']} files/{st_d['rows']:,} rows)",
    ]
    print("\n".join(lines), flush=True)
    os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
    with open(STATS_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("DONE: backfill_all complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
