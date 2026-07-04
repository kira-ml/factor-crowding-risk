"""
BATCH 3: Combined Level 1 Tests
Tests: Continuous Sizing, Combined Factors, Decision Tree, Ridge/Lasso
All in one efficient run.
"""

import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data import load_data
from features import engineer_transformed_features, prepare_multi_target_data

# Models
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import r2_score

def calc_metrics(returns_series):
    """Calculate Sharpe, drawdown, total return from a Pandas Series."""
    cum = (1 + returns_series).cumprod()
    sharpe = (returns_series.mean() / returns_series.std()) * np.sqrt(52)
    drawdown = (cum / cum.expanding().max() - 1).min()
    total = cum.iloc[-1] - 1
    return sharpe, drawdown, total

def main():
    print("="*80)
    print("BATCH 3: COMBINED LEVEL 1 TESTS")
    print("="*80)
    print("""
    Tests:
    1. Continuous Sizing (Regression → predicted return)
    2. Combined Value + Momentum Portfolio
    3. Decision Tree (Depth 2-3)
    4. Ridge/Lasso with All Features
    """)
    
    # 1. Load data
    print("\n1. LOADING DATA...")
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    
    # 2. Engineer features
    print("\n2. ENGINEERING FEATURES...")
    features = engineer_transformed_features(prices, factor_returns, rebalance_freq='weekly')
    multi_target_data = prepare_multi_target_data(features, factor_returns)
    
    all_results = []
    
    # Get data for each factor
    value_df = multi_target_data['value']
    momentum_df = multi_target_data['momentum']
    
    # Align dates for combined strategy
    common_dates = value_df.index.intersection(momentum_df.index)
    value_df = value_df.loc[common_dates]
    momentum_df = momentum_df.loc[common_dates]
    
    # Factor returns for backtest
    factor_ret_value = factor_returns['value'].loc[common_dates]
    factor_ret_momentum = factor_returns['momentum'].loc[common_dates]
    
    print(f"\n  Common dates: {len(common_dates)}")
    print(f"  Date range: {common_dates[0].strftime('%Y-%m-%d')} to {common_dates[-1].strftime('%Y-%m-%d')}")
    
    # ========================================================================
    # TEST 1: Continuous Sizing (Regression)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 1: CONTINUOUS SIZING (Regression)")
    print("="*80)
    
    factor_configs = {
        'value': {
            'df': value_df,
            'feature': 'correlation_raw',
            'target': 'forward_3m',
            'returns': factor_ret_value,
            'crowding_high_is_bad': True
        },
        'momentum': {
            'df': momentum_df,
            'feature': 'hhi_z',
            'target': 'spearman_6w',
            'returns': factor_ret_momentum,
            'crowding_high_is_bad': True
        }
    }
    
    for factor_name, config in factor_configs.items():
        print(f"\n  {factor_name.upper()} FACTOR")
        
        df = config['df']
        X = df[[config['feature']]].copy()
        y = df[config['target']].copy()
        
        # Split train/test (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Drop NaN
        train_mask = X_train.notna().values.flatten() & y_train.notna().values
        test_mask = X_test.notna().values.flatten() & y_test.notna().values
        
        X_train_clean = X_train[train_mask].values.reshape(-1, 1)
        y_train_clean = y_train[train_mask].values
        X_test_clean = X_test[test_mask].values.reshape(-1, 1)
        y_test_clean = y_test[test_mask].values
        
        if len(X_train_clean) < 50:
            print(f"    Skipping — not enough data")
            continue
        
        # Train Linear Regression
        model = LinearRegression()
        model.fit(X_train_clean, y_train_clean)
        y_pred = model.predict(X_test_clean)
        r2 = r2_score(y_test_clean, y_pred)
        
        print(f"    R²: {r2:.4f}")
        
        # Now apply to full period: continuous sizing
        X_full = X.values.reshape(-1, 1)
        y_pred_full = model.predict(X_full)
        
        # Map predictions to weights
        y_pred_scaled = (y_pred_full - y_pred_full.min()) / (y_pred_full.max() - y_pred_full.min() + 1e-10)
        continuous_weights = 0.7 + 0.3 * y_pred_scaled
        continuous_weights = np.clip(continuous_weights, 0.5, 1.0)
        
        # Apply to returns (as Pandas Series)
        factor_ret = config['returns'].copy()
        dynamic_returns = factor_ret * continuous_weights
        
        # Static returns (baseline)
        static_returns = factor_ret
        
        # Metrics using helper function
        static_sharpe, static_drawdown, static_total = calc_metrics(static_returns)
        dynamic_sharpe, dynamic_drawdown, dynamic_total = calc_metrics(dynamic_returns)
        
        print(f"    Static Sharpe: {static_sharpe:.4f} → Dynamic: {dynamic_sharpe:.4f}")
        print(f"    Static Max DD: {static_drawdown:.2%} → Dynamic: {dynamic_drawdown:.2%}")
        print(f"    Sharpe Δ: {dynamic_sharpe - static_sharpe:+.4f}")
        
        all_results.append({
            'test': 'continuous_sizing',
            'factor': factor_name,
            'sharpe_improvement': dynamic_sharpe - static_sharpe,
            'drawdown_reduction': static_drawdown - dynamic_drawdown,
            'r2': r2
        })
    
    # ========================================================================
    # TEST 2: Combined Value + Momentum Portfolio
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 2: COMBINED VALUE + MOMENTUM PORTFOLIO")
    print("="*80)
    
    # Get features and targets for combined strategy
    value_feature = value_df['correlation_raw']
    momentum_feature = momentum_df['hhi_z']
    
    # 50/50 combined returns
    combined_returns = (factor_ret_value + factor_ret_momentum) / 2
    
    # Crowding flags (75th percentile)
    value_thresh = value_feature.quantile(0.75)
    momentum_thresh = momentum_feature.quantile(0.75)
    
    value_crowded = (value_feature > value_thresh).astype(int)
    momentum_crowded = (momentum_feature > momentum_thresh).astype(int)
    
    # Strategy 1: Static 50/50 portfolio
    static_combined = combined_returns
    
    # Strategy 2: Reduce when EITHER factor is crowded
    either_crowded = (value_crowded | momentum_crowded).astype(int)
    dynamic_weights_combined = 1.0 - (either_crowded * 0.2)  # 20% reduction when crowded
    dynamic_combined = combined_returns * dynamic_weights_combined
    
    # Metrics
    static_sharpe, static_drawdown, static_total = calc_metrics(static_combined)
    dynamic_sharpe, dynamic_drawdown, dynamic_total = calc_metrics(dynamic_combined)
    
    print(f"    Static Sharpe: {static_sharpe:.4f} → Dynamic: {dynamic_sharpe:.4f}")
    print(f"    Static Max DD: {static_drawdown:.2%} → Dynamic: {dynamic_drawdown:.2%}")
    print(f"    Sharpe Δ: {dynamic_sharpe - static_sharpe:+.4f}")
    
    all_results.append({
        'test': 'combined_portfolio',
        'factor': 'value_momentum',
        'sharpe_improvement': dynamic_sharpe - static_sharpe,
        'drawdown_reduction': static_drawdown - dynamic_drawdown,
        'r2': None
    })
    
    # ========================================================================
    # TEST 3: Decision Tree (Depth 2-3)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 3: DECISION TREE (Depth 2-3)")
    print("="*80)
    
    for depth in [2, 3]:
        print(f"\n  Depth: {depth}")
        
        for factor_name, config in factor_configs.items():
            df = config['df']
            X = df[[config['feature']]].copy()
            y = df[config['target']].copy()
            
            # Train on full period (we're testing rules, not forecasting)
            X_clean = X.dropna()
            y_clean = y.loc[X_clean.index]
            
            if len(X_clean) < 50:
                continue
            
            # Train tree
            tree = DecisionTreeRegressor(max_depth=depth, random_state=42)
            tree.fit(X_clean.values.reshape(-1, 1), y_clean.values)
            
            # Get predictions for weights
            y_pred = tree.predict(X_clean.values.reshape(-1, 1))
            
            # Map predictions to weights
            y_pred_scaled = (y_pred - y_pred.min()) / (y_pred.max() - y_pred.min() + 1e-10)
            tree_weights = 0.7 + 0.3 * y_pred_scaled
            tree_weights = np.clip(tree_weights, 0.5, 1.0)
            
            # Apply to returns
            factor_ret = config['returns'].loc[X_clean.index].copy()
            dynamic_returns = factor_ret * tree_weights
            static_returns = factor_ret
            
            static_sharpe, static_drawdown, static_total = calc_metrics(static_returns)
            dynamic_sharpe, dynamic_drawdown, dynamic_total = calc_metrics(dynamic_returns)
            
            print(f"    {factor_name.upper()}: Sharpe Δ = {dynamic_sharpe - static_sharpe:+.4f}")
            
            all_results.append({
                'test': f'decision_tree_depth_{depth}',
                'factor': factor_name,
                'sharpe_improvement': dynamic_sharpe - static_sharpe,
                'drawdown_reduction': static_drawdown - dynamic_drawdown,
                'r2': None
            })
    
    # ========================================================================
    # TEST 4: Ridge/Lasso with All Features
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 4: RIDGE/LASSO WITH ALL FEATURES")
    print("="*80)
    
    for model_name, Model in [('Ridge', Ridge), ('Lasso', Lasso)]:
        print(f"\n  {model_name}")
        
        for factor_name, config in factor_configs.items():
            df = config['df']
            
            # Get all feature columns (exclude targets)
            exclude = ['forward_2w', 'forward_4w', 'forward_6w', 'forward_1m', 'forward_3m',
                       'spearman_6w', 'spearman_3m', 'rolling_ic_3m', 'rolling_ic_6w',
                       'z_composite_lag1', 'z_composite_lag2']
            feature_cols = [c for c in df.columns if c not in exclude]
            
            X = df[feature_cols].copy()
            y = df[config['target']].copy()
            
            # Drop NaN
            valid_mask = X.notna().all(axis=1) & y.notna()
            X_clean = X[valid_mask]
            y_clean = y[valid_mask]
            
            if len(X_clean) < 50:
                continue
            
            # Train/test split
            split_idx = int(len(X_clean) * 0.8)
            X_train, X_test = X_clean.iloc[:split_idx], X_clean.iloc[split_idx:]
            y_train, y_test = y_clean.iloc[:split_idx], y_clean.iloc[split_idx:]
            
            try:
                model = Model(alpha=1.0, random_state=42, max_iter=10000)
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                r2 = r2_score(y_test, y_pred)
                
                # Get feature importance
                coefs = pd.Series(model.coef_, index=feature_cols)
                top_features = coefs.abs().sort_values(ascending=False).head(3)
                
                print(f"    {factor_name.upper()}: R² = {r2:.4f}")
                print(f"      Top features: {dict(top_features)}")
                
                all_results.append({
                    'test': f'{model_name.lower()}_all_features',
                    'factor': factor_name,
                    'sharpe_improvement': None,
                    'drawdown_reduction': None,
                    'r2': r2
                })
            except Exception as e:
                print(f"    {factor_name.upper()}: Failed — {str(e)}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("BATCH 3 SUMMARY")
    print("="*80)
    
    results_df = pd.DataFrame(all_results)
    results_df.to_csv('outputs/batch3_results.csv', index=False)
    print("✅ Results saved to: outputs/batch3_results.csv")
    
    # Trading tests (with Sharpe improvements)
    trading_results = results_df[results_df['sharpe_improvement'].notna()]
    
    if not trading_results.empty:
        print("\nTRADING TESTS (Sharpe Improvement):")
        print("-"*60)
        for _, row in trading_results.sort_values('sharpe_improvement', ascending=False).iterrows():
            status = "✅" if row['sharpe_improvement'] > 0 else "❌"
            print(f"  {status} {row['test']} | {row['factor']} | ΔSharpe: {row['sharpe_improvement']:+.4f}")
    
    # Regression tests
    regression_results = results_df[results_df['r2'].notna()]
    if not regression_results.empty:
        print("\nREGRESSION TESTS (R²):")
        print("-"*60)
        for _, row in regression_results.sort_values('r2', ascending=False).iterrows():
            print(f"  {row['test']} | {row['factor']} | R²: {row['r2']:.4f}")
    
    # Final verdict
    print("\n" + "="*80)
    print("FINAL VERDICT")
    print("="*80)
    
    best_trading = trading_results.loc[trading_results['sharpe_improvement'].idxmax()] if not trading_results.empty else None
    best_regression = regression_results.loc[regression_results['r2'].idxmax()] if not regression_results.empty else None
    
    if best_trading is not None:
        print(f"\nBEST TRADING: {best_trading['test']} | {best_trading['factor']}")
        print(f"  Sharpe Δ: {best_trading['sharpe_improvement']:+.4f}")
    
    if best_regression is not None:
        print(f"\nBEST REGRESSION: {best_regression['test']} | {best_regression['factor']}")
        print(f"  R²: {best_regression['r2']:.4f}")
    
    if best_trading is not None and best_trading['sharpe_improvement'] > 0:
        print("\n✅ FOUND POSITIVE SHARPE IMPROVEMENT!")
    else:
        print("\n❌ NO POSITIVE SHARPE IMPROVEMENT FOUND")
        print("\nRECOMMENDATION:")
        print("  The crowding signal is real (F1 > 0.80) but trading rules based on")
        print("  these simple models don't capture it. This is a valid result.")
        print("  Document honestly and move to visualizations.")

if __name__ == "__main__":
    main()