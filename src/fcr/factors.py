"""Factor construction (methodology section 2).

Three price-based factors with disjoint economic content. Weights are
dollar-neutral, equal-weight deciles with a per-name cap. Beta exposure is
removed in signal space rather than weight space so that the long and short legs
remain interpretable for the fragility measures. See DECISIONS.md ADR-0005.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .data import Panel
from .universe import Universe, market_returns


@dataclass
class FactorSet:
    dates: pd.DatetimeIndex
    weights: dict[str, pd.DataFrame]
    long_mask: dict[str, pd.DataFrame]
    signals: dict[str, pd.DataFrame]
    returns: pd.DataFrame  # dates x factors
    betas: pd.DataFrame  # daily betas
    diagnostics: pd.DataFrame
    portfolio_dates: pd.DatetimeIndex | None = None
    portfolio_weights: dict[str, pd.DataFrame] | None = None
    portfolio_masks: dict[str, pd.DataFrame] | None = None

    def weights_long(self) -> pd.DataFrame:
        """Long-form weights: date, factor, ticker, weight."""
        rows = []
        for factor, frame in self.weights.items():
            stacked = frame.stack()
            stacked = stacked[stacked != 0]
            for (date, ticker), weight in stacked.items():
                rows.append((date, factor, ticker, float(weight)))
        return pd.DataFrame(rows, columns=["date", "factor", "ticker", "weight"])


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
def compute_daily_betas(panel: Panel, cfg: Config) -> pd.DataFrame:
    ret = panel.returns
    mkt = market_returns(panel)
    window = cfg.beta_window
    min_periods = max(60, int(window * 0.7))
    cov = ret.rolling(window, min_periods=min_periods).cov(mkt)
    var = mkt.rolling(window, min_periods=min_periods).var()
    beta = cov.div(var, axis=0)
    return beta.replace([np.inf, -np.inf], np.nan)


def compute_signals(
    panel: Panel, dates: pd.DatetimeIndex, cfg: Config
) -> dict[str, pd.DataFrame]:
    close = panel.close
    ret = panel.returns

    momentum = close.shift(cfg.mom_skip) / close.shift(cfg.mom_lookback) - 1.0
    reversal = -(close / close.shift(cfg.rev_window) - 1.0)
    vol = ret.rolling(cfg.vol_window, min_periods=int(cfg.vol_window * 0.8)).std()
    lowvol = -vol

    raw = {"MOM": momentum, "STREV": reversal, "LOWVOL": lowvol}
    return {name: frame.reindex(dates) for name, frame in raw.items()}


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
def _residualize_on_beta(signal: pd.Series, beta: pd.Series) -> pd.Series:
    """Cross-sectional regression of signal on [1, beta]; return residual."""
    frame = pd.concat([signal.rename("s"), beta.rename("b")], axis=1).dropna()
    if len(frame) < 20 or frame["b"].std() == 0:
        return pd.Series(0.0, index=signal.index)
    x = np.column_stack([np.ones(len(frame)), frame["b"].to_numpy()])
    y = frame["s"].to_numpy()
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ coef
    return pd.Series(resid, index=frame.index).reindex(signal.index).fillna(0.0)


def _apply_cap(weights: pd.Series, cap: float) -> pd.Series:
    """Cap absolute weights and redistribute the excess pro rata (iterative)."""
    w = weights.copy()
    for _ in range(10):
        over = w.abs() > cap + 1e-12
        if not over.any():
            break
        excess = (w.abs()[over] - cap).sum()
        w[over] = np.sign(w[over]) * cap
        free = ~over & (w != 0)
        if not free.any() or w[free].abs().sum() == 0:
            break
        w[free] = (
            w[free] + np.sign(w[free]) * excess * w[free].abs() / w[free].abs().sum()
        )
    return w


def build_weights(
    signals: dict[str, pd.DataFrame],
    betas: pd.DataFrame,
    universe: Universe,
    cfg: Config,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame]:
    cap_abs = cfg.name_cap * cfg.gross
    all_tickers = next(iter(signals.values())).columns
    weights: dict[str, pd.DataFrame] = {}
    masks: dict[str, pd.DataFrame] = {}

    for factor in cfg.factors:
        signal = signals[factor]
        frame = pd.DataFrame(0.0, index=universe.dates, columns=all_tickers)
        mask = pd.DataFrame(False, index=universe.dates, columns=all_tickers)
        state_long: set[str] = set()
        state_short: set[str] = set()

        for date in universe.dates:
            names = universe.members[date]
            s = signal.loc[date, names].dropna()
            if len(s) < 50:
                continue
            b = betas.loc[date, names].reindex(s.index)
            s = _residualize_on_beta(s, b)

            lo, hi = s.quantile([0.01, 0.99])
            s = s.clip(lo, hi)
            if s.abs().sum() == 0:
                continue

            k = max(1, int(len(s) * cfg.decile), min(cfg.min_leg_names, len(s) // 2))
            pct = s.rank(pct=True)
            ranked = s.sort_values(ascending=False).index

            # Entry/exit bands (hysteresis). A name enters only in the top
            # (1 - entry_pct) and is retained until it falls out of the top
            # (1 - exit_pct). This cuts boundary churn, which otherwise makes a
            # 12-1 signal trade its whole book several times a year.
            keep_long = [
                n for n in state_long if n in pct.index and pct[n] >= cfg.exit_pct
            ]
            add_long = [
                n for n in ranked if pct[n] >= cfg.entry_pct and n not in keep_long
            ]
            longs = (keep_long + add_long)[:k]
            if len(longs) < k:
                longs += [n for n in ranked if n not in longs][: k - len(longs)]

            keep_short = [
                n
                for n in state_short
                if n in pct.index and pct[n] <= 1.0 - cfg.exit_pct
            ]
            add_short = [
                n
                for n in reversed(ranked)
                if pct[n] <= 1.0 - cfg.entry_pct and n not in keep_short
            ]
            shorts = (keep_short + add_short)[:k]
            if len(shorts) < k:
                shorts += [n for n in reversed(ranked) if n not in shorts][
                    : k - len(shorts)
                ]

            longs = [n for n in longs if n not in set(shorts)]
            shorts = [n for n in shorts if n not in set(longs)]
            state_long = set(longs)
            state_short = set(shorts)

            w = pd.Series(0.0, index=s.index)
            w[longs] = 1.0 / k
            w[shorts] = -1.0 / k
            w = _apply_cap(w, cap_abs)

            gross = w.abs().sum()
            if gross == 0:
                continue
            w = w * (cfg.gross / gross)

            frame.loc[date, w.index] = w.to_numpy()
            mask.loc[date, longs] = True

        weights[factor] = frame
        masks[factor] = mask

    diagnostics = _diagnostics(weights, betas, universe, cfg)
    return weights, masks, diagnostics


def _diagnostics(
    weights: dict[str, pd.DataFrame],
    betas: pd.DataFrame,
    universe: Universe,
    cfg: Config,
) -> pd.DataFrame:
    rows = []
    for factor, frame in weights.items():
        active = frame[frame.abs().sum(axis=1) > 0]
        beta_frame = betas.reindex(active.index)
        common = active.columns.intersection(beta_frame.columns)
        port_beta = (active[common] * beta_frame[common]).sum(axis=1)
        rows.append(
            {
                "factor": factor,
                "dates": len(active),
                "mean_abs_portfolio_beta": float(port_beta.abs().mean()),
                "max_abs_portfolio_beta": float(port_beta.abs().max()),
                "mean_names_long": float((active > 0).sum(axis=1).mean()),
                "mean_names_short": float((active < 0).sum(axis=1).mean()),
            }
        )
    return pd.DataFrame(rows).set_index("factor")


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------
def weekly_returns(panel: Panel, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Return over (t, t+1] for each rebalance date t, compounded from daily.

    The daily return on day d spans (d-1, d]. Label d with the previous day's
    rebalance label so that the return *on* a rebalance date is assigned to the
    week that ends there, not the week that starts there. Without this shift the
    forward return double-counts a day already inside the signal window.
    """
    daily = panel.returns
    labels = pd.Series(dates, index=dates).reindex(daily.index, method="ffill").shift(1)
    mask = labels.notna()
    grouped = (1.0 + daily.loc[mask].fillna(0.0)).groupby(labels[mask]).prod() - 1.0
    grouped.index = pd.DatetimeIndex(grouped.index)
    return grouped.sort_index()


