"""Task 2.3 — monthly winners: top 5% of eligible stocks by adjusted return (BRD §4).

Per decision month M (mdate = last trading day of M):
  pool  = symbols ELIGIBLE at the PRIOR decision date (the §7 decision happens after M-1's
          close; M's own close is not yet known — no lookahead). A symbol that falls out of
          the universe during M still counts (it was tradeable at the decision).
  ret   = adj_me(M month) / adj_me((M-1) month) - 1 from the month-end panels (panels.py):
          the last adjusted print INSIDE each month, so a stale cross-month price can never
          become a return. A >40-day decision gap = suspension break — no return, no winner.
  labels: winner = top 5% (percent_rank < 0.05, ties share the label, counts scale with the
          pool); secondary top-decile and top-20 (row_number, ties broken by symbol).

Output `winners(mdate, symbol, ret, is_winner, is_top_decile, is_top20)`. This is the LABEL
table only — the monthly pick ranking (§7/§8 model score) is a later phase.

python -m src.universe.winners self-check: synthetic hand-computed returns/labels (incl. the
all-tie month), then live: label-count invariants + n random months recomputed EXACTLY by an
independent from-scratch pandas pass over the sampled months only (returns < 1e-9, winner
sets identical).
"""
import random
import sys

import duckdb

from src.config import load
from src.normalize import panels
from src.universe import eligibility, rank

_WINNERS_SQL = """
CREATE OR REPLACE TABLE winners AS
WITH cal AS (SELECT DISTINCT mdate FROM universe_rank),
pool AS (
    SELECT e.symbol, e.mdate AS d_start, date_trunc('month', e.mdate) AS m_start,
           (SELECT min(c.mdate) FROM cal c WHERE c.mdate > e.mdate) AS d_end
    FROM eligible e
    WHERE e.eligible
),
ar AS (
    SELECT p.d_end AS mdate, p.symbol,
           a1.adj_close / a0.adj_close - 1.0 AS ret
    FROM pool p
    JOIN adj_me a1 ON a1.symbol = p.symbol AND a1.m = date_trunc('month', p.d_end)
    JOIN adj_me a0 ON a0.symbol = p.symbol AND a0.m = p.m_start
    WHERE p.d_end IS NOT NULL
      AND date_diff('day', p.d_start, p.d_end) <= 40
      AND a1.adj_close > 0 AND a0.adj_close > 0
      -- label only COMPLETE calendar months: an unfinished month's return would be a
      -- provisional short-month number that silently changes as the month goes on
      AND last_day(p.d_end) <= '{end}'::DATE
),
lbl AS (
    SELECT mdate, symbol, ret,
           percent_rank() OVER (PARTITION BY mdate ORDER BY ret DESC) AS pct,
           row_number() OVER (PARTITION BY mdate ORDER BY ret DESC, symbol) AS rn
    FROM ar
)
SELECT mdate, symbol, ret,
       pct < {winner_pct} AS is_winner,
       pct < {decile_pct} AS is_top_decile,
       rn <= {top20} AS is_top20
FROM lbl
"""


def build(con, cfg: dict) -> dict:
    s, w = cfg["stats"], cfg["stats"]["secondary_winner_labels"]
    con.execute(_WINNERS_SQL.format(winner_pct=s["winner_top_pct"],
                                    decile_pct=w["top_decile_pct"], top20=w["top_n_abs"],
                                    end=cfg["end_date"]))
    months, nw = con.execute(
        "SELECT count(DISTINCT mdate), count(*) FILTER (WHERE is_winner) FROM winners").fetchone()
    return {"months": months, "winners": nw}


