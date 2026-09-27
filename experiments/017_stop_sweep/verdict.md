# E017 verdict — REJECTED per the pre-registered bar (missed by 0.66pp); but the sweep produced the first positive-CAGR engine arms ever measured

Run 2026-09-27, profile `full`, 145-month validation slice (2011-07-29 → 2023-07-31,
boundary 2023-09-24), test window untouched. `results.json` is the record;
`hypothesis.md` was written before the run and is not edited. One pre-run disclosure:
G3's original strict monotonicity (A < D1 < D2) was replaced BEFORE the full run by a
directional rule (T1 > A, D5 < A) when the pilot showed the shipped widths bind rarely and
most trigger_b sells come from the DMA/delivery clauses the sweep does not touch; the
replacement and its reason are recorded in `results.json` `guards.G3_note` (the E013/E014
disclosure convention). The G3 directional rule passed: T1 576 > A 486 > D5 475.

> **Index-equivalent:** over this slice the same capital in Nifty 500 TRI compounds at
> **+13.17% CAGR** — the best engine arm in the program's history (D2, below) still trails
> buy-and-hold by ~12.3pp/yr.

## Guards — all passed

- **G1** arm A json-equal to E016's committed `arms.A` (which is E014's baseline; the chain
  is bit-for-bit back to the committed record).
- **G2** tape pins: arm-convention picks 5,605 ≥ 4,579; eligible 161,942; mean monthly IC
  0.0720292285 == the repaired-tape pin to 1e-9.
- **G3** (as disclosed above) T1 576 > A 486 > D5 475 trigger_b sells.
- **G4** stop/trail counts zero where required (D3: 0 stop sells; D4: 0 trail sells; D5:
  both 0) and GSM machinery intact in every arm.

## The numbers

| arm | equity | total | CAGR | Sharpe | maxDD | fills | stop/trail sells |
|---|---|---|---|---|---|---|---|
| A shipped 0.08/0.12 | 942,030 | −5.80% | −0.50% | 0.090 | −65.58% | 983 | 116/65 |
| D1 WIDE 2x | 1,061,242 | +6.12% | +0.50% | 0.138 | −63.34% | 965 | 50/8 |
| **D2 VERY_WIDE 4x** | **1,105,731** | **+10.57%** | **+0.84%** | **0.153** | **−63.34%** | 963 | 19/1 |
| D3 STOP_ONLY_OFF | 942,030 | −5.80% | −0.50% | 0.090 | −65.58% | 983 | 0/163 |
| D4 TRAIL_ONLY_OFF | 998,952 | −0.10% | −0.01% | 0.112 | −64.85% | 971 | 115/0 |
| D5 BOTH_OFF | 1,101,316 | +10.13% | +0.81% | 0.152 | −63.54% | 961 | 0/0 |
| T1 TIGHT 0.5x | 927,798 | −7.22% | −0.62% | 0.073 | −63.91% | 1,157 | 211/282 |

## Bars (pre-registered)

- **B1** an arm reaches CAGR ≥ A + 2.0pp (≥ +1.50%): **FAIL for every arm** — D2's +0.84%
  misses by 0.66pp; D5 (+0.81%) misses by 0.69pp.
- **B2** maxDD not worse by >5pp: every arm passes (wider stops IMPROVE drawdown).

**Decision: REJECTED** — no arm clears B1+B2. The stop/trail family is not adopted, and
per the pre-registration the remaining cost lever is the cost model itself.

## What this actually taught (the real result of the day)

1. **The whipsaw decomposition is clean and monotone.** Tighter stops lose (T1 −0.12pp vs
   A), shipped loses (−0.50%), wider wins (D1 +0.50%, D2 +0.84%, D5 +0.81%). The shipped
   8%/12% widths were selling positions that went on to recover — the "stops are alpha"
   hypothesis is falsified in this signal, and the falsification arm behaved exactly as
   the whipsaw story predicts.
2. **The stop is the whole effect; the trail is noise-plus.** D3 (stop off, trail kept)
   equals A to the last fill — the stop's 116 sells were perfectly replaced by 163 trail
   sells. D4 (trail off, stop kept) is worth +0.49pp. So of the +1.31pp total from D2→A,
   essentially all comes from stopping the stop-whipsaw, and the trail contributes little
   once the stop is off (D5 ≈ D2).
3. **First positive-CAGR engine arms ever measured** — D1, D2, D5, with Sharpe 0.138–0.153
   and IMPROVED maxDD (−63.3% vs −65.6%). All still lose to the index by ~12.3pp/yr.
4. **The cost-drag arithmetic now closes.** Fills barely moved (983 → 963) across the whole
   sweep: the gain is not from trading less, it is from trading the SAME amount while not
   realizing losses at the local low. Combined with E016 (review sells were alpha) and the
   break-even arithmetic (edge survives long holds), the engine's deficit vs its own picks
   is now attributed: whipsaw losses + cost model, not review churn, not slot count, not
   benchmark timing, not sizing.
5. **What adoption would require** (not done — B1 failed): re-deriving E012's floor at the
   changed turnover, a drawdown check on the wider-loss tail (maxDD improved here, but the
   per-trade loss distribution widens), and the decision whether +0.84% CAGR at Sharpe
   0.153 is worth shipping when the index alternative pays +13.17%.

**Consequences:** no config change, nothing promoted; the sweep's arms are config-only and
reproducible. The family is closed per the pre-registration. The recorded next lever is the
cost model: E010's sweep measured the modeled 0.5%/side; real-world delivery costs
(~0.1–0.2%/side) are the one input no experiment has yet varied honestly.
