# Methodology Specification

**Version 2.0. This document is normative: the implementation must match it, and any
deviation requires an entry in `DECISIONS.md`.**

Companion to `problem_framing.md`, which defines the research question. This document
defines how it is answered.

---

## 1. Data

### 1.1 Sources

| Source | Fields | Frequency | Lag |
| :--- | :--- | :--- | :--- |
| Wikipedia S&P 500 / S&P 400 constituent pages | ticker, GICS sector, date added | Snapshot | None |
| `yfinance` | adjusted OHLC, volume | Daily | None |

There is no fundamental data. No feature in this project depends on accounting data,
analyst estimates, or holdings. That is a deliberate constraint, not an oversight: it
keeps the pipeline reproducible and prevents another "value factor that is not value".

### 1.2 Caching and validation

Raw downloads are cached as parquet under `data/raw/`, keyed by ticker, and are
never committed. Every load runs these checks and fails loudly:

- Index is a monotonically increasing `DatetimeIndex`, timezone-naive.
- No duplicate dates.
- Prices strictly positive where present; zero or negative prices are data errors.
- Non-negative, finite volume.
- A panel content hash is written to `data/panel/metadata.json` and the run
  manifest.

A full split/dividend consistency check is a known limitation, not a completed
guarantee. Dollar volume is adjusted close × reported volume; treat it as an
approximate liquidity measure.

Rows are never forward-filled across a delisting. A ticker that stops trading
disappears from the panel on its last valid date. V1's `ffill` created stale
prices for dead companies; that is forbidden here.

### 1.3 Returns

`r_{i,t} = P_{i,t} / P_{i,t-1} - 1` on adjusted close. Daily returns are used for
volatility, beta, and residual correlation. Weekly returns are compounded from daily
returns, not taken from Friday-to-Friday closes, to avoid losing mid-week moves on
holiday-shortened weeks.

### 1.4 Universe

At each weekly date `t`:

```
eligible_t = { i : history_i(t) >= 252 trading days
                 and price_i(t) >= 5
                 and ADV_i(t) >= $5m }

U_t = top 500 of eligible_t by ADV_i(t)
ADV_i(t) = median( dollar volume ) over the 60 trading days ending at t
```

All inputs are lagged to `t`. The universe is recomputed at every rebalance and stored,
so it can be audited. Selection is point-in-time with respect to liquidity, price,
and history. It is **not** point-in-time with respect to existence: the candidate
pool is current index membership.

Survivorship: names absent from `yfinance` cannot enter, even if they were
liquid at the time. The panel contains zero delistings, so this is **complete
survivorship**, not a residual bias. The report quantifies it (0 delistings;
equal-weight CAGR 18.14% versus 10.80% for the S&P 500 total return) and treats
factor premia and capacity levels as upward-biased model outputs, not investable
estimates. No correction is applied.

---

## 2. Factor construction

### 2.1 Signals

Computed at each weekly date `t`, using only data at or before `t`:

| Factor | Raw signal | Notes |
| :--- | :--- | :--- |
| `MOM` | `P_{t-21}/P_{t-252} - 1` | Skips the most recent month |
| `STREV` | `-(P_t/P_{t-21} - 1)` | Negative one-month return |
| `LOWVOL` | `-std(r_{i,d})` over 252 trading days | Negative realized volatility |

### 2.2 Portfolio weights

1. Winsorize the signal at the 1st and 99th percentile of the cross-section.
2. Estimate beta by OLS of daily excess returns on the equal-weight universe return over
   the trailing 252 days.
3. **Residualize the signal** cross-sectionally on `[1, beta]` and keep the residual. Beta
   is removed in signal space, not weight space.
4. Rank the residual. Long the top decile, short the bottom decile. Each leg holds at least
   25 names (`min_leg_names`), so that equal weighting never breaches the per-name cap on a
   small universe; for the 500-name universe the decile contains 50 names.
