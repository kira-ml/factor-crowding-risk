# Problem Framing: Exit Risk and Capacity in Equity Factors

**Version 2.0. Supersedes the V1 framing, archived at `docs/archive/v1/problem_framing.md`.**
**Status: framing finalized. Implementation follows this document.**

---

## 1. The question, in one paragraph

A factor strategy is a claim on future returns that must be *held*. Holding it requires
capital, and exiting it requires liquidity. The V1 project asked whether crowding
predicts the sign of future factor returns. That question is close to unanswerable with
public price data and, more importantly, it is not the question a portfolio manager
actually faces. The question a manager faces is: **how much can I hold, and how bad is
the exit if everyone leaves at once?** V2 answers that. It measures the *liquidity-adjusted
fragility* of equity factor portfolios, estimates their *capacity* under a market-impact
model, and tests whether fragile factors suffer worse left tails than the volatility
alone would predict.

## 2. Why the original framing failed

Three independent problems, documented in full in `docs/audit_v1.md`.

### 2.1 The construct was not measurable with the data

Crowding is a latent state of *other investors' positioning*. Measuring it requires
holdings, flows, or prime-brokerage data. V1 had daily prices and used raw pairwise
correlation as a proxy. That proxy is dominated by market volatility: correlations rise
for every stock when the market falls. V1 therefore measured the volatility regime and
called it crowding. No amount of modelling fixes a proxy that is confounded with the
most obvious alternative explanation.

### 2.2 The target had almost no independent variation

Forward three-month factor returns sampled weekly overlap by twelve weeks out of
thirteen. A four-year sample contains roughly sixteen independent three-month
observations. V1 then classified the sign of that target and reported an F1 of 0.9483,
which the recorded confusion matrix shows to be the class base rate. The project was
not detecting decay; it was detecting that one factor fell in one window.

### 2.3 The decision was mis-specified

Even a correct forecast of a factor's mean return does not tell a manager what to do.
The binding constraints in real allocation are capacity, impact, and the risk of a
correlated exit. V1's backtest compared a de-risked portfolio with a fully invested one
and attributed the difference to a crowding signal. It never asked whether the same
result could be obtained by holding less, or by volatility targeting, both of which
require no crowding measurement at all.

## 3. The reframed problem

### 3.1 Statement

> **Can the exit risk and the capital capacity of an equity factor be measured ex ante,
> and does that measurement add information about the factor's left tail beyond
> volatility?**

Two measurable objects replace the single unmeasurable one:

- **Fragility**: how synchronized, concentrated, slow to exit, and consensus-driven the
  factor's active positions are. Observable from prices and volume.
- **Capacity**: the capital at which trading costs consume a stated fraction of the
  gross premium. A property of the strategy and the market, not of other investors'
  intentions.

### 3.2 Why this is a better problem

| Criterion | V1 framing | V2 framing |
| :--- | :--- | :--- |
| Construct measurable | No (latent positioning) | Yes (correlation, concentration, ADV, turnover) |
| Target has power | No (~16 independent blocks) | Yes (~250 effective four-week blocks) |
| Decision-relevant | Weakly (predict sign) | Directly (size, exit, capacity) |
| Falsifiable | No clear null | Pre-specified null and minimum detectable effect |
| Survives a null result | No | Yes: the capacity report is a deliverable either way |
| Distinct from known effects | No (volatility timing) | Tested against volatility management explicitly |

The last row matters. Moreira and Muir (2017) show that scaling exposure by inverse
realized volatility improves Sharpe ratios across many factors. Any "fragility overlay"
that is really a volatility overlay will be exposed by a volatility-managed control.
That control is mandatory in V2.

### 3.3 The payoff is asymmetric

| Outcome | Deliverable | Value |
| :--- | :--- | :--- |
| Fragility predicts the left tail beyond volatility | A risk signal with an economic mechanism and honest inference | High |
| Fragility does not predict the left tail | A tight null with a reported minimum detectable effect, plus the capacity report | Still useful |
| Capacity is small at plausible AUM | A direct constraint on strategy scale, which is actionable | High |

