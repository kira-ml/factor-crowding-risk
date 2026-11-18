# Trial Ledger

This file records the specifications that were tried during development. It is
reconstructed from `DECISIONS.md`, the V1 audit, the prior red-team review, and
the working tree history. It is not a complete keystroke log, but it is the
minimum disclosure a reviewer needs to judge selection effects.

**Status of the current specification:** exploratory. The final factor set,
rebalancing frequency, turnover bands, execution horizon, and capacity
definition were not frozen before the results were seen. Do not describe the
current study as pre-registered.

## Factor set

| Candidate | Status | Reason |
| :--- | :--- | :--- |
| MOM (12-1) | Kept | Distinct economics, low turnover |
| STREV (1-month reversal) | Kept | High turnover, liquidity-sensitive |
| LOWVOL (trailing 252-day volatility) | Kept | Low turnover, no gross premium in this sample |
| MAX | Rejected | Overlaps LOWVOL; no distinct mechanism in this data |
| HIGH52 | Rejected | Overlaps MOM |
| IVOL | Rejected | Overlaps LOWVOL |
| BAB | Rejected | Requires a beta-sorted construction; overlaps LOWVOL |

## Construction

| Dimension | Values tried | Current |
| :--- | :--- | :--- |
| Rebalance frequency | weekly, monthly | monthly |
| Turnover control | none, 8%/18% entry/exit bands | 8%/18% bands |
| Beta treatment | weight-space hedge, signal-space residualization | signal-space residualization |
| Leg size | decile, minimum 25 names | decile with a 25-name floor |
| Name cap | 2% of gross | 2% of gross |
| Gross exposure | 2.0 | 2.0 |
| Return convention | constant weights, monthly buy-and-hold | monthly buy-and-hold |
| Weighting within leg | equal | equal |

## Capacity

| Dimension | Values tried | Current |
| :--- | :--- | :--- |
| Impact coefficient `c` | 0.10, 0.314, 0.50 | 0.314 baseline, all three in the grid |
| Spread | 1bp, 3bp, 10bp | 3bp baseline, all three in the grid |
| Execution horizon | 1, 5, 10, 21 days | 10 days baseline, all four in the grid |
| Capacity definition | premium retention, cost drag | cost drag at 100bp headline; retention reported alongside |
| Borrow | 50bp baseline | 50bp |
| Turnover convention | one-week drift, full-month drift, weekly rebalance | full-month drift with monthly buy-and-hold |

## Inference and study

| Dimension | Values tried | Current |
| :--- | :--- | :--- |
| Bootstrap duplicates | collapsed (`np.isin`), retained | retained |
| Controls | post-decision week, lagged | lagged |
| Target start | `t+1`, `t` | `t` |
| Primary quantile | 0.05, 0.10, 0.25, 0.50, 0.75, 0.90 | 0.10 primary; 0.50 tail-specificity |
| Bootstrap reps | 200, 400, 800, 2000 | 2000 primary; 400 secondary/per-factor |
| Composite | equal, drop-one, rank-average, PCA | equal headline; drop-one and rank-average reported |
| Secondary family | 4 measures x 2 horizons | same, BH at 10% |
| Overlay schedule | floor 0.0-0.5, start 0.4-0.8, end 0.85-0.99 | floor 0.3, start 0.6, end 0.9 |

The overlay design grid had 48 configurations. The fragility overlay never beat
the volatility-managed comparator on 5% expected shortfall in any of them. That
is a robustness result, not a pre-registered test.

## Data and survivorship

| Dimension | Values tried | Current |
| :--- | :--- | :--- |
| Candidate pool | current S&P 500 + S&P 400 | current membership, 900 names |
| Survivorship | current membership, no delistings | survivor-only; disclosed |
| History filter | 252 days from panel start | 252 days |
| Price floor | $5 | $5 |
| ADV floor | $5m | $5m |
| Universe size | 500 | 500 |

## What this means

The project has a credible negative result and a reusable capacity framework.
It does **not** have a confirmatory test of a crowding signal. A genuine
pre-registration on a future period, or a point-in-time dataset with delistings,
would be a new study. Until then, every inference in `docs/report.md` is
exploratory and should be read with the selection history above in mind.
