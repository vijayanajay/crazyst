"""quantdata — the whole data pipeline as one command.

    quantdata.py status                       rows/spans/cutoff, in seconds, always current
    quantdata.py query symbol RELIANCE        one symbol's full daily history (multi-project use)
    quantdata.py query symbols EQ             every EQ symbol ever seen
    quantdata.py query dates 2025-01          the month's trading calendar
    quantdata.py query sql "SELECT ..."       read-only escape hatch (SELECT/WITH only)
    quantdata.py query matrix                 labeled feature rows for modeling (CSV via -o)

    quantdata.py refresh [--date D] [--no-verify]   daily catch-up, then the self-check gate
    quantdata.py scheduler [--once]                 cron entry point (waits for the cutoff)
    quantdata.py selfcheck [--force] [--verbose]    the full 17-check suite
    quantdata.py check                              quick sanity: cutoff, dupes, coverage

From source:   .venv/Scripts/python quantdata.py <cmd>   (repo root = home)
Frozen build:  build_exe.py -> dist/quantdata.exe (+ config.yaml + quantdata_build_id.txt);
               the exe keeps config.yaml and data/ next to itself wherever it is copied, so
               one binary plus its data folder moves between machines and projects intact.

This file is the only new orchestration; every command is a thin wrapper over the existing
modules (src.config.load, src.download.*, src.selfcheck), which stay the implementation.
"""
import csv
import os
import re
import runpy
import sys


def _dispatch_module(argv: list[str]) -> int:
    """Run a src module's __main__ inside this process — how the frozen exe 'runs -m'.

    The children spawned via config.python_child_args re-enter here with --run-module;
    module exit codes (sys.exit inside their __main__) propagate as SystemExit, which is
    exactly the contract subprocess.run observes from `python -m`.
    """
    module = argv[0]
    sys.argv = [module, *argv[1:]]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
    return 0


def _open_ro(cfg: dict):
    """Open the database read-only, with a first-run message instead of a DuckDB traceback."""
    import duckdb
    path = cfg["paths"]["duckdb"]
    if not os.path.exists(path):
        raise SystemExit(f"no database at {path} yet — run `quantdata backfill` (history) "
                         f"or `quantdata refresh` (daily catch-up) first")
    return duckdb.connect(path, read_only=True)


def _cmd_status() -> int:
    from src.config import home_dir, load
    import duckdb
    from src.normalize import panels

    cfg = load()
    con = _open_ro(cfg)
    try:
        print(f"home        {home_dir()}")
        print(f"profile     {cfg['profile']}  (data from {cfg['data_start_date']})")
        print(f"cutoff      {panels.data_cutoff(con)}  (newest bhav date — from the database)")
        print()
        print(f"{'table':<14}{'rows':>10}  {'min':<12}{'max'}")
        for t in ("bhav", "delivery", "adj_close", "month_grid", "adj_me", "liq_me",
                  "deliv_me", "universe_rank", "eligible", "winners", "feature_panel",
                  "feature_matrix"):
            if not panels.has_table(con, t):
                print(f"{t:<14}{'—':>10}  (not built yet)")
                continue
            cols = [r[1] for r in con.execute(f"PRAGMA table_info('{t}')").fetchall()]
            dcol = next((c for c in ("mdate", "date", "adate") if c in cols), None)
            n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            if dcol:
                mn, mx = con.execute(f'SELECT min("{dcol}"), max("{dcol}") FROM "{t}"').fetchone()
                print(f"{t:<14}{n:>10,}  {str(mn)[:10]:<12}{str(mx)[:10]}")
            else:
                print(f"{t:<14}{n:>10,}")
    finally:
        con.close()
    raw = os.path.join(home_dir(), "data", "raw")
    if os.path.isdir(raw):
        files = sum(len(fs) for _, _, fs in os.walk(raw))
        print(f"\nraw cache   {files:,} files under data/raw/")
    return 0


