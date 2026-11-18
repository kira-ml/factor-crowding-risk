import numpy as np
import pandas as pd

from fcr.config import Config
from fcr.overlay import (
    _scaled_to_mean,
    build_comparators,
    expanding_percentile,
    overlay_weight,
    volatility_target,
)


def test_expanding_percentile_uses_only_prior_values():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    pct = expanding_percentile(series, min_periods=3)
    assert pct.iloc[:3].isna().all()
    # At index 3, history is [1,2,3], so 4 is above all of them.
    assert pct.iloc[3] == 1.0
    # At index 4, history is [1,2,3,4], so 5 is above all of them.
    assert pct.iloc[4] == 1.0


def test_overlay_schedule_boundaries():
    cfg = Config(overlay_start_pct=0.60, overlay_end_pct=0.90, overlay_floor=0.30)
    pct = pd.Series([0.0, 0.60, 0.75, 0.90, 1.0])
    weight = overlay_weight(pct, cfg)
    assert weight.iloc[0] == 1.0
    assert weight.iloc[1] == 1.0
    assert abs(weight.iloc[2] - 0.65) < 1e-12
    assert abs(weight.iloc[3] - 0.30) < 1e-12
    assert abs(weight.iloc[4] - 0.30) < 1e-12


def test_scaled_to_mean_is_exact_after_clipping():
    base = pd.Series([0.1, 0.2, 1.0, 2.0, 5.0])
    scaled = _scaled_to_mean(base, target=0.8, cap=1.5)
    assert abs(scaled.mean() - 0.8) < 1e-10
    assert scaled.max() <= 1.5 + 1e-12


def test_volatility_comparator_matches_average_exposure():
    dates = pd.date_range("2020-01-03", periods=400, freq="W-FRI")
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.0, 0.02, len(dates)), index=dates)
    overlay = pd.Series(0.9, index=dates)
    cfg = Config()
    comparators = build_comparators(overlay, returns, cfg)
    assert abs(comparators["vol_managed"].mean() - overlay.mean()) < 1e-8
