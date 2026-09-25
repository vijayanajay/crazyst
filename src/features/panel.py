"""Phase 3 panel-wide features: monthly momentum, daily volume structure, delivery, volatility
state and candlesticks.

`feature_panel` contains one row per eligible symbol-month. One DuckDB CTAS computes the whole
panel; no Python loop performs per-symbol or per-month feature calculations.

Monthly momentum (BRD §6): adjusted close M versus M-1, M-3, M-6 and M-12-to-M-1.
Daily features are sampled on each eligible decision date. Windows use the EQ session calendar,
with absent symbol/session data left NULL rather than shifting a lag or being treated as zero:
  volume_zscore             current raw volume vs previous 20 sessions
  up_down_volume_ratio      raw volume on up-close days / down-close days, last 20 sessions
  breakout_volume_confirmed adjusted close above previous 20 adjusted highs, with volume above
                            the previous 20-session mean
  delivery_pct              current day's NSE delivery percentage (no carry-forward)
  delivery_pct_zscore       current delivery% vs previous 20 delivery observations
  delivery_pct_trend        current delivery% minus value 20 exchange sessions earlier
  delivery_spike_while_flat delivery z-score above threshold with a flat 5-session adjusted return
  atr_ratio                 mean 14-session adjusted true range before the day, over the close
  nr7                       decision-day true range is the narrowest of the last 7 sessions
  squeeze_days_20d          sessions in the last 20 whose true range is under the configured
                            squeeze fraction of their own prior-20-session mean true range
  range_compression_20d     mean (adjusted high - adjusted low) / adjusted close, last 20 sessions
  close_in_range            decision-day close position within its adjusted high-low range
  upper_wick_ratio          upper wick / range of the decision day
  lower_wick_ratio          lower wick / range of the decision day
  consec_higher_lows        consecutive rising adjusted lows ending at the decision day
  big_body_day_in_trend     body above the big-body multiple of the prior-20 mean, aligned with
                            the 20-session trend direction

The rolling windows end at the decision date; monthly returns and daily feature inputs are never
forward-filled. Missing/incomplete lookbacks produce SQL NULL (pandas NaN), not zero.

`python -m src.features.panel` runs hand-computed synthetic checks, including missing sessions,
missing delivery, empty inputs, and future-data isolation, then verifies the live quick profile.
"""
import calendar
import math
import os
import sys
import tempfile
import time
from datetime import date, timedelta

import duckdb

from src.config import load
from src.normalize import panels

_FEATURES = (
    "mom_1m", "mom_3m", "mom_6m", "mom_12m_1m",
    "volume_zscore", "up_volume_20d", "down_volume_20d", "up_down_volume_ratio",
    "breakout_volume_confirmed", "delivery_pct", "delivery_pct_zscore",
    "delivery_pct_trend", "delivery_spike_while_flat",
    "atr_ratio", "nr7", "squeeze_days_20d", "range_compression_20d",
    "close_in_range", "upper_wick_ratio", "lower_wick_ratio",
    "consec_higher_lows", "big_body_day_in_trend",
)
_NUMERIC_FEATURES = (
    "mom_1m", "mom_3m", "mom_6m", "mom_12m_1m", "volume_zscore",
    "up_volume_20d", "down_volume_20d", "up_down_volume_ratio",
    "delivery_pct", "delivery_pct_zscore", "delivery_pct_trend",
    "atr_ratio", "range_compression_20d", "close_in_range",
    "upper_wick_ratio", "lower_wick_ratio",
)

