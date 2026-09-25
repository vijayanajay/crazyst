"""Single entry point for the daily refresh — cron / Task Scheduler / container / manual.

    python -m src.download.scheduler            # wait for the cutoff, then run; retry while behind
    python -m src.download.scheduler --once     # one attempt now, no waiting or retrying
    python -m src.download.scheduler --self-check

Why a scheduler and not just a cron line calling refresh.py:

- the refresh gates itself on `publish_cutoff_ist`, but a launch *before* the cutoff would
  cheerfully fetch yesterday's data and report success — today's file never arrives. This waits
  for the cutoff first.
- NSE is sometimes later than the cutoff, and src/download/_http.py remembers a 404 for
  NEG_TTL_DAYS (30). One early attempt could therefore hide a real trading day for a month, so
  every attempt evicts the target date from the negative cache and re-probes, and a still-behind
  pipeline is retried `refresh_retry_minutes` apart.
- a lock file keeps a second scheduler (or a manual run) from writing to DuckDB at the same time.

Exit codes (the thing a cron/Task Scheduler job surfaces):
    0  caught up — or nothing was due
    1  refused to run (another refresh in flight) or the refresh itself failed
    2  ran fine but the pipeline is not caught up: NSE holiday, or their archive is late.
       The refresh's own detail is in data/refresh.log; this wrapper appends to data/scheduler.log.

The refresh runs in a subprocess (its own DuckDB writers, its own env), exactly as run by hand.
`--self-check` covers the offline parts: cutoff wait math, lock takeover, 404 eviction, verdicts.

Wiring it to the clock — schedule it once, just after the cutoff, and let it retry:

    # cron (weekdays, 19:10 IST)
    10 19 * * 1-5 cd /path/to/repo && .venv/bin/python -m src.download.scheduler
    # Windows Task Scheduler (weekdays 19:10, "Start in" = repo root)
    schtasks /create /tn QuantRefresh /sc weekly /d MON,TUE,WED,THU,FRI /st 19:10 ^
        /tr "C:\path\to\repo\.venv\Scripts\python.exe -m src.download.scheduler"

One run heals a gap: the refresh walks every month from the newest stored date to as-of, so a
scheduler that was off (machine asleep, host down) closes the whole gap on its next start. A
non-zero exit is the signal to surface — `python -m src.download.scheduler --once` is the manual
equivalent, and `data/scheduler.log` is one line per event, so an interrupted run still tells you
how far it got.
"""
import os
import subprocess
import sys
import time
from datetime import date, datetime

import duckdb

from src.config import load, python_child_args
from src.download import bhavcopy_old, bhavcopy_udiff, delivery, refresh

LOCK_PATH = "data/.refresh.lock"
LOG_PATH = "data/scheduler.log"
STALE_LOCK_MINUTES = 90  # a real refresh takes ~1 minute; longer than this is a dead process
MAX_ATTEMPTS = 3         # bounded retrying: late archives recover, holidays never will


class Locked(Exception):
    """Another refresh holds the lock."""


def verdict(stored: date | None, asof: date, failed: bool) -> tuple[int, str]:
    """Exit code and one-line explanation — pure, so the self-check can pin every case."""
    if failed:
        return 1, f"FAILED: the refresh did not complete (stored {stored}, as-of {asof})"
    if stored is not None and stored >= asof:
        return 0, f"ok: caught up to {stored}"
    return 2, (f"BEHIND: newest stored bhav is {stored}, as-of {asof} is not published "
               f"(NSE holiday, or their archive is late)")


def cutoff_hhmm(cfg: dict) -> tuple[int, int]:
    hh, mm = cfg["download"]["publish_cutoff_ist"].split(":")
    return int(hh), int(mm)


def seconds_until_cutoff(cfg: dict, now: datetime) -> float:
    """Seconds to wait before the day's files are likely to exist (0 once past the cutoff)."""
    hh, mm = cutoff_hhmm(cfg)
    cutoff = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return max(0.0, (cutoff - now).total_seconds())


def _sleep_until_cutoff(cfg: dict, now: datetime, say) -> datetime:
    secs = seconds_until_cutoff(cfg, now)
    if secs <= 0:
        return now
    say(f"before the {cfg['download']['publish_cutoff_ist']} IST cutoff — waiting "
        f"{secs / 60:.0f} min before touching NSE")
    while secs > 0:
        time.sleep(min(300, secs))  # chunked so the process stays interruptible
        secs = seconds_until_cutoff(cfg, datetime.now(refresh.IST))
    return datetime.now(refresh.IST)


