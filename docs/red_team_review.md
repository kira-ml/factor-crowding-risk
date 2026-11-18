# Red-Team Review: Crowded Exits v2

> **Historical self-audit (pre-v2.1).** This review was written against the
> pre-fix working tree. Most code-level findings were addressed in v2.1; the
> current status is in `TODO.md` and `docs/report.md`. The data and paper-level
> gaps remain. Kept for the audit trail.

**Date:** 2026-11-17
**Scope:** the entire repository at the v2 working tree, including generated results.
**Stance:** adversarial. The objective was to falsify the headline claims, not to confirm them.
**Independence:** this review was produced by the same session that built the project, so it is
a **self-audit** and its PASS carries less weight than an external review. An independent
red-team agent was commissioned in parallel; this document is the self-audit, and any
independent findings that arrive should be merged before release. The experiments below were
re-run from the cached data, not copied from the report.

**Verdict in one line:** a strong engineering portfolio project with a credible negative
result, but **not ready for formal publication**, and not ready for a public GitHub release
until the blockers in Section 6 are fixed. The headline null survives two inference bugs;
the published interval is too narrow and the true MDE is 1.52%, not 1.12%.

---

## 1. Claims under audit

Steelmanned, in the strongest form the repository supports:

| ID | Claim | Evidence tier offered | Tier required |
| :--- | :--- | :--- | :--- |
| C1 | V1's two factors are the same portfolio up to sign, so its "value vs momentum" comparisons are void | Derived algebra + exact recomputation | E2 sufficient |
| C2 | Capacity at 100bp cost drag orders STREV < MOM < LOWVOL ($8m, $466m, $2,531m) | Model calculation on in-sample data | E2 for a model output; not an empirical test |
| C3 | The fragility composite does not predict the left tail of 4-week factor returns at the pre-registered resolution | In-sample QR + block bootstrap, no holdout | E2 at best; E3 for a generalization claim |
| C4 | A fragility overlay underperforms volatility management at equal average exposure | In-sample backtest with costs | E2; the claim is comparative and in-sample |
| C5 | The pipeline is leakage-free and reproducible | One truncation test; run manifest | E2 for the tested path; E3 for the whole pipeline |
| C6 | The capacity ordering is a robust empirical finding | Sensitivity grid over model parameters | Not applicable: it is a model identity |

C1 and C3 are the claims with the best and worst evidence-to-importance ratios,
respectively. C6 is the claim most likely to be rejected by a referee.

---

## 2. Verdict table

| Gate | Result | Severity of test | Evidence | Residual risk |
| :--- | :--- | :--- | :--- | :--- |
| Claim precision | **FAIL** | The primary claim is precise, but C2/C6 is presented as a hypothesis and the decision layer mislabels a quantile as expected shortfall | Sections 3.2 and 3.3 | A reader cannot tell which numbers are model outputs and which are estimates |
| Leakage / information flow | **FAIL (controls)** | The fragility features pass mutation testing, but the regression controls include the week after the decision date and the target skips it | Section 4 (B8) | The fully aligned specification gives -0.73% (CI -1.88%, +0.30%); the verdict survives, the reported number is not the pre-registered one |
| Selection / multiple testing | **FAIL** | No complete trial ledger; construction changed after inspecting results | Section 3.6 | Reported estimates are selected maxima |
| Baseline superiority | **PASS** | Static, volatility-managed, exposure-matched, randomized comparators | Section 7 | None material |
| Effect size / practical value | **INCONCLUSIVE** | Corrected MDE 1.52% per SD; corrected CI (-1.88%, +0.30%); exploratory effect flips sign across subsamples | Section 4 (B7) | The null is underpowered and the positive result is unstable |
| Tail / ruin | **FAIL (definition)** | `es_5` is a 5% quantile, not expected shortfall; the exposure match misses by up to 2pp | Section 3.3 | Tail risk is understated by roughly 40-65% |
| Counter-metrics | **FAIL (partial)** | Turnover and cost drag are reported; subsample analysis is omitted and the random-control percentile ranks are misread | Sections 3.3 and 4 | Regime dependence and timing value are hidden |
| Reflexivity / systems | **N/A** | Research output, no deployed policy | N/A | None |

**Hard-fail conditions met** (from the audit standard):

- Condition 6: the model, feature set, and construction parameters were selected on the
  evaluation data. The final specification is not a pre-registered holdout result.
