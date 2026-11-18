# Independent Audit: Crowded Exits v2

**Date:** 2026-11-18
**Scope:** the working tree, cached panel, generated results, documentation, tests, and git state of `factor-crowding-risk`.
**Method:** full code read, independent re-runs from the cached panel, targeted falsification tests, and a claim-by-claim comparison of README, report, methodology, and code.
**Stance:** adversarial. The objective was to find the evidence that would make the project's claims fail, not to confirm them.
**Independence:** this is a second-pass self-audit, not an external review. It was run in a separate session but by the same model family. Its PASS results should still be treated as provisional; its FAIL results are reproducible and should be treated as binding until fixed.

> **Status after the v2.1 fixes (2026-11-18):** this document records the audit that
> drove the current correction. Most code-level findings are now addressed: the
> bootstrap, control alignment, true ES, centered p-values, capacity reframing,
> tests, and documentation drift. The survivor-only data, missing point-in-time
> delistings, and the paper-level gaps remain. Read this as the audit trail, not as
> the current status of the repository. Current results: `docs/report.md`.

---

## 1. Verdict

**The project is not complete, and it is not yet flagship-quality.** It is a strong, unusually honest research prototype with a credible negative result and a good engineering skeleton. But the implementation does not yet support the claims the documentation makes.

The single most important finding:

> **The project has diagnosed its own defects but has not fixed them in code. The README now describes a corrected study that the pipeline does not run, the generated report still contains the uncorrected numbers, and the entire V2 codebase is untracked in git.**

A fresh clone of the repository contains only V1 code. A reader cannot reproduce the V2 results from the repository, and the run manifest's `git_commit` points at a V1 documentation commit. That is a release blocker independent of any statistical question.

The second most important finding:

> **The fragility result is weaker than the report states: the composite is dominated by one measure (liquidity-weighted breadth), it is 40% correlated with volatility, and the project's own pre-registered H2 test fails. After controls, the coefficient loses about 68% of its magnitude. The honest conclusion is "this fragility proxy is largely a volatility proxy", not "no left-tail association was detected".**

The third:

> **The capacity numbers are model illustrations, not measurements. They move by 21x with the execution horizon, by about 2x with the turnover convention, and by orders of magnitude with the assumed premium. The realized factor premia are not statistically distinguishable from zero, and the factors are not beta-neutral.**

These are fixable. The project has the right ingredients for a flagship portfolio piece: a forensic V1 audit, a clear research question, a credible negative result, a modular pipeline, and a level of candor that is rare. What it lacks is the last mile of execution: commit the code, fix the inference, align the documents, quantify the uncertainty, and stop overclaiming.

**Recommended positioning:** a rigorous case study in **measurement failure and negative results** for factor crowding proxies, plus a transparent **capacity-model template**. Not an investable crowding signal, not a source of capacity measurements, and not yet a paper.

---

## 2. What the project claims, and what is actually true

| Claim in the documentation | Evidence tier offered | Audit verdict |
| :--- | :--- | :--- |
| "Version 2 implementation complete. Results generated, tested, and reproducible." (`README.md`) | None; assertion | **False.** V2 code, tests, configs, and docs are untracked. The manifest commit is V1. The report is stale. |
| "Public release is gated on the P0 list" (`README.md`) | Self-audit | **Accurate, but the gate is wide open.** All code-level P0 items remain open. |
| Primary coefficient `-0.73%` per SD, 95% CI `-1.88%` to `+0.30%`, MDE `1.52%` (`README.md`) | Ad hoc recomputation after the self-audit | **Not produced by the code.** The code still collapses bootstrap duplicates. Independent corrected estimates are `-0.68%` (CI `-1.68%` to `+0.26%`) as-reported, or `-0.73%` (CI `-1.94%` to `+0.50%`) fully aligned, with MDE `1.43%` or `1.69%`. The exact "corrected" numbers are themselves not stable. |
| Generated report's `-0.68%`, CI `-1.49%` to `+0.08%`, MDE `1.12%` (`docs/report.md`) | Pipeline | **Computed with the defective bootstrap.** The SE is understated by about 21%. |
| "The fragility composite does not predict the left tail" | In-sample QR + bootstrap | **Defensible as "not detected at this resolution", not as "does not predict".** H2 fails: the raw association is largely volatility. The study is underpowered. |
| "The overlay loses to volatility management" | In-sample backtest, quantile ES | **Qualitatively robust, but the report uses a quantile, not ES.** True ES differences are `-1.49%`, `-1.10%`, `-0.76%` per week for MOM/STREV/LOWVOL, about twice the reported magnitudes. |
| "The overlay beats 74-98% of random paths on tail timing" (`README.md`) | Red-team recomputation | **Directionally correct, but not in the generated report.** Our true-ES ranks are 0.94, 0.87, 0.85. The report text still says "inside this range", which is the wrong interpretation. |
| "Capacity ordering STREV <= MOM <= LOWVOL" | H4 hypothesis test | **Not a test.** It is a deterministic function of turnover under the cost model. The report still presents it as a result; the README qualifies it. |
| "Capacity at 100bp cost drag: $8m, $466m, $2.5bn" | Model calculation | **Model output, not measurement.** The number is conditional on an unestimated execution horizon, impact coefficient, turnover convention, and a survivor-only data set. See B5 and Section 5.7. |
| "Beta-neutral" factors | Signal-space residualization | **False as stated.** Realized S&P betas are `-0.144` (MOM, t=-2.97), `+0.286` (STREV, t=5.15), `-0.113` (LOWVOL, t=-3.47). None of the CAPM alphas is significant. |
| "Pre-registered" primary and decision rules | Problem framing | **Overstated.** The construction changed after inspecting results (ADR-0005, ADR-0007). There is no trial ledger and no holdout. |
| "A reader can reproduce the headline table from the manifest and cached data" | Methodology §11 | **False in practice.** Code untracked, data mutable and unhashed, tables overwritten between runs. |
| "No claim in the README exceeds what the report shows" | Gate G6 | **False.** README and report disagree on the primary CI, MDE, ES definition, random-overlay interpretation, and survivorship. |

---

## 3. What is genuinely strong (keep this)

The audit should not obscure the parts that work. These are real assets:

1. **The V1 audit is excellent.** `docs/audit_v1.md` traces the invalid V1 numbers to specific code paths and arithmetic. The factor identity reproduces exactly: return correlation `-1.0000`, maximum weight gap `0.0`. This is the strongest part of the repository and a genuinely useful cautionary tale.
2. **The leakage guard has teeth.** The truncation test on the fragility features is a real mechanical check, not a slogan. The red-team mutation test (honest `0.0`, deliberately leaked `6.2e-3`) shows it would catch the V1 defect.
3. **The capacity solver is correct and tested.** The closed form matches brute force to `1e-8`, and net premium is monotone in AUM. The model is transparent and reusable.
4. **The overlay negative result is robust in direction.** Across 48 overlay configurations, the fragility overlay never beats the volatility-managed comparator on 5% ES. True ES makes the gap larger, not smaller. This is the most credible empirical result in the project.
5. **The documentation is candid.** The README, report, and red-team review state limitations and non-claims that most portfolio projects hide. That candor is the project's brand; it must be protected by fixing the remaining overclaims, not abandoned.
6. **The architecture is sensible.** Config, pipe, data, universe, factors, fragility, capacity, study, decision, report is a clean separation. The run manifest and config hash are the right instincts.
7. **The factor construction has real invariants.** Dollar-neutral, gross 2.0, name cap, and non-collinearity are asserted, not assumed. The `-1.0` correlation trap is explicitly guarded.
8. **No security exposure was found.** No secrets, credentials, or data files in git history. `.env` is ignored.

These strengths are why the project is worth finishing. They do not excuse the blockers below.

---

## 4. Critical findings

### B1. The V2 code is not in the repository

