import numpy as np
import pandas as pd
import pytest

from fcr.stats import (
    benjamini_hochberg,
    bootstrap_dates,
    bootstrap_pvalue,
    bootstrap_row_positions,
    minimum_detectable_effect,
    percentile_interval,
    probabilistic_sharpe,
    stationary_bootstrap_indices,
)


def test_bootstrap_indices_valid():
    rng = np.random.default_rng(0)
    idx = stationary_bootstrap_indices(100, 8, rng)
    assert len(idx) == 100
    assert idx.min() >= 0 and idx.max() < 100


def test_bootstrap_retains_duplicate_dates():
    dates = pd.date_range("2010-01-01", periods=200, freq="W-FRI")
    samples = bootstrap_dates(dates, n_reps=5, block_mean=4, seed=1)
    assert len(samples) == 5
    for sample in samples:
        assert len(sample) == 200
        assert set(sample).issubset(set(dates.to_numpy()))

    # Row-position bootstrap must repeat dates, not collapse them. A correct
    # with-replacement resample has length n and roughly 63% unique dates; the
    # old np.isin implementation returned a mask of length 0.63n.
    panel_dates = np.repeat(dates.to_numpy(), 3)  # three factors per date
    positions = bootstrap_row_positions(panel_dates, n_reps=5, block_mean=4, seed=1)
    for rows in positions:
        assert len(rows) == len(panel_dates)
        unique_dates = len(np.unique(panel_dates[rows]))
        assert 0.5 < unique_dates / len(dates.to_numpy()) < 0.8


def test_bootstrap_pvalue_is_centered():
    rng = np.random.default_rng(0)
    # Sampling distribution centered at 0.5 with a known spread. Under the null
    # theta=0, the centered p-value should be small but not degenerate.
    samples = rng.normal(0.5, 0.1, 5000)
    p = bootstrap_pvalue(samples, estimate=0.5)
    assert 0.0 <= p <= 1.0
    assert p < 1e-6
    # A zero estimate should produce a p-value near one.
    assert bootstrap_pvalue(samples - 0.5, estimate=0.0) > 0.99


def test_bh_rejects_clear_signal():
    pvalues = pd.Series([0.001, 0.002, 0.003, 0.9, 0.95])
    result = benjamini_hochberg(pvalues, alpha=0.10)
    assert result["reject"].sum() == 3
    assert result["adjusted"].min() <= 0.05


def test_bh_accepts_null():
    pvalues = pd.Series([0.4, 0.6, 0.8, 0.9])
    result = benjamini_hochberg(pvalues, alpha=0.10)
    assert result["reject"].sum() == 0


def test_mde_formula():
    # (1.96 + 0.8416) * se
    assert abs(minimum_detectable_effect(0.01) - 0.028016) < 1e-4
    assert np.isnan(minimum_detectable_effect(np.nan))


def test_percentile_interval_contains_median():
    samples = np.random.default_rng(3).normal(0, 1, 5000)
    lo, hi = percentile_interval(samples, 0.05)
    assert lo < 0 < hi
    assert hi - lo > 3.5


def test_probabilistic_sharpe_increases_with_sr():
    low = probabilistic_sharpe(0.1, 500)
    high = probabilistic_sharpe(0.5, 500)
    assert high > low