def _synth_check() -> None:
    import copy
    import os
    import tempfile
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["data_start_date"], cfg["end_date"] = "2024-01-01", "2024-09-30"
    cfg["universe"]["top_n"] = 4
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    con = duckdb.connect(cfg["paths"]["duckdb"])
    rank.synth_setup(con)                      # Sep closes: A 130 (+30%), Y 5.5 (+10%), rest flat
    con.execute("CREATE TABLE adj_close (symbol VARCHAR, date DATE, adj_close DOUBLE)")
    con.execute("INSERT INTO adj_close SELECT symbol, date, close FROM bhav WHERE series='EQ'")
    panels.build(con, cfg)                     # month_grid + adj_me + liq_me from the fixture
    rank.build(con, cfg)
    eligibility.build(con, cfg)
    build(con, cfg)

    sep = {s: (r, wi, d, t) for s, r, wi, d, t in con.execute(
        "SELECT symbol, ret, is_winner, is_top_decile, is_top20 FROM winners "
        "WHERE mdate = '2024-09-30'").fetchall()}
    # pool = eligible at the Aug 31 DECISION = {A, B, C} (D listed<6m, Y price+rank).
    # Sep returns: A +30% (100 -> 130), B 0% (100 -> 100), C 0% (50 -> 50).
    assert set(sep) == {"A", "B", "C"}, f"Sep pool wrong: {sorted(sep)}"
    assert abs(sep["A"][0] - 0.30) < 1e-12 and sep["A"][1:] == (True, True, True), \
        f"A must be the Sep winner: {sep['A']}"
    assert sep["B"][1] is False and sep["B"][3] is True, f"B: {sep['B']}"
    assert sep["C"][1] is False and sep["C"][3] is True, f"C: {sep['C']}"

    aug = {s: wi for s, wi in con.execute(
        "SELECT symbol, is_winner FROM winners WHERE mdate = '2024-08-31'").fetchall()}
    # Aug: pool from Jul = {A, B, C}, all returns 0.0 -> percent_rank ties -> EVERYONE wins
    # (documented tie semantics: labels scale by percentile, ties share them)
    assert aug == {"A": True, "B": True, "C": True}, f"all-tie month must crown everyone: {aug}"
    con.close()
    print("synthetic check passed (hand-computed returns, labels, tie semantics)", flush=True)


def _month_last(adj, end):
    """{symbol: (date, adj_close)} of the last VALID adjusted print inside `end`'s month.

    Mirrors the adj_me panel rule exactly: only rows with a real value count (Yahoo marks gap
    days NaN — a keep='last' that kept one would disagree with the panel's arg_max), and a
    month with no valid print yields no entry, so nothing is priced from a stale month.
    """
    win = adj[(adj.date >= end.replace(day=1)) & (adj.date <= end)]
    win = win[win.adj_close.notna() & (win.adj_close > 0)]
    return win.drop_duplicates("symbol", keep="last").set_index("symbol")[["date", "adj_close"]]


