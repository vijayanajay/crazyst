"""Task 3.5 — feature matrix: one row per eligible symbol-month with features + labels.

`feature_matrix` = `feature_panel` (all 22 features, one row per eligible symbol-month) joined to
  next_month_ret / is_winner  — the FORWARD month, not the past: `winners` rows are keyed by the
  decision date their return ENDS at, so decision D's label lives at the NEXT decision date. The
  join walks the decision calendar (universe_rank's dates — the same calendar `winners` pools
  over) with lead(); a same-date join would silently ship past-month returns as labels.
  Rows whose next month is unmeasured (last decision, unfinished month, suspension break,
  missing adjusted price) keep NULL — unknown, not False.
  liquidity_rank            — as-of rank at the decision date (universe_rank)
  size_bucket               — as-of rank bucket top{b1} / {b1+1}-{b2} / {b2+1}-{top_n}
                              (config universe.size_buckets; bucket bounds are per plan 3.5)

LEFT joins only: row count stays exactly the eligible symbol-month count (task 3.5 done-when),
and no feature/label join can drop or duplicate a row — keys (symbol, mdate) are unique in every
input, asserted in the checks.

python -m src.features.matrix runs the self-check: synthetic hand-computed forward returns and
labels (the +30% Sep month read from its Aug decision row), per-month as-of buckets, NULL rows at
the last decision, then live (profile quick): row count == eligible symbol-months, no duplicate
keys, rank never NULL, bucket coverage, ~5% winner rate among labeled rows.
"""
import sys
import time

import duckdb

from src.config import load
from src.normalize import panels

_MATRIX_SQL = """
CREATE OR REPLACE TABLE feature_matrix AS
WITH cal AS (SELECT DISTINCT mdate FROM universe_rank),
decisions AS (
    SELECT mdate, lead(mdate) OVER (ORDER BY mdate) AS next_mdate FROM cal
)
SELECT p.*,
       w.ret AS next_month_ret, w.is_winner,
       r.rank AS liquidity_rank,
       CASE WHEN r.rank <= {b1} THEN '{top_label}'
            WHEN r.rank <= {b2} THEN '{mid_label}'
            ELSE '{rest_label}' END AS size_bucket
FROM feature_panel p
JOIN decisions d ON d.mdate = p.mdate
LEFT JOIN winners w ON w.symbol = p.symbol AND w.mdate = d.next_mdate
LEFT JOIN universe_rank r ON r.symbol = p.symbol AND r.mdate = p.mdate
"""

_KEY_COLUMNS = ("mdate", "symbol")          # feature_panel's own leading columns


def build(con, cfg: dict) -> dict:
    """Rebuild the feature matrix from feature_panel + winners + universe_rank."""
    for table in ("feature_panel", "winners", "universe_rank"):
        if not panels.has_table(con, table):
            raise ValueError(f"missing {table}; build its module first")
    t0 = time.monotonic()
    b1, b2 = cfg["universe"]["size_buckets"]
    con.execute(_MATRIX_SQL.format(
        b1=b1, b2=b2, top_label=f"top{b1}", mid_label=f"{b1 + 1}-{b2}",
        rest_label=f"{b2 + 1}-{cfg['universe']['top_n']}"))
    rows, months = con.execute(
        "SELECT count(*), count(DISTINCT mdate) FROM feature_matrix").fetchone()
    return {"rows": rows, "months": months, "seconds": time.monotonic() - t0}