5. Equal weight within each leg, then apply a per-name cap of 2% of gross exposure
   (`Σ|w| = 2`), redistributing the excess pro rata.
6. Store `w_{i,t}`, the long-leg mask, and the short-leg mask.

Beta neutralization in *weight* space (`w ← w − kβ`) would place small positions in
hundreds of names outside the deciles, which raises turnover, inflates trading costs, and
destroys the long/short leg structure that the fragility measures depend on. Signal-space
neutralization keeps the portfolio interpretable and removes most of the beta tilt. The
residual beta is reported as a diagnostic (Section 2.4) rather than forced to zero. See
`DECISIONS.md` ADR-0005.

### 2.3 Factor return

`r^f_t = Σ_i w_{i,t} · r_{i,t+1}` where `r_{i,t+1}` is the return over the week following
`t`. Returns are computed from the panel, and a name that stops trading during the week
contributes its last available return, then is removed at the next rebalance.

### 2.4 Invariants (asserted in tests)

- `Σ_i w_{i,t} = 0` within 1e-8.
- `Σ_i |w_{i,t}| = 2` within 1e-8.
- `max_i |w_{i,t}| ≤ 0.02 + 1e-9`.
- Ex-post portfolio beta `Σ_i w_i β_i` has a mean absolute value below 0.25 and is
  reported per factor as a diagnostic. It is not forced to zero (ADR-0005).
- Pairwise correlation of the three full-sample factor return series is below 0.9 in
  absolute value. V1 fails this by construction at -1.0.
- No weight on a name outside `U_t`.

---

## 3. Fragility

All measures use data at or before `t`. All are stored per factor per date before any
standardization.

### 3.1 F1: residual synchronization

```
1. β_i from 252-day OLS of r_i on r_mkt (equal-weight universe), ending at t.
2. ε_{i,d} = r_{i,d} − β_i · r_{mkt,d} for the trailing 60 trading days.
3. Σ = Ledoit-Wolf shrinkage covariance of ε over the long-leg names.
4. R = correlation matrix implied by Σ.
5. ρ̄ = mean of Fisher-z(R_ij), i ≠ j, then inverse Fisher.
6. S_t = ρ̄.
```

Ledoit-Wolf is required because the long leg has about 50 names and the window has 60
days; the sample covariance is close to singular and raw average correlation is biased
downward by estimation noise.

### 3.2 F2: effective breadth

```
B_t      = (Σ_i |w_i|)² / Σ_i w_i²                  # unweighted
u_i      = (|w_i| / ADV_i) / Σ_j (|w_j| / ADV_j)
B_liq,t  = 1 / Σ_i u_i²                              # liquidity-weighted
```

`B_t` is the effective number of equal-sized positions. `B_liq,t` is the effective number
of liquidity-equivalent positions. Both are reported; `B_liq` enters the composite.

### 3.3 F3: exit horizon

```
D_t = Σ_i |w_i| · A_ref / (0.10 · ADV_i)      with A_ref = $1bn
```

Units: dollar-weighted days to liquidate the long leg at 10% participation. Also stored:
`max_i` days for the single worst name. `A_ref` is a scale for comparability; the capacity
model in Section 4 recomputes exit cost at any `A`.

### 3.4 F4: consensus persistence

```
age_i,t = consecutive rebalances for which name i has been in the long leg
P_t     = Σ_{i in long leg} |w_i| · 1[age_i,t >= 6] / Σ_{i in long leg} |w_i|
```

Robustness variant: `Disp_t = IQR(s_{i,t}) / MAD(s_{i,t})` over the cross-section.
Lower dispersion means greater consensus. It is correlated with `P_t` by construction and
is reported as a variant, not as an independent measure.

### 3.5 Standardization and composite

Each measure `m` is standardized with an expanding window using only observations up to
`t`:

```
z_{m,t} = (m_t − mean(m_{<t})) / std(m_{<t})      for t >= 104 weeks
```

