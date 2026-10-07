# E027 — the floor-1.5cr rung: extending the capacity ladder to the ₹40L account (E012 protocol, pre-registered)

Pre-registered 2026-10-02, **before the run** (BRD §12). Arms, floor values, slot,
guards, bars and decision rule below are frozen; the runner is implemented after this
file exists; verdict beside the runner as verdict.md.

## Question (from the capacity note's open row)

docs/capacity_note.md derived: at an ₹40L account (8 slots × ₹500k), the fill-gate
boundary is 1.0cr and E012's floor rule requires **floor = 1.5 cr** — a rung nobody has
measured. E009 measured 0.75, E012 measured 0.375/0.5/0.75 at 8-slot economics; and
both committed runs ran on the 2026-09-24 tape (cut-off era: slice 145 folds). This
experiment measures the 1.5cr rung **through the real pipeline** (real chain rebuilds,
not SQL slices) at the ₹500k slot, with the shipped 0.375 floor as the on-tape
reference arm, and reports the diagnostic 3.0cr (E012's own "floor ≥ gate" overshoot)
and the 0.75 (E009 R2 continuity) arms.

## Slot economics (frozen)

8 slots (E011), per-slot notional **S = ₹500,000** (cap tested: ₹40L), fill-gate
boundary `20 × S = 1.0 cr`, floor rule floor ≥ 1.5 × boundary → **1.5 cr is the
derived minimum floor for this account**. Reachability is additionally reported at
E009's full slot grid (125k/250k/500k/1M) per arm for cross-run continuity.

## Arms (frozen; each a real `E007._build_chain` rebuild, floors passed EXPLICITLY)

- **B floor 0.375** — the shipped floor, the on-tape reference (its own committed
  numbers live on the 2026-09-24 tape and cannot be asserted bit-exact today; see
  anchors).
- **A floor 1.5** — the candidate rung.
- **O floor 3.0** — diagnostic overshoot (2× the required floor; how fast IC/eligibles
  decay once the floor outruns the gate).
- **C floor 0.75** — E009 R2's floor, at S250k AND S500k, for continuity with E009's
  committed R2 row (measured and diff-disclosed, not asserted bit-exact — the tape
  moved under both runs; see anchors).

Order: B, C, A, O. Restore step after the arms: config floor returned to 0.375 and the
shipped chain rebuilt; the light-pass slice IC must equal `smoke.SLICE_IC_PIN` to 1e-9
(the zero-drift restore, E009's convention — the restore here must return the chain to
the exact state E026 pinned this session).

## Anchors at the current tape (frozen; replaces E012's bit-equality guards, with cause)

E012's baseline guard asserted bit-equality with E009's committed R1_by_slot. Those
committed numbers were computed at cutoff 2026-09-24 on a 145-fold slice; the 2026-10-01
refresh (labels revised retroactively — E026's disclosed re-baseline) and the tape's
own advancement (146 val folds; 2026-09 decision month labeled) make exact equality
unreachable on the current tape. Anchors certifiable TODAY, via E026's same-session
certification:

- **B-arm selection pins** on the exact 145-fold subset (val folds ≤ 2023-07-31):
  labeled top-5% picks == 4,579 and arm-convention picks == 5,605 (the same assertion
  E026 reproduced bit-for-bit this session — certifies E027's fetch/score/set-selection
  machinery is running the certified tape).
- **B-arm slice IC** == `smoke.SLICE_IC_PIN` to 1e-9 on the exact 145-fold subset
  (val folds ≤ 2023-07-31) — the same fold set and assertion E026's G2 certified this
  session (the pin is defined on that slice; the current val slice is 146 folds and is
  recorded, not pinned).
- **Structural guard:** every arm's `refused + fillable + missing_liq20 == picks` per
  slot, and refused shares are monotone non-decreasing in S within each arm (the
  arithmetic identity E009's tables satisfy).
- **Continuity (recorded, not asserted):** each arm's refusal/corrected-mean at S125k
  next to E012's committed table, diff disclosed in results.json.

## Guards (frozen; all must pass for the run to count)

- **G0** anchors above pass on arm B.
- **G1 (coverage class):** A's eligible count does not collapse mid-rung: eligible
  symbol-months at floor 1.5 remain ≥ 60% of B's (E009's 0.75 rung kept ~66%; a worse
  collapse is a finding, not an error, but the IC bars would then ride a degenerate
  universe, so it fails the run instead of being interpreted).
- **G2 (PIT):** A's and O's eligibility reasons respect the floor's as-of membership
  (arm builds go through the real chain; assert per-arm excluded_turnover counts
  increase monotonically with the floor).
- **G3 (machinery identity):** C's S250k refusals ≤ 5% and its corrected mean is within
  3pp/mo absolute of E009 R2's committed +2.614% (a coarse continuity tripwire — the
  tape moved, the mechanism did not).
- **Restore:** final rebuild at 0.375 asserts IC == smoke.SLICE_IC_PIN (1e-9) again.

## Bars (frozen; the E012 rule applied to the new rung)

Paired monthly t (P41._paired_t) of A's monthly IC series vs B's on common val months:

- **T1:** mean corrected pick return of A (at S500k) ≥ B's − 5bp/month
  (`TOL_CORRECTED = 0.0005`, E012 verbatim);
- **T2:** paired t(A − B) ≥ −2 (IC holds; E009/E012 verbatim);
- **T3:** A's refusal share at S500k ≤ 1/3 of the B-universe's refusal at S500k
  (the floor must fix the gate boundary it's sized for; E009 verbatim);
- **T4 (recorded, not gating):** refusal at S500k ≤ 5% (the loose definition of "the
  gate stops binding"); impact at S500k reported (E010's min(0.01, 0.10·S/med20)).

## Decision rule (frozen)

ADOPT floor 1.5 (i.e., record that an ₹40L account is supportable ONLY with this floor
and only on these numbers) iff T1 ∧ T2 ∧ T3 hold for A vs B and all guards pass.
Otherwise the ₹40L rung stays UNMEASURED-REJECTED: the capacity note's "no evidence
above ₹20L" conclusion stands, with this run as the evidence that the rung was tried.
Either way the note gains its measured cell; the shipped config (0.375) changes ONLY on
ADOPT, and the E012-style re-validation of everything downstream that adopting implies
is pre-declared here: adoption alone does not ship anything.

Disclosures rule: any deviation between coded bars and these words is recorded in
results.json (`bars`, `bars_as_coded`), the E013/E014 way.

## AMENDMENT 2026-10-03 — the G2 identity, corrected (definitional; no bar changes)

Discovered while executing the frozen G2, before any result was written. The words above
say `refused + fillable + missing_liq20 == picks`. That identity **cannot hold against
E009's dict**, and the code must not be bent to make it: `_reachability` counts
`picks` as `len(all_rets)`, and `all_rets` only receives picks that are BOTH labeled and
present in `liq_daily20` — so `picks` already excludes the missing rows and adding
`missing_liq20` double-counts them.

Measured on the live tape at floor 0.375 (arm B, `smoke._fetch` rows), independently
recounted from the raw pick set rather than from E009's own loop:

| slot | `picks` | refused | missing | recounted fillable | `refused + fillable` |
|---|---|---|---|---|---|
| S125k | 6,892 | 78 | 33 | 6,814 | 6,892 = `picks` ✓ |
| S500k | 6,892 | 1,750 | 33 | 5,142 | 6,892 = `picks` ✓ |

and the labeled pick set (6,925 rows, zero NULL forward returns) partitions as
`picks + missing = 6,892 + 33 = 6,925` ✓. E009's **committed** artifact says the same
thing, which is the independent check that this is a wording error and not a tape
effect: R1's four slots all report `picks` 8,802 / missing 99 (`refused + missing ==
picks` is False at every slot), and R2 reports 6,134 / 31.

**The corrected G2, as coded:** for every arm and slot, (a) `refused + fillable ==
picks` and (b) `picks + picks_missing_liq20 == labeled pick rows`, where `fillable` is
recounted in E027 from the raw picks and `liq_daily20` (never read back out of
`_reachability`'s own bookkeeping, which would prove nothing). This is strictly
stronger than the original: it partitions the whole labeled pick set into
refused/fillable/unenterable rather than three numbers that were never a partition.

**Unchanged by this amendment:** the arms and their order (B/C/A/O), the slot grid, the
anchors, G0/G1/G2(PIT)/G3/restore, bars T1–T4, and the decision rule. No number in the
table above enters any bar.
