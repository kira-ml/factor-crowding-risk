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


import os
import json
from datetime import datetime

def setup_logging():
    """Create outputs directory and log file with timestamp."""
    os.makedirs('../outputs', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return timestamp



def save_results(results_dict: dict, timestamp: str):
    """
    Save all results to CSV, JSON, and TXT files.
    """
    # 1. Save as CSV
    results_df = create_results_dataframe(results_dict)
    csv_path = f'../outputs/model_results_{timestamp}.csv'
    results_df.to_csv(csv_path, index=False)
    print(f"\n✅ CSV saved: {csv_path}")
    
    # 2. Save as JSON (full results)
    json_path = f'../outputs/model_results_{timestamp}.json'
    with open(json_path, 'w') as f:
        json.dump(results_dict, f, indent=2, default=str)
    print(f"✅ JSON saved: {json_path}")
    
    # 3. Save as TXT (human readable summary)
    txt_path = f'../outputs/model_summary_{timestamp}.txt'
    with open(txt_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("FACTOR CROWDING RISK - MODEL RESULTS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        f.write(results_df.to_string(index=False))
        f.write("\n\n" + "="*80 + "\n")
        f.write("DETAILED RESULTS\n")
        f.write("="*80 + "\n\n")
        
        for key, value in results_dict.items():
            if isinstance(value, dict):
                f.write(f"\n{key.upper()}:\n")
                f.write("-"*40 + "\n")
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, dict):
                        f.write(f"  {subkey}:\n")
                        for k, v in subvalue.items():
                            if isinstance(v, (int, float)):
                                f.write(f"    {k}: {v:.4f}\n")
                            else:
                                f.write(f"    {k}: {v}\n")
                    else:
                        f.write(f"  {subkey}: {subvalue}\n")
    
    print(f"✅ TXT saved: {txt_path}")








def run_staged_models(model_data: dict, 
                      target: str = 'forward_1m', 
                      feature_set: str = 'z_composite',
                      train_ratio: float = 0.8,
                      use_expanding: bool = False) -> dict:
    """
    Run staged modeling approach as defined in problem_framing.md.
    
    Parameters
    ----------
    model_data : dict
        Output from prepare_model_data() in features.py
    target : str
        'forward_1m' or 'forward_3m'
    feature_set : str
        'z_composite', 'correlation', 'hhi', 'valuation_spread', 
        'all', 'correlation_hhi', 'correlation_valuation', 'hhi_valuation'
    train_ratio : float
        0.8 (80/20), 0.7 (70/30), 0.6 (60/40)
    use_expanding : bool
        If True, use expanding window validation instead of single split
    """
    feature_sets = {
        'z_composite': ['z_composite'],
        'correlation': ['correlation'],
        'hhi': ['hhi'],
        'valuation_spread': ['valuation_spread'],
        'all': ['correlation', 'hhi', 'valuation_spread', 'z_composite'],
        'correlation_hhi': ['correlation', 'hhi'],
        'correlation_valuation': ['correlation', 'valuation_spread'],
        'hhi_valuation': ['hhi', 'valuation_spread']
    }
    
    if feature_set not in feature_sets:
        feature_set = 'z_composite'
    
    features_to_use = feature_sets[feature_set]
    
    results = {
        'stage_1_baseline': {},
        'stage_2_advanced': {}
    }
    
    print(f"\n  Target: {target}")
    print(f"  Feature Set: {feature_set} ({len(features_to_use)} features)")
    print(f"  Train Ratio: {train_ratio*100:.0f}/{100-train_ratio*100:.0f}")
    print(f"  Expanding Window: {use_expanding}")
    
    for factor in ['momentum', 'value']:
        print(f"\n{'='*70}")
        print(f"{factor.upper()} FACTOR - STAGED MODELING")
        print('='*70)
        
        df = model_data[factor]
        if df.empty:
            print("  No data available")
            continue
        
        print(f"\n  Dataset: {len(df)} observations")
        print(f"  Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        
        X = df[features_to_use].copy()
        y_reg = df[target].copy()
        y_class = (y_reg < 0).astype(int)
        
        print(f"  Class balance (negative returns): {y_class.mean():.1%}")
        
        if use_expanding:
            stage1_results = _run_expanding_window_models(
                X, y_reg, y_class, target, features_to_use
            )
        else:
            split_idx = int(len(X) * train_ratio)
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_reg_train, y_reg_test = y_reg.iloc[:split_idx], y_reg.iloc[split_idx:]
            y_class_train, y_class_test = y_class.iloc[:split_idx], y_class.iloc[split_idx:]
            
            print(f"\n  Train size: {len(X_train)}, Test size: {len(X_test)}")
            print(f"  Train date range: {X_train.index[0].strftime('%Y-%m-%d')} to {X_train.index[-1].strftime('%Y-%m-%d')}")
            print(f"  Test date range: {X_test.index[0].strftime('%Y-%m-%d')} to {X_test.index[-1].strftime('%Y-%m-%d')}")
            
            print("\n" + "-"*60)
            print("STAGE 1: BASELINE MODELS")
            print("-"*60)
            
            stage1_results = _run_baseline_models(
                X_train, X_test, y_reg_train, y_reg_test, 
                y_class_train, y_class_test, target, features_to_use
            )
        
        results['stage_1_baseline'][factor] = stage1_results
        
        if use_expanding:
            baseline_r2 = stage1_results['linear']['r2_median']
            baseline_f1 = stage1_results['logistic']['f1_median']
        else:
            baseline_r2 = stage1_results['linear']['r2']
            baseline_f1 = stage1_results['logistic']['f1']
        
        has_signal = (baseline_r2 > 0.0 or baseline_f1 > 0.50)
        
        print(f"\n  Baseline signal check:")
        print(f"    Linear R²: {baseline_r2:.4f}")
        print(f"    Logistic F1: {baseline_f1:.4f}")
        print(f"    Signal detected: {'YES ✅' if has_signal else 'NO ❌'}")
        
        if has_signal and not use_expanding:
            print("\n" + "-"*60)
            print("STAGE 2: ADVANCED MODELS (Signal detected, proceeding)")
            print("-"*60)
            
            stage2_results = _run_advanced_models(
                X_train, X_test, y_reg_train, y_reg_test, 
                y_class_train, y_class_test, factor
            )
            
            results['stage_2_advanced'][factor] = stage2_results
        else:
            reason = "expanding window mode" if use_expanding else "insufficient baseline signal"
            print("\n" + "-"*60)
            print(f"STAGE 2: ADVANCED MODELS (Skipped - {reason})")
            print("-"*60)
            results['stage_2_advanced'][factor] = {'skipped': True}
    
    return results


def _run_baseline_models(X_train, X_test, y_reg_train, y_reg_test,
                         y_class_train, y_class_test, target, features) -> dict:
    """
    Run both baseline models as specified in problem_framing.md.
    """
    results = {}
    
    # --- BASELINE 1: Logistic Regression ---
    print("\n  BASELINE 1: Logistic Regression")
    print("  ---------------------------------------------------")
    print(f"  Predicting: Negative {target} factor return")
    
    if 'z_composite' in features:
        X_train_z = X_train[['z_composite']].copy()
        X_test_z = X_test[['z_composite']].copy()
        print("  Feature: Z-Composite")
    else:
        X_train_z = X_train.iloc[:, [0]].copy()
        X_test_z = X_test.iloc[:, [0]].copy()
        print(f"  Feature: {features[0]}")
    
    log_model = LogisticRegression(random_state=42, max_iter=1000)
    log_model.fit(X_train_z, y_class_train)
    
    y_pred = log_model.predict(X_test_z)
    
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
    
    # --- BASELINE 2: Linear Regression ---
    print("\n  BASELINE 2: Linear Regression")
    print("  ---------------------------------------------")
    print(f"  Predicting: {target} forward factor return")
    
    if 'correlation' in features:
        X_train_corr = X_train[['correlation']].copy()
        X_test_corr = X_test[['correlation']].copy()
        print("  Feature: Pairwise Correlation")
    else:
        X_train_corr = X_train.iloc[:, [0]].copy()
        X_test_corr = X_test.iloc[:, [0]].copy()
        print(f"  Feature: {features[0]}")
    
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







def _run_expanding_window_models(X, y_reg, y_class, target, features, min_train: int = 100, step: int = 10) -> dict:
    """
    Run models on expanding windows for more robust evaluation.
    """
    print("\n  EXPANDING WINDOW VALIDATION")
    print("  ---------------------------------------------------")
    print(f"  Min train: {min_train}, Step: {step}")
    
    n = len(X)
    log_results = []
    lin_results = []
    
    for test_end in range(min_train, n, step):
        train_idx = range(0, test_end)
        test_idx = range(test_end, min(test_end + step, n))
        
        if len(test_idx) == 0:
            continue
        
        X_train = X.iloc[train_idx]
        X_test = X.iloc[test_idx]
        y_reg_train = y_reg.iloc[train_idx]
        y_reg_test = y_reg.iloc[test_idx]
        y_class_train = y_class.iloc[train_idx]
        y_class_test = y_class.iloc[test_idx]
        
        if len(X_train) < 50 or len(X_test) < 5:
            continue
        
        try:
            # Logistic
            if 'z_composite' in features:
                X_train_z = X_train[['z_composite']].copy()
                X_test_z = X_test[['z_composite']].copy()
            else:
                X_train_z = X_train.iloc[:, [0]].copy()
                X_test_z = X_test.iloc[:, [0]].copy()
            
            log_model = LogisticRegression(random_state=42, max_iter=1000)
            log_model.fit(X_train_z, y_class_train)
            y_pred = log_model.predict(X_test_z)
            f1 = f1_score(y_class_test, y_pred, zero_division=0)
            
            # Linear
            if 'correlation' in features:
                X_train_corr = X_train[['correlation']].copy()
                X_test_corr = X_test[['correlation']].copy()
            else:
                X_train_corr = X_train.iloc[:, [0]].copy()
                X_test_corr = X_test.iloc[:, [0]].copy()
            
            lin_model = LinearRegression()
            lin_model.fit(X_train_corr, y_reg_train)
            y_pred_lin = lin_model.predict(X_test_corr)
            r2 = r2_score(y_reg_test, y_pred_lin)
            
            log_results.append(f1)
            lin_results.append(r2)
            
        except:
            continue
    
    log_metrics = {
        'f1_mean': np.mean(log_results) if log_results else np.nan,
        'f1_median': np.median(log_results) if log_results else np.nan,
        'f1_std': np.std(log_results) if log_results else np.nan,
        'n_windows': len(log_results)
    }
    
    lin_metrics = {
        'r2_mean': np.mean(lin_results) if lin_results else np.nan,
        'r2_median': np.median(lin_results) if lin_results else np.nan,
        'r2_std': np.std(lin_results) if lin_results else np.nan,
        'n_windows': len(lin_results)
    }
    
    print(f"\n  Logistic F1:")
    print(f"    Mean:   {log_metrics['f1_mean']:.4f}")
    print(f"    Median: {log_metrics['f1_median']:.4f}")
    print(f"    Std:    {log_metrics['f1_std']:.4f}")
    print(f"    Windows: {log_metrics['n_windows']}")
    
    print(f"\n  Linear R²:")
    print(f"    Mean:   {lin_metrics['r2_mean']:.4f}")
    print(f"    Median: {lin_metrics['r2_median']:.4f}")
    print(f"    Std:    {lin_metrics['r2_std']:.4f}")
    print(f"    Windows: {lin_metrics['n_windows']}")
    
    return {
        'logistic': log_metrics,
        'linear': lin_metrics
    }





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


def create_results_dataframe(results_dict: dict) -> pd.DataFrame:
    """
    Convert results dictionary to a flat DataFrame for CSV export.
    """
    rows = []
    
    # Stage 1: Baseline
    for factor, factor_results in results_dict.get('stage_1_baseline', {}).items():
        if isinstance(factor_results, dict):
            # Logistic results
            if 'logistic' in factor_results:
                log = factor_results['logistic']
                row = {
                    'Stage': 'Baseline',
                    'Factor': factor.upper(),
                    'Model': 'Logistic',
                    'Feature': 'Z-Composite',
                    'Target': 'forward_1m',
                    'Metric': 'F1',
                    'Value': log.get('f1', np.nan),
                    'Accuracy': log.get('accuracy', np.nan),
                    'Precision': log.get('precision', np.nan),
                    'Recall': log.get('recall', np.nan),
                    'Coefficient': log.get('coef', np.nan)
                }
                rows.append(row)
            
            # Linear results
            if 'linear' in factor_results:
                lin = factor_results['linear']
                row = {
                    'Stage': 'Baseline',
                    'Factor': factor.upper(),
                    'Model': 'Linear',
                    'Feature': 'Correlation',
                    'Target': 'forward_1m',
                    'Metric': 'R²',
                    'Value': lin.get('r2', np.nan),
                    'RMSE': lin.get('rmse', np.nan),
                    'MAE': lin.get('mae', np.nan),
                    'Coefficient': lin.get('coef', np.nan)
                }
                rows.append(row)
    
    # Stage 2: Advanced
    for factor, factor_results in results_dict.get('stage_2_advanced', {}).items():
        if isinstance(factor_results, dict):
            if factor_results.get('skipped', False):
                row = {
                    'Stage': 'Advanced',
                    'Factor': factor.upper(),
                    'Model': 'Skipped',
                    'Feature': 'N/A',
                    'Target': 'forward_1m',
                    'Metric': 'Reason',
                    'Value': 'Insufficient baseline signal',
                    'Accuracy': np.nan,
                    'Precision': np.nan,
                    'Recall': np.nan,
                    'Coefficient': np.nan,
                    'RMSE': np.nan,
                    'MAE': np.nan
                }
                rows.append(row)
            else:
                # Isolation Forest
                if 'isolation_forest' in factor_results:
                    iso = factor_results['isolation_forest']
                    row = {
                        'Stage': 'Advanced',
                        'Factor': factor.upper(),
                        'Model': 'Isolation Forest',
                        'Feature': 'All',
                        'Target': 'forward_1m',
                        'Metric': 'Regime Diff',
                        'Value': iso.get('test_normal_mean', 0) - iso.get('test_crowded_mean', 0),
                        'Accuracy': np.nan,
                        'Precision': np.nan,
                        'Recall': np.nan,
                        'Coefficient': np.nan,
                        'RMSE': np.nan,
                        'MAE': np.nan
                    }
                    rows.append(row)
                
                # LightGBM
                if 'lightgbm' in factor_results and isinstance(factor_results['lightgbm'], dict):
                    lgb = factor_results['lightgbm']
                    if not lgb.get('skipped', False):
                        row = {
                            'Stage': 'Advanced',
                            'Factor': factor.upper(),
                            'Model': 'LightGBM',
                            'Feature': 'All',
                            'Target': 'forward_1m',
                            'Metric': 'R²',
                            'Value': lgb.get('r2', np.nan),
                            'Accuracy': np.nan,
                            'Precision': np.nan,
                            'Recall': np.nan,
                            'Coefficient': np.nan,
                            'RMSE': lgb.get('rmse', np.nan),
                            'MAE': lgb.get('mae', np.nan)
                        }
                        rows.append(row)
    
    return pd.DataFrame(rows)




def run_all_tests():
    """
    Run all simple tests and save results to files.
    """
    from data import load_data
    from features import engineer_features, prepare_model_data, print_correlation_summary
    
    # Setup logging
    timestamp = setup_logging()
    
    print("="*80)
    print("FACTOR CROWDING RISK - COMPREHENSIVE TESTING")
    print("="*80)
    print(f"Log file: outputs/model_results_{timestamp}.txt")
    
    # Load data
    print("\n1. Loading data...")
    data = load_data()
    prices = data['prices']
    factor_returns = data['factor_returns']
    
    print("\n2. Engineering features (weekly rebalancing)...")
    features = engineer_features(prices, factor_returns, rebalance_freq='weekly')
    
    all_results = {}
    test_counter = 0
    
    # ---- TEST 1: Different Feature Sets ----
    print("\n" + "="*80)
    print("TEST 1: Different Feature Sets")
    print("="*80)
    print("  Testing: z_composite, correlation, hhi, valuation_spread, all")
    
    feature_sets = ['z_composite', 'correlation', 'hhi', 'valuation_spread', 'all']
    test_results = []
    
    for fset in feature_sets:
        print(f"\n  Testing feature_set: {fset}")
        model_data = prepare_model_data(features, factor_returns)
        results = run_staged_models(model_data, target='forward_1m', feature_set=fset)
        test_results.append({
            'test': 'feature_set',
            'param': fset,
            'results': results
        })
    
    all_results['feature_set_tests'] = test_results
    
    # ---- TEST 2: Different Windows ----
    print("\n" + "="*80)
    print("TEST 2: Different Window Lengths")
    print("="*80)
    print("  Testing: 30, 60, 90 days")
    
    test_results = []
    for window in [30, 60, 90]:
        print(f"\n  Testing window: {window} days")
        features_window = engineer_features(prices, factor_returns, rebalance_freq='weekly', window_days=window)
        model_data = prepare_model_data(features_window, factor_returns)
        results = run_staged_models(model_data, target='forward_1m', feature_set='z_composite')
        test_results.append({
            'test': 'window',
            'param': window,
            'results': results
        })
    
    all_results['window_tests'] = test_results
    
    # ---- TEST 3: Different Quintiles ----
    print("\n" + "="*80)
    print("TEST 3: Different Quintile Sizes")
    print("="*80)
    print("  Testing: 10%, 20%, 30%")
    
    test_results = []
    for quintile in [0.1, 0.2, 0.3]:
        print(f"\n  Testing quintile: {quintile*100:.0f}%")
        features_quintile = engineer_features(prices, factor_returns, rebalance_freq='weekly', quintile_pct=quintile)
        model_data = prepare_model_data(features_quintile, factor_returns)
        results = run_staged_models(model_data, target='forward_1m', feature_set='z_composite')
        test_results.append({
            'test': 'quintile',
            'param': quintile,
            'results': results
        })
    
    all_results['quintile_tests'] = test_results
    
    # ---- TEST 4: Different Train Ratios ----
    print("\n" + "="*80)
    print("TEST 4: Different Train/Test Ratios")
    print("="*80)
    print("  Testing: 80/20, 70/30, 60/40")
    
    test_results = []
    for ratio in [0.8, 0.7, 0.6]:
        print(f"\n  Testing train ratio: {ratio*100:.0f}/{100-ratio*100:.0f}")
        model_data = prepare_model_data(features, factor_returns)
        results = run_staged_models(model_data, target='forward_1m', feature_set='z_composite', train_ratio=ratio)
        test_results.append({
            'test': 'train_ratio',
            'param': ratio,
            'results': results
        })
    
    all_results['train_ratio_tests'] = test_results
    
    # ---- TEST 5: Lagged Features ----
    print("\n" + "="*80)
    print("TEST 5: Lagged Features")
    print("="*80)
    print("  Testing: With lags vs Without lags")
    
    test_results = []
    
    # Without lags (baseline)
    print("\n  Testing: Without lags (baseline)")
    model_data = prepare_model_data(features, factor_returns, add_lags=False)
    results_no_lag = run_staged_models(model_data, target='forward_1m', feature_set='all')
    test_results.append({
        'test': 'lags',
        'param': 'no_lags',
        'results': results_no_lag
    })
    
    # With lags
    print("\n  Testing: With lags")
    model_data_lags = prepare_model_data(features, factor_returns, add_lags=True)
    results_lag = run_staged_models(model_data_lags, target='forward_1m', feature_set='all')
    test_results.append({
        'test': 'lags',
        'param': 'with_lags',
        'results': results_lag
    })
    
    all_results['lag_tests'] = test_results
    
    # ---- TEST 6: Expanding Window Validation ----
    print("\n" + "="*80)
    print("TEST 6: Expanding Window Validation")
    print("="*80)
    print("  Testing: Single split vs Expanding window")
    
    test_results = []
    
    # Single split
    print("\n  Testing: Single split (80/20)")
    model_data = prepare_model_data(features, factor_returns)
    results_single = run_staged_models(model_data, target='forward_1m', feature_set='z_composite', use_expanding=False)
    test_results.append({
        'test': 'validation',
        'param': 'single_split',
        'results': results_single
    })
    
    # Expanding window
    print("\n  Testing: Expanding window")
    results_expanding = run_staged_models(model_data, target='forward_1m', feature_set='z_composite', use_expanding=True)
    test_results.append({
        'test': 'validation',
        'param': 'expanding_window',
        'results': results_expanding
    })
    
    all_results['validation_tests'] = test_results
    
    # ---- Save All Results ----
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    # Create summary CSV for each test
    summary_rows = []
    
    for test_group, test_list in all_results.items():
        for test_item in test_list:
            test_name = test_item['test']
            param = test_item['param']
            results = test_item['results']
            
            for factor in ['momentum', 'value']:
                if factor in results.get('stage_1_baseline', {}):
                    factor_results = results['stage_1_baseline'][factor]
                    summary_rows.append({
                        'Test_Group': test_name,
                        'Parameter': param,
                        'Factor': factor.upper(),
                        'Logistic_F1': factor_results.get('logistic', {}).get('f1', np.nan),
                        'Linear_R2': factor_results.get('linear', {}).get('r2', np.nan),
                        'Linear_RMSE': factor_results.get('linear', {}).get('rmse', np.nan),
                        'Signal_Detected': 'Yes' if (factor_results.get('linear', {}).get('r2', 0) > 0 or factor_results.get('logistic', {}).get('f1', 0) > 0.50) else 'No'
                    })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_path = f'../outputs/test_summary_{timestamp}.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"✅ Summary CSV saved: {summary_path}")
    
    # Save full results as JSON
    json_path = f'../outputs/full_results_{timestamp}.json'
    with open(json_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"✅ Full results JSON saved: {json_path}")
    
    # Save human-readable summary as TXT
    txt_path = f'../outputs/test_summary_{timestamp}.txt'
    with open(txt_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("FACTOR CROWDING RISK - TEST SUMMARY\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        f.write(summary_df.to_string(index=False))
        f.write("\n\n" + "="*80 + "\n")
        f.write("BEST PERFORMING CONFIGURATIONS\n")
        f.write("="*80 + "\n\n")
        
        # Best for each factor
        for factor in ['MOMENTUM', 'VALUE']:
            factor_df = summary_df[summary_df['Factor'] == factor]
            if not factor_df.empty:
                # Best Logistic F1
                best_log = factor_df.loc[factor_df['Logistic_F1'].idxmax()]
                f.write(f"\n{factor} - BEST LOGISTIC F1:\n")
                f.write(f"  Test: {best_log['Test_Group']}, Parameter: {best_log['Parameter']}\n")
                f.write(f"  F1: {best_log['Logistic_F1']:.4f}\n")
                
                # Best Linear R²
                best_lin = factor_df.loc[factor_df['Linear_R2'].idxmax()]
                f.write(f"\n{factor} - BEST LINEAR R²:\n")
                f.write(f"  Test: {best_lin['Test_Group']}, Parameter: {best_lin['Parameter']}\n")
                f.write(f"  R²: {best_lin['Linear_R2']:.4f}\n")
    
    print(f"✅ Human-readable TXT saved: {txt_path}")
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print(f"Results saved in: outputs/ (timestamp: {timestamp})")
    print("="*80)
    
    return all_results, summary_df

# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Run all tests and save results
    all_results, summary_df = run_all_tests()
    
    # Print summary to console
    print("\n" + "="*80)
    print("CONSOLE SUMMARY - BEST PERFORMING CONFIGURATIONS")
    print("="*80)
    
    for factor in ['MOMENTUM', 'VALUE']:
        factor_df = summary_df[summary_df['Factor'] == factor]
        if not factor_df.empty:
            print(f"\n{factor}:")
            best_log = factor_df.loc[factor_df['Logistic_F1'].idxmax()]
            print(f"  Best F1: {best_log['Logistic_F1']:.4f} ({best_log['Test_Group']}, {best_log['Parameter']})")
            best_lin = factor_df.loc[factor_df['Linear_R2'].idxmax()]
            print(f"  Best R²: {best_lin['Linear_R2']:.4f} ({best_lin['Test_Group']}, {best_lin['Parameter']})")