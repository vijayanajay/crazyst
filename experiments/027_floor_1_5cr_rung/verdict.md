# E027 verdict — the ₹40L rung REJECTED: the gate can be fixed at ₹40L, but only by a floor that costs more than it saves

Run AFTER `hypothesis.md` (pre-registered 2026-10-02, run 2026-10-03; full profile, git
`5f4ed50`, cutoff **2026-10-01**, 325.9s). E009/E012's machinery imported
module-to-module; nothing ships; the shipped floor stays 0.375.

## The measurement (arms at the ₹40L slot, S = ₹500k, gate boundary 1.0 cr)

| arm | floor | eligible rows | refused @S500k | corrected mean | gross mean (no gate) | IC (145m) | impact |
|---|---|---|---|---|---|---|---|
| B (shipped) | 0.375 | 163,280 | **25.39%** (1,750/6,892) | **+2.633%** | +2.659% | 0.072045 | 0.316% |
| C (E009 R2 rung) | 0.75 | 145,397 | 12.66% (785/6,201) | +2.646% | +2.608% | 0.067751 | 0.213% |
| **A (candidate)** | **1.5** | 124,209 | **1.80%** (96/5,338) | **+2.457%** | +2.383% | 0.065098 | 0.122% |
| O (overshoot) | 3.0 | 99,660 | 0.12% (5/4,317) | +2.493% | +2.479% | 0.065210 | 0.065% |

Every arm is a real `E007._build_chain` rebuild at its own floor; the chain was restored
to the shipped 0.375 afterwards and the slice IC re-asserted.

## Guards (all green)

- **G0 anchors** — arm B on the exact 145-fold subset (val folds ≤ 2023-07-31)
  reproduces top-5% picks **4,579**, arm-convention picks **5,605**, and slice IC
  `0.07204549587457933` == `smoke.SLICE_IC_PIN` to 1e-9. Same fold set, same assertion
  E026 certified this session; 146 val folds recorded (the disclosed split drift).
- **G1 coverage** — A keeps 76.1% of B's eligible symbol-months (≥60% bar). No
  degenerate-universe escape hatch; the IC bars ride a real universe.
- **G2 (PIT)** — `excluded_turnover` rises monotonically with the floor
  (137,248 → 165,641 → 194,291 → 223,019), and the amended structural identity holds in
  all four arms at all four slots.
- **G3 continuity** — C at S250k refuses **1.451%** against E009 R2's committed
  **1.467%** (−1.6bp) with corrected mean **+2.571%** vs **+2.614%** (−4.3bp). The
  machinery is the same machine on a slightly newer tape: the continuity tripwire
  passes comfortably.
- **Restore** — final rebuild at 0.375, IC == pin again.

## Bars (frozen, evaluated mechanically)

| bar | requirement | measured | verdict |
|---|---|---|---|
| T1 | A's corrected mean ≥ B's − 5bp/mo | +2.457% vs +2.633% = **−17.6bp** | **FAIL** |
| T2 | paired t(A − B) ≥ −2 | **−1.81** (n = 146 months, mean diff −0.0069, p = 0.073) | PASS (barely) |
| T3 | A's refusal ≤ ⅓ of B's | 1.80% vs 25.39%/3 = 8.46% | PASS |
| T4 (recorded) | refusal ≤ 5% | 1.80% | recorded |

**DECISION: NOT ADOPT.** T1 fails by 12.6bp beyond its tolerance, so the ₹40L rung
stays unsupported and the capacity note's ₹20L ceiling stands — now as a *measured*
conclusion rather than an extrapolation.

## Why it fails — the honest decomposition

The gate problem at ₹40L is **solvable, and solving it is not what fails**. At floor
1.5cr the refusal collapses 25.39% → 1.80% (T3 clears by 6.7×) and modelled impact falls
0.316% → 0.122%. What pays for it is the universe itself:

- Floor 1.5cr removes 24% of B's eligible symbol-months (163,280 → 124,209) and cuts
  the **gross** mean pick return −27.6bp/month (+2.659% → +2.383%) *before any gate is
  applied*. That is the price of the floor, and it is 5× larger than the gate's damage.
- The gate interaction partly offsets it, by differently-sized amounts: at S500k the
  shipped arm's refusals were roughly return-neutral (refused share 25.39% carried
  26.11% of the return mass, so dropping them cost only 2.6bp), while A's few refusals
  were losers (refused return mass **−1.26%**, so dropping them *gained* 7.4bp). Net:
  −27.6bp of universe, +4.8bp of gate interaction, = the measured **−17.6bp**.
