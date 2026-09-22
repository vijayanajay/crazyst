"""BRD §11 canary checks (plan Phase 1 gate: must pass before Phase 3 experiments run).

  1. momentum IC positive    — 12M-1M adjusted momentum (lag 252 -> 21 trading days) vs
                               next-month return, Spearman IC per month-end, pooled median > 0.
                               Uses adj_close FULL history: the profile bounds the backtest
                               window, not feature lookback. ponytail: a delisted symbol's last
                               partial month becomes a pseudo month-end whose next-month return
                               is truncated — dropped (NULL) or slightly short; the median over
                               ~190 months is robust to it.
  2. delivery% autocorr      — monthly mean delivery% vs its 1-month lag, pooled Spearman over
                               liquid proxies (symbols observed in >= 12 distinct months,
                               >= 10 delivery rows in the month), above the config floor.
  3. eligible count stable   — proxy-eligible count per month (EQ, close >= price floor,
                               top-1500 by trailing 3-month median turnover) within ±20%
                               month-over-month. ponytail: proxy skips T2T/BE, listing-age and
                               GSM rules (task 2.2 owns real eligibility); the canary only
                               needs count STABILITY, not exact eligibility. Trailing median is
                               over the symbol's own last 3 observed months, not calendar months.

`python -m src.validate.canary` runs all three against the real DB and exits non-zero on
failure. A failed canary blocks experiments (BRD §11).
"""
import sys

import duckdb
import pandas as pd

from src.config import load

MOM_LAG, MOM_SKIP = 252, 21  # 12M-1M momentum in trading days (BRD §11 names the 6-12M family)


def _spearman(x: pd.Series, y: pd.Series) -> float:
    """Spearman == Pearson on average ranks; avoids the scipy dependency (BRD §13 rule)."""
    return x.rank().corr(y.rank())


def momentum_ic(con, cfg: dict) -> tuple[float, int]:
    v = cfg["validate"]
    df = con.execute(f"""
        WITH a AS (
            SELECT symbol, date, adj_close,
                   lag(adj_close, {MOM_LAG}) OVER w AS m_long,
                   lag(adj_close, {MOM_SKIP}) OVER w AS m_skip,
                   lead(date) OVER w AS next_d
            FROM adj_close
            WINDOW w AS (PARTITION BY symbol ORDER BY date)
        ),
        me AS (
            SELECT symbol, date, adj_close, m_long, m_skip
            FROM a
            WHERE next_d IS NULL OR date_trunc('month', next_d) != date_trunc('month', date)
        ),
        p AS (
            SELECT symbol, date, m_long, m_skip,
                   m_skip / m_long - 1.0 AS mom,  -- 12M-1M: P(t-21) vs P(t-252); the inverted
                   -- ratio silently measures REVERSAL (caught live: IC -0.05 -> +0.05 after fix)
                   lead(adj_close) OVER w2 / adj_close - 1.0 AS fwd_ret
            FROM me
            WINDOW w2 AS (PARTITION BY symbol ORDER BY date)
        )
        SELECT date, mom, fwd_ret FROM p
        WHERE m_long IS NOT NULL AND m_skip IS NOT NULL AND m_skip > 0 AND fwd_ret IS NOT NULL
    """).fetch_df()
    ics = [_spearman(g["mom"], g["fwd_ret"])
           for _, g in df.groupby("date") if len(g) >= v["canary_min_ic_names"]]
    assert len(ics) >= v["canary_min_ic_months"], \
        (f"momentum IC: only {len(ics)} month-ends with >= {v['canary_min_ic_names']} names "
         f"(got {len(df):,} rows) — adj_close backfill incomplete?")
    pooled = float(pd.Series(ics).median())
    assert pooled > 0, f"momentum canary FAILED: pooled median IC {pooled:.4f} <= 0 over {len(ics)} months"
    return pooled, len(ics)


