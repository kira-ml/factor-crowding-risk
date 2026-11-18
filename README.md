# Crowded Exits

**Exit risk and capital capacity in equity factors.**

![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-v2.1%20portfolio--ready-blue)

A leakage-audited study of momentum, short-term reversal, and low volatility in
US equities, 2005-2025, with a point-in-time liquidity universe and a disclosed
survivor-only sample. The project measures the exit risk and capital capacity of
factor portfolios, tests whether a price-based fragility proxy adds information
about the left tail beyond volatility, and reports what the data support -
including a negative result.

The short version: **the fragility proxy does not beat volatility management,
and the capacity numbers are model outputs, not measurements.** The value of the
project is the measurement framework, the forensic audit of a failed predecessor,
and a credible negative result that saves a practitioner from building the wrong
overlay.

---

## Why this repository exists

Version 1 asked whether crowding predicts the decay of a factor's information
coefficient. It reported an F1 of **0.9483** and a Sharpe improvement of
**+0.0182**.

Those numbers do not survive inspection. [`docs/audit_v1.md`](docs/audit_v1.md)
traces every one of them to its source:

- **The two factors were the same portfolio.** “Value” was the exact negative of
  “Momentum”, so every comparison was a number against its own negation.
- **The headline F1 was the class base rate.** The test set had 61 weekly
  observations and a 90% negative label rate. A constant predictor scores
  0.9483. The model never predicted the rare class.
- **Features and targets leaked.** Standardization used full-sample statistics,
  the train/test split had no purge against a 13-week overlapping target, and
  position sizing used test-period minima and maxima.

Version 2 replaces the question. The audit is kept in the repository because the
correction is the point.

---

## What this project does

| Construct | What it is | How it is measured |
| :--- | :--- | :--- |
| **Fragility** | How synchronized, concentrated, slow to exit, and consensus-driven the factor’s implied portfolio is | Residual correlation with shrinkage, effective breadth, days-to-liquidate at 10% participation, holding persistence |
| **Capacity** | The capital at which trading costs become material, or consume a stated share of the premium | Square-root market-impact model on traded notional, with sensitivity across horizon, impact, spread, and premium |
| **Decision value** | Whether a fragility overlay improves tail outcomes beyond a volatility-managed portfolio | Net-of-cost backtest against static, exposure-matched, volatility-managed, and randomized comparators |

Fragility is the risk question. Capacity is the sizing question. Neither
requires observing anyone else’s book.

### What this is

- A transparent measurement framework for factor exit risk and capacity.
- A negative result about a plausible but weak crowding proxy.
- A forensic case study in leakage, base-rate metrics, and doc-code drift.
- A tested Python package with a generated report, reproducible manifest, and CI.

### What this is not

- Not an alpha signal, a trading strategy, or investment advice.
- Not a measurement of other investors’ positions.
- Not a causal estimate of crowding.
- Not a source of investable capacity numbers: the sample is survivor-only.
- Not a paper; it is a portfolio project with a paper-level audit trail.

---

## Key findings

**1. The V1 defect reproduces exactly.** Rebuilding V1’s two factors gives a
return correlation of **-1.0000** and a maximum weight gap of zero. The F1
identity `F1 = 2π/(1+π)` implies a 0.902 base rate at the recorded 0.9483. The
exact digit depends on V1’s original data, which was never committed; the
mechanism is confirmed.

**2. The fragility composite does not add left-tail information beyond
volatility.** The primary quantile-0.10 coefficient is **-0.98% per one standard
deviation of fragility** (95% CI **-2.19% to +0.27%**), with a minimum detectable
effect of **1.69%**. The unconditional coefficient is -2.38%; with the full
control set it is -0.98%. **H2 fails**: retention is 0.41, below the stated 0.50
threshold. The composite is largely a volatility proxy.

