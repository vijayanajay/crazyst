# E025 — verdict: REJECTED — no deployable-sized inclusion effect at the monthly horizon

Run 2026-09-27, profile `full`, 145-month validation slice (test window untouched).
`results.json` is the record; `hypothesis.md` was written before the run. An IC screen,
not a design experiment.

| arm | event-months | mean IC (t) | mean label gap/mo (t) | flagged name-months |
|---|---|---|---|---|
| include (12-mo lookback) | 122 | −0.0012 (−0.23) | **−0.17pp** (−0.65) | 3,652 |
| exclude (12-mo lookback) | 122 | −0.0094 (−1.82) | **−0.58pp** (−0.96) | 1,898 |

Bars (frozen): includer gap ≥ +1.0pp/mo or excluder gap ≤ −1.0pp/mo, over ≥ 30
event-months. FAIL on both: the includer gap is the wrong sign and ~zero, the excluder
gap is the right sign (excluded names drift lower) but half the bar and insignificant.

Guards: G1 source coverage — 1,216 of 2,495 Nifty 500 events matched to NSE symbols
(via the EQUITY_L master; ≥ 1,000 required); G2 slice pins (145 months, boundary
2023-09-24); G3 no look-ahead by construction (flags read only events dated ≤ m).

## Data provenance (the honest part of this result)

The source fetched cleanly: `archives.nseindia.com/content/indices/IndexInclExcl.xls`
(2,495 Nifty 500 events, 1998-08-01 → **2020-09-14** — the community-reported staleness
confirmed) plus `EQUITY_L.csv` as the name→symbol bridge. 51.3% of events did not match a
current symbol (renames, delistings, master-snapshot gaps — counted and excluded, never
silently dropped). Months after 2021-09 (12-month lookback past the last event) carry no
flags and cannot contribute: 122 of 145 months are event-bearing, exactly as the frozen
disclosure anticipated. `src/download/index_events.py` is committed and re-runnable; the
raw files cache under `data/raw/index_events/`.

## Reading

Two real findings, both negative for deployment. First, at the monthly horizon with a
12-month lookback window there is **no includer drift** on this universe — consistent with
the academic consensus that index effects concentrate around the *announcement*, which a
12-month smearing window and a monthly label cannot capture. Second, the exclusion side
points the expected direction (excluded names underperform) but at half the practical bar
— a real-world nuisance (universe decay), not a tradeable signal. The audit's data
direction is therefore measured and closed: nothing in the public, free, stale-source
space justifies a portfolio pre-registration.

## Decision

Per the frozen rule: **REJECTED**. With E023 (composite family), E024 (conditional
volatility), and E025 (new data, first tranche) all rejected, the audit's shortlist is
exhausted of items expected to move the needle. The standing deploy recommendation is
unchanged — **pure indexing** — and the program's remaining honest options are recorded in
the LEDGER: prospective pre-registrations judged on virgin monthly folds, or a
fundamentals/vendor source as a distinct future effort.