- Condition 5 (partial): the reported metrics cannot be reproduced exactly from a frozen
  data artifact because `yfinance` is mutable and no data hash is recorded.
- Condition 3 (partial): the ADV feature is computed from split-adjusted prices and raw
  volume, which is not a valid point-in-time dollar volume around splits.

---

## 3. Blockers

### B1. The sample is survivor-only, and the report calls the bias "residual"

**Severity: blocker for publication; major for a public release.**

Evidence, computed from the cached panel:

| Quantity | Value |
| :--- | :--- |
| Tickers in panel | 895 |
| Tickers whose last valid date is before 2025-06-01 | **0** |
| Tickers whose first valid date is after 2005-02-01 | 271 |
| Median listing span | 21.0 years |
| Equal-weight panel CAGR, 2005-2025 | **18.14%** |
| S&P 500 price CAGR | 8.68% |
| S&P 500 total-return CAGR | 10.79% |

A 20-year sample of 895 large caps with **zero** delistings is not a market sample. It is
the set of companies that survived and remained large enough to be in the current S&P
500/400. Every delisted, acquired, or demoted name is absent by construction. This is not
"residual" survivorship, which is how `README.md` line 196 and `docs/report.md` Section 9
describe it. It is complete survivorship.

The 7.4 percentage-point gap between the equal-weight panel and the index is not all
survivorship: equal-weighting and the mid-cap exposure in the candidate pool contribute.
But a 20-year panel of 895 large caps with zero delistings is not a market sample, and the
gap cannot be decomposed without a point-in-time dataset. The direction of the bias is not
in doubt.

Consequences:

- Factor premia are biased upward. Long-short spreads are affected because the short leg
  never contains a company that later failed.
- Capacity is biased upward, because ADV is measured only for survivors.
- The capacity ordering (C2) may survive, since it is a turnover ordering, but the levels
  do not.

**Minimum fix.** For a paper, rebuild on a point-in-time dataset with delistings (CRSP, or
a licensed equivalent) and re-run. For a GitHub release, replace "residual survivorship"
with the table above and state that the levels are not investable estimates. Do not present
the capacity numbers without this paragraph on the same page.

### B2. The capacity ordering is a model identity, not an empirical test

**Severity: blocker for the paper's framing; major for the README.**

`capacity._solve_cost_drag` and `_solve` are deterministic monotone functions of the mean
traded notional `S1` and the impact term `S2`. With three factors, the "ordering" has no
sampling distribution and cannot fail unless the cost model is mis-specified. Recomputed
Spearman correlation between cost-drag capacity and turnover is **1.0**; with three points
that statistic is inevitable if the order matches, which is exactly the point. The
"ordering" is a restatement of the turnover ranking through a deterministic formula.

H4 in `problem_framing.md` is written as a hypothesis with a pass condition. The report
reports it as "Pass". That is not a test; it is algebra.

The substantive result is the **level**: under a calibrated square-root model with a 10-day
execution horizon, reversal loses 100bp of annual premium at roughly $8m, momentum at
$466m, low volatility at $2.5bn. That is useful. The ordering is not.

The level is not robust either. With equal weights, `S2` scales as `tau^(3/2)`, so
`A*` scales as `tau^-3`: the turnover ranking is cubed. More importantly, `A*` is linear in
the execution horizon `D`, and `D` is excluded from the published sensitivity grid:

| Execution horizon | LOWVOL | MOM | STREV |
| :--- | ---: | ---: | ---: |
| 1 day | $253m | $47m | $1m |
| 5 days | $1,266m | $233m | $4m |
| 10 days (headline) | $2,531m | $466m | $8m |
| 21 days | $5,315m | $979m | $16m |

A 21x range in an assumption that was set to 10 after one-day execution "made capacity
implausibly small" (ADR-0007). The headline is a choice of `D`, not a property of the
market. `methodology.md` lists `execution_days` as a sensitivity dimension; the code does
not vary it.

**Minimum fix.** Delete H4 as a hypothesis. Present capacity as a model-implied
quantification with an explicit statement that the ordering follows mechanically from
turnover, and put the execution horizon in the sensitivity grid. If an empirical ordering
is wanted, it must be tested against an external capacity proxy (fund AUM, ETF size, flow
elasticities), which the project does not have.

### B3. `es_5` is a quantile, not expected shortfall

