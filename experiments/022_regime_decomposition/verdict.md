# E022 — verdict: the edge is an UP-month edge; the family stays closed

Run 2026-09-27, profile `full`, all 180 labeled months (2011-07-29 → 2026-06-30; test
window pooled as disclosed). `results.json` is the record; `hypothesis.md` was written
before the run. One post-hoc addition, disclosed in `results.json` (`post_hoc_slice_split`)
and below: the slice × band split, added after the first run to reconcile with E020-C; no
gate reads it.

Guards: G1 top-5% 1-month gross anchor 0.0268 vs the smoke's committed 0.0281 (inside the
0.15pp tolerance, E018's G1 construction); G2 index leg == E019's committed index_equivalent
(0.131683 CAGR / its maxDD) to 1e-9; G3 180 months, 0 without a regime band, zero dropped
legs asserted. All green.

## Main table (decile rank-weighted book vs Nifty 500 TRI, same interval, excess = book − index)

Overall (179 intervals): book +2.27%/mo, index +1.14%/mo, **excess +1.13%/mo, t 2.86,
hit 61%**. The 2018–2020 episode contributes **7%** of the full-sample mean excess.

| regime band (index ret ending at m) | n  | mean excess | t    | hit |
|---|----|--------|------|-----|
| down  | 40 | +0.13% | 0.11 | 55% |
| flat  | 63 | +0.56% | 0.95 | 56% |
| up    | 76 | **+2.13%** | **4.23** | 68% |

| index drawdown at m | n  | mean excess | t    | hit |
|---|----|--------|------|-----|
| deep ≤ −15%      | 7  | +3.89% | 1.28 | 71% |
| moderate         | 58 | +0.17% | 0.23 | 59% |
| shallow > −5%    | 114 | +1.45% | 3.19 | 61% |

## Post-hoc slice × band (disclosed; descriptive only)

| slice | band | n  | book   | index  | excess | t    |
|---|---|----|--------|--------|--------|------|
| validation | down | 33 | +0.54% | +0.71% | −0.17% | −0.12 |
| validation | flat | 49 | +1.94% | +1.27% | +0.67% | 1.02 |
| validation | up   | 63 | +3.69% | +1.29% | **+2.40%** | **4.14** |
| test       | down | 7  | +3.78% | +2.27% | +1.50% | 0.84 |
| test       | flat | 14 | +0.52% | +0.36% | +0.16% | 0.12 |
| test       | up   | 13 | +2.05% | +1.22% | +0.83% | 1.01 |

## Reading

1. **The edge is an UP-month edge, not a crash edge.** In-sample the book outruns the
   index by +2.40%/mo in up months (t = 4.14) and adds nothing in down months (−0.17%,
   t = −0.12). The crash-alpha suspicion that motivated the experiment (E020's
   `dd_2018_2020` tracking, the deep-DD bucket) is dead on the evidence: 2018–2020 is 7%
   of the full-sample excess, and the deep-DD bucket is n = 7, t = 1.28 — noise. The
   −47% maxDD of the deployable book is beta times the index's crash, not negative alpha.
2. **E020-C reconciled.** The test window's up-month excess collapsed to +0.83%/mo
   (t = 1.01, n = 13) from the validation slice's +2.40% (t = 4.14, n = 63). With 13
   up-months, decay and sampling noise are indistinguishable — but either way, the
   deployable edge in the only window that matters was ≈ +0.04pp/mo.
3. **No stable conditional structure to exploit.** The frozen re-open rule was written
   for stress-concentrated alpha; it fails (deep − shallow = +2.44pp < 3.0pp, n_deep = 7).
   And the measured structure offers nothing better: conditioning exposure on the band
   that worked in-sample (up-months) would have *reduced* exposure in the test window's
   flat months and missed the test window's only positive bucket (down, +1.50%). The
   conditional structure flips sign out of sample — the same instability that killed the
   E021 gate, seen from the other side.

## Decision

Per the frozen rule: **the family stays closed.** The diagnostic's contribution is the
explanation for the closure: the satellite is a long-beta up-capture overlay whose alpha
is regime-concentrated in up months in-sample and indistinguishable from zero out of
sample. No mechanism on this signal — stops (E017), gates (E021), sizing (E015/E021),
blends (E020), or regime conditioning, now measured — converts it into a deployable
configuration. The program's next step is new signal families (the feature-family audit,
delivered alongside as `docs/feature_family_audit.md`), not more mechanics on this one.
The standing deploy recommendation remains pure indexing.
