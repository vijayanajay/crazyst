"""Task 2.2 — eligibility function: BRD §4 rules, evaluated as of the decision date D.

BRD §4 "Eligible stock": in the as-of universe · EQ series · not in T2T/BE · not under GSM/ASM
(as of D, where historical data exists) · listed >= 6 months · price >= ₹20. Every threshold comes
from config.yaml, including the turnover floor BRD §4 keeps "only as a config guard".

ONE definition, two readers. `_RULES` is the rule set and `_reasons_sql()` renders it once as a SQL
expression over the canonical context that `_context_sql()` renders once (one row per ranked
symbol-month carrying exactly the columns the rules need: in_universe, close, med3, listed_before,
stage). build() and eligible() are then two callers of the SAME SQL — one unscoped and materialized,
one scoped to a single symbol-month — rather than two implementations of the same rules, which is
what let the point form and the table drift apart before.

Both forms are self-sufficient: if the database has no rank they build it (panels -> rank), so
`eligible(symbol, date)` works on a fresh database with no prior build() and needs no
`month_history` table (listing age is a CTE over bhav inside the shared context).

Per-rule detail:

- series (T2T/BE): `not in T2T/BE` is one rule expressed as series IN allowed_series, rendered by
  panels.series_sql so the rank, the panel and this module cannot drift. In this data BE is the
  trade-to-trade series that actually appears (the literal code "T2T" appears in no bhav row), and
  the rank applies the same filter — so a T2T/BE symbol never reaches the universe at all. A symbol
  that spent a month as BE gets no allowed-series close for that month-end and fails as
  'no_eq_close_on_mdate'.
- listed >= min_listed_months: calendar age since the symbol's FIRST observed allowed-series month
  >= the config floor, evaluated as of the decision month. ponytail: bhav presence is a proxy for
  the listing register — a long halt then relist still counts as old (matches age-since-listing
  semantics); a genuinely new IPO is correctly excluded.
- GSM/ASM: enforced as of D from the `surveillance` table (symbol, effective_from, list, stage),
  which load_surveillance() fills from paths.surveillance_csv when a snapshot is supplied — NSE
  publishes current lists only, and no historical archive exists (BRD §5 D5, §15), so in the
  backtest the rule excludes nothing and nothing is faked. A malformed CSV row is QUARANTINED
  into `surveillance_rejects` (source, line, raw row, error) instead of aborting the build — the
  nightly refresh must survive one bad hand-edited line — but never silently: validate.report
  fails while rejects are non-empty. The rule that FORCES an exit at stage >= 2 is the engine's
  daily check (task 5.3, BRD §8.2) — a different decision from this one.
- turnover floor: BRD §4 keeps ₹5cr "as a config guard, subsumed by the top-1500 rank". Measured,
  that premise fails — rank 1500 turns over ₹1.94cr/day and 6,010 in-universe symbol-months sit
  below ₹5cr — so the floor is implemented (config > 0 excludes, reason turnover<Ncr) but left OFF
  (0.0) rather than silently cutting ~18% of the universe on a premise the data contradicts. The
  live check re-reports the measurement every run.
- a non-allowed series is answered rather than raising: BRD §4 filters series before liquidity, so
  `eligible("SOMEBE", date)` returns (False, ["series_not_allowed"]) and a caller can ask about a
  T2T/BE name directly.

python -m src.universe.eligibility runs the self-check: the 6 hand-built cases the plan names
(rank>1500, low turnover, recent listing, GSM-flagged, T2T/BE series, normal) on the shared
synthetic fixture, the fresh-database contract (no rank, no build), the config-driven stage
threshold, the CSV loader, then live: the point form against the materialized table for sampled
symbol-months, compared literally, plus the build invariants.
"""
import copy
import csv
import os
import random
import re
import sys
import tempfile
import time
from datetime import date

import duckdb

from src.config import load
from src.normalize import panels
from src.universe import rank

