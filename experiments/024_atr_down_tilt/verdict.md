# E024 — verdict: REJECTED — the low-ATR tilt is free but toothless

Run 2026-09-27, profile `full`, 145 validation months (test window untouched).
`results.json` is the record; `hypothesis.md` was written before the run.

| arm | down (n=33) | flat (n=49) | up (n=63) | overall excess |
|---|---|---|---|---|
| A baseline (E018/E022 book) | −0.17% | +0.67% | +2.40% | +1.23%/mo |
| B atr tilt (w ∝ 1/rank × (1−pct_atr)) | **+0.09%** | +0.68% | +2.48% | +1.33%/mo |

Paired B − A: **+0.099pp/mo, t = 0.33** over 145 months.

Bars: B1 down ≥ +0.5pp — **FAIL** (+0.09%); B2 up within 1pp of A — PASS (the tilt cost
nothing; it actually added +0.08pp up); B3 paired diff > 0 — PASS (point estimate), t 0.33
is nowhere near significant. Per the frozen rule (B1 ∧ B2 ∧ B3): **REJECTED**.

Guards: G1 arm A's by-band excess equals E022's committed `validation_by_band` to 1e-6
(reproducing its 145-interval chain including the 2023-07→2023-08 boundary interval —
disclosed in results.json); G2 index leg == E019's committed equivalent to 1e-9; G3 zero
mark-unpriceable legs, every tilted book ≥ 25 legs (5 tilt-dropouts across all cohorts are
the frozen construction, counted).

## Reading

The tilt works exactly as E002b's IC table promised — and that is the problem. In
down-months it shifts the book toward names that fall less, moving bucket excess from
−0.17% to +0.09% (+0.26pp) at zero cost to up-months. But a +0.26pp shift is a rounding
error against a −17%-type down month, and the frozen bar asked whether it *fills* the
zero-excess bucket (+0.5pp). It does not. The 94%-consistent cross-sectional IC is ranking
skill among falling names, and a tilt inside an already-long momentum book cannot convert
"falls less" into positive excess when the whole bucket's beta dominates. Making the tilt
stronger means adding a parameter — the overfitting surface the frozen construction
explicitly excluded, and E015/E021's lesson about conditional knobs stands.

## Decision

Per the frozen rule: **REJECTED**. The conditional-volatility direction closes: not
because the tilt harms (it is measurably free), but because it does not clear the bar that
would justify a promotion pre-registration. With E023 closing the composite family, the
audit's remaining direction is **new data** — index-inclusion flows (E025) — not new uses
of the existing panel. The standing deploy recommendation is unchanged: pure indexing.
