"""Generate the two charts used in the one-page research brief.

All values are read from the generated tables, never hardcoded, so the brief
follows the same source of truth as the report.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
OUT = ROOT / "docs" / "one_pager"

IVORY = "#F7F4EE"
NAVY = "#0E2238"
BRASS = "#A9854F"
BURGUNDY = "#7A2E2E"
MUTED = "#8C9AA6"
GRID = "#D8CFC0"


def style_axes(ax) -> None:
    ax.set_facecolor(IVORY)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#B9AE9D")
        ax.spines[side].set_linewidth(0.5)
    ax.tick_params(colors="#425466", labelsize=6.0, length=2, width=0.4)
    ax.grid(axis="y", color=GRID, linewidth=0.4, alpha=0.8)
    ax.set_axisbelow(True)


def capacity_chart() -> Path:
    data = pd.read_csv(TABLES / "capacity_sensitivity_cost.csv")
    data = data[(data["impact_c"] == 0.314) & (data["spread_bp"] == 3.0)]
    pivot = data.pivot(index="factor", columns="execution_days", values="capacity")
    colors = {"LOWVOL": NAVY, "MOM": BRASS, "STREV": BURGUNDY}
    order = ["LOWVOL", "MOM", "STREV"]

    fig, ax = plt.subplots(figsize=(4.65, 1.42), dpi=300)
    fig.patch.set_facecolor(IVORY)
    style_axes(ax)

    offsets = {"LOWVOL": (-6, 7), "MOM": (6, -8), "STREV": (6, 7)}
    aligns = {"LOWVOL": "right", "MOM": "left", "STREV": "left"}
    for factor in order:
        values = pivot.loc[factor, [1, 5, 10, 21]].to_numpy(dtype=float) / 1e6
        ax.plot(
            [1, 5, 10, 21],
            values,
            color=colors[factor],
            marker="o",
            markersize=2.6,
            linewidth=1.2,
            label=factor,
            zorder=3,
        )
        value = values[2]
        label = f"${value / 1000:.2f}B" if value >= 1000 else f"${value:.0f}M"
        ax.annotate(
            label,
            (10, value),
            textcoords="offset points",
            xytext=offsets[factor],
            ha=aligns[factor],
            fontsize=5.0,
            color=colors[factor],
            fontweight="bold",
        )

    ax.axvline(10, color=BRASS, linewidth=0.6, linestyle=(0, (2, 2)), alpha=0.9)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.9, 25)
    ax.set_xticks([1, 5, 10, 21])
    ax.set_xticklabels(["1", "5", "10", "21"])
    ax.set_xlabel("Execution horizon (days)", fontsize=5.5, color="#425466", labelpad=1)
    ax.set_ylabel("Cost-drag AUM (USD, log)", fontsize=5.5, color="#425466", labelpad=1)
    ax.set_ylim(0.7, 7000)
    ax.set_yticks([1, 100, 1000])
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda x, _: f"${x:,.0f}M" if x < 1000 else f"${x / 1000:.0f}B")
    )
    ax.tick_params(axis="both", labelsize=5.3)
    ax.legend(
        loc="upper left",
        frameon=False,
        fontsize=5.0,
        ncol=3,
        handlelength=1.2,
        columnspacing=0.9,
        borderaxespad=0.0,
    )
    fig.subplots_adjust(left=0.12, right=0.985, top=0.88, bottom=0.17)
    path = OUT / "chart_capacity.png"
    fig.savefig(path, dpi=300, facecolor=IVORY)
    plt.close(fig)
    return path


def overlay_chart() -> Path:
    data = pd.read_csv(TABLES / "overlay_summary.csv")
    data = data[data["strategy"].isin(["vol_managed", "fragility"])]
    pivot = data.pivot(index="factor", columns="strategy", values="es_5")
    tests = pd.read_csv(TABLES / "overlay_tests.csv")
    tests = tests[tests["metric"] == "es_5"].set_index("factor")
    order = ["MOM", "STREV", "LOWVOL"]

    fig, ax = plt.subplots(figsize=(2.35, 1.46), dpi=300)
    fig.patch.set_facecolor(IVORY)
    style_axes(ax)

    for i, factor in enumerate(order):
        vol = float(pivot.loc[factor, "vol_managed"])
        frag = float(pivot.loc[factor, "fragility"])
        ax.plot([vol, frag], [i, i], color="#C9BEAD", linewidth=1.8, zorder=1)
        ax.scatter(vol, i, color=NAVY, s=18, zorder=3)
        ax.scatter(frag, i, color=BRASS, s=18, zorder=3)
        ax.annotate(
            f"{float(tests.loc[factor, 'difference']) * 100:.2f} pp",
            (min(vol, frag) - 0.0012, i),
            ha="right",
            va="center",
            fontsize=5.2,
            color=BURGUNDY,
        )

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=6.0, color=NAVY)
    ax.invert_yaxis()
    ax.set_xlim(-0.066, -0.030)
    ax.set_xticks([-0.06, -0.05, -0.04, -0.03])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x * 100:.0f}%"))
    ax.set_xlabel("True 5% expected shortfall (weekly)", fontsize=5.6, color="#425466", labelpad=1)
    ax.tick_params(axis="x", labelsize=5.3)
    ax.grid(axis="x", color=GRID, linewidth=0.4, alpha=0.8)
    ax.grid(axis="y", visible=False)

    # Compact legend above the plot.
    ax.scatter([], [], color=NAVY, s=12, label="Vol-managed")
    ax.scatter([], [], color=BRASS, s=12, label="Fragility")
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=2,
        frameon=False,
        fontsize=5.0,
        handletextpad=0.3,
        columnspacing=1.0,
        borderaxespad=0.0,
    )
    fig.subplots_adjust(left=0.19, right=0.98, top=0.82, bottom=0.18)
    path = OUT / "chart_overlay_es.png"
    fig.savefig(path, dpi=300, facecolor=IVORY)
    plt.close(fig)
    return path


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print(capacity_chart())
    print(overlay_chart())