def delivery_autocorr(con, cfg: dict) -> tuple[float, int]:
    v = cfg["validate"]
    df = con.execute("""
        SELECT symbol, date_trunc('month', date) AS m, avg(deliv_per) AS dp
        FROM delivery GROUP BY 1, 2 HAVING count(*) >= 10
    """).fetch_df()
    months = df.groupby("symbol")["m"].nunique()
    df = df[df["symbol"].isin(months[months >= 12].index)].sort_values(["symbol", "m"])
    df["dp_lag"] = df.groupby("symbol")["dp"].shift(1)
    df["m_lag"] = df.groupby("symbol")["m"].shift(1)
    pairs = df[((df["m"] - df["m_lag"]).dt.days <= 40)]  # consecutive calendar months only
    pairs = pairs.dropna(subset=["dp", "dp_lag"])
    assert len(pairs) >= v["canary_min_deliv_pairs"], \
        (f"delivery autocorr: only {len(pairs):,} consecutive-month pairs "
         f"(< {v['canary_min_deliv_pairs']:,}) — delivery cache too sparse? finish the backfill first")
    r = _spearman(pairs["dp"], pairs["dp_lag"])
    assert r > v["canary_min_deliv_autocorr"], \
        f"delivery canary FAILED: pooled autocorr {r:.3f} <= {v['canary_min_deliv_autocorr']} over {len(pairs):,} pairs"
    return r, len(pairs)


_ELIG_SQL = """
WITH eq AS (SELECT symbol, date, close, turnover FROM bhav WHERE series = 'EQ'),
mt AS (SELECT symbol, date_trunc('month', date) AS m, median(turnover) AS med_t
       FROM eq GROUP BY 1, 2),
r AS (SELECT symbol, m, med_t,
             median(med_t) OVER (PARTITION BY symbol ORDER BY m
                                 ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS med3
      FROM mt),
lc AS (SELECT symbol, date_trunc('month', date) AS m, arg_max(close, date) AS last_close
       FROM eq GROUP BY 1, 2),
j AS (SELECT r.symbol, r.m, r.med3, lc.last_close
      FROM r JOIN lc USING (symbol, m) WHERE r.med3 IS NOT NULL),
ranked AS (SELECT *, row_number() OVER (PARTITION BY m ORDER BY med3 DESC) AS rk FROM j)
SELECT m, count(*) AS n FROM ranked
WHERE rk <= {top_n} AND last_close >= {min_price}
GROUP BY 1 ORDER BY 1
"""


def eligible_stable(con, cfg: dict) -> list[tuple]:
    u = cfg["universe"]
    rows = con.execute(_ELIG_SQL.format(top_n=u["top_n"], min_price=u["min_price"])).fetchall()
    assert len(rows) >= 3, f"eligible counts: only {len(rows)} months of data"
    for (m0, n0), (m1, n1) in zip(rows, rows[1:]):
        ratio = n1 / n0 if n0 else 0.0
        assert 0.80 <= ratio <= 1.25, \
            f"eligible count canary FAILED: {m1} count {n1} vs {m0} count {n0} (ratio {ratio:.2f} outside ±20%)"
    return rows


def _self_check() -> None:
    cfg = load("quick")
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        has_adj = con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = 'adj_close'").fetchone()[0]
        assert has_adj, "adj_close table missing — run python -m src.normalize.adj_close --backfill first (task 1.6)"
        n_adj = con.execute("SELECT count(DISTINCT symbol) FROM adj_close").fetchone()[0]
        n_eq = con.execute("SELECT count(DISTINCT symbol) FROM bhav WHERE series = 'EQ'").fetchone()[0]
        cov = n_adj / n_eq
        assert cov >= cfg["validate"]["canary_min_adj_coverage"], \
            f"adj_close coverage {cov:.1%} < {cfg['validate']['canary_min_adj_coverage']:.0%} — backfill incomplete"
        print(f"[0] adj_close coverage: {n_adj:,}/{n_eq:,} EQ symbols ({cov:.1%})", flush=True)

        ic, nm = momentum_ic(con, cfg)
        print(f"[1] momentum IC: pooled median {ic:+.4f} > 0 over {nm} month-ends "
              f"({MOM_LAG}-{MOM_SKIP}d adjusted momentum, Spearman)", flush=True)

        r, npairs = delivery_autocorr(con, cfg)
        print(f"[2] delivery% autocorr: {r:.3f} > {cfg['validate']['canary_min_deliv_autocorr']} "
              f"over {npairs:,} consecutive-month pairs (liquid proxy)", flush=True)

        rows = eligible_stable(con, cfg)
        print(f"[3] eligible count stable: {len(rows)} months, {rows[0][1]:,} -> {rows[-1][1]:,}, "
              f"every month-over-month ratio within ±20%", flush=True)
    finally:
        con.close()
    print("PASS: all BRD §11 canaries")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