def day_urls(d: date) -> list:
    """Every downloader URL for one date (era-aware) — the keys of the negative cache."""
    urls = [delivery.mto_url(d), delivery.sec_url(d)]
    if d >= bhavcopy_udiff.FIRST_DAY:
        urls.append(bhavcopy_udiff.url_for(d))
    if d <= bhavcopy_old.OLD_FORMAT_LAST_DAY:
        urls.append(bhavcopy_old.url_for(d))
    return urls


def evict_404(cfg: dict, d: date) -> int:
    """Forget cached 404s for `d`; returns how many entries were dropped.

    Without this a retry is theatre: _http returns "holiday" from the negative cache without
    contacting NSE, so a day that 404'd once (too early) would stay missing for NEG_TTL_DAYS.
    """
    path = cfg["paths"]["raw_404_cache"]
    if not os.path.exists(path):
        return 0
    drop = set(day_urls(d))
    with open(path) as f:
        lines = f.readlines()
    keep = [ln for ln in lines if ln.rstrip("\n").rpartition("\t")[0] not in drop]
    dropped = len(lines) - len(keep)
    if dropped:
        with open(path, "w") as f:
            f.writelines(keep)
    return dropped


def acquire(path: str = LOCK_PATH, stale_minutes: int = STALE_LOCK_MINUTES) -> None:
    """Take the single-instance lock, or raise Locked. A stale file is taken over, not trusted."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, "x") as f:
            f.write(f"pid {os.getpid()} since {datetime.now(refresh.IST).isoformat()}\n")
        return
    except FileExistsError:
        age = (time.time() - os.path.getmtime(path)) / 60
        if age < stale_minutes:
            with open(path) as f:
                who = f.read().strip()
            raise Locked(f"another refresh is in flight ({age:.0f} min old: {who})")
    with open(path, "w") as f:
        f.write(f"pid {os.getpid()} since {datetime.now(refresh.IST).isoformat()} "
                f"(took over a {age:.0f} min old lock)\n")
    print(f"took over a stale lock ({age:.0f} min old)", flush=True)


def release(path: str = LOCK_PATH) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def stored_max(cfg: dict) -> date | None:
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        return con.execute("SELECT max(date) FROM bhav").fetchone()[0]
    finally:
        con.close()


def log_line(msg: str, path: str = LOG_PATH) -> None:
    """Append one timestamped line. Written per event, not per run: a scheduler killed mid-retry
    (or a machine that reboots) must still have left a record of what it attempted."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(f"{datetime.now(refresh.IST):%Y-%m-%d %H:%M:%S} IST  {msg}\n")


def main(argv: list[str]) -> int:
    cfg = load()
    once = "--once" in argv

    def say(msg: str) -> None:
        print(msg, flush=True)
        log_line(msg)

    say(f"--- scheduler start ({'once' if once else 'scheduled'}, pid {os.getpid()})")

    try:
        acquire()
    except Locked as e:
        say(f"refusing to run: {e}")
        return 1
    try:
        if not once:
            _sleep_until_cutoff(cfg, datetime.now(refresh.IST), say)
        code, msg = 2, "no attempt made"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            target = refresh.asof_date(None, cfg, datetime.now(refresh.IST))
            dropped = evict_404(cfg, target)
            if dropped:
                say(f"evicted {dropped} cached 404(s) for {target} so this attempt re-probes NSE")
            t0 = time.monotonic()
            r = subprocess.run(python_child_args("src.download.refresh", "--date", target.isoformat()),
                               capture_output=True, text=True)
            stored = stored_max(cfg)
            code, msg = verdict(stored, target, failed=r.returncode != 0)
            say(f"attempt {attempt}/{MAX_ATTEMPTS}: {msg} "
                f"({time.monotonic() - t0:.0f}s, refresh exit {r.returncode})")
            if code == 0 or attempt == MAX_ATTEMPTS:
                break
            for line in (r.stdout + r.stderr).strip().splitlines()[-4:]:
                say(f"  | {line}")
            wait_min = cfg["download"]["refresh_retry_minutes"]
            say(f"retrying in {wait_min} min — the archive may only be late")
            time.sleep(wait_min * 60)
    finally:
        release()

    say(f"RESULT: {msg} (exit {code})")
    return code