# BRD §4's stated (and, on this data, false) "subsumed" floor. Reported by the live check, never
# enforced by it: enforcing a value is the config's job (universe.min_median_turnover_cr).
_BRD_TURNOVER_GUARD_CR = 5.0

# ---- BRD §4, in one place ---------------------------------------------------------------------
# (condition over the canonical CONTEXT columns, reason token). The order is the order reasons
# appear in, so the table's string and the point form's list agree by construction.
_RULES = [
    ("in_universe IS NOT TRUE", "rank>{top_n}"),
    ("NOT (close >= {min_price})", "price<{min_price}"),
    ("NOT (med3 >= {min_median_turnover_cr} * {rupee_per_crore})",
     "turnover<{min_median_turnover_cr}cr"),
    ("NOT (listed_before IS TRUE)", "listed<{min_listed_months}m"),
    ("COALESCE(stage, 0) > {gsm_asm_max_allowed_stage}", "gsm_asm"),
    ("close IS NULL", "no_eq_close_on_mdate"),
]

# Scope predicates for the point form. `ranked`/`me` narrow to the decision DATE (the column is
# `mdate` in the rank, `date` in bhav); `hist` narrows by symbol only, because listing age is the
# age since that symbol's first month and needs its whole history.
_ROW_SCOPE = "symbol = ? AND mdate = ?"
_ME_SCOPE = "symbol = ? AND date = ?"
_SYM_SCOPE = "symbol = ?"

_CONTEXT = """
    ranked AS (
        SELECT symbol, mdate, med3, "rank" AS rank, in_universe
        FROM universe_rank WHERE {ranked}
    ),
    me AS (
        SELECT symbol, date AS mdate, max(close) AS close
        FROM bhav b WHERE {series} AND {me} GROUP BY 1, 2
    ),
    hist AS (
        SELECT symbol, date_trunc('month', date) AS m FROM bhav b
        WHERE {series} AND {hist} GROUP BY 1, 2
    ),
    listed AS (
        SELECT r.symbol, r.mdate,
               date_diff('month', min(p.m), date_trunc('month', r.mdate))
                   >= {min_listed_months} AS listed_before
        FROM (SELECT DISTINCT symbol, mdate FROM ranked) r
        JOIN hist p ON p.symbol = r.symbol
        GROUP BY 1, 2
    ),
    {surv},
    ctx AS (
        SELECT r.mdate, r.symbol, me.close, l.listed_before,
               r.med3, r.rank, r.in_universe, sv.stage
        FROM ranked r
        LEFT JOIN me ON me.symbol = r.symbol AND me.mdate = r.mdate
        LEFT JOIN listed l ON l.symbol = r.symbol AND l.mdate = r.mdate
        LEFT JOIN surv sv ON sv.symbol = r.symbol AND sv.mdate = r.mdate
    )
"""


def _rule_params(cfg: dict) -> dict:
    u = cfg["universe"]
    return {"top_n": u["top_n"], "min_price": u["min_price"],
            "min_median_turnover_cr": u["min_median_turnover_cr"],
            "rupee_per_crore": panels.RUPEE_PER_CRORE,
            "min_listed_months": u["min_listed_months"],
            "gsm_asm_max_allowed_stage": u["gsm_asm_max_allowed_stage"]}


def _reasons_sql(cfg: dict) -> str:
    """The rule set as ONE SQL expression over the context columns (trailing comma included)."""
    p = _rule_params(cfg)
    return " || ".join(f"CASE WHEN {cond.format(**p)} THEN '{msg.format(**p)}' || ',' ELSE '' END"
                       for cond, msg in _RULES)


