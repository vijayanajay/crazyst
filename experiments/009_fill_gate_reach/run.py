"""E009 — fill-gate reachability: how much of the strategy's pick return is a paper return
on names the engine's ADV gate would refuse, and does ADV-aware eligibility fix it
(pre-registered in hypothesis.md; run AFTER that file was written, per BRD 12).

Constructions (fixed before the run):
  liq_daily20(symbol, mdate, med20, n_days) — one row per symbol per decision month: the
  median of the trailing 20-session daily turnover in rupees, sessions STRICTLY BEFORE D
  (the fill window is the month after D; the decision bar must not contribute to the
  gate's own window). Same canonical series filter as every other panel
  (panels.series_sql).
  adv_2020_02 — a frozen hand-check sample (every eligible row of the 2020-02 decision
  month), committed beside results.json and re-verified row-for-row every run.

R1 (measurement, no pipeline change): at equal per-pick notional S, a pick is enterable
iff med20 >= 20 x S (the engine refuses when notional > 5% x adv20). Headline at the
shipped Rs250k/slot: refusal share, refused vs fillable pick means, the reachability-
corrected mean; sensitivity at S in {125k, 250k, 500k, 1M}; the 2018-09 W1 case by name.

R2 (the fix): universe.min_median_turnover_cr = 0.75, enforced through the REAL pipeline
(config -> E007._build_chain at the full profile). Zero-drift restore: config back to
0.0, chain rebuilt, mean monthly IC re-asserted bit-identical to P4.1b's frozen value.

python -m experiments.009_fill_gate_reach.run --profile full
"""
import argparse
import importlib
import json
import os
import statistics
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.model import composite as model
from src.normalize import panels as panels_mod
from src.backtest import smoke_e2e as smoke          # _fetch (matrix read)

P41 = importlib.import_module("experiments.004_composite_v0.run")   # slice split + _paired_t
E007 = importlib.import_module("experiments.007_universe_cutoff.run")  # its chain builder

SLOT_SIZES = (125_000.0, 250_000.0, 500_000.0, 1_000_000.0)
HEADLINE_S = 250_000.0
FLOOR_CR = 0.75                      # the one pre-registered arm

_LIQ20_SQL = """
CREATE OR REPLACE TABLE liq_daily20 AS
WITH cal AS (
    SELECT row_number() OVER (ORDER BY date) AS session_no, date
    FROM (SELECT DISTINCT date FROM bhav b WHERE {series})
),
t AS (
    SELECT b.symbol, c.session_no, b.turnover
    FROM bhav b JOIN cal c ON c.date = b.date
    WHERE {series}
),
w AS (
    -- per-symbol continuous window (linear): the last 20 sessions' median, sessions
    -- strictly before each decision date are selected by the `s` join below
    SELECT symbol, session_no, turnover,
           median(turnover) OVER win AS med20,
           count(*) OVER win AS n20
    FROM t
    WINDOW win AS (PARTITION BY symbol ORDER BY session_no
                   ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
),
s AS (
    -- each decision month -> the last session STRICTLY before it (the fill window is the
    -- month after D; the decision bar must not contribute to the gate's own window)
    SELECT g.mdate, max(c.session_no) AS sn
    FROM (SELECT DISTINCT mdate FROM liq_me) g
    JOIN cal c ON c.date < g.mdate
    GROUP BY g.mdate
)
SELECT w.symbol, s.mdate, w.med20, w.n20 AS n_days
FROM w JOIN s ON s.sn = w.session_no
WHERE w.n20 = 20
"""


def _build_liq20(con, cfg) -> int:
    con.execute(_LIQ20_SQL.format(series=panels_mod.series_sql(cfg)))
    n, = con.execute("SELECT count(*) FROM liq_daily20").fetchone()
    return n


def _synthetic_fixture() -> None:
    """A hand-computed median over known windows: the median and the 20-print cap are the
    code under test; the SQL's window bounds are covered by the member recompute."""
    assert statistics.median([1.0e7, 2.0e7, 3.0e7, 5.0e7]) == 2.5e7
    assert statistics.median([1.0e6] * 20) == 1.0e6
    assert statistics.median([1.0e6] * 19 + [1.0e9]) == 1.0e6, \
        "one huge print must not move the median of 20"


