"""Statistical study (methodology section 6).

Primary estimand: the tau=0.10 quantile regression coefficient of forward
four-week factor returns on the fragility composite, pooled across factors with
factor fixed effects, controlling for volatility, trend, and liquidity regime.
Inference by stationary bootstrap over dates, retaining duplicate dates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from .factors import FactorSet
from .fragility import Fragility
from .overlay import expanding_percentile
from .stats import (
    benjamini_hochberg,
    bootstrap_pvalue,
    bootstrap_row_positions,
    minimum_detectable_effect,
    percentile_interval,
    quantile_regression,
)
from .targets import expected_shortfall, forward_returns
from .universe import Universe, market_returns

MEASURES = ("z_o_sync", "z_o_breadth", "z_o_exit", "z_o_persist")
CONTROLS = ("log_vol", "mkt_vol", "trail_12w", "liq_regime")
PERIODS = (
    ("2005-2009", 2005, 2009),
    ("2010-2017", 2010, 2017),
    ("2018-2025", 2018, 2025),
)


@dataclass
class StudyResult:
    dataset: pd.DataFrame
    primary: pd.DataFrame
    per_factor: pd.DataFrame
    secondary: pd.DataFrame
    es_table: pd.DataFrame
    es_difference: pd.DataFrame
    quintile_sort: pd.DataFrame
    subsample: pd.DataFrame
    composite_sensitivity: pd.DataFrame
    h2: pd.DataFrame
    placebo: pd.DataFrame
    placebo_summary: pd.DataFrame
    mde: dict
    diagnostics: dict
    dropped: dict


def _weekly_series(daily: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    labels = pd.Series(dates, index=dates).reindex(daily.index, method="ffill").shift(1)
    mask = labels.notna()
    grouped = (1.0 + daily.loc[mask].fillna(0.0)).groupby(labels[mask]).prod() - 1.0
    grouped.index = pd.DatetimeIndex(grouped.index)
    return grouped.sort_index()


def _controls(
    factors: FactorSet, universe: Universe, panel, cfg: Config
) -> pd.DataFrame:
    """Control variables known at each rebalance close.

    ``factors.returns[t]`` is the return over ``(t, t+1]``, so every control that
    uses returns is lagged one week. The target in ``targets.forward_returns``
    starts at ``t``. Both sides of the regression now use information available
    at the decision date.
    """
    market_weekly = (
        _weekly_series(market_returns(panel), factors.dates)
        .reindex(factors.dates)
        .shift(1)
    )
    market_vol = np.log(
        (market_weekly.ewm(span=4, min_periods=3).std() * np.sqrt(52)).replace(
            0.0, np.nan
        )
    )

    adv_daily = (
        panel.dollar_volume.sum(axis=1).rolling(cfg.adv_window, min_periods=10).median()
    )
    adv_at = adv_daily.reindex(factors.dates, method="ffill")
    liq_regime = np.log((adv_at / adv_at.shift(12)).replace(0.0, np.nan))

    out = {}
    for factor in cfg.factors:
        rf = factors.returns[factor].reindex(factors.dates).shift(1)
        vol = np.log(
            (rf.ewm(span=4, min_periods=3).std() * np.sqrt(52)).replace(0.0, np.nan)
        )
        trend = (1.0 + rf).rolling(12, min_periods=8).apply(np.prod, raw=True) - 1.0
        out[factor] = pd.DataFrame(
            {
                "log_vol": vol,
                "mkt_vol": market_vol,
                "trail_12w": trend,
                "liq_regime": liq_regime,
            }
        )
    return out


def build_dataset(
    factors: FactorSet,
    fragility: Fragility,
    universe: Universe,
    panel,
    cfg: Config,
) -> tuple[pd.DataFrame, dict]:
    fwd = forward_returns(factors.returns, cfg)
    controls = _controls(factors, universe, panel, cfg)
    frames = []
    dropped = {}

    for factor in cfg.factors:
        block = pd.DataFrame(
            {
                "fwd_4w": fwd["fwd_4w"][factor],
                "fwd_13w": fwd["fwd_13w"][factor],
                "composite": fragility.composite[factor],
            }
        )
        long = fragility.long.xs(factor, level="factor")
        for measure in MEASURES:
            block[measure] = long[measure]
        block = block.join(controls[factor])
        block["factor"] = factor
        before = len(block)
        required = ["fwd_4w", "composite", "fwd_13w"] + list(MEASURES) + list(CONTROLS)
        block = block.dropna(subset=required)
        dropped[factor] = {"before": before, "after": len(block)}
        frames.append(block)

    dataset = pd.concat(frames).sort_index()
    dataset.index.name = "date"
    return dataset.reset_index(), dropped


def _design(
    dataset: pd.DataFrame, term: str, with_controls: bool = True, factor_fe: bool = True
) -> tuple[np.ndarray, list[str]]:
    columns = [np.ones(len(dataset)), dataset[term].to_numpy(dtype=float)]
    names = ["const", term]
    if with_controls:
        for control in CONTROLS:
            columns.append(dataset[control].to_numpy(dtype=float))
            names.append(control)
    if factor_fe and dataset["factor"].nunique() > 1:
        for factor in ("STREV", "LOWVOL"):
            if (dataset["factor"] == factor).any():
                columns.append((dataset["factor"] == factor).to_numpy(dtype=float))
                names.append(f"factor_{factor}")
    return np.column_stack(columns), names


def _fit(
    frame: pd.DataFrame,
    term: str,
    q: float,
    with_controls: bool = True,
    factor_fe: bool = True,
    target: str = "fwd_4w",
) -> dict[str, float]:
    x, names = _design(frame, term, with_controls, factor_fe)
    fit = quantile_regression(frame[target].to_numpy(dtype=float), x, names, q)
    return fit.params


def _frames(dataset: pd.DataFrame, cfg: Config, seed: int, reps: int | None = None):
    reps = cfg.bootstrap_reps if reps is None else reps
    positions = bootstrap_row_positions(
        dataset["date"].to_numpy(), reps, cfg.block_mean, seed
    )
    for rows in positions:
        if len(rows) < 100:
            continue
        yield dataset.iloc[rows]


def primary_regression(dataset: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, dict]:
    """Point estimates and block-bootstrap intervals for the primary model."""
    terms = ["composite", "log_vol", "mkt_vol", "trail_12w", "liq_regime"]
    quantiles = (cfg.primary_quantile, 0.50)

    point = {q: _fit(dataset, "composite", q) for q in quantiles}
    draws = {q: [] for q in quantiles}
    differences = []

    for frame in _frames(dataset, cfg, cfg.seed):
        try:
            low = _fit(frame, "composite", quantiles[0])
            median = _fit(frame, "composite", quantiles[1])
        except Exception:
            continue
        draws[quantiles[0]].append(low)
        draws[quantiles[1]].append(median)
        differences.append(low["composite"] - median["composite"])

    rows = []
    for q in quantiles:
        frame = pd.DataFrame(draws[q])
        for term in terms:
            samples = frame[term].dropna().to_numpy() if term in frame else np.array([])
            lo, hi = percentile_interval(samples, cfg.alpha)
            rows.append(
                {
                    "quantile": q,
                    "term": term,
                    "estimate": point[q][term],
                    "se": float(np.nanstd(samples, ddof=1))
                    if samples.size > 5
                    else np.nan,
                    "ci_low": lo,
                    "ci_high": hi,
                    "negative_share": float(np.mean(samples < 0))
                    if samples.size
                    else np.nan,
                }
            )

    low_samples = pd.DataFrame(draws[quantiles[0]])["composite"].dropna().to_numpy()
    se_primary = (
        float(np.nanstd(low_samples, ddof=1)) if low_samples.size > 5 else np.nan
    )
    diff = np.asarray(differences)
    mde = {
        "se_primary": se_primary,
        "mde_absolute": minimum_detectable_effect(se_primary, cfg.alpha, cfg.power),
        "reps_used": int(len(low_samples)),
        "tail_difference": float(
            point[quantiles[0]]["composite"] - point[quantiles[1]]["composite"]
        ),
        "tail_difference_ci": percentile_interval(diff, cfg.alpha),
    }
    return pd.DataFrame(rows), mde


def per_factor_regression(dataset: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    rows = []
    for factor, frame in dataset.groupby("factor"):
        frame = frame.sort_values("date").reset_index(drop=True)
        if len(frame) < 200:
            continue
        point = _fit(frame, "composite", cfg.primary_quantile, factor_fe=False)
        samples = []
        for sub in _frames(frame, cfg, cfg.seed + 1, reps=400):
            try:
                samples.append(
                    _fit(
                        sub,
                        "composite",
                        cfg.primary_quantile,
                        factor_fe=False,
                    )["composite"]
                )
            except Exception:
                continue
        samples = np.asarray(samples)
        lo, hi = percentile_interval(samples, cfg.alpha)
        rows.append(
            {
                "factor": factor,
                "estimate": point["composite"],
                "se": float(np.nanstd(samples, ddof=1)),
                "ci_low": lo,
                "ci_high": hi,
                "pvalue": bootstrap_pvalue(samples, estimate=point["composite"]),
                "n": len(frame),
            }
        )
    return pd.DataFrame(rows)


def secondary_regression(dataset: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Four measures x two horizons, FDR-adjusted. Exploratory by construction."""
    rows = []
    horizons = {"fwd_4w": "4w", "fwd_13w": "13w"}
    for horizon, label in horizons.items():
        for measure in MEASURES:
            frame = dataset.dropna(subset=[measure, horizon]).reset_index(drop=True)
            if len(frame) < 300:
                continue
            point = _fit(frame, measure, cfg.primary_quantile, target=horizon)[measure]
            samples = []
            for sub in _frames(frame, cfg, cfg.seed + 2, reps=400):
                try:
                    samples.append(
                        _fit(
                            sub,
                            measure,
                            cfg.primary_quantile,
                            target=horizon,
                        )[measure]
                    )
                except Exception:
                    continue
            samples = np.asarray(samples)
            lo, hi = percentile_interval(samples, cfg.alpha)
            rows.append(
                {
                    "horizon": label,
                    "measure": measure.replace("z_o_", ""),
                    "estimate": point,
                    "se": float(np.nanstd(samples, ddof=1)),
                    "ci_low": lo,
                    "ci_high": hi,
                    "pvalue": bootstrap_pvalue(samples, estimate=point),
                    "n": len(frame),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        fdr = benjamini_hochberg(result["pvalue"], cfg.fdr_alpha)
        result["pvalue_adj"] = fdr["adjusted"].to_numpy()
        result["reject"] = fdr["reject"].to_numpy()
    return result


def _quintile_frame(dataset: pd.DataFrame, fragility: Fragility, cfg: Config):
    frames = []
    for factor in cfg.factors:
        frame = dataset[dataset["factor"] == factor].copy()
        pct = expanding_percentile(fragility.composite[factor], cfg.burn_in)
        frame["pct"] = frame["date"].map(pct)
        frame = frame.dropna(subset=["pct", "fwd_4w"])
        frame["quintile"] = pd.cut(
            frame["pct"], bins=np.linspace(0, 1, 6), labels=False, include_lowest=True
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def expected_shortfall_table(
    dataset: pd.DataFrame, fragility: Fragility, cfg: Config
) -> pd.DataFrame:
    frame = _quintile_frame(dataset, fragility, cfg)
    rows = []
    for (factor, quintile), group in frame.groupby(["factor", "quintile"]):
        if len(group) < 20:
            continue
        rows.append(
            {
                "factor": factor,
                "quintile": int(quintile) + 1,
                "mean_fwd_4w": float(group["fwd_4w"].mean()),
                "es_5": expected_shortfall(group["fwd_4w"], 0.05),
                "share_negative": float((group["fwd_4w"] < 0).mean()),
                "n": len(group),
            }
        )
    return pd.DataFrame(rows)


def expected_shortfall_difference(
    dataset: pd.DataFrame, fragility: Fragility, cfg: Config, reps: int = 600
) -> pd.DataFrame:
    """E2: ES5(high fragility) - ES5(low fragility), per factor and pooled."""
    frame = _quintile_frame(dataset, fragility, cfg)
    rows = []
    for factor, group in frame.groupby("factor"):
        high = group.loc[group["quintile"] == 4, "fwd_4w"]
        low = group.loc[group["quintile"] == 0, "fwd_4w"]
        if len(high) < 20 or len(low) < 20:
            continue
        point = expected_shortfall(high, 0.05) - expected_shortfall(low, 0.05)
        diffs = []
        for sub in _frames(group.reset_index(drop=True), cfg, cfg.seed + 31, reps):
            h = sub.loc[sub["quintile"] == 4, "fwd_4w"]
            l = sub.loc[sub["quintile"] == 0, "fwd_4w"]
            if len(h) > 10 and len(l) > 10:
                diffs.append(expected_shortfall(h, 0.05) - expected_shortfall(l, 0.05))
        lo, hi = percentile_interval(np.asarray(diffs), cfg.alpha)
        rows.append(
            {
                "factor": factor,
                "es_high": expected_shortfall(high, 0.05),
                "es_low": expected_shortfall(low, 0.05),
                "difference": point,
                "ci_low": lo,
                "ci_high": hi,
                "n_high": len(high),
                "n_low": len(low),
            }
        )

    high = frame.loc[frame["quintile"] == 4, "fwd_4w"]
    low = frame.loc[frame["quintile"] == 0, "fwd_4w"]
    point = expected_shortfall(high, 0.05) - expected_shortfall(low, 0.05)
    diffs = []
    for sub in _frames(frame, cfg, cfg.seed + 32, reps):
        h = sub.loc[sub["quintile"] == 4, "fwd_4w"]
        l = sub.loc[sub["quintile"] == 0, "fwd_4w"]
        if len(h) > 10 and len(l) > 10:
            diffs.append(expected_shortfall(h, 0.05) - expected_shortfall(l, 0.05))
    lo, hi = percentile_interval(np.asarray(diffs), cfg.alpha)
    rows.append(
        {
            "factor": "POOLED",
            "es_high": expected_shortfall(high, 0.05),
            "es_low": expected_shortfall(low, 0.05),
            "difference": point,
            "ci_low": lo,
            "ci_high": hi,
            "n_high": len(high),
            "n_low": len(low),
        }
    )
    return pd.DataFrame(rows)


def quintile_sort(
    dataset: pd.DataFrame, fragility: Fragility, cfg: Config, reps: int = 400
) -> pd.DataFrame:
    """Assumption-light check: mean forward return, fragile minus calm quintile."""
    frame = _quintile_frame(dataset, fragility, cfg)
    rows = []
    for factor, group in frame.groupby("factor"):
        high = group.loc[group["quintile"] == 4, "fwd_4w"]
        low = group.loc[group["quintile"] == 0, "fwd_4w"]
        if len(high) < 20 or len(low) < 20:
            continue
        point = high.mean() - low.mean()
        diffs = []
        for sub in _frames(group.reset_index(drop=True), cfg, cfg.seed + 41, reps):
            h = sub.loc[sub["quintile"] == 4, "fwd_4w"]
            l = sub.loc[sub["quintile"] == 0, "fwd_4w"]
            if len(h) > 10 and len(l) > 10:
                diffs.append(h.mean() - l.mean())
        lo, hi = percentile_interval(np.asarray(diffs), cfg.alpha)
        rows.append(
            {
                "factor": factor,
                "q5_minus_q1": point,
                "ci_low": lo,
                "ci_high": hi,
                "n_q5": len(high),
                "n_q1": len(low),
            }
        )
    return pd.DataFrame(rows)


def subsample_regression(
    dataset: pd.DataFrame, cfg: Config, reps: int = 200
) -> pd.DataFrame:
    rows = []
    for label, start, end in PERIODS:
        frame = dataset[
            (dataset["date"].dt.year >= start) & (dataset["date"].dt.year <= end)
        ].reset_index(drop=True)
        if len(frame) < 200:
            continue
        point = _fit(frame, "composite", cfg.primary_quantile)["composite"]
        samples = []
        for sub in _frames(frame, cfg, cfg.seed + 51, reps):
            try:
                samples.append(
                    _fit(sub, "composite", cfg.primary_quantile)["composite"]
                )
            except Exception:
                continue
        samples = np.asarray(samples)
        lo, hi = percentile_interval(samples, cfg.alpha)
        rows.append(
            {
                "period": label,
                "estimate": point,
                "ci_low": lo,
                "ci_high": hi,
                "n": len(frame),
            }
        )
    return pd.DataFrame(rows)


def composite_sensitivity(
    dataset: pd.DataFrame, cfg: Config, reps: int = 200
) -> pd.DataFrame:
    """Alternative composites: equal, drop-one, rank-average."""
    variants: dict[str, pd.Series] = {"equal": dataset["composite"]}
    for measure in MEASURES:
        label = "drop_" + measure.replace("z_o_", "")
        variants[label] = dataset[[m for m in MEASURES if m != measure]].mean(axis=1)

    rank = pd.Series(np.nan, index=dataset.index, dtype=float)
    for factor, group in dataset.groupby("factor"):
        parts = []
        for measure in MEASURES:
            parts.append(
                expanding_percentile(
                    group[measure].reset_index(drop=True), 52
                ).to_numpy()
            )
        stacked = np.column_stack(parts)
        valid = ~np.isnan(stacked).all(axis=1)
        values = np.full(len(stacked), np.nan)
        values[valid] = np.nanmean(stacked[valid], axis=1)
        rank.loc[group.index] = values
    variants["rank_average"] = rank

    rows = []
    for label, values in variants.items():
        frame = dataset.copy()
        frame["variant"] = np.asarray(values, dtype=float)
        frame = frame.dropna(subset=["variant"]).reset_index(drop=True)
        if len(frame) < 300:
            continue
        point = _fit(frame, "variant", cfg.primary_quantile)["variant"]
        samples = []
        for sub in _frames(frame, cfg, cfg.seed + 61, reps):
            try:
                samples.append(_fit(sub, "variant", cfg.primary_quantile)["variant"])
            except Exception:
                continue
        samples = np.asarray(samples)
        lo, hi = percentile_interval(samples, cfg.alpha)
        rows.append(
            {
                "variant": label,
                "estimate": point,
                "se": float(np.nanstd(samples, ddof=1)),
                "ci_low": lo,
                "ci_high": hi,
                "n": len(frame),
            }
        )
    return pd.DataFrame(rows)


def h2_attenuation(dataset: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """H2: does the coefficient retain at least half its magnitude under controls?"""
    base = _fit(dataset, "composite", cfg.primary_quantile, with_controls=False)[
        "composite"
    ]
    full = _fit(dataset, "composite", cfg.primary_quantile)["composite"]
    # Single-control model: log_vol only, with factor fixed effects.
    x = np.column_stack(
        [
            np.ones(len(dataset)),
            dataset["composite"].to_numpy(dtype=float),
            dataset["log_vol"].to_numpy(dtype=float),
        ]
    )
    for factor in ("STREV", "LOWVOL"):
        if (dataset["factor"] == factor).any():
            x = np.column_stack(
                [x, (dataset["factor"] == factor).to_numpy(dtype=float)]
            )
    names = ["const", "composite", "log_vol"] + [
        f"factor_{f}" for f in ("STREV", "LOWVOL") if (dataset["factor"] == f).any()
    ]
    logvol_beta = quantile_regression(
        dataset["fwd_4w"].to_numpy(dtype=float), x, names, cfg.primary_quantile
    ).params["composite"]
    rows = [
        {
            "specification": "uncontrolled",
            "estimate": base,
            "retention": np.nan,
        },
        {
            "specification": "full_controls",
            "estimate": full,
            "retention": full / base if base else np.nan,
        },
        {
            "specification": "log_vol_only",
            "estimate": logvol_beta,
            "retention": logvol_beta / base if base else np.nan,
        },
    ]
    return pd.DataFrame(rows)


def placebo_test(dataset: pd.DataFrame, cfg: Config, n_reps: int = 200) -> pd.DataFrame:
    """Block-shuffle the composite within factor and refit the primary model.

    Destroys the date alignment between fragility and returns while preserving
    the marginal distribution and the factor's autocorrelation structure.
    """
    rng = np.random.default_rng(cfg.seed + 11)
    rows = []
    for factor, frame in dataset.groupby("factor"):
        base = frame.sort_values("date").reset_index(drop=True)
        values = base["composite"].to_numpy(dtype=float)
        n = len(values)
        for _ in range(n_reps):
            block = 8
            order = []
            while len(order) < n:
                start = rng.integers(0, n)
                order.extend([(start + j) % n for j in range(block)])
            shuffled = values[np.asarray(order[:n])]
            trial = base.copy()
            trial["composite"] = shuffled
            try:
                rows.append(
                    {
                        "factor": factor,
                        "estimate": _fit(
                            trial, "composite", cfg.primary_quantile, factor_fe=False
                        )["composite"],
                    }
                )
            except Exception:
                continue
    return pd.DataFrame(rows)


def run_study(
    factors: FactorSet,
    fragility: Fragility,
    universe: Universe,
    panel,
    cfg: Config,
) -> StudyResult:
    dataset, dropped = build_dataset(factors, fragility, universe, panel, cfg)
    primary, mde = primary_regression(dataset, cfg)
    per_factor = per_factor_regression(dataset, cfg)
    secondary = secondary_regression(dataset, cfg)
    es_table = expected_shortfall_table(dataset, fragility, cfg)
    es_difference = expected_shortfall_difference(dataset, fragility, cfg)
    quintile = quintile_sort(dataset, fragility, cfg)
    subsample = subsample_regression(dataset, cfg)
    composite = composite_sensitivity(dataset, cfg)
    h2 = h2_attenuation(dataset, cfg)
    placebo = placebo_test(dataset, cfg)

    placebo_rows = []
    for factor, group in placebo.groupby("factor"):
        real = per_factor.loc[per_factor["factor"] == factor, "estimate"]
        if real.empty:
            continue
        value = float(real.iloc[0])
        pvalue = float(np.mean(np.abs(group["estimate"]) >= abs(value)))
        placebo_rows.append(
            {
                "factor": factor,
                "placebo_mean": float(group["estimate"].mean()),
                "placebo_sd": float(group["estimate"].std()),
                "real_estimate": value,
                "pvalue": pvalue,
                "n": len(group),
            }
        )
    placebo_summary = pd.DataFrame(placebo_rows)

    low = primary[
        (primary["term"] == "composite") & (primary["quantile"] == cfg.primary_quantile)
    ]
    se = float(low["se"].iloc[0]) if len(low) else np.nan
    threshold = minimum_detectable_effect(se, cfg.alpha, cfg.power)
    mde["mde_absolute"] = threshold
    mde["mde_in_sd_units"] = (
        threshold / float(dataset["fwd_4w"].std())
        if dataset["fwd_4w"].std()
        else np.nan
    )

    diagnostics = {
        "n_rows": int(len(dataset)),
        "n_dates": int(dataset["date"].nunique()),
        "n_blocks_4w": int(np.ceil(dataset["date"].nunique() / 4)),
        "n_factors": int(dataset["factor"].nunique()),
        "date_start": str(dataset["date"].min().date()),
        "date_end": str(dataset["date"].max().date()),
        "fwd_4w_sd": float(dataset["fwd_4w"].std()),
        "composite_sd": float(dataset["composite"].std()),
        "corr_composite_vol": float(dataset["composite"].corr(dataset["log_vol"])),
        "dropped": dropped,
    }
    return StudyResult(
        dataset=dataset,
        primary=primary,
        per_factor=per_factor,
        secondary=secondary,
        es_table=es_table,
        es_difference=es_difference,
        quintile_sort=quintile,
        subsample=subsample,
        composite_sensitivity=composite,
        h2=h2,
        placebo=placebo,
        placebo_summary=placebo_summary,
        mde=mde,
        diagnostics=diagnostics,
        dropped=dropped,
    )
