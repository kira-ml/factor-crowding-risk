"""
Batch 2: Target Definition Experiment Runner
Run this file to test different forward horizons and IC definitions.
"""

import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data import load_data
from features import engineer_features, prepare_multi_target_data
from model import run_target_experiment, print_target_experiment_results

def main():
    print("="*80)
    print("BATCH 2: TARGET DEFINITION EXPERIMENT")
    print("="*80)
    
    # 1. Load data
    print("\n" + "-"*60)
    print("1. LOADING DATA")
    print("-"*60)
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    print(f"  Prices: {prices.shape}")
    print(f"  Factor returns: {factor_returns.shape}")
    
    # 2. Engineer transformed features (includes hhi_z, hhi_log, hhi_rank)
    print("\n" + "-"*60)
    print("2. ENGINEERING TRANSFORMED FEATURES")
    print("-"*60)
    from features import engineer_transformed_features
    features = engineer_transformed_features(prices, factor_returns, rebalance_freq='weekly')
    
    # 3. Prepare multi-target data
    print("\n" + "-"*60)
    print("3. PREPARING MULTI-TARGET DATA")
    print("-"*60)
    multi_target_data = prepare_multi_target_data(features, factor_returns)
    
    for factor, df in multi_target_data.items():
        target_cols = [c for c in df.columns if c.startswith('forward_') or 
                       c.startswith('spearman_') or c.startswith('rolling_')]
        print(f"  {factor}: {len(df)} rows, {len(target_cols)} targets")
        print(f"    Targets: {target_cols}")
    
    # 4. Define which features to test (from Batch 1 results)
    features_to_test = {
        'value': ['correlation_raw'],  # Best from Batch 1
        'momentum': ['hhi_z', 'hhi_log', 'hhi_rank']  # Best from Batch 1
    }
    # These names should exist in transformed features
    
    print("\n" + "-"*60)
    print("4. RUNNING EXPERIMENT (Testing all targets)")
    print("-"*60)
    print(f"  Features to test:")
    print(f"    Value: {features_to_test['value']}")
    print(f"    Momentum: {features_to_test['momentum']}")
    
    results = run_target_experiment(multi_target_data, features_to_test)
    
    if results.empty:
        print("❌ No results generated. Check data quality.")
        return
    
    # 5. Print results
    print_target_experiment_results(results)
    
    # 6. Save results
    print("\n" + "-"*60)
    print("5. SAVING RESULTS")
    print("-"*60)
    
    os.makedirs('outputs', exist_ok=True)
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    
    results_path = f'outputs/target_experiment_results_{timestamp}.csv'
    results.to_csv(results_path, index=False)
    print(f"✅ Results saved to: {results_path}")
    
    # Save summary
    summary_path = f'outputs/target_experiment_summary_{timestamp}.txt'
    with open(summary_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("BATCH 2: TARGET DEFINITION RESULTS\n")
        f.write(f"Generated: {pd.Timestamp.now()}\n")
        f.write("="*80 + "\n\n")
        
        # Best per factor
        for factor in ['momentum', 'value']:
            factor_results = results[results['factor'] == factor]
            if not factor_results.empty:
                best = factor_results.loc[factor_results['f1'].idxmax()]
                f.write(f"\n{factor.upper()} - BEST:\n")
                f.write(f"  Feature: {best['feature']}\n")
                f.write(f"  Target: {best['target']}\n")
                f.write(f"  F1: {best['f1']:.4f}\n")
                f.write(f"  R²: {best['r2']:.4f}\n")
    
    print(f"✅ Summary saved to: {summary_path}")
    
    # 7. Final summary
    print("\n" + "="*80)
    print("BATCH 2 COMPLETE")
    print("="*80)
    print("\nKEY QUESTIONS TO ANSWER:")
    print("  1. Which target gives the best F1?")
    print("  2. Does Spearman IC work better than raw returns?")
    print("  3. Do shorter horizons (2w, 4w) have stronger signal?")
    print("  4. Does rolling IC (smoothed) improve R²?")
    print("\nReport back with findings.")

if __name__ == "__main__":
    main()