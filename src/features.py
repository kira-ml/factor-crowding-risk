"""
Feature Engineering for Crowding Detection

Implements:
- Baseline: Pairwise Correlation, HHI
- Advanced: Valuation Spread, Z-Score Composite

All features computed on monthly rebalance dates.
No look-ahead bias: uses only information available at rebalance date.
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")


def engineer_features(prices: pd.DataFrame, 
                      factor_returns: pd.DataFrame) -> dict:
    """
    Main entry point for feature engineering.
    
    Parameters
    ----------
    prices : pd.DataFrame
        Daily adjusted close prices. Rows = dates, columns = tickers.
    factor_returns : pd.DataFrame
        Daily factor returns. Columns = ['momentum', 'value'].
    
    Returns
    -------
    dict
        Keys: 'momentum', 'value'
        Each value is a DataFrame with crowding features by date.
    """
    print("Engineering crowding features...")
    
    # Get monthly rebalance dates (end of each month with factor data)
    daily_dates = factor_returns.index
    monthly_dates = daily_dates.to_series().resample('M').last().dropna()
    
    # Keep only dates that exist in factor_returns
    rebalance_dates = monthly_dates[monthly_dates.isin(daily_dates)]
    
    print(f"  Using {len(rebalance_dates)} monthly rebalance dates")
    
    # Get daily returns for correlation calculations
    daily_returns = prices.pct_change()
    
    features = {}
    
    for factor in ['momentum', 'value']:
        print(f"  Processing {factor}...")
        features[factor] = _compute_features_for_factor(
            prices, daily_returns, rebalance_dates, factor
        )
    
    print("Feature engineering complete.")
    return features


def _compute_features_for_factor(prices: pd.DataFrame,
                                  daily_returns: pd.DataFrame,
                                  rebalance_dates: pd.DatetimeIndex,
                                  factor: str) -> pd.DataFrame:
    """
    Compute all crowding features for a single factor.
    """
    results = []
    
    for date in rebalance_dates:
        # Get factor scores at this rebalance date
        factor_scores = _get_factor_scores(prices, date, factor)
        
        if factor_scores is None or len(factor_scores) < 50:
            continue
            
        # Identify top and bottom quintiles
        n_quintile = max(1, int(len(factor_scores) * 0.2))
        top_quintile = factor_scores.nlargest(n_quintile).index
        bottom_quintile = factor_scores.nsmallest(n_quintile).index
        
        # --- BASELINE FEATURES ---
        
        # 1. Pairwise Correlation (average correlation among top quintile)
        corr = _compute_pairwise_correlation(daily_returns, top_quintile, date)
        
        # 2. HHI (Factor Exposure Concentration)
        hhi = _compute_hhi(factor_scores)
        
        # --- ADVANCED FEATURES ---
        
        # 3. Valuation Spread (price spread between top and bottom)
        val_spread = _compute_valuation_spread(prices, top_quintile, bottom_quintile, date)
        
        # Store results
        results.append({
            'date': date,
            'correlation': corr if corr is not None else np.nan,
            'hhi': hhi if hhi is not None else np.nan,
            'valuation_spread': val_spread if val_spread is not None else np.nan,
        })
    
    # Convert to DataFrame
    if len(results) == 0:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    df.set_index('date', inplace=True)
    
    # Drop rows where all features are NaN
    df = df.dropna(how='all')
    
    # Compute z-score composite (using only non-NaN values)
    if len(df) > 0:
        # Use only rows where both correlation and HHI exist
        valid = df[['correlation', 'hhi']].dropna()
        if len(valid) > 0:
            # Handle case where std is zero (all values identical)
            corr_std = valid['correlation'].std()
            hhi_std = valid['hhi'].std()
            
            if corr_std > 0 and hhi_std > 0:
                corr_z = (valid['correlation'] - valid['correlation'].mean()) / corr_std
                hhi_z = (valid['hhi'] - valid['hhi'].mean()) / hhi_std
                z_composite = (corr_z + hhi_z) / 2
            else:
                z_composite = pd.Series(0, index=valid.index)
            
            # Merge back
            df['z_composite'] = np.nan
            df.loc[valid.index, 'z_composite'] = z_composite
        else:
            df['z_composite'] = np.nan
    
    return df


def _get_factor_scores(prices: pd.DataFrame, 
                       date: pd.Timestamp, 
                       factor: str) -> pd.Series:
    """
    Get factor scores for all stocks at a given date.
    
    For momentum: 12-month return (excluding most recent month)
    For value: inverse of momentum (cheap = low past return)
    """
    # Find closest available date
    available_dates = prices.index[prices.index <= date]
    if len(available_dates) == 0:
        return None
        
    current_date = available_dates[-1]
    
    # Get lookback period (12 months)
    lookback_date = current_date - pd.DateOffset(months=12)
    prev_date = current_date - pd.DateOffset(months=1)
    
    # Get prices at lookback date
    try:
        prices_lookback = prices.loc[lookback_date]
    except KeyError:
        lookback_available = prices.index[prices.index <= lookback_date]
        if len(lookback_available) == 0:
            return None
        lookback_date = lookback_available[-1]
        prices_lookback = prices.loc[lookback_date]
    
    # Get prices at previous month
    try:
        prices_prev = prices.loc[prev_date]
    except KeyError:
        prev_available = prices.index[prices.index <= prev_date]
        if len(prev_available) == 0:
            return None
        prev_date = prev_available[-1]
        prices_prev = prices.loc[prev_date]
    
    # Compute scores
    if factor == 'momentum':
        scores = (prices_prev / prices_lookback) - 1
    else:  # value
        momentum = (prices_prev / prices_lookback) - 1
        scores = -momentum  # Cheap stocks have low past returns
    
    # Clean up
    scores = scores.dropna()
    scores = scores[~scores.isin([np.inf, -np.inf])]
    
    return scores


def _compute_pairwise_correlation(daily_returns: pd.DataFrame,
                                   tickers: list,
                                   date: pd.Timestamp) -> float:
    """
    Compute average pairwise correlation among tickers over past 60 days.
    """
    # Get 60-day window ending at this date
    window_start = date - pd.DateOffset(days=60)
    window_returns = daily_returns.loc[(daily_returns.index <= date) & 
                                       (daily_returns.index > window_start)]
    
    if len(window_returns) < 30:
        return None
        
    # Filter to available tickers
    available_tickers = [t for t in tickers if t in window_returns.columns]
    if len(available_tickers) < 10:
        return None
        
    # Subset returns
    subset = window_returns[available_tickers]
    subset = subset.dropna(axis=1, how='all')
    
    if subset.shape[1] < 10 or subset.shape[0] < 10:
        return None
        
    # Remove columns with all NaN
    subset = subset.dropna(axis=1, how='all')
    
    if subset.shape[1] < 10:
        return None
        
    # Compute correlation matrix
    corr_matrix = subset.corr()
    
    # Average of upper triangle (excluding diagonal)
    n = len(corr_matrix)
    if n <= 1:
        return None
        
    upper_tri = corr_matrix.values[np.triu_indices(n, k=1)]
    return np.nanmean(upper_tri)


def _compute_hhi(factor_scores: pd.Series) -> float:
    """
    Compute Herfindahl-Hirschman Index of factor exposure concentration.
    """
    # Normalize scores to sum to 1 (portfolio weights)
    weights = factor_scores.abs() / factor_scores.abs().sum()
    
    # HHI = sum(weight_i^2)
    hhi = (weights ** 2).sum()
    
    return hhi


def _compute_valuation_spread(prices: pd.DataFrame,
                               top_tickers: list,
                               bottom_tickers: list,
                               date: pd.Timestamp) -> float:
    """
    Compute median price spread between top and bottom quintiles.
    
    Note: This is a simple proxy. In production, use P/B or P/E from fundamentals.
    """
    try:
        current_prices = prices.loc[date]
        
        # Get median prices for top and bottom
        top_prices = current_prices[top_tickers].dropna()
        bottom_prices = current_prices[bottom_tickers].dropna()
        
        if len(top_prices) > 0 and len(bottom_prices) > 0:
            top_median = top_prices.median()
            bottom_median = bottom_prices.median()
            
            # Spread = top - bottom (positive means expensive top quintile)
            return top_median - bottom_median
        else:
            return None
            
    except (KeyError, ValueError):
        return None


def prepare_model_data(features: dict, factor_returns: pd.DataFrame) -> dict:
    """
    Prepare data for modeling by aligning features with forward factor returns.
    
    Parameters
    ----------
    features : dict
        Output from engineer_features()
    factor_returns : pd.DataFrame
        Daily factor returns.
    
    Returns
    -------
    dict
        Keys: 'momentum', 'value'
        Each value is a DataFrame with features and forward returns.
    """
    model_data = {}
    
    for factor in ['momentum', 'value']:
        # Get features for this factor
        feat_df = features[factor]
        
        if feat_df.empty:
            model_data[factor] = pd.DataFrame()
            continue
        
        # Get forward returns (1-month and 3-month)
        forward_returns = []
        
        for date in feat_df.index:
            # Find next month end
            next_month = date + pd.DateOffset(months=1)
            next_3month = date + pd.DateOffset(months=3)
            
            # Get forward returns
            ret_1m = _get_forward_return(factor_returns[factor], date, next_month)
            ret_3m = _get_forward_return(factor_returns[factor], date, next_3month)
            
            forward_returns.append({
                'date': date,
                'forward_1m': ret_1m,
                'forward_3m': ret_3m
            })
        
        fwd_df = pd.DataFrame(forward_returns)
        fwd_df.set_index('date', inplace=True)
        
        # Combine features with forward returns
        combined = feat_df.join(fwd_df)
        combined = combined.dropna()
        
        model_data[factor] = combined
    
    return model_data


def _get_forward_return(series: pd.Series, start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    """
    Get cumulative return between two dates.
    """
    try:
        returns = series.loc[(series.index > start_date) & (series.index <= end_date)]
        if len(returns) == 0:
            return np.nan
        return (1 + returns).prod() - 1
    except:
        return np.nan


# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Load data
    from data import load_data
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    
    # Engineer features
    features = engineer_features(prices, factor_returns)
    
    # Prepare model data
    model_data = prepare_model_data(features, factor_returns)
    
    print("\n" + "="*60)
    print("FEATURE ENGINEERING SUMMARY")
    print("="*60)
    
    for factor, df in model_data.items():
        print(f"\n{factor.upper()} FACTOR - MODEL DATA")
        print("-"*40)
        if df.empty:
            print("  No data available")
            continue
            
        print(f"  Observations: {len(df)}")
        print(f"  Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"\n  Features:")
        print(f"    Correlation     | mean: {df['correlation'].mean():.4f} | std: {df['correlation'].std():.4f}")
        print(f"    HHI             | mean: {df['hhi'].mean():.4f} | std: {df['hhi'].std():.4f}")
        print(f"    Valuation Spread| mean: {df['valuation_spread'].mean():.4f} | std: {df['valuation_spread'].std():.4f}")
        print(f"    Z-Composite     | mean: {df['z_composite'].mean():.4f} | std: {df['z_composite'].std():.4f}")
        print(f"\n  Targets:")
        print(f"    Forward 1M      | mean: {df['forward_1m'].mean():.4f} | std: {df['forward_1m'].std():.4f}")
        print(f"    Forward 3M      | mean: {df['forward_3m'].mean():.4f} | std: {df['forward_3m'].std():.4f}")
        print(f"\n  Correlations with targets:")
        corr_1m = df[['correlation', 'hhi', 'valuation_spread', 'z_composite']].corrwith(df['forward_1m'])
        corr_3m = df[['correlation', 'hhi', 'valuation_spread', 'z_composite']].corrwith(df['forward_3m'])
        print(f"    Correlation     -> 1M: {corr_1m['correlation']:.4f} | 3M: {corr_3m['correlation']:.4f}")
        print(f"    HHI             -> 1M: {corr_1m['hhi']:.4f} | 3M: {corr_3m['hhi']:.4f}")
        print(f"    Valuation Spread-> 1M: {corr_1m['valuation_spread']:.4f} | 3M: {corr_3m['valuation_spread']:.4f}")
        print(f"    Z-Composite     -> 1M: {corr_1m['z_composite']:.4f} | 3M: {corr_3m['z_composite']:.4f}")