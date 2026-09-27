# Prospective protocol — scoring new designs on virgin folds only

2026-09-27. The program's closure finding (E020-C, E022–E025) is that every in-sample
evaluation path is burnt: the 145-month validation slice is in-sample for 25 experiments,
and the 35-month test window was spent by E020-C. Virgin labeled months accrue as the data
cutoff advances (one per month). This protocol is how a new design earns a verdict **without
touching history again**.

## The rule

A design evaluated here gets **one shot per virgin fold, frozen before the fold exists**:

1. **Freeze before the month arrives.** `docs/prospective/TEMPLATE.md` is copied to
   `docs/prospective/<design>/design.md`, filled in, and committed (or hashed into the
   LEDGER) **before** the fold month closes. Anything added after the fold is a disclosed
   amendment in `results.json`, never an edit.
2. **The fold is scored exactly once.** `python -m src.prospective.score --design <name>`
   finds the newest labeled month that is younger than the design's freeze date, runs the
   design's registered scorer on it, appends one row per month to
   `runs/prospective/<design>/folds.csv`, and never re-scores a month already in the file.
3. **No peeking, enforced mechanically:** the scorer reads only decision-month features and
   the label of the scored month (which the harness itself already treats as PIT); the
   design may not read any file produced after its freeze. The runner records the freeze
   hash and fails if `design.md` changed since registration.
4. **Verdict discipline:** a design's verdict is written when its pre-registered bar is
   **decidable** — after the fold count reaches the n the freeze named (or the bar is
   mathematically unreachable). Early stops are allowed only in the pre-registered
   direction (a clear fail may be called early; a pass needs its full n).
5. **What this protocol is for:** any *new* signal family or mechanism, pre-registered as a
   screen (E025's bar style) or a design (E020's bar style). It is NOT for re-running
   closed families: the breadth, sizing, gating, stop, blend, composite-3f, atr-tilt and
   inclusion-flow closures stand.

## Why monthly folds are enough

The program's measured effects are monthly-scale (IC ~0.05–0.07, book excess ~1pp/mo);
with one fold per month, a two-sided t-test with 80% power at the effect sizes worth
detecting needs roughly 2–4 years — that is the honest cost of having burnt the window,
and it is the same patience the closure findings already imply (a regime-mild window
showed nothing in 35 months).

## Operations

- The monthly job runs **after** the data refresh catches up: chain it behind
  `src.download.scheduler` (it exits 0 when caught up), then run
  `python -m src.prospective.score --all` to score every registered design on the newest
  fold. Idempotent; a fold scored twice is a hard error.
- With no registered designs the job is a no-op that still records the fold marker
  (`runs/prospective/_folds.json`: cutoff month, freeze-line hashes), so the wall between
  burnt and virgin months is auditable from the repo itself.

## Registered designs

None at creation. The next pre-registration (any new family) must either use this protocol
or justify in its hypothesis why it does not.
