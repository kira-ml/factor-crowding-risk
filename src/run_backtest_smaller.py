"""
Day 2: Backtest with Smaller Position Reductions
Tests 10%, 20%, 30% reductions instead of 50%.
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
    print("BACKTEST: SMALLER POSITION REDUCTIONS (10%, 20%, 30%)")
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
    
    # 3. Define configurations
    factor_configs = {
        'value': {
            'feature': 'correlation_raw',
            'target': 'forward_3m',
            'crowding_high_is_bad': True
        },
        'momentum': {
            'feature': 'hhi_z',
            'target': 'spearman_6w',
            'crowding_high_is_bad': True
        }
    }
    
    # Test smaller reductions
    reductions = [0.10, 0.20, 0.30]  # 10%, 20%, 30% instead of 50%
    thresholds = [0.70, 0.75, 0.80]
    
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
        
        X = df[feature_col]
        y = df[target_col]
        factor_ret_series = factor_returns[factor]
        
        valid_dates = df.index.intersection(factor_ret_series.index)
        X = X.loc[valid_dates]
        y = y.loc[valid_dates]
        factor_ret_series = factor_ret_series.loc[valid_dates]
        
        print(f"  Observations: {len(X)}")
        print(f"  Feature: {feature_col}")
        print(f"  Target: {target_col}")
        
        for threshold in thresholds:
            for reduction in reductions:
                print(f"\n  Threshold: {threshold*100:.0f}th | Reduction: {reduction*100:.0f}%")
                
                thresh_value = X.quantile(threshold)
                
                if config['crowding_high_is_bad']:
                    crowding_flag = (X > thresh_value).astype(int)
                else:
                    crowding_flag = (X < thresh_value).astype(int)
                
                # Static strategy
                static_returns = factor_ret_series
                
                # Dynamic: reduce by X% when crowded
                dynamic_weights = 1.0 - (crowding_flag * reduction)
                dynamic_returns = factor_ret_series * dynamic_weights
                
                # Metrics
                static_cum = (1 + static_returns).cumprod()
                dynamic_cum = (1 + dynamic_returns).cumprod()
                
                static_total = static_cum.iloc[-1] - 1
                dynamic_total = dynamic_cum.iloc[-1] - 1
                
                static_sharpe = (static_returns.mean() / static_returns.std()) * np.sqrt(52)
                dynamic_sharpe = (dynamic_returns.mean() / dynamic_returns.std()) * np.sqrt(52)
                
                static_drawdown = (static_cum / static_cum.expanding().max() - 1).min()
                dynamic_drawdown = (dynamic_cum / dynamic_cum.expanding().max() - 1).min()
                
                crowded_pct = crowding_flag.mean()
                
                results_row = {
                    'factor': factor.upper(),
                    'threshold': threshold,
                    'reduction': reduction,
                    'crowded_pct': crowded_pct,
                    'static_total': static_total,
                    'dynamic_total': dynamic_total,
                    'static_sharpe': static_sharpe,
                    'dynamic_sharpe': dynamic_sharpe,
                    'static_max_dd': static_drawdown,
                    'dynamic_max_dd': dynamic_drawdown,
                    'sharpe_improvement': dynamic_sharpe - static_sharpe,
                    'drawdown_reduction': static_drawdown - dynamic_drawdown,
                }
                
                all_results.append(results_row)
                
                print(f"    Static Sharpe: {static_sharpe:.4f} → Dynamic: {dynamic_sharpe:.4f}")
                print(f"    Static Max DD: {static_drawdown:.2%} → Dynamic: {dynamic_drawdown:.2%}")
                print(f"    Sharpe Δ: {results_row['sharpe_improvement']:+.4f}")
    
    # 4. Summary
    print("\n" + "="*80)
    print("SUMMARY — BEST CONFIGURATION BY FACTOR")
    print("="*80)
    
    results_df = pd.DataFrame(all_results)
    results_df.to_csv('outputs/backtest_smaller_results.csv', index=False)
    print("✅ Results saved to: outputs/backtest_smaller_results.csv")
    
    for factor in ['VALUE', 'MOMENTUM']:
        factor_results = results_df[results_df['factor'] == factor]
        if not factor_results.empty:
            best = factor_results.loc[factor_results['sharpe_improvement'].idxmax()]
            print(f"\n{factor}:")
            print(f"  Best Threshold: {best['threshold']*100:.0f}th")
            print(f"  Best Reduction: {best['reduction']*100:.0f}%")
            print(f"  Sharpe Δ: {best['sharpe_improvement']:+.4f}")
            print(f"  Drawdown Δ: {best['drawdown_reduction']:+.2%}")
            print(f"  Crowded Periods: {best['crowded_pct']:.1%}")
    
    # 5. Final verdict
    print("\n" + "="*80)
    print("FINAL VERDICT")
    print("="*80)
    
    best_overall = results_df.loc[results_df['sharpe_improvement'].idxmax()]
    
    if best_overall['sharpe_improvement'] > 0:
        print(f"""
✅ SUCCESS!
   Factor: {best_overall['factor']}
   Threshold: {best_overall['threshold']*100:.0f}th
   Reduction: {best_overall['reduction']*100:.0f}%
   Sharpe Improvement: {best_overall['sharpe_improvement']:+.4f}
   Drawdown Reduction: {best_overall['drawdown_reduction']:+.2%}
        """)
    else:
        print(f"""
❌ NO IMPROVEMENT FOUND
   Best Sharpe Δ: {best_overall['sharpe_improvement']:+.4f}
   Best Drawdown Δ: {best_overall['drawdown_reduction']:+.2%}
   
   RECOMMENDATION:
   The crowding signal is real (F1 > 0.80) but simple rules don't capture it.
   Consider:
   1. Using regression instead of classification
   2. Combining multiple features
   3. Documenting the honest result
        """)

if __name__ == "__main__":
    main()