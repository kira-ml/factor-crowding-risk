# Measuring the Crowd: Detecting Factor Capacity Risk and Modeling Alpha Decay in U.S. Equities

A data science project investigating whether observable crowding metrics can predict the degradation of factor performance in the S&P 500.

---

## Overview

In quantitative investing, a consistently profitable trading signal is a finite resource. As more capital chases well-known factors like value or momentum, the very act of trading can erode the signal's future profitability—a phenomenon known as **alpha decay**.

This project asks: **Can we detect when a factor becomes "crowded" and quantify the subsequent decline in its predictive power?**

The goal is not to find new alpha. It is to build a capacity-aware risk management tool that helps a hypothetical systematic manager decide *when to reduce exposure* to their own signals. The work frames crowding as an anomaly detection problem in the cross-sectional behavior of factor portfolios, demonstrating an understanding of implementation challenges that separate backtest-driven research from investable strategies.

---

## Investment Motivation

For a quantitative fund, factor crowding represents a critical, non-diversifiable business risk. It can lead to sharp, correlated drawdowns when crowded trades unwind—as seen in the August 2007 quant crisis.

A fund that can systematically measure crowding in its own strategies can make better capital allocation decisions. Instead of passively suffering through a decay cycle, a portfolio manager could use a crowding score to:

- Dynamically reduce position sizes
- Tactically hedge exposure
- Rotate capital toward less-crowded signals

This project develops a quantitative framework to move crowding from an anecdotal concern to a measurable, monitorable metric.

---

## Research Question

Can we construct a cross-sectional crowding score for standard equity factors (Value, Momentum) that reliably predicts the future decay of that factor's information coefficient (IC)?

Specifically: **Do anomalous patterns of high correlation and concentrated ownership within a factor's top-quintile stocks precede a statistically significant decline in forward-looking factor performance?**

---

## Project Scope

| Dimension | Specification |
|-----------|---------------|
| **Factors** | Momentum (12-1 month) and Book-to-Market (Value) |
| **Universe** | S&P 500 constituents |
| **Lookback Period** | 5 years of daily data |
| **Crowding Proxies** | 5 interpretable metrics (see Feature Engineering) |
| **Prediction Target** | Forward 1-month and 3-month factor rank IC |
| **Modeling Approach** | Two-stage: baseline → advanced (staged on baseline results) |
| **Output** | Interpretable crowding scores, decay analysis, comparative backtest |

---

## Data Sources

| Source | Data | Frequency |
|--------|------|-----------|
| `yfinance` | S&P 500 constituent prices, volumes, short interest | Daily |
| Ken French Data Library | Fama-French factor returns (or replicate simple factor definitions) | Daily/Monthly |
| SEC EDGAR (13F filings) | Institutional ownership data | Quarterly (lagged 45 days) |

---

## Feature Engineering

Five crowding proxies are constructed from raw data:

| # | Feature | Description | Rationale |
|---|---------|-------------|-----------|
| 1 | **Pairwise Correlation** | Average pairwise correlation of daily returns among stocks in the factor's top decile | High correlation suggests investors are piling into the same names |
| 2 | **Herfindahl-Hirschman Index (HHI)** | Concentration of factor exposure across the universe | Rising HHI indicates the factor bet is becoming less diversified |
| 3 | **Valuation Spread** | Difference in median P/B (or P/E) between top and bottom factor quintiles | Compressed spreads suggest the factor is "priced for perfection" |
| 4 | **Institutional Ownership Concentration** | HHI of 13F institutional ownership within the top decile | Measures whether a few large funds dominate the positions |
| 5 | **Short Interest** | Average `shortPercentOfFloat` for top-decile stocks | Elevated short interest can signal crowding in the opposite direction or increased fragility |

All 13F-derived features are constructed with a strict 45-day lag to eliminate look-ahead bias.

---

## Modeling Strategy

The modeling follows a staged approach: establish a simple, interpretable baseline before considering more complex methods.

### Baseline Models

#### 1. Composite Z-Score + Logistic Regression
Average the five normalized crowding proxies into a single crowding Z-score. Use this score in a logistic regression to predict whether the forward 3-month factor return is negative (binary classification).

**Why this baseline:** It is fully transparent. Any portfolio manager can understand and interrogate it. It directly tests the core hypothesis with no black-box complexity.

#### 2. Single-Feature Linear Decay Model
Use a univariate linear regression with only the "pairwise correlation of top-decile stocks" to predict forward factor IC.

**Why this baseline:** It isolates the most intuitive crowding mechanism and establishes a critical lower bound that more complex models must beat to justify their use.

### Advanced Models

*Only pursued if baseline results indicate a meaningful but potentially non-linear signal.*

#### 1. Isolation Forest for Regime Identification
Train an Isolation Forest on the full five-dimensional feature space. Use the anomaly score to segment time periods into "crowded" and "normal" regimes. Compare mean forward ICs between the two regimes.

**Why this is justified:** If the linear baseline shows a weak signal, crowding likely matters only in extreme tails. Isolation Forest is designed for unsupervised anomaly detection and treats crowding as a structural break rather than a smooth linear function.