**Severity: blocker for release, reproducibility, and credibility.**

`git ls-files` returns 21 files. All of them are V1 or project metadata. The entire V2 implementation is untracked:

```
?? src/fcr/
?? tests/
?? configs/
?? docs/audit_v1.md
?? docs/methodology.md
?? docs/red_team_review.md
?? docs/report.md
?? docs/roadmap.md
?? docs/figures/
?? DECISIONS.md
?? pyproject.toml
```

The last commit is `298dc6c docs: add detailed Day 3 log to TODO.md`. The V2 run manifest records `"git_commit": "298dc6c"`. That commit does not contain the code that produced the results.

Consequences:

- A fresh clone cannot run `python -m fcr`; the package does not exist in the clone.
- The manifest's provenance claim is false.
- The README's repository layout (`src/fcr/`, `tests/`, `configs/v2.json`) describes files that are not tracked.
- The old V1 modules (`src/data.py`, `src/features.py`, `src/model.py`, etc.) are still tracked and visible, so a reviewer sees the invalid V1 code first.
- The generated figures and report are untracked; a fresh clone's report images would break.

**Fix:** commit all V2 files, remove or archive the V1 modules, add a clean `.gitignore`, tag `v2.0.0`, and regenerate the manifest on a clean tree. This is a one-hour fix with the highest return in the project.

### B2. The documentation describes a corrected study that the code does not run

**Severity: blocker.**

The README says:

> "Corrected after the red-team review (2026-11-17). The primary interval and MDE were recomputed after the review found a bootstrap that collapsed duplicate draws and controls that used one week of post-decision data. The corrected primary estimate is **-0.73% per SD (95% CI -1.88% to +0.30%)**, with a **minimum detectable effect of 1.52%**."

The code still contains the defects:

- `src/fcr/stats.py:113-122` and `src/fcr/study.py:156-168` still use `np.isin(dates, drawn)`, which collapses duplicate dates. The mean unique fraction is 0.635; the bootstrap is a 63% subsample, not a bootstrap.
- `src/fcr/study.py:55-84` still computes controls from `factors.returns` through `t`, which includes the week after the decision date. The target still starts at `t+1`.
- `src/fcr/study.py:278` still uses `mean(samples >= 0)` as a p-value, not the centered bootstrap p-value.
- `src/fcr/backtest.py:65` and `src/fcr/decision.py:100` still use `net.quantile(0.05)` and label it `es_5`.
- `src/fcr/decision.py:118` still defines `improves = lo > 0` for both metrics, which makes H3 stricter than the protocol.

The generated `docs/report.md` is dated 2026-11-16 and still shows `-0.68%`, CI `-1.49%` to `+0.08%`, MDE `1.12%`, and quantile `es_5`. The README is dated 2026-11-17 and shows different numbers. The report was never regenerated after the README correction.

This is not a minor doc drift. It is the same failure mode the project criticizes: a claim that the evidence does not support. The project's own Gate G6 ("README matches the report") is marked **Pass** in `TODO.md`; it is false.

**Fix:** implement the corrections, regenerate the report, make the README numbers generated or checked by a script, and delete the ad hoc "corrected" numbers until they come from the pipeline.

### B3. The inference defects remain in the code and the test suite encodes one of them

**Severity: blocker for every interval and p-value in the project.**

The bootstrap defect is confirmed:

- `bootstrap_dates` returns an array of length `n` with replacement.
- Every consumer converts it to `np.isin(dates, drawn)`, which keeps each date at most once.
- The resulting sample contains about 63.5% of dates, sampled without replacement. Its variance is smaller than a full bootstrap.
- The primary SE is 0.399-0.403 (reported) versus 0.511 (corrected). The interval is too narrow by about 21%.
- `tests/test_stats.py:22-28` asserts that the resample is a **subset** of the dates. That is exactly the defect. The test passes while the inference is wrong.

The controls misalignment is confirmed:

- `factors.returns[t]` is the return over `(t, t+1]`.
- `_controls` uses that series through `t`, including the post-decision week.
- `forward_returns` defines the target as `cum[t+h]/cum[t]`, which starts at `t+1` and skips the week in the controls.
- The fully aligned specification uses lagged controls and `cum[t+h-1]/cum[t-1]`.

Our independent recomputation, using the project's functions and 400 bootstrap replicates:

| Specification | β₀.₁₀ | SE | 95% CI | MDE |
| :--- | ---: | ---: | :--- | ---: |
| As reported (current target, current controls) | -0.682% | 0.511% | (-1.678%, +0.261%) | 1.431% |
| Lagged controls only | -0.940% | 0.514% | (-2.035%, -0.006%) | 1.441% |
| Aligned target + lagged controls | -0.733% | 0.603% | (-1.937%, +0.504%) | 1.689% |

The verdict (interval includes zero) survives, but the published interval and MDE do not. The "corrected" README numbers (`-1.88%` to `+0.30%`, MDE `1.52%`) are not reproduced by either specification; the red team's computation used a slightly different sample/alignment. The exact corrected number is itself unstable, which is why the fix must be in code, not in prose.

**Fix:** retain duplicates in every bootstrap (`frame.iloc[rows]` or frequency weights), assert the resample length equals `n` and the SE matches a reference, lag the controls, align the target, recompute every interval and MDE, and replace the subset test with a duplicate-retention test. A correct with-replacement bootstrap has about 63% unique dates; the diagnostic is the resample length, not a unique fraction near one.

### B4. Survivorship is complete, not "residual", and the data pipeline does not validate corporate actions

**Severity: blocker for capacity levels and factor premia; major for the project's credibility.**

The cached panel has:

| Quantity | Value |
| :--- | ---: |
| Tickers with data | 895 |
| Tickers whose last valid date is before 2025-06-01 | **0** |
| Tickers whose last valid date is 2025 | **895** |
| Names in the panel at end-2005 | 638 |
| Names in the panel at end-2025 | 895 |
| Equal-weight panel CAGR, 2005-2025 | **18.14%** |
| S&P 500 total-return CAGR, 2005-2025 | **10.80%** |

A 20-year panel of 895 large caps with **zero delistings** is not a market sample. It is the set of companies that survived and remained large enough to be in the current S&P 500/400. The equal-weight CAGR is 7.3 percentage points above the index. Some of that gap is equal-weighting and mid-cap exposure, but the zero-delisting fact is decisive: the sample is survivor-only.

The current wording is still too soft:

- `docs/report.md` §3 says "delisting survivorship remains".
- `problem_framing.md` §4.2 and §8 say "residual survivorship".
- `docs/methodology.md` §1.4 says "Residual survivorship" and claims the universe "is not filtered using any future information, including index membership." The candidate pool **is** current index membership. The universe rule is point-in-time with respect to liquidity, but not with respect to existence.
- `docs/report.md` §6 presents capacity numbers before the limitations section, without the 0-delisting fact on the same page.

The data pipeline also has a corporate-action problem:

- `Panel.dollar_volume` is `adjusted close × volume` (`src/fcr/data.py:59-61`).
- Adjusted close is split- and dividend-adjusted; volume is not consistently adjusted. The product is not a clean dollar volume around splits.
- `data.validate` counts large price moves but does not test split consistency, adjusted/unadjusted mixing, or dollar-volume stability.
- The methodology claims a split/dividend artefact check (`docs/methodology.md` §1.2) that is not implemented.
- `_fetch_one` permanently caches an empty response (`src/fcr/data.py:175-179`). A transient outage becomes a permanent exclusion.

**Fix:** store unadjusted close alongside adjusted close and compute dollar volume from unadjusted close, or adjust volume by the split factor. Add a split-invariance test. Record a SHA256 of the panel in the manifest. Add the 0-delisting table and the CAGR gap to the report section that contains the capacity table, not only to the limitations section. Replace "residual" with "complete" in every document.

