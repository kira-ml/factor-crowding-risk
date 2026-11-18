"""Pipeline orchestration and run manifest."""

from __future__ import annotations

import json
import platform
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .capacity import Capacity, build_capacity
from .config import OUT_DIR, Config
from .data import Panel, load_panel, panel_hash
from .decision import DecisionResult, run_decision_layer
from .factors import FactorSet, build_factors, weekly_returns
from .fragility import Fragility, build_fragility
from .repro_v1 import reproduce_v1
from .study import StudyResult, run_study
from .universe import Universe, build_universe, coverage_report


@dataclass
class Results:
    cfg: Config
    panel: Panel
    universe: Universe
    factors: FactorSet
    fragility: Fragility
    capacity: Capacity
    study: StudyResult | None = None
    decision: DecisionResult | None = None
    repro: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)

    def run_dir(self) -> Path:
        path = Path(OUT_DIR) / "runs" / self.manifest.get("run_id", "unversioned")
        path.mkdir(parents=True, exist_ok=True)
        return path


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    try:
        return bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        )
    except Exception:
        return True


def _versions() -> dict[str, str]:
    import matplotlib
    import numpy
    import scipy
    import sklearn
    import statsmodels
    import yfinance

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "sklearn": sklearn.__version__,
        "statsmodels": statsmodels.__version__,
        "matplotlib": matplotlib.__version__,
        "yfinance": yfinance.__version__,
    }


def run_pipeline(
    cfg: Config,
    refresh_data: bool = False,
    skip_study: bool = False,
    verbose: bool = True,
) -> Results:
    started = time.time()
    git_dirty_at_start = _git_dirty()
    cfg.ensure_dirs()
    run_id = f"{cfg.hash()}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    if verbose:
        print("=" * 72)
        print("CROWDED EXITS: pipeline")
        print(f"  run_id: {run_id}")
        print("=" * 72)

    if verbose:
        print("\n[1/6] data")
    panel = load_panel(cfg, refresh=refresh_data, verbose=verbose)

    if verbose:
        print("\n[2/6] universe")
    universe = build_universe(panel, cfg)
    coverage = coverage_report(universe, panel)
    if verbose:
        print(
            f"  {len(universe.dates)} rebalance dates, "
            f"mean size {coverage['size'].mean():.0f}, "
            f"min {coverage['size'].min()}"
        )

    if verbose:
        print("\n[3/6] factors")
    factors = build_factors(panel, universe, cfg)
    if verbose:
        print(factors.diagnostics.round(3).to_string())
        print(factors.returns.describe().loc[["mean", "std"]].round(4).to_string())

    if verbose:
        print("\n[4/6] fragility")
    fragility = build_fragility(panel, factors, universe, cfg)
    if verbose:
        print(fragility.coverage.round(3).to_string())

    if verbose:
        print("\n[5/6] capacity")
    weekly = weekly_returns(panel, factors.dates)
    capacity = build_capacity(panel, factors, universe, weekly, cfg)
    if verbose:
        print(capacity.capacity.round(0).to_string())

    results = Results(
        cfg=cfg,
        panel=panel,
        universe=universe,
        factors=factors,
        fragility=fragility,
        capacity=capacity,
    )

    if not skip_study:
        if verbose:
            print("\n[6/6] study and decision layer")
        results.study = run_study(factors, fragility, universe, panel, cfg)
        results.decision = run_decision_layer(factors, fragility, cfg)
    else:
        if verbose:
            print("\n[6/6] study skipped")

    results.repro = reproduce_v1(panel, cfg)

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config": cfg.to_dict(),
        "config_hash": cfg.hash(),
        "git_commit": _git_commit(),
        "git_dirty": git_dirty_at_start,
        "versions": _versions(),
        "panel": {
            "sha256": panel_hash(panel),
            "rows": int(panel.close.shape[0]),
            "tickers": int(panel.close.shape[1]),
            "start": str(panel.dates[0].date()),
            "end": str(panel.dates[-1].date()),
        },
        "universe": {
            "dates": len(universe.dates),
            "mean_size": float(coverage["size"].mean()),
            "min_size": int(coverage["size"].min()),
        },
        "rows": {
            "factors": len(factors.returns),
            "fragility_composite": int(fragility.composite.notna().any(axis=1).sum()),
            "study": len(results.study.dataset) if results.study else 0,
        },
        "elapsed_seconds": round(time.time() - started, 1),
        "repro_passes": bool(results.repro.get("passes", False)),
    }
    results.manifest = manifest
    results.run_dir().joinpath("manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str)
    )

    if verbose:
        print(f"\nmanifest: {results.run_dir() / 'manifest.json'}")
        print(f"elapsed: {manifest['elapsed_seconds']}s")
    return results
