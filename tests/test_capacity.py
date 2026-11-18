import numpy as np
import pandas as pd

from fcr.capacity import _solve, portfolio_drift_trades
from fcr.config import Config


def test_portfolio_drift_trades_accounts_for_full_period():
    dates = pd.date_range("2020-01-03", periods=5, freq="W-FRI")
    portfolio_dates = pd.DatetimeIndex([dates[0], dates[3]])
    weights = pd.DataFrame(0.0, index=portfolio_dates, columns=["A", "B"], dtype=float)
    weights.loc[dates[0], ["A", "B"]] = [0.5, -0.5]
    weights.loc[dates[3], ["A", "B"]] = [0.5, -0.5]
    weekly = pd.DataFrame(
        {
            "A": [0.10, 0.10, 0.10, 0.0],
            "B": [0.00, 0.00, 0.00, 0.0],
        },
        index=dates[:4],
    )
    factor_returns = pd.Series([0.05, 0.05, 0.05, 0.0], index=dates[:4])
    trades = portfolio_drift_trades(
        weights, portfolio_dates, weekly, factor_returns, dates
    )
    # A drifts to 0.5*(1.1^3/1.05^3) = 0.573..., so the rebalance sells it.
    drift_a = 0.5 * (1.1**3) / (1.05**3)
    assert abs(trades.loc[dates[3], "A"] - (0.5 - drift_a)) < 1e-12
    assert trades.loc[dates[1]].abs().sum() == 0.0


def test_retention_capacity_is_nan_for_negative_premium():
    s1 = pd.Series([0.1, 0.1])
    s2 = pd.Series([1e-8, 1e-8])
    cfg = Config()
    assert np.isnan(_solve(s1, s2, -0.01, cfg, -0.005, cfg.impact_c, cfg.spread_bp))
