"""Capacity under a square-root market-impact model (methodology section 4).

The square-root law makes weekly cost linear in ``sqrt(A)``:

    cost_t(A) = 0.5 * spread * S1_t + c * sqrt(A) * S2_t
    S1_t = sum_i |dw_i|
    S2_t = sum_i |dw_i| * sigma_i * sqrt(|dw_i| / ADV_i)

So the net-premium curve has a closed form and capacity is solved exactly rather
than searched numerically. Monotonicity follows from ``S2 >= 0``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .data import Panel
from .factors import FactorSet, portfolio_drift_trades
from .universe import Universe


@dataclass
class Capacity:
    curve: pd.DataFrame  # factor, aum, cost_bp, net_premium, gross_premium, retention
    capacity: pd.DataFrame  # factor x hurdle
    sensitivity: pd.DataFrame  # factor x impact coefficient x spread x horizon
    liquidation: pd.DataFrame  # factor x aum, cost to exit the whole position
    turnover: pd.Series
    terms: pd.DataFrame  # factor x s1_mean, s2_mean (cost decomposition)
    sensitivity_cost: pd.DataFrame  # cost-drag capacity across the grid
    premium_sensitivity: pd.DataFrame  # retention capacity vs assumed premium


def _sigma(panel: Panel, dates: pd.DatetimeIndex) -> pd.DataFrame:
    vol = panel.returns.rolling(60, min_periods=30).std()
    return vol.reindex(dates, method="ffill")


def _adv(universe: Universe, dates: pd.DatetimeIndex) -> pd.DataFrame:
    return universe.adv.reindex(dates, method="ffill")


def traded_notional(
    weights: pd.DataFrame,
    weekly: pd.DataFrame,
    factor_returns: pd.Series,
) -> pd.DataFrame:
    """Weight change after return drift, at each rebalance."""
    prev = weights.shift(1).fillna(0.0)
    r_prev = weekly.shift(1).reindex_like(weights)
    rf_prev = factor_returns.shift(1).reindex(weights.index)
    drift = prev * (1.0 + r_prev).div(1.0 + rf_prev, axis=0)
    drift = drift.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return weights - drift


def cost_terms(
    weights: pd.DataFrame,
    sigma: pd.DataFrame,
    adv: pd.DataFrame,
    execution_days: int = 1,
) -> tuple[pd.Series, pd.Series]:
    """Return (S1, S2) such that cost(A) = 0.5*spread*S1 + c*sqrt(A)*S2.

    ``execution_days`` is the horizon over which a rebalance is worked. Cost
    scales with participation per day, so working an order over ten days rather
    than one reduces impact by sqrt(10).
    """
    absolute = weights.abs().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    sigma = sigma.reindex_like(absolute)
    adv = adv.reindex_like(absolute)
    s1 = absolute.sum(axis=1)
    capacity = (
        (adv * max(1, execution_days)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )
    ratio = (
        (absolute / capacity)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .clip(lower=0.0)
    )
    s2 = (absolute * sigma.fillna(0.0) * np.sqrt(ratio)).sum(axis=1)
    return s1, s2


def _mean_cost(
    s1: pd.Series, s2: pd.Series, aum: float, c: float, spread_bp: float
) -> float:
    half_spread = 0.5 * spread_bp / 1e4
    return float(half_spread * s1.mean() + c * np.sqrt(aum) * s2.mean())


def _solve(
    s1: pd.Series,
    s2: pd.Series,
    gross: float,
    cfg: Config,
    target: float,
    c: float,
    spread_bp: float,
) -> float:
    if gross <= 0:
        return np.nan
    fixed = cfg.borrow_bp / 1e4 + cfg.financing_bp / 1e4
    half_spread = 0.5 * spread_bp / 1e4
    slope = 52.0 * c * float(s2.mean())
    intercept = 52.0 * half_spread * float(s1.mean()) + fixed
    # net(A) = gross - intercept - slope*sqrt(A) >= target
    if slope <= 0:
        return (
            float(cfg.aum_bounds[1])
            if gross - intercept >= target
            else float(cfg.aum_bounds[0])
        )
    budget = gross - intercept - target
    if budget <= 0:
        return float(cfg.aum_bounds[0])
    aum = (budget / slope) ** 2
    return float(np.clip(aum, *cfg.aum_bounds))


def _solve_cost_drag(
    s1: pd.Series,
    s2: pd.Series,
    cfg: Config,
    target_bp: float,
    c: float,
    spread_bp: float,
) -> float:
    """Largest AUM at which annual implementation cost stays below ``target_bp``.

    Premium-independent, so it is defined for factors with no gross premium. This
    is the headline capacity definition because it answers the allocator's
    question directly: at what size do costs become material? Trading costs only;
    borrow and financing are carry costs and are reported separately.
    """
    fixed = 52.0 * 0.5 * spread_bp / 1e4 * float(s1.mean())
    slope = 52.0 * c * float(s2.mean())
    budget = target_bp / 1e4 - fixed
    if slope <= 0:
        return float(cfg.aum_bounds[1]) if budget >= 0 else float(cfg.aum_bounds[0])
    if budget <= 0:
        return float(cfg.aum_bounds[0])
    return float(np.clip((budget / slope) ** 2, *cfg.aum_bounds))


def build_capacity(
    panel: Panel,
    factors: FactorSet,
    universe: Universe,
    weekly: pd.DataFrame,
    cfg: Config,
) -> Capacity:
    dates = factors.dates
    sigma = _sigma(panel, dates)
    adv = _adv(universe, dates)

    gross_premium = {f: 52.0 * float(factors.returns[f].mean()) for f in cfg.factors}
    if factors.portfolio_weights is not None and factors.portfolio_dates is not None:
        traded = {
            f: portfolio_drift_trades(
                factors.portfolio_weights[f],
                factors.portfolio_dates,
                weekly,
                factors.returns[f],
                dates,
            )
            for f in cfg.factors
        }
    else:
        traded = {
            f: traded_notional(factors.weights[f], weekly, factors.returns[f])
            for f in cfg.factors
        }
        mask = pd.Series(
            pd.Index(factors.dates).isin(pd.Index(factors.portfolio_dates))
            if factors.portfolio_dates is not None
            else True,
            index=factors.dates,
        )
        for factor in cfg.factors:
            traded[factor] = traded[factor].where(mask, 0.0)

    terms = {}
    turnover = {}
    for factor in cfg.factors:
        s1, s2 = cost_terms(traded[factor], sigma, adv, cfg.execution_days)
        terms[factor] = (s1, s2)
        turnover[factor] = float(s1.mean())
    turnover = pd.Series(turnover)

    # ---- capacity at each hurdle ----------------------------------------
    cap_rows = []
    for factor in cfg.factors:
        for hurdle in cfg.hurdle_grid:
            target = hurdle * gross_premium[factor]
            s1, s2 = terms[factor]
            value = _solve(
                s1, s2, gross_premium[factor], cfg, target, cfg.impact_c, cfg.spread_bp
            )
            cap_rows.append({"factor": factor, "hurdle": hurdle, "capacity": value})
    capacity = pd.DataFrame(cap_rows).pivot(
        index="factor", columns="hurdle", values="capacity"
    )
    capacity.columns = [f"hurdle_{h:.2f}" for h in capacity.columns]
    capacity["gross_premium"] = pd.Series(gross_premium)
    capacity["turnover"] = turnover

    # Premium-independent capacity: AUM at which annual cost drag hits a hurdle.
    for hurdle_bp in cfg.cost_hurdle_bp_grid:
        values = {}
        for factor in cfg.factors:
            s1, s2 = terms[factor]
            values[factor] = _solve_cost_drag(
                s1, s2, cfg, hurdle_bp, cfg.impact_c, cfg.spread_bp
            )
        capacity[f"cost_{hurdle_bp:.0f}bp"] = pd.Series(values)

    # ---- main curve ------------------------------------------------------
    rows = []
    for factor in cfg.factors:
        s1, s2 = terms[factor]
        for aum in cfg.aum_grid:
            mean_cost = _mean_cost(s1, s2, aum, cfg.impact_c, cfg.spread_bp)
            annual = 52.0 * mean_cost
            net = (
                gross_premium[factor]
                - annual
                - cfg.borrow_bp / 1e4
                - cfg.financing_bp / 1e4
            )
            rows.append(
                {
                    "factor": factor,
                    "aum": aum,
                    "turnover": turnover[factor],
                    "cost_bp": mean_cost * 1e4,
                    "annual_cost": annual,
                    "gross_premium": gross_premium[factor],
                    "net_premium": net,
                    "retention": net / gross_premium[factor]
                    if gross_premium[factor] > 0
                    else np.nan,
                }
            )
    curve = pd.DataFrame(rows)

    # ---- sensitivity -----------------------------------------------------
    horizons = tuple(getattr(cfg, "execution_days_grid", (cfg.execution_days,)))
    sens_rows = []
    for factor in cfg.factors:
        target = cfg.hurdle * gross_premium[factor]
        for horizon in horizons:
            s1, s2 = cost_terms(traded[factor], sigma, adv, horizon)
            for c in cfg.impact_c_grid:
                for spread in cfg.spread_bp_grid:
                    value = _solve(
                        s1, s2, gross_premium[factor], cfg, target, c, spread
                    )
                    sens_rows.append(
                        {
                            "factor": factor,
                            "execution_days": horizon,
                            "impact_c": c,
                            "spread_bp": spread,
                            "capacity": value,
                        }
                    )
    sensitivity = pd.DataFrame(sens_rows)

    # Cost-drag capacity across the full grid. The ordering is a turnover
    # identity; the level is the interpretable quantity.
    cost_rows = []
    for factor in cfg.factors:
        for horizon in horizons:
            s1, s2 = cost_terms(traded[factor], sigma, adv, horizon)
            for c in cfg.impact_c_grid:
                for spread in cfg.spread_bp_grid:
                    value = _solve_cost_drag(s1, s2, cfg, 100.0, c, spread)
                    cost_rows.append(
                        {
                            "factor": factor,
                            "execution_days": horizon,
                            "impact_c": c,
                            "spread_bp": spread,
                            "capacity": value,
                        }
                    )
    sensitivity_cost = pd.DataFrame(cost_rows)

    # Retention capacity is undefined when the gross premium is non-positive.
    # This table makes the premium assumption explicit instead of hiding it in a
    # single point estimate.
    premium_rows = []
    premium_grid = tuple(
        getattr(cfg, "premium_assumption_grid", (0.01, 0.02, 0.03, 0.05, 0.075, 0.10))
    )
    for factor in cfg.factors:
        s1, s2 = terms[factor]
        for gross in premium_grid:
            premium_rows.append(
                {
                    "factor": factor,
                    "gross_premium": gross,
                    "hurdle": cfg.hurdle,
                    "capacity": _solve(
                        s1,
                        s2,
                        gross,
                        cfg,
                        cfg.hurdle * gross,
                        cfg.impact_c,
                        cfg.spread_bp,
                    ),
                }
            )
    premium_sensitivity = pd.DataFrame(premium_rows)

    # ---- liquidation cost (held notional, one exit) ----------------------
    liq_rows = []
    for factor in cfg.factors:
        held = factors.weights[factor].abs()
        s1_l, s2_l = cost_terms(held, sigma, adv, cfg.execution_days)
        for aum in cfg.aum_grid:
            liq_rows.append(
                {
                    "factor": factor,
                    "aum": aum,
                    "liquidation_cost_bp": _mean_cost(
                        s1_l, s2_l, aum, cfg.impact_c, cfg.spread_bp
                    )
                    * 1e4,
                }
            )
    liquidation = pd.DataFrame(liq_rows)

    result = Capacity(
        curve=curve,
        capacity=capacity,
        sensitivity=sensitivity,
        liquidation=liquidation,
        turnover=turnover,
        terms=pd.DataFrame(
            {
                factor: {
                    "s1_mean": float(terms[factor][0].mean()),
                    "s2_mean": float(terms[factor][1].mean()),
                }
                for factor in cfg.factors
            }
        ).T,
        sensitivity_cost=sensitivity_cost,
        premium_sensitivity=premium_sensitivity,
    )
    check_monotonicity(result)
    return result


def check_monotonicity(capacity: Capacity) -> None:
    for factor, group in capacity.curve.groupby("factor"):
        ordered = group.sort_values("aum")
        if (ordered["net_premium"].diff().dropna() > 1e-10).any():
            raise AssertionError(f"{factor}: net premium is not decreasing in AUM")