The project cannot end empty. That is deliberate: the empirical claim is uncertain, and
the engineering and measurement contribution does not depend on it.

---

## 4. Definitions

### 4.1 Notation

| Symbol | Meaning |
| :--- | :--- |
| `t` | Weekly rebalance date, Friday close |
| `U_t` | Point-in-time investable universe at `t` |
| `f` | Factor, one of `MOM`, `STREV`, `LOWVOL` |
| `s_{i,t}` | Factor signal for stock `i` at `t` |
| `w_{i,t}` | Active portfolio weight, dollar-neutral, `Σ|w| = 1` per leg |
| `r_{i,t+1}` | Next-period stock return |
| `r^f_t` | Factor return, `Σ_i w_{i,t} r_{i,t+1}` |
| `ADV_{i,t}` | Median daily dollar volume over the prior 60 trading days |
| `A` | Sleeve notional in dollars, one side |

### 4.2 Universe

At each `t`, `U_t` is the 500 stocks with the largest 60-day median dollar volume among
all candidates that have at least 252 trading days of history and a price of at least
$5. Membership is computed only from data available at `t`.

This is a *liquidity universe*, not an index. It is point-in-time with respect to
liquidity, price, and history, which removes the index-membership look-ahead in
V1. It is **not** point-in-time with respect to existence: the candidate pool is
current S&P 500/400 membership, and the panel contains zero delistings. This is
complete survivorship, disclosed and quantified in Section 8.

### 4.3 Factors

Three price-based factors, chosen because they have distinct economics, distinct
turnover, and distinct liquidity profiles:

| Factor | Signal | Economic content | Expected turnover |
| :--- | :--- | :--- | :--- |
| `MOM` | Cumulative return from `t-252` to `t-21` | Underreaction, information diffusion | Low |
| `STREV` | Negative return from `t-21` to `t` | Liquidity provision, overreaction | Very high |
| `LOWVOL` | Negative realized volatility over `t-252` to `t` | Leverage constraints, lottery aversion | Low |

Construction: signal winsorized at the 1st and 99th percentile, ranked
cross-sectionally, residualized on a 252-day rolling market beta in signal space,
and converted to weights with a per-name cap of 2% of gross exposure. Long the
top decile, short the bottom decile. Dollar-neutral and gross 2.0. The
construction is **not** beta-neutral: signal-space residualization removes most of
the tilt but not all of it. Realized CAPM beta and alpha are reported. See
ADR-0005.

There is no "value" factor. Value requires book equity or earnings, which this data
source does not provide. Claiming a price-based reversal signal is value was a V1 error
and will not be repeated.

**Invariant:** the three factor return series must not be pairwise collinear. A test
asserts `|corr| < 0.9` for every pair over the full sample. V1 would have failed this
test with a correlation of -1.0.

### 4.4 Fragility measures

Four families, each with a stated mechanism and a sign prediction. All are computed
from data at or before `t`.

**F1. Residual synchronization.** Average pairwise correlation of market-residual daily
returns within the long leg over the trailing 60 days, computed on a Ledoit-Wolf
shrinkage correlation matrix to handle the case where the number of names approaches the
number of days, then Fisher-z transformed.
*Mechanism:* correlated residual risk means holders share the same non-market exposure;
an unwind is common-mode.
*Prediction:* higher synchronization, worse left tail.

**F2. Effective breadth.** `N_eff = (Σ|w|)² / Σw²` on the active weights, reported both
unweighted and liquidity-weighted (`w_i` divided by `ADV_i` before normalization).
*Mechanism:* few independent bets means idiosyncratic shocks do not diversify.
*Prediction:* lower breadth, worse left tail.

**F3. Exit horizon.** Dollar-weighted days to liquidate the long leg at a 10%
participation rate for a reference sleeve size `A`:
`D_t = Σ_i |w_i| · A / (0.10 · ADV_{i,t})`.
*Mechanism:* the direct cost of a crowded exit; the quantity that binds capacity.
*Prediction:* longer exit horizon, worse left tail.

