"""Task 1.7 — validation report: one command prints data health and exits non-zero if a
configured threshold is breached (plan Phase 1.7 checkpoint deliverable).

Sections:
  1. bhav coverage per year   — distinct dates vs weekdays; FAIL below validate.min_year_coverage_pct
  2. calendar holes           — weekday dates with delivery data but no bhav row (suspicious —
                                a 404-as-holiday outage would show here), weekday dates in
                                neither table (market holidays, informational)
  3. per-symbol gaps          — worst EQ gaps between consecutive observations
                                (suspensions / delistings; informational)
  4. delivery join mismatch   — bhav EQ rows on delivery-dates lacking a delivery row
                                (reuses task 1.5's check); FAIL at/above max_join_mismatch_pct
  5. missing-delivery %       — EQ stock-days inside the delivery span with no delivery row
                                (informational: delivery has known missing stretches, BRD D2)
  6. adj_close coverage       — still-trading EQ symbols with Yahoo adjusted closes (all-time
                                count reported alongside: delisted tickers are absent on Yahoo)
                                (prerequisite gate for the momentum canary)
  7. surveillance rejects     — malformed quarantine rows from the last snapshot import; FAIL
                                while non-empty (quarantine keeps the refresh alive, this keeps
                                it honest)

The NSE-vs-Yahoo raw-price cross-check is live-network and lives in
`python -m src.normalize.adj_close` (20-symbol cross-check) — run it after a refresh.

`python -m src.validate.report` IS the self-check: it validates the real database, which a
synthetic copy cannot (ponytail: no synthetic section here — the normalizers own those).
"""
import subprocess
import sys
from datetime import date, timedelta

import duckdb

from src.config import load
from src.normalize import panels
from src.normalize.delivery import _join_check


def _git_hash() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "?"
    except Exception:
        return "?"


def _weekdays_between(a: date, b: date) -> int:
    n = 0
    while a <= b:
        n += a.weekday() < 5
        a += timedelta(days=1)
    return n


