# Decision Record

Material decisions for this repository, with the options considered, the expected outcome,
the assumptions, and the conditions under which the decision should be reversed.

---

## ADR-0001: Reframe from return prediction to exit risk and capacity

**Date:** 2026-11-16
**Status:** Accepted
**Supersedes:** the V1 problem framing

### Context

V1 asked whether a crowding score predicts the future decay of a factor's information
coefficient. The audit (`docs/audit_v1.md`) found three independent fatal defects: the two
factors are the same portfolio with opposite sign, the headline F1 is the label base rate,
and features and targets contain look-ahead. Beyond the defects, the question itself is
weakly identifiable with public price data and has low statistical power.

### Options

| Option | Description | Expected outcome | Why rejected or chosen |
| :--- | :--- | :--- | :--- |
| A | Repair V1 in place: fix leakage, add costs, keep the question | A defensible but still low-power study of a confounded proxy | Rejected. Fixes symptoms while keeping an unanswerable question and a degenerate factor set |
| B | Deepen the prediction question: better proxies, longer sample, ML | Marginal improvement in a noisy target, high overfitting risk | Rejected. Power analysis shows effects below the detection threshold; the decision value is unchanged |
| C | Replace the target with measurable exit risk and capacity | Two measurable constructs, a decision-relevant output, and a deliverable that survives a null | **Chosen** |

### Decision

V2 measures liquidity-adjusted fragility and capacity of three price-based equity factors,
and tests whether fragility adds information about the left tail beyond volatility. The
primary estimand is a quantile regression coefficient at `τ = 0.10` on four-week forward
returns. The decision layer is benchmarked against a volatility-managed control at equal
average exposure.

### Expected outcome

- A capacity report with a sensitivity band that is useful independent of the empirical
  result (high confidence).
- A fragility index with a documented mechanism and no look-ahead (high confidence).
- A tail-risk association that may or may not be detectable (genuinely uncertain).

### Assumptions

1. Liquidity and turnover are measurable from price and volume at acceptable accuracy.
2. The square-root impact law is a reasonable approximation for large US equities, with
   the coefficient uncertain by a factor of about two.
3. Fragility, if it matters, acts on the tail rather than the mean, so a tail estimand has
   more power than a mean-return forecast.
4. A careful null is a publishable result for a portfolio project.

### Consequences

Positive: the project has a guaranteed deliverable, a pre-registered test, and an honest
failure mode. It demonstrates measurement design, inference discipline, and software
engineering rather than a lucky backtest.

Negative: more engineering than V1. The capacity numbers are model estimates, not
measurements, and must always be shown with a band. Three factors limit generality.

### Review date

After Phase 3 (statistics). Review again before publication.

### Kill criteria

Reverse the decision, and fall back to option A or to a pure capacity study, if:

1. The V1 reproduction does not confirm the audit's arithmetic, invalidating the premise.
2. Fragility cannot be computed without leakage on more than 10% of dates.
3. The capacity model produces non-monotone or implausible curves that cannot be fixed by
   changing only the calibration.
4. Two of the three factors fail the factor invariants and cannot be repaired.

If the empirical tail test fails, the decision is **not** reversed. A null is an outcome,
and D1 and D4 remain.

---

## ADR-0002: Three price-based factors, and no value factor

**Date:** 2026-11-16
**Status:** Accepted

### Context

V1 labelled an inverse-momentum portfolio as "value", then reported that value was the
stronger factor. The label was wrong and the comparison was degenerate because the value
series was exactly minus momentum.

### Decision

Use `MOM`, `STREV`, and `LOWVOL`. Do not claim a value factor. Value requires book equity
or earnings, neither of which is available in this data source.

### Rationale

The three factors are economically distinct, have very different turnover and liquidity
profiles, and therefore produce a meaningful capacity ordering. That ordering is the basis
of hypothesis H4 and of the capacity report.

### Consequences

The project cannot speak to value or quality crowding. This is stated in the scope table.
Anyone wanting value must add fundamentals and re-derive the factor construction.

### Kill criteria

If the three factor return series fail the non-collinearity invariant (`|corr| < 0.9`) and
cannot be separated by construction changes, replace the factor set before continuing.

---

## ADR-0003: Quantile regression on the left tail as the primary estimand

**Date:** 2026-11-16
**Status:** Accepted

### Context

V1 used classification of the sign of forward returns, which produced a base-rate artefact
and discarded the magnitude of losses. Mean-return prediction is the standard alternative,
but the economic mechanism (a crowded exit) is a tail event, and mean effects are diluted
by the many periods in which nothing happens.

### Decision