No full-sample statistics are permitted anywhere. A test enforces this by truncation
(see Section 8).

Composite:

```
F_t = (z_S + z_B + z_D + z_P) / 4
```

Equal weights, fixed in advance, no fitting. Sensitivity to weighting (equal vs
first-principal-component fitted on expanding windows vs rank-average) is reported as a
robustness check, not used to select the headline.

Sign convention: every `z` is oriented so that **higher means more fragile**.

### 3.6 Guards

- The composite requires all four z-scores; rows with a missing component are
  dropped from that test, and the count of usable dates is reported in the
  coverage table.
- Winsorize each `z` at ±4 to prevent a single observation from dominating.
- If the expanding standard deviation is zero (flat measure), the `z` is set to 0.

---

## 4. Capacity

### 4.1 Cost model

For sleeve notional `A` per side:

```
D_i      = |Δw_i| · A                                   # traded dollars
q_i      = D_i / ADV_i                                  # participation
cost_i   = 0.5 · spread_i + c · σ_i · sqrt(q_i)         # in return units
C_t(A)   = Σ_i (D_i / A) · cost_i = Σ_i |Δw_i| · cost_i
```

`Q_i` in an earlier draft of this document was the held position `|w_i|·A`. That is the
right quantity for *liquidating a position*, not for *rebalancing* it. The capacity curve
uses traded notional, because that is what incurs impact each week. A separate
liquidation-cost table uses the full position, and the distinction is stated in the report.
See `DECISIONS.md` ADR-0006.

| Parameter | Baseline | Sensitivity |
| :--- | :--- | :--- |
| `c` | 0.314 | 0.10, 0.50 |
| `spread_i` | 3 bp | 1 bp, 10 bp |
| `execution_days` | 10 | reported in the sensitivity band |
| Borrow cost, shorts | 50 bp / yr | not varied in the current grid |
| Financing | 0 | 0 |

`σ_i` is the trailing 60-day daily return standard deviation.

### 4.2 Rebalance cost

```
C_t(A) = Σ_i |w_{i,t} − w_{i,t−1} · Π(1 + r_{i,s}) / Π(1 + r^f_s)| · cost_i(A)
```

The drift term compounds stock and factor returns from the previous monthly
rebalance to the current one. Using one week of drift, as an earlier version did,
understates turnover. The factor return series uses the same monthly buy-and-hold
convention: weights drift between rebalances, then reset.

### 4.3 Net premium and capacity

```
Π_gross = 52 · mean(r^f_t)                                  # annualized
Π_net(A) = Π_gross − 52 · mean(C_t(A)) − borrow(A) − financing(A)
A*(h) = max{ A : Π_net(A) >= h · Π_gross }
```

Primary hurdle `h = 0.50`; also 0.25 and 0.75. Solutions are clipped to
`[$1M, $100B]`; a value at the bound is a model limit, not a measurement.

Because retention-based capacity is undefined for a factor with no gross premium, a
second and **headline** definition is premium-independent:

```
A_cost(h) = max{ A : 52 · mean(C_t(A)) <= h }
```

with `h ∈ {50, 100, 200}` basis points of annual **trading-cost** drag. Borrow
and financing are reported separately; they are not included in the headline
cost-drag number. This answers the allocator's question directly: at what size do
implementation costs become material? The capacity ordering is a turnover
identity and is reported descriptively, not as a hypothesis test. Retention-based
capacity is reported alongside for factors with a positive gross premium, and
marked `n/a` otherwise.

### 4.4 Output

Per factor: gross premium with a bootstrap interval, turnover, cost in bp at
`A ∈ {10M, 100M, 1B, 5B, 10B}`, net premium at each, `A*` at each hurdle, and the
sensitivity band across `c` and spread. The headline table has one row per factor and
one column per AUM. This is the project's most portable deliverable.

---

## 5. Targets

