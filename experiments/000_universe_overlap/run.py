"""E000 — universe overlap: as-of top-1500 liquidity rank vs Nifty 200 constituents
(run only after hypothesis.md was written).

Per year (December decision month): overlap% = |snapshot ∩ in_universe ∧ trading| over
|snapshot ∧ trading|, from `universe_rank` at full profile — plus the hit-rate delta between
winners computed on `eligible ∩ snapshot` vs all `eligible` symbol-months. The snapshot is
the CURRENT Nifty 200 list (`data/index/ind_nifty200list.csv`, hand-downloaded from NSE
archives) applied as-of to every year; the survivorship bias is disclosed in the hypothesis
and re-printed here so no reader can miss it.

Usage:
    python -m experiments.000_universe_overlap.run --profile full

Writes results.json (config snapshot, git hash, data cutoff — BRD §13) and prints the table.
Verdict logic lives in verdict.md; this script only measures. Exit 0 iff the run completed.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

import duckdb

from src.config import load

SNAPSHOT = os.path.join("data", "index", "ind_nifty200list.csv")


def load_snapshot() -> list:
    """Validated symbols from the hand-downloaded Nifty 200 CSV (the trust boundary)."""
    if not os.path.exists(SNAPSHOT):
        raise FileNotFoundError(f"{SNAPSHOT} missing — download the Nifty 200 list first "
                                f"(see hypothesis.md)")
    with open(SNAPSHOT, newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for i, r in enumerate(rows, start=2):
        sym = (r.get("Symbol") or "").strip().upper()
        series = (r.get("Series") or "EQ").strip().upper()
        isin = (r.get("ISIN Code") or "").strip()
        if not sym:
            raise ValueError(f"{SNAPSHOT}:{i}: empty Symbol")
        if series != "EQ":
            raise ValueError(f"{SNAPSHOT}:{i}: non-EQ series {series!r} — check the file")
        if not isin:
            raise ValueError(f"{SNAPSHOT}:{i}: missing ISIN")
        out.append(sym)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    cfg = load(args.profile)
    snapshot = load_snapshot()
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    try:
        # December decision months = the per-year rows; winners/eligibility joined as-of
        years = con.execute("""
            SELECT year(mdate) AS y, max(mdate) AS dec_date
            FROM universe_rank WHERE month(mdate) = 12 GROUP BY 1 ORDER BY 1
        """).fetchall()
        cutoff = con.execute("SELECT max(mdate) FROM universe_rank").fetchone()[0]

        # one snapshot table per call site, scoped symbols only
        con.execute("CREATE OR REPLACE TEMP TABLE nifty200 (symbol VARCHAR)")
        con.executemany("INSERT INTO nifty200 VALUES (?)", [(s,) for s in snapshot])

        overlap = {}
        for y, dec in years:
            # denominator: snapshot names with a bhav print in the ~16 months before the
            # December decision (listed and trading around then); `not_ever_traded` counts
            # snapshot names with no bhav at all by that date (IPOs/renames after t) — read
            # from the snapshot directly, never from the trading subset.
            n_snap, n_trading, n_in, n_ever = con.execute("""
                WITH s AS (SELECT n.symbol FROM nifty200 n
                           WHERE EXISTS (SELECT 1 FROM bhav b WHERE b.symbol = n.symbol
                                         AND b.date <= ?::DATE AND b.date > ?::DATE - INTERVAL 400 DAY))
                SELECT (SELECT count(*) FROM s),
                       (SELECT count(*) FROM s WHERE EXISTS
                            (SELECT 1 FROM bhav b WHERE b.symbol = s.symbol
                             AND b.date <= ?::DATE AND b.date > ?::DATE - INTERVAL 40 DAY)),
                       (SELECT count(*) FROM s JOIN universe_rank r ON r.symbol = s.symbol
                             AND r.mdate = ?::DATE WHERE r.in_universe),
                       (SELECT count(*) FROM nifty200 n WHERE NOT EXISTS
                            (SELECT 1 FROM bhav b WHERE b.symbol = n.symbol AND b.date <= ?::DATE))
            """, [dec, dec, dec, dec, dec, dec]).fetchone()
            overlap[y] = {"snapshot": n_snap, "trading": n_trading, "in_universe": n_in,
                          "not_ever_traded_by_year_end": n_ever}

        # hit-rate delta: winners among eligible∩snapshot vs all eligible, per year
        hit = {}
        for y, dec in years:
            dec_next = con.execute(
                "SELECT min(mdate) FROM universe_rank WHERE mdate > ?::DATE",
                [dec]).fetchone()[0]
            if dec_next is None:
                continue  # the last year's December has no forward label
            rows = con.execute("""
                SELECT e.symbol, e.eligible, w.is_winner,
                       EXISTS (SELECT 1 FROM nifty200 n WHERE n.symbol = e.symbol) AS in_n200
                FROM eligible e
                LEFT JOIN winners w ON w.symbol = e.symbol AND w.mdate = ?::DATE
                WHERE e.mdate = ?::DATE
            """, [dec_next, dec]).fetchall()
            elig = [r for r in rows if r[1]]
            in200 = [r for r in elig if r[3]]
            labeled = [r for r in elig if r[2] is not None]
            labeled200 = [r for r in labeled if r[3]]
            win = [r for r in labeled if r[2]]
            win200 = [r for r in labeled200 if r[2]]
            hit[y] = {"eligible": len(elig), "eligible_n200": len(in200),
                      "labeled": len(labeled), "labeled_n200": len(labeled200),
                      "winners": len(win), "winners_n200": len(win200),
                      "hit_all": len(win) / len(labeled) if labeled else None,
                      "hit_n200": len(win200) / len(labeled200) if labeled200 else None}
    finally:
        con.close()

    ovr = {y: (v["in_universe"] / v["trading"] if v["trading"] else None)
           for y, v in overlap.items()}
    deltas = {y: (abs(h["hit_n200"] - h["hit_all"])
                  if h["hit_all"] is not None and h["hit_n200"] is not None else None)
              for y, h in hit.items() if h["hit_n200"] is not None or h["hit_all"] is not None}
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True
                         ).stdout.strip()
    out = {
        "experiment": "E000", "profile": args.profile, "git_hash": git,
        "config_snapshot": cfg, "data_cutoff": str(cutoff),
        "snapshot_file": SNAPSHOT, "snapshot_symbols": len(snapshot),
        "snapshot_downloaded": "current list, hand-downloaded (see hypothesis.md for the bias)",
        "random_seed": cfg["backtest"]["random_seed"],
        "decision_years": [y for y, _ in years],
        "runtime_seconds": round(time.monotonic() - t0, 3),
        "overlap": overlap, "overlap_pct": ovr,
        "hit_rates": hit, "hit_rate_deltas_pp": deltas,
        "min_overlap": min(v for v in ovr.values() if v is not None) if any(
            v is not None for v in ovr.values()) else None,
        "mean_overlap": (sum(v for v in ovr.values() if v is not None) /
                         sum(1 for v in ovr.values() if v is not None)),
        "mean_abs_delta_pp": (sum(d for d in deltas.values() if d is not None) /
                              sum(1 for d in deltas.values() if d is not None)),
    }
    path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"E000 overlap: {len(snapshot)} snapshot symbols x {len(years)} decision years "
          f"(cutoff {cutoff}) — wrote {path}", flush=True)
    print("SURVIVORSHIP: current Nifty 200 list applied as-of to every year — overlap is "
          "UNDERSTATED vs a true as-of membership list (names that left the index are "
          "absent everywhere). See hypothesis.md.", flush=True)
    print(f"\n{'year':>6}{'overlap%':>10}{'in_univ':>9}{'trading':>9}{'ever':>7}"
          f"{'lbl200':>7}{'hit_all':>9}{'hit_n200':>10}{'|delta|pp':>10}")
    for y, _ in years:
        v, h = overlap[y], hit.get(y, {})
        o = ovr[y]
        ha, hn = h.get("hit_all"), h.get("hit_n200")
        d = deltas.get(y)
        print(f"{y:>6}{o * 100 if o is not None else float('nan'):>10.1f}"
              f"{v['in_universe']:>9,}{v['trading']:>9,}{v['not_ever_traded_by_year_end']:>7,}"
              f"{h.get('labeled_n200', 0):>7,}"
              f"{ha * 100 if ha is not None else float('nan'):>9.1f}"
              f"{hn * 100 if hn is not None else float('nan'):>10.1f}"
              f"{d * 100 if d is not None else float('nan'):>10.2f}")
    print(f"\nmin overlap {out['min_overlap']:.1%}, mean {out['mean_overlap']:.1%}; "
          f"mean |hit-rate delta| {out['mean_abs_delta_pp'] * 100:.2f}pp", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