**3. The fragility overlay loses to volatility management.** On true 5% expected
shortfall, the overlay is worse than a volatility-managed portfolio at the same
average exposure by **-1.25, -1.03, and -0.62 percentage points per week** for
MOM, STREV, and LOWVOL, with bootstrap intervals excluding zero in every case.
The overlay does beat **86-98%** of random exposure paths on tail timing, so the
signal is not pure noise; it is simply weaker than volatility management.

**4. Capacity is a model surface, not a point estimate.** At a 100bp annual
trading-cost-drag hurdle and a 10-day execution horizon:

| Factor | Cost-drag AUM | At 1 day | At 21 days | Gross premium (95% CI) |
| :--- | ---: | ---: | ---: | :--- |
| LOWVOL | **$2.07B** | $207M | $4.34B | -4.84% (-11.08%, +1.40%) |
| MOM | **$395M** | $39M | $829M | 5.41% (-2.90%, +13.71%) |
| STREV | **$7M** | $1M | $15M | 1.70% (-5.14%, +8.54%) |

The ordering follows turnover by construction. The level moves by roughly 20x
across the execution horizon and by orders of magnitude across premium
assumptions. These are model outputs on a survivor-only sample.

**5. Survivorship is the binding limitation.** The panel has **895 tickers and
zero delistings** over 21 years. It compounds at **18.14%** equal-weight versus
**10.80%** for the S&P 500 total return (`^SP500TR`). Factor premia and capacity
levels are biased upward and are not investable estimates.

---

## Methodology at a glance

| Layer | Implementation |
| :--- | :--- |
| **Universe** | 500 largest 60-day median dollar volumes, $5 price floor, 252-day history, recomputed weekly from trailing data. Selection is point-in-time; existence is not (current index membership). |
| **Factors** | `MOM` (12-1), `STREV` (1-month reversal), `LOWVOL` (trailing 252-day volatility). Dollar-neutral deciles, gross 2.0, 2% name cap, 8%/18% entry/exit bands, monthly buy-and-hold. |
| **Fragility** | Four measures: residual synchronization (Ledoit-Wolf), liquidity-weighted effective breadth, exit horizon at 10% participation, long-leg persistence. Expanding z-scores, 104-week burn-in, ±4 winsorization, equal-weight composite. |
| **Capacity** | `cost_i = 0.5·spread + c·σ_i·sqrt(|Δw_i|·A / (ADV_i·D))` on traded notional, with full-month weight drift. Baseline `c = 0.314`, `D = 10` days, 3bp half-spread, 50bp borrow. |
| **Inference** | Quantile regression at `τ = 0.10`, factor fixed effects, lagged volatility/trend/liquidity controls, stationary bootstrap with duplicate dates retained (2,000 reps), centered p-values, Benjamini-Hochberg, reported MDE, and a non-overlapping every-fourth-week check. |
| **Decision layer** | Fragility overlay vs static, exposure-matched, volatility-managed, and randomized controls. True expected shortfall, maximum drawdown, costs, cash, and borrow. |

### The primary estimand

```
Q_0.10( fwd_4w[f,t] | F[f,t], X[f,t] ) = α_f + β_0.10 · F[f,t] + γ' X[f,t]
```

`F` is the fragility composite, `X` contains lagged log volatility, market
volatility, trailing 12-week return, and liquidity regime, and `α_f` are factor
fixed effects. The target is the return over `(t, t+4w]`; controls use
information available at `t`.

---

## Results

### Primary and H2

| Estimate | Value |
| :--- | ---: |
| `β_0.10` per SD | **-0.98%** |
| 95% CI | (-2.19%, +0.27%) |
| `β_0.50` per SD | +0.23% (CI -0.39%, +1.00%) |
| Tail difference (`β_0.10 - β_0.50`) | -1.21% (CI -2.42%, -0.12%) |
| Minimum detectable effect | **1.69%** |
| Uncontrolled `β_0.10` | -2.38% |
| H2 retention under controls | **0.41** (fail) |

The level coefficient includes zero. The tail difference is negative and
excludes zero, so there is a tail-specific pattern, but the left-tail
coefficient itself is not distinguishable from zero at this resolution.

### Per-factor and robustness

