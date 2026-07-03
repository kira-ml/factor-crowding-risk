"""
Data acquisition and cleaning.

Single entry point: load_data()
Returns a dictionary of clean DataFrames ready for feature engineering.

All external I/O lives here. All raw data transformations live here.
Nowhere else.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_data(start: str = "2018-01-01", end: str = "2024-12-31") -> dict:
    """
    Main entry point.

    Returns
    -------
    dict with keys:
        prices : pd.DataFrame
            Daily adjusted close prices for S&P 500 constituents.
        factor_returns : pd.DataFrame
            Daily factor returns for momentum and value.
    """
    print("Fetching S&P 500 constituents...")
    tickers = _get_snp500_tickers()

    print(f"Downloading price data for {len(tickers)} stocks...")
    prices = _download_prices(tickers, start, end)

    # Debug: check actual date range of downloaded data
    print(f"Price data date range: {prices.index[0]} to {prices.index[-1]}")
    print(f"Price data shape: {prices.shape}")
    monthly_test = prices.resample("ME").last()
    print(f"Monthly resample shape: {monthly_test.shape}")

    print("Constructing factor returns...")
    factor_returns = _build_factors(prices)

    print("Done.")
    return {
        "prices": prices,
        "factor_returns": factor_returns,
    }


# ---------------------------------------------------------------------------
# S&P 500 Constituents
# ---------------------------------------------------------------------------

def _get_snp500_tickers() -> list:
    """
    Scrape current S&P 500 tickers from Wikipedia.

    Returns
    -------
    list of valid ticker strings.
    """
    import requests

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    table = pd.read_html(response.text)[0]
    tickers = table["Symbol"].tolist()

    # Replace dots with hyphens for yfinance compatibility
    tickers = [t.replace(".", "-") for t in tickers]
    return tickers


# ---------------------------------------------------------------------------
# Price Data
# ---------------------------------------------------------------------------
def _download_prices(tickers: list, start: str, end: str) -> pd.DataFrame:
    """
    Download daily adjusted close prices for a list of tickers.

    Downloads in yearly chunks to avoid yfinance truncation issues
    with long date ranges and many tickers.

    Parameters
    ----------
    tickers : list
        List of ticker symbols.
    start, end : str
        Date range in "YYYY-MM-DD" format.

    Returns
    -------
    pd.DataFrame
        Rows = dates, columns = tickers, values = adjusted close.
    """
    import time

    start_date = pd.Timestamp(start)
    end_date = pd.Timestamp(end)

    all_chunks = []

    year_start = start_date
    while year_start < end_date:
        year_end = min(year_start + pd.DateOffset(years=1), end_date)
        chunk_start = year_start.strftime("%Y-%m-%d")
        chunk_end = year_end.strftime("%Y-%m-%d")

        print(f"  Downloading {chunk_start} to {chunk_end}...")

        try:
            raw = yf.download(
                tickers,
                start=chunk_start,
                end=chunk_end,
                auto_adjust=True,
                progress=False,
            )
        except Exception as e:
            print(f"    Warning: download failed ({e}), skipping chunk.")
            year_start = year_end
            continue

        if raw.empty:
            print(f"    Warning: empty DataFrame, skipping chunk.")
            year_start = year_end
            continue

        raw.index = pd.to_datetime(raw.index)

        # Extract Close prices regardless of column structure
        if isinstance(raw.columns, pd.MultiIndex):
            levels = raw.columns.get_level_values(0).unique()
            if "Close" in levels:
                prices_chunk = raw.xs("Close", axis=1, level=0)
            elif "Adj Close" in levels:
                prices_chunk = raw.xs("Adj Close", axis=1, level=0)
            else:
                prices_chunk = raw.copy()
                if isinstance(prices_chunk.columns, pd.MultiIndex):
                    prices_chunk = prices_chunk.xs(
                        prices_chunk.columns.get_level_values(0)[0],
                        axis=1,
                        level=0,
                    )
        else:
            if "Close" in raw.columns:
                prices_chunk = raw[["Close"]].copy()
            else:
                prices_chunk = raw.copy()

        # Ensure we have a 2D DataFrame with string columns
        if isinstance(prices_chunk, pd.Series):
            prices_chunk = prices_chunk.to_frame()

        prices_chunk.columns = [str(c) for c in prices_chunk.columns]

        if not prices_chunk.empty:
            all_chunks.append(prices_chunk)
            print(f"    Got {len(prices_chunk)} rows, {len(prices_chunk.columns)} tickers.")

        year_start = year_end
        time.sleep(0.5)

    if not all_chunks:
        raise ValueError("No data downloaded in any chunk.")

    # Merge all chunks
    print(f"  Merging {len(all_chunks)} chunks...")
    prices = pd.concat(all_chunks, axis=0, sort=True)
    prices.index.name = "date"

    # Group by date and take the first non-NaN value for each ticker
    prices = prices.groupby(prices.index).first()
    prices = prices.sort_index()

    # Clean up
    prices = prices.dropna(axis=1, how="all")   # Drop tickers with zero data
    prices = prices.ffill()                      # Forward-fill gaps within each ticker
    # Drop rows only if ALL tickers are NaN (not if ANY ticker is NaN)
    prices = prices.dropna(axis=0, how="all")
    # Now drop rows with fewer than 100 valid tickers (keep early years with partial coverage)
    prices = prices[prices.notna().sum(axis=1) >= 100]

    print(f"  Final: {len(prices)} rows, {len(prices.columns)} tickers.")
    print(f"  Date range: {prices.index[0]} to {prices.index[-1]}")

    return prices


# ---------------------------------------------------------------------------
# Factor Construction (Simple, Replicable Definitions)
# ---------------------------------------------------------------------------
def _build_factors(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Build daily momentum and value factor returns from price data.

    Momentum (12-1 month):
        Top quintile by trailing 12-month return (excluding most recent month)
        minus bottom quintile. Rebalanced monthly.

    Value (Book-to-Market proxy using Price reversal):
        Top quintile by low 12-month return (cheap)
        minus bottom quintile (expensive).
        This is a rough proxy. True B/M requires fundamental data.

    Parameters
    ----------
    prices : pd.DataFrame
        Daily adjusted close prices. Rows = dates, columns = tickers.

    Returns
    -------
    pd.DataFrame
        Daily factor returns. Columns: ['momentum', 'value'].
    """
    # Resample to monthly for signal construction
    monthly_prices = prices.resample("ME").last()
    daily_returns = prices.pct_change()

    factor_returns = []

    # Need at least 13 months of data (12 for lookback + 1 for forward)
    for i in range(12, len(monthly_prices) - 1):
        rebalance_date = monthly_prices.index[i]

        # Get tickers that have prices on this rebalance date
        available = monthly_prices.iloc[i].dropna()
        available_tickers = available.index

        if len(available_tickers) < 50:
            continue

        # --- Momentum: return from t-12 to t-1 ---
        start_price = monthly_prices.iloc[i - 12][available_tickers]
        end_price = monthly_prices.iloc[i - 1][available_tickers]

        # Only keep tickers with valid prices at both points
        valid = start_price.notna() & end_price.notna()
        start_price = start_price[valid]
        end_price = end_price[valid]

        if len(start_price) < 50:
            continue

        momentum_score = (end_price / start_price) - 1

        # Quintile split
        n_quintile = max(1, int(len(momentum_score) * 0.2))
        top_mom = momentum_score.nlargest(n_quintile).index
        bot_mom = momentum_score.nsmallest(n_quintile).index

        # --- Value: inverse of momentum (cheap = low past return) ---
        value_score = -momentum_score
        top_val = value_score.nlargest(n_quintile).index
        bot_val = value_score.nsmallest(n_quintile).index

        # --- Forward period: rebalance date to next month end ---
        next_rebalance = monthly_prices.index[i + 1]
        mask = (daily_returns.index > rebalance_date) & (daily_returns.index <= next_rebalance)
        period_returns = daily_returns.loc[mask]

        if period_returns.empty:
            continue

        # Factor returns for this period
        mom_factor = period_returns[top_mom].mean(axis=1) - period_returns[bot_mom].mean(axis=1)
        val_factor = period_returns[top_val].mean(axis=1) - period_returns[bot_val].mean(axis=1)

        combined = pd.DataFrame({
            "momentum": mom_factor,
            "value": val_factor,
        })

        factor_returns.append(combined)

    if not factor_returns:
        raise ValueError(
            "Could not construct factor returns. "
            f"Monthly data shape: {monthly_prices.shape}, "
            f"available tickers per month: ~{monthly_prices.notna().sum(axis=1).mean():.0f}"
        )

    result = pd.concat(factor_returns)
    result = result.sort_index()
    result = result.dropna()

    return result


# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data = load_data(start="2018-01-01", end="2024-12-31")
    print("\nPrice data shape:", data["prices"].shape)
    print("Factor returns shape:", data["factor_returns"].shape)
    print("\nFactor return stats:")
    print(data["factor_returns"].describe())
    print("\nMomentum cumulative return:", (1 + data["factor_returns"]["momentum"]).prod() - 1)
    print("Value cumulative return:", (1 + data["factor_returns"]["value"]).prod() - 1)