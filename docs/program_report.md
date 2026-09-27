# Program report — the full arc, E000 → E025, and the standing recommendation

2026-09-27. This is the program's capstone: what was asked, what was measured, what was
learned, and why the standing deploy recommendation is **pure indexing** (Nifty 500 TRI).
Every claim carries its evidence pointer — the LEDGER row, the experiment's
`results.json`/`verdict.md`, or a committed pin. The data dictionary and pin map live in
`docs/data_dictionary.md`; the protocol for any future work is `docs/prospective_protocol.md`.

## 1. The question

The BRD's goal was an automated monthly-rebalance India equity strategy built on a
cross-sectional signal, with an out-of-sample test window held in reserve (BRD §10) and
every experiment pre-registered before its run (BRD §12). The program asked one question in
three layers: **is there a measurable, deployable edge over the index — at paper level, at
deployable mechanics, and out of sample?**

## 2. What was measured, in order

| layer | experiments | verdicts |
|---|---|---|
| Signal discovery | E001/E002/E002b (feature anatomy + IC sweeps) | mom_12m_1m (+0.052 IC) and delivery_pct (+0.049) confirmed at 15y; atr_ratio regime-flipping; volume/candle families dead |
| Model | P4.1, P4.1b, P4.2 | composite_2f ships (beats best single, p 0.014); 3f and learned ranker rejected |
| Universe & costs | E000, E006–E010, E012 | top-1500 stands; 0.5%/side grounded as flat ~0.35% + impact ~0.14%; E009's unenterable-picks finding fixed by the derived 0.375cr floor |
| Engine | E011 | 8 slots adopted: the −51% harness loss was CONCENTRATION, not selection (−10.7% after) |
| Regimes & sizing | E013–E015, E017 | index gate, exposure sizing, per-name stops all rejected — timing knobs mistime; stops whipsaw (~1.3pp) |
| Breadth book | E018–E021 | +29.64% paper CAGR is real in-sample; deployable mechanics double maxDD to −47%; the 90/10 blend passes in-sample (+15.33%); the book-level gate costs 16pp |
| Out-of-sample | E020-C | **NON-CONFIRMED**: +12.59% vs index +12.46% over the 35 virgin months — no deployable edge |
| Closure forensics | E022–E025 | the edge is an UP-month edge (down-months ~0; 2018–20 = 7% of it); 3f composite significantly worse; atr tilt toothless; inclusion flows absent at monthly horizon |

Full rows: `LEDGER.md` (one per experiment, with the pre-registered prediction). The two
adopted changes in production config are E011's `n_slots: 8` and E009/E012's
`min_median_turnover_cr: 0.375` — both derived, neither tuned.

## 3. The three numbers that answer the question

1. **+29.64% / −23.05%** (E018): the idealized breadth book on the 145-month slice — the
   signal is real in-sample.
2. **+25.77% / −47.02%** (E019) and **+15.33% / −31.13%** (E020): deployable mechanics and
   the risk-priced blend — the edge survives costs, but its risk is structural (E021:
   gating costs 16pp; E022: the maxDD is beta, not alpha).
3. **+12.59% vs +12.46%** (E020-C): the frozen design on virgin months. The +0.13pp
   residual is not an edge; E022 shows the in-sample edge lives in up-months (+2.40%/mo,
   t 4.14) and the test window's up-months carried +0.83% (t 1.01, n 13) — decay and
   sampling noise are indistinguishable, and neither is deployable.

## 4. What the program actually built (the part that survives)

A trustworthy research factory: PIT-correct feature/matrix chain with as-of eligibility;
the walk-forward harness with no-peek asserts, realized-slippage accounting and sourced
TRI benchmarks; the pre-registration discipline (frozen hypotheses, guards tied to
committed pins — IC 0.07202922854484578, index equivalents, pick counts 4,579/5,605,
benchmark CAGR 0.12457495616414915 — every one reproduced to 1e-9 across experiments);
repair forensics (adj_close coverage, tape supersessions); and now the prospective
protocol (`src/prospective/score.py`), which makes the next design out-of-sample by
construction. Nothing in the factory depends on the failed signal.

## 5. Why pure indexing is the honest endpoint

- The only construction that ever beat the index in-sample does not out of sample, and the
  failure is explained (E022): the alpha is regime-concentrated where no mechanism can
  harvest it — stops, gates, sizing, blends and conditioning each measured and rejected.
- Every alternative signal family measured (momentum variants, delivery dynamics,
  volatility conditioning, learned rankers, inclusion flows) is rejected at its own
  pre-registered bar, most of them significantly.
- The index itself earned +13.17% (validation slice) and +12.46% (test window) with less
  drawdown than every deployable breadth configuration measured.

This is not "the project failed"; it is the project *succeeding at its own protocol*: 25
pre-registered questions asked, every one answered with a pinned number, and the answer to
the deployment question is no. The recommendation stands until a design passes the
prospective protocol — the one evaluation path that is still virgin.

## 6. What would change the recommendation

1. **A prospective PASS** (docs/prospective_protocol.md): a new family, frozen now, judged
   on ≥ 12 virgin monthly folds. Expected timeline: 1–3 years for a decisive read at the
   effect sizes worth detecting — that is the honest price of the burnt window.
2. **New information, not new mechanics:** a fundamentals/vendor tranche (accruals,
   promoter holding, quality) — the one domain with zero coverage today. Distinct
   engineering effort, gated through the same factory.
3. Nothing else. Re-running closed families on the same history is prohibited by their
   own pre-registrations, and the record explains why each closure is final.
