"""Month-end panels — the monthly anchors every later stage joins to (tasks 2.1/2.3, Phase 3).

Daily -> monthly ONCE, so repeated work over the big daily tables (bhav 7.9M rows, adj_close
17.7M after the history trim, delivery 6.3M) becomes joins against 1-2M-row panels:

    month_grid   (m, mdate)                                the decision calendar: each month's
                                                           last EQ trading day
    adj_me       (symbol, m, mdate, adate, adj_close)       last adjusted close of the month
    liq_me       (symbol, m, mdate, med3, n_days)           BRD §4 liquidity: median daily
                                                           turnover over the trailing
                                                           liquidity_lookback_months ending AT
                                                           mdate — the universe-rank input
    deliv_me     (symbol, m, mdate, deliv_per_mean, deliv_qty_sum, n_days)

- adj_me keeps the LAST VALID adjusted print AT OR BEFORE the month's last trading day, inside
  that same month. A month with no valid print yields no row, so a suspended/delisted symbol can
  never be priced from a stale row — correctness, not just speed: the alternative is a years-old
  price silently becoming a monthly return. For months that predate bhav (pre-2011 adj history)
  the calendar month end bounds the value and mdate stays NULL.
  "Valid" matters: Yahoo emits gap/partial days as NaN (467k NULL rows in the quick window),
  and DuckDB's arg_max skips NULLs while a naive pandas keep='last' would pick one up. Rows are
  therefore filtered on value first, and adate always dates the value it is stored with.
- panels are FULL-HISTORY regardless of profile: the profile bounds reported windows, not
  lookback (the rule the canaries already follow), so rank sees complete trailing windows.
- liq_me is pooled, not a median of monthly medians: it pools every daily turnover in the
  window and takes one median, because a median of medians is not a median. It is also
  FULL-HISTORY even when the profile window is shorter, so a decision month's lookback is
  never truncated by the profile start (see rank.py).
- the series filter is a RULE from config (universe.allowed_series), not a hardcoded string:
  month_grid (the decision calendar), liq_me (the rank input) and rank's from-scratch oracle must
  all see the same universe, so series_sql() renders it once. It is also a `cfg:` spec in the
  panel fingerprint — changing the allowed series must rebuild the panels.
- liq_me needs only bhav; adj_me needs adj_close; deliv_me is skipped when the delivery table is
  absent (synthetic fixtures). Rebuildable derived tables; liq_me is the expensive one (~4s full
  history, it is the price of the BRD §4 window) and everything else is ~1-3s.
- ensure(con, cfg) is stamped (src/stamp.py): it rebuilds when the source tables, the panel SQL
  or the config moved, and is a no-op in the steady state — callers (rank, winners, feature
  builds) pay only the fingerprint read.

python -m src.normalize.panels runs the self-check: a dedicated synthetic fixture hand-verifies
the month-end rule (a print after the decision date is ignored, a mid-month last print is kept,
a symbol with no print that month is absent, a pre-bhav month survives with NULL mdate, BE days
never enter the calendar, hand-computed turnover median and delivery aggregates), then the live
build with lookahead and coverage invariants.
"""
import copy
import os
import sys
import tempfile
import time

import duckdb

from src import stamp
from src.config import load

RUPEE_PER_CRORE = 1.0e7  # med3 is rupees; every config floor/report is in ₹ crore

_CORE = ("month_grid", "adj_me", "liq_me")  # ensure() gate; deliv_me is optional
_KEY = "panels"  # stamp key for ensure()

_GRID_SQL = """
CREATE OR REPLACE TABLE month_grid AS
SELECT date_trunc('month', date) AS m, max(date) AS mdate
FROM bhav b WHERE {series} GROUP BY 1
"""

_ADJ_SQL = """
CREATE OR REPLACE TABLE adj_me AS
WITH a AS (SELECT symbol, date_trunc('month', date) AS m, date, adj_close FROM adj_close)
SELECT a.symbol, a.m, g.mdate, max(a.date) AS adate, arg_max(a.adj_close, a.date) AS adj_close
FROM a LEFT JOIN month_grid g ON g.m = a.m
WHERE a.date <= coalesce(g.mdate, last_day(a.m))
  AND a.adj_close IS NOT NULL AND NOT isnan(a.adj_close) AND a.adj_close > 0
GROUP BY 1, 2, 3
"""