### B5. The capacity numbers are not statistically credible as point estimates

**Severity: blocker for the "capacity report" deliverable; major for the practical value of the project.**

The capacity model is a useful framework. The headline numbers are not robust enough to present as point estimates.

**(a) The premium is not statistically distinguishable from zero.** The capacity model protects a "gross premium" estimated from the same 21-year survivor sample. HAC standard errors:

| Factor | Annualized gross premium | 95% CI | t-stat | S&P CAPM alpha (annualized) | Alpha 95% CI | t-stat |
| :--- | ---: | :--- | ---: | ---: | :--- | ---: |
| MOM | 5.15% | (-3.23%, +13.53%) | 1.20 | +6.60% | (-1.42%, +14.62%) | 1.61 |
| STREV | 1.84% | (-5.11%, +8.78%) | 0.52 | -1.06% | (-7.52%, +5.40%) | -0.32 |
| LOWVOL | -5.38% | (-11.55%, +0.80%) | -1.71 | -4.24% | (-10.37%, +1.88%) | -1.36 |

At a 50% retention hurdle, MOM's capacity is $2.34bn at the point estimate, $0 at the lower CI, and $23.3bn at the upper CI. STREV's capacity is $1m at the point estimate and $405m at the upper CI. LOWVOL has no positive premium, so retention capacity is undefined. The report's capacity table shows point estimates without these intervals.

**(b) The execution horizon is the largest sensitivity and is missing from the published band.** Cost-drag capacity is linear in the execution horizon:

| Execution horizon | LOWVOL | MOM | STREV |
| :--- | ---: | ---: | ---: |
| 1 day | $253m | $47m | $1m |
| 5 days | $1,266m | $233m | $4m |
| 10 days (headline) | $2,531m | $466m | $8m |
| 21 days | $5,315m | $979m | $16m |

A 21x range in an assumption that was set to 10 after one-day execution "made capacity implausibly small" (ADR-0007). The methodology lists `execution_days` as a sensitivity dimension; the code does not vary it.

**(c) The capacity is sensitive to the turnover convention.** The factor return series holds monthly weights constant between rebalances, which implicitly assumes weekly rebalancing to those weights. The capacity model zeroes trades on non-rebalance weeks and applies a one-week drift correction. The annualized turnover and resulting capacity:

| Factor | Code (monthly, 1-week drift) | Correct monthly drift | Weekly rebalance to constant weights |
| :--- | :--- | :--- | :--- |
| MOM | 8.89x gross; **$466m** | 9.97x gross; **$396m** | 12.87x gross; **$289m** |
| STREV | 36.27x gross; **$7.5m** | 36.91x gross; **$7.2m** | 39.64x gross; **$5.6m** |
| LOWVOL | 4.04x gross; **$2,531m** | 4.96x gross; **$2,075m** | 7.61x gross; **$1,272m** |

The capacity changes by 1.3-2.0x depending on a convention that is not disclosed. The one-week drift correction understates the full-month drift by 11-18% for MOM/LOWVOL. The weekly-rebalance assumption in the return series is inconsistent with the monthly-trade assumption in the capacity model.

**(d) The ordering is an identity.** `capacity._solve_cost_drag` is a deterministic monotone function of turnover. The Spearman correlation between capacity and turnover is 1.0. With three factors, the "ordering" cannot fail unless the cost model is mis-specified. H4 is not a hypothesis test.

**(e) The capacity is not net of the factor's own implementation costs.** The decision layer charges a 5bp scaling cost on exposure changes, not the Section 4 impact cost. The factor returns are gross of the underlying rebalancing costs. At $1bn, MOM's capacity model implies ~190bp/year of cost; at $10bn, ~465bp/year. The decision layer's "net" returns are therefore gross of the largest cost. The relative overlay comparison is probably unaffected because all comparators share the factor, but the absolute Sharpe and return numbers are not investable.

**Fix:** present capacity as a **surface** (AUM × execution horizon × impact coefficient), with a premium-retention panel that shows the premium CI and a break-even premium. Remove H4 as a hypothesis. State the turnover convention and use it consistently. Either charge the Section 4 costs in the decision layer at a stated A, or label the layer "gross of factor implementation costs". Add a `$n/a` sentinel for undefined retention capacity, not `$0M`.

### B6. The fragility index is not robust, and H2 fails

**Severity: blocker for the empirical claim.**

The composite is an equal-weight average of four z-scores: synchronization, liquidity-weighted breadth, exit horizon, and persistence. The raw measures are not independent:

| | sync | breadth_liq | exit_days | persistence |
| :--- | ---: | ---: | ---: | ---: |
| sync | 1.00 | 0.29 | -0.48 | 0.36 |
| breadth_liq | 0.29 | 1.00 | **-0.76** | 0.08 |
| exit_days | -0.48 | -0.76 | 1.00 | -0.10 |
| persistence | 0.36 | 0.08 | -0.10 | 1.00 |

Liquidity-weighted breadth and exit horizon are two views of the same liquidity construct (`rho = -0.76`). The equal-weight composite double-counts liquidity and underweights synchronization and persistence. Unweighted breadth is degenerate: 13 unique values, 88-100, because dollar-neutral equal-weight legs of about 50 names give a breadth of about 100 by construction. It is not a separate measure.

The composite's correlation with its components is uneven:

| Factor | sync | breadth | exit | persist |
| :--- | ---: | ---: | ---: | ---: |
| MOM | 0.76 | 0.76 | 0.19 | 0.51 |
| STREV | 0.55 | 0.64 | 0.36 | 0.49 |
| LOWVOL | 0.71 | 0.57 | 0.21 | 0.33 |

The composite is 40% correlated with log realized volatility at the pooled level. The project's own H2 test asks whether the coefficient retains its sign and at least half its magnitude under controls. It does not:

| Specification | Uncontrolled β₀.₁₀ | Full-control β₀.₁₀ | Retention | log_vol-only β₀.₁₀ | Retention |
| :--- | ---: | ---: | ---: | ---: | ---: |
| As reported | -2.268% | -0.682% | **0.301** | -0.870% | 0.384 |
| Aligned | -2.263% | -0.733% | **0.324** | -0.861% | 0.380 |

H2 fails. The pre-registered rule says: "If it does not [retain sign and half magnitude], the finding is 'fragility proxies volatility', which is a real result and will be stated as one." The report does not state it. This is a missing pre-registered result and a more honest headline than "no left-tail association".

The composite is also driven by one measure. Dropping breadth collapses the coefficient to zero:

| Composite variant | β₀.₁₀ | SE | 95% CI |
| :--- | ---: | ---: | :--- |
| Equal (current) | -0.733% | 0.544% | (-1.970%, +0.217%) |
| Sync only | +0.027% | 0.193% | (-0.411%, +0.340%) |
| Breadth only | -0.697% | 0.428% | (-1.633%, -0.036%) |
| Exit only | -0.854% | 0.669% | (-2.239%, +0.319%) |
| Persist only | +0.161% | 0.344% | (-0.453%, +0.805%) |
| Drop sync | -0.932% | 0.736% | (-2.673%, +0.141%) |
| Drop breadth | -0.067% | 0.481% | (-1.224%, +0.629%) |
| Drop exit | -0.497% | 0.376% | (-1.252%, +0.285%) |
| Drop persist | -0.838% | 0.563% | (-2.061%, +0.215%) |

The equal-weight composite's negative sign is almost entirely liquidity-weighted breadth. The other three measures are noise or offset. The "four-family" index is not a coherent construct. The report must show this table, not assume the null is robust to weighting.

The secondary 4-week breadth result is also weaker than the report's table suggests. The report's p-value `0.028` is not a p-value. The centered bootstrap p-value is `0.130`; the 95% CI still excludes zero because the bootstrap distribution is skewed. Only the 13-week breadth result survives Benjamini-Hochberg after the centered p-value (`0.005`, adjusted `0.040`). The report's conclusion "the 13-week breadth result survives" is correct; its 4-week "near miss" is overstated.

