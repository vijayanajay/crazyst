# E002 — Univariate IC sweep (pre-registered 2026-09-24, BEFORE any run)

**Protocol (BRD §12):** hypothesis written before `run.py` executes; predictions may not be
edited after. The only thing written after the run is `results.json`, `verdict.md`, and the
LEDGER verdict.

**Question:** which single features predict the next month's cross-section of returns on the
as-of top-1500 universe?

**Metric:** monthly Spearman IC = cross-sectional Spearman rank correlation between the feature
value at decision date D and the forward month return (feature_matrix rows labeled from the next
decision month). Reported per decision month and pooled (all labeled rows, one rank correlation
over the whole sample — month fixed effects are not removed; the pooled number mixes market-wide
level shifts with within-month ranking, and verdicts lean on per-month ICs for that reason).
Significance uses the t approximation on Spearman: t = IC·sqrt((n−2)/(1−IC²)), two-sided
p from the t distribution (exact via the regularized incomplete beta, no scipy — ledger M2).

**Multiple testing:** Benjamini–Hochberg step-up across all tested features at α = 0.05
(BRD: ~20 univariate tests ⇒ ~1 false positive by chance; the ledger + walk-forward re-test
are the defense).

**Pre-registered directions** (BRD §6 priors + plan 3.7's "every feature has a pre-registered
direction"). `+` means higher feature value ⇒ positive expected IC; `0` = no prediction, counted
as tested-but-directionless (H1: IC ≠ 0).

| feature | dir | rationale (one line, written pre-run) |
|---|---|---|
| mom_1m | − | NSE monthly reversal is strong at 1M; last month's losers outperform |
| mom_3m | − | short-horizon reversal dominates on NSE mid-caps |
| mom_6m | + | classic 6M momentum horizon; E001's pre-registered 6–12M window |
| mom_12m_1m | + | 12M−1M strips the reversal month; the standard momentum factor |
| volume_zscore | 0 | no reliable prior; direction-agnostic |
| up_volume_20d | 0 | direction-agnostic (scale feature) |
| down_volume_20d | 0 | direction-agnostic (scale feature) |
| up_down_volume_ratio | + | accumulation: up-day volume dominance precedes gains |
| breakout_volume_confirmed | + | confirmed breakouts continue |
| delivery_pct | + | high delivery = conviction holding, a known NSE signal |
| delivery_pct_zscore | + | delivery spike vs own history; E001's pre-registered feature |
| delivery_pct_trend | + | rising delivery = accumulation trend |
| delivery_spike_while_flat | + | quiet accumulation while price flat |
| atr_ratio | − | high volatility predicts lower risk-adjusted continuation |
| nr7 | 0 | regime flag, no directional prior |
| squeeze_days_20d | + | volatility compression precedes expansion (breakout lore) |
| range_compression_20d | − | compressed ranges precede direction resolution (weak prior) |
| close_in_range | + | closing near the high = strength |
| upper_wick_ratio | − | selling pressure rejected at highs |
| lower_wick_ratio | + | buying pressure rejected at lows |
| consec_higher_lows | + | steady accumulation ladder |
| big_body_day_in_trend | + | conviction bar aligned with trend |

**False-positive control:** with 22 features at α = 0.05 two-sided, ~1.1 false positives are
expected by chance; BH is applied to all 22, and survivors must ALSO have the pre-registered
sign to count as confirmations (a significant IC with the wrong sign rejects the direction
prior and is reported as such, not celebrated).

**Decision rule (written pre-run):** E002 is **confirmed** iff at least one of the two
pre-registered headline features (mom_6m / mom_12m_1m as the momentum pair, delivery_pct_zscore
as the delivery one) has pooled IC of the pre-registered sign surviving BH at α = 0.05.
If momentum/delivery features show significance but in the opposite direction, the prediction is
**rejected** (direction was pre-registered). Everything else ⇒ **inconclusive** or partial,
described in verdict.md.

**Scope:** profile `quick` (12 months, the whole labeled matrix, ~14k rows). The `full` sweep is
the same code with a profile flag — not pre-registered here and not run in this pass.