_LIQ_SQL = """
CREATE OR REPLACE TABLE liq_me AS
SELECT b.symbol, g.m, g.mdate,
       median(b.turnover) AS med3, count(*) AS n_days
FROM bhav b JOIN month_grid g
  ON b.date > g.mdate - ({lookback} * INTERVAL '1 month') AND b.date <= g.mdate
WHERE {series}
GROUP BY 1, 2, 3
"""

_DELIVERY_SQL = """
CREATE OR REPLACE TABLE deliv_me AS
SELECT d.symbol, date_trunc('month', d.date) AS m, g.mdate,
       avg(d.deliv_per) AS deliv_per_mean, sum(d.deliv_qty) AS deliv_qty_sum, count(*) AS n_days
FROM delivery d LEFT JOIN month_grid g ON g.m = date_trunc('month', d.date)
GROUP BY 1, 2, 3
"""


def has_table(con, table: str) -> bool:
    """Whether a table exists — the gate for optional sources (delivery, surveillance)."""
    return con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = ?",
                       [table]).fetchone()[0] > 0


def series_sql(cfg: dict, alias: str = "b") -> str:
    """The universe's series filter, rendered from config (BRD §4 "EQ series; not in T2T/BE").

    One definition for every consumer: the decision calendar, the liquidity panel and the rank's
    own from-scratch oracle. A hardcoded 'EQ' in three places is how the rule and the config drift
    apart, which is exactly what the plan's working rule 1 forbids.
    """
    vals = ", ".join("'" + str(s).replace("'", "''") + "'" for s in cfg["universe"]["allowed_series"])
    return f"{alias}.series IN ({vals})"


def _fp(cfg: dict, con) -> str:
    """Stamp fingerprint of everything the panels are made of (sources + panel SQL + params).

    The lookback is a `cfg:` spec, not just part of the code hash: changing the config value must
    rebuild liq_me even though no source table and no source line moved.
    """
    return stamp.fingerprint(cfg, con, ["code", "table:bhav.date", "table:delivery.date",
                                        "table:adj_close.date",
                                        "cfg:universe.liquidity_lookback_months",
                                        "cfg:universe.allowed_series"])


def build(con, cfg: dict) -> dict:
    """Rebuild every month-end panel; returns per-panel row counts and elapsed seconds.

    Records its own stamp, so a build done by a self-check also leaves the panels marked fresh.
    """
    t0 = time.monotonic()
    rows = {}
    series = series_sql(cfg)
    for name, sql, needs in (("month_grid", _GRID_SQL.format(series=series), None),
                             ("adj_me", _ADJ_SQL, "adj_close"),
                             ("liq_me", _LIQ_SQL.format(
                                 series=series,
                                 lookback=cfg["universe"]["liquidity_lookback_months"]), None),
                             ("deliv_me", _DELIVERY_SQL, "delivery")):
        if needs and not has_table(con, needs):
            continue  # synthetic fixtures without that source
        con.execute(sql)
        rows[name] = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    st = {"rows": rows, "seconds": time.monotonic() - t0}
    stamp.record(con, _KEY, _fp(cfg, con), outputs=rows, seconds=st["seconds"])
    return st


def ensure(con, cfg: dict) -> bool:
    """Build the panels only when their inputs moved (no-op in the steady state).

    Stamped rather than merely existence-checked (src/stamp.py): the fingerprint covers the
    source tables' (rows, max date), the panel SQL and the config, so panels are rebuilt when
    data or code changed and skipped when neither did — and the stamp re-verifies the panels are
    still present with the row counts they were built with.
    """
    if all(has_table(con, t) for t in _CORE) and stamp.is_current(con, _KEY, _fp(cfg, con)):
        return False
    build(con, cfg)
    return True


