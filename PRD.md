# Product Requirements Document (PRD)
## RWA Transparency & Risk Dashboard

**Author:** Victory  
**Version:** 1.0  
**Date:** May 2026  
**Status:** Active

---

## 1. Overview

### 1.1 Project Summary
The RWA Transparency & Risk Dashboard is an interactive data analytics application that monitors the health and risk profile of tokenized Real-World Assets (RWAs) on the Centrifuge protocol. It gives any observer a clear, at-a-glance understanding of collateral health and default risk signals across multiple deRWA pools — without needing to be a blockchain expert.

### 1.2 Background & Motivation
Centrifuge is a DeFi protocol that tokenizes real-world assets such as treasury bills, corporate loans, and equities, making them accessible on-chain. While the platform exposes raw data, there is no consolidated risk view that:
- Aggregates metrics across pools in one place
- Calculates a meaningful risk score from multiple signals
- Presents findings in a way that non-technical stakeholders can understand

This dashboard fills that gap.

### 1.3 Capstone Context
This project is the capstone deliverable for a Python for Data Analysis bootcamp by Analytic Sage. It demonstrates proficiency in data fetching, cleaning, feature engineering, risk modelling, visualisation, and interactive dashboard development.

---

## 2. Goals & Success Criteria

### 2.1 Goals
- Track collateral health across 4 Centrifuge deRWA pools in real time
- Surface early warning signals for potential defaults
- Present findings through a clean, interactive Streamlit dashboard
- Gracefully fall back to mock data when the live API is unavailable

### 2.2 Success Criteria
| Criteria | Measure |
|---|---|
| Dashboard loads without errors | On both live and mock data |
| Risk score calculated for all 4 pools | Score between 0–100 with colour coding |
| All 4 pages render correctly | No broken charts or missing data |
| Mock data fallback works | "Demo Mode" banner appears when API fails |
| Code is clean and documented | Comments explain every major decision |
| Project is version-controlled | All phases committed to GitHub |

---

## 3. Target Users

| User | Description | Need |
|---|---|---|
| Bootcamp reviewer | Assesses the capstone project | Sees clear code quality, analytical thinking, and working product |
| DeFi investor | Holds or considers RWA tokens | Wants to quickly assess pool risk without reading raw chain data |
| Risk analyst | Monitors protocol health | Needs consolidated signals and trend data in one view |

---

## 4. Scope

### 4.1 In Scope
- 4 Centrifuge deRWA pools: JAAA, JTRSY, CRDX, SPXA
- Per-pool snapshot metrics: APY, TVL, NAV, Total Issuance, Token Price
- Per-network breakdown: Ethereum, Arbitrum, Avalanche, Base
- 30-day historical trend data: TVL and Token Price
- Engineered risk score (0–100) per pool
- 4-page Streamlit dashboard
- Live API + mock data fallback architecture

### 4.2 Out of Scope
- RWA (institutional) pools — require 100K–500K minimum investment access
- User authentication or wallet connection
- Real-time streaming (data refreshes on page load only)
- Historical data beyond 30 days (v1)
- Mobile-optimised layout (v1)

---

## 5. Data Sources

### 5.1 Primary — Centrifuge / The Graph API
Centrifuge exposes pool data via The Graph, a decentralised indexing protocol queried using GraphQL.

- **Endpoint:** `https://api.centrifuge.io/`
- **Auth:** None required for public pool data
- **Stored in:** `data/fetcher.py`

### 5.2 Fallback — Mock Data
Realistic mock data modelled directly from the Centrifuge platform screenshots.

- **Stored in:** `data/mock_data.py`
- **Trigger:** Automatically used when the live API call fails
- **Indicator:** "Demo Mode" banner shown in the dashboard

### 5.3 Data Fields

| Field | Description | Used For |
|---|---|---|
| `pool_id` | Short identifier e.g. JAAA | Joins across tables |
| `pool_name` | Full token name | Display labels |
| `asset_type` | e.g. US Treasury Bills | Grouping and context |
| `apy` | Annual percentage yield | APY anomaly signal |
| `tvl` | Total Value Locked (USD) | Size metric, trend signal |
| `nav` | Net Asset Value | Collateral health |
| `total_issuance` | Total tokens issued | Collateral health |
| `token_price` | Price per token (target ~1.00) | Price deviation signal |
| `network` | Blockchain network name | Network breakdown view |
| `date` | Date of historical record | Trend charts |

---

## 6. Risk Scoring Model

The risk score is the analytical core of this project. It is a composite score from 0 to 100 built from three signals using NumPy.

### 6.1 Formula

```
Risk Score = (Price Deviation Score × 40%)
           + (TVL Trend Score       × 35%)
           + (APY Anomaly Score     × 25%)
```

