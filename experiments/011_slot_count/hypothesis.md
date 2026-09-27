# E011 — slot-count attribution: is the walk-forward's −51% concentration or selection?

Written BEFORE any run (BRD §12). The Phase 6.1 harness's first full-profile run
(2026-09-26, cutoff 2026-09-24) realized **−51.0%** (Rs 489,703 from Rs 1,000,000, maxDD
−65.2%) while the SAME fold months' paper top-5% picks averaged **+1.32% net** (2,196
picks, 56.6% hit, binomial p ≈ 0). The harness report named candidate mechanisms: 4-slot
concentration, the adverse T+1 open, churn. This experiment moves ONE lever —
`portfolio.n_slots` — through the unmodified harness, everything else shipped.

**Question:** how much of the realized −51.0% is attributable to holding 4 names
(idiosyncratic variance of a concentrated book) rather than to the selection itself?

**Why n_slots is the right first lever:** the paper edge is a breadth statistic over ~63
picks per fold month; the portfolio realizes only 4 names' worth of it at a time. If the
realized equity path converges toward the paper mean as slots widen, concentration — not
selection — is the dominant loss mechanism. If it does not, the portfolio RULES (entry
timing, exits, churn) are implicated, not the slot count.

## Arms (fixed before the run)

- **A4 (control):** shipped config, n_slots = 4. MUST reproduce the Phase 6.1 baseline
  bit-for-bit on every reported number (final equity to 1e-6, completed picks, hit rates,
  churn, slippage) — the zero-drift guard. No comparison is valid without it.
- **A8:** n_slots = 8, everything else identical.
- **A12:** n_slots = 12, everything else identical.
- **B8 (churn control):** n_slots = 8 with
  `portfolio.monthly_review.sell_below_top_pct`/`replace_above_top_pct` widened to 0.15 /
  0.10, to read whether A8's churn (if higher) is a slot artifact or a ranking-pressure
  artifact. Secondary; reported, never load-bearing.

Slot sizing stays equal-weight across free slots (the §8 rule, unchanged); per-slot
notional therefore falls as slots widen, and the E006/E009 fill gate sees SMALLER orders —
the direction of any fill-gate change is disclosed by the non-fill counts, not tuned for.

## Metrics and bars (fixed before the run)

Per arm: final equity, total return, CAGR, Sharpe (monthly), maxDD, completed picks, pick
and month hit rate, churn/month, avg holding days, non-fill counts, realized slippage
(means over all fills and over the realized book), paper-pick stats (identical across
arms — the picks do not depend on slots; asserted once as an internal consistency check),
per-fold mean net, and the §11 regime table.

**ADOPT a wider slot count as the new default** iff, for A8 or A12:
1. final equity >= A4 + Rs 200,000 (the noise bar: the A4 book's monthly equity changes
   by ~Rs 1-2 lakh on idiosyncratic single-name moves; an improvement below that cannot
   be distinguished from one different coin flip), AND
2. Sharpe (monthly) > A4's Sharpe, AND
3. maxDD is no worse than A4 − 2pp, AND
4. pick hit rate does not fall below A4 − 3pp (guards against the wider book quietly
   filling worse names the old gate would have refused).

If two arms pass, the WIDER one is adopted only if it also beats the narrower on final
equity; otherwise the narrower of the passing pair. Ties resolve to the shipped 4.

**KEEP 4** if no arm clears all four bars — even if some arm improves. The bars are the
pre-registration; a marginal win is not a mandate to rewrite the shipped portfolio.

## Scope and discipline

- Everything else stays shipped: cost 0.50%/side + capped impact, exit_gate escalate,
  floor 0.75, top-5% picks, the frozen composite_2f, warm-ADV markets, the same 35 fold
  months from the same cutoff (2026-09-24), determinism asserted per arm (each pass run
  twice, serialized evaluations identical).
- No-peek: the slot count is a PORTFOLIO parameter, not model information; it never
  touches scoring. The harness's no-peek asserts run unchanged in every arm.
- This is an attribution experiment on an existing harness run, not a search: three slot
  values fixed now, no post-hoc exploration. A FAIL closes the concentration hypothesis
  as the dominant mechanism and redirects to entry timing / exit rules.
- Expected direction (pre-registered, soft): A8/A12 recover a large part of the −51%
  toward the paper mean. If they do not, the loss lives in the portfolio layer's timing
  and rules, not in breadth.