def _synth_check() -> None:
    from datetime import date
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    con = duckdb.connect(cfg["paths"]["duckdb"])
    con.execute("""CREATE TABLE bhav (symbol VARCHAR, series VARCHAR, date DATE, open DOUBLE,
        high DOUBLE, low DOUBLE, close DOUBLE, prev_close DOUBLE, last DOUBLE, volume BIGINT,
        turnover DOUBLE, trades BIGINT, isin VARCHAR)""")
    rows = [("X", "EQ", date(2024, 9, d), 100.0, t) for d, t in
            ((5, 1e7), (10, 2e7), (15, 3e7), (20, 4e7), (27, 5e7))]   # last EQ day: Sep 27
    rows += [("Y", "EQ", date(2024, 9, 10), 50.0, 9e7),
             ("Z", "EQ", date(2024, 8, 30), 10.0, 1e6),
             ("Z", "EQ", date(2024, 9, 27), 10.0, 2e6),
             ("W", "BE", date(2024, 9, 27), 7.0, 5e6)]                 # BE never enters the grid
    con.executemany("INSERT INTO bhav (symbol, series, date, close, turnover) VALUES (?,?,?,?,?)", rows)
    con.execute("CREATE TABLE adj_close (symbol VARCHAR, date DATE, adj_close DOUBLE)")
    con.executemany("INSERT INTO adj_close VALUES (?,?,?)", [
        ("X", date(2024, 9, 5), 100.0), ("X", date(2024, 9, 20), 111.0),
        ("X", date(2024, 9, 30), 999.0),        # AFTER the Sep 27 decision date: must be ignored
        ("X", date(2010, 6, 15), 7.0),          # pre-bhav month -> mdate NULL, still a row
        ("Y", date(2024, 8, 30), 50.0),         # no Sep print -> no (Y, Sep) row
        ("Z", date(2024, 9, 10), 12.0)])        # mid-month last print is the month's value
    con.execute("CREATE TABLE delivery (symbol VARCHAR, date DATE, deliv_qty BIGINT, deliv_per DOUBLE)")
    con.executemany("INSERT INTO delivery VALUES (?,?,?,?)", [
        ("X", date(2024, 9, 5), 100, 40.0), ("X", date(2024, 9, 20), 300, 60.0)])
    build(con, cfg)

    grid = con.execute("SELECT m::DATE, mdate FROM month_grid ORDER BY 1").fetchall()
    assert grid == [(date(2024, 8, 1), date(2024, 8, 30)), (date(2024, 9, 1), date(2024, 9, 27))], \
        f"month_grid must be EQ month-ends only (BE ignored), got {grid}"
    adj = {(s, m): (mdate, adate, val) for s, m, mdate, adate, val in con.execute(
        "SELECT symbol, m::DATE, mdate, adate, adj_close FROM adj_me").fetchall()}
    assert adj[("X", date(2024, 9, 1))] == (date(2024, 9, 27), date(2024, 9, 20), 111.0), \
        f"Sep 30 print is after the Sep 27 decision date and must be ignored: {adj[('X', date(2024, 9, 1))]}"
    assert adj[("Z", date(2024, 9, 1))] == (date(2024, 9, 27), date(2024, 9, 10), 12.0), \
        f"mid-month last print must be kept: {adj[('Z', date(2024, 9, 1))]}"
    assert ("Y", date(2024, 9, 1)) not in adj, "a month with no adjusted print must yield no row"
    assert adj[("Y", date(2024, 8, 1))] == (date(2024, 8, 30), date(2024, 8, 30), 50.0), adj[("Y", date(2024, 8, 1))]
    assert adj[("X", date(2010, 6, 1))] == (None, date(2010, 6, 15), 7.0), \
        f"pre-bhav month must survive with NULL mdate: {adj[('X', date(2010, 6, 1))]}"

    # liq_me is the POOLED trailing-window median. At the Sep 27 decision the window is
    # (Jun 27, Sep 27], so Z pools its Aug 30 and Sep 27 rows: median(1e6, 2e6) = 1.5e6 over
    # 2 days — a median of monthly medians would have said 2e6 over 1 day.
    lq = {(s, m): (med, n) for s, m, med, n in con.execute(
        "SELECT symbol, m::DATE, med3, n_days FROM liq_me").fetchall()}
    assert lq[("X", date(2024, 9, 1))] == (3e7, 5), f"median of 1e7..5e7 = 3e7 over 5 days: {lq}"
    assert lq[("Z", date(2024, 9, 1))] == (1.5e6, 2), \
        f"the window must pool August with September: {lq[('Z', date(2024, 9, 1))]}"
    assert lq[("Z", date(2024, 8, 1))] == (1e6, 1), lq[("Z", date(2024, 8, 1))]
    assert ("W", date(2024, 9, 1)) not in lq, "BE turnover must not enter the panel"

    dl = con.execute("SELECT deliv_per_mean, deliv_qty_sum, n_days FROM deliv_me "
                     "WHERE symbol='X' AND m::DATE = '2024-09-01'").fetchone()
    assert dl == (50.0, 400, 2), f"delivery mean/sum wrong: {dl}"

    # ensure() contract (src/stamp.py): a no-op right after a build, a rebuild once the stamp is
    # gone. Cheap here on the 6-row fixture; the live check re-proves the no-op on real panels.
    assert ensure(con, cfg) is False, "ensure() rebuilt panels whose inputs did not change"
    stamp.clear(con, _KEY)
    assert ensure(con, cfg) is True, "ensure() must rebuild when its stamp is missing"
    assert ensure(con, cfg) is False, "ensure() must be a no-op after rebuilding"
    con.close()
    print("synthetic check passed (month-end rule, after-date print ignored, no-print month absent, "
          "pre-bhav month NULL mdate, hand-computed medians, ensure() skip/rebuild contract)",
          flush=True)