**F4. Consensus persistence.** Fraction of long-leg weight held in names that have been
in the long leg for six or more consecutive rebalances, with signal dispersion as a
robustness variant.
*Mechanism:* stale positioning means the marginal holder has not re-underwritten the
trade; nobody has left.
*Prediction:* higher persistence, worse left tail, with the caveat that slow factors
mechanically score higher.

Each measure is standardized with an **expanding** window, minimum 104 weeks, and
combined into a single composite by equal weight. The composite is the primary
independent variable; the four measures are secondary and subject to FDR control.

### 4.5 Capacity

Per-name temporary impact follows the square-root form used in practice
(Almgren et al., 2005; Frazzini, Israel and Moskowitz, 2018):

```
cost_i(A) = 0.5 · spread_i + c · σ_i · sqrt( Q_i(A) / ADV_i )
Q_i(A)    = |w_i| · A
```

with `c = 0.314` as the baseline, `spread_i = 5bp` for large caps, and sensitivity runs
at `c ∈ {0.1, 0.5}` and `spread ∈ {2bp, 15bp}`. Round-trip cost per rebalance is
`C(A) = Σ_i |Δw_i| · cost_i(A)`, and the net annualized premium is
`Π_net(A) = Π_gross − 52 · E[C(A)]`.

**Capacity** at hurdle `h` is the largest `A` with `Π_net(A) ≥ h · Π_gross`. Primary
`h = 0.5`; also reported at 0.25 and 0.75.

This is a model, not a measurement. Its inputs are estimated and its coefficient is
calibrated from published work. The deliverable is a curve with a sensitivity band, not
a point estimate. Section 8 states this as a limitation, and the report presents the band
alongside the headline.

### 4.6 Estimands

| ID | Estimand | Role |
| :--- | :--- | :--- |
| E1 | Quantile regression coefficient `β_τ` of the forward 4-week factor return on the standardized composite fragility, `τ = 0.10`, pooled across factors with factor fixed effects, controlling for volatility | **Primary** |
| E2 | Difference in expected shortfall, `ES_5%(high fragility) − ES_5%(low fragility)` | Secondary |
| E3 | Net-of-cost tail metrics of a fragility overlay versus a volatility-matched control at equal average exposure | Secondary, decision layer |
| E4 | Capacity curve and capacity at 50% premium retention, per factor | Descriptive |

`β_0.50` is estimated alongside `β_0.10`. The claim is *tail-specific*: fragility should
move the left tail without simply shifting the mean. If `β_0.10 ≈ β_0.50`, the measure is
a repackaged volatility or drift signal and will be reported as such.

---

## 5. Hypotheses and decision rules

Pre-specified before the final run. The study is **exploratory**, not
confirmatory: the construction was revised after inspecting results (ADR-0005,
ADR-0007), and there is no holdout. These are the rules that decide what the
project concludes.

### H1. Fragility is associated with a worse left tail

`β_0.10 < 0` in E1, with a stationary-bootstrap 95% interval excluding zero.
The composite is a single pre-specified test. The four individual measures are
secondary and are reported with Benjamini-Hochberg FDR-adjusted p-values.

**Pass:** the composite satisfies the sign and interval rule. Individual
measures may be weaker; they are labelled secondary.

### H2. The effect is not volatility

The coefficient in H1 must survive controls for 20-day EWMA realized factor
volatility, realized market volatility, trailing 12-week factor return, and a
liquidity-regime variable (median ADV growth).

**Pass:** `β_0.10` retains its sign and at least half its magnitude with the full
control set. If it does not, the finding is "fragility proxies volatility",
which is a real result and will be stated as one.

### H3. The overlay improves tail outcomes

The fragility overlay must beat a volatility-managed portfolio with the *same
average exposure* and the same overlay cost and borrow assumptions, on `ES_5%`
and maximum drawdown, over the test period, with a block-bootstrap interval on
the difference. The comparison is gross of the underlying factor's rebalancing
cost; capacity reports that separately.