def _raw_spot_check(con, cfg: dict, n: int = 10) -> None:
    """Done-when: n random months, an INDEPENDENT from-scratch recompute (pandas, not the
    winners SQL) reproduces per-symbol returns to 1e-9 and winner sets EXACTLY — 10/10.
    Catches every wiring bug: wrong month-end dates, wrong pool, wrong month pairing,
    off-by-one months, label/threshold drift.

    Cost shape: only the sampled months' adjusted rows are loaded (hundreds of thousands
    instead of the whole table) and each month-end lookup is one sorted drop_duplicates pass
    rather than a full-frame mask per end — the same numbers for a fraction of the work.

    ponytail: the recompute shares adj_close — price-source validity is owned by Phase 1's
    20-symbol NSE<->Yahoo cross-check. Raw bhav ratios are NOT a usable return oracle
    (measured live, Feb 2026: 149/1,279 names diverge >5pts because NSE and Yahoo place
    dividend adjustments differently, in both directions). BRD §4 rules: adjusted closes.
    """
    import pandas as pd
    months = [r[0] for r in con.execute(
        "SELECT DISTINCT mdate FROM winners ORDER BY 1").fetchall()]
    rng = random.Random(cfg["backtest"]["random_seed"])
    sample = rng.sample(months, min(n, len(months)))
    prevs = {d: con.execute("SELECT max(mdate) FROM (SELECT DISTINCT mdate FROM universe_rank "
                            "WHERE mdate < ?::DATE)", [d]).fetchone()[0] for d in sample}
    lo = min(pd.Timestamp(str(p)) for p in prevs.values()).replace(day=1)  # earliest month needed
    adj = con.execute("SELECT symbol, date, adj_close FROM adj_close WHERE date >= ?",
                      [lo]).fetch_df()
    adj["date"] = pd.to_datetime(adj["date"])
    adj = adj.sort_values("date")          # once: keep='last' below then means latest date
    print(f"  recompute input: {len(adj):,} adjusted rows from {lo.date()} "
          f"(scoped to the sampled months)", flush=True)
    for d in sample:
        prev = prevs[d]
        ends = [pd.Timestamp(str(prev)), pd.Timestamp(str(d))]
        table = dict(con.execute(
            "SELECT symbol, ret FROM winners WHERE mdate = ?::DATE", [d]).fetchall())
        pool = {s for (s,) in con.execute(
            "SELECT symbol FROM eligible WHERE mdate = ?::DATE AND eligible", [prev]).fetchall()}
        if (ends[1] - ends[0]).days > 40:      # the SQL's suspension break
            assert not table, f"{d}: >40-day decision gap must produce no winners"
            continue
        a0, a1 = (_month_last(adj, e) for e in ends)
        common = sorted(set(pool) & set(a0.index) & set(a1.index))
        j = a0.loc[common].join(a1.loc[common], lsuffix="_s", rsuffix="_e")
        j = j[(j.adj_close_s > 0) & (j.adj_close_e > 0)]
        j["ret"] = j.adj_close_e / j.adj_close_s - 1.0
        # winners SQL labels: percent_rank() = (rank-1)/(n-1) over ret DESC, ties share
        n_rows = len(j)
        pct = (j.ret.rank(ascending=False, method="min") - 1) / (n_rows - 1)
        recomp_win = set(j.index[pct < cfg["stats"]["winner_top_pct"]])
        table_win = {s for (s,) in con.execute(
            "SELECT symbol FROM winners WHERE mdate = ?::DATE AND is_winner", [d]).fetchall()}
        assert set(j.index) == set(table), \
            f"{d}: recompute pool {len(j)} != winners pool {len(table)}"
        worst = max(abs(j.loc[s, "ret"] - table[s]) for s in j.index)
        assert worst < 1e-9, f"{d}: per-symbol returns differ, worst {worst:.2e}"
        assert recomp_win == table_win, \
            f"{d}: winner sets differ: {sorted(recomp_win ^ table_win)[:8]}"
    print(f"independent recompute: {len(sample)}/{len(sample)} months match exactly "
          f"(returns < 1e-9, winner sets identical)", flush=True)


def _live_check(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        panels.ensure(con, cfg)
        if con.execute("SELECT count(*) FROM duckdb_tables() "
                       "WHERE table_name = 'universe_rank'").fetchone()[0] == 0:
            rank.build(con, cfg)
        if con.execute("SELECT count(*) FROM duckdb_tables() "
                       "WHERE table_name = 'eligible'").fetchone()[0] == 0:
            eligibility.build(con, cfg)
        st = build(con, cfg)
        assert st["months"] >= 10, f"only {st['months']} winner months — quick profile expects ~11"
        print(f"winners: {st['winners']:,} winner rows over {st['months']} months", flush=True)

        last = con.execute("SELECT max(mdate) FROM winners").fetchone()[0]
        nw = con.execute("SELECT count(*) FROM winners WHERE mdate = ? AND is_winner", [last]).fetchone()[0]
        ne = con.execute("SELECT count(*) FROM eligible WHERE mdate = ? AND eligible", [last]).fetchone()[0]
        assert abs(nw - 0.05 * ne) <= max(3, 0.01 * ne), \
            f"winner count {nw} vs 5% of {ne} eligible at {last}"
        bad = con.execute("""SELECT count(*) FROM (
                SELECT mdate FROM winners WHERE is_top20 GROUP BY 1
                HAVING count(*) != 20)""").fetchone()[0]
        assert bad == 0, f"{bad} months where top-20 count != 20"
        bad = con.execute("SELECT count(*) FROM winners WHERE ret IS NULL OR isnan(ret) "
                          "OR abs(ret) > 10").fetchone()[0]
        assert bad == 0, f"{bad} rows with NULL/NaN/absurd returns"
        _raw_spot_check(con, cfg)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: winners (synthetic labels + live count invariants + 10-month raw recompute)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
