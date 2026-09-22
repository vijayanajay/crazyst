"""Task 1.5 — normalizer: both delivery formats -> one `delivery` table in DuckDB.

    delivery(symbol, date, deliv_qty, deliv_per)

- MTO .DAT (2011→) parsed positionally per src/normalize/columns_mto.py; the file's own
  "Trade Date <...>" header line is validated against the filename date — a corrupt or
  mismatched file is refused (fail-at-end: every other file still loads, then the pass
  raises — one truncated download must not block the other ~3800, but must be loud).
- sec_bhavdata_full (2019-10→) via src/normalize/columns_sec.py (skipinitialspace).
- EQ series only (features are computed on the eligible EQ universe).
- idempotent + resumable (loaded dates skipped, cache enumerated before the done-snapshot
  — same backfill-race fix as bhav) + end-of-pass self-heal dedupe.

`python -m src.normalize.delivery` runs the self-check:
  synthetic: hand-built MTO + sec files (wrong-date MTO must be refused) -> exact table values
  live: normalizes the real cache, asserts no dupes, and the done-when check —
        bhav left-join delivery mismatch < 1% — plus cache-skip on a rerun.
"""
import copy
import glob
import os
import re
import sys
import tempfile
import zipfile
from datetime import date

import duckdb
import pandas as pd

from src.config import load
from src.normalize import columns_mto, columns_sec
from src.normalize.bhav import _self_heal  # shared dedupe+checkpoint over the same DB

