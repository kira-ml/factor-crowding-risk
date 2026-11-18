import numpy as np
import pandas as pd

from fcr.decision import _bootstrap_difference
from fcr.overlay import random_overlays
from fcr.targets import expected_shortfall


def test_bootstrap_difference_detects_shift():
    rng = np.random.default_rng(0)
    dates = pd.date_range("2020-01-03", periods=300, freq="W-FRI")
    a = pd.Series(rng.normal(0.01, 0.02, len(dates)), index=dates)
    b = a - 0.01
    mean, lo, hi = _bootstrap_difference(a, b, lambda x: float(np.mean(x)), 200, 8, 1)
    assert mean > 0
    assert lo > 0


def test_true_es_difference_is_larger_than_quantile_difference():
    rng = np.random.default_rng(1)
    dates = pd.date_range("2020-01-03", periods=500, freq="W-FRI")
    a = pd.Series(rng.normal(0.0, 0.02, len(dates)), index=dates)
    b = a - 0.01
    quantile_diff = a.quantile(0.05) - b.quantile(0.05)
    es_diff = expected_shortfall(a, 0.05) - expected_shortfall(b, 0.05)
    assert abs(es_diff) > abs(quantile_diff)


def test_random_overlays_are_reproducible_and_same_distribution():
    dates = pd.date_range("2020-01-03", periods=200, freq="W-FRI")
    overlay = pd.Series(np.linspace(0.3, 1.0, len(dates)), index=dates)
    from fcr.config import Config

    cfg = Config(n_random_overlays=10, seed=7)
    a = random_overlays(overlay, cfg)
    b = random_overlays(overlay, cfg)
    assert a.equals(b)
    assert abs(a.mean().mean() - overlay.mean()) < 0.02
