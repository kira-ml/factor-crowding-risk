"""
Batch 1: Feature Transform Experiment Runner
Run this file to test all feature transformations in one batch.
"""

import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data import load_data
from features import engineer_transformed_features, print_transformed_features_summary
from model import run_feature_transform_experiment, print_feature_experiment_results

def main():
    print("="*80)
    print("BATCH 1: FEATURE TRANSFORM EXPERIMENT")
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
    
    # 2. Generate all transformed features
    print("\n" + "-"*60)
    print("2. GENERATING TRANSFORMED FEATURES")
    print("-"*60)
    features_transformed = engineer_transformed_features(
        prices, factor_returns, rebalance_freq='weekly'
    )
    
    # Print summary
    print_transformed_features_summary(features_transformed)
    
    # 3. Run experiment
    print("\n" + "-"*60)
    print("3. RUNNING EXPERIMENT (Testing all features)")
    print("-"*60)
    results = run_feature_transform_experiment(features_transformed, factor_returns)
    
    if results.empty:
        print("❌ No results generated. Check data quality.")
        return
    
    # 4. Print results
    print_feature_experiment_results(results)
    
    # 5. Save results
    print("\n" + "-"*60)
    print("4. SAVING RESULTS")
    print("-"*60)
    
    # Create outputs directory if it doesn't exist
    os.makedirs('outputs', exist_ok=True)
    
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    results_path = f'outputs/feature_transform_results_{timestamp}.csv'
    results.to_csv(results_path, index=False)
    print(f"✅ Results saved to: {results_path}")
    
    # Also save a summary
    summary_path = f'outputs/feature_transform_summary_{timestamp}.txt'
    with open(summary_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("BATCH 1: FEATURE TRANSFORM RESULTS\n")
        f.write(f"Generated: {pd.Timestamp.now()}\n")
        f.write("="*80 + "\n\n")
        f.write(results.to_string(index=False))
    print(f"✅ Summary saved to: {summary_path}")
    
    # 6. Final summary
    print("\n" + "="*80)
    print("BATCH 1 COMPLETE")
    print("="*80)
    print("\nNEXT STEPS:")
    print("  1. Review results above")
    print("  2. Identify which features improved over correlation_raw")
    print("  3. Report back with findings")
    print("  4. We'll decide whether to proceed to Batch 2 (Target Definitions)")

if __name__ == "__main__":
    main()