| Check | MOM | STREV | LOWVOL |
| :--- | ---: | ---: | ---: |
| Per-factor `β_0.10` | -2.49% | -1.02% | +0.33% |
| 95% CI | (-4.42%, -0.13%) | (-3.22%, +1.44%) | (-1.84%, +1.90%) |
| Centered p-value | 0.028 | 0.375 | 0.778 |
| Quintile sort (Q5-Q1) | +0.90% | +0.97% | +1.00% |
| Quintile sort 95% CI | (-1.03%, +2.81%) | (-0.60%, +2.53%) | (-0.95%, +4.35%) |

The per-factor MOM coefficient is borderline, but the raw quintile sort points
the opposite way and the pooled coefficient flips sign across subsamples
(**-1.79%** in 2005-09, **+1.02%** in 2010-17, **-1.20%** in 2018-25). It is not
a robust finding.

The one secondary result that survives Benjamini-Hochberg is liquidity-weighted
breadth at the 13-week horizon: **-2.13%** (95% CI -3.79% to -0.43%), centered
p = 0.005, adjusted p = 0.040. The 4-week version is not significant after the
centered p-value (p = 0.075).

### Decision layer

| Factor | Fragility ES5 | Vol-managed ES5 | Difference | 95% CI | Random rank |
| :--- | ---: | ---: | ---: | :--- | ---: |
| MOM | -5.85% | -4.62% | **-1.25%** | (-2.14%, -0.37%) | 0.975 |
| STREV | -4.62% | -3.60% | **-1.03%** | (-1.59%, -0.41%) | 0.905 |
| LOWVOL | -3.96% | -3.33% | **-0.62%** | (-1.12%, -0.17%) | 0.855 |

True expected shortfall is the mean of the worst 5% of weeks. The overlay has
better tail timing than most random paths, but it is dominated by volatility
management on every factor.

### Factor premia and beta

| Factor | Gross premium | 95% CI | CAPM alpha | Alpha t-stat | Beta vs equal-weight | Beta t-stat |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: |
| MOM | 5.41% | (-2.90%, +13.71%) | +8.22% | 2.07 | -0.146 | -3.44 |
| STREV | 1.70% | (-5.14%, +8.54%) | -2.63% | -0.81 | +0.225 | 5.97 |
| LOWVOL | -4.84% | (-11.08%, +1.40%) | -3.31% | -1.05 | -0.080 | -3.40 |

The factors are dollar-neutral but **not beta-neutral**. MOM’s beta-adjusted
alpha versus the equal-weight universe is positive and significant at 5%, but the
raw gross premium is imprecise and the capacity level is conditional on it.

---

## Capacity model

The capacity model answers two separate questions:

1. **Cost drag:** at what sleeve size do annual trading costs reach 50, 100, or
   200 basis points?
2. **Premium retention:** at what sleeve size does the strategy retain 25%, 50%,
   or 75% of its assumed gross premium?

```text
D_i   = |Δw_i| · A                         traded dollars
q_i   = D_i / (ADV_i · D)                  participation per day
cost  = 0.5 · spread + c · σ_i · sqrt(q_i)
C(A)  = Σ_i |Δw_i| · cost_i
```

`Δw_i` is the trade after full-month weight drift. The baseline uses `c = 0.314`
and a 10-day execution horizon. The report shows the full surface across
execution horizon (1, 5, 10, 21 days), impact coefficient (0.10, 0.314, 0.50),
spread (1, 3, 10bp), and assumed gross premium (1% to 10%).

**What the numbers mean:** at 100bp of annual trading-cost drag and a 10-day
horizon, MOM can hold about **$395M**, STREV about **$7M**, and LOWVOL about
**$2.07B**. At a 1-day horizon MOM falls to **$39M**; at 21 days it rises to
**$829M**. Capacity is a model output, not a market measurement.

---

## Quickstart

Requires Python 3.10 or newer.

