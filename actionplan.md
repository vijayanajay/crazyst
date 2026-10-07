# Action Plan — Fundamental & Forensic Elimination with 12-Month Quality Momentum

> **Context & Why This Plan Exists**:
> Across 28 pre-registered experiments (E000–E027 in [LEDGER.md](file:///d:/Code/crazyst/LEDGER.md)), our quantitative engine proved three structural truths:
> 1. **Monthly equity rebalancing is an uncanny valley**: It is too slow to capture event-driven order flow ([E025](file:///d:/Code/crazyst/LEDGER.md#L39)) and too fast for compounding, bleeding 0.5%/side in statutory fees (STT, GST, stamp duty) and slippage every 30 days.
> 2. **Technical stops and macro gates do not work**: Stop-losses ([E017](file:///d:/Code/crazyst/LEDGER.md#L30)) whipsawed and destroyed alpha. Macro 200-DMA switches ([E014](file:///d:/Code/crazyst/LEDGER.md#L29)) and drawdown gates ([E021](file:///d:/Code/crazyst/LEDGER.md#L39)) sat in cash during the most explosive recovery rallies.
> 3. **Small-cap momentum has a hard capital ceiling**: At ₹40L account size, illiquidity floors destroy 17.6 bps/mo of gross alpha ([E027](file:///d:/Code/crazyst/LEDGER.md#L32), [capacity_note.md](file:///d:/Code/crazyst/docs/capacity_note.md)). In our out-of-sample test ([E020-C](file:///d:/Code/crazyst/LEDGER.md#L457)), the monthly momentum edge over Nifty 500 TRI collapsed to +0.13 pp/yr.
>
> **The Pivot**:
> We replace high-turnover monthly trading with a **Forensic Elimination + 12-Month Quality Momentum Pipeline**. 
> - **Primary edge in India is negative screening**: In Indian markets, the median company siphons capital. Alpha is created by ruthlessly killing the 70% of companies with governance red flags, accrual traps, and pledge risks.
> - **Holding horizon matched to filing cadence**: Positions are held for **12 months** (or staggered quarterly cohorts). Turnover drops from 300%+/yr to $< 25\%$/yr. Friction collapses.
> - **Real risk management**: Risk is managed through **governance elimination, strict 8-10% position sizing, and multi-asset capital allocation (Equity + Gold + Liquid Bees)** — not whipsawing technical stop-losses.
>
> **Core Developer Guidelines (AGENTS.md / Ponytail Mode)**:
> - **Zero parallel stack**: All configurations live in [config.yaml](file:///d:/Code/crazyst/config.yaml). All tables live in `data/duckdb/quant.duckdb`. No new databases or config duplicates.
> - **No bloat dependencies**: Use Python standard library (`xml.etree.cElementTree`, `re`, `urllib/requests`) and existing project tools (`DuckDB`, `pandas`). No unapproved heavy frameworks.
> - **Deterministic regex before LLMs**: Legal audit clauses ("Qualified Opinion", "Going Concern") use compiled regex. LLM is strictly reserved for unstructured Related-Party Transaction (RPT) notes.
> - **Auditable trail**: Every killed company is logged in `data/reports/rejections.csv` with the exact numerical rule that triggered the kill.

---

## Architecture Flow

```
                      ┌────────────────────────────────────────────────────────┐
                      │      NSE Top-1500 Universe (from quant.duckdb)         │
                      │      (Turnover Floor: med20 >= Rs 1.5 Cr for scale)    │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                        ┌─────────────────────────┴─────────────────────────┐
                        ▼                                                   ▼
           ┌─────────────────────────┐                         ┌─────────────────────────┐
           │   PRIMARY: BSE XBRL     │                         │   BACKUP: SCREENER.IN   │
           │   (Official IND-AS XML) │                         │   (Polite Token Bucket) │
           │   Zero OCR, Schema-safe │                         │   3.5s-5.0s delay       │
           └────────────┬────────────┘                         └────────────┬────────────┘
                        │                                                   │
                        └─────────────────────────┬─────────────────────────┘
                                                  ▼
                                 ┌──────────────────────────────────┐
                                 │       quant.duckdb Storage       │
                                 │   financials_annual / bfsi       │
                                 │   shareholding_reported          │
                                 └────────────────┬─────────────────┘
                                                  │
                                                  ▼
                                 ┌──────────────────────────────────┐
                                 │  Phase 2: Forensic Elimination   │
                                 │  • Sloan Accrual Trap (> 0.10)   │
                                 │  • ICR Solvency (< 3.0x)         │
                                 │  • CFO/EBITDA Conversion (< 0.65)│
                                 │  • Promoter Pledging (> 10%)     │
                                 │  • Piotroski F-Score (< 7/9)     │
                                 │  • Audit Qualifications (Regex)  │
                                 └────────────────┬─────────────────┘
                                                  │ (Writes rejections.csv)
                                                  ▼
                                 ┌──────────────────────────────────┐
                                 │    ~200-300 Clean Survivors      │
                                 └────────────────┬─────────────────┘
                                                  │
                                                  ▼
                                 ┌──────────────────────────────────┐
                                 │  Phase 3: 12-Month Momentum Rank │
                                 │  • Composite 2F (12-1 Mom + Del) │
                                 │  • Top 10-15 Stocks (8-10% each) │
                                 │  • Annual Rebalance (Low Churn)  │
                                 └────────────────┬─────────────────┘
                                                  │
                                                  ▼
                                 ┌──────────────────────────────────┐
                                 │  Phase 4: Multi-Asset Risk Shell │
                                 │  • 70% Clean Momentum Basket     │
                                 │  • 15% Sovereign Gold (GOLDBEES) │
                                 │  • 15% Liquid/Cash (LIQUIDBEES)  │
                                 └──────────────────────────────────┘
```

---

## Accounting & Data Schema (`data/duckdb/quant.duckdb`)

All tables are created in the existing DuckDB database:

```sql
CREATE TABLE IF NOT EXISTS financials_annual (
    symbol VARCHAR,
    fy_year INTEGER,
    filing_date DATE,
    is_consolidated BOOLEAN,
    -- P&L
    revenue DOUBLE,
    cogs DOUBLE,
    ebitda DOUBLE,
    depreciation DOUBLE,
    finance_cost DOUBLE,
    tax_expense DOUBLE,
    pat DOUBLE,
    -- Balance Sheet
    total_assets DOUBLE,
    net_worth DOUBLE,
    total_debt DOUBLE,
    current_assets DOUBLE,
    current_liabilities DOUBLE,
    receivables DOUBLE,
    inventory DOUBLE,
    cwip DOUBLE,
    gross_block DOUBLE,
    shares_outstanding DOUBLE,
    -- Cash Flow
    cfo DOUBLE,
    capex DOUBLE,
    cfi DOUBLE,
    cff DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, fy_year, is_consolidated)
);

CREATE TABLE IF NOT EXISTS financials_bfsi (
    symbol VARCHAR,
    fy_year INTEGER,
    filing_date DATE,
    npa_gross DOUBLE,
    npa_net DOUBLE,
    advances DOUBLE,
    deposits DOUBLE,
    car DOUBLE,
    pcr DOUBLE,
    nim DOUBLE,
    pat DOUBLE,
    total_assets DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, fy_year)
);

CREATE TABLE IF NOT EXISTS shareholding_reported (
    symbol VARCHAR,
    quarter_end DATE,
    promoter_pct DOUBLE,
    pledged_pct DOUBLE,
    fii_pct DOUBLE,
    dii_pct DOUBLE,
    public_pct DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, quarter_end)
);
```

---

## Phase 0 — Config, Schema & Universe Integration (Day 1: 3 Hours)

### Objective
Wire the database tables, universe resolution, and configuration without creating parallel files or changing existing conventions.

### Tasks for Developer
1. **Config Expansion (`config.yaml`)**:
   Add a `fundamental` block to `config.yaml`:
   ```yaml
   fundamental:
     rate_limits:
       screener_delay_sec: 4.0
       jitter_sec: 1.5
       cooldown_after_requests: 40
       cooldown_sec: 45
     forensics:
       sloan_accrual_max: 0.10
       icr_min: 3.0
       cfo_ebitda_min: 0.65
       promoter_pledge_max_pct: 10.0
       piotroski_f_min: 7
       debt_equity_max: 1.0
     portfolio:
       holding_period_months: 12
       target_positions: 12
       max_weight_per_stock: 0.10
       cash_buffer_pct: 0.15
       gold_buffer_pct: 0.15
   ```
2. **Schema Module (`src/fundamental/schema.py`)**:
   Implement table creation and verification functions using `src.config` and DuckDB connection routines.
3. **Symbol Master Bridge (`src/fundamental/universe.py`)**:
   Map NSE symbols to BSE Scrip codes using the existing `EQUITY_L` table and official NSE/BSE mappings.

### Verification & Criteria
* Run: `python -m src.fundamental.schema`
  * **Expected Result**: Exit code 0. Tables created, schema verified with dummy insert/rollback.
* Run: `python -m src.fundamental.universe`
  * **Expected Result**: $\ge 98\%$ of the top-1500 universe successfully mapped to BSE scrips.

---

## Phase 1 — Ingestion Engine (Day 1-2: 6 Hours)

### Objective
Ingest 10 years of annual balance sheet, P&L, cash flow, and shareholding data for the top-1500 universe with caching and zero data loss.

### Tasks for Developer
1. **BSE XBRL Ingester (`src/fundamental/bse_xbrl.py`)**:
   * Download official IND-AS XBRL filings (zip/xml) from BSE.
   * Parse taxonomy using stdlib `xml.etree.cElementTree`.
   * Standardize extraction for: `RevenueFromOperations`, `ProfitLossForPeriod`, `CashFlowFromUsedInOperatingActivities`, `FinanceCosts`, `CapitalWorkInProgress`, `TradeReceivables`.
   * Prioritize Consolidated financial context; fall back to Standalone only if Consolidated is absent.
2. **Polite Screener Backup (`src/fundamental/screener.py`)**:
   * Token-bucket rate limiter: 3.5s–5.0s delay with randomized jitter.
   * Store raw responses to `data/raw/screener/{symbol}.json`.
   * Cache-first: if file exists on disk, network call is skipped entirely.
3. **Unified Normalizer (`src/fundamental/normalize.py`)**:
   * Normalizes fields into `financials_annual` and `financials_bfsi`.
   * Identifies BFSI entities via industry code or keywords (`BANK`, `FINANCE`, `HOUSING`, `CAPITAL`) to route to `financials_bfsi`.

### Verification & Criteria
* Test with 10 sample companies (e.g., RELIANCE, TCS, HDFCBANK, INFOSYS, INFY):
  * **Expected Result**: Revenue, PAT, and CFO match audited annual reports to the rupee.
* Network resilience test: Simulate HTTP 429; verify exponential backoff triggers without program crash.

---

## Phase 2 — Mathematical Forensic Rules Engine (Pre-Registered Experiment E028)

### Objective
Filter the universe down from 1,500 names to a clean basket of 200–300 companies by eliminating accounting red flags, debt distress, and capital leakage.

### The Forensic Elimination Rules
1. **Sloan Accrual Anomaly**:
   $$\text{Accrual Ratio} = \frac{\text{PAT} - \text{CFO}}{\text{Total Assets}} > 0.10 \implies \text{FAIL (Aggressive Accounting)}$$
2. **Interest Coverage Ratio (ICR)**:
   $$\text{ICR} = \frac{\text{PAT} + \text{Tax} + \text{Finance Cost}}{\text{Finance Cost}} < 3.0 \implies \text{FAIL (Insolvent / Debt Stress)}$$
3. **Cash Conversion Health**:
   $$\frac{\text{CFO}}{\text{EBITDA}} < 0.65 \quad \text{or} \quad (\text{PAT} > 0 \text{ and } \text{CFO} < 0) \implies \text{FAIL (Earnings Not Backed by Cash)}$$
4. **Working Capital Divergence (Channel Stuffing)**:
   $$\Delta \% \text{Receivables} - \Delta \% \text{Revenue} > 25\% \implies \text{FAIL (Uncollected Revenue)}$$
5. **Asset Siphoning via CWIP**:
   $$\frac{\text{CWIP}}{\text{Gross Block}} > 0.35 \text{ for } \ge 3 \text{ consecutive years} \implies \text{FAIL (Unfinished Projects / Leakage)}$$
6. **Promoter Pledging Hard Veto**:
   $$\text{Pledged \% of Promoter Holding} > 10.0\% \implies \text{FAIL (Vulnerable to Margin Calls)}$$
7. **Piotroski F-Score**:
   $$\text{Score} < 7 / 9 \implies \text{FAIL (Operational Deterioration)}$$
8. **Regex Audit Opinion Filter (`src/fundamental/audit_regex.py`)**:
   Scan Independent Auditor's Reports using regex:
   * Hard Veto: `qualified opinion`, `adverse opinion`, `disclaimer of opinion`, `material uncertainty related to going concern`.
   * Flag: `emphasis of matter`.

### Pre-Registered Experiment Protocol (E028)
* **Hypothesis**: The deterministic forensic screen eliminates $\ge 90\%$ of known historical corporate distress cases while falsely eliminating $\le 15\%$ of clean Nifty 50 compounders.
* **Test Set (Known Canaries)**:
  * DHFL (FY18), Manpasand Beverages (FY18), Cox & Kings (FY18), Yes Bank (FY19), Reliance Communications (FY17), PC Jeweller (FY18).
* **Control Set (Clean Blue Chips)**:
  * TCS, HUL, Titan, Infosys, Asian Paints, Bajaj Auto.

### Verification & Criteria
* Run: `python -m src.fundamental.forensics`
  * **PASS**: $\ge 90\%$ of Canaries rejected AND $\ge 85\%$ of Clean Blue Chips pass.
  * **Output**: Generates `data/reports/rejections.csv` logging every eliminated scrip with its specific trigger value.

---

## Phase 3 — The 12-Month Clean Momentum Strategy (Experiment E029)

### Objective
Replace the failed monthly-rebalance engine with an annual holding / 12-month cohort momentum strategy on the forensically cleaned universe.

### Strategy Construction
1. **Universe**: Only stocks passing Phase 2 forensic elimination AND trading with trailing-20 median turnover $\ge ₹1.5\text{ Cr}$ (preventing illiquidity traps).
2. **Signal**: Validated `composite_2f` = mean percentile rank of:
   * `mom_12m_1m` (12-month momentum skipping the most recent month).
   * `delivery_pct` (delivery volume as percentage of total volume).
3. **Portfolio Allocation**:
   * Select top **12 stocks**.
   * Equal weight ($1/12 \approx 8.33\%$ each).
   * **Rebalance Frequency**: Rebalanced once every 12 months (or four overlapping quarterly cohorts of 3 stocks each to smooth timing luck).
4. **Friction Accounting**: Real delivery costs = 0.105%/side (STT, stamp duty, GST, exchange charges, brokerage). Churn is $\le 20-25\%$ per year, so transaction drag is $< 0.1\%$ per year.

### Pre-Registered Experiment Protocol (E029)
* **Hypothesis**: 12-Month Clean Momentum beats both Nifty 500 TRI and the Equal-Weight Universe over the 15-year history net of transaction costs, with Sharpe ratio $\ge 0.85$ and max drawdown $\le -35\%$.
* **Comparative Arms**:
  * Arm A: Unfiltered 12-month momentum (all top-1500 names).
  * Arm B: Forensically cleaned 12-month momentum (post-Phase 2).
  * Benchmark 1: Nifty 500 TRI.
  * Benchmark 2: Equal-Weight Top-1500 Universe.

### Verification & Criteria
* Run: `python -m src.backtest.clean_momentum`
  * **PASS**: Arm B CAGR exceeds Nifty 500 TRI by $\ge 4.0\text{ pp/year}$ net of costs, AND Arm B max drawdown is at least 8.0 pp better than Arm A.
  * **Output**: `experiments/029_clean_momentum/results.json` and `verdict.md`.

---

## Phase 4 — Multi-Asset & Structural Risk Architecture (Experiment E030)

### Objective
Solve the equity drawdown problem structurally across uncorrelated asset classes rather than relying on failing single-stock stop-losses.

### Strategy Shell
Instead of 100% equity allocation, deploy capital into an all-weather Core-Satellite shell:
* **70% Equity Satellite**: The Phase 3 Clean Momentum portfolio (12 high-conviction compounders).
* **15% Gold Allocation**: Sovereign Gold / Gold ETF (`GOLDBEES`), providing inverse correlation during global and geopolitical shocks.
* **15% Cash / Liquid**: Liquid ETF (`LIQUIDBEES`) or Treasury arbitrage, acting as dry powder and reducing portfolio volatility.

### Dynamic Trend Protection (Asset-Level, NOT Stock-Level)
* Evaluate Nifty 500 on a monthly basis against its 10-month (200-session) moving average:
  * If Nifty 500 is **above** 10-month SMA: Maintain full 70% Equity exposure.
  * If Nifty 500 is **below** 10-month SMA: Shift half of the equity allocation ($35\%$) into `LIQUIDBEES` upon scheduled rebalance.
  * *Why this works when stock stops failed*: Stock-level stops whipsaw on daily noise. Broad index trend-following over monthly closes only triggers in severe structural bear markets (2008, 2020) and avoids false intraday exits.

### Pre-Registered Experiment Protocol (E030)
* **Hypothesis**: The Multi-Asset Shell compresses maximum drawdown from $-47\%$ to $\le -22\%$ while preserving $\ge 16\%$ CAGR over 15 years.
* **Verification**: Run `python -m src.backtest.multi_asset_shell`. Verify max drawdown severity and Sharpe ratio improvement.

---

## Phase 5 — Production Pipeline & Investment Dossiers (Day 3: 4 Hours)

### Objective
Provide a unified CLI runner that produces clean portfolio picks, elimination audit trails, and 1-page investment dossiers for human review.

### Deliverables
1. **Runner Module (`src/fundamental/run.py`)**:
   * Single command: `python -m src.fundamental.run`
   * Performs: Ingestion sync $\rightarrow$ Forensic elimination $\rightarrow$ Momentum ranking $\rightarrow$ Multi-asset sizing.
2. **Rejection Audit Trail (`data/reports/rejections.csv`)**:
   * Columns: `symbol`, `fy_year`, `failed_rule`, `metric_value`, `threshold_value`, `status`.
3. **Markdown Dossier Generator (`reports/investment_dossier_latest.md`)**:
   * Produces a clean 1-page profile for each of the top 12 selected companies:
     * Business & Capital Allocation: 5Y Sales/PAT CAGR, 5Y Average ROIC, Free Cash Flow.
     * Forensic Health: Sloan Accrual score, ICR, CFO/EBITDA, Piotroski F-Score.
     * Governance & Audit: Regex audit verdict, promoter pledging status.
     * Allocation & Position Size: Target rupee amount and percentage of portfolio.

---

## Summary of Milestones & Deliverables

| Phase | Output Artifacts | Primary Verification Command | Pass/Fail Criteria |
|---|---|---|---|
| **Phase 0** | Schema in `quant.duckdb`, `universe.py` | `python -m src.fundamental.schema` | All 3 tables exist; universe bridge $\ge 98\%$ |
| **Phase 1** | Ingested financials in DuckDB, local cache | `python -m src.fundamental.normalize` | 50 test stocks ingested; zero PK collisions |
| **Phase 2** | `data/reports/rejections.csv`, Experiment E028 | `python -m src.fundamental.forensics` | $\ge 90\%$ canaries rejected, $\ge 85\%$ blue chips pass |
| **Phase 3** | Experiment E029, 12-month clean momentum engine | `python -m src.backtest.clean_momentum` | CAGR $\ge \text{Index} + 4\%$, Churn $< 25\%$/yr |
| **Phase 4** | Experiment E030, Multi-asset shell | `python -m src.backtest.multi_asset_shell` | Max Drawdown $\le -22\%$, Sharpe $\ge 1.0$ |
| **Phase 5** | `reports/investment_dossier_latest.md` | `python -m src.fundamental.run` | Execution completes in $< 2$ mins on cache |
