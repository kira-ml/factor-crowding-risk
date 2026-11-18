# V1 Audit: Why the Original Result Cannot Stand

> **Archived source:** V1 code is preserved at `docs/archive/v1/src/`. The
> line references below refer to the V1 files at commit `298dc6c`, before the
> v2.1 tree moved them into the archive.

**Scope:** every file at commit `298dc6c`, including all source modules and the recorded
result files in `outputs/`.
**Method:** read the source, re-derived each reported metric from the code path that
produced it, and checked the arithmetic of the recorded numbers. Findings are graded
**Blocking** (invalidates a headline claim), **Major** (materially biases an inference),
**Moderate**, or **Minor**.
**Verdict:** the V1 conclusions are not supported. Three defects are individually fatal
and each is independently sufficient: the two "factors" are the same portfolio with
opposite sign, the headline F1 is the class base rate rather than skill, and the
features and targets are constructed with look-ahead. This document exists so that V2
does not repeat them and so that no V1 number is cited as evidence.

---

## 1. What V1 claimed

| Claim | Where | Recorded value |
| :--- | :--- | :--- |
| Value factor crowding predicts forward returns | README lines 25-30 | F1 0.9483, precision 0.96, recall 0.94 |
| Momentum signal is weaker but real | README lines 28-29 | F1 0.6593 |
| A crowding-aware overlay improves risk-adjusted return | README lines 123-133 | Sharpe +0.0182, max drawdown -2.82% |
| Correlation is the best crowding proxy | README line 27 | `correlation_raw` wins every comparison |

## 2. Blocking findings

### B1. There is only one factor. "Value" is exactly minus "Momentum".

`data.py:262-277` builds both factors from the same momentum score:

```python
value_score = -momentum_score
top_val = value_score.nlargest(n_quintile).index   # = lowest momentum quintile
bot_val = value_score.nsmallest(n_quintile).index  # = highest momentum quintile
val_factor = period_returns[top_val].mean(axis=1) - period_returns[bot_val].mean(axis=1)
```

Substituting the definitions gives
`val_factor = mean(bottom_mom) - mean(top_mom) = -mom_factor`, exactly, because the
sets are complementary and the weights are identical. The two columns of
`factor_returns` are the same series with a sign flip.

Consequences:

- Every "Value versus Momentum" comparison in `TODO.md` and the README compares a
  number with its own negation. The observation that value correlations are roughly
  `+0.31` where momentum correlations are `-0.36` is not a discovery about two
  factors; it is an arithmetic identity.
- The claim "Value is the stronger factor" (TODO.md lines 512-521) is a statement
  about the sign of one factor's return in one window.
- There is no value factor in the project. `problem_framing.md` promises
  book-to-market; `README.md` line 40 calls it an "inverse momentum proxy";
  the paper calls it "price reversal". All three descriptions appear, and none is
  book-to-market. Value requires fundamentals that were never loaded.

### B2. The headline F1 of 0.9483 is the class base rate, not predictive skill.

Recorded in `outputs/target_experiment_results_20260705_012831.csv`:
`f1 = 0.948276`, `n_train = 243`, `n_test = 61`.

F1 for the positive class can be written as `2TP / (2TP + FP + FN)`. The recorded
value is exactly `55/58`. Combined with the reported precision near `0.96` and recall
near `0.94`, the implied confusion matrix is approximately `TP=55, FP=2, FN=4, TN=0`
out of 61 observations. Two implications follow.

1. **The target is almost always the same sign.** 55 of 61 test observations, or 90%,
   had a negative forward three-month return. For a base rate `π`, a classifier that
   predicts the majority class for every observation scores
   `F1 = 2π / (1 + π)`. At `π = 0.902` that is `0.9483`, the reported number to four
   decimals. The model's score is the score of a constant predictor.
2. **The model never predicted the rare class.** `TN = 0`. It did not detect
   "non-crowded" periods; it detected nothing.

This is what an F1 of 0.95 looks like when the label is an autocorrelated sign of a
trending series. It is a property of the test window, not of the feature.

The same defect invalidates the model-selection gate at `model.py:209`:

```python
has_signal = (baseline_r2 > 0.0 or baseline_f1 > 0.50)
```

An F1 above 0.50 is treated as evidence of signal. Under class imbalance, 0.50 is far
below the base-rate benchmark and a useless model clears it. The gate selects on a
metric with no null model attached.

### B3. The train/test split leaks across the boundary.

`model.py:182-185` splits chronologically with no gap. The target is a forward
three-month cumulative return (`features.py:573-583`), sampled weekly. The last
training observation's outcome window extends roughly 13 weeks into the test period,
and the first 13 test rows share most of their outcome window with training rows.

So the model is tested on labels that overlap its training labels. Reported out-of-sample
performance is not out of sample. A purged split needs an embargo of at least the target
horizon. V1 has an 80/20 split, a 60/40 split, and an "expanding window" at
`model.py:663-737` with `step=10`; all three leak in the same way.

