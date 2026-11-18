"""Fragility measures F1-F4 and the composite index (methodology section 3).

Every measure is computed from data at or before the rebalance date. All
standardization is expanding with a burn-in; no full-sample statistic is used.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from .config import Config
from .data import Panel
from .factors import FactorSet
from .universe import Universe, market_returns


@dataclass
class Fragility:
    long: pd.DataFrame  # date, factor, raw and standardized measures
    composite: pd.DataFrame  # dates x factors
    coverage: pd.DataFrame  # per factor, counts and NaN rates

    def for_factor(self, factor: str) -> pd.DataFrame:
        return self.long[self.long["factor"] == factor].droplevel("factor")


# ---------------------------------------------------------------------------
# F1: residual synchronization
# ---------------------------------------------------------------------------
def residual_returns(panel: Panel, betas: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    mkt = market_returns(panel)
    resid = panel.returns.sub(betas.mul(mkt, axis=0))
    return resid.replace([np.inf, -np.inf], np.nan)


def _fisher_mean_corr(window: np.ndarray) -> float:
    """Average pairwise correlation with Ledoit-Wolf shrinkage, Fisher-z pooled."""
    if window.shape[1] < 10 or window.shape[0] < 30:
        return np.nan
    # Drop names with any missing day inside the window.
    keep = ~np.isnan(window).any(axis=0)
    window = window[:, keep]
    if window.shape[1] < 10:
        return np.nan
    if window.shape[0] <= window.shape[1]:
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cov = LedoitWolf().fit(window).covariance_
    sd = np.sqrt(np.diag(cov))
    denom = np.outer(sd, sd)
    if (denom <= 0).any():
        return np.nan
    corr = cov / denom
    iu = np.triu_indices(corr.shape[0], k=1)
    values = corr[iu]
    values = values[np.abs(values) < 0.999999]
    if values.size == 0:
        return np.nan
    return float(np.tanh(np.arctanh(values).mean()))


def compute_synchronization(
    resid: pd.DataFrame,
    factors: FactorSet,
    cfg: Config,
) -> dict[str, pd.Series]:
    cols = pd.Index(resid.columns)
    values = resid.to_numpy(dtype=float)
    position = {date: i for i, date in enumerate(resid.index)}
    out: dict[str, pd.Series] = {}

    for factor in cfg.factors:
        mask = factors.long_mask[factor]
        series = {}
        for date in factors.dates:
            pos = position.get(date)
            if pos is None or pos + 1 < 30:
                continue
            names = mask.columns[mask.loc[date].to_numpy()]
            idx = cols.get_indexer(names)
            idx = idx[idx >= 0]
            if idx.size < 10:
                continue
            lo = max(0, pos - cfg.corr_window + 1)
            window = values[lo : pos + 1][:, idx]
            series[date] = _fisher_mean_corr(window)
        out[factor] = pd.Series(series, dtype=float)
    return out


# ---------------------------------------------------------------------------
# F2-F4
# ---------------------------------------------------------------------------
def compute_breadth(weights: pd.Series, adv: pd.Series) -> tuple[float, float]:
    w = weights[weights != 0]
    if w.empty:
        return np.nan, np.nan
    total = w.abs().sum()
    breadth = float(total**2 / (w**2).sum())

    liquid = (
        (w.abs() / adv.reindex(w.index)).replace([np.inf, -np.inf], np.nan).dropna()
    )
    if liquid.empty or liquid.sum() == 0:
        return breadth, np.nan
    u = liquid / liquid.sum()
    breadth_liq = float(1.0 / (u**2).sum())
    return breadth, breadth_liq


def compute_exit_days(
    weights: pd.Series, adv: pd.Series, cfg: Config
) -> tuple[float, float]:
    longs = weights[weights > 0]
    if longs.empty:
        return np.nan, np.nan
    days = longs * cfg.adv_ref_aum / (cfg.participation * adv.reindex(longs.index))
    days = days.replace([np.inf, -np.inf], np.nan).dropna()
    if days.empty:
        return np.nan, np.nan
    return float(days.sum() / longs.sum()), float(days.max())


def compute_persistence(
    mask: pd.DataFrame,
    dates: pd.DatetimeIndex,
    cfg: Config,
) -> pd.Series:
    """Weight in the long leg that has been there for N consecutive rebalances."""
    streak: dict[str, int] = {}
    out = {}
    for date in dates:
        current = set(mask.columns[mask.loc[date].to_numpy()])
        for name in list(streak):
            if name not in current:
                streak.pop(name)
        share_num = 0.0
        share_den = 0.0
        for name in current:
            streak[name] = streak.get(name, 0) + 1
            share_num += 1.0 if streak[name] >= cfg.persist_rebalances else 0.0
            share_den += 1.0
        out[date] = share_num / share_den if share_den else np.nan
    return pd.Series(out, dtype=float)


def signal_dispersion(signal: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    values = {}
    for date in dates:
        s = signal.loc[date].dropna()
        if len(s) < 50:
            continue
        q75, q25 = s.quantile([0.75, 0.25])
        values[date] = float((q75 - q25) / s.std()) if s.std() > 0 else np.nan
    return pd.Series(values, dtype=float)


# ---------------------------------------------------------------------------
# Standardization and composite
# ---------------------------------------------------------------------------
def expanding_z(series: pd.Series, burn_in: int, clip: float) -> pd.Series:
    """Standardize with statistics computed strictly before each date."""
    prior = series.shift(1)
    mean = prior.expanding(min_periods=burn_in).mean()
    std = prior.expanding(min_periods=burn_in).std()
    z = pd.Series(np.nan, index=series.index, dtype=float)
    positive = std > 0
    z[positive] = ((series - mean) / std)[positive]
    flat = mean.notna() & std.notna() & ~positive
    z[flat] = 0.0
    return z.clip(-clip, clip)


def build_fragility(
    panel: Panel,
    factors: FactorSet,
    universe: Universe,
    cfg: Config,
) -> Fragility:
    dates = factors.dates
    betas = factors.betas.reindex(panel.dates)
    resid = residual_returns(panel, betas, cfg)
    sync = compute_synchronization(resid, factors, cfg)

    adv_w = universe.adv.reindex(dates, method="ffill")

    rows = []
    for factor in cfg.factors:
        persistence = compute_persistence(
            factors.portfolio_masks[factor]
            if factors.portfolio_masks
            else factors.long_mask[factor],
            factors.portfolio_dates if factors.portfolio_dates is not None else dates,
            cfg,
        ).reindex(dates, method="ffill")
        dispersion = signal_dispersion(factors.signals[factor], dates)

        for date in dates:
            weights = factors.weights[factor].loc[date]
            adv = adv_w.loc[date]
            breadth, breadth_liq = compute_breadth(weights, adv)
            exit_mean, exit_max = compute_exit_days(weights, adv, cfg)
            rows.append(
                {
                    "date": date,
                    "factor": factor,
                    "sync": float(sync[factor].get(date, np.nan)),
                    "breadth": breadth,
                    "breadth_liq": breadth_liq,
                    "exit_days": exit_mean,
                    "exit_days_max": exit_max,
                    "persistence": float(persistence.get(date, np.nan)),
                    "dispersion": float(dispersion.get(date, np.nan)),
                }
            )

    long = pd.DataFrame(rows).set_index(["date", "factor"]).sort_index()

    # Oriented so that higher means more fragile.
    long["o_sync"] = long["sync"]
    long["o_breadth"] = -np.log(long["breadth_liq"].replace(0, np.nan))
    long["o_exit"] = np.log(long["exit_days"].replace(0, np.nan))
    long["o_persist"] = long["persistence"]

    components = ["o_sync", "o_breadth", "o_exit", "o_persist"]
    for factor in cfg.factors:
        sl = long.xs(factor, level="factor")
        for component in components:
            long.loc[(slice(None), factor), f"z_{component}"] = expanding_z(
                sl[component], cfg.burn_in, cfg.z_clip
            ).to_numpy()

    z_cols = [f"z_{component}" for component in components]
    weights = np.asarray(cfg.composite_weights, dtype=float)
    weights = weights / weights.sum()
    long["composite"] = (long[z_cols] * weights).sum(axis=1, min_count=len(z_cols))

    composite = long["composite"].unstack("factor").reindex(dates)

    coverage = (
        long.reset_index()
        .groupby("factor")
        .agg(
            dates=("date", "count"),
            sync_missing=("sync", lambda s: float(s.isna().mean())),
            breadth_missing=("breadth_liq", lambda s: float(s.isna().mean())),
            exit_missing=("exit_days", lambda s: float(s.isna().mean())),
            persist_missing=("persistence", lambda s: float(s.isna().mean())),
            composite_missing=("composite", lambda s: float(s.isna().mean())),
        )
    )
    coverage["composite_usable"] = (
        coverage["dates"] * (1 - coverage["composite_missing"])
    ).astype(int)

    return Fragility(long=long, composite=composite, coverage=coverage)
