# LEDGER — every experiment, its pre-registered prediction, and its verdict (BRD §12)

Predictions are written **before** the experiment runs and may not be edited after (BRD §12).
Verdicts: `confirmed` / `rejected` / `inconclusive`. One row per experiment; a run without a
ledger row is not done. Profile (`quick`/`full`), git hash, and data cutoff are logged in each
experiment's `results.json`.

| # | Experiment | Pre-registered prediction | Verdict | Date |
|---|---|---|---|---|
| E000 | Universe overlap: as-of top-1500 liquidity vs Nifty 200 | Overlap ≥ 80% of Nifty 200 constituents per year; hit rates computed on the two universes differ by < 2pp | **rejected on the letter of the rule** — overlap clause decisively confirmed (min 97.7% / mean 98.7% per year, 15 years); hit-rate trigger fired (mean yearly |Δ| 2.48pp ≥ 2pp) but the fired statistic is noise-bound (yearly binomial noise floor ±1.91pp; pooled |Δ| = 0.86pp, below the bar). No index-membership data needed; universe choice (0.86pp, ~2σ) handed to the BRD owner. See 2026-09-25 E000 block | 2026-09-25 |
| E002b | Full-profile confirmation IC sweep (mean monthly IC, month fixed effects removed) | Momentum features (mom_6m / mom_12m_1m) confirmed at 15 years; volatility-state finding reproduces with a stable sign | **confirmed, with one major reversal** — mom_12m_1m +0.052 (p = 1.1e-6) and mom_6m confirmed; **delivery family CONFIRMED at full history** (delivery_pct +0.049, p = 1.2e-11) — E002's quick rejection was a bull-window artifact; atr_ratio is regime-flipping (+0.045 up / −0.183 down, 94% down-month consistency), so its pre-registered sign holds only in the regime quick never sampled. See 2026-09-25 E002b block | 2026-09-25 |
| E001 | Anatomy of winners: winners differ from rest on momentum/delivery features | Winners' 6–12M momentum and 20-day delivery% z-score distributions sit above the eligible rest (median shift > 0) | **partial** — momentum anatomy confirmed (mom_12m_1m AUC 0.544, +0.050 median shift, 64% per-month consistency); delivery z-score anatomy REJECTED (AUC 0.478, wrong sign — matches E002); strongest separator is volatility state with the LORE-DIRECTION wrong (atr_ratio AUC 0.639 at every month, uniform across size buckets — not a small-cap artifact; momentum vanishes in the 601–1500 bucket, AUC 0.507). See 2026-09-25 block | 2026-09-25 |
| E002 | Univariate IC sweep (all features) | 6–12M momentum and delivery% z-score have positive pooled Spearman IC, surviving BH at α = 0.05 | **partial** — mom_12m_1m confirmed (+0.065, right sign, BH-surviving); delivery z-score REJECTED (−0.010, n.s.); mom_6m wrong sign; volatility-state features dominate (see 2026-09-24 block) | 2026-09-24 |
| P4.1 | Composite v0 (rank-avg of E002b survivors) beats the best single feature on the pre-test-window validation slice (paired monthly t, α = 0.05); atr overlay additive on the same test | **inconclusive** — composite 0.0625 vs best single (mom_12m_1m) 0.0529 mean monthly IC, diff +0.0096 over 145 months, p = 0.0585: point estimate wins, pre-registered bar missed ⇒ **mom_12m_1m ships as v0** (tie ⇒ simpler). Atr overlay REJECTED as an addition (−0.0390, p = 0.0033): the trailing-market regime proxy dilutes, not captures. Overlay's 0.0625-vs-0.0529 gap is the number the 4.2 ranker must justify. See 2026-09-25 P4.1 block | 2026-09-25 |
| P4.1b | Two-feature composite (mom_12m_1m + delivery_pct; P4.1's weakest-vote follow-up) clears the M3 bar vs the slice-selected best single | **confirmed** — 0.0681 vs 0.0529, diff +0.0153 over 145 months, p = 0.0140; 3f control recomputed (0.0625), 2f > 3f +0.0057 (p = 0.196, mom_6m was dead weight, not poison). **composite_2f ships as v0**, superseding P4.1's single-feature ship; precision flip (3f 55.4% > 2f 54.8%) disclosed. See 2026-09-25 P4.1b block | 2026-09-25 |
| P4.2 | Learned ranker (HistGBR, monthly walk-forward refits, all 22 features, fixed hyperparameters) beats composite_2f on the same validation-slice gate; freeze protocol reproduces picks | **rejected** — ranker 0.0402 vs composite_2f 0.0681, paired diff −0.0221 over 120 months, p = 0.0159: a clear loss (all-features rope + squared-error loss grabs noise the two-feature blindness avoids). **composite_2f ships as the Phase 4 model**; freeze protocol passed (bit-identical refits, max|diff| 0.00e+00; top-5% picks reproduce exactly; artifact round-trips). sklearn dependency justified in requirements.txt. See 2026-09-25 P4.2 block | 2026-09-25 |
| E006 | Cost sensitivity: 0.2 / 0.5 / 1.0 % per side | Net edge at 0.2% does not survive 1.0% for picks ranked below ~600 (BRD §9.7) | **rejected** — the >600 tail's edge SURVIVES: 3.34% → 1.74% mean net per pick (52% of base, above the 50% line), the strongest group at every cost level. The uniform-haircut model cannot see impact/non-fill — the fill model (Phase 5) is the open question, not the cost constant. Phase 6 default set to 0.5% per side (edge 82% of base), all three levels reported. See 2026-09-25 E006 block | 2026-09-25 |
| E003 | Bulk/block deal net buying overlay (Phase 7) | Net institutional buying in the prior month adds IC on top of E002 survivors | pending | — |
| E004 | SAST/insider buying overlay (Phase 7) | Insider % acquisitions in the prior quarter add IC on top of E002 survivors | pending | — |
| E005 | F&O OI overlay, optional (Phase 7) | OI build-up with price adds IC on top of E002 survivors | pending | — |
| E007 | Universe cutoff: rolling top-1000 vs top-1500 (BRD-owner question from fixissues_phase36.md) | The cut must BUY cross-sectional signal to justify discarding evidence: B's mean monthly IC higher at paired t ≥ 2 AND engine-pass gate stress materially lower; otherwise keep 1500 | **rejected** — IC 0.0695 vs 0.0681, paired diff +0.0014, t = −0.57, p = 0.57 (noise); precision +1.0pp at −57,226 symbol-months (−26%) of evidence; the below-₹5cr share only falls 62.8% → 50.1% (half the top-1000 still trades under ₹5cr/day — illiquidity is the whole small/mid tail, not a 1001–1500 island); engine pass: −1 non-fill, 0 fewer forced exits, worse churn. **top-1500 stands.** See 2026-09-26 E007 block | 2026-09-26 |
| E008a | Own-data market breadth (as-of top-200, 200-session adj DMA) predicts losing pick-months at monthly decision cadence; threshold family {30/40/50} consistent across adjacent thresholds; ρ ≥ 0.15 | **rejected** — ρ = +0.144 (below bar); NO consistent low-breadth penalty: <30 months are the BEST pick months (+10.70% vs +3.28%, hit 82% vs 54% — troughs mark rebound months); only 40–50 shows a penalty (−1.8pp) with a near-zero universe penalty, inverting at 40 and reversing at 30. Gauge itself validated (stress months read: 2018-09 30.7%, 2020-03 15.5%; a first-run aggregate bug was caught by the member-level sanity layer). **No monthly gate; table kept for §11 per-regime reporting; intra-month breadth is a separate pre-registration.** See 2026-09-26 E008a block | 2026-09-26 |
| E008b | Intra-month breadth protection: daily/weekly breadth (E008a machinery, as-of daily membership) tightens the Trigger-B trail while breadth < {30/40/50}; evaluated on an interim per-session engine pass (3 fixed windows: 2017 calm, 2018 midcap stress, 2020 crash+rebound); PASS = lower max drawdown in both stress windows, equity >= baseline, no W0 fires | **failed** — max drawdown identical to baseline in BOTH stress windows; the only gate fire in the whole experiment (HDFCBANK, 2020-04-15, breadth 24%) lands in the REBOUND and its T+1 fill falls outside the window (equity identical to the rupee); W0 curves bit-identical (zero false fires, default-OFF contract holds). The baseline stop/DMA/review clauses already exit before breadth reads low - E008a's monthly-cadence mistiming reproduces intra-month. Gauge validated (member-level recompute to 1e-6; 2020-03 trough 4.1% on Mar 23 vs 15.5% month-end; 2018-09/10 avg 33.2% vs 2017 calm 78.9%). W1 was uncontrolled: the E006 fill gate refused 26/50 selection orders (top-4 scored names untradable at Rs250k/slot) so the book sat in cash through the crash. **No wiring; tighten stays null (OFF); breadth protection closed at monthly AND intra-month cadence.** See 2026-09-26 E008b block | 2026-09-26 |
| E009 | Fill-gate reachability: the E006 ADV fill gate refuses a buy when notional > 5% of trailing-20 median turnover; at the shipped Rs250k/slot that excludes med20 < 0.5cr names. Measured how much of composite_2f's pick return is unenterable, and whether ADV-aware eligibility (universe.min_median_turnover_cr: 0.75, chosen by the gate's own arithmetic, not tuned) fixes it. ADOPT iff corrected mean improves AND paired-t >= -2 AND refusal drops to <= 1/3 | **adopted** - 38.8% of pick-months (3,413/8,802) and 50.5% of gross pick return mass were UNENTERABLE at Rs250k; the refused picks were the model's BEST (+4.05% vs +2.52% fillable) - illiquidity concentrates exactly where the composite concentrates. The 0.75cr floor (through the real chain) cuts refusal to 1.5%, corrected pick mean +2.52% -> +2.61%, IC 0.0675 vs 0.0681 (paired t = -0.12); zero-drift restore bit-identical (1.4e-17). Config floor 0.0 -> 0.75 with this row cited. Postscript: E008b's W1 refusal count was inflated by its evaluator's window-starved ADV (LIQUIDETF/SPLIL were enterable at decision time) - E008b's arm-vs-arm conclusion untouched. See 2026-09-26 E009 block | 2026-09-26 |
| E010 | E006's cost sensitivity re-measured on the E009 floor universe (the only change): edge-halving point, absolute net at 0.2%, impact decomposition at the shipped slot. MOVE default to 0.2% iff net >= 2.0% AND >600 halving point relaxes AND floor-arm impact <= 80% of pre-floor AND gross >= 2.3% | **kept 0.5%/side** - backward guard reproduced E006 exactly (6,622 picks, means within tie-swap tol, half-edge None); floor arm nets 2.36% at 0.2% (a PASS), gross 2.76% (d PASS), modelled pick impact 0.565% -> 0.139%/side (c PASS, 4x). Criterion (b) FAILED conservatively: the >600 halving point TIGHTENS (E006's warning never bound pre-floor - it was masked by untradable gems; on the tradable book the >600 edge halves at 1.0%). Headline mechanism: E006's flat 0.5% default was almost exactly the mean modelled impact of a paper portfolio the engine refuses to build (0.565%); the honest cost stack on the tradable book is flat ~0.35% + impact 0.14% = ~0.5%. Default grounded, not hand-waved. See 2026-09-26 E010 block | 2026-09-26 |
| E011 | Slot-count attribution on the Phase 6.1 walk-forward harness: arms A4 (shipped control, zero-drift guard vs the baseline run), A8, A12, B8 (8 slots + wider review percentiles, churn control). ADOPT a wider count iff equity >= A4 + Rs200k AND Sharpe higher AND maxDD no worse than A4 - 2pp AND pick hit >= A4 - 3pp; between passing arms the higher final equity wins; ties keep 4 | **adopted n_slots = 8** - A4 reproduced the shipped baseline bit-for-bit; 8 slots recovered Rs402,923 of the Rs510,297 loss (489,703 -> 892,626; -51.0% -> -10.7%; maxDD -65.2% -> -23.9%; Sharpe -0.38 -> -0.29) with the completed-pick hit rate unchanged (33% -> 32%): the realized loss was CONCENTRATION, not selection. A12 cleared the bars too but lost to A8 on final equity (731,870); B8 ruled the churn rise (1.66 -> 3.46/mo) a slot artifact, not ranking pressure (wider percentiles: -Rs10,159, churn 3.43). Buy-side slippage vs the decision mark FLIPPED +0.441% -> -0.099%/side at the halved per-slot notional - part execution gain, part diversification; the held-constant-notional decomposition arm is pre-declared as the follow-up. Config n_slots 4 -> 8 with this row cited. See 2026-09-26 E011 block | 2026-09-26 |
| E012 | The E009 floor re-measured at the E011 8-slot notional (S=Rs125k, gate boundary 0.25cr): arms floor 0.375 / 0.5 / 0.75 through the real chain, baseline 0.0 guarded bit-identical to E009's R1 rows + restore IC = P4.1b frozen + the 0.75 arm = E009's R2 verbatim. ADOPT the LOOSEST floor clearing: corrected mean >= 0.75's - 5bp, paired t >= -2 vs baseline, refusal <= 1/3 of un-floored, floor >= gate boundary | **adopted 0.375** (boundary x E009's own 1.5x headroom - derived, not tuned): refusal 1.14%, corrected mean +2.692% vs +2.632% at 0.75, IC 0.0717 vs 0.0675, modelled impact 0.092%/side vs the 0.5% cost stack. Answer: the floor MUST move with slot size - it is derived from the gate boundary, which scales with per-slot notional. Disclosure: the runner initially reported 0.5 (candidate order inverted the pre-registered 'loosest wins'); caught pre-adoption, fixed, re-run - every measured number identical. Config 0.75 -> 0.375; smoke re-pinned (4,579 picks, IC = E012 arm); harness reference re-run bit-identical equity 892,626.09 (one trigger label moved: HARDWYN 2023-09 rank exit -> DMA). See 2026-09-26 E012 block | 2026-09-26 |
| E013 | The shelved index regime filter (BRD §15: Nifty 200 TRI vs its 200-session DMA), measured on the realized 35-month harness window: arms BUY_BLOCK / CASH (diagnostic) at risk-off fold month-ends. PASS = all three pre-registered bars (CAGR, drawdown severity, Sharpe) vs the shipped baseline, with a hair-trigger probe (2024-12-31, ratio 0.9990, forced risk-ON) | **passed, NOT adopted** — baseline 835,695 / −6.14% CAGR / −0.427 Sharpe / −22.99% maxDD; CASH 883,270 / −4.29% / −0.244 / −19.55%; NO_BUYS 886,195 / −4.18% / −0.235 (better than CASH — the liquidation leg adds nothing); forced-risk-on probe 873,170 / −4.68% / −0.273 / −20.47%, the gain survives. NOT adopted: the test window is burned for this rule family, the gate's 8 intervals were the baseline's *better* ones in aggregate (attribution), and VIX still has no data path. Disclosed sign slip in the hypothesis (maxDD is a negative fraction; the prose governs, the literal signed reading is recorded as REJECTED). E014 later rejected the premise on the validation slice. See 2026-09-27 E013 block | 2026-09-27 |
| E014 | The risk-off buy-block re-run on the 145-month validation slice (test window untouched) across 6 pre-named episodes: B1 the baseline is worse inside gated intervals (mean d < 0 at one-sided p < 0.05, n ≥ 10); B2 ≥ ceil(2/3) counted episodes gate-favored | **rejected** — mean d = +0.542%, p(gate helps) = 0.654; the baseline's engine return was +0.754%/mo (sd 8.26%) in the gate's 35 intervals vs −0.026% (sd 5.50%) in the other 109 — risk-off marks VOLATILE months, not losing ones; 3/5 counted episodes gate-favored, 4 needed. The arm's whole-slice equity advantage (1,108,821 vs 942,030; maxDD −46.5% vs −65.6%) traces to exposure / variance drag, not timing. Index leg closed; no config change. See 2026-09-27 E014 block | 2026-09-27 |
| E015 | Signal-free slot sizing by own-name volatility on the same slice: A baseline, B EQUAL_RISK_MEAN1 = clip(σ_med/σ, 0.5, 2.0) normalized so the month's pool mean scale is exactly 1.0 (unchanged average exposure), C DERISK_CAP = clip(…, 1.0) unnormalized (diagnostic). PASS iff B's maxDD severity gain ≥ R/3 (R = E014's committed relief 19.07pp) AND CAGR ≥ A − 1.00pp AND better DD in ≥ 3 of 6 episodes AND B's mean invested share within ±2.00pp of A's | **failed** — all guards passed (hook inert, A == E014 baseline, picks 5,605, IC pin, σ PIT 1.4e-17, exposure −0.49pp): B's drawdown gain **−1.93pp** (−10% of R) at CAGR −2.13% vs −0.50%, maxDD WORSE (−67.51% vs −65.58%). B's arithmetic mean fell 0.149pp/mo (sd 6.31% → 6.17%): equal-risk weighting is a bet against the composite's own alpha concentration. C captured 17.8% of R (3.40pp) with CAGR +0.21pp better — directional confirmation of E014's variance-drag mechanism, ~1/5 of the relief, and C removed 1.5pp of mean invested share to do it: the relief scales with exposure ACTUALLY removed. No config change; sizing family closed on the slice. See 2026-09-27 E015 block | 2026-09-27 |

---

## Milestone M2 — Phase 1 data pipeline complete (2026-09-22, commit `a2318ce`)

Not an experiment — the data-layer sign-off gate from actionplan.md Phase 1. Recorded here
because the plan's checkpoint is "show the validation report, get sign-off."

**Data state** (`full` profile, DuckDB `data/duckdb/quant.duckdb`, cutoff 2026-09-21):

| Source | Rows | Dates | Span |
|---|---|---|---|
| bhav (old + UDiFF formats) | 7,896,137 | 3,878 | 2011-01-03 → 2026-09-21 |
| delivery (MTO + sec_bhavdata_full) | 6,262,863 | 3,879 | same, incl. 7 healed days |
| adj_close (yfinance `.NS`) | 4,048 / 4,048 EQ symbols | — | 0 permanently unavailable after retries |

> **Superseded by M2.2 (below).** The 4,048/4,048 count was `count(DISTINCT symbol)`, which
> counted symbols whose frames were entirely NULL as priced. Real coverage: 2,982 priced
> symbols, 1,066 of them (26%) delisted tickers Yahoo no longer serves. Left as written,
> with this note, rather than quietly edited.

**Validation report:** yearly bhav coverage 93.1–95.4% (weekday-count denominator); 0 outage
holes — 222 weekday gaps == 222 recorded NSE holidays; delivery↔bhav join mismatch 0.00%;
result **PASS**.

**Canaries (BRD §11):** momentum Spearman IC **+0.065** pooled (285 months, > 0 ✓);
delivery% autocorrelation **0.89** (293,787 symbol pairs, > 0.5 ✓); eligible-count stability
all 189 months within ±20% of median (1,214 → 1,463) ✓. Selfcheck suite 8/8.

**Decision: the 7 corrupt MTO days (2017–2019).** Files arrive from NSE's archive with the
header's first byte truncated (`rade Date <…>`); re-downloading reproduces the corruption, so
it is source-side, not ours. Two normalizer rules were adopted as policy: (1) a wrong-dated
row is still refused outright; (2) when the header is truncated, the trade date is recovered
from the intact `10,MTO,DDMMYYYY` counts line — spot-checked against the filename for all 7
days. Corollary policy: one corrupt file never blocks a batch; refused files are collected
and raised at the end, loudly. The 7 healed days are in the delivery table and join bhav
with 0.00% mismatch.

**Honest caveats:** (1) the momentum canary was initially computed with an inverted ratio and
reported −0.065; the inversion was caught and fixed — the +0.065 figure is the corrected one.
(2) The IC pool includes micro-caps with gappy history; the Phase 3 experiment recomputes IC
on the as-of top-1500 universe (the canary's eligibility SQL is the template). (3) scipy was
not added: Spearman is computed as Pearson-on-ranks (identical math) — BRD §13 dependency
justification avoided by construction.

---

## Milestone M2.2 — pipeline performance and input stamps (2026-09-22, uncommitted; working tree on `7d5d431`)

Not an experiment — an infrastructure pass. Recorded because it changed **what the data tables
contain**, not only how fast they load. Commit hash to be filled in once committed.

### Measured savings

| What | Before | After |
|---|---|---|
| self-check suite, real work | 156.0s | 30.0s |
| self-check suite, nothing changed | 156.0s | **1.9s** (cached) |
| `universe.winners` check | 134.3s | 2.7s |
| `adj_close` table | 30.3M rows | **6.79M** |
| DuckDB file / free blocks | 551 MB / 419 blocks | 437 MB / **0** |
| `adj_close` → pandas | 2.4 GB, 2.9s | 0.55 GB, 0.85s |
| winners recompute input | 30.3M rows, 4.9s | 688,824 rows, 0.12s |
| winners build SQL | 6.97s | 0.22s |
| full-history rank build | 6.35s* | 4.02s |
| month-end panels (new) | — | 2.9s, 1.45M rows |

\* the 6.35s figure was measured while the MTO/adj backfills were running, and rank has since
moved onto the `liq_me` panel (follow-up note at the end of this block) — treat this row as
contention, not speedup.

**R1 — scoped recompute.** The winners spot-check loaded all 30.3M `adj_close` rows into pandas
(2.4 GB) and re-sliced the frame 20 times — 128.7s of the 134.3s check. It now fetches only the
sampled months' window (688,824 rows, 0.12s) in one pass. Verified equivalent, not assumed:
**10/10 months identical, worst return difference 0.00e+00, winner sets identical.**

**R2 — table diet.** See the NULL/coverage decision below for the row reduction, plus the
`--trim` repair, the bounded fetch, and the file rewrite that reclaimed the deleted blocks.

**R3 — month-end panels** (`month_grid`, `adj_me`, `turnover_me`, `deliv_me`): daily→monthly
once, so repeated work is joins against 1–2M-row panels. `winners` now joins `adj_me` instead of
two ASOF joins over 30M daily rows. `turnover_me`/`deliv_me` are built but **not yet read by
anything** — Phase 3 staging at 0.3s each; delete them if the feature library does not want them.

### Decision: 10.9M NULL `adj_close` rows, and why coverage was reporting a false 100%

Of 30.3M stored rows, **10,929,155 (36%) had `adj_close IS NULL`**, and **1,066 of 4,048 EQ
symbols (26%) were entirely NULL** — delisted or renamed tickers Yahoo no longer serves (probe:
"possibly delisted"; multi-ticker batches also pad gap and pre-listing days with NaN). The old
backfill cached those all-NaN frames and counted the symbols as *fetched*, and the canary's
coverage metric was `count(DISTINCT symbol)` — so it reported **100% coverage over symbols it
could not price**. Policy adopted:

1. the fetcher skips an all-NaN frame, so a delisted ticker is reported *unavailable* rather
   than cached as permanently empty;
2. `--trim` deletes pre-`adj_history_start` **and** NULL rows from an existing table (idempotent:
   a second run removes 0); the fetch floor is `adj_history_start: 2009-01-01`, not `period="max"`,
   so the 1991–2008 tail (42% of the table, unreachable by any profile) cannot come back;
3. coverage is measured on **still-trading** symbols: 2,738/2,738 = **100%**, with the all-time
   2,982/4,048 = 73.7% reported alongside as the survivorship hole BRD §4 warns about.

Consequence for the panel invariant: 17,066/17,225 eligible symbol-months (99.1%) are priced, and
the 159 holes trace to exactly **36 unpriceable symbols** (24 entirely NULL, 12 sparse). The
gap assertion therefore tests *"a valid in-month print existed and the panel lost it"* rather
than *"zero holes"* — it must fail on a panel bug, not on Yahoo's absent tickers.

### Winners relabelling caused by R3

The rewiring tightened two rules: no symbol can be priced from a stale cross-month row, and the
current **partial month (2026-09-21) is never labeled** (it would silently change tomorrow).
Against the pre-change snapshot: **1,276 rows removed = exactly the September pool** (64 winners /
128 top-decile / 20 top-20), **0 label flips and 0 return changes across all 11 shared months**,
and 3 pool rows *added* (INFRABEES, NIF100BEES, NIFTYIETF) that the old NULL-matching ASOF join
had dropped. Database file shrank 551→437 MB: the reclamation needed a rewrite (parquet
EXPORT/IMPORT *grew* it 498→506 MB; native `ATTACH` + `CREATE TABLE AS` gave 421 MB with 0 free
blocks), done with a verified backup that was removed after the suite passed.

**Canary note:** momentum IC is now **+0.0639 over 200 month-ends** (was +0.065 over 285) —
deleting NULL rows means `lag(252)` counts trading days that actually have prices, so a few
pseudo month-ends disappear. Same sign, still passes.

### Input stamps (`src/stamp.py`, check #2 in the runner)

A stamp is a `build_stamp` row: fingerprint + output row counts + built-at. The fingerprint hashes
five spec kinds — `code` (sha256 over `src/**/*.py`, `config.yaml`, `requirements.txt`),
`cfg:a.b`, `table:t.col` as `(rows, max)`, `dir:path` as `(files, bytes, newest mtime)`, `file:p` —
and an unknown spec **raises** rather than being ignored. It is current only if the fingerprint
matches **and** every recorded output table still holds its recorded row count (a dropped or
truncated table forces a rerun). It is **cleared before** the run and **recorded only after all
13 checks pass**, so a failure can never look like a pass.

`(rows, max)` instead of a content hash is deliberate: every check rebuilds the tables it
validates, and a rebuild writing identical rows must not invalidate its own stamp — asserted in
the self-check and confirmed live (an `ensure()` rebuild of all four panels left the suite stamp
current).

| Evidence | Result |
|---|---|
| repeat run, nothing touched | **1.9s**, `ALL PASS (13 checks, cached …)` |
| `--force` | 46.3s, reruns every check (bypass proven) |
| comment-only edit to `src/validate/report.py` | full 27.2s rerun — the code hash is content-based, so even a comment invalidates |
| one cached MTO file mtime-touched (bytes unchanged) | full 29.3s rerun, then 1.9s cached |
| `panels.ensure()` no-op / rebuild / no-op | 0.01s / 1.78s / 0.01s (vs 2.9s unconditional) |
| `python -m src.stamp` | full rule set asserted: absent/dir/file hashing, identical-rebuild stability, new row + config change invalidate, unknown spec raises, dropped/truncated output not current, record/clear round-trip |

`data/raw/404_cache.txt` is deliberately **not** in the fingerprint: it is a negative cache of
URLs NSE 404'd, appending to it changes no table, and including it would let one network 404
defeat the cache forever.

**Honest caveats:** (1) a cached pass means "this exact fingerprint passed" — `--force` exists
for when that is not good enough. (2) The file-size gain is modest (437 MB); the real win is the
78% row reduction, which shrinks every scan rather than the bytes on disk. (3) Phase 1's
momentum verdict and the M2 sign-off above were computed before the NULL trim; the table state
has changed since, so the M2 canary numbers should be read as "same sign, re-measured" rather
than bit-identical.

### Follow-up (same session): rank reads the panel

The unused `turnover_me` (monthly medians) was replaced by **`liq_me`** — the BRD §4 trailing-
window median, **pooled** (a median of monthly medians is not a median) and full-history — and
`universe_rank` now ranks that instead of rescanning daily bhav. The window expression lives in
one place from here on.

Equivalence, measured rather than asserted:

- **`full` profile: bit-identical.** 330,831 rows both ways, 0 added, 0 removed, 0 differing
  med3/rank/in_universe values against the old daily-bhav query. (Expected: no bhav data precedes
  2011, so the window was never truncated there.)
- **Rank's own self-check** now recomputes med3 straight from bhav for sampled decision dates
  (7,765 symbol-months, incl. first and last month) and asserts exact equality with the panel,
  plus every `universe_rank` row against its `liq_me` row — 0 mismatches.
- **`quick` changes exactly three months** (2025-09-30, 2025-10-31, 2025-11-28). Cause: the old
  query filtered *daily* rows by profile start before building the window, so the first
  lookback−1 decision months were ranked on truncated evidence — the wart its own docstring
  admitted. Fixing it adds 84 symbol-months, flips 121 eligible flags/reasons, and moves winners
  by 56 rows added / 39 removed / **1 gained winner, 0 lost**.
- Cost: panel rebuild +0.94s (`liq_me` is 2.21s of the 3.84s), and rank's build drops from 4.02s
  to **1.11s** for the full history (330,831 rows) because it no longer touches daily bhav.

---

## Milestone M2.3 — daily refresh and scheduler (2026-09-23, uncommitted; working tree on `7d5d431`)

Not an experiment — the operational gate that turns Phase 1's tables from "built once" into
"current every evening". Two new modules: `src/download/refresh.py` (the pipeline, callable by
hand) and `src/download/scheduler.py` (the single entry point the clock calls). Data cutoff moved
**2026-09-21 → 2026-09-22**; bhav is now **7,899,813 rows**, delivery 6,262,863, and adj_close
prices **2,658 of 2,662 traded symbols on the newest NSE day**.

### The daily path

`python -m src.download.refresh` (`--date` for catch-up): as-of → fetch → normalize → `end_date`
→ adj_close → derived rebuild → stamped self-check.

- **as-of** is today once past `download.publish_cutoff_ist` (19:00 IST), else yesterday. Not a
  nicety: `_http` remembers a 404 for 30 days, so one run before NSE publishes would hide a real
  trading day for a month.
- **adj_close gets a daily path** (`refresh_recent`). `backfill()` skips symbols that already
  exist, so it could never see a new day. It fetches one short window for symbols whose bhav
  history runs past their last stored adjusted date, and **self-heals corporate actions**: a
  split rewrites Yahoo's whole adjusted history, which an append cannot fix, so when the adj/raw
  factor moves between the two days the symbol's entire series is re-fetched and replaced.
- **`end_date` is set from the data, not the clock** — the clock decides what to fetch, the newest
  bhav date present decides what is written. The edit preserves the line's comment (a yaml
  round-trip would have deleted every comment in config.yaml).

### Live verification

| Test | Result |
|---|---|
| New day (2026-09-22) fetched and normalized | bhav **+3,676 rows**, 2,662 EQ symbols; `end_date` bumped 2026-09-21 → 2026-09-22; derived rebuilt; self-check **ALL PASS (13)** |
| Adjusted-close coverage of that day | **2,662/2,662 traded symbols priced** |
| Second run the same day | 8.4s, "panels already current", self-check **cached** |
| Delete 2 settled adj rows, re-run | restored exactly — "+2 symbols, +2 rows" |
| `scheduler --once` (real run) | **exit 0**, "ok: caught up to 2026-09-22", 42s |
| that run's own verify step | self-check **ALL PASS (13 checks) in 28.4s**, stamp recorded |
| `scheduler --self-check` | verdict codes (equal/ahead/behind/empty/failed), cutoff wait math, era-aware URL set, lock exclusivity + stale takeover, 404 eviction scoping + idempotence + missing file |
| suite afterwards | **13/13 in 32.8s**, no stale lock, both stamps current |

The daily log line reads: `2,658/2,662 traded symbols priced (4 missing)` — the missing four are
`20MICRONS, 21STCENMGM, 360ONE, 3BBLACKBIO`, whose 2026-09-22 rows my delete-and-restore test
removed and Yahoo is currently serving as a **placeholder row (Close and Adj Close both NaN)**.
The notna guard correctly refuses to store it and the day stays queued; the table, not the code,
is what is 4 rows short, and the recovery mechanism is the one proven above.

### The scheduler: entry points and exit codes

| Invocation | Behaviour |
|---|---|
| `python -m src.download.scheduler` | waits for the cutoff, refreshes, retries while behind |
| `--once` | one attempt now, no waiting or retrying (the manual equivalent) |
| `--self-check` | the offline rules above; no network, no DB writes |
| exit **0** | caught up — or nothing was due |
| exit **1** | refused to run (another refresh in flight) or the refresh itself failed |
| exit **2** | ran fine but still behind: NSE holiday, or their archive is late |

Two pieces are load-bearing, not decoration:

- **Every attempt evicts the target date from the negative cache first**, otherwise a retry is
  theatre — `_http` would answer "holiday" from the 30-day cache without contacting NSE. Verified
  against the live 451-line cache: exactly the target date's 3 URLs dropped, other dates and
  unrelated lines untouched.
- **A single-instance lock** (takeover only after 90 min, i.e. a dead process, not a slow one),
  so a scheduled run and a manual run cannot both write DuckDB.

The refresh runs in a subprocess — its own DuckDB writers, its own env, exactly as run by hand —
and the wrapper judges it from `max(bhav.date)`, not from the exit code alone.

### Finding: retrying a late archive is expensive, and that is what the cutoff is for

The live scheduled-mode test hit the 600s tool timeout. It was **not** a bug: with
`refresh_retry_minutes: 1` (a test value) the run did 3 attempts × (full refresh 40–90s + real NSE
probes + 60s sleeps), which exceeds ten minutes. The honest lesson is the cost model — a retry
against a not-yet-published day spends real NSE timeout time (60s read timeout × retries per
source), which is exactly why the default cutoff is 19:00 and the retry gap 20 minutes. Bounded
retrying stays: a late archive recovers, a holiday never will.

### Change: per-event logging (prompted by that timeout)

The wrapper originally buffered its output and wrote one block at the end of the run. A killed or
rebooted run therefore left **no record at all** — the failure mode most worth logging was the one
case that logged nothing. `log_line()` now appends one IST-timestamped line per event through
`say()`, so an interrupted run still shows how far it got:

```
2026-09-23 00:33:32 IST  --- scheduler start (once, pid 24916)
2026-09-23 00:34:14 IST  attempt 1/3: ok: caught up to 2026-09-22 (42s, refresh exit 0)
2026-09-23 00:34:14 IST  RESULT: ok: caught up to 2026-09-22 (exit 0)
```

The module docstring now carries the concrete cron and `schtasks` lines, plus the property that
makes one missed night harmless: the refresh walks every month from the newest stored date to
as-of, so a run after downtime closes the whole gap.

### Bugs found and fixed on the way

1. **Any run in the current month could crash**: `delivery.download_month` ignored `end_date`
   unless the caller passed `up_to`, while both bhavcopy loops bound themselves. The same latent
   shape existed in `bhavcopy_old.download_month`. Both now bound themselves, so no call site can
   walk into a day `fetch_day` refuses.
2. **Yahoo rate-limited us (HTTP 429)**: ~1,067 delisted tickers sat in the fetch set on *every*
   run, because after the NULL trim they have no stored rows, so their bhav max always looked
   newer than "no stored date". The daily set is now scoped to symbols that traded in the last 30
   days (114s → 47s); a symbol suspended longer is picked up by itself when it resumes.
3. **My own assertion was wrong**, twice: it demanded `panels.ensure()` rebuild every time, which
   breaks the harmless second run of the day (now reported, not required), and it asserted the
   2024-07 era boundary could be straddled by a single *date* when it is a straddled *month*.
4. `months_between` is a generator — the fetch plan was a generator, not the list the code assumed.

### Number reconciliation (looked contradictory in the logs)

`winners` holds **14,373 rows** = one per eligible symbol-month (~1,337/month, 11 months), of which
**724 are winner flags** (~67/month, top 5%), 1,441 top-decile, 220 top-20. The stamp reports table
rows, the refresh reports winner flags; both numbers are right.

---

## Phase 2 (M1) complete — universe + labels (2026-09-23, uncommitted; working tree on `8df273b`)

Not an experiment — the plan's Phase 2 checkpoint ("show 3 winner lists side by side with
re-computation"). Recorded because the audit found three BRD §4 rules that existed only in config
or docstrings, and because one of them falsifies a stated assumption in the BRD.

### The audit: plan Phase 2 against the working tree

| Task | Plan's done-when | Before this pass | Now |
|---|---|---|---|
| 2.1 as-of rank | 5 dates printed; stable MoM except real liquidity shifts; minutes not hours | **satisfied** (`rank.py` + the `liq_me` panel; 5 dates printed; Jaccard ≥ 0.85 asserted on all 12 transitions; 1.5–3.7s vs a 300s bar) | unchanged — not rebuilt |
| 2.2 eligibility | BRD §4 as a pure function from config; 6 hand-built cases (T2T, low turnover, recent listing, GSM-flagged, rank>1500, normal) | **partial**: 4 of §4's rules present; series rule hardcoded rather than from config; turnover floor dead config; GSM/ASM implemented nowhere. Of the 6 cases: normal, rank>1500 and recent listing covered; **low turnover and GSM-flagged had none**; T2T covered only at the rank layer (BE never ranks) and unanswerable in the point form | completed (below) |
| 2.3 winners | top 5% + top-20 + top-decile; 10 random months recomputed, 10/10 | **satisfied** with one documented deviation; checkpoint lists not printed | checkpoint artifact added (below) |

What 2.2 was missing, and what it cost: the series rule lived as a hardcoded `'EQ'` string in
`rank.py`, `panels.py` and `eligibility.py` while `universe.allowed_series` — the config key that
owns it — was never read (plan working rule 1). All ~180 series codes in `bhav` were checked to
settle it: **`"T2T"` appears in no row** (BE is the trade-to-trade series that actually exists), so
the `exclude_series: [BE, T2T]` key was dead config and is gone. `panels.series_sql()` is now the
single renderer for the decision calendar, the liquidity panel, eligibility and rank's oracle, and
`allowed_series` is a `cfg:` spec in the panel stamp — changing it rebuilds the panels.

### Decision: BRD §4's "subsumed" ₹5-crore floor is measurably false

BRD §4 states: *"The ₹5-crore-turnover floor is subsumed by the top-1500 rank and kept only as a
config guard."* Nothing read the key, so the claim had never been tested. Measured on the quick
profile (13 decision months):

| Quantity | Value |
|---|---|
| Rank-1500 median daily turnover (pooled 3-month), by month | **₹1.01cr – ₹1.94cr/day** |
| In-universe symbol-months below ₹5cr | **6,010 of 19,500 (30.8%)** |
| Effect of enforcing the floor | excludes ~31% of the as-of universe |

**Decision: implemented, shipped OFF.** The floor is now a real config-driven rule (`> 0` excludes
with reason `turnover<Ncr`), but `min_median_turnover_cr: 0.0` leaves live behaviour BRD-normative —
the premise is false, the *policy* that follows from it (rank governs liquidity) is still the BRD's,
and silently relabelling 30.8% of the universe on a contradicted sentence is not an audit's call.
`_live_check` re-reports the measurement on every run so the claim can never go unverified again.
Switching it on is one config line, and it needs the BRD owner.

Implementation bug caught here: `med3` is in **rupees** while the floor is in **₹ crore**, so the
first version compared 1e8 against 15.0 and never fired. There is now one shared conversion
(`panels.RUPEE_PER_CRORE`, also used by rank's `med3_cr`).

### GSM/ASM: a real rule with no historical source

BRD §4 requires "not under GSM/ASM (as of D, where historical data exists)"; the code had nothing.
Now: `surveillance(symbol, effective_from, list, stage)`, excluded when `max(stage)` over rows with
`effective_from <= D` exceeds `universe.gsm_asm_max_allowed_stage` (default **0** — any listing
excludes). §8.2's *hold* rule (`gsm_asm_stage_exit: 2`, forced exit) is a different decision and
stays in the engine. `load_surveillance()` imports `paths.surveillance_csv` when a snapshot exists;
the CSV is the trust boundary, so rows are validated and a malformed one raises rather than being
skipped. Live, the rule reports itself honestly:

```
surveillance: none — no historical GSM/ASM archive exists (BRD §4 'where historical data exists'),
so the rule excludes nothing in the backtest
```

Exercised end to end on real data with a temporary snapshot: a symbol in the universe for all 13
months took eligible **17,204 → 17,191** (−13 = exactly its 13 months), the point form returned
`(False, ['gsm_asm'])`, and dropping the snapshot + rebuilding restored the baseline hash. Known
limits, recorded rather than hidden: no `effective_to`, so "left the list" is unrepresentable; the
table survives removal of the CSV (deliberate — a snapshot is an import, not a lease), which the
live check makes visible every run; and one bad row aborts the whole `build()` (robustness gap,
named in the audit, not yet fixed).

### The six cases the plan names

| Case | Fixture | Expected reasons at the Sep decision |
|---|---|---|
| normal | A, B | `''` (eligible) |
| rank>1500 (+ penny) | Y (rank 6, ₹5) | `rank>5,price<20.0,turnover<15.0cr` |
| recent listing | D (first month Aug) | `listed<6m,gsm_asm` |
| low turnover | C (rank 5 — **inside** the universe) | `turnover<15.0cr` |
| GSM-flagged | G (GSM stage 2 from Jan 2024) | `gsm_asm` |
| T2T stock | X (`BE`), Q (`'T'`) | never enter the rank; point form → `series_not_allowed` |

The low-turnover case deliberately mirrors the live finding: a symbol **inside** the top-1500 and
still excluded by the floor. `D`'s ASM begins Sep 1, so its Aug row must *not* carry `gsm_asm` — the
as-of test — while `A`'s flag (Oct 1) is after the window and must not exclude at all. Flipping the
stage threshold 0 → 2 makes G eligible again, then back to 0 re-excludes it, so the threshold is
provably config. One feature of the rewrite: table and point form are now compared **literally,
reason for reason**, and that caught a latent divergence — a NULL close suppressed the `listed`
reason in the point form only. Three live rows exercise it (SCANSTL 2026-08-31, BTTL 2026-09-22,
KAVDEFENCE 2025-09-30); all three now agree.

### 2.3 winners — satisfied, with one documented deviation

The done-when is met: top 5% (724 flags / 11 months), top decile 1,441, top 20 220, and an
**independent from-scratch pandas recompute matches 10/10 sampled months exactly** (worst per-symbol
return difference < 1e-9, winner sets identical). The deviation the plan should know about: the
recompute reads `adj_close`, not raw bhav ratios. Raw month-end ratios are not a return oracle —
a mid-month 10:1 split reads as −89% (GOLDADD, Aug 2026) and NSE vs Yahoo place dividend adjustments
differently (Feb 2026: 149 of 1,279 names diverging >5pts, in both directions) — while BRD §4 rules
that returns come from adjusted closes. The raw→bhav half of the chain is Phase 1's (task 1.4's
done-when plus the canaries), so the chain is verified in two halves rather than by a zips-level
oracle.

### Checkpoint: three winner lists, table vs recomputation

Now printed by the check itself, because a claim without a visible artifact is not a checkpoint:

```
2026-08-31: pool 1,337 | winners 67 (recomputed 67)
  table     : MOREPENLAB +87.87%, RATNAVEER +68.72%, INDSWFTLAB +62.69%, KENNAMET +55.81%, SHILPAMED +55.30%
  recomputed: MOREPENLAB +87.87%, RATNAVEER +68.72%, INDSWFTLAB +62.69%, KENNAMET +55.81%, SHILPAMED +55.30%
2025-11-28: pool 1,282 | winners 65 (recomputed 65)
  table     : SILVER1 +66.07%, THANGAMAYL +49.98%, RICOAUTO +44.96%, CUPID +40.95%, LGBBROSLTD +38.34%
  recomputed: SILVER1 +66.07%, THANGAMAYL +49.98%, RICOAUTO +44.96%, CUPID +40.95%, LGBBROSLTD +38.34%
2025-10-31: pool 1,304 | winners 66 (recomputed 66)
  table     : GMBREW +74.60%, MCLEODRUSS +67.17%, SHAREINDIA +46.20%, INDOTHAI +43.18%, TATVA +40.56%
  recomputed: GMBREW +74.60%, MCLEODRUSS +67.17%, SHAREINDIA +46.20%, INDOTHAI +43.18%, TATVA +40.56%
independent recompute: 10/10 months match exactly (returns < 1e-9, winner sets identical)
```

### Zero drift: the audit changed no label

Snapshotted before the first edit, compared by hash after the last:

| Table | Baseline (before) | After | |
|---|---|---|---|
| `eligible` | 33,567 rows / 17,204 eligible / reasons_hash `309004543472110316846433` | identical | **IDENTICAL** |
| `winners` | 14,373 / 724 win / 1,441 decile / 220 top20 / labels_hash `132390852150023982609164` | identical | **IDENTICAL** |
| `universe_rank` | 33,567 rows / rank_hash `310020180659703283487795` | identical | **IDENTICAL** |

That is the property that mattered: the series rule was re-expressed (not changed in effect), the
floor stayed off, and the surveillance table is empty — so every number Phase 3 will join to is
bit-for-bit what it was. Suite after the change: `python -m src.selfcheck` → **ALL PASS (13 checks)
in 28.5s**.

### Open items for the next pass

1. **The ₹5cr floor decision** — the premise is falsified; enforcing it cuts ~31% of the universe.
   Needs the BRD owner, not an agent.
2. **`eligible()` is not the "pure function" the plan asks for**: it needs an open connection *and*
   the `month_history` table that only `build()` creates (on a fresh DB:
   `CatalogException: Table with name month_history does not exist!`).
3. **The rule set has two owners**: `_CHECKS` (SQL) and the point form's if-chain must be
   hand-synchronised — the divergence found above is the class, and fixing that class is the
   highest-value next pass.
4. **A malformed surveillance row aborts the whole build** (and with it the daily refresh chain)
   instead of being quarantined.
5. Minor, recorded for honesty: `eligible` keeps the partial September month while `winners`
   excludes it (benign — no return is provisional — but previously undocumented); 2.1's "5
   hand-picked dates" are deterministic picks (first, quartiles, last); and printing `₹` raises
   `UnicodeEncodeError` on this cp1252 console, so new output says `Rs`.

---

## Experiment E002 — univariate IC sweep (2026-09-24, profile `quick`)

- **Prediction (pre-registered in the ledger row above and in
  `experiments/002_ic_sweep/hypothesis.md`, written before the run):** 6–12M momentum and
  delivery% z-score have positive pooled Spearman IC, surviving BH at α = 0.05.
- **Run:** `experiments/002_ic_sweep/run.py --profile quick` — 22 features × 11 decision months,
  14,373 labeled rows (as-of top-1500 universe), cutoff 2026-09-22, git `d37580c`, 64s. All
  per-month and pooled ICs, p-values, top-5% precisions and the BH step-up are in
  `experiments/002_ic_sweep/results.json`; every number is reproducible from that config snapshot.
- **Verdict: PARTIALLY CONFIRMED.**
  - **CONFIRMED, right sign, BH-surviving: `mom_12m_1m` pooled IC +0.065 (p = 2.5e-14) — exactly
    the +0.065 the M2 momentum canary measured on its own universe, now on the as-of top-1500
    with the proper forward label.** `mom_1m` −0.095 (p = 2e-30): monthly reversal confirmed at
    the pre-registered negative sign, top-5%-by-value precision 72%.
  - **REJECTED, pre-registered positive direction: `delivery_pct_zscore` IC −0.010
    (p = 0.22, not even significant).** The E001/E002 delivery prior is falsified on quick data.
  - **`mom_6m` IC −0.024 (p = 0.004, wrong sign): rejected as a positive-direction prior** —
    on 12 months of quick data the 6M horizon still carries reversal, not momentum.
  - **Direction-agnostic findings (no pre-registered direction, reported not celebrated):**
    `squeeze_days_20d` −0.196 (p = 7e-123) and `atr_ratio` +0.126 (p = 2e-51) are the two
    strongest signals in the sweep — **low volatility predicts higher next-month returns** on
    this universe (volatility-compression "breakout lore" points the WRONG way here), and
    `volume_zscore` +0.106. Volatility-state features dominate the sweep; most candle features
    are weak-to-negative.
  - 18 of 22 features survive BH (n = 14k ⇒ tiny ICs are "significant"); the discipline that
    matters is the pre-registered sign + the per-month view: pooled ranks mix market-wide level
    shifts, and several features flip sign between pooled and monthly means (e.g. `mom_3m`
    pooled −0.019, monthly mean +0.028) — pooled-only verdicts would be fragile. The 0.10 IC
    "conventional" threshold leaves only `mom_12m_1m` (monthly mean +0.102) standing.
- **Honest caveats:** quick profile = 11 months, one regime; monthly IC counts are small
  (~1,300 rows/month) so per-month ICs are noisy; multiple-testing across 22 features is
  handled by BH but the direction-agnostic features get no such protection — their findings are
  hypotheses for E001/the full-profile re-run, not conclusions. The full-profile sweep is the
  same code with `--profile full` and is NOT pre-registered here.
- **Consequence for the plan:** Phase 4's composite (4.1) must rank-average features that
  survived E002 **with the measured signs** — low volatility is now a candidate factor, the
  delivery z-score is not.

---

## Refactor — `end_date` removed from config; the cutoff is the data (2026-09-25, uncommitted; working tree on `440e923`)

Not an experiment — an infrastructure pass in the M2.2/M2.3 line: it changed **where the pipeline's
data cutoff lives** and removed the one write the daily refresh made to a versioned file. No
experiment, label, or universe number moved; the zero-drift evidence is below.

### What moved where

| Was (M2.3 state) | Now |
|---|---|
| `config.yaml` carried `end_date: "2026-09-22"`, and the refresh **rewrote that line** every evening (`bump_end_date`, regex edit + atomic replace, adopted precisely because a yaml round-trip would have eaten the file's comments) | the key is **gone from config**, and `config.load()` now **refuses** a config that carries it — the class of state-in-config problems is deleted, not guarded |
| every stage trusted the config value as the cutoff | **`panels.data_cutoff(con)` is the single source of truth**: `max(bhav.date)`, read-only, with an empty/missing-bhav sentinel. bhav (the price backbone) decides — the delivery feed's one-day lead still must not move the cutoff (validate.report keeps classifying that as informational) |
| rank/winners formatted `end=cfg["end_date"]` into their SQL | `end=panels.data_cutoff(con)` — the database cannot disagree with the build inputs |
| validate.report's holes-vs-ahead split and adj_close's `_window_start` empty-table fallback read `cfg["end_date"]` | same reads against the database cutoff (`_window_start` still honors an `end_date` cfg key, explicitly marked backward-compat, so its self-check stays pure/offline) |
| refresh owned `asof_date()` (cutoff-gated today-or-yesterday, `--date` wins); the three downloader month loops self-bounded to `date.fromisoformat(cfg["end_date"])` | `asof_date()` moved to **`src/download/_http.py`** — the module every downloader already imports (a refresh-side home would make the backfill tools import refresh: a cycle); the downloaders bound their loops to the **as-of fetch-plan bound** (`cfg["fetch_asof"]`, set per-process by the refresh from its `--date`), and the backfill tools use it as their end bound |
| `git status` dirty after every refresh (`config.yaml` always modified) | the refresh writes **no repo file**; a run's outputs are the raw cache, the DuckDB tables and `data/refresh.log` |

The downloaders' upper bound changed meaning, deliberately: "config end_date" was *stored state*;
the as-of bound is *the fetch plan*. Same effective coverage on every real run (the refresh passes
`--date asof`; the live months sit under both bounds), but a downloader now refuses days the plan
did not ask for rather than days past a file line — and can never again be the thing that silently
clamps a catch-up run.

### Bug caught while re-auditing for this block

The first pass left `refresh.main()` still setting `work["end_date"] = asof` — a key the
downloaders had stopped reading. Harmless on the routine path (as-of defaults to the same
cutoff-gated yesterday), but a `--date 2026-09-15` catch-up would have fetch-planned the whole
current month instead of stopping at the 15th. Fixed: the plan key is `fetch_asof`, and the
as-of date flows from the one place that owns it (`--date` → `asof_date` → the downloaders'
`_http.asof_date` bound). Proven live: with `fetch_asof: 2026-09-21` the udiff month loop accepts
Sep-1 rows (its bounds check passed the probe before the probe's toy config ran out of fixture),
and the module self-check pins both refusal directions.

### New invariant replacing the old write

`bump_end_date` was the refresh's mechanism for keeping the cutoff monotonic. It is gone with the
key, so the guarantee moved into an assertion right after normalize:

```python
if not after["bhav"][1] or after["bhav"][1] < before["bhav"][1]:
    raise AssertionError(f"normalize shrank bhav: {before['bhav'][1]} -> {after['bhav'][1]}")
assert after["bhav"][1] <= asof, f"bhav holds {after['bhav'][1]}, past as-of {asof}"
```

A normalize run can no longer silently lose the newest bhav day (which would move every downstream
cutoff, rank and label backwards), and bhav cannot hold a date past the fetch plan. The refresh
log now states the property outright: *the cutoff downstream stages read is that bhav max date
(panels.data_cutoff)*.

### Zero drift, measured

The refactor rewired reads only, so the derived tables must be bit-identical. Every chain stage
was rebuilt through its real entry point and compared to the Phase 2/3 checkpoints above:

| Table / check | Baseline (this ledger) | After the refactor | |
|---|---|---|---|
| data cutoff | config `end_date: 2026-09-22` | `2026-09-22` from `max(bhav.date)` | **IDENTICAL** |
| `universe_rank` | 33,567 rows / 13 decision months | 33,567 / 13 | **IDENTICAL** |
| `eligible` | 17,204 eligible of 33,567 | 17,204 of 33,567 | **IDENTICAL** |
| `winners` | 724 winner flags / 11 months | 724 / 11 | **IDENTICAL** |
| independent recompute | 10/10 months exact (returns < 1e-9, sets identical) | 10/10, same months printed side by side | **IDENTICAL** |
| `feature_panel` / `feature_matrix` | 17,204 rows; labeled 14,373 at 5.0% winners | 17,204; 14,373 / 5.0% | **IDENTICAL** |

Suite after the change: `python -m src.selfcheck` → **ALL PASS (17 checks) in 57.8s**, and
`config.load()` reports `end_date in config: False` — with the new guard in place, a config that
tried to bring the key back refuses to load rather than silently half-working.

### Honest caveats

1. The three downloader self-checks now pin their offline upper bound to an explicit `fetch_asof`
   fixture and take the live bound from the database cutoff — the month-count asserts are
   unchanged (2024-01: 21 files, 2026-08: 21, MTO 20), but the *mechanism* of the bound changed;
   anyone diffing M2.3's check descriptions against these will see that, and it is intended.
2. The as-of bound is one knob with two spellings: `--date` (the refresh's CLI) and
   `cfg["fetch_asof"]` (what the downloaders read). The refresh is its only writer today; a
   future second caller should go through `_http.asof_date` rather than invent another.
3. `_window_start`'s backward-compat `end_date` branch exists so its self-check stays pure and
   offline; nothing in the repo sets that key anymore. If a third caller ever appears, delete the
   branch and test against the database cutoff instead.

Consequence for the plan: actionplan's M2.3 status clause "the scheduler's `end_date` write is
now atomic" describes a mechanism that no longer exists — the write is gone, and the 2026-09-23
audit finding it answered is closed at the root rather than defended in place.

---

## Experiment E001 — anatomy of winners (2026-09-25, profile `quick`)

- **Prediction (pre-registered in the ledger row above and in
  `experiments/001_anatomy/hypothesis.md`, written before the run):** winners' 12M−1M momentum
  and 20-day delivery% z-score distributions sit above the eligible rest (median shift > 0),
  judged by tie-safe AUC, BH across 22 features, and per-month sign consistency, with a
  pre-registered size-bucket split as the small-cap-artifact check on E002's volatility
  finding.
- **Run:** `experiments/001_anatomy/run.py --profile quick` — 22 features, 14,373 labeled rows
  (724 winners), 11 decision months, cutoff 2026-09-24, 1.8s. All shifts, AUCs, p-values,
  BH flags, regime and bucket splits are in `experiments/001_anatomy/results.json`.
- **Verdict: PARTIAL** (details in the ledger row and `verdict.md`). Momentum anatomy
  confirmed; delivery anatomy rejected (second independent falsification of the delivery
  prior); the volatility-state direction is the strongest and most consistent winner anatomy
  on this window — against the pre-registered lore direction — and it is uniform across size
  buckets, while momentum's separation concentrates in the top/mid buckets.
- **Honest caveats:** quick profile = 11 months, all of them up-regime, so the pre-registered
  regime split was vacuous (needs the full-profile re-run to mean anything); the pooled
  tail-vs-bulk disagreement on mom_1m/mom_3m (pooled positive, monthly bulk reversal) is
  flagged for E002b, not resolved here; E001 shares E002's window, so "confirmed" here means
  "confirmed on the same 11 up-months", not out-of-sample.

### Live verification (2026-09-25) — and one bug the live run caught

First real execution of the committed code: `python -m src.download.scheduler --once`, pre-cutoff
(10:52 IST), as-of 2026-09-24, a genuine 2-day gap to close (stored cutoff was 2026-09-22).

| Step | Result |
|---|---|
| 404 eviction for the target date | 1 entry dropped, re-probed NSE (the M2.3 mechanism, unchanged) |
| fetch + normalize (2 missed days, cache-skip after an interrupted first attempt) | bhav **7,899,813 → 7,907,146 rows**, cutoff **2026-09-22 → 2026-09-24**; delivery 6,262,863 → 6,268,195; adj_close +1 straggler row (the 4-missing self-heal queue from M2.3) |
| cutoff provenance | the log states it outright: *the cutoff downstream stages read is that bhav max date (panels.data_cutoff)* — no config write anywhere |
| derived rebuild | `universe_rank` 33,563 rows / 13 months, `eligible` 33,563, **winners 724 over 11 months (unchanged)** |
| verification gate | selfcheck **ALL PASS (17 checks) in 294.2s** inside the refresh; scheduler verdict **ok: caught up to 2026-09-24, exit 0** (336s) |
| repo hygiene | `git status` after the run: clean apart from the one-line fix below — the property this refactor exists for |
| Yahoo lag (documented, by design) | newest NSE day 2026-09-24: 804/2,664 traded symbols priced — placeholder NaN rows refused, queued for the next run |

**The bug:** the refactor's constants cleanup deleted `LOG_PATH` along with `CONFIG`, and the
refresh crashed with a `NameError` **after all data work had succeeded** — exit 1 on a run that
had caught up. The scheduler judged it exactly right (`FAILED: the refresh did not complete
(stored 2026-09-24, as-of 2026-09-24)`, traceback tail logged per-event, retry scheduled), which
is the verdict logic working as designed against the new cutoff path — and the per-event log
captured the whole failure, the exact killed-run record M2.3's logging change exists for. Fixed
by restoring the constant; the lesson is the same one M2.3 learned: self-checks green ≠ the job
entry point exercised. The live run is the check.

---

## Experiment E002b — full-profile confirmation IC sweep (2026-09-25, profile `full`)

- **Why a new experiment:** E002 ran on `quick` (11 decision months, one regime) and its own
  row pre-registered that the full sweep "is NOT pre-registered here". Running more data
  through the same code after seeing quick results would be post-hoc; `E002b`'s hypothesis
  (written before the run) fixes the method instead: **mean monthly Spearman IC with a
  one-sample t-test across months** — month fixed effects removed by construction, closing
  the pooled-ranks fragility E002's verdict itself flagged. E002 is frozen and unedited.
- **Run:** full-profile derived chain rebuilt through its real entry points (panels 5.7s,
  rank 6.2s, eligible 8.0s, winners 8.3s, feature_panel 59.0s, feature_matrix 0.9s → 218,648
  rows × 183 decision months), then `experiments/002b_ic_sweep_full/run.py --profile full` —
  22 features, **178,171 labeled rows / 181 measured months**, cutoff 2026-09-24. All mean
  monthly ICs, t/p values, BH flags, pooled-raw-IC continuity columns and the regime/bucket
  splits are in `experiments/002b_ic_sweep_full/results.json`.
- **Verdict: CONFIRMED, with one major reversal** (details in the ledger row and
  `verdict.md`):
  - `mom_12m_1m` +0.052 (p = 1.1e-6, BH ✓, 64% of months) and `mom_6m` +0.024 (BH ✓) — the
    momentum prior survives 15 years, and it is counter-cyclical: down-months +0.099
    (75% of 69) vs up-months +0.023 (n.s.).
  - **The delivery family is confirmed at full history** — `delivery_pct` +0.049
    (t = 7.2, p = 1.2e-11, 72% of months), trend +0.023, z-score +0.017 (all BH ✓). E002's
    quick-profile rejection was a bull-window artifact: delivery IC is +0.087 in down-months
    (87%) vs +0.026 in up-months. The two experiments deliberately disagree; E002b is the
    citation.
  - `atr_ratio` is a **regime-flipping** feature: +0.045 in up-months (matches E001's
    quick-window anatomy) and **−0.183 in down-months** (94% of 67, p = 7e-19). Low-vol is a
    crash factor, not an all-weather one. Five candle/accumulation features (up-down ratio,
    breakout, close_in_range, higher-lows, big-body) are BH-rejected on direction at full
    history.
- **Bucket attribution:** the confirmed features price the whole universe (mom_12m_1m
  0.038/0.049/0.052, delivery_pct 0.047/0.059/0.054 across top200/201–600/601–1500) — 15
  years overrules E001's quick-window impression that momentum dies in the small-cap tail.
- **Method note:** the first run of the splits counted month×bucket cells as months
  (336+207 = 543 "months", p-values anti-conservative); caught by the months-not-summing
  sanity check and fixed before any verdict was written — regime stats now use one IC per
  month over the full cross-section (112 + 69 = 181).
- **Consequence for the plan:** Phase 4's composite candidates are `mom_12m_1m` (+),
  `mom_6m` (+), `delivery_pct` (+), with `atr_ratio` as a regime-conditional overlay; the
  delivery features are correlated (one family = one vote). E002's verdict stands as
  written; its "delivery falsified" claim is superseded by this row, and the status line at
  the top of this plan is updated accordingly.

---

## Experiment E000 — universe overlap (2026-09-25, profile `full`)

- **Source decision (settled pre-run, recorded in `hypothesis.md`):** historical Nifty 200
  membership has no clean source (yfiua.github.io does not carry NIFTY200; index-report
  scraping is a plan non-goal), so E000 ran on the **current** constituents CSV
  (`data/index/ind_nifty200list.csv`, 200 validated symbols, hand-downloaded from
  `nsearchives.nseindia.com` — the same trust-boundary pattern as the surveillance snapshot)
  applied as-of to every year, with the survivorship bias disclosed and its direction argued
  (it understates overlap → conservative for the verdict that matters).
- **Run:** `experiments/000_universe_overlap/run.py --profile full` — 15 December decision
  years, per-year overlap from `universe_rank` and hit-rate delta from `eligible`/`winners`
  with the forward label. All counts in `results.json`.
- **Verdict: REJECTED on the letter of the pre-registered rule, noise-bound in substance**
  (details in the ledger row and `verdict.md`):
  - overlap: **min 97.7% / mean 98.7%** — the top-1500 as-of universe contains the Nifty 200
    in every year; index membership is never needed on the critical path.
  - hit-rate delta: mean yearly |Δ| 2.48pp fired the ≥ 2pp trigger; at ~130 labeled N200
    names/year the binomial noise floor is ±1.91pp, and the **pooled** |Δ| (not the
    pre-registered trigger, reported as the tiebreaker) is **0.86pp** (5.04% vs 4.17%, 741 vs
    94 winners) with noise sd 0.46pp — small, likely real, immaterial.
  - recommendation to the BRD owner: keep top-1500; N200-only would discard ~85% of labeled
    rows for ~0.9pp of hit rate within yearly noise.
- **Honest caveats:** early-year N200 rows are the least trustworthy (today's list applied
  as-of; 71/200 names did not exist by end-2011); 2011's 0/123 N200 hit rate is the noise
  floor, not a finding; the pooled 2σ significance was not family-corrected.
- **Method note:** the survivorship-drift column was initially computed from the trading
  subset (structurally zero — a mislabeled denominator). Caught on the live run and fixed
  before the verdict: `not_ever_traded_by_year_end` now reads the snapshot directly.

---

## Experiment P4.1 — composite score v0 (2026-09-25, profile `full`)

- **Universe decision implemented:** as-of top-1500, turnover floor OFF — the top-1500 /
  floor-off default from `docs/brd_decisions_universe.md`, flagged BRD-owner-review-pending
  in the pre-registration. (The full-profile feature matrix had been left at the quick
  profile by the selfcheck suite's rebuilds; the chain was rebuilt through its real entry
  points before the run — 218,648 rows × 183 months, 47.7s.)
- **Prediction (pre-registered in `experiments/004_composite_v0/hypothesis.md`, written
  before the run):** the rank-average composite of the E002b survivors
  (`mom_12m_1m`, `mom_6m`, `delivery_pct`; equal weights, parameter-free) beats the best
  single feature on the pre-test-window validation slice (paired monthly t, α = 0.05); the
  atr-regime overlay is additive on the same test. The comparator is selected ON the slice
  (winner's curse included) — the conservative form of BRD M3's bar. The test window (last
  36 months, BRD §10.1; boundary 2023-09-24) is excluded and not scored.
- **Run:** `experiments/004_composite_v0/run.py --profile full` — validation slice
  **145 decision months / 132,530 labeled rows** (2011-07 → 2023-08), 35 test-window months
  excluded. All arm ICs, paired tests and precisions in `results.json`.
- **Verdict: INCONCLUSIVE — mom_12m_1m ships as v0** (details in the ledger row and
  `verdict.md`):
  - composite **0.0625** vs best single (mom_12m_1m) **0.0529** mean monthly IC; paired diff
    +0.0096, t = 1.91, **p = 0.0585** — the point estimate wins, the pre-registered α does
    not clear, and the tie rule (⇒ simpler ships) applies as written.
  - atr overlay **rejected**: 0.0223 vs 0.0625 (diff −0.0390, p = 0.0033) — E002b's
    regime flip is real in cross-section but the pre-registered trailing-market proxy
    dilutes the composite instead of capturing it. A real regime classifier remains an open,
    separately-pre-registrable idea.
  - top-5% precision on the slice: composite 55.4% > overlay 53.2% > single 53.0% — the
    composite's edge concentrates in the picked tail.
- **Consequence for the plan:** 4.1 ships the single feature; 4.2 (learned ranker) proceeds
  against the unchanged gate ("beats best single feature out-of-sample"), with the honest
  reference number to justify complexity being the composite's 0.0625. The walk-forward
  (Phase 6) remains the only result that counts (BRD §10).
- **Honest caveats:** p = 0.0585 is a near-miss recorded as a near-miss; the comparator's
  0.0529 carries its own winner's curse; nothing here predicts the Phase 6 test window.

---

## Experiment P4.1b — two-feature composite (2026-09-25, profile `full`)

- **Why:** P4.1's verdict flagged `mom_6m` as the weakest third vote (slice IC 0.0276 vs its
  siblings' 0.0529/0.0445) and asked, pre-registered, whether dropping it lets the composite
  clear the M3 bar the three-feature form missed (p = 0.0585).
- **Prediction (pre-registered in `experiments/004b_composite_2feat/hypothesis.md`, before
  the run):** `composite_2f` (mean percentile rank of `mom_12m_1m` + `delivery_pct`) vs the
  slice-selected best single (paired monthly t, α = 0.05) — same gate, same slice, P4.1's
  three-feature form recomputed as the within-experiment control.
- **Run:** `experiments/004b_composite_2feat/run.py --profile full` — reuses P4.1's slice and
  scoring code by importlib (the two experiments cannot drift); asserts the full-history
  matrix before scoring (145 months / 132,530 rows, boundary 2023-09-24; 35 test-window
  months excluded, untouched).
- **Verdict: CONFIRMED — `composite_2f` ships as Phase 4's v0** (details in the ledger row
  and `verdict.md`):
  - vs best single (mom_12m_1m, winner's curse included): 0.0681 vs 0.0529, paired diff
    **+0.0153**, t = 2.49, **p = 0.0140** — the gate clears.
  - vs the 3f control: +0.0057 (p = 0.196) — `mom_6m` was dead weight, not poison; the form
    wins by being simpler and no worse.
  - precision flip disclosed: top-5% slice precision prefers 3f (55.4%) to 2f (54.8%); mean
    monthly IC was the pre-registered primary, and the flip is recorded, not hidden.
- **Consequence for the plan:** the shipped v0 score is the two-feature composite; 4.2's
  ranker must beat it at the same gate (reference number 0.0681); task 4.3's freeze protocol
  applies to the two-feature definition. Phase 6 re-tests it out-of-sample — the only result
  that counts (BRD §10).
- **Honest caveats:** post-hoc refinement after P4.1 (pre-registration is the only
  protection); shared slice with P4.1, family error unadjusted by pre-registration as
  declared; the comparator's 0.0529 is itself winner's-curse-optimistic.

---

## Experiment P4.2 — learned ranker (2026-09-25, profile `full`)

- **Prediction (pre-registered in `experiments/0042_learned_ranker/hypothesis.md`, before
  the run):** a HistGradientBoosting ranker, refit walk-forward monthly (fixed
  hyperparameters, never swept; all 22 E002 features; 1-month purge by label end; ≥ 24
  training months before the first fold), beats `composite_2f` on the paired monthly IC
  test at α = 0.05 — and the 4.3 freeze protocol reproduces its picks exactly.
- **Run:** `experiments/0042_learned_ranker/run.py --profile full` — **120 walk-forward
  fits** over the 145 validation months (25 warm-up months scored for the baseline only),
  ~130k training rows per late fold, boundary 2023-09-24, test window untouched.
- **Verdict: REJECTED — composite_2f ships** (details in the ledger row and `verdict.md`):
  - ranker **0.0402** vs composite_2f **0.0681** mean monthly IC; paired diff **−0.0221**
    over the 120 shared months, t = −2.45, **p = 0.0159** — significantly worse, a clear
    loss, not a tie. All-features rope + squared-error-on-raw-returns grabs noise the
    two-feature blindness avoids; the plan's gate design (composite first) did its job.
  - **Freeze protocol (4.3) passed inside the run:** `artifact/model_meta.json`
    (hyperparameters, feature list, sklearn version, seed, 120-fold manifest); first and
    last scored folds refit **bit-identically** (max |diff| 0.00e+00); the last fold's
    top-5% pick set reproduces exactly from a fresh refit; the artifact fold count
    round-trips. Re-running with saved artifacts reproduces picks — the plan's done-when.
- **Consequence for the plan:** Phase 4's model is `composite_2f`; Phase 6 walks it
  forward. sklearn enters `requirements.txt` with the justification the plan demands
  (no lightgbm; NaN-native matching the panel's missing-data semantics; deterministic under
  a fixed seed with early stopping off) — earned by the experiment even though the model
  lost, as the Phase 6 harness may need it for diagnostics.
- **Honest caveats:** hyperparameters were fixed a priori — a tuned ranker might close the
  gap, and that is a future pre-registration, not a loophole pulled now; the paired test
  uses the 120 shared months (warm-up excluded for the ranker arm); the gate is the
  validation slice only — BRD §10's walk-forward on the test window remains the only result
  that counts.

---

## Experiment E006 — cost sensitivity (2026-09-25, profile `full`)

- **Prediction (pre-registered in `experiments/006_cost_sensitivity/hypothesis.md`, before
  the run):** per plan 4.4 and the ledger row — the net edge at 0.2% per side does not
  survive 1.0% for picks ranked below ~600 (BRD §9.7). Rule: >600 edge halves by 1.0% ⇒
  partial; turns negative or below 25% parity ⇒ confirmed; survives ≥ 50% ⇒ rejected.
- **Run:** `experiments/006_cost_sensitivity.run --profile full` — composite_2f's top-5%
  picks (6,622 pick-months, 145 validation months, boundary 2023-09-24), net = gross −
  2 × cost at 0.2 / 0.5 / 1.0% per side, split by the §9.7 rank boundary (≤ 600 vs > 600)
  and by size bucket. Test window excluded as in P4.1/P4.1b/P4.2.
- **Verdict: REJECTED — the warning does not bind at equal fills** (details in the ledger
  row and `verdict.md`):
  - rank > 600: **3.34%** mean net per pick at 0.2% → **1.74%** at 1.0% = **52.1% of base**,
    above the ≥ 50% survival line, positive at every level, and the strongest group at every
    level (rank ≤ 600: 2.25% → 0.65%).
  - the small-cap tail is the cost-resilient group, not the victim — the gross edge there
    (3.34% vs 2.25%) is bigger than the added cost.
- **The caveat that still bites (recorded in the verdict):** the scan models cost as a
  uniform haircut on month-end closes; it cannot see impact, slippage, or non-fill — the
  actual mechanism behind §9.7's warning. Conclusion: at equal fills the small-cap edge
  survives 1% costs; **whether fills are equal is Phase 5's fill model's job to test** (T+1
  open, circuit locks, liquidity-aware slippage) before Phase 6 believes it.
- **Consequence for the plan:** the Phase 6 report's default cost assumption is set to
  **0.5% per side** (edge at 82% of base; 0.2% optimistic for a 601–1500-heavy pick set,
  1.0% survivable but halves the hit rate), with all three levels reported per §9.7.
- **Honest caveats:** pick-level means on a fixed top-5% slice ignore slot competition and
  capacity; month-end-close fills differ from the engine's T+1 open; validation slice only —
  Phase 6 re-asks this inside the real engine on the test window.

---

## Phase 5 checkpoint — engine + portfolio rules + toy momentum, end to end (2026-09-26, commit `d0125bf`)

Not an experiment — the plan's Phase 5 checkpoint line ("run engine on synthetic data with a
trivial buy momentum model. Show equity curve + trade log"). With 5.6 (bucket attribution)
landed the same day, all Phase 5 tasks (5.1–5.6) are done; this block records the integration
run the checkpoint asks to see: `src/backtest/checkpoint.py`, results in
`src/backtest/checkpoint_results.json` (config snapshot + git hash embedded).

### The tape (declared simplifications)

6 names × 19 sessions spanning 4 curve months (Jan–Apr 2026); every bar has **open == close**
so fill prices are exactly the marks; **zero costs and no ADV history** (the engine's gate and
impact are off) so every equity value is hand-computable to the rupee. Cost math is
engine-tested separately; E006's 0.5%/side default is a Phase 6 report parameter, not this
tape's job. n_slots = 2, start 100,000. The toy model scores each month as first-to-last
close return; the checkpoint's point is deterministic plumbing and exact paper math, not edge.

### The story — each §8 rule firing exactly once (all asserted)

1. **Jan 12, initial selection:** ME (+10%) and MO (+5%) lead the momentum board → top-2
   buys; T+1 fills land Feb 02 at the open (the month-boundary case).
2. **Feb 09, monthly review:** ME has faded to the 5th of 6 ranks (0.667 > the 0.25 sell
   percentile) → sell; MB (+7.9%, rank 0) is the only candidate inside the 15% replace
   percentile → replacement buy (221 sh @ 218), fills Mar 02.
3. **Mar 04, Trigger B stop:** MO closes 96.0 ≤ its 96.6 stop (entry 105 × 0.92; the 12%
   trail from the 110 month-high sits at 96.8 — the stop wins by trigger_b's priority order)
   → mid-month sell, fills Mar 05. The one churn event.
4. **Mar 09, review with a cash slot:** MO's freed slot finds no candidate inside the top
   15% (MB is held; every other name ranks 1/6 or worse) → the slot **holds cash** (§8.1
   fallback). ME is already out (its round trip completed Mar 02).

Trigger A and C never fire on this tape (the monthly momentum spread stays under the 20%
relative excess) — both are unit-tested in `src.backtest.portfolio`'s own check.

### Equity curve (19 rows, asserted exact)

```
date          cash   market_value    equity
2026-01-05  100000             0    100000   (…flat through 01-12: capital uninvested)
2026-02-02      25         99975    100000   T+1 fills: ME 909 @ 55, MO 476 @ 105
2026-02-03      25        100451    100476
2026-02-04      25        100018    100043
2026-02-05      25        100494    100519
2026-02-06      25        100061    100086
2026-02-09      25        100537    100562
2026-03-02      24        100538    100562   fills: ME -909 @ 53, MB 221 @ 218
2026-03-03      24         95999     96023   MO gaps down
2026-03-04      24         94316     94340   close 96 <= stop 96.6 -> Trigger B
2026-03-05   45244         48841     94085   MO -476 @ 95 fills
2026-03-06   45244         49062     94306
2026-03-09   45244         49283     94527
2026-04-01   45244         49283     94527
```

### Trade log (5 fills, asserted exact, engine order = (date, symbol, qty))

```
signal 2026-01-12  fill 2026-02-02  ME   909 @ 55.00  select_momentum
signal 2026-01-12  fill 2026-02-02  MO   476 @ 105.00 select_momentum
signal 2026-02-09  fill 2026-03-02  MB   221 @ 218.00 replace
signal 2026-02-09  fill 2026-03-02  ME  -909 @ 53.00  monthly_review
signal 2026-03-04  fill 2026-03-05  MO  -476 @ 95.00  trigger_b_stop
```

### Paper math (how every number above is derived)

- **Sizing:** 50,000/slot → ME 909 = floor(50,000/55) costing 49,995, MO 476 =
  floor(50,000/105) costing 49,980 → cash 25.0. (The first paper draft said 486 MO shares —
  486 × 105 = 51,030 overdraws the slot; the assert caught the arithmetic, floor is the rule.)
- **Replacement sizing:** the Feb 09 buy is sized on cash + expected sell proceeds
  (25 + 909 × 53 = 48,202 → 221 = floor(48,202/218)); it fills at exactly 218 because the
  tape pins MB's Feb 09 close to its Mar 02 open — on real data the est and the fill price
  diverge and the engine's cash guard (never negative) is what binds.
- **State moves twice, on purpose:** sell decisions free portfolio slots at decision time
  (portfolio.py's contract) while cash/positions move at the T+1 fill — the Mar 02 fills
  settle both the ME sale and the MB buy on one session.
- **P&L at Apr 01:** ME −1,818 realized (909 × (53−55)), MO −4,760 realized (476 × (95−105)),
  MB +1,105 open (221 × (223−218)); sum −5,473 = final equity 94,527 − 100,000, with cash
  45,244 + MB mark 49,283. The tape is hostile on purpose: both completed picks are losers,
  and the asserts still hold to the rupee.
- **Churn:** 1 mid-month sell / 4 curve months = 0.25/month (< the 1.5 §8.3 flag). (First
  draft divided by 12 sessions; the metric's window is curve months — caught by the assert.)

### Bucket attribution on the checkpoint's own picks (task 5.6, review gates enforced)

```
201-600   picks 1   hit  0%   mean  -3.64%   churn/mo 0.00    (ME: Jan decision)
top200    picks 1   hit  0%   mean  -9.52%   churn/mo 0.25    (MO: Jan decision)
blended   picks 2   hit  0%   mean  -6.58%   churn/mo 0.25
```

601–1500 is absent: MB is still open, and the table only counts completed round trips.
Buckets are **as-of the decision month** — this checkpoint drove the fix that makes that
true: `TradeEvent` now carries `signal_month`, because a month-end signal fills in the next
month and attribution keyed on the fill month would file Jan's picks under February.

### What the checkpoint caught

- the real `signal_month` provenance fix above (a genuine attribution bug, not a tape quirk);
- two paper errors of the author's own (486-vs-476 share sizing; churn window in sessions
  vs months) — the asserts did their job, which is the point of asserting hand-computed
  values rather than re-deriving them in code.

### Honest caveats

1. Zero costs / no ADV gate are declared simplifications (see The tape); a real run adds
   E006's 0.5%/side, impact, and non-fills — the fill model remains the open question.
2. The toy momentum model is not composite_2f; Phase 6 wires the real model to real data.
   Nothing here predicts the test window — BRD §10's walk-forward stays the only result
   that counts.
3. Trigger A/C and the delisting/suspension paths are unexercised on this tape (unit-tested
   in their own modules); a tape that fires them end to end remains possible future work.
4. Determinism is asserted by running the checkpoint twice and comparing curve, trade log
   and decisions bit-for-bit; the run is 0.1s and registered as selfcheck
   `backtest.checkpoint` — suite **ALL PASS (23 checks)** after this block.

---

## Phase 5→6 smoke — composite_2f through the real engine on real data (2026-09-26, commit `af68a4c`)

Not an experiment — the bridge between Phase 5's synthetic checkpoints and Phase 6's harness:
`src/backtest/smoke_e2e.py` runs the shipped model's top-5% picks through the REAL
Market/Facts/Portfolio/Engine stack on the full-profile database (chain restored first via
its real entry points, commit `af060c8`: 218,648 rows × 183 months, labeled 178,171/181 —
E002b's numbers exactly). Results in `runs/smoke_e2e/smoke_results.json` (gitignored;
regenerate with `python -m src.backtest.smoke_e2e`, 6s). Deliberately **not** registered in
the selfcheck suite — it asserts on the full-profile matrix, which the suite's own rebuilds
reset to quick; the suite stays 23/23 unchanged.

### Light pass — the pick pipeline reproduces, except where it should not

All 145 validation slice months scored with P4.1b's `score_month_2f` (importlib, no drift):
**6,622 pick-months — exactly E006's count**, and the tie-stable cross-check the smoke
really exists for: the slice's **mean monthly IC = 0.0681243229, bit-identical to P4.1b's
frozen value to 1e-9**. The scoring pipeline is stable across table rebuilds. Bucket split
of picks (net at 0.2%/side): top200 221 / 59.3% hit / +2.60%; 201-600 1,562 / 53.8% /
+2.18%; 601-1500 4,839 / 52.2% / +3.34% — E006's committed table.

### Finding 1 — E006's pick sets are row-order-fragile at score ties

E006's *pick mean* does not reproduce to the float on today's rebuilt tables (delta
−1.02e-4 for the smoke's tie-broken picks, −1.09e-4 for E006's own code re-run — both within
the smoke's 5e-4 tolerance). Root cause, isolated before any conclusion was written:
**21 of 145 slice months have an exact composite_2f score tie crossing the top-5% boundary**, and
E006's `sorted(scored, key=-score)` breaks those ties by physical row order — a table rebuild
reorders tied rows, swapping boundary names. The frozen `results.json` remains the verdict's
evidence (its config/git snapshot is intact); the honest reading is that its pick-level means
carry a ±~1e-4 row-order band. **Consequence — the Phase 6 tie-break contract:** every
harness pick list is top-5% by composite_2f with **ties broken by symbol** (the contract
`src/backtest/audit.py` already uses), so no Phase 6 number depends on row order.

### Finding 2 — the fill gate vetoes exits: SOLARINDS, 8 consecutive reviews

The engine pass drives 12 consecutive slice months (2011-07→2012-06) of real bars through
the stack: 44 fills, 10 non-fills (all `non_fill_adv`), 16 completed FIFO picks (25% hit —
a hostile 2011-12 tape), churn 1.25/mo, final equity 1,022,878 (+2.29%; plumbing evidence,
not a result). The structural finding: **§9's ADV gate applies to sells too — 8 of the pass's
18 exit attempt-months were refused, all of them one position (SOLARINDS) re-refused at 8
consecutive monthly reviews (2011-09→2012-04)**. The slot froze (its month's replacement buy
skipped 8×, contingency semantics, logged), the §8.2 stop machinery had no exit path, and the
forced hold happened to close at **+19.59%** — the pass's best pick, on the name the strategy
tried hardest to leave: luck, not design. The pick set skews 601–1500 (4,839 of 6,622
pick-months), exactly where the gate bites. Handed to the BRD owner as **Decision 3** in
`docs/brd_decisions_universe.md` (stuck-and-retried / force-exit / escalate-after-N;
recommendation: escalate at N = 2 with uncapped reported impact) — **blocks 6.4**, since
drawdown, churn and turnover all move with the choice. Current behaviour stays
BRD-normative until decided, per the Decision-2 pattern.

The choice is now **implemented behind `backtest.exit_gate`** (commit `bfd0572`; Decision 3
doc updated to match): `stuck` is the shipped default and the run above; `escalate`
(N = 2) force-fills an exit refused at N consecutive reviews (`Fill.forced`, impact
capped at `min(coef·ratio, 1.0)`, reported in `forced_exits`). Same 12-month tape, one run
per mode in a single smoke invocation — the artifact now carries both side by side
(`engine_passes` in `runs/smoke_e2e/smoke_results.json`, gitignored; regenerate with
`python -m src.backtest.smoke_e2e`, ~9s):

| engine-pass metric | stuck (default) | escalate (N = 2) |
|---|---|---|
| non-fills | 10 | 4 |
| sell non-fills / stuck sell-months | 8 / 8 (SOLARINDS re-refused 8 reviews) | 2 / 2 |
| forced exits | 0 | 1 (SOLARINDS 2011-11, 1.42% reported impact) |
| replacement buys skipped (no slot) | 8 | 2 |
| completed picks | 16 | 20 |
| final equity | 1,022,878 (+2.29%) | +3.92% |

SOLARINDS exits ~7 months earlier (refused Sep + Oct, force-filled at the Nov review's
T+1) instead of riding the lucky +19.59% hold — the equity delta is plumbing, not alpha.
(An earlier hand-run logged 2 forced exits; the persisted artifact — the regenerable
evidence — shows 1, and the table above is corrected to it.) `force` mode is unit-tested
but not run on this tape. Neither run is a return claim (caveat 1); the owner still picks
the mode for 6.4.

### What the smoke itself caught (bugs the asserts fixed)

- `TradeEvent.qty` was passed unsigned in the smoke — sells disguised as buys, FIFO never
  closed a round trip; `completed_picks` returned 0 and the bucket gate failed loudly.
- Bucket attribution keys on the **decision month** (`signal_month`), not the fill month —
  the same fix the Phase 5 checkpoint drove, re-proven necessary on real data (a Jul 29
  signal fills in August).
- Two smoke-only wiring bugs (an int where a list belonged; the bucket map keyed on
  `mdate` vs `YYYY-MM`).

### Honest caveats

1. The smoke is a 12-month plumbing bridge: monthly-cadence rules only (no mid-month Trigger
   A/B checks, no delivery-z clause, no surveillance — nothing historical exists to load),
   50-close DMA window inside the month, engine costs at config's 0.20%/side with capped
   impact on real ADV. None of it is a return claim; 6.4 produces the first claim.
2. Blocked-sell re-owning and contingent-buy skipping are the smoke's declared stopgaps
   pending Decision 3 — they are logged in `smoke_results.json` (`sell_nonfills`,
   `buys_skipped_no_slot`), not hidden.
3. E006's frozen artifacts are point-in-time row-order evidence for its pick-level means
   (Finding 1); its verdict direction rests on the rank-group pattern, which the smoke
   reproduces at every cost level's sign and ordering.

---

## Fix pass — Phase 3-6 review items implemented / dispositions recorded (2026-09-26, uncommitted; working tree on `a8cc624`)

Not an experiment - the engineering pass over `fixissues_phase36.md` (the Kailash Nadh
review). Fixes that were code landed in code; fixes that need a BRD-owner decision, data
the repo does not have, or a pre-registered run are recorded as constraints here and in
BRD.md rather than half-implemented. What moved:

| Review item | Disposition | Where |
|---|---|---|
| 4.1 `Portfolio._replace` emits a buy for every top-15% candidate (loop never mutated `self.slots`) | **FIXED** - bounded by free slots + sells already emitted in the decision batch (the doc's own fix, `count(None)`, was the mirror bug: it would emit ZERO buys for the standard fully-invested sell-then-replace flow, since sells fill at T+1) | `src/backtest/portfolio.py` + 2 new self-check cases |
| 4.2 circuit locks never marked from real data | **FIXED** - marked in the smoke's `_market`: fully frozen OHLC bar, or a gap-open >= 4.9% (either direction: locked-down bars block sells too) with turnover < 10% of trailing-20-session ADV. 2,537 locked bars across 4 stress windows (COVID month: 1,346). ponytail: NSE bands vary per stock (5/10/20%); the ADV collapse is the real signal | `src/backtest/smoke_e2e.py` |
| 4.3 exit gate `escalate` as default | **ADOPTED** - the Decision-3 recommendation, already implemented behind `backtest.exit_gate`; the config default flips stuck -> escalate | `config.yaml` |
| 4.6 cost default 0.20% | **ADOPTED** - E006 already set the Phase 6 default at 0.5%/side; config.yaml just never caught up. `dp_charge_per_exit` (Rs 15.93) NOT added: ~0.002% of a 10% slot, noise - folded into the 0.5% | `config.yaml` + new config invariant (default cost must be one of E006's sensitivity levels) |
| 3.1 model lives in `experiments/` behind importlib | **FIXED** - extracted to `src/model/composite.py`, with a self-check proving the scores are BIT-IDENTICAL to the frozen P4.1b implementation (the experiments stay frozen - editing them would orphan every committed `results.json`, BRD 12/13); smoke_e2e and audit now import the model, not the experiment; the 22-feature column map comes from `src.features.panel._FEATURES` (production-owned), with an assert pinning panel order == experiment order | `src/model/composite.py`, `smoke_e2e.py`, `audit.py` |
| 1 Rolling top-1000 universe (config-only, per the review) | **CONSTRAINT - NOT APPLIED** - the review calls it a one-line change; it is not. Every experiment's evidence (E000, E002b, P4.1, P4.1b, P4.2, E006) is measured on top-1500; silently re-cutting the universe invalidates all of them (E002b's strongest ICs live in the 601-1500 bucket, exactly the ranks 1001-1500 being cut). Needs: the config change + `src/config.py`'s BRD invariant (`top_n == 1500`) + `size_buckets` labels + a full experiment re-run + a ledger row. Correctly a pre-registered experiment (E007), and correctly the BRD owner's call - it trades measured edge for a liquidity thesis | BRD.md 4 amendment note |
| 2.2 market regime filter (Nifty 200 vs 200-DMA + VIX) | **CONSTRAINT - NOT IMPLEMENTED** - three blockers: (a) no index or VIX series in the repo (BRD 5's free-data list has none; D4 exists for E000's overlap reference only); (b) P4.1 ALREADY pre-registered and tested a regime overlay and REJECTED it (diluted the composite, p = 0.0033) - the burden is on a better classifier, which means a new pre-registration, not a config flip; (c) point-in-time index membership has no clean free source (E000's caveat: today's list applied as-of is survivorship-biased). The regime QUESTION stays open via the per-regime reporting BRD already mandates (11). (2026-09-27: blocker (a) is dead for the index leg - daily NIFTY 200 TRI is now in-repo and E013 measured the filter itself on the realized window: it improves the window on all three pre-registered bars but is NOT adopted - test-window burn + small-sample attribution; see the E013 block.) | BRD.md 15 risks + LEDGER P4.1 row |
| 3.2 sector cap (max 2 per sector) | **CONSTRAINT - NOT IMPLEMENTED** - no sector/industry metadata exists in the repo for any year; point-in-time classifications (today's index/industry lists applied as-of) are survivorship-biased for a 15-year backtest, and BRD 5 lists no such source. Add the feed first (or pre-register a correlation-cluster cap as the proxy), then the rule is a ~10-line portfolio change | BRD.md 15 risks |
| 4.4 ATR-based stops replacing the 8% stop | **CONSTRAINT - NOT IMPLEMENTED** - a cross-sectional risk model change: it changes every drawdown, churn and turnover number the walk-forward will report, and BRD 8's preamble makes defaults pre-walk-forward re-tuning on pre-test-window data ONLY. Bundling it with the slot expansion (4.5) would make the two changes unattributable. Sequenced behind the 6.1 harness as pre-registered arms | BRD.md 8 note |
| 4.5 8-10 slots + volatility-inverse sizing | **CONSTRAINT - NOT IMPLEMENTED** - same class as 4.4 (BRD 2/7 fixes 4 slots in the design; changing it is a strategy redefinition, not a parameter tweak), plus a real cost: 8-10 names in the 601-1500 bucket against a 0.05 ADV gate means materially more non-fills and resize events - the very mechanism E006 showed dominates. To be tested as its own pre-registered arm, not adopted silently | BRD.md 8 note |
| 5.2 TRI benchmarks (Nifty 500 TRI / Smallcap 250 TRI) | **CONSTRAINT - PARTIALLY BLOCKED** - no TRI series in the repo and none freely downloadable; yfinance adjusted closes ARE dividend-adjusted, so a liquidity-weighted universe TRI can be built from `adj_close` for free (honest caveat: it inherits adj_close's own coverage caveats - M2.2's 26% delisted-symbol hole). Nifty 50/200 price or TRI can be added as reference series when needed | BRD.md 11 amendment note |
| 5.1 walk-forward harness | **NOT STARTED (by design)** - 6.1 is Phase 6's own task; the review's purge/rolling-window spec matches BRD 10 exactly. The smoke's monthly loop is the harness's 80% and gets promoted, not rewritten, when 6.1 starts | - |

**Equivalence evidence.** The model extraction is behavior-preserving by construction and
by measurement: the smoke's light pass still reproduces E006's 6,622 pick-months and the
frozen P4.1b IC (0.0681243229) bit-for-bit, and the stuck/escalate engine-pass table
regenerates the LEDGER's committed numbers exactly (stuck 44 fills / +2.29% / 16 picks;
escalate 1 forced exit / +3.92% / 20 picks). The `_replace` fix DOES change downstream
numbers in principle (it changes which orders exist); on this smoke tape the difference
is invisible because a fully-invested month whose sell fills lands its replacement in the
same batch - the new bound admits the buys the old loop already (wrongly) admitted; the
regression cases added to portfolio's self-check pin the corrected behavior directly.

---

---

## Experiment E007 - universe cutoff: rolling top-1000 vs top-1500 (2026-09-26, profile `full`)

- **Why:** `fixissues_phase36.md` (the Kailash Nadh review) recommends cutting the as-of
  universe from 1500 to a rolling 1000 to remove an "illiquidity graveyard" (ranks
  1001-1500). The BRD amendment of the same day made this the required pre-registered
  experiment before any re-cut. Hypothesis written before the run; the decision rule is
  the cut's burden of proof: B's mean monthly IC higher at paired t >= 2 AND materially
  less engine-pass gate stress, else keep 1500.
- **Run:** `experiments/007_universe_cutoff/run.py --profile full` - both arms rebuild
  the real derived chain (rank -> eligibility -> winners -> feature_panel -> feature_matrix)
  with ONLY `universe.top_n` overridden in memory; scored with the shipped
  `src.model.composite`; engine pass through smoke_e2e's own machinery at the shipped
  defaults (escalate N=2, 0.5%/side). Arm order A(1500) -> B(1000) -> A-again(restore);
  the restore reproduced arm A bit-for-bit (IC 0.068124..., 6,622 picks, identical shape)
  - zero drift, the database is left BRD-normative at top-1500.
- **Verdict: REJECTED - keep top-1500** (details in the ledger row and `verdict.md`):
  - IC: 0.0695 (B) vs 0.0681 (A), paired diff +0.0014, **t = -0.57, p = 0.57** over 145
    shared months - indistinguishable from noise, nowhere near the pre-registered bar.
  - precision 54.6% -> 55.6% (+1.0pp) bought with **-57,226 eligible symbol-months
    (-26%) of labeled evidence** - the 601-1500 bucket E002b measured its strongest ICs in.
  - the graveyard claim, tested: rank-1000 boundary turns over Rs 4.12cr/day vs Rs 1.36cr
    at rank-1500, yet the below-Rs-5cr/day share of eligible symbol-months falls only
    **62.8% -> 50.1%** - half the top-1000 STILL trades under Rs 5cr/day. Illiquidity is
    the whole small/mid tail, not a 1001-1500 island; the cut does not buy tradability.
  - engine pass (12 slice months, escalate): non-fills 4 -> 3, forced exits 1 -> 1,
    churn 1.58 -> 1.75/mo, tape return +3.92% -> +2.38% - marginal to worse.
- **Honest caveats:** (1) the below-5cr share here is pooled over the full history
  (183 decision months) - do not reconcile it with Phase 2's 30.8% quick-profile figure;
  early-year rupee turnover was much smaller, which is exactly why the share is higher
  pooled, and why a nominal turnover floor is era-dependent. (2) The engine pass is the
  smoke's 12-month plumbing scale - a direction check on gate stress, not a return claim;
  the pick-level mean return uses month-end close fills (the light-pass convention).
  (3) The paired test's power is monthly (145 obs), not pick-level (5,047-6,622); a
  sub-0.02 IC difference per month cannot be resolved at this sample size - the verdict
  rests on the burden of proof being unmet, not on proven equivalence.
- **Consequence for the plan:** `universe.top_n: 1500` stands with measured negative
  evidence attached; the config invariant stays; any future re-cut starts from this row,
  not from the review's thesis.

---

---

## Experiment E008a - own-data market breadth as a regime gauge: the premise test (2026-09-26, profile `full`)

- **Why:** the fixissues_phase36 follow-up proposed replacing the blocked external
  index/VIX regime filter with market breadth computed from the repo's own data (share of
  the as-of top-200 above their 200-day DMA; go to cash below 40%). The regime overlay
  itself was already rejected once (P4.1); this experiment pre-tests the PREMISE - low
  breadth must predict losing pick-months - before any portfolio rule is wired.
- **Construction (pre-registered):** `market_breadth` table, one row per decision date:
  as-of membership from universe_rank (top-200 and 201-1000 tiers, E000's no-static-list
  rule), 200-TRADING-PRINT adjusted-close DMA per symbol (dense calendar; raw prices
  would break at splits), symbols with <200 prints not counted (denominator shrinks,
  never votes "below"). 179 breadth months from 2011-10; 141 joined with the validation
  slice. A first run reported 141/141 months "below 30%": the member-level sanity layer
  caught an aggregate bug (tier FILTER on the count but not the avg - each tier's share
  was diluted by the other tier's rows, 74.7% real reported as 15.2%). Fixed, re-verified
  member-by-member, and the sanity layer is the reason the premise test is trustworthy.
- **Gauge validation:** blue chips above DMA through the 2017 bull, below in the 2020
  crash; the known stress months read correctly at the top-200 tier - 2018-09 30.7%,
  2018-10 28.8%, 2020-03 15.5%. The mid tier (201-1000) is nearly redundant (rho 0.939;
  19/141 month disagreements at the 30 line).
- **Verdict: REJECTED - the premise fails, and the failure is informative** (details in
  the ledger row and `verdict.md`):
  - rho(breadth, next-month pick return) = +0.144 - below the pre-registered 0.15 bar.
  - The deep-trough months (<30: Dec-2011, Feb-2016, Mar-2020, Jun-2022, Feb-2025) are
    the BEST pick months in the sample: +10.70% vs +3.28%, hit 82% vs 54%. Breadth
    troughs mark bottoms; the following month rebounds. A cash gate on those states sits
    out the best re-entry months of the entire 15-year sample.
  - The only supportive window is 40-50 (-1.8pp pick penalty, near-zero universe
    penalty), inverting at 40 and reversing at 30 - a regime correlation, not a gate.
  - Whipsaw was never the issue (1.0-2.3 flips/yr); the timing is. A monthly decision-date
    gate evaluates breadth AFTER the crash prints and is paid the rebound: structurally
    mistimed for crash avoidance at this cadence.
- **Consequence for the plan:** NO monthly breadth gate anywhere in the portfolio rules
  or the walk-forward; `market_breadth` is kept as a derived table for BRD 11's
  per-regime reporting (which previously had no classifier to split on) - the gate
  question is closed with evidence, not lore. If the regime idea lives on, it lives
  INTRA-MONTH (weekly/daily breadth against the Trigger-B layer, where protection is
  actually timed) as a separate pre-registration.

---

## Experiment E008b - intra-month breadth protection on the Trigger-B layer (2026-09-26, profile `full`)

- **Why:** E008a rejected the monthly breadth gate because a decision-date cadence is
  structurally mistimed (it reads breadth after the crash prints and is paid the rebound)
  and left intra-month sampling as the one legitimate use. This experiment pre-tested that
  BEFORE any wiring: does a breadth-tightened mid-month trail cut drawdown in stress
  windows without giving back return?
- **Evaluation plan (decided pre-registration, the harness gap):** the Phase 6.1
  walk-forward harness does not exist yet, so E008b used an INTERIM evaluator - the
  smoke's proven engine layers extended to per-session Trigger-B checks and daily equity
  marks over fixed pre-named windows (W0 calm 2017-06..08, W1 midcap stress 2018-09..11,
  W2 crash+rebound 2020-02..04) - with the harness named as final judge. Even a full PASS
  would not have flipped the default.
- **Construction:** `market_breadth_daily` (3,675 sessions from 2011-10-20): as-of
  membership from the LATEST universe_rank snapshot <= D (session-by-snapshot join, not a
  static list), 200-trading-print adjusted-close DMA over a dense calendar, <200 prints =
  not counted, member join only (E008a's FILTER lesson). Sanity layer caught nothing this
  time because it was built in from the start: member-level Python recompute agreed to
  1e-6 at all three probe dates; the 2020-03 trough is visible intra-month (4.1% on Mar 23
  vs 15.5% at month-end - the information a monthly gate throws away); stress reads low
  (2018-09/10 avg 33.2% vs 2017 calm 78.9%).
- **Gate mechanics:** config-gated OFF (`trigger_b_breadth_trail_tighten: null`); when
  armed, the trail GIVEBACK shrinks by the tighten pp (12% -> 8%) - the pre-registration's
  "added to the trail" wording was corrected before any run (adding would LOOSEN the
  trail and worsen drawdown). Facts.breadth_pct None = gate inert, so checkpoint/smoke
  stay bit-identical; four new self-check cases (armed/inert/at-threshold/off).
- **Verdict: FAILED on the pre-registered rule** - criterion (a) (strictly lower max
  drawdown in both stress windows) unmet: maxDD identical to baseline in BOTH (W1 0.03%,
  W2 20.41%). The only gate fire of the experiment (HDFCBANK 2020-04-15, breadth 24%,
  threshold 40) is in the rebound, 16 days after the trough, and its T+1 fill lands
  outside the window - in-window equity identical to the rupee. The baseline stop/DMA/
  review clauses exit the crash names before breadth reads low; the tightened trail had
  nothing left to protect earlier. W0 curves bit-identical (no false fires).
- **Honest caveats:** (1) W1 degenerated into a cash book - the E006 fill model refused
  26/50 selection orders as non_fill_adv (the model's four TOP-SCORED names were
  untradable at Rs250k/slot), so the "stress window" tested nothing; the conclusion rests
  on W2 alone. (2) Fixed windows from an all-cash start, no delivery-z clause, monthly
  re-selection only - the interim evaluator produces a direction, not results; the 6.1
  harness remains the final judge. (3) One threshold family {30/40/50} at one tighten
  step (4pp), pre-registered, not swept - a FAIL at 4pp kills the idea rather than
  inviting a tuning hunt.
- **Consequence for the plan:** NO breadth gate at any cadence. The tighten key stays
  `null` in config.yaml (the wiring stays, default-inert and self-checked);
  `market_breadth_daily` joins `market_breadth` as a BRD 11 per-regime reporting table;
  the regime question (P4.1 overlay, E008a monthly gate, E008b intra-month gate) is now
  closed at all three decision layers with evidence. Any future attempt starts from this
  row, not from the thesis.

---


## Experiment E009 - fill-gate reachability: the paper edge was half unreachable (2026-09-26, profile `full`)

- **Why:** E008b's W1 window degenerated into a cash book - the E006 fill model refused
  26/50 selection orders as non_fill_adv because a Rs250k slot cannot enter a stock that
  trades under ~Rs0.5cr/day (notional > 5% x trailing-20 median turnover). The question:
  how much of the strategy's MEASURED pick return belongs to names that could not have
  been bought, and does ADV-aware eligibility fix it?
- **Construction:** `liq_daily20` (301,659 symbol-months): the median of each symbol's
  last 20 sessions ENDING at the market's last session strictly before D - a decision-date
  predictor cannot borrow the fill month's bars, so <20-print listings are conservatively
  unenterable at D. Sanity: frozen 2020-02 sample (1,136 eligible rows) committed beside
  results.json and re-verified row-for-row every run; member-level recompute clean over 6
  sampled dates (9,186 rows) after the comparator was fixed twice (anchor-session
  semantics; the full-window requirement the table had and the scan lacked - ADLABS,
  n20=17, listed Mar 2015).
- **R1 (measurement):** at Rs250k/pick: 38.8% of pick-months refused (3,413/8,802), 50.5%
  of gross return mass, top-decile-score refusal 46.6%. Refused picks returned +4.05% vs
  +2.52% fillable: the model's BEST picks are its most illiquid. Sensitivity: 29.4%/39.4%
  of mass at Rs125k; 49.6%/57.0% at Rs500k; 61.2%/68.0% at Rs1M. The reachability-
  corrected paper mean is +2.52% (-0.59pp), and the correction compounds with E006: what
  the gate protects is the expensive-to-exit tail.
- **R2 (the fix):** `universe.min_median_turnover_cr: 0.75` (the 0.5cr boundary x the
  measured med20/med3 shrinkage - declared by arithmetic, not fitted), through the REAL
  chain (E007._build_chain): eligible symbol-months 218,648 -> 144,059 (-34%); refusal at
  250k 38.8% -> 1.5%; corrected pick mean +2.52% -> +2.61%; IC 0.0675 vs 0.0681 (paired
  t = -0.12, nowhere near the -2 bar). All three pre-registered criteria met -> ADOPT.
  Zero-drift restore: IC bit-identical (delta 1.4e-17), R1 reproduced exactly.
- **W1 postscript (E008b caveat corrected):** at decision time 2018-09-28, LIQUIDETF
  (med20 Rs0.90cr) and SPLIL (Rs0.62cr) were ENTERABLE - only INFRABEES and GKWLIMITED
  were under the 0.5cr line. E008b's W1 refusal count was inflated by its evaluator: the
  smoke's month-window Market starves the trailing-20 ADV at a window's first bars (the
  first bar's 20-session median IS that bar). E008b's arm-vs-arm conclusion stands (both
  arms shared the tape); the episode goes in the ledger as a harness-design lesson: an
  ADV gate needs a warm window, and any per-window market must carry history into its
  first session.
- **Consequence:** config floor 0.0 -> 0.75 (this row cited); BRD S4 note records the
  closed question (the "subsumed by the top-1500 rank" premise is measured-false twice
  over: rank 1500 still trades Rs1.94cr/day AND illiquidity concentrates where the picks
  do). The engine's fill gate stays as the last-resort reality check. Caveat: the +2.5-2.6%
  numbers are pick-level, costless, equal-notional headlines - engine-level results remain
  the 6.1 harness's job. Re-open needs a named microstructure regime change, not tuning.

---


## Experiment E010 - E006's cost sensitivity on the post-E009 floor universe (2026-09-26, profile `full`)

- **Why:** E009 proved the pre-floor universe's paper picks were 38.8% unenterable at the
  shipped slot size - and the refused tail is where per-side costs are worst. E006's
  0.5%/side default was therefore calibrated on a portfolio the engine itself would not
  have built. E010 re-runs E006's protocol (imported module-to-module, no drift) with the
  universe as the ONLY change, and decomposes where the cost actually comes from.
- **Method:** two arms through the real chain (floor 0.75 = shipped; pre-floor 0.0 =
  rebuilt) + a zero-drift BACKWARD guard: the pre-floor arm must reproduce E006's
  committed results.json exactly (6,622 picks, means/hit-rates within the tie-swap
  tolerance, edge-halving None) before any comparison - the discipline E007/E009 applied
  to forward restores, pointed at a frozen prior experiment. Sanity: E009's synthetic
  fixture, its frozen-sample layer re-run on E010's own sample (the floor universe's
  2020-02 eligible set, 616 rows - distinct from E009's pre-floor 1,136 by design), and
  the member recompute (9,186 rows).
- **Findings:** floor arm (3,902 picks): all nets 2.36/1.76/0.76% at 0.2/0.5/1.0%; >600
  nets 2.49/1.89/0.89%. Impact decomposition at Rs250k/slot (min(1%, 0.10 x S/med20)):
  pre-floor picks average 0.565%/side modelled impact - almost exactly E006's flat 0.5%
  default; the floor-arm picks average 0.139% (median pick med20 Rs2.63cr; bands: <1cr
  0.376%, 1-5cr 0.130%, 5-20cr 0.030%, >=20cr 0.006%). The default was the impact of a
  paper portfolio the fill gate refuses to build; the tradable book's honest stack is
  flat real costs (~0.2-0.35%) + 0.14% impact = ~0.5%.
- **Verdict: KEEP 0.5%/side** (pre-registered rule: a PASS, b FAIL, c PASS, d PASS). The
  one failure is conservative and diagnostic: the >600 edge-halving point TIGHTENS on the
  tradable universe (pre-floor it survived 1.0% at 52.1% of base - padded by untradable
  gems; floor arm halves at 1.0%, 0.89% = 35.7% of 2.49%). E006's BRD 9.7 warning was
  never actually binding via edge-halving - it was masked; now it binds where it should,
  on names actually held. The deep-cost stress level matters MORE post-floor, not less.
- **Consequence:** no config change (`backtest.cost_per_side_pct: 0.50` stands; 0.2% is
  the optimistic bound, 1.0% the stress bound, both reported per BRD 9.7). The pick-level
  tradable edge after the default cost: 1.76% net at 51% hit. Re-open conditions
  pre-declared: a real fill-model upgrade (per-name spreads, or the 6.1 harness's
  realized slippage) or a microstructure regime change - not re-tuning.

---


## Phase 6.1 — the walk-forward harness (2026-09-26, profile `full`)

**Not an experiment - the §10 evaluator itself.** A milestone block (like the Phase 5
checkpoint and the 5->6 smoke): E008b/E009/E010 all name this harness the final judge, and
E009/E010's re-open conditions point at its realized slippage. No prediction is registered;
everything below was decided BEFORE the first full-profile run and is recorded in every
`results.json` (`protocol` block). Repo: `src/walkforward/harness.py`, registered in the
suite as `walkforward.harness` (suite now 25 checks, all PASS). The smoke's engine loop was
PROMOTED, not rewritten (the 5.1 review note's prediction held): `_engine_pass` gained
`market_warm=` (20-session pad before the decision window - the E008b starved-ADV lesson),
`engine_months_limit=`, a `_facts(d_from=)` window filter, and dict-shaped
`events`/`fill_log` return keys; the light-pass pins were untouched and re-verified
(3,902 picks, IC bit-identical to E009's floor arm).

**Protocol (decided pre-run):**
- **Window:** the split's test slice (boundary 2023-09-24 at this cutoff), recomputed from
  the DB cutoff every run - the exact months every validation-slice experiment excluded.
- **Refit semantics:** composite_2f is parameter-free (two cross-sectional percentile
  ranks; no selection, no weights, no thresholds, only decision-date data). The monthly
  "fit" is the frozen decision function; the harness asserts it per fold: the function is
  the shipped two-feature composite and the refit month (2023-07-31) re-scores
  BIT-IDENTICALLY around the fold's own scoring (P4.2's freeze protocol, harness level - a
  stateful or refitted function trips it). A fitted-model refit variant is deliberately
  NOT invented here; if one ever ships, this assert is the first thing that breaks.
- **No-peek gate (the actionplan's "assert in code"):** per fold month - fold strictly
  after the refit month; every scored matrix symbol inside the decision-date `eligible`
  snapshot (a stale matrix would silently score names not eligible at D); frozen-decision
  check above. Self-check raises on stale matrix, empty snapshot, and a stateful scorer.
- **Trade M with the frozen decision:** the promoted pass over ALL 35 fold months
  consecutively, shipped exit_gate (escalate), shipped costs (0.50%/side + capped impact
  on real ADV), warm ADV per month.
- **Realized slippage (the one unmeasured cost component):** per fill, T+1 open
  (pre-impact) vs the decision-close mark the paper experiments measured against,
  side-signed so positive = worse than paper; means over all fills AND over the realized
  book (completed round trips).
- **Benchmark:** equal-weight total-return index of the eligible universe (adj closes are
  dividend-adjusted), monthly marks, as-of membership - the BRD 11 constraint's
  construction; a sourced Nifty 500 TRI replaces it when one exists.
- **Determinism:** one full-profile pass verified against a second pass (§9.5).

**First run (full profile, cutoff 2026-09-24, 35 fold months 2023-08-31 -> 2026-06-30,
refit month 2023-07-31):**
- Paper top-5% picks (the §11 label): 2,196 picks, 56.6% hits vs the 5% baseline,
  binomial p ~ 0 (CI95 [0.545, 0.586]); mean gross +2.32%/pick, net-of-flat-cost +1.32%.
- Engine (the §8 portfolio at 4 slots): 130 fills (1 non-fill, a circuit lock), 63
  completed picks, pick hit 33%, month hit 40%, churn 1.66/mo, avg hold 45d.
- **Equity 489,703 from 1,000,000 (-51.0%), CAGR -22.3% vs benchmark +8.5%, Sharpe -0.38
  vs +0.50, max drawdown -65.2%.** Per-regime mean net: down +3.17% (8 months), flat
  -1.06% (13), up +2.51% (14) - the paper edge is not surviving the portfolio layer.
- **Realized slippage: +0.441%/side on buys, -0.420%/side on sells vs the decision-close
  mark** (130 fills measured); realized book +0.176%/side. Fills land ~0.44% ADVERSE to
  the paper mark per side - E010's modelled ~0.14% impact was real but small; the
  overnight gap from decision close to next open is the larger, previously unmeasured
  component, and it lands almost entirely on the portfolio's first trading day.

**Reading (this is the report, not a verdict):** the harness works; the first full-profile
numbers are NEGATIVE for the shipped strategy. Paper selection edge (56.6% hit, +2.32%
gross) does not survive the §8 portfolio at 4 slots + real fills + real costs over the
test window: the engine realizes -51% while the same picks average +1.32% net on paper.
Candidate mechanisms (not conclusions): concentration (4 slots vs ~63-paper-pick breadth
per fold month), the adverse T+1 open (+0.44%/side on buys), and 1.66 replacements/month
churning flat-cost into the book. The per-fold and regime tables in
`runs/walkforward/harness_results.json` are where any proposed fix must show its delta -
per §10.3, any rule change after this report archives this run and re-runs from scratch.

## Experiment E011 - slot-count attribution: the -51% was concentration, not selection (2026-09-26, profile `full`)

- **Pre-registration:** `experiments/011_slot_count/hypothesis.md`, written and frozen
  BEFORE the first arm ran. Four arms through the UNMODIFIED harness - one lever
  (`portfolio.n_slots`), everything else shipped (costs 0.5%/side + impact, exit_gate
  escalate, floor 0.75, the frozen composite_2f, warm-ADV markets, the same 35 fold
  months, same cutoff 2026-09-24). Every arm run twice (verify_determinism; serialized
  evaluations identical). A4 is the zero-drift guard: bit-identical to the committed
  Phase 6.1 baseline on final_equity, completed picks, hit rates, churn, avg hold,
  maxDD, total return - and paper picks asserted identical ACROSS arms (slots never
  touch scoring).
- **Arms:** A4 = shipped 4 slots (control); A8 = 8; A12 = 12; B8 = 8 slots + wider
  monthly-review percentiles (sell_below 0.25->0.15, replace_above 0.15->0.10) as the
  churn control. Equal weight across FREE slots (the SS8 rule, unchanged), so per-slot
  notional halves at 8 - the fill gate sees SMALLER orders (non-fills: 1 circuit lock at
  A4, ZERO everywhere else).
- **Findings:** A4 489,703 (-51.03%, maxDD -65.2%, Sharpe -0.38, 63 picks, hit 33%,
  churn 1.66/mo). A8 892,626 (-10.74%, maxDD -23.9%, Sharpe -0.29, 125 picks, hit 32%,
  churn 3.46/mo, month-hit 63%). A12 731,870 (-26.81%, maxDD -42.1%, 182 picks, hit 34%,
  churn 5.03/mo). B8 882,467 (-11.75%, churn 3.43/mo). Paper picks arm-invariant: 2,196,
  56.6% hit, +1.32% net.
- **Verdict: ADOPT n_slots = 8** (the pre-registered rule fired mechanically: both A8 and
  A12 cleared all four bars - equity >= A4 + Rs200k, higher Sharpe, maxDD within 2pp,
  hit within 3pp - and A8 won on final equity). **The answer: concentration.** Widening
  4 -> 8 recovered Rs402,923 of the Rs510,297 loss (+38.6pp) while the pick hit rate
  barely moved - the idiosyncratic variance of a 4-name book, not the model's picks,
  was the dominant loss mechanism. Selection failure is what remains: A8 still loses
  10.7% vs the +8.5% benchmark, at a 32% completed-pick hit vs the paper 56.6%.
- **Secondary findings (disclosed, not load-bearing):** (1) Buy-side slippage vs the
  decision mark flipped +0.441% -> -0.099%/side at the halved per-slot notional
  (realized book -0.130%/side): part of A8's recovery is execution quality (smaller
  orders, less modelled impact, a wider entry spread across months), entangled with
  diversification by design - the held-constant-notional arm is the declared follow-up
  pre-registration. (2) Churn rises with slots (1.66 -> 3.46 -> 5.03/mo) - a slot
  artifact, NOT ranking pressure: B8's wider percentiles moved churn by 0.03 while
  giving up Rs10,159; widening review bands is not the knob. (3) A12 is worse than A8
  on every equity metric despite more breadth - the 9th-12th slots buy worse names
  deeper in the list and churn harder. (4) month_hit 40% -> 63%: the wider book's
  monthly outcomes track the paper distribution instead of 4 coin flips.
- **Consequence:** `portfolio.n_slots: 4 -> 8` in config.yaml with this block cited.
  The shipped Phase 6.1 baseline (git a8cc624) stands archived per BRD 10.3; A8's own
  determinism-verified pass is the re-run-from-scratch reference at the new default.
  Residual loss attribution, in order of evidence: residual concentration at 8, entry
  timing (the adverse open), exit-rule quality.

---

## Diagnostic - trigger-level P&L decomposition of the 8-slot walk-forward (2026-09-26, profile `full`)

**Not an experiment - an autopsy of the committed run** (BRD 12 pre-registration governs
rule changes; this changes none). Question: which SS 8 exit rule destroyed the most value
in the adopted 8-slot reference run (git a8cc624, 35 folds, 125 completed picks, equity
892,626)? Raw per-trigger mean returns cannot answer it - a stop firing at -8% before a
-15% slide CREATED value. The module (`src/walkforward/diag_trigger_pnl.py`, in the suite
as `walkforward.trigger_pnl`, 26 checks PASS) FIFO-closes the run's fills exactly like
`metrics.completed_picks`, tags each lot with the CLOSING fill's trigger, and scores a
timing counterfactual per lot: `delta_rs = qty x (close at the exit month's decision date
- exec price)`. POSITIVE = the rule sold cheaper than the month-end review it skipped
(destroyed); NEGATIVE = it beat the month-end (saved). Flat per-side costs cancel; the
counterfactual is the month-end cadence, not "sell never"; marks missing (delisted) are
excluded and counted. Runner: `src/walkforward/run_trigger_pnl.py` ->
`runs/walkforward/trigger_pnl_results.json`.

**The ranking (rupees destroyed vs the month-end review, most damaging first):**

| trigger | lots | hit | mean ret | total delta | mean/lot |
|---|---|---|---|---|---|
| trigger_b_dma | 87 | 43% | +1.71% | **+97,832** | +1,125 |
| trigger_b_stop | 22 | 0% | -17.44% | +28,643 | +1,302 |
| monthly_review | 4 | 25% | -3.48% | +1,298 | +324 |
| trigger_b_trail | 12 | 17% | -0.60% | **-11,655** | -971 |
| TOTAL | 125 | | | +116,117 | |

**Concentration finding: one name is +87,396 of the +116,117 - BSE**, whipsawed by every
rule (2025-03 stop +38,052, 2025-10 trail +27,153, 2026-04 DMA +24,900 - sold, and it kept
rebounding). Excluding BSE the ranking REORDERS: trigger_b_dma **+74,310** (still the
destroyer, now broad: INFY, SBIN, BHARTIARTL, RELIANCE, AXISBANK), monthly_review +1,298,
trigger_b_stop **-7,814** (net value-CREATING), trigger_b_trail **-39,073** (the best rule
by timing).

**Reading (groundwork for the next pre-registration, not a verdict):**
1. **The 2-consecutive-closes-below-50-DMA exit is the value destroyer** - 87 fires
   (2.5/month), cutting winners early (mean realized +1.71% on the highest-IC model's
   picks), +97.8k rupees of timing damage that is BROAD, not one name's artifact.
2. The stop and trail rules are EARNINGS their keep: net savers once BSE's whipsaw is
   excluded (stops save 7.8k, trails 39.1k). The -17.4% mean stop return is what stops
   are FOR; their timing, not their outcomes, is the metric that cleared them.
3. Rank-band monthly exits are a non-factor in exit P&L (4 fires, +1.3k) - E011's churn
   worry lives in the buy side's turnover, not the rank exits' losses.
4. Caveat: deltas measure the one-month mark only; a name that crashed after its
   month-end mark flatters neither the rule nor the wait. The ranking is consistent
   across lots, which is what a rank needs.

Still open at the final mark (8 lots, +7,281 unrealized net): the tail of the book sits
in large-cap banks; INFY -20,238 is the biggest open loser.

**No config change. Per SS 10.3, any rule motivated by this table (e.g. a DMA-exit
relaxation arm) archives the reference run, pre-registers, and re-runs the walk-forward
from scratch.**

---

## Experiment E012 - the E009 floor at the 8-slot notional: derived, not tuned (2026-09-26, profile `full`)

- **Pre-registration:** `experiments/012_floor_at_8slots/hypothesis.md`, written and
  frozen BEFORE any arm ran. Question: E009 set `min_median_turnover_cr: 0.75` from the
  gate's arithmetic at the 4-slot Rs250k notional (boundary med20 >= 20 x S = 0.5cr, x
  the measured med20/med3 shrinkage ~1.5x); E011 halved the per-slot notional to Rs125k,
  moving the boundary to 0.25cr - the floor's arithmetic moved underneath it. Re-measure
  reachability at S125k and decide whether the floor moves.
- **Machinery:** E009's, imported module-to-module (baseline chain at floor 0.0,
  liq_daily20 built once - chain-independent, the frozen 2020-02 sample re-verified
  row-for-row, the member recompute, top-5% composite_2f pick sets over ALL labeled
  months, reachability = refused iff med20 < 20 x S). Guards first: baseline R1 rows
  BIT-IDENTICAL to E009's committed table at all four slot sizes; restore IC = P4.1b's
  frozen 0.0681243229 (1e-9); the 0.75 arm reproduces E009's committed R2 row exactly +
  its IC.
- **Arms (S125k reachability, 145-month validation-slice ICs):** baseline 0.0: 29.36%
  refused, corrected mean +2.669%. **0.375: 1.14% refused, +2.692%, IC 0.071718** (161,942
  eligible rows). 0.5: 0.46%, +2.730%, IC 0.070110. 0.75: 0.21%, +2.632%, IC 0.067450.
  Modelled impact at S125k: 0.092% (0.375) / 0.074% (0.5) / 0.056% (0.75) - all an order
  of magnitude under the 0.5%/side cost stack. All four pre-registered bars passed for
  both moving arms; the LOOSEST (smallest) floor wins -> **ADOPT 0.375**.
- **The principle this experiment fixes: the floor is DERIVED, not fitted.** It must move
  with the gate boundary, which scales with per-slot notional (med20 >= 20 x S). The
  answer to "should the floor move with slot size" is yes, by construction - E009's own
  1.5x headroom arithmetic at the new notional lands on 0.375, and the measurement
  confirms it is safe (refusal 1.14% <= 1/3 bar, corrected mean and IC both better than
  the 0.75 floor's). Re-derive on any future notional change; it is not a tuning knob.
- **Disclosure (pre-adoption bug, caught):** the first runner execution reported ADOPT
  0.5 - the candidate order in the decision code inverted hypothesis.md's "ADOPT the
  LOOSEST floor clearing all bars" (loosest = SMALLEST floor; a higher minimum excludes
  more names). Caught by re-reading the run against the pre-registration BEFORE any
  adoption; fixed (one tuple order + comment); the experiment re-run; every measured
  number identical, only the decision field moved (0.5 -> 0.375). No number ever moved
  to fit a conclusion.
- **Consequences executed:** config 0.75 -> 0.375 with the citation; chain rebuilt at
  the shipped floor (161,942 rows / 183 months); smoke re-pinned to the E012 0.375 arm
  (eligibles asserted from its results.json, IC bit-identical, light-pass picks 4,579 -
  the E009-era 3,902 pin retired to E012 with the E006-to-E009 precedent); harness
  reference re-run at 0.375 + 8 slots, determinism-verified, final equity
  892,626.0949598341 BIT-IDENTICAL to E011's A8 arm - the single fill-level difference
  is HARDWYN's 2023-09-29 exit trigger label (monthly_review -> trigger_b_dma: the wider
  eligible universe moved the rank percentile under the rank-band rule; same fill, same
  quantity, same rupees, churn 3.457 -> 3.486/mo). Paper picks 2,196 -> 2,212 (hit
  56.6%). E012's runner made re-runnable post-ADOPT (shipped-floor assert accepts 0.75
  or 0.375; arms pass floors explicitly - the E009/E011 pattern). BRD SS4 amended inline
  (the derivation principle). Suite 26/26 PASS. Nothing committed.

---

## Experiment E013 — the shelved index regime filter (Nifty 200 vs 200-session DMA) on the harness window (2026-09-27, profile `full`)

- **Why:** the BRD 15 risk row kept "market regime filter (Nifty 200 vs 200-DMA + VIX)" at
  CONSTRAINT - NOT IMPLEMENTED behind three blockers. Blocker (a) died when the sourced
  daily NIFTY 200 TRI landed in `index_tri` (2011 -> cutoff) earlier today; blocker (b)
  described P4.1's score-level atr overlay, not this filter; blocker (c) is about index
  MEMBERSHIP, which this signal does not use. The review's substitutes (E008a/E008b
  breadth gates) were rejected on premise and intra-month; the index leg itself had never
  been measured. E013 pre-registers it (BRD 12) and runs it on the harness's realized
  window - the result of record - not on the validation slice; the burn is declared in
  hypothesis.md up front.
- **Signal & arms (pre-registered before the run):** daily NIFTY 200 TRI vs its own
  200-session DMA at each decision month-end (prints <= M only; every fold's DMA
  recomputed in Python, max diff 2.2e-11). Risk-off in 9/35 months (2024-12-31..2025-04-30,
  2026-03-30..2026-06-30). Arms through the harness's own engine pass at the shipped
  config: BASELINE (gate inert; MUST reproduce harness_results.json's engine block
  bit-for-bit - it does), CASH (risk-off month: liquidate at that month-end, block all new
  buys), NO_BUYS (block new buys only). No sweep: fixed 200-session DMA, strict on-close
  comparison, monthly cadence.
- **Result (PASS on all three pre-registered bars, primary arm CASH):** equity 835,694.98
  -> 883,269.82 (-16.43% -> -11.67%); CAGR -6.14% -> -4.29%; Sharpe -0.427 -> -0.244;
  maxDD -22.99% -> -19.55% severity. NO_BUYS is Rs 2,925 BETTER than CASH (886,195.37,
  CAGR -4.18%): in this window the liquidation leg added nothing - the review's own exits
  had already emptied the book whenever the gate fired (the gate's only extra sells were
  2 `regime` names at 2026-03-30) - the value is in NOT ENTERING. Post-hoc fragility probe
  (not pre-registered, disclosure only): forcing the hair-trigger month 2024-12-31 (ratio
  0.9990, 10bp below its DMA) risk-ON still clears all bars (+1.46pp CAGR, -2.5pp drawdown).
- **Disclosure (sign-convention slip, caught in the runner):** hypothesis.md wrote the
  drawdown bar as `maxdd_cash < maxdd_baseline`, but `metrics.max_drawdown` returns a
  NEGATIVE fraction, so the literal inequality asks for a DEEPER drawdown - the opposite
  of the hypothesis's words "strictly smaller drawdown". The words govern (E012's
  runner-bug precedent); the runner tests the magnitude and records the literal signed
  reading (REJECTED) beside it in results.json. Corrected after seeing the numbers,
  disclosed; no bar or threshold moved, and the arms clear the magnitude bar by 3.4pp.
- **Why a PASS is not an edge (attribution, correctly aligned):** the 8 gated intervals
  were BETTER than average in the baseline (mean -0.19% vs -0.54% over the 26 ungated
  ones). The +4.8pp total-return gain is ~+2.7pp from the gated intervals themselves
  (Jan/Feb-25 losses avoided at ~0% cash, partly offset by the Mar/Apr-25 rebounds missed)
  and ~+2.1pp from the post-gate re-entry path, which includes a -7.2pp interval (Aug-25:
  CASH -10.30% vs baseline -3.08%) and a +6.5pp pair (Jun/Jul-25). Paper per-pick means in
  the risk-off months are +0.76% - the gain is a realized-path effect, not pick quality.
  Eight gated intervals, one window, one re-entry lottery.
- **Consequences:** NO config / harness / portfolio change. The test window is BURNED for
  this rule family (10.3): a PASS here is opt-in-regret evidence, not validation - any
  adoption needs a fresh pre-registered out-of-sample plus the standard bookkeeping. The
  BRD 15 risk row is amended (blocker (a) dead for the index leg; measured, not adopted).
  Reusable machinery: inert-by-default `regime_off` / `regime_liquidate` hooks on
  `smoke_e2e._engine_pass` (the signal stays the caller's). Nothing committed.

---

## Experiment E014 — the risk-off buy-block on the validation slice: the premise fails (2026-09-27, profile `full`)

- **Why:** E013's test-window PASS (+1.9pp CAGR from 8 gated intervals) could not separate
  signal from path. E014 pre-registers the premise test on the frozen validation slice
  (145 months 2011-07-29 -> 2023-07-31; test window untouched) across six pre-named
  episodes: 2011 euro crisis, 2013 taper, 2015-16 China/oil, 2018 IL&FS, 2020 COVID,
  2022 rates.
- **Signal & arms:** the same construction (NIFTY 200 TRI vs its own 200-session DMA at
  each decision month-end, prints <= M); folds before the DMA warms (2011-10-31) are
  risk-on by construction; 35 of 145 folds risk-off. Arms through the harness's engine
  pass: BASELINE (gate inert), BUY_BLOCK (no new buys in risk-off folds - E013's core),
  CASH (also liquidates; diagnostic, 31 regime sells).
- **Guards:** the smoke's own convention (labeled-only rows, warm=0) over 12 months
  reproduces runs/smoke_e2e's escalate arm BIT-FOR-BIT; eligible rows 161,942 == E012's
  chain pin; IC 0.0717179780 == E012's 0.375-arm IC (1e-9); arm-convention picks 5,605 >=
  the labeled-only 4,579; every warmed fold's DMA recomputed in Python (max diff 1.1e-11
  over 142 folds).
- **Verdict: REJECTED, both sign readings.** B1 (gate helps = the baseline is worse in the
  gated intervals): mean d = +0.542% - the WRONG direction; p(gate helps) = 0.654. The
  decisive fact: the baseline's monthly engine return in the gate's own 35 intervals was
  +0.754% (sd 8.26%) vs -0.026% (sd 5.50%) in the 109 it left alone - risk-off marks
  VOLATILE months, not losing ones. B2: 3 of 5 counted episodes favor the gate, 4
  required (favored 2013_taper, 2020_covid, 2022_rates; against 2011_euro - the arm lost
  7.2% while the baseline gained 12.0% over that episode's gated intervals - and
  2015_16_china; 2018_ilfs has 2 gated intervals, not counted, also against).
  Disclosure: hypothesis.md's parenthetical sign claim ("positive = the baseline did
  worse") is inverted for d = base - arm; both readings were evaluated and give the same
  verdict; results.json records bars, bars_as_coded and the disclosure.
- **Why the equity column looks positive anyway (the finding):** BUY_BLOCK 1,108,821
  (+10.88%) vs baseline 942,030 (-5.80%), maxDD -46.5% vs -65.6% - but the arm's advantage
  comes from the UNGATED intervals (placebo d = -0.212%/mo over 109: after every gated
  episode it carries a different, later, thinner book) and from exposure arithmetic: the
  baseline's monthly mean is +0.164% with 6.29% sd, so variance drag (~0.198%) exceeds the
  mean and its geometric return is -0.041%/mo (the arm's sd is 4.83%). On a tape where the
  engine's own drag dominates, ANY exposure reduction improves the geometric path - signal
  or not. This retro-explains E013's test-window PASS as the same exposure/path artifact,
  not timing alpha - consistent with P4.1/E008a/E008b and with E008a's "troughs mark
  rebounds".
- **Consequences:** the index leg is CLOSED (hypothesis.md's own rule: REJECTED is
  terminal); BRD 15 risk row extended; no config/harness change; no further out-of-sample
  spend on this rule family. Machinery stays inert and reusable (`regime_off` /
  `regime_liquidate`); E014's signal sampler documents the two special-session folds
  (2015-02-28, 2016-10-30) where the sourced index's own month-end marks disagree with the
  equity calendar. Nothing committed.

## Break-even arithmetic - pick edge vs holding horizon: the edge is not a 1-month artifact (2026-09-27, decision basis for E016)

- **Why:** every engine configuration ever measured loses to the index while the raw picks
  carry ~+2.8%/month gross. Before spending another experiment inside the monthly-rebalance
  architecture, one number decides whether the architecture (churn x costs) is the binding
  constraint: does the pick edge survive longer holding periods? Computed by
  `experiments/016_low_turnover/breakeven.py` (assert-checked, re-runnable).
- **Method:** the 145-month validation slice, the smoke's labeled picks (4,579 == the E012
  pin, exact), overlap-free h-month books (enter at month i's picks, hold h, next entry at
  i+h). Three estimators: LABEL chains `next_month_ret` but must drop legs whose symbol
  loses its label mid-hold (12.6% of h=3 legs — optimistic, they are disproportionately
  delistings); DEAD books every missing mid-hold label as a -100% leg (pessimistic bound);
  PRICE uses actual `adj_close` month-end marks — entry at the entry month's own mark, exit
  at the symbol's last traded mark on or before the exit month (sell-at-last-trade delisting
  proxy), no leg dropped. Costs follow E006: 0.4% per round trip; h>1 pays one round trip
  per hold. Guards: h=1 label gross reproduces the smoke's committed `mean_gross` to 0.0e+00
  and legs == 4,579; net identity exact; LABEL >= PRICE at every horizon.
- **Result (net per month, PRICE estimator):** 1m **2.35%**, 3m 2.27%, 6m 2.15%, 12m
  **2.04%**. Bounds: LABEL 2.41/2.39/2.46/2.26; DEAD 2.41/**-2.13/-1.40/-0.48** — the
  dead-leg worst case flips the sign, which is precisely the survivorship trap, and is why
  the price-path estimator is the decision basis. The decay from 1m to 12m is ~0.31pp/month
  of holding — while round trips fall from 12 per year to 1.
- **Reading:** the pick edge is NOT concentrated in the first month; a 12-month hold keeps
  ~87% of the monthly edge while paying ~8% of the monthly-rebalance cost load. The engine's
  architecture — monthly churn x 0.5%/side x impact caps (E010) — is the difference between
  a +2%+/month raw edge and a -6% CAGR engine. This is the decision basis for E016: the
  low-turnover variant is the highest-expected-value experiment left inside this signal.
  (Caveats, deliberate: equal-weight mean of leg returns, not the portfolio's slot-weighted
  path; no fill-gate refusals, no ADV impact cap, mid-hold trail/trigger exits not modeled —
  those are what E016 itself must test through the real engine.)

## Experiment E016 - low-turnover engine: the monthly review was already inert; its sells were alpha (2026-09-27, profile `full`)

- **Why:** the break-even block above. Pre-registered in
  `experiments/016_low_turnover/hypothesis.md` before the run (BRD 12); the runner
  reuses E014's machinery (harness convention, warm=20) plus a config-only arm.
- **Arms:** A shipped config; B SELL_GATE (never sell on rank fade or the 50-DMA streak —
  `sell_below_top_pct` 1.01, `ma_below_consecutive_closes` 999; Trigger B stops/trails,
  GSM and universe exits unchanged); C MIN_HOLD_12 (new inert `_engine_pass` hook
  `min_hold`: monthly_review sells dropped before the 12th held decision month; stops fire
  even in month 1).
- **Guards, all passed:** G1 arm A json-equal to E014's committed baseline (bit-for-bit);
  G2 picks 5,605 >= 4,579, eligible 161,942, IC == repaired-tape pin to 1e-9; G3 the
  mechanism engaged — monthly_review sells A **8** vs B **3** vs C **2** over 145 months;
  G4 the hook is inert by default — the smoke's engine passes reproduce their committed
  artifact bit-for-bit after the hook edit.
- **Result: REJECTED, decisively.** B: 817,629 (CAGR -1.66%, **1.16pp WORSE than A**);
  C: 689,387 (CAGR -3.05%, 2.55pp worse). Fills essentially unchanged (983 -> 981/979) —
  suppressing review sells saved ~nothing on costs and gave up the alpha those 8 sells
  earned. maxDDs identical (-65.6/-65.9%): the drawdowns were never the review's doing.
  B1 failed for both arms; B2 passed trivially.
- **The finding:** the shipped monthly review emitted **8 sell decisions in 145 months** —
  it was already nearly inert by construction (rank threshold 0.25 vs a top-15% replace
  pool), and its rare sells were, in aggregate, alpha. The real turnover (~980 fills,
  ~0.85 round trips per position-month at 8 slots) lives in Trigger B stops/trails and the
  T+1 fill path — risk-control exits this experiment deliberately did not touch. Any
  future cost-drag attack must aim there (stop/exit design) or at the cost model, not at
  the review. Index-equivalent: the slice's Nifty 500 TRI CAGR +13.17% — every arm, and
  every arm of every prior experiment, loses to buy-and-hold by 12-17pp/yr. No config
  change; `min_hold` stays as an inert, G4-proven hook.

### Index-equivalent lines (2026-09-27) — no result may again read as success while losing to the index

- Every experiment verdict now carries an **index-equivalent** quote block: what the same
  capital earns in Nifty 500 TRI over that experiment's identical window, from the
  `arms.*.benchmark_cagr` fields already stored in every `results.json` (E013 +12.46%,
  E014/E015 +13.17% — every arm of every experiment loses to buy-and-hold by ~12-25pp/yr).
- The harness report prints a standing `index-equivalent` line (engine CAGR vs the sourced
  benchmark's CAGR over the same window, with the gap).

## Experiment E017 - Trigger B stop/trail sweep: REJECTED on the pre-registered bar, and the first positive-CAGR engine arms ever measured (2026-09-27, profile `full`)

- **Why:** E016 exonerated the monthly review and located the real turnover in Trigger B;
  the break-even arithmetic said the edge survives long holds. Pre-registered in
  `experiments/017_stop_sweep/hypothesis.md` before the run; arms are config-only via
  `portfolio_overrides` (A shipped 0.08/0.12; D1 2x; D2 4x; D3 stop off; D4 trail off;
  D5 both off; T1 half — the falsification arm). One pre-run disclosure: G3's strict
  monotonicity was replaced by a directional rule (T1 > A > D5) when the pilot showed the
  shipped widths bind rarely and most trigger_b sells are the DMA/delivery clauses the
  sweep does not touch (`results.json guards.G3_note`).
- **Guards, all passed:** G1 arm A json-equal to E016's committed baseline (bit-for-bit
  back to E014); G2 tape pins exact (picks 5,605, eligible 161,942, IC == repaired-tape
  pin to 1e-9); G3 T1 576 > A 486 > D5 475 trigger_b sells; G4 stop/trail counts zero
  where required, GSM intact everywhere.
- **Result: REJECTED** — B1 needed CAGR >= A + 2.0pp (>= +1.50%); the best arm (D2)
  reached **+0.84%** and missed by 0.66pp. B2 passed everywhere (wider stops IMPROVE
  maxDD: -63.3% vs -65.6%).
- **The findings that survive the rejection:** (1) the whipsaw decomposition is monotone —
  T1 -0.62% < A -0.50% < D1 +0.50% < D5 +0.81% ~ D2 +0.84% CAGR: tighter stops lose,
  wider wins, the "stops are alpha" hypothesis is falsified in this signal; (2) the stop
  is the whole effect — D3 (stop off, trail kept) equals A to the last fill (the stop's
  116 sells were perfectly replaced by 163 trail sells), D4 (trail off, stop kept) is
  worth +0.49pp; (3) **D1/D2/D5 are the first positive-CAGR engine arms ever measured**
  (Sharpe 0.138-0.153, improved maxDD, all still ~12.3pp/yr below the index's +13.17%);
  (4) fills barely moved across the sweep (983 -> 963): the gain is not trading less, it
  is not realizing losses at the local low. With E016 and the break-even arithmetic, the
  engine's deficit vs its own picks is now attributed: whipsaw losses + the cost model —
  not review churn, slot count, benchmark timing, or sizing. No config change; the family
  is closed per the pre-registration.

## Real-world delivery cost analysis - the modeled 0.5%/side is the largest modeled drag (2026-09-27, analysis on committed sweeps; not a pre-registered experiment)

- **Basis:** E006's measured picks-level response (net/mo: +3.05% at 0.2%/side, +2.45% at
  0.5%, +1.45% at 1.0% — linear, 1:1 in round-trip cost) x real-world Indian delivery
  costs at a discount broker: brokerage 0%, STT 0.1%+0.1%, exchange/SEBI/stamp/GST/DP
  bring the round trip to ~0.21-0.24% = ~0.105-0.12%/side. The shipped 0.5%/side model is
  ~4-5x real; E006's 0.2% floor is ~1.7-1.9x real.
- **Arithmetic:** engine cadence ~0.85 round trips per position-month (E017's fills) ->
  cost drag ~0.85%/mo modeled vs ~0.18%/mo real, a delta of ~+0.67%/mo (~+8.4%/yr) on the
  book. Re-costing E017's D2 path: +0.84% CAGR modeled -> roughly **+6-9% CAGR at real
  costs** (deployment-adjusted) — the first configuration in the index's neighborhood,
  though still below +13.17%. A baseline re-costs to ~+5-7.5%.
- **Status: analysis, not shipped.** This is arithmetic on measured responses, not a
  measured engine run; varying the shipped cost model re-pins every prior engine anchor
  and needs its own pre-registration (E018 candidate: one config change,
  `backtest.cost_per_side_pct` 0.5 -> 0.12, one validation-slice pass, fresh pins).
  The index-equivalent line still governs: buy-and-hold pays +13.17% with zero fills,
  zero model risk. Full workings in `experiments/018_real_costs/README.md`.

## Experiment E018 - breadth portfolio: the first PASS that beats the index, by ~16-19pp/yr (2026-09-27, profile `full`)

- **Why:** the 8-slot engine captures 9.4% of the composite's signal (529 of 5,605
  arm-convention picks); the basket arithmetic (E006 +3.05%/mo at 0.2%/side; break-even
  block: edge survives 12-month holds at ~87%) says the WHOLE cross-section, held, at
  breadth, is the architecture the program never tried. Pre-registered in
  `experiments/018_breadth_portfolio/hypothesis.md` before the run; paper-book experiment
  (the engine is the thing being replaced), 12-month overlapping cohorts priced on
  adj_close month-end marks, sell-at-last-trade delisting proxy, real costs 0.21%/round
  trip.
- **Pre-run disclosures (2, both in results.json guards):** G1's anchor was re-based from
  E006's +3.05% (a pre-floor 6,622-pick book) to the current tape's own committed
  mean_gross +2.8113% (arm A price-path +2.6840%, diff -1.27e-3 = the measured mark-timing
  gap); G4's width window [70,85]/<=90 was re-based to [55,85]/<=130 (the scored
  cross-section is smaller than the eligible count: decile median 61, max 115).
- **Pipeline finding (bigger than E015's):** the arm convention (all decision rows) puts
  **64.4% of picks in symbols with no adj_close coverage at all** - **1,066 of 4,052 bhav
  symbols (1.22M bhav rows) have zero Yahoo coverage** (renames/delistings: TUBEINVEST,
  MOTHERSUMI, CORPBANK, ABIRLANUVO, ADANIGAS...). Books were therefore drawn from LABELED
  rows (the tradeable universe; 4,522/4,522 top-5% legs priceable end-to-end); the labeled
  top-5% pin (4,579) is exact and the arm-convention pin (5,605) still cross-checks the
  selection code. Any future price-path work on unlabeled rows needs a rename map or an
  explicit tradeability filter.
- **Result: PASS, both bars.** A TOP5_EQUAL +32.33% CAGR / maxDD -21.58%; **B
  DECILE_RANK_W +29.64% / -23.05%**; C DECILE_EQUAL +31.04% / -21.67%; D (0.5%/side
  model) +28.85% / -24.30%. Index-equivalent +13.17% / -28.87%: B1 (+10% bar) passed at
  ~3x the bar; B2 passed with the breadth book a BETTER ride than buy-and-hold. Honest
  reading in the verdict: the cohort estimator annualizes overlapping cohorts (the
  deployable single-book path is the break-even block's ~2.04-2.35%/mo -> the same
  ~+28-34% band); no fill gate, no impact caps, no intra-month stops; even the pessimistic
  cost model keeps +28.85%.
- **Consequences:** no engine/config change (pre-registration rule). The 8-slot engine is
  now a MEASURED 9.4%-capture concentrated expression, with a measured breadth alternative
  that captures the whole signal. The follow-on is portfolio design (breadth book vs
  index core + satellite, execution costs at real ticket sizes); the slice is spent for
  the breadth family's design choices - test-window confirmation only after the design
  freeze. The 10-20% target band from the brainstorm was real: this is the first measured
  configuration above it.

## Pipeline repair - adj_close session coverage: seven Yahoo-less sessions, derived from bhav (2026-09-27, uncommitted; working tree on `b38f0b3`)

- **What was missing:** `adj_close` has no row at all for 7 sessions bhav (series EQ) traded -
  2011-10-26, 2012-10-26, 2012-11-13, 2014-10-23, 2015-11-11, 2019-02-13, 2019-03-29. Four are
  NSE Diwali muhurat sessions (1-hour evenings at 15-23% of a normal day's turnover) Yahoo
  simply does not carry; 2012-10-26 (71% turnover), 2019-02-13 and 2019-03-29 (full sessions)
  are ordinary vendor holes. **2019-03-29 is the March-2019 month-end**, so every symbol's
  March mark was a session stale (found twice: E015's sigma had no view at that fold, and the
  new coverage check's first run).
- **The check (new):** `adj_close.session_gaps()` + `_classify_gaps` - every bhav EQ session
  from the table's start to the cutoff must carry an adjusted close; the 7 holes are pinned
  in `KNOWN_SESSION_GAPS`, a NEW unpinned Yahoo-less session FAILS `normalize.adj_close`
  (registered in the suite), sessions inside refresh_recent's 7-day retry buffer are exempt
  ("still filling"), a pin Yahoo later covers is reported as healed, and rows covered only by
  derived data are reported as such - the FAIL contract keys on Yahoo's feed, so a derived
  row can never mask a new feed hole. Surfaced daily in src/download/refresh.py.
- **The repair:** `derive_session_gaps` - adj_close(s) = bhav raw close(s) x the adjustment
  factor held across the gap, the factor read from the nearest Yahoo row on EACH side of s,
  refusing when the two disagree by >0.5% (a corporate action inside the gap) or when either
  basis sits >10 sessions away. Rows land with `source='derived'` (a new nullable column; NULL
  = Yahoo's own row), are outranked by any real row (`_insert` prefers Yahoo on a (symbol,
  date) collision), are wiped by refresh_recent's full re-fetch, and the derivation is
  idempotent (a repaired session stops being a hole). Yield: **6,646 rows** over the 7
  sessions (820-1,188 per session); refused 129 symbol-sessions (moved factor / no raw close)
  and 3,239 with no Yahoo basis within +-10 sessions - verified to be renamed/delisted tickers
  Yahoo no longer serves (3IINFOTECH, ADANIGAS, ADANITRANS, ADLABS sampled: zero adj_close rows
  ever for the ticker),
  not a window bug. Hand-checked: derived value == raw close x held factor to the last bit.
- **Momentum canary before -> after:** PASS both times. [1] momentum IC pooled median
  +0.0639 -> +0.0639 (unchanged) over 200 -> **201** month-ends - the added month-end is
  2019-03-29 itself (1,182 names); [0] symbol coverage, [2] delivery autocorr (0.890 /
  293,787 pairs) and [3] eligible-count stability unchanged.
- **Tape effect (measured on a throwaway DB copy first, then in the workspace itself: panels +
  chain rebuilt, the derived rows are the only input change):** eligible 161,942, labeled
  picks 4,579 and arm-convention picks 5,605 all UNCHANGED; month-end dates 310 -> 311; the
  1,182 moved March marks move a median 1.18%
  (typical March-2019 daily move 1.32%, p95 5.3%, max 15% - ordinary session moves, no factor
  glitches). One number moves: the slice mean monthly IC **0.0717179780 -> 0.0720292285
  (+3.11e-4)**, and the whole delta is four decision months whose feature windows touch a
  repaired session - 2019-02-28 +0.0030, 2019-03-29 +0.0444 (the decision month that had no
  cross-sectional mark at all), 2019-04-30 -0.0031, 2020-03-31 +0.0008.
- **Named next step (DONE the same day, 2026-09-27):** the IC pin was re-baselined to the
  repaired tape. The smoke now holds `SLICE_IC_PIN = 0.07202922854484578` (with
  `SLICE_IC_PIN_PRE_REPAIR = 0.07171797803434904` beside it), and the light pass asserts the
  fresh IC against the new pin while a new 1e-12 assert pins E012's frozen
  `ic_val_slice` to the pre-repair value — the frozen artifact is forced to keep describing
  the tape it ran on. E014/E015 runners read `smoke.SLICE_IC_PIN` (single source of truth;
  their results.json gain an `ic_pin_source` note). Verified: smoke PASS with the engine
  passes bit-identical to the committed artifact (the repair touches only the 2019/2012-10
  label flows); a fresh E014 run differed from its frozen results.json ONLY in the IC fields
  (mean 0.0717179780 -> 0.0720292285, +3.11e-4) + runtime + git_hash — every decision-relevant
  number (all three arms' equity/curve/fills/picks, risk-off intervals, episodes, verdict) is
  bit-identical, so the repair moves no conclusion; the frozen results.json was restored
  untouched. E014/E015 verdicts carry a historical note recording their pre-repair IC.
  Picks (4,579 / 5,605) and eligible (161,942) pins unaffected. No config change.

## Experiment E015 - volatility-scaled slot sizing at unchanged average exposure: the relief is not reachable by sizing (2026-09-27, profile `full`)

- **Why:** E014 rejected the index regime filter as timing and traced its whole-slice edge
  to exposure / variance drag (baseline arithmetic +0.164%/mo at 6.29% sd, geometric
  −0.041%/mo, so ANY exposure reduction improves the geometric path signal-free). If
  exposure is the mechanism, a signal-free sizing rule should buy part of the relief back.
  Pre-registered in `experiments/015_exposure_sizing/hypothesis.md` before the run (BRD 12).
- **Design:** 145-month validation slice, test window untouched. σ = trailing 60 sessions
  of adj-close log returns ending at the fold's decision date (≥ 40 required, else no view
  and scale 1.0), σ_med over the month's pool = eligible with rank_pct ≤ 0.15 (the engine's
  own replace pool). Arms: A baseline (hook absent), B EQUAL_RISK_MEAN1 (normalized so the
  pool mean scale is exactly 1.0 — unchanged average exposure), C DERISK_CAP (diagnostic).
- **Guards, all passed:** G1a the hook is inert — the 12-month smoke escalate prefix is
  bit-equal; G1b arm A == E014's committed `arms.baseline` exactly; G2 picks 5,605 == pin,
  IC 0.0717179780 == E012; G3 σ point-in-time — every 40th (month, symbol) pair (364)
  recomputed from a fresh per-pair query, max abs diff 1.4e-17; G4 B's mean invested share
  67.4% vs A's 67.9% (−0.49pp, tol ±2.00) — B is mean-1 in fact, not just by construction;
  G5 pool mean scale exactly 1.0 for all 144 σ-bearing months, C max scale 1.000.
- **Verdict: FAILED** (B1 fails, B2 passes trivially 3/6 episodes). B: equity 772,093
  (−22.79%), CAGR −2.13%, Sharpe 0.009, maxDD −67.51%, invested 67.4%, mean buy scale
  1.040 — drawdown gain −1.93pp (−10% of E014's 19.07pp relief) and CAGR 1.63pp worse. C:
  965,412 (−3.46%), CAGR −0.29%, maxDD −62.19% — gain +3.40pp (17.8% of R) with CAGR
  0.21pp BETTER, at 66.4% mean invested share.
- **Mechanism:** B's tilt moves weight out of the volatile names into the calm ones; the
  realized book keeps its return in the volatile names, so the arithmetic mean fell
  0.149pp/mo (sd 6.31% → 6.17%) and the geometric path got worse (−0.179% vs −0.041%/mo).
  Equal-risk weighting is a bet against the composite's own alpha concentration. C keeps
  the arithmetic edge (+0.165%) and cuts the sd to 6.09% (geometric −0.024%) — the E014
  variance-drag channel — but it removed only 1.5pp of mean invested share and captured
  ~18% of the relief: the relief scales with exposure ACTUALLY REMOVED, and a mean-1 rule
  removes none. B's episode DDs were better in all three crises (2018_ilfs, 2020_covid,
  2022_rates) and worse in the other three; resized buys 12 vs A's 3 (upscaled buys
  hitting the cash constraint, disclosed in the hypothesis).
- **Disclosures:** the 0.375 floor is derived at the equal-weight notional (E012) and is
  NOT re-derived per arm, so no refusal rate is compared to the shipped 1.14%; 13.2% of
  pool symbol-months carry no σ (scale 1.0); `adj_close` has zero rows for the 2019-03-29
  session (bhav has it — one vendor gap in the adjusted-close feed), so that fold has no σ
  view and behaves as baseline (pipeline observation for the refresh/backfill task;
  month-end marks fall back a day there); weights drift after entry (the engine never
  rebalances), so B equalizes entry-notional risk only — volatility-scaled slot sizing,
  not risk parity.
- **Consequences:** no config change, nothing promoted; BRD §7 amended (the sizing half is
  now tested and rejected); the sizing family is closed on the validation slice — a re-open
  needs a different mechanism (an explicit exposure target) with a fresh pre-registration
  and E012's floor re-derivation per arm. The inert `size_scale` hook stays in
  `smoke_e2e._engine_pass` (default `None` = bit-identical, re-proved by G1a on every run).

### E015 supersession — rerun on the repaired tape: FAIL strengthened (2026-09-27, profile `full`)

- **Why rerun:** the adj_close repair (row above) fills the 7 Yahoo-less sessions, and
  E015 is the one experiment that consumes them at run time — σ windows end at each fold's
  decision date, so the repaired sessions enter arms B/C's σ directly (2019-03-29 gains a
  view it lacked — the frozen run's "no σ view, behaves as baseline" note is obsolete;
  months with no σ-bearing pool 1 → 0 of 145) and the four muhurat sessions enter the
  60-session windows of later folds. The IC-pin re-baseline (smoke `SLICE_IC_PIN`) was the
  prompting commit; this rerun measures what the repair actually did to E015's arms.
- **Protocol:** fresh full run after the re-baseline commit; frozen `results.json` diffed
  leaf-by-leaf against the fresh one (1,567 differing paths). Arm A baseline: ZERO differing
  paths — bit-identical to its frozen self and to E014's `arms.baseline` (G1b re-passed);
  it never reads σ, so the repair is invisible to it by construction. The IC-guard fields
  and `runtime_seconds`/`git_hash` account for the rest of the bookkeeping deltas.
- **Arms B/C magnitudes moved; direction did not:** B EQUAL_RISK_MEAN1 — final equity
  772,093 → **756,608** (−15,484), total −22.79% → −24.34%, CAGR −2.13% → −2.30%, Sharpe
  0.009 → 0.001, maxDD −67.51% → **−68.11%**, arith mean/mo +0.015% → +0.001% at sd 6.17%
  (unchanged to 3dp), fills 949 → 947; drawdown gain −1.93pp → **−2.53pp** (−10% → −13% of
  R). C DERISK_CAP — final equity 965,412 → 966,926, maxDD −62.19% → −62.13%, gain +3.40pp
  → +3.45pp (17.8% → 18.1% of R), CAGR −0.29% → −0.28%. Episodes: same 3/6 better for B
  (2018_ilfs, 2020_covid, 2022_rates), per-episode maxDDs moved ≤ 0.05pp except 2013_taper
  +0.16pp. Decision text unchanged: **FAIL** (B1 False, B2 True 3/6, G4 −0.49pp → −0.56pp
  inside ±2.00).
- **Reading:** the repair strengthens the verdict. B's arithmetic mean collapsed further
  (the composite's alpha concentration is now bet against across a slightly wider σ cross-
  section) while its sd barely moved, so the equal-risk normalization destroys even a
  little more compound return than first measured; C's relief remains proportional to the
  1.5pp of mean invested share it removes. The original arms stay the committed record
  (`results.json`/`verdict.md` not overwritten — they describe the pre-repair tape, as
  E012's do); this row + the verdict's historical note are the supersession record.
  No config change; nothing promoted.

---