**Severity: blocker for publication; major for the release.**

- `src/fcr/backtest.py:65` sets `es_5 = net.quantile(0.05)`.
- `src/fcr/decision.py:100` uses the same quantile in the bootstrap difference.
- `src/fcr/targets.py` contains a correct `expected_shortfall` (mean of the tail), but the
  decision layer does not use it.
- `docs/report.md` Section 7 uses the correct ES; Section 8 uses the quantile. The same
  label refers to two different statistics in one document.

Recomputed with true ES5:

| Factor | Fragility ES5 | Vol-managed ES5 | Difference | 95% CI |
| :--- | ---: | ---: | ---: | :--- |
| MOM | -5.99% | -4.45% | -1.54% | (-2.50%, -0.63%) |
| STREV | -4.67% | -3.53% | -1.14% | (-2.01%, -0.36%) |
| LOWVOL | -4.02% | -3.24% | -0.78% | (-1.31%, -0.30%) |

The qualitative conclusion survives and is **stronger**: the overlay is worse by 0.8 to
1.5 percentage points of weekly tail loss, not 0.4 to 0.7. But the reported magnitudes are
wrong by roughly half, and the label is wrong.

Two further defects in the same comparison, both confirmed:

- **The exposure match is not exact.** The volatility-managed leg is rescaled to the
  overlay's mean and then clipped, so its mean falls short: 0.900 vs 0.920 (MOM), 0.925 vs
  0.930 (STREV), 0.935 vs 0.942 (LOWVOL). The mismatch favours the comparator by up to 2
  percentage points.
- **The random control is read backwards.** The report says that if the overlay's tail
  metric is inside the random range, its timing is indistinguishable. Recomputing the
  percentile rank of the overlay's ES5 among 200 random exposure paths gives **0.74 (MOM),
  0.95 (STREV), 0.98 (LOWVOL)**. For two factors the overlay has better tail timing than
  95-98% of random paths. That is evidence of timing value, not of noise. It still loses to
  volatility management, but "adds nothing" is the wrong conclusion; "adds less than
  volatility management" is the defensible one.

**Minimum fix.** Use `targets.expected_shortfall` everywhere, rename the column `es_5` to
`es_5` only if it is true ES, regenerate the report and README, and state the definition in
the methodology.

### B4. The exploratory per-factor result is not robust

**Severity: blocker for the paper's exploratory claim; major for the release.**

The report highlights a significant momentum coefficient of -1.91% per SD. Two
falsification tests break it:

**Raw quintile sort.** The simplest assumption-light version of the hypothesis, most fragile
quintile minus calmest quintile of forward 4-week return:

| Factor | Q5 minus Q1 | 95% CI |
| :--- | ---: | :--- |
| MOM | **+0.77%** | (-0.36%, +1.91%) |
| STREV | **+1.02%** | (-0.05%, +2.29%) |
| LOWVOL | **+1.08%** | (-0.33%, +2.51%) |

All three point the **opposite way** to the hypothesis. The negative QR coefficient is a
function of the controls and the linear-in-z specification, not a monotone relationship
visible in the data.

**Subsample stability.** Pooled `tau = 0.10` coefficient:

| Period | Coefficient |
| :--- | ---: |
| 2005-2009 | -1.93% |
| 2010-2017 | **+1.01%** |
| 2018-2025 | -1.15% |

The sign flips. Per factor, MOM goes from +0.77% in 2010-2017 to -2.40% in 2018-2025;
LOWVOL from +1.13% to -3.71%. The full-sample "significant" result is an average over
regimes with opposite signs.

The corrected bootstrap makes the momentum result weaker still: the per-factor CI is
(-3.74%, -0.07%), barely excluding zero, and it is a 2018-2025 phenomenon inside an
unstable full-sample average. A result that survives one specification, one bootstrap, and
one subperiod, and reverses in the simplest sort, is not a finding. It is a specification
artifact.

The methodology promised subsample stability in Section 6.2. The report omits it. Running
it contradicts the exploratory narrative.

**Minimum fix.** Add the quintile sort and the subsample table to the report. Downgrade the
momentum result from "significant" to "unstable, regime-dependent, not replicated". Do not
use it to argue that fragility works for momentum.

### B5. The fragility composite is dominated by one construct, and one measure is degenerate

**Severity: major; blocks the "four families" claim.**

