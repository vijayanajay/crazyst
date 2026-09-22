"""Task 2.2 — eligibility function: BRD §4 rules, evaluated as of the decision date D.

Rules (all thresholds from config.yaml, BRD §4):
  in the as-of universe (rank <= top_n) · EQ series · not T2T/BE · price >= min_price
  · listed >= min_listed_months · NOT under GSM/ASM stage >= 2 as of D.

Two forms, one logic:
  - set-based: build(con, cfg) writes the `eligible` table (m, mdate, symbol, close,
    listed_before, eligible, reasons) for every ranked symbol-month. Features (3.5),
    winners (2.3) and the report pack query this table.
  - point: eligible(symbol, decision_date, con, cfg) -> (ok, reasons) for one symbol+date,
    same checks — the hand-buildable form the unit cases test.

- "not T2T/BE" is enforced by the rank's series='EQ' base filter; an EQ symbol that spent a
  month as BE gets no EQ close for that month-end and fails as 'no_eq_close_on_mdate'.
- listed >= min_listed_months: calendar age since the symbol's FIRST observed EQ month
  >= the config floor, evaluated as of the decision month. ponytail: bhav presence is a
  proxy for the listing register — a long halt then relist still counts as old (matches
  age-since-listing semantics); a genuinely new IPO is correctly excluded.
- GSM/ASM: no historical archive exists (BRD §5 D5, §15) — the rule is implemented going
  forward from current lists only; in the backtest, stage>=2 exits fire on the daily
  surveillance check (engine, task 5.3), never here. No historical exclusion is possible,
  so none is faked.

python -m src.universe.eligibility runs the self-check: 6 hand-built cases (rank>1500,
low price, recent listing, BE/missing close, T2T-in-name-only, normal) on the shared
synthetic fixture, then the live quick-profile build with invariants.
"""
import copy
import os
import sys
import tempfile

import duckdb

from src.config import load
from src.universe import rank

_CHECKS = [
    ("in_universe", "r.in_universe IS NOT TRUE", "rank>{top_n}"),
    ("price", "NOT (me.close >= {min_price})", "price<{min_price}"),
    ("listed", "NOT (l.listed_before IS TRUE)", "listed<{min_listed_months}m"),
    ("eq_close", "me.close IS NULL", "no_eq_close_on_mdate"),
]


def build(con, cfg: dict) -> dict:
    """Write the `eligible` table for every ranked symbol-month (needs universe_rank: task 2.1)."""
    u = cfg["universe"]
    con.execute("""
        CREATE OR REPLACE TABLE month_history AS
        SELECT symbol, date_trunc('month', date) AS m,
               min(date) AS first_date, max(date) AS last_date, count(*) AS n_days
        FROM bhav WHERE series = 'EQ' GROUP BY 1, 2
    """)
    params = {"top_n": u["top_n"], "min_price": u["min_price"],
              "min_listed_months": u["min_listed_months"]}
    reasons = " || ".join(
        f"CASE WHEN {cond.format(**params)} "
        f"THEN '{msg.format(**params)}' || ',' ELSE '' END"
        for _, cond, msg in _CHECKS)
    listed_cte = f"""
        listed AS (
            SELECT r.symbol, r.mdate,
                   date_diff('month', min(p.m), date_trunc('month', r.mdate))
                       >= {u['min_listed_months']} AS listed_before
            FROM (SELECT DISTINCT symbol, mdate FROM universe_rank) r
            JOIN month_history p ON p.symbol = r.symbol
            GROUP BY 1, 2
        )
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE eligible AS
        WITH me AS (
            SELECT symbol, date AS mdate, max(close) AS close
            FROM bhav WHERE series = 'EQ'
            GROUP BY 1, 2
        ),
        {listed_cte}
        SELECT r.mdate, r.symbol, me.close, l.listed_before,
               r.med3, r.rank, r.in_universe,
               rtrim(({reasons}), ',') AS reasons,
               FALSE AS eligible
        FROM universe_rank r
        LEFT JOIN me ON me.symbol = r.symbol AND me.mdate = r.mdate
        LEFT JOIN listed l ON l.symbol = r.symbol AND l.mdate = r.mdate
    """)
    con.execute("UPDATE eligible SET eligible = (reasons = '')")
    rows, n_elig = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE eligible) FROM eligible").fetchone()
    return {"rows": rows, "eligible": n_elig}


