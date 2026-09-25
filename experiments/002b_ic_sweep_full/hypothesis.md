# E002b — full-profile confirmation IC sweep (pre-registered 2026-09-25, BEFORE any run)

**Protocol (BRD §12):** hypothesis written before `run.py` executes; predictions may not be
edited after. Only `results.json`, `verdict.md`, and the LEDGER verdict are written after.

**Why this exists (and why it is a new experiment, not a re-run):** E002 ran on profile
`quick` (11 decision months, 14,373 rows, one regime — all of them up-months per E001's
regime table). Its own ledger row pre-registered that the full-profile sweep is "NOT
pre-registered here", and its verdict flagged the pooling method as fragile (pooled raw ranks
mix market-wide level shifts; `mom_3m` flips sign between pooled and monthly means). Running
the same code on more data after seeing quick results would be post-hoc; the honest form is a
new pre-registration with the method fixed in advance. E002 itself is frozen and is not
edited, re-run, or re-judged by this experiment.

**Question:** which single features survive a full-history (15-year, ~187 decision months,
multiple regimes) univariate IC test with a method that cannot be fooled by market-wide level
shifts?

**Metric — within-month pooling, fixed now:** for each feature and decision month, the
cross-sectional Spearman IC between the feature at D and the forward month return (same
labeling as E002). The headline statistic is the **mean monthly IC** with a one-sample t-test
across months (t = mean / (sd/sqrt(months)), two-sided p via `src.stats.t_sf_two_sided`) —
month fixed effects are removed by construction, so a bull window cannot manufacture IC.
Benjamini–Hochberg across all 22 tested features at α = 0.05. The raw pooled IC (E002's
statistic) is reported alongside for continuity, but no verdict leans on it. Per-regime
monthly IC means (up/down months, split on the month's realized cross-sectional mean forward
return) and per-size-bucket monthly IC means are reported for the headline features —
descriptive, closing what E001 could not (its regime split was vacuous on 11 up-months).

**Pre-registered directions:** identical to E002's frozen map (`experiments/002_ic_sweep/
hypothesis.md`), imported by `run.py` from that module so the two cannot drift. The E002
verdict's direction-agnostic findings (`volume_zscore`, `atr_ratio`, `squeeze_days_20d` etc.)
keep their E002 directions here; for them, surviving with either sign is reported but only
the pre-registered sign counts as confirmation.

**Decision rule (written pre-run):** a feature is **confirmed** iff its mean monthly IC has
the pre-registered sign AND survives BH at α = 0.05 on the across-month t-test; significant
with the opposite sign ⇒ that direction prior is **rejected**; everything else ⇒ not
confirmed (reported, no claim). The sweep as a whole is **confirmed** for Phase 4 purposes if
at least one of the momentum features (mom_6m / mom_12m_1m) is confirmed and the
volatility-state finding reproduces at full history with a stable sign across months (sign
consistency ≥ 70% of months). If momentum does not survive 15 years, the ledger says so and
Phase 4's composite is built from whatever did.

**Scope:** profile `full` (data start 2011-01-01, cutoff = newest bhav date). The derived
tables are rebuilt at full profile through their real entry points before the sweep; the
quick-profile tables are rebuilt by the next selfcheck run (the stamp invalidates itself —
that is the designed behavior, not drift).

**Survivorship note (pre-registered):** the universe is as-of top-1500 by liquidity rank, so
delisted names are included while they trade — no index-membership data is used anywhere in
this experiment.