| Target | Definition | Use |
| :--- | :--- | :--- |
| `fwd_4w` | `Π(1 + r^f_{t..t+4w}) − 1` | Primary |
| `fwd_13w` | `Π(1 + r^f_{t..t+13w}) − 1` | Secondary |
| `es_5` | Mean of the bottom 5% of `fwd_4w` | Descriptive |
| `dd_episode` | Peak-to-trough decline of the factor's cumulative return, episodes with depth ≥ 10% | Descriptive |

The target starts at the decision date `t` and includes exactly `h` weeks.
Controls are lagged one week so they use only information available at `t`.
Overlapping targets are permitted for estimation but never for naive inference.
Standard errors come from a stationary bootstrap with mean block length 8 weeks,
which accommodates the overlap. A non-overlapping subsample is reported in the
report.

---

## 6. Estimation and inference

### 6.1 Primary model

Pooled across factors:

```
Q_{0.10}( fwd_4w_{f,t} | F_{f,t}, controls ) = α_f + β_0.10 · F_{f,t} + γ' X_{f,t}
```

`α_f` are factor fixed effects. `X` contains:

| Control | Definition |
| :--- | :--- |
| `log_vol` | log of 20-day EWMA realized factor volatility |
| `mkt_vol` | log of 20-day EWMA realized universe volatility |
| `trail_12w` | trailing 12-week factor return |
| `liq_regime` | log change in median ADV over 12 weeks |

Estimated with `statsmodels` quantile regression. Standard errors from a
stationary bootstrap (Politis-Romano, mean block 8, 2,000 replications for the
primary estimate, 400 for secondary and per-factor tables), not from the
asymptotic formula, because residuals are autocorrelated and heteroskedastic.
Bootstrap replicates retain duplicate dates; a resample has length `n` and
roughly 63% unique dates, which is the correct with-replacement behavior.

`β_0.50` is estimated on the same specification. The tail-specificity check is
`β_0.10 < β_0.50` with a bootstrap interval on the difference.

**H2.** The uncontrolled coefficient is compared with the full-control and
log-vol-only specifications. H2 passes if the sign is retained and at least half
the magnitude remains. The current result fails and is reported as a volatility
proxy, not as a crowding signal.

### 6.2 Secondary

- Per-factor `β_0.10` for each of the four measures.
- **Expected shortfall:** `ES_5%` difference between the top and bottom fragility
  quintiles, with a block-bootstrap interval.
- **fwd_13w** versions.
- **Subsample stability:** 2005-2009, 2010-2017, 2018-2025.
- **Composite sensitivity:** equal, drop-one, rank-average.

### 6.3 Multiplicity

Pre-specified family for FDR: 4 measures × 2 horizons = 8 tests on the pooled panel.
Benjamini-Hochberg at 10%. Per-factor results are exploratory and reported without a
significance claim, clearly labelled.

Any comparison that was not pre-specified is labelled "exploratory" in every table.

### 6.4 Minimum detectable effect

Before running E1, compute and publish:

```
MDE_τ = (z_{1-α/2} + z_{power}) · SE_bootstrap(β_τ)
```

reported in units of four-week return per one standard deviation of fragility, and as a
percentage of the factor's four-week volatility. The report places the MDE beside every
null result. An effect smaller than the MDE is "not detected", never "absent".

---

## 7. Decision layer

### 7.1 Overlay

```
w_t = clip( g(F_t), 0.3, 1.0 )
g(F) = 1                                  if percentile(F) <= 0.60
     = 1 − (percentile(F) − 0.60)/0.30   if 0.60 < percentile(F) <= 0.90
     = 0.30                               otherwise
```

Percentiles are expanding, computed from data up to `t`. No parameter is fitted on the
evaluation period. The floor of 0.30 prevents a full exit, which no risk process should
do on a noisy signal.

### 7.2 Comparators