def _synth_check() -> None:
    import copy
    import os
    import tempfile

    from src.features import panel as feature_panel
    from src.universe import eligibility, rank, winners

    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["data_start_date"] = "2024-01-01"   # end bound comes from the bhav fixture itself
    # end_date moved out of config (panels.data_cutoff); a cfg end_date is now ignored
    cfg["universe"]["top_n"] = 5                 # ranks D,A,G,B,C — C (rank 5) stays eligible
    cfg["universe"]["size_buckets"] = [2, 3]     # forces every bucket onto the tiny fixture
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        rank.synth_setup(con)                    # Sep closes: A 130 (+30%), rest flat
        con.execute("CREATE TABLE adj_close (symbol VARCHAR, date DATE, adj_close DOUBLE)")
        con.execute("INSERT INTO adj_close SELECT symbol, date, close FROM bhav WHERE series='EQ'")
        panels.build(con, cfg)
        rank.build(con, cfg)
        eligibility.build(con, cfg)
        winners.build(con, cfg)
        feature_panel.build(con, cfg)

        # C ranks 5 at every month; pull its Aug rank into the middle bucket so one fixture
        # exercises all three. Buckets stay as-of: Sep must not inherit the edit.
        con.execute("UPDATE universe_rank SET rank = 3 "
                    "WHERE symbol = 'C' AND mdate = DATE '2024-08-31'")
        st = build(con, cfg)

        aug = {s: (ret, win, rk, bucket) for s, ret, win, rk, bucket in con.execute(
            "SELECT symbol, next_month_ret, is_winner, liquidity_rank, size_bucket "
            "FROM feature_matrix WHERE mdate = DATE '2024-08-31'").fetchall()}
        assert set(aug) == {"A", "B", "C"}, f"Aug matrix rows = eligible set: {sorted(aug)}"
        # Forward labels: winners keyed at the NEXT decision (Sep 30) — A +30% winner,
        # B/C 0% not (top-5% of 3). A same-date join would have returned 0.0 for everyone.
        assert abs(aug["A"][0] - 0.30) < 1e-12 and aug["A"][1] is True, f"A forward label: {aug['A']}"
        assert aug["B"][:2] == (0.0, False) and aug["C"][:2] == (0.0, False), f"flat months: {aug}"
        assert aug["A"][2] == 2 and aug["B"][2] == 4, f"as-of liquidity rank join: {aug}"
        assert aug["A"][3] == "top2" and aug["B"][3] == "4-5", f"bucket bounds: {aug}"
        assert aug["C"] == (0.0, False, 3, "3-3"), f"middle bucket from the edited rank: {aug['C']}"

        sep = {s: (ret, win, bucket) for s, ret, win, bucket in con.execute(
            "SELECT symbol, next_month_ret, is_winner, size_bucket "
            "FROM feature_matrix WHERE mdate = DATE '2024-09-30'").fetchall()}
        assert set(sep) == {"A", "B", "C"}, f"Sep matrix rows: {sorted(sep)}"
        assert all(r is None and w is None for r, w, _ in sep.values()), \
            f"last decision month has no next month — labels must be NULL: {sep}"
        assert sep["A"][2] == "top2" and sep["C"][2] == "4-5", \
            f"buckets are as-of per decision month (C back at rank 5): {sep}"

        # One momentum value as a through-line: A's Sep row carries the +30% month itself.
        mom = con.execute("SELECT mom_1m FROM feature_matrix "
                          "WHERE symbol = 'A' AND mdate = DATE '2024-09-30'").fetchone()[0]
        assert abs(mom - 0.30) < 1e-12, f"features carried through unchanged: {mom}"

        panel_cols = [r[0] for r in con.execute(
            "SELECT column_name FROM duckdb_columns() WHERE table_name = 'feature_panel' "
            f"ORDER BY column_index").fetchall()]
        matrix_cols = {r[0] for r in con.execute(
            "SELECT column_name FROM duckdb_columns() WHERE table_name = 'feature_matrix'").fetchall()}
        assert set(panel_cols) <= matrix_cols, \
            f"matrix lost feature columns: {sorted(set(panel_cols) - matrix_cols)}"
        assert st["rows"] == con.execute(
            "SELECT count(*) FROM eligible WHERE eligible").fetchone()[0], \
            f"matrix rows {st['rows']} must equal eligible symbol-months"
    finally:
        con.close()
    print("synthetic check passed (forward labels from the next decision, as-of buckets, "
          "last-month NULLs, schema completeness)", flush=True)


def _live_check(cfg: dict) -> None:
    from src.features import panel as feature_panel
    from src.universe import eligibility, rank, winners

    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        feature_panel._prepare_live(con, cfg)
        if not panels.has_table(con, "winners"):
            winners.build(con, cfg)
        st = build(con, cfg)

        n_elig = con.execute("SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]
        assert st["rows"] == n_elig, \
            f"row count {st['rows']:,} != eligible symbol-months {n_elig:,} (task 3.5 done-when)"
        dups = con.execute("SELECT count(*) FROM (SELECT mdate, symbol FROM feature_matrix "
                           "GROUP BY 1, 2 HAVING count(*) != 1)").fetchone()[0]
        assert dups == 0, f"{dups} duplicate (mdate, symbol) keys"
        unranked = con.execute("SELECT count(*) FROM feature_matrix "
                               "WHERE liquidity_rank IS NULL").fetchone()[0]
        assert unranked == 0, \
            f"{unranked} rows without an as-of rank — eligibility requires the universe"
        buckets = dict(con.execute(
            "SELECT size_bucket, count(*) FROM feature_matrix GROUP BY 1").fetchall())
        assert len(buckets) >= 3 and all(buckets.values()), \
            f"all three size buckets must be populated on the live universe: {buckets}"
        labels = con.execute("SELECT count(*), count(*) FILTER (WHERE is_winner IS NOT NULL), "
                             "count(*) FILTER (WHERE is_winner) FROM feature_matrix").fetchone()
        rate = labels[2] / labels[1] if labels[1] else 0.0
        assert labels[1] > 0 and 0.02 <= rate <= 0.10, \
            (f"winner rate among labeled rows {rate:.3f} outside [0.02, 0.10] "
             f"({labels[2]} winners / {labels[1]} labeled) — label join drift?")
        print(f"feature_matrix: {st['rows']:,} rows x {st['months']} decision months in "
              f"{st['seconds']:.2f}s; buckets {buckets}; labeled {labels[1]:,} "
              f"({rate:.1%} winners), unlabeled {labels[0] - labels[1]:,} (last/incomplete month)",
              flush=True)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: feature matrix (forward labels, as-of buckets, row count = eligible months)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