def _surv_cte(con) -> str:
    """As-of-D stage per symbol-month: the latest applicable stage wins (max over prior rows).

    Without the surveillance table the rule contributes a NULL stage, so the rest of the SQL is
    identical instead of forking the whole build.
    """
    if not panels.has_table(con, "surveillance"):
        return "surv AS (SELECT NULL::VARCHAR AS symbol, NULL::DATE AS mdate, 0 AS stage)"
    return """surv AS (
        SELECT r.symbol, r.mdate, max(s.stage) AS stage
        FROM (SELECT DISTINCT symbol, mdate FROM ranked) r
        JOIN surveillance s ON s.symbol = r.symbol AND s.effective_from <= r.mdate
        GROUP BY 1, 2
    )"""


def _context_sql(cfg: dict, con, ranked: str = "TRUE", me: str = "TRUE",
                 hist: str = "TRUE") -> str:
    """The canonical evaluation context (CTEs ending in `ctx`) — the same text for both readers."""
    return _CONTEXT.format(series=panels.series_sql(cfg, "b"), surv=_surv_cte(con),
                           ranked=ranked, me=me, hist=hist,
                           min_listed_months=cfg["universe"]["min_listed_months"])


def _bind(pred: str, values: dict) -> list:
    """Bound values for a `col = ?` predicate in placeholder order (a mistyped column raises)."""
    return [values[col] for col in re.findall(r"(\w+) = \?", pred)]


def _ensure_rank(con, cfg: dict) -> None:
    """Self-sufficiency: both readers need the rank, so build it when the database has none."""
    if not panels.has_table(con, "bhav"):
        raise ValueError("no bhav table in this database — download and normalize data first")
    if not panels.has_table(con, "universe_rank"):
        rank.build(con, cfg)  # builds the panels too (panels.ensure), so a fresh DB works


def load_surveillance(con, cfg: dict) -> int:
    """Import a GSM/ASM snapshot into `surveillance`; returns the rows loaded.

    The CSV is the trust boundary (a hand-downloaded NSE list): every row is validated. A
    malformed row is quarantined into `surveillance_rejects` (source, line, raw, error) rather
    than aborting the build — one bad hand-edited line must not kill the nightly refresh — but
    the import is loud about it and validate.report FAILS while rejects are non-empty. No file
    → no build, and any existing table is left alone rather than cleared.
    """
    path = cfg["paths"].get("surveillance_csv")
    if not path or not os.path.exists(path):
        return 0
    rows, rejects = [], []
    with open(path, newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            sym, eff, lst, stg = ((r.get(k) or "").strip() for k in
                                  ("symbol", "effective_from", "list", "stage"))
            if not (sym or eff or lst or stg):
                continue  # blank line
            err = None
            try:
                eff_d = date.fromisoformat(eff)
                stage = int(stg)
            except ValueError as e:
                err = f"bad effective_from/stage ({eff!r}, {stg!r}): {e}"
            if err is None and not sym:
                err = "empty symbol"
            if err is None and (stage < 0 or lst.upper() not in ("GSM", "ASM", "")):
                err = f"stage must be >= 0 and list GSM|ASM, got {stage}, {lst!r}"
            if err is not None:
                rejects.append((os.path.basename(path), i, csv_row_str(r), err))
                continue
            rows.append((sym.upper(), eff_d, lst.upper(), stage))
    con.execute("CREATE OR REPLACE TABLE surveillance (symbol VARCHAR, effective_from DATE, "
                "list VARCHAR, stage INTEGER)")
    if rows:
        con.executemany("INSERT INTO surveillance VALUES (?, ?, ?, ?)", rows)
    # Quarantine is a table, not an exception: the reject survives the run and every report sees it.
    con.execute("CREATE OR REPLACE TABLE surveillance_rejects (source VARCHAR, line INTEGER, "
                "raw VARCHAR, error VARCHAR)")
    if rejects:
        con.executemany("INSERT INTO surveillance_rejects VALUES (?, ?, ?, ?)", rejects)
        print(f"surveillance: QUARANTINED {len(rejects)} malformed row(s) from {path} "
              f"(surveillance_rejects) — validate.report will FAIL until the CSV is fixed",
              flush=True)
    return len(rows)


def csv_row_str(row: dict) -> str:
    """Stable one-line rendering of a rejected CSV row (quarantine evidence, not a re-parse)."""
    return "|".join(f"{k}={v}" for k, v in sorted(row.items()) if v not in (None, ""))


def build(con, cfg: dict) -> dict:
    """Materialize the `eligible` table for every ranked symbol-month (needs the rank: task 2.1)."""
    _ensure_rank(con, cfg)
    load_surveillance(con, cfg)
    con.execute(f"""
        CREATE OR REPLACE TABLE eligible AS
        WITH {_context_sql(cfg, con)}
        SELECT ctx.mdate, ctx.symbol, ctx.close, ctx.listed_before, ctx.med3, ctx.rank,
               ctx.in_universe,
               rtrim(({_reasons_sql(cfg)}), ',') AS reasons,
               FALSE AS eligible
        FROM ctx
    """)
    con.execute("UPDATE eligible SET eligible = (reasons = '')")
    rows, n_elig = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE eligible) FROM eligible").fetchone()
    return {"rows": rows, "eligible": n_elig}