- T1's 5bp tolerance was not a near miss by construction; it is a near miss on a gap
  that is mostly a real, measured universe effect.

**The slot-robustness check (recorded, not a bar).** The corrected mean is not monotone
in S inside an arm — B wobbles 2.461%–2.646% across the four slots — so a single-slot
verdict deserves the same number computed at all four:

| slot | B corrected | A corrected | gap |
|---|---|---|---|
| S125k | +2.645% | +2.397% | −24.8bp |
| S250k | +2.522% | +2.403% | −11.9bp |
| S500k | +2.633% | +2.457% | −17.6bp (headline) |
| S1000k | +2.461% | +2.309% | −15.1bp |

The *magnitude* is slot-sensitive (as noisy quantities should be), but the **sign is
negative at all four slots**. The NO-ADOPT reading does not depend on the headline slot
choice.

**T2 is not comfort.** t = −1.81 clears −2 by 0.19 of a t-unit, on p = 0.073 over 146
months. Read plainly: the IC loss from floor 1.5cr is borderline-significant at this
sample size — the rung is not "statistically intact" the way the 0.75cr rung was
(E009 R2: t −0.12, p 0.91). If the next tape adds a few months against the floor, T2
would fail too, and T1's verdict would not change.

**Where the damage stops (diagnostic arm O).** IC falls 0.072045 → 0.065098 across
0.375 → 1.5cr and then **flattens** (0.065210 at 3.0cr), and the corrected mean ticks
back up (+2.457% → +2.493%). The ranking quality is lost in the 0.375 → 1.5 step, not
gradually; past 1.5cr the floor buys almost no further IC, only breadth. Any future
floor work should treat 0.375–1.5cr as the single decision and everything above it as
breadth-vs-nothing.

## Disclosure — two runner defects, caught before any result was written

Both were found by the run refusing to complete, and both are recorded here because
neither moved a measured number:

1. **The arm-convention anchor used the wrong fetch.** `smoke._fetch` filters
   `next_month_ret IS NOT NULL`, which silently collapsed the arm pin onto the
   labeled-only count (4,579 instead of 5,605). The arm convention is select-then-label,
   so its cross-section needs the unlabeled decision rows — E014's definition, fetched
   via `HARNESS._fetch`. Fixed in the anchor block; the pins then reproduced exactly.
2. **The frozen G2 identity was definitionally wrong.** It read
   `refused + fillable + missing_liq20 == picks`, but `_reachability` counts `picks` as
   `len(all_rets)`, which already excludes the missing rows — the identity double-counts
   `missing` by exactly 33 (arm B) and cannot hold. E009's own committed artifact says
   so at every slot (R1: 8,802 picks / 99 missing at all four). `hypothesis.md` carries a
   dated **AMENDMENT 2026-10-03** recording the measured decomposition and the corrected
   identity (`refused + fillable == picks` and `picks + missing == labeled pick rows`,
   with `fillable` recounted independently in E027). No arm, slot, bar, or decision rule
   changed; the corrected identity is strictly stronger — it partitions the whole labeled
   pick set instead of three numbers that were never a partition.

`--self-check` pins the decision rule itself: T1/T2/T3 boundary inclusivity, T4 recorded
and never gating, the G1 floor, and the anchor veto.

## Consequences

1. **No config change.** The shipped floor stays 0.375cr; nothing downstream is
   re-validated because nothing was adopted.
2. `docs/capacity_note.md` gains its measured ₹40L cell and loses the "unmeasured"
   caveat for that rung.
3. The ₹80L rung (boundary 2.0cr, floor 3.0cr) is **still** unmeasured as a floor+slot
   pair. Arm O shows the floor-3.0cr universe is mechanically clean at S500k
   (0.12% refusal) and, per the flattening above, would not be buying IC back — but that
   is an extrapolation from the wrong slot and does not constitute a rung.

**One-line answer: at ₹40L the fill gate is not the binding constraint — the floor that
would fix it is, costing 17.6bp/month of corrected pick return (−2.1%/yr) and a
borderline-significant IC loss, for a 1.80% refusal rate that was never worth that much.
The measured ceiling stays ₹20 lakh.**