```bash
git clone https://github.com/kira-ml/factor-crowding-risk.git
cd factor-crowding-risk

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

### Run the full study

```bash
python -m fcr all --config configs/v2.json
```

The first data run downloads roughly 900 tickers and takes about 12 minutes.
With the cache, the full pipeline takes about 10-15 minutes on a laptop,
depending on bootstrap reps. The default config uses 2,000 primary bootstrap
replications.

### Fast end-to-end check

```bash
python -m fcr all --config configs/smoke.json
```

The smoke config uses fewer bootstrap replications and random overlays. It is
for checking the pipeline, not for reporting results.

### Stage by stage

```bash
python -m fcr data --config configs/v2.json    # download/cache the panel
python -m fcr core --config configs/v2.json    # universe, factors, fragility, capacity
python -m fcr all  --config configs/v2.json    # everything, including the report
```

### Tests

```bash
pytest -q
```

**39 tests** cover factor invariants, leakage/truncation, target alignment,
bootstrap duplicate retention, expected shortfall, overlay schedules, comparator
exposure matching, capacity drift, data validation, and the study controls.

---

## Outputs

| Path | Contents |
| :--- | :--- |
| `docs/report.md` | Generated research report with every table and figure |
| `docs/figures/` | Six figures: factor returns, fragility, conditional returns, quantile coefficients, capacity, overlay |
| `outputs/tables/` | Machine-readable tables: primary, H2, per-factor, secondary, E2, quintile, subsample, composite sensitivity, capacity, overlay |
| `outputs/runs/<run_id>/manifest.json` | Config hash, git commit, package versions, data SHA256, row counts, elapsed time |
| `outputs/runs/<run_id>/` | Copy of the tables and figures for that run |

The manifest records whether the working tree was dirty. A release run should
have `git_dirty: false`.

---

## Repository layout

```text
factor-crowding-risk/
├── README.md
├── LICENSE
├── TODO.md
├── DECISIONS.md
├── problem_framing.md
├── pyproject.toml
├── requirements.txt
├── configs/
│   ├── v2.json                  # full configuration
│   └── smoke.json               # fast pipeline check
├── src/fcr/
│   ├── data.py                  # download, cache, validate, hash
│   ├── universe.py              # point-in-time liquidity universe
│   ├── factors.py               # signals, weights, buy-and-hold returns
│   ├── fragility.py             # F1-F4 and the composite
│   ├── capacity.py              # impact model, capacity surface
│   ├── targets.py               # forward returns, ES, drawdown
│   ├── stats.py                 # bootstrap, QR, BH, MDE
│   ├── overlay.py               # schedule and comparators
│   ├── backtest.py              # P&L, costs, borrow, metrics
│   ├── study.py                 # primary, H2, E2, robustness
│   ├── decision.py              # overlay vs comparators
│   ├── report.py                # generated report and figures
│   ├── pipeline.py              # orchestration and manifest
│   └── cli.py                   # `python -m fcr`
├── tests/                       # 39 tests
├── docs/
│   ├── report.md                # generated results
│   ├── methodology.md           # normative specification
│   ├── audit_v1.md              # forensic V1 audit
│   ├── audit_v2_independent.md  # pre-fix audit that drove v2.1
│   ├── trial_ledger.md          # specifications tried
│   ├── data_dictionary.md
│   ├── model_card.md
│   └── archive/v1/              # superseded V1, with banners
└── scripts/
    ├── fetch_data.py
    └── check_docs.py
