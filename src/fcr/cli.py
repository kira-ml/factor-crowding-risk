"""Command line entry point: ``python -m fcr``."""

from __future__ import annotations

import argparse
import json
import sys

from .config import Config
from .pipeline import run_pipeline
from .report import generate_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fcr",
        description="Crowded Exits: exit risk and capacity in equity factors.",
    )
    parser.add_argument(
        "stage",
        nargs="?",
        default="all",
        choices=["all", "data", "core", "study", "report"],
        help="pipeline stage to run",
    )
    parser.add_argument(
        "--config", type=str, default=None, help="path to a JSON config"
    )
    parser.add_argument(
        "--refresh-data", action="store_true", help="re-download prices"
    )
    parser.add_argument(
        "--skip-study", action="store_true", help="skip the statistical study"
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load(args.config) if args.config else Config()
    cfg.ensure_dirs()

    if args.stage == "data":
        from .data import load_panel

        panel = load_panel(cfg, refresh=args.refresh_data)
        print(json.dumps({"rows": len(panel.close), "tickers": panel.close.shape[1]}))
        return 0

    skip_study = args.skip_study or args.stage in {"core"}
    results = run_pipeline(
        cfg,
        refresh_data=args.refresh_data,
        skip_study=skip_study,
        verbose=not args.quiet,
    )

    if args.stage in {"all", "report"} and results.study is not None:
        path = generate_report(results)
        print(f"report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