### 6.2 Signal Definitions

**Price Deviation Score (40% weight)**
Measures how far the token price has drifted from its target of 1.00.
- Within ±2% → Low risk
- ±2% to ±5% → Medium risk
- Beyond ±5% → High risk

**TVL Trend Score (35% weight)**
Measures whether total value locked is growing or shrinking over 30 days.
- Growing or stable → Low risk
- Gradual decline → Medium risk
- Sharp decline → High risk

**APY Anomaly Score (25% weight)**
Flags yields that are suspiciously high (desperate for capital) or zero (non-functioning).
- Normal range (1%–10%) → Low risk
- 0% APY → Medium-High risk flag
- Above 15% → High risk flag

### 6.3 Risk Tiers

| Score | Tier | Colour |
|---|---|---|
| 0 – 30 | Low Risk | 🟢 Green |
| 31 – 60 | Medium Risk | 🟡 Yellow |
| 61 – 100 | High Risk | 🔴 Red |

---

## 7. Dashboard Pages

### Page 1 — Overview
**Purpose:** Give a full picture of all pools at a glance.
- Total TVL KPI card (sum across all pools)
- Average risk score KPI card
- Bar chart: TVL comparison across pools
- Risk summary table with colour-coded risk tiers

### Page 2 — Pool Deep Dive
**Purpose:** Explore a single pool in detail.
- Dropdown selector to choose a pool
- KPI cards: APY, TVL, Token Price, NAV
- Bar chart: network breakdown of NAV
- Risk score display with tier label

### Page 3 — Risk Signals
**Purpose:** Surface all active warning flags.
- All pools ranked by risk score (highest risk first)
- Price deviation flag: any token deviating beyond ±5% from 1.00
- APY anomaly highlights (0% or unusually high)
- Written risk commentary per flagged pool

### Page 4 — Collateral Health
**Purpose:** Assess the backing quality of each pool.
- NAV vs Total Issuance side-by-side bar chart
- Collateral ratio calculated per pool (NAV ÷ Total Issuance)
- 30-day TVL trend line chart (all pools overlaid)
- 30-day token price trend line chart

---

## 8. Technical Architecture

### 8.1 Project Structure
```
RTR_DASHBOARD_PROJECT/
├── PRD.md
├── app.py                    ← Streamlit entry point
├── .env                      ← API config
├── .gitignore
├── requirements.txt
├── data/
│   ├── fetcher.py            ← Live API logic
│   ├── mock_data.py          ← Fallback mock data
│   └── processor.py          ← Pandas cleaning & feature engineering
├── analysis/
│   └── risk_engine.py        ← NumPy risk scoring
└── visuals/
    └── charts.py             ← Matplotlib / Seaborn chart functions
```

### 8.2 Data Flow
```
app.py
  └── fetcher.py (try live API)
        ├── Success → processor.py → risk_engine.py → charts.py
        └── Failure → mock_data.py → processor.py → risk_engine.py → charts.py
```

### 8.3 Tech Stack
| Tool | Purpose |
|---|---|
| Python 3.10+ | Core language |
| Pandas | Data cleaning and transformation |
| NumPy | Risk score calculations |
| Matplotlib / Seaborn | Charts and visualisations |
| Streamlit | Interactive dashboard framework |
| Requests | HTTP calls to Centrifuge API |
| python-dotenv | Load secrets from .env file |

---

## 9. Build Phases

| Phase | File | Description | Status |
|---|---|---|---|
| 1 | `data/mock_data.py` | Realistic mock data for all pools | ✅ Complete |
| 2 | `data/fetcher.py` | Live API call with mock fallback | 🔄 Up Next |
| 3 | `data/processor.py` | Data cleaning and feature engineering | ⏳ Pending |
| 4 | `analysis/risk_engine.py` | Risk scoring formula | ⏳ Pending |
| 5 | `visuals/charts.py` | All chart functions | ⏳ Pending |
| 6 | `app.py` | Streamlit dashboard (all 4 pages) | ⏳ Pending |

---

## 10. Constraints & Assumptions

- Centrifuge's public API may change structure without notice — mock fallback mitigates this
- Historical data is simulated in v1; a future version could source real on-chain history
- Token prices for RWA tokens are expected to stay close to 1.00 by design
- All monetary values are in USD
- Dashboard is read-only — no write operations to any blockchain or API

---

## 11. Future Improvements (v2)

- Add email or Slack alerts when a pool enters High Risk tier
- Expand to RWA (institutional) pools
- Pull real historical data from on-chain subgraph instead of simulating it
- Add more protocols beyond Centrifuge (e.g. Maple Finance, Goldfinch)
- Mobile-responsive layout

---

*This document reflects decisions made during the project planning phase and will be updated as the build progresses.*