def eligible(symbol: str, decision_date: str, con, cfg: dict) -> tuple[bool, list[str]]:
    """Point form of the SAME rule set: one symbol as of one decision date (a month's last day).

    Self-sufficient — it builds the rank when the database has none and reads no `month_history` —
    and its reasons come from the same SQL expression the table stores, in the same order.
    """
    _ensure_rank(con, cfg)
    values = {"symbol": symbol, "date": decision_date, "mdate": decision_date}
    args = _bind(_ROW_SCOPE, values) + _bind(_ME_SCOPE, values) + _bind(_SYM_SCOPE, values)
    row = con.execute(f"""
        WITH {_context_sql(cfg, con, ranked=_ROW_SCOPE, me=_ME_SCOPE, hist=_SYM_SCOPE)}
        SELECT rtrim(({_reasons_sql(cfg)}), ',') AS reasons
        FROM ctx
    """, args).fetchone()
    if row is not None:
        return (row[0] == ""), [r for r in row[0].split(",") if r]
    # No context row: either the series is filtered out before liquidity (BRD §4), or the pair is
    # not a ranked symbol-month at all. Both are answerable, so neither is left as a crash.
    series = con.execute("SELECT series FROM bhav WHERE symbol = ? AND date <= ?::DATE "
                         "ORDER BY date DESC LIMIT 1", [symbol, decision_date]).fetchone()
    if series is None:
        raise ValueError(f"{symbol} @ {decision_date}: no bhav print on or before that date")
    if series[0] not in cfg["universe"]["allowed_series"]:
        return False, ["series_not_allowed"]
    raise ValueError(f"{symbol} @ {decision_date}: not a ranked symbol-month for {decision_date} "
                     f"(the decision date must be a month's last trading day)")


def _sep_rows(con, mdate: str) -> dict:
    """{symbol: (eligible, reasons-string)} for one decision date, from the table."""
    return {s: (bool(e), r or "") for s, e, r in con.execute(
        "SELECT symbol, eligible, reasons FROM eligible WHERE mdate = ?::DATE", [mdate]).fetchall()}