Computed from `fragility.long`:

| Measure | Unique values | Range |
| :--- | ---: | ---: |
| Unweighted breadth | **13** | 88 to 100 |
| Liquidity-weighted breadth | 3,131 | 38 to 79 |

Unweighted effective breadth is constant by construction: dollar-neutral equal-weight legs
of 50 names give a breadth of 100. It contributes no information and should not be described
as a separate measure.

Spearman correlations among the raw measures:

| | sync | breadth_liq | exit_days | persistence |
| :--- | ---: | ---: | ---: | ---: |
| sync | 1.00 | 0.29 | -0.48 | 0.36 |
| breadth_liq | 0.29 | 1.00 | **-0.76** | 0.08 |
| exit_days | -0.48 | -0.76 | 1.00 | -0.10 |
| persistence | 0.36 | 0.08 | -0.10 | 1.00 |

Liquidity-weighted breadth and exit horizon are two views of the same liquidity construct
(rho = -0.76). The equal-weighted composite therefore double-counts liquidity and
under-counts synchronization and persistence.

**Minimum fix.** Drop the unweighted breadth from the composite, report the correlation
matrix, and show a sensitivity analysis with alternative weights (equal, PCA, rank-average)
and with each measure alone. The composite's null result should be shown to be robust to
that choice, not assumed.

### B6. Selection is not accounted for: no trial ledger, and construction changed after seeing results

**Severity: blocker for publication; major for the release.**

The repository does not disclose the search that produced the final specification. From the
development history and ADRs, the following were evaluated on the same data:

- Seven factor candidates: MOM, STREV, LOWVOL, MAX, HIGH52, IVOL, BAB.
- Two rebalancing frequencies (weekly, monthly).
- Two turnover-control settings (none, 8%/18% bands).
- Two execution horizons (1 and 10 days).
- Two capacity definitions (premium retention, cost drag).
- At least 48 overlay configurations.
- Multiple bootstrap sizes.

The report presents the final three factors and the final construction as if they were
pre-specified. `DECISIONS.md` ADR-0007 discloses four changes, which is good practice, but
the report's limitations section does not say that the specification was revised after
inspecting results. This is HARKing-adjacent. A referee will ask for the trial ledger and a
holdout.

**Minimum fix.** Add a "researcher degrees of freedom" section listing every specification
tried, including the rejected factors and the reason. Either pre-register the final
specification on a fresh period or label the entire study as exploratory. The current
"pre-registered" language overstates what happened.

---

## 4. Independent review and additional blockers

An independent red-team pass read the code without running it. Six findings were raised. I
verified each; one was directionally wrong, and correcting it matters for the record.

| Independent finding | Status | Verified result |
| :--- | :--- | :--- |
| The bootstrap collapses duplicates via `np.isin`, so the interval is wrong and H1 flips | **Confirmed bug, wrong direction** | Mean unique fraction is 0.635. The resample is a 63% subsample, which *understates* the SE. Corrected SE is larger (0.51-0.54 vs 0.40), the corrected CI is wider (-1.88%, +0.30%), and the null verdict **stands**. The independent reviewer's predicted CI (-1.30%, -0.06%) is not reproducible. |
| The candidate pool is current index membership, not point-in-time | **Confirmed** | Matches B1. Zero delistings in 895 names. |
| The controls include the week after the decision date, and the target skips it | **Confirmed** | Lagged controls change the pooled estimate from -0.68% to -0.95%; fully aligning the target gives -0.73% (CI -1.88%, +0.30%). The verdict survives; the specification is still wrong. |
| Capacity ordering is an identity, and the execution horizon is omitted from the sensitivity band | **Confirmed** | A* is proportional to the execution horizon. At D=1, 5, 10, 21: MOM $47m, $233m, $466m, $979m; LOWVOL $253m, $1.27bn, $2.53bn, $5.32bn. A 21x range in an unestimated assumption. |
| `es_5` is a quantile; the exposure match is not exact; the random control is read backwards | **Mostly confirmed** | ES mislabel and exposure mismatch confirmed. Random percentile ranks are 0.74 (MOM), 0.95 (STREV), 0.98 (LOWVOL), so the overlay has *better* tail timing than most random paths, not "indistinguishable" timing. It still loses to volatility management. |
| One fragility measure is degenerate and two are the same variable | **Confirmed** | Matches B5. Unweighted breadth has 13 unique values; breadth_liq and exit horizon correlate -0.76. |