| ID | Portfolio | Purpose |
| :--- | :--- | :--- |
| C0 | Static, `w = 1` | Naive baseline |
| C1 | Volatility-managed, `w = min(1.5, σ_target / σ_EWMA)`, rescaled to the same average exposure as the overlay | **The real test.** Controls for Moreira-Muir |
| C2 | Exposure-matched constant, `w = mean(w_overlay)` | Controls for de-risking |
| C3 | Randomized overlay: same exposure path, dates block-shuffled | Controls for luck and for the exposure distribution |
| C4 | Fragility overlay | Treatment |

C1 is the hypothesis test. If C4 does not beat C1 on tail metrics net of costs, the
honest conclusion is that fragility measurement adds nothing to volatility management.

### 7.3 Backtest mechanics

- Weekly overlay decisions, weights applied to next-week returns.
- The decision layer charges a 5bp scaling cost on exposure changes and 50bp
  annual borrow on short notional. The underlying factor's own rebalancing cost
  is **not** charged in the overlay comparison; the capacity model reports it
  separately. Absolute "net" returns are therefore gross of factor
  implementation costs.
- Cash earns the 3-month T-bill rate when exposure is below 1.0. The rate series
  is `^IRX`; if unavailable, 0% with a documented flag.
- Short proceeds earn the T-bill rate less 50bp borrow.
- No shorting constraints beyond the borrow cost. This is optimistic and disclosed.

### 7.4 Metrics

Primary: `ES_5%`, maximum drawdown, `ES_10%`.
Secondary: annualized Sharpe, Sortino, Calmar, annualized volatility, average exposure,
annual turnover, net return. Counter-metrics: turnover, cost drag in bp, and
performance in the pre-2010 and post-2018 subsamples.

The tail-metric differences have stationary-bootstrap 95% intervals. Secondary
metrics are point estimates; they are not given intervals in the current report.

---

## 8. Leakage protocol

This is the part V1 failed. It is enforced mechanically, not by discipline.

### 8.1 Rules

1. No statistic used at time `t` may be computed from data after `t`. This includes
   means, standard deviations, quantiles, correlations, and universe ranks.
2. Standardization is expanding, minimum 104 weeks, never full-sample.
3. Any fitted model uses walk-forward with a purge of at least the target horizon and an
   embargo of 2 weeks.
4. The universe is recomputed from lagged data at every date.
5. Capacity inputs use trailing ADV and trailing volatility only.
6. No min-max scaling on the evaluation period. Any scaling must use training data.

### 8.2 Truncation-invariance test

The core automated check:

```
for a selected date t*:
    full  = compute_all_features(panel)
    trunc = compute_all_features(panel.loc[:t*])
    assert max |full.loc[t*] − trunc.loc[t*]| < 1e-10
```

The test covers factor weights, fragility features, and the study controls.
Adding a new feature requires adding it to the test. The current suite uses a
single cutoff for speed; a production run can extend it to a random set of dates.

### 8.3 Other tests

- **Perturbation test:** multiply all data after `t*` by a random factor; feature
  values at `t*` must be unchanged.
- **Placebo block-shuffle:** shuffle the composite within factor and refit; the
  placebo distribution is reported.
- **Constant-predictor benchmark:** every classifier-style metric must report the
  majority-class score alongside it.
- **Capacity monotonicity:** `Π_net(A)` must be non-increasing in `A`.
- **Bootstrap duplicate retention:** the resample length equals `n`; duplicates
  are present; the SE is compared with a reference.

---

## 9. Software architecture

```
src/fcr/
  __init__.py
  config.py        # frozen dataclass config; JSON-serialisable; hashable
  data.py          # download, cache, validate; no feature logic
  universe.py      # point-in-time universe
  factors.py       # signals, weights, returns; asserts invariants
  fragility.py     # F1-F4, expanding standardization, composite
  capacity.py      # cost model, net premium curve, capacity
  targets.py       # forward returns, ES, drawdown episodes
  stats.py         # stationary bootstrap, quantile regression wrapper, BH, MDE
  overlay.py       # g(F), comparators, exposure matching
  backtest.py      # P&L, costs, cash, borrow, metrics
  report.py        # tables, figures, markdown report
  cli.py           # `python -m fcr <stage>`
tests/
  test_stats.py
  test_targets.py
  test_backtest.py
  test_overlay.py
  test_decision.py
  test_factors.py
  test_capacity.py
  test_leakage.py
  test_data.py
  test_study.py
```