**Pass:** both tail metrics improve and at least one improvement is significant
at 5%. Losing to the volatility-matched control is a substantive finding:
crowding adds nothing beyond volatility management.

### H4. Capacity orders the factors by turnover (descriptive)

At a fixed 100bp annual trading-cost-drag hurdle, `STREV` has lower capacity than
`MOM`, which has lower capacity than `LOWVOL`. This is a **deterministic identity
of the cost model**, not a hypothesis test. It is reported as a descriptive
decomposition. The substantive result is the level and its sensitivity to the
execution horizon, impact coefficient, spread, and assumed premium.

### Falsification conditions

The thesis is rejected, and the report says so, if any of the following holds:

1. The V1 reproduction shows that the constant predictor does **not** reproduce F1
   0.9483. Then the audit is wrong and must be revised before V2 continues.
2. E1 gives `β_0.10 ≥ 0`, or an interval that excludes any economically meaningful
   effect, with adequate power.
3. H2 fails: the effect vanishes under volatility controls.
4. H3 fails against the volatility-matched control.
5. The capacity curve is flat over $10M to $10B, implying impact is not binding at
   plausible scale and the capacity contribution is academic.

---

## 6. Identification and confounders

This is an observational study of a time series. Nothing here identifies a causal
effect of crowding on returns, and the report will not claim one.

| Confounder | Why it matters | Control |
| :--- | :--- | :--- |
| Market volatility | Raises correlation and worsens tails simultaneously | Residual correlations; EWMA vol controls; volatility-matched overlay |
| Liquidity regime | Illiquidity raises impact and crashes together | Exit horizon is liquidity-adjusted; median ADV control |
| Factor momentum | Recent returns predict both fragility and next returns | Trailing 12-week factor return control |
| Publication and decay trend | Factor premia decay over calendar time (McLean and Pontiff, 2016) | Subsample stability: pre-2010 vs post-2010 |
| Selection of the universe | Liquid names are the survivors | Point-in-time rule; survivorship bias quantified |
| Overlapping targets | Inflates effective sample size | Block bootstrap; non-overlapping subsample check |

The estimand is associational. A causal claim would require holdings and flow data, which
are out of scope.

---

## 7. Evaluation philosophy

Four commitments.

1. **A null result with a tight bound is a success.** The report states the minimum
   detectable effect in economic units. "No detectable tail signal above 80bp per four
   weeks" is a useful finding.
2. **The benchmark is the argument.** Every overlay is compared with a static portfolio,
   a volatility-managed portfolio, and a randomized overlay with the same exposure path
   distribution. Beating only the static portfolio proves nothing.
3. **The primary test is pre-specified and singular.** Secondary results are labelled
   exploratory and FDR-adjusted. There is no best-of reporting.
4. **Every number is reproducible from a manifest.** Seeds, config hash, data snapshot
   date, and package versions are recorded with each run.

### Power

Weekly data from 2005 to 2025 gives roughly 1,090 observations. Four-week forward
returns give about 270 effective independent blocks. The standard error of a quantile
regression coefficient at `τ = 0.10` is roughly 1.5 to 2 times the least-squares standard
error. With a factor return standard deviation of 3% to 5% over four weeks, the minimum
detectable effect is on the order of **0.6% to 1.1% of four-week return per one standard
deviation of fragility**, at 5% significance and 80% power.

That is the honest resolution of this design. Smaller effects exist and cannot be
detected here. The report computes the exact figure from the realized series and states
it next to every null.

Tail-specific tests at `τ = 0.05` have roughly five effective tail episodes across 20
years and are reported as exploratory only. This is stated in advance so that no reader
mistakes a `τ = 0.05` p-value for a reliable result.

---

## 8. Limitations, stated before the results

