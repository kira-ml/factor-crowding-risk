"""Decision layer: the fragility overlay and its comparators (methodology section 7)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .stats import stationary_bootstrap_indices


def expanding_percentile(series: pd.Series, min_periods: int = 104) -> pd.Series:
    """Percentile rank of each value within the strictly prior history."""
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    history: list[float] = []
    for i, value in enumerate(values):
        if np.isnan(value):
            history.append(value)
            continue
        if len(history) >= min_periods:
            array = np.asarray(history, dtype=float)
            valid = array[~np.isnan(array)]
            if valid.size >= min_periods:
                out[i] = (
                    np.sum(valid < value) + 0.5 * np.sum(valid == value)
                ) / valid.size
        history.append(value)
    return pd.Series(out, index=series.index)


def overlay_weight(percentile: pd.Series, cfg: Config) -> pd.Series:
    """Piecewise-linear de-risking schedule. Fixed in advance, never fitted."""
    out = pd.Series(cfg.overlay_cap, index=percentile.index, dtype=float)
    start, end = cfg.overlay_start_pct, cfg.overlay_end_pct
    middle = (percentile > start) & (percentile <= end)
    span = max(end - start, 1e-9)
    out[middle] = cfg.overlay_cap - (percentile[middle] - start) / span * (
        cfg.overlay_cap - cfg.overlay_floor
    )
    out[percentile > end] = cfg.overlay_floor
    out[percentile.isna()] = 1.0
    return out.clip(cfg.overlay_floor, cfg.overlay_cap)


def build_overlay(composite: pd.Series, cfg: Config) -> pd.DataFrame:
    pct = expanding_percentile(composite, cfg.burn_in)
    weight = overlay_weight(pct, cfg)
    return pd.DataFrame({"percentile": pct, "weight": weight}).dropna(subset=["weight"])


def _scaled_to_mean(base: pd.Series, target: float, cap: float) -> pd.Series:
    """Scale a non-negative series so its clipped mean equals ``target``.

    A simple rescale followed by a clip undershoots the target whenever the cap
    binds. Bisection on the scale factor gives an exact mean match, which is
    required for the volatility-managed comparator.
    """
    values = base.fillna(0.0).clip(lower=0.0)
    if values.empty or target <= 0 or values.mean() == 0:
        return pd.Series(0.0, index=values.index)
    target = min(target, cap)
    max_mean = float(np.where(values > 0, cap, 0.0).mean())
    if target >= max_mean:
        return (values * 1e12).clip(upper=cap)
    lo, hi = 0.0, max(1.0, target / max(values.mean(), 1e-12) * 2.0)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float((mid * values).clip(upper=cap).mean()) < target:
            lo = mid
        else:
            hi = mid
    return (hi * values).clip(upper=cap)


def volatility_target(
    factor_returns: pd.Series,
    cfg: Config,
    target_mean: float,
    span: int = 12,
) -> pd.Series:
    """Inverse-volatility weights, rescaled to an exact target average exposure.

    The volatility estimate at ``t`` uses returns through ``t-1`` only. The
    scale is solved so that the clipped series has the same mean as the overlay.
    """
    vol = factor_returns.ewm(span=span, min_periods=8).std() * np.sqrt(52)
    base = (cfg.vol_target / vol.replace(0, np.nan)).shift(1).fillna(1.0)
    return _scaled_to_mean(base, target_mean, cfg.vol_scale_cap)


def exposure_matched(overlay: pd.Series) -> pd.Series:
    return pd.Series(float(overlay.mean()), index=overlay.index)


def random_overlays(overlay: pd.Series, cfg: Config) -> pd.DataFrame:
    """Block-shuffled exposure paths with the same marginal distribution.

    Preserves autocorrelation in blocks while destroying the link to fragility,
    so it separates timing information from the exposure distribution.
    """
    rng = np.random.default_rng(cfg.seed + 7)
    values = overlay.to_numpy(dtype=float)
    n = len(values)
    out = {}
    for i in range(cfg.n_random_overlays):
        idx = stationary_bootstrap_indices(n, 8, rng)
        out[f"random_{i:03d}"] = values[idx]
    return pd.DataFrame(out, index=overlay.index)


def build_comparators(
    overlay: pd.Series,
    factor_returns: pd.Series,
    cfg: Config,
) -> dict[str, pd.Series]:
    target_mean = float(overlay.mean())
    return {
        "static": pd.Series(1.0, index=overlay.index),
        "vol_managed": volatility_target(
            factor_returns.reindex(overlay.index), cfg, target_mean
        ),
        "exposure_matched": exposure_matched(overlay),
        "fragility": overlay,
    }
