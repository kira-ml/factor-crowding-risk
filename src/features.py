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
                      rebalance_freq: str = 'weekly',
                      window_days: int = 60,
                      quintile_pct: float = 0.2) -> dict:
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
    window_days : int
        Window length for correlation calculation (30, 60, 90, 120).
    quintile_pct : float
        Top quintile percentage (0.1, 0.2, 0.3).
    
    Returns
    -------
    dict
        Keys: 'momentum', 'value'
        Each value is a DataFrame with crowding features by date.
    """
    print(f"Engineering crowding features ({rebalance_freq} rebalancing)...")
    print(f"  Window days: {window_days}, Quintile: {quintile_pct*100:.0f}%")
    
    # Get rebalance dates
    daily_dates = factor_returns.index
    
    if rebalance_freq == 'weekly':
        rebalance_dates = daily_dates.to_series().resample('W-FRI').last().dropna()
    else:
        rebalance_dates = daily_dates.to_series().resample('M').last().dropna()
    
    rebalance_dates = rebalance_dates[rebalance_dates.isin(daily_dates)]
    
    print(f"  Using {len(rebalance_dates)} {rebalance_freq} rebalance dates")
    
    daily_returns = prices.pct_change()
    
    features = {}
    
    for factor in ['momentum', 'value']:
        print(f"  Processing {factor}...")
        features[factor] = _compute_features_for_factor(
            prices, daily_returns, rebalance_dates, factor, window_days, quintile_pct
        )
    
    print("Feature engineering complete.")
    return features


def _compute_features_for_factor(prices: pd.DataFrame,
                                  daily_returns: pd.DataFrame,
                                  rebalance_dates: pd.DatetimeIndex,
                                  factor: str,
                                  window_days: int = 60,
                                  quintile_pct: float = 0.2) -> pd.DataFrame:
    """
    Compute all crowding features for a single factor.
    """
    results = []
    
    for date in rebalance_dates:
        factor_scores = _get_factor_scores(prices, date, factor)
        
        if factor_scores is None or len(factor_scores) < 50:
            continue
            
        # Identify top and bottom quintiles
        n_quintile = max(1, int(len(factor_scores) * quintile_pct))
        top_quintile = factor_scores.nlargest(n_quintile).index
        bottom_quintile = factor_scores.nsmallest(n_quintile).index
        
        # 1. Pairwise Correlation
        corr = _compute_pairwise_correlation(daily_returns, top_quintile, date, window_days)
        
        # 2. HHI
        hhi = _compute_hhi(factor_scores)
        
        # 3. Valuation Spread
        val_spread = _compute_valuation_spread(prices, top_quintile, bottom_quintile, date)
        
        results.append({
            'date': date,
            'correlation': corr if corr is not None else np.nan,
            'hhi': hhi if hhi is not None else np.nan,
            'valuation_spread': val_spread if val_spread is not None else np.nan,
        })
    
    if len(results) == 0:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    df.set_index('date', inplace=True)
    df = df.dropna(how='all')
    
    # Compute z-score composite
    if len(df) > 0:
        valid = df[['correlation', 'hhi']].dropna()
        if len(valid) > 0:
            corr_std = valid['correlation'].std()
            hhi_std = valid['hhi'].std()
            
            if corr_std > 0 and hhi_std > 0:
                corr_z = (valid['correlation'] - valid['correlation'].mean()) / corr_std
                hhi_z = (valid['hhi'] - valid['hhi'].mean()) / hhi_std
                z_composite = (corr_z + hhi_z) / 2
            else:
                z_composite = pd.Series(0, index=valid.index)
            
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
                                   date: pd.Timestamp,
                                   window_days: int = 60) -> float:
    """
    Compute average pairwise correlation among tickers over past window_days.
    """
    # Get window ending at this date
    window_start = date - pd.DateOffset(days=window_days)
    window_returns = daily_returns.loc[(daily_returns.index <= date) & 
                                       (daily_returns.index > window_start)]
    
    # Need at least 50% of days
    if len(window_returns) < window_days * 0.5:
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


def prepare_model_data(features: dict, factor_returns: pd.DataFrame, add_lags: bool = False) -> dict:
    """
    Prepare data for modeling by aligning features with forward factor returns.
    
    Parameters
    ----------
    features : dict
        Output from engineer_features()
    factor_returns : pd.DataFrame
        Daily factor returns.
    add_lags : bool
        If True, add 1-week and 2-week lagged features.
    
    Returns
    -------
    dict
        Keys: 'momentum', 'value'
        Each value is a DataFrame with features and forward returns.
    """
    model_data = {}
    
    for factor in ['momentum', 'value']:
        feat_df = features[factor]
        
        if feat_df.empty:
            model_data[factor] = pd.DataFrame()
            continue
        
        forward_returns = []
        
        for date in feat_df.index:
            next_month = date + pd.DateOffset(months=1)
            next_3month = date + pd.DateOffset(months=3)
            
            ret_1m = _get_forward_return(factor_returns[factor], date, next_month)
            ret_3m = _get_forward_return(factor_returns[factor], date, next_3month)
            
            forward_returns.append({
                'date': date,
                'forward_1m': ret_1m,
                'forward_3m': ret_3m
            })
        
        fwd_df = pd.DataFrame(forward_returns)
        fwd_df.set_index('date', inplace=True)
        
        combined = feat_df.join(fwd_df)
        
        # Add lagged features if requested
        if add_lags:
            combined['z_composite_lag1'] = combined['z_composite'].shift(1)
            combined['z_composite_lag2'] = combined['z_composite'].shift(2)
            combined['correlation_lag1'] = combined['correlation'].shift(1)
            combined['hhi_lag1'] = combined['hhi'].shift(1)
        
        combined = combined.dropna()
        model_data[factor] = combined
    
    return model_data




def prepare_multi_target_data(features: dict, factor_returns: pd.DataFrame) -> dict:
    """
    Prepare data with MULTIPLE target definitions in one pass.
    
    Returns dict with:
        - Same features aligned with multiple target definitions
        - All targets available in the same DataFrame
    """
    model_data = {}
    
    for factor in ['momentum', 'value']:
        feat_df = features[factor]
        
        if feat_df.empty:
            model_data[factor] = pd.DataFrame()
            continue
        
        # Get daily factor returns
        factor_ret_series = factor_returns[factor]
        
        target_data = []
        
        for date in feat_df.index:
            # Define various forward horizons
            horizons = {
                'forward_2w': pd.DateOffset(weeks=2),
                'forward_4w': pd.DateOffset(weeks=4),
                'forward_6w': pd.DateOffset(weeks=6),
                'forward_1m': pd.DateOffset(months=1),
                'forward_3m': pd.DateOffset(months=3),
                'forward_6w_ic': pd.DateOffset(weeks=6),   # For Spearman
                'forward_3m_ic': pd.DateOffset(months=3),   # For Spearman
            }
            
            row = {'date': date}
            
            # Raw cumulative returns for each horizon
            for name, offset in horizons.items():
                if 'ic' not in name:  # Raw returns
                    end_date = date + offset
                    ret = _get_forward_return(factor_ret_series, date, end_date)
                    row[name] = ret
            
            # Spearman rank IC (use rolling rank correlation)
            # Use 6-week and 3-month windows
            row['spearman_6w'] = _get_spearman_ic(factor_ret_series, date, pd.DateOffset(weeks=6))
            row['spearman_3m'] = _get_spearman_ic(factor_ret_series, date, pd.DateOffset(months=3))
            
            # Rolling average IC (smoother target)
            row['rolling_ic_3m'] = _get_rolling_ic(factor_ret_series, date, pd.DateOffset(months=3))
            row['rolling_ic_6w'] = _get_rolling_ic(factor_ret_series, date, pd.DateOffset(weeks=6))
            
            target_data.append(row)
        
        targets_df = pd.DataFrame(target_data)
        targets_df.set_index('date', inplace=True)
        
        # Combine features with targets
        combined = feat_df.join(targets_df)
        combined = combined.dropna()
        model_data[factor] = combined
    
    return model_data


def _get_spearman_ic(series: pd.Series, start_date: pd.Timestamp, window: pd.DateOffset) -> float:
    """
    Compute Spearman rank IC over a rolling window.
    Measures consistency of factor returns over time.
    """
    end_date = start_date + window
    try:
        window_returns = series.loc[(series.index > start_date) & (series.index <= end_date)]
        if len(window_returns) < 5:
            return np.nan
        
        # Create ranks
        ranks = window_returns.rank()
        
        # Spearman correlation with time (is performance consistent?)
        time_rank = np.arange(1, len(ranks) + 1)
        spearman = np.corrcoef(ranks.values, time_rank)[0, 1]
        
        return spearman if not np.isnan(spearman) else np.nan
    except:
        return np.nan


def _get_rolling_ic(series: pd.Series, start_date: pd.Timestamp, window: pd.DateOffset) -> float:
    """
    Compute rolling average of forward returns over a window.
    Smoothed target - less noisy.
    """
    end_date = start_date + window
    try:
        returns = series.loc[(series.index > start_date) & (series.index <= end_date)]
        if len(returns) < 5:
            return np.nan
        return returns.mean()
    except:
        return np.nan
    

    


def engineer_transformed_features(prices: pd.DataFrame,
                                   factor_returns: pd.DataFrame,
                                   rebalance_freq: str = 'weekly',
                                   window_days: int = 60,
                                   quintile_pct: float = 0.2) -> dict:
    """
    Generate ALL feature transformations in one pass.
    
    Returns dict with:
        - Each transformed feature as a separate column
        - All features aligned on same dates
    """
    # First, get base features using existing function
    base_features = engineer_features(
        prices, factor_returns, rebalance_freq, window_days, quintile_pct
    )
    
    transformed_features = {}
    
    for factor in ['momentum', 'value']:
        df = base_features[factor].copy()
        
        if df.empty:
            transformed_features[factor] = df
            continue
        
        # Start with raw features
        result = pd.DataFrame(index=df.index)
        result['correlation_raw'] = df['correlation']
        result['hhi_raw'] = df['hhi']
        result['valuation_spread_raw'] = df['valuation_spread']
        
        # --- CORRELATION TRANSFORMS ---
        
        # 1. Squared
        result['correlation_sq'] = df['correlation'] ** 2
        
        # 2. Rolling percentile rank (relative crowding)
        result['correlation_rank'] = df['correlation'].rolling(20, min_periods=5).apply(
            lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) if x.max() > x.min() else 0.5
        )
        
        # 3. Delta (change from 4 weeks ago)
        result['correlation_delta'] = df['correlation'] - df['correlation'].shift(4)
        
        # 4. Rolling standard deviation (stability)
        result['correlation_std'] = df['correlation'].rolling(12, min_periods=5).std()
        
        # --- HHI TRANSFORMS ---
        
        # 5. Log transform
        result['hhi_log'] = np.log(df['hhi'] + 1e-10)
        
        # 6. Rolling percentile rank
        result['hhi_rank'] = df['hhi'].rolling(20, min_periods=5).apply(
            lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) if x.max() > x.min() else 0.5
        )
        
        # 7. HHI delta
        result['hhi_delta'] = df['hhi'] - df['hhi'].shift(4)
        
        # --- INTERACTION TERMS ---
        
        # 8. Correlation × HHI
        result['corr_hhi_interaction'] = df['correlation'] * df['hhi']
        
        # 9. Correlation × Valuation Spread
        result['corr_val_interaction'] = df['correlation'] * df['valuation_spread']
        
        # --- NORMALIZED VERSIONS (for comparison) ---
        
        # 10. Z-score of correlation
        corr_mean = df['correlation'].mean()
        corr_std = df['correlation'].std()
        result['correlation_z'] = (df['correlation'] - corr_mean) / corr_std if corr_std > 0 else 0
        
        # 11. Z-score of HHI
        hhi_mean = df['hhi'].mean()
        hhi_std = df['hhi'].std()
        result['hhi_z'] = (df['hhi'] - hhi_mean) / hhi_std if hhi_std > 0 else 0
        
        # 12. Z-score of valuation spread
        val_mean = df['valuation_spread'].mean()
        val_std = df['valuation_spread'].std()
        result['valuation_spread_z'] = (df['valuation_spread'] - val_mean) / val_std if val_std > 0 else 0
        
        # 13. Z-composite (existing)
        result['z_composite'] = df['z_composite']
        
        # Drop rows with all NaNs
        result = result.dropna(how='all')
        
        transformed_features[factor] = result
    
    return transformed_features




def print_transformed_features_summary(features_transformed: dict):
    """
    Quick summary of what features were generated.
    """
    print("\n" + "="*70)
    print("TRANSFORMED FEATURES SUMMARY")
    print("="*70)
    
    for factor, df in features_transformed.items():
        print(f"\n{factor.upper()} FACTOR:")
        print(f"  Rows: {len(df)}")
        print(f"  Features: {len(df.columns)}")
        print(f"  Feature names: {list(df.columns)}")
        
        # Show first few rows
        print(f"\n  Sample data (first 3 rows):")
        print(df.head(3).to_string())






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
        
        feature_cols = ['correlation', 'hhi', 'valuation_spread', 'z_composite']
        target_cols = ['forward_1m', 'forward_3m']
        
        if 'z_composite_lag1' in df.columns:
            feature_cols.extend(['z_composite_lag1', 'z_composite_lag2'])
        
        corr_matrix = df[feature_cols + target_cols].corr()
        
        print("\n  Correlations with Forward Returns:")
        print(f"  {'Feature':<22} {'→ 1M':>10} {'→ 3M':>10}")
        print("  " + "-"*45)
        for feat in feature_cols:
            if feat in corr_matrix.index:
                corr_1m = corr_matrix.loc[feat, 'forward_1m']
                corr_3m = corr_matrix.loc[feat, 'forward_3m']
                print(f"  {feat:<22} {corr_1m:>10.4f} {corr_3m:>10.4f}")


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