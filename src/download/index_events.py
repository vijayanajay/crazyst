"""Sourced NSE index inclusion/exclusion events — E025's data direction (audit item #3).

Sources (both archived under paths.raw_index_events, fetched once, never re-fetched while
present — plan working rule 4):
- https://archives.nseindia.com/content/indices/IndexInclExcl.xls — multi-sheet BIFF
  workbook of security inclusions/exclusions per index with dates (Scrip Name + Event
  Date + Description; dates are a mix of real Excel dates and DD-MM-YYYY strings).
- https://archives.nseindia.com/content/equities/EQUITY_L.csv — NSE's equity master
  (SYMBOL + NAME OF COMPANY), the name->symbol bridge (bhav carries ISINs and tickers,
  not names; companies renamed since the master's snapshot will not match — counted).

Discipline (src/download/_http.py conventions): browser-like UA, .part atomic writes,
loud failures (a missing source raises, never silently degrades). The duckdb table
index_events is DERIVED from the raw files on every run — parse is cheap, the raw file
is the source of truth, the table is trivially idempotent.

`python -m src.download.index_events` fetches (if needed), parses, builds the table, and
prints a coverage report (per-index sheet event counts, match rates and date ranges).
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata

import duckdb
import requests

from src.config import load
from src.download import _http

SOURCE_URL = "https://archives.nseindia.com/content/indices/IndexInclExcl.xls"
MASTER_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SCHEMA = """CREATE TABLE IF NOT EXISTS index_events (
    index_name VARCHAR, date DATE, company VARCHAR, symbol VARCHAR, action VARCHAR)"""


def raw_path(cfg: dict) -> str:
    return os.path.join(cfg["paths"].get("raw_index_events", "data/raw/index_events"),
                        "IndexInclExcl.xls")


def master_path(cfg: dict) -> str:
    return os.path.join(cfg["paths"].get("raw_index_events", "data/raw/index_events"),
                        "EQUITY_L.csv")


def _get(url: str) -> bytes:
    """One browser-like GET; 403/404 raise — a missing source is loud, never silent."""
    r = requests.get(url, headers=_http.HEADERS, timeout=(10, 60))
    if r.status_code in (403, 404):
        raise IOError(f"{url}: HTTP {r.status_code} — source unavailable")
    r.raise_for_status()
    return r.content


def fetch(cfg: dict) -> str:
    """Download workbook + equity master unless cached. Returns 'cached' | 'downloaded'."""
    status = "cached"
    for path, url, magic in ((raw_path(cfg), SOURCE_URL, XLS_MAGIC),
                             (master_path(cfg), MASTER_URL, None)):
        if os.path.exists(path):
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = _get(url)
        if magic is not None and content[:8] != magic:
            raise IOError(f"{url}: not an OLE2 .xls container "
                          f"({len(content)} bytes, starts {content[:8]!r})")
        if magic is None and (b"<" in content[:64] or len(content) < 1_000):
            raise IOError(f"{url}: not a CSV ({len(content)} bytes)")
        part = path + ".part"
        with open(part, "wb") as f:
            f.write(content)
        os.replace(part, path)
        status = "downloaded"
    return status


_SUFFIXES = (" limited", " ltd", " ltd.", "industries", "corporation", "corpora",
             "company", "group")          # single trailing pass, in order


def _norm(s: str) -> str:
    """Company-name normalization for matching: NFKD, drop (Rs 10 paid up)-style legal
    notes, strip punctuation, one pass of legal-suffix stripping (Ltd./Limited merge).
    ponytail: single-pass heuristic, not entity resolution — renames since the master's
    snapshot still miss (counted, disclosed)."""
    s = unicodedata.normalize("NFKD", str(s))
    s = re.sub(r"\((?:Rs\.?\s*)?[^)]*\)", " ", s)          # drop (Rs 10 paid up) etc.
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s).lower()
    s = " ".join(s.split())
    for suf in _SUFFIXES:
        if s.endswith(suf):
            return s[: -len(suf)].strip()
    return s


def _event_date(v, datemode: int):
    """The sheet mixes real Excel dates with 'DD-MM-YYYY' strings; parse both. Returns
    None for the unparseable (counted by the caller, never silently dropped)."""
    import datetime as _dt
    import xlrd
    if isinstance(v, float) and v > 0:
        return xlrd.xldate_as_datetime(v, datemode).date()
    s = str(v).strip()
    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


_NORM_TO_SYM: dict[str, str] = {}


def _symbol_of(name: str) -> str | None:
    return _NORM_TO_SYM.get(_norm(name))


def build_symbol_map(cfg: dict) -> None:
    """Normalize the equity master's company names so sheet scrip names can be matched to
    NSE symbols."""
    global _NORM_TO_SYM
    _NORM_TO_SYM = {}
    with open(master_path(cfg), encoding="latin-1") as f:
        for row in csv.DictReader(f):
            sym, name = (row.get("SYMBOL", "").strip(), row.get("NAME OF COMPANY", ""))
            if sym:
                _NORM_TO_SYM.setdefault(_norm(name), sym.upper())


def parse_and_build(cfg: dict) -> dict:
    """Parse the cached workbook and (re)build the index_events table. Returns coverage."""
    import xlrd

    book = xlrd.open_workbook(raw_path(cfg))
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        con.execute(SCHEMA)
        con.execute("DELETE FROM index_events")
        build_symbol_map(cfg)
        coverage = {}
        for sh in book.sheets():
            if sh.nrows < 2:
                continue
            header = [_norm(str(sh.cell_value(0, c))) for c in range(sh.ncols)]
            date_col = next((c for c, h in enumerate(header) if "date" in h), None)
            # 'index name' (column 0) contains 'name' and would shadow the scrip column —
            # prefer 'scrip', and never match a column that is itself the index label
            name_col = next((c for c, h in enumerate(header)
                             if "scrip" in h or (("name" in h or "company" in h
                                                  or "secur" in h) and "index" not in h)),
                            None)
            sym_col = next((c for c, h in enumerate(header) if "symbol" in h), None)
            act_col = next((c for c, h in enumerate(header)
                            if "description" in h or "type" in h or "action" in h
                            or "incl" in h or "excl" in h), None)
            if date_col is None or (name_col is None and sym_col is None):
                continue
            batch, matched, skipped = [], 0, 0
            for r in range(1, sh.nrows):
                dt = _event_date(sh.cell_value(r, date_col), book.datemode)
                if dt is None:
                    skipped += 1
                    continue
                comp = str(sh.cell_value(r, name_col)) if name_col is not None else ""
                sym = None
                if sym_col is not None:
                    sym = str(sh.cell_value(r, sym_col)).strip() or None
                if sym is None and comp:
                    sym = _symbol_of(comp)
                act = str(sh.cell_value(r, act_col)).strip().lower() \
                    if act_col is not None else ""
                act = "include" if "incl" in act else (
                    "exclude" if "excl" in act else act or "include")
                batch.append((sh.name, dt, comp, sym, act))
                matched += sym is not None
            # one transaction: DuckDB autocommits per execute, which is death by thousands
            # of commits on a sheet this size (the 120s timeout that forced this batching)
            con.execute("BEGIN TRANSACTION")
            con.executemany("INSERT INTO index_events VALUES (?, ?, ?, ?, ?)", batch)
            con.execute("COMMIT")
            rows, unmatched = len(batch), sum(1 for b in batch if b[3] is None)
            if rows:
                dr = con.execute("SELECT min(date), max(date) FROM index_events "
                                 "WHERE index_name = ?", [sh.name]).fetchone()
                coverage[sh.name] = {"events": rows, "matched": matched,
                                     "unmatched": unmatched, "skipped": skipped,
                                     "first": str(dr[0]), "last": str(dr[1])}
        return coverage
    finally:
        con.close()


def main() -> int:
    import time
    t0 = time.monotonic()
    cfg = load("full")
    status = fetch(cfg)
    print(f"raw: {status} -> {raw_path(cfg)} (+ equity master)")
    coverage = parse_and_build(cfg)
    print(f"index_events built in {time.monotonic() - t0:.1f}s; coverage:")
    for k, v in sorted(coverage.items(), key=lambda kv: -kv[1]["events"]):
        print(f"  {k:<34} {v['events']:>5} events  matched {v['matched']:>5}  "
              f"unmatched {v['unmatched']:>4}  skipped {v['skipped']:>3}  "
              f"{v['first']} -> {v['last']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
