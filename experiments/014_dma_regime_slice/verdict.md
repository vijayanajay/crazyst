# E014 verdict — REJECTED: the signal does not mark bad months, and E013's gain was exposure, not timing

> **Index-equivalent (added 2026-09-27):** over this experiment's identical 145-month slice,
> the same capital in Nifty 500 TRI compounds at **+13.17% CAGR** (`results.json`
> `arms.*.benchmark_cagr`) — every arm in this verdict, including the best one (BUY_BLOCK,
> +0.86% CAGR), loses to the index by ~12pp/yr.

Run: `python -m experiments.014_dma_regime_slice.run --profile full` (175.1 s);
`results.json` committed. `hypothesis.md` was written before the run. No config, model,
portfolio, engine or harness change (the inert `regime_off` hook is E013's; the arms just
use it), and the test window was not touched.

## Guards (passed)

- The 12-month pass on the smoke's own convention and inputs (labeled-only rows, warm=0)
  reproduces the committed `runs/smoke_e2e/smoke_results.json` escalate arm **bit-for-bit**
  (curve / fill_log / decisions / month_rows).
- Eligible rows 161,942 == E012's chain pin; mean monthly IC 0.0717179780 == E012's
  0.375-arm IC (1e-9); the arm convention (the harness's: selection from ALL decision-date
  eligible rows) picks 5,605 ≥ the labeled-only pin 4,579; every warmed fold's DMA
  recomputed in Python, max diff 1.1e-11 over 142 folds. *(Historical note, 2026-09-27:
  the adj_close pipeline repair moved the repaired-tape IC to 0.0720292285 — LEDGER's
  adj_close-repair row — and the runner's IC pin was re-baselined to it the same day; this
  verdict records the pre-repair run as it happened. The other pins were unaffected.)*

## Arms (145 months, 2011-07-29 → 2023-07-31; the test window excluded)

| arm | final equity | total | CAGR | Sharpe | maxDD | fills | picks | churn/mo | regime sells |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 942,030 | −5.80% | −0.50% | 0.090 | −65.58% | 983 | 529 | 3.32 | 0 |
| BUY_BLOCK | 1,108,821 | +10.88% | +0.86% | 0.138 | −46.51% | 674 | 367 | 2.22 | 0 |
| CASH (diagnostic) | 1,101,496 | +10.15% | +0.81% | 0.131 | −42.11% | 690 | 384 | 2.06 | 31 |

Signal: risk-off in 35 of 145 folds (first warmed 2011-10-31; the three folds before it are
risk-on by warm-up — a filter with no history cannot fire).

## Verdict: REJECTED (both sign readings)

- **B1 (intended: gate helps ⇔ the baseline is worse in gated intervals, mean d < 0,
  one-sided p < 0.05):** mean d = **+0.542%** — the *wrong direction*; p(gate helps) =
  0.654. The baseline's monthly engine return in the gate's own 35 intervals was
  **+0.754%** (sd 8.26%) versus **−0.026%** (sd 5.50%) in the 109 intervals it left alone:
  risk-off marks *volatile* months, not losing ones.
- **B2 (episodes):** 3 of the 5 counted episodes favor the gate, 4 required. Favored:
  2013_taper (−0.20 pp/interval), 2020_covid (−2.63), 2022_rates (−2.23). Against:
  2011_euro (+6.39 — the arm lost 7.2% while the baseline gained 12.0% over that episode's
  gated intervals) and 2015_16_china (+1.36). 2018_ilfs (2 gated intervals, not counted)
  is also against (+1.56).
- **Disclosure (sign slip, second of its kind):** the hypothesis's parenthetical
  "positive = the baseline did worse" is arithmetically inverted for d = base − arm
  (negative d means the baseline's return was lower). Both readings were evaluated; the
  literal reading also reads REJECTED. Nothing hinges on the slip; `results.json` records
  `bars`, `bars_as_coded` and the disclosure.

## Why the equity column looks positive anyway (the important part)

The arm's whole-slice advantage — +17.7% relative equity, maxDD 65.6% → 46.5% — comes from
the **ungated** intervals (placebo d = −0.212%/month over 109: the arm holds a different,
later, thinner book after every gated episode) plus the arithmetic of exposure on this
tape: the baseline's monthly arithmetic mean is **+0.164%** with **6.29%** sd, so variance
drag (≈ sd²/2 = 0.198%) exceeds the mean and its geometric return is **−0.041%/month**;
the arm's sd is 4.83% (drag 0.117%). On a tape where the engine's own drag dominates, *any*
exposure reduction improves the geometric path — signal or not. This is exactly the
mechanism behind E013's +4.8 pp test-window PASS: that result is better explained as the
same exposure/path artifact (its 8 gated intervals were also the baseline's *better*
intervals), not as timing alpha.

So the pre-registered premise is refuted on both of its legs — no systematic
"risk-off months are the engine's losing months" effect, and no episode consistency — which
is a stronger and more useful finding than the slice's equity column. It is also consistent
with the ledger's three prior rejections (P4.1's overlay, E008a's monthly breadth gate —
"troughs mark rebounds" — and E008b's intra-month gate).

## Consequences (as pre-registered)

- **REJECTED closes the index leg.** The BRD §15 risk row's E013 amendment is extended with
  these numbers; the LEDGER gets this block. No config/harness change and no further
  out-of-sample spend on this rule family.
- The reusable machinery stays inert: `regime_off` / `regime_liquidate` on
  `smoke_e2e._engine_pass`, and the E014 signal sampler (with its explicit warm-up rule and
  the two special-session folds — 2015-02-28, 2016-10-30 — where the sourced index's own
  month-end marks disagree with the equity calendar).
- For any future exposure work, the lesson is in the numbers: on this tape the strategy's
  own variance drag, not the market regime, is what a filter would have to beat.
