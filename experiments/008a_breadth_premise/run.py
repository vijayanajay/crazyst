"""E008a — own-data market breadth as a regime gauge: the premise test (pre-registered
in hypothesis.md).

Construction (fixed before the run):
  market_breadth(date, breadth_200, breadth_mid) — one row per decision date:
    - membership is AS-OF (universe_rank at D: tier 200 = rank <= 200, tier mid = 201..1000);
    - the DMA is 200 TRADING SESSIONS of ADJUSTED closes over a dense session calendar
      (suspensions must not shift a window), per symbol;
    - a symbol with fewer than 200 sessions of history is NOT COUNTED (neither tier);
      the denominator is the number of defined DMAs, so a NULL adj print shrinks the
      denominator rather than voting "below".
  Months before the first defined breadth value are excluded from every statistic.

Measurements on the validation slice (boundary 2023-09-24, test window untouched):
  1. premise: pick mean return / universe return / hit rate for breadth < X vs >= X,
     X in {30, 40, 50} on the top-200 tier (adjacent-threshold consistency required);
  2. Spearman(breadth_month, pick_mean_ret) and vs universe return;
  3. flip frequency per year per threshold (whipsaw cost);
  4. two-tier agreement (top-200 vs 201-1000);
  5. sanity: breadth in the known stress months vs calm months.

python -m experiments.008a_breadth_premise.run --profile full
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load
from src.model import composite as model
from src.stats import spearman_ic

P41 = importlib.import_module("experiments.004_composite_v0.run")   # frozen slice split
from src.backtest import smoke_e2e as smoke                          # label fetch + picks
E007 = importlib.import_module("experiments.007_universe_cutoff.run")  # its chain builder

THRESHOLDS = (30.0, 40.0, 50.0)
STRESS_MONTHS = ("2011-08", "2011-09", "2018-09", "2018-10", "2018-11", "2018-12",
                 "2020-02", "2020-03")

_BREADTH_SQL = """
CREATE OR REPLACE TABLE market_breadth AS
WITH cal AS (
    SELECT row_number() OVER (ORDER BY date) AS session_no, date
    FROM (SELECT DISTINCT date FROM bhav WHERE series = 'EQ')
),
adj AS (
    SELECT a.symbol, c.session_no, a.adj_close
    FROM adj_close a JOIN cal c ON c.date = a.date
    WHERE a.adj_close IS NOT NULL AND isfinite(a.adj_close) AND a.adj_close > 0
),
adj_windowed AS (
    -- trailing 200 PRINTS per symbol (the sessions it actually traded): the full window
    -- (n200 = 200) is required, so a late-listed or suspended-heavy symbol is simply not
    -- counted until it has 200 prints of its own
    SELECT symbol, session_no, adj_close,
           count(*) OVER w AS n200,
           avg(adj_close) OVER w AS dma200
    FROM adj
    WINDOW w AS (PARTITION BY symbol ORDER BY session_no
                 ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)
),
dma AS (
    SELECT symbol, session_no, dma200 FROM adj_windowed WHERE n200 = 200
),
at_close AS (
    SELECT a.symbol, c.date, a.adj_close, d.dma200,
           a.adj_close > d.dma200 AS above
    FROM adj a
    JOIN cal c ON c.session_no = a.session_no
    JOIN dma d ON d.symbol = a.symbol AND d.session_no = a.session_no
),
members AS (
    SELECT u.mdate, u.symbol,
           CASE WHEN u.rank <= 200 THEN 'top200' ELSE 'mid' END AS tier
    FROM universe_rank u
    WHERE u.in_universe AND u.rank <= 1000
),
scored AS (
    SELECT m.mdate, m.tier, s.above
    FROM members m
    JOIN at_close s ON s.symbol = m.symbol AND s.date = m.mdate
)
SELECT mdate,
       -- FILTER on the avg itself: the aggregate runs over BOTH tiers' rows, so a plain
       -- CASE-ELSE would dilute each tier's share by the other tier's row count
       100.0 * avg(CASE WHEN above THEN 1.0 ELSE 0.0 END) FILTER (WHERE tier = 'top200') AS breadth_200,
       count(*) FILTER (WHERE tier = 'top200')                                           AS n_top200,
       100.0 * avg(CASE WHEN above THEN 1.0 ELSE 0.0 END) FILTER (WHERE tier = 'mid')    AS breadth_mid,
       count(*) FILTER (WHERE tier = 'mid')                                              AS n_mid
