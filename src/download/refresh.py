"""Daily refresh: fetch the day(s) since the last stored date, normalize, rebuild, verify.

    python -m src.download.refresh                     # routine run (waits for the cutoff)
    python -m src.download.refresh --date 2026-09-22   # catch-up / re-run for a specific day
    python -m src.download.refresh --no-verify         # skip the self-check gate
    python -m src.download.refresh --self-check        # offline checks of the scheduling logic

Steps:
 1. as-of date: today once past `download.publish_cutoff_ist` (IST), otherwise yesterday; `--date`
    wins. Before the cutoff the day's files usually do not exist yet, and a 404 is remembered for
    NEG_TTL_DAYS (30) by src/download/_http.py — so an early run waits instead of poisoning the
    day for a month.
 2. fetch every month between the oldest known date and as-of: both bhavcopy eras + MTO delivery.
    Cache-skip means a routine run is a few HTTP hits, and a week off is caught up in one run.
 3. normalize bhav + delivery (idempotent). The data cutoff needs no write: it IS the newest bhav
    date (panels.data_cutoff), read by every downstream stage straight from the database. The
    bhav date (not delivery's) is the cutoff because bhav is the price backbone; the delivery
    feed legitimately runs a day ahead and validate.report classifies that as informational.
 4. adj_close.refresh_recent() for adjusted closes: new days, plus a full re-fetch for any symbol
    whose adjustment basis moved.
 5. rebuild the derived tables: panels -> rank -> eligibility -> winners.
 6. verify with `python -m src.selfcheck`. It is stamped, so it runs in full exactly because the
    inputs moved; its gap report is the documented safety net for a trading day that NSE silently
    404s.

Exit code is non-zero if any step fails, so a scheduler surfaces the failure. This module is a
job, not a check: it is deliberately absent from src/selfcheck.py's registry (that suite must stay
offline and side-effect-free apart from rebuildable tables).
"""
import copy
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone

import duckdb
import requests

from src.config import load
from src.download._http import asof_date  # shared by every fetch-plan caller (re-exported)
from src.download.backfill_bhavcopy import months_between
from src.download.bhavcopy_old import OLD_FORMAT_LAST_DAY, download_month as old_month
from src.download.bhavcopy_udiff import FIRST_DAY as UDIFF_FIRST, download_month as udiff_month
from src.download.delivery import download_month as deliv_month
from src.normalize import adj_close, panels
from src.normalize import bhav as norm_bhav
from src.normalize import delivery as norm_deliv
from src.universe import eligibility, rank, winners

IST = timezone(timedelta(hours=5, minutes=30))
ERA_LAST = (OLD_FORMAT_LAST_DAY.year, OLD_FORMAT_LAST_DAY.month)  # 2024-07 straddles the two eras


def months_to_check(oldest_known: date, asof: date) -> list:
    """Months from `oldest_known` through as-of; as-of's own month when nothing is older."""
    if asof < oldest_known:
        return [(asof.year, asof.month)]
    return list(months_between(oldest_known, asof))  # generator -> list (the self-check pins this)


def era_calls(y: int, m: int) -> list:
    """Which bhavcopy format(s) a month needs: the 2024-07 boundary month needs both."""
    if (y, m) < ERA_LAST:
        return ["old"]
    if (y, m) == ERA_LAST:
        return ["old", "udiff"]
    return ["udiff"]


def _counts(cfg: dict) -> dict:
    """{table: (rows, max date)} for the three source tables."""
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        out = {}
        for table in ("bhav", "delivery", "adj_close"):
            try:
                out[table] = con.execute(f"SELECT count(*), max(date) FROM {table}").fetchone()
            except duckdb.Error:
                out[table] = (0, None)
        return out
    finally:
        con.close()


def _fetch_month(s: requests.Session, y: int, m: int, work: dict, asof: date) -> dict:
    """Fetch one month's bhavcopy (era-aware) + MTO delivery; returns downloaded/holiday counts."""
    got = {"downloaded": 0, "holidays": []}
    for era in era_calls(y, m):
        if era == "old":
            cap = min([d for d in (OLD_FORMAT_LAST_DAY, asof) if d])
            r = old_month(s, y, m, work, up_to=cap)
        else:
            from_d = UDIFF_FIRST if (y, m) == (UDIFF_FIRST.year, UDIFF_FIRST.month) else None
            r = udiff_month(s, y, m, work, from_d=from_d)
        got["downloaded"] += r["downloaded"]
        got["holidays"] += r["holidays"]
    d = deliv_month(s, y, m, work, "mto")
    got["downloaded"] += d["downloaded"]
    got["holidays"] += d["holidays"]
    return got