The effective sample size is also far smaller than the row count suggests. A 13-week
target sampled weekly has at most `1/13` independent observations. The 61-row test set
represents fewer than five non-overlapping three-month blocks. No F1, R², or Sharpe
computed on that set carries the precision implied by 61.

### B4. Feature standardization uses the full sample.

`features.py:120-136` computes the composite as

```python
corr_z = (valid['correlation'] - valid['correlation'].mean()) / corr_std
```

where `mean` and `std` are taken over the entire sample, 2019 through 2024. The same
pattern appears at `features.py:523-535` for `correlation_z`, `hhi_z`,
`valuation_spread_z`, and at `features.py:489-510` for rolling ranks and deltas that
use future rows in their windows.

Every z-scored feature therefore contains information from after the date on which it
is used. This is the specific failure the project claimed to avoid: `TODO.md:57` states
"No look-ahead bias enforced" (sic), and `features.py:9` states "No look-ahead bias".
Both statements are false.

Note the boundary of this defect: the headline backtest uses `correlation_raw`, so the
z-score leak does not contaminate that particular number. The leak does contaminate
every feature-transform and target experiment, including the `hhi_z` result and the
entire z-composite narrative.

### B5. The backtest has no valid counterfactual.

`run_visualizations.py:145-174` trains on 2019-2021, predicts on 2022-2024, maps
predictions to weights in `[0.7, 1.0]`, and compares the result with a 100% static
allocation.

Four problems, each sufficient to void the comparison:

1. **No costs.** No spread, commission, impact, borrow, or financing. The overlay
   trades every week.
2. **No cash return.** De-risking holds the remainder in cash at 0%, which is
   unrealistic and, in a period with positive short rates, punitive or generous
   depending on the sign of the factor.
3. **No exposure-matched control.** The overlay averages 83.7% exposure. The correct
   comparison holds average exposure constant and asks whether the *timing* adds
   value. As written, the test asks whether holding less of an asset with a negative
   Sharpe ratio loses less money. The answer is yes by construction. This is a
   de-risking result, not a crowding result.
4. **Test-period normalization.** `run_visualizations.py:163` min-max scales the
   predictions using the minimum and maximum *of the test period*. The position size
   at the start of 2022 depends on predictions made in 2024.

The reported improvement, `+0.0182` Sharpe, is the arithmetic consequence of (3). Both
Sharpe ratios are negative (`-0.6569` and `-0.6386`). Ranking two losing strategies by
a 0.018 difference, with no standard error, no cost model, and no matched control, does
not support a claim of improvement.

### B6. Two targets are not targets, and one is mislabelled.

`features.py:410-430` computes `spearman_6w` as the correlation between the ranks of
the forward returns and a time index `np.arange(len(ranks))`. That is the monotonicity
of the return path over the forward window, not a rank information coefficient. An IC
is a cross-sectional correlation between a signal and forward returns at one date. The
function has no cross-section in it.

`features.py:433-445` computes `rolling_ic_*` as the plain mean of forward returns. That
is a smoothed return, not an IC.

The "best target" search in Batch 2 therefore compared a return, a trend statistic, and
a mean, and selected whichever produced the highest F1 under an imbalanced label. The
selection is not evidence about decay horizons.

---

## 3. Major findings

### M1. Raw pairwise correlation is a market-volatility proxy, not a crowding measure.

`features.py:195-237` averages pairwise correlations of raw daily returns among the
long-leg names. Raw correlations rise for all stocks when market volatility rises,
because the common factor dominates. The measure therefore largely reports the VIX
regime. Its apparent predictive power is indistinguishable from generic volatility
timing, which is a known and separately documented effect (Moreira and Muir, 2017).

Any V2 measure must use market-residual returns, and any V2 overlay must be compared
with a volatility-managed control.

### M2. HHI is not concentration of holdings.

`features.py:240-250` computes `HHI = Σ (|s_i| / Σ|s|)²` over the factor scores of the
*entire cross-section*. With roughly 500 names this is approximately `1/500` and its
variation reflects the shape of the momentum-return distribution, not the concentration
of any portfolio. For the "value" factor it is a deterministic function of the same
12-1 return distribution that defines the factor, so it is mechanically circular.

The documented meaning, "concentration of factor exposure across the universe"
(README line 68), is not what the code computes.

### M3. Valuation spread is a price-level difference.

`features.py:253-279` returns `median(price of top quintile) - median(price of bottom
quintile)`. Share prices are arbitrary units. The statistic mixes price level, split
history, and quintile composition, has no valuation interpretation, and is not
comparable across time. It should never have entered a model.

### M4. The universe is not point-in-time and is survivorship-biased.

`data.py:61-80` scrapes the *current* Wikipedia constituent list and applies it to
history beginning in 2018. Companies removed from the index before the scrape are
absent, so the sample contains only firms that survived to 2026 and remained large
enough to be in the index. `data.py:187-192` forward-fills prices and keeps rows with at
least 100 names, which produces stale prices for names that stopped trading.

