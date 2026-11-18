import numpy as np
import pandas as pd
import pytest

from fcr.backtest import metrics, run_strategy
from fcr.config import Config


def test_run_strategy_net_of_costs_and_borrow():
    dates = pd.date_range("2020-01-03", periods=52, freq="W-FRI")
    returns = pd.Series(0.0, index=dates)
    weight = pd.Series(1.0, index=dates)
    cash = pd.Series(0.0, index=dates)
    cfg = Config(borrow_bp=100.0, scaling_cost_bp=0.0)
    frame = run_strategy(returns, weight, cash, cfg)
    # One year of 100bp borrow is approximately 1% of the short notional.
    assert abs(frame["net"].sum() - (-0.01)) < 1e-12


def test_run_strategy_rejects_out_of_range_exposure():
    dates = pd.date_range("2020-01-03", periods=5, freq="W-FRI")
    returns = pd.Series(0.0, index=dates)
    cash = pd.Series(0.0, index=dates)
    cfg = Config()
    with pytest.raises(ValueError):
        run_strategy(returns, pd.Series(2.0, index=dates), cash, cfg)


def test_metrics_es_is_true_expected_shortfall():
    dates = pd.date_range("2020-01-03", periods=100, freq="W-FRI")
    rng = np.random.default_rng(0)
    values = pd.Series(rng.normal(0.0, 0.02, len(dates)), index=dates)
    frame = pd.DataFrame({"weight": 1.0, "net": values, "cost": 0.0, "borrow": 0.0})
    row = metrics(frame)
    threshold = values.quantile(0.05)
    assert abs(row["es_5"] - values[values <= threshold].mean()) < 1e-12
    # The quantile is not the ES; keep the distinction explicit.
    assert row["q5"] != pytest.approx(row["es_5"])
