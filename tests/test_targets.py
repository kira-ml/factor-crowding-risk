import numpy as np
import pandas as pd

from fcr.config import Config
from fcr.targets import drawdown_episodes, expected_shortfall, forward_returns


def test_forward_returns_start_at_decision_date():
    dates = pd.date_range("2020-01-03", periods=8, freq="W-FRI")
    returns = pd.DataFrame(
        {"MOM": [0.01, 0.02, -0.01, 0.03, 0.00, -0.02, 0.01, 0.04]}, index=dates
    )
    cfg = Config(horizons_weeks=(1, 4))
    fwd = forward_returns(returns, cfg)

    one = fwd["fwd_1w"]["MOM"]
    four = fwd["fwd_4w"]["MOM"]

    # fwd_1[t] is the return over (t, t+1], i.e. r_t. The first observation has
    # no prior cumulative value, so it is NaN by construction.
    assert np.allclose(one.iloc[1:], returns["MOM"].iloc[1:])
    assert np.isnan(one.iloc[0])

    # fwd_4[t] compounds r_t through r_{t+3}, not r_{t+1} through r_{t+4}.
    for i in range(1, len(returns) - 4):
        expected = np.prod(1.0 + returns["MOM"].iloc[i : i + 4]) - 1.0
        assert abs(four.iloc[i] - expected) < 1e-12


def test_expected_shortfall_is_tail_mean():
    values = pd.Series([-0.10, -0.05] + [0.0] * 38)
    # The bottom 5% threshold is -0.05; the tail contains both negative values.
    assert abs(expected_shortfall(values, 0.05) - (-0.075)) < 1e-12


def test_drawdown_episodes_finds_trough_and_recovery():
    dates = pd.date_range("2020-01-01", periods=6, freq="W-FRI")
    returns = pd.Series([0.10, -0.20, -0.10, 0.05, 0.40, 0.0], index=dates)
    episodes = drawdown_episodes(returns, threshold=0.10)
    assert len(episodes) == 1
    assert episodes.iloc[0]["depth"] < -0.25
