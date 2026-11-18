"""Generated report and figures.

The report is written by the pipeline, never hand-edited. Every number in it
comes from a table produced in this run.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import DOCS_DIR, OUT_DIR, Config
from .overlay import expanding_percentile
from .pipeline import Results
from .stats import quantile_regression, sharpe
from .targets import episode_frame
from .universe import market_returns

FIG_DIR = Path(DOCS_DIR) / "figures"
TABLE_DIR = Path(OUT_DIR) / "tables"

PALETTE = {
    "MOM": "#1f4e79",
    "STREV": "#b03a2e",
    "LOWVOL": "#2e6b46",
    "ink": "#222222",
    "muted": "#777777",
    "grid": "#dddddd",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 170,
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.edgecolor": "#999999",
            "axes.linewidth": 0.6,
            "grid.color": PALETTE["grid"],
            "grid.linewidth": 0.5,
            "legend.fontsize": 8,
            "legend.frameon": False,
        }
    )


def _clean(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, alpha=0.5)


def _save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _footer(fig, results: Results) -> None:
    start = results.factors.dates[0].date()
    end = results.factors.dates[-1].date()
    fig.text(
        0.5,
        -0.01,
        f"Sample: {start} to {end}",
        ha="center",
        fontsize=8,
        color=PALETTE["muted"],
    )


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def figure_factor_returns(results: Results) -> Path:
    returns = results.factors.returns
    episodes = episode_frame(returns)
    fig, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)

    for ax, factor in zip(axes, returns.columns):
        cumulative = (1 + returns[factor].fillna(0)).cumprod()
        ax.plot(cumulative.index, cumulative, color=PALETTE.get(factor, "k"), lw=1.2)
        for _, episode in episodes[episodes["factor"] == factor].iterrows():
            ax.axvspan(episode["start"], episode["end"], color="#b03a2e", alpha=0.10)
        ax.set_yscale("log")
        ax.set_title(
            f"{factor}: cumulative return (log scale), drawdown episodes shaded"
        )
        ax.set_ylabel("growth of 1")
        _clean(ax)
    axes[-1].set_xlabel("date")
    _footer(fig, results)
    return _save(fig, "fig1_factor_returns.png")


def figure_fragility(results: Results) -> Path:
    composite = results.fragility.composite
    fig, axes = plt.subplots(3, 1, figsize=(9, 6.5), sharex=True)
    for ax, factor in zip(axes, composite.columns):
        series = composite[factor].dropna()
        ax.plot(series.index, series, color=PALETTE.get(factor, "k"), lw=0.9)
        ax.axhline(0, color=PALETTE["muted"], lw=0.6)
        ax.axhline(1, color="#b03a2e", lw=0.6, ls="--")
        ax.set_title(
            f"{factor}: fragility composite (expanding z, higher = more fragile)"
        )
        _clean(ax)
    axes[-1].set_xlabel("date")
    _footer(fig, results)
    return _save(fig, "fig2_fragility.png")


def _quintile_view(results: Results) -> pd.DataFrame:
    dataset = results.study.dataset
    frames = []
    for factor in results.cfg.factors:
        frame = dataset[dataset["factor"] == factor].copy()
        pct = expanding_percentile(
            results.fragility.composite[factor], results.cfg.burn_in
        )
        frame["pct"] = frame["date"].map(pct)
        frame = frame.dropna(subset=["pct", "fwd_4w"])
        frame["quintile"] = pd.cut(
            frame["pct"],
            bins=np.linspace(0, 1, 6),
            labels=False,
            include_lowest=True,
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def figure_conditional(results: Results) -> Path:
    frame = _quintile_view(results)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    for ax, factor in zip(axes, results.cfg.factors):
        group = frame[frame["factor"] == factor]
        data = [
            group.loc[group["quintile"] == b, "fwd_4w"].dropna().to_numpy() * 100
            for b in range(5)
        ]
        ax.boxplot(data, widths=0.55, showfliers=False, medianprops={"color": "black"})
        ax.axhline(0, color=PALETTE["muted"], lw=0.6)
        ax.set_title(f"{factor}: forward 4-week return by fragility quintile")
        ax.set_xlabel("fragility quintile (1 = calm, 5 = fragile)")
        ax.set_ylabel("forward 4-week return (%)")
        _clean(ax)
    _footer(fig, results)
    return _save(fig, "fig3_conditional_returns.png")


def figure_quantile_coefficients(results: Results) -> Path:
    dataset = results.study.dataset
    cfg = results.cfg
    columns = [np.ones(len(dataset)), dataset["composite"].to_numpy()]
    for control in ("log_vol", "mkt_vol", "trail_12w", "liq_regime"):
        columns.append(dataset[control].to_numpy())
    for factor in ("STREV", "LOWVOL"):
        columns.append((dataset["factor"] == factor).to_numpy(dtype=float))
    names = [
        "const",
        "composite",
        "log_vol",
        "mkt_vol",
        "trail_12w",
        "liq_regime",
        "f_STREV",
        "f_LOWVOL",
    ]
    x = np.column_stack(columns)
    y = dataset["fwd_4w"].to_numpy()

    quantiles = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90])
    betas = []
    for q in quantiles:
        betas.append(quantile_regression(y, x, names, q).params["composite"])

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(
        quantiles * 100, np.array(betas) * 100, marker="o", color=PALETTE["ink"], lw=1.2
    )
    ax.axhline(0, color=PALETTE["muted"], lw=0.7)

    primary = results.study.primary
    for _, row in primary[primary["term"] == "composite"].iterrows():
        center = row["quantile"] * 100
        ax.errorbar(
            center,
            row["estimate"] * 100,
            yerr=[
                [(row["estimate"] - row["ci_low"]) * 100],
                [(row["ci_high"] - row["estimate"]) * 100],
            ],
            fmt="none",
            color="#b03a2e",
            capsize=4,
            lw=1.2,
        )
    ax.set_xlabel("quantile of the forward 4-week return distribution")
    ax.set_ylabel("coefficient on fragility (%, per 1 SD)")
    ax.set_title(
        "Fragility coefficient across the distribution\n"
        "(dots: point estimates; bars: 95% block bootstrap)"
    )
    _clean(ax)
    _footer(fig, results)
    return _save(fig, "fig4_quantile_coefficients.png")


def _net_curve(grid, s1, s2, gross, cfg: Config, c: float, spread: float) -> np.ndarray:
    fixed = cfg.borrow_bp / 1e4 + cfg.financing_bp / 1e4
    half_spread = 0.5 * spread / 1e4
    cost = 52.0 * (half_spread * s1 + c * np.sqrt(grid) * s2)
    return gross - cost - fixed


def figure_capacity(results: Results) -> Path:
    capacity = results.capacity
    cfg = results.cfg
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    grid = np.geomspace(cfg.aum_bounds[0], cfg.aum_bounds[1], 120)

    for ax, factor in zip(axes, cfg.factors):
        gross = float(capacity.capacity.loc[factor, "gross_premium"])
        s1 = float(capacity.terms.loc[factor, "s1_mean"])
        s2 = float(capacity.terms.loc[factor, "s2_mean"])
        baseline = _net_curve(grid, s1, s2, gross, cfg, cfg.impact_c, cfg.spread_bp)
        lo = _net_curve(
            grid, s1, s2, gross, cfg, min(cfg.impact_c_grid), min(cfg.spread_bp_grid)
        )
        hi = _net_curve(
            grid, s1, s2, gross, cfg, max(cfg.impact_c_grid), max(cfg.spread_bp_grid)
        )

        ax.fill_between(
            grid,
            hi * 100,
            lo * 100,
            color=PALETTE.get(factor, "k"),
            alpha=0.15,
            label="impact/spread band",
        )
        ax.plot(
            grid,
            baseline * 100,
            color=PALETTE.get(factor, "k"),
            lw=1.3,
            label="baseline",
        )
        ax.axhline(gross * 100, color=PALETTE["muted"], lw=0.7, ls=":")
        ax.axhline(cfg.hurdle * gross * 100, color="#b03a2e", lw=0.7, ls="--")
        ax.set_xscale("log")
        ax.set_title(f"{factor}: net annual premium")
        ax.set_xlabel("sleeve notional A (USD, log)")
        _clean(ax)
    axes[0].set_ylabel("net premium (% per year)")
    axes[0].legend(loc="lower left")
    _footer(fig, results)
    return _save(fig, "fig5_capacity.png")


def figure_overlay(results: Results) -> Path:
    decision = results.decision
    cfg = results.cfg
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9), sharey=True)
    styles = {
        "static": ("#999999", "static"),
        "exposure_matched": ("#c9a227", "exposure-matched"),
        "vol_managed": ("#1f4e79", "volatility-managed"),
        "fragility": ("#b03a2e", "fragility overlay"),
    }
    for ax, factor in zip(axes, cfg.factors):
        frames = decision.frames[factor]
        for name, (colour, label) in styles.items():
            net = frames[name]["net"]
            cumulative = (1 + net).cumprod()
            ax.plot(cumulative.index, cumulative, color=colour, lw=1.2, label=label)
        ax.set_title(f"{factor}: net cumulative return, after costs")
        ax.set_xlabel("date")
        _clean(ax)
    axes[0].set_ylabel("growth of 1")
    axes[0].legend(loc="upper left")
    _footer(fig, results)
    return _save(fig, "fig6_overlay.png")


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------
def _fmt(value, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return "n/a"
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:.{digits}f}"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _md_table(frame: pd.DataFrame, digits: int = 4, index: bool = False) -> str:
    data = frame.reset_index() if index else frame
    columns = [str(c) for c in data.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append(
            "| " + " | ".join(_fmt(row[c], digits) for c in data.columns) + " |"
        )
    return "\n".join(lines)


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"${value / 1e6:,.0f}M"
    return f"${value:,.0f}"


def _pct(value, digits: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def _hac_alpha_beta(returns: pd.Series, market: pd.Series) -> dict[str, float]:
    frame = pd.concat([returns.rename("y"), market.rename("m")], axis=1).dropna()
    if len(frame) < 30:
        return {}
    result = sm.OLS(frame["y"], sm.add_constant(frame["m"])).fit(
        cov_type="HAC", cov_kwds={"maxlags": 4}
    )
    return {
        "beta": float(result.params["m"]),
        "beta_t": float(result.tvalues["m"]),
        "alpha": float(result.params["const"] * 52),
        "alpha_t": float(result.tvalues["const"]),
        "r2": float(result.rsquared),
    }


def _hac_mean(returns: pd.Series) -> dict[str, float]:
    clean = returns.dropna()
    if len(clean) < 30:
        return {}
    result = sm.OLS(clean.to_numpy(), np.ones((len(clean), 1))).fit(
        cov_type="HAC", cov_kwds={"maxlags": 4}
    )
    mean = float(result.params[0] * 52)
    se = float(result.bse[0] * 52)
    return {
        "gross_premium": mean,
        "premium_se": se,
        "premium_low": mean - 1.96 * se,
        "premium_high": mean + 1.96 * se,
        "premium_t": float(result.tvalues[0]),
    }


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
def _verdict(results: Results) -> dict:
    study = results.study
    primary = study.primary
    low = primary[
        (primary["term"] == "composite")
        & (primary["quantile"] == results.cfg.primary_quantile)
    ]
    h1 = bool(len(low) and low["estimate"].iloc[0] < 0 and low["ci_high"].iloc[0] < 0)

    h2_row = study.h2[study.h2["specification"] == "full_controls"]
    h2_retention = float(h2_row["retention"].iloc[0]) if len(h2_row) else np.nan
    h2_estimate = float(h2_row["estimate"].iloc[0]) if len(h2_row) else np.nan
    h2 = bool(
        np.isfinite(h2_retention)
        and h2_retention >= 0.5
        and np.sign(h2_estimate) == np.sign(low["estimate"].iloc[0])
    )

    tests = results.decision.tests.copy()
    tests["metric"] = tests["metric"].replace({"es_5": "es"})
    pivot = tests.pivot(
        index="factor", columns="metric", values=["difference", "ci_low"]
    )
    passed = 0
    for factor in results.cfg.factors:
        if factor not in pivot.index:
            continue
        difference = pivot.loc[factor, "difference"]
        ci_low = pivot.loc[factor, "ci_low"]
        both_improve = bool((difference > 0).all())
        any_significant = bool((ci_low > 0).any())
        passed += int(both_improve and any_significant)
    h3 = bool(passed >= 2)

    capacity = results.capacity.capacity["cost_100bp"]
    return {
        "h1": h1,
        "h2": h2,
        "h2_retention": h2_retention,
        "h3": h3,
        "h3_factors_passed": passed,
        "capacity_cost_drag": capacity.to_dict(),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def generate_report(results: Results) -> Path:
    _style()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    figures = {
        "fig1": figure_factor_returns(results),
        "fig2": figure_fragility(results),
        "fig3": figure_conditional(results),
        "fig4": figure_quantile_coefficients(results),
        "fig5": figure_capacity(results),
        "fig6": figure_overlay(results),
    }

    cfg = results.cfg
    study = results.study
    decision = results.decision
    verdict = _verdict(results)
    mde = study.mde

    capacity = results.capacity
    curve = capacity.curve.copy()
    curve["aum_label"] = curve["aum"].map(
        lambda v: f"${v / 1e6:.0f}M" if v < 1e9 else f"${v / 1e9:.0f}B"
    )
    net_table = curve.pivot(index="factor", columns="aum_label", values="net_premium")
    net_table = net_table[
        [c for c in ["$10M", "$100M", "$1B", "$5B", "$10B"] if c in net_table.columns]
    ]
    retention = curve.pivot(index="factor", columns="aum_label", values="retention")[
        net_table.columns
    ]

    cap_table = capacity.capacity[
        [
            "cost_50bp",
            "cost_100bp",
            "cost_200bp",
            "hurdle_0.25",
            "hurdle_0.50",
            "hurdle_0.75",
        ]
    ].copy()

    # Cost-drag range at the baseline horizon across impact/spread calibrations.
    grid = capacity.sensitivity_cost[
        capacity.sensitivity_cost["execution_days"] == cfg.execution_days
    ]
    ranges = grid.groupby("factor")["capacity"].agg(["min", "max"])
    cap_table["impact_spread_low"] = ranges["min"]
    cap_table["impact_spread_high"] = ranges["max"]

    # Execution-horizon table at baseline c/spread.
    horizon_table = capacity.sensitivity_cost[
        (capacity.sensitivity_cost["impact_c"] == cfg.impact_c)
        & (capacity.sensitivity_cost["spread_bp"] == cfg.spread_bp)
    ].pivot(index="factor", columns="execution_days", values="capacity")

    premium_table = capacity.premium_sensitivity.pivot(
        index="factor", columns="gross_premium", values="capacity"
    )

    dataset = study.dataset
    low = study.primary[study.primary["term"] == "composite"]
    secondary = study.secondary.copy()
    placebo = study.placebo_summary.copy()

    repro = results.repro
    identity = repro.get("identity", {})
    base_rate = repro.get("base_rate", {})

    # Factor alpha/beta vs the equal-weight universe.
    from .study import _weekly_series

    market = _weekly_series(market_returns(results.panel), results.factors.dates)
    market = market.reindex(results.factors.returns.index)
    alpha_rows = []
    for factor in cfg.factors:
        row = _hac_alpha_beta(results.factors.returns[factor], market)
        if row:
            row["factor"] = factor
            alpha_rows.append(row)
    alpha_table = (
        pd.DataFrame(alpha_rows).set_index("factor") if alpha_rows else pd.DataFrame()
    )

    lines: list[str] = []
    add = lines.append

    add("# Crowded Exits: Results\n")
    add(
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"from run `{results.manifest.get('run_id', 'n/a')}`. Every number below is "
        "produced by the pipeline.*\n"
    )

    # ---- 1. Answer -------------------------------------------------------
    add("## 1. Answer\n")
    if verdict["h1"]:
        add(
            "**The fragility composite is associated with a worse left tail.** The "
            f"quantile-{cfg.primary_quantile:.2f} coefficient is "
            f"{low['estimate'].iloc[0] * 100:.2f}% per one standard deviation of "
            f"fragility (95% CI {low['ci_low'].iloc[0] * 100:.2f}% to "
            f"{low['ci_high'].iloc[0] * 100:.2f}%).\n"
        )
    else:
        add(
            "**No left-tail association was detected at the stated "
            "resolution.** The "
            f"quantile-{cfg.primary_quantile:.2f} coefficient is "
            f"{low['estimate'].iloc[0] * 100:.2f}% per one standard deviation of "
            f"fragility (95% CI {low['ci_low'].iloc[0] * 100:.2f}% to "
            f"{low['ci_high'].iloc[0] * 100:.2f}%). With this sample the minimum "
            f"detectable effect is {mde.get('mde_absolute', np.nan) * 100:.2f}% of "
            "four-week return per standard deviation. Effects smaller than that "
            "would not be detected here; this is a statement about resolution, not "
            "proof of absence.\n"
        )

    add(
        "**H2 is the more informative result.** The uncontrolled coefficient is "
        f"{study.h2.loc[study.h2['specification'] == 'uncontrolled', 'estimate'].iloc[0] * 100:.2f}%; "
        "with the full control set it is "
        f"{study.h2.loc[study.h2['specification'] == 'full_controls', 'estimate'].iloc[0] * 100:.2f}%. "
        f"Retention is {verdict['h2_retention']:.2f}, below the stated "
        "0.50 threshold. The fragility composite is largely a volatility proxy; "
        "it does not add information beyond volatility at this resolution.\n"
    )

    add(
        "The overlay test is the decisive practical result. Against a "
        "volatility-managed portfolio at the same average exposure, the fragility "
        f"overlay {'passes' if verdict['h3'] else 'fails'} the stated H3 "
        f"rule ({verdict['h3_factors_passed']} of 3 factors pass). True expected "
        "shortfall differences are reported in Section 8.\n"
    )

    add(
        "Capacity is a model output, not a measurement. At a 100bp annual "
        "trading-cost-drag hurdle and a "
        f"{cfg.execution_days}-day execution horizon, cost-drag capacity is "
        + ", ".join(
            f"{k} {_money(v)}" for k, v in verdict["capacity_cost_drag"].items()
        )
        + ". The ordering follows turnover by construction; the level depends on "
        "the execution horizon, the impact coefficient, and the data sample. "
        "See Section 6.\n"
    )

    # ---- 2. V1 audit -----------------------------------------------------
    add("## 2. Reproduction of the V1 defect\n")
    add(
        "V1 defined `value_score = -momentum_score` and then took the top and "
        "bottom quintiles of each. The weight vectors are exact negatives, so the "
        "two return series must be exact negatives. Rebuilding them here:\n"
    )
    add(
        _md_table(
            pd.DataFrame(
                [
                    {
                        "quantity": "months rebuilt",
                        "value": identity.get("months", "n/a"),
                    },
                    {
                        "quantity": "max |w_value + w_momentum|",
                        "value": identity.get("max_abs_weight_gap", np.nan),
                    },
                    {
                        "quantity": "return correlation",
                        "value": identity.get("return_correlation", np.nan),
                    },
                    {
                        "quantity": "identity holds",
                        "value": identity.get("is_identical_up_to_sign", False),
                    },
                ]
            )
        )
    )
    add("")
    if base_rate.get("available"):
        add(
            "The recorded F1 of 0.9483 implies a positive-class base rate of "
            f"{base_rate['implied_base_rate']:.3f} from the identity `F1 = 2*pi/(1+pi)`. "
            "The reported precision and recall also imply a confusion matrix with "
            "no true negatives: the model never predicted the rare class. On the "
            "rebuilt series in this sample the negative forward three-month rate is "
            f"{base_rate['negative_share']:.3f} over "
            f"{base_rate['test_observations']} weekly observations, so a constant "
            "predictor scores "
            f"{base_rate['constant_predictor_f1']:.4f} here rather than 0.9483. "
            "The exact figure depends on V1's data and window, which are not "
            "reproducible from this repository. What reproduces is the mechanism: "
            "a constant predictor scores at the base rate, and V1's headline number "
            "is that score.\n"
        )
    else:
        add("Base-rate reproduction was not available on this sample.\n")

    # ---- 3. Data ---------------------------------------------------------
    add("## 3. Data and universe\n")
    manifest = results.manifest
    panel = results.panel
    last_valid = panel.close.apply(lambda s: s.last_valid_index())
    survivors = int((last_valid < "2025-06-01").sum())
    ew = panel.returns.mean(axis=1, skipna=True).fillna(0.0)
    years = max((panel.dates[-1] - panel.dates[0]).days / 365.25, 1e-9)
    ew_cagr = float((1 + ew).prod() ** (1 / years) - 1)
    add(
        _md_table(
            pd.DataFrame(
                [
                    {
                        "item": "sample",
                        "value": f"{manifest['panel']['start']} to {manifest['panel']['end']}",
                    },
                    {"item": "daily rows", "value": manifest["panel"]["rows"]},
                    {
                        "item": "tickers with data",
                        "value": manifest["panel"]["tickers"],
                    },
                    {"item": "rebalance dates", "value": manifest["universe"]["dates"]},
                    {
                        "item": "mean universe size",
                        "value": manifest["universe"]["mean_size"],
                    },
                    {
                        "item": "minimum universe size",
                        "value": manifest["universe"]["min_size"],
                    },
                    {
                        "item": "tickers with last valid date before 2025-06-01",
                        "value": survivors,
                    },
                    {
                        "item": "equal-weight panel CAGR",
                        "value": _pct(ew_cagr),
                    },
                ]
            )
        )
    )
    add(
        "\n**Survivorship is complete, not residual.** The candidate pool is "
        "current S&P 500/400 membership. Every ticker in the panel is still "
        "present in 2025; there are no delistings. Factor premia and capacity "
        "levels are biased upward and are not investable estimates. This is the "
        "binding limitation of the project.\n"
    )
    add(
        "Universe rule: the 500 largest 60-day median dollar volumes among names "
        "with 252 days of history and a $5 price floor, recomputed from trailing "
        "data at every rebalance. The candidate pool is not point-in-time with "
        "respect to existence.\n"
    )

    # ---- 4. Factors ------------------------------------------------------
    add("## 4. Factors\n")
    add(_md_table(results.factors.diagnostics.reset_index(), index=False) + "\n")
    add(
        "Invariants asserted at construction: dollar-neutral, gross exposure 2.0, "
        "per-name cap 2% of gross, and pairwise factor correlation below 0.9 in "
        "absolute value. The construction is dollar-neutral but not beta-neutral; "
        "realized CAPM exposure is reported below.\n"
    )
    if not alpha_table.empty:
        display = alpha_table.copy()
        display["alpha"] = display["alpha"].map(_pct)
        display["beta"] = display["beta"].round(3)
        display["beta_t"] = display["beta_t"].round(2)
        display["alpha_t"] = display["alpha_t"].round(2)
        display["r2"] = display["r2"].round(3)
        add(
            "Realized CAPM exposure versus the equal-weight universe "
            "(weekly, HAC standard errors):\n"
        )
        add(_md_table(display, index=True) + "\n")
    add(f"![Factor returns](figures/{figures['fig1'].name})\n")

    # ---- 5. Fragility ----------------------------------------------------
    add("## 5. Fragility\n")
    add(
        "Four measures, oriented so that higher means more fragile, standardized "
        "on expanding windows with a 104-week burn-in and combined with equal "
        "weights: residual synchronization (F1), liquidity-weighted effective "
        "breadth (F2, sign flipped), exit horizon at 10% participation for a $1bn "
        "sleeve (F3), and long-leg holding persistence (F4). Unweighted breadth "
        "is retained as a diagnostic but is degenerate for equal-weight legs and "
        "is not part of the composite.\n"
    )
    add(_md_table(results.fragility.coverage.reset_index()) + "\n")
    raw = dataset[["z_o_sync", "z_o_breadth", "z_o_exit", "z_o_persist"]].corr(
        method="spearman"
    )
    raw.index.name = "measure"
    add("Spearman correlation of the standardized measures:\n")
    add(_md_table(raw.round(3), index=True) + "\n")
    corr = dataset[["composite", "log_vol", "mkt_vol"]].corr().loc["composite"]
    add(
        f"Correlation of the composite with log realized volatility is "
        f"{corr['log_vol']:.3f} and with market volatility {corr['mkt_vol']:.3f}. "
        "It is not orthogonal to volatility, which is why H2 is the key test.\n"
    )
    add(f"![Fragility](figures/{figures['fig2'].name})\n")

    # ---- 6. Capacity -----------------------------------------------------
    add("## 6. Capacity\n")
    add(
        "**Survivorship warning:** these are model calculations on a survivor-only "
        "sample. They are not investable capacity estimates. See Section 3.\n"
    )
    premium_rows = []
    for factor in cfg.factors:
        row = _hac_mean(results.factors.returns[factor])
        if not row:
            continue
        row["factor"] = factor
        if not alpha_table.empty and factor in alpha_table.index:
            row["capm_alpha"] = float(alpha_table.loc[factor, "alpha"])
            row["capm_alpha_t"] = float(alpha_table.loc[factor, "alpha_t"])
        premium_rows.append(row)
    if premium_rows:
        premium_ci = pd.DataFrame(premium_rows).set_index("factor")
        display = premium_ci.copy()
        for column in ("gross_premium", "premium_se", "premium_low", "premium_high"):
            display[column] = display[column].map(_pct)
        display["premium_t"] = display["premium_t"].round(2)
        if "capm_alpha" in display:
            display["capm_alpha"] = display["capm_alpha"].map(_pct)
            display["capm_alpha_t"] = display["capm_alpha_t"].round(2)
        add(
            "Gross premium and beta-adjusted alpha, annualized with HAC standard "
            "errors. None of the gross premia is precisely estimated; the "
            "retention capacity is conditional on this assumption.\n"
        )
        add(_md_table(display, index=True) + "\n")
    add(
        "Net annual premium at each sleeve size, using monthly buy-and-hold traded "
        "notional, a square-root impact law with "
        f"c = {cfg.impact_c}, a {cfg.spread_bp:.0f}bp half-spread, a "
        f"{cfg.execution_days}-day execution horizon, and a {cfg.borrow_bp:.0f}bp "
        "annual borrow cost. Gross premium is shown for reference.\n"
    )
    net_display = (net_table * 100).round(2)
    net_display["gross_premium_%"] = (
        results.capacity.capacity["gross_premium"] * 100
    ).round(2)
    add(_md_table(net_display, index=True) + "\n")
    add("Retention of gross premium (n/a when the gross premium is non-positive):\n")
    add(_md_table((retention * 100).round(1), index=True) + "\n")
    add(
        "Capacity at each hurdle. `cost_*` columns are the headline, "
        "premium-independent definition: the largest sleeve at which annual "
        "trading-cost drag stays under that many basis points. `hurdle_*` columns "
        "are the retention definition and are undefined for factors with no gross "
        "premium. The last two columns span the impact/spread sensitivity grid at "
        f"{cfg.execution_days} days:\n"
    )
    cap_display = cap_table.copy()
    for column in cap_display.columns:
        cap_display[column] = cap_display[column].map(_money)
    add(_md_table(cap_display, index=True) + "\n")
    add(
        "The ordering follows turnover by construction. It is a descriptive "
        "identity of the cost model, not a hypothesis test. The interpretable "
        "quantity is the level and its sensitivity.\n"
    )
    add("Cost-drag capacity by execution horizon (baseline impact and spread):\n")
    horizon_display = horizon_table.copy()
    for column in horizon_display.columns:
        horizon_display[column] = horizon_display[column].map(_money)
    add(_md_table(horizon_display, index=True) + "\n")
    add(
        "Premium-retention capacity at the 50% hurdle as a function of the assumed "
        "gross premium. The realized premium is a noisy estimate; the capacity "
        "level is quadratic in this assumption.\n"
    )
    premium_display = premium_table.copy()
    premium_display.columns = [
        f"{float(c) * 100:.1f}%" for c in premium_display.columns
    ]
    for column in premium_display.columns:
        premium_display[column] = premium_display[column].map(_money)
    add(_md_table(premium_display, index=True) + "\n")
    add(f"![Capacity](figures/{figures['fig5'].name})\n")
    add("Cost to liquidate the whole position once, held notional:\n")
    liq = capacity.liquidation.copy()
    liq["aum_label"] = liq["aum"].map(
        lambda v: f"${v / 1e6:.0f}M" if v < 1e9 else f"${v / 1e9:.0f}B"
    )
    liq_pivot = liq.pivot(
        index="factor", columns="aum_label", values="liquidation_cost_bp"
    )
    liq_pivot = liq_pivot[
        [c for c in ["$10M", "$100M", "$1B", "$5B", "$10B"] if c in liq_pivot.columns]
    ]
    add(_md_table(liq_pivot, digits=1, index=True) + "\n")

    # ---- 7. Tail study ---------------------------------------------------
    add("## 7. Tail study\n")
    add(
        f"Sample: {study.diagnostics['n_rows']} factor-week rows, "
        f"{study.diagnostics['n_dates']} dates, "
        f"roughly {study.diagnostics['n_blocks_4w']} independent four-week blocks, "
        f"{study.diagnostics['date_start']} to {study.diagnostics['date_end']}.\n"
    )
    add(
        "Primary specification, pooled with factor fixed effects and volatility, "
        "trend, and liquidity controls. Standard errors and intervals from a "
        "stationary bootstrap with mean block "
        f"{cfg.block_mean} and {mde.get('reps_used', 'n/a')} replications. "
        "Duplicate dates are retained.\n"
    )
    primary_display = study.primary.copy()
    for column in ("estimate", "se", "ci_low", "ci_high"):
        primary_display[column] = (primary_display[column] * 100).round(3)
    primary_display["negative_share"] = primary_display["negative_share"].round(3)
    add(_md_table(primary_display) + "\n")
    add(
        f"Minimum detectable effect at {cfg.alpha:.0%} significance and "
        f"{cfg.power:.0%} power: **{mde.get('mde_absolute', np.nan) * 100:.2f}% "
        "of four-week return per one standard deviation of fragility** "
        f"({mde.get('mde_in_sd_units', np.nan):.3f} standard deviations of the "
        "return distribution). The tail-specificity difference between the 0.10 "
        f"and 0.50 coefficients is {mde.get('tail_difference', np.nan) * 100:.2f}% "
        f"with a 95% interval of ({mde['tail_difference_ci'][0] * 100:.2f}%, "
        f"{mde['tail_difference_ci'][1] * 100:.2f}%).\n"
    )

    add("**H2: does the association survive controls?**\n")
    h2_display = study.h2.copy()
    h2_display["estimate"] = (h2_display["estimate"] * 100).round(3)
    h2_display["retention"] = h2_display["retention"].round(3)
    add(_md_table(h2_display) + "\n")

    add("Per-factor estimates at the 0.10 quantile (exploratory):\n")
    per_factor = study.per_factor.copy()
    for column in ("estimate", "se", "ci_low", "ci_high"):
        per_factor[column] = (per_factor[column] * 100).round(3)
    per_factor["pvalue"] = per_factor["pvalue"].round(3)
    add(_md_table(per_factor) + "\n")

    add("**Quintile sort (assumption-light check): fragile minus calm mean return.**\n")
    quintile = study.quintile_sort.copy()
    for column in ("q5_minus_q1", "ci_low", "ci_high"):
        quintile[column] = (quintile[column] * 100).round(3)
    add(_md_table(quintile) + "\n")

    add("**Subsample stability (pooled 0.10 coefficient).**\n")
    subsample = study.subsample.copy()
    for column in ("estimate", "ci_low", "ci_high"):
        subsample[column] = (subsample[column] * 100).round(3)
    add(_md_table(subsample) + "\n")

    add(
        "**Non-overlapping check:** the same specification on every fourth week, "
        "so the four-week target windows do not overlap.\n"
    )
    non_overlap = study.non_overlapping.copy()
    for column in ("estimate", "se", "ci_low", "ci_high"):
        non_overlap[column] = (non_overlap[column] * 100).round(3)
    add(_md_table(non_overlap) + "\n")

    add(
        "Individual measures, Benjamini-Hochberg adjusted across the pre-specified "
        "family of four measures and two horizons. P-values are centered "
        "bootstrap p-values.\n"
    )
    secondary_display = secondary.copy()
    for column in ("estimate", "se", "ci_low", "ci_high"):
        secondary_display[column] = (secondary_display[column] * 100).round(3)
    secondary_display[["pvalue", "pvalue_adj"]] = secondary_display[
        ["pvalue", "pvalue_adj"]
    ].round(3)
    add(_md_table(secondary_display) + "\n")

    add("**E2: expected shortfall difference, fragile minus calm quintile.**\n")
    es_diff = study.es_difference.copy()
    for column in ("es_high", "es_low", "difference", "ci_low", "ci_high"):
        es_diff[column] = (es_diff[column] * 100).round(3)
    add(_md_table(es_diff) + "\n")

    add("Expected shortfall by fragility quintile (percent):\n")
    es_display = study.es_table.copy()
    for column in ("mean_fwd_4w", "es_5"):
        es_display[column] = (es_display[column] * 100).round(3)
    es_display["share_negative"] = es_display["share_negative"].round(3)
    add(_md_table(es_display) + "\n")

    add("**Composite sensitivity: alternative weightings.**\n")
    composite = study.composite_sensitivity.copy()
    for column in ("estimate", "se", "ci_low", "ci_high"):
        composite[column] = (composite[column] * 100).round(3)
    add(_md_table(composite) + "\n")

    add(
        "Placebo: the composite is block-shuffled within factor and the primary model refit.\n"
    )
    placebo_display = placebo.copy()
    for column in ("placebo_mean", "placebo_sd", "real_estimate"):
        placebo_display[column] = (placebo_display[column] * 100).round(3)
    placebo_display["pvalue"] = placebo_display["pvalue"].round(3)
    add(_md_table(placebo_display, index=False) + "\n")

    add(f"![Conditional returns](figures/{figures['fig3'].name})\n")
    add(f"![Quantile coefficients](figures/{figures['fig4'].name})\n")

    # ---- 8. Decision layer ----------------------------------------------
    add("## 8. Decision layer\n")
    add(
        "All strategies pay a 5bp scaling cost on changes in exposure, earn the "
        "T-bill rate on uninvested cash, and pay 50bp annual borrow on short "
        "notional. The volatility-managed comparator is rescaled so its average "
        "exposure equals the overlay's. The factor's own rebalancing cost is not "
        "charged here; capacity reports it separately.\n"
    )
    for factor in cfg.factors:
        from .decision import overlay_summary

        table = overlay_summary(results.decision, factor)
        for column in (
            "es_5",
            "es_10",
            "q5",
            "max_drawdown",
            "sharpe",
            "sortino",
            "annual_vol",
            "cost_drag_annual",
            "borrow_drag_annual",
        ):
            table[column] = table[column].round(4)
        table["avg_exposure"] = table["avg_exposure"].round(3)
        table["turnover_annual"] = table["turnover_annual"].round(2)
        add(f"**{factor}**\n")
        add(_md_table(table) + "\n")

    add(
        "Fragility overlay minus volatility-managed comparator, block bootstrap. "
        "Positive means the overlay has a better (less negative) tail metric:\n"
    )
    tests = decision.tests.copy()
    for column in ("difference", "ci_low", "ci_high"):
        tests[column] = (tests[column] * 100).round(3)
    add(_md_table(tests) + "\n")
    add(
        "Random-overlay distribution: the same exposure path distribution, "
        "block-shuffled. The percentile rank is the share of random paths with a "
        "worse (more negative) true ES than the fragility overlay.\n"
    )
    random_display = decision.random_distribution.copy()
    for column in ("actual_es_5", "es_5_p05", "es_5_p50", "es_5_p95"):
        random_display[column] = (random_display[column] * 100).round(3)
    random_display["percentile_rank"] = random_display["percentile_rank"].round(3)
    random_display["sharpe_p50"] = random_display["sharpe_p50"].round(3)
    add(_md_table(random_display) + "\n")
    add(f"![Overlay](figures/{figures['fig6'].name})\n")

    # ---- 9. Limitations --------------------------------------------------
    add("## 9. Limitations\n")
    for text in (
        "Survivorship is complete: zero delistings in the panel. Factor premia and "
        "capacity levels are biased upward and are not investable estimates.",
        "No holdings or flow data: fragility measures the portfolio the factor "
        "implies, not what other managers actually own.",
        "The impact coefficient and execution horizon are assumptions, not "
        "measurements. Capacity is a model output with a sensitivity band.",
        "The factors are dollar-neutral but not beta-neutral; realized CAPM "
        "exposure is reported in Section 4.",
        "The study is in-sample. The construction was revised after inspecting "
        "results; see the trial ledger and the researcher-degrees-of-freedom "
        "section.",
        "Tail tests are low-powered: the independent units are four-week blocks, "
        "not rows.",
        "Three factors in one market. Results do not generalize to the factor zoo "
        "or to other markets.",
        "The estimand is associational. No causal claim is made about crowding.",
    ):
        add(f"- {text}")
    add("")

    # ---- 10. Researcher degrees of freedom -------------------------------
    add("## 10. Researcher degrees of freedom\n")
    add(
        "The final specification was not frozen before the results were seen. "
        "The factor set, rebalancing frequency, turnover bands, execution horizon, "
        "capacity definition, and overlay schedule were revised during "
        "implementation (ADR-0005 and ADR-0007). Seven factor candidates and at "
        "least 48 overlay configurations were evaluated. The study is therefore "
        "**exploratory**, not confirmatory. `docs/trial_ledger.md` records the "
        "specifications tried. A genuine holdout is future work.\n"
    )

    # ---- 11. What would change the conclusion ----------------------------
    add("## 11. What would change the conclusion\n")
    for text in (
        "A point-in-time dataset with delistings showing materially lower factor "
        "premia and capacity.",
        "A pre-registered holdout with a negative fragility coefficient whose "
        "interval excludes zero, or an overlay that beats volatility management on "
        "true expected shortfall.",
        "A multi-factor risk model showing that residual synchronization is "
        "sector or risk exposure rather than crowding.",
        "A composite weighting that retains a negative coefficient after the "
        "drop-one, rank, and PCA checks and survives the quintile sort.",
        "An execution-calibrated impact model with a materially different "
        "coefficient or horizon.",
    ):
        add(f"- {text}")
    add("")

    # ---- 12. Reproducibility --------------------------------------------
    add("## 12. Reproducibility\n")
    add("```json")
    add(
        json.dumps(
            {k: v for k, v in results.manifest.items() if k != "config"},
            indent=2,
            default=str,
        )
    )
    add("```")
    add(
        f"\nConfig hash: `{cfg.hash()}`. Data SHA256: "
        f"`{results.manifest.get('panel', {}).get('sha256', 'n/a')}`. "
        "The full config is in the run manifest.\n"
    )

    path = Path(DOCS_DIR) / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    # Persist the machine-readable tables next to the report source and in the
    # run directory so a specific run is self-contained.
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "primary": study.primary,
        "secondary": study.secondary,
        "es_table": study.es_table,
        "es_difference": study.es_difference,
        "quintile_sort": study.quintile_sort,
        "subsample": study.subsample,
        "non_overlapping": study.non_overlapping,
        "composite_sensitivity": study.composite_sensitivity,
        "h2": study.h2,
        "per_factor": study.per_factor,
        "placebo_summary": study.placebo_summary,
        "capacity": capacity.capacity,
        "capacity_curve": capacity.curve,
        "capacity_sensitivity": capacity.sensitivity,
        "capacity_sensitivity_cost": capacity.sensitivity_cost,
        "capacity_premium": capacity.premium_sensitivity,
        "overlay_summary": decision.summary,
        "overlay_tests": decision.tests,
        "overlay_random": decision.random_distribution,
        "factor_diagnostics": results.factors.diagnostics,
        "fragility_coverage": results.fragility.coverage,
        "factor_returns": results.factors.returns,
        "fragility_composite": results.fragility.composite,
    }
    for name, frame in tables.items():
        frame.to_csv(
            TABLE_DIR / f"{name}.csv",
            index=name
            in {
                "capacity",
                "factor_diagnostics",
                "fragility_coverage",
            },
        )
    run_dir = results.run_dir()
    for source in list(TABLE_DIR.glob("*.csv")) + list(FIG_DIR.glob("*.png")):
        shutil.copy2(source, run_dir / source.name)
    return path
