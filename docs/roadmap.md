# Roadmap: Version 2

**Status:** portfolio-release complete. Core implementation, tests, generated
report, and README are current. The remaining work is data and paper-level:
point-in-time delistings, a genuine holdout, and an execution-calibrated impact
model. See `TODO.md`.

**Successor to:** V1, which produced invalid conclusions (`docs/audit_v1.md`).

---

## 1. What V2 must deliver

Four artifacts. Each stands alone if the others fail.

| # | Artifact | Audience | Why it matters |
| :-: | :--- | :--- | :--- |
| D1 | **Capacity report**: net premium and maximum AUM per factor, with a sensitivity band | Allocator, PM, risk | Answers "how much can this strategy hold" with a defensible number |
| D2 | **Fragility index**: four-measure composite, standardized without look-ahead, with a documented mechanism | Quant researcher | A reusable measure of exit risk, not a black box |
| D3 | **Tail-risk study**: does fragility predict the left tail beyond volatility, with power stated | Research | The empirical claim, honestly bounded |
| D4 | **Tested package**: leakage tests, invariant tests, one-command reproduction | Engineer | Proof that the numbers are not artefacts |

D1 and D4 do not depend on D3 succeeding. That is the point.

## 2. Phases

### Phase 0. Framing and audit (complete)

- [x] Read every V1 file and trace every reported number to its source.
- [x] Grade defects and record the audit (`docs/audit_v1.md`).
- [x] Reframe the problem (`problem_framing.md`).
- [x] Specify the method (`docs/methodology.md`).
- [x] Record the decision and its kill criteria (`DECISIONS.md`).
- [x] Archive V1 without deleting it (`docs/archive/v1/`).

### Phase 1. Foundations and the reproduction test

- [x] Package skeleton, config, manifest, CLI.
- [x] Data layer: download, cache, validate, snapshot.
- [x] Point-in-time universe.
- [x] Factor construction with invariant assertions.
- [x] **V1 reproduction harness**: confirm the factor sign identity and the F1 base rate.
      This is a gate. If the audit's arithmetic does not reproduce, stop and revise.

Exit criterion: `pytest tests/test_factors.py tests/test_leakage.py` passes, and the
reproduction report is written.

### Phase 2. Fragility and capacity

- [x] F1 to F4 with expanding standardization.
- [x] Leakage test suite, including truncation invariance.
- [x] Capacity model, monotonicity test, sensitivity band.
- [x] Capacity table and curves (D1).

Exit criterion: capacity is monotone in AUM, the sensitivity band is plausible, and the
capacity ordering across factors matches or contradicts H4 with a stated reason.

### Phase 3. Statistical study

- [x] Targets, quantile regression, stationary bootstrap, BH, MDE.
- [x] Primary estimate with controls and factor fixed effects.
- [x] Placebo block-shuffle, quintile sort, and subsample stability.
- [x] H2 attenuation and E2 expected-shortfall difference.

Exit criterion: E1 is estimated with an interval and an MDE; the pre-registered decision
rule in `problem_framing.md` Section 5 is applied mechanically.

### Phase 4. Decision layer

- [x] Overlay and four comparators, exposure-matched.
- [x] Cost model in the backtest, cash and borrow returns.
- [x] Tail metrics with bootstrap intervals.
- [x] Turnover and cost-drag counter-metrics.
Exit criterion: the overlay is compared against C1 (volatility-managed) at equal average
exposure, and the result is stated in either direction.

### Phase 5. Communication

- [x] Generated report (`docs/report.md`).
- [x] Six figures.
- [x] README rewritten to match the report, claim for claim.
- [x] `outputs/` reproducible from a manifest.

Exit criterion: no README sentence asserts something the report does not show.

---

## 3. Milestones and effort

| Milestone | Depends on | Estimate | Gate |
| :--- | :--- | :--- | :--- |
| M0 Framing | none | done | This document set |
| M1 Data and factors | M0 | 1 session | Invariants pass |
| M2 Reproduction | M1 | 0.5 session | Audit confirmed or revised |
| M3 Fragility | M1 | 1 session | Truncation invariance passes |
| M4 Capacity | M1, M3 | 1 session | Monotone curves, plausible magnitudes |
| M5 Statistics | M3, M4 | 1.5 sessions | Primary estimate + MDE |
| M6 Decision layer | M5 | 1 session | Four comparators, costs |
| M7 Report | all | 1 session | Generated, consistent |

Estimates assume cached data. The first download of 20 years of daily data for a broad
candidate pool is the main wall-clock cost and is cached thereafter.

## 4. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| `yfinance` rate limits or gaps | Medium | Blocks data | Cache by ticker-year; retry with backoff; fall back to a narrower candidate pool and document it |
| Survivorship dominates results | High | Inflates premium and capacity | Disclose; report pre-2010 vs post-2010; compare universe size over time |
| Fragility has no tail signal | Medium-high | D3 fails | D1 and D4 still deliver; report the MDE, not a null claim |
| Impact coefficient badly calibrated | High | Capacity numbers wrong | Sensitivity band is mandatory; present a range, never a point |
| Tail tests underpowered | Certain | Weak inference | Primary at `τ=0.10`, `τ=0.05` labelled exploratory, MDE published |
| Overlay is just volatility timing | Medium | H3 fails | C1 is the primary comparator; a loss is a finding, not a bug |
| Scope creep into fundamentals | Medium | Loses time, breaks reproducibility | Explicitly out of scope in `problem_framing.md` Section 9 |

## 5. Non-goals for V2

- A value or quality factor. No fundamental data.
- Live trading, execution algorithms, or a production risk system.
- Causal identification of crowding.
- Deep learning. Three factors and roughly 1,000 weekly observations do not support it,
  and the failure mode (overfitting an already noisy target) is the one V1 already
  demonstrated.
- Beating a benchmark. This is a measurement project.

## 6. Definition of done

V2 ships when:

1. `pytest` passes, including leakage and invariant tests.
2. The V1 reproduction is recorded.
3. The capacity table exists with a sensitivity band.
4. The primary estimate exists with an interval and an MDE.
5. The overlay comparison exists against all four comparators.
6. The report is generated and the README matches it.
7. Every claim in the README is traceable to a table or figure in the report.

If item 4 yields a null, item 1 through 3 and 5 through 7 are still required. The project
is designed so that an honest null is a complete result.

---

*Phase 0 is complete. Implementation proceeds in the order above.*