def compute_factor_returns(
    weights: dict[str, pd.DataFrame],
    weekly: pd.DataFrame,
    dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Constant-weight factor returns (kept for diagnostics and tests)."""
    out = {}
    for factor, frame in weights.items():
        aligned = weekly.reindex(index=frame.index, columns=frame.columns).fillna(0.0)
        series = (frame * aligned).sum(axis=1)
        active = frame.abs().sum(axis=1) > 0
        series = series.where(active)
        out[factor] = series
    result = pd.DataFrame(out)
    return result.reindex(dates)


def compute_factor_returns_buy_and_hold(
    portfolio_weights: dict[str, pd.DataFrame],
    portfolio_dates: pd.DatetimeIndex,
    weekly: pd.DataFrame,
    dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Monthly buy-and-hold factor returns.

    Holdings are set at the monthly rebalance and then drift with each stock's
    return until the next rebalance. The previous implementation held the target
    weights constant every week, which is a weekly-rebalanced portfolio and is
    inconsistent with the monthly turnover used by the capacity model.
    """
    pdates = list(portfolio_dates)
    out: dict[str, pd.Series] = {}
    for factor, weights in portfolio_weights.items():
        series = pd.Series(np.nan, index=dates, dtype=float)
        for i, start in enumerate(pdates):
            end = (
                pdates[i + 1]
                if i + 1 < len(pdates)
                else dates[-1] + pd.Timedelta(days=1)
            )
            w = weights.loc[start].astype(float).copy()
            holding = weekly.loc[(weekly.index >= start) & (weekly.index < end)]
            for date, row in holding.iterrows():
                r = row.reindex(w.index).fillna(0.0)
                port = float((w * r).sum())
                series.loc[date] = port
                if abs(1.0 + port) > 1e-12:
                    w = w * (1.0 + r) / (1.0 + port)
        out[factor] = series
    return pd.DataFrame(out).reindex(dates)


def portfolio_drift_trades(
    portfolio_weights: pd.DataFrame,
    portfolio_dates: pd.DatetimeIndex,
    weekly: pd.DataFrame,
    factor_returns: pd.Series,
    dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Trades at each monthly rebalance after full-period weight drift.

    The drift term compounds stock and factor returns from the previous
    rebalance to the current one. The capacity model needs this quantity; using
    one week of drift understates turnover.
    """
    trades = pd.DataFrame(
        0.0, index=dates, columns=portfolio_weights.columns, dtype=float
    )
    pdates = list(portfolio_dates)
    for i, date in enumerate(pdates):
        if i == 0:
            continue
        previous = pdates[i - 1]
        w_prev = portfolio_weights.loc[previous].astype(float)
        w_new = portfolio_weights.loc[date].astype(float)
        holding = weekly.loc[(weekly.index >= previous) & (weekly.index < date)]
        stock_return = (1.0 + holding).prod() - 1.0
        rf = float(
            (
                1.0
                + factor_returns.loc[
                    (factor_returns.index >= previous) & (factor_returns.index < date)
                ]
            ).prod()
            - 1.0
        )
        drift = (
            w_prev * (1.0 + stock_return.reindex(w_prev.index).fillna(0.0)) / (1.0 + rf)
        )
        trades.loc[date] = (w_new - drift).reindex(trades.columns).fillna(0.0)
    return trades


# ---------------------------------------------------------------------------
# Invariants (methodology section 2.4)
# ---------------------------------------------------------------------------
def check_invariants(factors: FactorSet, cfg: Config, tol: float = 1e-8) -> dict:
    report = {}
    for factor, frame in factors.weights.items():
        active = frame[frame.abs().sum(axis=1) > 0]
        dollar = active.sum(axis=1).abs().max()
        gross = (active.abs().sum(axis=1) - cfg.gross).abs().max()
        cap = active.abs().max().max()
        report[factor] = {
            "max_abs_dollar_imbalance": float(dollar),
            "max_gross_error": float(gross),
            "max_abs_weight": float(cap),
            "cap": cfg.name_cap * cfg.gross,
            "dates": int(len(active)),
        }
        if dollar > 1e-6:
            raise AssertionError(f"{factor}: not dollar-neutral ({dollar})")
        if gross > 1e-6:
            raise AssertionError(f"{factor}: gross exposure off ({gross})")
        if cap > cfg.name_cap * cfg.gross + 1e-9:
            raise AssertionError(f"{factor}: name cap breached ({cap})")

    corr = factors.returns.corr()
    pairs = []
    for i, a in enumerate(corr.columns):
        for b in corr.columns[i + 1 :]:
            pairs.append((a, b, float(corr.loc[a, b])))
            if abs(corr.loc[a, b]) > 0.9:
                raise AssertionError(
                    f"Factors {a} and {b} are collinear: {corr.loc[a, b]:.4f}"
                )
    report["pairwise_correlation"] = pairs
    return report


def build_factors(panel: Panel, universe: Universe, cfg: Config) -> FactorSet:
    dates = universe.dates
    portfolio = _monthly_view(universe)
    betas = compute_daily_betas(panel, cfg)
    signals = compute_signals(panel, dates, cfg)

    portfolio_weights, portfolio_masks, diagnostics = build_weights(
        signals, betas, portfolio, cfg
    )

    # Holdings change at the monthly rebalance and are held between rebalances.
    # Observation and the exposure overlay remain weekly.
    weights = {
        factor: frame.reindex(dates, method="ffill").fillna(0.0)
        for factor, frame in portfolio_weights.items()
    }
    masks = {
        factor: frame.reindex(dates, method="ffill").fillna(False).astype(bool)
        for factor, frame in portfolio_masks.items()
    }

    weekly = weekly_returns(panel, dates)
    returns = compute_factor_returns_buy_and_hold(
        portfolio_weights, portfolio.dates, weekly, dates
    )

    result = FactorSet(
        dates=dates,
        weights=weights,
        long_mask=masks,
        signals=signals,
        returns=returns,
        betas=betas,
        diagnostics=diagnostics,
        portfolio_dates=portfolio.dates,
        portfolio_weights=portfolio_weights,
        portfolio_masks=portfolio_masks,
    )
    check_invariants(result, cfg)
    return result


def _monthly_view(universe: Universe) -> Universe:
    """Monthly subset of the rebalance calendar, using the same membership sets."""
    series = pd.Series(universe.dates, index=universe.dates)
    monthly = pd.DatetimeIndex(
        series.groupby(pd.Grouper(freq="ME")).max().dropna().values
    )
    monthly = monthly[monthly.isin(universe.dates)]
    return Universe(
        dates=monthly,
        members={date: universe.members[date] for date in monthly},
        adv=universe.adv,
        history=universe.history,
        last_valid=universe.last_valid,
    )
