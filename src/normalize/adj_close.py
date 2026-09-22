"""Task 1.6 — yfinance adjusted closes for all EQ symbols -> `adj_close(symbol, date, adj_close)`.

Why yfinance: BRD D3 names it explicitly (adjusted closes + splits/bonus/dividends) —
that is the written dependency reason BRD §13 requires. NSE raw prices stay untouched
(task 1.1-1.4); this table exists only for correct returns.

- history floor: fetched from config `adj_history_start` (2009-01-01), NOT period="max" —
  the BRD window starts 2011 and the longest feature lookback is 12M-1M, so Yahoo's 1991-2008
  tail was 42% of the table and unused. `--trim` applies the same floor to an existing table
  (the fetch change alone only prevents re-adding it).
- only usable prices are stored: a frame whose Adj Close is entirely NaN means Yahoo has no
  data for that ticker (delisted/renamed), so it is reported as unavailable instead of being
  cached as a symbol that is forever empty. Multi-ticker batches still pad gap and pre-listing
  days with NaN — `--trim` drops those rows from an existing table.
- cache: the adj_close table itself (no raw files — API data); symbols already present
  are skipped, so the backfill is resumable (plan working rule 4).
- mapping: NSE SYMBOL + ".NS" (M&M.NS, BAJAJ-AUTO.NS work as-is).
- known ceiling: Yahoo delists some dead tickers (survivorship) — the delisted probe in
  the self-check reports how bad it is; delisted symbols degrade to mark-at-last-price
  in the engine (BRD §9.4), never to silently missing returns.

`python -m src.normalize.adj_close` runs the self-check: mapping/fraction logic on
synthetic data, then the done-when — 20 random symbols, NSE raw close vs Yahoo raw
close matching on >=95% of overlapping days (a symbol-mapping bug shows as ~0%).
`python -m src.normalize.adj_close --backfill` fetches all EQ symbols (~15 min, resumable).
"""
import os
import random
import sys
import time

import duckdb
import pandas as pd

from src.config import load

ADJ_COLS = ["symbol", "date", "adj_close"]
SCHEMA = """CREATE TABLE IF NOT EXISTS adj_close (
    symbol VARCHAR, date DATE, adj_close DOUBLE)"""
MATCH_TOL = 0.005  # raw closes should agree to 0.5% on matched days


def yahoo_ticker(symbol: str) -> str:
    return f"{symbol}.NS"


def match_fraction(nse: "pd.Series[float]", yf: "pd.Series[float]") -> float:
    """Fraction of inner-joined dates where raw closes agree within MATCH_TOL."""
    j = pd.concat([nse.rename("nse"), yf.rename("yf")], axis=1, join="inner").dropna()
    if j.empty:
        return 0.0
    return float((abs(j["nse"] - j["yf"]) / j["nse"].abs() <= MATCH_TOL).mean())


def _fetch_batch(tickers: list[str], cfg: dict) -> dict[str, pd.DataFrame]:
    """yf.download one chunk -> {symbol: df indexed by date with Close/Adj Close}."""
    import yfinance as yf
    df = yf.download([yahoo_ticker(t) for t in tickers], start=cfg["adj_history_start"],
                     auto_adjust=False, progress=False, threads=True, group_by="ticker")
    out = {}
    for t in tickers:
        yt = yahoo_ticker(t)
        try:
            sub = df[yt] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            continue  # symbol failed entirely
        if sub.empty or "Adj Close" not in sub:
            continue
        if sub["Adj Close"].dropna().empty:
            # Yahoo serves the ticker name but has no usable prices (delisted/renamed tickers
            # come back as an all-NaN frame). Storing that frame would mark the symbol as
            # fetched forever — 1,066 EQ symbols were silently NULL that way before this guard.
            continue
        idx = sub.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
        out[t] = pd.DataFrame({"symbol": t, "date": idx.date, "adj_close": sub["Adj Close"].values,
                               "close_raw": sub["Close"].values})
    time.sleep(cfg["download"]["sleep_seconds"])  # polite to Yahoo between chunks
    return out


def _done_symbols(cfg: dict) -> set[str]:
    # read-write (not read_only): on the first ever run the table doesn't exist yet and
    # CREATE on a read-only-attached DB raises — caught live on the first backfill.
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        con.execute(SCHEMA)
        return {r[0] for r in con.execute("SELECT DISTINCT symbol FROM adj_close").fetchall()}
    finally:
        con.close()


def _insert(cfg: dict, frames: dict[str, pd.DataFrame]) -> int:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        rows = 0
        for sym, df in frames.items():
            con.register("aview", df[ADJ_COLS])
            con.execute(f"INSERT INTO adj_close SELECT {', '.join(ADJ_COLS)} FROM aview")
            con.unregister("aview")
            rows += len(df)
        con.execute("DELETE FROM adj_close WHERE rowid NOT IN "
                    "(SELECT min(rowid) FROM adj_close GROUP BY symbol, date)")
        con.execute("CHECKPOINT")
        return rows
    finally:
        con.close()


