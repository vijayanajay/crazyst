"""Task 5.6 — size-bucket attribution: the blended line is never the whole story.

The plan's 5.6 done-when: a bucket table in the report pack; blended-only reporting fails
review. This module takes the same inputs metrics.py takes (a trade log of TradeEvents +
a (month, symbol) -> bucket source) and answers, per as-of bucket — top200 / 201-600 /
601-1500 (config universe.size_buckets) — what the report needs:

- picks + hit_rate         completed round trips per bucket (FIFO, via the metrics math)
- mean_return              mean net return of the bucket's completed picks
- churn_per_month          Trigger A/B mid-month replacements per month (§8.3 threshold)
- churn attribution        which bucket the mid-month churn came from

Bucketing is AS-OF the pick's decision month (the rank the strategy actually saw) — never a
current-membership split, which would leak. Buckets come from feature_matrix.size_bucket;
the caller supplies the mapping, so this module never queries the database and works on
synthetic runs unchanged.

python -m src.backtest.attribution runs the synthetic self-check: hand-built events whose
per-bucket hit rates, returns and churn are computed on paper first, plus the two
review gates — buckets must partition all picks, and per-bucket stats must reconstruct
the blended line exactly.
"""
from __future__ import annotations

import sys
from collections import defaultdict

from src.backtest.metrics import TradeEvent


def _bucket_map(bucket_of) -> dict[tuple[str, str], str]:
    """Accept a {(month, symbol): bucket} dict or rows of (mdate, symbol, size_bucket);
    return the {(month, symbol): bucket} dict."""
    if isinstance(bucket_of, dict):
        return bucket_of
    return {(str(m), s): b for m, s, b in bucket_of}


def bucket_attribution(events: list[TradeEvent], bucket_of,
                       months: int) -> dict[str, dict]:
    """Per-bucket {picks, hit_rate, mean_return, churn_per_month, churny} + "blended" row.

    `bucket_of` maps (decision month, symbol) -> bucket label; feature_matrix rows
    (mdate, symbol, size_bucket) are accepted directly. The BUY event carries the decision
    month; a sell — including mid-month churn sells — is attributed to the open lot's
    bucket. FIFO pairing replicates metrics.completed_picks exactly, with a bucket tag.
    """
    bm = _bucket_map(bucket_of)
    if months <= 0:
        raise ValueError("months must be positive")

    open_lots: dict[str, list[list]] = defaultdict(list)   # sym -> [month, basis, qty_left, bucket]
    picks: list[tuple[str, float, bool]] = []              # (bucket, net return, closed by a mid-month churn sell)
    for e in events:
        if e.buy:
            key_month = e.signal_month or e.date[:7]    # AS-OF: the decision month, not the fill
            bucket = bm.get((key_month, e.symbol))
            if bucket is None:
                raise ValueError(f"no bucket for ({key_month}, {e.symbol}) — "
                                 f"bucket_of must cover every bought symbol")
            open_lots[e.symbol].append([e.date[:7], e.price, e.qty, bucket])
            continue
        sell_qty = -e.qty                                   # sell quantities are negative
        cost_per_share = e.cost / sell_qty
        qty_to_close = sell_qty
        for lot in open_lots.get(e.symbol, []):
            if qty_to_close <= 0:
                break
            take = min(lot[2], qty_to_close)
            basis = lot[1] + cost_per_share                 # buy price + share of the sell's costs
            proceeds = e.price - cost_per_share
            picks.append((lot[3], proceeds / basis - 1.0, e.mid_month))
            qty_to_close -= take
            lot[2] -= take
        open_lots[e.symbol] = [lot for lot in open_lots.get(e.symbol, []) if lot[2] > 0]

    rows: dict[str, dict] = {}
    for b in sorted({bucket for bucket, _, _ in picks}):
        bp = [r for bucket, r, _ in picks if bucket == b]
        churn_sells = sum(1 for bucket, _, mid in picks if bucket == b and mid)
        rows[b] = {
            "picks": len(bp),
            "hit_rate": sum(1 for r in bp if r > 0) / len(bp) if bp else 0.0,
            "mean_return": sum(bp) / len(bp) if bp else 0.0,
            "churn_per_month": churn_sells / months,
            "churny": churn_sells / months > 1.5,           # §8.3 twitchy threshold
        }
    rows["blended"] = {
        "picks": len(picks),
        "hit_rate": (sum(1 for _, r, _ in picks if r > 0) / len(picks)) if picks else 0.0,
        "mean_return": (sum(r for _, r, _ in picks) / len(picks)) if picks else 0.0,
        "churn_per_month": sum(1 for _, _, mid in picks if mid) / months,
        "churny": sum(1 for _, _, mid in picks if mid) / months > 1.5,
    }
    return rows


def assert_consistent(attr: dict[str, dict]) -> None:
    """The review gates (plan 5.6): buckets must reconstruct the blended line.

    Raises if a caller tries to report blended-only, or if bucket stats disagree with the
    blend — exactly the failure the done-when describes.
    """
    assert "blended" in attr, "bucket_attribution must produce the blended line"
    buckets = [k for k in attr if k != "blended"]
    assert buckets, "no bucket rows — blended-only reporting fails review"
    blended = attr["blended"]
    assert sum(attr[b]["picks"] for b in buckets) == blended["picks"], \
        "bucket picks do not sum to blended picks"
    if blended["picks"]:
        wmean = sum(attr[b]["picks"] * attr[b]["mean_return"] for b in buckets) / blended["picks"]
        assert abs(wmean - blended["mean_return"]) < 1e-9, \
            f"per-bucket means do not reconstruct the blend: {wmean} vs {blended['mean_return']}"
        whr = sum(attr[b]["picks"] * attr[b]["hit_rate"] for b in buckets) / blended["picks"]
        assert abs(whr - blended["hit_rate"]) < 1e-9, \
            f"per-bucket hit rates do not reconstruct the blend: {whr} vs {blended['hit_rate']}"


