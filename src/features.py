"""
Feature Engineering for Crowding Detection

Implements:
- Baseline: Pairwise Correlation, HHI
- Advanced: Valuation Spread, Z-Score Composite

All features computed on configurable rebalance dates (weekly or monthly).
No look-ahead bias: uses only information available at rebalance date.
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")


def engineer_features(prices: pd.DataFrame, 
                      factor_returns: pd.DataFrame,
                      rebalance_freq: str = 'weekly') -> dict:
    """
    Main entry point for feature engineering.
    
    Parameters
    ----------
    prices : pd.DataFrame
        Daily adjusted close prices. Rows = dates, columns = tickers.
    factor_returns : pd.DataFrame
        Daily factor returns. Columns = ['momentum', 'value'].
    rebalance_freq : str
        'monthly' or 'weekly' - frequency of rebalancing.
        Default: 'weekly' for more observations.
    
    Returns
    -------
    dict
        Keys: 'momentum', 'value'
        Each value is a DataFrame with crowding features by date.
    """
    print(f"Engineering crowding features ({rebalance_freq} rebalancing)...")
    
    # Get rebalance dates
    daily_dates = factor_returns.index
    
    if rebalance_freq == 'weekly':
        # Use end of week (Friday)
        rebalance_dates = daily_dates.to_series().resample('W-FRI').last().dropna()
    else:
        # Default: monthly
        rebalance_dates = daily_dates.to_series().resample('M').last().dropna()
    
    # Keep only dates that exist in factor_returns
    rebalance_dates = rebalance_dates[rebalance_dates.isin(daily_dates)]
    
    print(f"  Using {len(rebalance_dates)} {rebalance_freq} rebalance dates")
    
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


def print_correlation_summary(model_data: dict):
    """
    Print detailed correlation summary for all features vs targets.
    """
    print("\n" + "="*70)
    print("FEATURE CORRELATION SUMMARY")
    print("="*70)
    
    for factor, df in model_data.items():
        if df.empty:
            continue
            
        print(f"\n{factor.upper()} FACTOR")
        print("-"*50)
        print(f"  Observations: {len(df)}")
        
        # Correlation matrix
        feature_cols = ['correlation', 'hhi', 'valuation_spread', 'z_composite']
        target_cols = ['forward_1m', 'forward_3m']
        
        corr_matrix = df[feature_cols + target_cols].corr()
        
        print("\n  Correlations with Forward Returns:")
        print(f"  {'Feature':<18} {'→ 1M':>10} {'→ 3M':>10}")
        print("  " + "-"*40)
        for feat in feature_cols:
            corr_1m = corr_matrix.loc[feat, 'forward_1m']
            corr_3m = corr_matrix.loc[feat, 'forward_3m']
            print(f"  {feat:<18} {corr_1m:>10.4f} {corr_3m:>10.4f}")
        
        print("\n  Feature Correlations (Inter-feature):")
        print(f"  {'Pair':<25} {'Correlation':>12}")
        print("  " + "-"*40)
        print(f"  {'Correlation ↔ HHI':<25} {corr_matrix.loc['correlation', 'hhi']:>12.4f}")
        print(f"  {'Correlation ↔ Z-Composite':<25} {corr_matrix.loc['correlation', 'z_composite']:>12.4f}")
        print(f"  {'HHI ↔ Z-Composite':<25} {corr_matrix.loc['hhi', 'z_composite']:>12.4f}")


# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Load data
    from data import load_data
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    
    print("="*70)
    print("TESTING WEEKLY VS MONTHLY REBALANCING")
    print("="*70)
    
    # Test both frequencies
    for freq in ['monthly', 'weekly']:
        print(f"\n{'='*70}")
        print(f"REBALANCE FREQUENCY: {freq.upper()}")
        print('='*70)
        
        # Engineer features
        features = engineer_features(prices, factor_returns, rebalance_freq=freq)
        model_data = prepare_model_data(features, factor_returns)
        
        # Print summary
        for factor, df in model_data.items():
            print(f"\n{factor.upper()} FACTOR:")
            print(f"  Observations: {len(df)}")
            print(f"  Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
            
            if len(df) > 10:
                z_1m = df['z_composite'].corr(df['forward_1m'])
                z_3m = df['z_composite'].corr(df['forward_3m'])
                print(f"  Z-Composite → 1M: {z_1m:.4f}")
                print(f"  Z-Composite → 3M: {z_3m:.4f}")
        
        # Print detailed correlation summary
        print_correlation_summary(model_data)