The most important correction: **the headline null is not an artifact of the bootstrap
bug.** It survives the corrected resampling, the lagged controls, and the fully aligned
target. But every interval in the report is too narrow, and the true MDE is **1.52%**, not
1.12%. The study is weaker than advertised, not wrong in sign.

### B7. The bootstrap is not a bootstrap

**Severity: blocker for publication; major for release.**

`stats.bootstrap_dates` returns an array of length n **with replacement**
(`stats.py:35-44`). Every consumer then converts it to a boolean set membership:
`mask = np.isin(dates, drawn)` (`study.py:156-160`, and the same pattern in
`per_factor_regression` and `secondary_regression`). `np.isin` collapses duplicates, so
each replicate contains about 63.5% of dates, sampled **without** replacement. The variance
of a 63% subsample is smaller than the variance of a full bootstrap, so the reported SE is
**understated by about 21%**.

Verified: mean unique fraction 0.635; primary SE 0.403 (current) vs 0.511 (corrected);
corrected CI (-1.68%, +0.26%) at 400 reps, and (-1.88%, +0.30%) with the aligned target.
The MDE becomes 1.52% per SD.

The test suite encodes the defect: `tests/test_stats.py:22-28` asserts that the resample is
a *subset* of the dates, which is true precisely because duplicates were collapsed.

**Fix:** resample rows with duplicates retained (`frame.iloc[rows]`), or fit with frequency
weights equal to the draw counts. Assert `mean(unique(draw)) > 0.99 * n`; a 0.63 fraction is
a failure, not a pass.

### B8. The controls use data from after the decision date

**Severity: blocker for publication; major for release.**

`factors.returns[t]` is the return over `(t, t+1]` (verified: `weekly.loc[t]` equals
close-to-close from `t` to the next rebalance). `_controls` then computes `log_vol`,
`mkt_vol` and `trail_12w` from that series **through index t**, which includes the week
after the decision date (`study.py:59-84`). The target, `cum.shift(-4)/cum - 1`, starts at
`t+1` and therefore skips that same week. The design inserts the post-decision week into the
controls and removes it from the outcome.

Quantified:

| Specification | tau=0.10 | tau=0.50 |
| :--- | ---: | ---: |
| As reported | -0.68% | +0.17% |
| Controls lagged one week | -0.95% | +0.09% |
| Controls lagged and target aligned to start at t | -0.73% | +0.16% |

The verdict is unchanged, but the reported coefficient is not the pre-registered estimand.
The fully aligned CI is (-1.88%, +0.30%).

**Fix:** build controls from `rf.shift(1)` and define `fwd_h[t] = cum[t+h-1]/cum[t-1] - 1`
(equivalently `cum.shift(-(h-1))/cum.shift(1) - 1`). Add a truncation test for the controls,
not only the fragility features.

---

## 5. Major findings

### M1. Split-adjusted close times raw volume is not dollar volume

`Panel.dollar_volume` = `close (split-adjusted) * volume (raw)`. Dollar volume is
split-invariant, so this product should be stable across a split. It is not:

| Ticker | Split date | Dollar volume after / before |
| :--- | :--- | ---: |
| NVDA | 2021-07-20 | 0.38 |
| AMZN | 2022-06-06 | 0.51 |
| AAPL | 2014-06-09 | 0.71 |
| TSLA | 2020-08-31 | 1.40 |

The ratios should be near 1.0. Pre-split ADV is understated by roughly the split factor,
which affects universe inclusion and capacity for the affected names. `data.validate`
counts large price moves but does not test this.

**Fix:** store unadjusted close alongside adjusted close, compute dollar volume from
unadjusted close, or adjust volume by the split factor.

### M2. `_fetch_one` permanently caches transient empty responses

`src/fcr/data.py:175-177` writes an empty parquet when `yfinance` returns an empty frame:
"A valid 'no data' answer". A transient outage, rate-limit response, or malformed response
is indistinguishable from a delisted ticker. Once cached, the ticker is excluded from every
future run, and the failure is silent.

**Fix:** distinguish "confirmed no data" (after N retries with distinct error handling) from
"transient empty"; never cache the latter; log excluded tickers to the manifest.

### M3. Test coverage does not reach the headline results