# ---- synthetic self-check: hand-computed on paper first ------------------------------------------


def _self_check() -> None:
    T = TradeEvent
    # Hand-built log, 3 buckets, paper math (no costs -> net return = sell/buy - 1):
    #   TOP   +20% win   bought Jan, monthly sell in Mar
    #   MID   -10% loss  bought Jan, monthly sell in Mar
    #   TAIL  -8% loss   bought Jan, MID-MONTH sell in Feb (churn)
    #   TOP2  +30% win   bought Feb, monthly sell in Mar
    #   T2MID -5% loss   bought Feb, MID-MONTH sell in Feb (churn)
    # Window: Jan..Mar = 3 months. Expected rows:
    #   top200:    2 picks, hit 1.0,  mean +25%,  churn 0   (TOP +20%, TOP2 +30% — both wins)
    #   201-600:   2 picks, hit 0.0,  mean -7.5%, churn 1/3 (T2MID)
    #   601-1500:  1 pick,  hit 0.0,  mean -8%,   churn 1/3 (TAIL)
    #   blended:   5 picks, hit 0.4,  mean +5.4%, churn 2/3
    events = [
        T("2026-01-05", "TOP", True, 100, 10.0, 0.0),
        T("2026-01-05", "MID", True, 100, 10.0, 0.0),
        T("2026-01-05", "TAIL", True, 100, 10.0, 0.0),
        T("2026-02-05", "TOP2", True, 100, 10.0, 0.0),
        T("2026-02-05", "T2MID", True, 100, 10.0, 0.0),
        T("2026-02-15", "TAIL", False, -100, 9.2, 0.0, True),
        T("2026-02-16", "T2MID", False, -100, 9.5, 0.0, True),
        T("2026-03-10", "TOP", False, -100, 12.0, 0.0),
        T("2026-03-10", "MID", False, -100, 9.0, 0.0),
        T("2026-03-10", "TOP2", False, -100, 13.0, 0.0),
    ]
    bucket_of = {
        ("2026-01", "TOP"): "top200", ("2026-01", "MID"): "201-600",
        ("2026-01", "TAIL"): "601-1500", ("2026-02", "TOP2"): "top200",
        ("2026-02", "T2MID"): "201-600",
    }
    attr = bucket_attribution(events, bucket_of, months=3)
    assert_consistent(attr)

    a, m, t = attr["top200"], attr["201-600"], attr["601-1500"]
    b = attr["blended"]
    assert a["picks"] == 2 and abs(a["hit_rate"] - 1.0) < 1e-12 \
        and abs(a["mean_return"] - 0.25) < 1e-12 and a["churn_per_month"] == 0.0, a
    assert m["picks"] == 2 and m["hit_rate"] == 0.0 \
        and abs(m["mean_return"] + 0.075) < 1e-12 \
        and abs(m["churn_per_month"] - 1 / 3) < 1e-12 and not m["churny"], m
    assert t["picks"] == 1 and t["hit_rate"] == 0.0 \
        and abs(t["mean_return"] + 0.08) < 1e-12 \
        and abs(t["churn_per_month"] - 1 / 3) < 1e-12 and not t["churny"], t
    assert b["picks"] == 5 and abs(b["hit_rate"] - 0.4) < 1e-12 \
        and abs(b["mean_return"] - 0.054) < 1e-12 \
        and abs(b["churn_per_month"] - 2 / 3) < 1e-12 and not b["churny"], b

    # FIFO partial-close across buckets: TOP bought in 2 lots (Jan @10 x50 in top200,
    # Feb @20 x50 also top200), one sell of 60 closes 50 @10 + 10 @20 -> two picks,
    # and the churn flag lands on BOTH partial picks of that sell (§8.3 counts sells).
    lots = [
        T("2026-01-05", "TOP", True, 50, 10.0, 0.0),
        T("2026-02-05", "TOP", True, 50, 20.0, 0.0),
        T("2026-02-16", "TOP", False, -60, 15.0, 3.0, True),
    ]
    attr2 = bucket_attribution(lots, {("2026-01", "TOP"): "top200",
                                      ("2026-02", "TOP"): "top200"}, months=1)
    assert attr2["top200"]["picks"] == 2, attr2
    # paper: cost/share = 3/60 = 0.05; lot1 (50 @10): (15-0.05)/(10+0.05)-1 = +49.005..%
    assert abs(attr2["top200"]["mean_return"] * 2
               - (14.95 / 10.05 - 1 + 14.95 / 20.05 - 1)) < 1e-12, attr2
    assert attr2["top200"]["churn_per_month"] == 2.0 and attr2["top200"]["churny"], attr2

    # every bought symbol must have a bucket (silent None would misattribute)
    try:
        bucket_attribution(lots, {("2026-01", "TOP"): "top200"}, months=1)
        raise SystemExit("missing bucket must raise")
    except ValueError:
        pass

    # review gate: a caller reporting blended-only must fail assert_consistent
    blended_only = {"blended": attr["blended"]}
    try:
        assert_consistent(blended_only)
        raise SystemExit("blended-only report must fail review")
    except AssertionError:
        pass

    print("PASS: attribution (per-bucket picks/hit/return/churn vs hand-computed paper "
          "values; FIFO partial closes; buckets reconstruct the blend; blended-only "
          "reporting fails review)", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _self_check()
