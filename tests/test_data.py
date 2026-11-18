import numpy as np
import pandas as pd
import pytest

from fcr.data import DataError, Panel, panel_hash, validate


def test_returns_do_not_forward_fill_prices():
    dates = pd.date_range("2020-01-01", periods=6, freq="B")
    close = pd.DataFrame({"A": [10.0, 11.0, np.nan, 12.0, 13.0, 14.0]}, index=dates)
    volume = pd.DataFrame({"A": 1000.0}, index=dates)
    panel = Panel(close, volume)
    returns = panel.returns["A"]
    assert np.isnan(returns.iloc[2])
    assert np.isnan(returns.iloc[3])


def test_panel_hash_is_stable_and_content_sensitive():
    dates = pd.date_range("2020-01-01", periods=3, freq="B")
    close = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=dates)
    volume = pd.DataFrame({"A": [10.0, 10.0, 10.0]}, index=dates)
    a = Panel(close.copy(), volume.copy())
    b = Panel(close.copy(), volume.copy())
    assert panel_hash(a) == panel_hash(b)
    b.close.iloc[0, 0] = 2.0
    assert panel_hash(a) != panel_hash(b)


def test_validate_rejects_non_positive_prices():
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    close = pd.DataFrame({"A": np.linspace(10, 20, 300)}, index=dates)
    volume = pd.DataFrame({"A": 1000.0}, index=dates)
    close.iloc[10, 0] = 0.0
    with pytest.raises(DataError):
        validate(Panel(close, volume))