**Fix:** drop unweighted breadth from the composite, report the correlation matrix, show the drop-one/rank/PCA sensitivity, and make H2 a headline result. If the project wants a fragility index, it should either (a) define the construct around liquidity/exit risk alone, with breadth and exit as the core and sync/persistence as separate diagnostics, or (b) justify the equal weights with a mechanism, not convenience.

### B7. The factors are not beta-neutral, and the premia are not significant

**Severity: major for factor interpretation; blocker for capacity/premium claims.**

The project residualizes the signal on beta in cross-section, then forms equal-weight decile portfolios. That does not make the weights beta-neutral. The ex-post portfolio beta diagnostic shows mean absolute values of 0.102 (MOM), 0.052 (STREV), and 0.066 (LOWVOL), with maxima of 0.529, 0.227, and 0.404. The ADR-0005 kill criterion is based on the mean, so it passes. But the realized regression betas are significant:

| Factor | Beta vs S&P 500 | t-stat | CAPM alpha (annualized) | Alpha t-stat | R² |
| :--- | ---: | ---: | ---: | ---: | ---: |
| MOM | -0.144 | -2.97 | +6.60% | 1.61 | 0.017 |
| STREV | +0.286 | 5.15 | -1.06% | -0.32 | 0.100 |
| LOWVOL | -0.113 | -3.47 | -4.24% | -1.36 | 0.020 |

The factor returns are not market-neutral. STREV has a large positive beta; MOM and LOWVOL have negative betas. The MOM alpha is not significant (`t = 1.61`), STREV's alpha is negative, and LOWVOL's alpha is negative. The "premia" being protected by the capacity model are partly market beta, and none is statistically distinguishable from zero after beta adjustment.

This matters for the capacity deliverable: the retention capacity is a quadratic function of the premium. If the premium is zero or negative after beta adjustment, the capacity is zero or undefined. The capacity report should use a beta-adjusted expected alpha with a confidence interval, not the raw gross mean.

**Fix:** either enforce beta neutrality in weight space (with a beta-hedge overlay or a constrained optimizer) or rename the construction to "beta-residualized signal; residual beta disclosed" and add the CAPM table. Compute capacity on alpha, not gross premium. Add a break-even premium column. This is a substantive change; do not paper over it with the mean-absolute-beta diagnostic.

### B8. Testing and QA do not reach the headline

**Severity: blocker for engineering credibility.**

The test suite has 18 tests. They cover factors, universe, capacity (partially), fragility leakage, and stats. There are **no tests** for `study.py`, `decision.py`, `overlay.py`, `backtest.py`, `targets.py`, `data.py` validation edge cases, `report.py`, `pipeline.py`, or `repro_v1.py`. The primary estimate, the overlay comparison, and the capacity table are protected only by the end-to-end run.

Worse, one test encodes the core defect:

- `tests/test_stats.py:22-28` asserts that a bootstrap resample is a subset of the dates. That is true only because duplicates were collapsed. A correct test asserts that the resample has length `n`, that duplicates are present, and that the bootstrap SE matches a reference.

The leakage test covers the fragility features at one cutoff, not the study controls, the target alignment, or the decision layer. That is why the post-decision-week control defect survived. The methodology promises 20 random truncation dates, a perturbation test, a label-shuffle false-positive test, a constant-predictor benchmark, and capacity monotonicity. Only one truncation cutoff and the capacity monotonicity exist.

**Fix:** add tests for the headline path before changing any more results:
- duplicate-retention bootstrap (length `n`, duplicates present, SE matches a reference)
- control truncation invariance (delete the future, controls at `t` unchanged)
- target alignment (`fwd_4[t]` starts at `t`)
- true ES definition and edge cases
- overlay schedule boundaries and monotonicity
- comparator exposure match (within 1e-6, not "close")
- capacity solver vs brute force across all factors
- data validation: empty response is not cached; split invariance
- report/README consistency check
- end-to-end smoke test on a small synthetic panel

Add CI (GitHub Actions) running `pytest`, `ruff`, and a docs check. A public repo without tests in CI is not a flagship.

### B9. The research is not pre-registered, and there is no trial ledger

**Severity: blocker for a paper; major for a flagship portfolio project.**

The problem framing says "Pre-registered before implementation." The implementation history says otherwise. The project's own review reports seven factor candidates (MOM, STREV, LOWVOL, MAX, HIGH52, IVOL, BAB), and the repository history and ADRs confirm that several construction choices changed after results were inspected:

- Two rebalancing frequencies, two turnover-control settings, two execution horizons, two capacity definitions, at least 48 overlay configurations, and multiple bootstrap sizes were evaluated.
- ADR-0005 changed beta neutralization after the original methodology.
- ADR-0007 changed monthly rebalancing, entry/exit bands, execution horizon, and the headline capacity definition after inspecting results.
- The final three factors and the final construction are presented as if they were pre-specified.

This is HARKing-adjacent. The report's "pre-registered" language overstates what happened. A referee will ask for the trial ledger and a holdout. The FDR correction covers the 8 secondary measure/horizon tests, not the factor selection, the construction choices, or the overlay grid.

**Fix:** add `docs/trial_ledger.md` listing every specification tried, including rejected factors and the reason. Add a "researcher degrees of freedom" section to the report. Either label the entire study **exploratory** or freeze the final specification and pre-register a genuine holdout. Do not use the word "pre-registered" for the final specification unless it was actually frozen before the results.

### B10. The report omits pre-registered analyses and robustness checks

**Severity: major.**

Missing from `docs/report.md`:

- **H2**: the volatility-attenuation test. It fails; this should be a headline.
- **E2**: the expected-shortfall difference between high and low fragility quintiles. The ES table is descriptive only, with no estimate or interval.
- **Quintile sort**: the simplest assumption-light test. All three factors point the opposite way to the hypothesis (MOM +0.82%, STREV +0.84%, LOWVOL +1.02%; CIs include zero). The report omits it.
- **Subsample stability**: 2005-2009 `-2.31%`, 2010-2017 `+1.12%`, 2018-2025 `-1.44%`. The sign flips. The report omits it.
- **Composite weight sensitivity**: drop-one, rank-average, PCA. The null is not robust to dropping breadth.
- **Non-overlapping subsample**: promised in methodology §5, not implemented.
- **Placebo p-values/percentiles**: the table shows mean and sd but no formal comparison.
- **True ES in the decision layer**: the report uses quantiles.
- **Random-overlay percentile ranks**: the report table has quantiles, not the rank of the actual overlay; the text misinterprets "inside the range".
- **Gross premium confidence intervals**: promised in methodology §4.4, not implemented.
- **Execution horizon sensitivity**: the largest capacity driver, missing from the band.
- **Factor alpha/beta**: no CAPM table.
- **n_blocks**: the report reports 2,780 rows, 928 dates, and per-factor n, but not the number of independent blocks. The independent units are roughly 232 four-week blocks, not 2,780.

This is not a presentation gap. These are the analyses that determine whether the conclusions are credible. The project's own methodology promised them.

### B11. Release hygiene is incomplete

**Severity: major for a public flagship.**

- No `LICENSE` file, despite the README saying MIT (P0-1).
- No CI workflow (P0-2).
- `requirements.txt` and `pyproject.toml` use lower bounds, not pins (P0-9).
- `configs/v2.json` contains only `bootstrap_reps`; the rest is code defaults. The manifest records the full config, but a reader cannot freeze the run from the config file alone.
- The archived V1 README and PDF have no "SUPERSEDED" banner (P0-7). The archived README also contains mojibake (garbled UTF-8/Windows-1252 characters), which looks unprofessional.
- `scripts/fetch_data.py` hardcodes `D:\machine_learning_prototypes\factor-crowding-risk\src`, so it fails on any other machine.
- The old V1 modules are still in `src/`; a reviewer sees them alongside `src/fcr/`.
- `src/evaluate.py` is zero bytes.
- `docs/figures/` and `docs/report.md` are untracked.
- There is no `CITATION.cff`, no release notes, no data dictionary, no model card.