def _synth_check() -> None:
    tmp = tempfile.mkdtemp()
    cfg = copy.deepcopy(load("quick"))
    cfg["data_start_date"], cfg["end_date"] = "2024-01-01", "2024-09-30"
    cfg["universe"]["top_n"] = 5              # Sep ranks: D,A,G,B,C in — Y (rank 6) out
    # ₹15cr floor: C turns over ₹10cr, is INSIDE the universe, and is still excluded — the case
    # the live measurement says matters (6,010 in-universe symbol-months sit below BRD §4's ₹5cr).
    cfg["universe"]["min_median_turnover_cr"] = 15.0
    cfg["paths"]["duckdb"] = os.path.join(tmp, "test.duckdb")
    con = duckdb.connect(cfg["paths"]["duckdb"])
    rank.synth_setup(con)          # bhav + surveillance only: no panels, no rank, no eligible

    # The plan's contract, on a FRESH database: no prior build(), no month_history, and the point
    # form is responsible for making its own inputs exist.
    assert not panels.has_table(con, "universe_rank"), "fixture must start without a rank"
    ok, why = eligible("A", "2024-09-30", con, cfg)
    assert (ok, why) == (True, []), f"fresh-DB eligible('A', ...) -> {(ok, why)}"
    assert panels.has_table(con, "universe_rank"), \
        "the point form must have built the rank it needed (standalone contract)"
    assert not panels.has_table(con, "month_history"), \
        "month_history is gone: the context computes listing age over bhav itself"

    build(con, cfg)
    sep = _sep_rows(con, "2024-09-30")
    # The 6 cases the plan names (task 2.2 done-when), plus the series rule:
    assert sep["A"] == (True, ""), f"normal: {sep['A']}"
    assert sep["B"] == (True, ""), f"normal: {sep['B']}"
    assert sep["C"] == (False, "turnover<15.0cr"), \
        f"low turnover (rank 5, inside the universe, below the floor): {sep['C']}"
    assert sep["D"] == (False, "listed<6m,gsm_asm"), \
        f"recent listing (Aug first month) + ASM from Sep 1: {sep['D']}"
    assert sep["G"] == (False, "gsm_asm"), f"GSM-flagged: {sep['G']}"
    assert sep["Y"] == (False, "rank>5,price<20.0,turnover<15.0cr"), f"rank>1500 + penny: {sep['Y']}"
    assert "X" not in sep and "Q" not in sep, \
        f"non-allowed series must not appear in the eligible table at all: {sorted(sep)}"

    # T2T/BE: the point form answers for those symbols instead of raising
    for sym, code in (("X", "BE"), ("Q", "T")):
        got = eligible(sym, "2024-09-30", con, cfg)
        assert got == (False, ["series_not_allowed"]), \
            f"{sym} (series {code}) must report series_not_allowed, got {got}"
    # and it still refuses nonsense rather than guessing
    try:
        eligible("NOPE", "2024-09-30", con, cfg)
        raise AssertionError("an unknown symbol must raise")
    except ValueError:
        pass
    try:
        eligible("A", "2024-09-15", con, cfg)   # not a month's last trading day
        raise AssertionError("a non-decision date must raise")
    except ValueError:
        pass

    # table == point form, literally (same reasons, same order)
    for sym, (ok, why) in sep.items():
        got_ok, got_why = eligible(sym, "2024-09-30", con, cfg)
        assert (got_ok, ",".join(got_why)) == (ok, why), \
            f"point form disagrees with the table for {sym}: {(got_ok, got_why)} vs {(ok, why)}"

    # as-of semantics: D enters ASM on Sep 1, so its Aug row must NOT carry gsm_asm
    aug = _sep_rows(con, "2024-08-31")
    assert aug["D"] == (False, "listed<6m"), f"a flag effective Sep 1 must not apply Aug 31: {aug['D']}"
    assert aug["A"] == (True, ""), f"A's flag (Oct 1) is after the fixture window: {aug['A']}"
    assert aug["C"] == (False, "turnover<15.0cr"), f"C in Aug: {aug['C']}"
    assert aug["G"] == (False, "gsm_asm"), f"G in Aug (flagged since Jan): {aug['G']}"

    # the stage threshold is config, and it is the stage as of D that is compared
    cfg["universe"]["gsm_asm_max_allowed_stage"] = 2
    build(con, cfg)
    relaxed = _sep_rows(con, "2024-09-30")
    assert relaxed["G"] == (True, ""), \
        f"stage 2 must be allowed when the threshold is 2, got {relaxed['G']}"
    assert relaxed["D"] == (False, "listed<6m,gsm_asm"), \
        f"stage 3 is still over a threshold of 2: {relaxed['D']}"
    cfg["universe"]["gsm_asm_max_allowed_stage"] = 0
    build(con, cfg)
    assert _sep_rows(con, "2024-09-30")["G"] == (False, "gsm_asm"), \
        "rebuilding with the threshold back at 0 must re-exclude G (the table follows config)"

    # the CSV loader is the only way real surveillance data arrives
    csv_path = os.path.join(tmp, "surv.csv")
    with open(csv_path, "w") as f:
        f.write("symbol,effective_from,list,stage\n")
        f.write("B,2024-09-01,ASM,1\n")      # stage 1 > max_allowed_stage 0
        f.write("C,2024-01-01,GSM,2\n")
    cfg["paths"]["surveillance_csv"] = csv_path
    assert load_surveillance(con, cfg) == 2, "the loader must import every valid row"
    build(con, cfg)
    from_csv = _sep_rows(con, "2024-09-30")
    assert from_csv["B"] == (False, "gsm_asm"), f"stage 1 must exclude: {from_csv['B']}"
    assert from_csv["C"] == (False, "turnover<15.0cr,gsm_asm"), f"C: {from_csv['C']}"
    assert from_csv["G"] == (True, ""), \
        "supplying a snapshot replaces the table — G is in no CSV and so is under no list"
    bad = os.path.join(tmp, "bad.csv")
    with open(bad, "w") as f:
        f.write("symbol,effective_from,list,stage\n")
        f.write("B,09-01-2024,ASM,1\n")          # malformed: quarantined, does not abort
        f.write("C,2024-01-01,GSM,2\n")          # valid row on a poisoned file still loads
    cfg["paths"]["surveillance_csv"] = bad
    n_loaded = load_surveillance(con, cfg)
    assert n_loaded == 1, f"the valid row must load despite its bad sibling: {n_loaded}"
    rej = con.execute("SELECT source, line, error FROM surveillance_rejects").fetchall()
    assert len(rej) == 1 and rej[0][1] == 2 and "bad effective_from/stage" in rej[0][2], \
        f"the malformed row must land in surveillance_rejects with its line + reason: {rej}"
    con.execute("DROP TABLE surveillance_rejects")
    assert load_surveillance(con, cfg) == 1  # re-import rebuilds the quarantine from scratch
    rej = con.execute("SELECT count(*) FROM surveillance_rejects").fetchone()[0]
    assert rej == 1, f"quarantine must be rebuilt per import, never accumulated: {rej}"
    cfg["paths"]["surveillance_csv"] = csv_path
    assert load_surveillance(con, cfg) == 2, "the loader must import every valid row"
    con.execute("DROP TABLE surveillance_rejects")   # the live DB carries no reject table
    con.close()
    print("synthetic check passed (standalone on a fresh DB, 6 plan cases + series rule, as-of "
          "GSM/ASM stages, config threshold, CSV loader with quarantine, table == point form)",
          flush=True)


