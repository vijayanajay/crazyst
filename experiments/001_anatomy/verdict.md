# E001 — verdict (written after the run; the hypothesis was not edited)

**Verdict: PARTIAL.** Per the pre-registered decision rule:

- **CONFIRMED — momentum anatomy (primary 1).** `mom_12m_1m`: winners' median is +0.050 above
  the rest, AUC 0.544 (p = 1.1e-4, BH-surviving), per-month sign consistency 64% (> 50%). The
  ledger's E001 prediction "winners' 6–12M momentum sits above the eligible rest" holds:
  `mom_6m` AUC 0.561, 64% consistency.
- **REJECTED — delivery anatomy (primary 2).** `delivery_pct_zscore`: median shift −0.046
  (opposite of the pre-registered +), AUC 0.478 < 0.5, sign consistency 45%, not BH-surviving
  (p = 0.045 uncorrected). The delivery prior fails the anatomy lens exactly as it failed
  E002's IC lens; `delivery_pct` is worse (AUC 0.439, BH-rejected, wrong sign). Consistent
  story, two independent measurements.

**Descriptive findings (pre-registered as hypotheses, not verdicts):**

1. **Volatility state is the strongest winner anatomy — and the pre-registered direction is
   wrong.** `atr_ratio` AUC 0.639 and `range_compression_20d` AUC 0.646 (both BH-rejected with
   shifts POSITIVE): winners were MORE volatile and wider-ranged than the rest before their
   winning month, at every decision month (sign consistency 0%). "Calm stocks then explode"
   does not describe this universe's winners; the lore-direction prediction (dir −1) is
   rejected in the anatomy as it was in E002's sweep.
2. **The size-bucket confounder check (pre-registered in the hypothesis) answered:** the
   volatility separation is uniform across as-of buckets — `atr_ratio` AUC 0.626 / 0.630 /
   0.638 for top200 / 201–600 / 601–1500 — NOT a small-cap artifact. Momentum is the opposite:
   `mom_12m_1m` AUC 0.587 / 0.653 / **0.507** — the momentum anatomy lives in the top and mid
   buckets and disappears in the 601–1500 tail. A Phase 4 composite should expect momentum to
   price mostly the liquid half of the universe and vol-state to price all of it.
3. **Pooled tail vs monthly bulk:** `mom_1m`/`mom_3m` show positive pooled shifts (AUC 0.545 /
   0.566) against their pre-registered negative (reversal) direction, but per-month consistency
   is 18% — the pooled number is driven by a few months. E002's IC (−0.095, bulk) and this
   tail statistic disagree; the honest reading is "the top-5% tail skews to recent winners in
   some months while the bulk reverses." Flagged for E002b, not resolved here.

**Consequence for the plan:** Phase 4's composite candidates, by anatomy + IC evidence, are
`mom_12m_1m` (+), `atr_ratio` (−, i.e. prefer HIGH ATR ratio here — against lore, measured
twice), `range_compression_20d` (−), `volume_zscore` / `up_down_volume_ratio` (weak, direction
mixed). Delivery features are out. The regime split was vacuous on quick data (11 of 11
decision months had a positive cross-sectional mean forward return — a bull-window artifact);
it needs the full-profile re-run to mean anything.