These are table stakes for a public flagship. They are also the easiest fixes.

### B12. The existing P0 list is almost entirely open

The project's own `TODO.md` lists 18 P0 items. Grouping them by status:

| P0 group | Items | Status |
| :--- | :--- | :--- |
| Code and inference | P0-3 (true ES), P0-8 (empty cache), P0-10 (centered p), P0-13 (bootstrap duplicates), P0-14 (lag controls/target), P0-15 (execution horizon) | **Open.** The code still contains every defect. |
| Tests | P0-11, P0-18 | **Open.** No tests for `study`, `decision`, `overlay`, `backtest`, `targets`, `data`, `report`, or `pipeline`. The bootstrap test encodes the defect. |
| Documentation and reframing | P0-4, P0-5, P0-6, P0-12, P0-16, P0-17 | **Partial.** The README has a corrected note; the generated report, methodology, problem framing, and TODO still contain the old numbers and claims. |
| Release hygiene | P0-1 (LICENSE), P0-2 (CI), P0-7 (archive banner), P0-9 (pins/full config) | **Open.** |

**None of the code-level P0 items is closed.** The README's correction is documentation-only. This is the central project-management finding: the project has a good diagnosis and a good plan, but it has not executed the plan. The audit's first recommendation is to stop adding analysis and close the P0 list.

### B13. Minor but real documentation/code mismatches

These are smaller than the blockers but they will be noticed by a careful reviewer:

| Claim in methodology/framing | Code reality |
| :--- | :--- |
| §1.2: cache keyed by ticker and year; split/dividend artefact check | Cache is per ticker; no split/dividend check. |
| §3.6: measure is NaN if fewer than 85% of inputs are available; zero-std z set to 0 and flagged | No 85% rule; zero std produces NaN, not 0, with no flag. |
| §4.1: baseline spread 5bp; sensitivity 2bp/15bp | Baseline 3bp; sensitivity 1bp/3bp/10bp. |
| §4.3: cost-drag includes borrow and financing | `_solve_cost_drag` includes spread and impact only; borrow/financing excluded. |
| §6.1: 5,000 bootstrap replications | Config default 2,000; `configs/v2.json` uses 800. |
| §7.3: costs charged using the Section 4 impact model; short proceeds earn T-bill less 50bp borrow | Decision layer charges 5bp scaling only; no Section 4 impact cost, no borrow. |
| §9.1: backtest fails loudly if exposure is outside [0, 1.5] | No validation. |
| §10: figures readable in grayscale and state the sample period on the face of the plot | Figure titles do not state the sample period; grayscale readability is untested. |
| Roadmap Phase 3: placebo, label-shuffle, subsample stability | Placebo exists but has no p-value; label-shuffle and subsample are not implemented. |
| Roadmap Phase 4: cost model, cash and borrow returns | Cash exists; borrow does not. |
| Roadmap Phase 5: README matches report | False. |
| Report §6: retention capacity undefined for LOWVOL | Table renders `$0M`, not `n/a`. |
| Report liquidation table | Columns are ordered `$100M, $10B, $10M, $1B, $5B`; not sorted. |

These are not all release blockers individually, but together they undermine the claim that the methodology is normative and the report is generated. The project should either implement each promise or amend the document with an ADR. Right now the documents describe a more rigorous project than the code implements.

---

## 5. Independent recomputations

All numbers below were produced from the cached panel in this audit, using the project's own functions where possible. They are not copied from the report. Reps: 400 for the primary bootstrap, 200 for composite variants and secondary, 600 for ES quintiles, 800 for the decision-layer true ES. The exact values will move slightly with the seed/spec; the qualitative pattern is stable.

### 5.1 Primary estimate under three specifications

| Specification | n | β₀.₁₀ | SE | 95% CI | MDE | β₀.₅₀ | Tail difference (CI) |
| :--- | ---: | ---: | ---: | :--- | ---: | ---: | :--- |
| As reported | 2,780 | -0.682% | 0.511% | (-1.678%, +0.261%) | 1.431% | +0.168% | -0.850% (-1.916%, +0.121%) |
| Lagged controls only | 2,780 | -0.940% | 0.514% | (-2.035%, -0.006%) | 1.441% | +0.098% | -1.037% (-2.138%, -0.051%) |
| Aligned target + lagged controls | 2,783 | -0.733% | 0.603% | (-1.937%, +0.504%) | 1.689% | +0.164% | -0.897% (-2.060%, +0.084%) |

The verdict is unchanged: the aligned interval includes zero. The tail-specificity claim is weaker: both corrected specifications have a tail-difference interval that includes zero; only the report's collapsed-bootstrap version excludes zero. The data do not establish that the effect is stronger in the left tail than at the median.

### 5.2 H2 attenuation

| Specification | Uncontrolled | Full controls | Retention | log_vol only | Retention |
| :--- | ---: | ---: | ---: | ---: | ---: |
| As reported | -2.268% | -0.682% | 0.301 | -0.870% | 0.384 |
| Aligned | -2.263% | -0.733% | 0.324 | -0.861% | 0.380 |

H2 fails by a wide margin. The log-vol control alone accounts for most of the attenuation.

### 5.3 Composite variants

| Variant | β₀.₁₀ | SE | 95% CI |
| :--- | ---: | ---: | :--- |
| Equal (current) | -0.733% | 0.544% | (-1.970%, +0.217%) |
| Breadth only | -0.697% | 0.428% | (-1.633%, -0.036%) |
| Exit only | -0.854% | 0.669% | (-2.239%, +0.319%) |
| Sync only | +0.027% | 0.193% | (-0.411%, +0.340%) |
| Persist only | +0.161% | 0.344% | (-0.453%, +0.805%) |
| Drop breadth | -0.067% | 0.481% | (-1.224%, +0.629%) |
| Drop sync | -0.932% | 0.736% | (-2.673%, +0.141%) |
| Drop exit | -0.497% | 0.376% | (-1.252%, +0.285%) |
| Drop persist | -0.838% | 0.563% | (-2.061%, +0.215%) |
| Rank average | -1.647% | 1.511% | (-4.549%, +1.173%) |

The equal-weight composite's sign is driven by breadth. Dropping breadth collapses it to zero. The breadth-only percentile interval excludes zero, but the centered bootstrap p-value for that specification is 0.13; the interval is not a test. No variant is significant after a two-sided centered test, but the index is not a coherent four-measure construct.

### 5.4 Quintile sort and subsample stability

**Quintile sort, aligned 4-week target, fragile minus calm:**

| Factor | Q5-Q1 | 95% CI | nQ1 | nQ5 |
| :--- | ---: | :--- | ---: | ---: |
| MOM | +0.824% | (-0.862%, +2.719%) | 214 | 106 |
| STREV | +0.838% | (-0.687%, +2.498%) | 222 | 82 |
| LOWVOL | +1.017% | (-1.187%, +4.241%) | 306 | 67 |

All three point the opposite way to the hypothesis. None is significant. The negative QR coefficient is a function of the controls and the linear-in-z specification, not a monotone relationship visible in the raw data.

**Subsample stability, aligned pooled β₀.₁₀:**

| Period | n | β₀.₁₀ |
| :--- | ---: | ---: |
| 2005-2009 | 314 | -2.310% |
| 2010-2017 | 1,251 | +1.117% |
| 2018-2025 | 1,218 | -1.435% |