def _frozen_sample_check(con, out_dir: str) -> dict:
    """adv_2020_02: every eligible row of the frozen month, verified row-for-row."""
    path = os.path.join(out_dir, "adv_2020_02.csv")
    rows = con.execute(
        "SELECT l.symbol, l.med20, l.n_days FROM liq_daily20 l "
        "JOIN eligible e ON e.symbol = l.symbol AND e.mdate = l.mdate AND e.eligible "
        "WHERE l.mdate = (SELECT max(mdate) FROM liq_daily20 "
        "                 WHERE mdate >= '2020-02-01'::DATE AND mdate < '2020-03-01'::DATE) "
        "ORDER BY l.symbol").fetchall()
    assert rows, "no eligible rows in the frozen month"
    if os.path.exists(path):
        frozen = {}
        with open(path, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            assert header == ["symbol", "med20", "n_days"], header
            for line in f:
                s, m, n = line.strip().split(",")
                frozen[s] = (float(m), int(n))
        got = {s: (m, n) for s, m, n in rows}
        val_diffs = sum(1 for s in set(got) & set(frozen) if got[s] != frozen[s])
        assert got == frozen, (f"liq_daily20 drifted from the frozen 2020-02 sample: "
                               f"{len(set(got) ^ set(frozen))} member diffs, "
                               f"{val_diffs} value diffs")
        status = f"re-verified vs frozen sample ({len(frozen)} rows)"
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("symbol,med20,n_days\n")
            for s, m, n in rows:
                f.write(f"{s},{m!r},{n}\n")
        status = f"first run: sample written ({len(rows)} rows)"
    return {"rows": len(rows), "status": status}


def _member_recompute_check(con, cfg) -> dict:
    """Per-decision-date member-level recompute: every liq_daily20 row of sampled dates vs
    a from-scratch bhav scan (rank's _source_equivalence pattern). liq_daily20's declared
    semantics: the window is each symbol's last 20 sessions ENDING at the market's last
    session strictly before D; symbols with <20 prints by D are absent — a decision-date
    predictor cannot borrow the fill month's bars (the engine's in-session window can),
    so a fresh listing is conservatively unenterable at D. The first E009 recompute run
    reported 13 src-only symbols at 2015-04-30: all <20-print listings (ADLABS n20=17) —
    the comparator was missing the full-window requirement, not the table."""
    dates = [r[0] for r in con.execute(
        "SELECT DISTINCT mdate FROM liq_daily20 ORDER BY hash(mdate) LIMIT 6").fetchall()]
    checked = 0
    series = panels_mod.series_sql(cfg)
    for d in dates:
        anchor, = con.execute(
            "SELECT max(b.date) FROM bhav b WHERE " + series + " AND b.date < ?::DATE",
            [d]).fetchone()
        assert anchor is not None, d
        src = {(s, n): m for s, m, n in con.execute(
            "WITH win AS ("
            "  SELECT b.symbol, b.turnover, row_number() OVER "
            "         (PARTITION BY b.symbol ORDER BY b.date DESC) AS rn"
            "  FROM bhav b WHERE " + series + " AND b.date <= ?::DATE"
            ")"
            "SELECT w.symbol, median(w.turnover), count(*) FROM win w "
            "WHERE w.rn <= 20 AND w.symbol IN "
            "  (SELECT b2.symbol FROM bhav b2 WHERE " + panels_mod.series_sql(cfg, "b2") +
            "   AND b2.date = ?::DATE) "
            "GROUP BY 1 HAVING count(*) = 20", [anchor, anchor]).fetchall()}
        tbl = {(s, n): m for s, m, n in con.execute(
            "SELECT symbol, med20, n_days FROM liq_daily20 WHERE mdate = ?::DATE",
            [d]).fetchall()}
        assert src == tbl, (d, len(src), len(tbl),
                            sum(1 for k in set(src) & set(tbl) if src[k] != tbl[k]))
        checked += len(src)
    return {"dates_checked": len(dates), "rows_checked": checked}


def _pick_set(rows, sym_at) -> dict:
    """Top-5% of composite_2f per month, tie-break by symbol -> {mdate: [(sym, score, ret)]}."""
    by_month: dict[str, list] = {}
    for r in rows:
        by_month.setdefault(str(r[0]), []).append(r)
    out = {}
    for m, rs in by_month.items():
        scores = model.score_month_2f(rs)
        scored = [(s, rs[i][sym_at], rs[i][1]) for i, s in enumerate(scores) if s is not None]
        if len(scored) < 20:
            continue
        k = max(1, round(len(scored) * 0.05))
        out[m] = sorted(scored, key=lambda p: (-p[0], p[1]))[:k]
    return out


def _reachability(picks: dict, med20: dict, s: float) -> dict:
    """At per-pick notional S: refused iff med20 < 20 x S (the engine's gate at 5%)."""
    cut = 20.0 * s
    all_rets, fill_rets, refused_rets = [], [], []
    missing = 0
    for m, lst in picks.items():
        for _, sym, ret in lst:          # lst is (score, symbol, ret)
            if ret is None:
                continue
            m20 = med20.get((sym, m))
            if m20 is None:
                missing += 1                 # no 20-session history before D: not enterable
                continue
            all_rets.append(ret)
            (fill_rets if m20 >= cut else refused_rets).append(ret)
    n_all = len(all_rets)
    tot = sum(all_rets)
    return {
        "slot_rupees": s,
        "enterable_boundary_cr": cut / 1e7,
        "picks": n_all,
        "picks_missing_liq20": missing,
        "refused": len(refused_rets),
        "refused_pct": len(refused_rets) / n_all,
        "refused_return_mass_pct": (sum(refused_rets) / tot) if tot else 0.0,
        "mean_all": sum(all_rets) / n_all,
        "mean_fillable": sum(fill_rets) / len(fill_rets) if fill_rets else None,
        "mean_refused": sum(refused_rets) / len(refused_rets) if refused_rets else None,
        "corrected_mean": sum(fill_rets) / len(fill_rets) if fill_rets else None,
    }


def _top_decile_refusal(picks: dict, med20: dict, s: float) -> float:
    """Refusal share of the TOP-DECILE-SCORE picks specifically (S = headline)."""
    cut = 20.0 * s
    tot = ref = 0
    for m, lst in picks.items():
        n = len(lst)
        if n < 10:
            continue
        for _, sym, ret in lst[:max(1, n // 10)]:     # lst is (score, symbol, ret), score-sorted
            m20 = med20.get((sym, m))
            if m20 is None:
                continue
            tot += 1
            ref += m20 < cut
    return ref / tot if tot else 0.0


def _mean_monthly_ic(by_month: dict, sym_at: int) -> float:
    from src.stats import spearman_ic
    ics = []
    for m in sorted(by_month):
        rs = by_month[m]
        scores = model.score_month_2f(rs)
        pairs = [(s, r[1]) for s, r in zip(scores, rs) if s is not None and r[1] is not None]
        ics.append(spearman_ic([p[0] for p in pairs], [p[1] for p in pairs]))
    return sum(ics) / len(ics)


def _ic_triples(by_month: dict, sym_at: int) -> list:
    """(month, ic, _) triples for P41._paired_t."""
    from src.stats import spearman_ic
    out = []
    for m in sorted(by_month):
        rs = by_month[m]
        scores = model.score_month_2f(rs)
        pairs = [(s, r[1]) for s, r in zip(scores, rs) if s is not None and r[1] is not None]
        ic = spearman_ic([p[0] for p in pairs], [p[1] for p in pairs])
        out.append((m, ic, None))
    return out


def _w1_case(con, med20: dict) -> list:
    """The 2018-09 refused top-scored names, by name: med20 and forward month return."""
    ms = con.execute("SELECT max(mdate) FROM liq_daily20 "
                     "WHERE mdate >= '2018-09-01'::DATE AND mdate < '2018-10-01'::DATE"
                     ).fetchone()[0]
    if ms is None:
        return []
    out = []
    for s in ("LIQUIDETF", "INFRABEES", "SPLIL", "GKWLIMITED"):
        row = con.execute(
            "SELECT l.med20, f.next_month_ret FROM liq_daily20 l "
            "LEFT JOIN feature_matrix f ON f.symbol = l.symbol AND f.mdate = l.mdate "
            "WHERE l.symbol = ? AND l.mdate = ?::DATE", [s, ms]).fetchone()
        if row:
            out.append({"symbol": s, "med20_cr": row[0] / 1e7,
                        "boundary_at_250k_cr": 20 * HEADLINE_S / 1e7,
                        "next_month_ret": row[1],
                        "refused_at_250k": row[0] < 20 * HEADLINE_S})
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out_dir = os.path.dirname(__file__)
    shipped_floor = cfg["universe"]["min_median_turnover_cr"]
    # the baseline arm is the PRE-floor universe regardless of the shipped default
    # (E009 itself shipped 0.75; a re-run must rebuild the baseline it measured)
    cfg["universe"]["min_median_turnover_cr"] = 0.0

    _synthetic_fixture()
    p41b = json.load(open(os.path.join(out_dir, "..", "004b_composite_2feat",
                                       "results.json"), encoding="utf-8"))
    frozen_ic = p41b["mean_monthly_ic"]["composite_2f"]["ic"]

    con = duckdb.connect(cfg["paths"].get("duckdb"))
    try:
        # ---- baseline chain (full profile, shipped config) ---------------------------
        E007._build_chain(con, cfg)
        n_liq = _build_liq20(con, cfg)
        frozen = _frozen_sample_check(con, out_dir)
        member = _member_recompute_check(con, cfg)

        rows, cutoff = smoke._fetch(con)
        val, test, boundary = P41.split_slice(rows, cutoff)
        sym_at = 2 + len(model.PANEL_FEATURES) + 1
        by_month: dict[str, list] = {}
        for r in val:
            by_month.setdefault(str(r[0]), []).append(r)
        picks = _pick_set(rows, sym_at)
        med20 = {(s, str(m)): m20 for s, m, m20 in con.execute(
            "SELECT symbol, mdate, med20 FROM liq_daily20").fetchall()}

        # ---- R1: reachability at four slot sizes ------------------------------------
        r1 = {f"S{int(s // 1000)}k": _reachability(picks, med20, s) for s in SLOT_SIZES}
        top_decile = _top_decile_refusal(picks, med20, HEADLINE_S)
        w1_case = _w1_case(con, med20)
        elig_baseline = con.execute(
            "SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]

        # ---- R2: the ADV-aware floor arm, through the REAL pipeline ------------------
        cfg["universe"]["min_median_turnover_cr"] = FLOOR_CR
        E007._build_chain(con, cfg)
        rows_f, cutoff_f = smoke._fetch(con)
        assert str(cutoff_f) == str(cutoff), (cutoff_f, cutoff)
        val_f, _, _ = P41.split_slice(rows_f, cutoff_f)
        by_month_f: dict[str, list] = {}
        for r in val_f:
            by_month_f.setdefault(str(r[0]), []).append(r)
        picks_f = _pick_set(rows_f, sym_at)
        r2 = _reachability(picks_f, med20, HEADLINE_S)   # liq_daily20 is chain-independent
        ic_floor = _mean_monthly_ic(by_month_f, sym_at)
        t_pairs = P41._paired_t(_ic_triples(by_month_f, sym_at),
                                _ic_triples(by_month, sym_at))
        excl = con.execute(
            "SELECT count(*) FROM eligible WHERE eligible = FALSE "
            "AND reasons LIKE '%turnover<%'").fetchone()[0]
        elig_floor = con.execute(
            "SELECT count(*) FROM eligible WHERE eligible").fetchone()[0]

        # ---- zero-drift restore (config AND chain) + the return-path guard ----------
        # (restore = the BASELINE universe the drift asserts reference, not the shipped
        # default: this must reproduce the pre-floor chain bit-for-bit)
        cfg["universe"]["min_median_turnover_cr"] = 0.0
        E007._build_chain(con, cfg)
        rows_r, cutoff_r = smoke._fetch(con)
        val_r, _, _ = P41.split_slice(rows_r, cutoff_r)
        by_month_r: dict[str, list] = {}
        for r in val_r:
            by_month_r.setdefault(str(r[0]), []).append(r)
        ic_restored = _mean_monthly_ic(by_month_r, sym_at)
        assert str(cutoff_r) == str(cutoff), (cutoff_r, cutoff)
        assert abs(ic_restored - frozen_ic) < 1e-9, (ic_restored, frozen_ic)
        picks_r = _pick_set(rows_r, sym_at)
        r1_restored = _reachability(picks_r, med20, HEADLINE_S)
        assert r1_restored == r1["S250k"], "restore drift in the R1 measurement itself"
        assert con.execute("SELECT count(*) FROM eligible WHERE eligible"
                           ).fetchone()[0] == elig_baseline
    finally:
        # hard guarantee: the in-memory config never leaks the arm floor
        cfg["universe"]["min_median_turnover_cr"] = shipped_floor
        con.close()

    # ---- pre-registered decision rule ------------------------------------------------
    base = r1["S250k"]
    ok_a = r2["corrected_mean"] is not None and base["corrected_mean"] is not None and \
        r2["corrected_mean"] >= base["corrected_mean"]
    ok_b = t_pairs is not None and t_pairs["t"] >= -2.0
    ok_c = r2["refused_pct"] <= base["refused_pct"] / 3.0
    adopt = ok_a and ok_b and ok_c

    out = {
        "experiment": "E009_fill_gate_reach", "profile": args.profile, "git_hash": git,
        "data_cutoff": str(cutoff), "validation_boundary": str(boundary),
        "liq_daily20_rows": n_liq, "frozen_sample": frozen, "member_recompute": member,
        "gate_arithmetic": {"max_position_adv_frac": 0.05,
                            "boundary_multiple_of_slot": 20.0},
        "R1_by_slot": r1,
        "R1_top_decile_refusal_at_250k": top_decile,
        "R1_w1_2018_09_case": w1_case,
        "R2": {"floor_cr": FLOOR_CR, "eligibles_baseline": elig_baseline,
               "excluded_by_floor": excl, "eligibles_floor": elig_floor,
               **r2, "ic_floor": ic_floor, "paired_t_vs_baseline": t_pairs},
        "restore": {"ic_restored": ic_restored, "frozen_ic": frozen_ic,
                    "delta": abs(ic_restored - frozen_ic)},
        "decision": {"corrected_mean_improves": ok_a, "ic_holds": ok_b,
                     "refusal_drops_materially": ok_c, "ADOPT": adopt},
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(out_dir, "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    h = base
    print(f"liq_daily20: {n_liq:,} rows; {frozen['status']}; member recompute "
          f"{member['rows_checked']:,} rows over {member['dates_checked']} dates")
    print(f"\nR1 headline at S = Rs {HEADLINE_S:,.0f}/pick (boundary med20 >= "
          f"{h['enterable_boundary_cr']:.2f}cr):")
    print(f"  picks {h['picks']:,}; refused {h['refused']:,} ({h['refused_pct']:.1%}); "
          f"return mass refused {h['refused_return_mass_pct']:.1%}")
    print(f"  mean all picks {h['mean_all']:+.2%}; fillable {h['mean_fillable']:+.2%}; "
          f"refused {h['mean_refused']:+.2%}")
    print(f"  reachability-corrected mean {h['corrected_mean']:+.2%} "
          f"(delta {h['corrected_mean'] - h['mean_all']:+.2%})")
    print(f"  top-decile-score picks refused: {top_decile:.1%}")
    for k, v in r1.items():
        if k == "S250k":
            continue
        print(f"  [{k}] boundary {v['enterable_boundary_cr']:.2f}cr: refused "
              f"{v['refused_pct']:.1%}, mean all {v['mean_all']:+.2%} vs fillable "
              f"{v['mean_fillable']:+.2%}")
    if w1_case:
        print("  2018-09 refused top-scored names:")
        for w in w1_case:
            print(f"    {w['symbol']:<12} med20 {w['med20_cr']:.2f}cr "
                  f"({'< cut' if w['refused_at_250k'] else '>= cut'}), "
                  f"next-month {w['next_month_ret']:+.2%}")
    print(f"\nR2 floor {FLOOR_CR}cr: excluded {excl:,} symbol-months "
          f"({elig_baseline:,} -> {elig_floor:,} eligible); refusal at 250k "
          f"{r2['refused_pct']:.1%} (baseline {base['refused_pct']:.1%}); corrected mean "
          f"{r2['corrected_mean']:+.2%} vs baseline corrected "
          f"{base['corrected_mean']:+.2%}; IC {ic_floor:.6f}; paired t = "
          f"{t_pairs['t'] if t_pairs else float('nan'):.2f}")
    print(f"restore: IC {ic_restored:.10f} vs frozen {frozen_ic:.10f} "
          f"(delta {abs(ic_restored - frozen_ic):.2e})")
    print(f"\nDECISION: {'ADOPT' if adopt else 'REJECT'} "
          f"(a corrected-mean {ok_a}, b IC {ok_b}, c refusal {ok_c})")
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