18 tests pass, covering `factors`, `universe`, `capacity` (partially), `fragility`
(leakage), and `stats`. There are **no tests** for `study.py`, `decision.py`, `overlay.py`,
`backtest.py`, `targets.py`, `data.py` validation edge cases, `report.py`, `pipeline.py`, or
`repro_v1.py`. The primary estimate, the overlay comparison, and the capacity table are
protected only by the end-to-end run.

**Fix:** add unit tests for the ES definition, the overlay schedule, the comparator
exposure matching, the p-value calculation, and the capacity solver against a brute-force
reference (the last already exists but is limited to one factor and 20 dates).

### M4. The secondary "p-value" is not a p-value

`src/fcr/study.py:278` computes `pvalue = mean(bootstrap_samples >= 0)`. The bootstrap
distribution is centered at the estimate, so this is the posterior probability that the
parameter is positive, not the probability of observing the estimate under the null. The
correct bootstrap p-value uses the centered distribution:
`P(|theta* - theta_hat| >= |theta_hat|)`.

For the breadth-at-13-weeks result, the reported p is 0.0000 and the centered p is also
0.0000 at four decimals, so the conclusion is unaffected. The method is still wrong and
would fail review.

**Fix:** use the centered p-value (already implemented in `stats.bootstrap_pvalue` but not
used), and report it for every secondary test.

### M5. Independent n is reported as rows

`docs/report.md` reports 2,780 rows. With 4-week overlapping returns and three correlated
factors, the independent units are roughly 261 four-week blocks, not 2,780 rows. The
evidence standard requires independent n. The bootstrap SE partially accounts for this, but
the reported n does not.

**Fix:** report `n_dates`, `n_blocks`, and `n_factors` separately; use the block count in
the power calculation.

### M6. H3 is implemented more strictly than the pre-registered rule

`problem_framing.md` says: both tail metrics improve and at least one is significant.
`src/fcr/report.py:319-320` requires `improves` for both metrics, and `improves` is defined
as the bootstrap CI excluding zero. So the code requires both to be significant, which is
stricter than the document. The result is the same (fail), but the implementation and the
protocol disagree.

**Fix:** align the code to the protocol or amend the protocol with an ADR.

### M7. The capacity table shows `$0M` where the text says "undefined"

For LOWVOL, the premium-retention capacity is undefined because the gross premium is
negative. `capacity._solve` returns 0.0, and the report renders it as `$0M`. The text
directly above says "undefined for factors with no gross premium". A reader sees a number
that contradicts the prose.

**Fix:** return `NaN` and render `n/a`, or use a sentinel and a footnote.

### M8. The archived V1 has no superseded banner

`docs/archive/v1/README.md` still opens with the original title and claims. A reader who
arrives via a search result can read the invalid 0.9483 result with no warning. The PDF is
also archived without a banner. This is a reputational risk, not a code risk.

**Fix:** prepend a two-line "SUPERSEDED: results invalid, see docs/audit_v1.md" banner to
both the archived README and a companion note for the PDF.

### M9. Reproducibility is weaker than the README claims

- No data hash or frozen snapshot. `yfinance` is mutable; a re-run in six months will
  produce different prices for the same tickers.
- Dependencies use lower bounds (`numpy>=1.26`), not pins.
- `configs/v2.json` contains only `bootstrap_reps`; the rest is the code default, so a
  default change silently changes the run.
- The README says "data snapshot" but the manifest records only start/end dates.

**Fix:** pin exact versions, freeze the full config, record a hash of the panel, and
publish a small frozen fixture or a data-availability statement.

### M10. The "no look-ahead, enforced mechanically" claim is too broad

`README.md` line 101 says look-ahead is enforced mechanically. The truncation test covers
fragility features at a set of dates. It does not cover the decision layer, the capacity
model, or data-quality leakage (M1). The claim should be "features are tested for
truncation invariance; the decision layer and data pipeline are audited separately."

**Fix:** narrow the claim and extend the test to the backtest/overlay path.

---

## 6. Release gates

### GitHub release: conditional GO after P0