def main() -> int:
    cfg = load("quick")
    v = cfg["validate"]
    con = duckdb.connect(cfg["paths"]["duckdb"], read_only=True)
    failures: list[str] = []
    try:
        db_min, db_max, n_dates = con.execute(
            "SELECT min(date), max(date), count(DISTINCT date) FROM bhav").fetchone()
        print(f"validation report — git {_git_hash()} | profile {cfg['profile']} | "
              f"data cutoff {db_max} | bhav {n_dates:,} dates {db_min} .. {db_max}")

        # ---- 1. coverage per year ----
        print("\n[1] bhav coverage per year (distinct dates vs weekdays)")
        for y, n in con.execute(
                "SELECT year(date), count(DISTINCT date) FROM bhav GROUP BY 1 ORDER BY 1").fetchall():
            a, b = max(date(y, 1, 1), db_min), min(date(y, 12, 31), db_max)
            wd = _weekdays_between(a, b)
            pct = 100.0 * n / wd if wd else 100.0
            flag = ""
            if wd and pct < v["min_year_coverage_pct"]:
                flag, _ = "  <-- FAIL", failures.append(f"{y} bhav coverage {pct:.1f}% "
                                                        f"(< {v['min_year_coverage_pct']}%)")
            print(f"  {y}: {n:4d}/{wd:4d} weekdays ({pct:5.1f}%){flag}")

        # ---- 2. calendar holes ----
        print("\n[2] calendar holes (cross-check: a bhav hole covered by delivery = outage, not holiday)")
        end = date.fromisoformat(panels.data_cutoff(con))
        deliv_only_days = [r[0] for r in con.execute(
            "SELECT DISTINCT date FROM delivery EXCEPT SELECT DISTINCT date FROM bhav ORDER BY 1").fetchall()]
        # the delivery feed can legitimately be fresher than the bhav cache (same-evening MTO vs
        # the bhav-bounded window); only holes INSIDE the bhav window are outage candidates
        holes = [d for d in deliv_only_days if d <= end]
        ahead = [d for d in deliv_only_days if d > end]
        wd_total = _weekdays_between(db_min, db_max)
        neither = wd_total - n_dates - len(holes)
        print(f"  weekdays in span: {wd_total:,} | bhav: {n_dates:,} | "
              f"delivery-only within window: {len(holes)} | beyond end_date (informational): {len(ahead)} "
              f"| in neither (holidays): {neither}")
        if ahead:
            print(f"  delivery ahead of bhav window: {[str(d) for d in ahead[:5]]} "
                  f"(fresh MTO; absorbed when the bhav cutoff moves)")
        if holes:
            print(f"  suspicious dates: {[str(d) for d in holes[:10]]}")
            failures.append(f"{len(holes)} delivery-dates lack a bhav row (outage holes?)")

        # ---- 3. per-symbol gaps ----
        print("\n[3] per-symbol gaps (EQ, calendar days between consecutive observations)")
        gaps = con.execute("""
            SELECT symbol, max(g) AS max_gap FROM (
                SELECT symbol, date - lag(date) OVER (PARTITION BY symbol ORDER BY date) AS g
                FROM bhav WHERE series = 'EQ')
            WHERE g IS NOT NULL GROUP BY symbol ORDER BY max_gap DESC
        """).fetchall()
        n_big = sum(1 for _, g in gaps if g > 30)
        print(f"  symbols with a gap > 30 days: {n_big:,} of {len(gaps):,} EQ symbols")
        for sym, g in gaps[:10]:
            print(f"    {sym:<15} {g:>5} days")

        # ---- 4. delivery join (done-when from 1.5) ----
        print("\n[4] delivery join mismatch on delivery-dates (task 1.5 done-when)")
        pct = _join_check(cfg)
        if pct >= v["max_join_mismatch_pct"]:
            failures.append(f"delivery join mismatch {pct:.2f}% >= {v['max_join_mismatch_pct']}%")

        # ---- 5. missing-delivery % ----
        print("\n[5] missing-delivery % (EQ stock-days in delivery span without a delivery row)")
        miss, tot = con.execute("""
            SELECT count(*) FILTER (WHERE d.symbol IS NULL), count(*)
            FROM bhav b LEFT JOIN delivery d ON d.symbol = b.symbol AND d.date = b.date
            WHERE b.series = 'EQ'
              AND b.date BETWEEN (SELECT min(date) FROM delivery) AND (SELECT max(date) FROM delivery)
        """).fetchone()
        print(f"  {miss:,}/{tot:,} ({100.0 * miss / tot if tot else 0.0:.1f}%) — informational "
              f"(BRD D2: known missing stretches; features degrade to NaN, never 0)")

        # ---- 6. adj_close coverage ----
        print("\n[6] adj_close coverage (momentum canary prerequisite)")
        if con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'adj_close'").fetchone()[0]:
            # Measured on symbols that STILL TRADE (see canary.py [0] for the rationale): Yahoo
            # serves no delisted/renamed ticker, so an all-symbol ratio measures survivorship,
            # not pipeline health. The all-time figure is printed as context only.
            n_eq = con.execute("SELECT count(DISTINCT symbol) FROM bhav WHERE series = 'EQ'").fetchone()[0]
            n_priced = con.execute("SELECT count(DISTINCT symbol) FROM adj_close").fetchone()[0]
            n_live, n_recent = con.execute("""
                WITH recent AS (SELECT DISTINCT symbol FROM bhav WHERE series = 'EQ'
                                AND date > (SELECT max(date) FROM bhav) - INTERVAL 30 DAY)
                SELECT (SELECT count(*) FROM recent r WHERE EXISTS (
                            SELECT 1 FROM adj_close a
                            WHERE a.symbol = r.symbol AND a.adj_close IS NOT NULL)),
                       (SELECT count(*) FROM recent)""").fetchone()
            cov = n_live / n_recent if n_recent else 0.0
            flag = ""
            if cov < v["canary_min_adj_coverage"]:
                flag, _ = "  <-- backfill incomplete", failures.append(
                    f"adj_close coverage {cov:.1%} < {v['canary_min_adj_coverage']:.0%}")
            print(f"  still-trading symbols priced: {n_live:,} / {n_recent:,} ({cov:.1%}){flag}")
            print(f"  all-time: {n_priced:,} / {n_eq:,} EQ symbols ({n_priced / n_eq:.1%}) — "
                  f"the remainder are delisted/renamed tickers Yahoo no longer serves "
                  f"(BRD §4: survivorship — as-of lists, never today's)")
        else:
            print("  adj_close table absent — run python -m src.normalize.adj_close --backfill (task 1.6)")

        # ---- 7. surveillance quarantine (non-empty = the last import had bad rows) ----
        print("\n[7] surveillance rejects (malformed CSV rows quarantined by the last import)")
        if con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'surveillance_rejects'").fetchone()[0]:
            rej = con.execute("SELECT source, line, error FROM surveillance_rejects ORDER BY line").fetchall()
            if rej:
                for source, line, err in rej[:10]:
                    print(f"  {source}:{line}: {err}")
                if len(rej) > 10:
                    print(f"  ... and {len(rej) - 10} more")
                failures.append(f"{len(rej)} quarantined surveillance row(s) in "
                                f"surveillance_rejects — fix the CSV and re-run the import")
            else:
                print("  none")
        else:
            print("  no quarantine table (no snapshot import has run)")
    finally:
        con.close()

    print()
    if failures:
        print(f"REPORT: FAIL — {len(failures)} threshold breach(es):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("REPORT: PASS — all configured thresholds met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