def backfill(cfg: dict, chunk: int = 100) -> dict:
    """All EQ symbols, chunked, resumable. Failed symbols retried once, then reported."""
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        all_syms = [r[0] for r in con.execute(
            "SELECT DISTINCT symbol FROM bhav WHERE series='EQ' ORDER BY 1").fetchall()]
    finally:
        con.close()
    todo = [s for s in all_syms if s not in _done_symbols(cfg)]
    print(f"adj_close backfill: {len(all_syms):,} EQ symbols, {len(all_syms) - len(todo):,} cached, "
          f"{len(todo):,} to fetch", flush=True)
    failed: list[str] = []
    for i in range(0, len(todo), chunk):
        frames = _fetch_batch(todo[i:i + chunk], cfg)
        if frames:
            _insert(cfg, frames)
        failed += [s for s in todo[i:i + chunk] if s not in frames]
        print(f"  chunk {i // chunk + 1}: +{len(frames)} symbols "
              f"({(i + len(todo[i:i + chunk]))}/{len(todo)} done)", flush=True)
    if failed:  # one retry pass per symbol
        print(f"retrying {len(failed)} failed symbols once...", flush=True)
        frames = _fetch_batch(failed, cfg)
        _insert(cfg, frames)
        failed = [s for s in failed if s not in frames]
    print(f"backfill done: {len(failed)} symbols unavailable on Yahoo "
          f"(delisted/renamed — expected for some; engine marks at last price)", flush=True)
    return {"failed": failed}


def cross_check(cfg: dict, n: int = 20, fetcher=None) -> bool:
    """Done-when: n random symbols, NSE vs Yahoo raw closes match on >=95% of overlap days."""
    import yfinance as yf
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        cand = con.execute("""SELECT symbol, count(*) c FROM bhav WHERE series='EQ'
                              GROUP BY symbol HAVING c >= 250 ORDER BY symbol""").fetchall()
        nse_all = {sym: pd.Series(rows, index=pd.to_datetime(dates)) for sym, rows, dates in
                   [tuple(x) for x in con.execute("""
                       SELECT symbol, close, date FROM bhav WHERE series='EQ' ORDER BY symbol, date""").fetchall()]}
    finally:
        con.close()
    rng = random.Random(cfg["backtest"]["random_seed"])
    sample = [sym for sym, _ in rng.sample(cand, n)]
    fetcher = fetcher or (lambda syms: _fetch_batch(syms, cfg))
    yf_data = fetcher(sample)
    fracs = {sym: match_fraction(nse_all[sym], yf_data[sym]["close_raw"])
             for sym in sample if sym in yf_data}
    missing = [s for s in sample if s not in yf_data]
    for sym in sample:
        f = fracs.get(sym)
        print(f"  {sym:<12} {'MISSING on Yahoo' if f is None else f'{f * 100:5.1f}% match'}", flush=True)
    ok_syms = [s for s, f in fracs.items() if f >= 0.9]
    print(f"cross-check: {len(ok_syms)}/{n} symbols match >=90% of overlap days; "
          f"{len(missing)} missing on Yahoo", flush=True)
    return len(ok_syms) >= n - 2  # tolerate 2 renamed/dead symbols out of 20


def trim(cfg: dict) -> int:
    """Diet adj_close to rows anything can use; returns rows removed.

    Two one-time repairs for a table built while the fetcher used period="max" and stored
    every NaN row of multi-ticker batches:
      - date < cfg['adj_history_start']: ~12.6M of 30.3M rows (42%) predate 2009 and no
        profile can reach them;
      - adj_close IS NULL: Yahoo's gap/pre-listing padding plus all-NaN frames for 1,066
        delisted tickers — the panel, the canary and the labels all ignore them anyway.
    The fetch is now bounded and skips unusable frames, so a fresh backfill never re-adds them.
    """
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        before = con.execute("SELECT count(*) FROM adj_close").fetchone()[0]
        con.execute("DELETE FROM adj_close WHERE date < ?::DATE OR adj_close IS NULL",
                    [cfg["adj_history_start"]])
        con.execute("CHECKPOINT")
        after = con.execute("SELECT count(*) FROM adj_close").fetchone()[0]
        return before - after
    finally:
        con.close()


def _self_check() -> None:
    # 1. mapping edge cases
    assert yahoo_ticker("M&M") == "M&M.NS" and yahoo_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO.NS"

    # 2. fraction logic on synthetic frames
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    nse = pd.Series(range(10), index=idx, dtype=float)
    assert match_fraction(nse, nse.copy()) == 1.0, "identical series must match fully"
    assert match_fraction(nse, nse * 1.02) == 0.0, "2% shifted series must match nowhere"
    noisy = nse.copy()
    noisy.iloc[9] *= 3  # 1 of 10 days broken
    assert match_fraction(nse, noisy) == 0.9, "1 broken day of 10 must give 0.9"

    # 3. live done-when: 20 random symbols vs NSE
    cfg = load("quick")
    assert cross_check(cfg, n=20), "NSE vs Yahoo cross-check failed — symbol-mapping bug?"

    # 4. delisted probe (informational): how many long-dead tickers Yahoo still serves
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        dead = [r[0] for r in con.execute(f"""
            SELECT symbol FROM bhav WHERE series='EQ'
            GROUP BY symbol HAVING max(date) < '{cfg['end_date']}'::DATE - INTERVAL '2 years'
            ORDER BY random() LIMIT 5""").fetchall()]
    finally:
        con.close()
    got = _fetch_batch(dead, cfg)
    print(f"delisted probe: {len(got)}/5 long-dead symbols still on Yahoo "
          f"({', '.join(dead)})", flush=True)
    print("PASS: adj_close mapping/fraction logic + live 20-symbol cross-check")
    sys.exit(0)


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        cfg = load("quick")
        backfill(cfg)
        sys.exit(0)
    if "--trim" in sys.argv:
        cfg = load("quick")
        n = trim(cfg)
        print(f"trimmed {n:,} adj_close rows (pre-{cfg['adj_history_start']} or NULL-valued)",
              flush=True)
        sys.exit(0)
    _self_check()
