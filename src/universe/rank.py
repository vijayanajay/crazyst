"""Task 2.1 — as-of universe rank: top-1500 by trailing 3-month median turnover (BRD §4).

Reads the `liq_me` month-end panel (src/normalize/panels.py) instead of rescanning daily bhav:
the BRD §4 window median is computed once, full history, and this module only ranks it. For
every decision date D (each month's last trading day), each EQ symbol's pooled median daily
turnover over the trailing {liquidity_lookback_months} calendar months ending AT D is ranked;
rank <= top_n is the as-of universe. The decision month is inside its own trailing window.

- one definition, one place: the window expression lives in the panel. Rank previously carried
  its own copy over daily bhav, which meant every future liquidity consumer would carry another.
- lookback is never truncated by the profile: the panel is full-history, so a decision month's
  window is complete even when it starts before the profile window. The old query filtered DAILY
  rows by profile start first, so the first lookback-1 decision months were ranked on partial
  evidence (a documented `ponytail:` wart) — under `full` nothing changes (no data precedes
  2011), under `quick` the first months get their real window.
- turnover unit: raw rupees (TOTTRDVAL / TtlTrfVal passed through unscaled by both mapping
  files); med3_cr is the rupee-crore view for humans.
- no lookahead by construction: the window ends at the decision date D. The rank carries NO
  price floor — a ₹5 stock can rank (the price floor is eligibility's job, task 2.2).
- rebuildable derived table (CREATE OR REPLACE), unlike the append-only bhav table (BRD §5).

build(con, cfg) takes an open DuckDB connection so the phase chain (rank -> eligibility ->
winners) runs on one connection, the way task 3.5's matrix build will call it. It calls
panels.ensure() first, so a standalone run on a fresh database works and the steady state pays
only the stamp read.

python -m src.universe.rank runs the self-check: synthetic hand-computed medians/ranks, then
live (profile quick): builds the table, PROVES the panel reproduces a from-scratch recompute of
med3 straight from daily bhav (sampled decision dates, exact on every symbol), prints the top 5
for 5 decision dates, asserts month-over-month membership overlap >= 85% and runtime in minutes.
"""
import copy
import os
import sys
import tempfile
import time

import duckdb

from src.config import load
from src.normalize import panels

_RANK_SQL = """
CREATE OR REPLACE TABLE universe_rank AS
WITH ranked AS (
    SELECT symbol, mdate, med3,
           row_number() OVER (PARTITION BY mdate ORDER BY med3 DESC, symbol) AS rank
    FROM liq_me
    WHERE mdate >= '{start}'::DATE AND mdate <= '{end}'::DATE
)
SELECT symbol, mdate, med3, med3 / 1.0e7 AS med3_cr, rank, rank <= {top_n} AS in_universe
FROM ranked
"""


def build(con, cfg: dict) -> dict:
    t0 = time.monotonic()
    panels.ensure(con, cfg)  # liq_me must exist; stamped, so this is a fingerprint read when current
    con.execute(_RANK_SQL.format(start=cfg["data_start_date"], end=cfg["end_date"],
                                 top_n=cfg["universe"]["top_n"]))
    rows, months = con.execute(
        "SELECT count(*), count(DISTINCT mdate) FROM universe_rank").fetchone()
    return {"rows": rows, "months": months, "seconds": time.monotonic() - t0}


def as_of(con, decision_date: str, k: int = 5) -> list[tuple]:
    """Top-k of the as-of universe for one decision date (mdate = that month's last trading day)."""
    return con.execute(
        "SELECT symbol, med3_cr, rank FROM universe_rank "
        "WHERE mdate = ?::DATE AND in_universe ORDER BY rank LIMIT ?",
        [decision_date, k]).fetchall()


# ---- synthetic fixture shared by the universe-layer self-checks (tasks 2.1-2.3) ----