1. **Survivorship.** `yfinance` does not reliably serve delisted tickers. The sample
   is survivor-only: the panel contains zero delistings. Factor premium estimates
   are biased upward, and capacity estimates are biased upward because failed and
   shrinking firms are missing. This is complete survivorship, not a residual bias.
2. **No holdings or flow data.** Fragility measures are proxies. They measure the
   *portfolio* the factor implies, not the portfolios other managers actually hold.
   Position overlap between real funds is unobservable here.
3. **Impact model uncertainty.** The square-root law is an empirical regularity, not a
   law. The coefficient varies by market, period, and order type. Capacity is reported
   with a sensitivity band for this reason.
4. **Three factors.** Conclusions do not generalize to the factor zoo. They are statements
   about momentum, short-term reversal, and low volatility in large US equities.
5. **One market.** US only. Capacity in other markets will differ with liquidity.
6. **Monthly rebalancing.** Daily or weekly rebalancing would raise costs and lower
   capacity; the monthly choice is disclosed and applied consistently to the
   return series and the capacity turnover.
7. **Model-free fragility is not achievable.** The composite weighting is a judgment.
   Equal weights are used to avoid fitting, and the sensitivity to weighting is reported.
8. **No causal identification.** Associations only.

---

## 9. Scope

| Dimension | In scope | Out of scope |
| :--- | :--- | :--- |
| Factors | MOM, STREV, LOWVOL | Value, quality, carry, multi-factor blends |
| Universe | Top 500 US stocks by dollar volume, point-in-time | Small caps, international, ETFs |
| Period | 2005-2025, weekly | Intraday, pre-2000 |
| Fragility | 4 price/volume measures | 13F holdings, prime brokerage, options positioning |
| Capacity | Square-root impact, sensitivity band | Full market-impact simulation, order-book data |
| Inference | Quantile regression, block bootstrap, FDR | Structural VAR, causal identification |
| Decision layer | Sizing overlay with matched controls and costs | Live trading, execution algorithms |
| Output | Capacity table, fragility index, report, tested package | Production risk system |

## 10. Non-claims

This project does not claim to predict factor returns, generate alpha, beat a benchmark,
measure other investors' positions, or provide investment advice. It measures two
properties of a strategy, exit risk and capacity, and reports what the data support. The
capacity numbers are model estimates with a stated sensitivity band. The fragility index
is a proxy with a stated failure mode. Where the evidence is weak, the report says so.

---

## 11. References

- Almgren, R., Thum, C., Hauptmann, E., and Li, H. (2005). Direct estimation of equity market impact. *Risk*.
- Arnott, R., Kalesnik, V., and Wu, L. (2019). The incredible shrinking factor return. *Financial Analysts Journal*.
- Barroso, P., and Santa-Clara, P. (2015). Momentum has its moments. *Journal of Financial Economics*.
- Brunnermeier, M., and Pedersen, L. (2009). Market liquidity and funding liquidity. *Review of Financial Studies*.
- Cahan, R., and Luo, Y. (2013). Standing out from the crowd: Measuring crowding in quantitative strategies. *Journal of Portfolio Management*.
- Daniel, K., and Moskowitz, T. (2016). Momentum crashes. *Journal of Financial Economics*.
- Frazzini, A., Israel, R., and Moskowitz, T. (2018). Trading costs. Working paper.
- Khandani, A., and Lo, A. (2007). What happened to the quants in August 2007? *Journal of Financial Markets*.
- Ledoit, O., and Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices. *Journal of Multivariate Analysis*.
- McLean, R., and Pontiff, J. (2016). Does academic research destroy stock return predictability? *Journal of Finance*.
- Moreira, A., and Muir, T. (2017). Volatility-managed portfolios. *Journal of Finance*.
- Novy-Marx, R., and Velikov, M. (2016). A taxonomy of anomalies and their trading costs. *Review of Financial Studies*.
- Politis, D., and Romano, J. (1994). The stationary bootstrap. *Journal of the American Statistical Association*.

---

*This document is the contract for V2. Changes require an entry in `DECISIONS.md`.*
