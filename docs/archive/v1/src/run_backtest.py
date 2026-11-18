"""
Day 2: Backtest Implementation
Tests crowding-aware strategy vs static allocation for both factors.
"""

import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data import load_data
from features import engineer_transformed_features, prepare_multi_target_data

def main():
    print("="*80)
    print("BACKTEST: CROWDING-AWARE VS STATIC STRATEGY")
    print("="*80)
    
    # 1. Load data
    print("\n1. LOADING DATA...")
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    
    # 2. Engineer features
    print("\n2. ENGINEERING FEATURES...")
    features = engineer_transformed_features(prices, factor_returns, rebalance_freq='weekly')
    multi_target_data = prepare_multi_target_data(features, factor_returns)
    
    # 3. Define which features and targets to use (from Batch 1 & 2 results)
    factor_configs = {
        'value': {
            'feature': 'correlation_raw',
            'target': 'forward_3m',  # Best from Batch 2
            'crowding_high_is_bad': True  # High correlation = high crowding = bad
        },
        'momentum': {
            'feature': 'hhi_z',
            'target': 'spearman_6w',  # Best from Batch 2
            'crowding_high_is_bad': True  # High HHI = high crowding = bad
        }
    }
    
    thresholds = [0.70, 0.75, 0.80]  # Test all 3 at once
    
    all_results = []
    
    for factor, config in factor_configs.items():
        print(f"\n{'='*80}")
        print(f"{factor.upper()} FACTOR")
        print('='*80)
        
        df = multi_target_data[factor]
        if df.empty:
            continue
        
        feature_col = config['feature']
        target_col = config['target']
        
        # Get feature and target
        X = df[feature_col]
        y = df[target_col]  # Forward returns
        
        # Get weekly factor returns for cumulative calculation
        factor_ret_series = factor_returns[factor]
        
        # Align dates
        valid_dates = df.index.intersection(factor_ret_series.index)
        X = X.loc[valid_dates]
        y = y.loc[valid_dates]
        factor_ret_series = factor_ret_series.loc[valid_dates]
        
        print(f"  Observations: {len(X)}")
        print(f"  Date range: {X.index[0].strftime('%Y-%m-%d')} to {X.index[-1].strftime('%Y-%m-%d')}")
        print(f"  Feature: {feature_col}")
        print(f"  Target: {target_col}")
        
        for threshold in thresholds:
            print(f"\n  Threshold: {threshold*100:.0f}th percentile")
            
            # Calculate threshold
            thresh_value = X.quantile(threshold)
            
            # Crowding flag: 1 = crowded (reduce exposure)
            if config['crowding_high_is_bad']:
                crowding_flag = (X > thresh_value).astype(int)
            else:
                crowding_flag = (X < thresh_value).astype(int)
            
            # Strategy 1: Static (always 100% invested)
            static_returns = factor_ret_series
            
            # Strategy 2: Crowding-Aware (50% when crowded)
            dynamic_weights = 1.0 - (crowding_flag * 0.5)  # 1.0 when not crowded, 0.5 when crowded
            dynamic_returns = factor_ret_series * dynamic_weights
            
            # Calculate metrics
            static_cum = (1 + static_returns).cumprod()
            dynamic_cum = (1 + dynamic_returns).cumprod()
            
            static_total = static_cum.iloc[-1] - 1
            dynamic_total = dynamic_cum.iloc[-1] - 1
            
            static_sharpe = (static_returns.mean() / static_returns.std()) * np.sqrt(52)
            dynamic_sharpe = (dynamic_returns.mean() / dynamic_returns.std()) * np.sqrt(52)
            
            static_drawdown = (static_cum / static_cum.expanding().max() - 1).min()
            dynamic_drawdown = (dynamic_cum / dynamic_cum.expanding().max() - 1).min()
            
            static_vol = static_returns.std() * np.sqrt(52)
            dynamic_vol = dynamic_returns.std() * np.sqrt(52)
            
            # Number of crowded periods
            crowded_pct = crowding_flag.mean()
            
            # Store results
            results_row = {
                'factor': factor.upper(),
                'threshold': threshold,
                'crowded_pct': crowded_pct,
                'static_total_return': static_total,
                'dynamic_total_return': dynamic_total,
                'static_sharpe': static_sharpe,
                'dynamic_sharpe': dynamic_sharpe,
                'static_max_drawdown': static_drawdown,
                'dynamic_max_drawdown': dynamic_drawdown,
                'static_volatility': static_vol,
                'dynamic_volatility': dynamic_vol,
                'sharpe_improvement': dynamic_sharpe - static_sharpe,
                'drawdown_reduction': static_drawdown - dynamic_drawdown,  # Positive = better
                'return_improvement': dynamic_total - static_total,
            }
            
            all_results.append(results_row)
            
            # Print summary
            print(f"    Crowded periods: {crowded_pct:.1%}")
            print(f"    Static Sharpe: {static_sharpe:.4f} | Dynamic Sharpe: {dynamic_sharpe:.4f}")
            print(f"    Static Max DD: {static_drawdown:.2%} | Dynamic Max DD: {dynamic_drawdown:.2%}")
            print(f"    Static Total: {static_total:.2%} | Dynamic Total: {dynamic_total:.2%}")
            print(f"    ✅ Sharpe Improvement: {results_row['sharpe_improvement']:.4f}")
            print(f"    ✅ Drawdown Reduction: {results_row['drawdown_reduction']:.2%}")
    
    # 4. Create summary table
    print("\n" + "="*80)
    print("SUMMARY — BEST CONFIGURATION BY FACTOR")
    print("="*80)
    
    results_df = pd.DataFrame(all_results)
    results_df.to_csv('outputs/backtest_results.csv', index=False)
    print("✅ Results saved to: outputs/backtest_results.csv")
    
    # Find best for each factor
    for factor in ['VALUE', 'MOMENTUM']:
        factor_results = results_df[results_df['factor'] == factor]
        if not factor_results.empty:
            best_sharpe = factor_results.loc[factor_results['sharpe_improvement'].idxmax()]
            print(f"\n{factor}:")
            print(f"  Best Threshold: {best_sharpe['threshold']*100:.0f}th percentile")
            print(f"  Sharpe Improvement: {best_sharpe['sharpe_improvement']:.4f}")
            print(f"  Drawdown Reduction: {best_sharpe['drawdown_reduction']:.2%}")
            print(f"  Crowded Periods: {best_sharpe['crowded_pct']:.1%}")
    
    # 5. Save detailed summary
    print("\n" + "="*80)
    print("FINAL RECOMMENDATION")
    print("="*80)
    
    # Pick best overall
    best_overall = results_df.loc[results_df['sharpe_improvement'].idxmax()]
    
    print(f"""
    FACTOR: {best_overall['factor']}
    THRESHOLD: {best_overall['threshold']*100:.0f}th percentile
    
    METRICS:
      Static Sharpe:  {best_overall['static_sharpe']:.4f}
      Dynamic Sharpe: {best_overall['dynamic_sharpe']:.4f}
      Sharpe Improvement: {best_overall['sharpe_improvement']:.4f}
      
      Static Max DD:  {best_overall['static_max_drawdown']:.2%}
      Dynamic Max DD: {best_overall['dynamic_max_drawdown']:.2%}
      Drawdown Reduction: {best_overall['drawdown_reduction']:.2%}
      
      Static Total Return:  {best_overall['static_total_return']:.2%}
      Dynamic Total Return: {best_overall['dynamic_total_return']:.2%}
      
    CONCLUSION:
    {'✅ CROWDING-AWARE STRATEGY OUTPERFORMS STATIC' if best_overall['sharpe_improvement'] > 0 else '❌ NO IMPROVEMENT'}
    """)

if __name__ == "__main__":
    main()