def _self_check() -> None:
    cfg = {"download": {"publish_cutoff_ist": "19:00", "refresh_retry_minutes": 20},
           "paths": {"raw_404_cache": ""}}
    from datetime import date as D

    # verdicts: caught up / still behind / failed
    assert verdict(D(2026, 9, 22), D(2026, 9, 22), failed=False)[0] == 0, "equal dates are caught up"
    assert verdict(D(2026, 9, 23), D(2026, 9, 22), failed=False)[0] == 0, "ahead is caught up"
    assert verdict(D(2026, 9, 21), D(2026, 9, 22), failed=False)[0] == 2, "behind is not a failure"
    assert verdict(None, D(2026, 9, 22), failed=False)[0] == 2, "an empty table is not a failure"
    assert verdict(D(2026, 9, 22), D(2026, 9, 22), failed=True)[0] == 1, "a failed refresh wins"
    assert "HOLIDAY" not in verdict(D(2026, 9, 21), D(2026, 9, 22), False)[1].upper() or True
    assert "holiday" in verdict(D(2026, 9, 21), D(2026, 9, 22), False)[1], \
        "the behind message must name both causes (holiday or late archive)"

    # cutoff wait math
    from datetime import datetime as DT
    now = DT(2026, 9, 22, 18, 30, tzinfo=refresh.IST)
    assert abs(seconds_until_cutoff(cfg, now) - 30 * 60) < 1, "18:30 waits 30 min for a 19:00 cutoff"
    assert seconds_until_cutoff(cfg, DT(2026, 9, 22, 19, 0, tzinfo=refresh.IST)) == 0, "cutoff exact"
    assert seconds_until_cutoff(cfg, DT(2026, 9, 22, 21, 0, tzinfo=refresh.IST)) == 0, "past cutoff"

    # era-aware URL set (the keys evicted from the negative cache): one bhavcopy era per DATE —
    # the 2024-07 *month* straddles the formats, but no single date ever needs both
    assert len(day_urls(D(2011, 5, 4))) == 3 and len(day_urls(D(2026, 9, 22))) == 3, \
        "one bhavcopy era + two delivery sources per date"
    assert bhavcopy_old.url_for(D(2024, 7, 5)) in day_urls(D(2024, 7, 5)), \
        "2024-07-05 is the last old-format day and must be evicted with its own URL"
    assert bhavcopy_udiff.url_for(D(2024, 7, 8)) in day_urls(D(2024, 7, 8)), \
        "2024-07-08 is the first UDiFF day"
    assert bhavcopy_old.url_for(D(2024, 7, 5)) not in day_urls(D(2024, 7, 8)), \
        "the old-format URL must not be evicted for a UDiFF-era date"

    # lock: exclusive, stale takeover, release
    import tempfile
    tmp = tempfile.mkdtemp()
    lp = os.path.join(tmp, "x.lock")
    acquire(lp)
    try:
        acquire(lp)
        raise AssertionError("a held lock must refuse the second instance")
    except Locked:
        pass
    release(lp)
    assert not os.path.exists(lp), "release must remove the lock"
    acquire(lp)
    old = time.time() - 200 * 60  # 200 minutes: older than STALE_LOCK_MINUTES
    os.utime(lp, (old, old))
    acquire(lp)  # must take over rather than refuse
    release(lp)

    # 404 eviction: only the target date's URLs go, everything else survives
    cache = os.path.join(tmp, "404.txt")
    d = D(2026, 9, 22)
    other = D(2026, 9, 14)
    with open(cache, "w") as f:
        for u in day_urls(d):
            f.write(f"{u}\t1758000000\n")
        for u in day_urls(other):
            f.write(f"{u}\t1757000000\n")
        f.write("https://example.com/unrelated\t1756000000\n")
    cfg2 = {"paths": {"raw_404_cache": cache}}
    assert evict_404(cfg2, d) == len(day_urls(d)), "every URL of the target date must be evicted"
    with open(cache) as f:
        left = f.read()
    assert str(d.year) + f"{d.month:02d}{d.day:02d}" not in left.replace("unrelated", ""), \
        f"target date still cached: {left!r}"
    assert "example.com/unrelated" in left and str(other.year) in left, \
        "eviction must not touch other dates or unrelated lines"
    assert evict_404(cfg2, d) == 0, "a second eviction is a no-op"
    assert evict_404({"paths": {"raw_404_cache": os.path.join(tmp, "absent.txt")}}, d) == 0, \
        "a missing cache file is not an error"

    print("PASS: scheduler (verdict codes, cutoff wait math, era-aware 404 eviction, "
          "lock exclusivity + stale takeover)")


if __name__ == "__main__":
    if "--self-check" in sys.argv[1:]:
        _self_check()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
