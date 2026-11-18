"""Frozen configuration.

Every parameter that affects a result lives here. No module defines a magic
number. The config is serialisable and hashable so that each run can record the
exact specification that produced it (methodology section 9.2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = ROOT / "outputs"
DOCS_DIR = ROOT / "docs"


@dataclass(frozen=True)
class Config:
    # ---- sample -----------------------------------------------------------
    start: str = "2005-01-01"
    end: str = "2025-12-31"
    max_tickers: int = 900
    universe_size: int = 500
    min_history_days: int = 252
    min_price: float = 5.0
    min_adv: float = 5e6
    adv_window: int = 60
    rebalance_freq: str = "W-FRI"

    # ---- factor construction ---------------------------------------------
    mom_lookback: int = 252
    mom_skip: int = 21
    rev_window: int = 21
    vol_window: int = 252
    beta_window: int = 252
    beta_terciles: int = 3
    decile: float = 0.10
    entry_pct: float = 0.92
    exit_pct: float = 0.82
    min_leg_names: int = 25
    name_cap: float = 0.02
    gross: float = 2.0
    factors: tuple[str, ...] = ("MOM", "STREV", "LOWVOL")

    # ---- fragility --------------------------------------------------------
    corr_window: int = 60
    burn_in: int = 104
    adv_ref_aum: float = 1e9
    participation: float = 0.10
    persist_rebalances: int = 6
    z_clip: float = 4.0
    composite_weights: tuple[float, ...] = (0.25, 0.25, 0.25, 0.25)

    # ---- targets ----------------------------------------------------------
    horizons_weeks: tuple[int, ...] = (4, 13)
    primary_horizon: int = 4

    # ---- capacity ---------------------------------------------------------
    impact_c: float = 0.314
    impact_c_grid: tuple[float, ...] = (0.10, 0.314, 0.50)
    execution_days: int = 10
    execution_days_grid: tuple[int, ...] = (1, 5, 10, 21)
    premium_assumption_grid: tuple[float, ...] = (0.01, 0.02, 0.03, 0.05, 0.075, 0.10)
    spread_bp: float = 3.0
    spread_bp_grid: tuple[float, ...] = (1.0, 3.0, 10.0)
    borrow_bp: float = 50.0
    financing_bp: float = 0.0
    aum_grid: tuple[float, ...] = (1e7, 1e8, 1e9, 5e9, 1e10)
    hurdle: float = 0.50
    hurdle_grid: tuple[float, ...] = (0.25, 0.50, 0.75)
    cost_hurdle_bp_grid: tuple[float, ...] = (50.0, 100.0, 200.0)
    aum_bounds: tuple[float, float] = (1e6, 1e11)

    # ---- inference --------------------------------------------------------
    quantiles: tuple[float, ...] = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90)
    primary_quantile: float = 0.10
    bootstrap_reps: int = 2000
    block_mean: int = 8
    fdr_alpha: float = 0.10
    alpha: float = 0.05
    power: float = 0.80
    seed: int = 20261116

    # ---- decision layer ---------------------------------------------------
    overlay_start_pct: float = 0.60
    overlay_end_pct: float = 0.90
    overlay_floor: float = 0.30
    overlay_cap: float = 1.00
    vol_target: float = 0.10
    vol_scale_cap: float = 1.50
    scaling_cost_bp: float = 5.0
    n_random_overlays: int = 200

    # ---- reporting --------------------------------------------------------
    figure_dpi: int = 160
    max_dropped_frac: float = 0.20

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def replace(self, **kwargs: Any) -> "Config":
        return replace(self, **kwargs)

    def ensure_dirs(self) -> None:
        for path in (DATA_DIR, RAW_DIR, OUT_DIR, DOCS_DIR, DOCS_DIR / "figures"):
            Path(path).mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        if path is None:
            return cls()
        payload = json.loads(Path(path).read_text())
        return cls(**payload)


DEFAULT = Config()
