# Three decisions for the BRD owner — universe scope + exit fills (2026-09-25 / 2026-09-26)

From the Phase 3 experiments (E000, E002b; pre-registered per BRD §12, evidence in
`experiments/000_universe_overlap/` and `experiments/002b_ic_sweep_full/`, verdicts in
`LEDGER.md`) and the Phase 5→6 engine smoke on real full-profile data
(`src/backtest/smoke_e2e.py`, commit `af68a4c`). The first two decisions block Phase 4/6: the
composite and the walk-forward report must state which universe they are claims about, and
today every experiment's evidence is on **top-1500**. The third blocks 6.4: the walk-forward's
exit semantics are undefined when the fill gate refuses a sell.

---

## Decision 1 — Is the strategy a top-1500 strategy or a large/mid-cap (Nifty-200) strategy?

**What we measured (E000).** The as-of top-1500 liquidity universe contains the Nifty 200 at
**min 97.7% / mean 98.7%** per year over 15 decision years (2011–2025, full profile). There
is no meaningful "large/mid-cap only" universe hiding inside the rank — the index is a subset
of it. The plan's question ("is index-membership data ever needed on the critical path?") is
answered: **no**.

**Winner rates on the two universes** (top 5% forward-month return, same labeling):

| universe | labeled symbol-months | winners | hit rate |
|---|---|---|---|
| all eligible (top-1500) | 14,706 | 741 | 5.04% |
| Nifty 200 only | 2,252 | 94 | 4.17% |

Pooled difference: **0.86pp** (noise sd 0.46pp — real at ~2σ, small). Yearly differences
flap between 0.01pp and 4.90pp around a binomial noise floor of **±1.91pp** at ~130 names —
no year is individually meaningful. E000's pre-registered "< 2pp" trigger fired on the
yearly mean (2.48pp), which is why the ledger verdict says "rejected"; the verdict then
shows the fired statistic is noise-bound and hands the choice to you with the pooled number.

**What choosing Nifty 200 would cost:** ~85% of the labeled evidence (2,252 of 14,706 rows),
delisted-name exposure, and — per E002b — the strongest ICs live in the 201–1500 buckets
(mom_12m_1m +0.052, delivery_pct +0.054 in the 601–1500 bucket), all inside the 200+ tail.
A Nifty-200-only strategy is a different, thinner strategy with less of the measured edge.

**One caveat that cuts both ways:** the overlap used today's constituents applied as-of
(71 of 200 names didn't exist by end-2011). A true historical membership list would raise
overlap further; early-year hit-rate rows are the least trustworthy in the table either way.

**Recommendation: keep top-1500.** The large/mid-cap intent is already subsumed; the 0.86pp
hit-rate difference does not justify discarding 85% of the evidence, and Phase 6's size-bucket
attribution (plan 5.6) will report the top-200 slice separately every run — the intent stays
visible without becoming the universe. **Decision needed before the Phase 6 report.**

---

## Decision 2 — Enforce the ₹5-crore median-turnover floor? (`min_median_turnover_cr`, now 0.0)

**What we measured.** BRD §4 states the ₹5cr floor is "subsumed by the top-1500 rank and kept
only as a config guard". The premise is measurably false: the rank-1500 boundary turns over
**₹1.01–1.95cr/day**, and **6,015 of 19,500 in-universe symbol-months (30.8%)** sit below
₹5cr (the eligibility check re-prints this measurement every run). Enforcing the floor would
exclude ~31% of the universe.

**What the floor would do to the strategy:** cut exactly the names the full-history evidence
is strongest on. E002b's confirmed ICs are *highest* in the 601–1500 bucket (mom_12m_1m
+0.052/69% consistency; delivery_pct +0.054/75%). The E000 hit-rate table shows the same.
The floor is also the one §4 rule the data contradicts rather than merely fails to have data
for — it is not a missing-data problem, it is a false premise.

**The rule is implemented and safe to switch on:** `universe.min_median_turnover_cr: 5.0`
excludes with reason `turnover<5.0cr`, propagates through eligibility → panel → matrix with
zero code change. It ships OFF so live behaviour stays BRD-normative until you decide.