_SQL = """
CREATE OR REPLACE TABLE feature_panel AS
WITH
    decisions AS (
        SELECT symbol, mdate FROM eligible WHERE eligible
    ),
    bounds AS (
        SELECT min(mdate) AS min_date, max(mdate) AS max_date FROM decisions
    ),
    symbols AS (
        SELECT DISTINCT symbol FROM decisions
    ),
    market_days AS ({market_days}),
    calendar AS (
        SELECT date, row_number() OVER (ORDER BY date) AS session_no
        FROM market_days
    ),
    decision_bounds AS (

        SELECT min(c.session_no) AS min_session, max(c.session_no) AS max_session
        FROM decisions d JOIN calendar c ON c.date = d.mdate
    ),
    source_days AS (
        -- One warm-up session beyond the longest window: true range needs a previous close,
        -- so without it the first decision month's TR-based windows are one observation short.
        SELECT c.date, c.session_no FROM calendar c CROSS JOIN decision_bounds b
        WHERE c.session_no BETWEEN b.min_session - {lookback} - 1 AND b.max_session
    ),
    daily AS (
{daily}
    ),
    daily_ordered AS (
        SELECT d.*,
               lag(adj_close, 1) OVER w AS previous_adj_close,
               lag(adj_close, {flat_sessions}) OVER w AS flat_adj_close,
               lag(deliv_per, {lookback}) OVER w AS prior_deliv_per,
               lag(adj_low, 1) OVER w AS previous_adj_low,
               lag(adj_close, {lookback}) OVER w AS trend_ref_close
        FROM daily d
        WINDOW w AS (PARTITION BY symbol ORDER BY session_no)
    ),
    daily_tr AS (
        SELECT *,
               CASE WHEN previous_adj_close IS NOT NULL AND adj_high IS NOT NULL
                          AND adj_low IS NOT NULL
                    THEN greatest(adj_high - adj_low, abs(adj_high - previous_adj_close),
                                  abs(adj_low - previous_adj_close)) END AS true_range,
               CASE WHEN adj_open IS NOT NULL AND adj_close IS NOT NULL
                    THEN abs(adj_close - adj_open) END AS body,
               CASE WHEN adj_high IS NOT NULL AND adj_low IS NOT NULL AND adj_close IS NOT NULL
                          AND adj_close > 0 AND adj_high > adj_low
                    THEN (adj_high - adj_low) / adj_close END AS range_frac,
               CASE WHEN adj_close IS NOT NULL AND adj_high IS NOT NULL AND adj_low IS NOT NULL
                          AND adj_high > adj_low
                    THEN (adj_close - adj_low) / (adj_high - adj_low) END AS close_in_range,
               CASE WHEN adj_open IS NOT NULL AND adj_close IS NOT NULL AND adj_high IS NOT NULL
                          AND adj_low IS NOT NULL AND adj_high > adj_low
                    THEN (adj_high - greatest(adj_open, adj_close)) / (adj_high - adj_low)
                    END AS upper_wick_ratio,
               CASE WHEN adj_open IS NOT NULL AND adj_close IS NOT NULL AND adj_high IS NOT NULL
                          AND adj_low IS NOT NULL AND adj_high > adj_low
                    THEN (least(adj_open, adj_close) - adj_low) / (adj_high - adj_low)
                    END AS lower_wick_ratio,
               CASE WHEN adj_low IS NOT NULL AND previous_adj_low IS NOT NULL
                    THEN adj_low > previous_adj_low END AS higher_low_flag,
               CASE WHEN adj_low IS NOT NULL AND previous_adj_low IS NOT NULL
                          AND adj_low > previous_adj_low THEN 0 ELSE 1 END AS run_reset
        FROM daily_ordered
    ),
    daily_rolling AS (
        SELECT *,
               count(volume) OVER prior AS prior_volume_n,
               avg(volume) OVER prior AS prior_volume_mean,
               stddev_samp(volume) OVER prior AS prior_volume_sd,
               count(adj_high) OVER prior AS prior_high_n,
               max(adj_high) OVER prior AS prior_high_max,
               count(deliv_per) OVER prior AS prior_delivery_n,
               avg(deliv_per) OVER prior AS prior_delivery_mean,
               stddev_samp(deliv_per) OVER prior AS prior_delivery_sd,
               sum(CASE WHEN adj_close > previous_adj_close THEN volume ELSE 0 END)
                   OVER recent AS raw_up_volume,
               sum(CASE WHEN adj_close < previous_adj_close THEN volume ELSE 0 END)
                   OVER recent AS raw_down_volume,
               count(*) FILTER (WHERE adj_close IS NOT NULL AND previous_adj_close IS NOT NULL
                                AND volume IS NOT NULL) OVER recent AS direction_n,
               count(true_range) OVER atrwin AS prior_atr_n,
               avg(true_range) OVER atrwin AS prior_atr_mean,
               count(true_range) OVER nr7win AS nr7_n,
               min(true_range) OVER nr7win AS nr7_min,
               count(true_range) OVER prior AS prior_tr_n_20,
               avg(true_range) OVER prior AS prior_tr_mean_20,
               count(body) OVER prior AS prior_body_n,
               avg(body) OVER prior AS prior_body_mean,
               count(range_frac) OVER recent AS recent_range_n,
               avg(range_frac) OVER recent AS recent_range_mean,
               count(true_range) OVER recent AS recent_tr_n,
               sum(run_reset) OVER run AS run_grp
        FROM daily_tr
        WINDOW prior AS (PARTITION BY symbol ORDER BY session_no
                         ROWS BETWEEN {lookback} PRECEDING AND 1 PRECEDING),
               recent AS (PARTITION BY symbol ORDER BY session_no
                          ROWS BETWEEN {lookback_minus_one} PRECEDING AND CURRENT ROW),
               atrwin AS (PARTITION BY symbol ORDER BY session_no
                          ROWS BETWEEN {atr} PRECEDING AND 1 PRECEDING),
               nr7win AS (PARTITION BY symbol ORDER BY session_no
                          ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING),
               run AS (PARTITION BY symbol ORDER BY session_no ROWS UNBOUNDED PRECEDING)
    ),
    daily_streaks AS (
        SELECT *, row_number() OVER (PARTITION BY symbol, run_grp ORDER BY session_no) AS run_pos
        FROM daily_rolling
    ),
    daily_stats AS (
        SELECT *,
               CASE WHEN prior_volume_n = {lookback} AND volume IS NOT NULL THEN
                   CASE WHEN prior_volume_sd > 0
                        THEN (volume - prior_volume_mean) / prior_volume_sd
                        WHEN volume = prior_volume_mean THEN 0.0 END
               END AS volume_zscore,
               CASE WHEN direction_n = {lookback} THEN raw_up_volume END AS up_volume,
               CASE WHEN direction_n = {lookback} THEN raw_down_volume END AS down_volume,
               CASE WHEN direction_n = {lookback} AND raw_down_volume > 0
                    THEN raw_up_volume / raw_down_volume END AS up_down_volume_ratio,
               CASE WHEN prior_high_n = {lookback} AND prior_volume_n = {lookback}
                          AND adj_close IS NOT NULL AND volume IS NOT NULL
                    THEN adj_close > prior_high_max AND volume > prior_volume_mean END
                    AS breakout_volume_confirmed,
               CASE WHEN prior_delivery_n = {lookback} AND deliv_per IS NOT NULL THEN
                   CASE WHEN prior_delivery_sd > 0
                        THEN (deliv_per - prior_delivery_mean) / prior_delivery_sd
                        WHEN deliv_per = prior_delivery_mean THEN 0.0 END
               END AS delivery_pct_zscore,
               CASE WHEN deliv_per IS NOT NULL AND prior_deliv_per IS NOT NULL
                    THEN deliv_per - prior_deliv_per END AS delivery_pct_trend,
               CASE WHEN prior_atr_n = {atr} AND true_range IS NOT NULL
                          AND prior_atr_mean > 0 AND adj_close > 0
                    THEN prior_atr_mean / adj_close END AS atr_ratio,
               CASE WHEN nr7_n = 6 AND true_range IS NOT NULL
                    THEN true_range <= nr7_min END AS nr7,
               CASE WHEN recent_tr_n = {lookback}
                    THEN sum(CASE WHEN prior_tr_n_20 = {lookback} AND true_range IS NOT NULL
                                       AND prior_tr_mean_20 > 0
                                       AND true_range < {squeeze_frac} * prior_tr_mean_20
                                  THEN 1 ELSE 0 END) OVER recent END AS squeeze_days_20d,
               CASE WHEN recent_range_n = {lookback}
                    THEN recent_range_mean END AS range_compression_20d,
               CASE WHEN higher_low_flag IS NULL THEN NULL
                    WHEN higher_low_flag THEN run_pos - 1 ELSE 0 END AS consec_higher_lows,
               CASE WHEN prior_body_n = {lookback} AND body IS NOT NULL AND prior_body_mean > 0
                          AND trend_ref_close IS NOT NULL AND adj_open IS NOT NULL
                    THEN body > {big_body_mult} * prior_body_mean
                         AND ((adj_close > trend_ref_close AND adj_close > adj_open)
                              OR (adj_close < trend_ref_close AND adj_close < adj_open)) END
                    AS big_body_day_in_trend
        FROM daily_streaks
        WINDOW recent AS (PARTITION BY symbol ORDER BY session_no
                          ROWS BETWEEN {lookback_minus_one} PRECEDING AND CURRENT ROW)
    ),
    daily_features AS (
        SELECT *,
               CASE WHEN delivery_pct_zscore IS NULL OR adj_close IS NULL
                          OR flat_adj_close IS NULL OR flat_adj_close <= 0
                    THEN NULL
                    ELSE delivery_pct_zscore >= {spike_z}
                         AND abs(adj_close / flat_adj_close - 1.0) <= {flat_return}
               END AS delivery_spike_while_flat
        FROM daily_stats
    ),
    decision_daily_features AS (
        SELECT f.* FROM daily_features f JOIN decisions d
          ON d.symbol = f.symbol AND d.mdate = f.date
    ),
    months AS (
        SELECT unnest(generate_series(
            date_trunc('month', min_date) - INTERVAL '12 months',
            date_trunc('month', max_date), INTERVAL '1 month')) AS m
        FROM bounds
        WHERE min_date IS NOT NULL AND max_date IS NOT NULL AND min_date <= max_date
    ),
    monthly_adj AS ({monthly_adj}),
    monthly_valid AS (
        SELECT symbol, m, adj_close FROM monthly_adj
        WHERE adj_close IS NOT NULL AND isfinite(adj_close) AND adj_close > 0
    ),
    monthly_spine AS (
        SELECT s.symbol, months.m, a.adj_close
        FROM symbols s CROSS JOIN months
        LEFT JOIN monthly_valid a ON a.symbol = s.symbol AND a.m = months.m
    ),
    monthly_lagged AS (
        SELECT symbol, m, adj_close,
               lag(adj_close, 1) OVER w AS close_1m,
               lag(adj_close, 3) OVER w AS close_3m,
               lag(adj_close, 6) OVER w AS close_6m,
               lag(adj_close, 12) OVER w AS close_12m
        FROM monthly_spine
        WINDOW w AS (PARTITION BY symbol ORDER BY m)
    ),
    monthly_features AS (
        SELECT symbol, m,
               CASE WHEN adj_close > 0 AND close_1m > 0
                    THEN adj_close / close_1m - 1.0 END AS mom_1m,
               CASE WHEN adj_close > 0 AND close_3m > 0
                    THEN adj_close / close_3m - 1.0 END AS mom_3m,
               CASE WHEN adj_close > 0 AND close_6m > 0
                    THEN adj_close / close_6m - 1.0 END AS mom_6m,
               CASE WHEN close_1m > 0 AND close_12m > 0
                    THEN close_1m / close_12m - 1.0 END AS mom_12m_1m
        FROM monthly_lagged
    )
SELECT d.mdate, d.symbol,
       m.mom_1m, m.mom_3m, m.mom_6m, m.mom_12m_1m,
       f.volume_zscore, f.up_volume AS up_volume_20d, f.down_volume AS down_volume_20d,
       f.up_down_volume_ratio, f.breakout_volume_confirmed,
       f.deliv_per AS delivery_pct, f.delivery_pct_zscore, f.delivery_pct_trend,
       f.delivery_spike_while_flat,
       f.atr_ratio, f.nr7, f.squeeze_days_20d, f.range_compression_20d,
       f.close_in_range, f.upper_wick_ratio, f.lower_wick_ratio,
       f.consec_higher_lows, f.big_body_day_in_trend
FROM decisions d
LEFT JOIN monthly_features m
  ON m.symbol = d.symbol AND m.m = date_trunc('month', d.mdate)
LEFT JOIN decision_daily_features f
  ON f.symbol = d.symbol AND f.date = d.mdate
"""


