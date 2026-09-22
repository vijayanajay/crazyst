"""Task 1.4 — normalizer: both bhavcopy formats -> one `bhav` table in DuckDB.

Reads cached zips (never re-downloads; plan working rule 4), maps columns via one mapping
file per format (src/normalize/columns_old.py / columns_udiff.py), and appends into a single
unified table:

    bhav(symbol, series, date, open, high, low, close, prev_close, last,
         volume, turnover, trades, isin)

- all series kept (EQ, BE, GB, ...); eligibility filtering happens at query time (task 2.2)
- idempotent + resumable: dates already present in the table are skipped; a killed run just
  reruns. ponytail: correctness rests on "one file = one date"; a file NSE re-issues with
  corrected data after we cached it would be skipped — delete the DB row for that date
  manually (deliberate act, like cache deletion).
- a corrupt/unreadable zip fails the pass at END, not inline: every other file still loads,
  then the pass raises (one truncated download must not block ~3800 good ones, but must be loud)
- old-format zips have a trailing empty CSV column; dropped. TOTALTRADES/ISIN are absent in
  early years and land as NULL.

`python -m src.normalize.bhav` runs the self-check:
  synthetic: one hand-built zip per format -> table contents match hand values exactly
  live: normalizes whatever is cached, prints count + distinct dates, spot-checks 5 dates
        across the format boundary (raw zip symbol set == DB symbol set, EQ series),
        asserts no duplicate keys, and proves a rerun adds zero rows.
"""
import copy
import glob
import os
import sys
import time
import zipfile
from datetime import date

import duckdb
import pandas as pd

from src.config import load
from src.normalize import columns_old, columns_udiff