### 9.1 Interfaces

| Module | Promises | Fails loudly if |
| :--- | :--- | :--- |
| `data` | A validated `Panel` with monotone dates and positive prices | Any validation rule in 1.2 is violated |
| `universe` | `members[t] -> Index`, only past data used | Fewer than 100 eligible names |
| `factors` | Weights satisfying all invariants in 2.4 | Any invariant fails |
| `fragility` | A `fragility` frame indexed by `(date, factor)` with no NaNs in the composite after burn-in | Burn-in not met |
| `capacity` | A monotone net-premium curve | Monotonicity violated |
| `stats` | Bootstrap distributions and intervals, seeded | Fewer than 30 observations |
| `backtest` | Net return series and a metrics dict | Exposure outside `[0, 1.5]`, or NaN in returns |
| `report` | Markdown and figures written atomically | Any required table is missing |

No module reaches into another module's internals. `config` is passed explicitly; there
are no global mutable settings.

### 9.2 Reproducibility

Each run writes `outputs/runs/<run_id>/manifest.json` with: config hash, git commit,
package versions, data snapshot date, seeds, row counts at each stage, and wall-clock
time per stage. `run_id` is the config hash plus a UTC timestamp. Results are
bit-reproducible given the cached data and the manifest.

### 9.3 Determinism

All randomness is seeded from the manifest. Bootstrap indices are generated from a
`numpy.random.Generator` seeded per test, not per call, so that adding a test does not
change existing results.

---

## 10. Reporting

The report (`docs/report.md`, generated) contains, in order:

1. The question and the answer, in plain language, with the MDE.
2. The V1 audit summary and why the question changed.
3. Method, at the level of a quant reader who has not seen the code.
4. Capacity table and curves. This comes before the fragility results because it is the
   robust contribution.
5. Fragility results: primary estimate, controls, FDR-adjusted secondary results,
   placebo and negative controls.
6. Decision layer: net-of-cost comparison against all four comparators.
7. Power, limitations, and what would change the conclusion.
8. Appendix: full result tables, including all exploratory specifications.

Figures, minimum set:

| Figure | Content |
| :--- | :--- |
| 1 | Cumulative factor returns with drawdown episodes marked |
| 2 | Fragility composite over time, per factor, with episodes |
| 3 | Forward return distribution conditional on fragility quintile |
| 4 | Quantile regression coefficients across `τ` with bootstrap bands |
| 5 | Capacity curves, three factors, sensitivity band |
| 6 | Overlay vs comparators, net of costs, with tail metrics |

Each figure must be readable in grayscale and must state its sample period on the face of
the plot.

---

## 11. Definition of done

The implementation is complete when all of the following hold.

- [x] `pytest` passes, including the leakage, invariant, and monotonicity tests.
- [x] The V1 reproduction confirms the audit's arithmetic.
- [x] All six figures are generated from a single command.
- [x] The capacity table covers three factors, five AUM levels, three impact sensitivities, and four execution horizons.
- [x] The primary estimate is reported with a bootstrap interval and an MDE.
- [x] Every null result is accompanied by the MDE and the word "detected" is used correctly.
- [x] The report exists, is generated rather than hand-edited, and matches the figures.
- [x] A reader can reproduce the headline table from the manifest and cached data.
- [x] No claim in the README exceeds what the report shows.
- [x] CI runs the test suite on Python 3.10 and 3.11.

---

*Normative specification. Implementation follows this document; where it cannot, the
document is amended first.*