def _empty_sql(columns: str) -> str:
    return f"SELECT {columns} WHERE FALSE"


def _sql_inputs(con, cfg: dict) -> dict:
    """Build SQL fragments over the existing month-end panels and daily normalized tables."""
    monthly_adj = ("SELECT symbol, m, adj_close FROM adj_me"
                   if panels.has_table(con, "adj_me") else
                   _empty_sql("NULL::VARCHAR AS symbol, NULL::TIMESTAMP AS m, NULL::DOUBLE AS adj_close"))
    if not panels.has_table(con, "bhav"):
        return {
            "monthly_adj": monthly_adj,
            "market_days": _empty_sql("NULL::DATE AS date"),
            "daily": """SELECT s.symbol, w.date, w.session_no, NULL::DOUBLE AS open,
                              NULL::DOUBLE AS high, NULL::DOUBLE AS low, NULL::DOUBLE AS close,
                              NULL::BIGINT AS volume, NULL::DOUBLE AS deliv_per,
                              NULL::DOUBLE AS adj_close, NULL::DOUBLE AS adj_high,
                              NULL::DOUBLE AS adj_open, NULL::DOUBLE AS adj_low
                       FROM symbols s CROSS JOIN source_days w WHERE FALSE""",
        }

    series = panels.series_sql(cfg, "b")
    market_days = (f"SELECT DISTINCT b.date FROM bhav b WHERE {series} "
                   "AND b.date <= (SELECT max_date FROM bounds)")
    adjusted = ("SELECT symbol, date, max(adj_close) AS adj_close FROM adj_close "
                "WHERE date IN (SELECT date FROM source_days) "
                "AND adj_close IS NOT NULL AND isfinite(adj_close) AND adj_close > 0 "
                "GROUP BY symbol, date" if panels.has_table(con, "adj_close") else
                _empty_sql("NULL::VARCHAR AS symbol, NULL::DATE AS date, NULL::DOUBLE AS adj_close"))
    delivery = ("SELECT symbol, date, avg(deliv_per) AS deliv_per FROM delivery "
                "WHERE date IN (SELECT date FROM source_days) "
                "AND deliv_per IS NOT NULL AND isfinite(deliv_per) GROUP BY symbol, date"
                if panels.has_table(con, "delivery") else
                _empty_sql("NULL::VARCHAR AS symbol, NULL::DATE AS date, NULL::DOUBLE AS deliv_per"))
    daily = f"""
        SELECT s.symbol, w.date, w.session_no, b.open, b.high, b.low, b.close, b.volume,
               d.deliv_per, a.adj_close,
               CASE WHEN b.close > 0 AND b.high > 0 AND a.adj_close > 0
                    THEN b.high * a.adj_close / b.close END AS adj_high,
               CASE WHEN b.close > 0 AND b.open > 0 AND a.adj_close > 0
                    THEN b.open * a.adj_close / b.close END AS adj_open,
               CASE WHEN b.close > 0 AND b.low > 0 AND a.adj_close > 0
                    THEN b.low * a.adj_close / b.close END AS adj_low
        FROM symbols s CROSS JOIN source_days w
        LEFT JOIN bhav b ON b.symbol = s.symbol AND b.date = w.date AND {series}
        LEFT JOIN ({adjusted}) a ON a.symbol = s.symbol AND a.date = w.date
        LEFT JOIN ({delivery}) d ON d.symbol = s.symbol AND d.date = w.date
    """
    return {"monthly_adj": monthly_adj, "market_days": market_days, "daily": daily}


