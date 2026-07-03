"""
Models for Factor Crowding Risk Detection

Implements staged modeling approach from problem_framing.md:

Stage 1: Baseline (Must Complete)
  - Baseline 1: Composite Z-Score + Logistic Regression
  - Baseline 2: Single-Feature Linear Decay Model

Stage 2: Advanced (Conditional on Baseline)
  - Advanced 1: Isolation Forest for Regime Identification
  - Advanced 2: LightGBM for Non-Linear Decay Prediction

Each stage builds on the previous. Advanced models only run if baselines show signal.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    r2_score, mean_squared_error, mean_absolute_error
)
import warnings
warnings.filterwarnings("ignore")

# Optional: LightGBM (only if available)
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("Warning: LightGBM not installed. Advanced 2 will be skipped.")


def run_staged_models(model_data: dict, target: str = 'forward_3m') -> dict:
    """
    Run staged modeling approach as defined in problem_framing.md.
    
    Parameters
    ----------
    model_data : dict
        Output from prepare_model_data() in features.py
    target : str
        'forward_1m' or 'forward_3m' - which forward return to predict
    
    Returns
    -------
    dict
        Results for each stage and model
    """
    results = {
        'stage_1_baseline': {},
        'stage_2_advanced': {}
    }
    
    print(f"\n  Target horizon: {target}")
    
    for factor in ['momentum', 'value']:
        print(f"\n{'='*70}")
        print(f"{factor.upper()} FACTOR - STAGED MODELING")
        print('='*70)
        
        df = model_data[factor]
        if df.empty:
            print("  No data available")
            continue
        
        # Print dataset info
        print(f"\n  Dataset: {len(df)} observations")
        print(f"  Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        
        # Prepare features
        features = ['correlation', 'hhi', 'valuation_spread', 'z_composite']
        X = df[features].copy()
        
        # Targets: use specified forward return
        y_reg = df[target].copy()
        y_class = (y_reg < 0).astype(int)
        
        # Check class balance
        class_balance = y_class.mean()
        print(f"  Class balance (negative returns): {class_balance:.1%}")
        
        # Chronological split (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_reg_train, y_reg_test = y_reg.iloc[:split_idx], y_reg.iloc[split_idx:]
        y_class_train, y_class_test = y_class.iloc[:split_idx], y_class.iloc[split_idx:]
        
        print(f"\n  Train size: {len(X_train)}, Test size: {len(X_test)}")
        print(f"  Train date range: {X_train.index[0].strftime('%Y-%m-%d')} to {X_train.index[-1].strftime('%Y-%m-%d')}")
        print(f"  Test date range: {X_test.index[0].strftime('%Y-%m-%d')} to {X_test.index[-1].strftime('%Y-%m-%d')}")
        
        # --- STAGE 1: BASELINE MODELS ---
        print("\n" + "-"*60)
        print("STAGE 1: BASELINE MODELS")
        print("-"*60)
        
        stage1_results = _run_baseline_models(
            X_train, X_test, y_reg_train, y_reg_test, 
            y_class_train, y_class_test, target
        )
        
        results['stage_1_baseline'][factor] = stage1_results
        
        # Check if baseline shows signal
        baseline_r2 = stage1_results['linear']['r2']
        baseline_f1 = stage1_results['logistic']['f1']
        
        has_signal = (baseline_r2 > 0.0 or baseline_f1 > 0.50)
        
        print(f"\n  Baseline signal check:")
        print(f"    Linear R²: {baseline_r2:.4f}")
        print(f"    Logistic F1: {baseline_f1:.4f}")
        print(f"    Signal detected: {'YES ✅' if has_signal else 'NO ❌'}")
        
        # --- STAGE 2: ADVANCED MODELS (Conditional) ---
        if has_signal:
            print("\n" + "-"*60)
            print("STAGE 2: ADVANCED MODELS (Signal detected, proceeding)")
            print("-"*60)
            
            stage2_results = _run_advanced_models(
                X_train, X_test, y_reg_train, y_reg_test, 
                y_class_train, y_class_test, factor
            )
            
            results['stage_2_advanced'][factor] = stage2_results
        else:
            print("\n" + "-"*60)
            print("STAGE 2: ADVANCED MODELS (Skipped - insufficient baseline signal)")
            print("-"*60)
            results['stage_2_advanced'][factor] = {'skipped': True}
    
    return results


def _run_baseline_models(X_train, X_test, y_reg_train, y_reg_test,
                         y_class_train, y_class_test, target) -> dict:
    """
    Run both baseline models as specified in problem_framing.md.
    """
    results = {}
    
    # --- BASELINE 1: Composite Z-Score + Logistic Regression ---
    print("\n  BASELINE 1: Composite Z-Score + Logistic Regression")
    print("  ---------------------------------------------------")
    print(f"  Predicting: Negative {target} factor return")
    print("  Feature: Z-Composite (avg of normalized Correlation + HHI)")
    
    # Use only Z-Composite feature
    X_train_z = X_train[['z_composite']].copy()
    X_test_z = X_test[['z_composite']].copy()
    
    log_model = LogisticRegression(random_state=42, max_iter=1000)
    log_model.fit(X_train_z, y_class_train)
    
    y_pred = log_model.predict(X_test_z)
    y_pred_proba = log_model.predict_proba(X_test_z)[:, 1]
    
    log_metrics = {
        'accuracy': accuracy_score(y_class_test, y_pred),
        'precision': precision_score(y_class_test, y_pred, zero_division=0),
        'recall': recall_score(y_class_test, y_pred, zero_division=0),
        'f1': f1_score(y_class_test, y_pred, zero_division=0),
        'coef': log_model.coef_[0][0],
        'intercept': log_model.intercept_[0]
    }
    
    print(f"    Accuracy:  {log_metrics['accuracy']:.4f}")
    print(f"    Precision: {log_metrics['precision']:.4f}")
    print(f"    Recall:    {log_metrics['recall']:.4f}")
    print(f"    F1 Score:  {log_metrics['f1']:.4f}")
    print(f"    Coefficient: {log_metrics['coef']:.4f}")
    
    results['logistic'] = log_metrics
    results['logistic_model'] = log_model
    
    # --- BASELINE 2: Single-Feature Linear Decay Model ---
    print("\n  BASELINE 2: Single-Feature Linear Decay Model")
    print("  ---------------------------------------------")
    print(f"  Predicting: {target} forward factor return")
    print("  Feature: Pairwise Correlation")
    
    # Use only Correlation feature
    X_train_corr = X_train[['correlation']].copy()
    X_test_corr = X_test[['correlation']].copy()
    
    lin_model = LinearRegression()
    lin_model.fit(X_train_corr, y_reg_train)
    
    y_pred = lin_model.predict(X_test_corr)
    
    lin_metrics = {
        'r2': r2_score(y_reg_test, y_pred),
        'mse': mean_squared_error(y_reg_test, y_pred),
        'rmse': np.sqrt(mean_squared_error(y_reg_test, y_pred)),
        'mae': mean_absolute_error(y_reg_test, y_pred),
        'coef': lin_model.coef_[0],
        'intercept': lin_model.intercept_
    }
    
    print(f"    R²:       {lin_metrics['r2']:.4f}")
    print(f"    RMSE:     {lin_metrics['rmse']:.6f}")
    print(f"    MAE:      {lin_metrics['mae']:.6f}")
    print(f"    Coefficient: {lin_metrics['coef']:.4f}")
    
    results['linear'] = lin_metrics
    results['linear_model'] = lin_model
    
    return results


def _run_advanced_models(X_train, X_test, y_reg_train, y_reg_test,
                         y_class_train, y_class_test, factor) -> dict:
    """
    Run advanced models (conditional on baseline signal).
    """
    results = {}
    
    # --- ADVANCED 1: Isolation Forest for Regime Identification ---
    print("\n  ADVANCED 1: Isolation Forest for Regime Identification")
    print("  -----------------------------------------------------")
    print("  Hypothesis: Crowding matters most in extreme regimes")
    
    # Train Isolation Forest on full feature space
    iso_model = IsolationForest(
        contamination=0.15,  # Expect ~15% crowded regimes
        random_state=42,
        n_estimators=100
    )
    
    # Fit on all training data
    iso_model.fit(X_train)
    
    # Predict anomalies (crowded regimes)
    train_pred = iso_model.predict(X_train)
    test_pred = iso_model.predict(X_test)
    
    # Convert to binary: -1 = anomaly (crowded), 1 = normal
    train_anomaly = (train_pred == -1).astype(int)
    test_anomaly = (test_pred == -1).astype(int)
    
    # Evaluate: Compare crowded vs normal regime forward returns
    train_crowded_returns = y_reg_train[train_anomaly == 1]
    train_normal_returns = y_reg_train[train_anomaly == 0]
    test_crowded_returns = y_reg_test[test_anomaly == 1]
    test_normal_returns = y_reg_test[test_anomaly == 0]
    
    # Calculate mean returns for each regime
    results['isolation_forest'] = {
        'train_crowded_mean': train_crowded_returns.mean() if len(train_crowded_returns) > 0 else np.nan,
        'train_normal_mean': train_normal_returns.mean() if len(train_normal_returns) > 0 else np.nan,
        'test_crowded_mean': test_crowded_returns.mean() if len(test_crowded_returns) > 0 else np.nan,
        'test_normal_mean': test_normal_returns.mean() if len(test_normal_returns) > 0 else np.nan,
        'train_crowded_count': len(train_crowded_returns),
        'test_crowded_count': len(test_crowded_returns),
        'n_anomalies': (test_pred == -1).sum(),
        'anomaly_rate': (test_pred == -1).mean()
    }
    
    print(f"    Test anomaly rate: {results['isolation_forest']['anomaly_rate']:.2%}")
    print(f"    Test crowded mean return: {results['isolation_forest']['test_crowded_mean']:.6f}")
    print(f"    Test normal mean return: {results['isolation_forest']['test_normal_mean']:.6f}")
    
    # Calculate regime difference
    regime_diff = (results['isolation_forest']['test_normal_mean'] - 
                   results['isolation_forest']['test_crowded_mean'])
    print(f"    Regime difference (Normal - Crowded): {regime_diff:.6f}")
    
    results['isolation_forest_model'] = iso_model
    
    # --- ADVANCED 2: LightGBM for Non-Linear Decay Prediction ---
    if LIGHTGBM_AVAILABLE:
        print("\n  ADVANCED 2: LightGBM for Non-Linear Decay Prediction")
        print("  --------------------------------------------------")
        print("  Hypothesis: Non-linear interactions matter for crowding")
        
        # Train LightGBM on all features
        lgb_model = lgb.LGBMRegressor(
            n_estimators=100,
            learning_rate=0.1,
            num_leaves=31,
            random_state=42,
            verbosity=-1
        )
        
        lgb_model.fit(X_train, y_reg_train)
        
        y_pred = lgb_model.predict(X_test)
        
        lgb_metrics = {
            'r2': r2_score(y_reg_test, y_pred),
            'mse': mean_squared_error(y_reg_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_reg_test, y_pred)),
            'mae': mean_absolute_error(y_reg_test, y_pred),
            'feature_importance': dict(zip(X_train.columns, lgb_model.feature_importances_))
        }
        
        print(f"    R²:       {lgb_metrics['r2']:.4f}")
        print(f"    RMSE:     {lgb_metrics['rmse']:.6f}")
        print(f"    MAE:      {lgb_metrics['mae']:.6f}")
        print(f"    Feature Importance:")
        for feat, imp in sorted(lgb_metrics['feature_importance'].items(), 
                               key=lambda x: x[1], reverse=True):
            print(f"      {feat}: {imp:.0f}")
        
        results['lightgbm'] = lgb_metrics
        results['lightgbm_model'] = lgb_model
    else:
        print("\n  ADVANCED 2: LightGBM (Skipped - library not installed)")
        results['lightgbm'] = {'skipped': True}
    
    return results


def create_stage_comparison_table(results: dict) -> pd.DataFrame:
    """
    Create comparison table across all stages.
    """
    rows = []
    
    # Stage 1: Baseline
    for factor, factor_results in results['stage_1_baseline'].items():
        if isinstance(factor_results, dict):
            row = {
                'Stage': 'Stage 1: Baseline',
                'Factor': factor.upper(),
                'Model': 'Logistic (Z-Composite)',
                'Metric': 'F1 Score',
                'Value': factor_results.get('logistic', {}).get('f1', np.nan)
            }
            rows.append(row)
            
            row = {
                'Stage': 'Stage 1: Baseline',
                'Factor': factor.upper(),
                'Model': 'Linear (Correlation)',
                'Metric': 'R²',
                'Value': factor_results.get('linear', {}).get('r2', np.nan)
            }
            rows.append(row)
    
    # Stage 2: Advanced
    for factor, factor_results in results['stage_2_advanced'].items():
        if isinstance(factor_results, dict) and not factor_results.get('skipped', False):
            # Isolation Forest
            if 'isolation_forest' in factor_results:
                iso = factor_results['isolation_forest']
                row = {
                    'Stage': 'Stage 2: Advanced',
                    'Factor': factor.upper(),
                    'Model': 'Isolation Forest',
                    'Metric': 'Regime Diff',
                    'Value': iso.get('test_normal_mean', 0) - iso.get('test_crowded_mean', 0)
                }
                rows.append(row)
            
            # LightGBM
            if 'lightgbm' in factor_results and isinstance(factor_results['lightgbm'], dict):
                if not factor_results['lightgbm'].get('skipped', False):
                    row = {
                        'Stage': 'Stage 2: Advanced',
                        'Factor': factor.upper(),
                        'Model': 'LightGBM',
                        'Metric': 'R²',
                        'Value': factor_results['lightgbm'].get('r2', np.nan)
                    }
                    rows.append(row)
        elif isinstance(factor_results, dict) and factor_results.get('skipped', False):
            row = {
                'Stage': 'Stage 2: Advanced',
                'Factor': factor.upper(),
                'Model': 'Skipped',
                'Metric': 'Reason',
                'Value': 'Insufficient baseline signal'
            }
            rows.append(row)
    
    return pd.DataFrame(rows)


def print_summary_report(results: dict):
    """
    Print a comprehensive summary report.
    """
    print("\n" + "="*70)
    print("STAGED MODELING SUMMARY REPORT")
    print("="*70)
    
    # Stage 1 Summary
    print("\n" + "-"*70)
    print("STAGE 1: BASELINE MODELS")
    print("-"*70)
    
    for factor in ['momentum', 'value']:
        if factor in results['stage_1_baseline']:
            factor_results = results['stage_1_baseline'][factor]
            print(f"\n{factor.upper()} FACTOR:")
            print(f"  Logistic (Z-Composite): F1 = {factor_results['logistic']['f1']:.4f}")
            print(f"  Linear (Correlation):   R²  = {factor_results['linear']['r2']:.4f}")
    
    # Stage 2 Summary
    print("\n" + "-"*70)
    print("STAGE 2: ADVANCED MODELS")
    print("-"*70)
    
    for factor in ['momentum', 'value']:
        if factor in results['stage_2_advanced']:
            factor_results = results['stage_2_advanced'][factor]
            print(f"\n{factor.upper()} FACTOR:")
            
            if factor_results.get('skipped', False):
                print("  Advanced models skipped (insufficient baseline signal)")
            else:
                if 'isolation_forest' in factor_results:
                    iso = factor_results['isolation_forest']
                    diff = iso['test_normal_mean'] - iso['test_crowded_mean']
                    print(f"  Isolation Forest: Regime Diff = {diff:.6f}")
                    print(f"    Crowded mean: {iso['test_crowded_mean']:.6f}")
                    print(f"    Normal mean:  {iso['test_normal_mean']:.6f}")
                    print(f"    Anomaly rate: {iso['anomaly_rate']:.2%}")
                
                if 'lightgbm' in factor_results and isinstance(factor_results['lightgbm'], dict):
                    lgb = factor_results['lightgbm']
                    if not lgb.get('skipped', False):
                        print(f"  LightGBM: R² = {lgb['r2']:.4f}")
                        print("    Feature Importance:")
                        for feat, imp in sorted(lgb.get('feature_importance', {}).items(),
                                               key=lambda x: x[1], reverse=True):
                            print(f"      {feat}: {imp:.0f}")
    
    # Overall Conclusion
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    
    # Check if advanced models improved over baselines
    improvements = []
    
    for factor in ['momentum', 'value']:
        if factor in results['stage_1_baseline'] and factor in results['stage_2_advanced']:
            baseline_r2 = results['stage_1_baseline'][factor]['linear']['r2']
            
            if not results['stage_2_advanced'][factor].get('skipped', False):
                advanced_r2 = results['stage_2_advanced'][factor].get('lightgbm', {}).get('r2', 0)
                improvement = advanced_r2 - baseline_r2
                improvements.append(improvement)
                
                print(f"\n{factor.upper()}:")
                print(f"  Baseline R²:  {baseline_r2:.4f}")
                print(f"  Advanced R²:  {advanced_r2:.4f}")
                print(f"  Improvement:  {improvement:.4f}")
                
                if improvement > 0.01:
                    print(f"  ✓ Advanced models show meaningful improvement")
                elif improvement > 0:
                    print(f"  △ Advanced models show slight improvement")
                else:
                    print(f"  ✗ Advanced models did not improve over baselines")
    
    # Overall verdict
    print("\n" + "-"*70)
    print("OVERALL VERDICT")
    print("-"*70)
    
    avg_improvement = np.mean(improvements) if improvements else 0
    
    if avg_improvement > 0.01:
        print("✓ The crowding signal is real and advanced models add value")
        print("  Recommendation: Proceed with crowding-aware portfolio allocation")
    elif avg_improvement > 0:
        print("△ The crowding signal is present but simple models capture it well")
        print("  Recommendation: Use baseline models for interpretability")
    else:
        print("✗ The crowding signal is weak or absent in this dataset")
        print("  Recommendation: Re-evaluate feature engineering or data quality")


# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Load data and engineer features
    from data import load_data
    from features import engineer_features, prepare_model_data
    
    print("="*70)
    print("FACTOR CROWDING RISK - STAGED MODELING PIPELINE")
    print("="*70)
    
    print("\n1. Loading data...")
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    
    print("\n2. Engineering features (weekly rebalancing)...")
    features = engineer_features(prices, factor_returns, rebalance_freq='weekly')
    model_data = prepare_model_data(features, factor_returns)
    
    print("\n3. Running staged models...")
    
    # Test both 1M and 3M targets
    for target in ['forward_1m', 'forward_3m']:
        print("\n" + "="*70)
        print(f"TARGET: {target}")
        print("="*70)
        results = run_staged_models(model_data, target=target)
        
        print("\n4. Creating comparison table...")
        comparison_df = create_stage_comparison_table(results)
        if not comparison_df.empty:
            print("\n" + comparison_df.to_string(index=False))
        
        print("\n5. Generating summary report...")
        print_summary_report(results)
        
        # Save outputs
        if not comparison_df.empty:
            import os
            os.makedirs('../outputs', exist_ok=True)
            comparison_df.to_csv(f'../outputs/staged_model_comparison_{target}.csv', index=False)
            print(f"\nResults saved to: outputs/staged_model_comparison_{target}.csv")
    
    print("\n" + "="*70)
    print("ALL EXPERIMENTS COMPLETE")
    print("="*70)