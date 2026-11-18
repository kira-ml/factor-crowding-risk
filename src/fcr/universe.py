"""Point-in-time liquidity universe (methodology section 1.4)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import Config
from .data import Panel


@dataclass
class Universe:
    """Weekly membership sets and the inputs used to build them."""

    dates: pd.DatetimeIndex
    members: dict[pd.Timestamp, pd.Index]
    adv: pd.DataFrame  # dollar ADV, daily
    history: pd.DataFrame  # count of valid observations, daily
    last_valid: pd.Series

    def size(self) -> pd.Series:
        return pd.Series({d: len(m) for d, m in self.members.items()})

    def membership_frame(self) -> pd.DataFrame:
        """Long frame of (date, ticker) membership, for audit and joins."""
        rows = [(d, t) for d, names in self.members.items() for t in names]
        frame = pd.DataFrame(rows, columns=["date", "ticker"])
        return frame


def rebalance_dates(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Last trading day of each period in ``index``.

    Using the observed trading calendar rather than a synthetic calendar means
    every rebalance date is a date on which prices exist.
    """
    series = pd.Series(index, index=index)
    grouped = series.groupby(pd.Grouper(freq=freq)).max().dropna()
    return pd.DatetimeIndex(grouped.values).sort_values()


def compute_adv(panel: Panel, cfg: Config) -> pd.DataFrame:
    """Rolling median dollar volume. Trailing only."""
    dv = panel.dollar_volume
    return dv.rolling(cfg.adv_window, min_periods=max(5, cfg.adv_window // 3)).median()


def compute_history(panel: Panel) -> pd.DataFrame:
    """Cumulative count of valid prices. Trailing only."""
    return panel.close.notna().cumsum()


def market_returns(panel: Panel) -> pd.Series:
    """Equal-weight cross-sectional mean of available daily returns.

    A broad, point-in-time market proxy used for beta estimation. It uses only
    contemporaneous cross-sectional information.
    """
    return panel.returns.mean(axis=1, skipna=True)


def build_universe(panel: Panel, cfg: Config) -> Universe:
    dates = rebalance_dates(panel.dates, cfg.rebalance_freq)
    adv = compute_adv(panel, cfg)
    history = compute_history(panel)
    last_valid = panel.last_valid()

    # Reindex trailing daily quantities to the rebalance calendar. ffill is safe
    # here because every input is already a trailing statistic.
    adv_w = adv.reindex(dates, method="ffill")
    hist_w = history.reindex(dates, method="ffill")
    price_w = panel.close.reindex(dates, method="ffill")

    members: dict[pd.Timestamp, pd.Index] = {}
    for date in dates:
        # Use the price observed on the rebalance date, not a full-sample
        # last-valid date. A name that trades on t is eligible at t even if it
        # later delists; a name that has already stopped trading is not.
        alive = panel.close.loc[date].notna()
        eligible = (
            alive
            & (price_w.loc[date] >= cfg.min_price)
            & (hist_w.loc[date] >= cfg.min_history_days)
            & (adv_w.loc[date] >= cfg.min_adv)
        )
        candidates = adv_w.loc[date][eligible].dropna()
        if len(candidates) < 100:
            continue
        members[date] = candidates.nlargest(cfg.universe_size).index

    if len(members) < 100:
        raise ValueError(f"Universe construction produced only {len(members)} dates")

    return Universe(
        dates=pd.DatetimeIndex(members.keys()),
        members=members,
        adv=adv,
        history=history,
        last_valid=last_valid,
    )


def adv_at(universe: Universe, date: pd.Timestamp) -> pd.Series:
    """ADV observable at ``date``."""
    return universe.adv.reindex([date], method="ffill").iloc[0].dropna()


def coverage_report(universe: Universe, panel: Panel) -> pd.DataFrame:
    """Universe size and coverage over time, used for the survivorship disclosure."""
    rows = []
    for date, names in universe.members.items():
        rows.append(
            {
                "date": date,
                "size": len(names),
                "available": int(panel.close.loc[date, names].notna().sum()),
            }
        )
    return pd.DataFrame(rows).set_index("date")