def build(con, cfg: dict) -> dict:
    """Rebuild the feature panel with one DuckDB CTAS."""
    if not panels.has_table(con, "eligible"):
        raise ValueError("missing eligible table; build the Phase 2 eligibility panel first")
    t0 = time.monotonic()
    f = cfg["features"]
    lookback = f["daily_lookback_sessions"]
    sql = _SQL.format(
        **_sql_inputs(con, cfg), lookback=lookback, lookback_minus_one=lookback - 1,
        flat_sessions=f["delivery_flat_lookback_sessions"],
        spike_z=f["delivery_spike_z"], flat_return=f["delivery_flat_max_return"],
        atr=f["atr_sessions"], squeeze_frac=f["squeeze_range_frac"],
        big_body_mult=f["big_body_mult"],
    )
    con.execute(sql)
    rows, months = con.execute(
        "SELECT count(*), count(DISTINCT mdate) FROM feature_panel").fetchone()
    return {"rows": rows, "months": months, "seconds": time.monotonic() - t0}


def _synth_check() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        con = duckdb.connect(os.path.join(tmp, "features.duckdb"))
        cfg = load("quick")
        try:
            con.execute("CREATE TABLE adj_me (symbol VARCHAR, m TIMESTAMP, mdate DATE, "
                        "adate DATE, adj_close DOUBLE)")
            con.execute("CREATE TABLE eligible (symbol VARCHAR, mdate DATE, eligible BOOLEAN)")
            con.execute("CREATE TABLE bhav (symbol VARCHAR, series VARCHAR, date DATE, "
                        "open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT)")
            con.execute("CREATE TABLE adj_close (symbol VARCHAR, date DATE, adj_close DOUBLE)")
            con.execute("CREATE TABLE delivery (symbol VARCHAR, date DATE, "
                        "deliv_qty BIGINT, deliv_per DOUBLE)")

            # January 2023-April 2024 adjusted month-ends; GAP has no March 2024 price.
            monthly_dates = []
            for i in range(16):
                year, month = 2023 + (i + 1) // 13, (i % 12) + 1
                first = date(year, month, 1)
                last = date(year, month, calendar.monthrange(year, month)[1])
                monthly_dates.append((first, last))
                con.execute("INSERT INTO adj_me VALUES ('X', ?, ?, ?, ?)",
                            [first, last, last, 100.0 + i])
            for i, price in ((12, 50.0), (13, 55.0), (15, 60.0)):
                first, last = monthly_dates[i]
                con.execute("INSERT INTO adj_me VALUES ('GAP', ?, ?, ?, ?)",
                            [first, last, last, price])
            con.execute("INSERT INTO adj_me VALUES ('X', TIMESTAMP '2024-05-01', "
                        "DATE '2024-05-31', DATE '2024-05-31', 10000.0)")

            sessions = []
            day = date(2024, 4, 2)
            while day <= date(2024, 4, 30):
                if day.weekday() < 5:
                    sessions.append(day)
                day += timedelta(days=1)
            assert len(sessions) == 21 and sessions[-1] == date(2024, 4, 30), sessions
            decision = sessions[-1]
            con.executemany("INSERT INTO eligible VALUES (?, ?, TRUE)", [
                ("X", date(2023, 2, 28)), ("X", decision), ("GAP", decision),
                ("MISSING", decision), ("BREAKOUT", decision), ("VOL", decision),
                ("NODELIV", decision), ("CANDLE", decision), ("NR", decision),
                ("RUN", decision),
            ])

            bhav_rows, adjusted_rows, delivery_rows = [], [], []
            for i, d in enumerate(sessions):
                # X is flat; delivery rises from 40 to 60, with 90 on the decision day.
                bhav_rows.append(("X", "EQ", d, 100.0, 101.0, 99.0, 100.0, 100))
                adjusted_rows.append(("X", d, 100.0))
                delivery_rows.append(("X", d, 100, 40.0 if i < 10 else 60.0 if i < 20 else 90.0))

                # VOL: prior volumes 1..20; current volume 30. Its final 20 sessions
                # contain up-volume 95 and down-volume 144.
                if i <= 10:
                    close = 100.0 + i
                elif i < 20:
                    close = 120.0 - i
                else:
                    close = 102.0
                volume = i + 1 if i < 20 else 30
                bhav_rows.append(("VOL", "EQ", d, close, close + 0.1, close - 0.1, close, volume))
                adjusted_rows.append(("VOL", d, close))

                # BREAKOUT clears all prior adjusted highs and prior average volume.
                bclose = 100.0 if i < 20 else 102.0
                bhav_rows.append(("BREAKOUT", "EQ", d, bclose, 101.0 if i < 20 else 103.0,
                                  bclose - 1.0, bclose, 100 if i < 20 else 200))
                adjusted_rows.append(("BREAKOUT", d, bclose))

                # NODELIV has complete price/volume data but no delivery rows.
                nvolume = i + 1 if i < 20 else 30
                bhav_rows.append(("NODELIV", "EQ", d, 100.0, 101.0, 99.0, 100.0, nvolume))
                adjusted_rows.append(("NODELIV", d, 100.0))

                # CANDLE: flat 7-wide ranges; the decision day is a big bullish body
                # (12 > 2 x the prior-20 mean 5) above the 20-session-ago close of 105.
                c_open = 100.0
                c_close, c_high = (105.0, 106.0) if i < 20 else (112.0, 113.0)
                bhav_rows.append(("CANDLE", "EQ", d, c_open, c_high, 99.0, c_close, 100))
                adjusted_rows.append(("CANDLE", d, c_close))

                # NR: same flat history; decision-day TR=3 is both NR7 (< 7) and a
                # squeeze day (< 0.5 x the prior-20 mean TR of 7).
                n_open, n_close = (100.0, 105.0) if i < 20 else (103.0, 104.0)
                n_high, n_low = (106.0, 99.0) if i < 20 else (105.5, 102.5)
                bhav_rows.append(("NR", "EQ", d, n_open, n_high, n_low, n_close, 100))
                adjusted_rows.append(("NR", d, n_close))

                # RUN: lows rise every session; decision-day TR=7 ties the prior six (NR7).
                low = 99.0 + i
                bhav_rows.append(("RUN", "EQ", d, low + 5.0, low + 7.0, low, low + 6.0, 100))
                adjusted_rows.append(("RUN", d, low + 6.0))

                # GAP lacks one exchange-session row; the dense calendar must preserve its slot.
                if i != 10:
                    bhav_rows.append(("GAP", "EQ", d, 100.0, 101.0, 99.0, 100.0, 100))
                    adjusted_rows.append(("GAP", d, 100.0))

            # NR needs a session before the window start so its earliest true range has a
            # previous close; without it the decision day's TR-based windows run one short.
            bhav_rows.append(("NR", "EQ", date(2024, 3, 29), 100.0, 106.0, 99.0, 105.0, 100))
            adjusted_rows.append(("NR", date(2024, 3, 29), 105.0))

            con.executemany("INSERT INTO bhav VALUES (?, ?, ?, ?, ?, ?, ?, ?)", bhav_rows)
            con.executemany("INSERT INTO adj_close VALUES (?, ?, ?)", adjusted_rows)
            con.executemany("INSERT INTO delivery VALUES (?, ?, ?, ?)", delivery_rows)

            stats = build(con, cfg)
            assert stats["rows"] == 10, f"one row per eligible symbol-month: {stats}"
            mom = con.execute("SELECT mom_1m, mom_3m, mom_6m, mom_12m_1m FROM feature_panel "
                              "WHERE symbol='X' AND mdate=?", [decision]).fetchone()
            want_mom = (115 / 114 - 1, 115 / 112 - 1, 115 / 109 - 1, 114 / 103 - 1)
            assert all(abs(got - want) < 1e-12 for got, want in zip(mom, want_mom)), \
                f"monthly momentum formulas/offsets: {mom}"
            gap_mom = con.execute("SELECT mom_1m, mom_3m FROM feature_panel "
                                  "WHERE symbol='GAP' AND mdate=?", [decision]).fetchone()
            assert gap_mom[0] is None and abs(gap_mom[1] - 0.2) < 1e-12, \
                f"missing March price must null 1M while retaining Jan-to-Apr 3M: {gap_mom}"

            vol = con.execute("        SELECT volume_zscore, up_volume_20d, down_volume_20d, up_down_volume_ratio, "

                              "breakout_volume_confirmed FROM feature_panel "
                              "WHERE symbol='VOL' AND mdate=?", [decision]).fetchone()
            assert abs(vol[0] - 19.5 / math.sqrt(35.0)) < 1e-12, \
                f"volume z-score vs prior 20 sessions: {vol}"
            assert vol[1:3] == (95, 144), f"20-session up/down volumes: {vol}"
            assert abs(vol[3] - 95 / 144) < 1e-12, f"20-session up/down volume ratio: {vol}"
            assert vol[4] is False, f"high volume without a breakout must be false: {vol}"
            breakout = con.execute("SELECT breakout_volume_confirmed FROM feature_panel "
                                    "WHERE symbol='BREAKOUT' AND mdate=?", [decision]).fetchone()[0]
            assert breakout is True, f"adjusted-high and volume confirmation should pass: {breakout}"

            delivery = con.execute("SELECT delivery_pct, delivery_pct_zscore, delivery_pct_trend, "
                                   "delivery_spike_while_flat FROM feature_panel "
                                   "WHERE symbol='X' AND mdate=?", [decision]).fetchone()
            assert delivery[0] == 90.0, f"delivery level is today's DELIV_PER: {delivery}"
            assert abs(delivery[1] - 40 / math.sqrt(2000 / 19)) < 1e-12, \
                f"delivery z-score vs prior 20 observations: {delivery}"
            assert delivery[2] == 50.0, f"trend is current minus value 20 sessions earlier: {delivery}"
            assert delivery[3] is True, f"delivery spike while price flat should pass: {delivery}"
            no_delivery = con.execute("SELECT delivery_pct, delivery_pct_zscore, delivery_pct_trend, "
                                      "delivery_spike_while_flat FROM feature_panel "
                                      "WHERE symbol='NODELIV' AND mdate=?", [decision]).fetchone()
            assert no_delivery == (None, None, None, None), \
                f"missing delivery must remain NULL, never zero/false: {no_delivery}"
            missing_session = con.execute("SELECT volume_zscore, up_volume_20d, down_volume_20d, "
                                          "up_down_volume_ratio, breakout_volume_confirmed "
                                          "FROM feature_panel "
                                          "WHERE symbol='GAP' AND mdate=?", [decision]).fetchone()
            assert missing_session == (None,) * 5, \
                f"a missing market session must not shorten windows: {missing_session}"

            cand = con.execute("SELECT atr_ratio, nr7, squeeze_days_20d, range_compression_20d, "
                               "close_in_range, upper_wick_ratio, lower_wick_ratio, "
                               "consec_higher_lows, big_body_day_in_trend FROM feature_panel "
                               "WHERE symbol='CANDLE' AND mdate=?", [decision]).fetchone()
            assert abs(cand[0] - 7.0 / 112.0) < 1e-12, \
                f"ATR ratio = prior-14 mean true range / close: {cand}"
            assert cand[1] is False, f"decision TR 14 vs prior-6 min 7 is no NR7: {cand}"
            assert cand[2] == 0, f"no earlier session has a full prior window to squeeze on: {cand}"
            assert abs(cand[3] - 167 / 2400) < 1e-12, \
                f"mean range fraction over the last 20 sessions: {cand}"
            assert abs(cand[4] - 13 / 14) < 1e-12 and abs(cand[5] - 1 / 14) < 1e-12 \
                and abs(cand[6] - 1 / 14) < 1e-12, f"close position and wick ratios: {cand}"
            assert cand[7] == 0 and cand[8] is True, \
                f"flat lows then a big bullish body above the trend reference: {cand}"
            nr = con.execute("SELECT nr7, squeeze_days_20d, atr_ratio, consec_higher_lows, "
                             "big_body_day_in_trend, close_in_range FROM feature_panel "
                             "WHERE symbol='NR' AND mdate=?", [decision]).fetchone()
            assert nr[0] is True and nr[1] == 1, f"TR 3 is both NR7 and a squeeze day: {nr}"
            assert abs(nr[2] - 7.0 / 104.0) < 1e-12 and nr[3] == 1 and nr[4] is False \
                and abs(nr[5] - 0.5) < 1e-12, f"narrow decision day: {nr}"
            run = con.execute("SELECT nr7, consec_higher_lows, atr_ratio, close_in_range, "
                              "big_body_day_in_trend FROM feature_panel "
                              "WHERE symbol='RUN' AND mdate=?", [decision]).fetchone()
            assert run[0] is True, f"TR equal to the prior-6 minimum still counts as NR7: {run}"
            assert run[1] == 20, f"every low in the fixture rose, decision day included: {run}"
            assert abs(run[2] - 7.0 / 125.0) < 1e-12 and abs(run[3] - 6 / 7) < 1e-12 \
                and run[4] is False, f"rising-lows day: {run}"
            gap_vol = con.execute("SELECT atr_ratio, squeeze_days_20d, range_compression_20d, "
                                  "big_body_day_in_trend, nr7 FROM feature_panel "
                                  "WHERE symbol='GAP' AND mdate=?", [decision]).fetchone()
            assert gap_vol[:4] == (None,) * 4 and gap_vol[4] is True, \
                f"missing session NULLs windowed volatility but keeps the intact NR7 window: {gap_vol}"
            missing_symbol = con.execute("SELECT " + ", ".join(_FEATURES) + " FROM feature_panel "
                                         "WHERE symbol='MISSING'").fetchone()
            assert missing_symbol == (None,) * len(_FEATURES), \
                f"missing symbol data must stay NULL: {missing_symbol}"

            # A future daily print lies past the maximum decision date and must not change April.
            before = vol
            con.execute("INSERT INTO bhav VALUES "
                        "('VOL','EQ',DATE '2024-05-01',999,1000,998,999,999999)")
            con.execute("INSERT INTO adj_close VALUES ('VOL',DATE '2024-05-01',999)")
            con.execute("INSERT INTO delivery VALUES ('VOL',DATE '2024-05-01',100,0)")
            build(con, cfg)
            after = con.execute("        SELECT volume_zscore, up_volume_20d, down_volume_20d, up_down_volume_ratio, "

                                "breakout_volume_confirmed FROM feature_panel "
                                "WHERE symbol='VOL' AND mdate=?", [decision]).fetchone()
            assert after == before, f"future daily data leaked into April: {after} != {before}"

            # Empty decision universe and absent source tables do not crash or fabricate zero.
            con.execute("DELETE FROM eligible")
            assert build(con, cfg)["rows"] == 0, "empty eligible input must yield no feature rows"
            for table in ("adj_me", "bhav", "adj_close", "delivery"):
                con.execute(f"DROP TABLE {table}")
            con.execute("INSERT INTO eligible VALUES ('NO_SOURCE', DATE '2024-06-30', TRUE)")
            assert build(con, cfg)["rows"] == 1, "missing sources must preserve the eligible key"
            absent = con.execute("SELECT " + ", ".join(_FEATURES) + " FROM feature_panel").fetchone()
            assert absent == (None,) * len(_FEATURES), f"absent sources must be NULL: {absent}"
        finally:
            con.close()
    print("synthetic check passed (momentum, volume/delivery, volatility/candle formulas, "
          "missing session/data, future isolation, empty universe/sources)", flush=True)