```

---

## Reproducibility

- **Config hash** and full config in every run manifest.
- **Git commit** and dirty-tree flag in every manifest.
- **Package versions** recorded; `requirements.txt` is pinned exactly.
- **Data SHA256** recorded in the manifest and in `data/panel/metadata.json`.
- **Generated report**: `docs/report.md` is written by the pipeline, not edited
  by hand. A docs check verifies the README’s headline numbers against the
  generated tables.
- **CI**: GitHub Actions runs the 39 tests on Python 3.10 and 3.11.

The raw data cache is not committed. To reproduce the exact panel, use the same
`yfinance` snapshot; the manifest tells you whether your panel hash matches.

---

## Limitations

**Survivorship is complete.** The candidate pool is current S&P 500/400
membership, and the panel has zero delistings. Factor premia and capacity levels
are biased upward. This is the binding limitation.

**The data are not frozen.** `yfinance` is mutable, and dollar volume is
adjusted close × reported volume. Split and dividend adjustments are not
independently validated in every series.

**The fragility index is a proxy.** It measures the portfolio the factor
implies, not other investors’ positions. It is about 40% correlated with
realized volatility, and H2 fails.

**The factors are not beta-neutral.** Signal-space residualization leaves
significant realized market beta.

**The study is in-sample and exploratory.** The construction was revised after
inspecting results; see [`docs/trial_ledger.md`](docs/trial_ledger.md). There is
no holdout.

**Capacity is a model output.** The impact coefficient and execution horizon are
assumptions, not measurements. The level moves by roughly 20x across the horizon
and by orders of magnitude across premium assumptions.

**Scope.** Three price-based factors in large US equities. No value, quality,
small caps, international, or intraday execution.

---

## Roadmap

The next improvements, in order of value:

1. **Point-in-time data with delistings** (CRSP or equivalent). Rebuild the
   premia and capacity levels on a market sample.
2. **A genuine holdout or pre-registration.** Freeze the specification and test
   it on a future period.
3. **Execution-calibrated impact.** Replace the assumed `c` and horizon with a
   broker or exchange calibration.
4. **External crowding benchmarks.** Cahan-Luo, Kinlaw-Kritzman, and
   liquidity-squeeze indices as horse-race comparators.
5. **Multi-factor residual model.** Sector and style-neutral residual
   synchronization instead of a single-market model.

See [`TODO.md`](TODO.md) for the full list.

---

## Documentation

| Document | What it answers |
| :--- | :--- |
| [`docs/report.md`](docs/report.md) | What the latest run found, with tables and figures |
| [`docs/methodology.md`](docs/methodology.md) | The normative technical specification |
| [`problem_framing.md`](problem_framing.md) | The research question, hypotheses, and non-claims |
| [`docs/audit_v1.md`](docs/audit_v1.md) | Why the V1 result was invalid |
| [`docs/audit_v2_independent.md`](docs/audit_v2_independent.md) | The pre-fix audit that drove v2.1 |
| [`docs/trial_ledger.md`](docs/trial_ledger.md) | Every specification tried, and why |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Column definitions |
| [`docs/model_card.md`](docs/model_card.md) | Intended use, limitations, and failure modes |
| [`DECISIONS.md`](DECISIONS.md) | Architecture decision records and kill criteria |

---

## Contributing

Issues and pull requests are welcome, especially:

- a point-in-time data source with delistings;
- a pre-registered holdout design;
- a better residual risk model for F1;
- a capacity calibration against real execution data.

Before opening a PR, run:

```bash
pytest -q
python scripts/check_docs.py
```

Please do not add factors, markets, or machine-learning models to the headline
study. The current sample cannot support them, and the failure mode is V1 again.
New ideas belong in a clearly labelled exploratory branch or a new study.

---

## Citation

```bibtex
@misc{lacson2026crowdedexits,
  author = {Lacson, Ken Ira},
  title  = {Crowded Exits: Exit Risk and Capital Capacity in Equity Factors},
  year   = {2026},
  url    = {https://github.com/kira-ml/factor-crowding-risk},
  note   = {Research and engineering portfolio project; not investment advice}
}
```

---

## Author

**Ken Ira Lacson**

- GitHub: [github.com/kira-ml](https://github.com/kira-ml)
- LinkedIn: [linkedin.com/in/ken-ira-lacson-852026343](https://www.linkedin.com/in/ken-ira-lacson-852026343/)

## License

MIT. See [`LICENSE`](LICENSE).

---

*This is a research and engineering portfolio project. It is not investment
advice, and nothing in it should be used to allocate capital. The capacity
numbers are model outputs, not measurements. The fragility index is a proxy, not
a crowding measure.*
