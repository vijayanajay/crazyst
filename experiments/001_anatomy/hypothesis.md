# E001 — Anatomy of winners (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12):** hypothesis written before `run.py` executes; predictions may not be
edited after. The only things written after the run are `results.json`, `verdict.md`, and the
LEDGER verdict.

**Question:** how do the winners (top 5% by forward month return, the E002 label set) differ
from the eligible rest on the feature distributions — and does the E002 picture (momentum
confirms, delivery does not, volatility state dominates) hold when read as winner-vs-rest
separation rather than correlation?

**Metric (winners vs rest, per feature):**

- median shift = median(winners) − median(rest), in the feature's own units, plus a
  scale-free version (median shift / rest MAD) so features are comparable;
- **AUC** = P(feature_winner > feature_rest) via the pooled rank sum (average ranks, tie-safe),
  0.5 = no separation, 1.0 = winners rank strictly above;
- normal-approximation p on the pooled AUC (z on the rank-sum statistic), Benjamini–Hochberg
  across all tested features at α = 0.05 — the same multiple-testing discipline as E002;
- **per-month sign consistency**: the share of decision months whose own median shift carries
  the pre-registered sign — the guard against a pooled number driven by one or two months
  (E002's lesson: pooled-only verdicts are fragile).

**Regime split (descriptive, not predictive):** a decision month is UP if the cross-sectional
mean forward return of its eligible rows is > 0, else DOWN. Headline features are reported per
regime — the anatomy question "do winners look different in bad months?" is descriptive and
uses the month's realized return only to bucket months, never to rank names.

**Size-bucket split (pre-registered confounder check, written after E002, before this run):**
headline features are also reported per as-of liquidity bucket (top200 / 201–600 / 601–1500,
`feature_matrix.size_bucket`). Motivation, written down now: E002's dominant finding — the
volatility state (high `atr_ratio`, few `squeeze_days_20d` predicting HIGHER forward returns,
both against their pre-registered lore directions) — could be a small-cap artifact of the
quick-profile universe. If the volatility separation lives only in the 601–1500 bucket, the
Phase 4 composite must not treat it as a broad-market factor.

**Pre-registered directions** (the ledger's E001 row governs; the same sign map as E002 for
the remaining features, which are reported, not celebrated — direction-agnostic `0` features
get AUC only):

| feature | dir | prediction (written pre-run) |
|---|---|---|
| mom_12m_1m | + | **PRIMARY (ledger E001 row):** winners' 12M−1M momentum sits above the rest — median shift > 0, AUC > 0.5 |
| delivery_pct_zscore | + | **PRIMARY (ledger E001 row):** winners' 20-day delivery% z-score sits above the rest — median shift > 0, AUC > 0.5 |
| mom_6m | + | same direction prior as the ledger row's "6–12M momentum" |
| mom_1m, mom_3m | − | reversal horizons: winners sit BELOW the rest |
| all other features | E002's sign map | reported for the anatomy table; their verdicts live in E002 |

**Decision rule (written pre-run):** E001 is **confirmed** iff BOTH primary features show a
median shift of the pre-registered sign with AUC > 0.5 and per-month sign consistency > 50%
on the labeled matrix. If a primary shows significance in the OPPOSITE direction, that prior
is **rejected** (the direction was pre-registered; E002 already warns the delivery prior is
weak). Anything else ⇒ **partial**, described in verdict.md. The volatility-state and
size-bucket findings are explicitly descriptive hypotheses for the full-profile re-run
(E002b) and the Phase 4 composite — they cannot make E001 confirmed or rejected on their own.

**Scope:** profile `quick` (the labeled `feature_matrix`, ~14.4k rows, cutoff = newest bhav
date). No synthetic data: the experiment is a description of the matrix Phase 3 built, and
`feature_matrix`'s own self-check owns the label semantics.