Survivorship inflates long-only returns and biases factor spreads. The README discloses
the bias (line 227) but the reported numbers were produced under it, and the disclosure
does not repair the inference.

### M5. Roughly 300 configurations were evaluated and the maximum was reported.

Batch 1 tests 13 feature transforms for each of two factors. Batch 2 tests 13 features
against 9 targets for each factor. `model.py:1137-1301` adds six test groups. The
headline table reports the single best result of each group.

No multiplicity correction, no pre-registration, no holdout. The language at
`model.py:565-566` ("Significant improvement found") refers to a 0.05 threshold on a
difference in F1 between configurations, not to a hypothesis test. With roughly 300
fits, a best-of improvement of this size is expected under the null.

### M6. In-sample R² is presented as the headline R².

`run_visualizations.py:398` and `:428` call `model.score(X_clean, y_clean)` on the full
sample using a model fitted on 2019-2021. The README's "R²: 0.0500 in this sample"
(line 163) is therefore not an out-of-sample statistic. The out-of-sample R² recorded
in the result files is negative (`-0.9876` for the headline configuration).

### M7. Feature engineering is re-run per experiment, but the target alignment is not.

`prepare_model_data` computes forward returns for every feature date and then calls
`dropna()`, which silently removes the tail of the sample where the target is
unavailable. Combined with the full-sample z-scores, the number of usable rows differs
between experiments. Cross-experiment comparisons (window length, quintile size,
feature transform) are not on a common sample, so differences between them partly
reflect different date ranges.

---

## 4. Minor findings

| ID | Finding | Evidence |
| :--- | :--- | :--- |
| m1 | README documents `src/models.py`; the file is `src/model.py` | README line 174, `src/` |
| m2 | `src/evaluate.py` is zero bytes and no test suite exists | file size 0, no `tests/` |
| m3 | Outputs are written to `../outputs` relative to the caller's working directory | `model.py:51` |
| m4 | `requirements.txt` lists `lightgbm` and `seaborn`, absent from the environment; the pipeline cannot run as installed | verified import failure |
| m5 | Deprecated `resample("M")` on pandas 2.3 | `features.py:54` |
| m6 | Convergence warnings suppressed globally, including real failures | `features.py:15`, `model.py:26` |
| m7 | No seed control, no config file, no run manifest | throughout |
| m8 | Documentation, PDF, and README disagree on what the value factor is | README line 40 vs paper vs `problem_framing.md` |

## 5. What V1 got right

The audit should not obscure the parts worth keeping.

- The instinct to establish baselines before advanced models is correct, and the
  observation that LightGBM did not beat linear models on this data is probably true
  and worth reporting.
- The limitations section is unusually candid for a portfolio project.
- The move from an in-sample to an out-of-sample evaluation on day three was the right
  instinct, even though the split was not purged.
- The distinction between prediction quality and trading utility (TODO.md lines
  502-510) is a real insight and is carried into V2.

The problem was not effort or honesty. It was that the question was unanswerable with
the data, and the defects made it appear answered.

## 6. Reproduction experiment (to be run in V2)

Claims B1, B2, and B3 are derived from the source and from the recorded numbers, not
yet reproduced end to end. Phase 1 of V2 includes a forensic reproduction:

1. Rebuild the V1 factor series and confirm
   `corr(value_returns, momentum_returns) = -1.0` to machine precision.
2. Rebuild the V1 label and confirm the 61-row test set has a 90% negative base rate.
3. Score a constant "negative" predictor on the same test set and confirm it reproduces
   `F1 = 0.9483`.
4. Score the V1 model with the training window purged by 13 weeks and record the change.

If the constant predictor does not reproduce the F1, the audit's arithmetic is wrong and
this document must be revised before any V2 result is published. That is the test that
could disconfirm the diagnosis.

## 7. Defect to design mapping

| V1 defect | V2 requirement |
| :--- | :--- |
| Value is minus momentum | Explicit factor definitions with disjoint economic content; assert pairwise correlation of factor returns is not ±1 |
| F1 on an imbalanced, overlapping label | No classification on sign. Tail estimands with block-bootstrap inference and a reported minimum detectable effect |
| Unpurged chronological split | Purge and embargo of at least the target horizon; walk-forward only |
| Full-sample standardization | Expanding-window standardization with a documented burn-in; truncation-invariance test |
| No costs, no cash, no matched control | Cost model, financing, and volatility-matched plus exposure-matched controls |
| Raw correlation as crowding | Market-residual correlation with shrinkage estimation |
| Price-level spread | Removed. No feature without units and an economic mechanism |
| ~300 unaudited configurations | Pre-specified primary estimand; secondary results labelled exploratory; FDR control |
| Survivorship | Point-in-time universe rule; bias documented and bounded where possible |
| No tests | Leakage, unit, and reproducibility tests in CI |

---

*Audit complete. No V1 number is carried forward into V2 except as an object of study.*