def _prepare_live(con, cfg: dict) -> None:
    if not panels.has_table(con, "bhav"):
        raise ValueError("no bhav table; load and normalize source data before building features")
    panels.ensure(con, cfg)
    if not panels.has_table(con, "universe_rank"):
        from src.universe import rank
        rank.build(con, cfg)
    if not panels.has_table(con, "eligible"):
        from src.universe import eligibility
        eligibility.build(con, cfg)


def _live_check(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        _prepare_live(con, cfg)
        stats = build(con, cfg)
        expected = con.execute("SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]
        assert stats["rows"] == expected, \
            f"feature rows {stats['rows']:,} != eligible symbol-months {expected:,}"
        duplicates = con.execute("SELECT count(*) FROM (SELECT symbol, mdate FROM feature_panel "
                                 "GROUP BY 1, 2 HAVING count(*) != 1)").fetchone()[0]
        assert duplicates == 0, f"{duplicates} duplicate feature keys"
        nonfinite = con.execute(
            "SELECT count(*) FROM feature_panel WHERE " + " OR ".join(
                f"({name} IS NOT NULL AND NOT isfinite({name}))" for name in _NUMERIC_FEATURES)
        ).fetchone()[0]
        assert nonfinite == 0, f"{nonfinite} non-finite numeric features"
        nulls = con.execute("SELECT " + ", ".join(
            f"count(*) FILTER (WHERE {name} IS NULL)" for name in _FEATURES) + " FROM feature_panel").fetchone()
        print(f"feature_panel: {stats['rows']:,} eligible symbol-months across {stats['months']} months, "
              f"built in {stats['seconds']:.2f}s; NULL counts in feature order: {nulls}", flush=True)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: panel-wide feature checks (hand values, as-of windows, missing data, live panel)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
