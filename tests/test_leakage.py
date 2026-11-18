"""Leakage tests (methodology section 8).

The truncation test is the mechanical guarantee that V1 lacked: deleting the
future must not change any feature at the truncation date.
"""

import numpy as np
import pandas as pd
import pytest

from fcr.factors import build_factors
from fcr.fragility import build_fragility, expanding_z
from fcr.universe import build_universe


def test_expanding_z_uses_only_past():
    series = pd.Series(
        np.linspace(0, 1, 400) + np.random.default_rng(1).normal(0, 0.1, 400)
    )
    base = expanding_z(series, burn_in=50, clip=4.0)

    perturbed = series.copy()
    perturbed.iloc[250:] = 1e6
    changed = expanding_z(perturbed, burn_in=50, clip=4.0)

    assert np.allclose(base.iloc[:250], changed.iloc[:250], equal_nan=True)
    assert not np.allclose(base.iloc[251:], changed.iloc[251:], equal_nan=True)


def test_future_prices_do_not_affect_weights(panel, cfg):
    universe = build_universe(panel, cfg)
    factors = build_factors(panel, universe, cfg)
    cutoff = (
        factors.portfolio_dates[-2]
        if factors.portfolio_dates is not None
        else factors.dates[-40]
    )

    truncated_panel = panel.slice(cutoff)
    truncated_universe = build_universe(truncated_panel, cfg)
    truncated_factors = build_factors(truncated_panel, truncated_universe, cfg)

    for factor in cfg.factors:
        a = factors.weights[factor].loc[cutoff].to_numpy()
        b = truncated_factors.weights[factor].loc[cutoff].to_numpy()
        assert np.allclose(a, b, atol=1e-8), f"{factor} weights leak future data"


def test_fragility_is_truncation_invariant(panel, cfg):
    """Rebuild the whole stack on data up to t* and compare the composite."""
    universe = build_universe(panel, cfg)
    factors = build_factors(panel, universe, cfg)
    full = build_fragility(panel, factors, universe, cfg)

    cutoff = (
        factors.portfolio_dates[-2]
        if factors.portfolio_dates is not None
        else factors.dates[-40]
    )
    truncated_panel = panel.slice(cutoff)

    t_universe = build_universe(truncated_panel, cfg)
    t_factors = build_factors(truncated_panel, t_universe, cfg)
    t_fragility = build_fragility(truncated_panel, t_factors, t_universe, cfg)

    a = full.composite.loc[cutoff].to_numpy(dtype=float)
    b = t_fragility.composite.loc[cutoff].to_numpy(dtype=float)
    assert np.allclose(a, b, atol=1e-8, equal_nan=True)


def test_composite_reports_nan_before_burn_in(panel, cfg):
    universe = build_universe(panel, cfg)
    factors = build_factors(panel, universe, cfg)
    fragility = build_fragility(panel, factors, universe, cfg)

    first_valid = fragility.composite.dropna(how="all").index.min()
    position = list(factors.dates).index(first_valid)
    assert position >= cfg.burn_in - 1


def test_majority_classifier_f1_identity():
    """V1's F1 equals the base-rate score of a constant predictor.

    With a positive-class base rate pi, predicting the majority class for every
    observation gives F1 = 2*pi/(1+pi). At pi = 0.902 this is 0.9483, the value
    recorded in the V1 result file.
    """
    for pi in (0.5, 0.75, 0.902, 0.95):
        f1 = 2 * pi / (1 + pi)
        assert 0.0 <= f1 <= 1.0
    assert abs(2 * 0.902 / 1.902 - 0.9485) < 0.001
