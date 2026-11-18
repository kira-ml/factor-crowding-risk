"""Decision layer: overlay versus matched comparators (methodology section 7)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import compare_strategies, metrics, run_strategy
from .cash import load_cash_rate
from .config import Config
from .factors import FactorSet
from .fragility import Fragility
from .overlay import build_comparators, build_overlay, random_overlays
from .stats import max_drawdown, percentile_interval, stationary_bootstrap_indices
from .targets import expected_shortfall


@dataclass
class DecisionResult:
    summary: pd.DataFrame
    by_factor: pd.DataFrame
    random_distribution: pd.DataFrame
    exposure: pd.DataFrame
    tests: pd.DataFrame
    frames: dict[str, dict[str, pd.DataFrame]] = field(default_factory=dict)


def _bootstrap_difference(
    a: pd.Series,
    b: pd.Series,
    statistic,
    reps: int,
    block_mean: int,
    seed: int,
) -> tuple[float, float, float]:
    a = a.dropna()
    b = b.dropna()
    index = a.index.intersection(b.index)
    a, b = a.reindex(index), b.reindex(index)
    if len(index) < 60:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    samples = np.empty(reps)
    samples[:] = np.nan
    for i in range(reps):
        idx = stationary_bootstrap_indices(len(index), block_mean, rng)
        samples[i] = statistic(a.iloc[idx]) - statistic(b.iloc[idx])
    lo, hi = percentile_interval(samples, 0.05)
    return float(np.nanmean(samples)), lo, hi


def run_decision_layer(
    factors: FactorSet,
    fragility: Fragility,
    cfg: Config,
) -> DecisionResult:
    cash = load_cash_rate(cfg, factors.dates)

    summary_rows = []
    random_rows = []
    exposure_rows = []
    test_rows = []
    frames: dict[str, dict[str, pd.DataFrame]] = {}

    for factor in cfg.factors:
        composite = fragility.composite[factor]
        overlay_frame = build_overlay(composite, cfg)
        overlay = overlay_frame["weight"]
        factor_returns = factors.returns[factor].reindex(overlay.index)

        comparators = build_comparators(overlay, factor_returns, cfg)
        results = {
            name: run_strategy(factor_returns, weight, cash, cfg)
            for name, weight in comparators.items()
        }
        frames[factor] = results

        table = compare_strategies(results, cfg)
        table["factor"] = factor
        summary_rows.append(table)

        exposure_rows.append(
            pd.DataFrame(
                {
                    "factor": factor,
                    "strategy": list(results),
                    "mean_exposure": [
                        float(f["weight"].mean()) for f in results.values()
                    ],
                    "turnover": [
                        float(f["weight"].diff().abs().sum()) for f in results.values()
                    ],
                }
            )
        )

        # Hypothesis test: fragility versus volatility management.
        for label, statistic in (
            ("es_5", lambda x: expected_shortfall(pd.Series(x), 0.05)),
            ("max_drawdown", max_drawdown),
        ):
            mean, lo, hi = _bootstrap_difference(
                results["fragility"]["net"],
                results["vol_managed"]["net"],
                statistic,
                cfg.bootstrap_reps,
                cfg.block_mean,
                cfg.seed + 3,
            )
            test_rows.append(
                {
                    "factor": factor,
                    "metric": label,
                    "difference": mean,
                    "ci_low": lo,
                    "ci_high": hi,
                    "improves": bool(lo > 0),
                }
            )

        randoms = random_overlays(overlay, cfg)
        random_es = []
        random_sharpe = []
        for column in randoms.columns:
            frame = run_strategy(factor_returns, randoms[column], cash, cfg)
            row = metrics(frame)
            random_es.append(row.get("es_5", np.nan))
            random_sharpe.append(row.get("sharpe", np.nan))
        random_es = np.asarray(random_es, dtype=float)
        random_sharpe = np.asarray(random_sharpe, dtype=float)
        actual_es = metrics(results["fragility"]).get("es_5", np.nan)
        random_rows.append(
            {
                "factor": factor,
                "actual_es_5": actual_es,
                "es_5_p05": float(np.nanquantile(random_es, 0.05)),
                "es_5_p50": float(np.nanquantile(random_es, 0.50)),
                "es_5_p95": float(np.nanquantile(random_es, 0.95)),
                "percentile_rank": float(np.nanmean(random_es <= actual_es)),
                "sharpe_p50": float(np.nanquantile(random_sharpe, 0.50)),
                "n": int(len(random_es)),
            }
        )

    summary = pd.concat(summary_rows, ignore_index=True)
    columns = [
        "factor",
        "strategy",
        "es_5",
        "es_10",
        "q5",
        "max_drawdown",
        "sharpe",
        "sortino",
        "annual_vol",
        "avg_exposure",
        "turnover_annual",
        "cost_drag_annual",
        "borrow_drag_annual",
    ]
    return DecisionResult(
        summary=summary,
        by_factor=summary[columns],
        random_distribution=pd.DataFrame(random_rows),
        exposure=pd.concat(exposure_rows, ignore_index=True),
        tests=pd.DataFrame(test_rows),
        frames=frames,
    )


def overlay_summary(decision: DecisionResult, factor: str) -> pd.DataFrame:
    frame = decision.summary[decision.summary["factor"] == factor].copy()
    order = ["static", "exposure_matched", "vol_managed", "fragility"]
    frame["order"] = frame["strategy"].map({name: i for i, name in enumerate(order)})
    frame = frame.sort_values("order").drop(columns="order")
    columns = [
        "strategy",
        "es_5",
        "es_10",
        "q5",
        "max_drawdown",
        "sharpe",
        "sortino",
        "annual_vol",
        "avg_exposure",
        "turnover_annual",
        "cost_drag_annual",
        "borrow_drag_annual",
    ]
    return frame[columns].reset_index(drop=True)