def _cmd_query(argv: list[str]) -> int:
    """Read-only data export — the cross-project consumption surface."""
    from src.config import load

    args = [a for a in argv if not a.startswith("-")]
    out = argv[argv.index("-o") + 1] if "-o" in argv else None
    assert args, "query what? see --help: symbol|symbols|dates|sql|matrix"
    what, val = args[0], (args[1] if len(args) > 1 else None)
    cfg = load()
    con = _open_ro(cfg)
    try:
        if what == "symbol" and val:
            sql, params = """SELECT date, series, open, high, low, close, prev_close, last,
                                    volume, turnover, trades, isin
                             FROM bhav WHERE symbol = ? ORDER BY date""", [val]
        elif what == "symbols" and val:
            sql, params = ("SELECT symbol, min(date) AS first, max(date) AS last "
                           "FROM bhav WHERE series = ? GROUP BY 1 ORDER BY 1"), [val]
        elif what == "dates" and val:
            sql, params = ("SELECT DISTINCT date FROM bhav WHERE series = 'EQ' "
                           "AND strftime(date, '%Y-%m') = ? ORDER BY date"), [val]
        elif what == "matrix":
            sql, params = "SELECT * FROM feature_matrix ORDER BY mdate, symbol", []
        elif what == "sql" and val:
            assert re.match(r"(?is)\s*(select|with)\b", val), \
                "only SELECT/WITH — this is a read-only export"
            sql, params = val, []
        else:
            raise SystemExit(f"unknown query {what!r} — see --help")
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    if out:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"{len(rows):,} rows -> {out}")
    else:
        print("\t".join(cols))
        for r in rows:
            print("\t".join("" if v is None else str(v) for v in r))
    return 0


def _cmd_check() -> int:
    """A 30-second sanity read: the numbers that catch most data trouble."""
    from src.config import load
    from src.normalize import panels

    cfg = load()
    con = _open_ro(cfg)
    try:
        cutoff = panels.data_cutoff(con)
        n = con.execute("SELECT count(*) FROM bhav").fetchone()[0]
        dup = con.execute("SELECT count(*) FROM (SELECT symbol, series, date FROM bhav "
                          "GROUP BY 1, 2, 3 HAVING count(*) > 1)").fetchone()[0]
        eq_syms = con.execute("SELECT count(DISTINCT symbol) FROM bhav "
                              "WHERE series = 'EQ'").fetchone()[0]
        adj_syms = con.execute("SELECT count(DISTINCT symbol) FROM adj_close").fetchone()[0]
        n_live, n_recent = con.execute("""
            WITH recent AS (SELECT DISTINCT symbol FROM bhav WHERE series = 'EQ'
                            AND date > (SELECT max(date) FROM bhav) - INTERVAL 30 DAY)
            SELECT (SELECT count(*) FROM recent r WHERE EXISTS (
                        SELECT 1 FROM adj_close a
                        WHERE a.symbol = r.symbol AND a.adj_close IS NOT NULL)),
                   (SELECT count(*) FROM recent)""").fetchone()
        bad = con.execute("SELECT count(*) FROM adj_close WHERE adj_close IS NULL "
                          "OR NOT isfinite(adj_close) OR adj_close <= 0").fetchone()[0]
        cov = n_live / n_recent if n_recent else 0.0
        print(f"cutoff          {cutoff}")
        print(f"bhav rows       {n:,} (duplicate keys: {dup})")
        print(f"adj coverage    {n_live:,}/{n_recent:,} still-trading EQ symbols = {cov:.1%} "
              f"(floor {cfg['validate']['canary_min_adj_coverage']:.0%}); "
              f"all-time {adj_syms:,}/{eq_syms:,}")
        print(f"adj bad values  {bad:,}"
              + ("" if bad == 0 else "  (Yahoo placeholder rows from batch padding — inert by "
                                      "construction, every consumer filters on value; "
                                      "'trim-adj' removes them)"))
        assert dup == 0, "duplicate bhav keys — rerun a normalize pass (self-heal dedupes)"
        assert cov >= cfg["validate"]["canary_min_adj_coverage"], \
            "adj coverage below the canary floor — rerun backfill/refresh"
    finally:
        con.close()
    print("OK")
    return 0


COMMANDS = {
    "status": lambda a: _cmd_status(),
    "query": _cmd_query,
    "check": lambda a: _cmd_check(),
    "refresh": lambda a: _dispatch_module(["src.download.refresh", *a]),
    "scheduler": lambda a: _dispatch_module(["src.download.scheduler", *a]),
    "backfill": lambda a: _dispatch_module(["src.download.backfill_all"]),
    "backfill-adj": lambda a: _dispatch_module(["src.normalize.adj_close", "--backfill"]),
    "trim-adj": lambda a: _dispatch_module(["src.normalize.adj_close", "--trim"]),
    "selfcheck": lambda a: _dispatch_module(["src.selfcheck", *a]),
    "validate": lambda a: _dispatch_module(["src.validate.report"]),
    "canary": lambda a: _dispatch_module(["src.validate.canary"]),
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--run-module":          # frozen children land here
        return _dispatch_module(argv[1:])
    cmd = argv[0]
    assert cmd in COMMANDS, f"unknown command {cmd!r} — see --help"
    return COMMANDS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