The sign flips. The full-sample "negative" coefficient is an average over regimes with opposite signs.

**Per-factor aligned β₀.₁₀:**

| Factor | n | β₀.₁₀ | SE | 95% CI |
| :--- | ---: | ---: | ---: | :--- |
| MOM | 925 | -1.906% | 1.054% | (-4.283%, -0.065%) |
| STREV | 929 | -0.679% | 1.179% | (-3.348%, +1.629%) |
| LOWVOL | 929 | +0.181% | 0.986% | (-1.622%, +1.723%) |

MOM's interval barely excludes zero, but it reverses in the raw quintile sort and flips sign across subsamples. It is not a robust finding.

### 5.5 E2: expected shortfall by fragility quintile

**ES5(high) - ES5(low), full expanding percentile, aligned 4-week target:**

| Factor | ES5 high | ES5 low | Difference | 95% CI | nH | nL |
| :--- | ---: | ---: | ---: | :--- | ---: | ---: |
| MOM | -11.34% | -6.53% | **-4.81%** | (-7.64%, -0.21%) | 106 | 214 |
| STREV | -8.25% | -7.25% | -1.01% | (-6.28%, +3.57%) | 82 | 222 |
| LOWVOL | -10.87% | -9.08% | -1.79% | (-5.54%, +4.92%) | 67 | 306 |
| Pooled | — | — | -3.07% | (-5.20%, +0.58%) | — | — |

MOM shows a significant tail difference in this specification, but the mean quintile sort points the other way and the subsample is unstable. This is exactly the kind of exploratory result that must be labelled and not used to rescue the hypothesis. The report currently omits E2 entirely.

### 5.6 Decision layer: quantile vs true ES and random ranks

| Factor | Strategy | 5% quantile | True ES5 | Mean exposure |
| :--- | :--- | ---: | ---: | ---: |
| MOM | static | -4.30% | -6.67% | 1.000 |
| MOM | vol-managed | -3.17% | -4.45% | 0.900 |
| MOM | fragility | -3.86% | -5.99% | 0.920 |
| STREV | static | -3.13% | -5.08% | 1.000 |
| STREV | vol-managed | -2.29% | -3.53% | 0.925 |
| STREV | fragility | -2.83% | -4.67% | 0.930 |
| LOWVOL | static | -3.15% | -4.23% | 1.000 |
| LOWVOL | vol-managed | -2.45% | -3.24% | 0.935 |
| LOWVOL | fragility | -2.92% | -4.02% | 0.942 |

**True ES difference, fragility minus vol-managed:**

| Factor | Difference | 95% CI |
| :--- | ---: | :--- |
| MOM | -1.49% | (-2.36%, -0.53%) |
| STREV | -1.10% | (-1.96%, -0.33%) |
| LOWVOL | -0.76% | (-1.31%, -0.23%) |

The qualitative conclusion survives and is stronger than the report's quantile version. The magnitudes are about twice as large. The report's `es_5` column is a quantile, not ES; the same label refers to two different statistics in one document.

**Random-overlay percentile ranks (true ES):**

| Factor | Actual ES5 | Random p05 | Random p50 | Random p95 | Rank |
| :--- | ---: | ---: | ---: | ---: | ---: |
| MOM | -5.99% | -6.60% | -6.34% | -5.96% | 0.94 |
| STREV | -4.67% | -5.03% | -4.90% | -4.59% | 0.87 |
| LOWVOL | -4.02% | -4.21% | -4.12% | -3.96% | 0.85 |

The overlay has better tail timing than 85-94% of random paths. The report's text says if the metric is inside the random range, the timing is indistinguishable. That is the wrong interpretation: the overlay is at the 94th, 87th, and 85th percentiles for MOM, STREV, and LOWVOL, respectively. The signal is not pure noise; it is simply weaker than volatility management. The README's corrected note says 74-98%, which is closer, but the generated report still has the old table and text.

**Overlay cost/borrow accounting:**

| Factor | Scaling cost (total) | Omitted borrow (total) | Mean exposure |
| :--- | ---: | ---: | ---: |
| MOM | 0.73% | 9.24% | 0.920 |
| STREV | 1.16% | 9.34% | 0.930 |
| LOWVOL | 0.58% | 9.47% | 0.942 |

The README claims the decision layer is "net of costs, cash, and borrow". The scaling cost is negligible; the borrow is omitted and is about 44bp/year, roughly an order of magnitude larger than the scaling cost. The relative comparison is probably unchanged (all comparators have similar exposure), but the absolute net returns are overstated. The factor's own rebalancing costs are omitted entirely.

### 5.7 Capacity sensitivity

**Execution horizon (cost-drag 100bp):**

| Horizon | LOWVOL | MOM | STREV |
| :--- | ---: | ---: | ---: |
| 1 day | $253m | $47m | $1m |
| 5 days | $1,266m | $233m | $4m |
| 10 days | $2,531m | $466m | $8m |
| 21 days | $5,315m | $979m | $16m |

**Turnover convention (cost-drag 100bp):**

| Factor | Code | Correct monthly drift | Weekly rebalance |
| :--- | ---: | ---: | ---: |
| MOM | $466m | $396m | $289m |
| STREV | $7.5m | $7.2m | $5.6m |
| LOWVOL | $2,531m | $2,075m | $1,272m |

**Premium-retention capacity (50% hurdle, MOM):**

| Assumed gross premium | Capacity |
| :--- | ---: |
| 2.00% | $84m |
| 5.15% (point estimate) | $2,340m |
| 13.53% (upper 95% CI) | $23,347m |

The point estimate is not robust. The capacity surface must show the premium dimension, not only c and spread.

### 5.8 Data and survivorship

| Quantity | Value |
| :--- | ---: |
| Panel rows × tickers | 5,282 × 895 |
| Sample | 2005-01-03 to 2025-12-30 |
| Tickers with last valid date before 2025-06-01 | 0 |
| Tickers with first valid date after 2005-02-01 | 271 |
| Names at end-2005 / end-2025 | 638 / 895 |
| Equal-weight panel CAGR | 18.14% |
| S&P 500 total-return CAGR | 10.80% |
| Candidate pool | current S&P 500 + S&P 400, 900 names |
| Candidate names with data | 895 |

The candidate pool is current index membership, sorted alphabetically and truncated at 900. It happens to include all 900 names in the current union, but if the union grows or `max_tickers` changes, the truncation is alphabetical, not liquidity-based. That is a latent selection bug.

The dollar-volume issue is not resolved. `Panel.dollar_volume = adjusted close × volume` is not a valid point-in-time dollar volume around splits and dividends. The validation function counts large price moves but does not test split invariance. The methodology claims a split/dividend check that is not implemented.

---

## 6. Inversion and falsification

### 6.1 What could make the project fundamentally fail?

1. **The data are survivor-only.** The factor premia and capacity levels are not market estimates. If the true premia are lower, retention capacity collapses quadratically. The project's headline capacity numbers could be off by an order of magnitude.
2. **The ADV is not dollar volume.** Split-adjusted close × raw volume biases universe inclusion and capacity. If the bias is large for high-priced stocks, the factor portfolios and capacity ordering change.
3. **The fragility index is not a crowding measure.** It measures the factor's own implied portfolio. If the mechanism is wrong, the null is uninformative about crowding. The project would be testing a proxy no practitioner uses.
4. **The factors are not beta-neutral.** The premia are partly market beta; after beta adjustment, none is significant. The capacity of a zero-alpha strategy is irrelevant.
5. **The study is underpowered.** The null is not evidence of absence. A true effect of 1% per SD would be missed. The conclusion must be "not detected at this resolution", not "does not predict".
6. **The specification was selected after inspecting results.** The p-values and CIs are not valid for a pre-registered test. A reviewer will discount them.
7. **The capacity model's assumptions dominate the level.** A 21x range in execution horizon and a 2x range in turnover convention make the point estimates model-dependent; the ordering is a turnover identity, not an empirical result.
8. **The code is not reproducible.** Untracked code, mutable data, no data hash. A reviewer cannot verify the claims.