def synth_bhav_rows() -> list[tuple]:
    """6 symbols x 9 months of 2024: (symbol, series, date, close, turnover).

    A,B,C,Y trade the whole span; D only Aug+Sep (recent listing); X is BE (excluded series).
    Closes: A 100 (130 in Sep — gives the winners test a +30% month), B 100, C 50, D 100,
    Y 5 (penny), X 100. Turnover varies for A in Jun/Jul/Aug so the trailing median is
    hand-checkable; B 2e8, C 1e8, D 5e8, Y 1e6, X 1e9.
    """
    import calendar
    rows = []
    for sym, series, close, to in (("A", "EQ", 100.0, 3.0e8), ("B", "EQ", 100.0, 2.0e8),
                                   ("C", "EQ", 50.0, 1.0e8), ("D", "EQ", 100.0, 5.0e8),
                                   ("Y", "EQ", 5.0, 1.0e6), ("X", "BE", 100.0, 1.0e9)):
        months = (8, 9) if sym == "D" else range(1, 10)
        for m in months:
            a_to = {6: 2.7e8, 7: 3.3e8, 8: 3.0e8}.get(m, 3.0e8) if sym == "A" else to
            close_eff = 130.0 if (sym == "A" and m == 9) else close
            for day in (15, calendar.monthrange(2024, m)[1]):
                rows.append((sym, series, __import__("datetime").date(2024, m, day), close_eff, a_to))
    return rows


def synth_setup(con) -> None:
    con.execute("""CREATE TABLE bhav (symbol VARCHAR, series VARCHAR, date DATE,
        open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, prev_close DOUBLE, last DOUBLE,
        volume BIGINT, turnover DOUBLE, trades BIGINT, isin VARCHAR)""")
    rows = synth_bhav_rows()
    con.executemany("INSERT INTO bhav (symbol, series, date, close, turnover) "
                    "VALUES (?, ?, ?, ?, ?)", rows)


def _synth_check() -> None:
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["data_start_date"], cfg["end_date"] = "2024-01-01", "2024-09-30"
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    con = duckdb.connect(cfg["paths"]["duckdb"])
    synth_setup(con)
    build(con, cfg)

    # hand-computed: at the Aug decision, A's trailing-3 monthly medians are
    # (2.7e8, 3.3e8, 3.0e8) -> med3 = 3.0e8; order D(5e8) > A(3e8) > B(2e8) > C(1e8) > Y(1e6)
    got = {r[0]: (r[1], r[2]) for r in con.execute(
        "SELECT symbol, med3, rank FROM universe_rank WHERE mdate = '2024-08-31'").fetchall()}
    assert got["A"] == (3.0e8, 2), f"A med3/rank: got {got['A']}, expected (3.0e8, 2)"
    assert [s for s, _ in sorted(got.items(), key=lambda kv: kv[1][1])] == \
        ["D", "A", "B", "C", "Y"], f"rank order wrong: {got}"
    assert "X" not in got, "BE series must never enter the EQ rank"
    assert got["Y"][1] <= cfg["universe"]["top_n"], \
        "rank has no price floor: the penny stock must rank and be excluded later (task 2.2)"
    # partial window: at the Jan decision only Jan exists -> median over Jan alone;
    # 4 symbols (A,B,C,Y — D first lists in Aug, so it cannot be ranked yet)
    jan = con.execute("SELECT count(*) FROM universe_rank WHERE mdate = '2024-01-31'").fetchone()[0]
    assert jan == 4, f"first decision month must rank the 4 existing EQ symbols, got {jan}"
    con.close()
    print("synthetic check passed (hand-computed med3, rank order, BE exclusion)", flush=True)


