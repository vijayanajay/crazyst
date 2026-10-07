# Capacity note — the largest account the shipped strategy can actually run

2026-10-01 (₹40L cell measured by **E027**, 2026-10-03 — see `experiments/027_floor_1_5cr_rung/`).
A derivation from **committed results only**: E009's fill-gate measurement, E011's slot
economics, E012's floor adoption, E027's ₹40L rung. The strategy is
currently **not confirmed for deployment** (E020-C NON-CONFIRMED; E026 re-based the
benchmark) — this note is the conditional arithmetic for the day something passes, so
the capacity question is settled before it can be improvised.

## 1. The two constraints, from the committed record

**Fill gate (E009).** The engine refuses a buy when its notional `S` exceeds 5% of the
symbol's trailing-20-session median turnover (`med20`): a pick is enterable iff
`med20 ≥ 20 × S`. E011 fixed `n_slots = 8`, so `S = C/8` for account size `C`, and the
gate boundary is `20 × C/8 = 2.5 × C` rupees = **`C / ₹40 lakh` in crore**:

- C = ₹10L → boundary **0.25 cr** (E012's committed `boundary_8_cr` at slot ₹125k ✓)
- C = ₹20L → **0.5 cr** (E009 R2's boundary at slot ₹250k ✓)

(the two committed boundary values reproduce the formula exactly — this note's one
runnable check, verified against E012/E009 results.json).

**Floor rule (E012).** The universe floor must lead the gate: E012 adopted
`floor = 1.5 × boundary` ("derived, not tuned") — at the shipped ₹10L, floor 0.375 cr.
So the floor a given account REQUIRES is `1.5 × 2.5 × C / 1e7 = 3.75 × C / 1e7` cr.

## 2. Account size vs refused-pick share (the measured table)

E009 R1 measured the gate on the pre-floor universe (top-5% composite picks, 145
months, 8,802 picks); E012 and E009 R2 measured the post-floor points through the real
chain. Refused picks are adversely selected — the gate removes the model's BEST picks
(E009: refused +4.05%/mo vs fillable +2.52% at the 250k boundary) — so the refused
share is a quality tax, not just lost breadth.

| Account C | Slot S = C/8 | Gate boundary | Universe floor required (E012 rule) | Refused-pick share | Corrected mean pick | Source |
|---|---|---|---|---|---|---|
| ₹10L | ₹125k | 0.25 cr | 0.375 cr | **1.14%** (78/6,825) | +2.692%/mo, IC 0.0717 | E012 (measured, shipped) |
| ₹10L | ₹125k | 0.25 cr | — (pre-floor) | 29.36% (2,584/8,802) | +2.669%/mo | E009 R1 |
| **₹20L** | ₹250k | 0.5 cr | **0.75 cr** | **1.47%** (90/6,134) | +2.614%/mo, IC 0.0675 (paired t −0.12, p 0.91) | E009 R2 (measured) |
| ₹20L | ₹250k | 0.5 cr | — (pre-floor) | 38.78% (3,413/8,802) | +2.517%/mo | E009 R1 |
| ₹40L | ₹500k | 1.0 cr | **1.5 cr (measured)** | **1.80%** (96/5,338) | **+2.457%/mo**, IC 0.0651 (paired t −1.81, p 0.073) | **E027 (measured, REJECTED)** |
| ₹40L | ₹500k | 1.0 cr | — (pre-floor) | 25.39% (1,750/6,892) | +2.633%/mo | E027 at floor 0.375 |
| ₹40L | ₹500k | 1.0 cr | — (no floor) | 49.65% (pre-floor, pre-refresh tape) | +2.659%/mo | E009 R1 only |
| ₹80L | ₹1M | 2.0 cr | 3.0 cr (unmeasured) | 61.18% (pre-floor) | +2.565%/mo | E009 R1 only |

Reading the table: **the floor, not the account size, is what buys capacity.** At the
required floor, refusal stays ~1–1.5% from ₹10L to ₹20L; the pre-floor curve (29→61%)
is what happens when the boundary outruns the floor — and E009 showed exactly what
those refusals cost (the best picks leave first). The corrected pick mean barely moves
across the pre-floor grid (2.52–2.67%) because the fillable pool self-selects for
liquidity — but each floor raise that guards the boundary thins the universe (floor
0.75 cr excluded 75.3% of eligible symbol-months, E009 R2) and each doubling of C
demands a doubling of the floor.

**E027 measured that trade at ₹40L and it stops paying.** Floor 1.5 cr does exactly
what it is supposed to — refusal 25.4% → 1.80%, impact 0.316% → 0.122% — but it removes
24% of the eligible universe and cuts the **gross** pick mean by 27.6bp/month before
the gate touches it. The net cost is 17.6bp/month of corrected return (negative at all
four slot sizes, so not a headline-slot artifact) plus a borderline IC loss
(paired t −1.81, p 0.073 — not the statistical intactness the 0.75 cr rung showed).
The ladder therefore stops at ₹20L: the next rung costs more in universe than it saves
in refusals.

## 3. The two unmodeled costs that grow with size

- **Impact beyond the gate.** The 5%-ADV cap is a gate, not a cost model; E010's
  impact decomposition and E011's realized slippage both worsen with slot size: E011
  measured buy-side slippage vs the decision mark **+0.441%/side at 4×₹250k slots vs
  −0.099% at 8×₹125k** — quartering the slot size flipped the sign. Bigger accounts
  re-concentrate per-slot notional and pay for it in execution, on top of the gate.
- **Breadth decay from floor raises.** E026 measured the universe tilt itself at
  +3.7 pp/yr over the index (validation slice) — a premium that lives in the
  small/mid tail each floor raise deletes. The 0.75-cr rung kept IC statistically
  intact (t −0.12); **E027 measured the 1.5-cr rung (₹40L) and it does not**
  (t −1.81, p 0.073, corrected mean −17.6bp/month), which is the second cost item
  turning from projection into measurement.

## 4. Conclusion — the maximum viable account size

- **₹20 lakh (measured ceiling).** The largest account with a measured rung: floor
  0.75 cr, refusal 1.47%, corrected mean +2.61%/mo, IC statistically intact. Reaching
  it requires RE-DERIVING the shipped floor (0.375 → 0.75 cr) through the E012
  protocol — a config change with its own re-validation, not a dial.
- **₹10 lakh (shipped, end-to-end measured).** The only account where every layer is
  measured on the same tape: floor 0.375 cr, refusal 1.14%, corrected mean +2.692%/mo,
  engine realized (E011 A8: ₹892,626 final equity over 35 folds), slippage known
  (−0.099%/side buys).
- **Beyond ₹20 lakh: measured, and rejected (E027).** The ₹40L rung now has a measured
  cell: floor 1.5 cr at S₹500k refuses 1.80% of picks but gives up 17.6bp/month of
  corrected return and a borderline-significant IC, failing the pre-registered T1 bar.
  The ladder stops there. ₹80L remains unmeasured as a floor+slot pair (arm O shows the
  3.0-cr universe is mechanically clean at the *wrong* slot, which is not a rung), and
  anyone proposing ₹80L+ must run the E012 ladder at floor 3.0 cr the same way — before
  the account exists.

**One-line answer: ₹20 lakh is the hard measured ceiling and ₹10 lakh the honest
operating point; at ₹40L the gate is fixable but the fix costs more in universe than it
saves in refusals (E027), and below ₹10L there is nothing to gain (the gate is not
binding).**
