# TODO: Version 2.1

**Status:** portfolio-release complete. The code, tests, figures, and generated
report are in the repository. The remaining gaps are data limitations and
paper-level work, not unfinished implementation.

**Framing:** `problem_framing.md`. **Results:** `docs/report.md`.
**Audit trail:** `docs/audit_v1.md`, `docs/audit_v2_independent.md`.
**Trial ledger:** `docs/trial_ledger.md`.

---

## Release gates

| Gate | Question | Pass condition | Status |
| :--- | :--- | :--- | :--- |
| G1 Reproduction | Does the V1 audit's arithmetic reproduce? | Factor correlation is -1.0 to 1e-9; base-rate mechanism confirmed | **Pass** (correlation -1.0000) |
| G2 Leakage | Do features and controls change when the future is deleted? | Truncation test max abs diff < 1e-10 | **Pass** (fragility and controls) |
| G3 Invariants | Are the portfolios what they claim to be? | Dollar-neutral, gross 2.0, cap, beta diagnostic, non-collinear | **Pass** |
| G4 Monotonicity | Is cost increasing in size? | Net premium non-increasing in AUM | **Pass** |
| G5 Inference | Is the uncertainty reported? | Every estimate has an interval; every null has an MDE | **Pass** |
| G6 Consistency | Does the README match the report? | Every README claim traces to a table or figure | **Pass** |

## P0 release blockers (closed)

- [x] P0-1 Add `LICENSE` (MIT)
- [x] P0-2 Add CI running `pytest` on push
- [x] P0-3 Replace the decision-layer `es_5` quantile with true expected shortfall
- [x] P0-4 Add the survivorship disclosure (0 delistings; EW CAGR 18.14%)
- [x] P0-5 Reframe capacity as a model output; remove H4 as a hypothesis test
- [x] P0-6 Add subsample and quintile-sort tables; downgrade the momentum claim
- [x] P0-7 Banner the archived V1 README and PDF as superseded
- [x] P0-8 Fix `_fetch_one` so transient empty responses are not cached permanently
- [x] P0-9 Pin dependencies and freeze the full config
- [x] P0-10 Replace the secondary bootstrap p-value with the centered version
- [x] P0-11 Add tests for `study`, `decision`, `overlay`, `backtest`, `targets`
- [x] P0-12 Narrow the "no look-ahead enforced mechanically" claim
- [x] P0-13 Fix the bootstrap to retain duplicates
- [x] P0-14 Lag the controls and align the target to start at `t`
- [x] P0-15 Add the execution horizon to the capacity sensitivity grid
- [x] P0-16 Report random-overlay percentile ranks
- [x] P0-17 Update the headline CI and MDE from the corrected pipeline
- [x] P0-18 Add tests for `study`, `decision`, `overlay`, `backtest`, `targets`

## P1 flagship-quality work (closed)

- [x] H2 volatility-attenuation table in the report
- [x] E2 expected-shortfall difference with a confidence interval
- [x] Composite sensitivity: equal, drop-one, rank-average
- [x] Realized CAPM beta/alpha table
- [x] Premium-retention capacity as a function of the assumed premium
- [x] Data SHA256 in the manifest and `data/panel/metadata.json`
- [x] Trial ledger and researcher-degrees-of-freedom section
- [x] Data dictionary and model card
- [x] Archive banner and PDF notice
- [x] 40 tests, CI workflow, exact dependency pins

## Remaining work (not release blockers)

- [ ] Point-in-time dataset with delistings (CRSP or equivalent)
- [ ] Pre-registered holdout on a future period
- [ ] Execution-calibrated impact coefficient and horizon
- [ ] External crowding benchmarks: Cahan-Luo, Kinlaw-Kritzman, liquidity squeeze
- [ ] Multi-factor risk model for residual synchronization
- [ ] Vectorized bootstrap or joblib parallelization for faster full runs
- [ ] Split-invariance test for dollar volume (adjusted close × volume)

---

## Results (final run)

| Item | Value |
| :--- | :--- |
| Sample | 2005-01-03 to 2025-12-30, 5,282 days, 895 tickers |
| Universe | 1,045 weekly dates, mean size 498 |
| Factor rows in study | 2,780 |
| Primary `beta_0.10` | -0.98% per SD (95% CI -2.19% to +0.27%) |
| `beta_0.50` | +0.23% (CI -0.39% to +1.00%) |
| MDE | 1.69% of four-week return per SD |
| H1 (tail association) | Not detected |
| H2 (association survives controls) | **Fail** (retention 0.41) |
| H3 (overlay beats volatility management) | **Fail**, all three factors |
| Capacity ordering | Turnover identity; not a hypothesis |
| Cost-drag capacity at 100bp / 10 days | LOWVOL $2.07B, MOM $395M, STREV $7M |

## Known traps from V1

Kept as a permanent checklist.

| Trap | Symptom | Guard |
| :--- | :--- | :--- |
| Degenerate factor pair | `corr(r1, r2) = -1` | Invariant test |
| Base-rate metric | F1 high while the rare class is never predicted | Constant-predictor benchmark |
| Overlapping labels | Test rows share outcome windows | Block bootstrap; block count reported |
| Full-sample scaling | Feature at `t` changes when the future is deleted | Truncation test |
| Controls use post-decision data | Control at `t` includes `r_t` | Lagged-control truncation test |
| Price-level features | A "valuation" measure that is a share price difference | Units check; no feature without a mechanism |
| De-risking passed off as skill | Overlay wins only against a fully invested portfolio | Volatility-matched comparator |
| Best-of reporting | The maximum of hundreds of fits presented as a finding | Trial ledger; exploratory label |
| Doc drift | README, report, and code disagree | Generated report; G6 |