FROM scored
GROUP BY mdate
ORDER BY mdate
"""


def _build_breadth(con) -> tuple[int, str]:
    con.execute(_BREADTH_SQL)
    n, first = con.execute(
        "SELECT count(*), min(mdate) FROM market_breadth WHERE n_top200 > 0").fetchone()
    return n, str(first)


def _picks_and_universe(con) -> dict:
    """Validation-slice months: composite_2f top-5% picks (tie-break by symbol) and the
    equal-weight universe forward return per month."""
    rows, cutoff = smoke._fetch(con)
    val, test, boundary = P41.split_slice(rows, cutoff)
    assert val, "empty validation slice — rebuild the full-profile chain first"
    by_month: dict[str, list] = {}
    for r in val:
        by_month.setdefault(str(r[0]), []).append(r)
    sym_at = 2 + len(model.PANEL_FEATURES) + 1
    out = {}
    for m, rs in sorted(by_month.items()):
        scores = model.score_month_2f(rs)
        scored = [(s, rs[i][sym_at], rs[i][1]) for i, s in enumerate(scores) if s is not None]
        if len(scored) < 20:
            continue
        k = max(1, round(len(scored) * 0.05))
        top = sorted(scored, key=lambda p: (-p[0], p[1]))[:k]     # ties broken by symbol
        labeled = [ret for _, _, ret in scored if ret is not None]
        out[m] = {"pick_ret": sum(r for _, _, r in top if r is not None)
                  / max(1, sum(1 for _, _, r in top if r is not None)),
                  "universe_ret": sum(labeled) / len(labeled) if labeled else None,
                  "hit_rate": (sum(1 for _, _, r in top if r is not None and r > 0)
                               / max(1, sum(1 for _, _, r in top if r is not None)))}
    return out, str(boundary), str(cutoff)


def _flip_rate(values: list[float], threshold: float) -> float:
    states = [v < threshold for v in values]
    flips = sum(1 for a, b in zip(states, states[1:]) if a != b)
    return flips / (len(states) / 12.0) if states else 0.0


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)
    t0 = time.monotonic()
    cfg = load(args.profile)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()

    con = duckdb.connect(cfg["paths"].get("duckdb"))
    try:
        # the selfcheck suite resets the derived chain to the quick profile; this experiment
        # needs the full-history matrix, so rebuild the chain through E007's real-builder
        # helper (rank -> eligibility -> winners -> panel -> matrix at the full profile)
        E007._build_chain(con, cfg)
        n_breadth, first_breadth = _build_breadth(con)
        picks, boundary, cutoff = _picks_and_universe(con)

        rows = con.execute(
            "SELECT strftime(mdate, '%Y-%m-%d'), breadth_200, breadth_mid FROM market_breadth "
            "WHERE n_top200 > 0 AND mdate <= ?::DATE", [cutoff]).fetchall()
    finally:
        con.close()
    breadth = {m: (b200, bmid) for m, b200, bmid in rows}

    months = sorted(set(picks) & set(breadth))
    assert len(months) >= 100, f"only {len(months)} joined months — construction too thin"

    # 1) premise: outcomes below vs at-or-above each threshold (top-200 tier)
    premise = {}
    for x in THRESHOLDS:
        below = [picks[m] for m in months if breadth[m][0] < x]
        above = [picks[m] for m in months if breadth[m][0] >= x]
        def _mean(vals, key):
            got = [v[key] for v in vals if v[key] is not None]
            return (sum(got) / len(got)) if got else None
        premise[str(x)] = {
            "months_below": len(below), "months_at_or_above": len(above),
            "pick_ret_below": _mean(below, "pick_ret"), "pick_ret_above": _mean(above, "pick_ret"),
            "universe_ret_below": _mean(below, "universe_ret"),
            "universe_ret_above": _mean(above, "universe_ret"),
            "hit_rate_below": _mean(below, "hit_rate"), "hit_rate_above": _mean(above, "hit_rate"),
            "flips_per_year": _flip_rate([breadth[m][0] for m in months], x),
        }

    # 2) predictiveness: month-level Spearman, breadth vs outcomes
    pairs_pick = [(breadth[m][0], picks[m]["pick_ret"]) for m in months
                  if picks[m]["pick_ret"] is not None]
    pairs_uni = [(breadth[m][0], picks[m]["universe_ret"]) for m in months
                 if picks[m]["universe_ret"] is not None]
    rho_pick = spearman_ic([p[0] for p in pairs_pick], [p[1] for p in pairs_pick])
    rho_uni = spearman_ic([p[0] for p in pairs_uni], [p[1] for p in pairs_uni])

    # 4) two-tier agreement on the 100-point scale
    both = [(breadth[m][0], breadth[m][1]) for m in months
            if breadth[m][1] is not None]
    disagree_30 = sum(1 for a, b in both if (a < 30) != (b < 30))
    rho_tiers = spearman_ic([p[0] for p in both], [p[1] for p in both])

    # 5) sanity: known stress months vs all months
    stress = {m: breadth[m][0] for m in months if m[:7] in STRESS_MONTHS}

    out = {
        "experiment": "E008a_breadth_premise", "profile": args.profile, "git_hash": git,
        "data_cutoff": cutoff, "validation_boundary": boundary,
        "breadth_months": n_breadth, "first_breadth_month": first_breadth,
        "joined_months": len(months),
        "premise_by_threshold": premise,
        "spearman_breadth_vs_pick_ret": rho_pick,
        "spearman_breadth_vs_universe_ret": rho_uni,
        "tier_spearman_200_vs_mid": rho_tiers,
        "tier_disagreement_months_at_30": disagree_30,
        "stress_month_breadth_200": stress,
        "runtime_seconds": round(time.monotonic() - t0, 1),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    pct = lambda v: f"{v:+.2%}" if v is not None else "n/a"
    print(f"breadth table: {n_breadth} months from {first_breadth} "
          f"({len(months)} joined with the slice)")
    for x, v in premise.items():
        print(f"  X<{x:>4}: below {v['months_below']:>3} mo, pick {pct(v['pick_ret_below'])} vs "
              f"{pct(v['pick_ret_above'])} above | universe {pct(v['universe_ret_below'])} vs "
              f"{pct(v['universe_ret_above'])} | hit {pct(v['hit_rate_below'])} vs "
              f"{pct(v['hit_rate_above'])} | flips/yr {v['flips_per_year']:.1f}")
    print(f"  rho(breadth, pick ret) = {rho_pick:+.3f}; rho(breadth, universe ret) = "
          f"{rho_uni:+.3f}; tier rho = {rho_tiers:+.3f}; tier disagreements at 30: "
          f"{disagree_30}")
    print(f"  stress months (breadth_200): " + ", ".join(
        f"{m} {v:.0f}%" for m, v in out["stress_month_breadth_200"].items()))
    print(f"wrote {path} ({out['runtime_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