DELIVERY_COLS = ["symbol", "date", "deliv_qty", "deliv_per"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS delivery (
    symbol VARCHAR, date DATE, deliv_qty BIGINT, deliv_per DOUBLE
)"""


def _read_mto(path: str, fname_date: date) -> pd.DataFrame:
    m = columns_mto
    with open(path, encoding="latin-1") as f:
        head = [f.readline() for _ in range(3)]
    hit = re.search(m.DATE_REGEX, head[m.DATE_LINE])
    if not hit:  # ~7 archive days have line 3 truncated to "rade Date" — fall back to the counts line
        c = re.search(m.COUNTS_DATE_RE, head[m.COUNTS_LINE])
        assert c, f"{path}: no Trade Date header line and no 10,MTO,<date> counts line found"
        hit = c
    content_date = pd.to_datetime(hit.group(1), format=(m.DATE_FORMAT if "Trade Date" in hit.group(0) else "%d%m%Y")).date()
    assert content_date == fname_date, \
        f"{path}: header says {content_date} but filename says {fname_date} — refusing"
    df = pd.read_csv(path, skiprows=m.SKIPROWS, header=None, names=m.POSITIONS,
                     encoding="latin-1")
    # Some files contain multiple settlement blocks (a <D> block re-followed by the
    # Trade Date + column-name header lines) — those text rows make record_type object-typed
    # strings, breaking an int comparison. Numeric coercion drops them and unifies the type.
    df["record_type"] = pd.to_numeric(df["record_type"], errors="coerce")
    df = df[df["record_type"] == m.RECORD_TYPE_KEEP]
    df = df[df["series"].isin(m.SERIES_KEEP)]
    df["deliv_qty"] = pd.to_numeric(df["deliv_qty"], errors="coerce").astype("Int64")
    df["deliv_per"] = pd.to_numeric(df["deliv_per"], errors="coerce")
    df["date"] = fname_date
    return df[DELIVERY_COLS].drop_duplicates(subset=["symbol", "date"], keep="first")


def _read_sec(path: str, fname_date: date) -> pd.DataFrame:
    m = columns_sec
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=m.COLS)
    df = df[df["series"].isin(m.SERIES_KEEP)]
    df["date"] = pd.to_datetime(df["date"], format=m.DATE_FORMAT).dt.date
    assert set(df["date"]) == {fname_date}, \
        f"{path}: content date(s) {set(map(str, df['date']))} != filename {fname_date} — refusing"
    df["deliv_qty"] = pd.to_numeric(df["deliv_qty"], errors="coerce").astype("Int64")
    df["deliv_per"] = pd.to_numeric(df["deliv_per"], errors="coerce")
    return df[DELIVERY_COLS].drop_duplicates(subset=["symbol", "date"], keep="first")


def _iter_cached(cfg: dict):
    """Yield (date, path, reader) for every cached delivery file."""
    root = cfg["paths"]["raw_delivery"]
    mto_dir = os.path.join(root, "mto")
    if os.path.isdir(mto_dir):
        for path in sorted(glob.glob(os.path.join(mto_dir, "*", "*", "*.DAT"))):
            name = os.path.basename(path)  # MTO_(0123)DD(4,5)MM(6,7)YYYY(8-11).DAT
            d = date(int(name[8:12]), int(name[6:8]), int(name[4:6]))
            yield d, path, _read_mto
    sec_dir = os.path.join(root, "sec_bhavdata_full")
    if os.path.isdir(sec_dir):
        for path in sorted(glob.glob(os.path.join(sec_dir, "*", "*", "*.csv"))):
            name = os.path.basename(path)  # sec_bhavdata_full_(0-17)DD(18,19)MM(20,21)YYYY(22-25).csv
            d = date(int(name[22:26]), int(name[20:22]), int(name[18:20]))
            yield d, path, _read_sec


def normalize(cfg: dict) -> dict:
    os.makedirs(os.path.dirname(cfg["paths"]["duckdb"]), exist_ok=True)
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        con.execute(SCHEMA)
        cached = list(_iter_cached(cfg))
        done = {r[0] for r in con.execute("SELECT DISTINCT date FROM delivery").fetchall()}
        stats = {"files": 0, "skipped": 0, "rows": 0, "loaded_paths": []}
        refused: list[str] = []
        for d, path, reader in cached:
            if d in done:
                stats["skipped"] += 1
                continue
            try:
                df = reader(path, d)
            except (AssertionError, ValueError) as e:
                refused.append(f"{path}: {e}")
                continue
            con.register("dview", df)
            con.execute(f"INSERT INTO delivery SELECT {', '.join(DELIVERY_COLS)} FROM dview")
            con.unregister("dview")
            done.add(d)
            stats["files"] += 1
            stats["rows"] += len(df)
            stats["loaded_paths"].append(path)
        _self_heal(con, table="delivery", keys=("symbol", "date"))
        if refused:
            raise AssertionError(
                f"{len(refused)} cached delivery file(s) failed validation — delete the corrupt "
                f"file(s) and re-download (backfill_all rerun heals them):\n  "
                + "\n  ".join(refused))
        return stats
    finally:
        con.close()


def _join_check(cfg: dict) -> float:
    """Done-when: for every date that HAS delivery data, bhav EQ rows must join < 1% missing.

    Restricted to dates present in `delivery` (not its min..max span) — the cached delivery
    span has huge holes while the backfill runs, and comparing against the whole span would
    fail on missing dates rather than on real symbol+date mismatches.
    """
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        total, missing = con.execute("""
            SELECT count(*), count(*) FILTER (WHERE d.symbol IS NULL)
            FROM bhav b
            LEFT JOIN delivery d
              ON d.symbol = b.symbol AND d.date = b.date
            WHERE b.series = 'EQ'
              AND b.date IN (SELECT DISTINCT date FROM delivery)
        """).fetchone()
    finally:
        con.close()
    pct = 100.0 * missing / total if total else 0.0
    print(f"join check: {missing:,}/{total:,} bhav EQ rows on delivery-dates lack a delivery "
          f"row ({pct:.2f}%)", flush=True)
    return pct


def _self_check() -> None:
    # ---- 1. synthetic: hand-built files -> exact values; wrong-date MTO refused ----
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["paths"]["raw_delivery"] = os.path.join(tmp, "delivery")
    cfg["paths"]["duckdb"] = os.path.join(tmp, "t.duckdb")
    mto_dir = os.path.join(cfg["paths"]["raw_delivery"], "mto", "2011", "01")
    sec_dir = os.path.join(cfg["paths"]["raw_delivery"], "sec_bhavdata_full", "2026", "08")
    os.makedirs(mto_dir); os.makedirs(sec_dir)

    mto_body = ("Security Wise Delivery Position\n"
                "10,MTO,03012011,1,1\n"
                "Trade Date <03-JAN-2011>,Settlement Type <N>,Settlement No <1>,Settlement Date <05-JAN-2011>\n"
                "Record Type,Sr No,Name of Security,Quantity Traded,Deliverable Quantity,% of Deliverable\n"
                "20,1,TESTA,EQ,1000,700,70.00\n"
                "20,2,TESTA,BE,50,10,20.00\n"
                "99,3,TESTIDX,EQ,10,5,50.00\n")
    p = os.path.join(mto_dir, "MTO_03012011.DAT")
    open(p, "w").write(mto_body)
    # (wrong-date file is created after normalize() below — it must not be in the scanned dir)

    sec_body = ("SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, "
                "LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, "
                "NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
                " TESTB, EQ, 03-Aug-2026, 1, 1, 1, 1, 1, 1, 1, 100, 1, 5, 45, 45.0\n")
    open(os.path.join(sec_dir, "sec_bhavdata_full_03082026.csv"), "w").write(sec_body)

    st = normalize(cfg)
    assert st["files"] == 2 and st["rows"] == 2, f"synthetic load wrong: {st}"  # 1 MTO EQ row + 1 sec row
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    row = con.execute("SELECT date, deliv_qty, deliv_per FROM delivery WHERE symbol='TESTA'").fetchone()
    assert row == (date(2011, 1, 3), 700, 70.0), f"MTO row wrong: {row}"  # BE row and index row excluded
    row = con.execute("SELECT date, deliv_qty, deliv_per FROM delivery WHERE symbol='TESTB'").fetchone()
    assert row == (date(2026, 8, 3), 45, 45.0), f"sec row wrong: {row}"
    con.close()
    # wrong-date MTO: filename says 04-Jan but content says 03-Jan -> direct refusal test
    p_bad = os.path.join(mto_dir, "MTO_04012011.DAT")
    open(p_bad, "w").write(mto_body)
    try:
        _read_mto(p_bad, date(2011, 1, 4))
        raise AssertionError("wrong-date MTO file should have been refused")
    except AssertionError as e:
        assert "refusing" in str(e), f"wrong error: {e}"
    os.remove(p_bad)
    print("synthetic check passed (MTO positional + sec padded CSV + wrong-date refusal)", flush=True)

    # ---- 2. live: normalize real cache, dupes check, join check, rerun skip proof ----
    real = load("quick")
    t0 = __import__("time").time()
    st1 = normalize(real)
    print(f"live normalize pass 1: {st1['files']} loaded, {st1['skipped']} skipped, "
          f"{st1['rows']} rows", flush=True)
    con = duckdb.connect(real["paths"]["duckdb"], read_only=True)
    n = con.execute("SELECT count(*) FROM (SELECT DISTINCT symbol, date FROM delivery)").fetchone()[0]
    total = con.execute("SELECT count(*) FROM delivery").fetchone()[0]
    con.close()
    assert n == total, f"duplicate keys in delivery: {total - n}"
    pct = _join_check(real)
    assert pct < 1.0, f"join mismatch {pct:.2f}% >= 1% (done-when fails)"
    st2 = normalize(real)
    stale = [p for p in st2["loaded_paths"] if os.path.getmtime(p) <= t0]
    assert not stale, f"idempotency violated: reload of pre-existing files: {stale}"
    print(f"rerun: {st2['files']} loaded, {st2['skipped']} skipped "
          f"({'all new since pass 1 (backfill running)' if st2['files'] else 'idempotent'})", flush=True)
    print("PASS: delivery normalizer synthetic + live checks (dupes, join <1%, idempotency)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
