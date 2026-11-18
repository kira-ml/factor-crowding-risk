import numpy as np
import pytest

from fcr.capacity import build_capacity, cost_terms, traded_notional
from fcr.factors import build_factors
from fcr.universe import build_universe


@pytest.fixture(scope="module")
def built(panel, cfg):
    universe = build_universe(panel, cfg)
    factors = build_factors(panel, universe, cfg)
    return universe, factors


def test_universe_is_point_in_time(built, panel, cfg):
    universe, _ = built
    assert len(universe.dates) > 200
    for date in list(universe.dates)[:5]:
        names = universe.members[date]
        assert len(names) >= 100
        # Every member must have enough history strictly before the date.
        history = panel.close.loc[:date, names].notna().sum()
        assert (history >= cfg.min_history_days).all()


def test_factor_invariants(built, cfg):
    _, factors = built
    for factor, weights in factors.weights.items():
        active = weights[weights.abs().sum(axis=1) > 0]
        assert active.sum(axis=1).abs().max() < 1e-6, f"{factor} not dollar-neutral"
        assert (active.abs().sum(axis=1) - cfg.gross).abs().max() < 1e-6
        assert active.abs().max().max() <= cfg.name_cap * cfg.gross + 1e-9


def test_factors_are_not_collinear(built):
    _, factors = built
    corr = factors.returns.corr()
    for i, a in enumerate(corr.columns):
        for b in corr.columns[i + 1 :]:
            assert abs(corr.loc[a, b]) < 0.9


def test_beta_diagnostic_is_small(built):
    _, factors = built
    assert factors.diagnostics["mean_abs_portfolio_beta"].max() < 0.25


def test_capacity_closed_form_matches_bruteforce(built, panel, cfg):
    universe, factors = built
    from fcr.capacity import _adv, _sigma
    from fcr.factors import weekly_returns

    weekly = weekly_returns(panel, factors.dates)
    sigma = _sigma(panel, factors.dates)
    adv = _adv(universe, factors.dates)
    traded = traded_notional(factors.weights["MOM"], weekly, factors.returns["MOM"])
    s1, s2 = cost_terms(traded, sigma, adv, cfg.execution_days)

    aum = 1e8
    fast = (
        0.5 * cfg.spread_bp / 1e4 * s1.iloc[-20:].mean()
        + cfg.impact_c * np.sqrt(aum) * s2.iloc[-20:].mean()
    )

    # Brute force on a subset of dates.
    slow = []
    for date in factors.dates[-20:]:
        row = traded.loc[date]
        names = row.index[row != 0]
        if len(names) == 0:
            continue
        dollars = row[names].abs() * aum
        part = (dollars / (adv.loc[date, names] * cfg.execution_days)).clip(lower=0)
        cost = 0.5 * cfg.spread_bp / 1e4 + cfg.impact_c * sigma.loc[
            date, names
        ] * np.sqrt(part)
        slow.append(float((row[names].abs() * cost).sum()))
    assert abs(fast - np.mean(slow)) < 1e-8


def test_capacity_monotone_and_ordered(built, panel, cfg):
    universe, factors = built
    from fcr.factors import weekly_returns

    weekly = weekly_returns(panel, factors.dates)
    capacity = build_capacity(panel, factors, universe, weekly, cfg)

    for factor, group in capacity.curve.groupby("factor"):
        ordered = group.sort_values("aum")
        assert (ordered["net_premium"].diff().dropna() <= 1e-10).all()

    # Higher turnover must produce lower cost-drag capacity, and the ordering
    # must survive every impact/spread calibration in the grid.
    ordered = capacity.capacity["cost_100bp"]
    turnover = capacity.turnover
    highest = turnover.idxmax()
    lowest = turnover.idxmin()
    assert ordered[highest] <= ordered[lowest]

    for _, group in capacity.sensitivity_cost.groupby(
        ["execution_days", "impact_c", "spread_bp"]
    ):
        values = group.set_index("factor")["capacity"]
        assert values["STREV"] <= values["MOM"] <= values["LOWVOL"]