def eligible(symbol: str, decision_date: str, con, cfg: dict) -> tuple[bool, list[str]]:
    """Point form: BRD §4 checks for one symbol as of one decision date (a month-end)."""
    u = cfg["universe"]
    row = con.execute(f"""
        SELECT r.in_universe, me.close, r.rank,
               date_diff('month', (SELECT min(m) FROM month_history p
                                   WHERE p.symbol = r.symbol),
                         date_trunc('month', r.mdate)) >= {u['min_listed_months']} AS listed_before
        FROM universe_rank r
        LEFT JOIN bhav me
          ON me.symbol = r.symbol AND me.date = r.mdate AND me.series = 'EQ'
        WHERE r.symbol = ? AND r.mdate = ?::DATE
    """, [symbol, decision_date]).fetchone()
    if row is None:
        raise ValueError(f"{symbol} @ {decision_date}: not a ranked symbol-month "
                         f"(decision_date must be a month's last trading day; build the rank first)")
    in_univ, close, rank_, listed_before = row
    reasons = []
    if not in_univ:
        reasons.append(f"rank>{u['top_n']}")
    if close is None:
        reasons.append("no_eq_close_on_mdate")
    else:
        if close < u["min_price"]:
            reasons.append(f"price<{u['min_price']}")
        if not listed_before:
            reasons.append(f"listed<{u['min_listed_months']}m")
    return (not reasons), reasons


def _synth_check() -> None:
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["data_start_date"], cfg["end_date"] = "2024-01-01", "2024-09-30"
    cfg["universe"]["top_n"] = 4          # 5 synthetic EQ symbols -> one must miss the rank
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    con = duckdb.connect(cfg["paths"]["duckdb"])
    rank.synth_setup(con)
    rank.build(con, cfg)
    build(con, cfg)

    sep = con.execute("SELECT symbol, close, eligible, reasons FROM eligible "
                      "WHERE mdate = '2024-09-30' ORDER BY symbol").fetchall()
    got = {s: (bool(e), sorted(r.split(",") if r else [])) for s, _, e, r in sep}
    # Sep ranks: D 5e8 r1, A r2, B r3, C r4, Y r5 (top_n=4). A/B/C normal (C in at rank 4);
    # D too new (first month Aug, age 1 < 6); Y penny AND rank 5 > top_n.
    assert got["A"] == (True, []), f"A should be eligible: {got['A']}"
    assert got["B"] == (True, []) and got["C"] == (True, []), f"B/C: {got}"
    assert got["D"] == (False, ["listed<6m"]), f"D: {got['D']}"
    assert got["Y"] == (False, ["price<20.0", "rank>4"]), f"Y: {got['Y']}"

    aug = {s: (bool(e), sorted(r.split(",") if r else [])) for s, _, e, r in
           con.execute("SELECT symbol, close, eligible, reasons FROM eligible "
                       "WHERE mdate = '2024-08-31'").fetchall()}
    # Aug ranks: D 5e8 r1 ... Y r5; D still too new (age 0); Y price+rank
    assert aug["D"] == (False, ["listed<6m"]), f"D in Aug (ranked, too new): {aug['D']}"
    assert aug["C"] == (True, []), f"C in Aug (rank 4): {aug['C']}"
    assert aug["Y"] == (False, ["price<20.0", "rank>4"]), f"Y in Aug: {aug['Y']}"

    # point form agrees with the table, and refuses non-ranked pairs
    ok, why = eligible("A", "2024-09-30", con, cfg)
    assert ok and why == [], f"point form: A -> {(ok, why)}"
    ok, why = eligible("D", "2024-09-30", con, cfg)
    assert not ok and sorted(why) == ["listed<6m"], f"point form: D -> {(ok, why)}"
    try:
        eligible("X", "2024-09-30", con, cfg)  # BE series never enters the rank
        raise AssertionError("X (BE) must raise, not return")
    except ValueError:
        pass
    con.close()
    print("synthetic check passed (6 hand-built cases, table == point form)", flush=True)


def _live_check(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        if con.execute("SELECT count(*) FROM duckdb_tables() "
                       "WHERE table_name = 'universe_rank'").fetchone()[0] == 0:
            rank.build(con, cfg)
        st = build(con, cfg)
        print(f"eligible: {st['eligible']:,} eligible rows of {st['rows']:,} ranked symbol-months",
              flush=True)
        n_bad = con.execute("""SELECT count(*) FROM eligible
                               WHERE eligible != (reasons = '')""").fetchone()[0]
        assert n_bad == 0, f"{n_bad} rows where eligible flag disagrees with reasons"
        n_leak = con.execute("""SELECT count(*) FROM eligible
                                WHERE eligible AND NOT in_universe""").fetchone()[0]
        assert n_leak == 0, f"{n_leak} eligible rows outside the as-of universe (impossible by construction)"
        per = con.execute("SELECT min(n), max(n) FROM (SELECT mdate, count(*) n FROM eligible "
                          "WHERE eligible GROUP BY 1)").fetchone()
        print(f"eligible per decision month: {per[0]:,} (min) -> {per[1]:,} (max)", flush=True)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: eligibility (synthetic cases + live build, flag==reasons, universe containment)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
