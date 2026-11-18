"""
Day 3: Visualization Generation — Quant Finance Theme
Professional styling inspired by institutional quant research reports.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter, PercentFormatter
import seaborn as sns
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data import load_data
from features import engineer_transformed_features, prepare_multi_target_data

# ---------------------------------------------------------------------------
# QUANT FINANCE THEME CONFIGURATION
# ---------------------------------------------------------------------------

# Color palette — institutional quant style
COLORS = {
    'primary': '#1a3a5c',          # Dark navy — main lines
    'secondary': '#4a7b9d',        # Muted blue — secondary lines
    'accent': '#b31b1b',           # Deep red — danger/crowding
    'accent_light': '#e87474',     # Light red — shading
    'positive': '#2a6b3e',         # Dark green — positive returns
    'negative': '#b31b1b',         # Deep red — negative returns
    'static': '#1a3a5c',           # Navy — static strategy
    'dynamic': '#4a7b9d',          # Muted blue — dynamic strategy
    'threshold': '#b31b1b',        # Red — threshold line
    'crowd_shade': '#f0e6e6',      # Very light red — crowding shading
    'grid': '#d9d9d9',             # Light gray — grid lines
    'text': '#1a1a1a',             # Dark gray — text
    'annotation_bg': '#ffffff',    # White — annotation background
    'scatter_cmap': 'RdYlBu_r',    # Red-Yellow-Blue colormap
}

# Font configuration
FONTS = {
    'family': 'sans-serif',
    'title': 14,
    'subtitle': 12,
    'label': 11,
    'legend': 10,
    'annotation': 9,
    'tick': 9,
}

# Figure configuration
FIGURE_CONFIG = {
    'dpi': 200,
    'figsize_large': (14, 8),
    'figsize_medium': (12, 7),
    'figsize_small': (10, 6),
}

# Set global style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette([COLORS['primary'], COLORS['secondary'], COLORS['accent']])

# Customize rcParams
plt.rcParams['font.family'] = FONTS['family']
plt.rcParams['font.size'] = FONTS['label']
plt.rcParams['axes.titlesize'] = FONTS['title']
plt.rcParams['axes.labelsize'] = FONTS['label']
plt.rcParams['legend.fontsize'] = FONTS['legend']
plt.rcParams['xtick.labelsize'] = FONTS['tick']
plt.rcParams['ytick.labelsize'] = FONTS['tick']
plt.rcParams['figure.titlesize'] = FONTS['title']
plt.rcParams['figure.dpi'] = FIGURE_CONFIG['dpi']
plt.rcParams['savefig.dpi'] = FIGURE_CONFIG['dpi']
plt.rcParams['axes.edgecolor'] = COLORS['grid']
plt.rcParams['axes.linewidth'] = 0.5
plt.rcParams['grid.alpha'] = 0.4
plt.rcParams['grid.linestyle'] = '-'
plt.rcParams['grid.linewidth'] = 0.5

# Create outputs directory
os.makedirs('outputs', exist_ok=True)

def format_percent(x, pos):
    """Format y-axis as percentage."""
    return f'{x:.0%}'

def format_percent_1d(x, pos):
    """Format y-axis as percentage with 1 decimal."""
    return f'{x:.1%}'

def add_watermark(ax, text="CONFIDENTIAL — FOR ILLUSTRATIVE PURPOSES"):
    """Add subtle watermark to figure."""
    ax.text(0.99, 0.01, text, transform=ax.transAxes, fontsize=7,
            color='gray', alpha=0.3, ha='right', va='bottom', rotation=0)

def add_source(ax, text="Source: Author's calculations"):
    """Add source attribution."""
    ax.text(0.99, 0.01, text, transform=ax.transAxes, fontsize=7,
            color='gray', alpha=0.5, ha='right', va='bottom')

print("="*80)
print("QUANT FINANCE VISUALIZATION GENERATOR")
print("="*80)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# ---------------------------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------------------------
print("\n1. LOADING DATA...")

data = load_data()
prices = data['prices']
factor_returns = data['factor_returns']

features = engineer_transformed_features(prices, factor_returns, rebalance_freq='weekly')
multi_target_data = prepare_multi_target_data(features, factor_returns)

# Use Value factor with continuous sizing (best from Batch 3)
value_df = multi_target_data['value']
common_dates = value_df.index

factor_ret_value = factor_returns['value'].loc[common_dates]

X = value_df[['correlation_raw']].copy()
y = value_df['forward_3m'].copy()

print(f"  Observations: {len(X)}")
print(f"  Date range: {X.index[0].strftime('%Y-%m-%d')} to {X.index[-1].strftime('%Y-%m-%d')}")

# ---------------------------------------------------------------------------
# 2. TRAIN MODEL & GENERATE PREDICTIONS
# ---------------------------------------------------------------------------
print("\n2. GENERATING STRATEGY RETURNS (OUT-OF-SAMPLE)...")

from sklearn.linear_model import LinearRegression

# Prepare data
X_clean = X.dropna()
y_clean = y.loc[X_clean.index]

# Split: train on 2019–2021, test on 2022–2024
train_cutoff = "2021-12-31"
train_mask = X_clean.index <= pd.Timestamp(train_cutoff)
test_mask = X_clean.index > pd.Timestamp(train_cutoff)

X_train = X_clean[train_mask]
y_train = y_clean.loc[X_train.index]
X_test = X_clean[test_mask]
y_test = y_clean.loc[X_test.index]

# Train on train period only
model = LinearRegression()
model.fit(X_train.values.reshape(-1, 1), y_train.values)

# Predict on test period
y_pred_test = model.predict(X_test.values.reshape(-1, 1))

# Map predictions to weights (continuous sizing) — test period only
y_pred_scaled = (y_pred_test - y_pred_test.min()) / (y_pred_test.max() - y_pred_test.min() + 1e-10)
weights = 0.7 + 0.3 * y_pred_scaled
weights = np.clip(weights, 0.5, 1.0)

# Align returns to test period
factor_ret_aligned = factor_ret_value.loc[X_test.index]

# Static strategy (100% invested) — test period
static_returns = factor_ret_aligned

# Dynamic strategy (continuous sizing) — test period
dynamic_returns = factor_ret_aligned * weights

# Calculate metrics
static_cum = (1 + static_returns).cumprod()
dynamic_cum = (1 + dynamic_returns).cumprod()

static_sharpe = (static_returns.mean() / static_returns.std()) * np.sqrt(52)
dynamic_sharpe = (dynamic_returns.mean() / dynamic_returns.std()) * np.sqrt(52)

static_drawdown = (static_cum / static_cum.expanding().max() - 1)
dynamic_drawdown = (dynamic_cum / dynamic_cum.expanding().max() - 1)

static_total = static_cum.iloc[-1] - 1
dynamic_total = dynamic_cum.iloc[-1] - 1

static_vol = static_returns.std() * np.sqrt(52)
dynamic_vol = dynamic_returns.std() * np.sqrt(52)

# Crowding signal
crowding_signal = X_clean['correlation_raw']
threshold = crowding_signal.quantile(0.75)
crowded_mask = crowding_signal > threshold

print(f"  Static Sharpe: {static_sharpe:.4f}")
print(f"  Dynamic Sharpe: {dynamic_sharpe:.4f}")
print(f"  Sharpe Δ: {dynamic_sharpe - static_sharpe:+.4f}")

# ---------------------------------------------------------------------------
# 3. VISUALIZATION 1: Crowding Signal Over Time
# ---------------------------------------------------------------------------
print("\n3. GENERATING VISUALIZATION 1: Crowding Signal Over Time...")

fig, ax = plt.subplots(figsize=FIGURE_CONFIG['figsize_large'])

# Plot crowding signal
ax.plot(crowding_signal.index, crowding_signal.values, 
        color=COLORS['primary'], linewidth=2, 
        label='Crowding Signal (Pairwise Correlation)')

# Threshold line
ax.axhline(y=threshold, color=COLORS['accent'], linestyle='--', 
           linewidth=1.5, alpha=0.8, label=f'75th Percentile Threshold ({threshold:.3f})')

# Shade crowded periods
ax.fill_between(crowding_signal.index, 0, crowding_signal.values,
                where=(crowding_signal.values > threshold),
                color=COLORS['accent'], alpha=0.15, 
                label='Crowded Regime', transform=ax.get_xaxis_transform())

# Find contiguous crowded periods for vertical shading
crowded_periods = []
start_idx = None
for i, val in enumerate(crowded_mask):
    if val and start_idx is None:
        start_idx = i
    elif not val and start_idx is not None:
        end_idx = i - 1
        if end_idx - start_idx >= 2:
            crowded_periods.append((crowding_signal.index[start_idx], crowding_signal.index[end_idx]))
        start_idx = None
if start_idx is not None and len(crowding_signal) - start_idx >= 2:
    crowded_periods.append((crowding_signal.index[start_idx], crowding_signal.index[-1]))

# Shade crowded periods with vertical spans
for start, end in crowded_periods:
    ax.axvspan(start, end, alpha=0.08, color=COLORS['accent'])

# Styling
ax.set_xlabel('Date', fontsize=FONTS['label'])
ax.set_ylabel('Crowding Signal (Pairwise Correlation)', fontsize=FONTS['label'])
ax.set_title('Value Factor Crowding Signal Over Time\n2019 – 2024', fontsize=FONTS['title'], fontweight='bold')
ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='none')
ax.grid(True, alpha=0.3, color=COLORS['grid'])

# Format y-axis to 3 decimals
ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.3f}'))

# Add watermark and source
add_watermark(ax)
add_source(ax)

plt.tight_layout()
plt.savefig('outputs/visualization_1_crowding_signal_over_time.png', 
            dpi=FIGURE_CONFIG['dpi'], bbox_inches='tight', facecolor='white')
plt.close()

print("  ✅ Saved: outputs/visualization_1_crowding_signal_over_time.png")

# ---------------------------------------------------------------------------
# 4. VISUALIZATION 2: Cumulative Returns Comparison
# ---------------------------------------------------------------------------
print("\n4. GENERATING VISUALIZATION 2: Cumulative Returns Comparison...")

fig, ax = plt.subplots(figsize=FIGURE_CONFIG['figsize_large'])

# Plot cumulative returns
ax.plot(static_cum.index, static_cum.values - 1, 
        color=COLORS['static'], linewidth=2.5, 
        label=f'Static Strategy (100% Allocation)  |  Sharpe: {static_sharpe:.2f}')

ax.plot(dynamic_cum.index, dynamic_cum.values - 1, 
        color=COLORS['dynamic'], linewidth=2.5, 
        label=f'Crowding-Aware Strategy (Continuous Sizing)  |  Sharpe: {dynamic_sharpe:.2f}')

# Add horizontal zero line
ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)

# Shade crowded periods
for start, end in crowded_periods[:5]:
    ax.axvspan(start, end, alpha=0.06, color=COLORS['accent'])

# Add annotations for key crowded periods
for i, (start, end) in enumerate(crowded_periods[:3]):
    mid_point = start + (end - start) / 2
    y_pos = ax.get_ylim()[0] + 0.02 * (ax.get_ylim()[1] - ax.get_ylim()[0])
    ax.text(mid_point, y_pos, 'Crowded', ha='center', fontsize=FONTS['annotation'],
            color=COLORS['accent'], alpha=0.7, style='italic')

# Styling
ax.set_xlabel('Date', fontsize=FONTS['label'])
ax.set_ylabel('Cumulative Return', fontsize=FONTS['label'])
ax.set_title('Value Factor Strategy Performance\nStatic vs Crowding-Aware Allocation', 
             fontsize=FONTS['title'], fontweight='bold')
ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='none')
ax.grid(True, alpha=0.3, color=COLORS['grid'])

# Format y-axis as percentage
ax.yaxis.set_major_formatter(FuncFormatter(format_percent))

# Add watermark and source
add_watermark(ax)
add_source(ax)

plt.tight_layout()
plt.savefig('outputs/visualization_2_cumulative_returns_comparison.png', 
            dpi=FIGURE_CONFIG['dpi'], bbox_inches='tight', facecolor='white')
plt.close()

print("  ✅ Saved: outputs/visualization_2_cumulative_returns_comparison.png")

# ---------------------------------------------------------------------------
# 5. VISUALIZATION 3: Drawdown Comparison
# ---------------------------------------------------------------------------
print("\n5. GENERATING VISUALIZATION 3: Drawdown Comparison...")

fig, ax = plt.subplots(figsize=FIGURE_CONFIG['figsize_large'])

# Plot drawdowns
ax.fill_between(static_drawdown.index, 0, static_drawdown.values, 
                color=COLORS['static'], alpha=0.3, 
                label=f'Static Strategy  |  Max DD: {static_drawdown.min():.2%}')

ax.fill_between(dynamic_drawdown.index, 0, dynamic_drawdown.values, 
                color=COLORS['dynamic'], alpha=0.3, 
                label=f'Crowding-Aware Strategy  |  Max DD: {dynamic_drawdown.min():.2%}')

# Mark max drawdown points
static_min_idx = static_drawdown.idxmin()
dynamic_min_idx = dynamic_drawdown.idxmin()

ax.scatter(static_min_idx, static_drawdown.min(), 
           color=COLORS['static'], s=100, zorder=5, marker='v', edgecolor='white')
ax.scatter(dynamic_min_idx, dynamic_drawdown.min(), 
           color=COLORS['dynamic'], s=100, zorder=5, marker='v', edgecolor='white')

# Add annotations for max drawdown
ax.annotate(f'Static Max DD: {static_drawdown.min():.2%}', 
            xy=(static_min_idx, static_drawdown.min()),
            xytext=(static_min_idx, static_drawdown.min() - 0.06),
            ha='center', fontsize=FONTS['annotation'], 
            color=COLORS['static'], fontweight='bold')

ax.annotate(f'Dynamic Max DD: {dynamic_drawdown.min():.2%}',
            xy=(dynamic_min_idx, dynamic_drawdown.min()),
            xytext=(dynamic_min_idx, dynamic_drawdown.min() - 0.06),
            ha='center', fontsize=FONTS['annotation'],
            color=COLORS['dynamic'], fontweight='bold')

# Add horizontal zero line
ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)

# Styling
ax.set_xlabel('Date', fontsize=FONTS['label'])
ax.set_ylabel('Drawdown', fontsize=FONTS['label'])
ax.set_title('Drawdown Comparison\nStatic vs Crowding-Aware Strategy', 
             fontsize=FONTS['title'], fontweight='bold')
ax.legend(loc='lower left', frameon=True, facecolor='white', edgecolor='none')
ax.grid(True, alpha=0.3, color=COLORS['grid'])

# Format y-axis as percentage
ax.yaxis.set_major_formatter(FuncFormatter(format_percent))

# Add watermark and source
add_watermark(ax)
add_source(ax)

plt.tight_layout()
plt.savefig('outputs/visualization_3_drawdown_comparison.png', 
            dpi=FIGURE_CONFIG['dpi'], bbox_inches='tight', facecolor='white')
plt.close()

print("  ✅ Saved: outputs/visualization_3_drawdown_comparison.png")

# ---------------------------------------------------------------------------
# 6. VISUALIZATION 4: Crowding vs Forward Return Scatter
# ---------------------------------------------------------------------------
print("\n6. GENERATING VISUALIZATION 4: Crowding vs Forward Return Scatter...")

fig, ax = plt.subplots(figsize=FIGURE_CONFIG['figsize_medium'])

# Scatter plot with time-based coloring
scatter = ax.scatter(X_clean['correlation_raw'].values, 
                      y_clean.values,
                      c=np.arange(len(y_clean)),
                      cmap=COLORS['scatter_cmap'],
                      alpha=0.7,
                      s=80,
                      edgecolors='white',
                      linewidth=0.5)

# Add regression line
x_line = np.linspace(X_clean['correlation_raw'].min(), X_clean['correlation_raw'].max(), 100)
y_line = model.predict(x_line.reshape(-1, 1))
ax.plot(x_line, y_line, color=COLORS['accent'], linewidth=2.5, 
        label=f'Regression Line  |  R²: {model.score(X_clean.values.reshape(-1, 1), y_clean.values):.4f}')

# Add threshold line
ax.axvline(x=threshold, color=COLORS['threshold'], linestyle='--', 
           linewidth=1.5, alpha=0.8, label=f'75th Percentile Threshold ({threshold:.3f})')

# Shade crowded region
ax.axvspan(threshold, X_clean['correlation_raw'].max(), 
           alpha=0.08, color=COLORS['accent'], label='Crowded Region')

# Add horizontal zero line
ax.axhline(y=0, color='black', linewidth=0.5, alpha=0.3)

# Add colorbar
cbar = fig.colorbar(scatter, ax=ax, shrink=0.7)
cbar.set_label('Time (Earlier → Later)', fontsize=FONTS['annotation'])

# Styling
ax.set_xlabel('Crowding Signal (Pairwise Correlation)', fontsize=FONTS['label'])
ax.set_ylabel('Forward 3-Month Return', fontsize=FONTS['label'])
ax.set_title('Value Factor: Crowding Signal vs Forward Performance\n2019 – 2024', 
             fontsize=FONTS['title'], fontweight='bold')
ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='none')
ax.grid(True, alpha=0.3, color=COLORS['grid'])

# Format y-axis as percentage
ax.yaxis.set_major_formatter(FuncFormatter(format_percent_1d))

# Add annotation with key stats
corr = X_clean['correlation_raw'].corr(y_clean)
ax.annotate(f'Correlation: {corr:.4f}\nR²: {model.score(X_clean.values.reshape(-1, 1), y_clean.values):.4f}',
            xy=(0.03, 0.95), xycoords='axes fraction',
            bbox=dict(boxstyle="round,pad=0.4", facecolor='white', alpha=0.9, edgecolor=COLORS['grid']),
            verticalalignment='top', fontsize=FONTS['annotation'])

# Add watermark and source
add_watermark(ax)
add_source(ax)

plt.tight_layout()
plt.savefig('outputs/visualization_4_crowding_vs_forward_return.png', 
            dpi=FIGURE_CONFIG['dpi'], bbox_inches='tight', facecolor='white')
plt.close()

print("  ✅ Saved: outputs/visualization_4_crowding_vs_forward_return.png")

# ---------------------------------------------------------------------------
# 7. METRICS TABLE
# ---------------------------------------------------------------------------
print("\n7. GENERATING METRICS TABLE...")

metrics_data = {
    'Metric': ['Total Return', 'Sharpe Ratio (Annualized)', 'Max Drawdown', 
               'Annualized Volatility', 'Average Exposure', 'Crowded Periods'],
    'Static Strategy': [
        f'{static_total:.2%}',
        f'{static_sharpe:.4f}',
        f'{static_drawdown.min():.2%}',
        f'{static_vol:.2%}',
        '100.0%',
        'N/A'
    ],
    'Crowding-Aware Strategy': [
        f'{dynamic_total:.2%}',
        f'{dynamic_sharpe:.4f}',
        f'{dynamic_drawdown.min():.2%}',
        f'{dynamic_vol:.2%}',
        f'{weights.mean():.1%}',
        f'{crowded_mask.mean():.1%}'
    ],
    'Improvement': [
        f'{dynamic_total - static_total:+.2%}',
        f'{dynamic_sharpe - static_sharpe:+.4f}',
        f'{static_drawdown.min() - dynamic_drawdown.min():+.2%}',
        f'{static_vol - dynamic_vol:+.2%}',
        'N/A',
        'N/A'
    ]
}

metrics_df = pd.DataFrame(metrics_data)
metrics_df.to_csv('outputs/metrics_table.csv', index=False)

print("  ✅ Saved: outputs/metrics_table.csv")

# Print formatted metrics table
print("\n" + "="*80)
print("METRICS SUMMARY TABLE")
print("="*80)
print(metrics_df.to_string(index=False))

# ---------------------------------------------------------------------------
# 8. SUMMARY REPORT
# ---------------------------------------------------------------------------
print("\n" + "="*80)
print("VISUALIZATION COMPLETE")
print("="*80)

print(f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│                    QUANT FINANCE VISUALIZATION SUMMARY                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FILES GENERATED:                                                           │
│    ├── visualization_1_crowding_signal_over_time.png                       │
│    ├── visualization_2_cumulative_returns_comparison.png                   │
│    ├── visualization_3_drawdown_comparison.png                             │
│    ├── visualization_4_crowding_vs_forward_return.png                     │
│    └── metrics_table.csv                                                   │
│                                                                             │
│  CONFIGURATION:                                                             │
│    Factor: Value                                                            │
│    Feature: correlation_raw                                                 │
│    Target: forward_3m                                                       │
│    Model: Linear Regression → Continuous Sizing                             │
│    Threshold: 75th percentile                                               │
│                                                                             │
│  KEY RESULTS:                                                               │
│    Static Sharpe:  {static_sharpe:.4f}                                      │
│    Dynamic Sharpe: {dynamic_sharpe:.4f}                                     │
│    Sharpe Δ:       {dynamic_sharpe - static_sharpe:+.4f}                    │
│                                                                             │
│    Static Max DD:  {static_drawdown.min():.2%}                              │
│    Dynamic Max DD: {dynamic_drawdown.min():.2%}                             │
│    DD Reduction:   {static_drawdown.min() - dynamic_drawdown.min():+.2%}    │
│                                                                             │
│    Correlation (Signal vs Forward Return): {corr:.4f}                       │
│    R²: {model.score(X_clean.values.reshape(-1, 1), y_clean.values):.4f}    │
│    Crowded Periods: {crowded_mask.mean():.1%}                               │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  NEXT STEPS:                                                                │
│  1. Review visualizations in outputs/                                       │
│  2. Use metrics_table.csv for final documentation                          │
│  3. Proceed to PDF paper generation                                        │
└─────────────────────────────────────────────────────────────────────────────┘
""")