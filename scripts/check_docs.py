"""Check that the README's headline numbers match the generated tables.

Run after a full pipeline:

    python scripts/check_docs.py

The check is intentionally narrow: it covers the numbers a reader is most likely
to quote. The generated report remains the source of truth for everything else.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
README = ROOT / "README.md"


def money(value: float) -> str:
    if not np.isfinite(value):
        return "n/a"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"${value / 1e6:,.0f}M"
    return f"${value:,.0f}"


def main() -> int:
    if not TABLE_DIR.exists() or not README.exists():
        print("README or tables missing; skipping docs check")
        return 0
    text = README.read_text(encoding="utf-8")
    checks: list[str] = []

    primary = pd.read_csv(TABLE_DIR / "primary.csv")
    row = primary[
        (primary["term"] == "composite") & (np.isclose(primary["quantile"], 0.10))
    ].iloc[0]
    checks.extend(
        [
            f"{row['estimate'] * 100:.2f}%",
            f"{row['ci_low'] * 100:.2f}%",
            f"{row['ci_high'] * 100:.2f}%",
        ]
    )
    mde = (1.959964 + 0.841621) * float(row["se"]) * 100
    checks.append(f"{mde:.2f}%")

    h2 = pd.read_csv(TABLE_DIR / "h2.csv")
    full = h2[h2["specification"] == "full_controls"].iloc[0]
    checks.append(f"{full['retention']:.2f}")

    capacity = pd.read_csv(TABLE_DIR / "capacity.csv", index_col=0)
    for factor in ("LOWVOL", "MOM", "STREV"):
        checks.append(money(float(capacity.loc[factor, "cost_100bp"])))

    overlay = pd.read_csv(TABLE_DIR / "overlay_tests.csv")
    es = overlay[overlay["metric"] == "es_5"]
    for value in es["difference"]:
        checks.append(f"{value * 100:.2f}%")

    missing = [value for value in checks if value not in text]
    if missing:
        print("README is missing generated values:")
        for value in missing:
            print("  ", value)
        return 1
    print(f"docs check passed ({len(checks)} headline values)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