def _point_vs_table(con, cfg: dict, also: list, n: int = 100) -> None:
    """The evidence that the two readers cannot drift: sample live symbol-months and compare the
    point form to the stored table literally, reason for reason."""
    rows = con.execute("SELECT symbol, mdate, reasons FROM eligible").fetchall()
    rng = random.Random(cfg["backtest"]["random_seed"])   # seeded: a reproducible sample
    sample = rng.sample(rows, min(n, len(rows))) + list(also)
    seen, checked, t0 = set(), 0, time.monotonic()
    for sym, mdate, reasons in sample:
        if (sym, mdate) in seen:
            continue
        seen.add((sym, mdate))
        ok, why = eligible(sym, str(mdate), con, cfg)
        assert (ok, ",".join(why)) == (reasons == "", reasons), \
            f"{sym} {mdate}: table {reasons!r} vs point form {','.join(why)!r}"
        checked += 1
    print(f"  point form == table for {checked:,} sampled symbol-months "
          f"({time.monotonic() - t0:.1f}s)", flush=True)


def _live_check(cfg: dict) -> None:
    con = duckdb.connect(cfg["paths"]["duckdb"])
    try:
        st = build(con, cfg)
        print(f"eligible: {st['eligible']:,} eligible rows of {st['rows']:,} ranked symbol-months",
              flush=True)
        n_bad = con.execute("""SELECT count(*) FROM eligible
                               WHERE eligible != (reasons = '')""").fetchone()[0]
        assert n_bad == 0, f"{n_bad} rows where eligible flag disagrees with reasons"
        n_leak = con.execute("""SELECT count(*) FROM eligible
                                WHERE eligible AND NOT in_universe""").fetchone()[0]
        assert n_leak == 0, f"{n_leak} eligible rows outside the as-of universe (impossible by construction)"
        if panels.has_table(con, "surveillance"):
            n_surv = con.execute("SELECT count(*), max(stage) FROM surveillance").fetchone()
            print(f"surveillance: {n_surv[0]:,} rows (max stage {n_surv[1]}) — "
                  f"threshold {cfg['universe']['gsm_asm_max_allowed_stage']}", flush=True)
        else:
            print("surveillance: none — no historical GSM/ASM archive exists (BRD §4 'where "
                  "historical data exists'), so the rule excludes nothing in the backtest",
                  flush=True)
        # BRD §4 claims the ₹5cr floor is subsumed by the top-1500 rank. Report the measurement.
        top = cfg["universe"]["top_n"]
        cut_lo, cut_hi, below, n = con.execute("""
            SELECT min(u.med3) FILTER (WHERE u.rank = ?) / 1e7,
                   max(u.med3) FILTER (WHERE u.rank = ?) / 1e7,
                   count(*) FILTER (WHERE u.in_universe AND u.med3 < ? * 1e7),
                   count(*) FILTER (WHERE u.in_universe)
            FROM universe_rank u""", [top, top, _BRD_TURNOVER_GUARD_CR]).fetchone()
        assert 0 <= below <= n, f"floor measurement is inconsistent: {below:,} of {n:,}"
        # "Rs", not the rupee glyph: this console is cp1252 and printing it raises.
        print(f"turnover floor: the rank-{top} boundary spans Rs {cut_lo:,.2f}-{cut_hi:,.2f}cr/day, "
              f"so BRD 4's Rs {_BRD_TURNOVER_GUARD_CR:g}cr guard is NOT subsumed: {below:,} of "
              f"{n:,} in-universe symbol-months ({below / n:.1%}) sit below it. Enforced value: "
              f"{cfg['universe']['min_median_turnover_cr']:g} (0 = guard off)", flush=True)
        if cfg["universe"]["min_median_turnover_cr"] > 0:
            n_floor = con.execute("SELECT count(*) FROM eligible WHERE reasons LIKE 'turnover<%'"
                                  ).fetchone()[0]
            print(f"  excluding {n_floor:,} symbol-months for turnover", flush=True)
        per = con.execute("SELECT min(n), max(n) FROM (SELECT mdate, count(*) n FROM eligible "
                          "WHERE eligible GROUP BY 1)").fetchone()
        print(f"eligible per decision month: {per[0]:,} (min) -> {per[1]:,} (max)", flush=True)
        # always re-check the rows whose point/table agreement was the original failure: a NULL
        # close AND a too-recent listing, plus one row per decision month
        always = con.execute("""SELECT symbol, mdate, reasons FROM eligible
                                WHERE close IS NULL AND listed_before IS FALSE""").fetchall()
        always += con.execute("""SELECT DISTINCT ON (mdate) symbol, mdate, reasons
                                 FROM eligible ORDER BY mdate""").fetchall()
        _point_vs_table(con, cfg, always)
    finally:
        con.close()


def _self_check() -> None:
    _synth_check()
    _live_check(load("quick"))
    print("PASS: eligibility (one rule set — table and point form verified against each other)")
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