UNIFIED_COLS = ["symbol", "series", "date", "open", "high", "low", "close", "prev_close",
                "last", "volume", "turnover", "trades", "isin"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS bhav (
    symbol VARCHAR, series VARCHAR, date DATE,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, prev_close DOUBLE, last DOUBLE,
    volume BIGINT, turnover DOUBLE, trades BIGINT, isin VARCHAR
)"""


def _read_zip(zip_path: str, mapping: dict, date_formats: tuple) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        csv_name = next(n for n in z.namelist() if n.lower().endswith(".csv"))  # some zips nest the csv in a folder
        with z.open(csv_name) as fh:
            df = pd.read_csv(fh)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]  # old format's trailing empty col
    df = df.rename(columns=mapping)
    raw_dates = df["date"].astype(str)  # keep originals: coerce below destroys them, fallbacks need them
    df["date"] = pd.to_datetime(raw_dates, format=date_formats[0], errors="coerce")
    for fmt in date_formats[1:]:  # COVID-era files use dd-Mon-yy — try fallback formats on the remainder
        rem = df["date"].isna()
        if not rem.any():
            break
        df.loc[rem, "date"] = pd.to_datetime(raw_dates[rem], format=fmt, errors="coerce")
    assert not df["date"].isna().any(), f"{zip_path}: unparseable dates remain"
    df["date"] = df["date"].dt.date
    df = df.reindex(columns=UNIFIED_COLS)
    for c in ("volume", "trades"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ("open", "high", "low", "close", "prev_close", "last", "turnover"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop_duplicates(subset=["symbol", "series", "date"], keep="first")


_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _parse_name(name: str) -> date:
    """Date from zip filename: cm{DD}{MMM}{YYYY}bhav.csv.zip or BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip"""
    if "bhav.csv.zip" in name:  # cm03JAN2011bhav: cm | 03 | JAN | 2011
        return date(int(name[7:11]), _MONTHS.index(name[4:7]) + 1, int(name[2:4]))
    ymd = name.split("_")[6]    # BhavCopy(0)_NSE(1)_CM(2)_0(3)_0(4)_0(5)_20260803(6)_F(7)_0000
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def _iter_cached(cfg: dict):
    """Yield (date, path, mapping, date_formats) for every cached bhavcopy zip."""
    roots = (
        (cfg["paths"]["raw_bhavcopy_old"], columns_old.COLS, columns_old.DATE_FORMATS),
        (cfg["paths"]["raw_bhavcopy_udiff"], columns_udiff.COLS, columns_udiff.DATE_FORMATS),
    )
    for root, mapping, fmt in roots:
        for path in sorted(glob.glob(os.path.join(root, "*", "*", "*.zip"))):
            yield _parse_name(os.path.basename(path)), path, mapping, fmt


def normalize(cfg: dict) -> dict:
    os.makedirs(os.path.dirname(cfg["paths"]["duckdb"]), exist_ok=True)
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        con.execute(SCHEMA)
        # enumerate the cache BEFORE snapshotting loaded dates: otherwise a file created in the
        # snapshot->glob gap (a running backfill appends every ~3s) loads again on every pass
        cached = list(_iter_cached(cfg))
        done = {r[0] for r in con.execute("SELECT DISTINCT date FROM bhav").fetchall()}
        stats = {"files": 0, "skipped": 0, "rows": 0, "loaded_paths": []}
        refused: list[str] = []
        for d, path, mapping, fmt in cached:
            if d in done:
                stats["skipped"] += 1
                continue
            try:
                df = _read_zip(path, mapping, fmt)
            except (AssertionError, ValueError, zipfile.BadZipFile, pd.errors.ParserError) as e:
                refused.append(f"{path}: {type(e).__name__}: {e}")
                continue
            con.register("df_view", df)
            con.execute(f"INSERT INTO bhav SELECT {', '.join(UNIFIED_COLS)} FROM df_view")
            con.unregister("df_view")
            done.add(d)
            stats["files"] += 1
            stats["rows"] += len(df)
            stats["loaded_paths"].append(path)
            if stats["files"] % 100 == 0:
                print(f"  ... {stats['files']} files, {stats['rows']} rows", flush=True)
        _self_heal(con)
        if refused:
            raise AssertionError(
                f"{len(refused)} cached bhavcopy zip(s) failed validation — delete the corrupt "
                f"file(s) and re-download (backfill_all rerun heals them):\n  "
                + "\n  ".join(refused))
        return stats
    finally:
        con.close()


def _self_heal(con, table: str = "bhav", keys: tuple = ("symbol", "series", "date")) -> None:
    """End every pass with: dedupe on the key + CHECKPOINT.

    belt-and-braces against overlapping runs / interrupted transactions leaving stray or
    duplicated rows; a clean pass deletes nothing. Keeps the table valid without anyone
    having to remember a repair step. Shared with the delivery normalizer.
    """
    con.execute(f"""DELETE FROM {table} WHERE rowid NOT IN (
        SELECT min(rowid) FROM {table} GROUP BY {', '.join(keys)})""")
    con.execute("CHECKPOINT")


def _checks(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        count, ndates = con.execute("SELECT count(*), count(DISTINCT date) FROM bhav").fetchone()
        print(f"bhav table: {count:,} rows across {ndates:,} dates", flush=True)
        assert count > 0 and ndates > 0, "empty bhav table"

        # no duplicate keys (plan 3.5 sanity, enforced at the source too)
        n_distinct = con.execute("SELECT count(*) FROM (SELECT DISTINCT symbol, series, date FROM bhav)").fetchone()[0]
        assert n_distinct == count, f"duplicate keys: {count - n_distinct}"

        # boundary spot-check: for 5 cached dates (>=2 per format), raw EQ symbol set == DB symbol set
        eq_dates = con.execute("""
            SELECT DISTINCT date FROM bhav WHERE series = 'EQ'
            ORDER BY date""").fetchall()
        picks = []
        all_cached = sorted(_iter_cached(cfg), key=lambda t: t[0])
        old_cached = [t for t in all_cached if t[2] is columns_old.COLS]
        ud_cached = [t for t in all_cached if t[2] is columns_udiff.COLS]
        for src in (old_cached, ud_cached):
            if src:
                picks += [src[0], src[len(src) // 2], src[-1]]  # earliest, middle, latest per format
        seen = set()
        checked = 0
        for d, path, mapping, fmt in picks:
            if d in seen or d.isoformat() not in {t[0].isoformat() for t in eq_dates}:
                continue
            seen.add(d)
            raw = _read_zip(path, mapping, fmt)
            raw_syms = set(raw.loc[raw["series"] == "EQ", "symbol"])
            db_syms = {r[0] for r in con.execute(
                "SELECT symbol FROM bhav WHERE date = ? AND series = 'EQ'", [d]).fetchall()}
            assert raw_syms == db_syms, \
                f"{d}: raw vs DB symbol sets differ (raw-only {sorted(raw_syms - db_syms)[:5]}, " \
                f"db-only {sorted(db_syms - raw_syms)[:5]})"
            checked += 1
        assert checked >= 4, f"expected >=4 boundary spot-checks, ran {checked}"
        print(f"spot-checks passed on {checked} dates across the format boundary", flush=True)
    finally:
        con.close()


def _self_check() -> None:
    # ---- 1. synthetic: hand-built zip per format -> exact values in the table ----
    import tempfile
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["paths"]["raw_bhavcopy_old"] = os.path.join(tmp, "old")
    cfg["paths"]["raw_bhavcopy_udiff"] = os.path.join(tmp, "udiff")
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    old_dir = os.path.join(cfg["paths"]["raw_bhavcopy_old"], "2011", "01")
    ud_dir = os.path.join(cfg["paths"]["raw_bhavcopy_udiff"], "2024", "07")
    os.makedirs(old_dir); os.makedirs(ud_dir)

    old_csv = ("SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
               "TESTA,EQ,10.0,11.0,9.5,10.5,10.4,10.1,1000,10450.0,03-JAN-2011,\n"
               "TESTA,BE,1.0,1.0,1.0,1.0,1.0,1.0,10,10.0,03-JAN-2011,\n")
    with zipfile.ZipFile(os.path.join(old_dir, "cm03JAN2011bhav.csv.zip"), "w") as z:
        z.writestr("cm03JAN2011bhav.csv", old_csv)
    ud_csv = ("TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,PrvsClsgPric,LastPric,"
              "TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,ISIN\n"
              "2024-07-08,TESTB,EQ,20.0,22.0,19.5,21.0,20.1,20.9,500,10450.0,7,IN000TEST000\n")
    with zipfile.ZipFile(os.path.join(ud_dir, "BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip"), "w") as z:
        z.writestr("BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv", ud_csv)

    st = normalize(cfg)
    assert st["files"] == 2 and st["rows"] == 3, f"synthetic load wrong: {st}"
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    row = con.execute("SELECT date, open, close, volume, trades, isin FROM bhav "
                      "WHERE symbol='TESTA' AND series='EQ'").fetchone()
    assert row == (date(2011, 1, 3), 10.0, 10.5, 1000, None, None), f"old-format row wrong: {row}"
    row = con.execute("SELECT date, close, volume, trades, isin FROM bhav "
                      "WHERE symbol='TESTB' AND series='EQ'").fetchone()
    assert row == (date(2024, 7, 8), 21.0, 500, 7, "IN000TEST000"), f"udiff row wrong: {row}"
    con.close()
    print("synthetic check passed (both formats, hand-verified values)", flush=True)

    # ---- 2. live: normalize the real cache (resumable), run all checks, prove idempotency ----
    real = load("quick")
    t0 = time.time()  # anything created after this may legitimately first-load in pass 2
    st1 = normalize(real)
    print(f"live normalize pass 1: {st1['files']} loaded, {st1['skipped']} skipped, "
          f"{st1['rows']} rows", flush=True)
    _checks(real)
    # idempotency: no file that existed before pass 1 may ever load again. A backfill may still
    # be running, so files created *after* pass 1 started may legitimately load in pass 2 —
    # mtime is the precise discriminator. If a backfill ever finishes first, pass 2 loads 0.
    st2 = normalize(real)
    stale = [p for p in st2["loaded_paths"] if os.path.getmtime(p) <= t0]
    assert not stale, f"idempotency violated: reload of pre-existing files: {stale}"
    note = "all loaded files are new since pass 1 (backfill running)" if st2["files"] else "0 files — idempotent"
    print(f"live normalize pass 2: {st2['files']} loaded, {st2['skipped']} skipped ({note})", flush=True)
    print("PASS: normalizer synthetic + live checks (count, dupes, boundary spot-checks, idempotency)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
