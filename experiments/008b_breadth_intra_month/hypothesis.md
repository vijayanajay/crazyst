# E008b — Hypothesis: intra-month breadth protection on the Trigger-B layer (pre-registered)

Written **before** the run, per BRD §12. Follows E008a's verdict: the monthly breadth gate
was rejected because a decision-date cadence is structurally mistimed — it reads breadth
*after* the crash prints and is paid the rebound. The one legitimate use E008a left open is
**intra-month**: the same gauge sampled daily, wired where protection is actually timed —
the Trigger-B layer (§8.2, any-close exits). This experiment pre-tests that BEFORE any
default changes: **daily breadth, tightened mid-month trails must cut drawdown in stress
windows without giving back the return.**

## Evaluation plan (decided before any code — the harness gap)

The Phase 6.1 walk-forward harness **does not exist yet** (`src/walkforward/` is empty).
Two options were on the table; the decision is:

- **Interim evaluator now, harness = final judge.** E008b extends the proven engine pass
  (`smoke_e2e` pattern: real bars, real `Market`/`Facts`/`Portfolio`/`Engine`, T+1 fills)
  to **per-session** Trigger-B checks and **daily** equity marks, run over **fixed,
  pre-named stress windows** — not a rolling re-score protocol. Building 6.1 inside this
  experiment would couple a pre-registered question to an unbuilt, unreviewed artifact;
  the question asked here ("does a breadth-tightened trail protect in a crash window?")
  is answerable on a fixed window with the real layers the gate touches.
- **Consequence:** even a full PASS does **not** flip any default. The gate key stays
  OFF in config.yaml; a PASS only promotes it to an experiment-backed candidate whose
  final judge is the 6.1 harness (walk-forward, 6.4). A FAIL closes the idea, exactly as
  E008a closed the monthly gate.

Interim evaluator's declared ceiling (`ponytail`): fixed windows from an all-cash start,
monthly re-selection only, no delivery-z clause, no surveillance (same as the smoke);
the comparison is arm-vs-arm on the identical tape, so these simplifications are fair,
but absolute numbers are plumbing-scale — the harness produces results, this produces a
direction.

## Construction (fixed before the run)

- **`market_breadth_daily(date DATE, breadth_200 DOUBLE, n_top200 INTEGER)`**, one row per
  bhav EQ session, rebuilt by this run script (derived-table status, like E008a's
  `market_breadth` — not part of the daily chain).
- **Same machinery as E008a, different sampling dates**: dense per-session calendar
  (suspensions cannot shift a window), 200-trading-**print** adjusted-close DMA per symbol
  (raw prices break at splits), a symbol with <200 prints of history **not counted**, the
  denominator is the count of defined DMAs (a NULL adj print shrinks it, never votes
  "below"). The E008a aggregate lesson is baked in: tier share is
  `avg(above) FILTER (WHERE ...)` on the aggregate itself.
- **As-of membership, daily:** the top-200 set at session D is each symbol's **latest
  `universe_rank` row with `mdate <= D`** (rank ≤ 200, in_universe) — never a static list,
  never the future month's rank (E000's rule, applied mid-month).
- **Top-200 tier only.** E008a measured the mid tier (201–1000) at ρ = 0.939 agreement —
  nearly redundant; a second tier is a second column with no new information. Dropped.
- **Weekly series** is derived from the same daily table: breadth on each week's last
  session (Monday-week). No separate construction.
- **Gate read timing:** `trigger_b` decides at the close of session D, orders fill T+1 —
  the gate reads breadth **as of D's close**, the same convention as the close-based
  stop/trail clauses it sits next to. The weekly arm reads the **last completed week-end
  session** (strictly ≤ D) — the coarser cadence E008a showed matters.

### Sanity layer (E008a's first run was wrong until caught — this is mandatory)

1. **Member-level recompute** at three fixed dates (2017-06-30 bull, 2018-10-25 stress,
   2020-03-23 crash trough): pull the as-of members, each member's trailing 200 adj
   prints, recompute the DMA and the above-share in Python, assert agreement with the
   table to 1e-6 (share and member count).
2. **Intra-month trough check (reported, not gating):** the daily minimum inside
   2020-03 must sit at or below the month-end print (15.5%) — if the trough is not
   visible intra-month, the whole premise of daily sampling is dead and the run says so.
3. **Stress visibility:** 2018-09/10 and 2020-03 daily breadths must trade well below the
   calm-2017 levels.

