"""Forward targets, tail measures, and drawdown episodes (methodology section 5)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config


def forward_returns(returns: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Forward cumulative factor returns from each decision date.

    ``factors.returns[t]`` is the return over ``(t, t+1]``. At a decision made
    on the close of ``t``, the first return that can be earned is ``r_t`` and the
    last known return is ``r_{t-1}``. The target is therefore

        fwd_h[t] = prod(1 + r_t ... r_{t+h-1}) - 1
                 = cum[t+h-1] / cum[t-1] - 1,

    which starts at ``t`` and includes exactly ``h`` weeks. The previous
    implementation started at ``t+1`` while the controls included ``r_t``.
    """
    clean = returns.dropna(how="all")
    cumulative = (1.0 + clean.fillna(0.0)).cumprod()
    out = {}
    for horizon in cfg.horizons_weeks:
        out[f"fwd_{horizon}w"] = (
            cumulative.shift(-(horizon - 1)) / cumulative.shift(1) - 1.0
        ).reindex(returns.index)
    return pd.concat(out, axis=1)


def cumulative(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.fillna(0.0)).cumprod()


def drawdown_series(returns: pd.Series) -> pd.Series:
    cum = cumulative(returns)
    return cum / cum.cummax() - 1.0


def expected_shortfall(returns: pd.Series, q: float = 0.05) -> float:
    values = returns.dropna()
    if len(values) < 20:
        return np.nan
    threshold = values.quantile(q)
    tail = values[values <= threshold]
    return float(tail.mean()) if len(tail) else np.nan


def drawdown_episodes(returns: pd.Series, threshold: float = 0.10) -> pd.DataFrame:
    """Peak-to-trough episodes deeper than ``threshold``."""
    cum = cumulative(returns)
    peak = cum.cummax()
    dd = cum / peak - 1.0
    episodes = []
    in_episode = False
    start = None
    trough_date = None
    trough = 0.0

    for date, value in dd.items():
        if not in_episode and value <= -threshold:
            in_episode = True
            start = peak.loc[:date].idxmax()
            trough_date = date
            trough = value
        elif in_episode:
            if value < trough:
                trough = value
                trough_date = date
            if value >= -1e-12:
                episodes.append(
                    {
                        "start": start,
                        "trough": trough_date,
                        "end": date,
                        "depth": trough,
                        "weeks": int(((date - start).days) / 7),
                    }
                )
                in_episode = False
                trough = 0.0

    if in_episode:
        episodes.append(
            {
                "start": start,
                "trough": trough_date,
                "end": dd.index[-1],
                "depth": trough,
                "weeks": int(((dd.index[-1] - start).days) / 7),
            }
        )
    return pd.DataFrame(episodes)


def episode_frame(returns: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for factor in returns.columns:
        episodes = drawdown_episodes(returns[factor])
        if episodes.empty:
            continue
        episodes["factor"] = factor
        frames.append(episodes)
    if not frames:
        return pd.DataFrame(
            columns=["factor", "start", "trough", "end", "depth", "weeks"]
        )
    return pd.concat(frames, ignore_index=True)[
        ["factor", "start", "trough", "end", "depth", "weeks"]
    ]