Primary: `τ = 0.10` quantile regression of four-week forward factor returns on the
fragility composite, pooled with factor fixed effects and volatility controls. Secondary:
expected shortfall differences and the `τ = 0.05` quantile, labelled exploratory.

### Rationale

The mechanism predicts asymmetry. A quantile estimand targets the part of the distribution
where the mechanism operates, avoids the base-rate problem entirely, and has a stated
minimum detectable effect. Reporting `β_0.50` alongside `β_0.10` tests whether the measure
is merely a repackaged drift or volatility signal.

### Consequences

Quantile regression standard errors are unreliable under autocorrelation, so inference
uses a stationary bootstrap. Results are less familiar to a general audience and require
clear exposition.

### Kill criteria

If `β_0.10` and `β_0.50` are statistically indistinguishable, the tail-specific claim is
withdrawn and the result is reported as a level effect, if any.

---

## ADR-0004: Volatility-managed portfolio as the mandatory comparator

**Date:** 2026-11-16
**Status:** Accepted

### Context

Any overlay that reduces exposure in turbulent periods will improve drawdowns relative to
a fully invested portfolio, regardless of whether crowding is measured. Moreira and Muir
(2017) document this effect across factors.

### Decision

The fragility overlay must beat a volatility-managed portfolio with the **same average
exposure** and the same cost model. Beating the static portfolio is necessary but not
sufficient.

### Rationale

Without this control, the project would repeat V1's error in a more sophisticated form:
attributing a de-risking benefit to a crowding signal.

### Consequences

The overlay may fail. That is an acceptable and informative outcome, and it is stated in
advance so that it cannot be reinterpreted after the fact.

### Kill criteria

Not applicable. This decision is a control, not a hypothesis.

---

## ADR-0005: Neutralize beta in signal space, not weight space

**Date:** 2026-11-16
**Status:** Accepted
**Amends:** `docs/methodology.md` Section 2.2 and 2.4

### Context

The methodology originally specified beta neutralization by subtracting `kβ` from the
weight vector. That produces small positions across the entire universe, which raises
turnover, inflates trading costs, and breaks the interpretation of the long and short
legs that the fragility measures rely on.

### Decision

Residualize the factor *signal* cross-sectionally on `[1, beta]`, then form decile
portfolios from the residual. Report ex-post portfolio beta as a diagnostic with a mean
absolute value below 0.25. Do not assert exact zero.

### Consequences

Portfolios remain dollar-neutral, cap-compliant, and interpretable as decile spreads.
Residual beta is small but nonzero and is disclosed. Capacity estimates are not inflated
by hedging trades in hundreds of names.

### Kill criteria

If mean absolute ex-post beta exceeds 0.25, revisit the signal construction. If it
exceeds 0.50, the factor is not sufficiently beta-neutral to support the fragility
interpretation and must be rebuilt.

---

## ADR-0006: Impact scales with traded notional, not held notional

**Date:** 2026-11-16
**Status:** Accepted
**Amends:** `docs/methodology.md` Section 4.1

### Context

The capacity cost formula originally set `Q_i = |w_i| · A`, the held position. That is
the right quantity for asking "what does it cost to exit this position once", but the
wrong quantity for a rebalancing cost, which is incurred on the *change* in position each
week.

### Decision

The capacity curve uses traded notional `D_i = |Δw_i| · A`, so weekly impact depends on
turnover. A separate liquidation table uses held notional `|w_i| · A` and answers the exit
question.

### Consequences

The two numbers answer different questions and are reported separately. Capacity is
driven mainly by turnover, which is the economically correct driver: a high-turnover
factor exhausts capacity at a smaller size. Liquidation cost is driven by position size
and liquidity and is reported as a distinct diagnostic.

### Kill criteria

If capacity does not fall with turnover across the three factors, the cost model is
mis-specified and must be reviewed before any capacity number is published.

---

## ADR-0007: Construction refinements discovered during implementation

**Date:** 2026-11-16
**Status:** Accepted
**Amends:** `docs/methodology.md` Sections 2.2, 4.1, 4.3, 7.3

### Context

Implementation exposed four issues that the framing could not have known about. Each is
recorded rather than silently fixed.

1. **Weekly rebalancing of a 12-1 signal produced implausible turnover.** A decile
   portfolio re-sorted weekly turns over roughly 30 times its book per year. Capacity
   estimates collapsed to the lower bound, which was a signal about the construction, not
   about the market.
2. **Monthly rebalancing alone still churned at the decile boundary.** Twenty-six percent
   of long-leg names changed each month from rank noise near the cutoff.