#### 2. LightGBM for Non-Linear Alpha Decay Prediction
Train a LightGBM regressor to predict continuous forward factor IC from all five crowding features. Analyze feature importance and partial dependence plots to understand interaction effects.

**Why this is justified:** Simple models cannot capture complex interactions (e.g., high correlation might only be dangerous when combined with extreme valuations). LightGBM learns these threshold effects automatically while maintaining interpretability through feature importance metrics.

---

## Evaluation Framework

The project is evaluated on practical utility, not just statistical metrics:

| Metric | What It Measures |
|--------|------------------|
| **Correlation (crowding score vs. forward IC)** | Does the score have predictive signal? |
| **Precision/Recall of crowded vs. normal regime flags** | Can we identify danger zones? |
| **Backtest comparison** | Does a crowding-aware sizing rule improve risk-adjusted outcomes? |

### Backtest Design

Two strategies are compared over the same out-of-sample period:
1. **Static allocation:** Constant 100% exposure to the factor
2. **Crowding-aware allocation:** Position size reduced to 50% when the composite crowding score exceeds the 75th percentile of its historical distribution

Evaluation metrics: Sharpe ratio, maximum drawdown, and annualized volatility.

---

## Assumptions

- Crowding is measurable through the convergence of behavior (high correlation) and saturation of ownership (concentration) within the most desirable quintile of a factor.
- Publicly available 13F and price data are sufficient to construct a meaningful, albeit lagged, real-time crowding estimate.
- Academic factor definitions are reasonable proxies for systematic signals used in practice.
- Alpha decay from crowding is just one of several sources of factor drawdown; this project does not control for macroeconomic regimes or volatility shifts.

---

## Constraints & Limitations

- **Data Lag:** 13F data is reported on a 45-day delay. The analysis explicitly simulates this "as-of" dating to avoid look-ahead bias.
- **Attribution, Not Causation:** A 2-3 day project cannot build a causal model of fund flows. The scope is limited to identifying a robust statistical relationship.
- **Factor Scope:** Only two factors are analyzed to keep the project feasible within the time constraint.
- **Universe:** Limited to S&P 500 large-cap equities where crowding effects are most economically relevant.

---

## Repository Structure

```
factor-crowding-risk/
├── README.md                        # Project overview and documentation
├── notebooks/
│   ├── 01_data_acquisition.ipynb    # Download and clean price, 13F, and factor data
│   ├── 02_feature_engineering.ipynb # Construct five crowding proxies
│   ├── 03_baseline_models.ipynb     # Z-score logistic regression and linear decay model
│   ├── 04_advanced_models.ipynb     # Isolation Forest and LightGBM (conditional on baseline)
│   └── 05_backtest_and_viz.ipynb    # Comparative backtest and final visualizations
├── src/
│   ├── data.py                      # Data loading and preprocessing utilities
│   ├── features.py                  # Feature engineering functions
│   ├── models.py                    # Model training and evaluation functions
│   └── viz.py                       # Visualization helpers
├── data/                            # Cached data files (gitignored)
├── outputs/                         # Saved figures and results
├── requirements.txt
└── .gitignore
```

---

## Setup & Installation

```bash
# Clone the repository
git clone https://github.com/kira-ml/factor-crowding-risk.git
cd factor-crowding-risk

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Dependencies

```
pandas>=1.5.0
numpy>=1.23.0
yfinance>=0.2.0
scikit-learn>=1.2.0
lightgbm>=3.3.0
matplotlib>=3.6.0
seaborn>=0.12.0
scipy>=1.9.0
requests>=2.28.0
```

---

## Estimated Completion Time

**2–3 days** for an experienced practitioner:
- **Day 1:** Data acquisition, cleaning, and feature engineering
- **Day 2:** Baseline model implementation and evaluation
- **Day 3:** Advanced models (if warranted), backtest, and visualizations

---

## Key Results

*[To be completed after implementation]*

- Did the composite crowding score show a statistically significant negative correlation with forward factor IC?
- Did the crowding-aware dynamic sizing strategy improve the Sharpe ratio and reduce max drawdown relative to static allocation?
- Which crowding proxy contributed the most predictive signal?

---

## Portfolio Signal

This project is designed to demonstrate:

- **Strong problem formulation:** Framing a real investment risk problem before writing code
- **ML judgment:** Staging models from simple to complex based on evidence
- **Feature engineering:** Constructing theory-driven proxies for an unobservable phenomenon
- **Experimental design:** Rigorous handling of data lags, look-ahead bias, and evaluation
- **Financial intuition:** Understanding capacity constraints, implementation costs, and signal decay
- **Scientific thinking:** Clear assumptions, honest limitations, and hypothesis-driven analysis
- **Communication:** Readable code, clear documentation, and interpretable visualizations

It signals to hiring managers at quantitative funds and asset managers that the author thinks about models as part of a complex system—not as standalone solutions.

---

## License

MIT

---

## Author

**Ken Ira Lacson**

- GitHub: [github.com/kira-ml](https://github.com/kira-ml)
- LinkedIn: [linkedin.com/in/ken-ira-lacson-852026343](https://www.linkedin.com/in/ken-ira-lacson-852026343/)

---

*This project was developed as a portfolio demonstration of applied machine learning for quantitative finance. It is not investment advice and does not claim to generate alpha or beat the market.*