def _source_equivalence(con, cfg: dict, dates: list) -> None:
    """Prove the panel reproduces the daily source: recompute med3 STRAIGHT FROM bhav (the
    definition rank used when it owned this query) for sampled decision dates and compare to
    liq_me exactly, both directions, plus every universe_rank row against its panel row.

    This is the check that would catch a wrong panel join, a wrong window bound (one day either
    side), a monthly-median shortcut, or a profile filter leaking into the window.
    """
    lookback = cfg["universe"]["liquidity_lookback_months"]
    total = 0
    for d in dates:
        n_src, n_panel, missing, extra, diff = con.execute(f"""
            WITH src AS (
                SELECT b.symbol, median(b.turnover) AS med3, count(*) AS n_days
                FROM bhav b
                WHERE b.series = 'EQ'
                  AND b.date > ?::DATE - ({lookback} * INTERVAL '1 month')
                  AND b.date <= ?::DATE
                GROUP BY 1),
            pnl AS (SELECT symbol, med3, n_days FROM liq_me WHERE mdate = ?::DATE)
            SELECT (SELECT count(*) FROM src), (SELECT count(*) FROM pnl),
                   count(*) FILTER (WHERE pnl.symbol IS NULL),
                   count(*) FILTER (WHERE src.symbol IS NULL),
                   count(*) FILTER (WHERE src.med3 != pnl.med3 OR src.n_days != pnl.n_days)
            FROM src FULL OUTER JOIN pnl USING (symbol)""", [d, d, d]).fetchone()
        assert n_src == n_panel and not (missing or extra or diff), (
            f"{d}: liq_me disagrees with a from-scratch bhav recompute — "
            f"panel {n_panel} vs source {n_src} symbols, missing {missing}, extra {extra}, "
            f"value/count mismatches {diff}")
        total += n_src
    bad = con.execute("SELECT count(*) FROM universe_rank u "
                      "LEFT JOIN liq_me l ON l.symbol = u.symbol AND l.mdate = u.mdate "
                      "WHERE l.symbol IS NULL OR u.med3 != l.med3 "
                      "OR u.in_universe != (u.rank <= ?)", [cfg["universe"]["top_n"]]).fetchone()[0]
    assert bad == 0, f"{bad} universe_rank rows do not match their liq_me row (join/filter drift)"
    print(f"source equivalence: med3 recomputed from daily bhav for {len(dates)} decision dates "
          f"({total:,} symbol-months) — 0 mismatches, rank table matches the panel", flush=True)


def _live_check(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        st = build(con, cfg)
        assert st["seconds"] < 300, f"universe rank build took {st['seconds']:.0f}s (done-when: minutes not hours)"
        print(f"universe_rank: {st['rows']:,} rows, {st['months']} decision months, "
              f"built in {st['seconds']:.1f}s", flush=True)

        dates = [r[0] for r in con.execute(
            "SELECT DISTINCT mdate FROM universe_rank ORDER BY 1").fetchall()]
        picks = sorted({dates[0], dates[len(dates) // 4], dates[len(dates) // 2],
                        dates[3 * len(dates) // 4], dates[-1]})
        _source_equivalence(con, cfg, picks[::2])  # the sampled subset, incl. first and last month
        for d in picks:
            top = ", ".join(f"{s} {cr:,.0f}Cr r{r}" for s, cr, r in as_of(con, str(d)))
            print(f"  as of {d}: {top}", flush=True)

        sets = {d: {r[0] for r in con.execute(
            "SELECT symbol FROM universe_rank WHERE mdate = ? AND in_universe", [d]).fetchall()}
            for d in dates}
        for a, b in zip(dates, dates[1:]):
            ov = len(sets[a] & sets[b]) / max(1, len(sets[a] | sets[b]))
            assert ov >= 0.85, (f"universe membership jumped {a} -> {b}: Jaccard {ov:.2f} < 0.85 "
                                f"(|A|={len(sets[a])}, |B|={len(sets[b])}) — liquidity data glitch?")
        print(f"month-over-month membership: Jaccard >= 0.85 across all "
              f"{len(dates) - 1} transitions", flush=True)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: universe rank (synthetic hand-values + live 5-date print, MoM stability, runtime)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
