# Feature-family audit: what the composite never measured, and what to test next

2026-09-27. Written for the post-closure decision recorded in E022: the breadth family is
closed on this signal, and the next program step is a **new signal family** run through the
existing experiment factory. This document inventories what the shipped composite_2f and the
panel actually use, what was already measured and rejected, and a shortlist of candidates —
each with the evidence that justifies it, the expected impact, and the honest tradeoff.

## 1. What the shipped signal is

`composite_2f` (P4.1b, extracted to `src/model/composite.py`): the mean cross-sectional
percentile rank of exactly **two** features —

| feature | E002b full-history mean monthly IC | p | note |
|---|---|---|---|
| `mom_12m_1m` | +0.0522 | 1.1e-6 | classic 12-1 momentum |
| `delivery_pct` | +0.0491 | 1.2e-11 | NSE delivery percentage (India-specific) |

That is the entire production signal. P4.1's composite-of-three (adding `mom_6m`, IC
+0.0242, p 0.019) missed its pre-registered bar (p 0.0585) and the simpler two-feature
version shipped. Everything else in the panel is scored nowhere.

## 2. What the panel already computes but the composite ignores (22 built, 2 used)

`src/features/panel.py` builds 22 features per eligible symbol-month; E002b IC-swept all of
them at full history with BH correction. The unused 20, by verdict:

- **Confirmed but not shipped (the natural next composites):**
  - `delivery_pct_zscore` (+0.0169, p 1.6e-5) and `delivery_pct_trend` (+0.0229, p 5.9e-9)
    — the delivery *dynamics*, vs the shipped level. Correlated with `delivery_pct`, so a
    composite test must pre-register the combination, not cherry-pick.
  - `mom_6m` (+0.0242, p 0.019) — P4.1's near-miss.
- **Regime-flipping (measured, conditionally real):** `atr_ratio` is +0.045 in up-months /
  **−0.183 in down-months** (94% down-month consistency) — the strongest conditional signal
  in the repo. Its unconditional IC is negative (−0.0431): as a *long* factor it selects
  low-vol; the information is in the regime interaction. P4.1's unconditional overlay was
  rejected (−0.0390, p 0.0033); a conditional use was never tested.
- **No edge (dead):** `volume_zscore`, `nr7`, `squeeze_days_20d`, `up_down_volume_ratio`
  (negative), `breakout_volume_confirmed` (negative), the wick/body candle family
  (`close_in_range`, `consec_higher_lows`, `big_body_day_in_trend` all negative),
  `range_compression_20d` (negative), `delivery_spike_while_flat` (flat), `mom_3m`,
  `mom_1m` (negative), `up_volume_20d`/`down_volume_20d`.
- Also measured and rejected downstream: the learned ranker over all 22 (P4.2 — rejected on
  the slice), regime overlays on the engine (E013/E014), exposure sizing (E015), low
  turnover (E016), stops (E017).

## 3. What no experiment has ever measured (the actual gaps)

The panel is 100% **price, volume, and delivery** data. Three whole data domains have zero
columns in `feature_panel`, zero experiments, and in two cases zero tables:

1. **Fundamentals / corporate events** — no earnings, no accruals, no balance-sheet items,
   no promoter-pledge data, no dividend announcements. Not a missing feature: a missing
   *source*. The remaining gap that is cheap: **corporate-action metadata already flows
   through bhavcopy** (series changes, 52-week flags) and the `adj_close` repair work
   surfaced symbol-lifecycle events (1,066 zero-coverage symbols = delistings/renames) —
   an unexploited event-study dataset sitting in tables the repo already owns.
2. **Index membership / flows** — `index_tri` exists only as a benchmark. NSE publishes
   index inclusion/exclusion dates, and the eligible-universe tables could identify
   "entering the Nifty 500" names. Inclusion-flow drift is a documented India effect and
   the factory could test it with one new download + one IC sweep.
3. **Cross-sectional market structure** — `market_breadth` / `market_breadth_daily` tables
   exist in the DB (built during the harness work) but feed no feature and no experiment.
   Breadth-conditioned *universe* selection (not book gating — E021's lesson applies) has
   never been measured.

Also never measured, without new data: **interaction/reversal terms** between the two
shipped features (e.g. `delivery_pct` × `mom_12m_1m` rank products — the composite's
equal-weight mean throws away any interaction), and **quality-of-momentum** filters
(momentum built on few up-days is known to be lower quality; the panel already has the
ingredients).

## 4. Shortlist — what to test next, in order

| # | Candidate | Evidence | Expected impact | Effort | Tradeoff |
|---|---|---|---|---|---|
| 1 | **3f composite re-test** (`delivery_pct` + `delivery_pct_zscore`/`_trend` + `mom_12m_1m`) | ICs above, all confirmed at 15y; P4.1's 3f bar miss was momentum-only | +1–2pp IC over 2f at best; the delivery dynamics add *stability*, not raw IC | Hours — panel exists; one pre-registered IC + book test | Correlated features; multiple-testing across combinations — freeze ONE combination before running |
| 2 | **Down-month volatility factor** (short high-`atr_ratio`, or atr-conditional tilt) | E002b: −0.183 down-month IC, 94% consistency — the strongest conditional signal in the repo | Targets exactly E022's dead bucket (down-months, where the book earns ~0); a hedge leg, not a return engine | Hours for the IC; a short/tilt book needs the E018 machinery | Shorting is out of scope for the deployable account; as a tilt it inherits E021/E022's instability risk — pre-register the conditional use explicitly |
| 3 | **Index-inclusion flow event study** | Documented India effect; zero coverage today; `eligible` + a new small download | Unknown — the first genuinely *new* information class | Days (new downloader + event calendar + IC test) | Event effects are front-run; needs careful as-of discipline |
| 4 | **Interaction terms of the shipped 2f** | The equal-weight mean provably discards interactions; never tested | Modest; often nothing | Hours | Classic overfitting surface — one pre-registered product only |
| 5 | **Momentum quality filter** (up-day count / path smoothness) | Literature-standard; panel ingredients exist; never measured | Sharpens the shipped feature rather than adding one | Hours | Marginal after E022's finding: the composite's edge is up-month beta-capture; a quality filter improves *which* up-months, not the regime problem |

Deliberately **not** shortlisted: more mechanics on the breadth book (closed, measured six
ways), candlestick/volume features (E002b dead), learned rankers (P4.2 dead), and anything
requiring the fundamentals firehose (real data-engineering project; revisit only if 1–4
exhaust).

## 5. The discipline that makes this list safe

Every candidate above goes through the same factory the first 22 experiments built:
`hypothesis.md` frozen before the run (BRD §12), guards tied to committed pins (IC pin,
index-equivalent, pick counts), the 145-month validation slice, the verdict beside the
results, the LEDGER row. The one lesson to carry from the closure: **the test window stays
closed until a design has passed the validation slice** — E020-C spent it once; virgin
folds accrue monthly (cutoff 2026-09-24) and are the only honest second chance a new signal
gets.