def main(argv: list[str]) -> int:
    cfg = load()
    override = argv[argv.index("--date") + 1] if "--date" in argv else None
    verify = "--no-verify" not in argv
    t0 = time.monotonic()
    lines: list[str] = []

    def say(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    before = _counts(cfg)
    asof = asof_date(override, cfg, datetime.now(IST))
    say(f"refresh as of {asof} | stored: bhav {before['bhav'][1]} ({before['bhav'][0]:,} rows), "
        f"delivery {before['delivery'][1]}, adj_close {before['adj_close'][1]}")

    work = copy.deepcopy(cfg)
    work["fetch_asof"] = asof.isoformat()  # the fetch-plan bound the downloaders honor
                                           # (_http.asof_date); the stored cutoff stays the bhav max date
    known = [d for d in (before["bhav"][1], before["delivery"][1]) if d]
    oldest = min(known) if known else asof
    months = months_to_check(oldest, asof)
    say(f"fetch plan: {len(months)} month(s) {months[0][0]}-{months[0][1]:02d} .. "
        f"{months[-1][0]}-{months[-1][1]:02d}")
    with requests.Session() as s:
        for y, m in months:
            r = _fetch_month(s, y, m, work, asof)
            say(f"  {y}-{m:02d}: +{r['downloaded']} files, {len(r['holidays'])} non-trading day(s)")

    st_b = norm_bhav.normalize(cfg)
    st_d = norm_deliv.normalize(cfg)
    say(f"normalize: bhav +{st_b['rows']:,} rows / {st_b['files']} files, "
        f"delivery +{st_d['rows']:,} rows / {st_d['files']} files")

    after = _counts(cfg)
    if not after["bhav"][1] or after["bhav"][1] < before["bhav"][1]:
        raise AssertionError(f"normalize shrank bhav: {before['bhav'][1]} -> {after['bhav'][1]}")
    assert after["bhav"][1] <= asof, f"bhav holds {after['bhav'][1]}, past as-of {asof}"
    say(f"bhav now {after['bhav'][1]} ({after['bhav'][0]:,} rows), "
        f"delivery now {after['delivery'][1]} ({after['delivery'][0]:,} rows) — "
        f"the cutoff downstream stages read is that bhav max date (panels.data_cutoff)")

    adj = adj_close.refresh_recent(cfg)
    agree = ("n/a (too few pairs)" if adj["agree"] is None or adj["pairs"] < 50
             else f"{adj['agree']:.1%} on {adj['pairs']:,} pairs")
    say(f"adj_close: +{adj['rows']:,} rows, {adj['symbols']:,} symbols touched, "
        f"{adj['replaced']:,} rows replaced by full re-fetch, raw-close agreement {agree}")
    if adj["traded"]:
        priced = adj["traded"] - adj["missing"]
        say(f"  newest NSE day {adj['newest']}: {priced:,}/{adj['traded']:,} traded symbols priced "
            f"({adj['missing']:,} missing)")
        if adj["missing"] > 0.01 * adj["traded"]:
            say(f"  NOTE: {adj['missing']:,} symbols have no settled adjusted close for "
                f"{adj['newest']} yet — Yahoo publishes later than the NSE close and serves a "
                f"placeholder row (Close and Adj Close both NaN, refused by design); they stay "
                f"queued and the next run retries them")

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        # False on a no-op run (nothing moved, the panel stamp is still valid) — a second refresh
        # the same day must be harmless, not an error.
        rebuilt = panels.ensure(con, cfg)
        r = rank.build(con, cfg)
        e = eligibility.build(con, cfg)
        w = winners.build(con, cfg)
    finally:
        con.close()
    say(f"derived: panels {'rebuilt' if rebuilt else 'already current'}, "
        f"universe_rank {r['rows']:,} rows / {r['months']} months, "
        f"eligible {e['rows']:,}, winners {w['winners']:,} over {w['months']} months")

    verdict = "skipped (--no-verify)"
    code = 0
    if verify:
        v = subprocess.run([sys.executable, "-m", "src.selfcheck"], capture_output=True, text=True)
        tail = (v.stdout + v.stderr).strip().splitlines()
        verdict = tail[-1] if tail else "(no output)"
        code = v.returncode
        say(f"self-check: {verdict}")
        if code != 0:
            for line in tail[-8:]:
                say(f"  | {line}")

    say(f"{'DONE' if code == 0 else 'FAILED'}: refresh in {time.monotonic() - t0:.1f}s")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(f"\n=== {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST "
                f"({'ok' if code == 0 else 'FAILED'}, {time.monotonic() - t0:.1f}s)\n")
        f.write("\n".join(lines) + "\n")
    return code


def _self_check() -> None:
    """Offline checks of the scheduling logic — the parts a wrong clock or a stale file could ruin."""
    from datetime import datetime as dt
    cfg = {"download": {"publish_cutoff_ist": "19:00"}}
    before = dt(2026, 9, 22, 18, 30, tzinfo=IST)
    after = dt(2026, 9, 22, 19, 30, tzinfo=IST)
    assert asof_date(None, cfg, before) == date(2026, 9, 21), \
        "before the cutoff the newest safe date is yesterday, not today"
    assert asof_date(None, cfg, after) == date(2026, 9, 22), "after the cutoff today's files exist"
    assert asof_date("2026-09-15", cfg, after) == date(2026, 9, 15), "--date must win"
    try:
        asof_date("2026-09-23", cfg, after)
        raise AssertionError("a future --date must be refused")
    except AssertionError as e:
        assert "future" in str(e), f"wrong failure for a future date: {e}"

    assert months_to_check(date(2026, 8, 1), date(2026, 9, 22)) == [(2026, 8), (2026, 9)], \
        "a gap must plan every month in between"
    assert months_to_check(date(2026, 9, 22), date(2026, 9, 22)) == [(2026, 9)], \
        "nothing older than as-of must plan only as-of's month"
    assert months_to_check(date(2026, 10, 1), date(2026, 9, 22)) == [(2026, 9)], \
        "as-of older than the stored data must not plan a backwards range"

    assert era_calls(2011, 1) == ["old"] and era_calls(2026, 9) == ["udiff"], "era dispatch broke"
    assert era_calls(2024, 7) == ["old", "udiff"], \
        "the 2024-07 boundary month spans both formats and must fetch both"

    print("PASS: refresh scheduling (cutoff gating, --date, month plan, era boundary)")


if __name__ == "__main__":
    if "--self-check" in sys.argv[1:]:
        _self_check()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
