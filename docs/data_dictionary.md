# Data Dictionary

## Panel

`data/panel/close.parquet` and `volume.parquet` are daily, wide frames indexed
by trading date with one column per ticker.

| Column concept | Definition | Source |
| :--- | :--- | :--- |
| `close` | Split- and dividend-adjusted close | `yfinance`, `auto_adjust=True` |
| `volume` | Reported share volume | `yfinance` |

`data/panel/metadata.json` records the SHA256 of the panel, its shape, date
range, and creation time. The SHA256 is also written to each run manifest.

**Known limitation:** dollar volume is computed as adjusted close × reported
volume. It is not independently validated around every split and dividend.
Treat ADV as an approximate point-in-time liquidity measure, not an exchange
tape. The methodology's split check is a roadmap item, not a completed fix.

## Universe

| Object | Definition |
| :--- | :--- |
| Candidate pool | Current S&P 500 and S&P 400 members |
| `members[t]` | 500 largest 60-day median dollar volumes among names with 252 days of history, price ≥ $5, ADV ≥ $5m, and a valid price at `t` |
| `adv` | Rolling 60-day median dollar volume, trailing |
| `history` | Cumulative count of valid daily prices |

The universe is point-in-time with respect to liquidity and price, not with
respect to existence. The candidate pool is current membership, so the sample
is survivor-only.

## Factors

| Field | Definition |
| :--- | :--- |
| `MOM` | `close[t-21] / close[t-252] - 1` |
| `STREV` | `-(close[t] / close[t-21] - 1)` |
| `LOWVOL` | `-std(daily returns, 252 days)` |
| `weights` | Dollar-neutral decile spread, gross 2.0, 2% name cap, 8%/18% entry/exit bands, monthly rebalance |
| `returns` | Monthly buy-and-hold factor return; weights drift between rebalances |

## Fragility

| Field | Definition | Orientation |
| :--- | :--- | :--- |
| `sync` | Ledoit-Wolf residual correlation, long leg, 60-day window | Higher = more fragile |
| `breadth` | `(Σ|w|)² / Σw²`, unweighted | Diagnostic only; degenerate for equal weights |
| `breadth_liq` | Effective breadth after dividing weights by ADV | Higher = more fragile after sign flip |
| `exit_days` | Dollar-weighted days to liquidate the long leg at 10% participation, $1bn reference | Higher = more fragile |
| `persistence` | Share of long-leg names held for ≥6 consecutive monthly rebalances | Higher = more fragile |
| `z_o_*` | Expanding z-score, 104-week burn-in, ±4 winsorization | Higher = more fragile |
| `composite` | Equal-weight mean of the four z-scores | Higher = more fragile |

## Study panel

`study.dataset` has one row per date × factor:

| Column | Definition |
| :--- | :--- |
| `fwd_4w` | Return over `(t, t+4w]` |
| `fwd_13w` | Return over `(t, t+13w]` |
| `composite` | Fragility composite at `t` |
| `log_vol` | log 20-day EWMA factor volatility, lagged one week |
| `mkt_vol` | log 20-day EWMA universe volatility, lagged one week |
| `trail_12w` | Trailing 12-week factor return, lagged one week |
| `liq_regime` | log 12-week change in median ADV |

## Capacity

| Column | Definition |
| :--- | :--- |
| `turnover` | Mean absolute traded notional per week, after full-month weight drift |
| `cost_bp` | Mean one-way trading cost in basis points per rebalance |
| `net_premium` | Annualized gross premium minus trading costs, borrow, and financing |
| `cost_100bp` | Largest sleeve where annual trading-cost drag reaches 100bp |
| `hurdle_0.50` | Largest sleeve retaining 50% of gross premium; `n/a` if gross ≤ 0 |
| `premium_sensitivity` | Retention capacity for alternative assumed gross premiums |