| # | Fix | Effort | Why |
| :-: | :--- | :--- | :--- |
| 1 | Add `LICENSE` (MIT) | minutes | README says MIT; no file exists |
| 2 | Add CI (pytest on push) | 30 min | Public repo without tests in CI |
| 3 | Fix `es_5` to true ES and regenerate | 1 h | Mislabeled headline metric |
| 4 | Add survivorship disclosure with the 0-delisting fact and CAGR gap | 30 min | Current "residual" wording is misleading |
| 5 | Reframe capacity as a model output, not an H4 test | 1 h | Unfalsifiable claim |
| 6 | Add subsample table and temper the momentum claim | 1 h | Exploratory result flips sign |
| 7 | Banner the archived V1 | 10 min | Prevents citation of invalid results |
| 8 | Fix the empty-cache failure | 30 min | Silent universe shrinkage |
| 9 | Pin dependencies; freeze config | 30 min | Reproducibility |
| 10 | Correct the secondary p-value | 30 min | Method is wrong even if conclusion holds |
| 11 | Fix the bootstrap to retain duplicates and assert unique fraction > 0.99 | 1 h | SE understated by 21%; MDE 1.52%, not 1.12% |
| 12 | Lag the controls and align the target to start at `t` | 1 h | The reported coefficient is not the pre-registered estimand |
| 13 | Add the execution horizon to the capacity sensitivity grid | 30 min | Capacity ranges 21x over D in {1..21} |
| 14 | Report random-overlay percentile ranks, not inside/outside | 30 min | The overlay beats 74-98% of random paths |
| 15 | Update the headline CI to (-1.88%, +0.30%) and MDE to 1.52% | 30 min | The current numbers are too narrow |
| 16 | Add tests for `study`, `decision`, `overlay`, `backtest`, `targets` | 2 h | Headline results have no unit protection |

After these, the repository is a credible portfolio project. It is not a paper.

### Formal publication: NO-GO

The paper-level blockers are not editorial:

1. **Survivor-only data.** A journal referee will reject on this alone. A point-in-time
   dataset with delistings is required (CRSP or equivalent). The capacity levels and the
   factor premia both change.
2. **No holdout and no pre-registration of the final specification.** The construction was
   revised four times after inspecting results. A paper needs a fresh period or a genuine
   pre-registration.
3. **No trial ledger.** Seven factor candidates and dozens of overlay configurations were
   evaluated. The reported results are selected.
4. **The headline "capacity ordering" is an identity.** It cannot carry a paper.
5. **The exploratory result is unstable.** The quintile sort points the other way, the sign
   flips across subsamples, and the corrected per-factor CI (-3.74%, -0.07%) barely excludes
   zero.
6. **No comparison to existing crowding measures.** Cahan-Luo, Kinlaw-Kritzman, and
   liquidity-squeeze indices are the natural benchmarks. The paper does not position
   against them.
7. **The inference code was wrong in two places.** The bootstrap collapsed duplicates and
   the controls used a post-decision week. Both are fixable, and the headline null survives
   both fixes, but the published interval and MDE are wrong until they are fixed.

A publishable version would need: PIT data, a pre-registered holdout, the trial ledger, a
correct ES definition, the subsample analysis, an external crowding benchmark, and a
reframing of the contribution as "a calibrated capacity measurement and a well-powered null"
rather than "a crowding signal". That is a different, larger project.

---

## 7. What survived the attack

These are genuine passes and should be kept.

1. **The leakage guard has teeth.** Mutation test: the correct expanding z-score gives a
   truncation difference of exactly 0.0; a deliberately leaked full-sample z-score gives
   6.2e-3. The test would catch the V1 defect. It does not cover the controls; that is B8,
   not a failure of this test.
2. **C1 is exact.** Rebuilding V1's two factors gives a return correlation of -1.0000 and a
   weight gap of 0.0. The audit's central finding is not in doubt.
3. **The headline null survives the inference repairs.** Correcting the bootstrap
   (duplicates retained), lagging the controls, and aligning the target to start at `t` gives
   **-0.73% per SD (95% CI -1.88% to +0.30%)**. The interval includes zero. The negative
   result is not an artifact of the bug; it is a real, and weaker, null. The corrected MDE is
   1.52%, not 1.12%.
4. **The secondary breadth result survives.** With the corrected bootstrap, the 13-week
   breadth coefficient is -2.27% (CI -3.75% to -0.41%) and remains the one measure that
   clears the pre-specified family.
5. **The overlay negative result is robust to design.** Across 48 overlay configurations
   (floor 0-0.5, start 0.4-0.8, end 0.85-0.99), the fragility overlay **never** beats the
   volatility-managed comparator on 5% ES. The best configuration still loses 0.34-0.42
   percentage points. This is the strongest result in the project.
