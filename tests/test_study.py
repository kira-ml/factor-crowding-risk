import numpy as np
import pytest

from fcr.factors import build_factors
from fcr.fragility import build_fragility
from fcr.study import (
    _controls,
    build_dataset,
    h2_attenuation,
    non_overlapping_regression,
)
from fcr.universe import build_universe


@pytest.fixture(scope="module")
def built(panel, cfg):
    universe = build_universe(panel, cfg)
    factors = build_factors(panel, universe, cfg)
    fragility = build_fragility(panel, factors, universe, cfg)
    return universe, factors, fragility


def test_controls_are_lagged_and_truncation_invariant(panel, cfg, built):
    universe, factors, _ = built
    cutoff = factors.portfolio_dates[-2]
    full = _controls(factors, universe, panel, cfg)["MOM"].loc[cutoff]

    truncated_panel = panel.slice(cutoff)
    truncated_universe = build_universe(truncated_panel, cfg)
    truncated_factors = build_factors(truncated_panel, truncated_universe, cfg)
    truncated = _controls(truncated_factors, truncated_universe, truncated_panel, cfg)["MOM"].loc[
        cutoff
    ]

    for column in ("log_vol", "mkt_vol", "trail_12w", "liq_regime"):
        assert np.isclose(full[column], truncated[column], atol=1e-8, equal_nan=True), (
            f"{column} leaks post-decision data"
        )


def test_h2_attenuation_reports_full_and_single_control(panel, cfg, built):
    universe, factors, fragility = built
    dataset, _ = build_dataset(factors, fragility, universe, panel, cfg)
    h2 = h2_attenuation(dataset, cfg)
    assert len(h2) == 3
    retention = h2.loc[h2["specification"] == "full_controls", "retention"].iloc[0]
    assert 0.0 < retention <= 1.0


def test_non_overlapping_regression_uses_fewer_dates(panel, cfg, built):
    universe, factors, fragility = built
    dataset, _ = build_dataset(factors, fragility, universe, panel, cfg)
    result = non_overlapping_regression(dataset, cfg, reps=20)
    assert len(result) == 1
    assert result["n_dates"].iloc[0] < dataset["date"].nunique()
    assert result["n_rows"].iloc[0] == result["n_dates"].iloc[0] * 3