3. **Charging square-root impact with one-day execution made capacity implausibly small.**
   Real rebalances are worked over days.
4. **Retention-based capacity is undefined for a factor with no premium.** Low volatility
   has no gross premium in this sample, so a premium-retention hurdle cannot be solved.

### Decision

1. Holdings rebalance monthly; observation and the exposure overlay remain weekly.
2. Entry and exit bands (8% and 18% rank thresholds) control boundary churn.
3. The impact model uses a ten-day execution horizon; participation is
   `Q / (ADV * execution_days)`.
4. Headline capacity is the premium-independent cost-drag definition, `A_cost(100bp)`.
   Retention-based capacity is reported alongside and marked undefined where the gross
   premium is non-positive.

### Consequences

Turnover falls to a plausible range (weekly gross 0.08 to 0.70 across the three factors),
capacity lands between $8m and $2.5bn at 100bp, and the H4 ordering is testable for all
three factors. Fragility measures are computed on a portfolio that changes monthly, so
persistence now counts monthly rebalances rather than weekly dates.

### Kill criteria

If the cost-drag ordering does not follow turnover, or if any factor's capacity exceeds
the total daily dollar volume of its holdings, the model is mis-specified and must be
reviewed before publication.



## ADR-0008: Correct inference before reporting any result

**Date:** 2026-11-18
**Status:** Accepted
**Amends:** `docs/methodology.md` Sections 5, 6, 7; `docs/audit_v2_independent.md`

### Context

The pre-fix version collapsed bootstrap duplicates with `np.isin`, used controls
that included the week after the decision date, labelled a 5% quantile as
expected shortfall, and used a non-centered bootstrap p-value. The README
described corrected numbers that the pipeline did not produce.

### Decision

1. The bootstrap resamples rows with replacement. A resample has length `n` and
   about 63% unique dates; that is correct. The test asserts the length and the
   presence of duplicates, not a unique fraction near one.
2. Controls are reindexed to the factor calendar and lagged one week. The target
   starts at the decision date: `cum[t+h-1] / cum[t-1] - 1`.
3. Expected shortfall is the mean of the tail, everywhere.
4. Secondary p-values use the centered bootstrap distribution.
5. Every interval and MDE is regenerated from the corrected path.

### Consequences

The primary estimate is -0.98% per SD (95% CI -2.19% to +0.27%) with an MDE of
1.69%. The null verdict is unchanged. The reported interval is wider and the
result is correctly labelled exploratory.

### Kill criteria

If a corrected run changes the sign or significance of a headline claim, the
claim is withdrawn. It is not rescued by choosing a different specification.

---

## ADR-0009: Monthly buy-and-hold returns and full-period capacity drift

**Date:** 2026-11-18
**Status:** Accepted
**Amends:** `docs/methodology.md` Section 4

### Context

The backtest held target weights constant every week while the capacity model
assumed monthly rebalancing. The return series was therefore a weekly-rebalanced
portfolio, and the capacity model applied only one week of weight drift at each
monthly rebalance. Both understated turnover relative to the stated construction.

### Decision

1. Factor returns are monthly buy-and-hold: weights drift with stock returns
   between rebalances, then reset.
2. Capacity trades use the full-period drift from the previous rebalance.
3. The same convention is used in the reported turnover and the capacity curve.

### Consequences

Annualized turnover changes by roughly 10-20%. At a 100bp cost-drag hurdle and a
10-day execution horizon, cost-drag capacity is LOWVOL $2.07B, MOM $395M, and
STREV $7M. The ordering remains a turnover identity.

### Kill criteria

If the buy-and-hold and capacity conventions diverge again, the capacity numbers
are withdrawn until they are reconciled.

---

## ADR-0010: Capacity is a surface, not a point estimate

**Date:** 2026-11-18
**Status:** Accepted
**Amends:** `docs/methodology.md` Section 4.4; `docs/report.md` Section 6

### Context

The published capacity number moved by 21x with the execution horizon, by about
2x with the turnover convention, and by orders of magnitude with the assumed
premium. The retention capacity is undefined for LOWVOL because its gross
premium is negative.

### Decision

Report cost-drag capacity as a surface across execution horizon, impact
coefficient, spread, and assumed premium. Report gross premium and alpha with
HAC intervals. Mark retention capacity `n/a` when gross premium is non-positive.
Remove H4 as a hypothesis; report the ordering as a turnover identity.

### Consequences

The capacity section is longer but honest. The headline is a range, not a point.
A reader can see exactly which assumption drives the number.

### Kill criteria

The capacity model is not a measurement. If a reader uses it as one, the framing
has failed and must be revised again.
