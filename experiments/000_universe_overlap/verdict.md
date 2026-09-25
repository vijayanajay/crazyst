# E000 — verdict (written after the run; the hypothesis was not edited)

**Verdict: REJECTED, on the letter of the pre-registered rule — with the fired statistic
shown to be noise-bound. Read the whole verdict before acting on the word.**

- **Overlap clause: decisively confirmed.** The as-of top-1500 universe contains the Nifty
  200 at **min 97.7% / mean 98.7%** across all 15 decision years (bar: ≥ 80%). The universe
  question the plan actually asked — "do we need index-membership data on the critical
  path?" — is answered **no**: there is nothing meaningful left outside the as-of rank.
- **Hit-rate clause: the pre-registered trigger fired.** Mean yearly |hit-rate delta|
  **2.48pp ≥ 2pp** → per the rule, "rejected: universe choice matters and the BRD owner must
  decide". The rule is applied as written.
- **But the fired statistic is noise-bound, and the verdict records why:** at ~130 labeled
  N200 names per year and a 5% winner rate, the binomial noise floor on a yearly hit rate is
  **±1.91pp** — the bar sits *inside* the noise. The observed yearly deltas (0.01pp … 4.90pp,
  flipping sign year to year) are exactly what pure noise predicts (a folded normal at
  σ = 1.91 has a mean |value| of 1.52pp). The pooled statistic — not pre-registered as the
  trigger, reported for exactly this situation — is **|Δ| = 0.86pp** (hit 5.04% on all
  eligible vs 4.17% on N200-only, 741 vs 94 winners over 14,706 vs 2,252 labeled
  symbol-months), noise sd 0.46pp: small, and below the 2pp bar.
- **Consequence per the rule:** the BRD owner must decide before Phase 6 whether the strategy
  is a top-1500 strategy or a large/mid-cap strategy. The evidence this verdict hands the
  owner: (a) Nifty 200 ⊂ top-1500 at ~98% every year; (b) pooled hit-rate difference 0.86pp —
  real but small (2σ); (c) N200-only would drop ~85% of the labeled universe for that 0.86pp.
  **Recommendation recorded: keep the top-1500 universe** — the winner-set difference is
  within yearly noise, and the survivorship caveat below runs against the N200 side too.
- **Survivorship bias (pre-registered, visible in the data):** the current-constituents
  snapshot applied as-of shows 71 of 200 names not yet traded by end-2011 (67 in 2012, …,
  1 by 2025) — early-year N200 coverage is thin *because* the snapshot is today's list. A
  true as-of membership list would raise overlap further and change early hit rates; both
  effects favor the as-of universe, so the overlap conclusion is robust to this bias while
  the early-year hit-rate rows are the least trustworthy in the table.
- **Honest caveats:** (1) the not-yet-listed filter (denominator = traded within ~16 months)
  is disclosed in results.json via `not_ever_traded_by_year_end`; (2) 2011's hit_n200 = 0/123
  is the noise floor in action, not a finding; (3) the pooled delta's 2σ significance is
  borderline and the family (overlap + delta) was not BH-corrected — treat 0.86pp as "small,
  likely real, immaterial" rather than a precise estimate.

**Bottom line for the plan:** no index-membership scraping, ever, on this evidence — the
as-of rank subsumes the index. The 2pp hit-rate trigger fired on a noise-bound statistic; the
BRD owner owns the universe choice with the pooled number in hand.
