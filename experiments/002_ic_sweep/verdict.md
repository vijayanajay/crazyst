# E002 — verdict (2026-09-24, profile `quick`)

**Prediction (pre-registered):** 6–12M momentum and delivery% z-score have positive pooled
Spearman IC, surviving BH at α = 0.05.

**Verdict: PARTIALLY CONFIRMED.**

## The headline features

| feature | pre-registered dir | pooled IC | p | BH | top-5% precision | verdict |
|---|---|---|---|---|---|---|
| mom_6m | + | −0.024 | 0.004 | * | 50.6% | **rejected** (wrong sign) |
| mom_12m_1m | + | **+0.065** | 2.5e-14 | * | 53.2% | **confirmed** |
| delivery_pct_zscore | + | −0.010 | 0.22 | | 45.6% | **rejected** (n.s. and wrong sign) |

The decision rule needed at least one headline feature positive + BH-surviving: **`mom_12m_1m`
meets it** — pooled +0.065, monthly IC mean +0.102 (the only feature above the conventional 0.10
IC bar), and it reproduces the M2 momentum canary's +0.065 on an independent universe/label path.
`mom_1m` confirms the pre-registered **negative** direction: IC −0.095 (p = 2e-30), and its
top-5%-by-value slice wins 72.0% of the time — on this universe and window, last month's losers
outperform last month's winners.

## Rejected priors

- **Delivery z-score** — the E001/E002 India-specific prior is falsified on quick data: not
  significant (p = 0.22), wrong sign. `delivery_pct` level (+0.034) and `delivery_pct_trend`
  (+0.021) survive BH, but both sit far below the momentum signal and their monthly means are
  small (+0.078 / +0.030); treat as weak.
- **`mom_6m`** — still reversal-dominated at the 6-month horizon on 12 months of data; the
  momentum horizon on NSE mid-caps appears to start later than 6M.
- **Breakout/compression lore** — pre-registered as positive: `squeeze_days_20d` is the
  sweep's strongest signal but at **−0.196** (p = 7e-123) — the opposite direction. Volatility
  compression predicts *continued* quiet, not breakout. `breakout_volume_confirmed` (+1 prior)
  is n.s. (−0.010).

## Direction-agnostic findings (hypotheses, not conclusions)

`atr_ratio` +0.126 (p = 2e-51; pre-registered −1, so also a direction rejection),
`volume_zscore` +0.106, `range_compression_20d` +0.078 (pre-registered −1: rejection),
`big_body_day_in_trend` +0.074, `nr7` −0.055. Together with `squeeze_days_20d` these say the
same thing one way: **low recent volatility predicts higher next-month returns on the as-of
top-1500** — the dominant pattern in this sweep, stronger than any momentum feature. No
pre-registered direction protected these from selection effects; they are the input to E001's
anatomy and the full-profile re-run, not settled findings.

## Reading discipline

18 of 22 features survive BH — with n ≈ 14k, tiny ICs are "significant," so the multiple-testing
correction alone is not the filter that matters; the pre-registered sign and the per-month view
are. Pooled ranks mix market-wide level shifts: several features flip sign between pooled and
monthly means (`mom_3m`: pooled −0.019 vs monthly +0.028), which is why the hypothesis
pre-committed verdicts to per-month ICs and why a single-sign composite must be re-tested on
`full` before Phase 4 trusts it.

## Reproduce

```
.venv/Scripts/python -m src.selfcheck            # suite incl. src.stats (exact t-tail vs closed forms)
.venv/Scripts/python -m experiments.002_ic_sweep.run            # profile quick
.venv/Scripts/python -m experiments.002_ic_sweep.run --profile full   # not pre-registered; run later
```