### 6.2 What assumptions might be wrong?

- The square-root impact law and `c = 0.314`.
- The 10-day execution horizon and 10% participation.
- The 3bp spread and 50bp borrow.
- Monthly rebalancing with 8%/18% entry/exit bands.
- Equal weights for the four fragility measures.
- Ledoit-Wolf residual correlation as a crowding proxy.
- The equal-weight market as the market factor.
- The 4-week horizon as the relevant tail horizon.
- The 100bp cost-drag hurdle and 50% retention hurdle.
- The overlay's 0.3 floor and 0.6-0.9 schedule.
- Current index membership as a valid candidate pool.
- yfinance as a reliable, split-consistent data source.

### 6.3 What evidence would disprove the methodology or conclusions?

- A point-in-time dataset with delistings showing materially lower premia and capacity.
- A pre-registered holdout showing a negative fragility coefficient with a CI excluding zero, or an overlay beating volatility management.
- A multi-factor risk model showing that residual synchronization is sector/risk exposure, not crowding.
- An execution-calibrated capacity model showing a very different `c` or `D`.
- A beta-hedged factor showing zero alpha.
- A composite weighting that flips the sign (we found drop-breadth collapses it to zero; a different weighting could be significant).
- A non-overlapping subsample showing the MOM ES effect disappears.
- A trial ledger showing the final specification was selected from many; the p-values are not adjusted.
- A different data source showing the ADV/split issue materially changes the universe.

### 6.4 What would make the results unreliable, misleading, or unusable?

- Survivorship, split-adjusted ADV, mutable data, no data hash.
- In-sample premium, no CI, beta contamination.
- Bootstrap/controls/ES bugs.
- Composite dominated by one measure.
- H2 failure not reported.
- Overclaiming "pre-registered", "reproducible", "beta-neutral", "capacity".
- Absolute net returns not net of factor costs/borrow.
- Capacity point estimates without D/premium/turnover bands.

### 6.5 What would an experienced reviewer identify?

- **Quant researcher:** inference bugs, multiple testing, pre-registration, beta neutrality, composite construction, capacity model assumptions, missing E2/H2.
- **Portfolio manager:** the signal does not beat vol management; the capacity numbers are not investable; the factor premia are not significant; the strategy has no alpha.
- **Technical reviewer:** untracked code, no CI, no tests for the headline, no data hash, no lock file, doc-code drift, hardcoded paths, old V1 code.
- **Risk reviewer:** survivorship, data quality, model risk, tail dependence, liquidity assumptions, crowding proxy validity.

---

## 7. Value assessment

### 7.1 What is genuinely valuable

1. **The V1 forensic audit.** It is specific, reproducible, and teaches a real lesson about base-rate metrics and look-ahead. This is the project's strongest asset.
2. **The negative result on the overlay.** A fragility-based de-risking overlay is dominated by a simple volatility-managed portfolio on true ES at equal average exposure, across all three factors. This is practical and actionable.
3. **The H2 result.** The fragility composite is largely a volatility proxy. That is a more precise and useful finding than "no tail association".
4. **The capacity model as a template.** The square-root framework, the closed-form solver, the sensitivity grid, and the liquidation table are reusable. The numbers are not investable, but the method is.
5. **The engineering skeleton.** Config, manifest, CLI, invariants, leakage test, and modular design are a good foundation for a flagship.
6. **The candor.** The project states non-claims and limitations that most portfolio projects hide. That is a differentiator.

### 7.2 What is not valuable (or is actively misleading)

1. **The "fragility index" as a crowding signal.** It is not validated, dominated by breadth, correlated with volatility, and the composite null is not robust. It should be presented as a portfolio-characteristic diagnostic, not a crowding measure.
2. **The capacity point estimates.** $466m for MOM, $8m for STREV, $2.5bn for LOWVOL are model outputs conditional on assumptions that move them by 20x. They are not measurements and should not be presented as such.
3. **The "pre-registered" claim.** The final specification was not pre-registered. This is a credibility risk.
4. **The "four-measure composite" claim.** One measure is degenerate, two are collinear, and one drives the result. It is not a coherent four-factor construct.
5. **The "beta-neutral" claim.** The factors have significant realized market beta.
6. **The "reproducible" claim.** The code is untracked and the data are mutable.

### 7.3 Who would use it?

- A quant researcher or PM evaluating crowding proxies: yes, as a cautionary case study and a volatility-control benchmark.
- A risk team looking for a capacity-model template: yes, with better data and calibrated assumptions.
- An allocator looking for a capacity number: no. The numbers are not investable.
- A journal referee: no, not without PIT data, a holdout, a trial ledger, and external benchmarks.

### 7.4 Defensible claims after the fixes

- "We audited a failed V1 and showed its 0.9483 F1 is the base rate of a constant predictor."
- "A price-based fragility composite does not add left-tail information beyond volatility in large US equities, 2005-2025. The raw association is largely a volatility proxy; H2 fails."
- "A fragility overlay is dominated by volatility management on true ES at equal average exposure."
- "Under a square-root impact model, cost-drag AUM is highly sensitive to execution horizon, turnover convention, and impact calibration; the ordering follows turnover by construction."
- "Capacity levels are model outputs, not measurements; the data are survivor-only."
- "The factors are dollar-neutral but not beta-neutral; realized CAPM alphas are not significant."

### 7.5 Claims that are not defensible

- "Capacity is $466m for MOM" as a fact.
- "Fragility predicts the left tail" (not supported).
- "Beta-neutral factors" (false).
- "Pre-registered" (not for the final specification).
- "Reproducible" (code untracked, data mutable).
- "Four-measure composite" (one degenerate, one dominant).

---

## 8. Completion criteria

### 8.1 Tier A: flagship portfolio project (current data, ~2-3 weeks)

This is the right target. It does not require CRSP data. It requires the project to be honest, reproducible, tested, and well-presented.

**A1. Repository and release**
- `git status --porcelain` is empty; all V2 code, tests, configs, docs, and figures are tracked.
- `git tag v2.0.0` points at the release commit; the manifest's `git_commit` equals `git rev-parse HEAD`.
- A fresh clone runs `pip install -e ".[dev]"`, `pytest -q`, and `python -m fcr all --config configs/v2.json`.
- `LICENSE` (MIT) exists; a CI workflow runs tests and lint on push.
- Dependencies are pinned in a lock file; `configs/v2.json` contains the full config.
- V1 code is moved to `archive/v1/` with a `SUPERSEDED` banner; the main tree contains only V2.
- No hardcoded absolute paths.

**A2. Reproducibility**
- The manifest records a SHA256 of the panel, the git commit (clean tree), package versions, seeds, and stage timings.
- The run directory contains all tables and figures for that run, not just the manifest.
- A second run from the same frozen data produces identical tables (hash match).
- A `docs/data_availability.md` states what is cached, what is not committed, and how to obtain it.

**A3. Inference correctness**
- The bootstrap retains duplicates; a test asserts the resample length equals `n`, duplicates are present, and the SE matches a reference.
- Controls are lagged; the target starts at `t`; a truncation test covers the controls.
- True expected shortfall is used everywhere; the label `es_5` is defined once.
- Secondary p-values are centered; the FDR family is stated.
- MDE is computed from the corrected bootstrap and reported next to every null.
- H2 and E2 are reported; H3 matches the protocol; H4 is removed as a hypothesis.
- `n_dates`, `n_blocks`, and `n_factors` are reported, not just rows.

