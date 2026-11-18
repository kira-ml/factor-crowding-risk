"""Cash return series from the 13-week T-bill rate (^IRX)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DATA_DIR, Config


def load_cash_rate(cfg: Config, dates: pd.DatetimeIndex) -> pd.Series:
    """Weekly cash return.

    Falls back to zero if the series is unavailable. Zero is conservative for a
    de-risking overlay because it removes the interest earned on cash.
    """
    cache = Path(DATA_DIR) / "cash.parquet"
    if cache.exists():
        series = pd.read_parquet(cache).iloc[:, 0]
    else:
        series = pd.Series(dtype=float)
        try:
            import yfinance as yf

            raw = yf.download(
                "^IRX",
                start=cfg.start,
                end=cfg.end,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                series = raw["Close"].astype(float)
                series.index = pd.to_datetime(series.index).tz_localize(None)
                series.to_frame("rate").to_parquet(cache)
        except Exception:
            series = pd.Series(dtype=float)

    if series.empty:
        return pd.Series(0.0, index=dates)

    combined = series.reindex(series.index.union(dates)).sort_index().ffill()
    weekly = combined.reindex(dates, method="ffill").fillna(0.0)
    return (weekly / 100.0 / 52.0).astype(float)