def _live_check(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        st = build(con, cfg)
        print(f"panels in {st['seconds']:.1f}s: "
              + ", ".join(f"{k} {v:,}" for k, v in st["rows"].items()), flush=True)
        assert ensure(con, cfg) is False, \
            "ensure() must be a no-op straight after a build — callers rely on it to skip"
        leak = con.execute("SELECT count(*) FROM adj_me "
                           "WHERE mdate IS NOT NULL AND adate > mdate").fetchone()[0]
        assert leak == 0, f"{leak} adj_me rows priced AFTER their month's decision date (lookahead)"
        if has_table(con, "eligible"):
            # A missing adj_me row is only a BUG when a valid print existed in that month.
            # For delisted/renamed tickers Yahoo has no print at all (BRD §4 survivorship bias) —
            # those 1,3xx symbols legitimately have no monthly price, and the fixture-proven
            # panel must not contort to invent one.
            bug = con.execute("""
                SELECT count(*) FROM eligible e
                LEFT JOIN adj_me a ON a.symbol = e.symbol AND a.m = date_trunc('month', e.mdate)
                WHERE e.eligible AND a.symbol IS NULL AND EXISTS (
                    SELECT 1 FROM adj_close x
                    WHERE x.symbol = e.symbol AND x.adj_close IS NOT NULL AND x.adj_close > 0
                      AND date_trunc('month', x.date) = date_trunc('month', e.mdate))""").fetchone()[0]
            assert bug == 0, \
                f"{bug} eligible symbol-months lost a valid in-month price (panel bug, not coverage)"
            n = con.execute("SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]
            holes, syms = con.execute("""
                SELECT count(*), count(DISTINCT e.symbol) FROM eligible e
                LEFT JOIN adj_me a ON a.symbol = e.symbol AND a.m = date_trunc('month', e.mdate)
                WHERE e.eligible AND a.symbol IS NULL""").fetchone()
            print(f"panels cover {n - holes:,}/{n:,} eligible symbol-months ({(n - holes) / n:.1%}); "
                  f"the rest ({syms:,} unpriceable symbols) have no Yahoo print at all", flush=True)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: month-end panels (synthetic hand-values + live lookahead/coverage invariants)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
