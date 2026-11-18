"""Reproduction of the V1 defects (audit sections B1 and B2).

This is a gate: if the identities below do not hold, the audit is wrong and no
V2 result may be published until it is revised.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .data import Panel


def v1_factor_identity(panel: Panel, cfg: Config) -> dict:
    """Rebuild V1's two factors and measure how far they are from opposite.

    V1 defined momentum as the top-minus-bottom quintile of the 12-1 return and
    value as the top-minus-bottom quintile of its negative. With identical
    quintile sizes the weight vectors are exact negatives, so the return series
    must be exact negatives.
    """
    monthly = panel.close.resample("ME").last()
    rows = []
    max_weight_gap = 0.0
    max_return_gap = 0.0

    for i in range(12, len(monthly) - 1):
        date = monthly.index[i]
        available = monthly.iloc[i].dropna().index
        if len(available) < 50:
            continue
        start = monthly.iloc[i - 12][available]
        end = monthly.iloc[i - 1][available]
        valid = start.notna() & end.notna()
        start, end = start[valid], end[valid]
        if len(start) < 50:
            continue

        score = end / start - 1.0
        k = max(1, int(len(score) * 0.20))
        top = score.nlargest(k).index
        bottom = score.nsmallest(k).index

        w_mom = pd.Series(0.0, index=score.index)
        w_mom[top] = 1.0 / k
        w_mom[bottom] = -1.0 / k

        # V1: value_score = -momentum_score, then top/bottom of that.
        w_val = pd.Series(0.0, index=score.index)
        w_val[bottom] = 1.0 / k
        w_val[top] = -1.0 / k

        gap = float((w_val + w_mom).abs().max())
        max_weight_gap = max(max_weight_gap, gap)

        nxt = monthly.index[i + 1]
        daily = panel.close.pct_change(fill_method=None)
        window = daily.loc[(daily.index > date) & (daily.index <= nxt)]
        if window.empty:
            continue
        r_mom = float((window[top].mean(axis=1) - window[bottom].mean(axis=1)).sum())
        r_val = float((window[bottom].mean(axis=1) - window[top].mean(axis=1)).sum())
        max_return_gap = max(max_return_gap, abs(r_val + r_mom))
        rows.append({"date": date, "momentum": r_mom, "value": r_val})

    returns = pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()
    correlation = (
        float(returns["momentum"].corr(returns["value"]))
        if len(returns) > 2
        else np.nan
    )

    return {
        "months": int(len(returns)),
        "max_abs_weight_gap": max_weight_gap,
        "max_abs_return_gap": max_return_gap,
        "return_correlation": correlation,
        "is_identical_up_to_sign": bool(max_weight_gap < 1e-12),
        "returns": returns,
    }


def _constant_predictor_f1(pi: float) -> float:
    """F1 of predicting the majority class for every observation."""
    return 2.0 * pi / (1.0 + pi)


def f1_base_rate_analysis(
    panel: Panel, cfg: Config, recorded_f1: float = 0.948276
) -> dict:
    """Show that V1's recorded F1 is the base-rate score.

    The recorded value implies a positive-class base rate of f1/(2-f1). We then
    measure the actual negative-return rate in the V1 test window and compare the
    constant predictor's score with the recorded one.
    """
    daily = panel.close.pct_change(fill_method=None)
    # V1's value factor is minus momentum, so its sign is inverted momentum's.
    # Build a cheap replica of that factor return: bottom-minus-top quintile.
    monthly = panel.close.resample("ME").last()
    records = []
    for i in range(12, len(monthly) - 1):
        date = monthly.index[i]
        available = monthly.iloc[i].dropna().index
        if len(available) < 50:
            continue
        start = monthly.iloc[i - 12][available]
        end = monthly.iloc[i - 1][available]
        valid = start.notna() & end.notna()
        start, end = start[valid], end[valid]
        if len(start) < 50:
            continue
        score = end / start - 1.0
        k = max(1, int(len(score) * 0.20))
        top = score.nlargest(k).index
        bottom = score.nsmallest(k).index
        nxt = monthly.index[i + 1]
        window = daily.loc[(daily.index > date) & (daily.index <= nxt)]
        if window.empty:
            continue
        records.append(
            {
                "date": date,
                "value_factor": float(
                    (window[bottom].mean(axis=1) - window[top].mean(axis=1)).sum()
                ),
            }
        )

    if not records:
        return {"available": False}

    factor = pd.DataFrame(records).set_index("date")["value_factor"]
    weekly = factor.resample("W-FRI").sum()
    cumulative = (1.0 + weekly).cumprod()
    forward_3m = cumulative.shift(-13) / cumulative - 1.0

    test = forward_3m.loc["2022-01-01":"2024-12-31"].dropna()
    if len(test) < 20:
        return {"available": False}

    negative_share = float((test < 0).mean())
    constant_f1 = _constant_predictor_f1(negative_share)
    implied_pi = recorded_f1 / (2.0 - recorded_f1)

    return {
        "available": True,
        "test_observations": int(len(test)),
        "negative_share": negative_share,
        "positive_share": 1.0 - negative_share,
        "constant_predictor_f1": constant_f1,
        "recorded_f1": recorded_f1,
        "implied_base_rate": implied_pi,
        "constant_f1_at_implied_rate": _constant_predictor_f1(implied_pi),
        "difference_from_recorded": constant_f1 - recorded_f1,
        "effective_independent_blocks": int(np.ceil(len(test) / 13)),
    }


def reproduce_v1(panel: Panel, cfg: Config) -> dict:
    identity = v1_factor_identity(panel, cfg)
    base_rate = f1_base_rate_analysis(panel, cfg)
    identity.pop("returns", None)
    return {
        "identity": identity,
        "base_rate": base_rate,
        "passes": bool(
            identity["max_abs_weight_gap"] < 1e-12
            and abs(identity["return_correlation"] + 1.0) < 1e-9
        ),
    }