## Gate design (fixed before the run)

- New `Facts.breadth_pct: float | None` (caller-computed; **None = gate inert** — before
  the first defined breadth date, or a caller that does not supply it: the checkpoint and
  smoke are untouched and bit-identical).
- Config (both under `portfolio.midmonth`):
  - `trigger_b_breadth_threshold: 40.0` — the gate's line, in gauge percent.
  - `trigger_b_breadth_trail_tighten: null` — **pp removed from the trail giveback when
  breadth < threshold; `null`/`0` = OFF (the shipped default)**. `src/config.py` validates
  shape when set (0 < tighten < trail_pct x 100; 0 < threshold < 100) and accepts OFF.
- **Mechanics: only the trail clause tightens** — the allowed giveback
  `trigger_b_trail_pct` 12% → 12% − tighten (e.g. 8%) when armed, so the exit limit rises
  toward the month's high and the position is sold **earlier** into stress. (A pre-run
  correction: the draft said "added to the trail"; adding to the giveback loosens the
  trail and would worsen drawdown — tightening means a smaller giveback. Fixed before any
  run; the semantics were always "protection = exit earlier".) The stop (8% below entry),
  the DMA/delivery streaks, GSM/ASM forced
  exits, and clause order (stop first) are untouched. **Entries are never touched** — no
  cash gate, no replacement suppression: that is precisely the monthly gate E008a
  rejected, and §8's grammar is monthly entries. Trigger-B sells fill T+1 through the
  normal engine path; a breadth-tightened exit is logged with a note naming the
  breadth state (the evaluator counts these as gate fires).
- **Alternatives considered and killed now:** suppressing new entries (the rejected
  monthly gate's mistake); tightening the hard stop (a risk jump, not a trail — and it
  double-punishes the same price level the stop already covers); continuous
  trail-scaling by breadth (an unbounded tunable surface; one declared step keeps the
  only free parameter the pre-registered threshold family).
- **Threshold family {30, 40, 50} and tighten = 4.0 pp are fixed now.** The 4 pp step
  (~⅓ of the base trail) is declared before any run; if the family fails at 4 pp the
  idea dies — it is not rescued by post-hoc tuning of the delta.

## Arms and windows (fixed before the run)

Arms: `off` (baseline) plus threshold ∈ {30, 40, 50} × cadence ∈ {daily, weekly} = **7
arms**, identical except the two midmonth keys. Windows (validation slice only, boundary
2023-09-24 — the test window is untouched):

- **W0 calm control** — decision months 2017-06, 2017-07, 2017-08. The gate must **never
  fire** here; gate-arm curves must equal the baseline curve exactly.
- **W1 midcap stress bleed** — 2018-09, 2018-10, 2018-11 (breadth 30.7% → 28.8%; a slow
  drawdown, not a waterfall — the hard case for a trail gate).
- **W2 crash + rebound** — 2020-02, 2020-03, 2020-04. February is the **false-fire
  probe** (breadth still elevated; any gate exit there is pure cost), March the crash
  (the gate's target), April the rebound (the cost side: an exited slot re-enters only
  at the April month-end, fills in May — the missed bounce is paid inside the window).

First month of each window is the setup month (initial selection at its month-end);
positions live in the later months. Metrics per arm per window: total return, **max
drawdown on daily session marks**, gate-fire count, trail-exit count, worst session.

## Pre-registered decision rule (written before the run)

- **PASS** iff, on the daily-cadence arms: (a) max drawdown is **strictly lower than
  baseline in both W1 and W2**; (b) end-of-window equity is **≥ baseline in both W1 and
  W2** (protection that sells into the rebound pays for itself or it is not protection);
  (c) W0 is **decision-identical to baseline** (no false fires); (d) at least one gate
  fire occurs in W1 or W2 (a gate that never fires is untested, not benign). Weekly-cadence
  arms are reported beside; if only weekly passes, the conclusion says so.
- **PASS** → the key is promoted to an experiment-backed candidate, **default stays OFF**,
  the 6.1 harness is the final judge (walk-forward §10, 6.4).
- **FAIL or MIXED** (any of a–d unmet) → no wiring anywhere; the intra-month gate is
  closed with evidence, exactly as the monthly gate was; `market_breadth_daily` remains a
  §11 per-regime reporting input.
- Anything ambiguous → no wiring, recorded as inconclusive. This file may not be edited
  after the run (BRD §12).
