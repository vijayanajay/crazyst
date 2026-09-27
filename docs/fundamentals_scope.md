# Fundamentals tranche — scope, effort, and the go/no-go

2026-09-27. The audit's last unexplored information domain (docs/feature_family_audit.md
§3): everything the program has measured is price/volume/delivery; balance-sheet and
income-statement data would unlock factor families the composite has never seen. This is
the go/no-go with numbers attached.

## 1. What it would unlock (factor families, by evidence prior)

| family | canonical signals | prior on this universe | why now-unmeasurable |
|---|---|---|---|
| Quality / accruals | accruals/assets, ROE stability, CFO/E | Decent — quality premia survive internationally, but are slow (12-mo horizons) | no balance-sheet source |
| Promoter/pledge | promoter holding Δ, pledged-share Δ, SAST tranches | Strong prior for India specifically — ownership structure is the local pathology; E004's pre-registration (insider overlay, still `pending` in the LEDGER) named exactly this | no ownership source |
| Earnings reactions | CAR around results, SUE | Mixed — post-earnings drift is documented but is an *event* effect (like E025's inclusion finding: concentrated in days, smeared dead at monthly horizon) | no earnings calendar |
| Value | E/P, B/P | Poor fit here — the eligible universe is small/mid-cap momentum infrastructure; value interacts with the quality of momentum, not standalone | no fundamentals source |

Honest base rate: E023/E024/E025 all REJECTED at their pre-registered bars. The prior that
any new tranche clears a deployable bar is maybe 1-in-4 per family — and the monthly-horizon
E022/E025 lessons (regime-concentration, announcement-window concentration) apply to several
of these too.

## 2. Sources, realistically

| source | coverage | cost | effort | catch |
|---|---|---|---|---|
| **screener.in** | 10y quarterly P&L/BS/CF, ratios per company | free site (ToS restrict scraping; no API) | days–week: scraper + per-symbol resolution + backfill | ToS/fragility; unit economics of a scraped pipeline are poor |
| NSE corporate filings (BSE/NSE announcements, shareholding patterns) | promoter holding, pledges, SAST — quarterly LODR | free, official | 1–2 weeks: announcement scraping is genuinely messy (PDFs/XBRL, name resolution) | the resolver problem again; quarterly cadence |
| **Paid vendor** (CMIE Prowess, Ace Equity, Tickertape API, FactSet) | deep history, clean, symbol-keyed | ₹50k–₹5L+/yr | days to integrate | the real cost is annual, forever |
| yfinance fundamentals | quarterly BS/IS/CF per ticker | free | 2–3 days — the downloader already exists (adj_close.py pattern); ~2,982 priced symbols | coverage is thin/dead for exactly the delisted tail that matters most (the 1,066 zero-coverage symbols are the *interesting* failures); history depth varies |

## 3. Effort to first verdict, honest accounting

Even with data in hand, the factory path is: downloader + normalize + panel CTAS
(1–2 weeks), PIT-discipline audit (the corporate-action date alignment work — the single
most error-prone step; adj_close's repair history shows how subtle this is), IC screen
pre-registered (E025 style, hours), and then the same base rate. Realistic total to a
first LEDGER row: **3–5 weeks** for the yfinance route, **6–10 weeks** for filings,
plus vendor cost if bought. Then the prospective protocol gates any design on ≥ 18
virgin months — so a deployable answer is **2+ years out** regardless of route.

## 4. Go/no-go

**NO-GO for now — with one exception.** Rationale:

1. The program's measured lesson is that *monthly-horizon cross-sectional* edge on this
   universe is regime-concentrated and fragile (E020-C, E022); fundamentals' documented
   premia are slower still (annual horizons), which makes the deployable monthly book the
   wrong consumer for them.
2. The highest-prior family (promoter/pledge/ownership) lives in quarterly LODR filings —
   the messiest, most name-resolution-heavy source, for a signal whose monthly-smeared
   version E025 just showed dies.
3. The cheap route (yfinance) has exactly inverted coverage: it is best where the program
   is already strongest (live names) and absent where the interesting failures are.
4. The prospective protocol means any new design costs 18+ months of patience *after*
   the build — the total latency to a deployable verdict is longer than the program's
   entire history so far.

**The exception:** if a *specific* ownership event source becomes cheaply available
(NSE's corporate announcements for pledge/SAST changes, machine-readable), a narrow
E004-style pre-registration (insider net-buying overlay, still pending in the LEDGER) is
the one item worth revisiting — it was pre-registered by the BRD, never measured, and is
event-shaped rather than level-shaped, which E025 showed is where the signal actually is.
Decision owner: the BRD owner, when that source appears.
