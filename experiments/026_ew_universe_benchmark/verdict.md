# E026 verdict — the EW universe benchmark, measured

**Kind: REPORTING** (no bars, no adoption; hypothesis.md frozen 2026-10-01 pre-run).
Guards: split amendment as measured (boundary 2023-10-01; val 146 folds, 145-subset
exact; test 35 folds 2023-09-29 → 2026-07-31); IC pin reproduced after the **disclosed
tape re-baseline** (+1.63e-5, selection pins bit-exact: 4,579 / 5,605); Nifty 500 TRI
pin on the 145-subset reproduced to **0.0e+00**; arm-B reproduction diff **3.2e-11**;
zero dropped legs; `python -m ... --self-check` PASS.

## The table

**Validation slice — 145 folds, 2011-07-29 → 2023-07-31** (E018's pinned window):

| leg | CAGR | maxDD | note |
|---|---|---|---|
| EW-ELIGIBLE universe (as-of top-1500, monthly rebal) | **+16.84%** | **−54.82%** | cohort-est +22.25%; min mark-coverage 62.0% (2011) |
| EW-LABELED (the labeled cross-section) | +16.84% | −54.82% | **identical to leg 1 — see finding F2** |
| B DECILE_RANK_W (E018 arm, real costs, reproduced) | **+29.64%** | −23.05% | 133 cohorts |
| Nifty 500 TRI (sourced) | +13.17% | −28.87% | pin diff 0.0e+00 |

**Test window — 35 folds, 2023-09-29 → 2026-07-31** (cutoff-derived; shifted one month
vs E020-C's window, disclosed):

| leg | CAGR | maxDD | note |
|---|---|---|---|
| EW-ELIGIBLE universe | **+14.17%** | −25.75% | cohort-est +6.88% (cohort estimator drops the first 12 of 35 months — warmup, not signal) |
| B DECILE_RANK_W (real costs) | +21.37% | −0.76% | 23 cohorts; post-hoc report on a burnt window |
| Nifty 500 TRI | +12.45% | −17.74% | vs E020-C's committed old-window pin 0.124575: diff −8.3e-5 (window moved, as disclosed) |

## The gaps (the answer to the review's question)

| gap | validation (145) | test (35) |
|---|---|---|
| B − EW-universe (**matched cohort estimator**) | **+7.40 pp/yr** | +14.49 pp/yr |
| B − Nifty 500 TRI (E018's original framing) | +16.47 pp/yr | +8.93 pp/yr |
| EW-universe − TRI (the universe premium) | **+3.67 pp/yr** | +1.73 pp/yr |

## Findings

- **F1 — the cap-weighted denominator was flattering, but not fatally.** The as-of
  top-1500 universe itself earned +3.67 pp/yr more than the Nifty 500 TRI in-sample
  (+16.84% vs +13.17%) and +1.73 pp/yr on the test window. Roughly **22% of E018's
  headline +16.5 pp "edge vs index" was universe beta**, not selection.
- **F2 — the selection edge survives the correct denominator in-sample: +7.40 pp/yr**
  over the matched-estimator EW universe (+29.64% vs +22.25%). The breadth book is not
  explained by holding the universe it trades. Caveat kept visible: this is the burnt
  validation slice; E020-C showed the same family's OOS blend at index-parity vs TRI.
  On E026's test window the book still led its own universe by +14.49 pp/yr (23
  cohorts; −0.76% maxDD) — but that window is burnt by E020-C and is short.
- **F3 — the ride is the argument.** The EW universe's own maxDD over the validation
  slice is **−54.82%** (vs index −28.87%, book −23.05%). "Just hold the universe"
  — the do-nothing alternative the benchmarks imply — was a −55% experience. The
  breadth premium F1/F2 measure is earned on top of a benchmark that is itself a
  violent hold.
- **F4 — legs 1 and 2 coincide by construction (disclosed outcome, not a bug).** The
  labeled set IS the marked subset of the eligible snapshot (labels derive from the
  same adj panel that produces the marks), so the EW mean over marked members is the
  same series to the last float (0.16840436005003845 in both legs). The
  "labeled-coverage filter" question is answered: **all of it** — and it means the EW
  benchmark measured here is already the tradeable book, not an untradeable ideal.
- **F5 — coverage honesty (G5).** 69 of 144 validation months sit below the 80%
  mark-coverage bar (min 62.0% in 2011; thin Yahoo coverage pre-~2016); the test
  window's floor is 93.5%. No month was dropped; the flagged list is in results.json.
  Because unmarked members are exactly the unlabeled rows (F4), low early coverage
  shrinks the measured EW book toward the labeled universe — it does not invent
  returns.

## Reading

The program's historical claim "the book did +29.6% vs the index +13.2%" should be
restated as: **"+29.6% vs +16.8% for the universe it actually trades (monthly
rebalanced, −54.8% maxDD), with +7.4 pp/yr of that gap attributable to the composite's
selection on the matched estimator."** The edge over the right denominator is roughly
half the edge over the old denominator — real, but the easy half was never the
selection. Going forward this EW-universe series is the benchmark the prospective
breadth_book design (registered the same day) is judged against on virgin folds.

## AMENDMENT 2026-10-02 (disclosed; per-year breakdown, same form as the program review)

The runner gained a per-year aggregation (plus one added leg: **B-1mo matched** — the
same decile books at 1-month holds, real costs, i.e. B's selection measured on the EW
benchmark's own accounting). All guards re-verified on the re-run: TRI pin 0.0e+00,
arm-B pin diff 3.2e-11, picks 4,579/5,605 exact, zero dropped legs. The frozen
hypothesis.md is untouched; the new leg and this section are the disclosed amendment.
Conventions: ew/tri compound the year's consecutive fold-pair returns; B-12mo
compounds cohort steps of cohorts ENTERED in the year (E018's proxy convention — so
the last 12 months of each window have structurally empty B-12mo cells, shown 0.00);
gap = growth-factor difference. `*` = partial year.

**Validation slice (2011-07 → 2023-07):**

| year | EW universe | TRI | B 12mo | B 1mo matched | gap (matched) |
|---|---|---|---|---|---|
| 2011* | −12.19% | −7.37% | +16.66% | −0.14% | +12.05 pp |
| 2012 | +16.65% | +18.84% | +14.31% | +17.18% | +0.52 pp |
| 2013 | −6.64% | −0.61% | +49.03% | −17.52% | **−10.88 pp** |
| 2014 | +88.16% | +53.75% | +58.76% | +114.18% | +26.02 pp |
| 2015 | −0.73% | −10.70% | +10.25% | +25.12% | +25.85 pp |
| 2016 | +27.29% | +17.84% | +40.73% | +41.99% | +14.70 pp |
| 2017 | +46.08% | +33.11% | +5.10% | +36.56% | **−9.52 pp** |
| 2018 | −27.53% | −5.95% | −12.78% | −19.88% | +7.64 pp |
| 2019 | +1.30% | +10.83% | +13.28% | +4.58% | +3.28 pp |
| 2020 | +22.84% | +15.82% | +74.18% | +19.61% | −3.23 pp |
| 2021 | +68.21% | +33.44% | +30.29% | +85.65% | +17.44 pp |
| 2022 | +3.13% | +1.28% | +2.80% | −3.16% | −6.28 pp |
| 2023* | +24.57% | +14.83% | (empty) | +29.86% | +5.29 pp |

**Test window (2023-09 → 2026-07):**

| year | EW universe | TRI | B 12mo | B 1mo matched | gap (matched) |
|---|---|---|---|---|---|
| 2023* | +23.22% | +14.72% | +21.18% | +32.78% | +9.56 pp |
| 2024 | +7.26% | +10.06% | +5.25% | +11.72% | +4.46 pp |
| 2025 | −3.12% | +7.98% | +7.98% | +10.42% | +13.55 pp |
| 2026* | +13.71% | +2.27% | (empty) | −3.88% | **−17.59 pp** |

**What the yearly cut adds to the verdict:**

- **F6 — the selection edge is broad-based but cyclical, not uniform:** positive in
  9 of 13 validation years and both full test years (2024 +4.5, 2025 +13.6 pp),
  averaging ≈ +6.1 pp/yr (consistent with the +5.94% matched CAGR gap). The failing
  years — 2013, 2017, 2020 (mildly), 2022, and 2026-YTD — are where the universe
  itself ran hard (2017 +46%, 2021 +68% EW years) or momentum broadened; in 2014 and
  2021 the book rode the same regimes AND beat the universe by +26/+17 pp.
- **F7 — the B-12mo yearly column is an accounting mismatch and must not be read
  alone** (2013 +55.7 vs matched −10.9): cohort arithmetic vs consecutive-pair
  compounding disagree year by year; the matched leg is the honest per-year cell.
- **F8 — 2026-YTD (7 months) shows a −17.6 pp matched gap, the worst cell in the
  table.** It is partial and it is the burnt window's tail — but it is exactly the
  question the breadth_book prospective design (frozen 2026-10-01, first virgin fold
  December 2026) will adjudicate on live data, against this same EW benchmark.
