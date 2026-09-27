"""Sourced Nifty TRI series — the §11 benchmark (Nifty 500) + large-cap reference (Nifty 200).

Source: niftyindices.com (NSE Indices Ltd) historical-data site. The total-return
endpoint is POST https://niftyindices.com/BackPage/getTotalReturnIndexString with
{"cinfo": "{'name':'NIFTY 500','startDate':'dd-Mon-yyyy','endDate':'dd-Mon-yyyy',
'indexName':'Nifty 500'}"} — the payload shape is IISLComponet.js's, which builds it
as a STRING inside cinfo (single quotes), JSON.stringify'd around it; the CDN host
405s POSTs, so it goes to the app domain. The site limits each call to <=365 days
(IISLComponet.js alert "not more than 1 Year"); chunks are calendar years, the
current year bounded by the bhav data cutoff. NIFTY 500 and NIFTY 200 are verified
live (2011 -> today); pre-~2020 NTR_Value is "-", stored NULL.

Discipline (src/download/_http.py conventions, adapted to a JSON API):
- raw cache: one JSON response file per (index, year) chunk under paths.raw_nifty_tri
  (per-index subdirs nifty500/ nifty200/) — a chunk is re-fetched only when missing or
  stale, so reruns are a few hits and history is never re-pulled (plan working rule 4).
- session: the POST works only with a seeded cookie (GET the historical-data page
  first) and browser-like headers; polite sleep between hits from download config.
- the duckdb table index_tri is DERIVED from the raw cache on every run (parse is
  cheap, the raw file is the source of truth, the table is trivially idempotent).
  The pre-200 flat layout (TRI_{year}.json in the cache root) is migrated into the
  subdirs on fetch — the rows' own "Index Name" identifies the file.

`python -m src.download.nifty_tri` runs the self-check: offline parse/parse-edge
checks, then the live fetch (both indices), the cache-skip proof, the migration
check, and the index_tri round-trip against the bhav session calendar.
"""
import json
import os
import sys
import time
from datetime import date, datetime

import duckdb
import requests

from src.config import load
from src.download import _http
from src.normalize import panels

PAGE_URL = "https://niftyindices.com/resources/historical-data"
POST_URL = "https://niftyindices.com/BackPage/getTotalReturnIndexString"
INDICES = {                    # BRD §11: benchmark + the large-cap reference, both verified
    "NIFTY 500": {"display": "Nifty 500", "slug": "nifty500"},
    "NIFTY 200": {"display": "Nifty 200", "slug": "nifty200"},
}
_DISPLAY_TO_API = {info["display"]: api for api, info in INDICES.items()}
FIRST_YEAR = 2011             # probed: 01-Jan-2011 returns rows for both indices
SCHEMA = """CREATE TABLE IF NOT EXISTS index_tri (
    index_name VARCHAR, date DATE, tri DOUBLE, ntr DOUBLE)"""


def chunk_path(year: int, cfg: dict, api_name: str) -> str:
    return os.path.join(cfg["paths"]["raw_nifty_tri"], INDICES[api_name]["slug"],
                        f"TRI_{year}.json")


def _chunk_window(year: int, asof: date) -> tuple[date, date]:
    """The <=1yr window for one year chunk; the current year ends at the data cutoff."""
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), asof)
    assert (end - start).days <= 366, f"chunk {year} exceeds the API's 1-year limit"
    return start, end


def _migrate_legacy(cfg: dict) -> None:
    """Pre-200 layout: TRI_{year}.json flat in the cache root. Move each into its index's
    subdir (the rows' own Index Name identifies it). A file whose destination exists is
    dropped — the subdir copy is the maintained one (the legacy file was fetched once,
    frozen history; the subdir one carries the current-year refreshes)."""
    root = cfg["paths"]["raw_nifty_tri"]
    if not os.path.isdir(root):
        return
    for name in sorted(os.listdir(root)):
        if not (name.startswith("TRI_") and name.endswith(".json")):
            continue
        src = os.path.join(root, name)
        rows = json.load(open(src, encoding="utf-8"))
        api = _DISPLAY_TO_API.get(rows[0]["Index Name"] if rows else None)
        assert api, f"legacy chunk {src}: rows carry no known Index Name"
        dest = chunk_path(int(name[4:-5]), cfg, api)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            os.remove(src)
        else:
            os.replace(src, dest)  # atomic, like every cache write