**Recommendation: leave it at 0.0 (off) and amend §4** — replace "subsumed" with the
measured sentence ("rank-1500 turns over ~₹1–2cr/day; the floor would cut ~31% of the
universe and the strongest measured ICs"), or restate the floor as a bucket filter (e.g.
min rank 601–1500 excluded) if the *intent* was a quality bar rather than the ₹5cr number.
Enforcing it as written would make the strategy measurably worse on our own evidence.
**Decision needed before Phase 4 weights are frozen** (the composite trains on whatever
universe you choose).

---

## What happens after you decide

Either way, the choice is recorded in the ledger with the experiment numbers attached, the
hypothesis files stay untouched (BRD §12), and Phase 4's pre-registration states the
universe. If you defer: the default path is top-1500 / floor-off, flagged as
"BRD-owner-review-pending" in the Phase 4 hypothesis.

---

## Decision 3 — What happens when the fill gate refuses an EXIT? (§9 gate vs §8.2 exits)

**What we measured (`src/backtest/smoke_e2e.py`, engine pass: 12 consecutive validation-slice
months 2011-07→2012-06 on real bars through Market/Facts/Portfolio/Engine; results in
`runs/smoke_e2e/smoke_results.json`, gitignored — regenerate with
`python -m src.backtest.smoke_e2e`).** BRD §9's fill gate (`backtest.fill.
max_position_adv_frac: 0.05` of trailing-20-session median turnover) is written for entries
but the engine applies it to every order, sells included. On real data it bites exits:

| measurement | value |
|---|---|
| distinct exit attempts | 2 (SOLARINDS monthly review; ECLERX trigger_b_stop) |
| exits blocked by the ADV gate | **1 of 2 — SOLARINDS, refused at T+1 and re-refused at 8 consecutive monthly reviews (2011-09 → 2012-04); 8 of the pass's 10 non-fills** |
| consequence | the slot froze: that month's replacement buy skipped every month (8×); the §8.2 stop/track machinery had no exit path |
| outcome (luck, not design) | the forced hold closed at **+19.59%** after ~9 months — the pass's best closed pick, on the name the strategy tried hardest to leave |
| structural direction | the pick set skews 601–1500 (4,839 of 6,622 pick-months) — exactly where the gate bites; a liquidity-drying small-cap under a stop has **no §8 exit path at all** |

A stop-loss that the fill model can veto is decorative: §8.2 promises "stop = sell", §9
quietly answers "not necessarily". Phase 6.4 cannot report drawdowns or turnover honestly
until you choose the semantics.

**The options:**

- **(a) Stuck-and-retried** (current behaviour, the smoke's documented default): the review
  re-submits the exit every month; the slot stays frozen; no config change. Risk: an
  unbounded hold — the 8% stop becomes fiction, one illiquid pick can pin a slot
  indefinitely, and monthly-review names drift for months.
- **(b) Force-exit at any price**: a risk-management exit (trigger_b_*, gsm/asm, and the
  monthly review's out-of-universe sell) fills regardless of the gate, impact uncapped (or
  capped at a much higher bound), realized exit cost reported separately. Implements §8.2's
  guarantee literally; the cost is real but bounded and measurable. The entry gate stays
  untouched — a position too big to initiate is still refused.
- **(c) Escalate on a timer**: an exit refused at N consecutive review attempts (config,
  suggested N = 2) is marked `exit_impaired` — reported as a risk event, excluded from
  re-entry, and force-exited at the next session at any price. Bounded hold, loud report,
  one config knob.

**Recommendation: (c), N = 2, force-exit at any price with uncapped impact reported
separately.** Risk-management exits must dominate fill-model optimism or §8.2's protections
are decorative; the forced small-cap exit cost is bounded and reportable, while an unbounded
hold is an unbounded risk (the smoke's lucky +19.59% has an unlucky twin in every other
tape). Amend §9 with one sentence making the scope explicit: *the gate protects entries and
routine exits; a risk-management exit may exceed it, at reported uncapped cost.* Whatever
you choose, the smoke's current (a) behaviour stays BRD-normative until you decide — the
same pattern as Decision 2's floor. **Decision needed before Phase 6.4** (the walk-forward's
drawdown, churn and turnover numbers all move with this choice).

**Implemented (2026-09-26, commit `bfd0572`):** the recommendation ships behind
`backtest.exit_gate` in `config.yaml` — modes `stuck` (default = the BRD-normative
behaviour above) / `force` / `escalate` with `escalate_after: N`; engine and smoke honor
it. The owner's choice of mode is still what blocks 6.4.
