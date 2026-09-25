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
`--refresh` is the daily path (src/download/refresh.py calls it): symbols whose bhav history
runs past their last stored adjusted date, one short window each, plus a full re-fetch for any
symbol whose adjustment basis moved (a split/bonus rewrites Yahoo's whole adjusted history).
`--trim` applies the history floor and drops unusable rows.
"""
import os
import random
import sys
import time

import duckdb
import pandas as pd

from src.config import load
from src.normalize import panels

ADJ_COLS = ["symbol", "date", "adj_close"]
SCHEMA = """CREATE TABLE IF NOT EXISTS adj_close (
    symbol VARCHAR, date DATE, adj_close DOUBLE)"""
MATCH_TOL = 0.005  # raw closes should agree to 0.5% on matched days
RECENT_DAYS = 365  # cross-check window: see cross_check's docstring for why not full history


def yahoo_ticker(symbol: str) -> str:
    return f"{symbol}.NS"


def match_fraction(nse: "pd.Series[float]", yf: "pd.Series[float]") -> float:
    """Fraction of inner-joined dates where raw closes agree within MATCH_TOL.

    Relative form `|d| <= tol * |nse|` (not a division): a zero NSE close must give a
    definite verdict — equal closes match, unequal don't — never a NaN that mean()
    would silently drop from the denominator.
    """
    j = pd.concat([nse.rename("nse"), yf.rename("yf")], axis=1, join="inner").dropna()
    if j.empty:
        return 0.0
    return float(((j["nse"] - j["yf"]).abs() <= MATCH_TOL * j["nse"].abs()).mean())


def _fetch_batch(tickers: list[str], cfg: dict, start: str | None = None) -> dict[str, pd.DataFrame]:
    """yf.download one chunk -> {symbol: df indexed by date with Close/Adj Close}.

    `start` bounds the window (default: the full history floor); the daily refresh passes a
    short recent window so a routine run pulls days, not decades.
    """
    import yfinance as yf
    df = yf.download([yahoo_ticker(t) for t in tickers], start=start or cfg["adj_history_start"],
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


ACTION_TOL = 1e-4  # adjustment-factor move that means the symbol's adjusted history was rewritten


def _window_start(last_dates: dict, cfg: dict, buffer_days: int) -> "date":
    """Window start for a daily refresh: the oldest symbol's last stored date minus a buffer, so a
    short suspension or a late Yahoo print is covered, floored at the history floor.

    Pure so the self-check can pin it; an empty map (fresh table) falls back to the bhav cutoff.
    """
    from datetime import date, timedelta
    floor = date.fromisoformat(cfg["adj_history_start"])
    fallback = cfg.get("end_date") or panels.data_cutoff(
        duckdb.connect(cfg["paths"]["duckdb"], read_only=True))
    oldest = min([d for d in last_dates.values() if d], default=date.fromisoformat(fallback))
    return max(floor, oldest - timedelta(days=buffer_days))


def _replace_symbol(cfg: dict, symbol: str, df: pd.DataFrame) -> int:
    """Swap a symbol's entire series (used when an adjustment rewrote its history)."""
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        con.execute("DELETE FROM adj_close WHERE symbol = ?", [symbol])
        con.register("aview", df[ADJ_COLS])
        con.execute(f"INSERT INTO adj_close SELECT {', '.join(ADJ_COLS)} FROM aview")
        con.unregister("aview")
        con.execute("CHECKPOINT")
        return len(df)
    finally:
        con.close()


def refresh_recent(cfg: dict, chunk: int = 100, buffer_days: int = 7, fetcher=None) -> dict:
    """Daily-refresh path: bring adj_close up to the newest NSE trading day.

    `backfill()` skips symbols that already exist, so it can never pick up a NEW day. This
    fetches one short recent window for the symbols whose bhav history runs past their last
    stored adjusted date and inserts only rows after that date — bounded cost, idempotent.

    Corporate actions: Yahoo's Adj Close is adjusted *historically*, so a split/bonus today
    rewrites every past adjusted price for that symbol and an append alone would leave the old
    series stale (BRD D3: correct returns). Detected by comparing the adj/raw factor on the
    newest stored day with the new day's: when it moved, that symbol's whole series is re-fetched
    and replaced. ponytail: a suspension spanning an ex-date is not detected this way (the symbol
    would have to trade on both sides of the action); the Phase 1 cross-check and the canary
    remain the safety nets.

    Returns rows added/replaced, symbols touched, and Yahoo-vs-NSE raw-close agreement on the new
    rows — the daily trust check: a mapping regression shows up as disagreement, not a price.
    """
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        last = {s: d for s, d in con.execute(
            "SELECT symbol, max(date) FROM adj_close GROUP BY 1").fetchall()}
        # Recently-traded symbols only. Without the 30-day clause the ~1,067 delisted tickers
        # Yahoo cannot serve (they have no stored rows at all, so their bhav max always looks
        # newer than "no stored date") are re-requested every single day and get the refresh
        # rate-limited (HTTP 429) — measured live. ponytail: a symbol suspended for more than
        # 30 days is not topped up while suspended, and is picked up by itself when it trades
        # again (its bhav max becomes recent); deep history stays the one-off --backfill's job.
        todo = [r[0] for r in con.execute("""
            SELECT b.symbol FROM bhav b WHERE b.series = 'EQ' GROUP BY 1
            HAVING max(b.date) > coalesce(
                       (SELECT max(a.date) FROM adj_close a WHERE a.symbol = b.symbol),
                       DATE '1900-01-01')
               AND max(b.date) >= (SELECT max(date) FROM bhav WHERE series = 'EQ')
                                  - INTERVAL 30 DAY
            ORDER BY 1""").fetchall()]
    finally:
        con.close()
    if not todo:
        return {"rows": 0, "symbols": 0, "replaced": 0, "agree": None, "pairs": 0, "start": None,
                "newest": None, "traded": 0, "missing": 0}
    start = _window_start({s: last.get(s) for s in todo}, cfg, buffer_days)
    start_iso = start.isoformat()
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        nse = {(s, d): c for s, d, c in con.execute(
            "SELECT symbol, date, close FROM bhav WHERE series = 'EQ' AND date >= ?", [start_iso]).fetchall()}
    finally:
        con.close()

    # start=None means the full history: a redo symbol needs its whole series, not the window
    fetch = fetcher or (lambda syms, start=None: _fetch_batch(syms, cfg, start=start))
    added = replaced = touched = 0
    pairs: list[bool] = []
    for i in range(0, len(todo), chunk):
        frames = fetch(todo[i:i + chunk], start_iso)
        fresh, redo = {}, []
        for sym, df in frames.items():
            cut = last.get(sym)
            if cut is None:
                redo.append(sym)  # listed in bhav but never stored: needs the whole series
                continue
            prev = df[df["date"] == cut]
            new = df[df["date"] > cut]
            if len(new) and len(prev) and prev["close_raw"].iloc[-1]:
                f_old = prev["adj_close"].iloc[-1] / prev["close_raw"].iloc[-1]
                f_new = new["adj_close"].iloc[-1] / new["close_raw"].iloc[-1]
                if f_old and abs(f_new / f_old - 1.0) > ACTION_TOL:
                    redo.append(sym)  # adjustment basis moved: history is stale
                    continue
            new = new[new["adj_close"].notna() & (new["adj_close"] > 0)]  # never store junk rows
            if len(new):
                fresh[sym] = new
        if fresh:
            added += _insert(cfg, fresh)
            touched += len(fresh)
            for sym, nf in fresh.items():
                for r in nf.itertuples():
                    c = nse.get((sym, r.date))
                    if c:
                        pairs.append(abs(r.close_raw - c) / abs(c) <= MATCH_TOL)
        for sym in redo:
            full = fetch([sym]).get(sym)
            if full is not None and len(full):
                replaced += _replace_symbol(cfg, sym, full)
                touched += 1
        print(f"  adj chunk {i // chunk + 1}: +{len(fresh)} symbols, {len(redo)} re-fetched",
              flush=True)
    # coverage of the newest NSE day: the number a daily job must watch (a Yahoo lag shows up
    # here as "not priced yet", not as a silently missing return)
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        newest = con.execute("SELECT max(date) FROM bhav WHERE series = 'EQ'").fetchone()[0]
        traded = con.execute("SELECT count(*) FROM bhav WHERE series = 'EQ' AND date = ?",
                             [newest]).fetchone()[0]
        missing = con.execute("""
            SELECT count(*) FROM bhav b WHERE b.series = 'EQ' AND b.date = ?
              AND NOT EXISTS (SELECT 1 FROM adj_close a
                              WHERE a.symbol = b.symbol AND a.date = b.date)""",
            [newest]).fetchone()[0]
    finally:
        con.close()

    agree = (sum(pairs) / len(pairs)) if pairs else None
    if agree is not None and len(pairs) >= 50 and agree < 0.9:
        raise AssertionError(
            f"Yahoo raw closes agree with NSE on only {agree:.1%} of {len(pairs):,} new symbol-days "
            f"(floor 90%) — a symbol-mapping or Yahoo data problem, not a price to trust")
    return {"rows": added, "symbols": touched, "replaced": replaced, "agree": agree,
            "pairs": len(pairs), "start": start_iso, "newest": newest,
            "traded": traded, "missing": missing}


def cross_check(cfg: dict, n: int = 20, fetcher=None) -> bool:
    """Done-when: n random symbols, NSE vs Yahoo raw closes match on >=95% of overlap days.

    Sampled from symbols that still traded in the last 30 days: Yahoo serves no delisted
    or renamed ticker (26% of all-time EQ symbols), and a dead name is a survivorship
    fact, not a symbol-mapping bug — the bug this check exists to catch corrupts live
    symbols too. Same still-trading scoping the refresh, the canary and report [6] use.

    Compared over the last RECENT_DAYS only. ponytail: Yahoo back-adjusts its RAW close
    through old corporate actions on some names (measured: SMSPHARMA x0.095, JAGSNPHARM
    x0.4 before their old split eras, both 100.0% on the last 365 days), so a full-history
    raw-close comparison measures Yahoo's lineage, not our mapping. The adjusted HISTORY
    is validated separately — refresh_recent re-fetches a symbol whose adjustment basis
    moved, and the momentum canary would smear if adj_close history were wrong.
    """
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        cand = con.execute("""SELECT symbol, count(*) c FROM bhav WHERE series='EQ'
                              GROUP BY symbol
                              HAVING c >= 250
                                 AND max(date) > (SELECT max(date) FROM bhav WHERE series = 'EQ')
                                                  - INTERVAL 30 DAY
                              ORDER BY symbol""").fetchall()
        cutoff, = con.execute(
            "SELECT max(date) FROM bhav WHERE series = 'EQ'").fetchone()
        cutoff = pd.Timestamp(cutoff) - pd.Timedelta(days=RECENT_DAYS)
        nse_all: dict = {}
        for sym, d, c in con.execute("""
                SELECT symbol, date, close FROM bhav WHERE series='EQ' ORDER BY symbol, date""").fetchall():
            if c is not None and d >= cutoff.date():  # NULL can never agree; keep Series float-typed
                nse_all.setdefault(sym, ([], []))
                nse_all[sym][0].append(d)
                nse_all[sym][1].append(c)
    finally:
        con.close()
    nse_all = {s: pd.Series(cl, index=pd.to_datetime(ds)) for s, (ds, cl) in nse_all.items()}
    rng = random.Random(cfg["backtest"]["random_seed"])
    sample = [sym for sym, _ in rng.sample(cand, n)]
    fetcher = fetcher or (lambda syms: _fetch_batch(syms, cfg))
    yf_data = fetcher(sample)
    # _fetch_batch frames are column-keyed with a RangeIndex; match_fraction joins on the
    # index, so the close must be re-indexed by date for the comparison to see any overlap
    yf_close = {s: pd.Series(df["close_raw"].values, index=pd.to_datetime(df["date"]))
                for s, df in yf_data.items()}
    yf_close = {s: v[v.index >= cutoff] for s, v in yf_close.items()}
    fracs = {sym: match_fraction(nse_all[sym], yf_close[sym])
             for sym in sample if sym in yf_close}
    missing = [s for s in sample if s not in yf_close]
    for sym in sample:
        f = fracs.get(sym)
        print(f"  {sym:<12} {'MISSING on Yahoo' if f is None else f'{f * 100:5.1f}% match'}", flush=True)
    ok_syms = [s for s, f in fracs.items() if f >= 0.95]
    print(f"cross-check: {len(ok_syms)}/{n} symbols match >=95% of overlap days; "
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

    # 2. fraction logic on synthetic frames (prices start at 1: a 0 close is the degenerate
    #    case the relative form above settles by equality, not a realistic fixture price)
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    nse = pd.Series(range(1, 11), index=idx, dtype=float)
    assert match_fraction(nse, nse.copy()) == 1.0, "identical series must match fully"
    assert match_fraction(nse, nse * 1.02) == 0.0, "2% shifted series must match nowhere"
    noisy = nse.copy()
    noisy.iloc[9] *= 3  # 1 of 10 days broken
    assert match_fraction(nse, noisy) == 0.9, "1 broken day of 10 must give 0.9"

    # 3. daily-refresh window: oldest last-stored date minus the buffer, floored at the history floor.
    # An end_date key is still honored (backward compat) but nothing in config carries it anymore:
    # without one, the empty-map fallback is the bhav cutoff (panels.data_cutoff) — the live path.
    from datetime import date as _date, timedelta as _td
    cfg0 = {"adj_history_start": "2009-01-01", "end_date": "2026-09-21"}
    assert _window_start({"A": _date(2026, 9, 21), "B": _date(2026, 9, 18)}, cfg0, 7) == _date(2026, 9, 11), \
        "window must start buffer_days before the OLDEST symbol's last stored date"
    assert _window_start({}, cfg0, 7) == _date(2026, 9, 14), "empty table must fall back to end_date"
    assert _window_start({"A": _date(2009, 1, 3)}, cfg0, 7) == _date(2009, 1, 1), \
        "window must never reach before adj_history_start"
    cfg1 = {"adj_history_start": "2009-01-01", "paths": {"duckdb": load("quick")["paths"]["duckdb"]}}
    live_cutoff = panels.data_cutoff(duckdb.connect(cfg1["paths"]["duckdb"], read_only=True))
    assert _window_start({}, cfg1, 7) == _date.fromisoformat(live_cutoff) - _td(days=7), \
        "without end_date, the empty-map fallback must be the bhav cutoff minus the buffer"

    # 4. live done-when: 20 random symbols vs NSE
    cfg = load("quick")
    assert cross_check(cfg, n=20), "NSE vs Yahoo cross-check failed — symbol-mapping bug?"

    # 5. delisted probe (informational): how many long-dead tickers Yahoo still serves
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        dead = [r[0] for r in con.execute(f"""
            SELECT symbol FROM bhav WHERE series='EQ'
            GROUP BY symbol HAVING max(date) < (SELECT max(date) FROM bhav) - INTERVAL '2 years'
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
    if "--refresh" in sys.argv:
        st = refresh_recent(load("quick"))
        agree = "n/a" if st["agree"] is None else f"{st['agree']:.1%}"
        print(f"adj refresh: +{st['rows']:,} rows for {st['symbols']:,} symbols "
              f"(window from {st['start']}, {st['replaced']:,} rows replaced by full re-fetch, "
              f"raw-close agreement {agree} on {st['pairs']:,} pairs)", flush=True)
        if st["traded"]:
            print(f"  newest NSE day {st['newest']}: {st['traded'] - st['missing']:,}/"
                  f"{st['traded']:,} traded symbols priced ({st['missing']:,} missing)", flush=True)
        sys.exit(0)
    _self_check()