6. **True ES confirms it.** With the correct definition, the overlay is worse by 0.8-1.5
   percentage points with CIs excluding zero. The conclusion is stronger than reported.
   The random-path ranks add nuance: the overlay beats 74-98% of random exposure paths on
   tail timing, so the signal is not pure noise; it is simply weaker than volatility
   management.
7. **The capacity solver is correct.** Closed form matches brute force to 1e-8, and net
   premium is monotone in AUM.
8. **No security exposure found.** No secrets, no credentials, no data files in git history,
   no large binaries. `.env` is ignored. The only hygiene issue is the hardcoded path in
   `scripts/fetch_data.py`.
9. **The tests pass.** 18/18, including the truncation and invariant suites.

---

## 8. What would change the verdict

| Claim | Current verdict | Evidence that would change it |
| :--- | :--- | :--- |
| C2 capacity levels | INCONCLUSIVE | Re-run on a PIT dataset with delistings; show the ordering and levels under two independent impact calibrations |
| C3 null | INCONCLUSIVE | Pre-register the specification on 2026+ data; show the CI remains inside the equivalence bound |
| C4 overlay | PASS (negative) | A pre-registered overlay that beats vol-managed on true ES with a CI excluding zero |
| C6 ordering | FAIL as a test | Replace with an external capacity proxy (fund AUM, ETF flows) and test the ordering out of sample |

---

## Appendix A: experiments run for this review

| # | Experiment | Result |
| :-: | :--- | :--- |
| A1 | Mutation test of the leakage suite | Honest 0.0, leaked 6.2e-3. Guard has teeth. |
| A2 | Breadth uniqueness | Unweighted 13 values (88-100); liquidity-weighted 3,131 (38-79) |
| A3 | Measure correlation matrix | breadth_liq vs exit -0.76; others weak |
| A4 | Capacity vs turnover rank correlation | Spearman 1.0 |
| A5 | Survivorship profile | 0 delistings in 895 tickers; EW CAGR 18.14% vs 10.79% |
| A6 | Split/dollar-volume distortion | NVDA 0.38, AMZN 0.51, AAPL 0.71, TSLA 1.40 |
| A7 | Overlay design grid | 0/48 configurations beat vol-managed |
| A8 | True ES5 recomputation | Differences -1.54%, -1.14%, -0.78%; CIs exclude zero |
| A9 | Raw quintile sort | +0.77%, +1.02%, +1.08% (opposite sign to hypothesis) |
| A10 | Subsample stability | -1.93%, +1.01%, -1.15% (sign flip) |
| A11 | Secondary p-value calibration | Reported and centered both ~0.0000; method still invalid |
| A12 | Repository security scan | No secrets, no data in history, no large files |
| A13 | Install and CLI | `pip install -e .` works; `python -m fcr --help` works |
| A14 | Bootstrap uniqueness check | Mean unique fraction 0.635; corrected SE 0.511 vs 0.403 |
| A15 | Corrected per-factor inference | MOM -1.91% (CI -3.74, -0.07); STREV -0.76% (-2.82, +1.18); LOWVOL +0.38% (-1.53, +1.76) |
| A16 | Lagged controls and aligned target | -0.95% (controls lagged); -0.73% (fully aligned, CI -1.88, +0.30) |
| A17 | Random-overlay percentile ranks | 0.74 (MOM), 0.95 (STREV), 0.98 (LOWVOL) |
| A18 | Execution-horizon sensitivity | 21x range from D=1 to D=21 |

## Appendix B: artifacts that must not be cited as-is

- `docs/archive/v1/README.md` and the archived PDF: contain the invalid 0.9483 result.
- `docs/report.md` Section 1 and Section 7: the reported CI (-1.49%, +0.08%) and MDE 1.12%
  were computed with the collapsed bootstrap. The corrected values are (-1.88%, +0.30%) and
  1.52%.
- `docs/report.md` Section 8: `es_5` is a quantile, not ES. True ES differences are larger.
- `README.md` lines 63-76: capacity ordering presented as a finding rather than a model
  output, and the level depends on the execution horizon.
- `README.md` line 196: "survivorship" understated as residual.

---

*This is a self-audit. Its PASS results are weaker than an external review's, and its FAIL
results should be treated as binding until resolved. Nothing here is investment advice.*
