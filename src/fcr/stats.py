"""Inference utilities: block bootstrap, quantile regression, FDR, MDE."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def stationary_bootstrap_indices(
    n: int, block_mean: int, rng: np.random.Generator
) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices.

    Geometric block lengths with the given mean, wrapping at the end so that
    every observation has equal probability of inclusion.
    """
    p = 1.0 / max(2, block_mean)
    out = np.empty(n, dtype=int)
    idx = rng.integers(0, n)
    for i in range(n):
        if i > 0 and rng.random() < p:
            idx = rng.integers(0, n)
        else:
            idx = (idx + 1) % n
        out[i] = idx
    return out


def bootstrap_dates(
    dates: pd.Index, n_reps: int, block_mean: int, seed: int
) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    unique = pd.Index(dates.unique()).sort_values()
    samples = []
    for _ in range(n_reps):
        idx = stationary_bootstrap_indices(len(unique), block_mean, rng)
        samples.append(unique.to_numpy()[idx])
    return samples


def bootstrap_row_positions(
    dates: pd.Index | np.ndarray, n_reps: int, block_mean: int, seed: int
) -> list[np.ndarray]:
    """Stationary bootstrap over dates, returning row positions with duplicates.

    A panel has several rows per date (one per factor). Resampling dates and then
    selecting rows with ``np.isin`` collapses duplicate dates and produces a
    subsample, not a bootstrap. The positions returned here repeat every row for
    a drawn date once per draw, so the replicate has the correct bootstrap
    variance.
    """
    values = np.asarray(dates)
    unique = pd.Index(pd.unique(values)).sort_values()
    lookup = pd.DataFrame({"date": values, "position": np.arange(len(values))})
    positions = {
        date: group["position"].to_numpy(dtype=int)
        for date, group in lookup.groupby("date", sort=False)
    }
    rng = np.random.default_rng(seed)
    reps: list[np.ndarray] = []
    for _ in range(n_reps):
        idx = stationary_bootstrap_indices(len(unique), block_mean, rng)
        drawn = pd.DatetimeIndex(unique.to_numpy()[idx])
        reps.append(np.concatenate([positions[date] for date in drawn]))
    return reps


def percentile_interval(
    samples: np.ndarray, alpha: float = 0.05
) -> tuple[float, float]:
    clean = samples[~np.isnan(samples)]
    if clean.size < 20:
        return (np.nan, np.nan)
    return (
        float(np.quantile(clean, alpha / 2)),
        float(np.quantile(clean, 1 - alpha / 2)),
    )


def bootstrap_ci(
    values: pd.Series,
    statistic,
    n_reps: int,
    block_mean: int,
    seed: int,
    alpha: float = 0.05,
) -> tuple[float, float, np.ndarray]:
    """Bootstrap a statistic over a time-ordered series."""
    clean = values.dropna()
    samples = np.empty(n_reps)
    samples[:] = np.nan
    dates = clean.index
    for i, drawn in enumerate(bootstrap_dates(dates, n_reps, block_mean, seed)):
        samples[i] = statistic(clean.reindex(drawn))
    lo, hi = percentile_interval(samples, alpha)
    return lo, hi, samples


# ---------------------------------------------------------------------------
# Quantile regression
# ---------------------------------------------------------------------------
@dataclass
class QuantileFit:
    quantile: float
    params: dict[str, float]
    nobs: int


def quantile_regression(
    y: np.ndarray, x: np.ndarray, names: list[str], q: float
) -> QuantileFit:
    from statsmodels.regression.quantile_regression import QuantReg

    model = QuantReg(y, x)
    result = model.fit(q=q, max_iter=5000)
    return QuantileFit(
        quantile=q, params=dict(zip(names, result.params)), nobs=int(result.nobs)
    )


def bootstrap_quantile_regression(
    y: np.ndarray,
    x: np.ndarray,
    dates: np.ndarray,
    names: list[str],
    q: float,
    n_reps: int,
    block_mean: int,
    seed: int,
) -> pd.DataFrame:
    """Block bootstrap over dates, keeping all factors on a date together."""
    rows = []
    for positions in bootstrap_row_positions(dates, n_reps, block_mean, seed):
        if len(positions) < 100:
            continue
        try:
            fit = quantile_regression(y[positions], x[positions], names, q)
        except Exception:
            continue
        rows.append(fit.params)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Multiple testing and power
# ---------------------------------------------------------------------------
def benjamini_hochberg(pvalues: pd.Series, alpha: float = 0.10) -> pd.DataFrame:
    values = pvalues.dropna()
    n = len(values)
    ordered = values.sort_values()
    ranks = np.arange(1, n + 1)
    threshold = ranks / n * alpha
    passed = ordered.to_numpy() <= threshold
    cutoff = int(np.max(np.where(passed)[0])) + 1 if passed.any() else 0
    reject = pd.Series(False, index=ordered.index)
    if cutoff:
        reject.loc[ordered.index[:cutoff]] = True
    adjusted = pd.Series(
        np.minimum(1.0, ordered.to_numpy() * n / ranks), index=ordered.index
    )
    adjusted = adjusted.reindex(values.index)
    return pd.DataFrame({"pvalue": values, "adjusted": adjusted, "reject": reject})


def minimum_detectable_effect(
    se: float, alpha: float = 0.05, power: float = 0.80
) -> float:
    if not np.isfinite(se) or se <= 0:
        return np.nan
    z_alpha = scipy_stats.norm.ppf(1 - alpha / 2)
    z_power = scipy_stats.norm.ppf(power)
    return float((z_alpha + z_power) * se)


def bootstrap_pvalue(
    samples: np.ndarray,
    estimate: float | None = None,
    null: float = 0.0,
    two_sided: bool = True,
) -> float:
    """Bootstrap p-value from the centered sampling distribution.

    ``samples`` are bootstrap draws of the estimator. They are centered at the
    point estimate, not at the null. The correct two-sided p-value is
    ``P(|theta* - theta_hat| >= |theta_hat - null|)``.
    """
    clean = samples[~np.isnan(samples)]
    if clean.size < 20:
        return np.nan
    point = float(np.mean(clean)) if estimate is None else float(estimate)
    if two_sided:
        return float(np.mean(np.abs(clean - point) >= abs(point - null)))
    return float(np.mean(clean - point <= null - point))


def sharpe(returns: pd.Series, periods: int = 52) -> float:
    clean = returns.dropna()
    if clean.std() == 0 or len(clean) < 10:
        return np.nan
    return float(clean.mean() / clean.std() * np.sqrt(periods))


def max_drawdown(returns: pd.Series) -> float:
    cum = (1.0 + returns.fillna(0.0)).cumprod()
    return float((cum / cum.cummax() - 1.0).min())


def probabilistic_sharpe(
    sr: float, n: int, skew: float = 0.0, kurt: float = 3.0
) -> float:
    """Probability that the true Sharpe exceeds zero (Bailey-Lopez de Prado)."""
    if not np.isfinite(sr) or n < 10:
        return np.nan
    numerator = sr * np.sqrt(n - 1)
    denominator = np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    return float(scipy_stats.norm.cdf(numerator / denominator))


def deflated_sharpe(
    sr: float, n: int, trials: int, skew: float = 0.0, kurt: float = 3.0
) -> float:
    """Sharpe probability after correcting for the number of trials."""
    if trials < 1 or not np.isfinite(sr):
        return np.nan
    e_max = scipy_stats.norm.ppf(1 - 1.0 / max(2, trials))
    benchmark = e_max / np.sqrt(max(2, n))
    return probabilistic_sharpe(sr - benchmark, n, skew, kurt)