**A4. Robustness**
- Composite variants: equal, drop-one, rank-average, PCA; per-measure results.
- Quintile sort and subsample table in the report.
- Non-overlapping subsample check.
- Placebo p-value/percentile.
- ES by quintile with a confidence interval.
- Factor alpha/beta table.
- Capacity sensitivity: execution horizon, turnover convention, impact coefficient, spread, borrow, premium.
- Break-even premium table.

**A5. Data integrity**
- Unadjusted close stored or volume adjusted; split-invariance test.
- Empty responses are not cached; excluded tickers are logged.
- Candidate pool selection documented; no alphabetical truncation.
- Survivorship table (0 delistings, 18.14% vs 10.80%) in the same section as the capacity table.
- The words "residual survivorship" are removed.

**A6. Tests and QA**
- Tests for `study`, `decision`, `overlay`, `backtest`, `targets`, `data`, `report`, `pipeline`.
- Leakage tests for controls and the decision layer.
- ES definition, comparator exposure match, capacity solver, bootstrap duplicates.
- End-to-end smoke test.
- CI green; coverage reported; no test encodes a bug.

**A7. Documentation**
- `docs/report.md` is regenerated from the fixed code and is the single source of truth.
- README numbers are generated or checked by `scripts/check_docs.py`.
- `docs/methodology.md` and `problem_framing.md` match the code; stale claims removed.
- `docs/trial_ledger.md` lists every specification tried.
- A "researcher degrees of freedom" section is in the report.
- The study is labelled exploratory, or a genuine holdout is added.
- `docs/data_dictionary.md` and a model card exist.
- The archive has a banner and correct encoding.

**A8. Practical value**
- A two-page decision memo for a PM/allocator: what the project measures, what it found, what it does not claim, how to use the capacity surface, and what would change the conclusion.
- The memo must say: no investable crowding signal; capacity is a model output; the overlay loses to vol management; H2 fails.
- A "what would change the conclusion" section in the report.

**A9. Release**
- Public GitHub repo with a compelling README, figures, license, and citation.
- A one-command demo that runs on a small synthetic fixture (no network).
- No secrets, no data files in git history, no large binaries.

### 8.2 Tier B: publishable paper (months)

- B1. Point-in-time data with delistings (CRSP/Compustat or equivalent).
- B2. Pre-registered final specification on a genuine holdout.
- B3. Trial ledger and multiple-testing correction across the full search.
- B4. External crowding benchmarks: Cahan-Luo, Kinlaw-Kritzman, liquidity-squeeze.
- B5. Multi-factor risk model for residual synchronization; sector neutrality.
- B6. Execution-calibrated capacity model; out-of-sample validation against fund AUM/flows.
- B7. Independent replication and referee-grade writing.

Tier B is a different, larger project. Do not let it block Tier A.

---

## 9. Prioritized roadmap

### P0: release blockers (must fix before public release)

| # | Item | Why | Effort |
| :-: | :--- | :--- | :--- |
| P0-A | Commit V2, archive V1 code, clean tree, tag | A fresh clone is currently V1; the manifest commit is misleading | 1-2 h |
| P0-B | Fix bootstrap duplicates, lag controls, align target, true ES, centered p | Every interval and p-value is currently wrong | 1-2 d |
| P0-C | Regenerate report and README from one code path | Docs describe a study the code does not run | 0.5 d |
| P0-D | Survivorship disclosure + split-adjusted ADV + data hash | Capacity and premia are biased; data are not reproducible | 1 d |
| P0-E | Reframe capacity: model output, D/premium/turnover sensitivity, no H4 | The headline is not robust; the ordering is an identity | 1 d |
| P0-F | Add H2, E2, quintile sort, subsample, composite robustness to report | The strongest evidence is missing or contradicts the narrative | 1 d |
| P0-G | Add tests for headline modules; replace the subset test; CI | The headline is unprotected; a test encodes the bug | 1-2 d |
| P0-H | LICENSE, lock file, archive banner, empty-cache fix, hardcoded path | Table stakes for a public flagship | 0.5 d |
| P0-I | Make README numbers generated/checked; update methodology/framing | Doc-code drift is the project's central credibility risk | 0.5 d |

Do P0-A first. It protects the work and takes an hour. Nothing else on this list matters if the code is not in the repository.

### P1: flagship quality (high value, not strictly release-blocking)

| # | Item | Why | Effort |
| :-: | :--- | :--- | :--- |
| P1-A | Composite weight sensitivity (drop-one, rank, PCA) and per-measure table | The null is not robust to weighting; breadth drives it | 1 d |
| P1-B | Beta/alpha table; enforce beta neutrality or disclose; capacity on alpha | The factors are not beta-neutral; premia are not significant | 1 d |
| P1-C | Trial ledger + researcher degrees of freedom + exploratory label/holdout | The "pre-registered" claim is not true | 0.5 d |
| P1-D | Non-overlapping subsample, placebo p-values, ES by quintile with CI | Promised but missing | 1 d |
| P1-E | Data dictionary, model card, decision memo | Makes the project usable and reviewable | 1 d |
| P1-F | Figure polish: sample periods, grayscale, consistent labels | Methodology promises this | 0.5 d |
| P1-G | External crowding benchmark or a clear "not attempted" statement | Positions the contribution | 2-3 d |

### P2: optional / paper

| # | Item | Why | Effort |
| :-: | :--- | :--- | :--- |
| P2-A | Point-in-time data with delistings | The only way to make capacity/premia investable | Weeks |
| P2-B | Genuine holdout / pre-registration | The only way to make the inference confirmatory | Weeks |
| P2-C | Execution-calibrated impact model | The only way to make capacity a measurement | Weeks |
| P2-D | External benchmarks and horse race | The only way to claim a better crowding measure | Weeks |
| P2-E | Paper/PDF, DOI, citation | Publication | Weeks |

### What not to do

- Do not add more factors, markets, or machine-learning models before the core is fixed. The sample cannot support them, and the failure mode is V1 again.
- Do not tweak the composite until it becomes significant. That is HARKing and would destroy the project's credibility.
- Do not present capacity as a measurement or an investable estimate.
- Do not add a complex risk model without data to calibrate it.
- Do not spend time on visual polish before the numbers are correct.

---

## 10. Appendix: reproduction notes

The independent checks in this audit were run from the cached panel with:

```text
python outputs/audit/diag_core.py          # factor, fragility, capacity, splits
python outputs/audit/diag_study2.py        # corrected bootstrap, alignment, per-factor, quintile, subsample
python outputs/audit/diag_decision.py      # true ES, random ranks, secondary centered p
python outputs/audit/diag_es.py            # E2 ES quintiles
python outputs/audit/diag_extra.py         # H2, composite variants, alpha/beta, turnover
python outputs/audit/diag_h2.py            # H2 under both specs
python outputs/audit/diag_premium.py       # gross premium CI and capacity vs premium
python outputs/audit/diag_beta_sp.py       # CAPM betas vs S&P 500
python outputs/audit/diag_turnover2.py     # turnover convention and capacity
```

These scripts live under `outputs/audit/`, which is gitignored. They are working evidence, not part of the release. If the project wants the audit to be reproducible, promote the useful ones to `scripts/audit/` and commit them.

Key files reviewed:

- `README.md`, `TODO.md`, `DECISIONS.md`, `problem_framing.md`
- `docs/audit_v1.md`, `docs/methodology.md`, `docs/roadmap.md`, `docs/report.md`, `docs/red_team_review.md`
- `src/fcr/*.py`, `tests/*.py`, `configs/v2.json`
- `outputs/tables/*.csv`, `outputs/runs/*/manifest.json`, `data/panel/*.parquet`

The audit does not claim external independence. An external quant reviewer should still be commissioned before publication. The findings above are reproducible from the cached data and the project's own functions; that is the standard this audit holds the project to.

---

*Nothing in this document is investment advice. The capacity numbers are model outputs, not measurements, and the fragility index is a proxy, not a crowding measure.*
