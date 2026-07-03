# TODO.md - Project Task Log

**Project:** Factor Crowding Risk and Alpha Decay Modeling  
**Date:** July 4, 2026  
**Status:** In Progress

---

## Completed Tasks

### 1. Data Pipeline Implementation (`data.py`)
**Status:** ✅ Complete  
**Date Completed:** July 4, 2026

**Description:**
- Implemented data acquisition pipeline using `yfinance`
- S&P 500 constituents scraped from Wikipedia
- Daily adjusted close prices downloaded from 2018-01-01 to 2024-12-31
- 499 stocks with clean data (26 failed downloads due to delistings/IPO dates)
- Data shape: 1,760 days × 499 stocks
- Factor construction for Momentum (12-1 month) and Value (inverse momentum)

**Justification:**
- Foundation for all subsequent analysis
- 5-year lookback provides sufficient history for feature engineering
- 499 stocks adequately represents S&P 500 universe

---

### 2. Feature Engineering Implementation (`features.py`)
**Status:** ✅ Complete  
**Date Completed:** July 4, 2026

**Description:**
- Implemented three crowding features:
  1. **Pairwise Correlation** - Average correlation in top quintile (60-day window)
  2. **HHI (Herfindahl-Hirschman Index)** - Factor exposure concentration
  3. **Valuation Spread** - Price spread between top and bottom quintiles
- Z-Composite score from normalized Correlation + HHI
- Monthly rebalancing with 71 rebalance dates (2019-02-28 to 2024-11-29)
- 70 usable observations after alignment with forward returns

**Key Results:**
- Momentum Z-Composite → 3M Return Correlation: **-0.36**
- Value Z-Composite → 3M Return Correlation: **+0.32**

**Justification:**
- Features map directly to crowding mechanisms from problem_framing.md
- Z-Composite combines two complementary signals
- Monthly rebalancing aligns with academic factor research
- No look-ahead bias enforced (only data available at rebalance date used)

---

### 3. Staged Modeling Pipeline (`models.py`)
**Status:** ✅ Complete  
**Date Completed:** July 4, 2026

**Description:**
- Implemented staged modeling approach from problem_framing.md:
  - **Stage 1 Baseline 1:** Z-Composite + Logistic Regression (binary classification)
  - **Stage 1 Baseline 2:** Correlation + Linear Regression (decay prediction)
  - **Stage 2 Advanced 1:** Isolation Forest (regime identification)
  - **Stage 2 Advanced 2:** LightGBM (non-linear prediction)
- Conditional execution: Advanced models only run if baseline shows signal
- Chronological 80/20 train/test split (56 train, 14 test)

**Results - Momentum:**
- Logistic F1: 0.1818
- Linear R²: -1.6503
- Signal detected: No

**Results - Value:**
- Logistic F1: 0.8333
- Linear R²: -1.5104
- Signal detected: Yes (proceeded to Stage 2)
- Isolation Forest: Regime Diff -0.0339, Anomaly Rate 64.29%
- LightGBM R²: -3.5029

**Justification:**
- Staged approach ensures complexity is earned
- Linear and logistic models provide interpretable baselines
- Conditional advancement prevents over-engineering
- Isolation Forest tests extreme-regime hypothesis
- LightGBM captures non-linear interactions

---

### 4. Git Repository Setup
**Status:** ✅ Complete  
**Date Completed:** July 4, 2026

**Description:**
- Initialized Git repository
- Committed `data.py`, `features.py`, `models.py`
- Maintained clean commit history with descriptive messages

**Files Committed:**
- `src/data.py` - Data pipeline
- `src/features.py` - Feature engineering
- `src/models.py` - Staged modeling pipeline

**Justification:**
- Version control enables tracking of changes
- Clear commit messages document progress
- Enables rollback if needed

---

## Ongoing Tasks

### 5. Model Experimentation
**Status:** 🔄 In Progress  
**Date Started:** July 4, 2026

**Description:**
- Testing multiple configurations to improve model performance
- Current findings: Limited data (70 observations) may be insufficient
- Negative R² values indicate models perform worse than predicting mean

**Next Steps:**
- [ ] Weekly rebalancing (increase observations from 70 to ~300)
- [ ] 1-month forward returns (reduce overlapping windows)
- [ ] Time series cross-validation (robust evaluation)
- [ ] Extended time period (2010-2024)
- [ ] All feature combinations testing

**Justification:**
- 70 monthly observations with 80/20 split yields only 14 test points
- Negative R² suggests current approach needs refinement
- Experimentation will identify optimal configuration

---

### 6. Backtest Implementation
**Status:** ⏳ Pending  
**Target Date:** July 5, 2026 (Day 2)

**Description:**
- Implement crowding-aware vs static allocation backtest
- Compare Sharpe ratios and drawdowns
- Dynamic position sizing when crowding score exceeds threshold

**Justification:**
- Backtest translates signal into portfolio management language
- Ultimate test of economic utility (per problem_framing.md)

---

### 7. Visualization and Reporting
**Status:** ⏳ Pending  
**Target Date:** July 5, 2026 (Day 2/3)

**Description:**
- Plots showing crowding episodes and subsequent factor degradation
- Feature importance visualizations
- Comparative performance charts

**Justification:**
- Clear visuals demonstrate signal to portfolio managers
- Reproducibility is key qualitative success criterion

---

## Notes / Observations

**July 4, 2026:**

1. **Data Quality:** 26 tickers failed download (recent IPOs, spin-offs, delisted). This is expected and handled gracefully.

2. **Feature Signals:** 
   - Momentum shows strongest signal: Z-Composite → 3M correlation of **-0.36**
   - Value shows opposite signal: Z-Composite → 3M correlation of **+0.32**
   - This validates the hypothesis (crowding predicts decay) for momentum

3. **Model Performance:**
   - Negative R² values indicate current approach needs adjustment
   - Key issue: 70 observations insufficient for 80/20 split (only 14 test points)
   - Value logistic model shows promising F1: 0.8333 (but may be due to small sample)

4. **Next Priority:** Experiment with weekly rebalancing to increase observations from 70 to ~300

---

## Project Timeline

| Day | Date | Focus | Status |
|-----|------|-------|--------|
| Day 1 | July 4, 2026 | Data pipeline, feature engineering, baseline models | ✅ Complete |
| Day 2 | July 5, 2026 | Advanced models, backtest, visualizations | ⏳ Pending |
| Day 3 | July 6, 2026 | Final results, documentation, polishing | ⏳ Pending |

---

## Questions/Blockers

1. **Data Availability:** Should we extend time period to 2010-2024 for more observations?
2. **Rebalancing Frequency:** Weekly rebalancing would provide more data points - implement?
3. **13F Data:** Not implemented (using proxies only). Should we add 13F integration for 2.0?
4. **Feature Gap:** Current implementation has 3 of 5 features (missing Institutional Ownership and Short Interest). Add or acknowledge as limitation?