def _post_chunk(session: requests.Session, year: int, asof: date, cfg: dict,
                api_name: str) -> str:
    """POST one chunk, validate, write the raw cache atomically. Returns 'downloaded'.

    An empty body ([] = no rows in range) is cached too — the negative proof that this
    year simply has no data, so a rerun doesn't re-POST it.
    """
    display = INDICES[api_name]["display"]
    start, end = _chunk_window(year, asof)
    cinfo = ("{'name':'" + api_name + "','startDate':'" + f"{start:%d-%b-%Y}"
             + "','endDate':'" + f"{end:%d-%b-%Y}" + "','indexName':'" + display + "'}")
    headers = {"Content-Type": "application/json; charset=utf-8",
               "X-Requested-With": "XMLHttpRequest",
               "Origin": "https://niftyindices.com",
               "Referer": PAGE_URL,
               "User-Agent": _http.HEADERS["User-Agent"],
               "Accept-Language": _http.HEADERS["Accept-Language"]}
    attempts = cfg["download"]["retry_attempts"]  # linear retries like _http.fetch; 403/5xx transient
    for attempt in range(1, attempts + 1):
        try:
            r = session.post(POST_URL, data=json.dumps({"cinfo": cinfo}),
                             headers=headers, timeout=(10, 90))
            r.raise_for_status()
            body = r.json()
            rows = json.loads(body["d"]) if isinstance(body, dict) and "d" in body else body
            assert isinstance(rows, list), f"unexpected TRI payload shape: {str(body)[:120]}"
            # the API serves both case variants of the display name in row payloads
            assert {str(r.get("Index Name", "")).upper() for r in rows} <= {display.upper()}, \
                f"{api_name}: response rows are not {display}"
            out = chunk_path(year, cfg, api_name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            part = out + ".part"
            with open(part, "w", encoding="utf-8") as f:
                json.dump(rows, f)
            os.replace(part, out)  # atomic, like _http.fetch
            return "downloaded"
        except Exception as e:
            if attempt == attempts:
                raise IOError(f"TRI chunk {api_name} {year}: "
                              f"giving up after {attempts} attempts: {e}") from e
    raise AssertionError("unreachable")


def parse_chunk(path: str) -> list[tuple]:
    """Raw JSON chunk -> sorted (date, tri, ntr) tuples. Rows come newest-first."""
    rows = json.load(open(path, encoding="utf-8"))
    out = []
    for r in rows:
        d = datetime.strptime(r["Date"], "%d %b %Y").date()
        tri = float(r["TotalReturnsIndex"].replace(",", ""))
        ntr = r.get("NTR_Value")
        ntr = float(ntr.replace(",", "")) if ntr not in (None, "", "-") else None
        out.append((d, tri, ntr))
    out.sort()
    dates = [d for d, _, _ in out]
    assert len(dates) == len(set(dates)), f"{path}: duplicate dates"
    assert all(tri > 0 for _, tri, _ in out), f"{path}: non-positive TRI"
    return out


def _asof(cfg: dict) -> date:
    """The fetch bound: the stored bhav cutoff (a str from panels), coerced to a date."""
    return date.fromisoformat(str(panels.data_cutoff(
        duckdb.connect(cfg["paths"]["duckdb"], read_only=True))))


def fetch_chunks(cfg: dict, asof: date | None = None) -> dict:
    """Fetch every (index, year) chunk 2011..asof not cached or stale; rebuild index_tri."""
    asof = asof or _asof(cfg)
    _migrate_legacy(cfg)
    summary = {"downloaded": 0, "cached": 0, "refreshed": 0}
    with requests.Session() as session:
        session.headers.update({"User-Agent": _http.HEADERS["User-Agent"],
                                "Accept-Language": _http.HEADERS["Accept-Language"]})
        r = session.get(PAGE_URL, timeout=30)  # seed the session cookie
        assert r.status_code == 200, f"TRI: page GET {r.status_code} (session seed failed)"
        for api_name in INDICES:
            for year in range(FIRST_YEAR, asof.year + 1):
                path = chunk_path(year, cfg, api_name)
                if os.path.exists(path):
                    if year < asof.year:
                        summary["cached"] += 1       # a past year is complete forever
                        continue
                    # The current year must cover as-of; a stale chunk re-POSTs (one wasted
                    # request at most on a non-session day — the index shares the bhav calendar).
                    if max(d for d, _, _ in parse_chunk(path)) >= asof:
                        summary["cached"] += 1
                        continue
                    summary["refreshed"] += 1
                time.sleep(cfg["download"]["sleep_seconds"])  # polite between hits, as every downloader
                _post_chunk(session, year, asof, cfg, api_name)
                summary["downloaded"] += 1
    rebuild_table(cfg)
    return summary


def rebuild_table(cfg: dict) -> int:
    """index_tri <- every cached chunk (both indices). The raw cache is the source of
    truth, so the table is dropped and rebuilt — a schema change self-heals here."""
    rows: list[tuple] = []
    root = cfg["paths"]["raw_nifty_tri"]
    if os.path.isdir(root):
        for slug in sorted(INDICES[api]["slug"] for api in INDICES):
            subdir = os.path.join(root, slug)
            if not os.path.isdir(subdir):
                continue
            api = next(a for a, info in INDICES.items() if info["slug"] == slug)
            for name in sorted(os.listdir(subdir)):
                if name.endswith(".json"):
                    rows.extend((api, d, tri, ntr) for d, tri, ntr
                                in parse_chunk(os.path.join(subdir, name)))
    rows.sort()
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        con.execute("DROP TABLE IF EXISTS index_tri")
        con.execute(SCHEMA)
        if rows:
            con.executemany("INSERT INTO index_tri VALUES (?, ?, ?, ?)", rows)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return len(rows)


def _month_marks(cfg: dict, api_name: str = "NIFTY 500") -> list[tuple]:
    """(month-end date, tri) per month for one index — the self-check's mirror of the
    harness's own query."""
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        rows = con.execute("SELECT max(date), arg_max(tri, date) FROM index_tri "
                           "WHERE index_name = ? GROUP BY date_trunc('month', date)",
                           [api_name]).fetchall()
    finally:
        con.close()
    return sorted(rows)


def _self_check() -> None:
    cfg = load("quick")

    # 1. chunk windows: full year and cutoff-bounded current year, both <=366 days
    s, e = _chunk_window(2011, date(2026, 9, 24))
    assert (s, e) == (date(2011, 1, 1), date(2011, 12, 31)), (s, e)
    s, e = _chunk_window(2026, date(2026, 9, 24))
    assert (s, e) == (date(2026, 1, 1), date(2026, 9, 24)), (s, e)
    s, e = _chunk_window(2026, date(2026, 12, 25))
    assert (e - s).days <= 366
    assert chunk_path(2011, cfg, "NIFTY 200").endswith(
        os.path.join("nifty200", "TRI_2011.json")), chunk_path(2011, cfg, "NIFTY 200")

    # 2. parse on a synthetic chunk shaped exactly like the API's rows (newest first,
    #    NTR "-" in the early era, comma thousands)
    rows = [{"Index Name": "Nifty 500", "Date": "31 Dec 2024", "TotalReturnsIndex": "1,234.56",
             "NTR_Value": "-"},
            {"Index Name": "Nifty 500", "Date": "30 Dec 2024", "TotalReturnsIndex": "1,200.00",
             "NTR_Value": "1,150.25"}]
    os.makedirs(cfg["paths"]["raw_nifty_tri"], exist_ok=True)
    p = os.path.join(cfg["paths"]["raw_nifty_tri"], "_synthetic.json")
    json.dump(rows, open(p, "w", encoding="utf-8"))
    try:
        got = parse_chunk(p)
        assert got == [(date(2024, 12, 30), 1200.0, 1150.25),
                       (date(2024, 12, 31), 1234.56, None)], got
    finally:
        os.remove(p)

    # 3. live: both indices, migration of the legacy flat layout, cache-skip on rerun
    asof = _asof(cfg)
    print(f"fetching TRI chunks 2011..{asof.year} for {list(INDICES)} (live)...")
    a = fetch_chunks(cfg, asof)
    root = cfg["paths"]["raw_nifty_tri"]
    assert not [n for n in os.listdir(root) if n.startswith("TRI_")], "legacy chunks not migrated"
    b = fetch_chunks(cfg, asof)
    assert b["downloaded"] == 0 and b["cached"] == a["cached"] + a["downloaded"], \
        f"cache-skip violated: {a} then {b}"

    m5 = _month_marks(cfg, "NIFTY 500")
    m2 = _month_marks(cfg, "NIFTY 200")
    assert m5 and m2, "index_tri is empty after a live fetch"
    assert [d for d, _ in m5] == [d for d, _ in m2], "index calendars diverge"
    assert all(tri > 0 for _, tri in m5 + m2)
    # last TRI mark sits on/near the data cutoff (the index trades the same calendar)
    last = date.fromisoformat(str(m5[-1][0]))
    assert (asof - last).days <= 10, f"last TRI mark {last} too far behind cutoff {asof}"

    print(f"PASS: nifty_tri (chunk windows, API-shaped parse with NTR '-', live fetch of "
          f"{a['downloaded']} new chunk(s), legacy layout migrated, cache-skip on rerun, "
          f"index_tri {len(m5)} month-end marks {m5[0][0]} -> {m5[-1][0]} for both indices, "
          f"last TRI 500 {m5[-1][1]} / 200 {m2[-1][1]})")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
