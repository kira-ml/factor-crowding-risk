"""Backtest P&L, costs, and metrics (methodology sections 4 and 7).

Funding convention: uninvested capital earns the cash rate; short proceeds are
assumed to collateralise the position and earn nothing net of borrow. This is
conservative for a de-risking overlay and is disclosed in the report.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .stats import max_drawdown, sharpe
from .targets import expected_shortfall


def run_strategy(
    factor_returns: pd.Series,
    weight: pd.Series,
    cash_rate: pd.Series,
    cfg: Config,
    cost_bp: float | None = None,
) -> pd.DataFrame:
    weight = weight.reindex(factor_returns.index).ffill().fillna(1.0)
    if (weight < -1e-9).any() or (weight > cfg.vol_scale_cap + 1e-9).any():
        raise ValueError("exposure outside [0, vol_scale_cap]")
    rf = factor_returns.fillna(0.0)
    cash = cash_rate.reindex(factor_returns.index).fillna(0.0)

    turn = weight.diff().abs().fillna(0.0)
    scaling_cost = turn * (cfg.scaling_cost_bp if cost_bp is None else cost_bp) / 1e4
    # A dollar-neutral factor has one dollar of short notional per unit of
    # exposure. Charge borrow on that notional. The short proceeds are assumed
    # to collateralise the position and earn nothing net of borrow.
    borrow = weight.clip(lower=0.0) * cfg.borrow_bp / 1e4 / 52.0
    gross = weight * rf
    funding = (1.0 - weight) * cash
    net = gross + funding - scaling_cost - borrow

    return pd.DataFrame(
        {
            "weight": weight,
            "factor_return": rf,
            "gross": gross,
            "funding": funding,
            "cost": scaling_cost,
            "borrow": borrow,
            "net": net,
        }
    )


def metrics(frame: pd.DataFrame, periods: int = 52) -> dict:
    net = frame["net"].dropna()
    if len(net) < 20:
        return {}
    downside = net[net < 0]
    sortino = (
        net.mean() / downside.std() * np.sqrt(periods)
        if len(downside) > 5 and downside.std() > 0
        else np.nan
    )
    cum = (1.0 + net).cumprod()
    years = max(len(net) / periods, 1e-9)
    return {
        "total_return": float(cum.iloc[-1] - 1.0),
        "annual_return": float(cum.iloc[-1] ** (1 / years) - 1.0),
        "annual_vol": float(net.std() * np.sqrt(periods)),
        "sharpe": sharpe(net, periods),
        "sortino": float(sortino) if np.isfinite(sortino) else np.nan,
        "max_drawdown": max_drawdown(net),
        "es_5": expected_shortfall(net, 0.05),
        "es_10": expected_shortfall(net, 0.10),
        "q5": float(net.quantile(0.05)) if len(net) > 40 else np.nan,
        "calmar": float(cum.iloc[-1] ** (1 / years) - 1.0) / abs(max_drawdown(net))
        if max_drawdown(net) < 0
        else np.nan,
        "avg_exposure": float(frame["weight"].mean()),
        "turnover_annual": float(frame["weight"].diff().abs().sum() / years),
        "cost_drag_annual": float(frame["cost"].sum() / years),
        "borrow_drag_annual": float(frame["borrow"].sum() / years),
    }


def tail_metric(net: pd.Series, q: float = 0.05) -> float:
    values = net.dropna()
    if len(values) < 40:
        return np.nan
    threshold = values.quantile(q)
    return float(values[values <= threshold].mean())


def compare_strategies(
    results: dict[str, pd.DataFrame],
    cfg: Config,
) -> pd.DataFrame:
    rows = []
    for name, frame in results.items():
        row = metrics(frame)
        if not row:
            continue
        row["strategy"] = name
        rows.append(row)
    columns = (
        ["strategy"] + [c for c in rows[0] if c != "strategy"] if rows else ["strategy"]
    )
    return pd.DataFrame(rows)[columns]


def cost_per_unit(factor_returns: pd.Series, cfg: Config) -> pd.Series:
    """Placeholder hook for factor-level cost passed from the capacity model.

    The overlay test charges scaling costs here; factor rebalance costs are
    charged inside the capacity module and reported separately.
    """
    return pd.Series(0.0, index=factor_returns.index)
