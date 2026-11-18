import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fcr.config import Config  # noqa: E402
from fcr.data import Panel  # noqa: E402


@pytest.fixture(scope="session")
def cfg() -> Config:
    return Config(
        start="2008-01-01",
        end="2025-12-31",
        max_tickers=150,
        universe_size=120,
        min_history_days=252,
        min_adv=1e5,
        adv_ref_aum=1e9,
        bootstrap_reps=200,
        n_random_overlays=20,
        burn_in=104,
    )


@pytest.fixture(scope="session")
def panel() -> Panel:
    """Synthetic panel: market factor plus idiosyncratic noise, deterministic."""
    rng = np.random.default_rng(7)
    n_days = 4000
    n_names = 140
    dates = pd.bdate_range("2008-01-02", periods=n_days)

    market = rng.normal(0.0003, 0.010, n_days)
    beta = rng.uniform(0.6, 1.6, n_names)
    idio = rng.normal(0.0, 0.014, (n_days, n_names))
    returns = market[:, None] * beta[None, :] + idio

    # Give the first 10 names a listing delay so the history filter matters.
    returns[:300, :10] = np.nan

    prices = 50.0 * np.exp(np.nancumsum(np.nan_to_num(returns), axis=0))
    prices[:300, :10] = np.nan
    close = pd.DataFrame(prices, index=dates, columns=[f"S{i:03d}" for i in range(n_names)])

    volume = pd.DataFrame(
        rng.lognormal(13, 0.4, (n_days, n_names)), index=dates, columns=close.columns
    )
    return Panel(close, volume)
