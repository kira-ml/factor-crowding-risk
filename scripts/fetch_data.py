"""Download and validate the price panel.

Run from anywhere:

    python scripts/fetch_data.py

The cache is written under ``data/`` and is intentionally not committed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fcr.config import Config  # noqa: E402
from fcr.data import load_panel, panel_hash, validate  # noqa: E402


def main() -> int:
    cfg = Config()
    started = time.time()
    panel = load_panel(cfg)
    print("FETCH_DONE", round(time.time() - started, 1), "s")
    print(validate(panel))
    print("panel sha256:", panel_hash(panel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
